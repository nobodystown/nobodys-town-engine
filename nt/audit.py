"""Quarterly health audit of a run. Reads the records only: no API calls, never touches the town.
Flags what we need to know before spending more or airing anything:
  loops        the same person attempting nearly the same thing again and again
  referee      how often attempts succeed, by person and by kind (a check on the referee's neutrality)
  standards    lines that may cross the channel standards (to review by hand before anything airs)
  names        names in referee outcomes that don't belong to anyone in town
  cost/pace    dollars and seconds per day, by role
  life         what people actually talked about and did (topic mix, chance vs planned talk)
usage: python3 -m nt.audit <run_dir> [--from-day N] [--to-day N]"""
import collections, json, os, re, sys
from difflib import SequenceMatcher

STANDARDS = re.compile(r"\b(suicid\w*|kill (my|him|her)self|hang (my|him|her)self|self[- ]harm|slit|overdose|rape[ds]?|raping|molest\w*|sex|sexual\w*|naked|nude|n[i1]gg\w*|kike|spic|chink|wetback)\b", re.I)
TOPICS = {"money": r"\$|money|loan|owe|debt|pay|wage|rent|mortgage|savings|dollar|cash|afford|price",
          "town business": r"council|mayor|treasury|ledger|measure|vote|election|clerk|town hall",
          "work": r"\bmine\b|shift|work|job|boss|foreman|payroll|hire|fired",
          "family": r"\b(wife|husband|son|daughter|mother|father|mama|daddy|baby|kids?|children|brother|sister)\b",
          "church/faith": r"church|pray|preacher|sunday|bible|lord",
          "hobbies/fun": r"fish|hunt|baseball|radio|dance|picture show|cards|checkers|garden|quilt|bowling",
          "romance": r"sweetheart|court|marry|kiss|darling|love you",
          "health": r"sick|doctor|flu|fever|hurt|cough|hospital"}


def load(run, lo, hi):
    rd = lambda f: [json.loads(l) for l in open(os.path.join(run, f))] if os.path.exists(os.path.join(run, f)) else []
    ev = [e for e in rd("events.jsonl") if lo <= e["day"] <= hi]; dl = [d for d in rd("dialogues.jsonl") if lo <= d["day"] <= hi]
    sn = [s for s in rd("snapshots.jsonl") if lo <= s["day"] <= hi]; calls = rd("api_calls.jsonl")
    return ev, dl, sn, calls


def loops(ev, sim=0.72, min_run=4):
    by = collections.defaultdict(list)
    for e in ev:
        if e["kind"] == "attempt" and e["actors"]: by[e["actors"][0]].append(e)
    out = []
    for pid, xs in by.items():
        run = [xs[0]] if xs else []
        for a, b in zip(xs, xs[1:]):
            strip = lambda s: re.sub(r"[\d$,.]+", "", s[:200])  # ignore changing figures ($4019 vs $4115): Richard's 10 ledger checks slipped past (Nov 18)
            if SequenceMatcher(None, strip(a["text"]), strip(b["text"])).ratio() >= sim: run.append(b)
            else:
                if len(run) >= min_run: out.append(run)
                run = [b]
        if len(run) >= min_run: out.append(run)
    return sorted(out, key=len, reverse=True)


def referee_stats(ev):
    by_person, by_kind = collections.defaultdict(lambda: [0, 0]), collections.defaultdict(lambda: [0, 0])
    for e in ev:
        if e["kind"] != "attempt": continue
        ok = bool((e.get("data") or {}).get("ruling", {}).get("possible")); who = e["actors"][0] if e["actors"] else None
        verb = e["text"].split(" tries to ", 1)[-1].split(":", 1)[0]
        by_person[who][0] += ok; by_person[who][1] += 1; by_kind[verb][0] += ok; by_kind[verb][1] += 1
    return by_person, by_kind


