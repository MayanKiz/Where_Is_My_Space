#!/usr/bin/env bash
# Start the on-premise counter portal on macOS / Linux:   bash run.sh
cd "$(dirname "$0")" || exit 1
if [ ! -f .env ]; then
  echo "No .env found. Run  bash install.sh  first, then fill in .env."
  exit 1
fi
if [ -x venv/bin/python ]; then
  exec venv/bin/python app.py
fi
exec python3 app.py
