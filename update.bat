@echo off
chcp 65001 >nul
echo ========================================
echo    Short Video Creator - Auto Update
echo ========================================
echo.

echo [1/4] Reset ve phien ban moi nhat...
git fetch origin
git reset --hard origin/claude/video-shorts-automation-HrKXG

echo.
echo [2/4] Checkout dung branch...
git checkout claude/video-shorts-automation-HrKXG

echo.
echo [3/4] Cap nhat dependencies...
pip install -r requirements.txt --quiet

echo.
echo [4/4] Hoan thanh!
echo.
echo ========================================
echo    DA CAP NHAT XONG!
echo    Commit hien tai:
git log --oneline -1
echo.
echo    Chay GUI: python run_gui.py
echo    Chay CLI: python -m src.main grok-batch
echo ========================================
pause
