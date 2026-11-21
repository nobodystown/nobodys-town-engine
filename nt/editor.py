"""Story editor: reads a recorded season and builds an episode plan from REAL moments only. Editing only, never steering.
People-first: each episode follows 3-4 households' threads through the season, cut together in time order,
documentary-style. Conversations carry about half the runtime; the narrator only bridges.
Weather stays in the background (only a severe disaster that hurt or killed someone can be a scene).
A found object only matters if it changed something afterwards (talked about, sold, fought over).
Also computes the Ledger stats straight from the snapshots."""
import json, os, re, collections
from .llm import LLM

KIND_BONUS = {"election_result": 6, "death": 6, "wedding": 5, "birth": 4, "fired": 4, "hired": 2, "telegram": 6, "draft_notice": 4, "left_town": 3, "returned": 4,
              "fame": 6, "candidacy": 3, "measure_vote": 2, "outcome": 1, "separation": 5, "newcomer": 2, "company_broke": 4, "household_broke": 3, "eavesdrop": 2,
              "lend": 1, "pay": 1, "promise": 1, "history": 0, "discovery": 0, "disaster": 0, "lots_drawn": 4, "election_notice": 1}
SKIP = {"engine_warning", "engine_stop", "recovered", "taxes", "weather_season", "weather_event", "illness", "opportunity", "attempt", "conversation", "job_application"}
GAZETTE_KINDS = ("election_result", "death", "wedding", "birth", "fame")
STOP = {"while", "which", "something", "inside", "there", "about", "would", "their", "found", "small", "heavy", "strange", "large", "rattling", "half", "buried"}

EDITOR_RULES = """You are the story editor of "Nobody's Town", an observational documentary series about a real, unscripted town of AI residents. Every event and every line of dialogue below truly happened. You edit; you never invent.
ONE EPISODE = ONE YEAR of the town's life. You are given the year's biggest events and a pre-selected set of its strongest conversations (the full record is longer; everything you see is real).
THIS EPISODE FOLLOWS {leads_rule}. Choose the lead(s) whose lives carry the most HUMAN story across this year: family, love, friendship, work, trouble, a secret, a hope. Town business (the council, the treasury, votes) is background: only choose it when it truly changes someone's life, never just because people talked about it a lot. The rest of the town appears when they cross a lead's path.
YEAR SHAPE
- Cold open on the single biggest moment of the year (it may come from late in the year), then after the title tell the year IN ORDER, spring to winter or however the year runs. Let the seasons pass in the narration with plain time words (that spring, by midsummer, come the first snow) rather than dates.
- Spread the scenes across the whole year; don't spend half the episode on one month. The year's big public events (a fire, a wedding, a death, a business opening or closing, someone arriving or leaving) are scenes too: use them by event id with a one-sentence setup.
MAKE IT EASY TO FOLLOW
- Episode shape: what each lead wants or is facing -> what happens -> where it's left at year's end.
- The narrator SETS UP each scene before anyone speaks: one short sentence, 20 words or fewer, saying who, where and what's going on, so the viewer knows what to listen for. The residents carry the story; the narrator only bridges. Leave a setup empty when the scene speaks for itself. Plain, warm, specific. Never open with a date ("On September 23rd..."); use natural time words (that morning, two days later, by the weekend) only when they help.
{welcome_rule}
CLOSING
- Closing scene: end the year on a real moment. Pick ONE conversation from LAST DAYS OF THE YEAR (ideally with a lead), 2-3 lines, that leaves the viewer with how the year ends for them. Then the closing sentence plays over the evening street as the lights go out.
HOOK AND PACE
- Cold open: the single most gripping real exchange involving a lead, 1-3 lines, plus ONE narrator sentence that sets up the stakes without giving away how it ends.
- Cut hard: at most 4 lines from any conversation. For each line keep only the sentence(s) that carry it, copied EXACTLY (word for word). Drop small talk, repetition and recaps.
RULES
- Use ONLY the events, dialogues and lines given, by id and number. Never invent events, quotes, motives or outcomes. Never claim to know a private thought.
- Narrator voice: a British nature-documentary observer watching a town the way one watches a valley of animals: calm, curious, precise, a little dry. A quiet ominous edge is welcome when the facts support it (a debt coming due, a secret someone is keeping, a company in the red, a rift that hasn't healed), never manufactured. Plain words, concrete details, no hype, no jokes at anyone's expense, never gives the viewer advice.
- Weather stays in the background: never narrate it unless it hurt or killed someone.
- Sensitive events (marked sensitive): off-screen and gentle, through the family's reaction; never in the title or thumbnail.
- TITLE: stakes first. Lead with what was at stake or the most surprising TRUE outcome of the year, in plain words a stranger gets at a glance (under 60 characters). A good shape: "{pop} AI People, One Year: <true outcome>" or "<lead> Bet Everything on <true thing>". Never a death, illness, miscarriage or grief in the title or thumbnail text; never a claim the year doesn't support.
OUTPUT one JSON object:
{{"title": "<under 60 characters>",
 "leads": [{{"name": "<full name>", "intro": "<who they are, under 45 characters>", "want": "<what they want or face this episode, one short true sentence>"}}],
 "welcome": "<{welcome_field}>",
 "cold_open": {{"dialogue_index": <index>, "lines": [{{"n": <line number>, "keep": "<exact words>"}}], "hook": "<one narrator sentence>"}},
 "scenes": [{{"lead": "<lead's full name>", "dialogue_index": <index or null>, "lines": [{{"n": <line number>, "keep": "<exact words>"}}], "event_ids": [<ids, may be empty>], "setup": "<one narrator sentence of 20 words or fewer before the scene, or empty if the last scene already set it up>"}}],
 "closing_scene": {{"dialogue_index": <index from LAST DAYS OF THE YEAR>, "lines": [{{"n": <line number>, "keep": "<exact words>"}}], "setup": "<one narrator sentence, 20 words or fewer, or empty>"}},
 "closing": "<one sentence: where each lead is left>",
 "teaser": "<one true sentence about something still unresolved>",
 "shorts": [{{"dialogue_index": <index>, "lines": [{{"n": <line number>, "keep": "<exact words>"}}], "hook": "<under 50 characters>"}}],
 "thumbnail_dialogue_index": <index>, "thumbnail_text": "<2-4 words, true>"}}"""
