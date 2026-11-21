"""Voices straight from ElevenLabs (Nov 21): replaces the hand-made vidIQ MP3s.
Reads an episode folder's voices.json (every spoken line, in timeline order, by role) and cast.json (one permanent voice per role),
makes each line once (cached by model + voice + text, so a re-mix never pays twice), joins each role's lines into one track,
writes vo_lines.json in the shape nt.mix expects, then runs the final mix.
  python3 -m nt.tts <episode_dir> <episode_no> [--dry] [--no-mix] [--model eleven_multilingual_v2]
--dry: count characters and check the account's quota; makes nothing.
Key: ~/.secrets/elevenlabs_key (never anywhere else). Edit layer only: never touches the town."""
import hashlib, json, os, sys, time, urllib.request, urllib.error
import numpy as np

API = "https://api.elevenlabs.io/v1"
MODEL = "eleven_multilingual_v2"
GAP = 0.25  # seconds of silence between lines inside a role's track (only the line spans are used by the mix)


def key():
    return open(os.path.expanduser("~/.secrets/elevenlabs_key")).read().strip()


def _req(path, body=None, timeout=120):
    h = {"xi-api-key": key()}
    if body is not None: h["Content-Type"] = "application/json"
    r = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None, headers=h)
    return urllib.request.urlopen(r, timeout=timeout).read()


def quota():
    d = json.loads(_req("/user/subscription"))
    return d["character_limit"] - d["character_count"], d


def synth(text, voice_id, model, prev_text=None, next_text=None, tries=3):
    body = {"text": text, "model_id": model}
    if prev_text: body["previous_text"] = prev_text
    if next_text: body["next_text"] = next_text
    for k in range(tries):
        try: return _req(f"/text-to-speech/{voice_id}?output_format=mp3_44100_128", body)
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode(errors="replace")
            if e.code in (429, 500, 502, 503, 504) and k + 1 < tries: time.sleep(5 * (k + 1)); continue
            sys.exit(f"STOPPED: ElevenLabs {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError) as e:
            if k + 1 < tries: time.sleep(5 * (k + 1)); continue
            sys.exit(f"STOPPED: ElevenLabs unreachable: {e}")


def main(ep_dir, epn, dry=False, mix=True, model=MODEL):
    from . import mix as M
    base = os.path.join(ep_dir, f"episode_{epn}")
    lines = json.load(open(base + "_voices.json")); cast = json.load(open(base + "_cast.json"))
    missing = sorted({v["role"] for v in lines if not (cast.get(v["role"]) or {}).get("voice_id")})
    if missing: sys.exit(f"STOPPED: no voice for {missing}")
    cache = os.path.join(ep_dir, "tts"); os.makedirs(cache, exist_ok=True)
    def cpath(v): return os.path.join(cache, hashlib.sha1(f"{model}|{cast[v['role']]['voice_id']}|{v['text']}".encode()).hexdigest()[:16] + ".mp3")
    todo = [v for v in lines if not os.path.exists(cpath(v))]
    chars = sum(len(v["text"]) for v in todo)
    left, sub = quota()
    print(json.dumps({"lines": len(lines), "to_make": len(todo), "characters": chars, "quota_left": left, "tier": sub.get("tier")}))
    if chars > left: sys.exit(f"STOPPED: needs {chars} characters, {left} left this month.")
    if dry: return
    by_role = {}
    for v in lines: by_role.setdefault(v["role"], []).append(v)
    for role, vs in by_role.items():  # neighbouring lines of the same voice give ElevenLabs the flow (request stitching by text)
        for j, v in enumerate(vs):
            p = cpath(v)
            if os.path.exists(p): continue
            audio = synth(v["text"], cast[role]["voice_id"], model, vs[j - 1]["text"] if j else None, vs[j + 1]["text"] if j + 1 < len(vs) else None)
            open(p, "wb").write(audio)
        print(f"  {role} ({cast[role].get('name') or cast[role].get('voice_name')}): {len(vs)} lines")
    # one track per role, lines in order, with each line's start and length inside the track
    from .ambience import write_wav, RATE
    vo, tracks = {}, {}
    for role, vs in by_role.items():
        parts, spans, t = [], [], 0.0
        for v in vs:
            a = M.decode(cpath(v)); d = len(a) / RATE
            parts += [a, np.zeros(int(GAP * RATE), dtype=np.float32)]; spans.append([round(t, 4), round(d, 4)]); t += d + GAP
        tr = os.path.join(cache, role.replace(":", "_") + ".wav")
        write_wav(np.stack([np.concatenate(parts)] * 2, axis=1), tr); tracks[role] = tr; vo[role] = {"lines": spans}
    vo_path = base + "_vo_lines.json"; json.dump(vo, open(vo_path, "w"), indent=1)
    after, _ = quota()
    print(json.dumps({"vo_lines": vo_path, "characters_used": left - after, "quota_left": after}))
    if mix: M.main(ep_dir, epn, vo_path, tracks)


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], int(a[1]), dry="--dry" in a, mix="--no-mix" not in a, model=a[a.index("--model") + 1] if "--model" in a else MODEL)
