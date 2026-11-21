"""Snow globe mark v2 (128px pixel canvas): glass seated in a wooden collar, mound-shaped ground inside,
water tower set back behind the houses. season: winter | spring | summer | autumn."""
import math, random
from PIL import Image, ImageDraw
from .brand import F, COND, INK, CREAM, RED, TEAL, BUTTER, MINT, sh, mix

N = 128; CX, CY, R = 64, 58, 44
SEASON = {
    "winter": {"sky": ((26, 30, 84), (92, 70, 130)), "ground": (236, 240, 248), "ground2": (206, 214, 232), "roof_snow": True, "trees": None, "part": ((255, 255, 255), 34)},
    "spring": {"sky": ((88, 140, 210), (200, 170, 210)), "ground": (128, 196, 112), "ground2": (100, 168, 92), "roof_snow": False, "trees": ((250, 186, 206), (230, 150, 180)), "part": ((255, 196, 214), 22)},
    "summer": {"sky": ((60, 70, 150), (240, 150, 120)), "ground": (96, 168, 84), "ground2": (76, 140, 70), "roof_snow": False, "trees": ((70, 140, 72), (52, 110, 58)), "part": ((255, 236, 120), 16)},
    "autumn": {"sky": ((60, 50, 110), (230, 140, 90)), "ground": (196, 150, 84), "ground2": (168, 122, 66), "roof_snow": False, "trees": ((222, 120, 48), (190, 76, 44)), "part": ((236, 132, 52), 20)},
}


def inside_mask():
    m = Image.new("L", (N, N), 0); ImageDraw.Draw(m).ellipse([CX - R, CY - R, CX + R, CY + R], fill=255); return m


