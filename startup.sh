#!/bin/bash
set -e

cd /home/site/wwwroot

# Azure App Service typically provides a port via PORT or WEBSITES_PORT.
PORT="${PORT:-${WEBSITES_PORT:-8000}}"

# Run behind a production WSGI server.
# app.py exposes the Flask app instance as `app`.
exec gunicorn \
	--bind "0.0.0.0:${PORT}" \
	--workers "${GUNICORN_WORKERS:-2}" \
	--threads "${GUNICORN_THREADS:-4}" \
	--timeout "${GUNICORN_TIMEOUT:-120}" \
	app:app
