param(
    [string]$RuntimePath = "",
    [string]$ModelPath = "",
    [string]$ModelName = "qwen2.5-7b-instruct-q4_k_m",
    [int]$ContextSize = 4096,
    [int]$GpuLayers = 32,
    [int]$Port = 8080
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $ProjectRoot "logs"

if (-not $RuntimePath) {
    $RuntimePath = if ($env:LUMOS_LLAMA_SERVER_EXE) {
        $env:LUMOS_LLAMA_SERVER_EXE
    } else {
        "tools/llama.cpp/b10375/llama-server.exe"
    }
}

if (-not $ModelPath) {
    $ModelPath = if ($env:LUMOS_LLAMA_MODEL_PATH) {
        $env:LUMOS_LLAMA_MODEL_PATH
    } else {
        "models/Qwen/Qwen2.5-7B-Instruct-GGUF/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf"
    }
}

if ($env:LUMOS_LLAMA_CONTEXT) {
    $ContextSize = [int]$env:LUMOS_LLAMA_CONTEXT
}
if ($env:LUMOS_LLAMA_GPU_LAYERS) {
    $GpuLayers = [int]$env:LUMOS_LLAMA_GPU_LAYERS
}
if ($env:LUMOS_LLM_MODEL) {
    $ModelName = $env:LUMOS_LLM_MODEL
}

$RuntimeFullPath = if ([System.IO.Path]::IsPathRooted($RuntimePath)) {
    $RuntimePath
} else {
    Join-Path $ProjectRoot $RuntimePath
}
$ModelFullPath = if ([System.IO.Path]::IsPathRooted($ModelPath)) {
    $ModelPath
} else {
    Join-Path $ProjectRoot $ModelPath
}

if (-not (Test-Path -LiteralPath $RuntimeFullPath -PathType Leaf)) {
    throw "llama-server.exe wurde nicht gefunden: $RuntimeFullPath"
}
if (-not (Test-Path -LiteralPath $ModelFullPath -PathType Leaf)) {
    throw "GGUF-Modell wurde nicht gefunden: $ModelFullPath"
}

$Existing = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($Existing) {
    throw "Port $Port ist bereits auf 127.0.0.1 belegt. Bitte stop-llm.ps1 oder einen anderen Port verwenden."
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$OutLog = Join-Path $LogDir "llama-server.out.log"
$ErrLog = Join-Path $LogDir "llama-server.err.log"

$env:LUMOS_LLM_BASE_URL = "http://127.0.0.1:$Port/v1"
$env:LUMOS_LLM_MODEL = $ModelName

$Arguments = @(
    "--host", "127.0.0.1",
    "--port", "$Port",
    "--model", $ModelFullPath,
    "--alias", $ModelName,
    "--ctx-size", "$ContextSize",
    "--n-gpu-layers", "$GpuLayers"
)

Write-Host "Starte llama-server auf http://127.0.0.1:$Port"
Write-Host "Modell: $ModelName"
Write-Host "Kontext: $ContextSize"
Write-Host "GPU-Layer: $GpuLayers"

Start-Process -FilePath $RuntimeFullPath `
    -ArgumentList $Arguments `
    -WorkingDirectory (Split-Path -Parent $RuntimeFullPath) `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -WindowStyle Hidden

Write-Host "Logs: $OutLog / $ErrLog"
