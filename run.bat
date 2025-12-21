@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
REM ========================================
REM   Short Video Creator - Auto Update & Run
REM ========================================

REM Kich hoat virtual environment neu co
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Tao thu muc backup neu chua co
if not exist "config_backup" mkdir config_backup

REM Backup config truoc khi update
if exist "config\gui_config.json" (
    copy /Y "config\gui_config.json" "config_backup\gui_config.json" >nul
)
if exist "config\credentials.json" (
    copy /Y "config\credentials.json" "config_backup\credentials.json" >nul
)

REM Fetch tat ca branches
echo Dang kiem tra cap nhat...
git fetch --all 2>nul

REM Tim branch claude moi nhat (theo commit date)
set LATEST_BRANCH=
for /f "tokens=*" %%i in ('git for-each-ref --sort=-committerdate --format="%%(refname:short)" refs/remotes/origin/claude/* --count=1') do set LATEST_BRANCH=%%i

REM Neu tim thay branch moi
if defined LATEST_BRANCH (
    REM Bo prefix "origin/" - su dung delayed expansion
    set BRANCH_NAME=!LATEST_BRANCH:origin/=!
    echo Branch moi nhat: !BRANCH_NAME!

    REM Checkout va reset ve branch moi nhat
    git checkout !BRANCH_NAME! 2>nul
    git reset --hard origin/!BRANCH_NAME! 2>nul
    echo Da cap nhat thanh cong!
) else (
    echo Khong tim thay branch, dung phien ban hien tai...
)

REM Khoi phuc config sau khi update
if exist "config_backup\gui_config.json" (
    copy /Y "config_backup\gui_config.json" "config\gui_config.json" >nul
)
if exist "config_backup\credentials.json" (
    copy /Y "config_backup\credentials.json" "config\credentials.json" >nul
)

echo.
REM Chay GUI
python run_gui.py
endlocal
