"""Draws VECTOR's icons from scratch. Run after changing the design:

    python scripts/make_icons.py

Writes vector/assets/: icon.ico (Windows shortcuts and windows, 16-256 px),
icon.png (256 px), icon.icns (the macOS app, 16-1024 px), phone-icon.png (VECTOR Remote), tray.png (64 px), and docs/logo.png
(wordmark for the README).
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "vector" / "assets"
BG = (11, 16, 22, 255)          # #0B1016
EDGE = (31, 58, 64, 255)        # #1F3A40
CYAN = (92, 214, 234, 255)      # #5CD6EA
WHITE = (230, 237, 243, 255)    # #E6EDF3
SS = 4                          # supersampling for smooth edges


def triangle(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], width: float,
             color=CYAN) -> None:
    """The VECTOR mark: a triangle with a line from its centre down to the base."""
    x0, y0, x1, y1 = box
    top = ((x0 + x1) / 2, y0)
    left, right = (x0, y1), (x1, y1)
    w = max(1, round(width))
    draw.line([left, top, right, left, top], fill=color, width=w, joint="curve")
    mid = (top[0], y0 + (y1 - y0) * 0.42)
    draw.line([mid, (top[0], y1)], fill=color, width=w)
    r = w / 2  # round the line ends and corners
    for (px, py) in (top, left, right, mid):
        draw.ellipse((px - r, py - r, px + r, py + r), fill=color)


def app_icon(size: int, pad_ratio: float = 0.04) -> Image.Image:
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = s * pad_ratio
    radius = s * 0.23 * (1 - 2 * pad_ratio) / 0.92  # same shape, smaller when padded
    d.rounded_rectangle((pad, pad, s - pad, s - pad), radius=radius, fill=BG,
                        outline=EDGE, width=max(SS, round(s * 0.012)))
    stroke = s * (0.085 if size <= 32 else 0.065)  # thicker lines stay visible when tiny
    inset = s * 0.25 + pad - s * 0.04
    triangle(d, (inset, s * 0.25 + (pad - s * 0.04) * 0.5, s - inset,
                 s * 0.74 - (pad - s * 0.04) * 0.5), stroke)
    return img.resize((size, size), Image.LANCZOS)


def mac_icon() -> Image.Image:
    """macOS icons leave a margin around the rounded square (Apple's icon grid: ~10%)."""
    return app_icon(1024, pad_ratio=0.1)


def phone_icon(size: int = 512) -> Image.Image:
    """The phone's home-screen icon: a full square (iPhone and Android round the corners)."""
    s = size * SS
    img = Image.new("RGBA", (s, s), BG)
    triangle(ImageDraw.Draw(img), (s * 0.27, s * 0.25, s * 0.73, s * 0.72), s * 0.06)
    return img.resize((size, size), Image.LANCZOS)


def tray_icon(size: int = 64) -> Image.Image:
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, s - 1, s - 1), fill=BG)
    triangle(d, (s * 0.2, s * 0.22, s * 0.8, s * 0.74), s * 0.09)
    return img.resize((size, size), Image.LANCZOS)


def wordmark(height: int = 160) -> Image.Image:
    font_path = next((p for p in (
        "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ) if Path(p).exists()), None)
    h = height * SS
    font = ImageFont.truetype(font_path, int(h * 0.42)) if font_path else ImageFont.load_default()
    letters = "VECTOR"
    spacing = h * 0.16
    widths = [font.getbbox(c)[2] - font.getbbox(c)[0] for c in letters]
    text_w = sum(widths) + spacing * (len(letters) - 1)
    mark = h * 0.62
    gap = h * 0.28
    pad = h * 0.3
    w = int(pad + mark + gap + text_w + pad)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h * 0.22, fill=BG, outline=EDGE, width=SS * 2)
    top = (h - mark) / 2
    triangle(d, (pad, top, pad + mark, top + mark), h * 0.05)
    x = pad + mark + gap
    for c, cw in zip(letters, widths, strict=True):
        bbox = font.getbbox(c)
        d.text((x - bbox[0], (h - (bbox[3] - bbox[1])) / 2 - bbox[1]), c, font=font, fill=WHITE)
        x += cw + spacing
    return img.resize((w // SS, height), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    big = app_icon(256)
    big.save(ASSETS / "icon.png")
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    frames = [app_icon(n) for n in sizes]
    frames[-1].save(ASSETS / "icon.ico", sizes=[(n, n) for n in sizes], append_images=frames[:-1])
    mac_icon().save(ASSETS / "icon.icns")
    phone_icon().save(ASSETS / "phone-icon.png")
    tray_icon(64).save(ASSETS / "tray.png")
    (ROOT / "docs").mkdir(exist_ok=True)
    wordmark(160).save(ROOT / "docs" / "logo.png")
    print("Icons written to", ASSETS)


if __name__ == "__main__":
    main()
