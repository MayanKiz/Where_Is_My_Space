@echo off
REM Removes the Library Counter background service. Run as administrator.
setlocal
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Please run this as Administrator ^(right-click = Run as administrator^).
  pause
  exit /b 1
)
echo Stopping and removing scheduled task "LibraryCounter" ...
schtasks /End /TN "LibraryCounter" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Unregister-ScheduledTask -TaskName 'LibraryCounter' -Confirm:$false"
echo.
echo   Removed. The counter will no longer start automatically.
echo.
pause
