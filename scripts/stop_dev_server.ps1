
param(
	[switch]$ForcePortKill,
	[int]$Port = 5000
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $repoRoot "flask_dev_server.pid"

function Get-ListeningPids([int]$ListenPort) {
	try {
		return Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction SilentlyContinue |
			Select-Object -ExpandProperty OwningProcess -Unique
	} catch {
		return @()
	}
}

function Stop-Pids([int[]]$Pids) {
	foreach ($procId in ($Pids | Where-Object { $_ })) {
		try {
			Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
			Write-Host "Stopped PID $procId"
		} catch {
			# ignore
		}
	}
}

if ($ForcePortKill) {
	$pids = @(Get-ListeningPids -ListenPort $Port)
	if ($pids.Count -eq 0) {
		Write-Host "No listener on :$Port"
		exit 0
	}
	Write-Host "Force-stopping PID(s) on :$Port => $($pids -join ', ')"
	Stop-Pids -Pids $pids
	exit 0
}

if (Test-Path $pidFile) {
	$pidText = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
	$pidVal = 0
	[void][int]::TryParse($pidText, [ref]$pidVal)
	if ($pidVal -gt 0) {
		Write-Host "Stopping dev server PID $pidVal ..."
		Stop-Pids -Pids @($pidVal)
	}
	try { Remove-Item $pidFile -Force -ErrorAction SilentlyContinue } catch { }
	exit 0
}

# Fallback: if pidfile missing, stop whatever is listening.
$fallbackPids = @(Get-ListeningPids -ListenPort $Port)
if ($fallbackPids.Count -gt 0) {
	Write-Host "Stopping listener PID(s) on :$Port => $($fallbackPids -join ', ')"
	Stop-Pids -Pids $fallbackPids
} else {
	Write-Host "Nothing to stop."
}

