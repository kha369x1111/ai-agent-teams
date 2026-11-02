#!/usr/bin/env bash
# بناء ريلز «حرف الباء (ب) — ثوب الوجود وسر النقطة التكوينية» بالكامل بأمر واحد.
#
#    bash make_reel.sh
#
set -euo pipefail
cd "$(dirname "$0")"

echo "① التحقق من التبعيات البرمجية"
python3 -m pip install --quiet --break-system-packages \
  pillow numpy scipy uharfbuzz imageio-ffmpeg || true

mkdir -p _work deliver docs

echo "② هندسة الصوت (Deep Bass + صدى القاعات الحجرية + الموسيقى الشرقية + المؤثرات)"
python3 tools/audio_engine.py

echo "③ توليد الوثائق وبيانات العرض التفاعلي"
python3 tools/report.py

echo "④ الرندر السينمائي العمودي (1080×1920 · 30 FPS · Chiaroscuro + Sacred VFX)"
python3 tools/render_reel.py \
  --audio _work/master_mix.wav \
  --subs _work/subtitles.json \
  --out deliver/baa_secret_reel_1080x1920.mp4 \
  --crf 17

echo "⑤ جاهز للمعاينة"
echo "   python3 tools/serve.py --port 8088"
