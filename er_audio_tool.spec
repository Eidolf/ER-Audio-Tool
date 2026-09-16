# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for er-audio-tool portable build.

Build:
  Linux:   pyinstaller er_audio_tool.spec
  Windows: pyinstaller er_audio_tool.spec

Output:
  dist/er-audio-tool          (Linux single binary)
  dist/er-audio-tool.exe      (Windows single binary)
"""

import platform
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
IS_WINDOWS = platform.system() == "Windows"

datas = [
    ("assets", "assets"),
    ("frames", "frames"),
    ("browser_extension", "browser_extension"),
] + collect_data_files("customtkinter")

# Include _version.txt if present
import os
from pathlib import Path
if Path("_version.txt").exists():
    datas.append(("_version.txt", "."))

hiddenimports = [
    # GUI
    "customtkinter",
    "tkinter",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "tkinter.ttk",
    "darkdetect",
    "PIL",
    "PIL.Image",
    # Audio & Numerical
    "numpy",
    "scipy",
    "scipy.signal",
    "soundfile",
    "sounddevice",
    "_soundfile_data",
    "mutagen",
    "mutagen.wave",
    "mutagen.flac",
    "mutagen.mp3",
    "mutagen.easyid3",
    "mutagen.id3",
] + collect_submodules("er_audio_tool")

a = Analysis(
    ["er_audio_tool/cli.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pandas",
        "PyQt5",
        "PyQt6",
        "wx",
    ],
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
    name="er-audio-tool.exe" if IS_WINDOWS else "er-audio-tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=not IS_WINDOWS,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
