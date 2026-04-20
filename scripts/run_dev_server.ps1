
param(
    [int]$Port = 5000
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $repoRoot "flask_dev_server.pid"
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"

function Get-ListeningPids([int]$ListenPort) {
    try {
        return Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    }
    catch {
        return @()
    }
}

if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

# If already listening, assume server is running.
$existingPids = @(Get-ListeningPids -ListenPort $Port)
if ($existingPids.Count -gt 0) {
    Write-Host "Dev server already listening on :$Port (PID(s): $($existingPids -join ', '))."
    exit 0
}

Write-Host "Starting Flask dev server on :$Port ..."

# Start detached so tasks can return immediately.
$proc = Start-Process -FilePath $pythonExe -ArgumentList "app.py" -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden

try {
    Set-Content -Path $pidFile -Value $proc.Id -Encoding ASCII
}
catch {
    # Non-fatal
}

Write-Host "Started PID $($proc.Id)."