WELCOME_EP1 = "- This is EPISODE 1: viewers know nothing. Write a welcome (2-3 short sentences) that introduces the town in plain words and hands the viewer to the lead(s) by name."
WELCOME_LATER = "- Viewers may have missed earlier episodes: write a 'previously' (1-2 short sentences) about the lead(s), from what you can see in these events, or leave it empty."


def load_run(run_dir):
    ev = [json.loads(l) for l in open(os.path.join(run_dir, "events.jsonl"))]
    dl = [json.loads(l) for l in open(os.path.join(run_dir, "dialogues.jsonl"))]
    sn = [json.loads(l) for l in open(os.path.join(run_dir, "snapshots.jsonl"))]
    return ev, dl, sn


def load_cuts(run_dir):
    """Continuity cuts (Aaron, Nov 20): records that contradict the town's own record never reach the edit.
    editor_cuts.json in the run folder or the folder above it: {"cut_events": [{"id": n, "reason": "..."}], "notes": ["..."]}.
    This only decides what airs; it never changes the town."""
    for d in (run_dir, os.path.dirname(os.path.abspath(run_dir))):
        f = os.path.join(d, "editor_cuts.json")
        if os.path.exists(f):
            c = json.load(open(f)); return {x["id"] for x in c.get("cut_events", [])}, list(c.get("notes", []))
    return set(), []


def find_mattered(e, dl):
    """A discovery matters only if the finder talked about it (or traded it) afterwards."""
    words = {w.strip(".,").lower() for w in e["text"].split(" while ")[0].split() if len(w) > 4} - STOP
    who = e["actors"][0] if e["actors"] else None
    for d in dl:
        if d["day"] < e["day"] or who not in (d["a"], d["b"]): continue
        if any(w in t.lower() for _, t in d["lines"] for w in words): return True
    return False


def keep_event(e, dl):
    if e["kind"] in SKIP: return False
    if e["kind"] == "disaster": return e.get("data", {}).get("severity") == "severe" and ("Hurt:" in e["text"] or "killed" in e["text"])
    if e["kind"] == "discovery": return find_mattered(e, dl)
    if e["kind"] == "history": return False  # the outside world stays on the radio, in the background
    return True


