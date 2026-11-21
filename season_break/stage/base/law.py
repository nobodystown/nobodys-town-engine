"""Laws that bind (approved by Aaron, Nov 18 9:56pm).

When the council passes a measure, a neutral town clerk writes down what it binds people to, using a fixed list of operations.
The clerk never adds anything the measure doesn't say, never judges it, never enforces it. From then on it is real:
  tax, spend, pay (a town salary), license, permit, price_cap, min_wage, closing: the town's books and shops simply follow them.
  ban: anyone can still break it. Whether a breach is noticed is the dice (how public it was); whether the marshal fines anyone
       is the marshal's own decision (action "enforce"). A marshal can also fine someone with nothing on record: that's on them.
  repeal: takes an earlier law off the books.
What can't be put into those operations stays on the books as words only ("unbound"), the way a resolution does.
"""
import json, re
from . import econ

CLERK_RULES = """You are the town clerk of a small American town. The town council has just passed a measure. Write down, neutrally and exactly, what it binds people to, using only the operations below.
- Never add anything the measure does not say. Never judge whether it is wise, legal or fair. Never enforce it yourself.
- Use people's exact full names and the place ids given. Dollar amounts as numbers.
- Anything in the measure that can't be put into these operations (a statement, thanks, a request to the county or state, a plan with no money attached) goes in "unbound", in plain words.
Operations:
 {"op":"tax","per_household_quarter":<dollars>}                      the town tax each household pays every quarter
 {"op":"spend","amount":<dollars>,"to":"<full name of a resident>"|"outside","for":"<what>"}   one payment from the treasury, now
 {"op":"pay","to":"<full name>","amount":<dollars>,"per":"month"|"year","for":"<the post or work>"}   a standing town salary
 {"op":"license","applies_to":"all businesses"|"<business name or place id>","fee":<dollars>,"per":"year"}
 {"op":"permit","for":"build"|"start_business","fee":<dollars>}      a fee to the town before building or opening a business
 {"op":"ban","what":"<the forbidden conduct, plainly>","fine":<dollars>}   the marshal decides whether to fine anyone who breaks it
 {"op":"closing","place":"<place id>","when":"sunday"|"night"|"always"}
 {"op":"price_cap","place":"store"|"diner","max":<store: percent above county-seat prices; diner: dollars for a meal>}
 {"op":"min_wage","per_week":<dollars>}                               the least anyone employed in town may be paid
 {"op":"repeal","law":"<law id>"}
Reply with one JSON object only: {"summary":"<one plain sentence: what the law now requires>", "ops":[...], "unbound":"<plain words, or empty>"}"""

ENFORCERS = ("town marshal", "deputy sheriff", "marshal", "constable", "sheriff")


def laws_in_force(w): return [l for l in w.town.get("laws", []) if not l.get("repealed")]


def law_lines(w, k=8):
    out = []
    for l in laws_in_force(w)[-k:]:
        out.append(f"{l.get('id', '?')}: {l.get('summary') or l['text']}")
    return out


def enact(e, m):
    """A measure has passed. The clerk records what it binds; the town follows it from today."""
    w = e.w
    lid = f"L{len(w.town['laws']) + 1}"
    law = {"id": lid, "text": m["text"], "day": w.day, "date": w.date_str, "by": m["by"], "ops": [], "summary": m["text"], "unbound": ""}
    out = interpret(e, m["text"])
    law["summary"] = str(out.get("summary") or m["text"])[:300]; law["unbound"] = str(out.get("unbound") or "")[:300]
    ops = [o for o in (out.get("ops") or []) if isinstance(o, dict) and o.get("op") in OPS]
    law["ops"] = ops
    w.town["laws"].append(law)
    done = []
    for o in ops:
        try: r = OPS[o["op"]](e, law, o)
        except Exception as ex:
            e.ev("engine_warning", text=f"law {lid} op {o}: {ex}", importance=0); r = None
        if r: done.append(r)
    e.ev("law_enacted", actors=[m["by"]], text=f"Town law {lid} takes effect: {law['summary']}" + (f" ({'; '.join(done)})" if done else ""), importance=7, public=True,
         data={"law": lid, "ops": ops, "unbound": law["unbound"], "said": f"The council passed a new town rule: {law['summary']}"})
    return law


