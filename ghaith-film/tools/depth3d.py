"""تحريك ثلاثي الأبعاد حقيقي من صورة ثابتة — Depth-based 3D camera.

الفكرة بثلاث خطوات:
  1. نبني «خريطة عمق»: لكل بكسل رقم 0 (بعيد جدًا) … 1 (قريب من الكاميرا).
  2. نقصّ الصورة إلى ثلاث طبقات: قريبة، وسط، بعيدة.
  3. نحرّك كل طبقة بمقدار مختلف (القريبة تكبر وتزحف أكثر) → إحساس عمق حقيقي.
     ثم نضيف: عمق ميدان خفيف + تظليل أطراف + حبيبات فيلم → «واقعية».

الاستخدام:
    python3 tools/depth3d.py --shots S01 S17            # لقطات محددة
    python3 tools/depth3d.py --all --strength 1.2       # كل الصور
    python3 tools/depth3d.py --images s01_livingroom    # صورة بالاسم
    python3 tools/depth3d.py --still s17_baby_closeup --u 0.5 --out _work/preview.png

خريطة عمق من ذكاء اصطناعي (اختياري، أدق):
    ضع صورة رمادية بنفس الاسم في storyboard/depth/s01_livingroom.png
    ثم أضف --ai-depth   (الأبيض = قريب، الأسود = بعيد)

بعد التوليد:  bash make_film.sh     (المحرك يستخدم storyboard/clips تلقائيًا)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "project"))
import imageio_ffmpeg  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
RAW = ROOT / "storyboard/raw"
AIDEPTH = ROOT / "storyboard/depth"
CLIPS = ROOT / "storyboard/clips"
CACHE = ROOT / "_work/depth"
W, H = 1920, 1080
FPS = 24

# مركز الاهتمام الافتراضي لكل صورة (إن لم تحدّده shots_data)
FOCUS = {
    "s00_title": (0.50, 0.50),
    "s17_baby_closeup": (0.50, 0.45),
}


# --------------------------------------------------------------------------- #
# 1) خريطة العمق
# --------------------------------------------------------------------------- #
def _smoothstep(x, a, b):
    t = np.clip((x - a) / max(b - a, 1e-6), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _feather(mask: np.ndarray, radius: int = 14) -> np.ndarray:
    im = Image.fromarray((np.clip(mask, 0, 1) * 255).astype(np.uint8))
    im = im.filter(ImageFilter.GaussianBlur(radius))
    return np.asarray(im, dtype=np.float32) / 255.0


def estimate_depth(img: Image.Image, focus=(0.5, 0.5)) -> np.ndarray:
    """خريطة عمق تقديرية (0..1، 1 = قريب) من إشارات بصرية — بلا إنترنت وبلا نموذج."""
    small = img.convert("RGB").resize((W // 4, H // 4), Image.BILINEAR)
    rgb = np.asarray(small, dtype=np.float32) / 255.0
    h, w, _ = rgb.shape

    lum = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    fx, fy = focus[0] * w, focus[1] * h

    # (أ) القرب من مركز الاهتمام = الموضوع الرئيسي
    dist = np.sqrt(((xx - fx) / w) ** 2 + ((yy - fy) / h) ** 2)
    near_center = np.clip(1.0 - dist / 0.62, 0.0, 1.0) ** 1.5

    # (ب) المناطق المضيئة جدًا (نوافذ/سماء) عادة أبعد
    bright = np.clip((lum - 0.55) / 0.45, 0.0, 1.0)

    # (ج) تفاصيل الحواف = ملامح وملابس = أقرب
    gy, gx = np.gradient(lum)
    edges = np.clip(np.sqrt(gx ** 2 + gy ** 2) * 6.0, 0.0, 1.0)
    edges = np.asarray(Image.fromarray((edges * 255).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(5)), dtype=np.float32) / 255.0

    # (د) أسفل الصورة (أرضية) أقرب في اللقطات الداخلية
    bottom = np.clip((yy / h - 0.55) / 0.45, 0.0, 1.0)

    depth = 0.46 * near_center + 0.24 * edges + 0.18 * bottom + 0.12 * (1.0 - bright)
    d = Image.fromarray(((depth - depth.min()) / (np.ptp(depth) + 1e-6) * 255)
                        .astype(np.uint8))
    d = d.filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR)
    out = np.asarray(d, dtype=np.float32) / 255.0
    return (out - out.min()) / (np.ptp(out) + 1e-6)


def find(name: str, folder: Path, exts=(".jpg", ".png")) -> Path | None:
    for ext in exts:
        p = folder / f"{name}{ext}"
        if p.exists():
            return p
    return None


def depth_for(name: str, focus=(0.5, 0.5), ai: bool = False) -> np.ndarray:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / f"{name}_{focus[0]:.2f}_{focus[1]:.2f}{'_ai' if ai else ''}.npy"
    if key.exists():
        return np.load(key)

    if ai:
        p = find(name, AIDEPTH, (".png", ".jpg", ".jpeg"))
        if p is None:
            raise FileNotFoundError(
                f"لا توجد خريطة عمق في {AIDEPTH.name}/{name}.png — شغّل بلا --ai-depth")
        arr = np.asarray(Image.open(p).convert("L").resize((W, H), Image.BILINEAR),
                         dtype=np.float32) / 255.0
        arr = (arr - arr.min()) / (np.ptp(arr) + 1e-6)
    else:
        src = find(name, RAW)
        if src is None:
            raise FileNotFoundError(f"{RAW}/{name}.jpg")
        arr = estimate_depth(Image.open(src), focus)

    np.save(key, arr)
    return arr


# --------------------------------------------------------------------------- #
# 2) الطبقات والكاميرا
# --------------------------------------------------------------------------- #
def build_masks(depth: np.ndarray, feather: int = 14):
    """ثلاثة أقنعة ناعمة: قريب / وسط / بعيد."""
    near = _smoothstep(depth, 0.55, 0.78)
    far = 1.0 - _smoothstep(depth, 0.28, 0.50)
    mid = np.clip(1.0 - near - far, 0.0, 1.0)
    return [Image.fromarray((_feather(m, feather) * 255).astype(np.uint8))
            for m in (near, mid, far)]


# حركات الكاميرا — تُختار لكل لقطة لتنويع الإيقاع
MOVES = {
    "dolly_in":  dict(scale=(0.085, 0.048, 0.016), pan=(-36, -15, 0), tilt=(-9, -4, 0)),
    "dolly_out": dict(scale=(-0.070, -0.040, -0.014), pan=(30, 12, 0), tilt=(8, 3, 0)),
    "pan_left":  dict(scale=(0.030, 0.018, 0.006), pan=(58, 40, 20), tilt=(-4, -2, 0)),
    "pan_right": dict(scale=(0.030, 0.018, 0.006), pan=(-58, -40, -20), tilt=(-4, -2, 0)),
    "tilt_up":   dict(scale=(0.045, 0.026, 0.008), pan=(-10, -6, 0), tilt=(34, 16, 4)),
}

# الحركة الأنسب لكل مشهد — عدّلها كما تشاء
MOVE_FOR = {
    "S00": "dolly_in", "S01": "pan_right", "S02": "dolly_in", "S03": "pan_left",
    "S04": "dolly_out", "S05": "tilt_up", "S06": "pan_right", "S07": "dolly_in",
    "S08": "pan_left", "S09": "dolly_in", "S10": "dolly_out", "S11": "pan_right",
    "S12": "tilt_up", "S13": "dolly_in", "S14": "pan_left", "S15": "dolly_in",
    "S16": "pan_right", "S17": "dolly_in", "S18": "dolly_out", "S19": "pan_left",
    "S20": "dolly_in", "S21": "tilt_up", "S22": "pan_right", "S23": "dolly_in",
    "S24": "pan_left", "S25": "dolly_in", "S26": "dolly_out", "S27": "tilt_up",
    "S28": "pan_right", "S29": "dolly_in", "S30": "pan_left", "S31": "dolly_in",
    "S32": "pan_right", "S33": "dolly_in", "S34": "dolly_out", "S35": "tilt_up",
    "S36": "pan_left", "S37": "dolly_in",
}


class Camera3D:
    """كاميرا افتراضية بثلاث طبقات عمق + لمسات واقعية."""

    def __init__(self, img: Image.Image, depth: np.ndarray, move: str = "dolly_in",
                 seed: int = 0, film_grain: bool = True, dof: bool = True,
                 vignette: bool = True):
        self.img = img.convert("RGB").resize((W, H), Image.LANCZOS)
        self.alpha = build_masks(depth)
        self.cfg = MOVES.get(move, MOVES["dolly_in"])
        self.move = move
        self.grain, self.dof = film_grain, dof
        self.base = (1.11, 1.06, 1.03)      # تكبير أساسي يمنع أي فراغ
        rng = np.random.default_rng(seed)
        self.phase = rng.uniform(0, 2 * np.pi, 3)
        self._vig = self._make_vignette() if vignette else None

    @staticmethod
    def _make_vignette() -> Image.Image:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx / W - 0.5) * 1.15) ** 2 + ((yy / H - 0.5) * 1.15) ** 2)
        v = 1.0 - 0.30 * np.clip((r - 0.32) / 0.62, 0, 1) ** 1.7
        return Image.fromarray((np.stack([v] * 3, -1) * 255).astype(np.uint8))

    def _layer(self, alpha: Image.Image, scale: float, tx: float, ty: float,
               blur: float = 0.0):
        w2, h2 = max(2, int(W * scale)), max(2, int(H * scale))
        im = self.img.resize((w2, h2), Image.BILINEAR)
        a = alpha.resize((w2, h2), Image.BILINEAR)
        if blur > 0:
            im = im.filter(ImageFilter.GaussianBlur(blur))
        ox, oy = (W - w2) // 2 + int(tx), (H - h2) // 2 + int(ty)
        canvas = Image.new("RGB", (W, H), (0, 0, 0))
        acanvas = Image.new("L", (W, H), 0)
        canvas.paste(im, (ox, oy))
        acanvas.paste(a, (ox, oy))
        return canvas, acanvas

    def frame(self, u: float, strength: float = 1.0, shake: float = 0.30) -> Image.Image:
        e = u * u * (3 - 2 * u)                      # ease in/out
        sc = [b + s * strength * e for b, s in zip(self.base, self.cfg["scale"])]
        drift = (e - 0.5) * strength
        dx = shake * np.sin(u * 7.3 + self.phase[0]) * 1.7
        dy = shake * np.sin(u * 5.1 + self.phase[1]) * 1.3

        out = Image.new("RGB", (W, H), (0, 0, 0))
        for i in range(3):
            li, la = self._layer(
                self.alpha[i], sc[i],
                self.cfg["pan"][i] * drift + dx,
                self.cfg["tilt"][i] * drift + dy,
                blur=(1.0 if (self.dof and i == 2) else 0.0),
            )
            out = Image.composite(li, out, la)

        if self._vig is not None:
            out = ImageChops.multiply(out, self._vig)
        if self.grain:
            out = self._add_grain(out, u)
        return out

    def _add_grain(self, im: Image.Image, u: float) -> Image.Image:
        rng = np.random.default_rng(int(u * 100000) + 7)
        n = rng.normal(0, 3.1, (H // 2, W // 2)).astype(np.float32)
        n = np.repeat(np.repeat(n, 2, 0), 2, 1)
        arr = np.asarray(im, dtype=np.float32) + n[..., None]
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


# --------------------------------------------------------------------------- #
# 3) توليد المقاطع
# --------------------------------------------------------------------------- #
def load_durations() -> dict:
    """مدّة كل صورة = مجموع لقطاتها (المقطع الواحد يُقصّ من بدايته لكل لقطة)."""
    for p in (ROOT / "_work/timeline_full.json", ROOT / "_work/timeline_plan.json"):
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text())
        except Exception:
            continue
        durs: dict = {}
        for s in data.get("shots", []):
            if s.get("img") and "dur" in s:
                durs[s["img"]] = durs.get(s["img"], 0.0) + float(s["dur"])
        if durs:
            return {k: v + 0.6 for k, v in durs.items()}
    return {}


def render_shot(name, dur, shot_id=None, focus=None, strength=1.0, move=None,
                crf=19, out_dir=None, ai=False):
    src = find(name, RAW)
    if src is None:
        raise FileNotFoundError(f"{RAW}/{name}.jpg")
    move = move or MOVE_FOR.get(shot_id or "", "dolly_in")
    focus = focus or FOCUS.get(name, (0.5, 0.5))
    depth = depth_for(name, focus, ai=ai)

    cam = Camera3D(Image.open(src), depth, move, seed=abs(hash(name)) % 9973)
    out_dir = Path(out_dir) if out_dir else CLIPS
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{name}.mp4"

    n = max(2, int(round(dur * FPS)))
    cmd = [FF, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-an",
           "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL)
    for i in range(n):
        proc.stdin.write(cam.frame(i / max(1, n - 1), strength).tobytes())
    proc.stdin.close()
    proc.wait()
    return out


def main():
    ap = argparse.ArgumentParser(description="تحريك 3D من صورة واحدة")
    ap.add_argument("--shots", nargs="*", help="أرقام لقطات مثل S01 S17")
    ap.add_argument("--all", action="store_true", help="كل صور الفيلم")
    ap.add_argument("--images", nargs="*", help="أسماء صور مباشرة")
    ap.add_argument("--strength", type=float, default=1.0, help="قوة الحركة 0.5 … 2.0")
    ap.add_argument("--move", choices=sorted(MOVES), help="نوع حركة الكاميرا")
    ap.add_argument("--crf", type=int, default=19)
    ap.add_argument("--out", help="مجلد الإخراج")
    ap.add_argument("--ai-depth", action="store_true", help="استخدم خرائط storyboard/depth")
    ap.add_argument("--still", metavar="NAME", help="صورة واحدة فقط (اختبار سريع)")
    ap.add_argument("--u", type=float, default=0.5, help="نقطة الزمن للاختبار")
    a = ap.parse_args()

    if a.still:
        src = find(a.still, RAW)
        if src is None:
            ap.error(f"لا توجد صورة {a.still}")
        depth = depth_for(a.still, FOCUS.get(a.still, (0.5, 0.5)), a.ai_depth)
        cam = Camera3D(Image.open(src), depth, a.move or "dolly_in")
        p = Path(a.out or f"_work/preview_{a.still}.png")
        p.parent.mkdir(parents=True, exist_ok=True)
        cam.frame(a.u, a.strength).save(p)
        print(p)
        return

    import shots_data

    durs = load_durations()
    shots = list(shots_data.SHOTS)

    if a.images:
        targets = [dict(id=None, img=n, dur=durs.get(n, 5.0),
                        focus=FOCUS.get(n, (0.5, 0.5))) for n in a.images]
    else:
        if a.shots:
            want = {s.upper() for s in a.shots}
            shots = [s for s in shots if s["id"] in want]
        elif not a.all:
            ap.error("استخدم --shots S01 S17  أو  --all  أو  --images name")
        seen, targets = set(), []
        for s in shots:
            img = s.get("img")
            if not img or img in seen:
                continue
            seen.add(img)
            targets.append(dict(id=s["id"], img=img, dur=durs.get(img, 5.0),
                                focus=tuple(s.get("focus", FOCUS.get(img, (0.5, 0.5))))))

    total = 0.0
    for t in targets:
        print(f"  {t['id'] or '--':4s} {t['img']:24s} {t['dur']:5.2f}s", end=" ... ", flush=True)
        p = render_shot(t["img"], t["dur"], t["id"], t["focus"], a.strength, a.move,
                        a.crf, a.out, a.ai_depth)
        print(f"{p.stat().st_size / 1e6:.1f} MB")
        total += t["dur"]
    print(f"\nتم: {len(targets)} مقطعًا · {total:.1f} ثانية → {Path(a.out or CLIPS)}")


if __name__ == "__main__":
    main()