def main(run, lo=0, hi=10 ** 9):
    ev, dl, sn, calls = load(run, lo, hi)
    if not sn: print("no data"); return
    names = {int(k): v["name"] for k, v in sn[-1]["people"].items()}; nm = lambda pid: names.get(pid, str(pid))
    first_names = {n.split()[0] for n in names.values()}; surnames = {n.split()[-1] for n in names.values()}
    days = sn[-1]["day"] - sn[0]["day"] + 1
    print(f"== AUDIT {os.path.basename(run)}  days {sn[0]['day']}-{sn[-1]['day']} ({sn[0]['date']} to {sn[-1]['date']})  population {sum(1 for p in sn[-1]['people'].values() if p['alive'] and not p['offtown'])}")
    # cost and pace
    usd = collections.Counter(); n = collections.Counter()
    for c in calls: usd[c["role"]] += c["usd"]; n[c["role"]] += 1
    if calls: print(f"\nCOST (whole run so far): ${sum(usd.values()):.2f} = " + ", ".join(f"{r} ${v:.2f} ({n[r]} calls)" for r, v in usd.most_common()))
    # loops
    L = loops(ev)
    print(f"\nLOOPS: {len(L)} found" + (" (the same person doing nearly the same thing 4+ times in a row)" if L else ""))
    for run_ in L[:6]: print(f"  {nm(run_[0]['actors'][0])}: {len(run_)}x from {run_[0]['date']} to {run_[-1]['date']}: \"{run_[0]['text'][:110]}...\"")
    # referee
    bp, bk = referee_stats(ev); tot = sum(v[1] for v in bk.values()); ok = sum(v[0] for v in bk.values())
    print(f"\nREFEREE: {tot} rulings, {ok / max(1, tot):.0%} allowed. By kind: " + ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in sorted(bk.items(), key=lambda kv: -kv[1][1])[:8]))
    odd = [(nm(p), v) for p, v in bp.items() if v[1] >= 5 and (v[0] / v[1] < 0.3 or v[0] / v[1] > 0.97)]
    if odd: print("  worth a look (5+ attempts, almost always or almost never allowed): " + "; ".join(f"{a} {v[0]}/{v[1]}" for a, v in odd))
    # names the referee invented
    bad = collections.Counter()
    for e in ev:
        if e["kind"] == "outcome":
            for m in re.finditer(r"\b([A-Z][a-z]+) ([A-Z][a-z]*'?[A-Z]?[a-z]+)\b", e["text"]):
                if m.group(2) in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday") or m.group(0).endswith("'s"): continue
                if m.group(1) in first_names and m.group(2) not in surnames and f"{m.group(1)} {m.group(2)}" not in names.values(): bad[m.group(0)] += 1
    print(f"\nNAMES: {sum(bad.values())} wrong full names in referee outcomes" + (": " + ", ".join(f"{k} ({v})" for k, v in bad.most_common(6)) if bad else ""))
    # standards
    hits = []
    for d in dl:
        for sp, t in d["lines"]:
            if STANDARDS.search(t): hits.append((d["date"], sp, t[:140]))
    for e in ev:
        if STANDARDS.search(e.get("text") or ""): hits.append((e["date"], e["kind"], e["text"][:140]))
    print(f"\nSTANDARDS: {len(hits)} lines to review by hand" + ("" if hits else " (none)"))
    for h in hits[:8]: print("  ", h)
    # life: what they talk about
    tc = collections.Counter(); chance = sum(1 for d in dl if d["kind"] == "chance")
    for d in dl:
        txt = " ".join(t for _, t in d["lines"]).lower()
        for k, rx in TOPICS.items():
            if re.search(rx, txt): tc[k] += 1
    print(f"\nLIFE: {len(dl)} conversations ({chance / max(1, len(dl)):.0%} chance meetings), {len(dl) / max(1, days):.1f} per day. Topics (share of conversations): " +
          ", ".join(f"{k} {v / max(1, len(dl)):.0%}" for k, v in tc.most_common()))
    talk = collections.Counter()
    for d in dl: talk[d["a"]] += 1; talk[d["b"]] += 1
    print("  most in conversation: " + ", ".join(f"{nm(p)} {c}" for p, c in talk.most_common(6)))
    quiet = [nm(int(p)) for p, v in sn[-1]["people"].items() if v["alive"] and v["age"] >= 12 and not v["offtown"] and talk[int(p)] == 0]
    if quiet: print("  never in a conversation: " + ", ".join(quiet))
    real_life(ev, sn, days)
    threads(ev)
    economy(ev, sn)
    big = [e for e in ev if e["importance"] >= 7 and e["kind"] not in ("conversation", "attempt", "outcome", "household_broke", "company_broke")]
    print(f"\nBIG EVENTS ({len(big)}):"); [print(f"  {e['date']} {e['kind']}: {e['text'][:120]}") for e in big[:15]]


