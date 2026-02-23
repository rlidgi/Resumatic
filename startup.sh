#!/usr/bin/env bash
set -u

# Azure App Service (Linux) deploys the Playwright Python package via pip,
# but does NOT automatically download browser binaries. We install Chromium
# at startup into persistent /home storage.
#
# IMPORTANT: This script must NEVER prevent the web server from starting.
# If Playwright install fails (network/transient), we still start Gunicorn;
# PDF downloads will return a helpful error until install succeeds.

cd /home/site/wwwroot

# Persist browsers across restarts (App Service storage is mounted at /home).
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/home/site/wwwroot/ms-playwright}"
echo "Using PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH}"

# Azure provides PORT or WEBSITES_PORT.
export PORT="${PORT:-${WEBSITES_PORT:-8000}}"

echo "Kicking off Playwright Chromium install (non-blocking)..."
# Do NOT block app startup on browser downloads; Azure health probes can time out.
# Install in the background and log to a file under /home so it persists.
(
  echo "[playwright] install start $(date -Is)"
  python -m playwright install chromium
  echo "[playwright] install done $(date -Is)"
) >> /home/site/wwwroot/playwright-install.log 2>&1 &

exec gunicorn --bind "0.0.0.0:${PORT}" \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile "-" \
  --error-logfile "-" \
  app:app
