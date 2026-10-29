"""تحريك الصور الثابتة — «الصورة الحيّة» (2.5D parallax).

يحوّل أي لقطة PNG في storyboard/raw إلى مقطع MP4 متحرك:
  • طبقتان من الصورة نفسها تتحركان بسرعتين مختلفتين (خلفية بطيئة + مقدمة أسرع)
    تُدمجان بقناع بيضاوي ناعم حول نقطة التركيز → إحساس بالعمق.
  • نبض إضاءة خفيف + اهتزاز كاميرا دقيق + حبيبات فيلم + غبار متطاير.
  • الناتج يُكتب في storyboard/clips/<name>.mp4، و tools/render.py يلتقطه
    تلقائيًا بدل الصورة الثابتة (انظر docs/animation-guide.md).

    python3 tools/parallax.py --shots S01 S06 S21
    python3 tools/parallax.py --all
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "project"))
import imageio_ffmpeg  # noqa: E402
import shots_data  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
RAW = ROOT / "storyboard/raw"
CLIPS = ROOT / "storyboard/clips"
CACHE = ROOT / "_work/parallax"
W, H, FPS = 1920, 1080, 24


# --------------------------------------------------------------------------- #
# assets
# --------------------------------------------------------------------------- #
def soft_mask(path: Path, fx: float, fy: float, rx: float = 0.62, ry: float = 0.60,
              feather: int = 260):
    """قناع بيضاوي ناعم: أبيض في المقدمة (حول نقطة التركيز) وأسود في الخلفية."""
    h, w = H // 2, W // 2
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    cx, cy = fx * w, fy * h
    d.ellipse([cx - rx * w, cy - ry * h, cx + rx * w, cy + ry * h], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(feather // 2)).resize((W, H), Image.BILINEAR)
    m.save(path)
    return path


def dust_layer(path: Path, seed: int = 7, count: int = 90):
    """غبار/ذرّات ضوء متطايرة على خلفية شفافة."""
    rng = np.random.default_rng(seed)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for _ in range(count):
        r = rng.uniform(1.5, 5.5)
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        a = int(rng.uniform(25, 95))
        col = (255, 246, 225, a) if rng.random() > 0.35 else (255, 224, 180, a)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    img.filter(ImageFilter.GaussianBlur(0.7)).save(path)
    return path


# --------------------------------------------------------------------------- #
# filter graph
# --------------------------------------------------------------------------- #
def build_filter(shot: dict, dur: float, mask: Path, dust: Path, strength: float = 1.0) -> str:
    """جراف ffmpeg: parallax طبقتين + نبض + غبار + حبيبات + خفوت أطراف."""
    fx, fy = shot.get("focus", [0.5, 0.5])
    z_bg0, z_bg1 = 1.02, 1.02 + 0.045 * strength
    z_fg0, z_fg1 = 1.00, 1.00 + 0.115 * strength
    # إزاحة أفقية بسيطة معاكسة للطبقتين (parallax)
    dx = 0.010 * strength
    n = max(2, int(round(dur * FPS)))

    def zp(z0, z1, pan):
        z = f"{z0}+({z1}-{z0})*on/{n}"
        x = f"clip(({fx}+{pan}*on/{n})*iw-iw/zoom/2,0,iw-iw/zoom)"
        y = f"clip({fy}*ih-ih/zoom/2,0,ih-ih/zoom)"
        return f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={W}x{H}:fps={FPS}"

    pre = f"scale={W * 2}:{H * 2}:flags=lanczos"
    graph = (
        # الخلفية: تحرّك أبطأ وفي اتجاه مضاد
        f"[0:v]{pre},{zp(z_bg0, z_bg1, -dx)}[bg];"
        # المقدمة: تحرّك أسرع
        f"[0:v]{pre},{zp(z_fg0, z_fg1, dx)}[fg];"
        # دمج بقناع → إحساس العمق
        f"[bg][fg][2:v]maskedmerge[comp];"
        # نبض إضاءة + تشبّع
        f"[comp]eq=brightness='0.014*sin(2*PI*t/7.5)':saturation=1.06:contrast=1.02[lit];"
        # غبار متطاير (حركة صاعدة بطيئة)
        f"[3:v]format=rgba,colorchannelmixer=aa=0.55[dust];"
        f"[lit][dust]overlay=x='-6*sin(t/9)':y='-14*t':shortest=1[air];"
        # حبيبات فيلم + خفوت أطراف
        f"[air]noise=alls=4:allf=t+u,vignette=PI/7,format=yuv420p[v]"
    )
    return graph


def source_image(name: str) -> Path:
    for ext in (".png", ".jpg"):
        cand = RAW / f"{name}{ext}"
        if cand.exists():
            return cand
    raise FileNotFoundError(RAW / f"{name}.png")


def render_shot(shot: dict, dur: float, strength: float = 1.0, crf: int = 18) -> Path:
    img = source_image(shot["img"])
    CACHE.mkdir(parents=True, exist_ok=True)
    CLIPS.mkdir(parents=True, exist_ok=True)
    fx, fy = shot.get("focus", [0.5, 0.5])
    mask = soft_mask(CACHE / f"mask_{shot['img']}.png", fx, fy)
    dust = CACHE / "dust.png"
    if not dust.exists():
        dust_layer(dust)

    out = CLIPS / f"{shot['img']}.mp4"
    graph = build_filter(shot, dur, mask, dust, strength)
    cmd = [FF, "-y",
           "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(img),
           "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(img),
           "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(mask),
           "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(dust),
           "-filter_complex", graph, "-map", "[v]", "-an",
           "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr[-1500:])
        raise RuntimeError(f"parallax failed for {shot['id']}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", nargs="*", help="معرّفات اللقطات مثل S01 S06")
    ap.add_argument("--all", action="store_true", help="كل اللقطات التي لها صورة")
    ap.add_argument("--strength", type=float, default=1.0, help="قوة الحركة")
    ap.add_argument("--crf", type=int, default=18)
    a = ap.parse_args()

    shots = shots_data.SHOTS
    if a.shots:
        wanted = set(a.shots)
        shots = [s for s in shots if s["id"] in wanted]
    elif not a.all:
        ap.error("اختر --shots S01 S06 أو --all")

    # مدة كل لقطة من نفس منطق خط الإنتاج (تقديري هنا لأن الصوت غير مقروء دائمًا)
    from build import build_timeline  # noqa: WPS433 (استيراد كسول)
    tl = {s["id"]: s for s in build_timeline()["shots"]}

    done = 0
    for shot in shots:
        if "img" not in shot:
            continue
        dur = tl.get(shot["id"], {}).get("dur", shot.get("dur", 5.0))
        print(f"  {shot['id']:4s} {shot['img']:22s} {dur:5.2f}s ...", flush=True)
        out = render_shot(shot, dur, a.strength, a.crf)
        print(f"        -> {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.1f} MB)")
        done += 1
    print(f"تم توليد {done} مقطعًا في {CLIPS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
