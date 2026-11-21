"""Vertical Shorts (1080x1920) built from the real conversations the editor flagged. Hook on top, scene in the middle, the line below.
Plan format: plan["shorts"] = [{"dialogue_index": i, "lines": [{"n": k, "keep": "<exact words>"}], "hook": "..."}]
usage: python3 -m nt.shorts <run_dir> <world.json> [episode_no]"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter
from . import scenes, overlays
from .art import font, FB, FR, INK, CREAM, BUTTER, OW, OH
from .assemble import expr_of, PLACE_KIND

VW, VH = 1080, 1920
STRIP_XY = (30, 490)  # inside the scene band, top-left: clear of the hook text and of the Shorts buttons (right side, lower half)


def frame_vertical(scene_img, hook, town, dlg=None, board=None, cap=None):
    bg = scene_img.resize((int(VH * 16 / 9), VH)).crop(((int(VH * 16 / 9) - VW) // 2, 0, (int(VH * 16 / 9) - VW) // 2 + VW, VH)).filter(ImageFilter.GaussianBlur(28))
    bg = Image.blend(bg, Image.new("RGB", (VW, VH), (20, 14, 26)), 0.45)
    crop = scene_img.crop((int(OW * 0.17), 0, int(OW * 0.83), OH)); mid = crop.resize((VW, int(VW * crop.height / crop.width)), Image.NEAREST); bg.paste(mid, (0, 470))
    if board: strip = overlays.board_strip(board, town); bg.paste(strip, STRIP_XY, strip)
    d = ImageDraw.Draw(bg); f = font(FB, 64)
    for k, r in enumerate(scenes.wrap(d, hook.upper(), f, VW - 140)[:3]): tw = d.textlength(r, font=f); d.text(((VW - tw) / 2, 210 + k * 80), r, font=f, fill=BUTTER, stroke_width=5, stroke_fill=(0, 0, 0))
    tag = f"NOBODY'S TOWN · {town.upper()}"; ft = font(FB, 30); d.text(((VW - d.textlength(tag, font=ft)) / 2, 140), tag, font=ft, fill=CREAM)
    if cap:
        fc = font(FB, 52)
        for k, r in enumerate(scenes.wrap(d, cap, fc, VW - 140)[:4]): tw = d.textlength(r, font=fc); d.text(((VW - tw) / 2, 1460 + k * 70), r, font=fc, fill=(255, 255, 255), stroke_width=5, stroke_fill=(0, 0, 0))
    if dlg:
        snap, seed, pid, text, ex = dlg
        d.rounded_rectangle([40, 1440, VW - 40, 1800], 24, fill=(250, 244, 226), outline=INK, width=6)
        por = scenes.portrait(scenes.app_of(snap, pid, seed), ex).resize((220, 220), Image.NEAREST); bg.paste(por, (70, 1500)); d.rectangle([70, 1500, 290, 1720], outline=INK, width=5)
        d.text((320, 1470), snap["people"][str(pid)]["name"].upper(), font=font(FB, 40), fill=(214, 52, 64))
        fd = font(FR, 40)
        for k, r in enumerate(scenes.wrap(d, text, fd, VW - 400)[:5]): d.text((320, 1530 + k * 50), r, font=fd, fill=INK)
    foot = "Every resident is an AI. Nothing scripted."; ff = font(FR, 30); d.text(((VW - d.textlength(foot, font=ff)) / 2, VH - 90), foot, font=ff, fill=(220, 210, 230))
    return bg


def build_short(spec, d, sn, gen, out, fps=24):
    s = sn[min(d["day"], len(sn) - 1)]; seed = gen["seed"]; frames = []; vlines = []; t = 0.0
    board = overlays.board_state(s)
    place = str(d["place"]); hh = int(place.split("_")[1]) if place.startswith("home_") else s["people"][str(d["a"])]["household"]
    pk = "home" if place.startswith("home") else PLACE_KIND.get(place, "home")
    for x in spec.get("lines") or [{"n": k, "keep": d["lines"][k][1]} for k in range(min(4, len(d["lines"])))]:
        k = x["n"]; text = x["keep"]; sp = d["lines"][k][0]
        pid = d["a"] if s["people"][str(d["a"])]["name"] == sp else d["b"]
        img = scenes.interior(s, seed, pk, hh, [d["a"], d["b"]], None, d["slot"], zoom=pid if len(frames) % 2 else None)
        dur = max(2.8, len(text.split()) / 2.8 + 1)
        vlines.append({"start": round(t + 0.2, 2), "role": f"resident:{pid}", "name": s["people"][str(pid)]["name"], "text": text, "max_seconds": round(dur - 0.4, 2)})
        frames.append((frame_vertical(img, spec["hook"], gen["name"], (s, seed, pid, text, expr_of(text)), board), dur)); t += dur
        if t > 55: break
    json.dump(vlines, open(out.replace(".mp4", "_voices.json"), "w"), indent=1)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}", "-r", str(fps), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    for img, dur in frames:
        b = img.tobytes()
        for _ in range(int(dur * fps)): p.stdin.write(b)
    p.stdin.close(); p.wait()
    return round(t, 1)


if __name__ == "__main__":
    run, world = sys.argv[1], sys.argv[2]; epn = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    gen = json.load(open(world)); plan = json.load(open(os.path.join(run, f"episode_{epn}_plan.json")))
    sn = [json.loads(l) for l in open(os.path.join(run, "snapshots.jsonl"))]
    alldl = [json.loads(l) for l in open(os.path.join(run, "dialogues.jsonl"))]
    out = []
    for i, spc in enumerate(plan.get("shorts", [])[:5]):
        di = spc.get("dialogue_index")
        if di is None or not (0 <= di < len(alldl)): continue
        o = os.path.join(run, f"episode_{epn}_short_{i + 1}.mp4"); dur = build_short(spc, alldl[di], sn, gen, o)
        out.append({"file": o, "seconds": dur, "hook": spc["hook"]})
    print(json.dumps(out, indent=1))
