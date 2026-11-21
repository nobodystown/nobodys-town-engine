"""Locked style ("Option B"): 480x270 pixel art, scaled to 1280x720. Original art drawn in code.
Characters, portraits, buildings, street/overview/interior scenes, title card, newspaper, Ledger."""
import math, random
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

BW, BH = 480, 270
OW, OH = 1280, 720
INK = (38, 28, 40); CREAM = (250, 244, 226); RED = (214, 52, 64); TEAL = (64, 190, 196); BUTTER = (246, 216, 120)
FB = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"; FR = "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf"
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"; SANSB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_fc = {}
def font(path, size):
    k = (path, size)
    if k not in _fc: _fc[k] = ImageFont.truetype(path, size)
    return _fc[k]
def sh(c, k): return tuple(max(0, min(255, int(v * k))) for v in c[:3])
def mix(a, b, u): return tuple(int(a[i] * (1 - u) + b[i] * u) for i in range(3))

SKINS = [(255, 224, 196), (241, 194, 160), (224, 172, 128), (198, 140, 96), (160, 104, 66), (116, 74, 46), (88, 56, 36)]
HAIRS = [(30, 22, 20), (70, 44, 30), (120, 74, 40), (176, 110, 60), (226, 190, 110), (200, 90, 50)]
CLOTH = [(214, 52, 64), (64, 190, 196), (74, 92, 140), (236, 120, 130), (246, 216, 120), (130, 190, 160), (120, 90, 140), (90, 130, 90), (180, 120, 70), (70, 70, 80), (200, 160, 110), (140, 60, 60)]
WALLS = [(246, 214, 120), (236, 150, 140), (160, 222, 196), (200, 180, 230), (246, 236, 208), (150, 200, 230), (230, 190, 150), (190, 210, 160)]
CARS = [(170, 40, 50), (60, 110, 160), (230, 226, 210), (90, 150, 130), (40, 40, 50), (230, 190, 110), (150, 170, 190), (120, 70, 90)]
ROOFS = [(64, 170, 180), (90, 100, 150), (214, 52, 64), (110, 90, 80), (90, 130, 90), (150, 78, 66), (70, 70, 90)]


# ---------------------------------------------------------------- appearance (stable per resident)
def appearance(person, seed):
    r = random.Random(seed * 100003 + person["id"])
    age, sex, job = person["age"], person["sex"], (person.get("job") or "")
    stage = "baby" if age < 3 else "kid" if age < 13 else "teen" if age < 18 else "elder" if age >= 65 else "adult"
    hair = r.choice(HAIRS)
    if age >= 65 or (age > 50 and r.random() < 0.45): hair = r.choice([(150, 150, 150), (200, 200, 205), (230, 230, 232)])
    j = job.lower()
    if sex == "male":
        outfit = ("suit" if any(k in j for k in ("owner", "salesman", "bookkeeper", "editor", "doctor", "postmaster")) else
                  "overalls" if any(k in j for k in ("mill", "mine", "farm", "feedlot", "works at", "carpenter", "mechanic", "handyman", "lumber", "cannery", "quarry")) else
                  "cardigan" if stage == "elder" else "letterman" if stage == "teen" else "shirt")
        hat = r.choice(["fedora", "fedora", None]) if outfit == "suit" else r.choice(["cap", None, None]) if stage in ("adult", "elder") else (r.choice(["cap", None]) if stage == "kid" else None)
        style = r.choice(["short", "parted", "buzz"] + (["bald"] if age > 45 else []))
    else:
        outfit = ("apron" if any(k in j for k in ("diner", "homemaker", "cook")) and r.random() < 0.6 else "suit_f" if any(k in j for k in ("teacher", "bookkeeper", "postmaster", "owner", "nurse", "operator")) else
                  "cardigan" if stage == "elder" else "dress")
        hat = r.choice(["sunhat", None, None, None]) if stage in ("adult", "elder") else None
        style = r.choice(["bob", "curls", "bun", "pony"] if stage != "elder" else ["bun", "curls"])
    return {"stage": stage, "sex": sex, "skin": r.choice(SKINS), "hair": hair, "style": style, "outfit": outfit, "c1": r.choice(CLOTH), "c2": r.choice(CLOTH),
            "hat": hat, "glasses": r.random() < (0.45 if age > 45 else 0.1), "cane": stage == "elder" and r.random() < 0.5}


