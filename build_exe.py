#!/usr/bin/env python
"""
Build script để đóng gói ứng dụng thành exe
"""

import subprocess
import sys
import shutil
from pathlib import Path

def build():
    """Build exe using PyInstaller"""
    print("=" * 50)
    print("Video Creator Tool - Build EXE")
    print("=" * 50)

    # Check PyInstaller
    try:
        import PyInstaller
        print(f"✓ PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("✗ PyInstaller chưa được cài đặt")
        print("  Chạy: pip install pyinstaller")
        sys.exit(1)

    # Paths
    root = Path(__file__).parent
    main_script = root / "run_gui.py"
    icon_file = root / "icon" / "app.ico"
    dist_folder = root / "dist"
    build_folder = root / "build"

    # Clean previous builds
    print("\nDọn dẹp build cũ...")
    if dist_folder.exists():
        shutil.rmtree(dist_folder)
    if build_folder.exists():
        shutil.rmtree(build_folder)

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=VideoCreatorTool",
        "--onefile",
        "--windowed",
        "--add-data=src;src",
        "--add-data=config;config",
        "--add-data=icon;icon",
        "--hidden-import=customtkinter",
        "--hidden-import=PIL",
        "--hidden-import=cv2",
        "--hidden-import=gspread",
        "--hidden-import=google.oauth2",
        "--hidden-import=pyautogui",
        "--hidden-import=pyperclip",
        "--collect-all=customtkinter",
    ]

    # Add icon if exists
    if icon_file.exists():
        cmd.append(f"--icon={icon_file}")

    cmd.append(str(main_script))

    print("\nĐang build...")
    print(f"Command: {' '.join(cmd)}")
    print()

    # Run PyInstaller
    result = subprocess.run(cmd, cwd=root)

    if result.returncode == 0:
        exe_path = dist_folder / "VideoCreatorTool.exe"
        if exe_path.exists():
            print("\n" + "=" * 50)
            print("✓ BUILD THÀNH CÔNG!")
            print(f"  File: {exe_path}")
            print(f"  Size: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
            print("=" * 50)
        else:
            print("\n✗ Không tìm thấy file exe")
    else:
        print("\n✗ BUILD THẤT BẠI!")
        sys.exit(1)


if __name__ == "__main__":
    build()
