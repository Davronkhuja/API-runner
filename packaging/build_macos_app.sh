#!/bin/bash
# macOS .app (alohida oyna, Dock ikonkasi): pywebview + PyInstaller.
# Ishlatish:  packaging/build_macos_app.sh [--smoke]   → dist/API Runner.app
# Frontend allaqachon apirunner/static/app da (git'da); Node kerak emas.
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
VENV=".venv-build"
[ -d "$VENV" ] || "$PY" -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt pywebview pyinstaller "quickjs-ng>=0.17"

# .icns (sips + iconutil — macOS'ning o'zida bor)
ICONSET="build/icon.iconset"
rm -rf "$ICONSET" && mkdir -p "$ICONSET"
SRC="apirunner/static/app/icon-512.png"
for s in 16 32 64 128 256 512; do
  sips -z $s $s "$SRC" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2)); [ $d -le 512 ] && sips -z $d $d "$SRC" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null || true
done
iconutil -c icns "$ICONSET" -o build/icon.icns

VERSION="$(python -c 'import apirunner; print(apirunner.__version__)')"
pyinstaller --noconfirm --clean --windowed --name "API Runner" \
  --icon build/icon.icns \
  --osx-bundle-identifier uz.localhost.apirunner \
  --add-data "apirunner/static:apirunner/static" \
  --hidden-import quickjs --collect-submodules apirunner --collect-all webview \
  --distpath dist --workpath build/pyi --specpath build \
  packaging/desktop_entry.py

# Info.plist: versiya va yuqori aniqlik
PLIST="dist/API Runner.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$PLIST" 2>/dev/null || /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $VERSION" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$PLIST" 2>/dev/null || /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $VERSION" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :NSHighResolutionCapable bool true" "$PLIST" 2>/dev/null || true
echo "✓ dist/API Runner.app (v$VERSION)"

if [ "${1:-}" = "--smoke" ]; then
  # server qismini .app ichidagi Python bilan emas, manba bilan tekshiramiz: bundle ochilishi va importlar
  APIRUNNER_HOME="$(mktemp -d)" "dist/API Runner.app/Contents/MacOS/API Runner" --selftest
fi
