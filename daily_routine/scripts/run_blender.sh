#!/usr/bin/env bash
# Blender CLIラッパースクリプト
#
# macOS環境でBlenderのbundled Pythonが正しく解決されない問題を回避する。
# 原因: シンボリックリンク経由の起動でPythonパスがビルド時のハードコード値になる。
#       また、pyenvやVSCodeのPYTHONSTARTUPが干渉する。
#
# 使い方:
#   scripts/run_blender.sh --background file.blend --python script.py
#   scripts/run_blender.sh --background file.blend --python-expr "import bpy; ..."

set -euo pipefail

# Blender.appのパス（標準インストール先）
BLENDER_APP="/Applications/Blender.app"
BLENDER_BIN="${BLENDER_APP}/Contents/MacOS/Blender"

if [[ ! -x "$BLENDER_BIN" ]]; then
    echo "ERROR: Blender not found at ${BLENDER_BIN}" >&2
    exit 1
fi

# Blenderのバージョンを検出してPythonパスを解決
BLENDER_RESOURCES="${BLENDER_APP}/Contents/Resources"
BLENDER_PYTHON=$(find "$BLENDER_RESOURCES" -maxdepth 2 -type d -name "python" | head -1)

if [[ -z "$BLENDER_PYTHON" ]]; then
    echo "ERROR: Blender bundled Python not found in ${BLENDER_RESOURCES}" >&2
    exit 1
fi

# 干渉する環境変数をクリアし、PYTHONHOMEを明示的に設定して実行
exec env \
    -u PYTHONSTARTUP \
    -u PYTHONPATH \
    PYTHONHOME="$BLENDER_PYTHON" \
    "$BLENDER_BIN" "$@"
