#!/usr/bin/env bash
set -euo pipefail

echo "Starting Discord Music Bot..."

VENV_DIR="${VENV_DIR:-venv}"
PY_EXE="$VENV_DIR/bin/python"

if [[ ! -x "$PY_EXE" ]]; then
  echo "No virtualenv Python found. Run ./setup.sh first."
  exit 1
fi

"$PY_EXE" --version
"$PY_EXE" bot.py
