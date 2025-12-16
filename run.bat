@echo off
echo ========================================
echo    Short Video Creator - Run
echo ========================================
echo.

REM Kich hoat virtual environment neu co
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Chay lenh
python -m src.main %*
