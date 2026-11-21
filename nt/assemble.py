"""Episode assembler: episode plan -> silent MP4 + timed voice script by role + SRT.
Structure (fixed): cold open -> title -> scenes -> closing -> Ledger -> teaser -> end screen.
Every scene opens with a short establishing shot (a side-scrolling pan down the street, at the scene's real time of day)
with the Town Board; then the people talk, board hidden. Big news shows briefly on the board's bottom line.
Weather is only ever what you see in the picture.
usage: python3 -m nt.assemble <run_dir> <world.json> [episode_no] [--fps 24]"""
import json, os, re, subprocess, sys
from . import scenes, overlays, voices, cutaways
from .art import OW, OH

NEG = re.compile(r"\b(no|never|hate|damn|liar|fired|lose|lost|broke|won't|can't|get out|how dare|stole)\b", re.I)
POS = re.compile(r"\b(thank|wonderful|love|glad|congrat|happy|yes|grand|swell)\b", re.I)
SAD = re.compile(r"\b(sorry|miss|died|gone|funeral|alone|cry|lost him|lost her)\b", re.I)
GAZETTE_KINDS = ("election_result", "death", "wedding", "birth", "fame")
SLOTS = ["morning", "midday", "evening", "night"]
PLACE_KIND = {"diner": "diner", "town_hall": "town_hall", "company": "company", "store": "store"}
BOARD_NEWS = False  # Aaron, Nov 18: the news line under the Town Board was too small to read. The announcer still reads the news aloud.


def expr_of(text):
    if SAD.search(text): return "sad"
    if "!" in text and NEG.search(text): return "angry"
    if text.strip().endswith("?!") or "what?" in text.lower(): return "shocked"
    if NEG.search(text): return "angry" if "!" in text else "scheming"
    if POS.search(text): return "happy"
    return "neutral"


def words_secs(text): return max(2.5, len((text or "").split()) / 2.6 + 0.6) if text else 0.0
def line_secs(text): return max(3.0, len(text.split()) / 2.8 + 1.0)


def caption_pages(text, max_rows=2):
    from PIL import Image, ImageDraw
    from .art import font, FB
    d = ImageDraw.Draw(Image.new("RGB", (8, 8))); f = font(FB, 30); width = OW - 240
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
    pages, cur = [], ""
    for s in sents:
        trial = (cur + " " + s).strip()
        if len(scenes.wrap(d, trial, f, width)) <= max_rows: cur = trial; continue
        if cur: pages.append(cur); cur = ""
        rows = scenes.wrap(d, s, f, width)
        while len(rows) > max_rows: pages.append(" ".join(rows[:max_rows])); rows = rows[max_rows:]
        cur = " ".join(rows)
    if cur: pages.append(cur)
    return pages


def page_times(text, offset, real=None):
    """real: the recorded voice length in seconds when known (Nov 21 fix: with the word estimate, a narrator who read faster than
    the estimate left the last caption page timed after the shot ended, so it never showed, e.g. Part 2's teaser)."""
    pages = caption_pages(text); total = sum(len(p.split()) for p in pages) or 1
    read = (real - 0.3) if real else words_secs(text) - 0.6
    out, acc = [], 0
    for p in pages: out.append((offset + read * acc / total, p)); acc += len(p.split())
    return out


def box_pages(text, rows=3):
    """Split a resident's line into pages that fit the dialogue box, breaking at sentence ends where possible."""
    from PIL import Image, ImageDraw
    from .art import font, FR
    d = ImageDraw.Draw(Image.new("RGB", (8, 8))); f = font(FR, 27); width = OW - 80 - 210
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    pages, cur = [], ""
    for x in sents:
        trial = (cur + " " + x).strip()
        if len(scenes.wrap(d, trial, f, width)) <= rows: cur = trial; continue
        if cur: pages.append(cur); cur = ""
        r_ = scenes.wrap(d, x, f, width)
        while len(r_) > rows: pages.append(" ".join(r_[:rows])); r_ = r_[rows:]
        cur = " ".join(r_)
    if cur: pages.append(cur)
    return pages or [text]


