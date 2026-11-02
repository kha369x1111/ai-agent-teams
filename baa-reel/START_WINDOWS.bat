@echo off
chcp 65001 >nul
title مشروع ريلز حرف الباء — أكاديمية مفتاح الأسرار السبعة
cd /d "%~dp0"

echo ============================================================================
echo   مشروع ريلز حرف الباء ^(ب^) — التشغيل الفوري بدون تثبيت مكتبات خارجية
echo   سيفتح الاستوديو التفاعلي الآن على المتصفح: http://127.0.0.1:8088
echo ============================================================================
echo.

where py >nul 2>nul && (
    py -3 launch_studio.py --host 127.0.0.1 --port 8088 --open-browser
    goto :eof
)

where python >nul 2>nul && (
    python launch_studio.py --host 127.0.0.1 --port 8088 --open-browser
    goto :eof
)

echo [خطأ] لم يتم العثور على Python 3 على جهازك.
echo يرجى تثبيت Python 3.11+ من https://www.python.org/downloads/ مع تفعيل "Add python.exe to PATH"
echo أو يمكنك فتح ملف index.html أو مشاهدة الفيديو مباشرة من مجلد deliver\baa_secret_reel_1080x1920.mp4
echo.
pause
