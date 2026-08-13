@echo off
setlocal
cd /d "%~dp0"
echo Starte LumOS Frontend auf http://127.0.0.1:1420
npm install
npm run dev
