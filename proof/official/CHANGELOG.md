# Nobody's Town: rule changelog

The rules were locked at the roll. After that, only mechanical fixes are allowed: a fix may stop a crash
or a mechanical failure, and must not change what can happen in town. Every fix is listed here with its
exact diff and the fingerprint chain, so anyone can check it.

- Roll settings fingerprint: `ea836d0f3b6d8de2ccf6d548bf2211cd6e5021a3fa52fda37c19ade61687eced`

## Fix 1: Bank refusal text crashed when a resident asked for a loan without naming an amount (money(None)). The refusal rule already existed; only the wording of the refusal is fixed. Outcome unchanged: the loan is still turned down.

- Town day 87 (1950-03-29); recorded 2026-11-20T20:48:03+00:00
- Files: econ.py
- Fingerprint: `ea836d0f3b6d8de2ccf6d548bf2211cd6e5021a3fa52fda37c19ade61687eced` -> `f26facbcfccc1958c215260fc250307621d82b1388cebed44ba783e1289f3bb8`
- Diff sha256: `db52ef12e6091ba15740ffe79273b64821ae2c1b0c3ecfa6dce6015cafe5d837`

```diff
--- a/nt/econ.py
+++ b/nt/econ.py
@@ -521,9 +521,10 @@
     w = e.w; h = w.households[p["household"]]; kind = classify(purpose)
     inc = income_m(h); owed = payments(w, h); nm = "the bank in the county seat"
     def no(why):
-        w.minds_memory[p["id"]].add(w.day, w.slot, f"I asked {nm} for a loan of {money(amount)} ({purpose[:80]}). They turned me down: {why}.")
-        e.ev("loan_refused", actors=[p["id"]], text=f"{nm.capitalize()} turns down {p['name']}'s request for a {money(amount)} loan ({kind}): {why}.", importance=5)
-        return f"asked the county bank for {money(amount)}: turned down"
+        amt = money(amount) if amount else "an unstated amount"  # fix 1: refusal text crashed on money(None)
+        w.minds_memory[p["id"]].add(w.day, w.slot, f"I asked {nm} for a loan of {amt} ({(purpose or '')[:80]}). They turned me down: {why}.")
+        e.ev("loan_refused", actors=[p["id"]], text=f"{nm.capitalize()} turns down {p['name']}'s request for a loan of {amt} ({kind}): {why}.", importance=5)
+        return f"asked the county bank for {amt}: turned down"
     if not amount or amount <= 0: return no("they need to know how much")
     if p["age"] < 21: return no("you have to be 21 to sign a note")
     if h["credit"].get("bad_until") and h["credit"]["bad_until"] > w.date_str: return no("they know about the repossession or foreclosure on our record")
```

## Fix 2: No doctor existed in the town's data, so models invented different doctors for the same town (Dr. Whitfield, Dr. Lowry, 'Doc'; Herman Lowry is a boatyard hand). Adds one county-seat doctor, rolled once from the town's own seed on a separate dice stream (no shared first name or surname with any resident), to the fact sheet the referee and world step already see, and to a resident's notes only on days someone in their household is sick or hurt. A doctor living in town would be used instead. Consistency fix: nothing new can happen that couldn't before.

- Town day 90 (1950-04-01); recorded 2026-11-20T21:10:05+00:00
- Files: minds.py, routine.py
- Fingerprint: `f26facbcfccc1958c215260fc250307621d82b1388cebed44ba783e1289f3bb8` -> `51e0a93adddf610e99dea7c0118d54ce838c1d91c9d62d9a8bba47f9687c4e7d`
- Diff sha256: `0c12abd00c3a9e43f16fc93a68fb9f2b07837a71d65d585a579ba64829ce94ce`

