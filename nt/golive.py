"""Nobody's Town control script.
  python3 -m nt.golive ping                       one tiny API call: key + credits OK?
  python3 -m nt.golive smoke                      live 2-day test on a TEST town, $1 cap; prints real cost + sample dialogue
  python3 -m nt.golive fix "<reason>" --base DIR   record a post-lock mechanical fix (diff vs DIR) in fixes.json + CHANGELOG.md
  python3 -m nt.golive roll                       ONE-TIME official town roll (true randomness) + fingerprint. Refuses if one exists.
  python3 -m nt.golive season <n> [--budget 15]   run the next season (episode n) of the OFFICIAL town, live, continuing the saved state
  python3 -m nt.golive episode <n>                editor (live) + render + voice scripts by role + subtitles + thumbnail
"""
import json, os, pickle, random, sys, hashlib
from .llm import LLM, ping
from .generator import generate, fingerprint, VERSION

HOME = "/home/claude/nobodys_town"; OFFICIAL = os.path.join(HOME, "OFFICIAL"); TEST = os.path.join(HOME, "TEST")
SEASON_DAYS = 365  # about one year per episode (smoke-test estimate only; real episodes end on December 31, see cmd_season)
# Every file that decides what happens in town. fate.py (world events, rates, threads) and llm.py (which model plays which role)
# were added Nov 18: before that, both could have been changed after the roll without the lock noticing.
RULE_FILES = ("generator.py", "world.py", "history.py", "minds.py", "referee.py", "engine.py", "fate.py", "llm.py", "names.py", "econ.py", "law.py", "routine.py")  # econ + law + routine added Nov 18


def settings_fingerprint(here=None):
    """Hash of every rule file (RULE_FILES). Published at launch."""
    here = here or os.path.dirname(__file__); h = hashlib.sha256()
    for f in RULE_FILES:
        h.update(open(os.path.join(here, f), "rb").read())
    return h.hexdigest()


# ---- Post-lock mechanical fixes (approved by Aaron, Nov 20 2026) ----
# A fix may only stop a crash or a mechanical failure; it must not change what can happen in town.
# Each fix is recorded with its reason, the town day, the exact diff and old -> new fingerprint, in
# OFFICIAL/fixes.json and the public OFFICIAL/CHANGELOG.md. `season` runs only if the chain is unbroken
# from the roll fingerprint to the code on disk.
def fixes_path(): return os.path.join(OFFICIAL, "fixes.json")


def load_fixes():
    p = fixes_path(); return json.load(open(p)) if os.path.exists(p) else []


def chain_ok(gen, current=None):
    """True if the code on disk is the roll fingerprint or the end of an unbroken fix chain from it."""
    current = current or settings_fingerprint(); head = gen.get("settings_fingerprint")
    for i, f in enumerate(load_fixes()):
        if f["n"] != i + 1 or f["old_fingerprint"] != head: return False, f"fix chain broken at fix {i + 1}"
        if hashlib.sha256(f["diff"].encode()).hexdigest() != f["diff_sha256"]: return False, f"fix {i + 1} diff was altered"
        head = f["new_fingerprint"]
    return (current == head), ("ok" if current == head else "rule files changed outside the fix log")


def write_changelog(fixes, gen):
    L = ["# Nobody's Town: rule changelog", "",
         "The rules were locked at the roll. After that, only mechanical fixes are allowed: a fix may stop a crash",
         "or a mechanical failure, and must not change what can happen in town. Every fix is listed here with its",
         "exact diff and the fingerprint chain, so anyone can check it.", "",
         f"- Roll settings fingerprint: `{gen.get('settings_fingerprint')}`", ""]
    for f in fixes:
        L += [f"## Fix {f['n']}: {f['reason']}", "",
              f"- Town day {f['town_day']} ({f['town_date']}); recorded {f['recorded']}",
              f"- Files: {', '.join(f['files'])}",
              f"- Fingerprint: `{f['old_fingerprint']}` -> `{f['new_fingerprint']}`",
              f"- Diff sha256: `{f['diff_sha256']}`", "", "```diff", f["diff"].rstrip(), "```", ""]
    open(os.path.join(OFFICIAL, "CHANGELOG.md"), "w").write("\n".join(L))


