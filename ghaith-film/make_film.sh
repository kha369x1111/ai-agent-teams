#!/usr/bin/env bash
# إعادة بناء الفيلم من الصفر (بعد استنساخ المشروع أو حذف مجلد _work).
#
#    bash make_film.sh            # الفيلم + بطاقات + ترجمات + صوت + رندر
#    bash make_film.sh --animate  # نفس الشيء + تحريك كل اللقطات (2.5D parallax)
#
set -euo pipefail
cd "$(dirname "$0")"

echo "① التبعيات"
python3 -m pip install --quiet --break-system-packages \
  pillow numpy uharfbuzz imageio-ffmpeg || true
python3 -c "import PIL, numpy, uharfbuzz, imageio_ffmpeg; print('   ok')"

echo "② بطاقات العنوان والنهاية"
mkdir -p _work/cards _work/caps deliver
python3 tools/build.py cards

echo "③ الجدول الزمني"
python3 tools/build.py plan | tail -3

echo "④ التحريك (داخل الرندر — بلا ملفات وسيطة)"
PARALLAX=0.0
if [[ "${1:-}" == "--animate" || "${1:-}" == "--parallax" ]]; then
  PARALLAX=0.9
  echo "   عمق 2.5D مفعّل (0.9)"
else
  echo "   حركة كاميرا فقط (استخدم --animate لإضافة العمق)"
fi

echo "⑤ الترجمات + الموسيقى + المزج الصوتي"
python3 - <<'PY'
import sys, json
from pathlib import Path
sys.path.insert(0, 'tools')
import build as B

tl = B.build_timeline()
caps = [B.make_caption(c, i) for i, c in enumerate(tl["captions"])]
tl["captions"] = caps
Path("_work/timeline_full.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1))
print(f"   {len(tl['shots'])} shots · {len(caps)} captions · {tl['total']:.1f}s")
voice, music = B.step_audio(tl)
B.step_mix(voice, music, tl["total"])
PY

echo "⑥ الرندر النهائي"
python3 tools/render.py --timeline _work/timeline_full.json --audio _work/mix.wav \
                        --out deliver/ghaith_alhurras_1080p.mp4 --crf 19 \
                        --parallax "$PARALLAX"

echo "⑦ المعاينة"
echo "   python3 tools/serve.py --port 8080   ثم افتح http://localhost:8080/تحميل.html"
