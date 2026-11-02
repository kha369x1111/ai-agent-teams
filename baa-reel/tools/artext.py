"""Arabic Calligraphy Shaping, Metallic Gold-Leaf Embossing & Highlighted Subtitles.

Built on HarfBuzz (uharfbuzz) vector glyph extraction + 2x supersampled rasterisation:
  1. Exact RTL shaping & ligatures without libraqm.
  2. Vector separation of حرف الباء («ب») into its upper vessel stroke (صحن الباء)
     and lower formative dot (النقطة التكوينية) for independent 30fps animation.
  3. Procedural antique gold-leaf shading with bevel, warm specular sheen & deep shadow.
  4. Word-level gold highlighting for synchronized Arabic Reels captions.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import uharfbuzz as hb
from PIL import Image, ImageChops, ImageDraw, ImageFilter

SS = 2


class Shaper:
    def __init__(self, font_path: str):
        with open(font_path, "rb") as fh:
            self.blob = hb.Blob(fh.read())
        self.face = hb.Face(self.blob)
        self.font = hb.Font(self.face)
        self.upem = self.face.upem

    def shape(self, text: str, size: int):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.font, buf, {"kern": True, "liga": True})
        k = size / self.upem
        glyphs = [i.codepoint for i in buf.glyph_infos]
        adv = [p.x_advance * k for p in buf.glyph_positions]
        off = [(p.x_offset * k, p.y_offset * k) for p in buf.glyph_positions]
        return glyphs, adv, off


_CACHE: dict[str, Shaper] = {}


def shaper(font_path: str) -> Shaper:
    key = str(font_path)
    if key not in _CACHE:
        _CACHE[key] = Shaper(key)
    return _CACHE[key]


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
            nxt = end if i == len(pts) - 1 else (
                (pts[i][0] + pts[i + 1][0]) / 2,
                (pts[i][1] + pts[i + 1][1]) / 2,
            )
            for k in range(1, 11):
                t = k / 10
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
            for k in range(1, 13):
                t = k / 12
                mt = 1 - t
                a, b, c, d = mt**3, 3 * mt * mt * t, 3 * mt * t * t, t**3
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


def glyph_contours(sh: Shaper, gid: int, ox: float, oy: float, size: float):
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
    bboxes = [
        ((min(p[0] for p in c), min(p[1] for p in c)),
         (max(p[0] for p in c), max(p[1] for p in c)))
        for c in contours
    ]
    depths = []
    for i, c in enumerate(contours):
        pt = c[0]
        d = 0
        for j, other in enumerate(contours):
            if i == j:
                continue
            (x0, y0), (x1, y1) = bboxes[j]
            if x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1 and _point_in_poly(pt, other):
                d += 1
        depths.append(d)
    return depths


def measure(text: str, font_path: str, size: int) -> float:
    sh = shaper(font_path)
    total = 0.0
    for chunk in text.split("\n"):
        _, adv, _ = sh.shape(chunk, size)
        total = max(total, sum(adv))
    return total


def wrap(text: str, font_path: str, size: int, max_width: float) -> list[str]:
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
        if line:
            out.append(line)
    return out


def render_mask(
    text: str,
    font_path: str,
    size: int,
    *,
    max_width: float | None = None,
    line_gap: float = 0.42,
    align: str = "center",
) -> Image.Image:
    """Render shaped Arabic text to an 8-bit antialiased alpha mask."""
    sh = shaper(font_path)
    lines = wrap(text, font_path, size, max_width) if max_width else text.split("\n")
    line_h = size * (1 + line_gap)
    widths = [measure(ln, font_path, size) for ln in lines]
    pad = int(size * 0.55)
    w = max(4, int(max(widths, default=1) + pad * 2))
    h = max(4, int(line_h * len(lines) + pad * 2))

    mask = Image.new("L", (w * SS, h * SS), 0)
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
        y = pad + idx * line_h + size * 0.90
        for gid, a, (ox, oy) in zip(glyphs, adv, offs):
            cs = glyph_contours(sh, gid, (x + ox) * SS, (y - oy) * SS, size * SS)
            if cs:
                depths = contour_depths(cs)
                for i in sorted(range(len(cs)), key=lambda k: depths[k]):
                    mdraw.polygon(cs[i], fill=(255 if depths[i] % 2 == 0 else 0))
            x += a
    return mask.resize((w, h), Image.LANCZOS)


def apply_gold_leaf(
    mask: Image.Image,
    sheen_pos: float = 0.5,
    glow_radius: int = 14,
    bevel: float = 1.0,
) -> Image.Image:
    """Turn an alpha mask into embossed antique metallic gold-leaf RGBA."""
    w, h = mask.size
    a = np.asarray(mask, dtype=np.float32) / 255.0
    # Compute surface normals from blurred heightmap for realistic metallic bevel
    blurred = np.asarray(mask.filter(ImageFilter.GaussianBlur(max(1.2, 2.2 * bevel))), dtype=np.float32) / 255.0
    gy, gx = np.gradient(blurred)
    # Light from top-left-front
    shade = np.clip(0.58 - 2.6 * gx - 3.1 * gy, 0.0, 1.35)

    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]

    # Base antique gold gradient (bronze shadow -> antique gold -> warm highlight)
    c_dark = np.array([118.0, 78.0, 34.0], dtype=np.float32)
    c_mid  = np.array([214.0, 173.0, 92.0], dtype=np.float32)
    c_hi   = np.array([255.0, 243.0, 198.0], dtype=np.float32)

    t = np.clip(shade * (1.08 - 0.22 * yy), 0.0, 1.25)[..., None]
    rgb = np.where(
        t < 0.65,
        c_dark + (c_mid - c_dark) * (t / 0.65),
        c_mid + (c_hi - c_mid) * np.clip((t - 0.65) / 0.55, 0.0, 1.0),
    )

    # Diagonal moving specular sheen across the gold leaf
    diag = xx * 0.82 + yy * 0.35
    band = np.exp(-((diag - sheen_pos) ** 2) / (2 * 0.055 ** 2))[..., None]
    rgb = np.clip(rgb + band * np.array([62.0, 56.0, 44.0]), 0, 255)

    glyph_rgba = np.zeros((h, w, 4), dtype=np.uint8)
    glyph_rgba[..., :3] = rgb.astype(np.uint8)
    glyph_rgba[..., 3] = (a * 255).astype(np.uint8)
    fg = Image.fromarray(glyph_rgba, mode="RGBA")

    if glow_radius <= 0:
        return fg

    # Deep charcoal drop shadow + warm antique-gold halo
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh_mask = mask.filter(ImageFilter.GaussianBlur(max(3, glow_radius // 2)))
    shadow = Image.new("RGBA", (w, h), (5, 4, 7, 0))
    shadow.putalpha(sh_mask.point(lambda p: min(255, int(p * 0.85))))
    out.alpha_composite(shadow, (0, min(4, h - 1)))

    halo_mask = mask.filter(ImageFilter.GaussianBlur(glow_radius))
    halo = Image.new("RGBA", (w, h), (218, 168, 78, 0))
    halo.putalpha(halo_mask.point(lambda p: min(255, int(p * 0.52))))
    out = Image.alpha_composite(out, halo)
    out = Image.alpha_composite(out, fg)
    return out


def render_gold_text(
    text: str,
    font_path: str,
    size: int,
    *,
    max_width: float | None = None,
    sheen_pos: float = 0.55,
    glow_radius: int = 12,
) -> Image.Image:
    mask = render_mask(text, font_path, size, max_width=max_width)
    return apply_gold_leaf(mask, sheen_pos=sheen_pos, glow_radius=glow_radius)


def render_plain_text(
    text: str,
    font_path: str,
    size: int,
    color=(248, 241, 226, 255),
    *,
    max_width: float | None = None,
    shadow_blur: int = 6,
) -> Image.Image:
    mask = render_mask(text, font_path, size, max_width=max_width)
    w, h = mask.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if shadow_blur > 0:
        sm = mask.filter(ImageFilter.GaussianBlur(shadow_blur))
        sh_img = Image.new("RGBA", (w, h), (6, 5, 8, 0))
        sh_img.putalpha(sm.point(lambda p: min(255, int(p * 0.90))))
        out = Image.alpha_composite(out, sh_img)
    fg = Image.new("RGBA", (w, h), color)
    fg.putalpha(mask)
    return Image.alpha_composite(out, fg)


def render_subtitle_plate(
    text: str,
    highlight_words: list[str],
    font_path: str,
    size: int = 44,
    max_width: int = 900,
) -> Image.Image:
    """Render an RTL Arabic caption with pivotal words highlighted in antique gold."""
    sh = shaper(font_path)
    lines = wrap(text, font_path, size, max_width)
    line_h = int(size * 1.48)
    pad_x, pad_y = 44, 24

    # Measure line widths cleanly by shaping whole line
    line_widths = [measure(ln, font_path, size) for ln in lines]
    box_w = int(max(line_widths, default=200) + pad_x * 2)
    box_h = int(len(lines) * line_h + pad_y * 2)

    plate = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(plate)
    # Subtle royal charcoal-parchment translucent cartouche with thin antique-gold hair-border
    d.rounded_rectangle(
        [2, 2, box_w - 3, box_h - 3],
        radius=20,
        fill=(11, 9, 13, 178),
        outline=(198, 156, 78, 115),
        width=2,
    )

    hl_clean = {w.strip("….,،؛:؟!«»") for w in highlight_words}
    space_w = measure(" ", font_path, size)

    for idx, ln in enumerate(lines):
        words = [w for w in ln.split(" ") if w]
        w_imgs = []
        total_w = 0.0
        for wi, w in enumerate(words):
            stripped = w.strip("….,،؛:؟!«»")
            is_hl = stripped in hl_clean or w in highlight_words
            if is_hl:
                wim = render_gold_text(w, font_path, size, sheen_pos=0.48, glow_radius=7)
            else:
                wim = render_plain_text(w, font_path, size, (248, 242, 228, 255), shadow_blur=5)
            # Tight horizontal advance using shaped measurement
            adv_w = measure(w, font_path, size)
            w_imgs.append((wim, adv_w))
            total_w += adv_w + (space_w if wi < len(words) - 1 else 0)

        # Lay out RTL (right-to-left) from right start of centered line
        gap_w = space_w * 1.32
        total_line_w = sum(a for _, a in w_imgs) + gap_w * max(0, len(w_imgs) - 1)
        cursor_right = (box_w + total_line_w) / 2
        cy = pad_y + idx * line_h + line_h * 0.50
        for wi, (wim, adv_w) in enumerate(w_imgs):
            cx = cursor_right - adv_w / 2
            px = int(round(cx - wim.width / 2))
            py = int(round(cy - wim.height / 2))
            plate.alpha_composite(wim, (px, py))
            cursor_right -= adv_w + gap_w

    return plate


@lru_cache(maxsize=8)
def extract_baa_anatomy(font_path: str, size: int = 560) -> dict:
    """Extract separated vector contours of «ب»: upper vessel (صحن الباء) & lower Nuqta (النقطة)."""
    sh = shaper(font_path)
    glyphs, adv, offs = sh.shape("ب", size)
    all_c = []
    x = 0.0
    for gid, a, (ox, oy) in zip(glyphs, adv, offs):
        cs = glyph_contours(sh, gid, x + ox, size - oy, size)
        all_c.extend(cs)
        x += a

    # Sort contours by vertical centroid: upper = vessel, lower = Nuqta
    scored = []
    for c in all_c:
        xs = [p[0] for p in c]
        ys = [p[1] for p in c]
        scored.append(((min(ys) + max(ys)) / 2, (min(xs), min(ys), max(xs), max(ys)), c))
    scored.sort(key=lambda item: item[0])

    vessel_contours = [scored[0][2]] if scored else []
    nuqta_contours = [s[2] for s in scored[1:]] if len(scored) > 1 else []

    all_pts = [p for c in all_c for p in c]
    min_x = min(p[0] for p in all_pts)
    max_x = max(p[0] for p in all_pts)
    min_y = min(p[1] for p in all_pts)
    max_y = max(p[1] for p in all_pts)
    pad = int(size * 0.28)
    cw = int(math.ceil(max_x - min_x + pad * 2))
    ch = int(math.ceil(max_y - min_y + pad * 2))
    dx, dy = pad - min_x, pad - min_y

    def shift(cs):
        return [[(p[0] + dx, p[1] + dy) for p in c] for c in cs]

    v_cs = shift(vessel_contours)
    n_cs = shift(nuqta_contours)

    n_pts = [p for c in n_cs for p in c]
    nuqta_center = (
        sum(p[0] for p in n_pts) / len(n_pts),
        sum(p[1] for p in n_pts) / len(n_pts),
    ) if n_pts else (cw / 2, ch * 0.78)

    v_pts = [p for c in v_cs for p in c]
    vessel_bbox = (
        min(p[0] for p in v_pts),
        min(p[1] for p in v_pts),
        max(p[0] for p in v_pts),
        max(p[1] for p in v_pts),
    )

    return {
        "width": cw,
        "height": ch,
        "vessel": v_cs,
        "nuqta": n_cs,
        "nuqta_center": nuqta_center,
        "vessel_bbox": vessel_bbox,
    }
