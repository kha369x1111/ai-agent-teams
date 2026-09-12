@echo off
chcp 65001 >nul
title SMC/ICT Trading Bot
color 0A

echo ╔══════════════════════════════════════════════════════════════╗
echo ║                                                              ║
echo ║          🚀  SMC/ICT TRADING BOT  📈                        ║
echo ║                                                              ║
echo ║     بنقرة واحدة فقط!                                        ║
echo ║                                                              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM التحقق من Python
echo [1/4] 🔍 جاري التحقق من Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python غير مثبت!
    echo 📥 حمّله من: https://www.python.org/downloads/
    echo ⚠️  تأكد من تفعيل "Add to PATH"
    pause
    exit /b 1
)

REM تفعيل البيئة الافتراضية
echo [2/4] 🔧 تفعيل البيئة الافتراضية...
if not exist "venv\Scripts\activate.bat" (
    echo ⚠️  البيئة الافتراضية غير موجودة، جاري إنشائها...
    python -m venv venv
)

call venv\Scripts\activate.bat

REM التحقق من المكتبات
echo [3/4] 📦 التحقق من المكتبات...
python -c "import pandas, numpy, ccxt" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  المكتبات غير مثبتة، جاري التثبيت...
    pip install -r requirements.txt
)

REM التحقق من ملف .env
echo [4/4] ⚙️  التحقق من الإعدادات...
if not exist ".env" (
    echo ❌ ملف .env غير موجود!
    echo 📝 انسخ .env.example إلى .env واملأ المفاتيح
    pause
    exit /b 1
)

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  ✅ كل شيء جاهز!                                            ║
echo ║  🚀 جاري تشغيل البوت...                                     ║
echo ║                                                              ║
echo ║  للإيقاف: اضغط Ctrl + C                                    ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

REM تشغيل البوت
python main.py

pause
