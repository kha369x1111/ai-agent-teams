"""تحريك الشخصيات فعليًا: كلام متزامن مع الصوت + تنفّس + حركة كاميرا خفيفة.

لا يحرّك الكاميرا فقط — بل **يفتح أفواه الشخصيات** بحسب صوت كل سطر.

كيف يعمل؟
  لكل صورة أساسية (A) نولّد إطارًا ثانيًا (B) بنفس المشهد لكن الأفواه مفتوحة.
  عند الرندر نقيس شدّة الصوت في كل لحظة، ثم نمزج A و B **بداخل منطقة الاختلاف فقط**
  (قناع مشتق من فرق الصورتين), فيظهر الفم مفتوحًا وقافلًا مع الكلام دون أي ظلال مزدوجة.

    storyboard/raw/s03_nana_worried.jpg        ← الإطار A (فم مغلق) — الأصلي
    _work/keys/s03_nana_worried_B.png          ← الإطار B (فم مفتوح)

الاستخدام:
    python3 tools/talk_char.py --shots S03 S02          # مقاطع محددة
    python3 tools/talk_char.py --all                    # كل الصور المتوفرة
    python3 tools/talk_char.py --still s03_nana_worried --u 0.5 --amp 1 --out _work/p.png
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "project"))

import depth3d as D3  # noqa: E402

ROOT = D3.ROOT
RAW = D3.RAW
KEYS_DIRS = [ROOT / "storyboard/keys", ROOT / "_work/keys"]
W, H = D3.W, D3.H
FPS = D3.FPS


# --------------------------------------------------------------------------- #
# ١) قناع الكلام = منطقة الاختلاف بين A و B
# --------------------------------------------------------------------------- #
def load_pair(name: str):
    a_path = D3.find(name, RAW)
    b_path = None
    for folder in KEYS_DIRS:
        for ext in (".jpg", ".png"):
            p = folder / f"{name}_B{ext}"
            if p.exists():
                b_path = p
                break
        if b_path is not None:
            break
    if a_path is None:
        return None, None, None
    a = Image.open(a_path).convert("RGB").resize((W, H), Image.LANCZOS)
    if b_path is None:
        return a, None, None
    b = Image.open(b_path).convert("RGB").resize((W, H), Image.LANCZOS)
    mask = speech_mask(a, b, name=name)
    return a, b, mask


def _components(mask: np.ndarray, step: int = 2):
    """مكوّنات متصلة سريعة على شبكة مخفّضة."""
    h, w = mask.shape
    hh, ww = h // step, w // step
    grid = mask[:hh * step, :ww * step].reshape(hh, step, ww, step).max(axis=(1, 3))
    seen = np.zeros_like(grid, dtype=bool)
    out = []
    from collections import deque
    for y in range(hh):
        for x in range(ww):
            if not grid[y, x] or seen[y, x]:
                continue
            q = deque([(y, x)])
            seen[y, x] = True
            cells = []
            while q:
                cy, cx = q.popleft()
                cells.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < hh and 0 <= nx < ww and grid[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            out.append(dict(y0=min(ys) * step, y1=(max(ys) + 1) * step,
                            x0=min(xs) * step, x1=(max(xs) + 1) * step,
                            n=len(cells)))
    return sorted(out, key=lambda c: -c["n"])


# مواضع فم مضبوطة يدويًا للصور التي يخفق فيها الكشف التلقائي
MOUTH_HINTS = {
    "s01_livingroom": (0.185, 0.300, 0.028, 0.032),
    "s02_gigi_dad": (0.345, 0.462, 0.045, 0.050),
    "s03_nana_worried": (0.395, 0.452, 0.040, 0.044),
    "s04_candle_talk": (0.452, 0.445, 0.040, 0.044),
    "s05_mission_cheer": (0.545, 0.525, 0.028, 0.032),
    "s06_group_hug": (0.520, 0.497, 0.032, 0.036),
    "s10_nana_card": (0.375, 0.478, 0.042, 0.046),
    "s17_baby_closeup": (0.318, 0.645, 0.050, 0.054),
    "s19_nana_pinky": (0.485, 0.552, 0.040, 0.044),
    "s20_sara_proud": (0.487, 0.452, 0.045, 0.050),
}


def find_mouth(a: Image.Image, b: Image.Image, name: str | None = None) -> tuple[float, float, float, float]:
    """يحدّد الفم: نافذة صغيرة تكون «أغمق في B» ومحاطة بمناطق لم تتغيّر."""
    if name and name in MOUTH_HINTS:
        return MOUTH_HINTS[name]
    SW, SH = 640, 360
    A = np.asarray(a.convert("L").resize((SW, SH), Image.BILINEAR), dtype=np.float32)
    B = np.asarray(b.convert("L").resize((SW, SH), Image.BILINEAR), dtype=np.float32)
    dark = np.clip((A - B) / 40.0, 0, 1)                # صار أغمق = فتحة الفم
    dark = np.asarray(Image.fromarray((dark * 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float32) / 255.0

    ii = np.zeros((SH + 1, SW + 1), dtype=np.float64)
    ii[1:, 1:] = dark.cumsum(0).cumsum(1)

    def box_sum(x0, y0, x1, y1):
        return ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]

    best = None
    for side in (0.055, 0.075, 0.095, 0.115):
        bw, bh = int(SW * side), int(SH * side * 1.25)
        if bw < 8 or bh < 8:
            continue
        step = max(4, bw // 4)
        for y0 in range(0, SH - bh - 1, step):
            for x0 in range(0, SW - bw - 1, step):
                inside = box_sum(x0, y0, x0 + bw, y0 + bh) / (bw * bh)
                # محيط أوسع للمقارنة
                ox0, oy0 = max(0, x0 - bw), max(0, y0 - bh)
                ox1, oy1 = min(SW, x0 + 2 * bw), min(SH, y0 + 2 * bh)
                ring = (box_sum(ox0, oy0, ox1, oy1) - box_sum(x0, y0, x0 + bw, y0 + bh))
                ring_n = max(1, (ox1 - ox0) * (oy1 - oy0) - bw * bh)
                outside = ring / ring_n
                score = inside - outside * 1.05 + inside * side * 2.0
                if best is None or score > best[0]:
                    best = (score, x0, y0, bw, bh, inside)
    if best is None:
        return (0.5, 0.5, 0.10, 0.10)
    _, x0, y0, bw, bh, inside = best
    if inside < 0.10:                                   # لا تغيّر واضح
        return (0.5, 0.5, 0.10, 0.10)
    return ((x0 + bw / 2) / SW, (y0 + bh / 2) / SH,
            (bw / SW) * 1.45, (bh / SH) * 1.6)


def speech_mask(a: Image.Image, b: Image.Image, hint=None, blur: int = 26,
                keep: float = 0.42, name: str | None = None,
                rx: float = 0.125, ry: float = 0.105) -> Image.Image:
    """قناع الفم: قطعة ناقصة كبيرة حول «أقوى تغيّر محلي» بين A و B.

    التجربة أثبتت أن قناعًا صغيرًا جدًا حول نقطة واحدة لا يكفي (النزوح بين
    الإطارين يغطي منطقة أكبر)، وأن القناع الكبير الناعم يعطي فتح فم طبيعيًا.
    """
    A = np.asarray(a.convert("L"), dtype=np.float32)
    B = np.asarray(b.convert("L"), dtype=np.float32)
    d = np.abs(A - B)
    # نزيل التغيّر المنخفض التردّد (فرق إضاءة/إزاحة كاميرا) ونُبقي التغيّر المحلي
    low = np.asarray(Image.fromarray(np.clip(d, 0, 255).astype(np.uint8))
                     .filter(ImageFilter.GaussianBlur(50)), dtype=np.float32)
    hi = np.asarray(Image.fromarray(np.clip(d - low, 0, 255).astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(4)), dtype=np.float32)

    # نتجاهل الأطراف
    search = hi.copy()
    search[:int(H * 0.10)] = 0
    search[-int(H * 0.10):] = 0
    search[:, :int(W * 0.05)] = 0
    search[:, -int(W * 0.05):] = 0
    if hint is not None:                        # لو أعطينا نقطة مبدئية، نبحث حولها فقط
        hx, hy = hint[0], hint[1]
        win = np.zeros_like(search)
        x0 = int(max(0, (hx - 0.18) * W)); x1 = int(min(W, (hx + 0.18) * W))
        y0 = int(max(0, (hy - 0.18) * H)); y1 = int(min(H, (hy + 0.18) * H))
        win[y0:y1, x0:x1] = search[y0:y1, x0:x1]
        search = win

    peak = float(search.max())
    if peak < 3.0:                               # لا تغيّر محلي واضح
        peak = 3.0
    iy, ix = np.unravel_index(int(np.argmax(search)), search.shape)

    shape = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shape).ellipse(
        [ix - rx * W, iy - ry * H, ix + rx * W, iy + ry * H], fill=255)
    shape = shape.filter(ImageFilter.GaussianBlur(blur))

    arr = np.asarray(shape, dtype=np.float32) / 255.0
    arr = np.clip(arr * float(np.clip(peak / 25.0, 0.85, 1.0)), 0, 1)
    return Image.fromarray((arr * 255).astype(np.uint8))


# --------------------------------------------------------------------------- #
# ٢) منحنى الكلام من صوت اللقطة
# --------------------------------------------------------------------------- #
def speech_curve(shot_id: str) -> np.ndarray | None:
    """منحنى الكلام لسطر اللقطة: [(زمن نسبي للقطة, شدّة 0..1)]."""
    tl = ROOT / "_work/timeline_full.json"
    if not tl.exists():
        return None
    try:
        data = json.loads(tl.read_text())
    except Exception:
        return None
    shot = next((s for s in data.get("shots", []) if s["id"] == shot_id), None)
    if not shot:
        return None
    dur = float(shot["dur"])
    start = float(shot["start"])
    env = np.zeros(int(dur * 100) + 2, dtype=np.float32)

    def read_wav(p: Path):
        """يقرأ wav/mp3 مباشرة (ffmpeg يحوّل إلى 16 kHz أحادي)."""
        if not p.exists():
            alt = p.with_suffix(".wav")
            if alt.exists():
                p = alt
            else:
                return None
        sr = 16000
        if p.suffix.lower() == ".wav":
            try:
                with wave.open(str(p), "rb") as f:
                    ch, sw_, sr0 = f.getnchannels(), f.getsampwidth(), f.getframerate()
                    raw = f.readframes(f.getnframes())
                if sw_ == 2 and sr0 > 0:
                    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                    if ch > 1:
                        a = a.reshape(-1, ch).mean(1)
                    sr = sr0
                    hop = max(1, sr // 100)
                    n = len(a) // hop
                    return np.abs(a[:n * hop].reshape(n, hop)).mean(1) if n else None
            except Exception:
                pass
        try:
            out = subprocess.run([D3.FF, "-v", "error", "-i", str(p), "-ac", "1",
                                  "-ar", str(sr), "-f", "s16le", "-"],
                                 capture_output=True, timeout=120)
            a = np.frombuffer(out.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception:
            return None
        if a.size == 0:
            return None
        hop = max(1, sr // 100)
        n = len(a) // hop
        if n == 0:
            return None
        return np.abs(a[:n * hop].reshape(n, hop)).mean(1)

    found = False
    for item in data.get("audio", []):
        # نأخذ كل سطر يبدع داخل حدود اللقطة زمنيًا
        s0 = float(item["start"])
        s1 = s0 + float(item["dur"])
        if s1 < start + 0.05 or s0 > start + dur - 0.05:
            continue
        p = Path(item["src"])
        e = read_wav(p)
        if e is None:
            continue
        e = e / (np.percentile(e, 96) + 1e-6)
        e = np.clip(e, 0, 1.3)
        offset = float(item["start"]) - start          # زمن نسبي للقطة
        for k, v in enumerate(e):
            idx = int(round((offset + k / 100.0) * 100))
            if 0 <= idx < len(env):
                env[idx] = max(env[idx], v)
        found = True
    if not found or env.max() < 0.02:
        return None
    env = np.convolve(env, np.ones(4) / 4, mode="same")
    env = np.clip((env - 0.08) / 0.55, 0, 1) ** 0.7
    xs = np.arange(len(env)) / 100.0
    return np.stack([xs, env], 1)


# --------------------------------------------------------------------------- #
# ٣) المحرك
# --------------------------------------------------------------------------- #
class TalkRig:
    """يمزج A↔B بقناع الكلام + تنفّس + وميض عينين خفيف."""

    def __init__(self, a: Image.Image, b: Image.Image | None, mask: Image.Image | None,
                 curve: np.ndarray | None, breath: bool = True, seed: int = 0):
        self.a = a
        self.b = b
        self.curve = curve
        self.mask_arr = np.asarray(mask, dtype=np.float32)[..., None] / 255.0 \
            if mask is not None else None
        self.A = np.asarray(a, dtype=np.float32)
        self.B = np.asarray(b, dtype=np.float32) if b is not None else None
        self.breath = breath
        rng = np.random.default_rng(seed)
        self.ph = rng.uniform(0, 6.28, 3)

    def amp(self, t: float) -> float:
        if self.curve is None:
            # بلا صوت: فتح/إغلاق هادئ جدًا كأنه تنفّس
            return 0.12 + 0.10 * np.sin(t * 2.1)
        xs, ys = self.curve[:, 0], self.curve[:, 1]
        if t <= xs[0]:
            return float(ys[0])
        if t >= xs[-1]:
            return float(ys[-1])
        return float(np.interp(t, xs, ys))

    def morph(self, t: float, strength: float = 1.0) -> Image.Image:
        """يُرجع صورة A مع فم مفتوح بمقدار الكلام في اللحظة t (بلا حركة كاميرا)."""
        if self.B is None or self.mask_arr is None:
            return self.a
        k = float(np.clip(self.amp(t) * strength, 0.0, 1.0))
        if k <= 0.01:
            return self.a
        w = self.mask_arr * k
        out = self.A * (1 - w) + self.B * w
        return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))



class HeadMotion:
    """تنفّس وإيماءة عامّة (تحريك الإطار كله) — بلا أي حدود أو وصلات مرئية."""

    def __init__(self, hint=None, bob: float = 1.0):
        self.bob = bob

    def apply(self, frame: Image.Image, t: float, amp: float) -> Image.Image:
        # تنفّس: تكبير/تصغير ٠.٧٪ · إيماءة: هبوط ٢ بكسل مع الكلام
        s = 1.0 + 0.007 * math.sin(t * 2 * math.pi / 4.4)
        dy = self.bob * (1.2 * amp + 0.8 * math.sin(t * 2 * math.pi / 5.6))
        if abs(s - 1.0) < 1e-4 and abs(dy) < 0.4:
            return frame
        nw, nh = max(8, int(W * s)), max(8, int(H * s))
        scaled = frame.resize((nw, nh), Image.BILINEAR)
        plate = Image.new("RGB", (W, H), (0, 0, 0))
        plate.paste(scaled, ((W - nw) // 2, (H - nh) // 2 + int(round(dy))))
        return plate


# --------------------------------------------------------------------------- #
# ٤) الرندر
# --------------------------------------------------------------------------- #
def render_talk(name: str, dur: float, shot_id=None, focus=None, strength=0.55,
                move=None, crf=19, out_dir=None, talk_scale=1.7):
    a, b, mask = load_pair(name)
    if a is None:
        raise FileNotFoundError(name)
    curve = speech_curve(shot_id) if shot_id else None

    move = move or D3.MOVE_FOR.get(shot_id or "", "dolly_in")
    focus = focus or D3.FOCUS.get(name, (0.5, 0.5))
    depth = D3.depth_for(name, focus)
    cam = D3.Camera3D(a, depth, move, seed=abs(hash(name)) % 9973)
    rig = TalkRig(a, b, mask, curve, seed=3)
    head = HeadMotion()

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
        cam.img = rig.morph(t, talk_scale)          # الفم يتحرك في الفضاء الأصلي
        amp = float(np.clip(rig.amp(t) * talk_scale, 0.0, 1.0))
        frame = cam.frame(i / max(1, n - 1), strength)   # ثم حركة الكاميرا
        if head is not None:
            frame = head.apply(frame, t, amp)            # ثم إيماءة الرأس
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    return out, b is not None, curve is not None


def main():
    ap = argparse.ArgumentParser(description="كلام متزامن + حركة شخصيات")
    ap.add_argument("--shots", nargs="*")
    ap.add_argument("--images", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--still", metavar="NAME")
    ap.add_argument("--u", type=float, default=0.5)
    ap.add_argument("--amp", type=float, default=1.0, help="قوة فتح الفم للاختبار")
    ap.add_argument("--strength", type=float, default=0.55, help="حركة الكاميرا")
    ap.add_argument("--talk", type=float, default=1.7, help="مقياس الكلام")
    ap.add_argument("--move", default=None)
    ap.add_argument("--crf", type=int, default=19)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    if a.still:
        img_a, img_b, mask = load_pair(a.still)
        depth = D3.depth_for(a.still, D3.FOCUS.get(a.still, (0.5, 0.5)))
        cam = D3.Camera3D(img_a, depth, a.move or "dolly_in")
        rig = TalkRig(img_a, img_b, mask, None)
        cam.img = rig.morph(0.0, a.amp)
        out = cam.frame(a.u, a.strength)
        p = Path(a.out or f"_work/talk_{a.still}.png")
        p.parent.mkdir(parents=True, exist_ok=True)
        out.save(p)
        print(p, "B:", img_b is not None)
        return

    import shots_data
    durs = D3.load_durations()
    shots = list(shots_data.SHOTS)
    first_shot = {}
    for sh in shots:
        if sh.get("img") and sh["img"] not in first_shot:
            first_shot[sh["img"]] = sh["id"]
    if a.images:
        targets = [dict(id=first_shot.get(n), img=n, dur=durs.get(n, 5.0),
                        focus=D3.FOCUS.get(n, (0.5, 0.5))) for n in a.images]
    else:
        if a.shots:
            want = {s.upper() for s in a.shots}
            shots = [s for s in shots if s["id"] in want]
        elif not a.all:
            ap.error("--shots S03  أو  --all  أو  --images name")
        seen, targets = set(), []
        for s in shots:
            img = s.get("img")
            if not img or img in seen:
                continue
            seen.add(img)
            targets.append(dict(id=s["id"], img=img, dur=durs.get(img, 5.0),
                                focus=tuple(s.get("focus", D3.FOCUS.get(img, (0.5, 0.5))))))

    for t in targets:
        print(f"  {t['id'] or '--':4s} {t['img']:24s} {t['dur']:5.2f}s", end="", flush=True)
        p, has_b, has_audio = render_talk(t["img"], t["dur"], t["id"], t["focus"],
                                          a.strength, a.move, a.crf, a.out, a.talk)
        tag = "كلام" if (has_b and has_audio) else ("صورة فقط" if not has_b else "بلا صوت")
        print(f"  [{tag}]  -> {p.stat().st_size / 1e6:.1f} MB")
    print(f"\nتم: {len(targets)} مقطعًا")


if __name__ == "__main__":
    main()
