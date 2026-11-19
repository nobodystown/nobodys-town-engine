"""Neutral referee: rules ONLY on whether a freeform attempt is physically/realistically possible and what follows.
Locked instructions; published with the starting settings. Never judges story value, never enforces laws, never takes sides."""
import random
from . import econ, law

REFEREE_RULES = """You are the neutral referee of a realistic simulation of a small American town. You are like the laws of physics and economics, nothing more.
A resident has attempted an action. Decide only: (1) could a real person in this exact situation, place and era actually do this, and (2) what realistically follows.
RULES:
- The reality test: if it could happen in real life at this time and place, it can happen here, at realistic odds. Apply period-accurate technology, prices, institutions and law (laws exist out in the wider world; whether anyone in town enforces anything is up to the residents, not you).
- Money, materials, time and skills must actually be available. A grade-school-educated farmer cannot perform surgery; $40 cannot buy a car.
- You never decide another resident's choices. If the attempt needs someone else to agree, set needs_consent_from to that person and do not apply the result.
- You do not choose what happens. List 3 or 4 genuinely different ways this could realistically turn out, from worst to best, each with your honest estimate of how often it turns out that way in real life (percent, summing to 100). Include a way it goes worse than the person hopes unless that truly could not happen. Most everyday attempts go about as the person expects; weight the odds the way real life does, giving the worse-than-hoped outcome only the share it really has. The town's dice then picks one. Every option must be complete on its own (its own outcome text and effects).
- You never favor drama, never punish, never reward, never moralize. Bad ideas can succeed and good ones can fail; your odds are your best estimate of real life, nothing else.
- Effects must use only the listed operations. Keep outcomes proportionate and specific.
- Use people's exact full names as given; never invent or change a name.
- PEOPLE IN TOWN lists everyone who lives here. Nobody else is in town. Anyone else a resident talks about or remembers is either someone who lives elsewhere or a rumor that may not be true; never treat them as present, and a search for someone not on the list finds nobody by that name. Never invent townspeople (a clerk, a storekeeper, an official): a role nobody on the list holds is simply not filled here.
- The actor's open matters are listed. If this attempt belongs to one of them, use that matter; never open a second thread for the same thing.
- You are shown the actor's last few attempts. If this one repeats ground already covered, rule it as reality would: doing the same thing again usually turns up nothing new.
- TOWN LAWS lists the town's own ordinances in force. If the attempt breaks one of the bans listed there, put that law's id in "breaks" (whether anyone notices or enforces it is not yours to decide; it still happens as reality would have it). Out in the wider world, state and federal law apply as usual.
- HOUSEHOLD DEBTS are the actor's real debts, exactly as the lender has them: no other fees, penalties or terms exist. A lender may agree to let missed payments slide (op loan_relief) at realistic 1950s odds; it is never certain.
- Shop prices, wages and loans have their own rules in town: don't move money for buying goods off a shelf, borrowing from a bank, or setting pay (residents do those themselves). A private deal between two people is yours to rule on as usual.
- Channel standards: self-harm or suicide is not possible as an action (return possible=false, no effects). No sexual content in outcome text. Children are never victims of violence or abuse (impossible). No outcome may be based on race, ethnicity or religion.
OUTPUT one JSON object:
{"possible": true|false, "needs_consent_from": null|"<full name>", "breaks": [<ids of town laws this breaks, if any>], "why_not": "<if impossible: one plain sentence of what happens instead>",
 "outcomes": [ {"odds": <percent>, "outcome": "<1-2 plain sentences of what actually happens>", "visibility": "private"|"witnessed"|"public", "importance": 1-10, "effects": [...] }, ... 3 or 4 of these ]}
Each option's "effects" list uses only these operations:
 [ {"op": "money", "from": "<full name>|town|outside", "to": "<full name>|town|outside", "amount": <dollars>},
              {"op": "memory", "who": "<full name>", "text": "<what they now know>"},
              {"op": "relationship", "a": "<full name>", "b": "<full name>", "delta": <-30..30>},
              {"op": "injure", "who": "<full name>", "days": <1-90>},
              {"op": "item", "who": "<full name>", "desc": "<object they now have>"},
              {"op": "building", "who": "<full name>", "what": "<what is built>", "cost": <dollars>},
              {"op": "repair", "who": "<full name of someone who lives in the house>", "amount": <dollars spent>, "paid_by": "<full name of whoever pays, if not the household>", "labor": <dollars' worth of work donated, if any>},
              {"op": "move", "who": "<full name>", "household": true|false (the whole household moves, or just this person), "to": "<full name of the person whose home they move into>" | "<id of a vacant house>" | "new place", "terms": "rent"|"mortgage"|"own"|"free"},
              {"op": "draft", "who": "<full name>", "status": "deferred"|"dodged"|"enlisted"},
              {"op": "company", "who": "<full name>", "name": "<business name>", "industry": "<what it does>", "capital": <dollars>},
              {"op": "job", "who": "<full name>", "job": "<new job>"},
              {"op": "leave_town", "who": "<full name>", "where": "<destination>", "kind": "city"|"college"|"hollywood"|"army"|"oilfields"|"prison"},
              {"op": "discover", "who": "<full name>", "activity": "dig"|"explore"|"build"},
              {"op": "loan_relief", "who": "<full name>", "months": <1-3>} (only if the lender agrees to carry missed payments to the end of the loan),
              {"op": "thread", "title": "<short neutral title>", "truth": "<the private whole truth>", "people": ["<full names>"]} (only if this leaves something unsettled that will play out over time: a theft, a debt, a quarrel, a deal) ]"""


