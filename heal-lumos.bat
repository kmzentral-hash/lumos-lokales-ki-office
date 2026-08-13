@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0heal-lumos.ps1" -Restart
if errorlevel 1 (
  echo.
  echo LumOS Selbstheilung konnte nicht abgeschlossen werden.
  pause
  exit /b 1
)
echo.
echo LumOS Selbstheilung abgeschlossen.
pause