def globe(season="winter", seed=9):
    S = SEASON[season]; r = random.Random(seed)
    im = Image.new("RGB", (N, N)); d = ImageDraw.Draw(im)
    for y in range(N): d.line([(0, y), (N, y)], fill=mix((40, 30, 62), (92, 56, 94), y / N))  # backdrop
    for _ in range(18):
        x, y = r.randrange(N), r.randrange(60)
        if math.hypot(x - CX, y - CY) > R + 3: d.point((x, y), fill=(230, 226, 250))
    # ---- interior scene (drawn full-size, then clipped to the sphere)
    sc = Image.new("RGB", (N, N)); s = ImageDraw.Draw(sc)
    top, bot = S["sky"]
    for y in range(CY - R, CY + R + 1): s.line([(0, y), (N, y)], fill=mix(top, bot, (y - (CY - R)) / (2 * R)))
    if season in ("winter", "autumn"): s.ellipse([82, 26, 92, 36], fill=(250, 244, 220))
    gl = 80  # ground line where houses stand
    # water tower first, set back (legs reach the ground behind the houses)
    leg = (98, 106, 124)
    s.line([(56, 40), (53, gl)], fill=leg); s.line([(71, 40), (74, gl)], fill=leg)
    s.line([(55, 54), (72, 54)], fill=leg); s.line([(54, 66), (73, 66)], fill=leg); s.line([(56, 54), (72, 66)], fill=leg)
    s.rectangle([52, 29, 75, 40], fill=(152, 162, 178)); s.rectangle([69, 29, 75, 40], fill=(126, 136, 152)); s.rectangle([52, 38, 75, 40], fill=(126, 136, 152))
    s.polygon([(50, 29), (63.5, 21), (77, 29)], fill=(118, 128, 144))
    if S["roof_snow"]: s.polygon([(50, 29), (63.5, 21), (63.5, 23), (53, 29)], fill=(250, 250, 255))
    s.rectangle([63, 18, 64, 21], fill=(118, 128, 144)); s.point((63, 17), fill=RED)
    # trees behind houses
    if S["trees"]:
        for tx in (30, 88, 100):
            s.rectangle([tx, gl - 10, tx + 1, gl], fill=(90, 62, 44)); s.ellipse([tx - 7, gl - 24, tx + 8, gl - 8], fill=S["trees"][1]); s.ellipse([tx - 5, gl - 23, tx + 5, gl - 12], fill=S["trees"][0])
    else:
        for tx in (30, 100):
            s.line([(tx, gl), (tx, gl - 16)], fill=(90, 70, 60)); s.line([(tx, gl - 10), (tx - 5, gl - 16)], fill=(90, 70, 60)); s.line([(tx, gl - 8), (tx + 5, gl - 14)], fill=(90, 70, 60))
    # mound-shaped ground following the sphere's curve
    s.ellipse([CX - 58, gl - 6, CX + 58, gl + 50], fill=S["ground2"]); s.ellipse([CX - 54, gl - 4, CX + 54, gl + 44], fill=S["ground"])
    # houses on the mound (in front of the tower legs)
    for hx, wall, roof in ((34, BUTTER, TEAL), (56, (236, 150, 140), (90, 100, 150)), (78, MINT, RED)):
        s.rectangle([hx, gl - 14, hx + 15, gl + 1], fill=wall); s.rectangle([hx + 12, gl - 14, hx + 15, gl + 1], fill=sh(wall, 0.85))
        s.polygon([(hx - 2, gl - 14), (hx + 7.5, gl - 23), (hx + 17, gl - 14)], fill=roof); s.polygon([(hx + 7.5, gl - 23), (hx + 17, gl - 14), (hx + 9, gl - 14)], fill=sh(roof, 0.8))
        if S["roof_snow"]: s.polygon([(hx - 2, gl - 14), (hx + 7.5, gl - 23), (hx + 7.5, gl - 20), (hx + 1, gl - 14)], fill=(250, 250, 255))
        s.rectangle([hx + 3, gl - 10, hx + 7, gl - 6], fill=(255, 214, 120)); s.rectangle([hx + 9, gl - 7, hx + 12, gl + 1], fill=sh(roof, 0.7))
        s.rectangle([hx - 1, gl + 1, hx + 16, gl + 2], fill=S["ground2"])
    # particles (snow / petals / fireflies / leaves)
    pc, n = S["part"]
    for _ in range(n):
        x, y = r.randrange(CX - R + 4, CX + R - 4), r.randrange(CY - R + 6, gl + 6)
        if season == "autumn": s.rectangle([x, y, x + 1, y], fill=pc)
        elif season == "summer": s.point((x, y), fill=pc); s.point((x, y - 1), fill=sh(pc, 0.7))
        else: s.point((x, y), fill=pc)
    im.paste(sc, (0, 0), inside_mask())
    # ---- glass: rim, inner shade, highlights
    d.ellipse([CX - R, CY - R, CX + R, CY + R], outline=(176, 190, 230), width=1)
    d.arc([CX - R + 1, CY - R + 1, CX + R - 1, CY + R - 1], 20, 160, fill=(120, 128, 180), width=2)
    d.arc([CX - R + 5, CY - R + 5, CX + R - 5, CY + R - 5], 190, 232, fill=(244, 246, 255), width=2)
    d.arc([CX - R + 10, CY - R + 10, CX + R - 10, CY + R - 10], 196, 214, fill=(244, 246, 255), width=1)
    d.rectangle([CX + 24, CY - 30, CX + 25, CY - 29], fill=(250, 250, 255))
    # ---- wooden collar that the glass sits in (overlaps the sphere's bottom), then the base
    wood, wood_d, wood_l = (134, 84, 52), (98, 60, 40), (168, 110, 70)
    d.ellipse([CX - 34, 90, CX + 34, 104], fill=wood_d)              # collar top (dark recess)
    d.rectangle([CX - 34, 97, CX + 34, 104], fill=wood)              # collar band
    d.ellipse([CX - 34, 100, CX + 34, 108], fill=wood)
    d.arc([CX - 34, 90, CX + 34, 104], 180, 360, fill=wood_l)        # collar lip highlight
    d.polygon([(CX - 40, 104), (CX + 40, 104), (CX + 47, 120), (CX - 47, 120)], fill=wood)   # base body
    d.polygon([(CX + 24, 104), (CX + 40, 104), (CX + 47, 120), (CX + 28, 120)], fill=wood_d)
    d.line([(CX - 40, 104), (CX + 40, 104)], fill=wood_l)
    d.rectangle([CX - 50, 120, CX + 50, 125], fill=(78, 48, 34)); d.line([(CX - 50, 120), (CX + 50, 120)], fill=wood_d)  # plinth
    d.rectangle([CX - 30, 107, CX + 30, 117], fill=INK); d.rectangle([CX - 29, 108, CX + 29, 116], fill=BUTTER)              # nameplate
    return im


def lettering(img):
    """Real-type nameplate text at output resolution."""
    k = img.width / N; d = ImageDraw.Draw(img)
    f = F(COND, int(6.6 * k)); t = "NOBODY'S TOWN"; tw = d.textlength(t, font=f)
    d.text(((img.width - tw) / 2, 108.9 * k), t, font=f, fill=INK)


def render(season="winter", size=800):
    im = globe(season).resize((size, size), Image.NEAREST); lettering(im); return im


if __name__ == "__main__":
    tiles = [render(s, 480) for s in ("winter", "spring", "summer", "autumn")]
    sheet = Image.new("RGB", (960, 960)); [sheet.paste(t, ((i % 2) * 480, (i // 2) * 480)) for i, t in enumerate(tiles)]
    sheet.save("/tmp/globes.png"); render("winter", 800).save("/tmp/globe_winter.png"); print("ok")