class Referee:
    def __init__(self, llm, mode, seed=0): self.llm = llm; self.mode = mode; self.r = random.Random(seed)

    def rule(self, w, p, attempt, here_names, recent=()):
        roll = self.r.randint(0, 99)
        if self.mode != "live":
            out = {"possible": True, "needs_consent_from": None, "outcomes": [
                {"odds": o, "outcome": f"[MOCK {tag}] {p['name']} tries: {attempt[:60]}", "visibility": "witnessed", "importance": 3,
                 "effects": [{"op": "memory", "who": p["name"], "text": f"[MOCK {tag}] I tried: {attempt[:60]}"}]} for o, tag in ((20, "worse"), (50, "as hoped"), (30, "better"))]}
            return pick(out, roll)
        h = w.households[p["household"]]
        ctx = (f"DATE: {w.date_str}. TOWN: {w.town['name']} ({w.geo}, {w.gen['region']}). PLACE: {w.places.get(p['location'], {}).get('name')}. PRESENT: {', '.join(here_names) or 'nobody'}.\n"
               f"ACTOR: {p['name']}, {p['age']}, {p['sex']}, job: {p['job']}, education: {p['education']}, health: {p['health']}, injury days: {p['injury']}. "
               f"Household savings ${int(h['savings'])}" + (f" (plus ${int(sum(h.get('deposits', {}).values()))} in the bank)" if h.get("deposits") else "") + f", debt ${int(h['debt'])}. Items: {[i['desc'] for i in p.get('items', [])]}."
               + (f" Household owns: {econ.owns_text(w, h)}." if h.get("owns") else "") + "\n"
               + (f"HOUSEHOLD DEBTS (exact; there are no others): {econ.loans_text(w, h)}\n" if econ.loans_text(w, h) else "")
               + "OUTSIDE THE TOWN: the bank in the county seat holds the town's mortgages and bank loans (reached by telephone, letter or a trip); dealers and the mail-order catalog sell goods.\n"
               + (f"TOWN LAWS: {' | '.join(law.law_lines(w, 12))}\n" if law.laws_in_force(w) else "") +
               f"HOME: {w.places.get(h['place'], {}).get('name', 'none')} ({h['home']}). VACANT HOUSES: {', '.join(k + ' = ' + v['name'] for k, v in w.places.items() if v.get('vacant')) or 'none'}.\n"
               f"TOWN TREASURY: ${int(w.town['treasury'])}. MAIN EMPLOYER: {w.companies['co1']['name']} (cash ${int(w.companies['co1']['cash'])}).\n"
               f"PEOPLE IN TOWN: {'; '.join(q['name'] + ' (' + (q['job'] or q['role']) + ')' for q in w.living())}\n"
               + (f"THIS PERSON'S OPEN MATTERS: {' | '.join(t['id'] + ': ' + t['title'] for t in w.threads if t['status'] == 'open' and p['id'] in t['people'])}\n" if any(t['status'] == 'open' and p['id'] in t['people'] for t in w.threads) else "")
               + (f"THIS PERSON'S LAST ATTEMPTS: {' | '.join(recent)}\n" if recent else "") +
               f"ATTEMPT: {attempt}")
        big = any(k in attempt.lower() for k in ("company", "bank", "land", "oil", "election", "law", "fire ", "burn", "steal", "shoot", "kill", "lawsuit", "sell the", "buy the"))
        out, raw = self.llm.call_json("referee_big" if big else "referee", [REFEREE_RULES], [{"role": "user", "content": ctx}], max_tokens=1400)
        if not out: return {"possible": False, "outcome": "(referee could not parse)", "effects": [], "visibility": "private", "importance": 1, "_raw": raw[:200], "_roll": roll}
        return pick(out, roll)


