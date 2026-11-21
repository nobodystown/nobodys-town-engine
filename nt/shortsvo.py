"""Voiced Shorts (Nov 21): a clip-bank clip -> vertical 1080x1920 MP4 with each resident's permanent ElevenLabs voice.
Exact words from the record (the clip bank's standards-checked lines); frames timed to the real voiced lines; -14 LUFS.
  python3 -m nt.shortsvo <dialogue_index> [<dialogue_index> ...] [--model eleven_multilingual_v2] [--hook "<text>"]
Output: OFFICIAL/shorts/short_<i>.mp4 (+ _voices.json). Edit layer only: never touches the town."""
import hashlib, json, os, subprocess, sys
import numpy as np
from . import shorts, tts, golive
from .mix import decode
from .ambience import write_wav, RATE

OUT = os.path.join(golive.OFFICIAL, "shorts")


def make(di, model=tts.MODEL, hook=None):
    run = os.path.join(golive.OFFICIAL, "run"); gen = json.load(open(os.path.join(golive.OFFICIAL, "world.json")))
    clip = next(c for c in json.load(open(os.path.join(golive.OFFICIAL, "clip_bank.json")))["clips"] if c["dialogue_index"] == di)
    d = json.loads(next(l for k, l in enumerate(open(os.path.join(run, "dialogues.jsonl"))) if k == di))
    sn = [json.loads(l) for l in open(os.path.join(run, "snapshots.jsonl")) if abs(json.loads(l)["day"] - d["day"]) <= 0]
    sn = [None] * d["day"] + sn  # build_short indexes snapshots by day
    vm = json.load(open(os.path.join(golive.OFFICIAL, "voice_map.json")))
    s = sn[d["day"]]; pid_of = {s["people"][str(x)]["name"]: x for x in (d["a"], d["b"])}
    os.makedirs(os.path.join(OUT, "tts"), exist_ok=True)
    lines = [{"n": l["n"], "keep": l["keep"]} for l in clip["lines"]]
    durs, wavs = [], []
    for i, l in enumerate(lines):
        sp = d["lines"][l["n"]][0]; vid = vm[str(pid_of[sp])]
        p = os.path.join(OUT, "tts", hashlib.sha1(f"{model}|{vid}|{l['keep']}".encode()).hexdigest()[:16] + ".mp3")
        if not os.path.exists(p):
            open(p, "wb").write(tts.synth(l["keep"], vid, model, lines[i - 1]["keep"] if i else None, lines[i + 1]["keep"] if i + 1 < len(lines) else None))
        a = decode(p); wavs.append(a); durs.append(len(a) / RATE)
    out = os.path.join(OUT, f"short_{di}.mp4"); pic = out.replace(".mp4", "_picture.mp4")
    secs = shorts.build_short({"lines": lines, "hook": hook or clip["hook"]}, d, sn, gen, pic, durs=durs)
    track = np.zeros(int((secs + 1) * RATE), dtype=np.float32); t = 0.0
    for a, du in zip(wavs, durs):
        i = int((t + 0.2) * RATE); track[i:i + len(a)] += a[: len(track) - i]; t += du + 0.6
    wav = out.replace(".mp4", ".wav"); write_wav(np.stack([track] * 2, axis=1) * 0.9, wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", pic, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", out], check=True)
    os.remove(pic); os.remove(wav)
    return {"file": out, "seconds": secs, "hook": hook or clip["hook"], "characters": sum(len(l["keep"]) for l in lines)}


if __name__ == "__main__":
    a = sys.argv[1:]; model = a[a.index("--model") + 1] if "--model" in a else tts.MODEL
    hook = a[a.index("--hook") + 1] if "--hook" in a else None
    ids = [int(x) for x in a if x.isdigit()]
    for di in ids: print(json.dumps(make(di, model, hook)))
