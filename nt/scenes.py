"""Scene renderers (each returns a 1280x720 RGB frame). Locked style."""
import math, random
from PIL import Image, ImageDraw, ImageFilter
from .art import *


def app_of(snap, pid, seed):
    p = snap["people"][str(pid)]; q = dict(p); q["id"] = int(pid); return appearance(q, seed)


def hh_colors(hid, seed):
    r = random.Random(seed * 13 + int(hid)); return r.choice(WALLS), r.choice(ROOFS)


def house_state(snap, hid, seed):
    """What the camera sees at a household on this day: condition, burned out, TV antenna, and the family car (dressing, by wealth)."""
    h = snap["households"].get(str(hid), {}); pl = snap.get("places", {}).get(h.get("place") or f"home_{hid}", {})
    r = random.Random(seed * 17 + int(hid)); has_car = r.random() < min(0.9, 0.35 + max(0, h.get("savings", 0)) / 2000)
    car_col = r.choice(CARS) if has_car else None; year = int(snap["date"][:4])
    age = r.choice([0, 1, 2, 3, 4, 5, 6, 8, 10, 13]) if h.get("savings", 0) > 1500 else r.choice([3, 5, 6, 8, 10, 12, 14, 16])  # richer families drive newer cars
    if "car_year" in h:  # since Nov 18 the town tracks real cars: the family's own car, or none
        has_car = bool(h["car_year"]); car_col = car_col or (r.choice(CARS) if has_car else None); car_col = car_col if has_car else None
        age = year - (h["car_year"] or year)
    return {"cond": h.get("condition", 1.0), "burned": bool(pl.get("burned")) or bool(h.get("homeless")), "tv": bool(h.get("has_tv")) and not h.get("homeless"),
            "car": car_col, "year": year, "car_year": year - age}


def wrap(d, text, f, width):
    words, rows, cur = text.split(), [], ""
    for w_ in words:
        if d.textlength((cur + " " + w_).strip(), font=f) > width: rows.append(cur); cur = w_
        else: cur = (cur + " " + w_).strip()
    if cur: rows.append(cur)
    return rows