def interpret(e, text):
    w = e.w
    if e.mode != "live":  # mock: only a plain tax line is read; everything else stays words
        t = re.search(r"tax[^$]*\$\s?(\d+)", text.lower()); f = re.search(r"(?:ban|forbid|no )([^$]*?)(?:fine|\$)\s*\$?(\d+)", text.lower())
        ops = [{"op": "tax", "per_household_quarter": int(t.group(1))}] if t else []
        if f and not t: ops.append({"op": "ban", "what": f.group(1).strip() or text[:80], "fine": int(f.group(2))})
        return {"summary": text[:200], "ops": ops, "unbound": "" if ops else text[:200]}
    places = "; ".join(f"{k} = {v['name']}" for k, v in w.places.items() if v.get("kind") in ("diner", "store", "town_hall", "school", "company", "business", "building", "outdoors"))
    ctx = (f"DATE: {w.date_str}. TOWN: {w.town['name']}. TREASURY: ${int(w.town['treasury'])}. TAX NOW: ${w.town['tax_per_household_quarter']} per household a quarter.\n"
           f"LAWS IN FORCE: {' | '.join(law_lines(w, 20)) or 'none'}\nPLACES: {places}\n"
           f"RESIDENTS: {'; '.join(q['name'] + ' (' + (q['job'] or q['role']) + ')' for q in w.living() if q['age'] >= 18)}\n"
           f"THE MEASURE AS PASSED: {text}")
    out, raw = e.llm.call_json("law", [CLERK_RULES], [{"role": "user", "content": ctx}], max_tokens=900)
    return out or {"summary": text[:200], "ops": [], "unbound": text[:200]}


# ------------------------------------------------------------------ what each operation does
def _num(x, d=0.0):
    try: return float(x)
    except (TypeError, ValueError): return d


def op_tax(e, law, o):
    v = int(round(_num(o.get("per_household_quarter"), -1)))
    if v < 0: return None
    e.w.town["tax_per_household_quarter"] = v; return f"tax now ${v} a quarter"


def op_spend(e, law, o):
    w = e.w; amt = max(0.0, _num(o.get("amount"))); have = max(0.0, w.town["treasury"]); paid = min(amt, have)
    if paid <= 0: return "the treasury had nothing to pay with"
    w.town["treasury"] -= paid; q = w.by_name(o.get("to")) if o.get("to") not in (None, "outside") else None
    if q:
        hh = w.households[q["household"]]; hh["savings"] += paid; w.earned(hh, paid)
        w.minds_memory[q["id"]].add(w.day, w.slot, f"The town paid me ${int(paid)} under {law['id']} ({o.get('for', '')}).")
    return f"${int(paid)} paid out" + (f" to {q['name']}" if q else "") + (f" for {o.get('for')}" if o.get("for") else "") + (f" (${int(amt - paid)} short)" if paid < amt else "")


def op_pay(e, law, o):
    q = e.w.by_name(o.get("to")); return f"a town salary for {q['name']}" if q else None


def op_license(e, law, o):
    charge_licenses(e, [(law, o)]); return f"a ${int(_num(o.get('fee')))} license fee"


def op_noop(e, law, o): return None


def op_repeal(e, law, o):
    w = e.w; tgt = str(o.get("law") or "").strip().upper()
    for l in w.town["laws"]:
        if l.get("id") == tgt and not l.get("repealed"):
            l["repealed"] = w.date_str
            if any(x.get("op") == "tax" for x in l.get("ops") or []): pass  # the tax stays where it is until another law sets it
            return f"{tgt} repealed"
    return None


OPS = {"tax": op_tax, "spend": op_spend, "pay": op_pay, "license": op_license, "permit": op_noop, "ban": op_noop, "closing": op_noop,
       "price_cap": op_noop, "min_wage": op_noop, "repeal": op_repeal}


def active_ops(w, name):
    return [(l, o) for l in laws_in_force(w) for o in (l.get("ops") or []) if o.get("op") == name]


def businesses(w):
    """(name, place id, owning household id) for every business in town."""
    out = [(c["name"], c.get("place"), w.people[c["owner"]]["household"]) for c in w.companies.values() if c["status"] == "open" and w.people[c["owner"]]["alive"]]
    for k, s in w.shops.items():
        if s["owner_h"] in w.households: out.append(("the diner" if k == "diner" else "the general store", k, s["owner_h"]))
    return out


def charge_licenses(e, items=None):
    w = e.w
    for law, o in (items or active_ops(w, "license")):
        fee = max(0.0, _num(o.get("fee"))); tgt = str(o.get("applies_to") or "all businesses").lower()
        if fee <= 0: continue
        for nm, pid, hid in businesses(w):
            if tgt.startswith("all") or tgt in nm.lower() or (pid and tgt == str(pid).lower()):
                h = w.households[hid]; h["savings"] -= fee; w.town["treasury"] += fee
                for a in [i for i in h["members"] if w.people[i]["alive"] and w.people[i]["age"] >= 18][:2]:
                    w.minds_memory[a].add(w.day, w.slot, f"We paid the town ${int(fee)} for the license on {nm} ({law['id']}).")


