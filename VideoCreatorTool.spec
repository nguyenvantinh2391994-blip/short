# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Video Creator Tool
Run: pyinstaller VideoCreatorTool.spec
"""

import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

a = Analysis(
    ['run_gui.py'],
    pathex=[str(root)],
    binaries=[],
    datas=[
        ('src', 'src'),
        ('config', 'config'),
        ('icon', 'icon'),
    ],
    hiddenimports=[
        'customtkinter',
        'PIL',
        'PIL._tkinter_finder',
        'cv2',
        'gspread',
        'google.oauth2',
        'google.oauth2.service_account',
        'google.auth.transport.requests',
        'pyautogui',
        'pyperclip',
        'rich',
        'click',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VideoCreatorTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon/app.ico' if (root / 'icon' / 'app.ico').exists() else None,
)
