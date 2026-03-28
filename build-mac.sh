#!/usr/bin/env bash
# Build QuiKeys for macOS — produces dist/QuiKeys-macos-vX.Y.Z.zip
# Run from the QuiKeys project root.
# Requirements: Python 3.10+, pip

set -e
VERSION="0.1.0"
APP_NAME="QuiKeys"

echo "=== QuiKeys macOS Build ==="

# ── Virtual environment ──────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Installing dependencies..."
.venv/bin/pip install --quiet -r requirements.txt
.venv/bin/pip install --quiet -r requirements-mac.txt

# ── Generate icon ────────────────────────────────────────────────────
echo "Generating icon assets..."
.venv/bin/python src/generate_icon.py

# Convert PNG → ICNS (requires macOS)
if command -v sips &>/dev/null && command -v iconutil &>/dev/null; then
    mkdir -p build/icon.iconset
    sips -z 16 16   assets/icon.png --out build/icon.iconset/icon_16x16.png    &>/dev/null
    sips -z 32 32   assets/icon.png --out build/icon.iconset/icon_32x32.png    &>/dev/null
    sips -z 64 64   assets/icon.png --out build/icon.iconset/icon_64x64.png    &>/dev/null
    sips -z 128 128 assets/icon.png --out build/icon.iconset/icon_128x128.png  &>/dev/null
    sips -z 256 256 assets/icon.png --out build/icon.iconset/icon_256x256.png  &>/dev/null
    iconutil -c icns build/icon.iconset -o assets/icon.icns
    ICON_ARG="--icon assets/icon.icns"
else
    ICON_ARG=""
    echo "Warning: sips/iconutil not found, skipping ICNS conversion"
fi

# ── PyInstaller ──────────────────────────────────────────────────────
echo "Running PyInstaller..."

.venv/bin/pyinstaller \
    src/main.py \
    --name "$APP_NAME" \
    --windowed \
    --onedir \
    --add-data "assets:assets" \
    --paths src \
    --hidden-import pystray._darwin \
    --osx-bundle-identifier com.quikeys.app \
    --osx-entitlements-file assets/macos/entitlements.plist \
    $ICON_ARG \
    --noconfirm \
    --distpath dist \
    --workpath build/_work \
    --specpath build

# Inject custom Info.plist keys not supported by PyInstaller flags
PLIST="dist/${APP_NAME}.app/Contents/Info.plist"
if command -v /usr/libexec/PlistBuddy &>/dev/null; then
    /usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$PLIST" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Set :LSUIElement true" "$PLIST"
    /usr/libexec/PlistBuddy -c \
        "Add :NSAppleEventsUsageDescription string 'QuiKeys needs Accessibility access for hotkeys and text expansion.'" \
        "$PLIST" 2>/dev/null || true
fi

# ── Package into ZIP ─────────────────────────────────────────────────
ZIP_NAME="${APP_NAME}-macos-v${VERSION}.zip"
ZIP_PATH="dist/${ZIP_NAME}"

rm -f "$ZIP_PATH"
cd dist
zip -r "$ZIP_NAME" "${APP_NAME}.app" --quiet
cd ..

echo ""
echo "✅ Build complete: $ZIP_PATH"
echo "   Users: extract ZIP, right-click QuiKeys.app → Open → Open Anyway (first launch only)."
