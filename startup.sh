#!/usr/bin/env bash
set -u
set -o pipefail

# Azure App Service (Linux) deploys the Playwright Python package via pip,
# but does NOT automatically download browser binaries. We install Chromium
# at startup into persistent /home storage.
#
# IMPORTANT: This script must NEVER prevent the web server from starting.
# If Playwright install fails (network/transient), we still start Gunicorn;
# PDF downloads will return a helpful error until install succeeds.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Oryx often extracts the app to a temp APP_PATH like /tmp/<id>.
# Prefer that if present; otherwise run from the script directory.
_APP_ROOT="${APP_PATH:-${SCRIPT_DIR}}"
cd "${_APP_ROOT}" || { echo "startup.sh ERROR: cannot cd to ${_APP_ROOT}"; exit 1; }
ROOT_DIR="$(pwd)"
echo "startup.sh root_dir=${ROOT_DIR} script_dir=${SCRIPT_DIR} app_path=${APP_PATH:-}"

# Find the project's app.py (avoid picking up flask's site-packages app.py).
APP_PY="$(
  find . -maxdepth 6 \
    \( -path './antenv' -o -path './.python_packages' -o -path './__pycache__' -o -path './node_modules' \) -prune -o \
    -name 'app.py' -print -quit
)"
echo "APP_PY=${APP_PY}"
if [ -z "${APP_PY}" ]; then
  echo "ERROR: project app.py not found under ${ROOT_DIR}"
  echo "Top-level files:"
  find . -maxdepth 2 -type f -print | head -200 || true
  # Don't crash-loop forever; exit so logs show the issue clearly.
  exit 1
fi

APP_DIR="$(dirname "${APP_PY}")"
echo "APP_DIR=${APP_DIR}"
cd "${APP_DIR}" || exit 1
echo "startup.sh app_cwd=$(pwd)"

# Prefer the deployed virtualenv python if present (Oryx typically creates ./antenv).
PY="${ROOT_DIR}/antenv/bin/python"
if [ ! -x "${PY}" ]; then
  PY="python3"
  if ! command -v python3 >/dev/null 2>&1; then
    PY="python"
  fi
  echo "startup.sh using system python: ${PY}"
fi

echo "PY=${PY}"
${PY} -V || true

# Persist browsers across restarts (App Service storage is mounted at /home).
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/home/site/wwwroot/ms-playwright}"
mkdir -p "${PLAYWRIGHT_BROWSERS_PATH}" || true
echo "Using PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH}"

# Azure provides PORT or WEBSITES_PORT.
export PORT="${PORT:-${WEBSITES_PORT:-8000}}"

# Memory is tight on smaller App Service plans; prefer fewer workers by default on Azure.
if [ -n "${WEBSITE_INSTANCE_ID:-}" ] || [ -n "${WEBSITE_HOSTNAME:-}" ]; then
  : "${GUNICORN_WORKERS:=1}"
  : "${GUNICORN_THREADS:=4}"
  : "${GUNICORN_TIMEOUT:=120}"
fi

