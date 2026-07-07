<#
.SYNOPSIS
    Local development launcher for ResumaticAI (Windows / PowerShell)

.DESCRIPTION
    Runs the project on your desktop WITHOUT touching or interfering
    with your live Azure deployment settings.

    All Python packages are installed into a local .\venv virtual
    environment - your system Python is never modified.

.PARAMETER Mode
    preview  (default) - Build React with Vite, then serve via Flask + Stripe
    dev                - Flask + Vite hot-reload + Stripe running side by side
    flask              - Flask + Stripe only (reuse existing React build)
    install            - Create venv, install Python + Node deps, then exit

.EXAMPLE
    .\run_local.ps1              # preview mode
    .\run_local.ps1 dev          # hot-reload dev mode
    .\run_local.ps1 flask        # Flask + Stripe only
    .\run_local.ps1 install      # install deps only

.NOTES
    First-time setup:
      1. Copy .env.local.example -> .env.local
      2. Fill in any local-only overrides (API keys etc.)
      3. Run: .\run_local.ps1

    If you see "running scripts is disabled", run once as Admin:
      Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
#>

param(
    [string]$Mode = "preview"
)

# ── Strict mode ───────────────────────────────────────────────────
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Ports ─────────────────────────────────────────────────────────
$FLASK_PORT = 5001    # prod uses 8000 - no clash
$VITE_PORT  = 5173    # Vite dev server

# ── Resolve project root ──────────────────────────────────────────
$ROOT = $PSScriptRoot
Set-Location $ROOT

# ── Colour helpers ────────────────────────────────────────────────
function Write-Info    { param([string]$Msg) Write-Host "[local] $Msg" -ForegroundColor Cyan    }
function Write-Success { param([string]$Msg) Write-Host "[local] $Msg" -ForegroundColor Green   }
function Write-Warn    { param([string]$Msg) Write-Host "[local] $Msg" -ForegroundColor Yellow  }
function Write-Err     { param([string]$Msg) Write-Host "[local] ERROR: $Msg" -ForegroundColor Red }

function Write-Banner {
    param([string]$Title)
    $line = "=" * 44
    Write-Host ""
    Write-Host $line                       -ForegroundColor DarkCyan
    Write-Host "  $Title"                  -ForegroundColor White
    Write-Host $line                       -ForegroundColor DarkCyan
    Write-Host ""
}

# ══════════════════════════════════════════════════════════════════
#  STEP 1 - Find the real system Python (only used to create the venv)
# ══════════════════════════════════════════════════════════════════
function Find-SystemPython {
    foreach ($cmd in @("python", "python3", "py")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $found) { continue }

        # Reject the Windows Store stub (it pops a dialog instead of running)
        $ver = & $cmd -c "import sys; print(sys.version_info >= (3,9))" 2>$null
        if ($ver -eq "True") {
            return $cmd
        }
    }
    Write-Err "Python 3.9+ not found. Install Python and add it to your PATH."
    Write-Err "Download: https://www.python.org/downloads/"
    exit 1
}

# ══════════════════════════════════════════════════════════════════
#  STEP 2 - Create .\venv if missing, then return path to venv Python
# ══════════════════════════════════════════════════════════════════
$VENV_DIR = Join-Path $ROOT "venv"
$VENV_PY  = Join-Path $VENV_DIR "Scripts\python.exe"

function Ensure-Venv {
    param([string]$SysPython)

    if (Test-Path $VENV_PY) {
        Write-Info "Virtual env    : $VENV_DIR  (already exists)"
    } else {
        Write-Info "Creating virtual environment at $VENV_DIR ..."
        & $SysPython -m venv $VENV_DIR
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VENV_PY)) {
            Write-Err "Failed to create virtual environment."
            exit 1
        }
        Write-Success "Virtual environment created."
    }

    $pyVer = & $VENV_PY --version 2>&1
    Write-Info "Venv Python    : $VENV_PY  ($pyVer)"
}

# ══════════════════════════════════════════════════════════════════
#  STEP 3 - Upgrade pip inside the venv
# ══════════════════════════════════════════════════════════════════
function Upgrade-Pip {
    Write-Info "Upgrading pip inside venv..."
    & $VENV_PY -m pip install --quiet --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "pip upgrade failed - continuing anyway."
    }
}

# ══════════════════════════════════════════════════════════════════
#  STEP 4 - Install Python dependencies into the venv
# ══════════════════════════════════════════════════════════════════
function Install-PythonDeps {
    if (-not (Test-Path "requirements.txt")) {
        Write-Warn "requirements.txt not found - skipping pip install."
        return
    }

    # Fast check: if Flask is already importable in the venv, skip
    $flaskOk = & $VENV_PY -c "import flask" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Info "Python deps already installed in venv - skipping."
        return
    }

    Upgrade-Pip
    Write-Info "Installing Python dependencies into venv..."
    & $VENV_PY -m pip install --quiet -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Err "pip install failed. Check requirements.txt and your internet connection."
        exit 1
    }
    Write-Success "Python dependencies installed."
}

