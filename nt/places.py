"""Places: Main Street storefronts, the company works, open country with the town's landmark, and lived-in rooms.
All original pixel art in the locked style (480x270 canvas, scaled up). Each returns an un-vignetted 1280x720 panel
so panels can be joined into a side-scrolling pan."""
import math, random
from PIL import Image, ImageDraw, ImageFilter
from .art import *
from .art import font as _font

GROUND = 206


def _backdrop(c, tod, weather, season, hill_shift=0, sun=True):
    sky(c, tod, weather, season, sun)
    hill = (150, 110, 140) if tod == "evening" else (40, 50, 80) if tod == "night" else (130, 165, 140)
    c.P([(0, 172)] + [(x, 152 - 10 * math.sin((x + hill_shift) / 50) - 6 * math.sin((x + hill_shift) / 17)) for x in range(0, 481, 6)] + [(480, 172)], hill)


def _road(c, season, weather):
    c.R(0, GROUND + 6, 480, GROUND + 16, (206, 198, 182) if season != "winter" else (232, 236, 242))
    for k in range(0, 480, 24): c.R(k, GROUND + 6, k + 1, GROUND + 16, (180, 172, 158))
    c.R(0, GROUND + 16, 480, GROUND + 18, (150, 144, 134)); c.R(0, GROUND + 18, 480, 270, (70, 72, 88) if weather == "clear" else (56, 58, 72))
    for k in range(0, 480, 32): c.R(k, 248, k + 16, 250, (232, 206, 110))


def _sign(c, x, y, w, text, bg, fg=CREAM):
    c.R(x, y, x + w, y + 14, INK); c.R(x + 1, y + 1, x + w - 1, y + 13, bg)
    c._labels.append((x + w / 2, y + 7, text, fg))


def _windows(c, x, y, w, h, lit, cols=2):
    gw = (w - 6 * (cols + 1)) / cols
    for i in range(cols):
        wx = x + 6 + i * (gw + 6); c.R(wx - 1, y - 1, wx + gw + 1, y + h + 1, (250, 248, 240)); c.R(wx, y, wx + gw, y + h, (255, 214, 130) if lit else (150, 190, 220))