echo "Kicking off Playwright Chromium install (non-blocking)..."
# Do NOT block app startup on browser downloads; Azure health probes can time out.
# Install in the background and log to a file under /home so it persists.
# (Some App Service images don't reliably stream background pipeline output.)
PW_LOG="/home/site/wwwroot/playwright-install.log"
echo "[playwright] preflight euid=$(id -u 2>/dev/null || echo '?') apt_get=$(command -v apt-get 2>/dev/null || echo 'no') sudo=$(command -v sudo 2>/dev/null || echo 'no')"
(
  MARKER_CHROMIUM="/home/site/wwwroot/.playwright_chromium_installed"

  # Install OS dependencies required by Chromium/Playwright.
  # App Service images can be missing libs like libglib-2.0.so.0.
  # IMPORTANT: /home persists, but apt-installed system libs do NOT. So we must probe
  # for required libraries instead of relying on a marker file.
  NEED_DEPS="0"
  if command -v "${PY}" >/dev/null 2>&1; then
    "${PY}" - <<'PY'
import ctypes, sys
libs = [
  "libglib-2.0.so.0",
  "libnss3.so",
  "libatk-1.0.so.0",
  "libatk-bridge-2.0.so.0",
  "libatspi.so.0",
  "libgtk-3.so.0",
  "libX11-xcb.so.1",
  "libXcomposite.so.1",
  "libXdamage.so.1",
  "libXfixes.so.3",
  "libXrandr.so.2",
  "libxkbcommon.so.0",
  "libgbm.so.1",
  "libdrm.so.2",
  "libasound.so.2",
  "libpango-1.0.so.0",
  "libpangocairo-1.0.so.0",
  "libcups.so.2",
]
missing = []
for lib in libs:
  try:
    ctypes.CDLL(lib)
  except Exception:
    missing.append(lib)
if missing:
  sys.stderr.write("MISSING_LIBS=" + ",".join(missing) + "\n")
  sys.exit(42)
print("MISSING_LIBS=")
PY
    rc=$?
    if [ "${rc}" = "42" ]; then NEED_DEPS="1"; fi
  else
    NEED_DEPS="1"
  fi

  if [ "${NEED_DEPS}" = "1" ]; then
    echo "[playwright] deps missing -> installing via apt-get start $(date -Is)"
    if command -v apt-get >/dev/null 2>&1; then
      SUDO=""
      if command -v sudo >/dev/null 2>&1 && [ "$(id -u)" != "0" ]; then
        SUDO="sudo"
      fi
      export DEBIAN_FRONTEND=noninteractive
      # Network to deb.debian.org can be flaky in App Service containers.
      # Use retries/timeouts and try multiple attempts before giving up.
      APT_OPTS=(
        "-o" "Acquire::Retries=5"
        "-o" "Acquire::http::Timeout=30"
        "-o" "Acquire::https::Timeout=30"
        "-o" "Acquire::http::Pipeline-Depth=0"
      )

      for attempt in 1 2 3; do
        echo "[playwright] apt attempt=${attempt} update $(date -Is)"
        $SUDO apt-get "${APT_OPTS[@]}" update -y && break || true
        sleep 2 || true
      done

      for attempt in 1 2 3; do
        echo "[playwright] apt attempt=${attempt} install $(date -Is)"
        $SUDO apt-get "${APT_OPTS[@]}" install -y --no-install-recommends --fix-missing \
          libglib2.0-0 \
          libnss3 \
          libatk-bridge2.0-0 \
          libatk1.0-0 \
          libatspi2.0-0 \
          libgtk-3-0 \
          libx11-xcb1 \
          libxcomposite1 \
          libxdamage1 \
          libxfixes3 \
          libxrandr2 \
          libxkbcommon0 \
          libgbm1 \
          libdrm2 \
          libasound2 \
          libpangocairo-1.0-0 \
          libpango-1.0-0 \
          libcups2 \
          fonts-liberation \
          ca-certificates \
          && break || true
        # If partial downloads occurred, fix broken deps and retry.
        $SUDO apt-get -f install -y || true
        sleep 2 || true
      done
    else
      echo "[playwright] apt-get not available; cannot install OS deps"
    fi
    echo "[playwright] deps install done $(date -Is)"
  else
    echo "[playwright] deps already present; skipping apt-get"
  fi

  if [ -f "${MARKER_CHROMIUM}" ]; then
    echo "[playwright] chromium already installed marker=${MARKER_CHROMIUM}"
  else
    # If the chromium folder already exists, don't redownload.
    if ls -d "${PLAYWRIGHT_BROWSERS_PATH}"/chromium-* >/dev/null 2>&1 || ls -d "${PLAYWRIGHT_BROWSERS_PATH}"/chromium_headless_shell-* >/dev/null 2>&1; then
      echo "[playwright] chromium appears present under ${PLAYWRIGHT_BROWSERS_PATH}; skipping download"
      touch "${MARKER_CHROMIUM}" || true
    else
      echo "[playwright] install start $(date -Is)"
      ${PY} -m playwright install chromium
      echo "[playwright] install done $(date -Is)"
      touch "${MARKER_CHROMIUM}" || true
    fi
  fi
) >> "${PW_LOG}" 2>&1 &
echo "[playwright] background pid=$! log=${PW_LOG}"

exec ${PY} -m gunicorn --bind "0.0.0.0:${PORT}" \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile "-" \
  --error-logfile "-" \
  app:app
