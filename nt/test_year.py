"""Resumable TEST-town runner (never the official town). Saves after every day; run the same command again to continue.
usage: python3 -m nt.test_year <seed> [--budget USD] [--days N] [--minutes M] [--mock]
  --budget   hard cap for THIS session's spend (the meter starts at 0 each session; earlier spend is in api_calls.jsonl)
  --days     stop after this many town-days in total (default 91 = one quarter)
  --minutes  stop cleanly after about M minutes (keep foreground chunks under 9)"""
import json, os, pickle, sys, time
from .generator import generate
from .llm import LLM, BudgetExceeded

HOME = "/home/claude/nobodys_town/TEST"


def main():
    a = sys.argv[1:]
    seed = int(a[0]); opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d
    budget, days, minutes, mode = opt("--budget", 5.0), opt("--days", 91), opt("--minutes", 0.0), "mock" if "--mock" in a else "live"
    from .engine import Engine
    run = os.path.join(HOME, f"year_{seed}"); os.makedirs(run, exist_ok=True); state = os.path.join(run, "state.pkl")
    if os.path.exists(state):
        e = pickle.load(open(state, "rb"))
        for f in ("events.jsonl", "dialogues.jsonl", "snapshots.jsonl"):  # drop records of a day cut short (budget or crash), so the redone day isn't counted twice
            p = os.path.join(run, f)
            if os.path.exists(p):
                rows = [l for l in open(p) if json.loads(l)["day"] < e.w.day]; open(p, "w").writelines(rows)
        e.reopen(run, LLM(mode, budget, os.path.join(run, "api_calls.jsonl")), mode)
    else:
        gen = generate(seed); gen["fingerprint"] = "TEST"; json.dump(gen, open(os.path.join(run, "world.json"), "w"), indent=1)
        e = Engine(gen, run, mode, budget, workers=8)
    e.compress = True; t0 = time.time(); stop = None
    def save():
        tmp = state + ".tmp"; pickle.dump(e, open(tmp, "wb")); os.replace(tmp, state)
    try:
        while e.w.day < days:
            e.run_day(); save()
            print(f"day {e.w.day}/{days}  {e.w.date_str}  session ${e.llm.meter.spent:.2f}", flush=True)
            if minutes and time.time() - t0 > minutes * 60: stop = "paused (time limit)"; break
    except BudgetExceeded as ex: stop = f"budget cap: {ex}"
    print(json.dumps({"seed": seed, "town": e.w.town["name"], "day": e.w.day, "of": days, "status": stop or "done", "session_usd": round(e.llm.meter.spent, 3),
                      "by_role": {k: round(v["usd"], 3) for k, v in e.llm.meter.by_role.items()}, "tokens": e.llm.meter.tokens}))


if __name__ == "__main__":
    main()
