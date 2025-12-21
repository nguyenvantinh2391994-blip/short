@echo off
chcp 65001 >nul
echo ========================================
echo    Short Video Creator - Auto Update
echo ========================================
echo.

REM Tao thu muc backup neu chua co
if not exist "config_backup" mkdir config_backup

echo [1/6] Backup config...
if exist "config\gui_config.json" (
    copy /Y "config\gui_config.json" "config_backup\gui_config.json" >nul
    echo    Da backup gui_config.json
)
if exist "config\credentials.json" (
    copy /Y "config\credentials.json" "config_backup\credentials.json" >nul
    echo    Da backup credentials.json
)

echo.
echo [2/6] Fetch tat ca branches...
git fetch --all

echo.
echo [3/6] Tim branch moi nhat...
for /f "tokens=*" %%i in ('git for-each-ref --sort=-committerdate --format="%%(refname:short)" refs/remotes/origin/claude/* --count=1') do set LATEST_BRANCH=%%i

if not defined LATEST_BRANCH (
    echo Khong tim thay branch claude nao!
    pause
    exit /b 1
)

REM Bo prefix "origin/"
set LATEST_BRANCH=%LATEST_BRANCH:origin/=%
echo Branch moi nhat: %LATEST_BRANCH%

echo.
echo [4/6] Checkout va reset ve branch moi nhat...
git checkout %LATEST_BRANCH%
git reset --hard origin/%LATEST_BRANCH%

echo.
echo [5/6] Khoi phuc config...
if exist "config_backup\gui_config.json" (
    copy /Y "config_backup\gui_config.json" "config\gui_config.json" >nul
    echo    Da khoi phuc gui_config.json
)
if exist "config_backup\credentials.json" (
    copy /Y "config_backup\credentials.json" "config\credentials.json" >nul
    echo    Da khoi phuc credentials.json
)

echo.
echo [6/6] Cap nhat dependencies...
pip install -r requirements.txt --quiet

echo.
echo ========================================
echo    DA CAP NHAT XONG!
echo    Branch: %LATEST_BRANCH%
echo    Commit hien tai:
git log --oneline -1
echo.
echo    Chay GUI: python run_gui.py
echo    Hoac:     run.bat
echo ========================================
pause
