param(
  [int]$Tail = 200
)

$ErrorActionPreference = 'Stop'

# Repo root is one level up from this scripts folder
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$logPath = Join-Path $repoRoot 'local_errors.log'

if (-not (Test-Path -LiteralPath $logPath)) {
  Write-Host "local_errors.log not found at: $logPath"
  Write-Host "If the app never started, the log may not be created yet."
  exit 1
}

Write-Host "Showing last $Tail lines from: $logPath"
Get-Content -LiteralPath $logPath -Tail $Tail
