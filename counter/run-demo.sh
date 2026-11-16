#!/usr/bin/env bash
# Start the Library Counter Demo v1.0 (browser webcam) on macOS / Linux:   bash run-demo.sh
cd "$(dirname "$0")" || exit 1
if [ ! -f .env ]; then
  echo "No .env found. Run  bash install.sh  first, then fill in .env."
  exit 1
fi
if [ -x venv/bin/python ]; then
  exec venv/bin/python demo.py
fi
exec python3 demo.py
