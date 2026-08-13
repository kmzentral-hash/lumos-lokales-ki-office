@echo off
setlocal
cd /d "%~dp0core"
echo Starte LumOS Backend auf http://127.0.0.1:8765
uv sync
uv run uvicorn lumos_core.main:app --host 127.0.0.1 --port 8765
