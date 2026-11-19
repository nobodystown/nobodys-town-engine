"""The world step and threads (approved Nov 18).

Everything nobody in town chose comes from here. Real-world numbers decide HOW OFTEN something comes into the town's life,
by broad category. The model only estimates, for this exact town, date and people, what it could realistically be (4-6 options
with odds). The town's dice picks. "Nothing worth mentioning" is always an option.

Anything left unsettled becomes a THREAD. Each thread is stepped weekly (daily while an event place is open): the model lists
what could realistically happen next, with odds ("nothing new yet" always on the list), and the dice picks. A thread ends only as
resolved, given up, gone cold, or gone (everyone involved dead or away). Nothing goes quiet without an ending in the record.
The model never decides a resident's choices; residents act on threads themselves, and what they did is shown to the step.
"""
import json, random
from . import law as L, econ

# (category, unit, yearly rate per unit, season weights or None, source)
# unit: person = each resident in town; household = each household; town = the town as a whole; secret = each unrevealed secret
CATEGORIES = [
    ("everyday", "household", 36.0, None, "estimate: small household happenings; same rate as the old fixed list"),
    ("crime", "person", 0.02, None, "FBI UCR 1959: rural index crime 397 per 100,000 reported (0.004 a person); x5 for petty, unreported theft, vandalism, trespass"),
    ("fire", "household", 0.012, {"winter": 2.0, "autumn": 1.0, "spring": 0.8, "summer": 0.6}, "NFPA 1980: 3.2 reported home fires per 1,000 people; 1950s stoves, chimneys and wiring ran higher"),
    ("accident", "person", 0.04, None, "estimate: work, farm, road and home injuries bad enough for the doctor"),
    ("visitor", "household", 1.0, None, "estimate: kin, strangers, salesmen, someone from the past"),
    ("news_from_away", "household", 2.0, None, "estimate: letters, telegrams, deaths, troubles and windfalls among kin elsewhere"),
    ("work_and_money", "town", 2.0, None, "estimate: contracts, layoffs, prices, the bank, the main employer"),
    ("nature", "town", 3.0, None, "estimate: animals, weather short of disaster, the land itself"),
    ("gathering", "town", 6.0, {"summer": 2.0, "autumn": 1.5, "spring": 1.0, "winter": 0.5}, "estimate: circuses, revivals, carnivals, fairs, dances, ballgames, socials, traveling shows"),
    ("luck", "person", 0.15, None, "estimate: found money, a prize, a loss, a stroke of good or bad luck"),
    ("secret", "secret", 0.12, None, "estimate: chance a year that a secret slips out on its own"),
]
BIG = {"crime", "fire", "accident", "secret"}

STANDARDS = ("Channel standards: no sexual content; children are never victims of violence or abuse; no suicide or self-harm; "
             "nothing may happen to anyone because of their race, ethnicity or religion; deaths and injuries are told plainly, never gory.\n"
             "Grounding: RESIDENTS lists everyone who lives in town. Anyone else residents talk about is someone from elsewhere or a rumor that may not be true; "
             "never treat them as present. Never invent townspeople (a clerk, a storekeeper, an official): a role nobody on the list holds is not filled here. "
             "An outsider enters town only through a newcomer operation.")

