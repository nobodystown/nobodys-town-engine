"""Voice roles for every spoken line.
  narrator   the observer: male, British, warm and wry documentary voice (Aaron can replace this role with his own voice)
  announcer  the Gazette and big-news voice: female, 1950s American newsreel announcer
  resident   each resident speaks in their own voice, matched to their sex, age and temperament
Outputs per episode: voices.json (timed lines by role), cast.json (who sounds like what), narrator_script.txt (for a human read)."""
import json, re
from .minds import trait_words

NARRATOR = {"role": "narrator", "brief": "Male, British (Received Pronunciation), 50s-60s. Warm, wry, unhurried nature-documentary observer. Never excited; lets the facts land.",
            "voice_id": "JBFqnCBsd6RMkjVDRZzb", "voice_name": "George"}   # chosen by Aaron, Nov 18
ANNOUNCER = {"role": "announcer", "brief": "Female, American, 1950s newsreel/radio announcer. Bright, crisp Mid-Atlantic diction, a touch faster than the narrator. Reads headlines and big news only.",
             "voice_id": "hpp4J3VqNfWAUOO0d1Us", "voice_name": "Bella"}   # chosen by Aaron, Nov 18

# Resident voices: vidIQ's stock American voices (Nov 18 list). George and Bella are kept for the narrator and announcer.
# ages: the life stages each voice can pass for. There are no child voices in the library, so children get the youngest-sounding ones.
VOICE_POOL = [
    {"id": "TX3LPaxmHKxFdv7VOQHJ", "name": "Liam", "sex": "male", "ages": {"child", "teen", "young adult"}},
    {"id": "bIHbv24MWmeRgasZH58o", "name": "Will", "sex": "male", "ages": {"teen", "young adult", "adult"}},
    {"id": "iP95p4xoKVk53GoZ742B", "name": "Chris", "sex": "male", "ages": {"young adult", "adult"}},
    {"id": "cjVigY5qzO86Huf0OWal", "name": "Eric", "sex": "male", "ages": {"adult"}},
    {"id": "pNInz6obpgDQGcFmaJgB", "name": "Adam", "sex": "male", "ages": {"young adult", "adult"}},
    {"id": "CwhRBWXzGAHq8TQ4Fs17", "name": "Roger", "sex": "male", "ages": {"adult", "older adult"}},
    {"id": "N2lVS1w4EtoT3dr4eOWO", "name": "Callum", "sex": "male", "ages": {"adult", "older adult"}},
    {"id": "nPczCjzI2devNBz1zQrb", "name": "Brian", "sex": "male", "ages": {"adult", "older adult", "elderly"}},
    {"id": "pqHfZKP75CvOlQylNhV4", "name": "Bill", "sex": "male", "ages": {"older adult", "elderly"}},
    {"id": "SOYHLrjzK2X1ezoPC6cr", "name": "Harry", "sex": "male", "ages": {"young adult", "adult"}},
    {"id": "cgSgspJ2msm6clMCkdW9", "name": "Jessica", "sex": "female", "ages": {"child", "teen", "young adult"}},
    {"id": "FGY2WhTYpPnrIDTdsKH5", "name": "Laura", "sex": "female", "ages": {"child", "teen", "young adult", "adult"}},
    {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Sarah", "sex": "female", "ages": {"young adult", "adult", "older adult"}},
    {"id": "XrExE9yKIg1WjnnlVkGX", "name": "Matilda", "sex": "female", "ages": {"adult", "older adult", "elderly"}},
    {"id": "SAz9YHcvj6GT2YYXdXww", "name": "River", "sex": "female", "ages": {"young adult", "adult", "older adult"}},
]


def stage_of(age): return "child" if age < 13 else "teen" if age < 18 else "young adult" if age < 30 else "adult" if age < 55 else "older adult" if age < 70 else "elderly"


def assign_voices(people, dialogues, existing=None):
    """Every resident keeps one voice for life (decided Nov 18). The library has far fewer voices than the town has people,
    so voices repeat; a voice is shared only between people who seldom talk to each other.
    people: {pid: {"sex", "age"}}; dialogues: records with "a" and "b"; existing: {pid: voice_id} already assigned (never changed).
    Busiest talkers choose first. Cost of a voice = sharing it with someone this person talks to (heavy) + age fit + how often it's used."""
    import collections
    vm = {int(k): v for k, v in (existing or {}).items()}
    pair = collections.Counter(); volume = collections.Counter()
    for d in dialogues:
        a, b = d["a"], d["b"]; pair[frozenset((a, b))] += 1; volume[a] += 1; volume[b] += 1
    used = collections.Counter(vm.values())
    for pid in sorted(people, key=lambda p: (-volume[p], p)):
        if pid in vm: continue
        p = people[pid]; st = stage_of(p["age"])
        pool = [v for v in VOICE_POOL if v["sex"] == p["sex"]] or VOICE_POOL
        def cost(v):
            clash = sum(pair[frozenset((pid, q))] for q, vid in vm.items() if vid == v["id"])
            return clash * 100 + (0 if st in v["ages"] else 25) + used[v["id"]] * 3
        best = min(pool, key=cost); vm[pid] = best["id"]; used[best["id"]] += 1
    return vm
REGION_ACCENT = {"the Great Plains": "light Plains/Midwest", "the High Plains": "light Plains/Midwest", "the prairie Midwest": "Midwest",
                 "the Gulf Coast": "Gulf Coast Southern", "the New England coast": "New England", "the Pacific Northwest coast": "neutral Pacific Northwest",
                 "the Carolina coast": "Carolina Southern", "the Rocky Mountains": "Western", "the Appalachians": "Appalachian", "the Sierra foothills": "Western",
                 "the Ozarks": "Ozark", "the Southwest desert": "Southwestern", "the Great Basin": "Western", "the high desert of the West": "Western",
                 "the Great Lakes shore": "Great Lakes", "the Minnesota lake country": "Upper Midwest", "a lake in the Adirondacks": "upstate New York",
                 "a reservoir in the Tennessee Valley": "Tennessee", "the Louisiana bayou": "Cajun/Louisiana", "the Florida wetlands": "Southern", "the Carolina lowcountry": "Lowcountry",
                 "the North Woods": "Upper Midwest", "the Pacific Northwest timberlands": "neutral Pacific Northwest", "the Piney Woods of the South": "East Texas", "the Upper Peninsula": "Yooper/Upper Midwest"}


def speakable(text):
    """Small fixes so a voice reads the real event text naturally. Facts are unchanged."""
    t = re.sub(r"\s\((\d+)\)", r", \1,", text or "")
    return t.strip()


def gazette_read(town, e, headline):
    if e["kind"] == "election_result" and e.get("data", {}).get("tallies"):
        tallies = sorted(e["data"]["tallies"].items(), key=lambda kv: -kv[1])
        counts = "; ".join(f"{n}, {v} vote{'s' if v != 1 else ''}" for n, v in tallies[:3])
        return f"The {town} Gazette. {headline}. Final count: {counts}. Turnout: {e['data'].get('turnout', '?')}."
    return f"The {town} Gazette. {speakable(headline).rstrip('.')}."


def resident_brief(pid, snap, gen, traits=None, voice_id=None):
    p = snap["people"][str(pid)]; age = p["age"]
    if traits is None:
        for h in gen.get("households", []):
            for m in h["members"]:
                if m["name"].split()[0] == p["name"].split()[0]:  # first names are unique in town
                    traits = m.get("traits"); break
            if traits: break
    stage = "child" if age < 13 else "teen" if age < 18 else "young adult" if age < 30 else "adult" if age < 55 else "older adult" if age < 70 else "elderly"
    temper = trait_words(traits) if traits else "temperament not recorded (arrived or born in the sim)"
    accent = REGION_ACCENT.get(gen.get("region"), "American")
    return {"role": f"resident:{pid}", "name": p["name"], "sex": p["sex"], "age": age, "stage": stage, "job": p.get("job"),
            "brief": f"{p['sex'].capitalize()}, {age} ({stage}), {accent} accent. {temper}.", "voice_id": voice_id,
            "voice_name": next((v["name"] for v in VOICE_POOL if v["id"] == voice_id), None)}


def cast(voices, snaps_by_pid, gen, voice_map=None):
    out = {"narrator": NARRATOR, "announcer": ANNOUNCER}
    for v in voices:
        if v["role"].startswith("resident:") and v["role"] not in out:
            pid = int(v["role"].split(":")[1]); out[v["role"]] = resident_brief(pid, snaps_by_pid[pid], gen, voice_id=(voice_map or {}).get(pid))
    return out


def town_voice_map(run_dir, sn):
    """Load the town's permanent voice map (voice_map.json in the run folder), add anyone new, save it back."""
    import os
    path = os.path.join(run_dir, "voice_map.json"); existing = json.load(open(path)) if os.path.exists(path) else {}
    people = {}
    for s in sn:
        for pid, p in s["people"].items(): people[int(pid)] = {"sex": p["sex"], "age": p["age"]}
    dpath = os.path.join(run_dir, "dialogues.jsonl")
    dl = [json.loads(l) for l in open(dpath)] if os.path.exists(dpath) else []
    vm = assign_voices(people, dl, existing)
    json.dump({str(k): v for k, v in sorted(vm.items())}, open(path, "w"), indent=1)
    return vm


def ts(x):
    m, s = divmod(x, 60); return f"{int(m):02}:{s:05.2f}"


def narrator_script(voices, title, episode):
    rows = [f"NOBODY'S TOWN, EPISODE {episode}: {title}", "NARRATOR SCRIPT (read in order; timecodes show where each line lands in the cut)", ""]
    for v in voices:
        if v["role"] == "narrator": rows += [f"[{ts(v['start'])}]  ({v['max_seconds']:.0f}s window)", v["text"], ""]
    return "\n".join(rows)


def write_files(T, base, gen, sn, title, episode):
    by_pid = {}
    for s in sn:
        for pid in s["people"]: by_pid[int(pid)] = s
    import os
    c = cast(T.voices, by_pid, gen, town_voice_map(os.path.dirname(base) or ".", sn))
    json.dump(T.voices, open(base + "_voices.json", "w"), indent=1)
    json.dump(c, open(base + "_cast.json", "w"), indent=1)
    open(base + "_narrator_script.txt", "w").write(narrator_script(T.voices, title, episode))
    return c
