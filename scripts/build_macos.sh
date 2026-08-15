#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m pip install --upgrade pip
python3 -m pip install -e '.[build]'
rm -rf build "dist/LLM API Lab.app"
mkdir -p dist/data
python3 -m PyInstaller \
  --noconfirm \
  --windowed \
  --name "LLM API Lab" \
  --osx-bundle-identifier "com.llmapilab.desktop" \
  --target-architecture universal2 \
  run_app.py