class Timeline:
    def __init__(self, vo=None):
        """vo: {role: [real recorded seconds per line, in order]}. When given, the picture is timed to the real voices, not word-count estimates."""
        self.shots = []; self.narr = []; self.voices = []; self.t = 0.0
        self.vo = {k: list(v) for k, v in (vo or {}).items()}

    def secs(self, role, text, estimate):
        q = self.vo.get(role)
        return q.pop(0) + 0.15 if q else estimate

    def add(self, kind, dur, narration=None, pre=None, **kw):
        """pre: [(role, text)] read before the narration (announcer). The narrator never talks over the announcer."""
        off = 0.3; lines = []
        for role, text in pre or []:
            d = self.secs(role, text, words_secs(text)); lines.append({"start": round(self.t + off, 2), "role": role, "text": text, "max_seconds": round(d, 2)}); off += d + 0.2
        narr_offset = off if pre else 0.3
        need = off + 0.3 if pre else 0.0
        if narration:
            nd = self.secs("narrator", narration, words_secs(narration))
            lines.append({"start": round(self.t + narr_offset, 2), "role": "narrator", "text": narration, "max_seconds": round(nd, 2)}); need = narr_offset + nd + 0.3
            self.narr.append({"start": round(self.t + narr_offset, 2), "text": narration})
        dur = max(dur, need)
        sh = {"kind": kind, "start": self.t, "dur": dur, "narration": narration, "narr_offset": narr_offset, "narr_secs": nd if narration else None, **kw}
        self.voices += lines; self.shots.append(sh); self.t += dur
        return sh

    def add_line(self, pid, name, text, **kw):
        """One spoken line. Long lines page through the dialogue box (3 rows at a time) while the voice reads the whole line."""
        real = self.vo.get(f"resident:{pid}")
        dur = real.pop(0) + 0.65 if real else line_secs(text)
        self.voices.append({"start": round(self.t + 0.25, 2), "role": f"resident:{pid}", "name": name, "text": text, "max_seconds": round(dur - 0.4, 2)})
        pages = box_pages(text); total = sum(len(p.split()) for p in pages) or 1
        for k, pg in enumerate(pages):
            kw2 = dict(kw); kw2["line"] = (kw["line"][0], pg, kw["line"][2])
            if k > 0: kw2["intro"] = None
            self.add("interior", dur * len(pg.split()) / total, None, **kw2)


