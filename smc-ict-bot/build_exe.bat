@echo off
chcp 65001 >nul
title Build Executable
color 0E

echo ╔══════════════════════════════════════════════════════════════╗
echo ║                                                              ║
echo ║       📦  BUILDING WINDOWS EXECUTABLE  📦                   ║
echo ║                                                              ║
echo ║   سيتم إنشاء ملف .exe يعمل بدون Python                     ║
echo ║                                                              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM تفعيل البيئة
call venv\Scripts\activate.bat

REM تثبيت PyInstaller
echo [1/3] Installing PyInstaller...
pip install pyinstaller

REM بناء التطبيق
echo.
echo [2/3] Building executable... (هذا قد يأخذ 5-10 دقائق)
echo.

pyinstaller --onefile ^
    --windowed ^
    --name "SMC_ICT_Trading_Bot" ^
    --icon=app_icon.ico ^
    --add-data ".env.example;." ^
    --add-data "agents;agents" ^
    --add-data "core;core" ^
    --add-data "ml_engine;ml_engine" ^
    --add-data "monitoring;monitoring" ^
    --add-data "strategies;strategies" ^
    --add-data "websocket;websocket" ^
    --add-data "multi_exchange;multi_exchange" ^
    --hidden-import=tkinter ^
    desktop_app.py

echo.
echo [3/3] Done!

if exist "dist\SMC_ICT_Trading_Bot.exe" (
    echo.
    echo ╔══════════════════════════════════════════════════════════════╗
    echo ║   ✅ تم بنجاح!                                              ║
    echo ║                                                              ║
    echo ║   📁 الملف في: dist\SMC_ICT_Trading_Bot.exe                 ║
    echo ║                                                              ║
    echo ║   💡 يمكنك نسخه لأي مكان وتشغيله بنقرة واحدة              ║
    echo ╚══════════════════════════════════════════════════════════════╝
) else (
    echo.
    echo ❌ فشل البناء - راجع الأخطاء أعلاه
)

echo.
pause
