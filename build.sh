#!/usr/bin/env bash
# Build portable Linux binary
# Usage: bash build.sh
set -e

echo "=== er-audio-tool — Linux Build ==="

# 1. Create / activate venv
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# 2. Install dependencies
pip install --quiet --upgrade pip
pip install --quiet -e .[dev,full]
pip install --quiet pyinstaller>=6.0

# 3. Clean previous build
rm -rf build/ dist/

# 4. Build
pyinstaller er_audio_tool.spec --clean --noconfirm

# 5. Result
BINARY="dist/er-audio-tool"
if [ -f "$BINARY" ]; then
    chmod +x "$BINARY"
    SIZE=$(du -sh "$BINARY" | cut -f1)
    echo ""
    echo "Build successful!"
    echo "  Binary: $BINARY  ($SIZE)"
    echo ""
    echo "Usage:"
    echo "  $BINARY"
else
    echo "Build failed — check PyInstaller output above."
    exit 1
fi
