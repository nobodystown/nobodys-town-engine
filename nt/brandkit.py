"""Nobody's Town brand kit. Profile = snow globe (C). Signature = welcome sign (A).
Outputs to ~/nobodys_town/brand/: avatar, banner, watermark, end screen, thumbnail template sample."""
import os, random
from PIL import Image, ImageDraw, ImageFilter
from .brand import (mark_globe, lettering_globe, mark_sign, F, SERIF, COND, SCRIPT, POP, INK, CREAM, RED, TEAL, BUTTER, MINT, NIGHT_T, NIGHT_B, sh, mix)

OUT = "/home/claude/nobodys_town/brand"
PALETTE = {"Ink": INK, "Cream": CREAM, "Cherry": RED, "Teal": TEAL, "Butter": BUTTER, "Mint": MINT, "Night": NIGHT_T, "Dusk plum": NIGHT_B}


def sign(w, pop="?", town=None, glow=True):
    """The welcome sign at any width (crisp pixel board + real type). pop: '?' or a real number."""
    s = w / 96; h = int(w * 0.62)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    R = lambda x0, y0, x1, y1, c: d.rectangle([x0 * s, y0 * s, x1 * s, y1 * s], fill=c)
    R(20, 48, 23, 60, (70, 50, 40)); R(72, 48, 75, 60, (70, 50, 40))
    R(8, 4, 87, 52, INK); R(10, 6, 85, 50, TEAL); R(12, 8, 83, 48, sh(TEAL, 0.9)); R(10, 6, 85, 13, RED)
    for x in range(14, 84, 6): R(x, 9, x, 9.8, BUTTER)
    f1 = F(SCRIPT, int(12 * s)); t = "Welcome to"; d.text(((w - d.textlength(t, font=f1)) / 2, 12.5 * s), t, font=f1, fill=CREAM)
    t = "NOBODY'S TOWN"; sz = int(11.2 * s); f2 = F(COND, sz)
    while d.textlength(t, font=f2) > 69 * s and sz > 8: sz -= 1; f2 = F(COND, sz)  # keep the wordmark inside the board (Nov 20: it ran past the edges)
    tw = d.textlength(t, font=f2)
    d.text(((w - tw) / 2 + s, 25 * s + s), t, font=f2, fill=INK); d.text(((w - tw) / 2, 25 * s), t, font=f2, fill=CREAM)
    f3 = F(COND, int(7.5 * s)); t = (town.upper() + "  ·  " if town else "") + f"POP. {pop}"
    while d.textlength(t, font=f3) > 69 * s and f3.size > 8: f3 = F(COND, f3.size - 1)  # long town names
    d.text(((w - d.textlength(t, font=f3)) / 2, 39.5 * s), t, font=f3, fill=BUTTER)
    if glow:
        g = im.filter(ImageFilter.GaussianBlur(int(4 * s))); base = Image.new("RGBA", im.size, (0, 0, 0, 0))
        base.alpha_composite(Image.eval(g, lambda v: v // 3)); base.alpha_composite(im); im = base
    return im


def night_scene(w, h, seed=4):
    im = Image.new("RGB", (w, h)); d = ImageDraw.Draw(im)
    for y in range(h): d.line([(0, y), (w, y)], fill=mix(NIGHT_T, NIGHT_B, y / h))
    r = random.Random(seed)
    for _ in range(w * h // 9000): d.point((r.randrange(w), r.randrange(int(h * 0.65))), fill=(240, 236, 255))
    u = max(4, w // 320)
    for k in range(0, w, 34 * u):  # pixel rooftops with lit windows
        hh = (30 + (k * 13) % 26) * u; x = k + r.randrange(0, 6 * u)
        d.rectangle([x, h - hh, x + 26 * u, h], fill=(22, 18, 38)); d.polygon([(x - 2 * u, h - hh), (x + 13 * u, h - hh - 12 * u), (x + 28 * u, h - hh)], fill=(22, 18, 38))
        for wy in range(h - hh + 6 * u, h - 6 * u, 10 * u):
            for wx in (x + 4 * u, x + 15 * u):
                if r.random() < 0.5: d.rectangle([wx, wy, wx + 6 * u, wy + 5 * u], fill=(255, 210, 120))
    return im


def avatar(size=800, season="winter"):
    from .globe import render
    return render(season, size)


def banner():
    W, H = 2560, 1440; im = night_scene(W, H)
    # safe area for all devices: centered 1546x423
    sx, sy = (W - 1546) // 2, (H - 423) // 2
    s = sign(560, "?"); im.paste(s, (sx + 10, sy + (423 - s.height) // 2 - 10), s)
    d = ImageDraw.Draw(im)
    d.text((sx + 620, sy + 70), "AN AI TOWN.", font=F(SERIF, 92), fill=CREAM)
    d.text((sx + 620, sy + 175), "NOBODY RUNS IT.", font=F(SERIF, 92), fill=BUTTER)
    d.text((sx + 624, sy + 300), "New episode every week  ·  Real residents. Nothing scripted.", font=F(POP, 34), fill=(230, 220, 240))
    return im


def watermark(size=150, season="winter"):
    a = avatar(size * 4, season).resize((size, size), Image.LANCZOS)
    m = Image.new("L", (size, size), 0); ImageDraw.Draw(m).ellipse([0, 0, size - 1, size - 1], fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0)); out.paste(a, (0, 0), m); return out


def end_screen(season="winter"):
    W, H = 1920, 1080; im = night_scene(W, H, 7); d = ImageDraw.Draw(im)
    t = "WHAT HAPPENS NEXT IS UP TO THEM."; f = F(SERIF, 64); d.text(((W - d.textlength(t, font=f)) / 2, 90), t, font=f, fill=CREAM)
    # YouTube end-screen element zones (video slots + subscribe), drawn as framed placeholders
    for x in (160, 1000):
        d.rounded_rectangle([x, 300, x + 760, 728], 18, outline=BUTTER, width=6)
    av = watermark(300, season); im.paste(av, ((W - 300) // 2, 760), av)
    return im


def thumbnail(scene_img, portrait_img, headline, episode=None, sub=None):
    """Template: real scene, a big resident face with emotion, 2-4 word headline, episode badge."""
    W, H = 1280, 720; im = scene_img.resize((W, H)).convert("RGB")
    im = Image.blend(im, Image.new("RGB", (W, H), (20, 12, 30)), 0.25)
    d = ImageDraw.Draw(im)
    p = portrait_img.resize((480, 480), Image.NEAREST); d.rectangle([W - 520, H - 520, W - 20, H - 20], fill=INK); im.paste(p, (W - 510, H - 510))
    f = F(COND, 150); words = headline.upper().split(); rows, cur = [], ""
    for w_ in words:
        if d.textlength((cur + " " + w_).strip(), font=f) > 640: rows.append(cur); cur = w_
        else: cur = (cur + " " + w_).strip()
    rows.append(cur)
    y = 60
    for k, row in enumerate(rows[:3]):
        d.text((48 + 6, y + 6), row, font=f, fill=INK); d.text((48, y), row, font=f, fill=BUTTER if k == 0 else CREAM); y += 150
    if sub: d.text((52, y + 10), sub, font=F(POP, 40), fill=CREAM, stroke_width=4, stroke_fill=INK)
    if episode:
        b = " · ".join(episode.split(" · ")[:2]) if isinstance(episode, str) else f"EP {episode}"; fb = F(POP, 40); bw = d.textlength(b, font=fb)
        d.rounded_rectangle([40, H - 100, 40 + bw + 40, H - 36], 12, fill=RED); d.text((60, H - 96), b, font=fb, fill=CREAM)
    wm = watermark(110); im.paste(wm, (W - 140, 20), wm)
    return im


def title_card(town, episode, title, pop, premise=None):
    """Episode title card: the welcome sign with the town's REAL population."""
    W, H = 1280, 720; im = night_scene(W, H, 11); d = ImageDraw.Draw(im)
    s = sign(560, pop, town); im.paste(s, ((W - s.width) // 2, 70), s)
    ep = episode if isinstance(episode, str) else f"EPISODE {episode}"; f = F(POP, 36)  # quarterly parts carry a label: "1950 · PART 1 · WINTER"
    if isinstance(episode, str): title = title.split(" | ")[0]  # the part suffix is already on the label line; d.text(((W - d.textlength(ep, font=f)) / 2, 500), ep, font=f, fill=BUTTER)
    # the title always fits: shrink to fit, wrap to two lines if needed (never runs off the screen)
    size = 44; maxw = W - 160
    while size > 26:
        ft = F(SERIF, size); words = title.split(); rows, cur = [], ""
        for w_ in words:
            if d.textlength((cur + " " + w_).strip(), font=ft) > maxw: rows.append(cur); cur = w_
            else: cur = (cur + " " + w_).strip()
        rows.append(cur)
        if len(rows) <= 2: break
        size -= 2
    band_h = len(rows[:2]) * (size + 10) + (52 if premise else 14)
    band = Image.new("RGBA", (W, band_h + 80), (16, 12, 30, 190)); im.paste(band, (0, 488), band); d = ImageDraw.Draw(im)
    d.text(((W - d.textlength(ep, font=f)) / 2, 500), ep, font=f, fill=BUTTER)
    for i, row in enumerate(rows[:2]): d.text(((W - d.textlength(row, font=ft)) / 2, 552 + i * (size + 10)), row, font=ft, fill=CREAM)
    if premise:
        fp = F(POP, 22); d.text(((W - d.textlength(premise, font=fp)) / 2, 552 + len(rows[:2]) * (size + 10) + 14), premise, font=fp, fill=(200, 190, 220))
    return im
