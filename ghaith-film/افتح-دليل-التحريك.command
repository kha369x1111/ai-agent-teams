#!/usr/bin/env bash
# افتح دليل التحريك بنقرة واحدة (ماك / لينكس)
cd "$(dirname "$0")" || exit 1
if [ -f "دليل-التحريك.html" ]; then
  if command -v open >/dev/null 2>&1; then
    open "دليل-التحريك.html"        # macOS
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "دليل-التحريك.html"    # Linux
  else
    echo "افتح يدويًا: دليل-التحريك.html"
  fi
else
  echo "لم أجد دليل-التحريك.html — تأكد أنك فككت ضغط المشروع كاملًا."
  read -r -p "اضغط Enter للخروج"
fi
