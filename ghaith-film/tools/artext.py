"""Arabic text shaping + rendering for the Ghaith film pipeline.

Pillow in this environment is built without libraqm, so it cannot shape Arabic
(letters would appear disconnected and left-to-right).  This module shapes text
with HarfBuzz (uharfbuzz), converts each glyph outline to polygons and rasterises
it with Pillow at 2x supersampling.

Public API
----------
render(text, font_path, size, color, ...)   -> RGBA image
draw_text(base, xy, text, ...)              -> draws onto an RGBA image
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import uharfbuzz as hb
from PIL import Image, ImageDraw, ImageFilter

SS = 2  # supersampling factor for glyph rasterisation


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

    def shape(self, text: str, size: int):
        """Return (glyphs, advances_px, offsets_px) laid out left->right."""
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.font, buf, {"kern": True, "liga": True})
        k = size / self.upem
        glyphs = [i.codepoint for i in buf.glyph_infos]
        adv = [p.x_advance * k for p in buf.glyph_positions]
        off = [(p.x_offset * k, p.y_offset * k) for p in buf.glyph_positions]
        return glyphs, adv, off


_PEN_CACHE: dict[str, Shaper] = {}


def shaper(font_path: str) -> Shaper:
    if font_path not in _PEN_CACHE:
        _PEN_CACHE[font_path] = Shaper(font_path)
    return _PEN_CACHE[font_path]


class _Pen:
    """Collect contours from HarfBuzz outlines (font units, y-up).

    uharfbuzz pen API: moveTo(pt) / lineTo(pt) / qCurveTo(*pts) /
    cCurveTo(*pts) / closePath(), where pts are (x, y) tuples and a trailing
    None marks an implied on-curve end point.
    """

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
        # remaining points: control points; interpolate quadratic chain
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
                a, b, c, d = mt**3, 3 * mt * mt * t, 3 * mt * t * t, t**3
                px = a * prev[0] + b * c1[0] + c * c2[0] + d * end[0]
                py = a * prev[1] + b * c1[1] + c * c2[1] + d * end[1]
                self.cur.append(self._map((px, py)))
            prev = end
        self._pt = prev

    # aliases used by different pen bindings (fontTools style curveTo = quadratic)
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
# layout helpers
# --------------------------------------------------------------------------- #
def measure(text: str, font_path: str, size: int) -> float:
    sh = shaper(font_path)
    total = 0.0
    for chunk in text.split("\n"):
        _, adv, _ = sh.shape(chunk, size)
        total = max(total, sum(adv))
    return total


def wrap(text: str, font_path: str, size: int, max_width: float) -> list[str]:
    """Word-wrap to max_width (logical order, RTL friendly)."""
    out: list[str] = []
    for para in text.split("\n"):
        words = para.split(" ")
        line = ""
        for w in words:
            cand = (line + " " + w).strip()
            if measure(cand, font_path, size) <= max_width or not line:
                line = cand
            else:
                out.append(line)
                line = w
        out.append(line)
    return out


def render(
    text: str,
    font_path: str,
    size: int,
    color=(255, 255, 255, 255),
    *,
    max_width: float | None = None,
    line_gap: float = 0.42,
    align: str = "center",
    stroke: int = 0,
    stroke_color=(60, 35, 20, 255),
    shadow: int = 0,
    shadow_color=(0, 0, 0, 110),
    max_lines: int | None = None,
) -> Image.Image:
    """Render (possibly multi-line) Arabic text to a tight RGBA image."""
    sh = shaper(font_path)
    lines = wrap(text, font_path, size, max_width) if max_width else text.split("\n")
    if max_lines:
        lines = lines[:max_lines]
    line_h = size * (1 + line_gap)
    widths = [measure(ln, font_path, size) for ln in lines]
    pad = int(size * 0.45 + stroke + shadow)
    w = int(max(widths) + pad * 2) if widths else 1
    h = int(line_h * len(lines) + pad * 2)

    canvas = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    mask = Image.new("L", canvas.size, 0)
    mdraw = ImageDraw.Draw(mask)

    for idx, ln in enumerate(lines):
        glyphs, adv, offs = sh.shape(ln, size)
        lw = sum(adv)
        if align == "center":
            x = (w - lw) / 2
        elif align in ("right", "rtl"):
            x = w - pad - lw
        else:
            x = pad
        y = pad + idx * line_h + size * 0.92
        for gid, a, (ox, oy) in zip(glyphs, adv, offs):
            contours = _glyph_contours(sh, gid, (x + ox) * SS, (y - oy) * SS, size * SS)
            if contours:
                depths = contour_depths(contours)
                order = sorted(range(len(contours)), key=lambda i: depths[i])
                for i in order:
                    mdraw.polygon(contours[i], fill=(255 if depths[i] % 2 == 0 else 0))
            x += a

    canvas.paste(Image.new("RGBA", canvas.size, color), (0, 0), mask)

    out = canvas.resize((w, h), Image.LANCZOS)

    if stroke:
        # dilate alpha to fake an outline, then punch the glyphs through
        alpha = out.split()[3]
        grown = alpha.filter(ImageFilter.MaxFilter(stroke * 2 + 1))
        plate = Image.new("RGBA", out.size, stroke_color)
        plate.putalpha(grown)
        out = Image.alpha_composite(plate, out)
    return out


def draw_text(
    base: Image.Image,
    xy: tuple[float, float],
    text: str,
    font_path: str,
    size: int,
    color=(255, 255, 255, 255),
    anchor: str = "mm",
    **kw,
) -> tuple[int, int, int, int]:
    """Composite text onto `base` at xy using PIL-style anchors (m/l/r + m/t/b)."""
    img = render(text, font_path, size, color, **kw)
    hx, hy = anchor[0], anchor[1]
    x = xy[0] - (img.width / 2 if hx == "m" else img.width if hx == "r" else 0)
    y = xy[1] - (img.height / 2 if hy == "m" else img.height if hy == "b" else 0)
    base.alpha_composite(img, (int(x), int(y)))
    return int(x), int(y), img.width, img.height