```diff
--- a/nt/minds.py
+++ b/nt/minds.py
@@ -209,6 +209,10 @@
     if pl.get("burned"): notes.append(f"Your house burned down. Rebuilding would cost about ${int(h.get('repairs_needed', 0))}.")
     elif h.get("repairs_needed", 0) > 0 and pl.get("condition", 1) < 0.95: notes.append(f"Your house is damaged; fixing it would cost about ${int(h['repairs_needed'])}.")
     if p["pregnant"] and w.day - p["pregnant"]["start"] >= 60: notes.append("You're expecting a baby.")
+    sick = [q for q in [p] + [w.people[i] for i in h["members"] if i != p["id"]] if q["alive"] and (q.get("illness") or q.get("injury"))]
+    if sick:  # fix 2: someone at home is sick or hurt, so you'd know who the doctor is
+        from .routine import doctor_line
+        notes.append(doctor_line(w))
     if p.get("items"): notes.append("You have: " + "; ".join(it["desc"] for it in p["items"]) + ".")
     if p["age"] < 18 and w.date.weekday() < 5 and p["education"] == "in school": notes.append("It's a school day.")
     for e in t["elections"]:
--- a/nt/routine.py
+++ b/nt/routine.py
@@ -8,7 +8,7 @@
 Also here: the town FACT SHEET the referee and the world step see on every call (offices and when the council meets, who runs
 and works at each business, the lawman, the church), so they have nothing to guess at.
 """
-import re
+import random, re
 from . import history, econ
 
 HARD = re.compile(r"\b(steal|break|burn|threaten|fight|hit|bribe|hide|search|follow|spy|sneak|forge|poison)\b", re.I)
@@ -141,6 +141,31 @@
     return None
 
 
+def county_doctor(w):
+    """Fix 2 (Nov 20): the town had no doctor in its data, so models invented different ones (Dr. Whitfield, Dr. Lowry, "Doc").
+    A doctor who lives in town is used if there is one; otherwise one county-seat doctor, rolled once from the town's own seed on
+    a separate dice stream (so the town itself rolls the same), never sharing a first name or surname with anyone in town."""
+    here = [q for q in w.living() if re.search(r"\bdoctor\b|physician", q.get("job") or "", re.I)]
+    if here: return {"name": "Dr. " + here[0]["name"], "male": here[0]["sex"] == "male" if "sex" in here[0] else True, "in_town": True}
+    d = w.town.get("county_doctor")
+    if d: return d
+    from .names import baby_name
+    from .generator import SURNAMES
+    r = random.Random(f"{w.gen['seed']}-county-doctor")
+    taken_first = {q["name"].split()[0] for q in w.people.values()}; taken_sur = {q["name"].split()[-1] for q in w.people.values()}
+    male = r.random() < 0.94; age = r.randint(34, 66)
+    first = baby_name(r, w.gen["start"]["year"] - age, male, taken_first)
+    sur = r.choice([x for x in SURNAMES if x not in taken_sur and x != first])
+    d = {"name": f"Dr. {first} {sur}", "male": male, "in_town": False}; w.town["county_doctor"] = d
+    return d
+
+
+def doctor_line(w):
+    d = county_doctor(w); he = "he" if d["male"] else "she"
+    if d.get("in_town"): return f"The town doctor is {d['name']}."
+    return f"No doctor lives in town; the doctor people here use is {d['name']} in the county seat, reached by telephone ({he} makes house calls)."
+
+
 def fact_sheet(w):
     """What anyone in town knows as plain fact. Shown to the referee and the world step on every call."""
     t = w.town; off = t["offices"]; nm = lambda i: w.people[i]["name"] if i and i in w.people else None
@@ -159,5 +184,6 @@
     law = [q["name"] + f" ({q['job']})" for q in w.living() if any(x in (q.get("job") or "") for x in ("marshal", "sheriff"))]
     lines.append(f"THE LAW: {', '.join(law) or 'none in town; the county sheriff, from the county seat'}.")
     clergy = [q["name"] for q in w.living() if re.search(r"preacher|minister|pastor|priest|reverend", q.get("job") or "", re.I)]
+    lines.append("DOCTOR: " + doctor_line(w))
     lines.append("CHURCH: the church holds services Sunday mornings; " + (f"church people in town: {', '.join(clergy)}." if clergy else "no minister lives in town."))
     return "\n".join(lines)
```

## Fix 3: World-step and thread records could say money changed hands or went missing with no money operation, so household books never moved (the Duvals' savings tin, Jan 1950: books unchanged, no amount ever known). Adds the requirement to the options format, and when an option says money moved without a money operation, asks the model once to add the exact amount (or reword). The odds are kept exactly as first estimated and the dice pick among the same options.

- Town day 90 (1950-04-01); recorded 2026-11-20T21:10:19+00:00
- Files: fate.py
- Fingerprint: `51e0a93adddf610e99dea7c0118d54ce838c1d91c9d62d9a8bba47f9687c4e7d` -> `25a2aef3ee10a8a82bba63b8886d0351f0e58ae56c19ca726d22483b454c5726`
- Diff sha256: `56c3dc19d653e18a26523c1bf992be989d3755d2964e4507f23a6c59abb056b3`

