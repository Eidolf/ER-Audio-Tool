@echo off
REM Build portable Windows .exe
REM Usage: build.bat

echo === er-audio-tool — Windows Build ===

REM 1. Create venv
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

REM 2. Install dependencies
pip install --quiet --upgrade pip
pip install --quiet -e .[dev,full]
pip install --quiet pyinstaller>=6.0

REM 3. Clean previous build
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 4. Build
pyinstaller er_audio_tool.spec --clean --noconfirm

REM 5. Result
if exist "dist\er-audio-tool.exe" (
    echo.
    echo Build successful!
    echo   Binary: dist\er-audio-tool.exe
    echo.
    echo Usage:
    echo   dist\er-audio-tool.exe
) else (
    echo Build failed. Check PyInstaller output above.
    exit /b 1
)