def pick(out, roll):
    """The town's dice (0-99) picks one of the referee's options by its odds. The model estimates; it never chooses."""
    opts = [o for o in (out.get("outcomes") or []) if isinstance(o, dict) and o.get("outcome")]
    if not out.get("possible", True) or not opts:
        res = {k: v for k, v in out.items() if k != "outcomes"}
        res.setdefault("outcome", out.get("why_not") or "(nothing comes of it)"); res.setdefault("effects", [])
        res.setdefault("visibility", "private"); res.setdefault("importance", 1); res["_roll"] = roll
        if not opts and out.get("possible", True) and "outcome" not in out: res["possible"] = False
        return res
    w = [max(0.0, float(o.get("odds") or 0)) for o in opts]; tot = sum(w) or len(opts); w = [x / tot if sum(w) else 1 / len(opts) for x in w]
    acc, chosen = 0.0, opts[-1]
    for o, x in zip(opts, w):
        acc += x
        if roll < acc * 100: chosen = o; break
    res = {"possible": True, "needs_consent_from": out.get("needs_consent_from"), "breaks": out.get("breaks") or chosen.get("breaks") or [], "outcome": chosen["outcome"],
           "visibility": chosen.get("visibility", "witnessed"), "importance": chosen.get("importance", 3), "effects": chosen.get("effects") or [],
           "_roll": roll, "_options": [{"odds": round(x * 100), "outcome": o["outcome"][:200]} for o, x in zip(opts, w)]}
    return res


