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
