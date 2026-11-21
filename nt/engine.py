"""Nobody's Town engine: runs the town untouched and records everything.
usage: python3 -m nt.engine <world.json> <days> <out_dir> [--live] [--budget 20] [--workers 8]"""
import datetime as dt, json, os, random, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from .world import World, SLOTS
from .minds import LiveMind, MockMind, Memory
from .referee import Referee, apply_effects
from .llm import LLM, BudgetExceeded
from .fate import Fate
from . import history, econ, law, routine

OVERHEAR_QUIRKS = {"nosy", "gossip", "busybody"}



PASSING = re.compile(r"passing through|passes through|just passing|leaves? (town )?the same day|on (his|her) way\b|mov(es|ed|ing) on|stay(s|ed)? (a|one|two|three|a couple of) nights?|traveling (salesman|through)|for the day|overnight only|one night", re.I)
STAYING = re.compile(r"\b(stays?|settl\w+|moves? (in|here|to town)|to live|takes a room|rents a room|for good|looking for work)\b", re.I)

class Engine:
    def __init__(self, gen, out_dir, mode="mock", budget=20.0, workers=8):
        self.out = out_dir; os.makedirs(out_dir, exist_ok=True)
        self.mode = mode; self.workers = workers if mode == "live" else 1
        self.llm = LLM(mode, budget, log_path=os.path.join(out_dir, "api_calls.jsonl"))
        self.w = World(gen); self.r = random.Random(gen["seed"] * 31 + 7)
        self.mind = LiveMind(self.llm) if mode == "live" else MockMind(gen["seed"])
        self.est = {"plan_calls": 0, "plan_in_chars": 0, "say_calls": 0, "say_in_chars": 0, "sys_chars": 0}
        self.ref = Referee(self.llm, mode, gen["seed"])
        self.fate = Fate(self, gen["seed"]); self.w.fate = self.fate; self.w.engine = self
        from collections import defaultdict
        self.w.minds_memory = defaultdict(Memory, {pid: Memory() for pid in self.w.people})
        self.events, self.dialogues = [], []
        self.ev_f = open(os.path.join(out_dir, "events.jsonl"), "a"); self.dl_f = open(os.path.join(out_dir, "dialogues.jsonl"), "a")
        self.snap_f = open(os.path.join(out_dir, "snapshots.jsonl"), "a")
        self.plans = {}; self.pending = {}  # pid -> list of strings shown in next plan
        self.applications = []  # (applicant pid, company id)
        import threading; self._lock = threading.RLock()
        self._seed_memories()

    # ---------------------------------------------------------------- recording
    def ev(self, kind, actors=(), text="", importance=3, public=False, place=None, data=None, sensitive=False):
        with self._lock:
            return self._ev(kind, actors, text, importance, public, place, data, sensitive)

    def _ev(self, kind, actors, text, importance, public, place, data, sensitive):
        w = self.w
        e = {"id": len(self.events) + 1, "day": w.day, "slot": SLOTS[w.slot], "date": w.date_str, "kind": kind, "actors": list(actors), "place": place,
             "text": text, "importance": importance, "public": public, "sensitive": sensitive, "data": data or {}}
        self.events.append(e); self.ev_f.write(json.dumps(e) + "\n"); self.ev_f.flush()
        if kind == "engine_warning": return e
        if kind != "conversation" and not (data or {}).get("no_memory"):  # talkers remember the talk itself; world-step events give each person their own version
            for a in actors:
                if a in w.minds_memory: w.minds_memory[a].add(w.day, w.slot, text, importance)
        if place:  # witnesses
            for p in w.living():
                if p["id"] not in actors and p["location"] == place: w.minds_memory[p["id"]].add(w.day, w.slot, "I saw: " + text, max(1, importance - 1))
        if public:  # word spreads around a small town, in plain words (never the engine's damage figures)
            said = (data or {}).get("said") or text
            for p in w.living():
                if p["id"] not in actors and self.r.random() < min(0.95, 0.35 + importance / 15): w.minds_memory[p["id"]].add(w.day, w.slot, "I heard: " + said, max(1, importance - 2))
        return e

    def _seed_memories(self):
        w = self.w
        for p in w.people.values():
            m = w.minds_memory[p["id"]]
            for l in w.gen["history_links"]:
                if p["household"] in l["between"] and p["age"] >= 14: m.add(-1, 0, l["_text"], 6)
            if p.get("secret"): m.add(-1, 0, f"(private) I {p['secret']}.", 7)
        off = w.town["offices"]; ago = w.town.get("elected_days_ago", 0)
        runs = f"{w.name(off['mayor'])} is the mayor" + (f"; {', '.join(w.name(i) for i in off['council'])} sit on the council" if off["council"] else "") + "." if off["mayor"] else ""
        if runs:
            for p in w.people.values():
                if p["age"] >= 14: w.minds_memory[p["id"]].add(-1, 0, runs)
        when = "a few weeks ago" if ago < 45 else f"about {round(ago / 30)} months ago" if ago < 330 else "a little over a year ago" if ago < 540 else "nearly two years ago"
        for pid in [off["mayor"]] + off["council"]:
            if pid: w.minds_memory[pid].add(-1, 0, f"I was elected to the town {'mayor' if pid == off['mayor'] else 'council'}'s seat {when}.", 6)

    # ---------------------------------------------------------------- one day
    def is_lived(self):
        """Residents' minds 'live' Sundays, election days and about two other days a week (dice). The world runs every day.
        Like a documentary, we only watch some days; nothing about the dice favors drama."""
        w = self.w
        if w.day == 0 or w.date.weekday() == 6: return True
        if any(e["day"] == w.day for e in w.town["elections"]): return True
        if any(pl.get("kind") == "event" for pl in w.places.values()): return True  # while something is on in town, we watch
        return self.r.random() < 2 / 6

    def world_day(self):
        """A day the world runs without the residents' minds: physics, money, life and death, events. Everyone stays home."""
        w = self.w; w.slot = 0
        if w.season != w.weather["season"]: w.roll_season(self.ev)
        w.outside_day(self.ev); w.roll_day_weather(self.ev); w.economy_day(self.ev); self.money_calendar(); w.life_day(self.ev)
        warming = getattr(self, "warming", False)  # TEST-only fast-forward: rules only, no world step, no threads (never set on the official town)
        if not warming: self.fate.daily(self.ev)
        self.election_calendar(); self.books_note(); self.newcomers()
        for p in w.living(): p["location"] = w.households[p["household"]]["place"]
        for si in range(4):
            w.slot = si; self.needs_tick()
            if si == 3: self.night()
        if not warming: self.fate.step_threads(self.ev, weekly=w.date.weekday() == 6)
        self.skipped = getattr(self, "skipped", 0) + 1
        self.snap_f.write(json.dumps(w.snapshot()) + "\n"); self.snap_f.flush()
        w.day += 1; w.date += dt.timedelta(days=1)

    def sunday_reflections(self, actors):
        """Weekly reflection (approved Nov 18): each resident sums up their own week in their own words; it becomes a memory they rate like any other."""
        w = self.w
        def one(p): return p["id"], self.mind.reflect(w, p, w.minds_memory[p["id"]].since(w.day - 7))
        if self.workers > 1:
            with ThreadPoolExecutor(self.workers) as ex: res = list(ex.map(one, actors))
        else: res = [one(p) for p in actors]
        for pid, refl in res:
            for t in refl: w.minds_memory[pid].add(w.day, 0, f"(looking back on the week) {t}")
            if refl: self.ev("reflection", actors=[pid], text=f"{w.name(pid)} looks back on the week: " + " / ".join(refl), importance=2)

    def run_day(self, lived=None):
        if lived is None: lived = self.is_lived() if getattr(self, "compress", False) else True
        if not lived: return self.world_day()
        w = self.w; w.slot = 0
        if w.day == 0 or w.season != w.weather["season"]: w.roll_season(self.ev)
        w.outside_day(self.ev); w.roll_day_weather(self.ev); w.economy_day(self.ev); self.money_calendar(); w.life_day(self.ev); self.fate.daily(self.ev)
        self.election_calendar()
        self.books_note()
        self.newcomers()
        actors = [p for p in w.living() if p["age"] >= 12]
        kids = [p for p in w.living() if p["age"] < 12]
        for p in actors:  # mood of the day: dice, nudged by how they've actually been
            low = p["needs"]["mood"] < 30 or p["needs"]["energy"] < 25
            p["mood_today"] = self.r.choices(["good", "ordinary", "sour", "tired"], [22, 58, 14 + (12 if low else 0), 6 + (8 if low else 0)])[0]
        if w.date.weekday() == 6 and w.day > 0: self.sunday_reflections(actors)
        self.plans = {}; self.gap_before_today = getattr(self, "skipped", 0); self.skipped = 0
        if not self.gap_before_today or not getattr(self, "did", None): self.yesterday = getattr(self, "did", {})
        self.did = {}
        def do_plan(p):
            notes = self.pending.pop(p["id"], [])
            y = self.yesterday.get(p["id"])
            gap = getattr(self, "gap_before_today", 0)
            if y: notes = [(f"The last day you remember clearly ({gap + 1} days ago), you: " if gap else "Yesterday you: ") + "; ".join(f"{s}: {t}" for s, t in y) + "."] + notes
            if gap: notes = [f"{gap} ordinary days have gone by since then: work, chores, meals, sleep. Anything that happened in them is in your memories."] + notes
            wk = self.week_talks(p)  # people know when they've seen someone a lot (memory, not a nudge)
            if wk: notes = [f"This past week you've talked with: {wk}."] + notes
            tried = (getattr(self, "attempt_hist", None) or {}).get(p["id"])  # their own last few attempts and how they went (memory, not a nudge; Nov 18)
            if tried: notes = notes + ["What you've tried lately, and how it went: " + " | ".join(tried)]
            extra = "\n".join(notes)
            ctx = [w.name(i) for i in p["rel"] if i in w.people] + [w.town["name"]]
            mm = w.minds_memory[p["id"]]; new = mm.unrated()
            mem = mm.recall(w.day, ctx, exclude=new)
            if self.mode != "live": self._estimate("plan", w, p, mem, extra)
            return p["id"], self.mind.plan(w, p, mem, extra, new)
        if self.workers > 1:
            with ThreadPoolExecutor(self.workers) as ex: results = list(ex.map(do_plan, actors))
        else: results = [do_plan(p) for p in actors]
        for pid, plan in results:
            self.plans[pid] = plan; p = w.people[pid]
            w.minds_memory[pid].rate(plan.get("rate") if isinstance(plan.get("rate"), dict) else {})
            for refl in (plan.get("thoughts") or plan.get("reflections") or [])[:3]: w.minds_memory[pid].add(w.day, 0, f"(thought) {refl}")
            for nm, d in (plan.get("feelings") or {}).items():
                q = w.by_name(nm)
                if q and q["id"] != pid:
                    r = p["rel"].setdefault(q["id"], {"affinity": 0, "trust": 30, "tags": []})
                    try: r["affinity"] = max(-100, min(100, r["affinity"] + max(-20, min(20, int(d)))))
                    except (TypeError, ValueError): pass
        for si, sname in enumerate(SLOTS):
            w.slot = si; convs = []
            for p in kids: self.kid_routine(p, sname)
            todo = []
            for p in actors:
                if not p["alive"] or p["offtown"]: continue
                act = next((a for a in self.plans.get(p["id"], {}).get("slots", []) if isinstance(a, dict) and a.get("slot") == sname), None)
                if not act: act = {"do": "sleep" if sname == "night" else "home", "place": w.households[p["household"]]["place"]}
                if p["illness"] and p["illness"]["serious"] or p["injury"] > 20: act = {"do": "home", "place": w.households[p["household"]]["place"], "detail": "laid up"}
                pl = act.get("place")
                if pl in w.places: p["location"] = pl
                ep = w.places.get(pl) or {}
                if ep.get("kind") == "event" and p.get("went_to") != pl + str(w.day):  # went to the show: pay at the gate, once a day
                    p["went_to"] = pl + str(w.day); price = float(ep.get("price") or 0); hh = w.households[p["household"]]
                    if price and hh["savings"] >= price: hh["savings"] -= price
                    w.minds_memory[p["id"]].add(w.day, w.slot, f"I went to {ep['name']}.")
                todo.append((p, act))
            # free-form attempts go to the referee in parallel (everyone has already moved, so "who's here" is right)
            ref_jobs = [(p, a) for p, a in todo if (a.get("do") or "").lower() in ("build", "start_business", "attempt", "write_letter", "sell") and a.get("detail")
                        and not routine.match(w, p, a.get("do"), a.get("detail"))]  # everyday doings are plain rules, not referee calls (Nov 18)
            rulings = {}
            if ref_jobs and self.workers > 1:
                def job(pa):
                    p, a = pa
                    try: amt = float(a.get("amount")) if a.get("amount") is not None else None
                    except (TypeError, ValueError): amt = None
                    d0 = a["do"].lower(); det = a["detail"][:400]
                    if d0 == "sell": d0, det = "attempt", "sell " + det
                    return p["id"], self.rule_for(p, d0, det, amt)
                with ThreadPoolExecutor(self.workers) as ex: rulings = dict(ex.map(job, ref_jobs))
            for p, act in todo:
                c = self.do_action(p, act, rulings.get(p["id"]))
                if c: convs.append(c)
            convs += self.chance_encounters(convs)
            self.run_convs(convs)
            self.needs_tick()
            if sname == "night": self.night()
        self.fate.step_threads(self.ev, weekly=w.date.weekday() == 6)
        self.snap_f.write(json.dumps(w.snapshot()) + "\n"); self.snap_f.flush()
        w.day += 1; w.date += dt.timedelta(days=1)

    def money_calendar(self):
        """Loan payments, interest, town salaries and each family's look at the books on the 1st; owners' weekly books and the Sunday paper."""
        w = self.w
        if w.date.day == 1: econ.monthly(self, self.ev); law.monthly(self, self.ev)
        if w.date.weekday() == 6: econ.weekly(self, self.ev)

    def kid_routine(self, p, sname):
        w = self.w; home = w.households[p["household"]]["place"]
        if sname in ("morning", "midday") and w.date.weekday() < 5 and 6 <= p["age"]: p["location"] = "school"
        elif sname == "midday" and self.r.random() < 0.3: p["location"] = self.r.choice([k for k in w.places if k.startswith("lm_")]); w.discovery_roll(p, "explore", self.ev) if self.r.random() < 0.3 else None
        else: p["location"] = home

    def newcomers(self):
        w = self.w
        if not w.flags.pop("newcomer_pending", False): return
        from .generator import person, SURNAMES
        used = {h["surname"] for h in w.households.values()} | {p["name"].split()[-1] for p in w.people.values()}
        free = [s for s in SURNAMES if s not in used]
        if not free: return
        sn = self.r.choice(free); hid = max(w.households) + 1
        w.households[hid] = {"id": hid, "surname": sn, "kind": "newcomer", "members": [], "savings": int(self.r.uniform(80, 900)), "debt": 0, "home": "rented",
                             "place": f"home_{hid}", "monthly_housing": 38, "withhold_tax": False, "has_tv": False}
        w.places[f"home_{hid}"] = {"name": f"the {sn} place", "kind": "home", "household": hid, "x": 0, "condition": 0.8}
        p = person(self.r, sn, self.r.randint(19, 45), self.r.random() < 0.65, w.date.year, "single", w.first_names()); p["job"] = "looking for work"
        pid = w.add_person(p, hid); w.minds_memory[pid] = Memory(); w.minds_memory[pid].add(w.day, 0, f"I just arrived in {w.town['name']} looking for work.", 6)
        self.ev("newcomer", actors=[pid], text=f"A newcomer, {p['name']}, arrives in town looking for work.", importance=6, public=True)

    # ---------------------------------------------------------------- actions
    def week_talks(self, p):
        c = {}
        for d in reversed(self.dialogues):
            if d["day"] < self.w.day - 7: break
            if p["id"] in (d["a"], d["b"]):
                o = d["b"] if d["a"] == p["id"] else d["a"]; c[o] = c.get(o, 0) + 1
        top = sorted(c.items(), key=lambda kv: -kv[1])[:5]
        return "; ".join(f"{self.w.name(o)} ({n} time{'s' if n > 1 else ''})" for o, n in top)

    def chance_encounters(self, planned):
        """Dice: people who end up in the same place may strike up a chat with no agenda (about half of all talk in a real town).
        Public places roll more often than home; nobody is in two conversations at once."""
        w = self.w; busy = {x for c in planned for x in (c[0]["id"], c[1]["id"])}; out = []
        if w.slot == 3: return out  # night: people are home and mostly asleep
        by_place = {}
        for p in w.living():
            if p["age"] >= 12 and not p["offtown"] and p["id"] not in busy and p["alive"]: by_place.setdefault(p["location"], []).append(p)
        for place, ps in by_place.items():
            home = str(place).startswith("home_")
            for _ in range(2 if not home else 1):
                if len(ps) < 2 or self.r.random() > (0.12 if home else 0.35): break
                a, b = self.r.sample(ps, 2); ps.remove(a); ps.remove(b)
                out.append((a, b, "", "in person", "chance"))
        return out

    def mind_seed(self, p):
        """What's on this person's mind today: drawn at random from THEIR OWN life (an interest, something recent, a family member). Never a topic of ours."""
        w = self.w; opts = []
        if p.get("interests"): opts += [f"{i}" for i in p["interests"]]
        rec = w.minds_memory[p["id"]].recent(w.day, 3)
        opts += [m["text"].replace("I heard: ", "something you heard: ").replace("(thought) ", "") for m in rec[-6:] if not m["text"].startswith(("I overheard", "I listened in", "I saw:"))]
        fam = [w.people[i] for i in w.households[p["household"]]["members"] if i != p["id"] and w.people[i]["alive"]]
        rel_word = lambda q: {"wife": "your wife", "husband": "your husband", "child": "your son" if q["sex"] == "male" else "your daughter"}.get(q["role"], "")
        opts += [f"{rel_word(q)} {q['name'].split()[0]}".strip() for q in fam]
        return self.r.choice(opts) if opts else None

    def note_did(self, p, text):
        self.did.setdefault(p["id"], []).append((SLOTS[self.w.slot], text[:160]))

    def do_action(self, p, a, ruling=None):
        w = self.w; do = (a.get("do") or "home").lower(); tgt = a.get("target"); detail = (a.get("detail") or "")[:400]
        if do not in ("sleep",): self.note_did(p, f"{do.replace('_', ' ')}" + (f" ({a.get('target')})" if isinstance(a.get("target"), str) and a.get("target") else "") + (f": {detail}" if detail and do != "home" else ""))
        q = w.by_name(tgt) if isinstance(tgt, str) else None
        h = w.households[p["household"]]
        amt = a.get("amount")
        try: amt = float(amt) if amt is not None else None
        except (TypeError, ValueError): amt = None
        place = p["location"]
        if do == "school": p["location"] = "school"
        elif do in ("work",):
            p["needs"]["energy"] -= 12
        elif do in ("home", "sleep"):
            p["needs"]["energy"] = min(100, p["needs"]["energy"] + (40 if do == "sleep" else 10))
        elif do == "eat_at_diner":
            closed = econ.is_closed(w, "diner")
            if closed: w.minds_memory[p["id"]].add(w.day, w.slot, f"The diner is closed by town law {closed['id']}."); return None
            meal = round(w.shops["diner"]["meal"] * history.price_index(w.date.year), 2)  # the price the owner set
            p["location"] = "diner"; dh = w.shops["diner"]["owner_h"]
            if dh != h["id"]:
                h["savings"] -= meal
                if dh in w.households: w.households[dh]["savings"] += meal; w.earned(w.households[dh], meal); w.shops["diner"]["meals"] += 1
            p["needs"]["hunger"] = 0; p["needs"]["social"] += 10
        elif do == "shop":
            closed = econ.is_closed(w, "store")
            if closed: w.minds_memory[p["id"]].add(w.day, w.slot, f"The general store is closed by town law {closed['id']}."); return None
            if econ.match_good(detail) and econ.match_good(detail) != "house":
                did, _ok = econ.buy(self, p, detail, amt, "store"); self.did[p["id"]][-1] = (SLOTS[w.slot], did); p["location"] = "store"; return None
            p["location"] = "store"; spend = min(max(1, amt or 3), max(0, h["savings"])); h["savings"] -= spend
            sh = w.shops["store"]["owner_h"]; st = w.shops["store"]
            if sh in w.households and sh != h["id"]:
                m = spend * (1 - econ.WHOLESALE / st["level"]); w.households[sh]["savings"] += m; w.earned(w.households[sh], m); st["week"] += m; st["week_sales"] += spend
        elif do in ("talk", "court", "ask_loan", "propose_marriage", "end_relationship") and q and q["id"] != p["id"]:
            if q["offtown"] or not q["alive"]: w.minds_memory[p["id"]].add(w.day, w.slot, f"I wanted to talk to {q['name']} but they're not around.", 2); return None
            if q["location"] != p["location"]:
                # you go find them if they're in town and awake; at night only at home
                if w.slot == 3 and q["location"] != w.households[q["household"]]["place"]: return None
                p["location"] = q["location"]
            purpose = {"court": f"court {q['name']}: {detail}", "ask_loan": f"ask {q['name']} for a loan of ${amt or '?'}: {detail}",
                       "propose_marriage": f"ask {q['name']} to marry you: {detail}", "end_relationship": f"end things with {q['name']}: {detail}"}.get(do, detail)
            return (p, q, purpose, "in person", do)
        elif do == "phone" and q and q["id"] != p["id"] and not q["offtown"] and q["alive"]:
            return (p, q, detail, "phone", do)
        elif do == "repair":  # their own choice to fix up the house, at the price they choose
            spent = w.repair(h, p, amt, self.ev, detail[:80])
            if not spent: w.minds_memory[p["id"]].add(w.day, w.slot, "There was nothing to repair, or no money to do it with." if h.get("repairs_needed", 0) <= 0 or h["savings"] <= 0 else "The repair didn't happen.")
            else: self.did[p["id"]][-1] = (SLOTS[w.slot], f"repaired the house (${int(spent)})")
        elif do == "chores":  # ordinary work around the house, yard or errands: no referee needed
            p["needs"]["energy"] -= 6
        elif do == "side_work" and p["age"] >= 12:  # odd jobs / extra hours: modest 1950s pay, by dice
            pay = round(self.r.uniform(1.5, 7.0) * history.wage_index(w.date.year) * (0.5 if p["age"] < 16 else 1.0) * (0.6 if p["needs"]["energy"] < 25 else 1.0), 2)
            h["savings"] += pay; p["needs"]["energy"] -= 14
            w.minds_memory[p["id"]].add(w.day, w.slot, f"I earned ${pay:.2f} doing {detail or 'odd jobs'}.")
            self.did[p["id"]][-1] = (SLOTS[w.slot], f"side work ({detail[:60] or 'odd jobs'}), earned ${pay:.2f}")
        elif do in ("sell", "write_letter", "attempt") and detail and routine.match(w, p, do, detail):
            return self.everyday(p, do, detail, amt)
        elif do == "sell" and detail:
            do = "attempt"; detail = "sell " + detail
            ru = ruling if ruling is not None else self.rule_for(p, do, detail, amt)
            return self._apply_ruling(p, do, detail, ru, place)
        elif do in ("dig", "explore", "fish", "farm"):
            p["needs"]["energy"] -= 10; w.discovery_roll(p, do, self.ev)
        elif do in ("pay", "give", "lend") and q and amt and amt > 0 and q["household"] == p["household"]:
            w.minds_memory[p["id"]].add(w.day, w.slot, f"{q['name']} and I share the same household money.")
        elif do in ("pay", "give", "lend") and q and amt and amt > 0:
            if amt > max(0, h["savings"]): w.minds_memory[p["id"]].add(w.day, w.slot, f"I meant to {do} {q['name']} ${int(amt)}, but we only had ${int(max(0, h['savings']))}.")
            amt = min(amt, max(0, h["savings"]))
            if amt > 0:
                h["savings"] -= amt; w.households[q["household"]]["savings"] += amt
                if do == "lend": h.setdefault("loans_out", []).append({"to": q["id"], "amount": amt, "day": w.day})
                self.did[p["id"]][-1] = (SLOTS[w.slot], f"{'paid' if do == 'pay' else 'gave' if do == 'give' else 'lent'} {q['name']} ${int(amt)}")  # yesterday = what happened, not the plan
                self.ev(do, actors=[p["id"], q["id"]], text=f"{p['name']} {do}s {q['name']} ${int(amt)}" + (f" ({detail})" if detail else "") + ".", importance=5, place=place)
        elif do == "buy" and detail:
            did, handled = econ.buy(self, p, detail, amt, a.get("place") or place)
            if not handled:  # not something sold off a shelf or a lot: the referee rules on it like any attempt
                do, detail = "attempt", "buy " + detail
                return self._apply_ruling(p, do, detail, ruling if ruling is not None else self.rule_for(p, do, detail, amt), place)
            self.did[p["id"]][-1] = (SLOTS[w.slot], did)
        elif do == "shop_at":
            where = "county seat" if re.search(r"county|seat|town over|city|elsewhere|a&p|supermarket", detail.lower()) else "store"
            if h.get("groceries_at", "store") != where:
                h["groceries_at"] = where
                for i in h["members"]:
                    if w.people[i]["alive"] and w.people[i]["age"] >= 18: w.minds_memory[i].add(w.day, w.slot, f"From now on we buy our groceries {'in the county seat' if where != 'store' else 'at the general store'}.")
                self.ev("shop_choice", actors=[p["id"]], text=f"The {h['surname']} household starts buying its groceries {'in the county seat' if where != 'store' else 'at the general store'}.", importance=3)
            self.did[p["id"]][-1] = (SLOTS[w.slot], f"decided we'd buy groceries {'in the county seat' if where != 'store' else 'at the general store'}")
        elif do == "set_price":
            r = econ.set_price(self, p, a.get("place"), amt, detail)
            if r: self.did[p["id"]][-1] = (SLOTS[w.slot], r)
        elif do == "set_wage":
            r = econ.set_wage(self, p, q, amt, detail)
            if r: self.did[p["id"]][-1] = (SLOTS[w.slot], r)
        elif do == "bank_loan":
            banks = econ.local_banks(w); tl = (str(tgt or "") + " " + detail).lower()
            b = next((x for x in banks if x["name"].lower() in tl or w.name(x["owner"]).lower() in tl or (q and q["id"] == x["owner"])), None)
            r = econ.local_bank_apply(self, p, b, amt, detail) if b else econ.county_bank(self, p, amt, detail)
            if r: self.did[p["id"]][-1] = (SLOTS[w.slot], r)
        elif do in ("approve_loan", "deny_loan"):
            r = econ.decide_application(self, p, q, do == "approve_loan", amt, detail)
            if r: self.did[p["id"]][-1] = (SLOTS[w.slot], r)
        elif do in ("deposit", "withdraw"):
            r = econ.deposit(self, p, amt, str(tgt or "") + " " + detail, out=do == "withdraw")
            if r: self.did[p["id"]][-1] = (SLOTS[w.slot], r)
        elif do == "enforce":
            r = law.enforce(self, p, q, detail)
            if r: self.did[p["id"]][-1] = (SLOTS[w.slot], r)
        elif do == "declare_candidacy":
            self.declare(p, detail)
        elif do == "vote":
            self.vote(p, tgt, detail)
        elif do == "propose_measure" and detail:
            mid = f"M{len(w.town['motions']) + 1}"
            w.town["motions"].append({"id": mid, "text": detail, "by": p["id"], "day": w.day, "status": "open", "votes": {}})
            self.ev("measure_proposed", actors=[p["id"]], text=f"{p['name']} proposes measure {mid}: \"{detail}\"", importance=6, public=True)
        elif do == "apply_job" and q and econ.shop_of(w, q) and not self.company_of(q):
            k = econ.shop_of(w, q); nm = "the diner" if k == "diner" else "the general store"
            self.pending.setdefault(q["id"], []).append(f"{p['name']} has asked you for work at {nm}. (Hire them, turn them down, or leave it: your call.)")
            self._ask_job(p, q["id"], nm)
            self.ev("job_application", actors=[p["id"], q["id"]], text=f"{p['name']} asks {q['name']} for work at {nm}.", importance=4)
        elif do == "apply_job":
            co = self.company_of(q) if q else w.companies.get("co1")
            if co and p["id"] not in co["employees"]:
                self.applications.append((p["id"], co["id"])); self.pending.setdefault(co["owner"], []).append(f"{p['name']} has asked you for a job at {co['name']}. (Hire them, turn them down, or leave it: your call.)")
                self._ask_job(p, co["owner"], co["name"])
                self.ev("job_application", actors=[p["id"], co["owner"]], text=f"{p['name']} asks {w.name(co['owner'])} for a job at {co['name']}.", importance=4)
        elif do == "turn_down" and q:
            # the boss says no: the person who asked hears it (Nov 20: in North Lake, people asked 33 times and never heard an answer)
            asks = [a for a in getattr(self, "job_asks", []) if a["who"] == q["id"] and a["boss"] == p["id"]]
            if asks:
                for a in asks: self.job_asks.remove(a)
                self.pending.setdefault(q["id"], []).append(f"{p['name']} told you there's no work for you at {asks[-1]['where']} right now." + (f" ({detail})" if detail else ""))
                self.ev("job_refused", actors=[p["id"], q["id"]], text=f"{p['name']} tells {q['name']} there's no work for them at {asks[-1]['where']}.", importance=4)
        elif do in ("hire", "fire") and q and not self.company_of(p) and econ.shop_of(w, p):
            k = econ.shop_of(w, p)
            if do == "hire":
                r = econ.shop_hire(self, p, q, k, amt)
                if r: self.did[p["id"]][-1] = (SLOTS[w.slot], r)
            elif q.get("shop_job") == k:
                econ.shop_leave(w, q); q["job"] = "out of work"
                self.ev("fired", actors=[p["id"], q["id"]], text=f"{p['name']} lets {q['name']} go from {'the diner' if k == 'diner' else 'the general store'}." + (f" ({detail})" if detail else ""), importance=7, public=True)
        elif do in ("hire", "fire") and q:
            co = self.company_of(p)
            if co:
                if do == "hire" and q["id"] not in co["employees"] and q["age"] >= 14:
                    if q.get("employer") and q["employer"] in w.companies and q["id"] in w.companies[q["employer"]]["employees"]: w.companies[q["employer"]]["employees"].remove(q["id"])
                    econ.shop_leave(w, q); co["employees"].append(q["id"]); q["employer"] = co["id"]; q["job"] = f"works at {co['name']}"
                    if amt and amt > 0: q["wage_day"] = round(max(amt / 5.5, econ.min_wage_day(w, co)), 3)
                    self.ev("hired", actors=[p["id"], q["id"]], text=f"{p['name']} hires {q['name']} at {co['name']}.", importance=6, public=True)
                    self.job_asks = [a for a in getattr(self, "job_asks", []) if a["who"] != q["id"]]
                elif do == "fire" and q["id"] in co["employees"]:
                    w.unemployment_claim(co, [q["id"]], firm_size=len(co["employees"]))
                    co["employees"].remove(q["id"]); q["employer"] = None; q["job"] = "out of work"
                    self.ev("fired", actors=[p["id"], q["id"]], text=f"{p['name']} fires {q['name']} from {co['name']}." + (f" ({detail})" if detail else ""), importance=8, public=True)
        elif do == "quit_job" and p.get("shop_job"):
            k = p["shop_job"]; econ.shop_leave(w, p); p["job"] = "out of work"
            boss = next((x["id"] for x in econ.shop_runners(w, k)), None)
            self.ev("quit", actors=[p["id"]] + ([boss] if boss else []), text=f"{p['name']} quits {'the diner' if k == 'diner' else 'the general store'}.", importance=6, public=True)
        elif do == "quit_job" and p.get("employer"):
            co = w.companies[p["employer"]]
            if p["id"] in co["employees"]: co["employees"].remove(p["id"])
            p["employer"] = None; p.pop("wage_day", None); p["job"] = "out of work"; self.ev("quit", actors=[p["id"], co["owner"]], text=f"{p['name']} quits {co['name']}.", importance=6, public=True)
        elif do == "trip":  # fix 5 (season break): away for a while, then home; job and home kept
            try: days = int(amt) if amt else 3
            except (TypeError, ValueError): days = 3
            w.trip(p, detail or "visit kin", days, self.ev)
        elif do == "leave_town":
            kind = "hollywood" if "hollywood" in detail.lower() else "college" if "college" in detail.lower() else "army" if "army" in detail.lower() or "enlist" in detail.lower() else "city"
            w.leave_town(p, detail or "the city", self.ev, kind=kind)
        elif do in ("build", "start_business", "attempt", "write_letter") and detail:
            ru = ruling if ruling is not None else self.rule_for(p, do, detail, amt)
            return self._apply_ruling(p, do, detail, ru, place)
        return None

    def everyday(self, p, do, detail, amt):
        """An ordinary doing handled by plain rules (routine.py): no referee call, nothing invented."""
        kind = routine.match(self.w, p, do, detail)
        did = routine.run(self, p, do, detail, amt, kind)
        if isinstance(did, tuple):  # a conversation with one neighbor
            return (p, did[1], detail, "in person", "talk")
        if did:
            self.did[p["id"]][-1] = (SLOTS[self.w.slot], did)
            self.ev("routine", actors=[p["id"]], text=f"{p['name']}: {did}", importance=1, data={"no_memory": True, "kind": kind})
        return None

    def _apply_ruling(self, p, do, detail, ru, place):
        w = self.w
        if True:
            self.ev("attempt", actors=[p["id"]], text=f"{p['name']} tries to {do.replace('_', ' ')}: {detail}", importance=4, data={"ruling": ru})
            hist = getattr(self, "attempt_hist", None)
            if hist is None: hist = self.attempt_hist = {}
            hist.setdefault(p["id"], []).append(f"{w.date_str}: tried to {do.replace('_', ' ')}: {detail[:160]} -> {str(ru.get('outcome', ''))[:160]}"); hist[p["id"]] = hist[p["id"]][-3:]
            if ru.get("needs_consent_from"):
                q2 = w.by_name(ru["needs_consent_from"])
                if q2 and q2["alive"] and not q2["offtown"]:
                    return (p, q2, f"get {q2['name']} to go along with this: {detail}", "in person", "attempt")
            if ru.get("possible"):
                apply_effects(w, ru.get("effects"), self.ev, p)
                vis = ru.get("visibility", "private")
                if ru.get("breaks"): law.record_breach(self, p, ru["breaks"] if isinstance(ru["breaks"], list) else [ru["breaks"]], ru.get("outcome", ""), vis)
                self.ev("outcome", actors=[p["id"]], text=ru.get("outcome", ""), importance=int(ru.get("importance", 4) or 4), public=vis == "public", place=place if vis == "witnessed" else None)
            else:
                w.minds_memory[p["id"]].add(w.day, w.slot, f"It didn't work: {ru.get('outcome', '')}", 4)
        return None

    def rule_for(self, p, do, detail, amt):
        here = [x["name"] for x in self.w.living() if x["location"] == p["location"] and x["id"] != p["id"]]
        recent = (getattr(self, "attempt_hist", None) or {}).get(p["id"], [])
        return self.ref.rule(self.w, p, f"{do.replace('_', ' ')}: {detail}" + (f" (budget ${int(amt)})" if amt else ""), here, recent)

    def company_of(self, p):
        if not p: return None
        return next((c for c in self.w.companies.values() if c["owner"] == p["id"]), None)

    # ---------------------------------------------------------------- conversations (+ party line + overhearing)
    def converse(self, a, b, purpose, medium, kind):
        res = self.talk(a, b, purpose, medium, kind)
        if res: self.apply_talk(a, b, purpose, medium, kind, *res)

    def talk(self, a, b, purpose, medium, kind):
        w = self.w
        if not (a["alive"] and b["alive"]) or a["offtown"] or b["offtown"]: return None
        transcript = []; asides = []; speakers = [a, b]; deal_log = []
        seeds = {a["id"]: self.mind_seed(a), b["id"]: self.mind_seed(b)} if kind == "chance" else {}
        ctx_a = [b["name"], b["name"].split()[0]]; ctx_b = [a["name"], a["name"].split()[0]]
        prev = next((d for d in reversed(self.dialogues) if {d["a"], d["b"]} == {a["id"], b["id"]} and d["day"] < w.day), None)
        last = (f"The last time you two talked ({prev['date']}): " + " / ".join(f"{s.split()[0]}: {t[:120]}" for s, t in prev["lines"][-3:])) if prev else None
        for turn in range(8):
            sp, other = speakers[turn % 2], speakers[(turn + 1) % 2]
            mem = w.minds_memory[sp["id"]].recall(w.day, (ctx_a if sp is a else ctx_b) + purpose.split()[:10], k=10)
            if self.mode != "live": self._estimate("say", w, sp, mem, "", transcript)
            out = self.mind.say(w, sp, other, transcript, mem, purpose if sp is a else "", seeds.get(sp["id"]), kind == "chance", last=last)
            line = (out.get("say") or "").strip()[:500]
            if line:
                transcript.append((sp["name"], line))
                asides.append((out.get("aside") or "").strip()[:300])
            deal = out.get("deal")
            if isinstance(deal, dict) and deal.get("type"): deal_log.append((sp, other, deal))
            if out.get("end") and turn >= 1: break
        if not transcript: return None
        return transcript, deal_log, asides

    def apply_talk(self, a, b, purpose, medium, kind, transcript, deal_log, asides=()):
        w = self.w
        d = {"day": w.day, "slot": SLOTS[w.slot], "date": w.date_str, "a": a["id"], "b": b["id"], "medium": medium, "kind": kind, "place": a["location"], "purpose": purpose,
             "lines": transcript, "asides": list(asides), "deals": [{"by": s["id"], "to": o["id"], **dl} for s, o, dl in deal_log]}
        # one commitment per person per conversation: if someone restates a promise, keep only their final wording
        last = {}
        for s, o, dl in deal_log: last[(s["id"], o["id"], dl.get("type") in ("promise", "agree"))] = (s, o, dl)
        deal_log = [x for x in deal_log if last.get((x[0]["id"], x[1]["id"], x[2].get("type") in ("promise", "agree"))) is x]
        d["deals"] = [{"by": s["id"], "to": o["id"], **dl} for s, o, dl in deal_log]
        self.dialogues.append(d); self.dl_f.write(json.dumps(d) + "\n"); self.dl_f.flush()
        gist = " / ".join(f"{s.split()[0]}: {t}" for s, t in transcript[-3:])
        for x, y in ((a, b), (b, a)):
            w.minds_memory[x["id"]].add(w.day, w.slot, f"Talked with {y['name']} ({medium}): {gist}", 5 if kind != "talk" else 4)
            x["needs"]["social"] = min(100, x["needs"]["social"] + 12)
        econ.pay_gossip(self, a, b)
        imp = 4 + (2 if deal_log else 0) + (2 if kind in ("propose_marriage", "end_relationship", "ask_loan") else 0)
        self.ev("conversation", actors=[a["id"], b["id"]], text=f"{a['name']} and {b['name']} talk ({medium}){': ' + purpose if purpose else ''}.", importance=imp, data={"dialogue_index": len(self.dialogues) - 1})
        # deals become real
        for s, o, dl in deal_log:
            t = dl.get("type"); amt = dl.get("amount")
            try: amt = float(amt) if amt is not None else None
            except (TypeError, ValueError): amt = None
            if t in ("pay", "lend") and amt and amt > 0 and s["household"] != o["household"]:
                hs = w.households[s["household"]]; amt = min(amt, max(0, hs["savings"]))
                if amt > 0:
                    hs["savings"] -= amt; w.households[o["household"]]["savings"] += amt
                    self.ev(t, actors=[s["id"], o["id"]], text=f"{s['name']} {t}s {o['name']} ${int(amt)} ({dl.get('terms', '')}).", importance=6)
            elif t == "agree" and kind == "propose_marriage" and s is b: self.marry(a, b)
            elif t == "agree" and kind == "end_relationship": self.separate(a, b)
            elif t in ("promise", "agree"): self.ev("promise", actors=[s["id"], o["id"]], text=f"{s['name']} promises {o['name']}: {dl.get('terms', '')}", importance=5)
        # overhearing
        if medium == "phone":
            for p in w.living():
                if p["id"] in (a["id"], b["id"]) or p["age"] < 12 or p["location"] != w.households[p["household"]]["place"]: continue
                odds = 0.25 if OVERHEAR_QUIRKS & set(p["quirks"]) else 0.04
                if self.r.random() < odds:
                    w.minds_memory[p["id"]].add(w.day, w.slot, f"I listened in on the party line: {a['name']} and {b['name']} -- {gist}", 6)
                    self.ev("eavesdrop", actors=[p["id"]], text=f"{p['name']} listens in on {a['name']}'s call with {b['name']}.", importance=5, data={"dialogue_index": len(self.dialogues) - 1})
        else:
            for p in w.living():
                if p["id"] in (a["id"], b["id"]) or p["location"] != a["location"] or p["age"] < 8: continue
                if self.r.random() < (0.5 if OVERHEAR_QUIRKS & set(p["quirks"]) else 0.2):
                    w.minds_memory[p["id"]].add(w.day, w.slot, f"I overheard {a['name']} and {b['name']}: {gist}", 4)

    def run_convs(self, convs):
        if self.workers <= 1:
            for c in convs: self.converse(*c)
            return
        pending = list(convs)
        while pending:  # batches where nobody is in two conversations at once
            busy, batch, rest = set(), [], []
            for c in pending:
                ids = {c[0]["id"], c[1]["id"]}
                (rest if ids & busy else batch).append(c); busy |= ids if c in batch else set()
            with ThreadPoolExecutor(self.workers) as ex: results = list(ex.map(lambda c: self.talk(*c), batch))
            for c, res in zip(batch, results):
                if res: self.apply_talk(*c, *res)
            pending = rest

    def marry(self, a, b):
        w = self.w
        if a.get("spouse") or b.get("spouse") or a["age"] < 18 or b["age"] < 18: return
        a["spouse"], b["spouse"] = b["id"], a["id"]
        for x, y in ((a, b), (b, a)):
            r = x["rel"].setdefault(y["id"], {"affinity": 50, "trust": 50, "tags": []}); r["tags"] += ["spouse"]
        mover, stay = (b, a) if a["sex"] == "male" else (a, b)
        old = w.households[mover["household"]]; old["members"].remove(mover["id"])
        mover["household"] = stay["household"]; w.households[stay["household"]]["members"].append(mover["id"])
        mover["name"] = mover["name"].split()[0] + " " + w.households[stay["household"]]["surname"]
        mover["role"], stay["role"] = ("wife", "husband") if mover["sex"] == "female" else ("husband", "wife")
        self.ev("wedding", actors=[a["id"], b["id"]], text=f"{a['name']} and {b['name']} are married.", importance=9, public=True)

    def separate(self, a, b):
        w = self.w
        if a.get("spouse") != b["id"]: return
        a["spouse"] = b["spouse"] = None; a["divorced"] = b["divorced"] = True
        self.ev("separation", actors=[a["id"], b["id"]], text=f"{a['name']} and {b['name']} have split up.", importance=9, public=True)

    # ---------------------------------------------------------------- governance
    def books_note(self):
        """Officeholders keep the town books: when the treasury changes, they know the new figure (as a memory, like anything else)."""
        t = self.w.town; cur = int(t["treasury"])
        if t.get("_books_seen") == cur: return
        t["_books_seen"] = cur
        for pid in [t["offices"]["mayor"]] + t["offices"]["council"]:
            if pid and self.w.people[pid]["alive"]: self.w.minds_memory[pid].add(self.w.day, 0, f"The town books: the treasury holds ${cur}.")

    def election_calendar(self):
        """Elections follow the charter's own schedule. Notice is posted 30 days ahead (anyone 21+ may declare from then on); polls open on the day."""
        w = self.w; t = w.town; ne = t.get("next_election_day", 0); term = t["charter"].get("term_days", 730)
        if not any(e["status"] == "scheduled" for e in t["elections"]) and w.day == max(0, ne - 30):
            date = (w.date + dt.timedelta(days=ne - w.day)).strftime("%B %d")
            t["elections"].append({"id": f"E{len(t['elections']) + 1}", "day": ne, "offices": ["mayor", "council"], "candidates": [], "cand_office": {}, "votes": {}, "status": "scheduled"})
            self.ev("election_notice", text=f"The town clerk posts notice: {t['name']} elects a mayor and a council of three on {date}. Anyone 21 or over may put their name in.", importance=6, public=True)
        for e in t["elections"]:
            if e["status"] == "scheduled" and e["day"] == w.day:
                e["status"] = "open"
                self.ev("election_day", text=f"Election day in {t['name']}." + (" A runoff between the tied candidates." if e.get("runoff") else ""), importance=7, public=True)
                if not e.get("runoff"): t["next_election_day"] = w.day + term

    def declare(self, p, detail):
        e = next((x for x in self.w.town["elections"] if x["status"] in ("scheduled", "open") and not x.get("runoff")), None)
        if not e or p["age"] < self.w.town["charter"]["voting_age"] or p["id"] in e["candidates"]: return
        office = "council" if "council" in (detail or "").lower() else "mayor"
        e["candidates"].append(p["id"]); e["cand_office"][p["id"]] = office
        self.ev("candidacy", actors=[p["id"]], text=f"{p['name']} declares for {office}." + (f" \"{detail}\"" if detail and len(detail) > 10 else ""), importance=7, public=True)

    def vote(self, p, tgt, detail):
        w = self.w
        if p["age"] < w.town["charter"]["voting_age"]: return
        e = next((x for x in w.town["elections"] if x["status"] == "open"), None)
        if e and tgt:
            if tgt == "__any_candidate__" and e["candidates"]: c = self.r.choice(e["candidates"])
            else: q = w.by_name(tgt); c = q["id"] if q and q["id"] in e["candidates"] else None
            if c: e["votes"].setdefault(p["id"], set()).add(c); return
        m = next((x for x in w.town["motions"] if x["id"] == str(tgt).strip() and x["status"] == "open"), None)
        if m and (p["id"] in w.town["offices"]["council"] or p["id"] == w.town["offices"]["mayor"]):
            m["votes"][p["id"]] = (detail or "").lower().startswith("y")

    def _ask_job(self, p, boss, where):
        if not hasattr(self, "job_asks"): self.job_asks = []
        if not any(a["who"] == p["id"] and a["boss"] == boss for a in self.job_asks):
            self.job_asks.append({"who": p["id"], "boss": boss, "where": where, "day": self.w.day, "told": False})

    def job_silence(self):
        """A week with no answer: the person who asked notices they haven't heard back (once). What they do about it is theirs."""
        for a in getattr(self, "job_asks", []):
            if not a["told"] and self.w.day - a["day"] >= 7:
                a["told"] = True
                self.pending.setdefault(a["who"], []).append(f"It's been a week and you haven't heard back from {self.w.name(a['boss'])} about the work you asked for at {a['where']}.")
        self.job_asks = [a for a in getattr(self, "job_asks", []) if self.w.day - a["day"] <= 30]

    def night(self):
        w = self.w
        self.job_silence()
        for e in w.town["elections"]:
            if e["status"] != "open": continue
            e["status"] = "closed"; tallies = {}
            for voter, picks in e["votes"].items():
                for c in picks: tallies[c] = tallies.get(c, 0) + 1
            v = lambda c: tallies.get(c, 0)
            seats = e.get("seats") or {"mayor": 1, "council": w.town["charter"].get("council_seats", 3)}
            res = ", ".join(f"{w.name(c)} ({e['cand_office'][c]}) {v(c)}" for c in e["candidates"]) or "nobody ran"
            e["result"] = {"tallies": {w.name(c): v(c) for c in e["candidates"]}, "turnout": len(e["votes"])}
            won, tied = {}, {}
            for office, n in seats.items():
                ranked = sorted([c for c in e["candidates"] if e["cand_office"][c] == office and v(c) > 0], key=lambda c: -v(c))
                if len(ranked) <= n: won[office] = ranked; continue
                cut = v(ranked[n - 1]); sure = [c for c in ranked if v(c) > cut]; edge = [c for c in ranked if v(c) == cut]
                if len(sure) + len(edge) == n: won[office] = sure + edge; continue
                if e.get("runoff"):  # tied twice: lots are drawn, as small towns did
                    drawn = self.r.sample(edge, n - len(sure)); won[office] = sure + drawn
                    self.ev("lots_drawn", actors=edge, text=f"Still tied after the runoff; the clerk draws lots for {office}: {', '.join(w.name(c) for c in drawn)}.", importance=8, public=True)
                else: won[office] = sure; tied[office] = (edge, n - len(sure))
            off = w.town["offices"]
            # winners take office; if nobody stood for a seat, the incumbent holds over
            if "mayor" in won and "mayor" not in tied and won["mayor"]: off["mayor"] = won["mayor"][0]
            if "council" in seats:
                if e.get("runoff"): off["council"] = (off["council"] + won.get("council", []))[:3]
                elif any(e["cand_office"][c] == "council" for c in e["candidates"]):
                    new = won.get("council", [])
                    if "council" not in tied and len(new) < seats["council"]:  # too few ran: seats nobody won are held over by sitting members who didn't run (Nov 18 dry-run fix)
                        new = new + [i for i in off["council"] if i not in new and i not in e["candidates"] and w.people[i]["alive"] and not w.people[i]["offtown"]]
                    off["council"] = new[:seats["council"]]
            if tied:
                cands = [c for ed, _ in tied.values() for c in ed]
                w.town["elections"].append({"id": f"E{len(w.town['elections']) + 1}", "day": w.day + 1, "offices": list(tied), "candidates": cands,
                                            "cand_office": {c: e["cand_office"][c] for c in cands}, "votes": {}, "status": "scheduled", "runoff": True,
                                            "seats": {o: k for o, (ed, k) in tied.items()}})
            winner = w.name(off["mayor"]) if off["mayor"] else ("undecided (runoff tomorrow)" if "mayor" in tied else "nobody")
            council_txt = ", ".join(w.name(c) for c in off["council"]) or "empty"
            runoff_txt = (" Tied: " + "; ".join(f"{o}: {', '.join(w.name(c) for c in ed)}" for o, (ed, k) in tied.items()) + ". Runoff tomorrow.") if tied else ""
            self.ev("election_result", actors=e["candidates"], text=f"{'Runoff results' if e.get('runoff') else 'Election results'}: {res}. Mayor: {winner}. Council: {council_txt}. Turnout: {len(e['votes'])}.{runoff_txt}",
                    importance=10, public=True, data=e["result"])
        if w.date.weekday() == w.town["charter"]["meeting_weekday"]:
            council = w.town["offices"]["council"]; mayor = w.town["offices"]["mayor"]
            for m in w.town["motions"]:
                if m["status"] != "open" or w.day - m["day"] < 1: continue
                yes = sum(1 for v, b in m["votes"].items() if b and v in council); no = sum(1 for v, b in m["votes"].items() if not b and v in council)
                if yes == no and mayor in m["votes"]: yes += m["votes"][mayor]; no += not m["votes"][mayor]
                if yes + no == 0 and w.day - m["day"] < 14: continue
                m["status"] = "passed" if yes > no else "failed"
                self.ev("measure_vote", actors=[m["by"]] + council, text=f"Council vote on {m['id']} (\"{m['text']}\"): {m['status']} ({yes} yes, {no} no).", importance=7, public=True)
                if m["status"] == "passed": law.enact(self, m)  # the clerk writes down what it binds; the town follows it from today (Nov 18)

    def needs_tick(self):
        for p in self.w.living():
            n = p["needs"]; n["hunger"] = min(100, n["hunger"] + 8); n["energy"] = max(0, min(100, n["energy"] - 4)); n["social"] = max(0, n["social"] - 3)
            n["mood"] = max(0, min(100, n["mood"] + (2 if n["social"] > 50 else -2) + (-3 if p["illness"] else 0) + (-4 if self.w.households[p["household"]]["savings"] < 0 else 0)))
            if self.w.slot in (0, 2): n["hunger"] = max(0, n["hunger"] - 30)  # meals at home

    # ---------------------------------------------------------------- save / resume between seasons
    def close_files(self):
        for f in (self.ev_f, self.dl_f, self.snap_f): f.close()

    def __getstate__(self):
        d = self.__dict__.copy()
        for k in ("ev_f", "dl_f", "snap_f", "_lock", "llm", "mind", "ref"): d.pop(k, None)
        return d

    def newcomer_named(self, x, ev):
        """A named outsider the world step brought to town who stays (a drifter, a kinsman, a new hand). Becomes a resident with a mind."""
        w = self.w
        from .generator import person
        nm = str(x.get("name") or "").strip()
        if not nm or w.by_name(nm): return
        # fix 7 (season break): someone described as passing through moves on; only people who come to live here become residents
        if PASSING.search(str(x.get("about") or "")) and not STAYING.search(str(x.get("about") or "")):
            self.ev("visitor_gone", text=f"{nm} passes through {w.town['name']} and moves on.", importance=2, data={"no_memory": True}); return
        sn = nm.split()[-1]; hid = max(w.households) + 1
        w.households[hid] = {"id": hid, "surname": sn, "kind": "newcomer", "members": [], "savings": int(self.r.uniform(5, 300)), "debt": 0, "home": "rented",
                             "place": f"home_{hid}", "monthly_housing": 30, "withhold_tax": False, "has_tv": False}
        w.places[f"home_{hid}"] = {"name": f"the room {nm.split()[0]} rents", "kind": "home", "household": hid, "x": 0, "condition": 0.7}
        try: age = max(16, min(80, int(x.get("age") or 30)))
        except (TypeError, ValueError): age = 30
        p = person(self.r, sn, age, (x.get("sex") or "male") != "female", w.date.year, "single", w.first_names()); p["name"] = nm; p["job"] = "looking for work"
        pid = w.add_person(p, hid); w.minds_memory[pid] = Memory(); w.minds_memory[pid].add(w.day, 0, f"I've just come to {w.town['name']}. {x.get('about', '')}".strip(), 6)
        self.ev("newcomer", actors=[pid], text=f"{nm} turns up in town and stays: {x.get('about', '')}".strip(), importance=6, public=True)

    def reopen(self, out, llm, mode="live"):
        import threading
        if not hasattr(self, "fate"): self.fate = Fate(self, self.w.gen["seed"] + self.w.day)
        if not hasattr(self.w, "threads"): self.w.threads = []
        self.w.fate = self.fate; self.w.engine = self
        self.out = out; self.llm = llm; self.mode = mode; self._lock = threading.RLock()
        self.mind = LiveMind(llm) if mode == "live" else MockMind(self.w.gen["seed"] + self.w.day)
        self.ref = Referee(llm, mode, self.w.gen["seed"] + self.w.day)
        self.ev_f = open(os.path.join(out, "events.jsonl"), "a"); self.dl_f = open(os.path.join(out, "dialogues.jsonl"), "a"); self.snap_f = open(os.path.join(out, "snapshots.jsonl"), "a")

    def _estimate(self, kind, w, p, mem, extra, transcript=None):
        from .minds import situation_block, persona_block, WORLD_RULES, PLAN_FORMAT, SAY_FORMAT
        body = situation_block(w, p, mem, extra) + (PLAN_FORMAT if kind == "plan" else SAY_FORMAT + "".join(t for _, t in (transcript or [])))
        self.est[f"{kind}_calls"] += 1; self.est[f"{kind}_in_chars"] += len(body)
        self.est["sys_chars"] = max(self.est["sys_chars"], len(WORLD_RULES) + 60 + len(persona_block(w, p)))

    def cost_forecast(self):
        """Forecast live cost from real prompt sizes measured during a dry run (~3.8 chars/token)."""
        e = self.est; tok = lambda ch: ch / 3.8
        from .llm import PRICES
        P = PRICES["claude-haiku-5-5"]
        sys_t = tok(e["sys_chars"]); calls = e["plan_calls"] + e["say_calls"]
        body_in = tok(e["plan_in_chars"] + e["say_in_chars"])
        out_t = e["plan_calls"] * 450 + e["say_calls"] * 90
        resident = (body_in * P["in"] + calls * sys_t * P["cache_read"] + len(self.w.people) * sys_t * 4 * P["cache_write"] + out_t * P["out"]) / 1e6
        attempts = sum(1 for x in self.events if x["kind"] == "attempt")
        referee = attempts * (1500 * 0.7 * PRICES["claude-haiku-5-5"]["in"] + 1500 * 0.3 * PRICES["claude-sonnet-5-5"]["in"] + 300 * 0.7 * P["out"] + 300 * 0.3 * PRICES["claude-sonnet-5-5"]["out"]) / 1e6
        editor = (60000 * PRICES["claude-sonnet-5-5"]["in"] + 3000 * PRICES["claude-sonnet-5-5"]["out"]) / 1e6
        return {"calls": calls + attempts + 1, "resident_usd": round(resident, 2), "referee_usd": round(referee, 2), "editor_usd": round(editor, 2),
                "total_usd": round(resident + referee + editor, 2), "batch_total_usd": round((resident + referee + editor) * 0.5, 2),
                "note": "estimate from real prompt sizes in a dry run; mock conversations are shorter than live ones, so live may run ~1.5x"}

    def run(self, days):
        t0 = time.time(); stop = None
        try:
            for _ in range(days): self.run_day()
        except BudgetExceeded as e: stop = str(e); self.ev("engine_stop", text=f"Budget cap reached: {e}", importance=0)
        summ = {"days_run": self.w.day, "events": len(self.events), "dialogues": len(self.dialogues), "seconds": round(time.time() - t0, 1), "mode": self.mode,
                "cost": self.llm.meter.summary(), "forecast_if_live": self.cost_forecast() if self.mode != "live" else None, "stopped": stop, "population": len(self.w.living()), "date": self.w.date_str}
        json.dump(summ, open(os.path.join(self.out, "run_summary.json"), "w"), indent=1)
        return summ


if __name__ == "__main__":
    args = sys.argv[1:]
    gen = json.load(open(args[0])); days = int(args[1]); out = args[2]
    live = "--live" in args; budget = float(args[args.index("--budget") + 1]) if "--budget" in args else 20.0
    workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 8
    e = Engine(gen, out, "live" if live else "mock", budget, workers)
    print(json.dumps(e.run(days), indent=1))
