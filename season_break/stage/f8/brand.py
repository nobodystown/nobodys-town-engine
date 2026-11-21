"""Nobody's Town brand concepts: pixel-art logo marks + wordmarks. Original designs drawn in code."""
import math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

INK = (38, 28, 40); CREAM = (250, 244, 226); RED = (214, 52, 64); TEAL = (64, 190, 196); BUTTER = (246, 216, 120); MINT = (160, 222, 196)
NIGHT_T, NIGHT_B = (24, 22, 56), (96, 52, 92)
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"; COND = "/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyreheroscn-bold.otf"
SCRIPT = "/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyrechorus-mediumitalic.otf"; PIX = "/usr/share/fonts/opentype/unifont/unifont.otf"
POP = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
F = lambda p, s: ImageFont.truetype(p, s)
def sh(c, k): return tuple(max(0, min(255, int(v * k))) for v in c)
def mix(a, b, u): return tuple(int(a[i] * (1 - u) + b[i] * u) for i in range(3))


def night(w, h, stars=40, seed=3):
    im = Image.new("RGB", (w, h)); d = ImageDraw.Draw(im)
    for y in range(h): d.line([(0, y), (w, y)], fill=mix(NIGHT_T, NIGHT_B, y / h))
    r = random.Random(seed)
    for _ in range(stars): d.point((r.randrange(w), r.randrange(int(h * 0.6))), fill=(240, 236, 255))
    return im, d


# ---------------------------------------------------------------- A: the welcome sign
def mark_sign(n=96):
    im, d = night(n, n, 30)
    d.rectangle([20, 70, 23, 92], fill=(70, 50, 40)); d.rectangle([72, 70, 75, 92], fill=(70, 50, 40))
    d.rectangle([0, 88, n, n], fill=(40, 60, 50))
    d.rectangle([8, 22, 87, 74], fill=INK); d.rectangle([10, 24, 85, 72], fill=TEAL); d.rectangle([12, 26, 83, 70], fill=sh(TEAL, 0.9))
    d.rectangle([10, 24, 85, 31], fill=RED)
    for x in range(14, 84, 6): d.point((x, 27), fill=BUTTER)  # marquee bulbs
    d.polygon([(30, 22), (48, 8), (66, 22)], fill=RED); d.polygon([(34, 22), (48, 11), (62, 22)], fill=BUTTER)
    return im


def lettering_sign(im, scale):
    d = ImageDraw.Draw(im); W = im.width
    f1 = F(SCRIPT, int(13 * scale)); t = "Welcome to"; d.text(((W - d.textlength(t, font=f1)) / 2, 30.5 * scale), t, font=f1, fill=CREAM)
    f2 = F(COND, int(12.5 * scale)); t = "NOBODY'S TOWN"; tw = d.textlength(t, font=f2)
    d.text(((W - tw) / 2 + scale, 44 * scale + scale), t, font=f2, fill=INK); d.text(((W - tw) / 2, 44 * scale), t, font=f2, fill=CREAM)
    f3 = F(COND, int(8 * scale)); t = "POP. ?"; d.text(((W - d.textlength(t, font=f3)) / 2, 61 * scale), t, font=f3, fill=BUTTER)


# ---------------------------------------------------------------- B: the water tower
def mark_tower(n=96):
    im, d = night(n, n, 40, 5)
    d.ellipse([60, 8, 74, 22], fill=(250, 244, 220))
    d.rectangle([0, 84, n, n], fill=(36, 44, 60))
    for x in range(0, n, 10): d.rectangle([x, 76 - (x * 7) % 9, x + 8, 84], fill=(30, 26, 46))
    for k in (24, 44, 52, 72):
        d.line([(k, 48), (k + (48 - k) * 0.25, 90)], fill=(110, 100, 120), width=2)
    d.line([(26, 66), (70, 66)], fill=(110, 100, 120), width=1); d.line([(30, 78), (66, 78)], fill=(110, 100, 120), width=1)
    d.rectangle([18, 24, 78, 50], fill=(150, 160, 175)); d.rectangle([18, 24, 78, 27], fill=(120, 130, 145)); d.rectangle([18, 47, 78, 50], fill=(120, 130, 145))
    d.polygon([(16, 24), (48, 8), (80, 24)], fill=(110, 120, 135)); d.rectangle([46, 4, 49, 9], fill=(110, 120, 135)); d.point((47, 3), fill=RED)
    d.rectangle([70, 24, 78, 50], fill=(128, 138, 152))
    return im


def lettering_tower(im, scale):
    d = ImageDraw.Draw(im); W = im.width
    f = F(COND, int(10.5 * scale)); t = "NOBODY'S"; d.text(((W - d.textlength(t, font=f)) / 2 - 2 * scale, 26 * scale), t, font=f, fill=INK)
    f2 = F(COND, int(8 * scale)); t = "TOWN"; d.text(((W - d.textlength(t, font=f2)) / 2 - 2 * scale, 37 * scale), t, font=f2, fill=RED)


