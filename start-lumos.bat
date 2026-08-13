@echo off
setlocal
cd /d "%~dp0"
echo Starte LumOS mit Selbstheilung.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0heal-lumos.ps1"
echo Frontend: http://127.0.0.1:1420
echo Backend:  http://127.0.0.1:8765/docs
