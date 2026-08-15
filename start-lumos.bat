@echo off
setlocal
cd /d "%~dp0"
title LumOS Lokal Office v1.4.0

echo ======================================================
echo LumOS Lokal Office - Vollstaendiger Systemstart (v1.4.0)
echo ======================================================
echo Starte Backend, Lokales LLM und Frontend...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0heal-lumos.ps1"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ======================================================
    echo LumOS ist ERFOLGREICH GESTARTET und BEREIT!
    echo ======================================================
    echo - Frontend:   http://127.0.0.1:1420
    echo - Backend:    http://127.0.0.1:8765/docs
    echo - LLM Engine: http://127.0.0.1:8080/v1 (Qwen2.5-7B)
    echo.
    echo Benutzeroberflaeche wird im Browser geoeffnet...
    start http://127.0.0.1:1420
    echo.
    echo Dieses Fenster laeuft als LumOS System-Dienst.
    echo Zum Beenden druecke Strg+C oder schliesse dieses Fenster.
    echo.
    pause
) else (
    echo.
    echo Fehler beim Starten von LumOS. Bitte Logs-Ordner pruefen.
    pause
)
