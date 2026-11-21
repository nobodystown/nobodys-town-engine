"""Final mix (Nov 18): picture timed to the real recorded voices, every line placed where it lands, the sound bed under it.
The voices are recorded on vidIQ (one track per voice, all of that voice's lines in order, with each line's start and length).
This workspace can't download from vidIQ, so the four MP3s come in as attachments; vo_lines.json maps them.
  python3 -m nt.mix <run_dir> <episode_no> <vo_lines.json> <role=track.mp3> ... [--short]
Output: episode_<n>_final.mp4 (voices + bed, loudness -14 LUFS for YouTube)."""
import json, os, subprocess, sys
import numpy as np
from . import assemble, ambience

RATE = ambience.RATE


def decode(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(RATE), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def voice_track(T, vo_lines, tracks):
    """Place every line of every voice at its moment in the cut. Lines are matched to the timeline in order, per role."""
    out = np.zeros(int(T.t * RATE) + RATE * 2, dtype=np.float32); used = {r: 0 for r in vo_lines}
    audio = {r: decode(p) for r, p in tracks.items()}
    for v in T.voices:
        r = v["role"]
        if r not in audio or used[r] >= len(vo_lines[r]["lines"]): continue
        s0, d = vo_lines[r]["lines"][used[r]]; used[r] += 1
        a = audio[r][int(s0 * RATE): int((s0 + d) * RATE)]
        f = min(len(a) // 4, int(0.01 * RATE))
        if f: a = a.copy(); a[:f] *= np.linspace(0, 1, f); a[-f:] *= np.linspace(1, 0, f)  # no clicks at the cuts
        i = int(v["start"] * RATE); out[i:i + len(a)] += a[: max(0, len(out) - i)]
    missing = {r: len(vo_lines[r]["lines"]) - used[r] for r in used if used[r] != len(vo_lines[r]["lines"])}
    return out, missing


def main(run, epn, vo_path, tracks, short=False):
    gen = json.load(open(os.path.join(run, "world.json"))); plan = json.load(open(os.path.join(run, f"episode_{epn}_plan.json")))
    sn = [json.loads(l) for l in open(os.path.join(run, "snapshots.jsonl"))]
    vo_lines = json.load(open(vo_path))
    T = assemble.build_timeline(plan, sn, gen, short=short, vo={r: [d for _, d in x["lines"]] for r, x in vo_lines.items()})
    base = os.path.join(run, f"episode_{epn}")
    assemble.render(T, base + "_picture.mp4", gen["seed"], gen)
    voice, missing = voice_track(T, vo_lines, tracks)
    bed = ambience.bed_for_timeline(T, gen, gen["seed"])[:, 0]
    n = max(len(voice), len(bed)); voice = np.pad(voice, (0, n - len(voice))); bed = np.pad(bed, (0, n - len(bed)))
    env = np.convolve((np.abs(voice) > 0.01).astype(np.float32), np.ones(int(0.3 * RATE)) / int(0.3 * RATE), "same")
    bed = bed * (1 - 0.45 * np.clip(env * 4, 0, 1))  # the bed dips under speech
    mixw = np.stack([voice + bed, voice + np.roll(bed, 220)], axis=1)
    ambience.write_wav(mixw * 0.9, base + "_mix.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", base + "_picture.mp4", "-i", base + "_mix.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", base + "_final.mp4"], check=True)
    assemble.srt(T, base + "_final.srt")
    print(json.dumps({"video": base + "_final.mp4", "seconds": round(T.t, 1), "missing_lines": missing}))


if __name__ == "__main__":
    a = sys.argv[1:]; run, epn, vo = a[0], int(a[1]), a[2]
    tracks = dict(x.split("=", 1) for x in a[3:] if "=" in x)
    main(run, epn, vo, tracks, short="--short" in a)
