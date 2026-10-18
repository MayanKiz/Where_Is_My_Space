@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv-live\Scripts\python.exe" (
    echo [WIMS] Creating an isolated local webcam environment...
    py -3.12 -m venv .venv-live 2>nul
)
if not exist ".venv-live\Scripts\python.exe" (
    python -m venv .venv-live
)
if not exist ".venv-live\Scripts\python.exe" (
    echo [ERROR] Python was not found. Install Python 3.12 or newer and enable "Add Python to PATH".
    pause
    exit /b 1
)

echo [WIMS] Checking local webcam dependencies...
".venv-live\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements-local.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. Check your internet connection and Python installation.
    pause
    exit /b 1
)

echo [WIMS] Starting live webcam people count and seat-zone estimate...
".venv-live\Scripts\python.exe" live_webcam.py %*
if errorlevel 1 (
    echo.
    echo [WIMS] The demo stopped with an error. Read the message above.
    pause
)
endlocal
