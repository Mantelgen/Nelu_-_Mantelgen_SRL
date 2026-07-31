#!/usr/bin/env bash
set -euo pipefail

# Make Deno available (required by yt-dlp 2025+ for YouTube n-challenge solving)
export PATH="$HOME/.deno/bin:$PATH"

echo "Starting Discord Music Bot..."

PY_EXE="venv/bin/python"
if [[ ! -x "$PY_EXE" ]]; then
  PY_EXE="venv313/bin/python"
fi

if [[ ! -x "$PY_EXE" ]]; then
  echo "No virtualenv Python found. Run ./setup.sh first."
  exit 1
fi

"$PY_EXE" --version
"$PY_EXE" bot.py