```diff
--- a/nt/fate.py
+++ b/nt/fate.py
@@ -9,7 +9,7 @@
 resolved, given up, gone cold, or gone (everyone involved dead or away). Nothing goes quiet without an ending in the record.
 The model never decides a resident's choices; residents act on threads themselves, and what they did is shown to the step.
 """
-import json, random
+import json, random, re
 from . import law as L, econ, routine
 
 # (category, unit, yearly rate per unit, season weights or None, source)
@@ -46,6 +46,7 @@
 - Use exact full names from the list. Never decide what a resident chooses, says or feels; only what happens to them and around them.
 - If it leaves something unsettled that will play out over time (a crime, a stranger who stays, a debt, an injury, a show in town, a quarrel), open a thread.
 - If it is an event people could go to (a show, a social, a game, a revival), give it a place with hours, days and price.
+- If money changes hands or goes missing (stolen, lost, found, paid, docked, won), that option must carry a money operation with the exact amount.
 """ + STANDARDS + """
 OUTPUT one JSON object:
 {"options": [ {"odds": <percent>,
@@ -71,6 +72,7 @@
 - Real matters end. An option may end it: "resolved" (settled one way or another), "given_up" (people let it go), "cold" (no answer, and none coming),
   but only when that is realistic now. Long-quiet matters do go cold.
 - If someone is caught, the law follows period procedure: questioning, the county court, a fine, jail time or release.
+- If money changes hands or goes missing (stolen, lost, found, paid, docked, won), that option must carry a money operation with the exact amount.
 """ + STANDARDS + """
 OUTPUT one JSON object:
 {"options": [ {"odds": <percent>, "record": "<what happens, 1-2 plain sentences; for 'nothing new yet' say so>",
@@ -78,6 +80,37 @@
    "said": "<how word gets around, if it does>", "importance": 1-10, "effects": [<same operations as before>],
    "end": null|"resolved"|"given_up"|"cold", "truth_update": "<new private facts, if any>"} ]}
 Operations: money, memory, relationship, injure, item, fire, jail, newcomer (same shapes as the world step)."""
+
+
+# Fix 3 (Nov 20): a record that says money moved must move money. At the Q1 midpoint the Duvals' savings "went missing" in the
+# record but no money operation came with it, so their books never changed and nobody knew how much was gone.
+MONEY_NOUN = re.compile(r"\$\s?\d|\bdollars?\b|\bmoney\b|\bsavings\b|\bcash\b|\bpay envelope\b|\bwages?\b|\bpaycheck\b", re.I)
+MONEY_VERB = re.compile(r"\b(stole|stolen|steals?|took|taken|takes|missing|gone|lost|loses|found|finds|paid|pays|spent|spends|docked|short|won|wins|gave|gives|lent|lends|borrowed|owes?d?|cost|costs|fined)\b", re.I)
+
+
+def money_unbacked(o):
+    """True if an option's record says money changed hands but it carries no money operation."""
+    if any(isinstance(x, dict) and x.get("op") == "money" and x.get("amount") for x in (o.get("effects") or [])): return False
+    rec = str(o.get("record") or o.get("text") or "")
+    if "nothing new" in rec.lower(): return False
+    return bool(MONEY_NOUN.search(rec) and MONEY_VERB.search(rec))
+
+
+def ask_options(llm, role, system, msg, max_tokens):
+    """Ask for the options; if any says money moved without a money operation, ask once more to fix just that. Then the dice roll as before."""
+    out, raw = llm.call_json(role, system, [{"role": "user", "content": msg}], max_tokens=max_tokens)
+    opts = (out or {}).get("options") or []
+    bad = [i + 1 for i, o in enumerate(opts) if isinstance(o, dict) and money_unbacked(o)]
+    if not bad: return out, raw
+    note = (f"Option{'s' if len(bad) > 1 else ''} {', '.join(map(str, bad))} say{'' if len(bad) > 1 else 's'} money changed hands or went missing but carr{'y' if len(bad) > 1 else 'ies'} no money operation. "
+            "Return the same JSON with the same options and odds, adding a money operation with the exact amount to each of those options "
+            "(or, if no money actually changes hands, rewording the record to say so). Change nothing else.")
+    out2, raw2 = llm.call_json(role, system, [{"role": "user", "content": msg}, {"role": "assistant", "content": raw}, {"role": "user", "content": note}], max_tokens=max_tokens)
+    opts2 = (out2 or {}).get("options") or []
+    if len(opts2) != len(opts): return out, raw
+    for a, b in zip(opts, opts2):  # the odds stay exactly as first estimated; only the money operations are filled in
+        if isinstance(a, dict) and isinstance(b, dict): b["odds"] = a.get("odds")
+    return out2, raw2
 
 
 def roll(r, opts):
@@ -152,7 +185,7 @@
         if self.e.mode != "live": out = self.mock_options(cat, u)
         else:
             msg = self.base_ctx() + "\n" + self.unit_text(cat, u)
-            out, raw = self.e.llm.call_json("world_big" if cat in BIG else "world", [FATE_RULES], [{"role": "user", "content": msg}], max_tokens=2200)
+            out, raw = ask_options(self.e.llm, "world_big" if cat in BIG else "world", [FATE_RULES], msg, 2200)
         ch, odds, d = roll(self.r, (out or {}).get("options") or [])
         if not ch: return
         self.apply(ch, ev, cat, odds, d, (out or {}).get("options") or [])
@@ -256,7 +289,7 @@
                        f"SO FAR:\n" + "\n".join("- " + hline for hline in th["history"][-10:]) + "\n"
                        + (f"WHAT THE PEOPLE INVOLVED DID LATELY:\n" + "\n".join("- " + x for x in lately) + "\n" if lately else "WHAT THE PEOPLE INVOLVED DID LATELY: nothing about this.\n")
                        + (f"AT {pl['name'].upper()} TODAY: {', '.join(there) or 'nobody from town went'}.\n" if there is not None and pl else ""))
-                out, raw = self.e.llm.call_json("world_big" if th["kind"] in BIG else "world", [THREAD_RULES.replace("{span}", span)], [{"role": "user", "content": msg}], max_tokens=1800)
+                out, raw = ask_options(self.e.llm, "world_big" if th["kind"] in BIG else "world", [THREAD_RULES.replace("{span}", span)], msg, 1800)
             th["last_step"] = w.day
             ch, odds, d = roll(self.r, (out or {}).get("options") or [])
             if not ch: continue
```
