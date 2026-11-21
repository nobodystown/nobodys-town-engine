"""A/B test of the one temperament line in the resident frame (FRAME_VARIANT "fact" vs "none").
Same TEST town, same seed, same first day, run once per variant. Writes a blind side-by-side (labels X/Y, key kept separately)
so the transcripts can be judged before knowing which is which.
usage: python3 -m nt.ab_frame <seed> [--budget-each 0.40]"""
import json, os, random, sys
from . import minds
from .generator import generate

OUT = "/home/claude/nobodys_town/TEST/ab_frame"


def run(seed, variant, budget):
    from .engine import Engine
    minds.FRAME_VARIANT = variant
    gen = generate(seed); gen["fingerprint"] = "TEST"
    d = os.path.join(OUT, f"{seed}_{variant}"); os.makedirs(d, exist_ok=True)
    e = Engine(gen, d, "live", budget, workers=8); s = e.run(1)
    return e, s


def main():
    a = sys.argv[1:]; seed = int(a[0]); b = float(a[a.index("--budget-each") + 1]) if "--budget-each" in a else 0.40
    res = {v: run(seed, v, b) for v in ("fact", "none")}
    minds.FRAME_VARIANT = "fact"
    labels = ["fact", "none"]; random.SystemRandom().shuffle(labels); key = {"X": labels[0], "Y": labels[1]}
    lines = [f"# Frame A/B, seed {seed} (blind: X and Y)\n"]
    for lab in ("X", "Y"):
        e, s = res[key[lab]]
        lines.append(f"\n## {lab}: {len(e.dialogues)} conversations, ${s['cost']['usd']:.2f}\n")
        th = [x for x in e.events if x["kind"] == "reflection"] + [x for x in e.events if x["kind"] == "attempt"][:8]
        for d in e.dialogues:
            lines.append(f"\n**{e.w.name(d['a'])} & {e.w.name(d['b'])}** ({d['kind']}, {d['slot']})")
            lines += [f"- {sp}: {t}" for sp, t in d["lines"]]
        lines.append("\n### Attempts")
        lines += [f"- {x['text'][:200]}" for x in th]
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, f"blind_{seed}.md"), "w").write("\n".join(lines))
    json.dump(key, open(os.path.join(OUT, f"key_{seed}.json"), "w"))
    print(json.dumps({v: {"usd": res[v][1]["cost"]["usd"], "dialogues": len(res[v][0].dialogues)} for v in res}))
    print("blind file:", os.path.join(OUT, f"blind_{seed}.md"))


if __name__ == "__main__":
    main()
