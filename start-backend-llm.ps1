param(
    [string]$LlmBaseUrl = "http://127.0.0.1:8080/v1",
    [string]$ModelName = "qwen2.5-7b-instruct-q4_k_m",
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$CoreRoot = Join-Path $ProjectRoot "core"

$env:LUMOS_LLM_BASE_URL = $LlmBaseUrl
$env:LUMOS_LLM_MODEL = $ModelName
$env:LUMOS_LLM_TIMEOUT_SECONDS = "$TimeoutSeconds"

Set-Location $CoreRoot
uv run uvicorn lumos_core.main:app --host 127.0.0.1 --port 8765
