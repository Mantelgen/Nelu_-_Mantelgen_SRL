#!/usr/bin/env bash
set -euo pipefail

echo "=== Discord Music Bot Setup (Linux) ==="
echo

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-venv}"

echo "[1/4] Installing system dependencies (ffmpeg, libsodium, build tools)..."
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y ffmpeg libsodium-dev build-essential python3-venv
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y ffmpeg libsodium-devel gcc gcc-c++ make python3-venv
elif command -v pacman >/dev/null 2>&1; then
  sudo pacman -Sy --noconfirm ffmpeg libsodium base-devel python
else
  echo "[WARN] Unsupported package manager. Install ffmpeg + libsodium + python3-venv manually."
fi

echo "[2/4] Creating virtual environment..."
"$PYTHON_BIN" -m venv "$VENV_DIR"

echo "[3/4] Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements.txt

echo "[4/4] Done!"
echo
"$VENV_DIR/bin/python" --version
echo "Next steps:"
echo "  1. Configure .env (especially DISCORD_TOKEN)."
echo "  2. Start bot with: ./run.sh"