def monthly(e, ev):
    """Standing town salaries come out of the treasury on the first of the month (if the money is there); licenses each January."""
    w = e.w
    for law, o in active_ops(w, "pay"):
        q = w.by_name(o.get("to"))
        if not q or not q["alive"]: continue
        amt = max(0.0, _num(o.get("amount"))); amt = amt / 12 if str(o.get("per", "month")).startswith("y") else amt
        if amt <= 0: continue
        if w.town["treasury"] >= amt:
            w.town["treasury"] -= amt; hh = w.households[q["household"]]; hh["savings"] += amt; w.earned(hh, amt)
        else:
            w.minds_memory[q["id"]].add(w.day, 0, f"The town couldn't pay my ${int(amt)} this month under {law['id']}: the treasury is short.")
            ev("town_short", actors=[q["id"]], text=f"The treasury can't cover {q['name']}'s ${int(amt)} town pay this month ({law['id']}).", importance=5)
    if w.date.month == 1: charge_licenses(e)


def permit_fee(w, p, kind, ev):
    """Called when someone builds or opens a business: the town's permit fee, if a law sets one."""
    for law, o in active_ops(w, "permit"):
        if str(o.get("for", "")).lower().startswith(kind[:5]):
            fee = max(0.0, _num(o.get("fee")))
            if fee <= 0: continue
            h = w.households[p["household"]]; h["savings"] -= fee; w.town["treasury"] += fee
            w.minds_memory[p["id"]].add(w.day, w.slot, f"I paid the town a ${int(fee)} permit fee ({law['id']}).")
            ev("permit", actors=[p["id"]], text=f"{p['name']} pays the town a ${int(fee)} permit fee ({law['id']}).", importance=3)


def bans_text(w):
    return [f"{l['id']}: forbidden: {o.get('what')} (fine ${int(_num(o.get('fine')))})" for l, o in active_ops(w, "ban")]


def record_breach(e, p, law_ids, outcome, visibility):
    """The referee judged that an attempt broke a town ban. Whether the law hears of it is chance, by how public it was."""
    w = e.w
    for lid in law_ids or []:
        lid = str(lid).strip().upper()
        law = next((l for l in laws_in_force(w) if l.get("id") == lid and any(o.get("op") == "ban" for o in l.get("ops") or [])), None)
        if not law: continue
        b = {"law": lid, "who": p["id"], "day": w.day, "date": w.date_str, "what": str(outcome)[:200], "enforced": False}
        w.town.setdefault("breaches", []).append(b)
        e.ev("breach", actors=[p["id"]], text=f"{p['name']} breaks town law {lid}: {str(outcome)[:160]}", importance=4, data={"law": lid, "visibility": visibility})
        for m in lawmen(w):
            if m["id"] == p["id"]: continue
            odds = 1.0 if m["location"] == p["location"] and visibility != "private" else {"public": 0.8, "witnessed": 0.35}.get(visibility, 0.05)
            if w.rng.random() < odds:
                w.minds_memory[m["id"]].add(w.day, w.slot, f"Word reached me that {p['name']} broke town law {lid} ({law['summary'][:100]}): {str(outcome)[:140]}")


def lawmen(w): return [q for q in w.living() if any(k in (q.get("job") or "").lower() for k in ENFORCERS)]


def enforce(e, m, q, detail):
    """The marshal's own decision: fine someone under a town ban."""
    w = e.w
    if not any(k in (m.get("job") or "").lower() for k in ENFORCERS):
        w.minds_memory[m["id"]].add(w.day, w.slot, "Only the town's lawman can fine anyone under a town law."); return None
    if not q or q["id"] == m["id"]: return None
    bans = active_ops(w, "ban")
    if not bans: w.minds_memory[m["id"]].add(w.day, w.slot, "There's no town law with a fine to enforce."); return None
    d = (detail or "").upper()
    pick = next(((l, o) for l, o in bans if l["id"] in d), None)
    if not pick:
        words = {x for x in re.findall(r"[a-z]{4,}", (detail or "").lower())}
        pick = max(bans, key=lambda lo: len(words & set(re.findall(r"[a-z]{4,}", (lo[1].get("what") or "").lower()))))
    law, o = pick; fine = max(0.0, _num(o.get("fine")))
    rec = next((b for b in reversed(w.town.get("breaches", [])) if b["law"] == law["id"] and b["who"] == q["id"] and not b["enforced"]), None)
    if rec: rec["enforced"] = True
    h = w.households[q["household"]]; h["savings"] -= fine; w.town["treasury"] += fine
    w.minds_memory[q["id"]].add(w.day, w.slot, f"{m['name']} fined me ${int(fine)} under town law {law['id']} ({o.get('what')}).")
    e.ev("fined", actors=[m["id"], q["id"]], text=f"{m['name']} fines {q['name']} ${int(fine)} under town law {law['id']} ({o.get('what')}).", importance=6, public=True,
         data={"law": law["id"], "on_record": bool(rec), "said": f"{m['name']} fined {q['name']} ${int(fine)} for breaking the town rule against {o.get('what')}."})
    return f"fined {q['name']} ${int(fine)} ({law['id']})"
