#!/usr/bin/env python
"""
Video Creator Tool - GUI Application
Chạy file này để khởi động ứng dụng
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

if __name__ == "__main__":
    try:
        from src.gui.app import run_app
        run_app()
    except ImportError as e:
        print(f"Lỗi import: {e}")
        print("\nCần cài đặt các thư viện:")
        print("  pip install customtkinter")
        print("  pip install pyautogui pyperclip")
        print("  pip install gspread google-auth")
        print("  pip install opencv-python")
        print("  pip install rich")
        sys.exit(1)
    except Exception as e:
        print(f"Lỗi: {e}")
        sys.exit(1)
