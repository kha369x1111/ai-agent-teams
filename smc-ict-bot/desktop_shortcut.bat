@echo off
REM إنشاء اختصار على سطح المكتب

set SCRIPT_DIR=%~dp0
set DESKTOP=%USERPROFILE%\Desktop

echo ╔══════════════════════════════════════════════════════════════╗
echo ║                                                              ║
echo ║   🖥️  إنشاء اختصار على سطح المكتب                          ║
echo ║                                                              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

REM إنشاء اختصار "Trading Bot"
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\Trading Bot.lnk'); $s.TargetPath = '%SCRIPT_DIR%MENU.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.IconLocation = 'shell32.dll,12'; $s.Description = 'SMC/ICT Trading Bot'; $s.Save()"

echo ✅ تم إنشاء اختصار "Trading Bot" على سطح المكتب

REM إنشاء اختصار "Dashboard"
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\Dashboard.lnk'); $s.TargetPath = '%SCRIPT_DIR%DASHBOARD.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.IconLocation = 'shell32.dll,238'; $s.Description = 'Trading Dashboard'; $s.Save()"

echo ✅ تم إنشاء اختصار "Dashboard" على سطح المكتب

REM إنشاء اختصار "Notebooks"
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\Trading Notes.lnk'); $s.TargetPath = '%SCRIPT_DIR%NOTEBOOKS.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.IconLocation = 'shell32.dll,1'; $s.Description = 'Jupyter Notebooks'; $s.Save()"

echo ✅ تم إنشاء اختصار "Trading Notes" على سطح المكتب

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║   🎉 تم! افتح سطح المكتب ستجد 3 اختصارات                  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

pause
