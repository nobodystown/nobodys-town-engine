"""Shorts clip bank (approved by Aaron, Nov 20, 2026): after each quarter review, read EVERY conversation of that quarter
and keep the best stand-alone moments for YouTube Shorts, TikTok and FB/IG Reels (one 1080x1920 render, nt.shorts).
Edit only: it reads the town's record and never changes it. Exact words only; honors editor_cuts.json; standards-checked.

    python3 -m nt.clipbank <run_dir> <label> <from_day> <to_day> [--budget 4]
    e.g. python3 -m nt.clipbank nobodys_town/OFFICIAL/run q3 181 272

Writes <run_dir>/../clip_bank.json: {"clips": [...], "quarters": {label: {...}}}. Re-running a label replaces only that label.
"""
import json, os, re, sys, argparse
from concurrent.futures import ThreadPoolExecutor
from .llm import LLM, parse_json
from .audit import STANDARDS
from .editor import load_cuts

CHUNK = 60  # conversations per editor call
OTHER_DOCTOR = re.compile(r"\b(Dr\.?|Doc|Doctor)\s+(Whitfield|Weller)\b|\bWeller\b")  # Dr. Ito is the only doctor (old memories still say these)

SYSTEM = """You are the Shorts editor for "Nobody's Town", a 1950s small town (Anchor Point, Carolina coast) where every resident is an AI living its own life. Nobody scripts them. We only watch and edit.
You pick moments for vertical Shorts/Reels (15-55 seconds, 2-6 lines). A good pick:
- stands on its own: a stranger scrolling past understands it in two seconds, with no earlier episode;
- has a hook in the first line: a sharp line, a funny exchange, a small reveal, warmth, a quarrel, a deal, a very human detail;
- sounds like real 1950 people, not a summary.
Rules (strict):
- Use the residents' EXACT words. "keep" is the line as written, or a contiguous piece of it cut at a sentence boundary. Never reword, never add.
- Lines must run in order within one conversation; you may skip a line in the middle only if the cut still reads naturally.
- Channel standards: no sexual content; children are never shown as victims of violence or abuse; nothing about self-harm; nothing that mocks race, ethnicity or religion. Skip anything near these.
- Grief, illness and money trouble can be picked only when the moment is tender or dignified, never as misery bait. Hooks never exploit hardship ("Watch her lose everything" is banned).
- Hooks: under 50 characters, plain and curious, no clickbait caps, no emoji, no invented facts.
- Most conversations are ordinary. Pick only the ones you'd actually post. Zero picks is fine.
Return JSON only."""

FORMAT = """Return JSON: {"picks": [{"dialogue_index": <int>, "lines": [{"n": <line number>, "keep": "<exact words>"}], "hook": "<under 50 chars>", "why": "<one short sentence>", "kind": "<funny|tender|tense|deal|small-town|surprise>", "score": <1-10, 8+ = post this week>}]}"""


def _norm(x): return re.sub(r"\s+", " ", x or "").strip()


def fmt(i, d):
    head = f"#{i} | {d['date']} {d['slot']} | {d['medium']} | {d.get('place')} | wanted: {_norm(d.get('purpose'))[:140]}"
    return head + "\n" + "\n".join(f"  [{n}] {sp}: {_norm(t)}" for n, (sp, t) in enumerate(d["lines"]))


