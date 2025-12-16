@echo off
echo ========================================
echo    Short Video Creator - Auto Update
echo ========================================
echo.

echo [1/3] Dang cap nhat code...
git pull origin claude/short-video-creator-tool-WAbnx

echo.
echo [2/3] Dang cap nhat dependencies...
pip install -r requirements.txt --quiet

echo.
echo [3/3] Hoan thanh!
echo.
echo ========================================
echo    Da cap nhat xong!
echo    Chay: python -m src.main --help
echo ========================================
pause
