$env:LUMOS_LLM_BASE_URL = "http://127.0.0.1:18080/v1"
$env:LUMOS_LLM_MODEL = "fake-local-model"
uv run uvicorn lumos_core.main:app --host 127.0.0.1 --port 8765
