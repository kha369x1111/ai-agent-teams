@echo off
chcp 65001 >nul
title Jupyter Notebooks
color 0D

echo ╔══════════════════════════════════════════════════════════════╗
echo ║                                                              ║
echo ║         📓  JUPYTER NOTEBOOKS  📓                          ║
echo ║                                                              ║
echo ║     سيتم فتح Jupyter في المتصفح                             ║
echo ║                                                              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

call venv\Scripts\activate.bat

echo 🚀 جاري تشغيل Jupyter...
echo ⏳ انتظر 3-5 ثواني...
echo.

jupyter notebook

pause
