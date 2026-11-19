"""Cutaways: short animated vignettes for the year's real events (a fire, a wedding, a moving truck, a hearse, a new baby,
a TV antenna going up, a business opening or closing, a tent in the field, a wreck, a storm). Locked pixel style.
A cutaway only ever illustrates an event that truly happened; the kind is chosen from the event record, never invented.
  kind_for(event)                       -> cutaway kind or None
  Cutaway(kind, snap, seed, gen, e).frame(t) -> 1280x720 frame"""
import math, random
from PIL import Image, ImageDraw
from .art import *
from .places import GROUND, _Canvas, _backdrop, _road, _finish_panel, shopfront, works_panel, country_panel
from . import scenes

BUILD_WORDS = ("build", "built", "opens", "opened", "open a", "starts a", "started a", "shop", "store", "business", "addition", "porch", "barn", "shed", "garage", "rebuil", "repair")


def kind_for(e):
    k = e["kind"]; d = e.get("data") or {}; txt = (e.get("text") or "").lower(); sub = d.get("kind")
    if k == "town_event":
        return {"house_fire": "fire", "barn_fire": "fire", "circus": "tent", "revival_tent": "tent", "car_wreck": "wreck", "break_in": "break_in",
                "stranger": "stranger", "new_doctor": "doctor", "epidemic": "doctor", "film_crew": "film", "contract_won": "works", "contract_lost": "works",
                "raise": "works", "new_preacher": "church", "school_fight": "school", "inheritance": "mail", "bank_trouble": "main"}.get(sub)
    if k == "disaster": return "storm"
    if k == "wedding": return "wedding"
    if k == "death": return "hearse"
    if k == "birth": return "baby"
    if k in ("newcomer", "moved"): return "truck_in"
    if k == "returned": return "bus_in"
    if k == "left_town": return "bus_out"
    if k == "purchase" and "television" in txt: return "antenna"
    if k == "company_closed": return "closed"
    if k in ("telegram", "letter", "draft_notice"): return "mail"
    if k == "outcome" and any(w in txt for w in BUILD_WORDS): return "build"
    if k == "repair" and "stands again" in txt: return "build"
    if k in ("hired", "fired", "quit"): return "works"
    return None


def _house(c, snap, seed, hid, x=170, lit=False, night=False):
    wall, roof = scenes.hh_colors(hid, seed); st = scenes.house_state(snap, hid, seed)
    if night: wall, roof = sh(wall, 0.6), sh(roof, 0.6)
    house_front(c, x, 140, 76, wall, roof, GROUND, lit, st["cond"], burned=st["burned"], tv=st["tv"])
    return st


def _street_base(snap, seed, tod, season, weather="clear"):
    c = _Canvas(); _backdrop(c, tod, weather, season)
    for tx in range(-10, 500, 34):
        tc = {"autumn": (200, 110, 50), "winter": (90, 100, 110), "spring": (110, 160, 100)}.get(season, (86, 120, 92)); ty = 150 + (tx * 7) % 6
        if tod == "night": tc = sh(tc, 0.5)
        c.E(tx - 16, ty - 34, tx + 16, ty, sh(tc, 0.85)); c.E(tx - 12, ty - 38, tx + 8, ty - 14, tc)
    return c


def _people(c, snap, seed, pids, xs, facing=None):
    from .scenes import app_of
    for i, (pid, x) in enumerate(zip(pids, xs)):
        if str(pid) not in snap["people"]: continue
        sp = sprite(app_of(snap, pid, seed), 0, (facing[i] if facing else (1 if i % 2 == 0 else -1)))
        c.d.ellipse([x + 2, GROUND + 15, x + 24, GROUND + 18], fill=(30, 20, 50, 80)); c.im.paste(sp, (int(x), GROUND + 16 - sp.height), sp)


def _hid_of(snap, e):
    for a in e.get("actors", []):
        p = snap["people"].get(str(a))
        if p: return str(p["household"])
    m = [h for h, v in snap["households"].items() if v["surname"].lower() in (e.get("text") or "").lower()]
    return m[0] if m else sorted(snap["households"], key=int)[0]


