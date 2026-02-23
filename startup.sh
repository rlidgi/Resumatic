#!/bin/bash
set -e

# Oryx/run-from-package often extracts the app to a temp folder (e.g. /tmp/...).
# Use the directory of this script as the app root so startup works regardless
# of where the code is mounted/extracted.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[startup] script_dir=$SCRIPT_DIR"
echo "[startup] pwd=$(pwd)"
echo "[startup] listing:"; ls -la
echo "[startup] python=$(command -v python || true)"; python --version || true
echo "[startup] gunicorn=$(command -v gunicorn || true)"; gunicorn --version || true

# Azure App Service typically provides a port via PORT or WEBSITES_PORT.
PORT="${PORT:-${WEBSITES_PORT:-8000}}"
echo "[startup] PORT=$PORT WEBSITES_PORT=${WEBSITES_PORT:-}"

# Run behind a production WSGI server.
# app.py exposes the Flask app instance as `app`.
exec gunicorn \
	--bind "0.0.0.0:${PORT}" \
	--workers "${GUNICORN_WORKERS:-2}" \
	--threads "${GUNICORN_THREADS:-4}" \
	--timeout "${GUNICORN_TIMEOUT:-120}" \
	app:app
