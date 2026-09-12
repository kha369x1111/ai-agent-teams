@echo off
chcp 65001 >nul
title SMC/ICT Dashboard
color 0B

echo ╔══════════════════════════════════════════════════════════════╗
echo ║                                                              ║
echo ║          📊  TRADING DASHBOARD  📈                          ║
echo ║                                                              ║
echo ║     سيتم فتح Dashboard في المتصفح تلقائياً                  ║
echo ║                                                              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM تفعيل البيئة
call venv\Scripts\activate.bat

REM تشغيل Dashboard
echo 🚀 جاري تشغيل Dashboard...
echo ⏳ انتظر 5-10 ثواني...
echo.

streamlit run dashboard\streamlit_app\dashboard.py --server.headless true

pause
