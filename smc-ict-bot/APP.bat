@echo off
chcp 65001 >nul
title SMC/ICT Trading Bot - Desktop App
color 0A

cd /d "%~dp0"

REM تفعيل البيئة
call venv\Scripts\activate.bat

REM تشغيل التطبيق
python desktop_app.py

if errorlevel 1 (
    echo.
    echo ❌ حدث خطأ!
    pause
)