# ---------------------------------------------------------------- street
def street(snap, seed, hids, walkers, tod="midday", weather="clear", season="summer", t=0.0, bubble=None, storefront=None, vignette_on=True, wx_t=None, precip_on=True, sun=True):
    """hids: up to 3 household ids for the house fronts; walkers: list of (pid, x0, speed, facing); bubble: (pid, text)."""
    c = C(); sky(c, tod, weather, season, sun)
    hill = (150, 110, 140) if tod == "evening" else (40, 50, 80) if tod == "night" else (130, 165, 140)
    c.P([(0, 170)] + [(x, 150 - 10 * math.sin(x / 50) - 6 * math.sin(x / 17)) for x in range(0, 481, 6)] + [(480, 170)], hill)
    for tx in range(-10, 500, 34):
        tc = {"autumn": (200, 110, 50), "winter": (90, 100, 110), "spring": (110, 160, 100)}.get(season, (86, 120, 92)); ty = 150 + (tx * 7) % 6
        if tod == "night": tc = sh(tc, 0.5)
        c.E(tx - 16, ty - 34, tx + 16, ty, sh(tc, 0.85)); c.E(tx - 12, ty - 38, tx + 8, ty - 14, tc); c.E(tx - 8, ty - 36, tx + 2, ty - 26, sh(tc, 1.15))
    ground = 206; lit = tod in ("evening", "night")
    xs = [18, 176, 352] if not storefront else [18, 352]
    states = []
    for i, hid in enumerate(hids[:len(xs)]):
        wall, roof = hh_colors(hid, seed); st = house_state(snap, hid, seed); states.append((xs[i], st))
        house_front(c, xs[i], 116, 70, sh(wall, 0.6) if tod == "night" else wall, sh(roof, 0.6) if tod == "night" else roof, ground, lit and not st["burned"], st["cond"], burned=st["burned"], tv=st["tv"])
    if storefront:
        dx0, dw = 170, 150; dtop = ground - 84; col = {"diner": RED, "store": (150, 100, 60), "company": (120, 120, 130), "town_hall": (180, 170, 150)}.get(storefront, RED)
        c.R(dx0, dtop, dx0 + dw, ground, (240, 236, 224)); c.R(dx0, dtop, dx0 + dw, dtop + 6, col)
        c.R(dx0 + 10, dtop + 30, dx0 + dw - 10, dtop + 62, (255, 214, 140) if lit or storefront == "diner" else (170, 200, 220))
        for k in range(0, dw, 10): c.P([(dx0 + k, dtop + 18), (dx0 + k + 10, dtop + 18), (dx0 + k + 12, dtop + 30), (dx0 + k + 2, dtop + 30)], col if (k // 10) % 2 else (250, 250, 245))
        for k in range(dx0, dx0 + dw, 4): c.R(k, dtop + 64, k + 2, ground, col if (k // 4) % 2 else (250, 250, 245))
        c.R(dx0 + 30, dtop - 22, dx0 + dw - 30, dtop - 2, (40, 60, 90)); c.R(dx0 + 32, dtop - 20, dx0 + dw - 32, dtop - 4, TEAL)
    c.R(0, ground + 6, 480, ground + 16, (206, 198, 182) if season != "winter" else (232, 236, 242))
    for k in range(0, 480, 24): c.R(k, ground + 6, k + 1, ground + 16, (180, 172, 158))
    c.R(0, ground + 16, 480, ground + 18, (150, 144, 134)); c.R(0, ground + 18, 480, 270, (70, 72, 88) if weather == "clear" else (56, 58, 72))
    r = random.Random(1)
    for _ in range(400): x, y = r.randrange(480), r.randrange(ground + 19, 270); c.R(x, y, x + 1, y + 1, (78, 80, 96))
    for k in range(0, 480, 32): c.R(k, 248, k + 16, 250, (232, 206, 110))
    if season == "winter":
        for hx in xs: c.R(hx - 12, ground - 1, hx + 128, ground + 3, (240, 244, 250))
    c.R(150, 120, 153, ground + 12, (40, 40, 48)); c.P([(144, 120), (159, 120), (156, 112), (147, 112)], (255, 226, 150) if lit else (210, 210, 200))
    pos = {}
    for pid, x0, speed, facing in walkers:
        a = app_of(snap, pid, seed); x = (x0 + speed * t) % 520 - 20
        sp = sprite(a, int(t * 6) % 4 if speed else 0, facing)
        c.d.ellipse([x + 2, ground + 15, x + 24, ground + 18], fill=(30, 20, 50, 80))
        c.im.paste(sp, (int(x), ground + 16 - sp.height), sp); pos[pid] = (x + 11, ground + 16 - sp.height)
    for i, (hx, st) in enumerate(states):  # the family car, parked at the curb out front: in the road, so drawn in front of people on the sidewalk
        if st["car"] and not st["burned"]: car(c, hx + 12, ground + 18, st["car"], st["year"], 1 if i % 2 == 0 else -1, model_year=st["car_year"], night=tod == "night")
    img = c.im
    if lit: img = grade(img, tod)
    big = finish(img, vignette_on)
    if precip_on and weather in ("rain", "storm", "snow"): precip(big, weather, t if wx_t is None else wx_t)
    if bubble and bubble[0] in pos: speech_bubble(big, pos[bubble[0]], bubble[1])
    return big


def precip(big, weather, t):
    d = ImageDraw.Draw(big, "RGBA"); W = big.width
    for k in range(200 * W // OW):
        x = (k * 97 + t * (900 if weather != "snow" else 60)) % W; y = (k * 61 + t * (1400 if weather != "snow" else 120)) % OH
        if weather == "snow": d.ellipse([x, y, x + 5, y + 5], fill=(255, 255, 255, 200))
        else: d.line([(x, y), (x - 6, y + 22)], fill=(200, 210, 230, 110), width=2)


LEAD_W = 380  # width of the edge-of-town stretch before the street, when the welcome sign is shown


class StreetPan:
    """Side-scrolling pan down the street: a strip of house fronts the camera glides along (the scene transition).
    The strip is rendered once; each frame is a moving 1280-wide window, then vignetted."""
    def __init__(self, snap, seed, hids, tod, weather, season, walkers=(), storefront=None, setting="home", gen=None, place=None, sign_pop=None, town=None):
        """setting: home (the family's street), main (Main Street), works (the company), country (open land + landmark)."""
        from . import places
        hids = list(hids) or sorted(snap["households"], key=int)[:3]
        a = hids[:3]; b = (hids[3:6] or hids[:3])
        if setting == "main":
            first = ["school", "church", "barber"] if place == "school" else ["town_hall", "church", "barber"] if place == "town_hall" else ["diner", "store", "post_office"]
            second = ["diner", "store", "post_office"] if first[0] != "diner" else ["town_hall", "church", "barber"]
            biz = places.resident_businesses(snap)
            if biz: second = (biz[-3:] + second)[:3]  # Main Street grows: the residents' own businesses take their places along it
            left = places.main_street_panel(snap, seed, first, tod, weather, season, list(walkers), 0); right = places.main_street_panel(snap, seed, second, tod, weather, season, (), 240, sun=False)
        elif setting == "works" and gen:
            left = places.works_panel(snap, seed, gen, tod, weather, season, list(walkers)); right = places.main_street_panel(snap, seed, ["store", "post_office", "barber"], tod, weather, season, (), 120, sun=False)
        elif setting == "country" and gen:
            lms = gen.get("landmarks", []); lm = (place or "").replace("lm_", "").replace("_", " ")
            left = places.country_panel(snap, seed, gen, tod, weather, season, lm, list(walkers)); right = places.country_panel(snap, seed, gen, tod, weather, season, next((x for x in lms if x != lm), ""), (), sun=False)
        else:
            left = street(snap, seed, a, list(walkers), tod, weather, season, 0.0, storefront=storefront, vignette_on=False, precip_on=False)
            right = street(snap, seed, b, [], tod, weather, season, 0.0, vignette_on=False, precip_on=False, sun=False)
        lead = None
        if sign_pop is not None:  # the edge of town: open roadside with the welcome sign showing the town's real population (set dressing; residents never see it)
            from .brandkit import sign
            lead = street(snap, seed, [], [], tod, weather, season, 0.0, vignette_on=False, precip_on=False, sun=False).crop((0, 0, LEAD_W, OH))
            sg = sign(240, sign_pop, town, glow=tod in ("evening", "night"))
            lead.paste(sg, ((LEAD_W - sg.width) // 2 + 20, int(206 * OH / 270) + 12 - sg.height), sg)
        lw = LEAD_W if lead else 0
        self.strip = Image.new("RGB", (OW * 2 + lw, OH))
        if lead: self.strip.paste(lead, (0, 0))
        self.strip.paste(left, (lw, 0)); self.strip.paste(right, (OW + lw, 0)); self.travel = OW + lw
        self.weather = weather  # rain/snow is drawn live over the moving window

    def frame(self, u, t=0.0):
        """u in 0..1: how far along the pan; eased."""
        e = u * u * (3 - 2 * u); x = int(e * self.travel)
        im = self.strip.crop((x, 0, x + OW, OH))
        if self.weather in ("rain", "storm", "snow"): precip(im, self.weather, t)
        return vignette(im)


def speech_bubble(big, anchor, text):
    d = ImageDraw.Draw(big); f = font(FB, 22); ax, ay = anchor[0] * OW / BW, anchor[1] * OH / BH
    rows = wrap(d, text, f, 520); tw = max(d.textlength(r_, font=f) for r_ in rows); h = 14 + 32 * len(rows)
    bx = min(max(20, ax - tw / 2 - 16), OW - tw - 52); by = max(20, ay - h - 40)
    d.rounded_rectangle([bx, by, bx + tw + 32, by + h], 14, fill=(255, 252, 240), outline=INK, width=3)
    d.polygon([(ax - 9, by + h - 1), (ax + 9, by + h - 1), (ax, by + h + 22)], fill=(255, 252, 240), outline=INK); d.rectangle([ax - 8, by + h - 4, ax + 8, by + h], fill=(255, 252, 240))
    for k, r_ in enumerate(rows): d.text((bx + 16, by + 8 + 32 * k), r_, font=f, fill=INK)


# ---------------------------------------------------------------- isometric overview
def overview(snap, seed, gen, tod="midday", season="summer", weather="clear", t=0.0, highlight=None):
    c = C(); TW, TH = 24, 12; OX, OY = 240, 46
    iso = lambda gx, gy, z=0: (OX + (gx - gy) * TW / 2, OY + (gx + gy) * TH / 2 - z)
    base_bg = {"night": (16, 20, 48), "evening": (60, 50, 96)}.get(tod, (110, 160, 210))
    for y in range(BH): c.d.line([(0, y), (BW, y)], fill=mix(base_bg, sh(base_bg, 1.3), y / BH))
    N = 14; dark = tod in ("night", "evening")
    gcol = {"winter": (225, 230, 238), "autumn": (150, 140, 70), "spring": (110, 170, 90)}.get(season, (88, 146, 80))
    if gen["geography"] == "desert": gcol = (210, 180, 130)
    water = gen["geography"] in ("island", "coast", "lakeside")
    for gx in range(N):
        for gy in range(N):
            road = gy == 6 or gx == 7
            edge = water and (gx == 0 or gy == N - 1 or (gen["geography"] == "island" and (gx == N - 1 or gy == 0)))
            col = (60, 110, 170) if edge else (72, 74, 88) if road else (gcol if (gx + gy) % 2 else sh(gcol, 0.94))
            if dark: col = sh(col, 0.6)
            c.P([iso(gx, gy), iso(gx + 1, gy), iso(gx + 1, gy + 1), iso(gx, gy + 1)], col)
    def box(gx, gy, w, dp, h, col, roof=None, lit=False):
        a, b, cc, e = iso(gx, gy), iso(gx + w, gy), iso(gx + w, gy + dp), iso(gx, gy + dp)
        if dark: col = sh(col, 0.7); roof = sh(roof, 0.7) if roof else None
        c.P([e, cc, (cc[0], cc[1] - h), (e[0], e[1] - h)], sh(col, 0.82)); c.P([cc, b, (b[0], b[1] - h), (cc[0], cc[1] - h)], sh(col, 0.66))
        for (p, q), k in (((e, cc), 0), ((cc, b), 1)):
            n = max(1, int(math.dist(p, q) // 12))
            for j in range(n):
                u = (j + 0.5) / n; x = p[0] + (q[0] - p[0]) * u; y = p[1] + (q[1] - p[1]) * u - h * 0.55
                c.R(x - 2, y - 2, x + 2, y + 3, (255, 214, 120) if lit and (j + gx) % 3 else (110, 140, 180))
        top = [(a[0], a[1] - h), (b[0], b[1] - h), (cc[0], cc[1] - h), (e[0], e[1] - h)]
        if roof is None: c.P(top, col)
        else:
            m1 = ((a[0] + e[0]) / 2, (a[1] + e[1]) / 2 - h - 8); m2 = ((b[0] + cc[0]) / 2, (b[1] + cc[1]) / 2 - h - 8)
            c.P([top[3], top[2], m2, m1], sh(roof, 0.95)); c.P([top[0], top[1], m2, m1], sh(roof, 0.75)); c.P([top[2], top[1], m2], sh(col, 0.6))
    spots = [(1, 2), (4, 2), (9, 2), (11, 3), (1, 8), (4, 9), (9, 9), (11, 10), (2, 11), (5, 12), (8, 12), (12, 12)]
    items = []
    hids = sorted(snap["households"], key=int)
    for i, hid in enumerate(hids[:len(spots)]):
        gx, gy = spots[i]; wall, roof = hh_colors(hid, seed); st = house_state(snap, hid, seed)
        items.append((gx + gy, ("house", gx, gy, wall, roof, st["cond"], st["burned"], st["tv"])))
    from .places import resident_businesses
    for (gx, gy), (_, co) in zip([(5, 4), (2, 7), (4, 7), (12, 4)], resident_businesses(snap)):  # the residents' own businesses
        rr = random.Random(co["name"]); col = rr.choice([(230, 210, 170), (180, 200, 210), (220, 190, 200), (200, 210, 170)])
        items.append((gx + gy, ("b", gx, gy, 1, 1, 9, col if co["status"] == "open" else (120, 116, 112), rr.choice([(160, 60, 60), (60, 110, 160), (70, 130, 90)]) if co["status"] == "open" else (90, 86, 84))))
    items += [(13, ("b", 8, 4, 2, 2, 12, CREAM, None)), (14, ("co", 10, 7, 3, 2, 16, (150, 150, 158), None)), (5, ("b", 0, 5, 2, 1, 10, (176, 130, 86), (120, 80, 60)))]
    for k, (gx, gy) in enumerate([(3, 3), (6, 1), (13, 5), (3, 10), (7, 13), (13, 8), (0, 0), (13, 1)]): items.append((gx + gy, ("tree", gx, gy)))
    for _, it in sorted(items, key=lambda z: z[0]):
        if it[0] == "house":
            _, gx, gy, wall, roof, cond, burned, tv = it
            if burned: box(gx, gy, 2, 2, 3, (44, 36, 36)); p_ = iso(gx + 1.6, gy + 0.4, 3); c.R(p_[0], p_[1] - 12, p_[0] + 3, p_[1], (120, 64, 56)); continue
            box(gx, gy, 2, 2, 12, wall if cond > 0.5 else sh(wall, 0.7), roof, dark and cond > 0.5)
            if tv: p_ = iso(gx + 1, gy + 1, 26); c.L([(p_[0], p_[1]), (p_[0], p_[1] - 8)], (60, 60, 70)); c.L([(p_[0] - 3, p_[1] - 7), (p_[0] + 3, p_[1] - 7)], (60, 60, 70))
        elif it[0] in ("b", "co"):
            _, gx, gy, w, dp, h, col, roof = it; box(gx, gy, w, dp, h, col, roof, dark)
            if it[0] == "co": s = iso(gx + w - 0.5, gy + 0.5, h); c.R(s[0] - 2, s[1] - 26, s[0] + 3, s[1], (160, 70, 60))
        else:
            _, gx, gy = it; p = iso(gx + 0.5, gy + 0.5); tc = {"autumn": (200, 110, 50), "winter": (110, 120, 120)}.get(season, (56, 120, 64))
            c.R(p[0], p[1] - 6, p[0] + 2, p[1], (80, 56, 40)); c.E(p[0] - 7, p[1] - 20, p[0] + 9, p[1] - 4, sh(tc, 0.7) if dark else tc)
    img = finish(c.im)
    d = ImageDraw.Draw(img)
    # labels sit just above each building's own roofline (STORE label moved off the neighbouring house)
    for (gx, gy, z), lab in (((9, 5, 18), "DINER"), ((11.5, 8, 26), gen["company"]["name"].upper()), ((1, 5.5, 14), "STORE")):
        x, y = iso(gx, gy, z); f = font(FB, 16); tw = d.textlength(lab, font=f)
        d.text((x * OW / BW - tw / 2, y * OH / BH - 30), lab, font=f, fill=CREAM, stroke_width=2, stroke_fill=INK)
    return img


# ---------------------------------------------------------------- interior cut-in
def interior(snap, seed, place_kind, hid, speakers, line, tod="evening", zoom=None, thought=None, intro=None):
    """speakers: [pid_left, pid_right]; line: (pid, text, expr). zoom: pid for a close-up; thought: (pid, text) shows a thought bubble instead of the line; intro: (name, sub, line) name card."""
    c = C(); r = random.Random(seed * 7 + int(hid or 0))
    wealth = snap["households"][str(hid)]["savings"] if hid and str(hid) in snap["households"] else 500
    from . import places
    if place_kind == "home": places.furnish_home(c, snap, seed, hid, tod, "kitchen" if tod in ("morning", "evening") else "parlor"); built = True
    else: built = places.furnish_place(c, place_kind, tod)
    if not built: _old_room(c, r, place_kind, wealth, tod)
    night = tod in ("evening", "night")
    _people_and_finish = None
    return _interior_finish(c, snap, seed, place_kind, hid, speakers, line, tod, zoom, thought, intro)


def _old_room(c, r, place_kind, wealth, tod):
    wallc = r.choice([(226, 206, 170), (200, 220, 210), (230, 200, 200), (210, 205, 230)]) if place_kind == "home" else {"diner": (240, 236, 224), "town_hall": (210, 200, 180), "company": (190, 190, 196), "store": (220, 200, 160)}.get(place_kind, (220, 210, 190))
    c.R(0, 0, BW, 180, wallc)
    for x in range(0, BW, 16):
        for y in range(8, 170, 18): c.P([(x + 8, y), (x + 12, y + 5), (x + 8, y + 10), (x + 4, y + 5)], sh(wallc, 0.93))
    c.R(0, 170, BW, 180, (150, 110, 80))
    for y in range(180, BH, 5): c.R(0, y, BW, y + 2, (176, 124, 82) if (y // 5) % 2 else (160, 112, 74))
    night = tod in ("evening", "night")
    c.R(170, 30, 280, 110, (250, 248, 240)); c.R(174, 34, 276, 106, (30, 36, 80) if night else (150, 200, 240))
    c.R(224, 34, 226, 106, (250, 248, 240)); c.R(174, 68, 276, 70, (250, 248, 240)); c.R(158, 24, 172, 116, RED); c.R(278, 24, 292, 116, RED)
    if place_kind == "home":
        c.R(60, 40, 110, 76, (120, 80, 50)); c.R(64, 44, 106, 72, (150, 190, 170)); c.P([(66, 70), (84, 52), (104, 70)], (90, 130, 100))
        c.R(360, 64, 380, 104, (50, 40, 40)); c.R(364, 68, 376, 84, (80, 70, 70)); c.E(363, 88, 377, 100, (30, 30, 30))
        c.P([(30, 104), (56, 104), (62, 128), (24, 128)], BUTTER); c.R(42, 128, 45, 180, (80, 60, 40))
        sofa = TEAL if wealth > 300 else (140, 120, 100)
        c.R(80, 136, 230, 186, sofa); c.R(86, 146, 224, 172, sh(sofa, 0.85))
        if wealth > 800: c.R(400, 136, 460, 192, (110, 70, 40)); c.R(406, 142, 444, 172, (170, 210, 220))
    elif place_kind == "diner":
        c.R(0, 150, BW, 170, RED); c.R(0, 146, BW, 150, (230, 230, 230))
        for x in range(30, 460, 60): c.E(x, 172, x + 26, 182, RED); c.R(x + 12, 182, x + 14, 200, (180, 180, 180))
    elif place_kind in ("town_hall",):
        c.R(140, 120, 340, 170, (110, 74, 44)); c.R(150, 110, 330, 120, (130, 90, 56)); c.R(60, 20, 120, 100, (60, 80, 140)); c.R(64, 24, 116, 96, (250, 250, 250))


def _interior_finish(c, snap, seed, place_kind, hid, speakers, line, tod, zoom, thought, intro):
    night = tod in ("evening", "night")
    big_people = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
    for side, pid in enumerate(speakers[:2]):
        if pid is None: continue
        a = app_of(snap, pid, seed); sp = sprite(a, 0, 1 if side == 0 else -1).resize((44, 84), Image.NEAREST)
        x = 250 + side * 70 if place_kind == "home" else 180 + side * 90
        big_people.paste(sp, (x, 196 - 84), sp)
    c.im.paste(big_people, (0, 0), big_people)
    img = c.im
    if night:
        g = Image.new("RGBA", (BW, BH), (0, 0, 0, 0)); gd = ImageDraw.Draw(g); gd.ellipse([0, 60, 90, 170], fill=(255, 210, 130, 80))
        img = Image.alpha_composite(img.convert("RGBA"), g.filter(ImageFilter.GaussianBlur(14))).convert("RGB")
    if zoom in speakers[:2]:  # close-up: crop in on the speaker (pixel-exact, keeps the look)
        side = speakers.index(zoom); sx = (250 + side * 70 if place_kind == "home" else 180 + side * 90) + 22
        cw, ch = 200, 113; x0 = max(0, min(BW - cw, sx - cw // 2)); y0 = 52 if thought else 92  # thoughts: faces sit below the cloud
        img = img.crop((x0, y0, x0 + cw, y0 + ch)).resize((BW, BH), Image.NEAREST)
    big = finish(img)
    if thought: thought_bubble(big, snap, seed, *thought)
    elif line: dialogue_box(big, snap, seed, *line)
    if intro: name_card(big, *intro)
    return big


def thought_bubble(big, snap, seed, pid, text):
    """A private thought: cloud bubble, italic-feel text, 'THINKING' tag. Shown instead of the spoken line."""
    d = ImageDraw.Draw(big, "RGBA"); f = font(FR, 28); rows = wrap(d, text, f, 760)[:4]
    tw = max(d.textlength(r_, font=f) for r_ in rows); h = 30 + 38 * len(rows); bx = (OW - tw) / 2 - 36; by = 70
    for k in range(9):  # cloud edge
        cx = bx + (tw + 72) * k / 8; d.ellipse([cx - 34, by - 18, cx + 34, by + 26], fill=(255, 255, 255, 235))
        d.ellipse([cx - 34, by + h - 26, cx + 34, by + h + 18], fill=(255, 255, 255, 235))
    d.rounded_rectangle([bx, by, bx + tw + 72, by + h], 36, fill=(255, 255, 255, 235))
    for r_, (ox, oy) in zip((16, 11, 7), ((OW / 2 + 40, by + h + 40), (OW / 2 + 70, by + h + 78), (OW / 2 + 92, by + h + 108))): d.ellipse([ox - r_, oy - r_, ox + r_, oy + r_], fill=(255, 255, 255, 235))
    name = snap["people"][str(pid)]["name"].split()[0].upper() + " THINKS"; fl = font(FB, 18)
    d.rounded_rectangle([bx + 24, by - 30, bx + 40 + d.textlength(name, font=fl), by - 4], 8, fill=(120, 90, 140)); d.text((bx + 32, by - 29), name, font=fl, fill=CREAM)
    for k, r_ in enumerate(rows): d.text((bx + 36, by + 16 + 38 * k), r_, font=f, fill=(70, 56, 90))


def name_card(big, name, sub, line=""):
    """Documentary lower-third, top-left (the dialogue box owns the bottom): name, age and job, one true line."""
    d = ImageDraw.Draw(big, "RGBA"); fn = font(FB, 30); fs = font(FR, 19); fl = font(FB, 20)
    w = max(d.textlength(name.upper(), font=fn), d.textlength(sub, font=fs), d.textlength(line, font=fl)) + 44; h = 96 if line else 70
    d.rounded_rectangle([34, 34, 34 + w, 34 + h], 12, fill=(250, 244, 226, 245), outline=INK, width=4); d.rectangle([34, 34, 44, 34 + h], fill=RED)
    d.text((58, 40), name.upper(), font=fn, fill=RED); d.text((58, 76), sub, font=fs, fill=INK)
    if line: d.text((58, 100), line, font=fl, fill=(120, 90, 140))


def dialogue_box(big, snap, seed, pid, text, expr="neutral"):
    d = ImageDraw.Draw(big); bx, by, bw, bh = 40, OH - 200, OW - 80, 170
    d.rounded_rectangle([bx, by, bx + bw, by + bh], 18, fill=(250, 244, 226), outline=INK, width=5)
    a = app_of(snap, pid, seed); por = portrait(a, expr).resize((132, 132), Image.NEAREST); big.paste(por, (bx + 20, by + 19))
    d.rectangle([bx + 20, by + 19, bx + 152, by + 151], outline=INK, width=4)
    d.text((bx + 176, by + 16), snap["people"][str(pid)]["name"].upper(), font=font(FB, 26), fill=RED)
    f = font(FR, 27)
    for k, row in enumerate(wrap(d, text, f, bw - 210)[:3]): d.text((bx + 176, by + 56 + k * 36), row, font=f, fill=INK)


# ---------------------------------------------------------------- title card, newspaper, captions, ledger
def newspaper(town, date, headline, sub="", body=""):
    im = Image.new("RGB", (OW, OH), (240, 232, 210)); d = ImageDraw.Draw(im); r = random.Random(2)
    for _ in range(5000): d.point((r.randrange(OW), r.randrange(OH)), fill=(226, 216, 190))
    d.rectangle([60, 30, OW - 60, OH - 30], outline=INK, width=3)
    mast = f"THE {town.upper()} GAZETTE"; f = font(SERIF, 54); tw = d.textlength(mast, font=f); d.text(((OW - tw) / 2, 46), mast, font=f, fill=INK)
    d.line([(80, 118), (OW - 80, 118)], fill=INK, width=3); d.text((86, 124), date, font=font(FR, 20), fill=INK); d.text((OW - 220, 124), "PRICE 5 CENTS", font=font(FR, 20), fill=INK)
    d.line([(80, 152), (OW - 80, 152)], fill=INK, width=1)
    fh = font(SERIF, 58)
    rows = wrap(d, headline.upper(), fh, OW - 200)
    for k, row in enumerate(rows[:3]): tw = d.textlength(row, font=fh); d.text(((OW - tw) / 2, 176 + k * 70), row, font=fh, fill=INK)
    y = 176 + 70 * min(3, len(rows)) + 16
    if sub:
        fs = font(SERIF, 30)
        for k, row in enumerate(wrap(d, sub, fs, OW - 260)[:2]): tw = d.textlength(row, font=fs); d.text(((OW - tw) / 2, y + k * 38), row, font=fs, fill=(70, 60, 60))
        y += 90
    fb_ = font(FR, 20)
    for k, row in enumerate(wrap(d, body, fb_, OW - 220)[:6]): d.text((110, y + k * 28), row, font=fb_, fill=(60, 50, 50))
    return im


def caption(big, text):
    if not text: return big
    d = ImageDraw.Draw(big, "RGBA"); f = font(FB, 30); rows = wrap(d, text, f, OW - 240)[:3]
    h = 20 + 42 * len(rows); y0 = OH - h - 30
    d.rounded_rectangle([90, y0, OW - 90, y0 + h], 14, fill=(20, 14, 26, 170))
    for k, row in enumerate(rows):
        tw = d.textlength(row, font=f); d.text(((OW - tw) / 2, y0 + 10 + k * 42), row, font=f, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    return big


def ledger_card(L, town, episode):
    im = Image.new("RGB", (OW, OH), (244, 236, 214)); d = ImageDraw.Draw(im); r = random.Random(2)
    for _ in range(4000): d.point((r.randrange(OW), r.randrange(OH)), fill=(232, 222, 198))
    d.rectangle([24, 24, OW - 24, OH - 24], outline=INK, width=3); d.rectangle([32, 32, OW - 32, OH - 32], outline=INK, width=1)
    t = f"THE {town.upper()} LEDGER"; f = font(SERIF, 44); d.text(((OW - d.textlength(t, font=f)) / 2, 44), t, font=f, fill=INK)
    sub = (f"END OF {episode}" if isinstance(episode, str) else f"END OF EPISODE {episode}") + f"  ·  {L['date_end']}"; f2 = font(FB, 18); d.text(((OW - d.textlength(sub, font=f2)) / 2, 100), sub, font=f2, fill=RED)
    d.line([(48, 132), (OW - 48, 132)], fill=INK, width=3)
    G, Rd = (40, 120, 70), (180, 40, 46)
    def ch(v, money=False):
        if v is None or v == 0: return ("", INK)
        return (("▲ +" if v > 0 else "▼ -") + (f"${abs(int(v)):,}" if money else f"{abs(int(v))}"), G if v > 0 else Rd)
    def spark(x, y, vals, col):
        if not vals or len(vals) < 2: return
        lo, hi = min(vals), max(vals); w_, h_ = 86, 34
        pts = [(x + i * w_ / (len(vals) - 1), y + h_ - (v - lo) / max(hi - lo, 1e-6) * h_) for i, v in enumerate(vals)]
        d.line(pts, fill=col, width=3); d.ellipse([pts[-1][0] - 4, pts[-1][1] - 4, pts[-1][0] + 4, pts[-1][1] + 4], fill=col)
    cols = [(56, "THE PEOPLE", [("Population", str(L["population"]), ch(L["population_change"]), L["population_series"]), ("Births", str(L["births"]), ("", INK), None),
                                 ("Deaths", str(L["deaths"]), ("", INK), None), ("Arrived / left", f"{L['arrivals']} / {L['left']}", ("", INK), None), ("Marriages", str(L["marriages"]), ("", INK), None)]),
            (468, "THE MONEY", [("Town treasury", f"${int(L['treasury']):,}", ch(L["treasury_change"], True), L["treasury_series"]), ("Richest house", L["richest"], ("", INK), None),
                                ("Poorest house", L["poorest"], ("", INK), None), (L["company"][:26], f"${int(L['company_cash']):,}", ch(L["company_change"], True), L["company_series"]),
                                ("Workers / let go", f"{L['workers']} / {L['layoffs']}", ("", INK), None)]),
            (880, "POWER & TALK", [("Mayor", L["mayor"], ("", INK), None), ("Council votes", L["council_votes"], ("", INK), None), ("Conversations", str(L["conversations"]), ("", INK), None),
                                   ("Party-line calls overheard", str(L["overheard"]), ("", INK), None), ("Most talked-about", L["most_talked_about"], ("", INK), None)])]
    for x, head, rows in cols:
        d.text((x, 150), head, font=font(SERIF, 26), fill=INK); d.line([(x, 186), (x + 360, 186)], fill=INK, width=2)
        for k, (lab, val, (chg, cc), sp) in enumerate(rows):
            y = 198 + k * 60
            d.text((x, y), lab.upper(), font=font(FR, 15), fill=(110, 96, 90)); fv = font(FB, 25); d.text((x, y + 17), val, font=fv, fill=INK)
            if chg: d.text((x + 10 + d.textlength(val, font=fv), y + 22), chg, font=font(SANSB, 16), fill=cc)
            if sp: spark(x + 270, y + 10, sp, cc if chg else (110, 96, 90))
            d.line([(x, y + 54), (x + 360, y + 54)], fill=(210, 198, 176), width=1)
    d.line([(48, 508), (OW - 48, 508)], fill=INK, width=2)
    d.text((56, 520), "BIGGEST WINNER", font=font(FR, 15), fill=(110, 96, 90)); d.text((56, 538), L["winner"], font=font(FB, 22), fill=G)
    d.text((56, 574), "BIGGEST LOSER", font=font(FR, 15), fill=(110, 96, 90)); d.text((56, 592), L["loser"], font=font(FB, 22), fill=Rd)
    d.text((660, 520), "THIS EPISODE", font=font(FR, 15), fill=(110, 96, 90))
    cut = lambda x, n: x if len(x) <= n else x[:n - 1].rsplit(" ", 1)[0] + "…"
    extra = [cut(x, 54) for x in L.get("notes", [])][:3] or [cut(f"News: {x}", 54) for x in L["news"][:1]]
    for k, row in enumerate(extra[:3]): d.text((660, 540 + k * 28), row, font=font(FB, 18), fill=INK)
    d.text((56, 650), "Every number comes straight from the simulation. Nothing is staged.", font=font(FR, 16), fill=(110, 96, 90))
    return im


def meet_card(snap, seed, pid, name, sub, intro):
    """'Meet the lead' card: their street behind, big portrait, name, age and job, one true line."""
    p = snap["people"][str(pid)]; hid = p["household"]
    bg = street(snap, seed, [str(hid)], [], "evening", "clear", snap["season"], vignette_on=True).filter(ImageFilter.GaussianBlur(6))
    bg = Image.blend(bg, Image.new("RGB", bg.size, (20, 14, 34)), 0.45); d = ImageDraw.Draw(bg)
    por = portrait(app_of(snap, pid, seed), "neutral").resize((336, 336), Image.NEAREST)
    d.rectangle([110, 182, 462, 534], fill=INK); bg.paste(por, (118, 190))
    d.text((520, 220), "MEET", font=font(FB, 30), fill=BUTTER)
    fn = font(SERIF, 64); nm = name.upper()
    while d.textlength(nm, font=fn) > OW - 560 and fn.size > 30: fn = font(SERIF, fn.size - 4)
    d.text((520, 262), nm, font=fn, fill=CREAM); d.text((524, 350), sub, font=font(FR, 30), fill=(210, 200, 230))
    for k, row in enumerate(wrap(d, intro, font(FB, 32), OW - 580)[:2]): d.text((524, 410 + k * 44), row, font=font(FB, 32), fill=BUTTER)
    return bg


def family_board_card(fb, town, episode=None):
    """Viewer-only standings. The residents never see this; it's our scoreboard of what they did."""
    im = Image.new("RGB", (OW, OH), (244, 236, 214)); d = ImageDraw.Draw(im); r = random.Random(5)
    for _ in range(4000): d.point((r.randrange(OW), r.randrange(OH)), fill=(232, 222, 198))
    d.rectangle([24, 24, OW - 24, OH - 24], outline=INK, width=3)
    t = "THE FAMILY BOARD"; f = font(SERIF, 44); d.text(((OW - d.textlength(t, font=f)) / 2, 40), t, font=f, fill=INK)
    # quarterly parts say "END OF PART 2 · SPRING 1950" (Nov 21)
    sub = f"{town.upper()}  ·  END OF {episode if isinstance(episode, str) else fb['year_end']}"; f2 = font(FB, 18); d.text(((OW - d.textlength(sub, font=f2)) / 2, 96), sub, font=f2, fill=RED)
    cols = [(60, "#"), (110, "FAMILY"), (370, "SAVINGS"), (560, "AT HOME"), (700, "BUSINESSES"), (1000, "IN OFFICE")]
    for x, h in cols: d.text((x, 136), h, font=font(FR, 15), fill=(110, 96, 90))
    d.line([(52, 160), (OW - 52, 160)], fill=INK, width=2)
    G, Rd = (40, 120, 70), (180, 40, 46)
    for k, row in enumerate(fb["rows"]):
        y = 172 + k * 54; fv = font(FB, 24)
        d.text((60, y), str(row["rank"]), font=fv, fill=INK)
        move = (row["was_rank"] or row["rank"]) - row["rank"]
        if move: d.text((84, y + 4), ("▲" if move > 0 else "▼"), font=font(SANSB, 16), fill=G if move > 0 else Rd)
        d.text((110, y), f"The {row['surname']}s" + ("  (new)" if row.get("new") else ""), font=fv, fill=INK)
        if row["home"] != "standing": d.text((110, y + 28), row["home"], font=font(FR, 14), fill=Rd)
        d.text((370, y), f"${row['savings']:,}", font=fv, fill=INK)
        dv = row["savings"] - row["was_savings"]
        if dv and not row.get("new"): d.text((370, y + 28), ("+" if dv > 0 else "-") + f"${abs(dv):,}", font=font(FR, 14), fill=G if dv > 0 else Rd)
        d.text((560, y), str(row["people"]), font=fv, fill=INK)
        biz = ", ".join(row["businesses"]) or "-"; fb_ = font(FB, 18)
        while d.textlength(biz, font=fb_) > 280 and len(biz) > 4: biz = biz[:-2]
        d.text((700, y + 4), biz, font=fb_, fill=INK); d.text((1000, y + 4), ", ".join(row["seats"]) or "-", font=fb_, fill=INK)
        d.line([(52, y + 48), (OW - 52, y + 48)], fill=(210, 198, 176), width=1)
    q = fb["question"]; fq = font(SERIF, 30); d.text(((OW - d.textlength(q, font=fq)) / 2, OH - 112), q, font=fq, fill=RED)
    d.text((56, OH - 60), "Ranked by " + fb["formula"] + ". The residents never see this board.", font=font(FR, 15), fill=(110, 96, 90))
    return im


def season_stamp(big, text):
    """Big season/year stamp for the time-lapse (e.g. 'SPRING 1953')."""
    d = ImageDraw.Draw(big); f = font(SERIF, 54); tw = d.textlength(text, font=f)
    d.text(((OW - tw) / 2 + 3, 40 + 3), text, font=f, fill=INK); d.text(((OW - tw) / 2, 40), text, font=f, fill=CREAM)
    return big