def cmd_fix(reason, base):
    """Record a mechanical fix: `golive fix "<reason>" --base <dir with the currently-locked rule files>`."""
    import difflib, datetime as dt
    gen = json.load(open(os.path.join(OFFICIAL, "world.json"))); fixes = load_fixes()
    head = fixes[-1]["new_fingerprint"] if fixes else gen["settings_fingerprint"]
    ok, why = chain_ok(gen, head)
    if not ok: sys.exit(f"Refusing: existing chain is not valid ({why}).")
    if settings_fingerprint(base) != head: sys.exit("Refusing: --base is not the currently locked code (fingerprint mismatch).")
    if not reason.strip(): sys.exit("A reason is required.")
    here = os.path.dirname(__file__); diff = ""; files = []
    for f in RULE_FILES:
        a = open(os.path.join(base, f)).readlines(); b = open(os.path.join(here, f)).readlines()
        d = "".join(difflib.unified_diff(a, b, f"a/nt/{f}", f"b/nt/{f}"))
        if d: diff += d; files.append(f)
    if not diff: sys.exit("No rule-file changes to record.")
    st = os.path.join(OFFICIAL, "state.pkl"); day, date = None, None
    if os.path.exists(st):
        e = pickle.load(open(st, "rb")); day, date = e.w.day, e.w.date_str
    fixes.append({"n": len(fixes) + 1, "reason": reason, "town_day": day, "town_date": date, "files": files,
                  "recorded": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                  "old_fingerprint": head, "new_fingerprint": settings_fingerprint(), "diff": diff,
                  "diff_sha256": hashlib.sha256(diff.encode()).hexdigest()})
    json.dump(fixes, open(fixes_path(), "w"), indent=1); write_changelog(fixes, gen)
    print(f"recorded fix {len(fixes)}: {head[:12]} -> {fixes[-1]['new_fingerprint'][:12]} ({', '.join(files)})")


def cmd_ping():
    llm = LLM("live", 0.05); t, u, m = ping(llm); print("reply:", t, "| cost:", m)


def cmd_smoke():
    from .engine import Engine
    os.makedirs(TEST, exist_ok=True)
    gen = generate(random.Random().randrange(10 ** 9)); gen["fingerprint"] = "TEST"
    out = os.path.join(TEST, f"smoke_{gen['seed']}"); json.dump(gen, open(out + "_world.json", "w"))
    e = Engine(gen, out, "live", budget=1.0, workers=6); s = e.run(2)
    print(json.dumps({k: s[k] for k in ("days_run", "events", "dialogues", "seconds", "cost", "stopped")}, indent=1))
    per_day = s["cost"]["usd"] / max(1, s["days_run"])
    print(f"\nLIVE COST: ${per_day:.3f} per town-day  ->  ~${per_day * SEASON_DAYS:.2f} per episode (one season)")
    for d in e.dialogues[:3]:
        print("\n--", e.w.name(d["a"]), "&", e.w.name(d["b"]), f"({d['medium']}):")
        for sp, t in d["lines"]: print(f"   {sp}: {t}")


def cmd_roll():
    if os.path.exists(os.path.join(OFFICIAL, "world.json")): sys.exit("An official town already exists. It is rolled once and never re-rolled.")
    os.makedirs(OFFICIAL, exist_ok=True)
    seed = random.SystemRandom().randrange(10 ** 12)
    gen = generate(seed); gen["fingerprint"] = fingerprint(seed); gen["settings_fingerprint"] = settings_fingerprint()
    json.dump(gen, open(os.path.join(OFFICIAL, "world.json"), "w"), indent=1)
    proof = {"seed": seed, "generator": VERSION, "world_fingerprint": gen["fingerprint"], "settings_fingerprint": gen["settings_fingerprint"], "rule_files": list(RULE_FILES), "outside_minds": "about 17.5% of adults (minds.OUTSIDE_SHARE), split DeepSeek 50 / GPT 25 / Gemini 25, dice stream '<seed>-outside-minds'"}
    json.dump(proof, open(os.path.join(OFFICIAL, "PROOF.json"), "w"), indent=1)
    print(f"OFFICIAL TOWN: {gen['name']} — {gen['geography']}, {gen['region']}, {gen['start']['season']} {gen['start']['year']}, population {gen['population']}")
    print(json.dumps(proof, indent=1))


def trim_unsaved(out, day):
    """A run killed mid-day leaves that day's half-written records behind; the saved state replays the day from its start.
    Drop records for days >= the saved day so a day is never logged twice. (api_calls.jsonl is kept: that money was spent.)"""
    for f in ("events.jsonl", "dialogues.jsonl", "snapshots.jsonl"):
        path = os.path.join(out, f)
        if not os.path.exists(path): continue
        rows = open(path).readlines(); keep = [l for l in rows if json.loads(l)["day"] < day]
        if len(keep) != len(rows):
            tmp = path + ".tmp"; open(tmp, "w").writelines(keep); os.replace(tmp, path)
            print(f"trimmed {len(rows) - len(keep)} unsaved rows from {f} (day {day} replays)", flush=True)