def dl_score(d):
    return len(d["lines"]) * 0.6 + 2.5 * len(d["deals"]) + (3 if d["kind"] in ("propose_marriage", "end_relationship", "ask_loan", "court") else 0) + (1 if d["medium"] == "phone" else 0)


def ev_score(e): return e["importance"] + KIND_BONUS.get(e["kind"], 0)


def household_of(sn, pid):
    for s in reversed(sn):
        p = s["people"].get(str(pid))
        if p: return p["household"]
    return None


def thread_scores(ev, dl, sn):
    """How much happened to each household this period (conversations + real events)."""
    sc = collections.Counter()
    for d in dl:
        for pid in {d["a"], d["b"]}: sc[household_of(sn, pid)] += dl_score(d) / 2
    for e in ev:
        if keep_event(e, dl):
            for pid in set(e["actors"][:4]): sc[household_of(sn, pid)] += ev_score(e) / 3
    sc.pop(None, None)
    return sc


def activity(dl, kept):
    """How much each resident was in the year's real moments (talk + events). Used to name lead candidates; not a ranking shown to anyone."""
    act = collections.Counter()
    for d in dl:
        for pid in (d["a"], d["b"]): act[pid] += dl_score(d)
    for e in kept:
        for pid in e["actors"][:3]: act[pid] += ev_score(e) / 2
    return act


EV_CAP, DL_CAP, DL_PER_LEAD = 260, 150, 14
ROUTINE = {"happening", "pay", "lend", "give", "promise", "outcome", "measure_proposed", "candidacy", "purchase"}