class Cutaway:
    def __init__(self, kind, snap, seed, gen, e, prev_snap=None):
        self.kind, self.snap, self.seed, self.gen, self.e = kind, snap, seed, gen, e
        self.year = int(snap["date"][:4]); season = snap["season"]; self.r = random.Random(seed + e.get("id", 0))
        hid = _hid_of(snap, e); actors = [a for a in e.get("actors", []) if str(a) in snap["people"]]
        self.tod = {"fire": "night", "break_in": "night", "hearse": "morning", "storm": "evening", "tent": "evening", "wedding": "midday"}.get(kind, "midday")
        weather = "rain" if kind in ("storm", "hearse") else "clear"
        self.labels = []; self.weather = weather
        if kind in ("works", "closed"):
            self.base_big = works_panel(prev_snap or snap, seed, gen, self.tod, weather, season); self.base = None
        elif kind in ("tent", "wreck"):
            self.base_big = None; c = _Canvas(); self.base = c
            big = country_panel(snap, seed, gen, self.tod, weather, season, (gen.get("landmarks") or [""])[0]); self.base_big = big
        else:
            c = _street_base(snap, seed, self.tod, season, weather); self.base_big = None
            lit = self.tod in ("evening", "night")
            if kind in ("wedding", "hearse", "church"): shopfront(c, 180, "church", lit)
            elif kind in ("main", "film", "stranger"):
                x = 10
                for k in ("diner", "store", "post_office"): x += shopfront(c, x, k, lit) + 18
            elif kind == "school": shopfront(c, 170, "school", lit)
            elif kind == "build":
                self._frame_house(c, 170)
            else: _house(c, prev_snap if (kind == "fire" and prev_snap) else snap, seed, hid, 170, lit, self.tod == "night")
            _road(c, season, weather)
            if kind == "wedding": _people(c, snap, seed, actors[:2], [228, 252], [1, -1])
            elif kind == "hearse": _people(c, snap, seed, [p for p in snap["households"][hid]["members"] if snap["people"].get(str(p), {}).get("alive")][:3], [120, 146, 172], [1, 1, 1])
            elif kind == "baby": self._carriage(c, 236)
            elif kind == "antenna" and actors: self._ladder(c, 290)
            elif kind == "doctor": self._doctor_bag(c)
            elif kind in ("stranger",): pass
            self.base = c
        self.hid = hid; self.actors = actors
        if self.base is not None and self.base_big is None:
            self.base_img = self.base.im.copy(); self.base_labels = list(self.base._labels)

    # ---- static props
    def _frame_house(self, c, x):  # a building going up: framing, scaffolding, lumber pile
        top = GROUND - 76
        for k in range(0, 141, 14): c.R(x + k, top, x + k + 3, GROUND, (200, 160, 100))
        c.R(x, top, x + 142, top + 4, (200, 160, 100)); c.R(x, top + 36, x + 142, top + 39, (200, 160, 100))
        c.P([(x - 6, top), (x + 71, top - 34), (x + 148, top)], (0, 0, 0, 0)); c.L([(x - 6, top), (x + 71, top - 34), (x + 148, top)], (200, 160, 100), 3)
        for k in range(3): c.R(x + 160, GROUND - 6 - k * 4, x + 210, GROUND - 3 - k * 4, (190, 150, 90))
        c.R(x - 20, top + 10, x - 18, GROUND, (120, 110, 100)); c.R(x - 20, top + 40, x + 30, top + 42, (120, 110, 100))

    def _carriage(self, c, x):
        y = GROUND + 2; c.E(x, y - 22, x + 26, y - 6, (40, 50, 80)); c.R(x + 2, y - 14, x + 26, y - 6, (40, 50, 80)); c.R(x + 22, y - 26, x + 24, y - 14, (60, 60, 60))
        for wx in (x + 4, x + 20): c.E(wx - 4, y - 7, wx + 4, y + 1, INK); c.E(wx - 1, y - 4, wx + 1, y - 2, (200, 200, 200))
        boy = "boy" in (self.e.get("text") or ""); col = (130, 180, 240) if boy else (246, 160, 190)
        c.R(232, GROUND - 60, 244, GROUND - 48, col); c.P([(232, GROUND - 48), (236, GROUND - 40), (238, GROUND - 48)], col); c.P([(238, GROUND - 48), (242, GROUND - 40), (244, GROUND - 48)], col)

    def _ladder(self, c, x):
        for k in range(2): c.L([(x + k * 8, GROUND), (x + 10 + k * 8, GROUND - 90)], (150, 110, 70), 2)
        for k in range(1, 9): y = GROUND - k * 10; c.L([(x + k * 1.1, y), (x + 8 + k * 1.1, y)], (150, 110, 70), 1)

    def _doctor_bag(self, c):
        c.R(330, GROUND + 22, 376, GROUND + 26, (30, 30, 34)); car(c, 340, GROUND + 18, (30, 30, 36), self.year, model_year=self.year - 3)

    # ---- animation
    def frame(self, t):
        if self.base_big is not None:
            big = self.base_big.copy(); d = ImageDraw.Draw(big, "RGBA"); k = OW / BW
            self._big_overlay(d, t, k)
            out = vignette(big)
        else:
            c = _Canvas(); c.im = self.base_img.copy(); c.d = ImageDraw.Draw(c.im, "RGBA"); c._labels = list(self.base_labels)
            self._overlay(c, t)
            out = _finish_panel(c, self.tod); out = vignette(out)
        if self.weather in ("rain", "snow"): scenes.precip(out, self.weather, t)
        return out

    def _overlay(self, c, t):
        k = self.kind; r = random.Random(int(t * 8)); y = GROUND + 18
        if k == "fire":
            sev = (self.e.get("data") or {}).get("severity", "bad"); n = {"small": 4, "bad": 9, "destroyed": 14}.get(sev, 8)
            for i in range(n):
                fx = 180 + (i * 37) % 130 + r.randint(-3, 3); fh = r.randint(16, 40) * (1.4 if sev == "destroyed" else 1)
                fy = GROUND - (20 if sev == "small" else 60) - (i % 3) * 10
                c.P([(fx - 8, fy), (fx, fy - fh), (fx + 8, fy)], (240, 120, 40)); c.P([(fx - 4, fy), (fx + 1, fy - fh * 0.6), (fx + 5, fy)], (255, 220, 110))
            for i in range(6):
                sy = GROUND - 90 - ((t * 30 + i * 22) % 120); c.E(220 + i * 12 + math.sin(t + i) * 8, sy, 250 + i * 12, sy + 22, (90, 86, 96, 120))
            g = Image.new("RGBA", c.im.size, (255, 140, 50, 30 + r.randint(0, 20))); c.im.paste(Image.alpha_composite(c.im.convert("RGBA"), g).convert("RGB"))
        elif k in ("truck_in", "bus_in", "bus_out"):
            x = (-80 + t * 70) if k != "bus_out" else (200 + t * 80)
            if k == "truck_in": x = min(x, 330)
            if k == "truck_in":
                c.R(x, y - 30, x + 54, y, (200, 190, 160)); c.R(x + 54, y - 20, x + 74, y, (170, 40, 50)); c.R(x + 60, y - 18, x + 70, y - 10, (150, 190, 220))
                c._labels.append((x + 27, y - 15, "MOVING", INK))
            else:
                c.R(x, y - 26, x + 90, y, (150, 160, 175)); c.R(x, y - 26, x + 90, y - 22, (60, 80, 140)); [c.R(x + 6 + i * 14, y - 20, x + 16 + i * 14, y - 12, (150, 190, 220)) for i in range(6)]
            for wx in (x + 12, x + 60): c.E(wx - 5, y - 4, wx + 5, y + 6, (30, 28, 34))
        elif k == "wedding":
            for i in range(40):
                cx = (i * 53 + t * 20 * (1 + i % 3)) % 480; cy = (i * 29 + t * 40) % 200
                c.R(cx, cy, cx + 2, cy + 2, [RED, BUTTER, TEAL, (250, 250, 250)][i % 4])
            car(c, 340, GROUND + 18, (240, 240, 236), self.year, model_year=self.year - 2); c._labels.append((386, GROUND + 22, "JUST MARRIED", RED))
        elif k == "hearse":
            x = 480 - t * 30; car(c, x, GROUND + 18, (24, 22, 28), self.year, -1, hearse=True)
        elif k == "antenna":
            ax = 240 + 14; top = GROUND - 76; up = min(1, t / 2.5)
            c.L([(ax, top - 26), (ax, top - 26 - 26 * up)], (70, 70, 80))
            if up >= 1: [c.L([(ax - 9 + k2, top - 50 + k2 * 5), (ax + 9 - k2, top - 50 + k2 * 5)], (70, 70, 80)) for k2 in range(3)]
            if self.actors:
                from .scenes import app_of
                sp = sprite(app_of(self.snap, self.actors[0], self.seed), 0, 1); c.im.paste(sp, (ax - 26, top - 38 - sp.height + 20), sp)
        elif k == "build":
            for i in range(3):
                hx = 200 + i * 40; up = abs(math.sin(t * 5 + i)) * 4; c.R(hx, GROUND - 40 - up, hx + 3, GROUND - 34 - up, (120, 120, 126))
            if (self.e.get("text") or "").lower().find("open") >= 0:
                c.L([(166, GROUND - 20), (316, GROUND - 20)], RED, 2)
        elif k == "baby":
            pass
        elif k == "break_in":
            c.P([(200, GROUND - 62), (214, GROUND - 52), (206, GROUND - 46)], (30, 30, 50)); c.R(232, GROUND - 56, 240, GROUND, (20, 20, 30))
        elif k == "storm":
            for i in range(10):
                dx = (i * 61 + t * 160) % 520 - 20; dy = 80 + (i * 37 + t * 50) % 120
                c.R(dx, dy, dx + 6, dy + 3, (90, 70, 60)); c.L([(dx - 20, dy - 4), (dx - 6, dy)], (200, 200, 210, 120))
            if int(t * 3) % 7 == 0: c.R(0, 0, 480, 270, (255, 255, 255, 60))
        elif k == "mail":
            x = min(220, -30 + t * 80); c.E(x, y - 10, x + 12, y + 2, INK); c.E(x + 24, y - 10, x + 36, y + 2, INK); c.L([(x + 6, y - 4), (x + 18, y - 16), (x + 30, y - 4)], (60, 60, 70), 2)
            c.R(x + 12, y - 30, x + 20, y - 16, (60, 80, 140)); c.E(x + 12, y - 38, x + 20, y - 30, (230, 190, 150)); c.R(x + 22, y - 22, x + 30, y - 16, (240, 236, 220))
        elif k == "stranger":
            x = -20 + t * 40; c.R(x + 6, y - 34, x + 14, y - 10, (90, 80, 70)); c.E(x + 6, y - 42, x + 14, y - 34, (220, 180, 140)); c.R(x + 4, y - 44, x + 16, y - 42, (60, 50, 40))
            c.R(x + 6, y - 10, x + 8, y, INK); c.R(x + 12, y - 10, x + 14, y, INK); c.R(x + 16, y - 22, x + 26, y - 14, (130, 90, 60))
        elif k == "film":
            c.L([(250, y), (260, y - 30)], INK, 2); c.L([(270, y), (260, y - 30)], INK, 2); c.R(250, y - 44, 276, y - 30, (40, 40, 48)); c.E(252, y - 54, 264, y - 42, INK); c.E(262, y - 54, 274, y - 42, INK)

    def _big_overlay(self, d, t, k):
        kind = self.kind
        if kind == "tent":
            revival = "revival" in (self.e.get("text") or "").lower(); x0, y0 = 120 * k, 120 * k; w = 220 * k; h = 80 * k
            for i in range(8):
                col = (250, 248, 236) if revival or i % 2 else (214, 52, 64)
                d.polygon([(x0 + w * i / 8, y0 + h), (x0 + w / 2, y0), (x0 + w * (i + 1) / 8, y0 + h)], fill=col)
            d.rectangle([x0, y0 + h, x0 + w, y0 + h + 30 * k], fill=(250, 248, 236) if revival else (214, 52, 64)); d.rectangle([x0 + w / 2 - 14 * k, y0 + h, x0 + w / 2 + 14 * k, y0 + h + 30 * k], fill=(40, 30, 30))
            d.line([(x0 + w / 2, y0), (x0 + w / 2, y0 - 20 * k)], fill=INK, width=4); d.polygon([(x0 + w / 2, y0 - 20 * k), (x0 + w / 2 + 16 * k, y0 - 15 * k), (x0 + w / 2, y0 - 10 * k)], fill=BUTTER if int(t * 4) % 2 else RED)
            f = font(FB, 26); lab = "REVIVAL" if revival else "CIRCUS"; d.text((x0 + w / 2 - d.textlength(lab, font=f) / 2, y0 + h + 4 * k), lab, font=f, fill=INK if revival else CREAM)
        elif kind == "wreck":
            x, y = 200 * k, 220 * k; d.polygon([(x, y), (x + 50 * k, y - 18 * k), (x + 56 * k, y - 4 * k), (x + 8 * k, y + 14 * k)], fill=(150, 60, 50)); d.ellipse([x + 4 * k, y - 4 * k, x + 18 * k, y + 10 * k], fill=INK)
            for i in range(4): sy = y - 30 * k - ((t * 40 + i * 30) % 80) * k / 2; d.ellipse([x + 30 * k, sy, x + 50 * k, sy + 14 * k], fill=(160, 160, 166, 110))
        elif kind == "works":
            x = (-60 + t * 70) * k; y = 224 * k; d.rectangle([x, y - 26 * k, x + 50 * k, y], fill=(90, 110, 80)); d.rectangle([x + 50 * k, y - 18 * k, x + 68 * k, y], fill=(170, 40, 50))
            for wx in (x + 10 * k, x + 54 * k): d.ellipse([wx - 5 * k, y - 4 * k, wx + 5 * k, y + 6 * k], fill=INK)
        elif kind == "closed":
            for i in range(5):
                y = (110 + i * 18) * k; d.polygon([(40 * k, y), (300 * k, y - 10 * k), (300 * k, y - 2 * k), (40 * k, y + 8 * k)], fill=(150, 120, 80))
            f = font(FB, 44); d.rounded_rectangle([110 * k, 140 * k, 230 * k, 170 * k], 10, fill=(240, 236, 220), outline=INK, width=4)
            d.text((170 * k - d.textlength("CLOSED", font=f) / 2, 141 * k), "CLOSED", font=f, fill=RED)
