@echo off
setlocal
cd /d "%~dp0"
echo ======================================================
echo LumOS Lokal Office - Vollstaendiger Systemstart
echo ======================================================
echo Starte Backend, Lokales LLM und Frontend...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0heal-lumos.ps1"
if %ERRORLEVEL% EQU 0 (
    echo.
    echo LumOS ist bereit! Oeffne Benutzeroberflaeche im Browser...
    start http://127.0.0.1:1420
) else (
    echo.
    echo Fehler beim Starten von LumOS. Bitte Logs-Ordner pruefen.
    pause
)
