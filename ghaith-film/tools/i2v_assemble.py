"""تجميع مقاطع Image-to-Video في الفيلم الكامل — بأمر واحد.

الكيفية:
  ١) تولّد الحزمة:  python3 tools/i2v.py --all --split 5
  ٢) ترفع صور i2v/upload/ إلى أداة مجانية (Kling / Luma / Runway / Pika / Veo)
     وتلصق برومبت i2v/segments/<SHOT>_<n>.txt لكل مقطع.
  ٣) تنزّل الناتج وتسمّيه باسم المقطع نفسه: S01_1.mp4 · S01_2.mp4 …
     وتضعه في i2v/clips_returned/
  ٤) تشغّل:  python3 tools/i2v_assemble.py --render
     فيُركّب كل لقطة من مقاطعها، ويكتبها في storyboard/clips/<الصورة>.mp4،
     ثم يبني الفيلم كاملًا بالصوت والترجمة.

بدون --render يبقى التجميع فقط (لا رندر)، وهو الأسرع للتجربة.

    python3 tools/i2v_assemble.py --check      # ما الناقص؟
    python3 tools/i2v_assemble.py              # ركّب فقط
    python3 tools/i2v_assemble.py --render     # ركّب + ابنِ الفيلم
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RETURNED = ROOT / "i2v/clips_returned"
SEGDIR = ROOT / "i2v/segments"
CLIPS = ROOT / "storyboard/clips"
MANIFEST = ROOT / "i2v/segments.json"

sys.path.insert(0, str(ROOT / "tools"))
import imageio_ffmpeg  # noqa: E402

FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS = 1920, 1080, 24


def probe_duration(path: Path) -> float:
    out = subprocess.run([FF, "-i", str(path)], capture_output=True, text=True).stderr
    for line in out.splitlines():
        if "Duration:" in line:
            hh, mm, ss = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(hh) * 3600 + int(mm) * 60 + float(ss)
    return 0.0


def find_segment(name: str) -> Path | None:
    """يبحث عن مقطع راجع بأي امتداد شائع، ويقبل الاسم بحروف كبيرة/صغيرة."""
    if not RETURNED.exists():
        return None
    want = name.lower()
    for p in RETURNED.iterdir():
        if p.is_file() and p.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv", ".m4v"):
            if p.stem.lower() == want:
                return p
    # اسم قد يكون فيه لاحقة من الأداة: S01_1_kling.mp4
    for p in RETURNED.iterdir():
        if p.is_file() and p.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv", ".m4v"):
            if p.stem.lower().startswith(want + "_") or p.stem.lower().startswith(want + "-"):
                return p
    return None


def normalize(src: Path, dst: Path, dur: float):
    """يوحّد المقاطع الراجعة: 1920×1080 · 24 إطار · بلا صوت · بالضبط dur ثانية.

    إن كان المقطع أقصر من المطلوب نُبطّئه قليلًا (حتى 15%)، وإلا نكرّر آخر إطار.
    """
    have = probe_duration(src)
    speed = 1.0
    if 0 < have < dur:
        speed = max(0.85, have / dur)      # تبطيء لطيف بدل التجميد
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"fps={FPS},setpts={(1 / speed):.4f}*PTS")
    cmd = [FF, "-y", "-loglevel", "error", "-i", str(src), "-an",
           "-vf", vf, "-t", f"{dur:.3f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", str(dst)]
    subprocess.run(cmd, check=True)


def build_shot(shot: str, segs: list, tmp: Path) -> Path:
    """يدمج مقاطع لقطة واحدة بالترتيب ويكتب storyboard/clips/<الصورة>.mp4."""
    parts = []
    for s in segs:
        src = find_segment(s["file"])
        if src is None:                      # لن يحدث: نتحقق قبل النداء
            raise FileNotFoundError(s["file"])
        part = tmp / f"{s['file']}.mp4"
        normalize(src, part, s["dur"])
        parts.append(part)

    lst = tmp / f"{shot}.txt"
    lst.write_text("\n".join(f"file '{p.resolve()}'" for p in parts))
    out = tmp / f"{shot}_full.mp4"
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(out)], check=True)
    return out


def main():
    ap = argparse.ArgumentParser(description="تجميع مقاطع i2v في الفيلم")
    ap.add_argument("--check", action="store_true", help="عرض الناقص فقط")
    ap.add_argument("--render", action="store_true", help="بعد التجميع: ابنِ الفيلم كاملًا")
    ap.add_argument("--crf", default="20", help="جودة الرندر (افتراضي 20)")
    a = ap.parse_args()

    RETURNED.mkdir(parents=True, exist_ok=True)
    if not MANIFEST.exists():
        sys.exit("لا يوجد i2v/segments.json — شغّل أولًا: python3 tools/i2v.py --all --split 5")
    data = json.loads(MANIFEST.read_text())
    segs = data["segments"]

    by_shot: dict[str, list] = {}
    for s in segs:
        by_shot.setdefault(s["shot"], []).append(s)
    for v in by_shot.values():
        v.sort(key=lambda x: x["segment"])

    ready, missing = {}, []
    for shot, lst in by_shot.items():
        got = [bool(find_segment(s["file"])) for s in lst]
        if all(got):
            ready[shot] = lst
        else:
            missing += [s["file"] for s, g in zip(lst, got) if not g]

    total = len(segs)
    done = total - len(missing)
    print(f"مقاطع جاهزة: {done}/{total}  ·  لقطات مكتملة: {len(ready)}/{len(by_shot)}")
    if missing:
        print("\nالناقص (سمّها بهذه الأسماء وضعها في i2v/clips_returned/):")
        for name in missing[:40]:
            print("  ", name + ".mp4", " → ", (SEGDIR / f"{name}.txt").relative_to(ROOT))
        if len(missing) > 40:
            print(f"   … و{len(missing) - 40} غيرها")
    if a.check:
        return

    if not ready:
        sys.exit("\nلا مقاطع مكتملة بعد — ابدأ بأداة مجانية وضَع الناتج في i2v/clips_returned/")

    # نسخة احتياطية من مقاطعنا القديمة (تحريك الفم) قبل الكتابة فوقها
    backup = ROOT / "_work/clips_backup"
    backup.mkdir(parents=True, exist_ok=True)
    CLIPS.mkdir(parents=True, exist_ok=True)
    tmp = ROOT / "_work/i2v_tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    written = []
    for shot, lst in ready.items():
        name = lst[0]["image"]
        dst = CLIPS / f"{name}.mp4"
        old = dst.resolve() if dst.exists() else None
        if old and old.exists() and not (backup / f"{name}.mp4").exists():
            shutil.copy2(old, backup / f"{name}.mp4")
        full = build_shot(shot, lst, tmp)
        shutil.copy2(full, dst)
        written.append((shot, name, round(sum(s["dur"] for s in lst), 2)))
        print(f"  ✓ {shot} → storyboard/clips/{name}.mp4  ({written[-1][2]}s، {len(lst)} مقطعًا)")

    for p in tmp.glob("*"):
        p.unlink(missing_ok=True)

    print(f"\nتم تركيب {len(written)} لقطة. النسخة القديمة محفوظة في _work/clips_backup/")
    if not a.render:
        print("لإنتاج الفيلم: python3 tools/i2v_assemble.py --render")
        return

    print("\n-- بناء الفيلم كاملًا --")
    sys.path.insert(0, str(ROOT / "tools"))
    import build as B  # noqa: WPS433

    tl = B.build_timeline()
    tl["captions"] = [B.make_caption(c, i) for i, c in enumerate(tl["captions"])]
    (ROOT / "_work").mkdir(exist_ok=True)
    (ROOT / "_work/caps").mkdir(exist_ok=True)
    (ROOT / "_work/cards").mkdir(exist_ok=True)
    (ROOT / "_work/timeline_full.json").write_text(json.dumps(tl, ensure_ascii=False))
    v, m = B.step_audio(tl)
    B.step_mix(v, m, tl["total"])

    out = ROOT / "_work/final_i2v.mp4"
    subprocess.run([sys.executable, str(ROOT / "tools/render.py"),
                    "--timeline", str(ROOT / "_work/timeline_full.json"),
                    "--audio", str(ROOT / "_work/mix.wav"),
                    "--out", str(out), "--crf", str(a.crf), "--parallax", "0"], check=True)
    small = ROOT / "_work/final_i2v_small.mp4"
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(out),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "25",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    "-c:a", "aac", "-b:a", "160k", str(small)], check=True)
    dst = ROOT / "deliver/ghaith_alhurras_1080p_i2v.mp4"
    dst.parent.mkdir(exist_ok=True)
    shutil.copy2(small, dst)
    print(f"\nالفيلم جاهز → {dst.relative_to(ROOT)}  ({dst.stat().st_size/1048576:.0f} MB)")


if __name__ == "__main__":
    main()
