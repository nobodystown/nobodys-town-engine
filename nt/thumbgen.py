"""Episode thumbnails (Nov 21): the recipe that scored 83-86 on vidIQ (the first try with a face + 4 words scored 24).
Whole town at night filling the frame (overview crop), the season's falling specks (snow in winter, blossom in spring,
leaves in fall, fireflies in summer), one warm glowing spot with a red ring + arrow, and a short TRUE question in huge type.
Keep it truthful: the season must be the episode's season, the question must be one the episode really raises.
  python3 -m nt.thumbgen <episode_dir> "<LINE 1>" "<LINE 2>" <out.jpg> [--x 752 --y 415] [--season spring]
--x/--y: the spot to ring, in the overview's own 1280x720 coordinates (752,415 = the boatyard). Edit layer only."""
import json, os, random, sys
from PIL import Image, ImageDraw, ImageFilter
from . import scenes
from .brand import F, COND, INK, CREAM, BUTTER

W, H = 1280, 720
CROP = (300, 100, 1090, 545)
SPECK = {"winter": (240, 244, 255), "spring": (255, 190, 215), "summer": (255, 236, 140), "autumn": (235, 150, 70), "fall": (235, 150, 70)}


def make(ep_dir, line1, line2, out, x=752, y=415, season=None, seed=3):
    gen = json.load(open(os.path.join(ep_dir, "world.json")))
    sn = [json.loads(l) for l in open(os.path.join(ep_dir, "snapshots.jsonl"))]
    s = sn[len(sn) // 2]; season = season or s["season"]
    ov = scenes.overview(s, gen["seed"], gen, tod="night", season=season).crop(CROP).resize((W, H), Image.NEAREST)
    bx, by = int((x - CROP[0]) * W / (CROP[2] - CROP[0])), int((y - CROP[1]) * H / (CROP[3] - CROP[1]))
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(g).ellipse((bx - 260, by - 200, bx + 260, by + 200), fill=(255, 150, 60, 150))
    im = Image.alpha_composite(ov.convert("RGBA"), g.filter(ImageFilter.GaussianBlur(90))).convert("RGB")
    d = ImageDraw.Draw(im); r = random.Random(seed); col = SPECK.get(season, SPECK["winter"])
    for _ in range(260):
        px, py, z = r.randrange(W), r.randrange(H), r.choice((4, 6, 8)); d.rectangle([px, py, px + z, py + z], fill=col)
    rx, ry = 190, 130
    for k in range(10): d.ellipse([bx - rx - k, by - ry - k, bx + rx + k, by + ry + k], outline=(230, 40, 40))
    d.line([(bx + rx + 150, by - ry - 150), (bx + rx + 25, by - ry + 10)], fill=(230, 40, 40), width=22)
    d.polygon([(bx + rx + 5, by - ry + 30), (bx + rx + 70, by - ry - 10), (bx + rx + 35, by - ry - 55)], fill=(230, 40, 40))
    big = 190 if len(line1) <= 5 else 160
    d.text((40, 20), line1, font=F(COND, big), fill=BUTTER, stroke_width=12, stroke_fill=INK)
    d.text((40, 20 + big + 10), line2, font=F(COND, 160), fill=CREAM, stroke_width=12, stroke_fill=INK)
    im.save(out, quality=95)
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    opt = lambda k, dflt: type(dflt)(a[a.index(k) + 1]) if k in a else dflt
    print(make(a[0], a[1], a[2], a[3], opt("--x", 752), opt("--y", 415), opt("--season", "") or None))
