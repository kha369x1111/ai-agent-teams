"""Arabic (and mixed Arabic/Latin/number) typesetting for the Alif film.

Pillow here is built without libraqm, so it cannot shape Arabic. This module:

1. resolves the Unicode bidi algorithm (python-bidi) to get one embedding level
   per character,
2. groups characters into directional runs, mirroring paired punctuation in
   RTL runs (HarfBuzz does not mirror brackets for us),
3. shapes every run with HarfBuzz, converts outlines to polygons and rasterises
   at 2x supersampling, filling counters (holes) correctly,
4. lays the runs out in visual order (right-to-left base by default).

Public API
----------
render(text, font_path, size, color, ...)      -> RGBA image
draw_text(base, xy, text, font, size, ...)     -> composite onto RGBA image
measure(text, font_path, size)                 -> width in px
gold_image(text, font_path, size, ...)         -> RGBA image filled with a
                                                  vertical gold gradient
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import uharfbuzz as hb
from PIL import Image, ImageChops, ImageDraw, ImageFilter

SS = 2  # supersampling factor for glyph rasterisation

MIRROR = {
    "(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{",
    "<": ">", ">": "<", "«": "»", "»": "«", "‹": "›", "›": "‹",
}

ARABIC_RANGES = (
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
)


def _is_arabic(ch: str) -> bool:
    o = ord(ch)
    return any(a <= o <= b for a, b in ARABIC_RANGES)


# --------------------------------------------------------------------------- #
# shaping
# --------------------------------------------------------------------------- #
class Shaper:
    def __init__(self, font_path: str):
        with open(font_path, "rb") as fh:
            self.blob = hb.Blob(fh.read())
        self.face = hb.Face(self.blob)
        self.font = hb.Font(self.face)
        self.upem = self.face.upem

    def shape(self, text: str, size: int, rtl: bool):
        """Return (glyph_ids, advances_px, offsets_px) for one directional run."""
        if not text:
            return [], [], []
        buf = hb.Buffer()
        buf.add_str(text)
        buf.direction = "rtl" if rtl else "ltr"
        has_arabic = any(_is_arabic(c) for c in text)
        buf.script = "Arab" if (has_arabic or rtl) else "Latn"
        buf.language = "ar" if has_arabic else "en"
        hb.shape(self.font, buf, {"kern": True, "liga": True, "calt": True})
        k = size / self.upem
        glyphs = [i.codepoint for i in buf.glyph_infos]
        adv = [p.x_advance * k for p in buf.glyph_positions]
        off = [(p.x_offset * k, p.y_offset * k) for p in buf.glyph_positions]
        return glyphs, adv, off


_SHAPERS: dict[str, Shaper] = {}


def shaper(font_path: str) -> Shaper:
    if font_path not in _SHAPERS:
        _SHAPERS[font_path] = Shaper(font_path)
    return _SHAPERS[font_path]


@dataclass
class Run:
    text: str
    rtl: bool
    width: float = 0.0


def _levels(text: str, base_dir: str):
    """(levels, display_chars) after the full UBA pipeline up to mirroring."""
    try:
        from bidi.algorithm import (PARAGRAPH_LEVELS, explicit_embed_and_overrides,
                                    get_embedding_levels, get_empty_storage,
                                    resolve_implicit_levels, resolve_neutral_types,
                                    resolve_weak_types)
    except Exception:  # pragma: no cover - python-bidi missing: crude fallback
        lv, chars = [], []
        for ch in text:
            if _is_arabic(ch):
                lv.append(1); chars.append(MIRROR.get(ch, ch))
            elif ch.isdigit() or (ch.isalpha() and not _is_arabic(ch)):
                lv.append(2); chars.append(ch)
            else:
                lv.append(1); chars.append(MIRROR.get(ch, ch))
        return lv, "".join(chars)

    storage = get_empty_storage()
    storage["base_level"] = PARAGRAPH_LEVELS[base_dir]
    storage["base_dir"] = base_dir
    get_embedding_levels(text, storage)
    explicit_embed_and_overrides(storage, False)
    resolve_weak_types(storage, False)
    resolve_neutral_types(storage, False)
    resolve_implicit_levels(storage, False)
    chars = storage["chars"]
    if len(chars) != len(text):
        return [1] * len(text), text
    levels = [c["level"] for c in chars]
    # UBA mirroring: paired punctuation at odd levels is rendered mirrored
    disp = "".join(MIRROR.get(c["ch"], c["ch"]) if c["level"] % 2 else c["ch"]
                   for c in chars)
    return levels, disp


def runs(text: str, base_dir: str = "R") -> list[Run]:
    """Split text into directional runs already ordered right-to-left visually."""
    levels, disp = _levels(text, base_dir)
    spans: list[tuple[int, int, int]] = []
    for i, lv in enumerate(levels):
        if spans and spans[-1][2] == lv:
            spans[-1] = (spans[-1][0], i + 1, lv)
        else:
            spans.append((i, i + 1, lv))
    base_rtl = (1 if base_dir == "R" else 0) == 1
    seq = list(reversed(spans)) if base_rtl else spans
    return [Run(disp[start:end], (lv % 2) == 1) for start, end, lv in seq]


def layout(text: str, font_path: str, size: int, base_dir: str = "R"):
    """Return list of (run, glyphs, advances, offsets) with run widths filled."""
    sh = shaper(font_path)
    out = []
    for run in runs(text, base_dir):
        g, a, o = sh.shape(run.text, size, run.rtl)
        run.width = sum(a)
        out.append((run, g, a, o))
    return out


def measure(text: str, font_path: str, size: int, base_dir: str = "R") -> float:
    best = 0.0
    for chunk in text.split("\n"):
        laid = layout(chunk, font_path, size, base_dir)
        best = max(best, sum(r.width for r, *_ in laid))
    return best


# --------------------------------------------------------------------------- #
# glyph outlines -> polygons
# --------------------------------------------------------------------------- #
class _Pen:
    def __init__(self, ox: float, oy: float, scale: float):
        self.ox, self.oy, self.scale = ox, oy, scale
        self.contours: list[list[tuple[float, float]]] = []
        self.cur: list[tuple[float, float]] = []
        self._pt = (0.0, 0.0)
        self._start = (0.0, 0.0)

    def _map(self, pt):
        x, y = pt
        s = self.scale
        return (self.ox + x * s, self.oy - y * s)

    def moveTo(self, pt):
        self.closePath()
        self.cur = [self._map(pt)]
        self._pt = pt
        self._start = pt

    def lineTo(self, pt):
        self.cur.append(self._map(pt))
        self._pt = pt

    def qCurveTo(self, *pts):
        pts = list(pts)
        end = pts.pop()
        if end is None:
            end = self._start
        prev = self._pt
        for i in range(len(pts)):
            ctrl = pts[i]
            nxt = end if i == len(pts) - 1 else ((pts[i][0] + pts[i + 1][0]) / 2,
                                                 (pts[i][1] + pts[i + 1][1]) / 2)
            for k in range(1, 9):
                t = k / 8
                mt = 1 - t
                px = mt * mt * prev[0] + 2 * mt * t * ctrl[0] + t * t * nxt[0]
                py = mt * mt * prev[1] + 2 * mt * t * ctrl[1] + t * t * nxt[1]
                self.cur.append(self._map((px, py)))
            prev = nxt
        self._pt = end

    def cCurveTo(self, *pts):
        pts = [p for p in pts if p is not None]
        prev = self._pt
        for i in range(0, len(pts) - 2, 3):
            c1, c2, end = pts[i], pts[i + 1], pts[i + 2]
            for k in range(1, 11):
                t = k / 10
                mt = 1 - t
                a, b, c, d = mt ** 3, 3 * mt * mt * t, 3 * mt * t * t, t ** 3
                px = a * prev[0] + b * c1[0] + c * c2[0] + d * end[0]
                py = a * prev[1] + b * c1[1] + c * c2[1] + d * end[1]
                self.cur.append(self._map((px, py)))
            prev = end
        self._pt = prev

    curveTo = qCurveTo

    def closePath(self):
        if len(self.cur) > 2:
            self.contours.append(self.cur)
        self.cur = []
        self._pt = self._start


def _glyph_contours(sh: Shaper, gid: int, ox: float, oy: float, size: int):
    pen = _Pen(ox, oy, size / sh.upem)
    sh.font.draw_glyph_with_pen(gid, pen)
    pen.closePath()
    return pen.contours


def _point_in_poly(pt, poly) -> bool:
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            xint = (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
            if x < xint:
                inside = not inside
        j = i
    return inside


def contour_depths(contours) -> list[int]:
    """Nesting depth of every contour (even = ink, odd = hole)."""
    bboxes = [((min(p[0] for p in c), min(p[1] for p in c)),
               (max(p[0] for p in c), max(p[1] for p in c))) for c in contours]
    depths = []
    for i, c in enumerate(contours):
        pt = c[0]
        d = 0
        for j, other in enumerate(contours):
            if i == j:
                continue
            (x0, y0), (x1, y1) = bboxes[j]
            if not (x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1):
                continue
            if _point_in_poly(pt, other):
                d += 1
        depths.append(d)
    return depths


# --------------------------------------------------------------------------- #
# line wrapping
# --------------------------------------------------------------------------- #
def wrap(text: str, font_path: str, size: int, max_width: float,
         base_dir: str = "R") -> list[str]:
    out: list[str] = []
    for para in text.split("\n"):
        words = para.split(" ")
        line = ""
        for w in words:
            cand = (line + " " + w).strip()
            if not line or measure(cand, font_path, size, base_dir) <= max_width:
                line = cand
            else:
                out.append(line)
                line = w
        out.append(line)
    return out


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def _draw_lines(lines: list[str], font_path: str, size: int, *,
                line_gap: float, align: str, base_dir: str, pad: int,
                max_width: float | None):
    """Rasterise lines to an L mask at SS scale. Returns (mask, w, h)."""
    sh = shaper(font_path)
    laid = [layout(ln, font_path, size, base_dir) for ln in lines]
    widths = [sum(r.width for r, *_ in row) for row in laid]
    line_h = size * (1 + line_gap)
    w = int(max(widths) + pad * 2) if widths else 1
    h = int(line_h * len(laid) + pad * 2)
    mask = Image.new("L", (max(1, w * SS), max(1, h * SS)), 0)
    mdraw = ImageDraw.Draw(mask)
    for idx, row in enumerate(laid):
        lw = widths[idx]
        if align == "center":
            x = (w - lw) / 2
        elif align in ("right", "rtl"):
            x = w - pad - lw
        else:
            x = pad
        y = pad + idx * line_h + size * 0.90
        for run, glyphs, adv, offs in row:
            for gid, a, (ox, oy) in zip(glyphs, adv, offs):
                contours = _glyph_contours(sh, gid, (x + ox) * SS, (y - oy) * SS, size * SS)
                if contours:
                    depths = contour_depths(contours)
                    order = sorted(range(len(contours)), key=lambda i: depths[i])
                    for i in order:
                        mdraw.polygon(contours[i], fill=(255 if depths[i] % 2 == 0 else 0))
                x += a
    return mask, w, h


def render(
    text: str,
    font_path: str,
    size: int,
    color=(255, 255, 255, 255),
    *,
    max_width: float | None = None,
    line_gap: float = 0.42,
    align: str = "center",
    base_dir: str = "R",
    stroke: int = 0,
    stroke_color=(0, 0, 0, 255),
    shadow: int = 0,
    shadow_color=(0, 0, 0, 120),
    glow: int = 0,
    glow_color=(255, 190, 90, 255),
    max_lines: int | None = None,
) -> Image.Image:
    """Render (possibly multi-line) Arabic text to a tight RGBA image."""
    lines = wrap(text, font_path, size, max_width, base_dir) if max_width else text.split("\n")
    if max_lines:
        lines = lines[:max_lines]
    extra = max(stroke, shadow, glow)
    pad = int(size * 0.42 + extra * 2)
    mask, w, h = _draw_lines(lines, font_path, size, line_gap=line_gap, align=align,
                             base_dir=base_dir, pad=pad, max_width=max_width)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if glow:
        halo = mask.filter(ImageFilter.GaussianBlur(glow * SS)).resize((w, h), Image.LANCZOS)
        halo = halo.point(lambda v: min(255, int(v * 1.15)))
        layer = Image.new("RGBA", (w, h), glow_color[:3] + (0,))
        layer.putalpha(halo)
        out = Image.alpha_composite(out, layer)
    if shadow:
        sm = mask.filter(ImageFilter.MaxFilter(shadow * 2 + 1)).resize((w, h), Image.LANCZOS)
        layer = Image.new("RGBA", (w, h), shadow_color[:3] + (0,))
        layer.putalpha(sm.point(lambda v: v * shadow_color[3] // 255))
        out = Image.alpha_composite(out, layer)
    if stroke:
        sm = mask.filter(ImageFilter.MaxFilter(stroke * 2 + 1)).resize((w, h), Image.LANCZOS)
        layer = Image.new("RGBA", (w, h), stroke_color)
        layer.putalpha(sm)
        out = Image.alpha_composite(out, layer)
    body = Image.new("RGBA", (w, h), color)
    body.putalpha(ImageChops.multiply(body.split()[3], mask.resize((w, h), Image.LANCZOS)))
    return Image.alpha_composite(out, body)


def gold_image(
    text: str,
    font_path: str,
    size: int,
    *,
    stops=((255, 244, 214), (246, 205, 120), (196, 138, 48), (255, 232, 178)),
    line_gap: float = 0.42,
    align: str = "center",
    base_dir: str = "R",
    glow: int = 0,
    glow_color=(255, 176, 72, 255),
    bevel: bool = True,
    pad_ratio: float = 0.42,
) -> Image.Image:
    """Text filled with a metallic vertical gradient plus optional warm halo."""
    lines = text.split("\n")
    extra = glow * 2
    pad = int(size * pad_ratio + extra)
    mask, w, h = _draw_lines(lines, font_path, size, line_gap=line_gap, align=align,
                             base_dir=base_dir, pad=pad, max_width=None)
    mask_r = mask.resize((w, h), Image.LANCZOS)
    grad = Image.new("RGBA", (w, h))
    gd = ImageDraw.Draw(grad)
    n = len(stops) - 1
    for y in range(h):
        t = y / max(1, h - 1) * n
        i = min(n - 1, int(t))
        f = t - i
        c0, c1 = stops[i], stops[i + 1]
        gd.line([(0, y), (w, y)], fill=tuple(int(c0[k] + (c1[k] - c0[k]) * f) for k in range(3)) + (255,))
    grad.putalpha(mask_r)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if glow:
        halo = mask_r.filter(ImageFilter.GaussianBlur(glow)).point(
            lambda v: min(255, int(v * 1.35)))
        layer = Image.new("RGBA", (w, h), glow_color[:3] + (0,))
        layer.putalpha(halo)
        out = Image.alpha_composite(out, layer)
    out = Image.alpha_composite(out, grad)
    if bevel:  # darker lower edge for a chiselled-metal feel
        edge = mask_r.filter(ImageFilter.GaussianBlur(max(1, size * 0.012)))
        bottom = Image.new("L", (w, h), 0)
        ImageDraw.Draw(bottom).rectangle([0, int(h * 0.55), w, h], fill=90)
        sh = ImageChops.multiply(edge, bottom.filter(ImageFilter.GaussianBlur(size * 0.02)))
        layer = Image.new("RGBA", (w, h), (60, 34, 10, 0))
        layer.putalpha(sh)
        out = Image.alpha_composite(out, layer)
    return out


def draw_text(base: Image.Image, xy, text: str, font_path: str, size: int,
              color=(255, 255, 255, 255), anchor: str = "mm", **kw):
    img = render(text, font_path, size, color, **kw)
    hx, hy = anchor[0], anchor[1]
    x = xy[0] - (img.width / 2 if hx == "m" else img.width if hx == "r" else 0)
    y = xy[1] - (img.height / 2 if hy == "m" else img.height if hy == "b" else 0)
    base.alpha_composite(img, (int(x), int(y)))
    return int(x), int(y), img.width, img.height
