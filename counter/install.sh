#!/usr/bin/env bash
# ============================================================================
#  One-time setup for the Library Counter on macOS / Linux.
#  Run from Terminal:   bash install.sh
#  Creates a private Python environment (venv) and installs everything.
#  Safe to run again - it picks up where it left off.
# ============================================================================
cd "$(dirname "$0")" || exit 1

fail() {
  echo
  echo "  Installation did not finish - usually a slow or blocked internet connection."
  echo "  Just run  bash install.sh  again; already-downloaded parts are kept."
  echo
  exit 1
}

# --- find a Python 3.10+ (macOS ships an old python3 stub on some machines)
PY=""
for cand in python3.12 python3.11 python3.10 python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && \
     "$cand" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
    PY="$cand"; break
  fi
done
if [ -z "$PY" ]; then
  echo
  echo "  Python 3.10 or newer is not installed."
  echo "  macOS: install it from https://www.python.org/downloads/"
  echo "  Linux: sudo apt install python3 python3-venv   (or your distro's equivalent)"
  echo "  Then run  bash install.sh  again."
  echo
  exit 1
fi
echo "Using $("$PY" --version)"

# a half-made venv (e.g. from a failed earlier run) has python but no pip
if [ -d venv ] && ! venv/bin/python -m pip --version >/dev/null 2>&1; then
  rm -rf venv
fi
if [ ! -x venv/bin/python ]; then
  echo "Creating a private environment..."
  if ! "$PY" -m venv venv; then
    rm -rf venv
    echo
    echo "  Could not create the environment."
    echo "  On Ubuntu/Debian run:  sudo apt install python3-venv   and try again."
    exit 1
  fi
fi
VPY="venv/bin/python"
PIP_OPTS="--disable-pip-version-check -q --timeout 180 --retries 10"

echo
echo "[1/3] Installing the detection engine. This can take several minutes..."
if [ "$(uname -s)" = "Darwin" ]; then
  # macOS wheels on the normal index are already CPU/Apple-silicon builds
  $VPY -m pip install $PIP_OPTS torch torchvision || fail
else
  # Linux: the CPU-only build avoids a ~2 GB GPU download
  $VPY -m pip install $PIP_OPTS torch torchvision --index-url https://download.pytorch.org/whl/cpu || fail
fi

echo "[2/3] Installing the remaining components..."
$VPY -m pip install $PIP_OPTS -r requirements.txt || fail

echo "[3/3] Checking everything loads..."
if ! YOLO_OFFLINE=1 $VPY -c "import ultralytics, cv2, fastapi, cryptography; print('      All components OK')"; then
  if [ "$(uname -s)" = "Linux" ]; then
    echo "  If the error mentions libGL, run:  sudo apt install libgl1 libglib2.0-0"
  fi
  fail
fi

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo
  echo "  Created .env - fill in PORTAL_EMAIL, PORTAL_PASSWORD and DEVICE_API_KEY."
  if [ "$(uname -s)" = "Darwin" ]; then
    echo "  Open it with:   open -e .env"
  else
    echo "  Open it with:   nano .env      (Ctrl+O, Enter to save; Ctrl+X to exit)"
  fi
fi

echo
echo "  Setup complete."
echo "  - Webcam demo:   bash run-demo.sh   then open http://127.0.0.1:8901"
echo "  - CCTV counter:  bash run.sh        then open http://127.0.0.1:8900"
echo