FATE_RULES = """You are the world itself in a realistic simulation of a small American town. You never choose what happens; you estimate.
Something in the CATEGORY below comes into this town's life today. List 4 to 6 genuinely different, specific things it could realistically be,
for this exact town, date, season and these exact people, each with your honest estimate of how often it would turn out to be that in real life
(percent, summing to 100). The town's dice picks one.
- Real life is mostly small and ordinary; weight options the way real life does. Always include one option where it amounts to nothing worth mentioning.
- Period- and place-accurate. Nothing cartoonish; nothing that would not happen in a real town of this size.
- If someone did something (a theft, damage, a prank), say exactly who: a named resident who would realistically do it given their situation and
  character, or an outsider (give a name and one line about them). Who did it is known only to them unless someone saw.
- Use exact full names from the list. Never decide what a resident chooses, says or feels; only what happens to them and around them.
- If it leaves something unsettled that will play out over time (a crime, a stranger who stays, a debt, an injury, a show in town, a quarrel), open a thread.
- If it is an event people could go to (a show, a social, a game, a revival), give it a place with hours, days and price.
""" + STANDARDS + """
OUTPUT one JSON object:
{"options": [ {"odds": <percent>,
   "record": "<the full truth of what happens, 1-2 plain sentences, for the town's record>",
   "involved": [ {"name": "<full name>", "knows": "<what this person now knows, in plain words>"} ],
   "visibility": "private"|"witnessed"|"public", "said": "<how word of it goes around town, if it gets around>", "importance": 1-10,
   "effects": [<operations, below>],
   "thread": null | {"title": "<short neutral title that gives away nothing private>", "truth": "<the private whole truth, including who did it>", "people": ["<full names>"], "pace": "weekly"|"daily"},
   "place": null | {"name": "<e.g. the circus tent in the east field>", "hours": "<e.g. evenings>", "days": <1-14>, "price": <dollars or 0>}
 } ]}
Operations: {"op": "money", "from": "<full name>|town|outside", "to": "<full name>|town|outside", "amount": <dollars>}
 {"op": "memory", "who": "<full name>", "text": "<what they now know>"}   {"op": "relationship", "a": "<full name>", "b": "<full name>", "delta": <-30..30>}
 {"op": "injure", "who": "<full name>", "days": <1-90>}   {"op": "item", "who": "<full name>", "desc": "<object>"}
 {"op": "fire", "who": "<full name in the household>", "severity": "small"|"bad"|"destroyed"}
 {"op": "jail", "who": "<full name>", "days": <1-365>}   {"op": "newcomer", "name": "<full name>", "age": <n>, "sex": "male"|"female", "about": "<one line>"}"""

THREAD_RULES = """You are the world itself in a realistic simulation of a small American town. You never choose what happens; you estimate.
Below is an unsettled matter in town: the whole private truth, what has happened so far, and what the people involved have done lately.
Time has passed ({span}). List 3 to 5 genuinely different things that could realistically happen in that time, each with your honest estimate of
how often it would go that way in real life (percent, summing to 100). The town's dice picks one.
- "Nothing new yet" is usually the most likely; always include it.
- Take what residents did as given. Never decide what a resident chooses, says or feels; only what happens around them and as a result.
- Real matters end. An option may end it: "resolved" (settled one way or another), "given_up" (people let it go), "cold" (no answer, and none coming),
  but only when that is realistic now. Long-quiet matters do go cold.
- If someone is caught, the law follows period procedure: questioning, the county court, a fine, jail time or release.
""" + STANDARDS + """
OUTPUT one JSON object:
{"options": [ {"odds": <percent>, "record": "<what happens, 1-2 plain sentences; for 'nothing new yet' say so>",
   "involved": [ {"name": "<full name>", "knows": "<what this person now knows>"} ], "visibility": "private"|"witnessed"|"public",
   "said": "<how word gets around, if it does>", "importance": 1-10, "effects": [<same operations as before>],
   "end": null|"resolved"|"given_up"|"cold", "truth_update": "<new private facts, if any>"} ]}
Operations: money, memory, relationship, injure, item, fire, jail, newcomer (same shapes as the world step)."""


def roll(r, opts):
    """The town's dice picks one option by its odds. Returns (chosen, normalized odds list, roll)."""
    opts = [o for o in opts if isinstance(o, dict) and (o.get("record") or o.get("text"))]
    if not opts: return None, [], None
    w = [max(0.0, float(o.get("odds") or 0)) for o in opts]; t = sum(w)
    w = [x / t for x in w] if t else [1 / len(opts)] * len(opts)
    d = r.randint(0, 99); acc = 0.0
    for o, x in zip(opts, w):
        acc += x
        if d < acc * 100: return o, w, d
    return opts[-1], w, d


