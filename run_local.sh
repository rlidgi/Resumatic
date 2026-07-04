#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  run_local.sh  –  Local development launcher for ResumaticAI
# ══════════════════════════════════════════════════════════════════
#
#  Runs the project on your desktop WITHOUT touching or interfering
#  with your live Azure deployment settings.
#
#  All Python packages are installed into a local ./venv virtual
#  environment – your system Python is never modified.
#
#  USAGE
#  ─────────────────────────────────────────────────────────────────
#    ./run_local.sh            Preview mode  (build React → start Flask)
#    ./run_local.sh dev        Dev    mode   (Flask + Vite hot-reload in parallel)
#    ./run_local.sh flask      Flask  only   (reuse existing React build)
#    ./run_local.sh install    Install deps only (venv + pip + npm)
#
#  PREREQUISITES
#  ─────────────────────────────────────────────────────────────────
#    • Python 3.9+  (python or python3 on your PATH)
#    • Node.js 18+  (only needed for "preview" / "dev" modes)
#    • Run in Git Bash, WSL, or any POSIX shell on Windows
#
#  FIRST-TIME SETUP
#  ─────────────────────────────────────────────────────────────────
#    1. Copy .env.local.example → .env.local
#    2. Fill in any local-only overrides (API keys etc.)
#    3. Run:  ./run_local.sh
#       (creates ./venv, installs packages, builds React, starts Flask)
#
# ══════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${CYAN}[local]${RESET} $*"; }
success() { echo -e "${GREEN}[local]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[local]${RESET} $*"; }
error()   { echo -e "${RED}[local] ERROR:${RESET} $*"; }

# ── Resolve project root (wherever this script lives) ─────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# ── Mode / port config ────────────────────────────────────────────
MODE="${1:-preview}"
FLASK_PORT=5001       # Local Flask port (prod uses 8000 – no port clash)
VITE_PORT=5173        # Vite dev server port

# ══════════════════════════════════════════════════════════════════
#  STEP 1 – Find the system Python (used only to CREATE the venv)
# ══════════════════════════════════════════════════════════════════
detect_system_python() {
    # On Windows, 'python3' often resolves to the MS Store stub – try 'python' first.
    for cmd in python python3; do
        if command -v "${cmd}" &>/dev/null; then
            # Reject the Windows Store stub (it exits non-zero for -c)
            if "${cmd}" -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
                echo "${cmd}"; return 0
            fi
        fi
    done
    error "Python 3.9+ not found. Install Python and add it to your PATH."
    exit 1
}

SYS_PY="$(detect_system_python)"
info "System Python : ${SYS_PY} ($(${SYS_PY} --version 2>&1))"

# ══════════════════════════════════════════════════════════════════
#  STEP 2 – Create ./venv if it does not exist, then point PY at it
# ══════════════════════════════════════════════════════════════════
VENV_DIR="${SCRIPT_DIR}/venv"

# Resolve the venv Python path (Windows uses Scripts/, Unix uses bin/)
venv_python_path() {
    if [ -f "${VENV_DIR}/Scripts/python.exe" ]; then
        echo "${VENV_DIR}/Scripts/python.exe"
    elif [ -f "${VENV_DIR}/bin/python" ]; then
        echo "${VENV_DIR}/bin/python"
    else
        echo ""
    fi
}

ensure_venv() {
    local vp
    vp="$(venv_python_path)"

    if [ -n "${vp}" ] && [ -x "${vp}" ]; then
        info "Virtual env    : ${VENV_DIR} (already exists)"
    else
        info "Creating virtual environment at ${VENV_DIR} ..."
        "${SYS_PY}" -m venv "${VENV_DIR}"
        vp="$(venv_python_path)"
        if [ -z "${vp}" ] || [ ! -x "${vp}" ]; then
            error "Virtual environment creation failed."
            exit 1
        fi
        success "Virtual environment created."
    fi

    # From here on, PY always refers to the venv interpreter
    PY="${vp}"
    info "Venv Python    : ${PY} ($(${PY} --version 2>&1))"
}

ensure_venv   # sets PY

