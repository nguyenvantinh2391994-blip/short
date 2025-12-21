@echo off
chcp 65001 >nul
REM ========================================
REM   Short Video Creator - Auto Update & Run
REM ========================================

REM Kich hoat virtual environment neu co
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Fetch tat ca branches
echo Dang kiem tra cap nhat...
git fetch --all 2>nul

REM Tim branch claude moi nhat (theo commit date)
for /f "tokens=*" %%i in ('git for-each-ref --sort=-committerdate --format="%%(refname:short)" refs/remotes/origin/claude/* --count=1') do set LATEST_BRANCH=%%i

REM Neu tim thay branch moi
if defined LATEST_BRANCH (
    REM Bo prefix "origin/"
    set LATEST_BRANCH=%LATEST_BRANCH:origin/=%
    echo Branch moi nhat: %LATEST_BRANCH%

    REM Checkout va reset ve branch moi nhat
    git checkout %LATEST_BRANCH% 2>nul
    git reset --hard origin/%LATEST_BRANCH% 2>nul
    echo Da cap nhat thanh cong!
) else (
    echo Khong tim thay branch, dung phien ban hien tai...
)

echo.
REM Chay GUI
python run_gui.py
