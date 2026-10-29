@echo off
chcp 65001 >nul
REM افتح دليل التحريك بنقرة واحدة (ويندوز)
cd /d "%~dp0"
if exist "دليل-التحريك.html" (
  start "" "دليل-التحريك.html"
) else (
  echo لم أجد ملف دليل-التحريك.html
  echo تأكد أنك فككت ضغط المشروع كاملا في هذا المجلد.
  pause
)