# ── Node / npm helpers ────────────────────────────────────────────
function Test-Node {
    $node = Get-Command node -ErrorAction SilentlyContinue
    if (-not $node) {
        Write-Warn "Node.js not found - React build steps will be skipped."
        return $false
    }
    $ver = node --version 2>&1
    Write-Info "Node.js        : $ver"
    return $true
}

$FRONTEND_DIRS = @("frontend", "resume_builder_frontend")

function Install-NodeDeps {
    foreach ($dir in $FRONTEND_DIRS) {
        if (Test-Path $dir) {
            Write-Info "Checking Node deps for $dir..."
            $nodeModules = Join-Path $dir "node_modules"
            if (-not (Test-Path $nodeModules)) {
                Write-Info "Installing Node dependencies in $dir (first run)..."
                Push-Location $dir
                npm install --silent
                Pop-Location
                if ($LASTEXITCODE -ne 0) {
                    Write-Err "npm install failed in $dir."
                    exit 1
                }
                Write-Success "Node dependencies installed in $dir."
            } else {
                Write-Info "Node deps      : $dir\node_modules\ already present."
            }
        }
    }
}

function Build-React {
    foreach ($dir in $FRONTEND_DIRS) {
        if (Test-Path $dir) {
            Write-Info "Building React frontend in $dir..."
            Push-Location $dir
            npm run build
            Pop-Location
            if ($LASTEXITCODE -ne 0) {
                Write-Err "React build failed in $dir."
                exit 1
            }
            Write-Success "React build complete for $dir."
        }
    }
}

# ── Stripe CLI helper ─────────────────────────────────────────────
function Start-Stripe {
    $stripe = Get-Command stripe -ErrorAction SilentlyContinue
    if (-not $stripe) {
        Write-Warn "Stripe CLI not found in PATH. Skipping webhook forwarding."
        Write-Warn "Download: https://docs.stripe.com/stripe-cli"
        return $null
    }
    Write-Info "Starting Stripe CLI webhook listener..."
    # Launches Stripe listening in a separate window so it doesn't clutter Flask logs
    $stripeProc = Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/k", "stripe listen --forward-to 127.0.0.1:$FLASK_PORT/stripe/webhook" `
        -PassThru
    return $stripeProc
}

