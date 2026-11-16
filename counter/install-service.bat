@echo off
REM ============================================================================
REM  Installs the Library Counter as a Windows background service (scheduled task)
REM  so it starts automatically at boot and restarts itself if it ever stops.
REM  Right-click this file  ->  "Run as administrator".
REM ============================================================================
setlocal
cd /d "%~dp0"

REM --- must be Administrator ---
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo.
  echo   Please run this as Administrator:
  echo   right-click install-service.bat  ->  Run as administrator
  echo.
  pause
  exit /b 1
)

REM --- need a config file ---
if not exist "%~dp0.env" (
  echo.
  echo   No .env found. Copy .env.example to .env and fill it in first.
  echo.
  pause
  exit /b 1
)

REM --- pick pythonw: prefer the venv, fall back to system ---
set "PYW=%~dp0venv\Scripts\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw.exe"

REM --- counter folder without trailing backslash ---
set "APPDIR=%~dp0"
if "%APPDIR:~-1%"=="\" set "APPDIR=%APPDIR:~0,-1%"

echo Installing scheduled task "LibraryCounter" ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$a = New-ScheduledTaskAction -Execute '%PYW%' -Argument 'app.py' -WorkingDirectory '%APPDIR%';" ^
  "$t = New-ScheduledTaskTrigger -AtStartup;" ^
  "$p = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest;" ^
  "$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew;" ^
  "Register-ScheduledTask -TaskName 'LibraryCounter' -Action $a -Trigger $t -Principal $p -Settings $s -Force | Out-Null;" ^
  "Start-ScheduledTask -TaskName 'LibraryCounter'"

if %errorlevel% neq 0 (
  echo.
  echo   Installation failed. See the message above.
  pause
  exit /b 1
)

echo.
echo   Done. The counter now runs in the background, starts at every boot,
echo   and restarts on its own if it stops.
echo.
echo   Open the portal:  http://127.0.0.1:8900
echo.
pause
