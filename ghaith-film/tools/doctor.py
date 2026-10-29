"""فاحص جاهزية المشروع — بلغة بسيطة.

    python3 tools/doctor.py

يفحص: بايثون، الحزم، ffmpeg، الصور، الأصوات، والملفات الأساسية.
يطبع ✅ أو ❌ مع الحل بجملة واحدة.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OK, BAD, WARN = "✅", "❌", "⚠️ "

problems: list[str] = []


def say(mark: str, title: str, hint: str = ""):
    print(f"{mark} {title}")
    if hint:
        print(f"   ← {hint}")


def check_python():
    v = sys.version_info
    if v >= (3, 9):
        say(OK, f"بايثون {v.major}.{v.minor} موجود")
    else:
        say(BAD, f"بايثون قديم ({v.major}.{v.minor})", "نزّل بايثون 3.10 أو أحدث من python.org")
        problems.append("python")


def check_packages():
    for mod, pip_name in (("numpy", "numpy"), ("PIL", "pillow"),
                          ("uharfbuzz", "uharfbuzz"), ("imageio_ffmpeg", "imageio-ffmpeg")):
        try:
            __import__(mod)
            say(OK, f"مكتبة {pip_name}")
        except ImportError:
            say(BAD, f"مكتبة {pip_name} ناقصة",
                f"شغّل: pip install --break-system-packages {pip_name}")
            problems.append(pip_name)


def check_ffmpeg():
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if Path(exe).exists():
            say(OK, "برنامج ffmpeg (محرّك الفيديو) جاهز")
            return
    except Exception:
        pass
    if shutil.which("ffmpeg"):
        say(OK, "برنامج ffmpeg موجود في النظام")
    else:
        say(BAD, "ffmpeg ناقص", "شغّل: pip install --break-system-packages imageio-ffmpeg")
        problems.append("ffmpeg")


def check_files():
    images = list((ROOT / "storyboard/raw").glob("*.jpg")) + \
             list((ROOT / "storyboard/raw").glob("*.png"))
    if len(images) >= 20:
        say(OK, f"الصور موجودة ({len(images)} صورة)")
    elif images:
        say(WARN, f"الصور قليلة ({len(images)}) — الفيلم سيعمل لكن بلقطات أقل")
    else:
        say(BAD, "لا توجد صور", "تأكد أنك فككت الضغط داخل مجلد ghaith-film")
        problems.append("images")

    lines = list((ROOT / "audio/lines").glob("*.mp3")) + \
            list((ROOT / "audio/lines_wav").glob("*.wav"))
    say(OK if lines else BAD, f"ملفات الأصوات ({len(lines)} ملف)")
    if not lines:
        problems.append("audio")

    for f in ("script/lines_data.py", "project/shots_data.py", "tools/render.py"):
        if not (ROOT / f).exists():
            say(BAD, f"ملف ناقص: {f}", "أعد فك ضغط المشروع كاملًا")
            problems.append(f)


def check_output():
    film = ROOT / "deliver/ghaith_alhurras_1080p.mp4"
    if film.exists():
        mb = film.stat().st_size / 1e6
        say(OK, f"الفيلم النهائي موجود ({mb:.0f} م.ب) — افتحه وشاهده!")
    else:
        say(WARN, "الفيلم لم يُبنَ بعد",
            "شغّل: bash make_film.sh        (أول مرة ≈ ١٥ دقيقة)")


def main():
    print("=" * 52)
    print("  فحص مشروع: فريق الحراسة السرّي")
    print("=" * 52)
    check_python()
    check_packages()
    check_ffmpeg()
    check_files()
    check_output()
    print("=" * 52)
    if problems:
        print("🔧 هناك أشياء تحتاج إصلاحًا (انظر الأسهم أعلاه).")
        print("   إن استعصى شيء: ثبّت كل الحزم بأمر واحد:")
        print("   pip install --break-system-packages pillow numpy uharfbuzz imageio-ffmpeg")
        return 1
    print("🎉 كل شيء جاهز! الخطوة التالية:")
    print("   bash make_film.sh --animate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
