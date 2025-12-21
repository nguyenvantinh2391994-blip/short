@echo off
REM ========================================
REM   Short Video Creator - Auto Update & Run
REM ========================================

REM Kich hoat virtual environment neu co
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Auto pull code moi nhat (branch hien tai)
echo Dang kiem tra cap nhat...
git pull 2>nul
if %errorlevel%==0 (
    echo Da cap nhat code moi nhat!
) else (
    echo Khong the cap nhat, tiep tuc chay...
)

REM Chay GUI mac dinh
if "%~1"=="" (
    python run_gui.py
) else (
    python -m src.main %*
)
