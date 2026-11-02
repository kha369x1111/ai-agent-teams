@echo off
chcp 65001 >nul
title إعادة بناء ورندر ريلز حرف الباء — 1080x1920
cd /d "%~dp0"

echo ============================================================================
echo   إعادة بناء الصوت والرندر الكامل للفيديو ^(1080x1920 @ 30fps^) على ويندوز
echo ============================================================================
echo.

set "SYS_PY="
where py >nul 2>nul && set "SYS_PY=py -3"
if "%SYS_PY%"=="" (
    where python >nul 2>nul && set "SYS_PY=python"
)
if "%SYS_PY%"=="" (
    echo [خطأ] يرجى تثبيت Python 3.11+ من https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] إنشاء البيئة الافتراضية .venv وتثبيت متطلبات الرندر...
    %SYS_PY% -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo [2/4] بناء المسارات الصوتية المعيارية والموسيقى والمؤثرات...
".venv\Scripts\python.exe" tools\audio_engine.py
if errorlevel 1 ( pause & exit /b 1 )

echo [3/4] رندر الفيديو العمودي 1080x1920 بمعدل 30 إطار/ثانية...
".venv\Scripts\python.exe" tools\render_reel.py
if errorlevel 1 ( pause & exit /b 1 )

echo [4/4] تحديث ملفات التوثيق وحقيبة النشر...
".venv\Scripts\python.exe" tools\report.py
if errorlevel 1 ( pause & exit /b 1 )

echo.
echo [تم بنجاح] الفيديو جاهز في: deliver\baa_secret_reel_1080x1920.mp4
pause