# ══════════════════════════════════════════════════════════════════
#  STEP 3 – Helper: upgrade pip inside the venv (silent)
# ══════════════════════════════════════════════════════════════════
upgrade_pip() {
    info "Upgrading pip inside venv..."
    "${PY}" -m pip install --quiet --upgrade pip
}

# ══════════════════════════════════════════════════════════════════
#  STEP 4 – Install Python dependencies into the venv
# ══════════════════════════════════════════════════════════════════
install_python_deps() {
    if [ ! -f "requirements.txt" ]; then
        warn "requirements.txt not found – skipping pip install."
        return
    fi

    # Check if deps look already installed (Flask is a reliable proxy)
    if "${PY}" -c "import flask" 2>/dev/null; then
        info "Python deps already installed in venv – skipping."
        return
    fi

    upgrade_pip
    info "Installing Python dependencies into venv..."
    "${PY}" -m pip install --quiet -r requirements.txt
    success "Python dependencies installed."
}

# ── Detect Node / npm ─────────────────────────────────────────────
detect_node() {
    if ! command -v node &>/dev/null; then
        warn "Node.js not found – React build steps will be skipped."
        return 1
    fi
    info "Node.js        : $(node --version)"
    return 0
}

# ── Install Node dependencies ─────────────────────────────────────
install_node_deps() {
    if [ ! -d "node_modules" ]; then
        info "Installing Node dependencies (first run)..."
        npm install --silent
        success "Node dependencies installed."
    else
        info "Node deps      : node_modules/ already present."
    fi
}

# ── Build React (Vite production build → static/react/) ──────────
build_react() {
    info "Building React frontend..."
    npm run build
    success "React build complete → static/react/"
}

