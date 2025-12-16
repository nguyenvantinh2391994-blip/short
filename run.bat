@echo off
REM ========================================
REM   Short Video Creator - Auto Update & Run
REM ========================================

REM Kich hoat virtual environment neu co
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Auto pull code moi nhat (silent)
git pull origin claude/short-video-creator-tool-WAbnx >nul 2>&1

REM Chay lenh - Mac dinh la grok-batch neu khong co tham so
if "%~1"=="" (
    python -m src.main grok-batch
) else (
    python -m src.main %*
)
