@echo off
REM ============================================================================
REM  One-time setup for the Library Counter. Double-click this file.
REM  Creates a private Python environment (venv) and installs everything.
REM  Safe to run again - it picks up where it left off.
REM ============================================================================
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
  echo.
  echo   Python is not installed.
  echo   Install Python 3.10 or newer from https://www.python.org/downloads/
  echo   and tick "Add Python to PATH" during installation. Then run this again.
  echo.
  pause
  exit /b 1
)

REM --- Windows limits file paths to 260 characters unless "long paths" are on.
REM     The detection engine has deeply nested files, so the folder must sit on
REM     a short path, or its installation breaks part-way.
set "LONGPATHS=0"
for /f "tokens=3" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled 2^>nul ^| find "LongPathsEnabled"') do set "LONGPATHS=%%a"
if "%LONGPATHS%"=="0x1" goto :pathok
python -c "import os,sys; sys.exit(0 if len(os.getcwd()) <= 60 else 1)"
if not errorlevel 1 goto :pathok
echo.
echo   This folder is too deep for Windows - its path is longer than 60 characters:
echo   "%CD%"
echo   Move the counter folder to a short location such as C:\library-counter
echo   and run install.bat again from there.
echo.
pause
exit /b 1
:pathok

if not exist "venv\Scripts\python.exe" (
  echo Creating a private environment...
  python -m venv venv
  if errorlevel 1 goto :fail
)

echo.
echo [1/3] Installing the detection engine (CPU build, about 200 MB).
echo       This can take several minutes on a slow connection...
venv\Scripts\python.exe -m pip install --disable-pip-version-check -q --timeout 180 --retries 10 torch torchvision --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto :fail

echo [2/3] Installing the remaining components...
venv\Scripts\python.exe -m pip install --disable-pip-version-check -q --timeout 180 --retries 10 -r requirements.txt
if errorlevel 1 goto :fail

echo [3/3] Checking everything loads...
set "YOLO_OFFLINE=1"
venv\Scripts\python.exe -c "import ultralytics, cv2, fastapi, cryptography; print('      All components OK')"
if errorlevel 1 goto :fail

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo.
  echo   Created .env - open it in Notepad and fill in PORTAL_EMAIL, PORTAL_PASSWORD,
  echo   DEVICE_API_KEY and BACKEND_URL before starting.
)

echo.
echo   Setup complete.
echo   - Webcam demo:      double-click run-demo.bat, open http://127.0.0.1:8901
echo   - CCTV counter:     double-click run.bat,      open http://127.0.0.1:8900
echo.
pause
exit /b 0

:fail
echo.
echo   Installation did not finish - usually a slow or blocked internet connection.
echo   Just run install.bat again; already-downloaded parts are kept.
echo.
pause
exit /b 1
