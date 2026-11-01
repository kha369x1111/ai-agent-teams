"""تركيب الإطارات: كاميرا، تلاشٍ، ضوء عابر، حرف الألف، نصوص عربية، حبيبات فيلم.

كل شيء رقمي هنا: اللوحات صور ثابتة (بلا حروف)، والكاميرا تتحرك عليها،
والحرف والنصوص تُركَّب طبقةً فوقها — تطبيقًا لقاعدة «لا نصوص داخل التوليد».
"""

from __future__ import annotations

import math
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import artext

PLATE_SCALE = 1.5  # دقة وسيطة للوحة (لتقليل الاهتزاز عند التكبير)


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(u: float) -> float:
    return u * u * (3 - 2 * u)


def ramp(t: float, points) -> float:
    """استيفاء خطي متعدد النقاط: [(t0,v0),(t1,v1),…]"""
    if not points:
        return 0.0
    if t <= points[0][0]:
        return points[0][1]
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t0 <= t <= t1:
            u = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * ease(u)
    return points[-1][1]


# --------------------------------------------------------------------------- #
# عناصر بصرية مُحضّرة
# --------------------------------------------------------------------------- #
class Assets:
    def __init__(self, plan: dict, root: Path, work: Path, spec):
        self.plan, self.root, self.work, self.spec = plan, root, work, spec
        self.W, self.H = plan["w"], plan["h"]
        self.raw = root / "storyboard/raw"
        self.font_amiri = str(root / spec.FONT_AMIRI)
        self.font_bold = str(root / spec.FONT_TAJ_BOLD)
        self.font_black = str(root / spec.FONT_TAJ_BLACK)
        self._plates: dict[str, Image.Image] = {}
        self._cache: dict = {}
        self.vignette = self._make_vignette()
        self.grain = self._make_grain()
        self.grade = self._make_grade()
        self.scrim = self._make_scrim()
        self.band = self._make_band()
        self.beam = self._make_beam()
        self.ring = self._make_ring()
        self.emblem = self._make_emblem()
        self.glyph = self._make_glyph()
        self.texts = self._prepare_texts()
        self.subs = self._prepare_subs()
        self.sections = {s["id"]: s for s in plan["sections"]}
        self._glyph_cache: dict = {}
        self._ring_cache: dict = {}

    # ---- لوحات ----
    def plate(self, name: str) -> Image.Image:
        if name in self._plates:
            return self._plates[name]
        src = None
        for ext in (".png", ".jpg"):
            p = self.raw / f"{name}{ext}"
            if p.exists():
                src = p
                break
        if src is None:
            raise FileNotFoundError(name)
        im = Image.open(src).convert("RGB")
        tw, th = int(self.W * PLATE_SCALE), int(self.H * PLATE_SCALE)
        s = max(tw / im.width, th / im.height)
        im = im.resize((max(tw, int(im.width * s + 0.5)), max(th, int(im.height * s + 0.5))),
                       Image.LANCZOS)
        x = (im.width - tw) // 2
        y = (im.height - th) // 2
        im = im.crop((x, y, x + tw, y + th))
        if len(self._plates) > 3:
            self._plates.pop(next(iter(self._plates)))
        self._plates[name] = im
        return im

    # ---- حبيبات وتظليل ----
    def _make_vignette(self) -> np.ndarray:
        W, H = self.W, self.H
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        cx, cy = W * 0.5, H * 0.47
        r = np.sqrt(((xx - cx) / (W * 0.72)) ** 2 + ((yy - cy) / (H * 0.62)) ** 2)
        v = np.clip(1.0 - 0.52 * np.clip(r - 0.45, 0, None) ** 1.35, 0.30, 1.0)
        return v.astype(np.float32)

    def _make_grain(self, n: int = 6) -> list[np.ndarray]:
        rng = np.random.default_rng(3)
        return [rng.normal(0, 1, (self.H, self.W)).astype(np.float32) for _ in range(n)]

    def _make_grade(self) -> np.ndarray:
        x = np.arange(256, dtype=np.float32) / 255.0
        y = np.clip(x ** 0.92, 0, 1)  # رفع خفيف للظلال
        y = np.clip((y - 0.5) * 1.06 + 0.5, 0, 1)
        lut = np.stack([y * 1.02, y * 0.995, y * 0.955], axis=0)  # ميل ذهبي دافئ
        return np.clip(lut * 255, 0, 255).astype(np.uint8)  # (3, 256)

    def _make_scrim(self) -> Image.Image:
        W, H = self.W, self.H
        g = Image.new("L", (1, H), 0)
        d = ImageDraw.Draw(g)
        for y in range(H):
            if y > H * 0.55:
                v = int(150 * ((y - H * 0.55) / (H * 0.45)) ** 1.7)
                d.point((0, y), fill=min(150, v))
        g = g.resize((W, H))
        layer = Image.new("RGBA", (W, H), (4, 4, 7, 255))
        layer.putalpha(g)
        return layer

    def _make_band(self) -> Image.Image:
        """شريط ضوء ناعم للانتقالات (Light Sweep)."""
        W, H = self.W, self.H
        w = int(W * 0.62)
        x = np.linspace(-1, 1, w, dtype=np.float32)
        prof = np.exp(-(x ** 2) * 7.0)
        arr = np.tile(prof, (H, 1))
        core = np.exp(-(x ** 2) * 90.0)
        arr = np.clip(arr * 0.55 + core, 0, 1)
        a = Image.fromarray((arr * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))
        band = Image.new("RGBA", (w, H), (255, 238, 205, 255))
        band.putalpha(a)
        return band

    def _make_beam(self) -> Image.Image:
        W, H = self.W, self.H
        w = int(W * 0.16)
        arr = np.zeros((H, w), dtype=np.float32)
        x = np.linspace(-1, 1, w, dtype=np.float32)
        prof = np.exp(-(x ** 2) * 40.0) + 0.55 * np.exp(-(x ** 2) * 5.0)
        arr[:] = prof
        a = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(4))
        beam = Image.new("RGBA", (w, H), (255, 232, 176, 255))
        beam.putalpha(a)
        return beam

    def _make_ring(self) -> Image.Image:
        """دائرة هندسية إسلامية: نجمة ثمانية + حلقات + ٢٨ نقطة."""
        S = 1200
        im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        cx = cy = S / 2
        gold = (255, 214, 150, 160)
        dim = (255, 200, 130, 90)
        for r, wd, col in ((S * 0.46, 2, gold), (S * 0.44, 1, dim), (S * 0.33, 1, dim),
                           (S * 0.185, 2, gold)):
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=wd)
        # نجمة ثمانية من مربعين
        for rot in (0, 45):
            pts = []
            for k in range(4):
                a = math.radians(rot + 90 * k + 45)
                pts.append((cx + S * 0.33 * math.cos(a), cy + S * 0.33 * math.sin(a)))
            d.line(pts + [pts[0]], fill=gold, width=2)
        # ٢٨ منزلة
        for k in range(28):
            a = 2 * math.pi * k / 28
            r = S * 0.395
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            d.ellipse([x - 3.2, y - 3.2, x + 3.2, y + 3.2], fill=(255, 224, 170, 190))
        # أشعة
        for k in range(16):
            a = 2 * math.pi * k / 16
            d.line([(cx + S * 0.185 * math.cos(a), cy + S * 0.185 * math.sin(a)),
                    (cx + S * 0.33 * math.cos(a), cy + S * 0.33 * math.sin(a))],
                   fill=(255, 210, 150, 70), width=1)
        return im

    def _make_emblem(self) -> Image.Image:
        S = 640
        im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        cx = cy = S / 2
        gold = (255, 220, 160, 235)
        dim = (255, 205, 140, 150)
        d.ellipse([cx - S * 0.47, cy - S * 0.47, cx + S * 0.47, cy + S * 0.47], outline=gold, width=4)
        d.ellipse([cx - S * 0.43, cy - S * 0.43, cx + S * 0.43, cy + S * 0.43], outline=dim, width=2)
        for rot in (0, 45):
            pts = []
            for k in range(4):
                a = math.radians(rot + 90 * k + 45)
                pts.append((cx + S * 0.33 * math.cos(a), cy + S * 0.33 * math.sin(a)))
            d.line(pts + [pts[0]], fill=gold, width=3)
        for k in range(8):
            a = 2 * math.pi * k / 8
            d.line([(cx + S * 0.33 * math.cos(a), cy + S * 0.33 * math.sin(a)),
                    (cx + S * 0.43 * math.cos(a), cy + S * 0.43 * math.sin(a))],
                   fill=dim, width=2)
        for k in range(7):  # الأسرار السبعة
            a = 2 * math.pi * k / 7 - math.pi / 2
            x, y = cx + S * 0.115 * math.cos(a), cy + S * 0.115 * math.sin(a)
            d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=gold)
        return im

    def _make_glyph(self) -> Image.Image:
        img, ink = build_glyph(self.font_amiri)
        self.glyph_ink = ink
        return img

    # ---- نصوص ----
    @staticmethod
    def _trim(img: Image.Image, margin: int = 10) -> Image.Image:
        bbox = img.split()[3].point(lambda v: 255 if v > 6 else 0).getbbox()
        if not bbox:
            return img
        x0, y0, x1, y1 = bbox
        return img.crop((max(0, x0 - margin), max(0, y0 - margin),
                         min(img.width, x1 + margin), min(img.height, y1 + margin)))

    def _style(self, style: str, text: str, sub: str | None) -> list[Image.Image]:
        W = self.W
        if style == "title":
            out = [artext.gold_image(text, self.font_amiri, 150, glow=22, pad_ratio=0.3)]
            if sub:
                out.append(artext.render(sub, self.font_amiri, 62, (246, 232, 206, 235),
                                         stroke=2, stroke_color=(0, 0, 0, 190), max_width=W * 0.82))
        elif style == "numbers":
            out = [artext.gold_image(text, self.font_bold, 108, glow=18, pad_ratio=0.3)]
        elif style == "caption":
            out = [artext.render(text, self.font_amiri, 80, (250, 238, 214, 252), stroke=4,
                                 stroke_color=(0, 0, 0, 210), shadow=6, max_width=W * 0.86)]
            if sub:
                out.append(artext.render(sub, self.font_amiri, 54, (236, 214, 178, 235), stroke=3,
                                         stroke_color=(0, 0, 0, 190), max_width=W * 0.8))
        elif style == "creed":
            out = [artext.gold_image(text, self.font_amiri, 104, glow=28, pad_ratio=0.34)]
        elif style == "latin":
            out = [artext.render(text, self.font_bold, 54, (250, 232, 196, 240), stroke=3,
                                 stroke_color=(0, 0, 0, 170), base_dir="L")]
        else:  # note
            out = [artext.render(text, self.font_bold, 38, (232, 204, 162, 215), stroke=3,
                                 stroke_color=(0, 0, 0, 170), max_width=W * 0.84)]
        return out

    def _prepare_texts(self) -> dict[str, list[dict]]:
        res: dict[str, list[dict]] = {}
        for sec in self.plan["sections"]:
            items = []
            for i, tx in enumerate(sec["texts"]):
                parts = [self._trim(im) for im in
                         self._style(tx["style"], tx["text"], tx["sub"])]
                gap = int(parts[0].height * 0.10) if len(parts) > 1 else 0
                w = max(p.width for p in parts)
                h = sum(p.height for p in parts) + gap * (len(parts) - 1)
                block = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                y = 0
                for p in parts:
                    block.alpha_composite(p, ((w - p.width) // 2, y))
                    y += p.height + gap
                items.append({"entry": tx, "img": block, "key": i})
            res[sec["id"]] = items
        return res

    def _prepare_subs(self) -> list[dict]:
        out = []
        for cue in self.plan["subtitles"]:
            img = artext.render(cue["text"], self.font_amiri, 54, (247, 241, 230, 252),
                                stroke=3, stroke_color=(0, 0, 0, 210), shadow=6,
                                max_width=self.W * 0.84)
            out.append({**cue, "img": img})
        return out


# --------------------------------------------------------------------------- #
# الألف: صورة ذهبية بقلب نور
# --------------------------------------------------------------------------- #
def build_glyph(font_path: str):
    """الألف كما يُعرَض: ذهب مصهور بقلب نور، وهج دافئ، وهالة داكنة للفصل.

    التدرّج أفقي (أسطواني) لأن شكل الحرف عمودي: حافة مضيئة، عمق ذهبي،
    وحافة ثانية مضيئة — فيُقرأ الحرف قضيبًا ذهبيًا لا شريطًا أبيض.
    """
    size = 1100
    src = artext.render("ا", font_path, size, (255, 255, 255, 255))
    mask = src.split()[3]
    w, h = mask.size
    W = int(w * 1.70)
    H = int(h * 1.52)
    canvas_mask = Image.new("L", (W, H), 0)
    canvas_mask.paste(mask, ((W - w) // 2, (H - h) // 2))
    x0 = (W - w) // 2
    x1 = x0 + w

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # وهج خارجي دافئ
    glow = canvas_mask.filter(ImageFilter.GaussianBlur(size * 0.085)).point(
        lambda v: min(255, int(v * 1.6)))
    layer = Image.new("RGBA", (W, H), (255, 172, 74, 255))
    layer.putalpha(glow.point(lambda v: int(v * 0.72)))
    out = Image.alpha_composite(out, layer)
    # هالة داكنة تفصل الحرف عن الإضاءة الخلفية
    halo = canvas_mask.filter(ImageFilter.GaussianBlur(size * 0.045))
    layer = Image.new("RGBA", (W, H), (10, 7, 4, 255))
    layer.putalpha(halo.point(lambda v: int(v * 0.86)))
    out = Image.alpha_composite(out, layer)
    # جسم معدني: تدرّج أفقي عبر عرض الحبر
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    stops = [(0.00, (255, 250, 228)), (0.13, (255, 214, 132)), (0.33, (214, 154, 62)),
             (0.52, (150, 98, 34)), (0.70, (224, 160, 70)), (0.86, (255, 226, 158)),
             (1.00, (255, 252, 236))]
    span = max(1, x1 - x0)
    for x in range(W):
        t = min(1.0, max(0.0, (x - x0) / span))
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                f = (t - t0) / max(1e-6, t1 - t0)
                col = tuple(int(c0[k] + (c1[k] - c0[k]) * f) for k in range(3)) + (255,)
                gd.line([(x, 0), (x, H)], fill=col)
                break
    grad.putalpha(canvas_mask)
    out = Image.alpha_composite(out, grad)
    # قلب النور: خيط رفيع مضيء يتبع محور الحرف
    core = canvas_mask.filter(ImageFilter.MinFilter((int(size * 0.030) | 1)))
    core = core.filter(ImageFilter.GaussianBlur(size * 0.006)).point(
        lambda v: int(v * 0.78))
    layer = Image.new("RGBA", (W, H), (255, 252, 240, 255))
    layer.putalpha(core)
    out = Image.alpha_composite(out, layer)
    # لمعة عند رأس الحرف
    head = Image.new("L", (W, H), 0)
    ImageDraw.Draw(head).ellipse([W / 2 - w * 0.5, H * 0.10 - w * 0.4,
                                  W / 2 + w * 0.5, H * 0.10 + w * 0.4], fill=120)
    head = head.filter(ImageFilter.GaussianBlur(w * 0.35))
    layer = Image.new("RGBA", (W, H), (255, 240, 205, 255))
    layer.putalpha(Image.composite(head, Image.new("L", (W, H), 0), canvas_mask))
    out = Image.alpha_composite(out, layer)
    # نقيس الحبر (بلا قصّ، حتى لا تُقطع الهالة بحدود حادة)
    bx0, by0, bx1, by1 = canvas_mask.getbbox()
    return out, (bx0 / W, by0 / H, bx1 / W, by1 / H)



# --------------------------------------------------------------------------- #
# التركيب
# --------------------------------------------------------------------------- #
GRADE = None


class Compositor:
    def __init__(self, plan: dict, root: Path, work: Path, spec):
        self.plan, self.root, self.work = plan, root, work
        self.a = Assets(plan, root, work, spec)
        self.W, self.H = plan["w"], plan["h"]
        self.sections = {s["id"]: s for s in plan["sections"]}
        self._glyph_cache: dict = {}
        self._ring_cache: dict = {}
        self.glyph_cfg = {
            "s1": {"h": 0.58, "y": 0.52, "alpha": [(0.9, 0), (2.3, 0.97)],
                   "wscale": [(0.9, 0.03), (3.4, 1.0)], "beam": True},
            "s2": {"h": 0.40, "y": 0.42, "alpha": [(0.3, 0), (1.3, 0.94)], "ring": (0.40, 0.60)},
            "s3": {"h": 0.44, "y": 0.47, "alpha": [(0.3, 0), (1.2, 0.92)], "ring": (0.42, 0.5)},
            "s4": {"h": 0.40, "y": 0.45, "alpha": [(0.3, 0), (1.4, 0.92)]},
            "s5": {"h": 0.42, "y": 0.44, "alpha": [(0.5, 0), (2.0, 0.88)]},
            "s6": {"h": 0.48, "y": 0.52, "alpha": [(0.4, 0), (1.3, 0.95)], "ring": (0.46, 0.26)},
            "s7": {"h": 0.46, "y": 0.47, "alpha": [(0.2, 0), (1.2, 0.95)],
                   "rise": [(0.2, 0.55), (6.0, 0.40)]},
        }

    # ---- كاميرا ----
    def _camera(self, shot: dict, u: float):
        z = shot["z0"] + (shot["z1"] - shot["z0"]) * ease(u)
        fx, fy = shot["focus"]
        mv = shot["move"]
        if mv == "tilt_up":
            fy = 0.72 + (0.40 - 0.72) * ease(u)
        elif mv == "pan_right":
            fx = 0.38 + (0.62 - 0.38) * ease(u)
        elif mv == "hold_drift":
            fx += 0.012 * math.sin(u * 2.4)
            fy += 0.010 * math.sin(u * 1.7 + 1.2)
        elif mv == "diag":
            fx += 0.05 * ease(u)
            fy -= 0.05 * ease(u)
        return z, fx, fy

    def _shot_frame(self, shot: dict, t: float) -> Image.Image:
        u = clamp((t - shot["start"]) / max(1e-6, shot["end"] - shot["start"]))
        if shot["plate"] is None:
            return self._black_frame(shot, u)
        base = self.a.plate(shot["plate"])
        z, fx, fy = self._camera(shot, u)
        bw, bh = base.width / z, base.height / z
        x = clamp(fx * base.width - bw / 2, 0, base.width - bw)
        y = clamp(fy * base.height - bh / 2, 0, base.height - bh)
        box = (int(x), int(y), min(base.width, int(x + bw)), min(base.height, int(y + bh)))
        return base.crop(box).resize((self.W, self.H), Image.BILINEAR)

    def _black_frame(self, shot: dict, u: float) -> Image.Image:
        im = Image.new("RGB", (self.W, self.H), (4, 4, 6))
        if shot["move"] == "black_line":
            grow = ramp(u, [(0.0, 0.0), (0.55, 1.0)])
            h = int(self.H * 0.92 * grow)
            if h > 4:
                beam = self.a.beam.crop((0, 0, self.a.beam.width, h))
                beam = beam.resize((int(self.a.beam.width * 0.55), h), Image.BILINEAR)
                rgba = im.convert("RGBA")
                rgba.alpha_composite(beam, ((self.W - beam.width) // 2, (self.H - h) // 2))
                im = rgba.convert("RGB")
        return im

    # ---- طبقات ----
    def _glyph_layer(self, sec_id: str, t_local: float, t: float) -> Image.Image | None:
        cfg = self.glyph_cfg.get(sec_id)
        if not cfg:
            return None
        alpha = ramp(t_local, cfg["alpha"])
        if alpha <= 0.01:
            return None
        g = self.a.glyph
        ix0, iy0, ix1, iy1 = self.a.glyph_ink
        ink_h = max(1.0, (iy1 - iy0) * g.height)
        ink_c = (iy0 + iy1) / 2
        scale = (cfg["h"] * self.H) / ink_h  # ارتفاع الحبر كنسبة من الإطار
        wscale = ramp(t_local, cfg["wscale"]) if "wscale" in cfg else 1.0
        gw = max(2, int(g.width * scale * max(0.01, wscale)))
        gh = max(2, int(g.height * scale))
        key = (sec_id, gh)
        base_img = self._glyph_cache.get(key)
        if base_img is None:
            base_img = g.resize((int(g.width * scale), gh), Image.BICUBIC)
            if len(self._glyph_cache) > 6:
                self._glyph_cache.pop(next(iter(self._glyph_cache)))
            self._glyph_cache[key] = base_img
        img = base_img if abs(gw - base_img.width) < 2 else base_img.resize((gw, gh), Image.BILINEAR)
        if alpha < 0.995:
            a = img.split()[3].point(lambda v: int(v * alpha))
            img = img.copy()
            img.putalpha(a)
        yfrac = ramp(t_local, cfg["rise"]) if "rise" in cfg else cfg["y"]
        cy = int(yfrac * self.H)
        top = cy - int(ink_c * gh)
        canvas = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        # ظلّ محيطي ناعم: يفصل الحرف عن لوحات الإضاءة القوية
        bw2, bh2 = int(gw * 0.95), int(gh * 0.92)
        back = Image.new("L", (bw2, bh2), 0)
        ImageDraw.Draw(back).ellipse([bw2 * 0.18, bh2 * 0.02, bw2 * 0.82, bh2 * 0.98], fill=190)
        back = back.filter(ImageFilter.GaussianBlur(max(6, int(gw * 0.16))))
        glowl = Image.new("RGBA", (bw2, bh2), (8, 5, 3, 255))
        glowl.putalpha(back.point(lambda v: int(v * alpha * 0.55)))
        canvas.alpha_composite(glowl, ((self.W - gw) // 2, top - int(bh2 * 0.04)))
        canvas.alpha_composite(img, ((self.W - gw) // 2, top))
        return canvas

    def _ring_layer(self, sec_id: str, t_local: float, t: float) -> Image.Image | None:
        cfg = self.glyph_cfg.get(sec_id, {})
        if "ring" not in cfg:
            return None
        size_frac, base_alpha = cfg["ring"]
        fade = ramp(t_local, [(0.0, 0.0), (1.6, 1.0)])
        alpha = base_alpha * fade
        if alpha <= 0.02:
            return None
        size = int(size_frac * self.W * 2)
        ang = round(((t * 4.0) % 360) / 6.0) * 6.0
        key = (size, ang)
        ring = self._ring_cache.get(key)
        if ring is None:
            ring = self.a.ring.resize((size, size), Image.BICUBIC)
            ring = ring.rotate(ang, resample=Image.BICUBIC, center=(size / 2, size / 2))
            if len(self._ring_cache) > 24:
                self._ring_cache.pop(next(iter(self._ring_cache)))
            self._ring_cache[key] = ring
        a = ring.split()[3].point(lambda v: int(v * alpha))
        ring.putalpha(a)
        canvas = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        canvas.alpha_composite(ring, ((self.W - size) // 2, int(self.H * 0.45 - size / 2)))
        return canvas

    def _texts_layer(self, sec: dict, t: float) -> Image.Image | None:
        items = self.a.texts.get(sec["id"])
        if not items:
            return None
        canvas = None
        for item in items:
            tx = item["entry"]
            if not (tx["start"] - 0.5 <= t <= tx["end"] + 0.6):
                continue
            fin = ramp(t, [(tx["start"] - 0.5, 0.0), (tx["start"] + 0.35, 1.0)])
            fout = ramp(t, [(tx["end"] - 0.45, 1.0), (tx["end"] + 0.55, 0.0)])
            alpha = min(fin, fout)
            if alpha <= 0.01:
                continue
            drift = int((1 - alpha) * 14)
            y = tx.get("y") or self._text_y(tx["style"])
            if canvas is None:
                canvas = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            img = item["img"]
            if img.width > self.W * 0.92:
                k = self.W * 0.92 / img.width
                img = img.resize((int(img.width * k), int(img.height * k)), Image.LANCZOS)
            a = img.split()[3].point(lambda v: int(v * alpha))
            layer = img.copy()
            layer.putalpha(a)
            canvas.alpha_composite(layer, ((self.W - img.width) // 2,
                                           int(self.H * y) + drift - img.height // 2))
        return canvas

    def _text_y(self, style: str) -> float:
        return {"title": 0.145, "caption": 0.13, "numbers": 0.145, "creed": 0.30,
                "latin": 0.145, "note": 0.705}.get(style, 0.22)

    def _subs_layer(self, t: float) -> Image.Image | None:
        canvas = None
        active = []
        for cue in self.a.subs:
            if not (cue["start"] - 0.25 <= t <= cue["end"] + 0.35):
                continue
            fin = ramp(t, [(cue["start"] - 0.25, 0), (cue["start"] + 0.18, 1)])
            fout = ramp(t, [(cue["end"] - 0.18, 1), (cue["end"] + 0.30, 0)])
            alpha = min(fin, fout)
            if alpha > 0.01:
                active.append((alpha, cue))
        if active:
            alpha, cue = max(active, key=lambda x: x[0])
            canvas = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            img = cue["img"]
            a = img.split()[3].point(lambda v: int(v * alpha))
            layer = img.copy()
            layer.putalpha(a)
            canvas.alpha_composite(layer, ((self.W - img.width) // 2,
                                           int(self.H * 0.855) - img.height // 2))
        return canvas

    def _sweep(self, t: float) -> Image.Image | None:
        for shot in self.plan["shots"][1:]:
            d = t - shot["start"]
            if -0.52 <= d <= 0.52:
                u = (d + 0.52) / 1.04
                alpha = math.sin(math.pi * clamp(u)) ** 1.4 * 0.62
                if alpha <= 0.02:
                    return None
                band = self.a.band
                x = int(-band.width * 0.35 + (self.W + band.width * 0.7) * ease(clamp(u)))
                canvas = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
                b = band
                if alpha < 0.99:
                    b = band.copy()
                    b.putalpha(band.split()[3].point(lambda v: int(v * alpha)))
                canvas.alpha_composite(b, (x, 0))
                return canvas
        return None

    def _outro(self, t: float) -> Image.Image:
        o = self.plan["outro"]
        t0 = o["start"]
        u = clamp((t - t0) / o["dur"])
        W, H = self.W, self.H
        im = Image.new("RGBA", (W, H), (3, 3, 5, 255))

        # وهج ذهبي مركزي هادئ + دائرة رقيقة خلف الشعار
        glow = Image.new("L", (W, H), 0)
        r = int(W * 0.62)
        ImageDraw.Draw(glow).ellipse([W / 2 - r, H * 0.40 - r, W / 2 + r, H * 0.40 + r], fill=34)
        glow = glow.filter(ImageFilter.GaussianBlur(170))
        layer = Image.new("RGBA", (W, H), (255, 176, 80, 255))
        layer.putalpha(glow)
        im = Image.alpha_composite(im, layer)

        ring = self.a.ring.resize((int(W * 1.15), int(W * 1.15)), Image.LANCZOS)
        ring = ring.filter(ImageFilter.GaussianBlur(2))
        ra = ring.split()[3].point(lambda v: int(v * 0.30))
        ring.putalpha(ra)
        im.alpha_composite(ring, ((W - ring.width) // 2, int(H * 0.295 - ring.height / 2)))

        fade = ramp(t, [(t0, 0), (t0 + 1.2, 1)])
        em = self.a.emblem.resize((int(W * 0.30), int(W * 0.30)), Image.LANCZOS)
        im.alpha_composite(self._fade(em, fade), ((W - em.width) // 2, int(H * 0.295 - em.height / 2)))

        title = artext.gold_image(self.plan["academy"], self.a.font_amiri, 78, glow=16)
        im.alpha_composite(self._fade(title, ramp(t, [(t0 + 0.8, 0), (t0 + 2.1, 1)])),
                           ((W - title.width) // 2, int(H * 0.435 - title.height / 2)))

        rule = Image.new("RGBA", (int(W * 0.46), 2), (214, 172, 106, 200))
        fa = ramp(t, [(t0 + 1.5, 0), (t0 + 2.6, 1)])
        rw = max(2, int(rule.width * fa))
        rimg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        rimg.alpha_composite(rule.crop((0, 0, rw, 2)), ((W - rw) // 2, int(H * 0.487)))
        im = Image.alpha_composite(im, rimg)

        sub = artext.render("الألف (ا) — قطب الحروف", self.a.font_amiri, 58,
                            (244, 230, 204, 240), stroke=2, stroke_color=(0, 0, 0, 180))
        im.alpha_composite(self._fade(sub, ramp(t, [(t0 + 2.0, 0), (t0 + 3.2, 1)])),
                           ((W - sub.width) // 2, int(H * 0.523 - sub.height / 2)))

        lines = ["من عرف سر البداية…", "أدرك معنى الاستقامة."]
        for k, line in enumerate(lines):
            img = artext.render(line, self.a.font_amiri, 64, (240, 224, 196, 242), stroke=2,
                                stroke_color=(0, 0, 0, 170))
            a = ramp(t, [(t0 + 3.4 + k * 1.2, 0), (t0 + 4.6 + k * 1.2, 1)])
            im.alpha_composite(self._fade(img, a),
                               ((W - img.width) // 2, int(H * (0.595 + 0.055 * k)) - img.height // 2))

        note = artext.render("مادة ثقافية رمزية تعليمية — ليست حقائق علمية",
                             self.a.font_bold, 30, (206, 184, 152, 205), max_width=W * 0.88)
        im.alpha_composite(self._fade(note, ramp(t, [(t0 + 6.2, 0), (t0 + 7.8, 1)])),
                           ((W - note.width) // 2, int(H * 0.81)))

        mark = artext.render(self.plan["series"], self.a.font_bold, 27, (206, 182, 146, 170),
                             max_width=W * 0.9)
        im.alpha_composite(self._fade(mark, ramp(t, [(t0 + 1.0, 0), (t0 + 2.4, 1)])),
                           ((W - mark.width) // 2, int(H * 0.075)))

        out = im.convert("RGB")
        if u < 0.06:
            out = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), out, u / 0.06)
        return out

    @staticmethod
    def _fade(img: Image.Image, alpha: float) -> Image.Image:
        if alpha >= 0.999:
            return img
        out = img.copy()
        out.putalpha(img.split()[3].point(lambda v: int(v * max(0.0, alpha))))
        return out

    # ---- الإطار ----
    def frame(self, t: float) -> Image.Image:
        if t >= self.plan["outro"]["start"]:
            base = self._outro(t)
            return self._finish(base, t, overlay_scrim=False)

        shots = self.plan["shots"]
        idx = 0
        for i, s in enumerate(shots):
            if s["start"] <= t < s["end"]:
                idx = i
                break
        shot = shots[idx]
        img = self._shot_frame(shot, t)
        # تلاشٍ بين اللقطات
        if idx + 1 < len(shots):
            nxt = shots[idx + 1]
            d = 0.62
            if nxt["start"] - d <= t:
                u = clamp((t - (nxt["start"] - d)) / d)
                blend = self._shot_frame(nxt, t)
                img = Image.blend(img, blend, ease(u))

        sec = self.sections[shot["section"]]
        tl = t - sec["start"]
        rgba = img.convert("RGBA")
        ring = self._ring_layer(sec["id"], tl, t)
        if ring:
            rgba = Image.alpha_composite(rgba, ring)
        g = self._glyph_layer(sec["id"], tl, t)
        if g:
            rgba = Image.alpha_composite(rgba, g)
        sweep = self._sweep(t)
        if sweep:
            rgba = Image.alpha_composite(rgba, sweep)
        txt = self._texts_layer(sec, t)
        if txt:
            rgba = Image.alpha_composite(rgba, txt)
        # شعار السلسلة في الافتتاح
        if sec["id"] == "s1" and t - sec["start"] < 4.2:
            mark = artext.render(self.plan["series"], self.a.font_bold, 26,
                                 (206, 184, 154, 165), max_width=self.W * 0.9)
            a = ramp(tl, [(0.6, 0), (1.8, 1)])
            rgba.alpha_composite(self._fade(mark, a), ((self.W - mark.width) // 2,
                                                       int(self.H * 0.062)))
        return self._finish(rgba.convert("RGB"), t)

    def _finish(self, img: Image.Image, t: float, overlay_scrim: bool = True) -> Image.Image:
        rgba = img.convert("RGBA")
        if overlay_scrim:
            sub = self._subs_layer(t)
            rgba = Image.alpha_composite(rgba, self.a.scrim)
            if sub:
                rgba = Image.alpha_composite(rgba, sub)
        arr = np.asarray(rgba.convert("RGB"), dtype=np.float32)
        arr *= self.a.vignette[:, :, None]
        # تراكم الطبقات
        arr = np.tanh(arr / 255.0 * 1.02) * 255.0
        idx = np.clip(arr, 0, 255).astype(np.uint8)
        out = np.stack([self.a.grade[c][idx[:, :, c]] for c in range(3)], axis=-1)
        g = self.a.grain[int(t * 30) % len(self.a.grain)]
        out = np.clip(out.astype(np.float32) + g[:, :, None] * 3.4, 0, 255).astype(np.uint8)
        return Image.fromarray(out)


# --------------------------------------------------------------------------- #
# الترميز
# --------------------------------------------------------------------------- #
def encode(comp: Compositor, audio_path: Path, out_path: Path, ffmpeg: str,
           start: float = 0.0, end: float | None = None, progress=None) -> Path:
    plan = comp.plan
    fps = plan["fps"]
    t0 = start
    t1 = plan["total"] if end is None else min(end, plan["total"])
    n = int(round((t1 - t0) * fps))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{plan['w']}x{plan['h']}",
           "-r", str(fps), "-i", "-",
           "-ss", str(t0), "-i", str(audio_path),
           "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-x264-params", "keyint=60:min-keyint=30:scenecut=0",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", f"{t1 - t0:.3f}", "-movflags", "+faststart", str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE)
    import time
    t_start = time.time()
    try:
        for i in range(n):
            t = t0 + i / fps
            fr = comp.frame(t)
            proc.stdin.write(np.asarray(fr, dtype=np.uint8).tobytes())
            if progress and (i % 60 == 0):
                el = time.time() - t_start
                eta = el / max(1, i) * (n - i) if i else 0
                progress(i, n, el, eta)
    finally:
        if proc.stdin:
            proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore") if proc.stderr else ""
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError("ffmpeg encode failed:\n" + err[-2500:])
    return out_path
