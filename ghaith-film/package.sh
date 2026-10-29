#!/usr/bin/env bash
# يبني حزم التحميل في مجلد packages/:
#   1) ghaith-film-code.zip   — الكود والوثائق والخطوط فقط (~300 ك.ب)
#   2) ghaith-film-light.zip  — + الصور والأصوات (بدون الفيلم)
#   3) ghaith-film-full.zip   — كل شيء بما فيه الفيلم النهائي
#
#    bash package.sh
set -euo pipefail
cd "$(dirname "$0")"

OUT=packages
mkdir -p "$OUT"

echo "→ حزمة الكود"
rm -f "$OUT/ghaith-film-code.zip"
zip -q -r "$OUT/ghaith-film-code.zip" \
  README.md index.html package.sh make_film.sh tools script project docs assets \
  -x '**/__pycache__/*' -x '*.pyc'

echo "→ حزمة خفيفة"
rm -f "$OUT/ghaith-film-light.zip"
zip -q -r "$OUT/ghaith-film-light.zip" \
  README.md index.html package.sh make_film.sh tools script project docs assets \
  storyboard/raw audio \
  -x '**/__pycache__/*' -x '*.pyc'

if [ "${WITH_FILM:-0}" = "1" ]; then
  echo "→ حزمة كاملة (مع الفيلم)"
  rm -f "$OUT/ghaith-film-full.zip"
  zip -q -r "$OUT/ghaith-film-full.zip" . \
    -x '_work/*' -x 'packages/*' -x '**/__pycache__/*' -x '*.pyc' -x '.DS_Store'
else
  echo "  (لتضمين الفيلم: WITH_FILM=1 bash package.sh)"
fi

for f in "$OUT"/*.zip; do
  printf '%-28s %s\n' "$(basename "$f")" "$(du -h "$f" | cut -f1)"
done