def check(p, dl, allowed):
    """Keep only picks that match the record word for word and pass the standards check."""
    i = p.get("dialogue_index")
    if not isinstance(i, int) or i not in allowed: return None
    d = dl[i]; out = []; last = -1
    for x in p.get("lines") or []:
        n = x.get("n")
        if not isinstance(n, int) or not (0 <= n < len(d["lines"])) or n <= last: continue
        orig = _norm(d["lines"][n][1]); keep = _norm(x.get("keep"))
        if not keep or keep not in orig: keep = orig  # never reworded: fall back to the full line
        if STANDARDS.search(keep) or OTHER_DOCTOR.search(keep): return None
        out.append({"n": n, "speaker": d["lines"][n][0], "keep": keep}); last = n
    if not out: return None
    hook = _norm(p.get("hook"))[:50]
    if STANDARDS.search(hook): return None
    words = sum(len(x["keep"].split()) for x in out)
    return {"dialogue_index": i, "day": d["day"], "date": d["date"], "slot": d["slot"], "medium": d["medium"], "place": d.get("place"),
            "a": d["a"], "b": d["b"], "lines": out, "hook": hook, "why": _norm(p.get("why"))[:200], "kind": p.get("kind"),
            "score": int(p.get("score") or 0), "est_seconds": round(min(60, words / 2.6 + 2 * len(out)), 1), "posted": False}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("label"); ap.add_argument("lo", type=int); ap.add_argument("hi", type=int)
    ap.add_argument("--budget", type=float, default=4.0); ap.add_argument("--workers", type=int, default=8); a = ap.parse_args()
    dl = [json.loads(l) for l in open(os.path.join(a.run, "dialogues.jsonl"))]
    cut_ids, notes = load_cuts(a.run)
    pool = [i for i, d in enumerate(dl) if a.lo <= d["day"] <= a.hi and len(d["lines"]) >= 2
            and not any(STANDARDS.search(t) for _, t in d["lines"])]
    allowed = set(pool)
    note_txt = ("Continuity notes (never pick a moment that contradicts these):\n- " + "\n- ".join(notes)) if notes else ""
    llm = LLM("live", a.budget, os.path.join(os.path.dirname(os.path.abspath(a.run)), "editorial_calls.jsonl"))  # kept apart from the town's own cost log
    chunks = [pool[k:k + CHUNK] for k in range(0, len(pool), CHUNK)]

    def one(ch):
        body = note_txt + "\n\nConversations:\n\n" + "\n\n".join(fmt(i, dl[i]) for i in ch) + "\n\n" + FORMAT
        try:
            out, raw = llm.call_json("editor", [SYSTEM], [{"role": "user", "content": body}], max_tokens=8000)
        except Exception as ex:
            print("chunk failed:", str(ex)[:160], flush=True); return []
        picks = (out or {}).get("picks") or []
        return [c for c in (check(p, dl, set(ch)) for p in picks) if c]

    with ThreadPoolExecutor(a.workers) as ex: got = [c for res in ex.map(one, chunks) for c in res]
    seen = set(); clips = []
    for c in sorted(got, key=lambda c: (-c["score"], c["day"])):
        if c["dialogue_index"] in seen: continue
        seen.add(c["dialogue_index"]); c["quarter"] = a.label; clips.append(c)
    path = os.path.join(os.path.dirname(os.path.abspath(a.run)), "clip_bank.json")
    bank = json.load(open(path)) if os.path.exists(path) else {"about": "Shorts/Reels clip bank (edit only; exact words; standards-checked; honors editor_cuts). Approved by Aaron, Nov 20, 2026.", "clips": [], "quarters": {}}
    bank["clips"] = [c for c in bank["clips"] if c.get("quarter") != a.label] + clips
    bank["clips"].sort(key=lambda c: (c["day"], c["dialogue_index"]))
    bank["quarters"][a.label] = {"days": [a.lo, a.hi], "conversations_read": len(pool), "chunks": len(chunks), "clips": len(clips),
                                 "score_8_plus": sum(c["score"] >= 8 for c in clips), "cost_usd": round(llm.meter.spent, 3)}
    json.dump(bank, open(path, "w"), indent=1)
    print(json.dumps(bank["quarters"][a.label]))
    for c in clips[:8]:
        print(f"\n[{c['score']}] {c['date']} {c['kind']} | {c['hook']}  ({c['est_seconds']}s)")
        for x in c["lines"]: print(f"   {x['speaker']}: {x['keep'][:160]}")


if __name__ == "__main__": main()