# ── Load .env.local on top of .env (local overrides win) ──────────
function Load-LocalEnv {
    if (Test-Path ".env.local") {
        Write-Info "Loading .env.local overrides..."
        foreach ($line in Get-Content ".env.local") {
            # Skip comments and blank lines
            if ($line -match '^\s*#' -or [string]::IsNullOrWhiteSpace($line)) { continue }
            # Parse KEY=VALUE  (value may contain = signs)
            if ($line -match '^([^=]+)=(.*)$') {
                $key = $Matches[1].Trim()
                $val = $Matches[2].Trim()
                [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
            }
        }
    } else {
        Write-Warn ".env.local not found - using .env only."
        Write-Warn "Tip: copy .env.local.example to .env.local to add local overrides."
    }
}

# ── Force LOCAL mode - never let the app think it is on Azure ─────
function Set-LocalMode {
    foreach ($v in @("WEBSITE_HOSTNAME","WEBSITE_INSTANCE_ID","WEBSITE_SITE_NAME","APPSETTING_WEBSITE_SITE_NAME")) {
        [System.Environment]::SetEnvironmentVariable($v, $null, "Process")
        Remove-Item -Path "Env:\$v" -ErrorAction SilentlyContinue
    }

    $env:FLASK_ENV                    = "development"
    $env:FLASK_DEBUG                  = "1"
    $env:OAUTHLIB_INSECURE_TRANSPORT  = "1"
    $env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1"
}

# ── Start Flask (blocking, foreground) ────────────────────────────
function Start-Flask {
    Write-Success "Starting Flask -> http://127.0.0.1:$FLASK_PORT"
    Write-Host "  Open http://127.0.0.1:$FLASK_PORT in your browser" -ForegroundColor White
    Write-Host "  Press Ctrl+C to stop servers." -ForegroundColor DarkGray
    Write-Host ""
    & $VENV_PY -m flask run --host=127.0.0.1 --port=$FLASK_PORT --debug
}

# ══════════════════════════════════════════════════════════════════
#  Detect system Python early (only needed to build the venv)
# ══════════════════════════════════════════════════════════════════
$SYS_PY = Find-SystemPython
$sysPyVer = & $SYS_PY --version 2>&1
Write-Info "System Python  : $SYS_PY  ($sysPyVer)"

Ensure-Venv -SysPython $SYS_PY

# ══════════════════════════════════════════════════════════════════
#  INSTALL mode - set up everything, then exit
# ══════════════════════════════════════════════════════════════════
if ($Mode -eq "install") {
    Write-Banner "ResumaticAI - Install dependencies"

    Upgrade-Pip
    Install-PythonDeps

    if (Test-Node) { Install-NodeDeps }

    Write-Host ""
    Write-Success "All dependencies installed."
    Write-Success "Virtual env is at: $VENV_DIR"
    Write-Host ""
    Write-Host "  Next step: " -NoNewline
    Write-Host ".\run_local.ps1" -ForegroundColor Cyan -NoNewline
    Write-Host "  to start the local server."
    Write-Host ""
    exit 0
}

# ══════════════════════════════════════════════════════════════════
#  Shared startup for all run modes
# ══════════════════════════════════════════════════════════════════
Write-Banner "ResumaticAI - Local Preview  [mode: $Mode]"

Load-LocalEnv
Set-LocalMode
Install-PythonDeps   # fast no-op if already installed

# Initialize background processes tracking
$stripeProc = $null
$viteProc = $null

# ══════════════════════════════════════════════════════════════════
#  PREVIEW mode (default)
# ══════════════════════════════════════════════════════════════════
if ($Mode -eq "preview") {
    if (Test-Node) {
        Install-NodeDeps
        Build-React
    } else {
        Write-Warn "Skipping React build (Node.js not found)."
        if (-not (Test-Path "static\react\index.html")) {
            Write-Err "No React build found at static\react\index.html."
            Write-Err "Install Node.js 18+ to build the frontend, or run: .\run_local.ps1 flask"
            exit 1
        }
        Write-Warn "Using existing React build in static\react\."
    }

    try {
        $stripeProc = Start-Stripe
        Start-Flask
    } finally {
        if ($stripeProc -and -not $stripeProc.HasExited) {
            Write-Info "Stopping Stripe listener (pid=$($stripeProc.Id))...."
            Stop-Process -Id $stripeProc.Id -Force -ErrorAction SilentlyContinue
        }
    }

# ══════════════════════════════════════════════════════════════════
#  DEV mode
# ══════════════════════════════════════════════════════════════════
} elseif ($Mode -eq "dev") {
    if (-not (Test-Node)) {
        Write-Err "Node.js is required for dev mode."
        Write-Err "Install Node.js 18+ or use: .\run_local.ps1 flask"
        exit 1
    }
    Install-NodeDeps

    Write-Info "Starting Vite dev server on port $VITE_PORT ..."
    $env:VITE_DEV_BACKEND_URL = "http://127.0.0.1:$FLASK_PORT"
    $viteProc = Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/k", "npm run dev -- --port $VITE_PORT" `
        -PassThru

    Write-Host ""
    Write-Host "  Flask (full app) : http://127.0.0.1:$FLASK_PORT" -ForegroundColor White
    Write-Host "  Vite  (React SPA): http://127.0.0.1:$VITE_PORT"  -ForegroundColor White
    Write-Host ""

    try {
        $stripeProc = Start-Stripe
        Start-Flask
    } finally {
        if ($viteProc -and -not $viteProc.HasExited) {
            Write-Info "Stopping Vite (pid=$($viteProc.Id))..."
            Stop-Process -Id $viteProc.Id -Force -ErrorAction SilentlyContinue
        }
        if ($stripeProc -and -not $stripeProc.HasExited) {
            Write-Info "Stopping Stripe listener (pid=$($stripeProc.Id))..."
            Stop-Process -Id $stripeProc.Id -Force -ErrorAction SilentlyContinue
        }
    }

# ══════════════════════════════════════════════════════════════════
#  FLASK mode
# ══════════════════════════════════════════════════════════════════
} elseif ($Mode -eq "flask") {
    if (-not (Test-Path "static\react\index.html")) {
        Write-Warn "No React build found - React SPA routes will 404."
        Write-Warn "Run '.\run_local.ps1 preview' to build the frontend first."
    }

    try {
        $stripeProc = Start-Stripe
        Start-Flask
    } finally {
        if ($stripeProc -and -not $stripeProc.HasExited) {
            Write-Info "Stopping Stripe listener (pid=$($stripeProc.Id))..."
            Stop-Process -Id $stripeProc.Id -Force -ErrorAction SilentlyContinue
        }
    }

# ══════════════════════════════════════════════════════════════════
#  Unknown mode
# ══════════════════════════════════════════════════════════════════
} else {
    Write-Err "Unknown mode: '$Mode'"
    Write-Host ""
    Write-Host "Usage: .\run_local.ps1 [preview|dev|flask|install]"
    exit 1
}