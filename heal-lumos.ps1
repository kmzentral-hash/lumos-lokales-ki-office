param(
    [switch]$Restart,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$CoreRoot = Join-Path $ProjectRoot "core"
$BackendPort = 8765
$FrontendPort = 1420
$BackendUrl = "http://127.0.0.1:$BackendPort"
$FrontendUrl = "http://127.0.0.1:$FrontendPort"
$LogDir = Join-Path $ProjectRoot "logs"

function Write-Step($Message) {
    Write-Host ""
    Write-Host "== $Message ==" -ForegroundColor Cyan
}

function Write-Ok($Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn($Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Test-Command($Name, $InstallHint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name wurde nicht gefunden. $InstallHint"
    }
}

function Get-Listener($Port) {
    Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
}

function Stop-LumosPortProcess($Port) {
    $Listener = Get-Listener $Port
    if (-not $Listener) {
        return
    }

    $Process = Get-Process -Id $Listener.OwningProcess -ErrorAction SilentlyContinue
    if (-not $Process) {
        return
    }

    $Path = [string]$Process.Path
    $LooksLikeLumos = $Path.StartsWith($ProjectRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        $Path.StartsWith($CoreRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        $Process.ProcessName -match "^(node|npm|python|uv|uvicorn)$"

    if ($LooksLikeLumos) {
        Write-Warn "Port $Port ist belegt durch $($Process.ProcessName) ($($Process.Id)); starte ihn neu."
        Stop-Process -Id $Process.Id -Force
        Start-Sleep -Seconds 1
        return
    }

    throw "Port $Port ist durch einen fremden Prozess belegt: $($Process.ProcessName) ($($Process.Id)). Bitte manuell pruefen."
}

function Wait-HttpOk($Url, $Name, $Seconds = 30) {
    for ($Index = 0; $Index -lt $Seconds; $Index++) {
        try {
            $Response = Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 2
            if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500) {
                Write-Ok "$Name antwortet auf $Url"
                return $true
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return $false
}

function Test-JsonPost($Url, $Body, $Name) {
    try {
        $Json = $Body | ConvertTo-Json -Compress
        Invoke-RestMethod $Url -Method Post -ContentType "application/json" -Body $Json -TimeoutSec 5 | Out-Null
        Write-Ok "$Name ist verfuegbar"
        return $true
    } catch {
        Write-Warn "$Name ist nicht verfuegbar: $($_.Exception.Message)"
        return $false
    }
}

Write-Step "LumOS Selbstheilung startet"
Write-Host "Projekt: $ProjectRoot"

Write-Step "Werkzeuge pruefen"
Test-Command "node" "Bitte Node.js 22+ installieren."
Test-Command "npm" "Bitte Node.js/npm installieren."
Test-Command "uv" "Bitte uv installieren: https://docs.astral.sh/uv/"
Write-Ok "node, npm und uv gefunden"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not $SkipInstall) {
    Write-Step "Abhaengigkeiten pruefen"
    Push-Location $ProjectRoot
    try {
        npm install
    } finally {
        Pop-Location
    }
    Push-Location $CoreRoot
    try {
        uv sync
    } finally {
        Pop-Location
    }
    Write-Ok "Frontend- und Backend-Abhaengigkeiten sind synchronisiert"
}

Write-Step "Ports pruefen"
if ($Restart) {
    Stop-LumosPortProcess $BackendPort
    Stop-LumosPortProcess $FrontendPort
} else {
    if (Get-Listener $BackendPort) { Write-Warn "Backend-Port $BackendPort ist bereits belegt; vorhandener Dienst wird verwendet." }
    if (Get-Listener $FrontendPort) { Write-Warn "Frontend-Port $FrontendPort ist bereits belegt; vorhandener Dienst wird verwendet." }
}

Write-Step "Backend starten"
if (-not (Get-Listener $BackendPort)) {
    $BackendOut = Join-Path $LogDir "backend.out.log"
    $BackendErr = Join-Path $LogDir "backend.err.log"
    Start-Process -FilePath "uv" `
        -ArgumentList "run", "uvicorn", "lumos_core.main:app", "--host", "127.0.0.1", "--port", "$BackendPort" `
        -WorkingDirectory $CoreRoot `
        -RedirectStandardOutput $BackendOut `
        -RedirectStandardError $BackendErr `
        -WindowStyle Hidden
}

if (-not (Wait-HttpOk "$BackendUrl/api/v1/health" "Backend Healthcheck" 40)) {
    throw "Backend startet nicht korrekt. Siehe logs/backend.err.log und logs/backend.out.log."
}

Write-Step "RAG-Schnittstellen pruefen"
Test-JsonPost "$BackendUrl/api/v1/search" @{ query = "__lumos_self_heal_probe__"; limit = 1 } "RAG-Suche" | Out-Null
try {
    $Llm = Invoke-RestMethod "$BackendUrl/api/v1/llm/status" -TimeoutSec 5
    if ($Llm.generation_available) {
        Write-Ok "Lokale KI-Antwort ist verfuegbar ($($Llm.model))"
    } elseif ($Llm.configured) {
        Write-Warn "Lokale KI ist konfiguriert, aber nicht erreichbar: $($Llm.last_error)"
    } else {
        Write-Warn "Lokale KI ist optional und aktuell nicht konfiguriert."
    }
} catch {
    Write-Warn "LLM-Status konnte nicht geprueft werden: $($_.Exception.Message)"
}
try {
    $Documents = Invoke-RestMethod "$BackendUrl/api/v1/documents" -TimeoutSec 5
    $Count = @($Documents.documents).Count
    Write-Ok "Dokument-API ist verfuegbar ($Count Dokumente)"
} catch {
    Write-Warn "Dokument-API ist nicht verfuegbar: $($_.Exception.Message)"
}

Write-Step "Frontend starten"
if (-not (Get-Listener $FrontendPort)) {
    $FrontendOut = Join-Path $LogDir "frontend.out.log"
    $FrontendErr = Join-Path $LogDir "frontend.err.log"
    Start-Process -FilePath "npm.cmd" `
        -ArgumentList "run", "dev" `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $FrontendOut `
        -RedirectStandardError $FrontendErr `
        -WindowStyle Hidden
}

if (-not (Wait-HttpOk $FrontendUrl "Frontend" 40)) {
    throw "Frontend startet nicht korrekt. Siehe logs/frontend.err.log und logs/frontend.out.log."
}

Write-Step "LumOS ist bereit"
Write-Ok "Frontend: $FrontendUrl"
Write-Ok "Backend:  $BackendUrl/docs"
Write-Ok "Health:   $BackendUrl/api/v1/health"