# 1950 US vital statistics (per 1,000 people a year): births 24.1, deaths 9.6, marriages 11.1 (marriages counted per person).
VITAL = {"birth": 24.1, "death": 9.6, "wedding": 11.1}


def real_life(ev, sn, days):
    """Is the town more (or less) eventful than a real one? Compares counts per 100 people a year with the world step's own rate table
    and 1950 vital statistics. Tune the RATES if this drifts; never the story."""
    from .fate import CATEGORIES
    pop = sum(1 for p in sn[-1]["people"].values() if p["alive"] and not p["offtown"]) or 1
    hh = len({p.get("household") for p in sn[-1]["people"].values() if p["alive"]}) or 1
    yrs = max(days, 1) / 365
    fresh = collections.Counter(e["data"].get("category") for e in ev if e["kind"] == "world" and not e["data"].get("thread"))
    print(f"\nREAL-LIFE CHECK (per 100 people a year; town of {pop}, {hh} households, {days} days):")
    units = {"person": pop, "household": hh, "town": 1}
    for cat, unit, rate, _s, src in CATEGORIES:
        if unit == "secret": continue
        exp = rate * units[unit] * yrs
        got = fresh.get(cat, 0); per = lambda n: n / pop / yrs * 100
        flag = "  <-- busier than real life" if got > max(3, exp * 2) else "  <-- quieter than expected" if exp >= 3 and got < exp / 2 else ""
        print(f"  {cat:15s} {got:4d} (expected about {exp:5.1f}; {per(got):6.1f} per 100/yr){flag}")
    for k, per1000 in VITAL.items():
        got = sum(1 for e in ev if e["kind"] == k); exp = per1000 / 1000 * pop * yrs
        print(f"  {k + 's':15s} {got:4d} (1950 US rate would give about {exp:.1f})")


def threads(ev):
    opened = {e["data"]["thread"]: e for e in ev if e["kind"] == "thread_open"}
    ended = {e["data"]["thread"]: e for e in ev if e["kind"] == "thread_end"}
    still = [t for t in opened if t not in ended]
    how = collections.Counter(e["data"].get("ending") for e in ended.values())
    print(f"\nTHREADS: {len(opened)} opened, {len(ended)} ended (" + ", ".join(f"{k} {v}" for k, v in how.most_common()) + f"), {len(still)} still open")
    for t in still[:8]: print(f"  open since {opened[t]['date']}: {opened[t]['text'][:110]}")


ECON_KINDS = ("purchase", "loan", "loan_relief", "loan_refused", "loan_application", "loan_paid", "payment_missed", "repossessed", "collection", "business_seized", "bank_failed",
              "price_change", "wage_change", "shop_choice", "hired", "fired", "quit", "job_application", "law_enacted", "fined", "breach", "permit", "town_short", "lost_home")


def economy(ev, sn):
    """Did anyone decide anything with money (the Nov 18 autonomy build)? Counts, then every decision in order."""
    xs = [e for e in ev if e["kind"] in ECON_KINDS]
    c = collections.Counter(e["kind"] for e in xs)
    print(f"\nECONOMY: " + (", ".join(f"{k} {v}" for k, v in c.most_common()) or "no money decisions at all"))
    biz = [e for e in ev if e["kind"] in ("attempt",) and "start business" in e["text"].lower()]
    if biz: print(f"  businesses attempted: {len(biz)}")
    for e in xs:
        if e["kind"] not in ("payment_missed",): print(f"  {e['date']} {e['kind']}: {e['text'][:130]}")
    t = sn[-1].get("town", {})
    if "store_level" in t: print(f"  at the end: store prices {round((t['store_level'] - 1) * 100):+d}% vs county seat; a diner meal ${t.get('meal')}; laws in force {len(t.get('laws', []))}")
    hh = sn[-1]["households"]; cs = sum(1 for h in hh.values() if h.get("groceries_at") == "county seat")
    if hh: print(f"  {cs} of {len(hh)} households buy groceries in the county seat; {sum(1 for h in hh.values() if h.get('deposits'))} keep money in a bank")


if __name__ == "__main__":
    a = sys.argv[1:]; lo = int(a[a.index("--from-day") + 1]) if "--from-day" in a else 0; hi = int(a[a.index("--to-day") + 1]) if "--to-day" in a else 10 ** 9
    main(a[0], lo, hi)
