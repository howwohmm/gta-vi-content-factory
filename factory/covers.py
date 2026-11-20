"""YouTube thumbnails / covers for the long gameplay parts. Pick a style, optionally your own background art."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from . import core

W, H = 1280, 720
STYLES = {
    "bold-left": "Big title on the left, red PART box, art on the right (great with key-art style backgrounds)",
    "center-banner": "Title across the top, PART banner at the bottom, full-bleed background",
    "minimal": "Small clean label in the corner, lets the frame speak",
}

def _font(size, heavy=True):
    return ImageFont.truetype(core.FONT_HEAVY if heavy else core.FONT_BOLD, size)

def _bg(path):
    img = Image.open(path).convert("RGB")
    r = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * r + 0.5), int(img.height * r + 0.5)), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))

def _shade(img, side="left", strength=150, reach=0.5):
    shade = Image.new("RGB", (W, H), (30, 10, 45)); mask = Image.new("L", (W, H)); d = ImageDraw.Draw(mask)
    if side == "left":
        for x in range(W): d.line([(x, 0), (x, H)], fill=int(strength * max(0, 1 - x / (W * reach)) ** 1.5))
    else:
        for y in range(H):
            t = max(0, 1 - y / (H * reach)) ** 1.5 + max(0, 1 - (H - y) / (H * reach)) ** 1.5
            d.line([(0, y), (W, y)], fill=int(strength * min(1, t)))
    return Image.composite(shade, img, mask)

def _text(d, xy, s, f, fill, stroke, anchor="la"):
    d.text(xy, s, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0), anchor=anchor)

def _box(d, x, y, label, f, center=False):
    tw = d.textlength(label, font=f)
    bw, bh = tw + 64, f.size + 48
    if center: x = (W - bw) / 2
    d.rectangle([x - 6, y - 6, x + bw + 6, y + bh + 6], fill=(255, 255, 255))
    d.rectangle([x, y, x + bw, y + bh], fill=(226, 28, 52))
    _text(d, (x + 32, y + 8), label, f, (255, 255, 255), 6)

def make(background, part, out, s, style=None, subtitle="FULL GAMEPLAY"):
    style = style or s.get("cover_style", "bold-left")
    img = ImageEnhance.Contrast(_bg(background)).enhance(1.05)
    title = s.get("game", "GTA VI").upper()
    if style == "bold-left":
        img = _shade(img, "left")
        d = ImageDraw.Draw(img)
        f = _font(200)
        while d.textlength(title, font=f) > 560 and f.size > 90: f = _font(f.size - 10)
        _text(d, (50, 55), title, f, (255, 255, 255), 9)
        _text(d, (54, 305), subtitle, _font(80), (245, 196, 20), 6)
        _box(d, 54, 430, f"PART {part}", _font(112))
    elif style == "center-banner":
        img = _shade(img, "top", 170, 0.45)
        d = ImageDraw.Draw(img)
        _text(d, (W / 2, 30), f"{title} {subtitle}", _font(118), (255, 255, 255), 8, anchor="ma")
        _box(d, 0, 540, f"PART {part}", _font(96), center=True)
    else:  # minimal
        d = ImageDraw.Draw(img)
        label = f"{title} · PART {part}"
        f = _font(64)
        tw = d.textlength(label, font=f)
        d.rectangle([30, H - 130, 30 + tw + 50, H - 30], fill=(0, 0, 0))
        _text(d, (55, H - 122), label, f, (255, 255, 255), 0)
    img.save(out, quality=92)
    return out

def background_for(project, s, render_still):
    """User's chosen art from 'Cover backgrounds', else a clean frame from the middle of the video."""
    name = s.get("cover_background")
    if name:
        p = os.path.join(core.DIRS["covers"], name)
        if os.path.exists(p): return p
    out = os.path.join(os.path.dirname(project["video"]), "_analysis", "cover_bg.jpg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if not os.path.exists(out):
        render_still(project["video"], project["duration"] * 0.3, out)
    return out
