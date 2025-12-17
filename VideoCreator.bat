@echo off
title Video Creator Tool
cd /d "%~dp0"

REM Kich hoat virtual environment neu co
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Chay GUI
python run_gui.py

pause