class Fate:
    def __init__(self, engine, seed):
        self.e = engine; self.r = random.Random(seed * 101 + 13)

    # ------------------------------------------------------------ context
    def people_list(self):
        w = self.w
        out = []
        for p in w.living():
            h = w.households[p["household"]]
            out.append(f"{p['name']} ({p['age']}, {p['sex']}, {p['role']}, {p['job'] or 'no job'}; household {h['surname']}"
                       + (f"; quirks {', '.join(p['quirks'])}" if p["age"] >= 14 else "") + f"; money {'none' if econ.cash(h) <= 0 else 'tight' if econ.cash(h) < 150 else 'comfortable' if econ.cash(h) < 3000 else 'well off'})")
        return "\n".join(out)

    @property
    def w(self): return self.e.w

    def base_ctx(self):
        w = self.w; law = [p["name"] + f" ({p['job']})" for p in w.living() if p.get("job") in ("town marshal", "deputy sheriff")]
        open_t = [f"- {t['title']}" for t in w.threads if t["status"] == "open"][:12]
        places = [f"- {pl['name']} ({pl.get('hours', '')}, until {pl.get('until_date', '')})" for pl in w.places.values() if pl.get("kind") == "event"]
        return (f"DATE: {w.date.strftime('%A, %B %d, %Y')} ({w.season}). TOWN: {w.town['name']}, {w.gen['region']} ({w.geo}); population {len(w.living())}. "
                f"Main employer: {w.companies['co1']['name']}. The law in town: {', '.join(law) or 'the county sheriff, from the county seat'}.\n"
                + (f"TOWN LAWS: {' | '.join(L.law_lines(w, 12))}\n" if L.laws_in_force(w) else "") +
                f"RESIDENTS:\n{self.people_list()}\n" + ("OPEN MATTERS IN TOWN:\n" + "\n".join(open_t) + "\n" if open_t else "")
                + ("GOING ON IN TOWN:\n" + "\n".join(places) + "\n" if places else ""))

    def unit_text(self, cat, unit):
        w = self.w
        if cat == "secret":
            p = unit; return f"CATEGORY: a secret coming out (or not). WHOSE: {p['name']}. THE SECRET: they {p['secret']}."
        if isinstance(unit, dict) and "members" in unit:
            ms = [w.people[i] for i in unit["members"] if w.people[i]["alive"] and not w.people[i]["offtown"]]
            pl = w.places.get(unit["place"], {})
            return (f"CATEGORY: {cat.replace('_', ' ')}. IT CONCERNS THE HOUSEHOLD: the {unit['surname']}s ({', '.join(q['name'] for q in ms)}); "
                    f"home: {pl.get('name', 'none')} ({unit['home']}).")
        if isinstance(unit, dict) and "name" in unit:
            return f"CATEGORY: {cat.replace('_', ' ')}. IT CONCERNS: {unit['name']}."
        return f"CATEGORY: {cat.replace('_', ' ')}. IT CONCERNS THE TOWN AS A WHOLE."

    # ------------------------------------------------------------ daily
    def daily(self, ev):
        """Roll every category for every unit at its real yearly rate. Live: the model lists options, the dice picks. Mock: placeholders."""
        w = self.w
        self.expire_places(ev); self.release_jail(ev)
        s = w.season; hits = []
        units = {"person": [p for p in w.living()], "household": [h for h in w.households.values() if any(w.people[i]["alive"] and not w.people[i]["offtown"] for i in h["members"])],
                 "town": [None], "secret": [p for p in w.living() if p.get("secret") and not p["flags"].get("secret_out")]}
        for cat, unit, rate, seasons, _src in CATEGORIES:
            f = (seasons or {}).get(s, 1.0)
            for u in units[unit]:
                if self.r.random() < rate * f / 365: hits.append((cat, u))
        for cat, u in hits: self.happen(cat, u, ev)

    def happen(self, cat, u, ev):
        w = self.w
        if self.e.mode != "live": out = self.mock_options(cat, u)
        else:
            msg = self.base_ctx() + "\n" + self.unit_text(cat, u)
            out, raw = self.e.llm.call_json("world_big" if cat in BIG else "world", [FATE_RULES], [{"role": "user", "content": msg}], max_tokens=2200)
        ch, odds, d = roll(self.r, (out or {}).get("options") or [])
        if not ch: return
        self.apply(ch, ev, cat, odds, d, (out or {}).get("options") or [])
        if ch.get("thread"): self.open_thread(ch, cat, ev)
        if ch.get("place"): self.add_place(ch, cat, ev)
        if cat == "secret" and (ch.get("visibility") == "public" or len(ch.get("involved") or []) > 1): u["flags"]["secret_out"] = w.date_str

    # ------------------------------------------------------------ applying an outcome
    def apply(self, ch, ev, cat, odds=(), d=None, opts=(), thread=None):
        w = self.w; e = self.e
        from .referee import apply_effects
        inv = [(w.by_name(x.get("name")), x.get("knows") or "") for x in (ch.get("involved") or []) if isinstance(x, dict)]
        inv = [(p, k) for p, k in inv if p]
        vis = ch.get("visibility", "private"); imp = int(ch.get("importance") or 3)
        rec = ch.get("record") or ch.get("text") or ""
        data = {"category": cat, "no_memory": True, "_roll": d, "_options": [{"odds": round(x * 100), "record": str(o.get("record") or o.get("text"))[:200]} for o, x in zip(opts, odds)]}
        if thread: data["thread"] = thread["id"]
        if ch.get("said"): data["said"] = ch["said"]
        place = inv[0][0]["location"] if inv and vis == "witnessed" else None
        e.ev("world", actors=[p["id"] for p, _ in inv], text=rec, importance=imp, public=vis == "public" and bool(ch.get("said") or rec), place=None, data=data)
        for p, k in inv:
            if k: w.minds_memory[p["id"]].add(w.day, w.slot, k)
        if place:
            for q in w.living():
                if q["location"] == place and q["id"] not in {p["id"] for p, _ in inv}: w.minds_memory[q["id"]].add(w.day, w.slot, "I saw: " + (ch.get("said") or rec))
        effs = []
        for x in ch.get("effects") or []:
            if not isinstance(x, dict): continue
            op = x.get("op")
            if op == "fire":
                q = w.by_name(x.get("who"))
                if q and w.places.get(w.households[q["household"]]["place"], {}).get("kind") == "home": w.house_fire(w.households[q["household"]], ev, sev=x.get("severity"))
            elif op == "jail":
                q = w.by_name(x.get("who"))
                if q and not q["offtown"]:
                    days = max(1, min(365, int(x.get("days") or 7)))
                    w.leave_town(q, "the county jail", ev, kind="jail"); w.offtown[q["id"]]["until"] = w.day + days
            elif op == "newcomer":
                self.e.newcomer_named(x, ev)
            else: effs.append(x)
        apply_effects(w, effs, ev, inv[0][0] if inv else {"id": -1})

    # ------------------------------------------------------------ threads
    def open_thread(self, ch, cat, ev, source="world"):
        w = self.w; t = ch["thread"]
        ppl = [w.by_name(n) for n in (t.get("people") or [])]; ppl = [p["id"] for p in ppl if p]
        for x in ch.get("involved") or []:
            q = w.by_name(x.get("name")) if isinstance(x, dict) else None
            if q and q["id"] not in ppl: ppl.append(q["id"])
        dup = self.same_matter(str(t.get("title") or ch.get("record", "")), ppl)
        if dup:  # the same matter again (Nov 18 fix: one missing $35 had opened 7 threads): add to the open one instead
            dup["history"].append(f"{w.date_str}: {ch.get('record', '')}")
            if t.get("truth") and t["truth"] not in dup["truth"]: dup["truth"] = (dup["truth"] + " " + str(t["truth"]))[-1200:]
            for i in ppl:
                if i not in dup["people"]: dup["people"].append(i)
            return dup
        if cat == "crime" and ch.get("visibility") in ("public", "witnessed"):
            for p in w.living():
                if p.get("job") in ("town marshal", "deputy sheriff") and p["id"] not in ppl: ppl.append(p["id"]); w.minds_memory[p["id"]].add(w.day, w.slot, "It's on my desk: " + (ch.get("said") or ch.get("record", "")))
        th = {"id": f"T{len(w.threads) + 1}", "title": str(t.get("title") or ch.get("record", ""))[:90], "kind": cat, "truth": str(t.get("truth") or ch.get("record", ""))[:800],
              "people": ppl, "pace": "daily" if t.get("pace") == "daily" or ch.get("place") else "weekly", "opened": w.date_str, "opened_day": w.day, "last_step": w.day,
              "history": [f"{w.date_str}: {ch.get('record', '')}"], "status": "open", "ending": None, "source": source, "quiet_steps": 0}
        w.threads.append(th)
        ev("thread_open", actors=ppl, text=f"Open matter: {th['title']}", importance=2, data={"thread": th["id"], "no_memory": True})
        return th

    STOP = {"the", "a", "an", "of", "and", "in", "on", "at", "to", "for", "from", "with", "over", "about", "s"}

    def same_matter(self, title, ppl):
        """An open thread about the same thing: shares at least one person (or has none) and at least half the title's words."""
        import re
        words = lambda s: {x for x in re.findall(r"[a-z0-9$]+", s.lower()) if x not in self.STOP}
        tw = words(title)
        if not tw: return None
        best, score = None, 0.0
        for th in self.w.threads:
            if th["status"] != "open": continue
            if ppl and th["people"] and not set(ppl) & set(th["people"]): continue
            ow = words(th["title"]); s = len(tw & ow) / max(1, min(len(tw), len(ow)))
            if s > score: best, score = th, s
        return best if score >= 0.5 else None

    def step_threads(self, ev, weekly):
        """End of day. Daily-pace threads step every lived day; weekly ones on Sundays. Threads whose people are all gone end as 'gone'."""
        w = self.w
        for th in [t for t in w.threads if t["status"] == "open"]:
            alive = [i for i in th["people"] if w.people[i]["alive"] and not w.people[i]["offtown"]]
            if not alive and th["people"]: self.end(th, "gone", "Everyone it concerned is dead or gone from town.", ev); continue
            if th["pace"] == "daily" and not any(pl.get("thread") == th["id"] for pl in w.places.values()): th["pace"] = "weekly"
            if not (th["pace"] == "daily" or weekly): continue
            span = f"{w.day - th['last_step']} days" if w.day - th["last_step"] != 1 else "one day"
            if th["pace"] == "daily":
                pl = next((p for p in w.places.values() if p.get("thread") == th["id"]), None)
                there = [q["name"] for q in w.living() if pl and q.get("went_to") == pl["id"] + str(w.day)]
            else: there = None
            if self.e.mode != "live": out = self.mock_step(th)
            else:
                lately = [x["text"] for x in self.e.events[-400:] if x["day"] > th["last_step"] - 1 and set(x.get("actors") or []) & set(th["people"])
                          and x["kind"] in ("outcome", "conversation", "attempt", "world", "pay", "lend", "promise")][-12:]
                msg = (self.base_ctx() + f"\nTHE MATTER ({th['id']}, open since {th['opened']}): {th['title']}\nWHOLE PRIVATE TRUTH: {th['truth']}\nPEOPLE: {', '.join(w.name(i) for i in th['people'])}\n"
                       f"SO FAR:\n" + "\n".join("- " + hline for hline in th["history"][-10:]) + "\n"
                       + (f"WHAT THE PEOPLE INVOLVED DID LATELY:\n" + "\n".join("- " + x for x in lately) + "\n" if lately else "WHAT THE PEOPLE INVOLVED DID LATELY: nothing about this.\n")
                       + (f"AT {pl['name'].upper()} TODAY: {', '.join(there) or 'nobody from town went'}.\n" if there is not None and pl else ""))
                out, raw = self.e.llm.call_json("world_big" if th["kind"] in BIG else "world", [THREAD_RULES.replace("{span}", span)], [{"role": "user", "content": msg}], max_tokens=1800)
            th["last_step"] = w.day
            ch, odds, d = roll(self.r, (out or {}).get("options") or [])
            if not ch: continue
            quiet = "nothing new" in str(ch.get("record", "")).lower()
            th["quiet_steps"] = th["quiet_steps"] + 1 if quiet else 0
            if not quiet:
                self.apply(ch, ev, th["kind"], odds, d, (out or {}).get("options") or [], thread=th)
                th["history"].append(f"{w.date_str}: {ch.get('record', '')}")
                for x in ch.get("involved") or []:
                    q = w.by_name(x.get("name")) if isinstance(x, dict) else None
                    if q and q["id"] not in th["people"]: th["people"].append(q["id"])
            if ch.get("truth_update"): th["truth"] = (th["truth"] + " " + str(ch["truth_update"]))[-1200:]
            if ch.get("end") in ("resolved", "given_up", "cold"): self.end(th, ch["end"], ch.get("record", ""), ev)

    def end(self, th, how, why, ev):
        w = self.w; th["status"] = "ended"; th["ending"] = how; th["ended"] = w.date_str; th["history"].append(f"{w.date_str}: ENDED ({how}). {why}")
        ev("thread_end", actors=th["people"], text=f"{th['title']}: {'settled' if how == 'resolved' else 'let go' if how == 'given_up' else 'gone cold' if how == 'cold' else 'over; everyone it concerned is gone'}.",
           importance=3, data={"thread": th["id"], "ending": how, "no_memory": True})

    def known_to(self, p):
        """Open matters this person is part of (they know their own business; the private truth stays private)."""
        return [t for t in self.w.threads if t["status"] == "open" and p["id"] in t["people"]]

    # ------------------------------------------------------------ places with hours
    def add_place(self, ch, cat, ev):
        w = self.w; pl = ch["place"]; days = max(1, min(14, int(pl.get("days") or 1)))
        pid = f"ev_{w.day}_{len(w.places)}"
        th = next((t for t in reversed(w.threads) if t["opened_day"] == w.day and t["status"] == "open"), None)
        if not th:  # an event people can go to is always followed while it's on
            th = self.open_thread({"thread": {"title": pl.get("name", "something in town"), "truth": ch.get("record", ""), "people": [], "pace": "daily"}, "record": ch.get("record", ""),
                                   "involved": ch.get("involved")}, cat, ev)
        th["pace"] = "daily"
        import datetime as dt
        w.places[pid] = {"name": str(pl.get("name") or "the event")[:80], "kind": "event", "x": 0, "hours": str(pl.get("hours") or "")[:40], "price": pl.get("price") or 0,
                         "until": w.day + days - 1, "until_date": (w.date + dt.timedelta(days=days - 1)).strftime("%A %B %d"), "thread": th["id"], "id": pid}

    def expire_places(self, ev):
        w = self.w
        for k in [k for k, v in w.places.items() if v.get("kind") == "event" and v["until"] < w.day]:
            pl = w.places.pop(k)
            for p in w.living():
                if p["location"] == k: p["location"] = w.households[p["household"]]["place"]

    def release_jail(self, ev):
        w = self.w
        for pid, rec in list(w.offtown.items()):
            if rec.get("kind") == "jail" and rec.get("until", 0) <= w.day and w.people[pid]["alive"]: w.return_home(w.people[pid], "out of the county jail", ev)

    # ------------------------------------------------------------ mock (dry runs only: tests the plumbing, never content)
    def mock_options(self, cat, u):
        w = self.w; who = (u if isinstance(u, dict) and "name" in u and "members" not in u else None)
        if isinstance(u, dict) and "members" in u: who = w.people[u["members"][0]]
        who = who or self.r.choice(w.living())
        o = [{"odds": 60, "record": f"[MOCK {cat}] nothing worth mentioning", "involved": [], "visibility": "private", "importance": 1, "effects": []},
             {"odds": 30, "record": f"[MOCK {cat}] something small for {who['name']}", "involved": [{"name": who["name"], "knows": f"[MOCK {cat}] something small"}],
              "visibility": "public", "said": f"[MOCK] word about {who['name']}", "importance": 3, "effects": []},
             {"odds": 10, "record": f"[MOCK {cat}] something that lingers for {who['name']}", "involved": [{"name": who["name"], "knows": "[MOCK] it lingers"}], "visibility": "public",
              "said": "[MOCK] it lingers", "importance": 6, "effects": [], "thread": {"title": f"[MOCK {cat}] matter for {who['name']}", "truth": "[MOCK]", "people": [who["name"]]},
              "place": {"name": "[MOCK] the show in the field", "hours": "evenings", "days": 2, "price": 0.25} if cat == "gathering" else None}]
        if cat in ("crime", "gathering"): o[2]["odds"] = 40; o[0]["odds"] = 30
        return {"options": o}

    def mock_step(self, th):
        return {"options": [{"odds": 70, "record": "nothing new yet", "end": None}, {"odds": 20, "record": f"[MOCK] a development in {th['id']}", "involved": [], "importance": 3},
                            {"odds": 10, "record": f"[MOCK] {th['id']} comes to an end", "end": self.r.choice(["resolved", "given_up", "cold"]), "importance": 4}]}
