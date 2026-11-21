"""Brand guide PDF for Nobody's Town."""
import os
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .brandkit import OUT, PALETTE

pdfmetrics.registerFont(TTFont("Serif", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Pop", "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"))
pdfmetrics.registerFont(TTFont("PopR", "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf"))
W, H = landscape(letter)
INK = (38/255, 28/255, 40/255); CREAM = (250/255, 244/255, 226/255); RED = (214/255, 52/255, 64/255)


def page(c, title, bg=CREAM):
    c.setFillColorRGB(*bg); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColorRGB(*INK); c.setFont("Serif", 30); c.drawString(48, H - 64, title)
    c.setStrokeColorRGB(*INK); c.setLineWidth(2); c.line(48, H - 76, W - 48, H - 76)
    c.setFont("PopR", 9); c.drawRightString(W - 48, 24, "Nobody's Town · Brand Guide v1 · Nov 2026")


def text(c, x, y, lines, size=12, font="PopR", lead=17, color=INK):
    c.setFillColorRGB(*color); c.setFont(font, size)
    for i, l in enumerate(lines): c.drawString(x, y - i * lead, l)


def build(path):
    c = canvas.Canvas(path, pagesize=landscape(letter))
    # cover
    c.drawImage(ImageReader(os.path.join(OUT, "banner_2560x1440.png")), 0, 0, W, H, preserveAspectRatio=False)
    c.setFillColorRGB(1, 1, 1); c.setFont("Pop", 14); c.drawString(48, H - 40, "BRAND GUIDE · v1 · November 2026"); c.showPage()
    # 1 the idea
    page(c, "The idea")
    text(c, 48, H - 120, ["Nobody's Town is a real, unscripted AI town that lives its own life.", "Every resident is an AI that makes its own choices. Nobody steers what happens: not us, not the viewers.",
                          "", "Brand promise: REAL. UNSTAGED. ONGOING.", "", "Tagline: \"An AI town. Nobody runs it.\"",
                          "End line: \"What happens next is up to them.\"", "", "Voice: a warm, wry 1950s newsreel announcer. Plain words, short sentences, concrete details.",
                          "Never: hype words, invented drama, clickbait that misrepresents what happened,", "or claims we can't prove from the sim."], 13, lead=22); c.showPage()
    # 2 logos
    page(c, "Logos")
    c.drawImage(ImageReader(os.path.join(OUT, "profile_800.png")), 60, 170, 280, 280)
    c.drawImage(ImageReader(os.path.join(OUT, "welcome_sign.png")), 400, 220, 340, 211, mask="auto")
    text(c, 60, 150, ["PROFILE MARK · the snow globe", "A whole town under glass: you watch,", "nobody touches it. Use for avatars,", "watermarks, favicons, small spaces."], 11)
    text(c, 400, 150, ["SIGNATURE · the welcome sign", "Banner, title cards, merch. On title cards", "\"POP.\" shows the town's REAL population;", "on brand pieces it stays \"POP. ?\""], 11)
    text(c, 60, 70, ["Don't: recolor, stretch, add outlines/effects, put photos inside the globe, or set the sign on busy backgrounds."], 11, color=RED); c.showPage()
    # 3 palette
    page(c, "Color")
    for i, (name, rgb) in enumerate(PALETTE.items()):
        x = 60 + (i % 4) * 175; y = H - 250 - (i // 4) * 170
        c.setFillColorRGB(*[v / 255 for v in rgb]); c.setStrokeColorRGB(*INK); c.setLineWidth(1); c.roundRect(x, y, 150, 110, 10, fill=1, stroke=1)
        hx = "#%02X%02X%02X" % rgb; text(c, x, y - 18, [name, hx], 11)
    text(c, 60, 60, ["Pastels for the town by day; night and dusk plum for brand surfaces. Cherry is for emphasis only (badges, losses, warnings)."], 11); c.showPage()
    # 4 type
    page(c, "Type")
    c.setFillColorRGB(*INK); c.setFont("Serif", 40); c.drawString(60, H - 150, "NOBODY'S TOWN")
    text(c, 60, H - 175, ["Headline serif: DejaVu Serif Bold — titles, Gazette, Ledger"], 11)
    c.setFont("Pop", 28); c.drawString(60, H - 245, "Real residents. Nothing scripted.")
    text(c, 60, H - 268, ["UI + captions: Poppins Bold / Regular — captions, labels, website"], 11)
    text(c, 60, H - 330, ["Sign lettering: TeX Gyre Heros Condensed Bold (thumbnail headlines, signs)", "Accent script: TeX Gyre Chorus (\"Welcome to\" only)",
                          "All type is set in real fonts at full resolution; only the art is pixelated."], 11); c.showPage()
    # 5 thumbnails + video
    page(c, "Thumbnails & video")
    tp = "/home/claude/nobodys_town/brand/thumb_sample.png"
    if os.path.exists(tp): c.drawImage(ImageReader(tp), 60, 230, 384, 216)
    text(c, 470, H - 120, ["Thumbnail rules:", "• A real moment from the episode", "• One resident's face, big, real emotion",
                           "• 2-4 words, condensed caps", "• Episode badge bottom-left", "• Globe watermark top-right", "• Words must be true to what happened",
                           "", "Video:", "• Cold open, then the welcome-sign card", "• Ends with the Ledger and", "   \"What happens next is up to them.\"",
                           "• Globe watermark bottom-right", "• Sensitive moments: never in titles", "   or thumbnails"], 12, lead=19); c.showPage()
    c.save(); return path


if __name__ == "__main__":
    print(build(os.path.join(OUT, "Nobodys_Town_Brand_Guide.pdf")))
