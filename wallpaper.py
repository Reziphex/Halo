"""Palet warna dominan - dari cover lagu (utama) atau wallpaper Windows (cadangan)."""
import colorsys
import ctypes
import io
import os

from PIL import Image

SPI_GETDESKWALLPAPER = 0x0073
FALLBACK = {"bg1": "#2b2540", "bg2": "#15121f", "accent": "#b9a3ff",
            "fg": "#f4f1ff", "muted": "#b8b2cc"}


def wallpaper_path():
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, 260, buf, 0)
    if buf.value and os.path.exists(buf.value):
        return buf.value
    # Slideshow / Windows Spotlight: Windows menyimpan hasil render di sini
    t = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Themes\TranscodedWallpaper")
    return t if os.path.exists(t) else None


def _hex(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def palette_from_image(img):
    """Kembalikan dict palet, atau None jika tidak ada warna yang layak."""
    img = img.convert("RGB")
    img.thumbnail((120, 120))
    q = img.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    best, best_score = None, -1
    for count, idx in q.getcolors():
        r, g, b = pal[idx * 3: idx * 3 + 3]
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if v < 0.2:
            continue
        score = count * (0.2 + s)
        if score > best_score:
            best, best_score = (h, s, v), score
    if best is None:
        return None
    h, s, _ = best
    return {
        "bg1": _hex(h, min(s, 0.75), 0.24),
        "bg2": _hex(h, min(s, 0.75), 0.10),
        "accent": _hex(h, max(min(s, 0.8), 0.3), 0.95),
        "fg": "#f5f5f7",
        "muted": _hex(h, min(s, 0.25), 0.80),
    }


def get_palette():
    """Palet dari wallpaper aktif."""
    try:
        path = wallpaper_path()
        if not path:
            return dict(FALLBACK)
        img = Image.open(path)
        img.draft("RGB", (160, 160))
        return palette_from_image(img) or dict(FALLBACK)
    except Exception:
        return dict(FALLBACK)


def palette_from_bytes(data):
    """Palet dari bytes gambar cover."""
    try:
        return palette_from_image(Image.open(io.BytesIO(data)))
    except Exception:
        return None