def shopfront(c, x, kind, lit, company=None, rng=None):
    """One building on Main Street. kind: diner, store, town_hall, church, post_office, school, barber."""
    r = rng or random.Random(x)
    if kind == "diner":
        w, h = 140, 70; top = GROUND - h
        c.R(x, top, x + w, GROUND, (244, 240, 228)); c.R(x, top, x + w, top + 8, RED); c.R(x, GROUND - 10, x + w, GROUND, RED)
        _windows(c, x + 4, top + 26, w - 50, 24, True, 3); c.R(x + w - 34, top + 22, x + w - 12, GROUND, (120, 60, 50))
        for k in range(0, w, 10): c.P([(x + k, top + 10), (x + k + 10, top + 10), (x + k + 12, top + 20), (x + k + 2, top + 20)], RED if (k // 10) % 2 else (250, 250, 245))
        c.R(x + 30, top - 22, x + 110, top - 4, (40, 60, 90)); c._labels.append((x + 70, top - 13, "DINER", (255, 120, 140) if lit else CREAM))
    elif kind == "store":
        w, h = 130, 76; top = GROUND - h
        c.R(x, top, x + w, GROUND, (176, 130, 86)); c.R(x - 2, top - 14, x + w + 2, top, (150, 100, 60))
        _sign(c, x + 10, top - 12, w - 20, "GENERAL STORE", (60, 90, 60))
        _windows(c, x + 4, top + 18, w - 46, 30, lit, 2); c.R(x + w - 36, top + 16, x + w - 12, GROUND, (90, 60, 40))
        for k in range(3): c.R(x + 10 + k * 22, GROUND - 12, x + 28 + k * 22, GROUND, (150, 110, 70)); c.E(x + 12 + k * 22, GROUND - 17, x + 26 + k * 22, GROUND - 9, (220, 80, 60) if k != 1 else (240, 200, 80))
    elif kind == "town_hall":
        w, h = 150, 86; top = GROUND - h
        c.R(x, top, x + w, GROUND, (226, 220, 206)); c.P([(x - 6, top), (x + w / 2, top - 26), (x + w + 6, top)], (180, 170, 150))
        for k in range(5): cx = x + 14 + k * 30; c.R(cx, top + 6, cx + 8, GROUND, (246, 244, 236)); c.R(cx - 2, top + 4, cx + 10, top + 8, (200, 196, 186))
        c.E(x + w / 2 - 9, top - 20, x + w / 2 + 9, top - 2, (250, 250, 240)); c.L([(x + w / 2, top - 11), (x + w / 2, top - 17)], INK); c.L([(x + w / 2, top - 11), (x + w / 2 + 4, top - 11)], INK)
        c.R(x + w + 10, top - 40, x + w + 12, GROUND, (90, 90, 96)); c.R(x + w + 12, top - 40, x + w + 32, top - 28, RED); c.R(x + w + 12, top - 40, x + w + 20, top - 34, (60, 80, 150))
        c._labels.append((x + w / 2, top + 16, "TOWN HALL", INK))
    elif kind == "church":
        w, h = 110, 70; top = GROUND - h
        c.R(x, top, x + w, GROUND, (246, 244, 236)); c.P([(x - 6, top), (x + w / 2, top - 30), (x + w + 6, top)], (120, 90, 80))
        c.R(x + w / 2 - 12, top - 70, x + w / 2 + 12, top - 10, (246, 244, 236)); c.P([(x + w / 2 - 15, top - 70), (x + w / 2, top - 104), (x + w / 2 + 15, top - 70)], (120, 90, 80))
        c.R(x + w / 2 - 1, top - 116, x + w / 2 + 1, top - 100, INK); c.R(x + w / 2 - 5, top - 112, x + w / 2 + 5, top - 110, INK)
        c.P([(x + w / 2 - 12, GROUND), (x + w / 2 - 12, top + 30), (x + w / 2, top + 20), (x + w / 2 + 12, top + 30), (x + w / 2 + 12, GROUND)], (120, 70, 60))
        for wx in (x + 12, x + w - 26): c.P([(wx, top + 50), (wx, top + 22), (wx + 7, top + 14), (wx + 14, top + 22), (wx + 14, top + 50)], (255, 214, 130) if lit else (130, 160, 220))
    elif kind == "post_office":
        w, h = 110, 66; top = GROUND - h
        c.R(x, top, x + w, GROUND, (200, 120, 100)); c.R(x, top, x + w, top + 4, (160, 90, 80)); _sign(c, x + 8, top + 6, w - 16, "U.S. POST OFFICE", (40, 60, 120))
        _windows(c, x + 2, top + 26, w - 4, 22, lit, 2); c.R(x + w / 2 - 9, top + 28, x + w / 2 + 9, GROUND, (60, 50, 50))
        c.R(x + w + 6, top - 30, x + w + 8, GROUND, (90, 90, 96)); c.R(x + w + 8, top - 30, x + w + 26, top - 19, (240, 240, 240)); c.R(x + w + 8, top - 30, x + w + 15, top - 25, (60, 80, 150)); c.R(x + w + 8, top - 26, x + w + 26, top - 25, RED); c.R(x + w + 8, top - 22, x + w + 26, top - 21, RED)
    elif kind == "school":
        w, h = 140, 64; top = GROUND - h
        c.R(x, top, x + w, GROUND, (190, 70, 60)); c.P([(x - 6, top), (x + w / 2, top - 24), (x + w + 6, top)], (90, 80, 80))
        c.R(x + w / 2 - 8, top - 40, x + w / 2 + 8, top - 18, (190, 70, 60)); c.P([(x + w / 2 - 11, top - 40), (x + w / 2, top - 52), (x + w / 2 + 11, top - 40)], (90, 80, 80)); c.E(x + w / 2 - 4, top - 34, x + w / 2 + 4, top - 26, BUTTER)
        _windows(c, x + 4, top + 16, w - 8, 26, lit, 4); c._labels.append((x + w / 2, top + 8, "SCHOOL", CREAM))
    elif kind == "biz":  # a business a resident started: their own name over the door; boarded up if it closed
        name = (company or {}).get("name", "BUSINESS").upper(); closed = (company or {}).get("status") != "open"
        rr = random.Random(name); wall = rr.choice([(230, 210, 170), (200, 170, 140), (180, 200, 210), (220, 190, 200), (200, 210, 170)]); aw = rr.choice([(60, 110, 160), (160, 60, 60), (70, 130, 90), (200, 150, 60)])
        tmp = ImageDraw.Draw(Image.new("RGB", (8, 8))); w = int(max(110, min(170, tmp.textlength(name, font=_font(FB, 15)) * BW / OW + 24))); h = 68; top = GROUND - h
        if closed: wall = sh(wall, 0.75)
        c.R(x, top, x + w, GROUND, wall); c.R(x - 2, top - 4, x + w + 2, top, sh(wall, 0.8))
        _sign(c, x + 6, top + 4, w - 12, name, (60, 50, 50) if closed else INK, (190, 180, 170) if closed else BUTTER)
        if not closed:
            for k in range(0, w, 10): c.P([(x + k, top + 22), (x + k + 10, top + 22), (x + k + 12, top + 30), (x + k + 2, top + 30)], aw if (k // 10) % 2 else (250, 250, 245))
        _windows(c, x + 2, top + 32, w - 34, 24, lit and not closed, 2); c.R(x + w - 28, top + 30, x + w - 10, GROUND, (90, 60, 40))
        if closed:  # boards nailed over the windows and door, and a sign
            for bx0, bx1 in ((x + 6, x + w - 32), (x + w - 30, x + w - 8)):
                for k in range(3): c.P([(bx0, top + 34 + k * 9), (bx1, top + 30 + k * 9), (bx1, top + 34 + k * 9), (bx0, top + 38 + k * 9)], (150, 120, 80))
            c.R(x + w / 2 - 20, top + 46, x + w / 2 + 10, top + 56, (240, 236, 220)); c._labels.append((x + w / 2 - 5, top + 51, "CLOSED", RED))
    else:  # barber
        w, h = 90, 62; top = GROUND - h
        c.R(x, top, x + w, GROUND, (150, 200, 220)); _sign(c, x + 6, top + 4, w - 12, "BARBER", INK); _windows(c, x + 2, top + 24, w - 30, 26, lit, 1); c.R(x + w - 24, top + 22, x + w - 8, GROUND, (60, 70, 90))
        for k in range(6): c.R(x - 8, top + 20 + k * 6, x - 3, top + 23 + k * 6, RED if k % 2 else (250, 250, 250))
    return w


class _Canvas(C):
    def __init__(self): super().__init__(); self._labels = []


def _finish_panel(c, tod):
    img = c.im
    if tod in ("evening", "night"): img = grade(img, tod)
    big = finish(img, False); d = ImageDraw.Draw(big)
    for x, y, text, col in c._labels:
        f = _font(FB, 15); tw = d.textlength(text, font=f); d.text((x * OW / BW - tw / 2, y * OH / BH - 10), text, font=f, fill=col, stroke_width=2, stroke_fill=INK)
    return big


def _walkers(c, snap, seed, walkers, t=0.0):
    from .scenes import app_of
    for pid, x0, speed, facing in walkers:
        a = app_of(snap, pid, seed); x = (x0 + speed * t) % 520 - 20; sp = sprite(a, 0, facing)
        c.d.ellipse([x + 2, GROUND + 15, x + 24, GROUND + 18], fill=(30, 20, 50, 80)); c.im.paste(sp, (int(x), GROUND + 16 - sp.height), sp)


def resident_businesses(snap):
    """Businesses the residents started themselves (everything but the town's original company), oldest first."""
    return [("biz", c) for cid, c in sorted(snap.get("companies", {}).items(), key=lambda kv: int(kv[0][2:]) if kv[0][2:].isdigit() else 0) if cid != "co1"]


def main_street_panel(snap, seed, kinds, tod, weather, season, walkers=(), shift=0, sun=True):
    c = _Canvas(); _backdrop(c, tod, weather, season, shift, sun); lit = tod in ("evening", "night")
    c.R(0, GROUND, 480, GROUND + 6, (190, 182, 168))
    x = 14; r = random.Random(seed + shift)
    for k in kinds:
        kind, co = (k[0], k[1]) if isinstance(k, (tuple, list)) else (k, None)
        if x > 470: break
        w = shopfront(c, x, kind, lit, company=co, rng=r); x += w + (34 if kind in ("town_hall", "post_office", "barber") else 18)
    c.R(0, GROUND + 3, 480, GROUND + 6, (150, 144, 134)); _road(c, season, weather)
    for lx in (8, 240, 470): c.R(lx, 116, lx + 3, GROUND + 12, (40, 40, 48)); c.P([(lx - 6, 116), (lx + 9, 116), (lx + 6, 108), (lx - 3, 108)], (255, 226, 150) if lit else (210, 210, 200))
    _walkers(c, snap, seed, walkers)
    return _finish_panel(c, tod)


def works_panel(snap, seed, gen, tod, weather, season, walkers=()):
    """The company: a works building fitting its industry, with the company's real name on it."""
    c = _Canvas(); _backdrop(c, tod, weather, season, 90); lit = tod in ("evening", "night"); ind = gen["company"]["industry"].lower()
    c.R(0, GROUND - 2, 480, GROUND + 6, (150, 140, 120))
    if "oil" in ind:
        for bx in (70, 250):
            c.L([(bx, GROUND), (bx + 30, GROUND - 120)], (80, 70, 70), 3); c.L([(bx + 60, GROUND), (bx + 30, GROUND - 120)], (80, 70, 70), 3)
            for k in range(1, 6): y = GROUND - k * 20; dx = (GROUND - y) * 30 / 120; c.L([(bx + dx, y), (bx + 60 - dx, y)], (80, 70, 70), 2); c.L([(bx + dx, y), (bx + 60 - (GROUND - y + 20) * 30 / 120, y - 20)], (80, 70, 70), 1)
        c.R(330, GROUND - 40, 450, GROUND, (170, 160, 150)); _windows(c, 334, GROUND - 32, 112, 14, lit, 3)
        c._labels.append((390, GROUND - 50, gen["company"]["name"].upper(), CREAM))
    else:
        c.R(40, GROUND - 90, 300, GROUND, (150, 120, 100)); c.P([(34, GROUND - 90), (170, GROUND - 120), (306, GROUND - 90)], (110, 90, 80))
        for k in range(5): _windows(c, 48 + k * 50, GROUND - 74, 40, 20, lit, 1)
        c.R(130, GROUND - 40, 210, GROUND, (90, 70, 60))
        c.R(330, GROUND - 150, 350, GROUND - 60, (160, 70, 60)); c.R(326, GROUND - 154, 354, GROUND - 146, (140, 60, 50))
        for k in range(4): c.E(330 + k * 8, GROUND - 175 - k * 12, 356 + k * 10, GROUND - 158 - k * 12, (220, 220, 225) if tod != "night" else (120, 120, 140))
        if any(w in ind for w in ("mill", "grain", "elevator")): c.R(380, GROUND - 130, 440, GROUND, (200, 196, 180)); c.R(374, GROUND - 136, 446, GROUND - 128, (170, 160, 150))
        c.R(40, GROUND - 106, 300, GROUND - 92, INK); c.R(42, GROUND - 104, 298, GROUND - 94, (240, 230, 200))
        c._labels.append((170, GROUND - 99, gen["company"]["name"].upper(), INK))
    for k in range(0, 480, 6): c.R(k, GROUND - 14, k + 1, GROUND + 2, (110, 110, 116))
    c.R(0, GROUND - 14, 480, GROUND - 13, (110, 110, 116)); c.R(0, GROUND - 6, 480, GROUND - 5, (110, 110, 116))
    _road(c, season, weather); _walkers(c, snap, seed, walkers)
    return _finish_panel(c, tod)


def country_panel(snap, seed, gen, tod, weather, season, landmark="", walkers=(), sun=True):
    """Open country: fields or shore by geography, a fence line, the town's landmark on the horizon."""
    c = _Canvas(); sky(c, tod, weather, season, sun); geo = gen["geography"]; dark = tod in ("evening", "night")
    field = {"desert": (214, 184, 130), "swamp": (90, 120, 80)}.get(geo, {"winter": (230, 234, 240), "autumn": (200, 160, 80), "spring": (130, 180, 90)}.get(season, (170, 180, 80)))
    if dark: field = sh(field, 0.6)
    water = geo in ("coast", "island", "lakeside")
    c.R(0, 150, 480, 270, field)
    if water: c.R(0, 150, 480, 176, sh((70, 120, 180), 0.6 if dark else 1.0)); [c.R(k, 160 + (k % 3) * 4, k + 10, 161 + (k % 3) * 4, (200, 220, 240)) for k in range(0, 480, 37)]
    else:
        for y in range(176, 270, 7): c.R(0, y, 480, y + 2, sh(field, 0.9))
    lm = (landmark or "").lower(); hx = 360
    if any(k in lm for k in ("elevator", "silo")): c.R(hx, 92, hx + 40, 176, (200, 196, 180)); c.R(hx - 4, 86, hx + 44, 94, (170, 160, 150)); c.R(hx + 44, 120, hx + 70, 176, (190, 186, 170))
    elif "lighthouse" in lm: c.P([(hx, 176), (hx + 8, 90), (hx + 22, 90), (hx + 30, 176)], (246, 244, 236)); [c.R(hx + 4, 110 + k * 22, hx + 26, 118 + k * 22, RED) for k in range(3)]; c.R(hx + 6, 80, hx + 24, 90, (255, 226, 150))
    elif "tower" in lm or "water" in lm: c.L([(hx + 6, 176), (hx + 12, 120)], (98, 106, 124), 2); c.L([(hx + 40, 176), (hx + 34, 120)], (98, 106, 124), 2); c.R(hx, 96, hx + 46, 122, (152, 162, 178)); c.P([(hx - 2, 96), (hx + 23, 84), (hx + 48, 96)], (118, 128, 144))
    elif "mesa" in lm: c.P([(300, 176), (330, 110), (440, 110), (470, 176)], (180, 110, 80))
    elif any(k in lm for k in ("mine", "trestle")): c.R(hx, 140, hx + 60, 176, (120, 90, 70)); c.E(hx + 18, 150, hx + 42, 176, INK)
    else:  # trees on the horizon
        for tx in range(250, 480, 26): c.E(tx, 128, tx + 24, 162, sh((70, 120, 70), 0.7 if dark else 1.0))
    for k in range(0, 480, 30): c.R(k, 196, k + 3, 226, (140, 110, 80))
    c.R(0, 202, 480, 204, (140, 110, 80)); c.R(0, 214, 480, 216, (140, 110, 80))
    c.R(0, 236, 480, 270, (170, 150, 110)); _walkers(c, snap, seed, walkers)
    return _finish_panel(c, tod)


# ---------------------------------------------------------------- lived-in rooms
def furnish_home(c, snap, seed, hid, tod, room):
    """Paint the room around the people. room: 'kitchen' or 'parlor'. Details vary by household (seeded) and by what they can afford."""
    h = snap["households"].get(str(hid), {}); wealth = h.get("savings", 300); has_tv = h.get("has_tv", False)
    r = random.Random(seed * 31 + int(hid or 0) * 7 + (1 if room == "kitchen" else 0))
    wall = r.choice([(226, 206, 170), (200, 220, 210), (230, 200, 200), (210, 205, 230), (236, 226, 190), (200, 214, 230)])
    if wealth < 150: wall = sh(wall, 0.9)
    c.R(0, 0, BW, 180, wall)
    pat = r.choice(["diamond", "stripe", "dots"])
    for x in range(0, BW, 16):
        for y in range(8, 170, 18):
            if pat == "diamond": c.P([(x + 8, y), (x + 12, y + 5), (x + 8, y + 10), (x + 4, y + 5)], sh(wall, 0.93))
            elif pat == "stripe": c.R(x, 0, x + 3, 180, sh(wall, 0.95))
            else: c.E(x + 6, y + 4, x + 9, y + 7, sh(wall, 0.9))
    floor = (176, 124, 82) if room == "parlor" else (220, 210, 190)
    c.R(0, 170, BW, 180, (150, 110, 80))
    for y in range(180, BH, 5):
        if room == "kitchen":
            for x in range(0, BW, 12): c.R(x, y, x + 12, y + 5, (230, 226, 214) if ((x // 12) + (y // 5)) % 2 else (190, 70, 70) if r.random() < 0.0 else (60, 60, 70))
        else: c.R(0, y, BW, y + 2, floor if (y // 5) % 2 else sh(floor, 0.9))
    night = tod in ("evening", "night")
    # window (always), curtains vary
    cur = r.choice([RED, (90, 130, 90), (230, 200, 120), (120, 100, 160)])
    c.R(176, 26, 284, 106, (250, 248, 240)); c.R(180, 30, 280, 102, (30, 36, 80) if night else (150, 200, 240)); c.R(229, 30, 231, 102, (250, 248, 240)); c.R(180, 65, 280, 67, (250, 248, 240))
    c.R(164, 20, 178, 112, cur); c.R(282, 20, 296, 112, cur)
    if room == "kitchen":
        # counter + cabinets, stove, icebox, table with chairs, wall clock, calendar
        c.R(20, 110, 150, 176, (240, 236, 224)); c.R(20, 106, 150, 112, (200, 70, 70) if r.random() < 0.5 else (90, 150, 140))
        for k in range(3): c.R(26 + k * 42, 120, 60 + k * 42, 168, sh((240, 236, 224), 0.92)); c.R(40 + k * 42, 140, 46 + k * 42, 142, INK)
        c.R(20, 30, 150, 70, (240, 236, 224)); [c.R(24 + k * 42, 34, 60 + k * 42, 66, sh((240, 236, 224), 0.94)) for k in range(3)]
        c.R(330, 104, 380, 176, (250, 250, 250)); c.R(332, 106, 378, 116, (40, 40, 48)); [c.E(336 + k * 11, 108, 344 + k * 11, 114, (90, 90, 96)) for k in range(4)]
        c.R(400, 70, 450, 176, (236, 236, 228) if wealth > 400 else (190, 160, 110)); c.R(444, 100, 446, 120, (150, 150, 150)); c.R(402, 112, 448, 114, sh((236, 236, 228), 0.85))
        c.E(310, 30, 330, 50, (250, 250, 240)); c.L([(320, 40), (320, 33)], INK); c.L([(320, 40), (325, 40)], INK)
        c.R(110, 40, 140, 64, (250, 250, 250)); c.R(110, 40, 140, 46, RED)
        c.R(190, 150, 290, 158, (150, 100, 60)); c.R(196, 158, 200, 196, (120, 80, 50)); c.R(280, 158, 284, 196, (120, 80, 50))
        c.E(222, 140, 238, 152, (250, 250, 250)); c.R(250, 142, 258, 152, (240, 220, 200))
    else:
        rug = r.choice([(150, 60, 60), (60, 90, 120), (110, 120, 70)]); c.E(60, 186, 420, 230, sh(rug, 0.9)); c.E(76, 190, 404, 226, rug)
        for k in range(r.randint(2, 4)):  # framed photos and a picture
            px = 30 + k * 34; c.R(px, 40 + (k % 2) * 8, px + 22, 68 + (k % 2) * 8, (110, 74, 44)); c.R(px + 3, 43 + (k % 2) * 8, px + 19, 65 + (k % 2) * 8, (200, 190, 170) if k else (150, 190, 170))
        c.E(330, 26, 350, 46, (250, 250, 240)); c.L([(340, 36), (340, 29)], INK); c.L([(340, 36), (345, 36)], INK)
        c.P([(30, 104), (56, 104), (62, 128), (24, 128)], BUTTER); c.R(42, 128, 45, 180, (80, 60, 40))
        sofa = (64, 160, 160) if wealth > 300 else (140, 120, 100)
        c.R(70, 136, 220, 186, sofa); c.R(76, 146, 214, 172, sh(sofa, 0.85)); c.R(66, 130, 78, 186, sh(sofa, 0.8)); c.R(212, 130, 224, 186, sh(sofa, 0.8))
        if has_tv: c.R(380, 120, 440, 186, (110, 70, 40)); c.R(386, 126, 434, 160, (60, 70, 70)); c.R(390, 130, 430, 156, (140, 170, 170) if not night else (170, 210, 220)); c.L([(400, 120), (392, 104)], INK); c.L([(420, 120), (428, 104)], INK)
        else: c.R(390, 136, 430, 186, (120, 80, 50)); c.R(394, 140, 426, 160, (90, 60, 40)); c.E(402, 144, 418, 156, (60, 40, 30))  # radio cabinet
        c.R(450, 60, 476, 186, (110, 74, 44)); [c.R(452, 66 + k * 24, 474, 70 + k * 24, (130, 90, 56)) for k in range(5)]
        for k in range(4): c.R(453 + k * 5, 52 + (k % 2) * 4 - 0, 457 + k * 5, 66, [RED, TEAL, BUTTER, (90, 90, 140)][k])
        if r.random() < 0.6: c.R(296, 160, 312, 186, (180, 110, 70)); c.E(290, 140, 318, 166, (80, 140, 80))  # houseplant


def furnish_place(c, place_kind, tod):
    """Rooms in town: the diner, the store, the town hall, the company office."""
    if place_kind == "store":
        c.R(0, 0, BW, 180, (220, 200, 160)); c.R(0, 170, BW, BH, (170, 120, 80))
        for y in (30, 70, 110):
            c.R(20, y + 26, 460, y + 30, (130, 90, 56))
            for x in range(26, 456, 14): c.R(x, y, x + 10, y + 26, [RED, (240, 200, 80), (90, 140, 90), (200, 200, 210), (150, 100, 60)][(x * 7 + y) % 5])
        c.R(120, 150, 360, 196, (130, 90, 56)); c.R(120, 146, 360, 152, (160, 110, 70)); c.R(300, 130, 340, 150, (60, 60, 70)); c.R(304, 134, 336, 144, (150, 200, 150))
    elif place_kind == "company":
        c.R(0, 0, BW, 180, (190, 190, 196)); c.R(0, 170, BW, BH, (120, 120, 126))
        c.R(30, 40, 150, 120, (240, 240, 230)); c.R(34, 44, 146, 116, (250, 250, 245)); [c.L([(40, 54 + k * 10), (138, 54 + k * 10)], (180, 180, 200)) for k in range(6)]
        c.R(380, 80, 440, 176, (110, 110, 120)); [c.R(384, 86 + k * 30, 436, 110 + k * 30, (130, 130, 140)) for k in range(3)]
        c.R(150, 140, 330, 150, (110, 74, 44)); c.R(160, 150, 166, 196, (90, 60, 40)); c.R(314, 150, 320, 196, (90, 60, 40)); c.R(200, 126, 236, 140, (40, 40, 48))
        c.R(176, 26, 284, 106, (250, 248, 240)); c.R(180, 30, 280, 102, (150, 200, 240) if tod not in ("evening", "night") else (30, 36, 80))
    else: return False
    return True
