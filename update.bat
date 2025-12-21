@echo off
chcp 65001 >nul
echo ========================================
echo    Short Video Creator - Auto Update
echo ========================================
echo.

echo [1/5] Xoa cac file conflict...
git clean -fd
git checkout -- .

echo.
echo [2/5] Fetch tat ca branches...
git fetch --all

echo.
echo [3/5] Tim branch moi nhat...
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
echo [4/5] Checkout va reset ve branch moi nhat...
git checkout %LATEST_BRANCH%
git reset --hard origin/%LATEST_BRANCH%

echo.
echo [5/5] Cap nhat dependencies...
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
