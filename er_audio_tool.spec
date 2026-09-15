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
    "soundfile",
    "sounddevice",
    "_soundfile_data",
    # Application modules
    "er_audio_tool",
    "er_audio_tool.cli",
    "er_audio_tool.core",
    "er_audio_tool.core.config",
    "er_audio_tool.core.state",
    "er_audio_tool.core.logging",
    "er_audio_tool.audio",
    "er_audio_tool.audio.interfaces",
    "er_audio_tool.audio.manager",
    "er_audio_tool.audio.buffer",
    "er_audio_tool.audio.encoder",
    "er_audio_tool.audio.backends",
    "er_audio_tool.audio.backends.mock_backend",
    "er_audio_tool.audio.backends.windows_wasapi",
    "er_audio_tool.audio.backends.linux_backends",
    "er_audio_tool.browser",
    "er_audio_tool.browser.server",
    "er_audio_tool.analysis",
    "er_audio_tool.analysis.analyzer",
    "er_audio_tool.midi",
    "er_audio_tool.midi.model",
    "er_audio_tool.midi.transcriber",
    "er_audio_tool.midi.renderer",
    "er_audio_tool.gui",
    "er_audio_tool.gui.app",
    "er_audio_tool.i18n",
]

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