def apply_effects(w, effects, ev, actor):
    """Validate and apply referee effects. Unknown ops or names are ignored (logged)."""
    applied = []
    for e in effects or []:
        op = e.get("op")
        try:
            if op == "money":
                amt = max(0, float(e.get("amount") or 0)); src, dst = e.get("from"), e.get("to")
                def acct(n):
                    if n == "town": return ("town", None)
                    if n == "outside": return ("outside", None)
                    q = w.by_name(n); return ("hh", w.households[q["household"]]) if q else (None, None)
                ks, hs = acct(src); kd, hd = acct(dst)
                if ks is None or kd is None: continue
                if ks == "town": w.town["treasury"] -= amt
                elif ks == "hh": hs["savings"] -= amt
                if kd == "town": w.town["treasury"] += amt
                elif kd == "hh": hd["savings"] += amt
                applied.append(e)
            elif op == "memory":
                q = w.by_name(e.get("who"))
                if q: w.minds_memory[q["id"]].add(w.day, w.slot, e.get("text", ""), 5); applied.append(e)
            elif op == "relationship":
                a, b = w.by_name(e.get("a")), w.by_name(e.get("b"))
                if a and b:
                    r = a["rel"].setdefault(b["id"], {"affinity": 0, "trust": 30, "tags": []}); r["affinity"] = max(-100, min(100, r["affinity"] + int(e.get("delta", 0)))); applied.append(e)
            elif op == "injure":
                q = w.by_name(e.get("who"))
                if q and q["age"] >= 18: q["injury"] = max(q["injury"], min(90, int(e.get("days", 5)))); applied.append(e)
            elif op == "item":
                q = w.by_name(e.get("who"))
                if q: q.setdefault("items", []).append({"desc": e.get("desc", "something"), "truth": e.get("desc"), "value": 0, "owner": q["id"], "found": w.date_str, "where": q["location"]}); applied.append(e)
            elif op == "building":
                q = w.by_name(e.get("who"))
                if q:
                    cost = float(e.get("cost") or 0); w.households[q["household"]]["savings"] -= cost; law.permit_fee(w, q, "build", ev)
                    pid = f"bld_{len(w.places)}"; w.places[pid] = {"name": e.get("what", "a new building"), "kind": "building", "owner": q["id"], "x": 0, "built": w.date_str}
                    w.discovery_roll(q, "build", ev); applied.append(e)
            elif op == "repair":
                q = w.by_name(e.get("who")); payer = w.by_name(e.get("paid_by")) if e.get("paid_by") else None
                if q and w.repair(w.households[q["household"]], payer or q, float(e.get("amount") or 0), ev, payer=w.households[payer["household"]] if payer else None, labor=float(e.get("labor") or 0)): applied.append(e)
            elif op == "move":
                q = w.by_name(e.get("who")); to = str(e.get("to") or "").strip(); terms = e.get("terms") or "rent"
                if not q: continue
                h = w.households[q["household"]]; host = w.by_name(to)
                if host:
                    hh = w.households[host["household"]]
                    for i in ([m for m in h["members"] if w.people[m]["alive"]] if e.get("household") else [q["id"]]): w.move_person(w.people[i], hh, ev)
                else:
                    target = h if e.get("household") else w.new_household(q, ev)
                    key = to if w.places.get(to, {}).get("vacant") else f"home_{target['id']}_{w.day}"
                    w.set_home(target, key, terms, ev)
                applied.append(e)
            elif op == "draft":
                q = w.by_name(e.get("who")); st = (e.get("status") or "").lower()
                if q and st in ("deferred", "dodged"): q["flags"]["dodged"] = st; q["flags"].pop("drafted_on", None); applied.append(e)
                elif q and st == "enlisted" and q["id"] == actor["id"]: w.leave_town(q, "the Army", ev, kind="army"); applied.append(e)
            elif op == "company":
                q = w.by_name(e.get("who"))
                if q:
                    cid = f"co{len(w.companies) + 1}"; cap = float(e.get("capital") or 0); w.households[q["household"]]["savings"] -= cap; law.permit_fee(w, q, "start_business", ev)
                    w.companies[cid] = {"id": cid, "name": e.get("name", f"{q['name']}'s business"), "industry": e.get("industry", "trade"), "owner": q["id"], "cash": cap,
                                        "employees": [], "wage_day": 9.0, "place": cid, "status": "open", "productivity": 13.0}  # wages about 62% of output, like co1
                    if "bank" in (w.companies[cid]["industry"] or "").lower(): w.companies[cid].update({"productivity": 2.0, "deposit_rate": None})  # a bank earns on its loans, not on labor
                    w.places[cid] = {"name": w.companies[cid]["name"], "kind": "business", "x": 0}
                    q["job"] = f"owner, {w.companies[cid]['name']}"; applied.append(e)
            elif op == "job":
                q = w.by_name(e.get("who"))
                if q and q["age"] >= 14: q["job"] = e.get("job"); applied.append(e)
            elif op == "leave_town":
                q = w.by_name(e.get("who"))
                if q and q["id"] == actor["id"]: w.leave_town(q, e.get("where", "the city"), ev, kind=e.get("kind", "city")); applied.append(e)
            elif op == "thread":
                if getattr(w, "fate", None): w.fate.open_thread({"thread": e, "record": e.get("truth", ""), "involved": []}, "attempt", ev, source="referee"); applied.append(e)
            elif op == "loan_relief":
                q = w.by_name(e.get("who"))
                if q and econ.relief(w, q, e.get("months"), ev): applied.append(e)
            elif op == "discover":
                q = w.by_name(e.get("who"))
                if q: w.discovery_roll(q, e.get("activity", "explore"), ev); applied.append(e)
        except Exception as ex:  # never let a malformed effect crash the town
            ev("engine_warning", text=f"bad effect {e}: {ex}", importance=0)
    return applied