# ---------------------------------------------------------------- C: the snow globe
def mark_globe(n=96):
    im = Image.new("RGB", (n, n), (40, 32, 58)); d = ImageDraw.Draw(im)
    for y in range(n): d.line([(0, y), (n, y)], fill=mix((44, 34, 66), (90, 56, 92), y / n))
    cx, cy, R = 48, 44, 34
    glass = Image.new("RGBA", (n, n), (0, 0, 0, 0)); g = ImageDraw.Draw(glass)
    g.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(40, 46, 110, 255))
    for y in range(cy - R, cy + R):
        u = (y - (cy - R)) / (2 * R); g.line([(cx - R, y), (cx + R, y)], fill=mix((30, 34, 90), (110, 70, 120), u) + (255,))
    mask = Image.new("L", (n, n), 0); ImageDraw.Draw(mask).ellipse([cx - R, cy - R, cx + R, cy + R], fill=255)
    gd = ImageDraw.Draw(glass)
    gd.rectangle([0, 58, n, 80], fill=(236, 240, 248, 255))  # snowy ground
    for hx, wall, roof in ((24, BUTTER, TEAL), (44, (236, 150, 140), (90, 100, 150)), (60, MINT, RED)):
        gd.rectangle([hx, 48, hx + 12, 60], fill=wall + (255,)); gd.polygon([(hx - 2, 48), (hx + 6, 41), (hx + 14, 48)], fill=roof + (255,))
        gd.polygon([(hx - 2, 48), (hx + 6, 41), (hx + 6, 43), (hx, 48)], fill=(250, 250, 255, 255))
        gd.rectangle([hx + 3, 51, hx + 6, 54], fill=(255, 214, 120, 255)); gd.rectangle([hx + 8, 54, hx + 10, 60], fill=sh(roof, 0.7) + (255,))
    gd.rectangle([40, 32, 41, 50], fill=(110, 120, 135, 255)); gd.rectangle([50, 32, 51, 50], fill=(110, 120, 135, 255)); gd.rectangle([37, 22, 54, 32], fill=(150, 160, 175, 255)); gd.polygon([(36, 22), (45, 16), (55, 22)], fill=(120, 130, 145, 255))
    r = random.Random(9)
    for _ in range(26): x, y = r.randrange(cx - R, cx + R), r.randrange(cy - R, 58); gd.point((x, y), fill=(255, 255, 255, 255))
    im.paste(glass, (0, 0), Image.composite(glass.split()[3], Image.new("L", (n, n), 0), mask))
    d.arc([cx - R, cy - R, cx + R, cy + R], 0, 360, fill=(200, 210, 240), width=2)
    d.arc([cx - R + 6, cy - R + 6, cx + R - 6, cy + R - 6], 200, 250, fill=(240, 244, 255), width=2)
    d.polygon([(cx - R + 2, cy + 26), (cx + R - 2, cy + 26), (cx + R + 6, cy + 44), (cx - R - 6, cy + 44)], fill=(130, 80, 50))
    d.rectangle([cx - R - 6, cy + 44, cx + R + 6, cy + 48], fill=(100, 60, 40)); d.rectangle([cx - R + 6, cy + 32, cx + R - 6, cy + 38], fill=BUTTER)
    return im


def lettering_globe(im, scale):
    d = ImageDraw.Draw(im); W = im.width
    f = F(COND, int(5.6 * scale)); t = "NOBODY'S TOWN"; d.text(((W - d.textlength(t, font=f)) / 2, 75.6 * scale), t, font=f, fill=INK)


def avatar(mark, letter, size=800):
    big = mark().resize((size, size), Image.NEAREST); letter(big, size / 96)
    m = Image.new("L", (size, size), 0); ImageDraw.Draw(m).ellipse([0, 0, size - 1, size - 1], fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0)); out.paste(big, (0, 0), m); return big, out


def wordmark(icon_big, w=1100, h=300, tagline="AN AI TOWN. NOBODY RUNS IT."):
    im = Image.new("RGB", (w, h), CREAM); d = ImageDraw.Draw(im)
    ic = icon_big.resize((h - 40, h - 40), Image.NEAREST); m = Image.new("L", ic.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, ic.width - 1, ic.height - 1], 30, fill=255)
    im.paste(ic, (20, 20), m)
    f = F(SERIF, 66); d.text((h + 10 + 4, 70 + 4), "NOBODY'S TOWN", font=f, fill=sh(RED, 0.7)); d.text((h + 10, 70), "NOBODY'S TOWN", font=f, fill=INK)
    d.text((h + 14, 170), tagline, font=F(POP, 30), fill=RED)
    return im


if __name__ == "__main__":
    concepts = [("A · WELCOME SIGN", mark_sign, lettering_sign, "1950s roadside sign. 'POP. ?' = nobody knows what this town becomes."),
                ("B · WATER TOWER", mark_tower, lettering_tower, "Every small town's landmark. Reads at any size, any geography."),
                ("C · SNOW GLOBE", mark_globe, lettering_globe, "A whole town under glass. You watch; nobody touches it.")]
    sheet = Image.new("RGB", (1800, 1260), (30, 26, 40)); d = ImageDraw.Draw(sheet)
    d.text((40, 24), "NOBODY'S TOWN · LOGO CONCEPTS", font=F(POP, 40), fill=CREAM)
    for i, (name, mk, lt, note) in enumerate(concepts):
        x = 40 + i * 590
        big, circ = avatar(mk, lt, 520); sheet.paste(circ, (x, 100), circ)
        small = circ.resize((88, 88), Image.LANCZOS); sheet.paste(small, (x, 640), small)
        tiny = circ.resize((40, 40), Image.LANCZOS); sheet.paste(tiny, (x + 110, 664), tiny)
        d.text((x + 170, 660), "actual size on YouTube", font=F(POP, 18), fill=(190, 180, 200))
        d.text((x, 760), name, font=F(POP, 30), fill=BUTTER)
        import textwrap
        for k, row in enumerate(textwrap.wrap(note, 46)[:3]): d.text((x, 805 + k * 30), row, font=F(POP, 20), fill=CREAM)
        wm = wordmark(big, 1100, 300).resize((550, 150), Image.LANCZOS); sheet.paste(wm, (x, 920))
        big.save(f"/home/claude/town/logo_{'ABC'[i]}.png"); circ.save(f"/home/claude/town/avatar_{'ABC'[i]}.png")
    sheet.save("/home/claude/town/logo_concepts.png"); print("ok")
