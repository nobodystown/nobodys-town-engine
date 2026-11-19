"""On-screen live data: the compact corner Town Board (+ its news line) and the Shorts strip.
Every number shown is read straight from the simulation snapshot for the day on screen. Nothing is typed in by hand.
  board_state(snap)                      -> dict of true values for that day
  town_board(state, town, delta, news)   -> RGBA panel, top-left; shown on establishing shots only, hidden during conversations
  board_strip(state, town)               -> RGBA one-line strip (Shorts)
Weather is never on the board: it stays in the picture, in the background.
Big news has no separate bar: it appears briefly on the board's bottom line."""
import datetime as dt
from PIL import Image, ImageDraw, ImageFilter
from .art import font, FB, FR, INK, CREAM, RED, TEAL, BUTTER, sh

BOARD_W, BOARD_H = 214, 94          # about two-thirds of the old 312x138
NEWS_H = 30                         # height of the news tab under the board
NEWS_MAX_W = 620                    # the tab may run wider than the board so the line stays readable
BOARD_XY = (20, 20)
GREEN = (96, 200, 120)
BOARD_BG = (22, 66, 72)


def population(snap):
    return sum(1 for p in snap["people"].values() if p["alive"] and not p["offtown"])


def board_state(snap, slot=None):
    """True values for the day on screen. snap is the end-of-day snapshot the engine wrote."""
    return {"day": snap["day"] + 1, "date": snap["date"], "pop": population(snap), "treasury": int(round(snap["town"]["treasury"]))}


def deltas(prev, cur):
    """Which tracked numbers changed since the last board the viewer saw."""
    if not prev: return {}
    out = {}
    for k in ("pop", "treasury"):
        if prev.get(k) is not None and cur.get(k) is not None and cur[k] != prev[k]: out[k] = cur[k] - prev[k]
    return out


def _date_label(iso):
    d = dt.date.fromisoformat(iso); return d.strftime("%b %d, %Y").replace(" 0", " ").upper()


def _fit(d, text, size, width, path=FB):
    f = font(path, size)
    while d.textlength(text, font=f) > width and size > 9: size -= 1; f = font(path, size)
    if d.textlength(text, font=f) > width:
        while text and d.textlength(text + "…", font=f) > width: text = text[:-1]
        text = text.rstrip() + "…"
    return text, f


def town_board(st, town, delta=None, news=None):
    """delta: {'pop': +1, 'treasury': -40} for values that just changed.
    news: short text shown on a tab hanging from the board's bottom edge (wider than the board so it can be read), or None."""
    delta = delta or {}
    W, H, pad = BOARD_W, BOARD_H, 8
    tmp = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    if news: ntxt, nf = _fit(tmp, news, 16, NEWS_MAX_W - 24); NW = int(tmp.textlength(ntxt, font=nf)) + 24
    else: NW = 0
    TW = max(W, NW); TH = H + (NEWS_H if news else 0)
    im = Image.new("RGBA", (TW + 10, TH + 10), (0, 0, 0, 0))
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(shadow); sd.rounded_rectangle([5, 6, W + 5, H + 6], 10, fill=(0, 0, 0, 100))
    if news: sd.rounded_rectangle([5, H + 2, NW + 5, TH + 6], 8, fill=(0, 0, 0, 100))
    im.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(3)))
    d = ImageDraw.Draw(im)
    if news:  # the news tab, tucked under the board
        d.rounded_rectangle([0, H - 8, NW, TH], 8, fill=RED + (245,), outline=INK, width=3)
        d.text((12, H + 2), ntxt, font=nf, fill=CREAM)
    d.rounded_rectangle([0, 0, W, H], 10, fill=BOARD_BG + (240,), outline=INK, width=3)
    d.rounded_rectangle([3, 3, W - 3, 21], 7, fill=RED)
    for x in range(10, W - 6, 11): d.ellipse([x, 5, x + 2, 7], fill=BUTTER)  # marquee bulbs, like the welcome sign
    name, fh = _fit(d, town.upper(), 12, W - 16); d.text(((W - d.textlength(name, font=fh)) / 2, 7), name, font=fh, fill=CREAM)
    # the date, with the year big: as the decades pass, the year is part of the story (Nov 18: the day count was dropped, it meant nothing to viewers)
    dd = dt.date.fromisoformat(st["date"]); md = dd.strftime("%B %d").replace(" 0", " ").upper(); yr = str(dd.year)
    fy = font(FB, 17); d.text((W - pad - d.textlength(yr, font=fy), 21), yr, font=fy, fill=BUTTER); d.text((pad + 1, 25), md, font=font(FR, 12), fill=(230, 236, 230))
    f_lab = font(FB, 9); fv = font(FB, 21)
    def cell(x, label, value, key):
        d.text((x, 42), label, font=f_lab, fill=(170, 210, 206))
        hot = key in delta; d.text((x, 52), value, font=fv, fill=BUTTER if hot else CREAM)
        if hot:
            v = delta[key]; badge = (f"+{v:,}" if v > 0 else f"{v:,}") if key == "pop" else (f"+${v:,}" if v > 0 else f"-${abs(v):,}")
            fb = font(FB, 10); bx = x + d.textlength(value, font=fv) + 5; bw = d.textlength(badge, font=fb) + 8
            d.rounded_rectangle([bx, 58, bx + bw, 73], 6, fill=GREEN if v > 0 else RED, outline=INK, width=2); d.text((bx + 4, 59), badge, font=fb, fill=INK)
    cell(pad + 1, "POPULATION", f"{st['pop']}", "pop")
    cell(W // 2 + 4, "TREASURY", f"${st['treasury']:,}", "treasury")
    return im


def board_strip(st, town):
    """Compact one-line version for vertical Shorts."""
    f = font(FB, 30); txt = f"{st['date'][:4]}  ·  POP. {st['pop']}  ·  ${st['treasury']:,}"
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10))); w = int(tmp.textlength(txt, font=f)) + 36
    im = Image.new("RGBA", (w, 56), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, 55], 14, fill=BOARD_BG + (255,), outline=INK, width=4)
    d.text((18, 9), txt, font=f, fill=CREAM)
    return im


def news_text(e):
    """First sentence of the real event text, short enough for the board line."""
    t = (e.get("text") or "").strip()
    first = t.split(". ")[0].rstrip(".")
    return first + "."


def is_news(e):
    """Big PUBLIC news the town would actually hear about. Never sensitive. Never weather unless it hurt or killed people."""
    if not e.get("public") or e.get("sensitive") or e.get("importance", 0) < 6: return False
    if e["kind"] == "disaster": return ("Hurt:" in e.get("text", "") or "killed" in e.get("text", "")) and e.get("data", {}).get("severity") == "severe"
    return e["kind"] not in ("weather_season", "weather_event", "taxes", "opportunity")
