@echo off
chcp 65001 >nul
title SMC/ICT Trading Bot - Main Menu
color 0E

:MENU
cls
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                                                              ║
echo ║       🤖  SMC/ICT TRADING BOT - MAIN MENU  📊              ║
echo ║                                                              ║
echo ║       اختر ما تريد تشغيله:                                  ║
echo ║                                                              ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║                                                              ║
echo ║   [1] 🚀 تشغيل البوت (Multi-Agent)                          ║
echo ║   [2] 📊 تشغيل Dashboard                                    ║
echo ║   [3] 📓 فتح Jupyter Notebooks                              ║
echo ║   [4] ⚙️  إعداد ملف .env                                    ║
echo ║   [5] 📦 تثبيت المكتبات                                     ║
echo ║   [6] 🧪 اختبار الاتصال                                     ║
echo ║   [7] 📁 فتح مجلد المشروع                                   ║
echo ║                                                              ║
echo ║   [0] ❌ خروج                                                ║
echo ║                                                              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

set /p choice="اختيارك (0-7): "

if "%choice%"=="1" goto RUN_BOT
if "%choice%"=="2" goto RUN_DASHBOARD
if "%choice%"=="3" goto RUN_JUPYTER
if "%choice%"=="4" goto SETUP_ENV
if "%choice%"=="5" goto INSTALL_DEPS
if "%choice%"=="6" goto TEST_CONN
if "%choice%"=="7" goto OPEN_FOLDER
if "%choice%"=="0" exit

echo ⚠️  اختيار غير صحيح!
pause
goto MENU

:RUN_BOT
cls
echo 🚀 تشغيل Multi-Agent Bot...
cd /d "%~dp0"
call venv\Scripts\activate.bat
python multi_agent_main.py
goto END

:RUN_DASHBOARD
cls
echo 📊 تشغيل Dashboard...
echo ⏳ سيتم فتح المتصفح تلقائياً...
cd /d "%~dp0"
call venv\Scripts\activate.bat
start "" "http://localhost:8501"
streamlit run dashboard\streamlit_app\dashboard.py
goto END

:RUN_JUPYTER
cls
echo 📓 فتح Jupyter...
cd /d "%~dp0"
call venv\Scripts\activate.bat
jupyter notebook
goto END

:SETUP_ENV
cls
echo ⚙️  إعداد ملف .env
if not exist ".env" (
    copy .env.example .env
    echo ✅ تم إنشاء .env
) else (
    echo ⚠️  .env موجود بالفعل
)
echo.
echo 📝 افتح الملف وأضف المفاتيح:
notepad .env
goto END

:INSTALL_DEPS
cls
echo 📦 تثبيت المكتبات...
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo.
echo ⏳ قد يأخذ 5-15 دقيقة...
pip install -r requirements.txt
echo.
echo ✅ تم التثبيت!
pause
goto MENU

:TEST_CONN
cls
echo 🧪 اختبار الاتصال...
cd /d "%~dp0"
call venv\Scripts\activate.bat
python test_connection.py
pause
goto MENU

:OPEN_FOLDER
cls
echo 📁 فتح مجلد المشروع...
explorer "%~dp0"
goto END

:END
echo.
pause
goto MENU