def build_timeline(plan, sn, gen, short=False, vo=None):
    """short=True: a pilot or trailer cut with no closing tail (time-lapse, Ledger, Family Board, end screen).
    vo: real recorded line lengths by role (see nt.mix); the picture is then timed to the voices."""
    T = Timeline(vo); seed = gen["seed"]; introduced = set()
    ev = {int(k): v for k, v in plan.get("_events", {}).items()}; dl = {int(k): v for k, v in plan.get("_dialogues", {}).items()}
    snap_at = lambda day: sn[min(max(0, day), len(sn) - 1)]
    all_h = lambda s: sorted(s["households"], key=int)
    news_q = sorted([e for e in ev.values() if overlays.is_news(e) and e["kind"] not in GAZETTE_KINDS], key=lambda e: e["id"])
    state = {"news_shown": set(), "last_board": None}

    intros = plan.get("intros") or {}

    def conversation(d, picked, cold=False, thought=None):
        """picked: [{"n": line number, "keep": exact words}]. Cuts between a two-shot and close-ups; one optional private thought."""
        s = snap_at(d["day"]); tod = d["slot"]
        place = str(d["place"]); pk = "home" if place.startswith("home") else PLACE_KIND.get(place, "home")
        hh = int(place.split("_")[1]) if place.startswith("home_") else s["people"][str(d["a"])]["household"]
        asides = d.get("asides") or []
        for j, x in enumerate(picked):
            k = x["n"] if isinstance(x, dict) else x; text = x["keep"] if isinstance(x, dict) else d["lines"][k][1]
            sp = d["lines"][k][0]
            pid = d["a"] if s["people"][str(d["a"])]["name"] == sp else d["b"]
            p = s["people"][str(pid)]; name = p["name"]
            zoom = None if (j == 0 or j % 3 == 2) else pid   # open on the two-shot, then cut in; back out every third line
            intro = None
            if not cold and name in intros and name not in introduced:
                introduced.add(name); intro = (name, f"{p['age']}  ·  {(p.get('job') or 'no job').replace('works at ', '')}", intros[name])
            T.add_line(pid, name, text, snap=s, place=pk, hid=hh, speakers=[d["a"], d["b"]], line=(pid, text, expr_of(text)), tod=tod, cold=cold, zoom=zoom, intro=intro)
            if thought is not None and k == thought and k < len(asides) and asides[k]:
                th = asides[k]; dur = line_secs(th) + 0.4
                T.voices.append({"start": round(T.t + 0.3, 2), "role": f"resident:{pid}", "name": name, "text": th, "max_seconds": round(dur - 0.5, 2), "style": "private thought: softer, close to the mic"})
                T.add("interior", dur, None, snap=s, place=pk, hid=hh, speakers=[d["a"], d["b"]], line=None, thought=(pid, th), tod=tod, cold=cold, zoom=pid)

    def setting_of(place):
        p = str(place or "")
        if p in ("diner", "store", "town_hall", "school"): return "main"
        if p == "company": return "works"
        if p.startswith("lm_"): return "country"
        return "home"

    def establishing(day, tod, hids, narration, walkers=(), place=None):
        s = snap_at(day); board = overlays.board_state(s)
        # big public news since the last board: shown on the board's bottom line, read by the announcer
        fresh = [e for e in news_q if e["day"] <= day and e["id"] not in state["news_shown"]]
        news = overlays.news_text(fresh[-1]) if fresh else None
        for e in fresh: state["news_shown"].add(e["id"])
        pre = [("announcer", f"News from {gen['name']}. " + voices.speakable(news))] if news else None
        order = list(hids) + [h for h in all_h(s) if h not in hids]
        T.add("pan", 3.2 if (narration or pre) else 2.6, narration, pre=pre, snap=s, board=board, news=news, hids=order[:6], tod=tod, weather=s["weather"].get("sky", "clear"), season=s["season"], walkers=list(walkers), setting=setting_of(place), place=place)

    # ---- cold open: the strongest real exchange, a few lines, no board
    co = plan.get("cold_open") or {}
    if co.get("dialogue_index") in dl and co.get("lines"):
        cd = dl[co["dialogue_index"]]; conversation(cd, co["lines"], cold=True)
        if co.get("hook"):
            s0 = snap_at(cd["day"]); hh0 = [str(s0["people"][str(x)]["household"]) for x in (cd["a"], cd["b"])]
            T.add("pan", 3.0, co["hook"], snap=s0, board=None, news=None, hids=list(dict.fromkeys(hh0)) + [h for h in all_h(s0) if h not in hh0], tod=cd["slot"], weather=s0["weather"].get("sky", "clear"), season=s0["season"], walkers=[])
    pop = plan["ledger"]["population"]; year = sn[0]["date"][:4]
    premise = f"{pop} people. {year}. Every one of them is an AI. Nobody is steering."
    T.add("title", 5.0, premise, town=gen["name"], episode=plan["episode"], title=plan.get("title", ""), pop=pop, premise=premise)
    # ---- welcome (Episode 1) or previously (later): a slow look at the town, then meet the lead(s)
    s0 = sn[0]
    if plan.get("welcome"):
        T.add("pan", 4.0, plan["welcome"], snap=s0, board=overlays.board_state(s0), news=None, hids=all_h(s0)[:6], tod="morning", weather="clear", season=s0["season"], walkers=[], setting="main", place="diner", sign_pop=overlays.population(s0), sign_town=gen["name"])
    T.add("overview", 3.5, None, snap=s0, tod="morning", weather="clear", season=s0["season"])  # the whole town as the year begins
    by_name = {v["name"]: int(k) for k, v in sn[-1]["people"].items()}
    for l in plan.get("leads", []):
        pid = by_name.get(l["name"])
        if pid is None: continue
        p = sn[-1]["people"][str(pid)]; introduced.add(l["name"])
        T.add("meet", 3.5, l.get("want") or None, snap=sn[-1], pid=pid, name=l["name"], sub=f"{p['age']}  ·  {(p.get('job') or 'no job').replace('works at ', '')}", intro=l.get("intro", ""))
    # ---- scenes
    for sc in plan.get("scenes", []):
        di = sc.get("dialogue_index"); es = [ev[i] for i in sc.get("event_ids", []) if i in ev]
        if di in dl:
            d = dl[di]; s = snap_at(d["day"])
            hh = [str(s["people"][str(x)]["household"]) for x in (d["a"], d["b"])]
            establishing(d["day"], d["slot"], list(dict.fromkeys(hh)), sc.get("narration") or None, place=d["place"])
            conversation(d, sc["lines"], thought=sc.get("thought"))
        elif es:
            e = es[0]; s = snap_at(e["day"])
            if e["kind"] in ("election_result", "fame"):
                import datetime as _dt
                date = _dt.date.fromisoformat(s["date"]).strftime("%A, %B %d, %Y").replace(" 0", " ")
                head, sub = e["text"], ""
                if e["kind"] == "election_result":
                    m = re.search(r"Mayor: ([^.]+)\.", e["text"]); who = (m.group(1) if m else "nobody").strip()
                    head = f"{who.split()[-1]} elected mayor" if who not in ("nobody",) and "runoff" not in who else "Runoff tomorrow"
                    tl = sorted((e.get("data", {}).get("tallies") or {}).items(), key=lambda kv: -kv[1]); sub = "  ·  ".join(f"{n} {v}" for n, v in tl)
                establishing(e["day"], e["slot"], [], None)
                T.add("newspaper", 5.0, sc.get("narration") or None, pre=[("announcer", voices.gazette_read(gen["name"], e, head))], town=gen["name"], date=date, headline=head[:90], sub=sub[:150])
            elif cutaways.kind_for(e):
                fresh = [x for x in news_q if x["day"] <= e["day"] and x["id"] not in state["news_shown"]]
                for x in fresh: state["news_shown"].add(x["id"])
                pre = [("announcer", f"News from {gen['name']}. " + voices.speakable(overlays.news_text(e)))] if overlays.is_news(e) and not sc.get("narration") else None
                T.add("cutaway", 4.2, sc.get("narration") or None, pre=pre, cut=cutaways.kind_for(e), snap=s, prev=snap_at(e["day"] - 1), event=e, board=overlays.board_state(s), news=overlays.news_text(e) if overlays.is_news(e) else None)
            else:
                hids = list(dict.fromkeys(str(s["people"][str(a)]["household"]) for a in e["actors"][:3] if str(a) in s["people"]))
                walkers = [(a, 90 + i * 80, 0, 1 if i % 2 == 0 else -1) for i, a in enumerate(e["actors"][:3]) if str(a) in s["people"] and s["people"][str(a)]["alive"]]
                establishing(e["day"], e["slot"], hids, sc.get("narration") or overlays.news_text(e), walkers, place=e.get("place"))
    # ---- closing scene (Aaron, Nov 21): end on a real moment from the last days, then the street goes dark
    cs = plan.get("closing_scene") or {}
    if cs.get("dialogue_index") in dl and cs.get("lines"):
        d = dl[cs["dialogue_index"]]; s = snap_at(d["day"])
        hh = [str(s["people"][str(x)]["household"]) for x in (d["a"], d["b"])]
        establishing(d["day"], d["slot"], list(dict.fromkeys(hh)), cs.get("narration") or None, place=d["place"])
        conversation(d, cs["lines"])
    last = sn[-1]
    if plan.get("closing"): T.add("pan", 6.0, plan["closing"], lights_out=True, snap=last, board=None, news=None, hids=all_h(last)[:6], tod="evening", weather=last["weather"].get("sky", "clear"), season=last["season"], walkers=[], sign_pop=overlays.population(last), sign_town=gen["name"])
    step = max(1, len(sn) // 12); lapse = sn[::step][:13] + ([sn[-1]] if sn[::step][-1] is not sn[-1] else [])
    if not short:
        T.add("timelapse", 9.0, None, snaps=lapse, season=last["season"])  # the year in nine seconds: what changed, where
        T.add("ledger", 11.0, None, L=plan["ledger"], town=gen["name"], episode=plan["episode"])
        if plan.get("family_board", {}).get("rows"): T.add("family", 9.0, None, fb=plan["family_board"], town=gen["name"], episode=plan["episode"])
    if plan.get("teaser"): T.add("pan", 4.0, "Next time: " + plan["teaser"], snap=last, board=None, news=None, hids=all_h(last)[-6:], tod="night", weather="clear", season=last["season"], walkers=[], teaser=True)
    if not short: T.add("endscreen", 12.0, None, season=last["season"])
    T.season = last["season"]; T.start_state = overlays.board_state(sn[0]); T.town = gen["name"]
    return T


_PANS = {}; _GEN = {}; _CACHE = {}
def _cached(sh, key, make):
    k = (id(sh), key)
    if k not in _CACHE:
        if len(_CACHE) > 40: _CACHE.clear()
        _CACHE[k] = make()
    return _CACHE[k]
def pan_for(sh, seed):
    key = id(sh)
    if key not in _PANS: _PANS.clear(); _PANS[key] = scenes.StreetPan(sh["snap"], seed, sh["hids"], sh["tod"], sh["weather"], sh["season"], sh.get("walkers", ()), setting=sh.get("setting", "home"), gen=_GEN.get("g"), place=sh.get("place"), sign_pop=sh.get("sign_pop"), town=sh.get("sign_town"))
    return _PANS[key]


def render_scene(sh, t_local, seed, gen):
    k = sh["kind"]
    if k == "pan":
        u = min(1.0, t_local / max(0.1, sh["dur"])); img = pan_for(sh, seed).frame(u, t_local)
        if sh.get("lights_out"):  # the same street at night, faded in over the second half: the town goes to bed
            key = ("night", id(sh))
            if key not in _PANS: _PANS[key] = scenes.StreetPan(sh["snap"], seed, sh["hids"], "night", sh["weather"], sh["season"], (), gen=_GEN.get("g"), sign_pop=sh.get("sign_pop"), town=sh.get("sign_town"))
            a = max(0.0, min(1.0, (u - 0.45) / 0.45))
            if a > 0:
                from PIL import Image as _I
                img = _I.blend(img, _PANS[key].frame(u, t_local), a)
                if u > 0.85: img = _I.blend(img, _I.new("RGB", img.size, (0, 0, 0)), min(1.0, (u - 0.85) / 0.15) * 0.6)
        return img
    if k == "overview": return _cached(sh, "ov", lambda: scenes.overview(sh["snap"], seed, gen, sh["tod"], sh["season"], sh["weather"], 0))
    if k == "cutaway": return _cached(sh, "cut", lambda: cutaways.Cutaway(sh["cut"], sh["snap"], seed, gen, sh["event"], sh.get("prev"))).frame(t_local)
    if k == "timelapse":
        snaps = sh["snaps"]; i = min(len(snaps) - 1, int(t_local / sh["dur"] * len(snaps))); sp = snaps[i]
        img = _cached(sh, f"tl{i}", lambda: scenes.overview(sp, seed, gen, "midday", sp["season"], "snow" if sp["season"] == "winter" else "clear", 0)).copy()
        import datetime as _dt
        return scenes.season_stamp(img, f"{sp['season'].upper()} {sp['date'][:4]}")
    if k == "family": return scenes.family_board_card(sh["fb"], sh["town"], sh.get("episode"))
    if k == "interior": return scenes.interior(sh["snap"], seed, sh["place"], sh["hid"], sh["speakers"], sh["line"], sh["tod"], sh.get("zoom"), sh.get("thought"), sh.get("intro"))
    if k == "newspaper": return scenes.newspaper(sh["town"], sh["date"], sh["headline"], sh.get("sub", ""))
    if k == "meet": return scenes.meet_card(sh["snap"], seed, sh["pid"], sh["name"], sh["sub"], sh["intro"])
    if k == "title":
        from .brandkit import title_card
        return title_card(sh["town"], sh["episode"], sh["title"], sh.get("pop", "?"), sh.get("premise"))
    if k == "ledger": return scenes.ledger_card(sh["L"], sh["town"], sh["episode"])
    if k == "endscreen":
        from .brandkit import end_screen
        return end_screen(sh["season"]).resize((OW, OH))
    raise ValueError(k)


_WM = {}
WM_SIZE, WM_ALPHA = 56, 0.55  # corner globe: always on (survives clips and reposts), small and faint (Aaron, Nov 19)
def _wm(season):
    if season not in _WM:
        from .brandkit import watermark
        wm = watermark(WM_SIZE, season); a = wm.getchannel("A").point(lambda v: int(v * WM_ALPHA)); wm.putalpha(a)
        _WM[season] = wm
    return _WM[season]


def base_layer(sh, t_local, seed, gen):
    img = render_scene(sh, t_local, seed, gen)
    if sh["kind"] not in ("title", "endscreen"):  # seasonal globe watermark, top-right
        wm = _wm(sh.get("_season", "winter")); img.paste(wm, (OW - wm.width - 18, 18), wm)
    return img


def captions_for(sh):
    if not sh.get("narration") or sh["kind"] in ("title", "ledger"): return []
    return page_times(sh["narration"], sh.get("narr_offset", 0.3), sh.get("narr_secs"))


def plan_boards(T):
    """Which board numbers flash: compared with the last board the viewer actually saw."""
    prev = T.start_state
    for sh in T.shots:
        b = sh.get("board")
        if not b: continue
        sh["_delta"] = overlays.deltas(prev, b); prev = b


def ENC_EPISODE():
    """NT_MASTER=1 (Nov 21): upload master. 3x nearest-neighbor to 3840x2160 (pixel-perfect; YouTube gives 4K uploads its better codec
    and bitrate, so pixel art stays crisp even at 1080p), high quality. Default: the quick 720p preview encode."""
    if os.environ.get("NT_MASTER"):
        return ["-vf", "scale=3840:2160:flags=neighbor", "-c:v", "libx264", "-preset", "medium", "-tune", "animation", "-crf", "16"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]


def render(T, out_mp4, seed, gen, fps=24):
    plan_boards(T); _GEN["g"] = gen
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(fps), "-i", "-",
                          *ENC_EPISODE(), "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_mp4], stdin=subprocess.PIPE)
    for sh in T.shots:
        sh["_season"] = getattr(T, "season", "winter"); town = getattr(T, "town", "")
        n = max(1, int(round(sh["dur"] * fps))); animated = sh["kind"] in ("pan", "cutaway", "timelapse")
        board = sh.get("board"); delta = sh.get("_delta") or {}
        # the board shows the news line for its first ~3.5 s, then settles to plain; changed numbers flash for 2.4 s
        b_news = overlays.town_board(board, town, delta, sh.get("news")) if board and sh.get("news") and BOARD_NEWS else None
        b_hot = overlays.town_board(board, town, delta) if board and delta else None
        b_plain = overlays.town_board(board, town) if board else None
        caps = captions_for(sh); static = None if animated else base_layer(sh, 0.0, seed, gen); cache = {}
        for i in range(n):
            t = i / fps
            ci = None
            for k, (start, _) in enumerate(caps):
                if t >= start: ci = k
            if animated:
                frame = base_layer(sh, t, seed, gen)
                if ci is not None: frame = scenes.caption(frame, caps[ci][1])
            else:
                if ci not in cache: cache[ci] = static if ci is None else scenes.caption(static.copy(), caps[ci][1])
                frame = cache[ci].copy()
            if board:
                bd = b_news if (b_news and t < 3.5) else b_hot if (b_hot and t < 2.4) else b_plain
                frame.paste(bd, overlays.BOARD_XY, bd)
            p.stdin.write(frame.tobytes())
    p.stdin.close(); p.wait()


def make_thumbnail(plan, sn, gen, out):
    from .brandkit import thumbnail
    dl = {int(k): v for k, v in plan.get("_dialogues", {}).items()}
    di = plan.get("thumbnail_dialogue_index"); d = dl.get(di) or (next(iter(dl.values())) if dl else None)
    seed = gen["seed"]; s = sn[min(d["day"], len(sn) - 1)] if d else sn[-1]
    who = d["a"] if d else int(next(iter(s["people"])))
    line = d["lines"][0][1] if d else ""
    hids = [str(s["people"][str(who)]["household"])] + [h for h in sorted(s["households"], key=int) if h != str(s["people"][str(who)]["household"])][:2]
    scene = scenes.street(s, seed, hids, [(who, 200, 0, 1)], d["slot"] if d else "evening", "clear", s["season"])
    ex = expr_of(line); face = scenes.portrait(scenes.app_of(s, who, seed), ex if ex != "neutral" else "shocked")
    thumbnail(scene, face, plan.get("thumbnail_text") or plan.get("title", ""), plan["episode"]).save(out)


def srt(T, path):
    def ts(x): h = int(x // 3600); m = int(x % 3600 // 60); s = x % 60; return f"{h:02}:{m:02}:{int(s):02},{int((s % 1) * 1000):03}"
    cues = []
    for v in T.voices:
        if v["role"] == "narrator":
            pages = page_times(v["text"], v["start"], v["max_seconds"])
            for j, (st, txt) in enumerate(pages): cues.append((st, pages[j + 1][0] if j + 1 < len(pages) else v["start"] + v["max_seconds"], txt))
        else:
            txt = f"{v['name'].split()[0]}: {v['text']}" if v["role"].startswith("resident:") else v["text"]
            cues.append((v["start"], v["start"] + v["max_seconds"], txt))
    cues.sort()
    with open(path, "w") as f:
        for k, (st, end, txt) in enumerate(cues):
            if k + 1 < len(cues): end = min(end, cues[k + 1][0] - 0.05)
            f.write(f"{k + 1}\n{ts(st)} --> {ts(end)}\n{txt}\n\n")


def write_outputs(T, plan, sn, gen, run, epn):
    base = os.path.join(run, f"episode_{epn}")
    json.dump(T.narr, open(base + "_narration.json", "w"), indent=1)
    srt(T, base + ".srt")
    voices.write_files(T, base, gen, sn, plan.get("title", ""), epn)
    make_thumbnail(plan, sn, gen, base + "_thumb.png")
    # sound beds (Nov 18): the town's own sounds under the picture, from each shot's real weather, place and time of day
    if os.path.exists(base + ".mp4"):
        from . import ambience
        ambience.write_wav(ambience.bed_for_timeline(T, gen, gen["seed"]), base + "_ambience.wav")
        ambience.mux(base + ".mp4", base + "_ambience.wav", base + "_tmp.mp4"); os.replace(base + "_tmp.mp4", base + ".mp4")


def stats(T):
    secs = lambda kinds: sum(s["dur"] for s in T.shots if s["kind"] in kinds)
    # (cutaways count as story, not as conversation)
    words = lambda role: sum(len(v["text"].split()) for v in T.voices if v["role"].startswith(role))
    return {"seconds": round(T.t, 1), "shots": len(T.shots), "conversation_share": round(secs({"interior"}) / max(1, T.t), 2),
            "narrator_words": words("narrator"), "resident_words": words("resident"), "announcer_words": words("announcer"),
            "news_on_board": sum(1 for s in T.shots if s.get("news"))}


if __name__ == "__main__":
    run, world = sys.argv[1], sys.argv[2]; epn = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 1
    fps = int(sys.argv[sys.argv.index("--fps") + 1]) if "--fps" in sys.argv else 24
    gen = json.load(open(world)); plan = json.load(open(os.path.join(run, f"episode_{epn}_plan.json")))
    sn = [json.loads(l) for l in open(os.path.join(run, "snapshots.jsonl"))]
    T = build_timeline(plan, sn, gen, short="--short" in sys.argv)
    out = os.path.join(run, f"episode_{epn}.mp4"); render(T, out, gen["seed"], gen, fps)
    write_outputs(T, plan, sn, gen, run, epn)
    print(json.dumps({**stats(T), "video": out}))
