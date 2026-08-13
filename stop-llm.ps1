param(
    [int]$Port = 8080
)

$Listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $Listener) {
    Write-Host "Kein llama-server auf 127.0.0.1:$Port gefunden."
    exit 0
}

$Process = Get-Process -Id $Listener.OwningProcess -ErrorAction SilentlyContinue
if (-not $Process) {
    Write-Host "Prozess fuer Port $Port nicht gefunden."
    exit 0
}

if ($Process.ProcessName -notmatch "llama|server") {
    throw "Port $Port gehoert nicht offensichtlich zu llama-server: $($Process.ProcessName) ($($Process.Id))"
}

Stop-Process -Id $Process.Id -Force
Write-Host "llama-server gestoppt: $($Process.Id)"
