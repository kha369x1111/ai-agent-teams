"""تحريك الشخصيات فعليًا من صورة واحدة — Character / talking-portrait rig.

الفرق عن depth3d.py:
  depth3d يحرّك **الكاميرا** حول صورة ثابتة (لا يتحرك أحد داخل الصورة).
  live_char يحرّك **الأشخاص أنفسهم**:
      • رمشة العيون (Blink)
      • تحريك الفم مع الكلام (Lip-sync) — عرض الفم يتغيّر مع صوت كل سطر
      • تنفّس الصدر (Breathing) — تكبير/تصغير ١٪
      • ميل الرأس وانزياح الوزن ٢–٤ بكسل
      • رفّ الحاجبين عند بداية الجملة

كيف يجد الوجوه؟ يكشف البؤبؤ الداكن المستدير تلقائيًا، يتحقق من لون البشرة حوله،
ثم يبني «هيكل الوجه»: عينان + فم مشتق من هندسة العينين.

الاستخدام:
    python3 tools/live_char.py --detect                # ورقة تحقّق
    python3 tools/live_char.py --shots S17 S03         # مقاطع محددة
    python3 tools/live_char.py --all                   # كل الصور
    python3 tools/live_char.py --still s17_baby_closeup --u 0.5 --out _work/p.png
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "project"))

import depth3d as D3  # noqa: E402

ROOT = D3.ROOT
RAW = D3.RAW
W, H = D3.W, D3.H
FPS = D3.FPS
SAMPLES = ROOT / "_work/lip"


# --------------------------------------------------------------------------- #
# ١) كشف الوجه: بؤبؤ داكن + تحقّق من لون البشرة
# --------------------------------------------------------------------------- #
def _components(mask: np.ndarray):
    """مكوّنات متصلة (union-find) بلا مكتبات خارجية."""
    parent = {}
    ys, xs = np.nonzero(mask)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    pts = list(zip(ys.tolist(), xs.tolist()))
    for p in pts:
        parent[p] = p
    for (y, x) in pts:
        for dy, dx in ((1, 0), (0, 1), (1, 1), (1, -1)):
            nb = (y + dy, x + dx)
            if nb in parent:
                ra, rb = find((y, x)), find(nb)
                if ra != rb:
                    parent[rb] = ra
    groups: dict = {}
    for p in pts:
        groups.setdefault(find(p), []).append(p)
    return list(groups.values())


def _is_skin(rgb: np.ndarray) -> np.ndarray:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    warm = (r > 95) & (r > b + 22) & (g > 55) & (r - g < 95)
    dark_skin = (r > 55) & (r > b + 12) & (g > 35) & (r < 150)
    return warm | dark_skin


def detect_faces(img: Image.Image, max_faces: int = 4) -> list[dict]:
    """يرجع قائمة وجوه: {eye_l, eye_r, eye_dist, mouth, mouth_w, score} بنسب 0..1."""
    SW = 760
    SH = int(SW * img.height / img.width)
    sm = img.convert("RGB").resize((SW, SH), Image.BILINEAR)
    arr = np.asarray(sm, dtype=np.float32)
    lum = arr @ np.array([0.299, 0.587, 0.114], dtype=np.float32) / 255.0

    dark = lum < 0.26
    if dark.sum() < 4:
        return []
    total = dark.size
    skin = _is_skin(arr)

    cands = []
    for comp in _components(dark):
        area = len(comp)
        if not (0.00010 * total <= area <= 0.0075 * total):
            continue
        ys = [p[0] for p in comp]
        xs = [p[1] for p in comp]
        h = max(ys) - min(ys) + 1
        w = max(xs) - min(xs) + 1
        if not (0.45 <= w / h <= 2.3):
            continue
        if area / (w * h) < 0.50:               # ممتلئ = بؤبؤ، لا خيط/رمز
            continue
        cx = sum(xs) / len(xs) / SW
        cy = sum(ys) / len(ys) / SH
        r = math.sqrt(area / math.pi) / SW
        cands.append(dict(x=cx, y=cy, r=r, area=area))
    if len(cands) < 2:
        return []

    cands.sort(key=lambda c: -c["area"])
    faces, used = [], set()
    for i, a in enumerate(cands):
        if i in used:
            continue
        best = None
        for j, b in enumerate(cands):
            if j <= i or j in used:
                continue
            dy = abs(a["y"] - b["y"])
            dx = abs(a["x"] - b["x"])
            if dy > max(0.030, dx * 0.30):       # نفس خط النظر
                continue
            if dx < 0.018:                       # عينان لا بد أن تتباعدا
                continue
            ratio = max(a["r"], b["r"]) / max(1e-6, min(a["r"], b["r"]))
            if ratio > 1.7:
                continue
            # تحقّق بشرة: الخدّان أسفل العينين قليلًا
            cy = (a["y"] + b["y"]) / 2
            cx = (a["x"] + b["x"]) / 2
            cheek_y = int(min(SH - 1, (cy + dx * 0.85) * SH))
            ok = 0
            for fx in (cx - dx * 1.15, cx + dx * 1.15, cx):
                xi = int(np.clip(fx * SW, 0, SW - 1))
                if skin[cheek_y, xi]:
                    ok += 1
            if ok < 3:
                continue
            score = dx * (1.0 / (ratio + 0.05)) * (ok / 3)
            if best is None or score > best[0]:
                best = (score, j, dx, cy, cx)
        if best is None:
            continue
        score, j, dx, cy, cx = best
        b = cands[j]
        used.update({i, j})
        left, right = (a, b) if a["x"] < b["x"] else (b, a)
        faces.append(dict(
            eye_l=(left["x"], left["y"]),
            eye_r=(right["x"], right["y"]),
            eye_dist=dx,
            eye_r_px=dx * SW,
            mouth=(cx + dx * 0.06, (left["y"] + right["y"]) / 2 + dx * 1.12),
            mouth_w=dx * 0.62,
            center=(cx, cy),
            score=score,
        ))
        if len(faces) >= max_faces:
            break
    faces.sort(key=lambda f: -f["eye_dist"])
    return faces


# --------------------------------------------------------------------------- #
# ٢) صوت كل لقطة (لمزامنة الفم)
# --------------------------------------------------------------------------- #

def shot_audio_env(shot_id: str) -> np.ndarray | None:
    """منحنى صوت اللقطة/السطر بصيغة (n,2): [زمن, شدّة 0..1]."""
    tl = ROOT / "_work/timeline_full.json"
    if not tl.exists():
        return None
    try:
        data = json.loads(tl.read_text())
    except Exception:
        return None
    shot = next((s for s in data["shots"] if s["id"] == shot_id), None)
    if not shot:
        return None
    start, dur = shot["start"], shot["dur"]
    paths = [ROOT / p for p in shot.get("audio", []) if p]
    if not paths:
        return None
    import wave
    env = np.zeros(int(dur * 100) + 1, dtype=np.float32)
    for p in paths:
        if not p.exists():
            continue
        wav = p if p.suffix == ".wav" else p.with_suffix(".wav")
        if not wav.exists():
            continue
        try:
            with wave.open(str(wav), "rb") as f:
                ch, sw_, sr = f.getnchannels(), f.getsampwidth(), f.getframerate()
                raw = f.readframes(f.getnframes())
        except Exception:
            continue
        if sw_ != 2:
            continue
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        if ch > 1:
            a = a.reshape(-1, ch).mean(1)
        a /= 32768.0
        # طاقة كل ١٠ ملي ثانية
        hop = max(1, sr // 100)
        n = len(a) // hop
        if n == 0:
            continue
        e = np.abs(a[:n * hop].reshape(n, hop)).mean(1)
        e = np.clip(e / (np.percentile(e, 95) + 1e-6), 0, 1)
        begin = int((p.stem and 0) + 0)  # الصوت يبدأ مع اللقطة
        for k, v in enumerate(e):
            idx = begin + k
            if idx < len(env):
                env[idx] = max(env[idx], v)
    # تنعيم
    if env.max() <= 0.01:
        return None
    k = np.ones(5, dtype=np.float32) / 5
    env = np.convolve(env, k, mode="same")
    xs = np.arange(len(env)) / 100.0
    return np.stack([xs, env], 1)


# --------------------------------------------------------------------------- #
# ٣) محرّك الحركة
# --------------------------------------------------------------------------- #
BLINK_PERIOD = 3.4
BLINK_DUR = 0.15


def _ell_mask(w: int, h: int, feather: int = 6) -> Image.Image:
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).ellipse([1, 1, w - 2, h - 2], fill=255)
    return m.filter(ImageFilter.GaussianBlur(feather))


class CharacterMotion:
    """يضيف حركة الوجوه فوق أي إطار (يُستخدم بعد كاميرا depth3d)."""

    def __init__(self, img: Image.Image, faces=None, mouth_env=None,
                 blink=True, breath=True, sway=True, brows=True):
        self.faces = detect_faces(img) if faces is None else faces
        self.env = mouth_env
        self.do = dict(blink=blink, breath=breath, sway=sway, brows=brows)
        rng = np.random.default_rng(11)
        self.phase = rng.uniform(0, 2 * math.pi, 12)
        self._masks = {}
        # منطقة التنفّس: صدر/كتفان أسفل الوجه
        self.body = []
        for f in self.faces:
            dx = f["eye_dist"]
            cx, cy = f["center"]
            bw = max(0.18, dx * 3.4)
            bh = max(0.22, dx * 3.0)
            x0 = int(np.clip((cx - bw / 2) * W, 0, W - 40))
            y0 = int(np.clip((cy + dx * 1.9) * H, 0, H - 40))
            x1 = int(np.clip((cx + bw / 2) * W, x0 + 40, W))
            y1 = int(np.clip((cy + dx * 1.9 + bh) * H, y0 + 40, H))
            self.body.append((x0, y0, x1, y1))

    # ---------- الفم ----------
    def _mouth_open(self, t: float) -> float:
        if self.env is None:
            # بلا صوت: حركة كلام خفيفة جدًا
            return 0.18 + 0.14 * math.sin(t * 6.0)
        xs, ys = self.env[:, 0], self.env[:, 1]
        if t <= xs[0] or t >= xs[-1]:
            return 0.0
        return float(np.interp(t, xs, ys))

    def _draw_mouth(self, frame: Image.Image, t: float, f: dict) -> Image.Image:
        amp = self._mouth_open(t)
        if amp < 0.06:
            return frame
        mx, my = f["mouth"]
        mw = f["mouth_w"]
        cx, cy = int(mx * W), int(my * H)
        bw = max(10, int(mw * W))
        bh = max(6, int(mw * W * 0.55))
        x0, y0 = max(0, cx - bw // 2), max(0, cy - bh // 2)
        x1, y1 = min(W, x0 + bw), min(H, y0 + bh)
        if x1 - x0 < 10 or y1 - y0 < 8:
            return frame
        region = frame.crop((x0, y0, x1, y1))
        # افتح الفم: نضغط الجزء السفلي للأسفل + نُظلم الوسط (فتحة الفم)
        open_k = 0.35 + 0.65 * amp
        nh = max(6, int(region.height * (1.0 + 0.55 * open_k)))
        stretched = region.resize((region.width, nh), Image.BILINEAR)
        plate = region.copy()
        plate.paste(stretched, (0, 0))
        # بقعة داكنة رقيقة في المنتصف = فتحة الفم
        dark = Image.new("RGB", plate.size, (38, 18, 20))
        hole_w = int(plate.width * (0.42 + 0.16 * open_k))
        hole_h = max(2, int(plate.height * (0.26 + 0.30 * open_k)))
        hm = Image.new("L", plate.size, 0)
        ImageDraw.Draw(hm).ellipse(
            [plate.width // 2 - hole_w // 2, plate.height // 2 - hole_h // 2,
             plate.width // 2 + hole_w // 2, plate.height // 2 + hole_h // 2], fill=110)
        hm = hm.filter(ImageFilter.GaussianBlur(2))
        plate = Image.composite(dark, plate, hm)
        mask = _ell_mask(plate.width, plate.height, 4)
        frame.paste(plate, (x0, y0), mask)
        return frame

    # ---------- الرمشة ----------
    def _blink_k(self, t: float, i: int) -> float:
        off = (i * 1.13)
        phase = ((t + off) % BLINK_PERIOD) / BLINK_PERIOD
        dt = abs(phase - 0.6) * BLINK_PERIOD
        if dt >= BLINK_DUR:
            return 1.0
        u = dt / BLINK_DUR
        return 0.14 + 0.86 * (u ** 0.55)

    def _lid_color(self, img: Image.Image, f: dict):
        """لون الجفن = لون الخدّ أسفل العين (بشرة مضمونة)، مضيء قليلًا."""
        ex = f["eye_dist"]
        cx, cy = f["center"]
        pxs = []
        for fx in (-0.55, 0.0, 0.55):
            for fy in (0.95, 1.25):
                x = int(np.clip((cx + fx * ex) * W, 1, W - 2))
                y = int(np.clip((cy + fy * ex) * H, 1, H - 2))
                patch = np.asarray(img.crop((x - 6, y - 6, x + 6, y + 6)),
                                   dtype=np.float32).reshape(-1, 3)
                pxs.append(patch)
        allp = np.concatenate(pxs, 0)
        lum = allp @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        sel = allp[lum > np.percentile(lum, 25)]
        col = sel.mean(0) if len(sel) else np.array([205, 165, 140], dtype=np.float32)
        col = np.clip(col * 1.06 + 6, 0, 255)
        return tuple(int(v) for v in col)

    def _eye_box(self, img: Image.Image, pupil, ex) -> tuple | None:
        """يحدّد مستطيل العين كاملًا (بياض + بؤبؤ) حول البؤبؤ."""
        cx, cy = int(pupil[0] * W), int(pupil[1] * H)
        hw, hh = int(ex * W * 0.50), int(ex * H * 0.90)
        x0, y0 = max(0, cx - hw), max(0, cy - hh)
        x1, y1 = min(W, cx + hw), min(H, cy + hh)
        if x1 - x0 < 20 or y1 - y0 < 16:
            return None
        sub = np.asarray(img.crop((x0, y0, x1, y1)).convert("RGB"), dtype=np.float32)
        lum = sub @ np.array([0.299, 0.587, 0.114], dtype=np.float32) / 255.0
        r, g, b = sub[..., 0], sub[..., 1], sub[..., 2]
        sclera = lum > 0.60
        pupil = lum < 0.30
        cand = sclera | pupil
        if cand.sum() < 30:
            return None
        ys, xs = np.nonzero(cand)
        # تجاهل الضوضاء: خذ الشريحة القريبة من مركز البؤبؤ
        keep = (np.abs(xs - hw) < hw * 0.95) & (np.abs(ys - hh) < hh * 0.85)
        if keep.sum() < 30:
            return None
        xs, ys = xs[keep], ys[keep]
        bx0, bx1 = xs.min(), xs.max()
        by0, by1 = ys.min(), ys.max()
        pad_x, pad_y = int((bx1 - bx0) * 0.14) + 2, int((by1 - by0) * 0.14) + 2
        return (max(0, x0 + bx0 - pad_x), max(0, y0 + by0 - pad_y),
                min(W, x0 + bx1 + pad_x), min(H, y0 + by1 + pad_y))

    def _draw_blink(self, frame: Image.Image, t: float, f: dict, i: int) -> Image.Image:
        """جفن علوي بلون البشرة ينزل على العين كاملة."""
        k = self._blink_k(t, i)                        # 1 مفتوح · 0.14 مغمض
        if k > 0.99:
            return frame
        cover = float(np.clip((1.0 - k) / 0.86, 0.0, 1.0)) * 0.94
        lid = self._lid_color(frame, f)
        lash = tuple(int(c * 0.45) for c in lid)
        ex = f["eye_dist"]

        for pupil_pt in (f["eye_l"], f["eye_r"]):
            box = self._eye_box(frame, pupil_pt, ex)
            if box is None:
                continue
            x0, y0, x1, y1 = box
            w_, h_ = x1 - x0, y1 - y0
            if w_ < 12 or h_ < 10:
                continue
            lid_img = Image.new("RGB", (w_, h_), lid)
            d = ImageDraw.Draw(lid_img)
            down = int(h_ * (0.04 + cover * 0.96))
            if down > 1:
                d.line([(0, down), (w_ - 1, down)], fill=lash, width=max(1, int(h_ * 0.10)))
            # قناع: شكل العين (بيضاوي عريض) يتلاشى عند الحواف
            m = Image.new("L", (w_, h_), 0)
            ImageDraw.Draw(m).ellipse([1, 1, w_ - 2, h_ - 2], fill=255)
            m = m.filter(ImageFilter.GaussianBlur(max(1, int(min(w_, h_) * 0.10))))
            m = m.point(lambda v: int(v * cover))
            frame.paste(lid_img, (x0, y0), m)
        return frame

    # ---------- تنفّس + ميل + حواجب ----------
    def _breath_sway(self, frame: Image.Image, t: float) -> Image.Image:
        for i, box in enumerate(self.body):
            x0, y0, x1, y1 = box
            region = frame.crop(box)
            ph = self.phase[i % len(self.phase)]
            ang = 2 * math.pi
            s = 1.0 + (0.010 * math.sin(t * ang / 4.1 + ph) if self.do["breath"] else 0.0)
            dx = 2.4 * math.sin(t * ang / 6.3 + ph * 1.7) if self.do["sway"] else 0.0
            dy = 1.5 * math.sin(t * ang / 5.1 + ph * 2.1) if self.do["sway"] else 0.0
            nw, nh = max(8, int(region.width * s)), max(8, int(region.height * s))
            scaled = region.resize((nw, nh), Image.BILINEAR)
            plate = Image.new("RGB", region.size, (0, 0, 0))
            plate.paste(scaled, ((region.width - nw) // 2 + int(dx),
                                 (region.height - nh) // 2 + int(dy)))
            key = ("body", i)
            if key not in self._masks:
                self._masks[key] = _ell_mask(region.width, region.height, 15)
            frame.paste(plate, (x0, y0), self._masks[key])
        return frame

    def apply(self, frame: Image.Image, t: float) -> Image.Image:
        if self.body:
            frame = self._breath_sway(frame, t)
        for i, f in enumerate(self.faces):
            frame = self._draw_mouth(frame, t, f)
            if self.do["blink"]:
                frame = self._draw_blink(frame, t, f, i)
        return frame


# --------------------------------------------------------------------------- #
# ٤) الرندر
# --------------------------------------------------------------------------- #
def render_live(name: str, dur: float, shot_id=None, focus=None, strength=1.0,
                move=None, crf=19, out_dir=None, env=None):
    src = D3.find(name, RAW)
    if src is None:
        raise FileNotFoundError(f"{RAW}/{name}.jpg")
    move = move or D3.MOVE_FOR.get(shot_id or "", "dolly_in")
    focus = focus or D3.FOCUS.get(name, (0.5, 0.5))
    depth = D3.depth_for(name, focus)

    base = Image.open(src)
    cam = D3.Camera3D(base, depth, move, seed=abs(hash(name)) % 9973)
    faces = detect_faces(base)
    chars = CharacterMotion(base, faces=faces, mouth_env=env)

    out_dir = Path(out_dir) if out_dir else D3.CLIPS
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{name}.mp4"

    n = max(2, int(round(dur * FPS)))
    cmd = [D3.FF, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-an",
           "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL)
    for i in range(n):
        t = i / FPS
        frame = cam.frame(i / max(1, n - 1), strength)
        frame = chars.apply(frame, t)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    return out, len(faces)


def contact_sheet(path=None):
    """ورقة تحقّق: عيون (دوائر) + فم (مستطيل) لكل وجه مكتشف."""
    import shots_data
    names = []
    for s in shots_data.SHOTS:
        if s.get("img") and s["img"] not in names:
            names.append(s["img"])
    tw = 620
    tiles = []
    for n in names:
        p = D3.find(n, RAW)
        if p is None:
            continue
        img = Image.open(p).convert("RGB")
        faces = detect_faces(img)
        im = img.resize((tw, int(tw * H / W)), Image.BILINEAR)
        d = ImageDraw.Draw(im)
        for f in faces:
            for (ex, ey) in (f["eye_l"], f["eye_r"]):
                d.ellipse([ex * im.width - 7, ey * im.height - 7,
                           ex * im.width + 7, ey * im.height + 7],
                          outline=(0, 255, 0), width=2)
            mx, my = f["mouth"]
            mw = f["mouth_w"] * im.width
            mh = max(5, mw * 0.5)
            d.rectangle([mx * im.width - mw / 2, my * im.height - mh / 2,
                         mx * im.width + mw / 2, my * im.height + mh / 2],
                        outline=(255, 60, 60), width=2)
        d.text((5, 4), f"{n}  faces={len(faces)}", fill=(255, 255, 0))
        tiles.append(im)
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    tw, th = tiles[0].size
    sheet = Image.new("RGB", (cols * tw, rows * th), (18, 18, 22))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * tw, (i // cols) * th))
    out = Path(path or ROOT / "_work/faces_sheet.jpg")
    out.parent.mkdir(exist_ok=True)
    sheet.save(out, quality=88)
    return out, len(tiles), sum(1 for _ in tiles)


def main():
    ap = argparse.ArgumentParser(description="حركة شخصيات: رمشة + كلام + تنفّس")
    ap.add_argument("--shots", nargs="*")
    ap.add_argument("--images", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--still", metavar="NAME")
    ap.add_argument("--u", type=float, default=0.5)
    ap.add_argument("--strength", type=float, default=1.0)
    ap.add_argument("--move", default=None)
    ap.add_argument("--crf", type=int, default=19)
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-mouth", action="store_true")
    ap.add_argument("--detect", action="store_true")
    a = ap.parse_args()

    if a.detect:
        p, n, _ = contact_sheet()
        print(p, n, "images")
        return

    if a.still:
        src = D3.find(a.still, RAW)
        depth = D3.depth_for(a.still, D3.FOCUS.get(a.still, (0.5, 0.5)))
        base = Image.open(src)
        cam = D3.Camera3D(base, depth, a.move or "dolly_in")
        chars = CharacterMotion(base)
        frame = chars.apply(cam.frame(a.u, a.strength), a.u * 5.0)
        out = Path(a.out or f"_work/live_{a.still}.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        frame.save(out)
        print(out, "faces:", len(chars.faces))
        return

    import shots_data
    durs = D3.load_durations()
    shots = list(shots_data.SHOTS)
    if a.images:
        targets = [dict(id=None, img=n, dur=durs.get(n, 5.0),
                        focus=D3.FOCUS.get(n, (0.5, 0.5))) for n in a.images]
    else:
        if a.shots:
            want = {s.upper() for s in a.shots}
            shots = [s for s in shots if s["id"] in want]
        elif not a.all:
            ap.error("--shots S01 S17  أو  --all  أو  --images name  أو  --detect")
        seen, targets = set(), []
        for s in shots:
            img = s.get("img")
            if not img or img in seen:
                continue
            seen.add(img)
            targets.append(dict(id=s["id"], img=img, dur=durs.get(img, 5.0),
                                focus=tuple(s.get("focus", D3.FOCUS.get(img, (0.5, 0.5))))))

    for t in targets:
        env = None if a.no_mouth else shot_audio_env(t["id"] or "")
        print(f"  {t['id'] or '--':4s} {t['img']:24s} {t['dur']:5.2f}s", end="", flush=True)
        p, nf = render_live(t["img"], t["dur"], t["id"], t["focus"], a.strength,
                            a.move, a.crf, a.out, env)
        print(f"  faces={nf}  -> {p.stat().st_size / 1e6:.1f} MB")
    print(f"\nتم: {len(targets)} مقطعًا")


if __name__ == "__main__":
    main()