def outline(im):
    a = im.split()[3]; edge = ImageChops.subtract(a.filter(ImageFilter.MaxFilter(3)), a)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0)); out.paste(Image.new("RGBA", im.size, INK + (255,)), (0, 0), edge); out.alpha_composite(im); return out


def sprite(app, frame=0, facing=1):
    """20x40 walking sprite in the locked style."""
    im = Image.new("RGBA", (22, 42), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    R = lambda x0, y0, x1, y1, c: d.rectangle([x0, y0, x1, y1], fill=c)
    st = app["stage"]; sk = app["skin"]; skd = sh(sk, 0.82); hc = app["hair"]; c1, c2 = app["c1"], app["c2"]
    ground = 40; cx = 11
    H = {"baby": 14, "kid": 26, "teen": 34, "adult": 38, "elder": 36}[st]
    top = ground - H; hh = 6 if st in ("baby", "kid") else 8; hx = cx - 4 + (1 if st == "elder" else 0)
    if st == "baby":  # carried bundle look
        R(cx - 4, ground - 10, cx + 4, ground, (250, 250, 245)); R(cx - 3, ground - 14, cx + 2, ground - 9, sk); d.point((cx - 1, ground - 12), fill=INK); d.point((cx + 1, ground - 12), fill=INK)
        return outline(im)
    # head
    R(hx, top + 1, hx + 7, top + hh, sk); R(hx + 6, top + 2, hx + 7, top + hh, skd)
    ey = top + 3 + (1 if hh == 8 else 0)
    R(hx + 2, ey, hx + 2, ey + 1, INK); R(hx + 5, ey, hx + 5, ey + 1, INK); R(hx + 3, top + hh - 1, hx + 5, top + hh - 1, (170, 80, 80))
    if app["glasses"]: R(hx + 1, ey, hx + 6, ey, (60, 60, 60))
    s = app["style"]
    if s != "bald":
        R(hx - 1, top - 1, hx + 8, top + 1, hc); R(hx - 1, top, hx - 1, top + (8 if s in ("bob", "curls") else 4), hc)
        if s in ("bob", "curls"): R(hx + 8, top, hx + 8, top + 6, hc)
        if s == "bun": R(hx + 1, top - 3, hx + 5, top - 1, hc)
        if s == "pony": R(hx - 3, top + 1, hx - 2, top + 7, hc)
        if s == "curls": [R(x, top - 2, x + 1, top - 1, hc) for x in range(hx - 1, hx + 9, 3)]
    else: R(hx - 1, top + 2, hx - 1, top + 4, hc)
    if app["hat"] == "fedora": R(hx - 2, top - 1, hx + 9, top - 1, (70, 54, 46)); R(hx - 1, top - 4, hx + 8, top - 2, (70, 54, 46)); R(hx - 1, top - 2, hx + 8, top - 2, (150, 40, 44))
    if app["hat"] == "cap": R(hx - 1, top - 2, hx + 7, top, c2); R(hx + 7, top, hx + 10, top, c2)
    if app["hat"] == "sunhat": R(hx - 3, top - 1, hx + 10, top - 1, (240, 220, 160)); R(hx - 1, top - 3, hx + 8, top - 2, (240, 220, 160)); R(hx - 1, top - 2, hx + 8, top - 2, c1)
    t0 = top + hh + 1; torso = int(H * 0.36); t1 = t0 + torso
    o = app["outfit"]; a, b = [(0, 0), (1, -1), (0, 0), (-1, 1)][frame % 4]
    legc = (52, 58, 84)
    if o in ("dress", "apron", "suit_f"):
        R(cx - 4, t0, cx + 3, t1, c1); R(cx + 2, t0, cx + 3, t1, sh(c1, 0.82))
        R(cx - 6, t1, cx + 5, t1 + int(H * 0.22), c1); R(cx + 2, t1, cx + 5, t1 + int(H * 0.22), sh(c1, 0.8))
        if o == "apron": R(cx - 3, t0 + 2, cx + 2, t1 + int(H * 0.2), (250, 250, 245))
        if o == "suit_f": R(cx - 1, t0, cx, t0 + 3, (250, 250, 245))
        if o == "dress":
            for k in range(cx - 5, cx + 5, 3): d.point((k, t1 + 3), fill=(250, 250, 245))
        R(cx - 3 + a, t1 + int(H * 0.22) + 1, cx - 2 + a, ground - 1, sk); R(cx + 1 + b, t1 + int(H * 0.22) + 1, cx + 2 + b, ground - 1, skd)
        R(cx - 4 + a, ground, cx - 1 + a, ground + 1, RED if st != "elder" else (60, 40, 40)); R(cx + 1 + b, ground, cx + 3 + b, ground + 1, RED if st != "elder" else (60, 40, 40))
    else:
        body = {"suit": c2 if c2 != c1 else (74, 92, 140), "overalls": (70, 90, 150), "cardigan": c1, "letterman": c1, "shirt": c1}[o]
        R(cx - 5, t0, cx + 4, t1, body); R(cx + 2, t0, cx + 4, t1, sh(body, 0.8))
        if o == "suit": R(cx - 1, t0, cx + 1, t0 + 6, (245, 245, 240)); R(cx, t0 + 1, cx, t0 + 6, c1)
        if o == "overalls": R(cx - 5, t0, cx + 4, t0 + 2, c1); R(cx - 3, t0, cx - 3, t0 + 4, (70, 90, 150)); R(cx + 2, t0, cx + 2, t0 + 4, (70, 90, 150))
        if o == "letterman": R(cx - 5, t0, cx - 4, t1, c2); R(cx + 3, t0, cx + 4, t1, c2); R(cx - 2, t0 + 3, cx, t0 + 5, (250, 250, 240))
        if o == "cardigan": R(cx, t0, cx, t1, sh(c1, 0.7))
        lc = (70, 90, 150) if o == "overalls" else legc if o == "suit" else (90, 80, 70) if st == "elder" else (60, 70, 110)
        R(cx - 4 + a, t1 + 1, cx - 1 + a, ground - 1, lc); R(cx + 1 + b, t1 + 1, cx + 3 + b, ground - 1, sh(lc, 0.85))
        R(cx - 5 + a, ground, cx - 1 + a, ground + 1, (30, 24, 24)); R(cx + 1 + b, ground, cx + 4 + b, ground + 1, (30, 24, 24))
    sw = [0, 1, 0, -1][frame % 4]; arm = c1 if o not in ("shirt", "overalls") or st in ("elder",) else sk
    R(cx - 6, t0 + 1 + sw, cx - 6, t1 - 1 + sw, arm if o not in ("dress",) else sk); R(cx + 5, t0 + 1 - sw, cx + 5, t1 - 1 - sw, sh(arm if o != "dress" else sk, 0.85))
    if app["cane"]: R(cx + 6, t1 - 2, cx + 6, ground + 1, (120, 80, 44))
    im = outline(im)
    return im if facing > 0 else im.transpose(Image.FLIP_LEFT_RIGHT)


def portrait(app, expr="neutral", size=48):
    """48x48 bust in the locked style; expressions: neutral, happy, angry, sad, scheming, shocked."""
    im = Image.new("RGB", (size, size), sh(app["c1"], 0.55)); d = ImageDraw.Draw(im)
    R = lambda x0, y0, x1, y1, c: d.rectangle([x0, y0, x1, y1], fill=c)
    for y in range(size): d.line([(0, y), (size, y)], fill=mix(sh(app["c1"], 0.45), sh(app["c1"], 0.7), y / size))
    sk = app["skin"]; skd = sh(sk, 0.84); hc = app["hair"]
    if expr == "angry": sk = (min(255, int(sk[0] * 1.07)), int(sk[1] * 0.9), int(sk[2] * 0.88))
    o = app["outfit"]; body = {"suit": app["c2"], "overalls": (70, 90, 150)}.get(o, app["c1"])
    R(8, 38, 39, 47, body); R(30, 38, 39, 47, sh(body, 0.8))
    if o == "suit": R(20, 38, 27, 47, (245, 245, 240)); R(23, 39, 24, 47, app["c1"])
    if o == "apron": R(15, 40, 32, 47, (250, 250, 245))
    if o == "overalls": R(14, 38, 16, 47, app["c1"]); R(31, 38, 33, 47, app["c1"])
    R(20, 33, 27, 38, skd)
    R(13, 10, 34, 34, sk); R(30, 12, 34, 34, skd); R(12, 18, 12, 26, sk); R(35, 18, 35, 26, skd)
    if app["stage"] == "elder": d.line([(16, 30), (19, 31)], fill=sh(sk, 0.8)); d.line([(28, 31), (31, 30)], fill=sh(sk, 0.8))
    s = app["style"]
    if s != "bald":
        R(12, 6, 35, 12, hc); R(12, 10, 14, 20 if s not in ("bob", "curls") else 32, hc); R(33, 10, 35, 18 if s not in ("bob", "curls") else 32, hc)
        if s == "bun": R(18, 1, 29, 6, hc)
        if s == "curls": [R(x, 4, x + 3, 7, hc) for x in range(11, 35, 4)]
        if s == "pony": R(35, 14, 38, 28, hc)
        if s == "parted": R(22, 6, 22, 9, sh(hc, 0.7))
    else: R(12, 14, 13, 20, hc); R(34, 14, 35, 20, hc)
    if app["hat"] == "fedora": R(7, 8, 40, 9, (70, 54, 46)); R(13, 1, 34, 7, (70, 54, 46)); R(13, 5, 34, 7, (150, 40, 44))
    if app["hat"] == "cap": R(12, 4, 35, 9, app["c2"]); R(31, 9, 41, 10, app["c2"])
    if app["hat"] == "sunhat": R(5, 8, 42, 9, (240, 220, 160)); R(13, 2, 34, 7, (240, 220, 160)); R(13, 5, 34, 7, app["c1"])
    bc = sh(hc, 0.75) if s != "bald" else sh(sk, 0.6)
    brows = {"angry": [((15, 15), (20, 17)), ((27, 17), (32, 15))], "sad": [((15, 17), (20, 15)), ((27, 15), (32, 17))],
             "scheming": [((15, 16), (20, 16)), ((27, 14), (32, 15))], "shocked": [((15, 13), (20, 13)), ((27, 13), (32, 13))]}.get(expr, [((15, 16), (20, 16)), ((27, 16), (32, 16))])
    for a_, b_ in brows: d.line([a_, b_], fill=bc, width=2)
    if expr == "happy": d.line([(16, 21), (18, 19), (20, 21)], fill=INK, width=2); d.line([(27, 21), (29, 19), (31, 21)], fill=INK, width=2)
    elif expr == "shocked": R(15, 18, 20, 23, (250, 250, 250)); R(27, 18, 32, 23, (250, 250, 250)); R(17, 20, 18, 21, INK); R(29, 20, 30, 21, INK)
    elif expr == "scheming": R(16, 20, 20, 21, (250, 250, 250)); R(27, 20, 31, 21, (250, 250, 250)); R(18, 20, 20, 21, INK); R(29, 20, 31, 21, INK)
    else: R(16, 19, 19, 22, (250, 250, 250)); R(28, 19, 31, 22, (250, 250, 250)); R(17, 20, 18, 22, INK); R(29, 20, 30, 22, INK)
    if app["glasses"]: d.rectangle([14, 17, 21, 24], outline=(50, 50, 50)); d.rectangle([26, 17, 33, 24], outline=(50, 50, 50)); d.line([(21, 19), (26, 19)], fill=(50, 50, 50))
    R(23, 22, 24, 26, sh(sk, 0.82))
    m = (160, 60, 70)
    if expr == "happy": d.line([(18, 28), (20, 30), (27, 30), (29, 28)], fill=m, width=2); R(15, 25, 17, 26, (240, 150, 140)); R(30, 25, 32, 26, (240, 150, 140))
    elif expr == "angry": R(19, 30, 28, 31, m); R(18, 31, 19, 32, m); R(28, 31, 29, 32, m)
    elif expr == "sad": R(19, 30, 28, 30, m); R(18, 29, 19, 29, m); R(28, 29, 29, 29, m); R(31, 22, 31, 27, (140, 200, 240))
    elif expr == "scheming": R(20, 30, 27, 30, m); R(27, 29, 29, 29, m)
    elif expr == "shocked": R(21, 28, 26, 32, (90, 30, 40))
    else: R(19, 30, 28, 30, m)
    return im


# ---------------------------------------------------------------- shared helpers for scenes
class C:
    def __init__(self): self.im = Image.new("RGB", (BW, BH)); self.d = ImageDraw.Draw(self.im, "RGBA")
    def R(self, x0, y0, x1, y1, c): self.d.rectangle([int(x0), int(y0), max(int(x0), int(x1) - 1), max(int(y0), int(y1) - 1)], fill=c)
    def P(self, pts, c): self.d.polygon([(int(x), int(y)) for x, y in pts], fill=c)
    def E(self, x0, y0, x1, y1, c): self.d.ellipse([int(x0), int(y0), int(x1), int(y1)], fill=c)
    def L(self, pts, c, w=1): self.d.line([(int(x), int(y)) for x, y in pts], fill=c, width=w)


TOD = {"morning": ((120, 170, 230), (250, 220, 190), (255, 230, 170, 26)), "midday": ((96, 160, 236), (196, 226, 248), (0, 0, 0, 0)),
       "evening": ((64, 66, 130), (252, 180, 140), (255, 160, 80, 40)), "night": ((14, 18, 46), (40, 48, 90), (20, 30, 90, 90))}


def sky(c, tod, weather, season, sun=True):
    top, bot, _ = TOD[tod]
    if weather in ("rain", "storm"): top, bot = sh(top, 0.6), sh((150, 160, 170), 0.9)
    if weather == "snow": top, bot = (150, 160, 185), (220, 225, 235)
    for y in range(BH):
        u = min(1, y / 165); c.d.line([(0, y), (BW, y)], fill=mix(top, bot, u))
        if y % 2 == 0 and 0.62 < u < 0.74 and tod in ("morning", "evening"):
            for x in range(y % 4, BW, 4): c.d.point((x, y), fill=mix(mix(top, bot, u), bot, 0.5))
    if tod == "night":
        r = random.Random(3)
        for _ in range(70): c.d.point((r.randrange(BW), r.randrange(120)), fill=(240, 240, 255))
        if sun: c.E(400, 24, 416, 40, (250, 244, 220))
    elif weather not in ("rain", "storm", "snow"):
        sx = {"morning": 90, "midday": 240, "evening": 360}[tod]; sy = {"morning": 110, "midday": 30, "evening": 110}[tod]
        if sun: c.E(sx - 20, sy - 20, sx + 20, sy + 20, (255, 236, 190)); c.E(sx - 32, sy - 32, sx + 32, sy + 32, (255, 236, 190, 50))
        for cx_, cy_, w_ in ((80, 46, 70), (210, 30, 90), (400, 58, 60)):
            cc = (250, 196, 176) if tod == "evening" else (250, 250, 252)
            for k in range(5): c.E(cx_ + k * w_ / 6 - w_ / 2, cy_ - 6 + (k % 2) * 3, cx_ + k * w_ / 6 - w_ / 2 + w_ / 3, cy_ + 8, cc)


def grade(img, tod):
    ov = TOD[tod][2]
    if ov[3]:
        g = Image.new("RGBA", img.size, ov); img = Image.alpha_composite(img.convert("RGBA"), g).convert("RGB")
    return img


_VIG = {}
def vignette(big):
    if big.size not in _VIG:
        W, H = big.size
        vig = Image.new("L", (W, H), 0); ImageDraw.Draw(vig).ellipse([-200, -160, W + 200, H + 160], fill=255)
        _VIG[big.size] = vig.filter(ImageFilter.GaussianBlur(120)).point(lambda v: int(150 + v * 105 / 255))
    return Image.composite(big, Image.new("RGB", big.size, (30, 20, 40)), _VIG[big.size])


def finish(img, vignette_on=True):
    big = img.resize((OW, OH), Image.NEAREST)
    return vignette(big) if vignette_on else big


CAR_LEN, CAR_H = 94, 40


def car_sprite(color, model_year=1950, facing=1, hearse=False, night=False):
    """A period car, drawn at true scale next to a resident (a 1950s sedan is about 17 ft long and 5 ft tall).
    Three looks by model year: pre-war (<1949: tall cab, separate pontoon fenders, running boards),
    early fifties (1949-54: rounded 'bathtub' body, sun visor, split windshield, wheel skirts),
    late fifties (1955+: long and low, two-tone, wraparound glass, chrome side spear, tail fins).
    Returns an RGBA sprite facing right (or left); wheels sit on the bottom row."""
    im = Image.new("RGBA", (CAR_LEN + 4, CAR_H + 2), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    R = lambda x0, y0, x1, y1, c_: d.rectangle([x0, y0, x1, y1], fill=c_)
    P = lambda pts, c_: d.polygon(pts, fill=c_)
    E = lambda x0, y0, x1, y1, c_: d.ellipse([x0, y0, x1, y1], fill=c_)
    body = sh(color, 0.6) if night else color; dark = sh(body, 0.72); hi = sh(body, 1.18)
    glass = (60, 70, 100) if night else (156, 196, 222); chrome = (150, 152, 160) if night else (226, 228, 232)
    tire = (28, 26, 32); white = (200, 200, 200) if night else (246, 246, 240)
    b = CAR_H  # ground row (bottom of the tires)
    era = "prewar" if model_year < 1949 else "early" if model_year < 1955 else "late"
    if hearse: era = "early"

    def wheel(cx, r=8, skirt=False):
        E(cx - r, b - 2 * r, cx + r, b, tire)
        if not skirt:
            E(cx - r + 3, b - 2 * r + 3, cx + r - 3, b - 3, white)       # whitewall
            E(cx - r + 5, b - 2 * r + 5, cx + r - 5, b - 5, (60, 60, 68))
            E(cx - 2, b - r - 2, cx + 2, b - r + 2, chrome)                # hubcap

    if era == "prewar":
        wheel(16); wheel(74)
        R(10, b - 12, 84, b - 9, dark)                                       # running board
        E(2, b - 22, 32, b - 6, body); E(58, b - 22, 90, b - 6, body)        # pontoon fenders
        R(14, b - 26, 82, b - 12, body)                                      # body tub
        P([(56, b - 26), (88, b - 22), (90, b - 14), (56, b - 14)], body)    # long hood
        R(86, b - 24, 90, b - 12, chrome); [R(87, y, 89, y, dark) for y in range(b - 23, b - 12, 2)]
        P([(20, b - 26), (24, b - 40), (54, b - 40), (58, b - 26)], body)   # tall upright cab
        R(26, b - 37, 37, b - 28, glass); R(40, b - 37, 52, b - 28, glass)
        E(82, b - 27, 87, b - 22, (255, 236, 170) if not night else (255, 214, 120))  # headlamp on the fender
        R(1, b - 14, 6, b - 11, chrome); R(88, b - 14, 93, b - 11, chrome)
        wheel(16); wheel(74)                                                 # tires over fenders' lower edge
        E(2, b - 22, 32, b - 13, body); E(58, b - 22, 90, b - 13, body)
    elif era == "early":
        L_ = 92 if not hearse else 94
        R(2, b - 24, L_ - 2, b - 8, body)                                    # one-piece body
        E(0, b - 26, 24, b - 6, body); E(L_ - 26, b - 26, L_, b - 6, body)   # rounded tail and nose
        R(4, b - 10, L_ - 4, b - 8, dark)                                    # rocker shadow
        R(6, b - 25, L_ - 8, b - 24, hi)                                     # highlight along the shoulder
        if hearse:
            P([(14, b - 24), (14, b - 42), (62, b - 42), (72, b - 24)], body)  # long, high roof
            R(18, b - 38, 40, b - 30, (40, 36, 44)); [R(x, b - 37, x + 1, b - 31, chrome) for x in (22, 28, 34)]  # landau bars
            R(44, b - 38, 58, b - 28, glass)
        else:
            E(22, b - 44, 66, b - 18, body)                                  # rounded fastback roof
            R(22, b - 31, 66, b - 24, body)
            P([(28, b - 26), (32, b - 38), (43, b - 40), (43, b - 26)], glass)  # rear side glass
            P([(46, b - 26), (46, b - 40), (56, b - 38), (62, b - 26)], glass)  # front side glass
            R(44, b - 40, 45, b - 26, body)                                  # B pillar
            R(54, b - 42, 66, b - 40, sh(body, 0.85))                        # sun visor
        wheel(18, skirt=True)                                                # rear tire: only its bottom shows under the skirt
        E(4, b - 26, 32, b - 10, body); R(6, b - 18, 30, b - 5, body)        # rear wheel skirt
        R(7, b - 6, 29, b - 5, chrome)
        wheel(L_ - 18)
        E(L_ - 32, b - 26, L_ - 4, b - 14, body)                             # front fender crown over the wheel
        R(L_ - 6, b - 20, L_, b - 12, chrome); [R(L_ - 5, y, L_ - 1, y, dark) for y in range(b - 19, b - 12, 2)]  # grille
        E(L_ - 7, b - 21, L_ - 3, b - 17, (255, 236, 170) if not night else (255, 214, 120))
        R(0, b - 12, 6, b - 9, chrome); R(L_ - 4, b - 12, L_ + 2, b - 9, chrome)  # bumpers
        R(L_ - 40, b - 18, L_ - 34, b - 17, chrome)                          # door handle
    else:
        roof = (246, 240, 224) if not night else (150, 146, 136)            # two-tone: cream top
        R(2, b - 22, 92, b - 8, body)
        R(2, b - 22, 92, b - 21, hi)
        P([(0, b - 22), (12, b - 22), (2, b - 31)], body)                    # tail fin
        R(0, b - 20, 3, b - 16, (220, 50, 50))                               # tail light
        P([(22, b - 22), (30, b - 36), (64, b - 36), (74, b - 22)], roof)    # long, low roof
        P([(30, b - 23), (34, b - 33), (48, b - 33), (48, b - 23)], glass)
        P([(51, b - 23), (51, b - 33), (62, b - 33), (70, b - 23)], glass)  # wraparound windshield edge
        R(49, b - 34, 50, b - 23, roof)
        _line(d, [(8, b - 15), (84, b - 15)], chrome, 2)                         # chrome side spear
        R(4, b - 10, 90, b - 8, dark)
        wheel(20); wheel(74)
        R(88, b - 19, 94, b - 11, chrome); [R(89, y, 93, y, dark) for y in range(b - 18, b - 11, 2)]
        E(89, b - 20, 93, b - 16, (255, 236, 170) if not night else (255, 214, 120))
        R(0, b - 12, 6, b - 9, chrome); R(90, b - 12, 96, b - 9, chrome)
    im = outline(im)
    return im if facing > 0 else im.transpose(Image.FLIP_LEFT_RIGHT)


def _line(d, pts, c_, w=1): d.line(pts, fill=c_, width=w)


def car(c, x, curb, color, year=1953, facing=1, model_year=None, hearse=False, night=False):
    """Draw a car parked (or driving) in the road lane just below the curb. curb = the road's top edge (ground + 18).
    model_year defaults to the current year: cars on the street are a mix of ages; callers pass the household's own."""
    sp = car_sprite(color, model_year or year, facing, hearse, night)
    y = int(curb + 26 - sp.height)  # tires rest a few pixels into the lane, below the curb
    c.d.ellipse([x + 6, curb + 23, x + sp.width - 6, curb + 28], fill=(20, 16, 30, 90))  # shadow
    c.im.paste(sp, (int(x), y), sp)


def ruin(c, x, w, h, ground):
    """What's left after a house burns to the ground: the chimney, charred posts and a black footprint."""
    top = ground - h
    c.R(x - 4, ground - 4, x + w + 4, ground + 2, (40, 34, 34)); c.R(x - 8, ground, x + w + 8, ground + 6, (80, 92, 70))
    for k, px in enumerate(range(int(x), int(x + w), 18)):
        ph = [30, 14, 42, 22, 8, 26, 18][k % 7]; c.R(px, ground - ph, px + 4, ground, (34, 28, 30)); c.R(px + 4, ground - ph + 4, px + 5, ground, (70, 50, 44))
    c.P([(x + 10, ground - 34), (x + 30, ground - 20), (x + 16, ground - 18)], (40, 32, 32))
    c.R(x + w - 28, top - 20, x + w - 16, ground, (130, 70, 60)); c.R(x + w - 28, top - 20, x + w - 16, top - 16, (60, 40, 40))
    for k in range(4): c.E(x + w - 30 + k * 6, top - 34 - k * 10, x + w - 16 + k * 8, top - 22 - k * 10, (120, 120, 126, 110))


def house_front(c, x, w, h, wall, roof, ground, lit, cond=1.0, label_pos=None, burned=False, tv=False, car_color=None, year=1953):
    if burned: return ruin(c, x, w, h, ground)
    top = ground - h
    c.P([(x + w, ground), (x + w + 30, ground), (x + w + 14, top + 10), (x + w, top + 10)], (40, 30, 60, 50))
    c.R(x, top, x + w, ground, wall)
    for yy in range(top + 3, ground, 3): c.R(x, yy, x + w, yy + 1, sh(wall, 0.92))
    c.R(x + w - 6, top, x + w, ground, sh(wall, 0.82))
    c.P([(x - 8, top + 1), (x + w / 2, top - 34), (x + w + 8, top + 1)], roof)
    c.P([(x + w / 2, top - 34), (x + w + 8, top + 1), (x + w / 2 + 4, top + 1)], sh(roof, 0.8))
    for k in range(6):
        yy = top - 28 + k * 5; half = (yy - (top - 34)) * (w / 2 + 8) / 35; c.L([(x + w / 2 - half, yy), (x + w / 2 + half, yy)], sh(roof, 0.85))
    c.R(x + w - 28, top - 32, x + w - 18, top - 6, (150, 78, 66))
    if tv:  # a TV antenna on the roof: the first thing a neighbor would notice
        ax = x + w / 2 + 14; c.L([(ax, top - 26), (ax, top - 52)], (70, 70, 80)); [c.L([(ax - 9 + k, top - 50 + k * 5), (ax + 9 - k, top - 50 + k * 5)], (70, 70, 80)) for k in range(3)]
    for wx in (x + 10, x + w - 34):
        c.R(wx - 2, top + 12, wx + 22, top + 38, (250, 248, 240))
        c.R(wx, top + 14, wx + 20, top + 36, (255, 214, 130) if lit else (130, 170, 210))
        c.R(wx + 9, top + 14, wx + 11, top + 36, (250, 248, 240)); c.R(wx, top + 24, wx + 20, top + 26, (250, 248, 240))
        c.R(wx, top + 14, wx + 5, top + 23, RED if lit else (236, 120, 130)); c.R(wx + 15, top + 14, wx + 20, top + 23, RED if lit else (236, 120, 130))
        if cond < 0.5: c.L([(wx, top + 14), (wx + 20, top + 36)], (60, 50, 40), 2); c.L([(wx + 20, top + 14), (wx, top + 36)], (60, 50, 40), 2)
    dx = x + w / 2 - 8
    c.R(dx - 6, top + 6, dx + 22, top + 10, (250, 248, 240)); c.R(dx, top + 20, dx + 16, ground, sh(roof, 0.75)); c.E(dx + 12, top + 40, dx + 14, top + 42, BUTTER)
    c.R(dx - 4, top + 10, dx - 2, ground, (250, 248, 240)); c.R(dx + 18, top + 10, dx + 20, ground, (250, 248, 240))
    if lit: c.E(dx + 6, top + 11, dx + 10, top + 15, (255, 230, 150))
    c.R(x - 12, ground, x + w + 12, ground + 6, (96, 150, 84))
    for k in range(int(x - 10), int(x + w + 12), 5):
        if not (dx - 4 <= k <= dx + 20): c.R(k, ground - 9, k + 2, ground + 3, (250, 250, 244)); c.R(k, ground - 10, k + 1, ground - 9, (250, 250, 244))
    c.R(x - 10, ground - 5, x + w + 12, ground - 4, (250, 250, 244))
    if cond < 0.7:  # visible damage
        c.R(x + 20, top - 12, x + 38, top - 4, (120, 100, 90)); c.L([(x + 22, top - 10), (x + 36, top - 5)], INK)
    if cond < 0.5:  # badly damaged: scorch marks and a tarp over the roof
        c.P([(x + 6, top + 2), (x + w / 2, top - 22), (x + w / 2 + 10, top - 14), (x + 20, top + 6)], (120, 110, 90)); c.R(x + w - 40, top + 2, x + w - 8, top + 10, (60, 50, 50, 140))
