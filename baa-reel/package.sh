#!/usr/bin/env bash
# بناء حزم التحميل لمشروع ريلز «حرف الباء (ب) — أكاديمية مفتاح الأسرار السبعة»
#
#    bash package.sh               # حزمة الكود + الحزمة الخفيفة
#    WITH_VIDEO=1 bash package.sh  # + الحزمة الشاملة مع ملف الـ MP4 النهائي
#
set -euo pipefail
cd "$(dirname "$0")"

OUT=packages
mkdir -p "$OUT"

echo "→ بناء حزمة الكود والوثائق (baa-reel-code.zip)"
rm -f "$OUT/baa-reel-code.zip"
zip -q -r "$OUT/baa-reel-code.zip" \
  README.md index.html تحميل.html make_reel.sh package.sh \
  project tools docs assets \
  -x '**/__pycache__/*' -x '*.pyc'

echo "→ بناء حزمة الإنتاج الكاملة باللوحات والأصوات (baa-reel-light.zip)"
rm -f "$OUT/baa-reel-light.zip"
zip -q -r "$OUT/baa-reel-light.zip" \
  README.md index.html تحميل.html make_reel.sh package.sh \
  project tools docs assets storyboard/raw audio/lines \
  -x '**/__pycache__/*' -x '*.pyc'

if [ "${WITH_VIDEO:-0}" = "1" ]; then
  echo "→ بناء الحزمة الشاملة مع الفيديو النهائي (baa-reel-full.zip)"
  rm -f "$OUT/baa-reel-full.zip"
  zip -q -r "$OUT/baa-reel-full.zip" \
    README.md index.html تحميل.html make_reel.sh package.sh \
    project tools docs assets storyboard/raw audio/lines deliver \
    -x '**/__pycache__/*' -x '*.pyc'
fi

for f in "$OUT"/*.zip; do
  printf '  %-28s %s\n' "$(basename "$f")" "$(du -h "$f" | cut -f1)"
done