# ── Load .env.local on top of .env (local overrides win) ──────────
load_local_env() {
    if [ -f ".env.local" ]; then
        info "Loading .env.local overrides..."
        while IFS= read -r line; do
            [[ "${line}" =~ ^[[:space:]]*# ]] && continue   # skip comments
            [[ -z "${line// }" ]]              && continue   # skip blank lines
            export "${line?}"
        done < .env.local
    else
        warn ".env.local not found – using .env only."
        warn "Tip: cp .env.local.example .env.local  to customise local settings."
    fi
}

# ── Force LOCAL mode (never let the app think it's running on Azure) ──
force_local_mode() {
    # Unsetting these makes app.py set _ON_AZURE=False:
    #   → template auto-reload enabled
    #   → SESSION_COOKIE_SECURE = False  (works over plain http://)
    #   → local error handler active
    unset WEBSITE_HOSTNAME            2>/dev/null || true
    unset WEBSITE_INSTANCE_ID         2>/dev/null || true
    unset WEBSITE_SITE_NAME           2>/dev/null || true
    unset APPSETTING_WEBSITE_SITE_NAME 2>/dev/null || true

    export FLASK_ENV=development
    export FLASK_DEBUG=1

    # Required for OAuth (Google/Facebook) to work over plain http://127.0.0.1
    export OAUTHLIB_INSECURE_TRANSPORT=1

    # Skip heavy Playwright/Chromium download on first local run.
    # Remove this line if you need PDF export to work locally.
    export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
}

# ── Cleanup background processes on exit ──────────────────────────
_PIDS=()
cleanup() {
    if [ ${#_PIDS[@]} -gt 0 ]; then
        info "Shutting down background processes..."
        for pid in "${_PIDS[@]}"; do
            kill "${pid}" 2>/dev/null || true
        done
    fi
}
trap cleanup EXIT INT TERM

# ══════════════════════════════════════════════════════════════════
#  INSTALL mode  –  set up venv + pip + npm, then exit
# ══════════════════════════════════════════════════════════════════
if [ "${MODE}" = "install" ]; then
    echo ""
    echo -e "${BOLD}══════════════════════════════════════${RESET}"
    echo -e "${BOLD}  ResumaticAI  –  Install dependencies${RESET}"
    echo -e "${BOLD}══════════════════════════════════════${RESET}"
    echo ""
    upgrade_pip
    install_python_deps
    if detect_node; then install_node_deps; fi
    echo ""
    success "All dependencies installed."
    success "Virtual env is at: ${VENV_DIR}"
    echo ""
    echo -e "  Next step: ${BOLD}./run_local.sh${RESET}  to start the local server."
    exit 0
fi

# ══════════════════════════════════════════════════════════════════
#  Shared startup for all run modes
# ══════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}══════════════════════════════════════════${RESET}"
echo -e "${BOLD}  ResumaticAI  –  Local Preview${RESET}  [mode: ${CYAN}${MODE}${RESET}]"
echo -e "${BOLD}══════════════════════════════════════════${RESET}"
echo ""

load_local_env
force_local_mode

# Always ensure Python deps are installed before any run mode
install_python_deps

# ══════════════════════════════════════════════════════════════════
#  PREVIEW mode  (default)
#  Build React with Vite → serve everything via Flask
#  Closest local experience to the live production site.
# ══════════════════════════════════════════════════════════════════
if [ "${MODE}" = "preview" ]; then
    if detect_node; then
        install_node_deps
        build_react
    else
        warn "Skipping React build (Node.js not found)."
        if [ ! -f "static/react/index.html" ]; then
            error "No React build found at static/react/index.html."
            error "Install Node.js 18+ to build the frontend, or run: ./run_local.sh flask"
            exit 1
        fi
        warn "Using existing React build in static/react/."
    fi

    echo ""
    success "Starting Flask → http://127.0.0.1:${FLASK_PORT}"
    echo -e "  ${BOLD}Open http://127.0.0.1:${FLASK_PORT} in your browser${RESET}"
    echo -e "  Press Ctrl+C to stop."
    echo ""
    exec "${PY}" -m flask run --host=127.0.0.1 --port="${FLASK_PORT}" --debug

# ══════════════════════════════════════════════════════════════════
#  DEV mode
#  Flask + Vite dev server in parallel (hot-reload on every save)
#  Best for active frontend development.
# ══════════════════════════════════════════════════════════════════
elif [ "${MODE}" = "dev" ]; then
    if ! detect_node; then
        error "Node.js is required for dev mode."
        error "Install Node.js 18+ or use: ./run_local.sh flask"
        exit 1
    fi
    install_node_deps

    info "Starting Vite dev server on port ${VITE_PORT}..."
    VITE_DEV_BACKEND_URL="http://127.0.0.1:${FLASK_PORT}" npm run dev -- --port "${VITE_PORT}" &
    _PIDS+=($!)
    success "Vite started (pid=${_PIDS[-1]})"

    sleep 1   # let Vite boot before Flask

    echo ""
    success "Starting Flask → http://127.0.0.1:${FLASK_PORT}"
    echo -e "  ${BOLD}Flask (full app) : http://127.0.0.1:${FLASK_PORT}${RESET}"
    echo -e "  ${BOLD}Vite  (React SPA): http://127.0.0.1:${VITE_PORT}${RESET}"
    echo -e "  Press Ctrl+C to stop both."
    echo ""
    exec "${PY}" -m flask run --host=127.0.0.1 --port="${FLASK_PORT}" --debug

# ══════════════════════════════════════════════════════════════════
#  FLASK mode
#  Flask only – uses whatever React build is already in static/react/
# ══════════════════════════════════════════════════════════════════
elif [ "${MODE}" = "flask" ]; then
    if [ ! -f "static/react/index.html" ]; then
        warn "No React build found – React SPA routes will 404."
        warn "Run './run_local.sh preview' to build the frontend first."
    fi

    echo ""
    success "Starting Flask → http://127.0.0.1:${FLASK_PORT}"
    echo -e "  ${BOLD}Open http://127.0.0.1:${FLASK_PORT} in your browser${RESET}"
    echo -e "  Press Ctrl+C to stop."
    echo ""
    exec "${PY}" -m flask run --host=127.0.0.1 --port="${FLASK_PORT}" --debug

else
    error "Unknown mode: '${MODE}'"
    echo ""
    echo "Usage: ./run_local.sh [preview|dev|flask|install]"
    echo ""
    echo "  preview  (default) – build React, then serve via Flask on :${FLASK_PORT}"
    echo "  dev                – Flask + Vite hot-reload in parallel"
    echo "  flask              – Flask only (reuse existing React build)"
    echo "  install            – create venv, install Python + Node deps only"
    exit 1
fi
