@echo off
REM Start the on-premise counter portal on Windows.
cd /d %~dp0
if not exist .env (
  echo No .env found. Copy .env.example to .env and fill it in first.
  pause
  exit /b 1
)
if exist venv\Scripts\python.exe (
  venv\Scripts\python.exe app.py
) else (
  python app.py
)
pause