def prefilter(ev, dl, sn, kept, act, ev_cap=EV_CAP, dl_cap=DL_CAP):
    """A year is too long to hand the editor whole. Keep (1) every big event, (2) everyday events only for likely leads or when they
    matter, (3) the strongest conversations overall, plus each likely lead's best ones, spread across the whole year.
    Pure selection by fixed scores: nothing is rewritten, and every kept item keeps its original id/number."""
    leads = {pid for pid, _ in act.most_common(8)}
    def ev_keep_score(e):
        s = ev_score(e) + (3 if set(e["actors"]) & leads else 0)
        if e["kind"] in ROUTINE and not set(e["actors"]) & leads: s -= 4
        return s
    big = [e for e in kept if ev_score(e) >= 12 or e["kind"] in GAZETTE_KINDS or (e["kind"] == "town_event" and e["importance"] >= 6)]
    rest = sorted((e for e in kept if e not in big), key=ev_keep_score, reverse=True)[: max(0, ev_cap - len(big))]
    ev_pick = sorted(big + rest, key=lambda e: e["id"])
    if not dl: return ev_pick, []
    first_day, last_day = dl[0]["day"], dl[-1]["day"]; span = max(1, last_day - first_day + 1)
    chosen = set()
    for pid in leads:  # each likely lead's strongest conversations
        mine = sorted((i for i, d in enumerate(dl) if pid in (d["a"], d["b"])), key=lambda i: -dl_score(dl[i]))[:DL_PER_LEAD]
        chosen.update(mine)
    months = collections.defaultdict(list)  # then the strongest of the rest, month by month so the whole year is represented
    for i, d in enumerate(dl):
        if i not in chosen: months[min(11, (d["day"] - first_day) * 12 // span)].append(i)
    per_month = max(1, (dl_cap - len(chosen)) // 12)
    for m in range(12): chosen.update(sorted(months[m], key=lambda i: -dl_score(dl[i]))[:per_month])
    return ev_pick, sorted(chosen)


def family_board(sn, gen):
    """Viewer-only standings: which families hold the money, the businesses, the seats and the numbers. Straight from the snapshots."""
    a, b = sn[0], sn[-1]
    def standing(s, hid):
        h = s["households"][hid]; members = [s["people"][str(m)] for m in h["members"] if str(m) in s["people"]]
        alive = [p for p in members if p["alive"] and not p["offtown"]]
        owned = [c for c in s["companies"].values() if str(s["people"].get(str(c["owner"]), {}).get("household")) == str(hid) and c["status"] == "open"]
        off = s["town"]["offices"]; seats = [("mayor" if pid == off["mayor"] else "council") for pid in [off["mayor"]] + off["council"] if pid and str(s["people"].get(str(pid), {}).get("household")) == str(hid)]
        return {"surname": h["surname"], "savings": h["savings"], "people": len(alive), "businesses": [c["name"] for c in owned], "seats": seats,
                "home": "burned out" if (s.get("places", {}).get(f"home_{hid}", {}).get("burned")) else "damaged" if h.get("condition", 1) < 0.7 else "standing"}
    rows = []
    for hid in b["households"]:
        now = standing(b, hid); was = standing(a, hid) if hid in a["households"] else None
        if now["people"] == 0 and not now["businesses"]: continue
        score = now["savings"] + 4000 * len(now["businesses"]) + 2500 * len(now["seats"]) + 150 * now["people"]  # a simple published formula for the ranking
        rows.append({**now, "hid": hid, "score": score, "was_savings": was["savings"] if was else 0, "new": was is None})
    rows.sort(key=lambda r: -r["score"])
    for k, r in enumerate(rows): r["rank"] = k + 1
    start_rank = {r["hid"]: k + 1 for k, r in enumerate(sorted([{"hid": h, "score": standing(a, h)["savings"] + 4000 * len(standing(a, h)["businesses"]) + 2500 * len(standing(a, h)["seats"]) + 150 * standing(a, h)["people"]} for h in a["households"]], key=lambda r: -r["score"]))}
    for r in rows: r["was_rank"] = start_rank.get(r["hid"])
    return {"year_end": b["date"][:4], "rows": rows[:8], "question": "Which family runs this town by 2000?",
            "formula": "savings + $4,000 per open business + $2,500 per seat in office + $150 per person at home"}


def ledger(ev, sn, gen, notes=()):
    a, b = sn[0], sn[-1]
    alive = lambda s: [p for p in s["people"].values() if p["alive"] and not p["offtown"]]
    kinds = collections.Counter(e["kind"] for e in ev)
    hh_delta = {h: b["households"][h]["savings"] - a["households"][h]["savings"] for h in a["households"] if h in b["households"]}
    win = max(hh_delta, key=hh_delta.get) if hh_delta else None; lose = min(hh_delta, key=hh_delta.get) if hh_delta else None
    co_a, co_b = a["companies"]["co1"], b["companies"]["co1"]
    mentions = collections.Counter()
    for e in ev:
        if e["kind"] in ("eavesdrop", "conversation", "outcome", "fired", "candidacy", "election_result", "wedding"):
            for x in e["actors"]: mentions[str(x)] += 1
    mayor = b["town"]["offices"]["mayor"]
    rich = max(b["households"].values(), key=lambda h: h["savings"]); poor = min(b["households"].values(), key=lambda h: h["savings"])
    series = lambda f: [f(s) for s in sn[:: max(1, len(sn) // 12)]]
    name = lambda pid: b["people"][str(pid)]["name"] if str(pid) in b["people"] else "-"
    return {"date_end": b["date"], "season_label": b.get("season_label") or "",
            "population": len(alive(b)), "population_change": len(alive(b)) - len(alive(a)), "population_series": series(lambda s: len(alive(s))),
            "births": kinds["birth"], "deaths": kinds["death"], "arrivals": kinds["newcomer"] + kinds["returned"], "left": kinds["left_town"], "marriages": kinds["wedding"],
            "treasury": b["town"]["treasury"], "treasury_change": b["town"]["treasury"] - a["town"]["treasury"], "treasury_series": series(lambda s: s["town"]["treasury"]),
            "richest": f"{rich['surname']} ${rich['savings']:,}", "poorest": f"{poor['surname']} ${poor['savings']:,}",
            "company": co_b["name"], "company_cash": co_b["cash"], "company_change": co_b["cash"] - co_a["cash"], "company_series": series(lambda s: s["companies"]["co1"]["cash"]),
            "workers": len(co_b["employees"]), "layoffs": kinds["fired"],
            "mayor": name(mayor) if mayor else "vacant", "council_votes": f"{kinds['measure_vote']} held", "overheard": kinds["eavesdrop"], "conversations": len([e for e in ev if e["kind"] == "conversation"]),
            "most_talked_about": name(int(mentions.most_common(1)[0][0])) if mentions else "-",
            "winner": f"The {b['households'][win]['surname']} family (+${hh_delta[win]:,})" if win else "-", "loser": f"The {b['households'][lose]['surname']} family (-${abs(hh_delta[lose]):,})" if lose else "-",
            "news": [e["data"].get("headline") for e in ev if e["kind"] == "history"][:2], "notes": list(notes)}



# Aaron, Nov 20-21: innocent people must not be shown doing what only the world step wrote about them. In 1950 the world step
# authored residents' confessions, thefts, lies, secrets and drinking (fixed in the rules for 1951 on by fix 4). For the edit, a
# WORLD-written record that names a resident next to a choice/guilt word never airs; it stays in the town's log. Residents' own
# words and their own refereed actions are untouched.
EDIT_GUILT = re.compile(r"\b(drinks?|drinking|drank|drunk|lies|lied|lying|tells? \w+ it went|hides?|hid|hidden|secret\w*|burn(ed|t|s)? (the |a )?\w*\s?letter|"
                        r"takes? (another |the )?\$\s?\d+|took (another |the )?\$\s?\d+|from the (till|drawer|tin|register)|covered it|skimm\w*|pinch\w*|embezzl\w*)\b", re.I)


def world_authored_guilt(ev, sn):
    from .fate import CHOICE, CULPRIT
    ppl = {}
    for snap in sn[:: max(1, len(sn) // 24)] + [sn[-1]]:
        for p in snap["people"].values(): ppl[p["name"]] = 1
    firsts = {}
    for n in ppl: firsts.setdefault(n.split()[0], []).append(n)
    names = list(ppl) + [f for f, v in firsts.items() if len(v) == 1 and len(f) > 2]
    rx = re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")\b")
    out = set()
    for e in ev:
        if e["kind"] != "world": continue
        for snt in re.split(r"(?<=[.!?;])\s+", e["text"]):
            if rx.search(snt) and (CHOICE.search(snt) or CULPRIT.search(snt) or EDIT_GUILT.search(snt)): out.add(e["id"]); break
    return out


def last_days(dl, n_days=7, k=10):
    if not dl: return []
    end = dl[-1]["day"]
    return sorted(sorted((i for i, d in enumerate(dl) if d["day"] > end - n_days), key=lambda i: -dl_score(dl[i]))[:k])


def build_episode(run_dir, gen, mode="mock", llm=None, episode_no=1, target_minutes=13, leads=2):
    ev, dl, sn = load_run(run_dir)
    cut, cut_notes = load_cuts(run_dir)
    ev = [e for e in ev if e["id"] not in cut]  # continuity cuts never air, as scenes or as news overlays
    authored = world_authored_guilt(ev, sn); ev = [e for e in ev if e["id"] not in authored]
    json.dump(sorted(authored), open(os.path.join(run_dir, "not_aired_world_authored.json"), "w"))
    names = lambda pid: next((s["people"][str(pid)]["name"] for s in reversed(sn) if str(pid) in s["people"]), "?")
    hh_name = lambda hid: sn[-1]["households"][str(hid)]["surname"] if str(hid) in sn[-1]["households"] else "?"
    ts = thread_scores(ev, dl, sn)
    kept = [e for e in ev if keep_event(e, dl)]
    if mode == "live":
        act = activity(dl, kept)
        ev_pick, dl_pick = prefilter(ev, dl, sn, kept, act)
        pop = sum(1 for p in sn[0]["people"].values() if p["alive"] and not p["offtown"])
        rules = EDITOR_RULES.format(leads_rule="ONE LEAD: one resident, for the whole episode" if leads == 1 else "TWO LEADS: two residents, ideally whose lives are linked or cross",
                                    welcome_rule=WELCOME_EP1 if episode_no == 1 else WELCOME_LATER, pop=pop,
                                    welcome_field="2-3 sentence welcome to the town and the lead(s)" if episode_no == 1 else "1-2 sentence previously, or empty")
        lines = [f"TOWN: {gen['name']}, {gen['region']}. Episode {episode_no}. Period: {sn[0]['date']} to {sn[-1]['date']} (one year). Target length: about {target_minutes} minutes "
                 f"(roughly {target_minutes * 9} dialogue lines in total; the narrator speaks less than a quarter of the words). "
                 f"Use at most {max(4, round(target_minutes * 1.8))} scenes: fewer, fuller scenes (3-4 lines each) beat many short ones. "  # Aaron, Nov 18: too many short scenes
                 f"The year held {len(dl)} conversations; the {len(dl_pick)} strongest are below, with their original numbers.",
                 "RESIDENTS WHO WERE IN THE MOST SCENES (candidates, not a ranking): " + "; ".join(f"{names(pid)} ({sn[-1]['people'][str(pid)]['age']}, {sn[-1]['people'][str(pid)]['job'] or 'no job'})" for pid, _ in act.most_common(12)), ""] + (["CONTINUITY NOTES (from the town's own record; follow them):"] + [f"- {x}" for x in cut_notes] + [""] if cut_notes else []) + ["EVENTS:"]
        for e in ev_pick:
            lines.append(f"[{e['id']}] {e['date']} {e['slot']} ({e['kind']}{', sensitive' if e['sensitive'] else ''}): {e['text']}")
        lines += ["", "DIALOGUES:"]
        for i in dl_pick:
            d = dl[i]
            lines.append(f"<{i}> {d['date']} {d['slot']}, {d['medium']}, at {d['place']}: {names(d['a'])} & {names(d['b'])}" + (f" (deal: {d['deals'][0]['terms']})" if d["deals"] else ""))
            for k, (sp, t) in enumerate(d["lines"]): lines.append(f"   {k}. {sp}: {t}")
        tail = last_days(dl)
        def dline(i, cap=None):
            d = dl[i]; L = [f"<{i}> {d['date']} {d['slot']}, {d['medium']}, at {d['place']}: {names(d['a'])} & {names(d['b'])}"]
            return L + [f"   {k}. {sp}: {t}" for k, (sp, t) in enumerate(d["lines"][:cap] if cap else d["lines"])]
        lines += ["", "LAST DAYS OF THE YEAR (pick the closing scene from these):"]
        for i in tail: lines += dline(i)
        plan_in = {"tail": tail}
        out = None
        for attempt in range(2):  # one retry if the reply didn't come back as clean JSON
            out, raw = llm.call_json("editor", [rules], [{"role": "user", "content": "\n".join(lines)}], max_tokens=48000)  # Nov 21: thinking used all of 24k once the closing scene was added
            if out and out.get("scenes"): break
        plan = out or {}
    else:
        plan = mock_plan(ev, dl, sn, gen, ts, episode_no, names, hh_name)
        plan_in = {"tail": last_days(dl)}
    plan = validate(plan, ev, dl)
    plan = validate_extras(plan, ev, dl, plan_in)
    followed = [l["name"] for l in plan.get("leads", [])] or [t.get("name", "") for t in plan.get("threads", [])]  # live plans name leads; mock plans name threads
    notes = [f"Followed: " + ", ".join(followed)] if followed else []
    plan["ledger"] = ledger(ev, sn, gen, notes); plan["family_board"] = family_board(sn, gen); plan["town"] = {"name": gen["name"], "geography": gen["geography"], "region": gen["region"]}; plan["episode"] = episode_no
    used_e = {i for s in plan["scenes"] for i in s.get("event_ids", [])}
    plan["_events"] = {e["id"]: e for e in ev if e["id"] in used_e or overlays_news(e)}
    used_d = {s["dialogue_index"] for s in plan["scenes"] if s.get("dialogue_index") is not None} | {plan["cold_open"].get("dialogue_index")} | {x.get("dialogue_index") for x in plan.get("shorts", [])} | {(plan.get("closing_scene") or {}).get("dialogue_index")}
    plan["_dialogues"] = {i: dl[i] for i in used_d if i is not None and 0 <= i < len(dl)}
    json.dump(plan, open(os.path.join(run_dir, f"episode_{episode_no}_plan.json"), "w"), indent=1, default=str)
    return plan


def validate_extras(plan, ev, dl, plan_in):
    """Closing scene (Aaron, Nov 21): must be one of the year's last-days conversations, exact words only. If the editor's pick
    fails, fall back to the latest strong real one; never repaired by invention."""
    def keep_lines(di, ls, cap):
        out = []
        for x in ls or []:
            try: k = int(x.get("n") if isinstance(x, dict) else x)
            except (TypeError, ValueError): continue
            if 0 <= k < len(dl[di]["lines"]) and k not in [z["n"] for z in out]:
                full = dl[di]["lines"][k][1]; kp = _norm(x.get("keep")) if isinstance(x, dict) else ""
                out.append({"n": k, "keep": kp if kp and kp in _norm(full) else full})
        return sorted(out, key=lambda z: z["n"])[:cap]
    used = {s["dialogue_index"] for s in plan["scenes"] if s["dialogue_index"] is not None} | {plan["cold_open"].get("dialogue_index")}
    cs = plan.get("closing_scene") or {}; di = cs.get("dialogue_index")
    if not (isinstance(di, int) and di in plan_in["tail"]):
        di = next((i for i in reversed(plan_in["tail"]) if i not in used), None)  # fallback: the latest strongest real one
    plan["closing_scene"] = None
    if di is not None and di not in used:
        ls = keep_lines(di, cs.get("lines"), 3) or [{"n": k, "keep": dl[di]["lines"][k][1]} for k in range(min(2, len(dl[di]["lines"])))]
        plan["closing_scene"] = {"dialogue_index": di, "lines": ls, "narration": short_setup(cs.get("setup") or "")}
    return plan


def overlays_news(e):
    from .overlays import is_news
    return is_news(e)


def _norm(x): return re.sub(r"\s+", " ", x or "").strip()


SETUP_MAX_WORDS = 28


def short_setup(text):
    """Keep a scene setup short (the residents carry the story): if the editor ran long, keep only its first sentence.
    Never cuts mid-sentence, never adds words."""
    t = _norm(text)
    if len(t.split()) <= SETUP_MAX_WORDS: return t
    first = re.split(r"(?<=[.!?;])\s+", t)[0].rstrip(";").strip()
    if first and not first.endswith((".", "!", "?")): first += "."
    return first


def validate(plan, ev, dl):
    """Keep only real ids, real line numbers and EXACT words from the real lines; at most 4 lines per conversation; scenes in time order."""
    ids = {e["id"]: e for e in ev}
    def lines_ok(di, ls, cap=4):
        if di is None or not (0 <= di < len(dl)): return []
        n = len(dl[di]["lines"]); out, seen = [], set()
        for x in ls or []:
            k = x.get("n") if isinstance(x, dict) else x
            try: k = int(k)
            except (TypeError, ValueError): continue
            if not (0 <= k < n) or k in seen: continue
            full = dl[di]["lines"][k][1]; keep = _norm(x.get("keep")) if isinstance(x, dict) else ""
            out.append({"n": k, "keep": keep if keep and keep in _norm(full) else full}); seen.add(k)
        out.sort(key=lambda z: z["n"])
        return out[:cap] or [{"n": k, "keep": dl[di]["lines"][k][1]} for k in range(min(n, 3))]
    scenes = []
    for s in plan.get("scenes", []):
        di = s.get("dialogue_index"); di = di if isinstance(di, int) and 0 <= di < len(dl) else None
        es = [i for i in s.get("event_ids", []) if i in ids]
        if di is None and not es: continue
        ls = lines_ok(di, s.get("lines")) if di is not None else []
        th = s.get("thought"); asides = dl[di].get("asides", []) if di is not None else []
        th = th if isinstance(th, int) and th in [z["n"] for z in ls] and th < len(asides) and asides[th] else None
        scenes.append({"thread": s.get("lead") or s.get("thread", ""), "dialogue_index": di, "lines": ls, "thought": None, "event_ids": es,  # thought bubbles paused
                       "narration": short_setup(s.get("setup") or s.get("narration") or "")})
    slot_i = lambda x: ["morning", "midday", "evening", "night"].index(x)
    when = lambda s: (dl[s["dialogue_index"]]["day"], slot_i(dl[s["dialogue_index"]]["slot"])) if s["dialogue_index"] is not None else (ids[s["event_ids"][0]]["day"], slot_i(ids[s["event_ids"][0]]["slot"]))
    plan["scenes"] = sorted(scenes, key=when)
    co = plan.get("cold_open") or {}; cdi = co.get("dialogue_index")
    if not (isinstance(cdi, int) and 0 <= cdi < len(dl)): cdi = next((s["dialogue_index"] for s in plan["scenes"] if s["dialogue_index"] is not None), None)
    plan["cold_open"] = {"dialogue_index": cdi, "lines": lines_ok(cdi, co.get("lines"), 3) if cdi is not None else [], "hook": (co.get("hook") or "").strip()}
    plan["shorts"] = [{"dialogue_index": x["dialogue_index"], "lines": lines_ok(x["dialogue_index"], x.get("lines")), "hook": x.get("hook", "")[:50]}
                      for x in plan.get("shorts", []) if isinstance(x.get("dialogue_index"), int) and 0 <= x["dialogue_index"] < len(dl)]
    leads = [l for l in plan.get("leads", []) if isinstance(l, dict) and l.get("name")]
    plan["leads"] = leads
    plan["intros"] = {**{k: str(v)[:60] for k, v in (plan.get("intros") or {}).items() if isinstance(k, str)}, **{l["name"]: str(l.get("intro", ""))[:60] for l in leads}}
    plan["welcome"] = (plan.get("welcome") or "").strip()
    plan["title"] = (plan.get("title") or "").strip()[:70]
    return plan


def mock_plan(ev, dl, sn, gen, ts, episode_no, names, hh_name):
    """Dry-run stand-in for the live editor: same structure, picked by score, no invented words beyond [MOCK] tags."""
    threads = [h for h, _ in ts.most_common(2)]
    hh = lambda pid: household_of(sn, pid)
    scenes = []
    if dl:  # year shape: the leads' best conversation in each quarter, plus the year's big events, all in time order
        first, span = dl[0]["day"], max(1, dl[-1]["day"] - dl[0]["day"] + 1)
        for h in threads:
            for q in range(4):
                mine = [i for i, d in enumerate(dl) if h in (hh(d["a"]), hh(d["b"])) and (d["day"] - first) * 4 // span == q]
                for i in sorted(mine, key=lambda i: -dl_score(dl[i]))[:1]:
                    scenes.append({"thread": f"The {hh_name(h)}s", "dialogue_index": i, "lines": list(range(min(3, len(dl[i]["lines"])))), "thought": None, "event_ids": [], "narration": "[MOCK] setup."})
    big = sorted([e for e in ev if keep_event(e, dl) and (ev_score(e) >= 12 or e["kind"] in ("town_event", "newcomer", "purchase") and e["importance"] >= 4)], key=lambda e: -ev_score(e))[:8]
    for e in big: scenes.append({"thread": "town", "dialogue_index": None, "lines": [], "event_ids": [e["id"]], "narration": f"[MOCK] {e['text']}"})
    best = max(range(len(dl)), key=lambda i: dl_score(dl[i])) if dl else None
    lead_pid = next((d["a"] for d in dl), None)
    return {"title": f"[MOCK] Episode {episode_no}: {gen['name']}", "leads": [{"name": names(lead_pid), "intro": "[MOCK] who they are", "want": "[MOCK] what they want."}] if lead_pid else [],
            "welcome": "[MOCK] Welcome to the town. Meet our lead.", "threads": [{"name": f"The {hh_name(h)}s", "people": [], "why": "[MOCK]"} for h in threads],
            "cold_open": {"dialogue_index": best, "lines": [0, 1], "hook": "[MOCK] hook sentence."}, "scenes": scenes, "closing": "[MOCK] closing line.", "teaser": "[MOCK] teaser line.",
            "shorts": [], "thumbnail_dialogue_index": best, "thumbnail_text": "[MOCK] Big Words"}


if __name__ == "__main__":
    import sys
    run, world = sys.argv[1], sys.argv[2]; live = "--live" in sys.argv
    gen = json.load(open(world)); llm = LLM("live", 3.0) if live else None
    p = build_episode(run, gen, "live" if live else "mock", llm)
    print(json.dumps({k: p[k] for k in ("title", "threads")}, indent=1, default=str)[:2500], "\nscenes:", len(p["scenes"]))