def cmd_season(n, budget, minutes=None):
    """Runs (or resumes) season n of the OFFICIAL town. Saves after EVERY day, so an interrupted run loses at most one day.
    --minutes M stops cleanly after about M minutes; run the same command again to continue."""
    import time
    from .engine import Engine
    from .llm import BudgetExceeded
    gen = json.load(open(os.path.join(OFFICIAL, "world.json")))
    ok, why = chain_ok(gen)
    if not ok: sys.exit(f"Rule files changed since the official roll ({why}). Refusing to run (that would be steering).")
    state = os.path.join(OFFICIAL, "state.pkl"); out = os.path.join(OFFICIAL, "run"); os.makedirs(out, exist_ok=True)
    if os.path.exists(state):
        e = pickle.load(open(state, "rb")); trim_unsaved(out, e.w.day)
        e.reopen(out, LLM("live", budget, os.path.join(out, "api_calls.jsonl")))
    else:
        e = Engine(gen, out, "live", budget, workers=8)
        from .minds import assign_outside_share
        got = assign_outside_share(e.w, gen["seed"])  # private record: never published, never in snapshots
        json.dump({e.w.people[k]["name"]: m for k, m in got.items()}, open(os.path.join(OFFICIAL, "outside_minds.json"), "w"), indent=1)
        print(f"outside minds: {len(got)} of {sum(1 for p in e.w.people.values() if p['alive'] and p['age'] >= 18)} adults", flush=True)
    e.compress = True
    from . import history
    year = gen["start"]["year"] + n - 1  # episode n is one calendar year (episode 1 = 1950)
    if year > history.ERA_THROUGH:
        sys.exit(f"Episode {n} is {year}, past the published era data (through {history.ERA_THROUGH}). Publish the next decade's era data first (season break).")
    prog = getattr(e, "progress", None)
    if not prog or prog["episode"] != n: e.progress = prog = {"episode": n, "first_day": e.w.day}
    import datetime as dt
    end = prog["first_day"] + (dt.date(year + 1, 1, 1) - max(e.w.date, dt.date(year, 1, 1))).days + (e.w.day - prog["first_day"]); t0 = time.time(); stop = None
    def save():
        tmp = state + ".tmp"; pickle.dump(e, open(tmp, "wb")); os.replace(tmp, state)
    try:
        while e.w.day < end:
            e.run_day(); save()
            print(f"day {e.w.day}/{end}  {e.w.date_str}  spent ${e.llm.meter.spent:.2f}", flush=True)
            if minutes and time.time() - t0 > minutes * 60: stop = "paused (time limit); run again to continue"; break
    except BudgetExceeded as ex: stop = f"budget cap: {ex}"
    if e.w.day >= end:
        json.dump({"episode": n, "first_day": prog["first_day"], "last_day": e.w.day - 1}, open(os.path.join(out, f"season_{n}.json"), "w"))
        e.progress = None; save(); stop = stop or "season complete"
    print(json.dumps({"episode": n, "day": e.w.day, "end": end, "status": stop, "spent_this_session": round(e.llm.meter.spent, 3)}))


def cmd_episode(n):
    from .editor import build_episode
    from . import assemble
    gen = json.load(open(os.path.join(OFFICIAL, "world.json"))); run = os.path.join(OFFICIAL, "run")
    span = json.load(open(os.path.join(run, f"season_{n}.json")))
    sub = os.path.join(OFFICIAL, f"ep{n}"); os.makedirs(sub, exist_ok=True)
    # slice this season's records into the episode folder
    for f in ("events.jsonl", "dialogues.jsonl", "snapshots.jsonl"):
        rows = [l for l in open(os.path.join(run, f)) if span["first_day"] <= json.loads(l)["day"] <= span["last_day"]]
        open(os.path.join(sub, f), "w").writelines(rows)
    # dialogue indexes must refer to the sliced file: rebuild events' dialogue_index
    dls = [json.loads(l) for l in open(os.path.join(run, "dialogues.jsonl"))]
    first_dl = next((i for i, d in enumerate(dls) if d["day"] >= span["first_day"]), len(dls))
    evs = [json.loads(l) for l in open(os.path.join(sub, "events.jsonl"))]
    for e in evs:
        if "dialogue_index" in e.get("data", {}): e["data"]["dialogue_index"] -= first_dl
    open(os.path.join(sub, "events.jsonl"), "w").writelines(json.dumps(e) + "\n" for e in evs)
    llm = LLM("live", 3.0, os.path.join(sub, "api_calls.jsonl"))
    plan = build_episode(sub, gen, "live", llm, n)
    sn = [json.loads(l) for l in open(os.path.join(sub, "snapshots.jsonl"))]
    T = assemble.build_timeline(plan, sn, gen); assemble.render(T, os.path.join(sub, f"episode_{n}.mp4"), gen["seed"], gen)
    assemble.write_outputs(T, plan, sn, gen, sub, n)  # voices by role, cast, narrator script, SRT, thumbnail
    print(json.dumps({"title": plan.get("title"), "seconds": T.t, "editor_cost": llm.meter.summary()["usd"]}, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit()
    budget = float(a[a.index("--budget") + 1]) if "--budget" in a else 15.0
    {"ping": cmd_ping, "smoke": cmd_smoke, "roll": cmd_roll}.get(a[0], lambda: None)()
    if a[0] == "season": cmd_season(int(a[1]), budget, float(a[a.index("--minutes") + 1]) if "--minutes" in a else None)
    if a[0] == "episode": cmd_episode(int(a[1]))
    if a[0] == "fix": cmd_fix(a[1], a[a.index("--base") + 1])
