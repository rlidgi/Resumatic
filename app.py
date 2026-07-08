from flask import (
    Flask, request, render_template, redirect, url_for, session, flash,
    send_file, send_from_directory,
    jsonify, Response, make_response, abort, has_request_context,
)
from jinja2 import TemplateNotFound
from io import BytesIO
import PyPDF2
import pdfplumber
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
import mammoth
import logging
import os


# Configure CA bundle before google-auth/requests import urllib3 (local Windows dev).
def _bootstrap_https_certificates() -> None:
    if os.getenv('WEBSITE_HOSTNAME') or os.getenv('WEBSITE_INSTANCE_ID'):
        return
    if os.name != 'nt':
        return
    try:
        # truststore needs platform.system(); on Windows that probes WMI and can hang for minutes.
        import platform

        platform.system = lambda: 'Windows'  # type: ignore[method-assign]
        platform.win32_ver = lambda *args, **kwargs: ('10', '10.0', '',
                                                      'Multiprocessor Free')  # type: ignore[method-assign]
        import truststore

        truststore.inject_into_ssl()
        return
    except Exception:
        pass
    try:
        import certifi

        ca_bundle = certifi.where()
        os.environ.setdefault('SSL_CERT_FILE', ca_bundle)
        os.environ.setdefault('REQUESTS_CA_BUNDLE', ca_bundle)
        os.environ.setdefault('CURL_CA_BUNDLE', ca_bundle)
    except Exception:
        pass


_bootstrap_https_certificates()


def _ensure_local_truststore_ssl() -> None:
    """Re-apply Windows trust-store SSL before outbound OAuth HTTPS calls."""
    if os.getenv('WEBSITE_HOSTNAME') or os.getenv('WEBSITE_INSTANCE_ID'):
        return
    if os.name != 'nt':
        return
    try:
        import platform

        platform.system = lambda: 'Windows'  # type: ignore[method-assign]
        platform.win32_ver = lambda *args, **kwargs: ('10', '10.0', '',
                                                      'Multiprocessor Free')  # type: ignore[method-assign]
        import truststore

        truststore.inject_into_ssl()
    except Exception:
        pass


import time
import ipaddress
import re
import threading
import atexit
import threading
import atexit

# Import newsletter system
from email_audit import read_email_events, record_email_event
from newsletter import NewsletterManager, NewsletterConfig

try:
    from analytics import analytics
except Exception as _analytics_import_error:
    class _NoopAnalytics:
        def track_visit(self, request_obj):
            return {"type": "organic", "source": "fallback",
                    "error": str(_analytics_import_error)}

        def track_conversion(
                self,
                session_data,
                conversion_type="resume_submission"
        ):
            return {"status": "skipped", "reason": "analytics_unavailable",
                    "type": conversion_type}

        def get_full_analytics(self):
            return {
                "summary": {
                    "total_visits": 0,
                    "facebook_ad_visits": 0,
                    "organic_visits": 0,
                    "total_conversions": 0,
                    "facebook_ad_conversions": 0,
                    "last_updated": ""
                },
                "daily_stats": {},
                "utm_campaigns": {},
                "referrer_data": {},
                "facebook_stats": {}
            }


    analytics = _NoopAnalytics()

from google_auth_oauthlib.flow import Flow
import google.auth
import google.auth.transport.requests
import google.oauth2.credentials
import google.oauth2.id_token
from google.oauth2 import service_account

from flask_dance.contrib.facebook import make_facebook_blueprint, facebook
from flask_login import (
    LoginManager, login_required, login_user,
    logout_user, UserMixin, current_user,
)
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None  # type: ignore
import calendar
import openai
import os
import json
import secrets
import copy
import html as html_stdlib
import requests
from docx import Document
import stripe
import csv
from azure.data.tables import TableServiceClient, UpdateMode
from urllib.parse import urlparse, urljoin
from urllib.parse import urlencode
from flask_session import Session
import re

# Lightweight TTL-backed JSON storage for SPA-like drafts
from temp_store import (
    save_payload, load_payload, delete_payload,
    DEFAULT_TTL_SECONDS,
)

# One-shot resume payloads for server-side PDF generation (Playwright loads /template-download with ?pdf_snapshot=…).
# Stored on disk (next to Flask filesystem sessions) so Gunicorn/uWSGI multi-worker pools can all read the same snapshot.
_pdf_snapshot_lock = threading.Lock()
_PDF_SNAPSHOT_TTL_S = 180.0


def _pdf_snapshot_dir() -> str:
    home_dir = (os.getenv("HOME") or "").strip()
    if home_dir:
        base = os.path.join(
            home_dir,
            "site",
            "wwwroot",
            ".flask_session",
            "pdf_snapshots"
        )
    else:
        base = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            ".flask_session",
            "pdf_snapshots"
        )
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return base


def _pdf_snapshot_sanitize_tok(tok: str) -> Optional[str]:
    t = str(tok or "").strip()
    if not t or len(t) > 200:
        return None
    for ch in t:
        if ch.isalnum() or ch in "-_":
            continue
        return None
    return t


def _pdf_snapshot_store_put(
        resume: dict,
        user_id: int,
        template_hint: Optional[str] = None
) -> str:
    tok = secrets.token_urlsafe(32)
    safe = _pdf_snapshot_sanitize_tok(tok)
    if not safe:
        raise RuntimeError("invalid snapshot token")
    payload = {
        "resume": copy.deepcopy(resume),
        "uid": int(user_id),
        "t": time.time(),
        "template_hint": str(template_hint or "").strip(),
    }
    path = os.path.join(_pdf_snapshot_dir(), f"{safe}.json")
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with _pdf_snapshot_lock:
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            os.replace(tmp, path)
        except Exception:
            try:
                if os.path.isfile(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            raise
    return tok


def _pdf_snapshot_store_get(tok: str) -> Optional[dict[str, Any]]:
    safe = _pdf_snapshot_sanitize_tok(tok)
    if not safe:
        return None
    path = os.path.join(_pdf_snapshot_dir(), f"{safe}.json")
    with _pdf_snapshot_lock:
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                ent = json.load(f)
        except Exception:
            return None
    if not isinstance(ent, dict):
        return None
    try:
        if time.time() - float(ent.get("t") or 0.0) > _PDF_SNAPSHOT_TTL_S:
            _pdf_snapshot_store_pop(tok)
            return None
    except Exception:
        return None
    return ent


def _pdf_snapshot_store_pop(tok: str) -> None:
    safe = _pdf_snapshot_sanitize_tok(str(tok or "").strip())
    if not safe:
        return
    path = os.path.join(_pdf_snapshot_dir(), f"{safe}.json")
    with _pdf_snapshot_lock:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except Exception:
            pass

try:
    print(f"DEBUG: Files in current app directory: {os.listdir('.')}")
    if os.path.exists('templates'):
        print(f"DEBUG: Files in templates folder: {os.listdir('templates')}")
    else:
        print("DEBUG: Templates folder NOT found in the app directory!")
except Exception as e:
    print(f"DEBUG: Error checking files: {e}")


# This line gets the absolute path of the directory containing app.py
# (which is /home/site/wwwroot/extracted/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# This creates the path: /home/site/wwwroot/extracted/templates/
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
# Initialize Flask with the dynamic path
# app = Flask(__name__, template_folder=TEMPLATE_DIR)
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)

# App Service runs behind a reverse proxy. Trust standard forwarding headers so
# Flask sees the correct scheme/host (important for redirects and health probes).
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_port=1
)

# React SPA shell (built by Vite into static/react)
_REACT_INDEX_REL_PATH = os.path.join("static", "react", "index.html")
_REACT_SPA_INFO_CACHE = {
    "mtime": None,
    "entry_js": "",
    "entry_css": "",
}


def _get_react_spa_shell_info():
    """Return (index_abs_path, entry_js_filename, entry_css_filename, index_mtime_int).

    Cached by index.html mtime to avoid re-reading/parsing on every request.
    """

    index_abs = os.path.join(app.root_path, _REACT_INDEX_REL_PATH)
    try:
        mtime = os.path.getmtime(index_abs)
    except Exception:
        return index_abs, "", "", 0

    if _REACT_SPA_INFO_CACHE["mtime"] != mtime:
        try:
            with open(
                    index_abs,
                    "r",
                    encoding="utf-8",
                    errors="ignore"
            ) as f:
                html = f.read()

            js_match = re.search(
                r"/static/react/assets/([^\"\s]+\.js)",
                html
            )
            css_match = re.search(
                r"/static/react/assets/([^\"\s]+\.css)",
                html
            )

            _REACT_SPA_INFO_CACHE["mtime"] = mtime
            _REACT_SPA_INFO_CACHE["entry_js"] = js_match.group(
                1
            ) if js_match else ""
            _REACT_SPA_INFO_CACHE["entry_css"] = css_match.group(
                1
            ) if css_match else ""
        except Exception:
            _REACT_SPA_INFO_CACHE["mtime"] = mtime
            _REACT_SPA_INFO_CACHE["entry_js"] = ""
            _REACT_SPA_INFO_CACHE["entry_css"] = ""

    return (
        index_abs,
        _REACT_SPA_INFO_CACHE["entry_js"],
        _REACT_SPA_INFO_CACHE["entry_css"],
        int(mtime),
    )


@app.route("/react")
@app.route("/react/<path:subpath>")
def react_app(subpath=None):
    index_abs, entry_js, entry_css, index_mtime = _get_react_spa_shell_info()
    resp = send_file(index_abs)

    # Ensure the SPA shell isn't cached (it points at hashed JS/CSS assets).
    resp.headers[
        "Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"

    # Debug headers to confirm exactly which Vite build is being served.
    # Safe to expose: contains only static asset filenames + file mtime.
    if entry_js:
        resp.headers["X-React-Asset-JS"] = entry_js
    if entry_css:
        resp.headers["X-React-Asset-CSS"] = entry_css
    if index_mtime:
        resp.headers["X-React-Index-MTime"] = str(index_mtime)

    # Optional: include the app build id if present.
    try:
        resp.headers["X-Resumatic-Build"] = str(_BUILD_ID)
    except Exception:
        pass

    return resp


@app.route("/create-resume")
@app.route("/create-resume/")
@app.route("/create-resume/<path:subpath>")
@app.route("/create-resume-builder")
@app.route("/create-resume-builder/")
@app.route("/create-resume-builder/<path:subpath>")
def imported_resume_builder(subpath=None):
    """Serve the imported standalone resume-builder as the primary /create-resume experience."""
    builder_root = os.path.join(app.root_path, "static", "resume-builder")

    if not subpath:
        return send_from_directory(builder_root, "index.html")

    requested = os.path.normpath(str(subpath)).replace("\\", "/").lstrip(
        "/"
    )
    if requested.startswith(".."):
        abort(404)

    file_abs = os.path.join(builder_root, requested)
    if os.path.isfile(file_abs):
        return send_from_directory(builder_root, requested)

    abort(404)


#####################
# ---- Make `current_user` available in all Jinja templates ----
try:
    from flask_login import (
        LoginManager,
        current_user as flask_login_current_user, AnonymousUserMixin,
    )

    login_manager = LoginManager()
    login_manager.init_app(app)


    @app.context_processor
    def inject_current_user():
        # This exposes the real Flask-Login current_user to Jinja
        return dict(current_user=flask_login_current_user)

except Exception:
    # Flask-Login not installed/configured: provide a safe dummy
    class _Anon:
        is_authenticated = False


    @app.context_processor
    def inject_current_user():
        return dict(current_user=_Anon())

################################
# 1. Only load local files if we are NOT running on Azure
if not os.getenv('WEBSITE_INSTANCE_ID'):
    load_dotenv()
    # .env.local overrides .env when present locally
    load_dotenv(".env.local", override=True)

# 2. Azure App Settings are now safe from being overwritten
stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Local debugging aid (Windows-safe): write exception traces to a file next to app.py.
# This avoids rare Windows console/stderr write errors that can mask the real exception.
try:
    _LOCAL_ERRORS_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'local_errors.log'
    )
except Exception:
    _LOCAL_ERRORS_PATH = 'local_errors.log'

# Create the file early so it's easy to locate during debugging.
try:
    with open(
            _LOCAL_ERRORS_PATH,
            'a',
            encoding='utf-8',
            errors='backslashreplace'
    ) as _f:
        from datetime import datetime

        _f.write(
            f"\n[{datetime.now(timezone.utc).isoformat()}] local_errors.log initialized\n"
        )
except Exception:
    pass


def _safe_log_exception(
        context: str,
        exc: Exception | None = None
) -> None:
    """Log exceptions without risking console write failures on Windows."""
    try:
        # logger.exception() captures the active exception traceback when called in an except block.
        if exc is not None:
            logger.exception('%s: %s', context, exc)
        else:
            logger.exception('%s', context)
    except Exception:
        pass

    try:
        from datetime import datetime

        import traceback

        with open(
                _LOCAL_ERRORS_PATH,
                'a',
                encoding='utf-8',
                errors='backslashreplace'
        ) as f:
            f.write(f"\n[{datetime.utcnow().isoformat()}Z] {context}\n")
            if exc is not None:
                f.write(f"{type(exc).__name__}: {exc}\n")
                tb = ''.join(
                    traceback.format_exception(
                        type(exc),
                        exc,
                        exc.__traceback__
                    )
                )
                f.write(tb)
            else:
                f.write(traceback.format_exc())
            f.write("\n")
    except Exception:
        # Never allow error-reporting to crash the request.
        pass


def _safe_log_event(message: str) -> None:
    """Append a diagnostic breadcrumb to local_errors.log (never raises)."""
    try:
        from datetime import datetime

        with open(
                _LOCAL_ERRORS_PATH,
                'a',
                encoding='utf-8',
                errors='backslashreplace'
        ) as f:
            f.write(f"[{datetime.utcnow().isoformat()}Z] {message}\n")
    except Exception:
        pass


def _safe_print(*args, **kwargs) -> None:
    """Best-effort print that never raises (avoids Windows console write crashes)."""
    try:
        print(*args, **kwargs)
    except Exception:
        pass


load_dotenv()
app.config['SECRET_KEY'] = os.getenv(
    'FLASK_SECRET_KEY'
) or 'a-very-secret-random-key'


# Local Windows Python often lacks a usable CA bundle for requests/google-auth HTTPS calls.
def _configure_local_ssl_cert_bundle() -> None:
    if bool(
            os.getenv('WEBSITE_HOSTNAME') or os.getenv(
                'WEBSITE_INSTANCE_ID'
            )
    ):
        return
    if os.name == 'nt':
        logger.info(
            'Using Windows trust store for local HTTPS (truststore)'
        )
        return
    for mod_name in ('truststore', 'pip._vendor.truststore'):
        try:
            mod = __import__(mod_name, fromlist=['inject_into_ssl'])
            mod.inject_into_ssl()
            logger.info('Using OS trust store for HTTPS via %s', mod_name)
            return
        except Exception:
            continue
    try:
        import certifi

        ca_bundle = certifi.where()
        os.environ.setdefault('SSL_CERT_FILE', ca_bundle)
        os.environ.setdefault('REQUESTS_CA_BUNDLE', ca_bundle)
    except Exception:
        pass


_configure_local_ssl_cert_bundle()

# Local-dev ergonomics: auto-reload templates/static caching unless running on Azure App Service.
_ON_AZURE = bool(
    os.getenv('WEBSITE_HOSTNAME') or os.getenv('WEBSITE_INSTANCE_ID')
)

# Local-only: capture any unhandled exceptions into local_errors.log.
# This is intentionally conservative to avoid changing production behavior.
if (not _ON_AZURE) and (os.name == 'nt'):
    try:
        from werkzeug.exceptions import HTTPException


        @app.errorhandler(Exception)
        def _log_unhandled_exception(e):
            if isinstance(e, HTTPException):
                # Don't spam local_errors.log with normal 4xxs (missing static files, bad URLs, etc.).
                code = getattr(e, 'code', None)
                if isinstance(code, int) and code >= 500:
                    _safe_log_exception('unhandled http exception', e)
                return e

            _safe_log_exception('unhandled exception', e)
            return "Internal Server Error", 500
    except Exception:
        pass

# Startup banner (helps confirm which process/code is actually running).
try:
    _BUILD_ID = str(int(os.path.getmtime(__file__)))
except Exception:
    _BUILD_ID = 'unknown'
logger.info(
    'ResumaticAI boot (build=%s pid=%s on_azure=%s)',
    _BUILD_ID,
    os.getpid(),
    _ON_AZURE
)

# ---- Playwright browser reuse (per-worker) ----
# Launching Chromium is expensive; reuse a single browser per Gunicorn worker for PDF generation.
_PDF_BROWSER_LOCK = threading.Lock()
_PDF_PW = None
_PDF_BROWSER = None

# ---- Playwright browser reuse (per-thread) ----
# Playwright's sync API is thread-affine; using the same browser object across threads can raise
# "Cannot switch to a different thread". To keep reuse safe, maintain a browser per *thread*.
_PDF_THREAD_LOCAL = threading.local()
_PDF_THREAD_RESOURCES_LOCK = threading.Lock()
_PDF_THREAD_RESOURCES = []  # best-effort cleanup list: [{'pw': pw, 'browser': browser}]

# ---- Font embedding cache (module-wide) ----
_PDF_FONT_LOCK = threading.Lock()
_PDF_INTER_FONT_B64 = None
_PDF_FONTS_DIR = None


def _get_pdf_fonts_dir() -> str:
    """Return absolute path to static fonts directory (cached)."""
    global _PDF_FONTS_DIR
    if _PDF_FONTS_DIR:
        return _PDF_FONTS_DIR
    try:
        _static_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "static"
        )
        _PDF_FONTS_DIR = os.path.join(_static_dir, "fonts")
    except Exception:
        _PDF_FONTS_DIR = ""
    return _PDF_FONTS_DIR


def _get_inter_font_b64_cache() -> dict:
    """Lazy-load base64 versions of Inter woff2 fonts once per process."""
    global _PDF_INTER_FONT_B64
    if isinstance(_PDF_INTER_FONT_B64, dict):
        return _PDF_INTER_FONT_B64
    with _PDF_FONT_LOCK:
        if isinstance(_PDF_INTER_FONT_B64, dict):
            return _PDF_INTER_FONT_B64
        try:
            import base64

            fonts_dir = _get_pdf_fonts_dir()
            inter_dir = os.path.join(
                fonts_dir,
                "inter"
            ) if fonts_dir else ""
            cache = {}
            for name in (
                    "inter-latin-400-normal.woff2",
                    "inter-latin-500-normal.woff2",
                    "inter-latin-600-normal.woff2",
                    "inter-latin-700-normal.woff2",
            ):
                p = os.path.join(inter_dir, name)
                if os.path.isfile(p):
                    with open(p, "rb") as f:
                        cache[name] = base64.b64encode(f.read()).decode(
                            "ascii"
                        )
            _PDF_INTER_FONT_B64 = cache
        except Exception:
            _PDF_INTER_FONT_B64 = {}
        return _PDF_INTER_FONT_B64


def _get_pdf_browser_threadlocal(launch_kwargs: dict):
    """Return a reused Chromium browser instance bound to the current thread."""
    tl = _PDF_THREAD_LOCAL
    try:
        b = getattr(tl, "browser", None)
        if b is not None:
            is_connected = getattr(b, "is_connected", None)
            if callable(is_connected):
                if is_connected():
                    return b
            else:
                return b
    except Exception:
        try:
            tl.browser = None
        except Exception:
            pass

    from playwright.sync_api import sync_playwright

    try:
        pw = getattr(tl, "pw", None)
    except Exception:
        pw = None
    if pw is None:
        pw = sync_playwright().start()
        try:
            tl.pw = pw
        except Exception:
            pass

    browser = pw.chromium.launch(**launch_kwargs)
    try:
        tl.browser = browser
    except Exception:
        pass
    # Track for best-effort cleanup.
    try:
        with _PDF_THREAD_RESOURCES_LOCK:
            _PDF_THREAD_RESOURCES.append({"pw": pw, "browser": browser})
    except Exception:
        pass
    return browser


def _get_pdf_browser(launch_kwargs: dict):
    """Return a reused Chromium browser instance for this worker."""
    global _PDF_PW, _PDF_BROWSER
    with _PDF_BROWSER_LOCK:
        try:
            if _PDF_BROWSER is not None:
                is_connected = getattr(_PDF_BROWSER, "is_connected", None)
                if callable(is_connected):
                    if is_connected():
                        return _PDF_BROWSER
                else:
                    # Some implementations may not expose is_connected; assume ok.
                    return _PDF_BROWSER
        except Exception:
            _PDF_BROWSER = None

        from playwright.sync_api import sync_playwright

        if _PDF_PW is None:
            _PDF_PW = sync_playwright().start()
        _PDF_BROWSER = _PDF_PW.chromium.launch(**launch_kwargs)
        return _PDF_BROWSER


@atexit.register
def _close_pdf_browser():
    """Best-effort cleanup when the worker exits."""
    global _PDF_PW, _PDF_BROWSER
    try:
        if _PDF_BROWSER is not None:
            _PDF_BROWSER.close()
    except Exception:
        pass
    _PDF_BROWSER = None
    try:
        if _PDF_PW is not None:
            _PDF_PW.stop()
    except Exception:
        pass
    _PDF_PW = None

    # Best-effort cleanup for thread-local resources.
    try:
        with _PDF_THREAD_RESOURCES_LOCK:
            resources = list(_PDF_THREAD_RESOURCES)
            _PDF_THREAD_RESOURCES.clear()
    except Exception:
        resources = []
    for r in resources:
        try:
            b = r.get("browser")
            if b is not None:
                b.close()
        except Exception:
            pass
        try:
            pw = r.get("pw")
            if pw is not None:
                pw.stop()
        except Exception:
            pass


# Azure SDK HTTP logging can drown out app logs (especially in Azure Log Stream).
# Default to quiet; allow overriding via standard logging config if needed.
try:
    logging.getLogger(
        'azure.core.pipeline.policies.http_logging_policy'
    ).setLevel(logging.WARNING)
    logging.getLogger(
        'azure.monitor.opentelemetry.exporter.export._base'
    ).setLevel(logging.WARNING)
except Exception:
    pass

if not _ON_AZURE:
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    try:
        app.jinja_env.auto_reload = True
    except Exception:
        pass
    # Reduce stale static assets during local debugging
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


# Server-side sessions (prevents oversized cookie drops when storing large resume/feedback payloads).
def _apply_flask_session_cookie_defaults() -> None:
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = bool(_ON_AZURE)


def _should_use_filesystem_sessions() -> bool:
    force = str(
        os.getenv('FLASK_FILESYSTEM_SESSIONS', '') or ''
    ).strip().lower()
    if force in ('0', 'false', 'no', 'off'):
        return False
    if force in ('1', 'true', 'yes', 'on'):
        return True
    if _ON_AZURE:
        return True
    # FileSystemCache can block for minutes on Windows during WMI/platform probes.
    if os.name == 'nt':
        return False
    return True


try:
    _apply_flask_session_cookie_defaults()
    if _should_use_filesystem_sessions():
        home_dir = (os.getenv('HOME') or '').strip()
        if home_dir:
            session_dir = os.path.join(
                home_dir,
                'site',
                'wwwroot',
                '.flask_session'
            )
        else:
            session_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '.flask_session'
            )
        os.makedirs(session_dir, exist_ok=True)
        app.config['SESSION_TYPE'] = 'filesystem'
        app.config['SESSION_FILE_DIR'] = session_dir
        Session(app)
        logger.info('Filesystem sessions enabled (dir=%s)', session_dir)
    elif (not _ON_AZURE) and os.name == 'nt':
        # Signed cookie sessions: fast startup, OAuth state survives Google redirect + debug reloader.
        logger.info('Signed cookie sessions enabled for local Windows dev')
    else:
        raise RuntimeError('no session backend selected for this host')
except Exception as e:
    logger.warning(
        f"Server-side session setup failed; falling back to cookie sessions: {type(e).__name__}: {str(e)}"
    )


def _is_safe_next_url(target: str) -> bool:
    """Allow only same-host redirects (prefer relative paths) to avoid open redirects."""
    try:
        if not target:
            return False
        # Disallow scheme-relative URLs
        if target.startswith("//"):
            return False
        # Relative path is OK
        if target.startswith("/"):
            return True
        # Otherwise require same host
        ref_url = urlparse(request.host_url)
        test_url = urlparse(urljoin(request.host_url, target))
        return test_url.scheme in (
            "http", "https") and ref_url.netloc == test_url.netloc
    except Exception:
        return False


def _set_auth_next_from_request() -> None:
    """Capture ?next=... into session for use after login/oauth completes."""
    try:
        nxt = request.args.get("next", "").strip()
        if nxt and _is_safe_next_url(nxt):
            session["auth_next"] = nxt
    except Exception:
        pass


def _pop_auth_next() -> Optional[str]:
    """Pop a safe next URL from session, if any."""
    try:
        nxt = session.pop("auth_next", None)
        if nxt and _is_safe_next_url(nxt):
            return nxt
    except Exception:
        pass
    return None


# --- Marketing attribution (personalized links) ---
_MARKETING_SESSION_KEY = 'marketing_params'
_MARKETING_REF_PARAM = 'ref'
_MARKETING_UTM_KEYS = (
    'utm_source',
    'utm_medium',
    'utm_campaign',
    'utm_content',
    'utm_term',
)


def _sanitize_marketing_value(value: str, max_len: int = 160) -> str:
    try:
        s = str(value or '').strip()
        if not s:
            return ''
        if len(s) > max_len:
            s = s[:max_len]
        return s
    except Exception:
        return ''


def _sanitize_ref_code(code: str) -> str:
    """Allow only simple URL-safe referral codes."""
    try:
        raw = str(code or '').strip()
        if not raw:
            return ''
        raw = raw[:64]
        cleaned = re.sub(r'[^A-Za-z0-9_.-]+', '', raw)
        return cleaned
    except Exception:
        return ''


@app.before_request
def _capture_marketing_params():
    """Capture ref/UTM params into session so later signups can be attributed."""
    try:
        args = request.args
        if not args:
            return None

        existing = session.get(_MARKETING_SESSION_KEY, {})
        if not isinstance(existing, dict):
            existing = {}
        m = dict(existing)

        updated = False

        ref_code = _sanitize_ref_code(args.get(_MARKETING_REF_PARAM, ''))
        if ref_code:
            if m.get('ref') != ref_code:
                m['ref'] = ref_code
                updated = True

        for k in _MARKETING_UTM_KEYS:
            v = _sanitize_marketing_value(args.get(k, ''))
            if v:
                if m.get(k) != v:
                    m[k] = v
                    updated = True

        if updated:
            now = datetime.now(timezone.utc).isoformat()
            if not m.get('first_seen_at'):
                m['first_seen_at'] = now
                m['landing_path'] = str(request.path or '')
            m['last_seen_at'] = now
            session[_MARKETING_SESSION_KEY] = m
    except Exception:
        return None
    return None


def _append_marketing_signup_csv(user: 'User', signup_method: str) -> None:
    """Append a marketing attribution record on signup (best-effort)."""
    try:
        m = session.get(_MARKETING_SESSION_KEY, {})
        if not isinstance(m, dict):
            m = {}

        traffic = session.get('traffic_source', {})
        if not isinstance(traffic, dict):
            traffic = {}

        filename = os.getenv(
            'MARKETING_SIGNUPS_CSV',
            'marketing_signups.csv'
        )
        file_exists = os.path.exists(filename)
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(
                    [
                        'timestamp_iso',
                        'signup_method',
                        'user_id',
                        'email',
                        'ref',
                        'utm_source',
                        'utm_medium',
                        'utm_campaign',
                        'utm_content',
                        'utm_term',
                        'traffic_type',
                        'traffic_campaign',
                        'traffic_referrer',
                        'first_seen_at',
                        'last_seen_at',
                        'landing_path',
                    ]
                )

            writer.writerow(
                [
                    datetime.now(timezone.utc).isoformat(),
                    str(signup_method or '').strip(),
                    str(getattr(user, 'id', '') or ''),
                    _normalize_email(getattr(user, 'email', '')),
                    str(m.get('ref') or ''),
                    str(m.get('utm_source') or ''),
                    str(m.get('utm_medium') or ''),
                    str(m.get('utm_campaign') or ''),
                    str(m.get('utm_content') or ''),
                    str(m.get('utm_term') or ''),
                    str(traffic.get('type') or ''),
                    str(traffic.get('campaign') or ''),
                    str(traffic.get('referrer') or ''),
                    str(m.get('first_seen_at') or ''),
                    str(m.get('last_seen_at') or ''),
                    str(m.get('landing_path') or ''),
                ]
            )
    except Exception:
        logger.exception('Failed to append marketing signup CSV')


@app.route('/r/<code>')
def referral_redirect(code: str):
    """Short personalized link: /r/yaron -> /?ref=yaron (+ any utm_* passthrough)."""
    try:
        ref_code = _sanitize_ref_code(code)
        params = {}
        if ref_code:
            params['ref'] = ref_code
        for k in _MARKETING_UTM_KEYS:
            v = _sanitize_marketing_value(request.args.get(k, ''))
            if v:
                params[k] = v

        base = url_for('index')
        if params:
            return redirect(f"{base}?{urlencode(params)}", code=302)
        return redirect(base, code=302)
    except Exception:
        return redirect(url_for('index'), code=302)


# Ensure HTTPS URLs in sitemap and external links
app.config['PREFERRED_URL_SCHEME'] = 'https'

# File upload configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'temp_uploads'

# Create upload folder if it doesn't exist
import os

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


def _append_google_signup_csv(
        user_id: str,
        name: str,
        email: str,
        created_at_iso: str
) -> None:
    """Append a record of a new Google signup to google_signups.csv.

    Columns: timestamp_iso, user_id, name, email
    """
    try:
        import csv

        filename = 'google_signups.csv'
        file_exists = os.path.exists(filename)
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(
                    ['timestamp_iso', 'user_id', 'name', 'email']
                )
            writer.writerow(
                [created_at_iso or datetime.now(timezone.utc).isoformat(),
                 user_id or '', name or '', (email or '').strip().lower()]
            )
    except Exception as e:
        logger.error(f"Failed to append google signup CSV: {str(e)}")


@app.before_request
def _redirect_http_to_https():
    # Avoid redirecting in local dev/debug.
    if app.debug:
        return None

    # Never redirect health checks (Azure probes may not follow redirects).
    if request.path in ('/health', '/path/health'):
        return None

    forwarded_proto = (request.headers.get(
        'X-Forwarded-Proto'
    ) or '').lower().strip()
    # Some proxies may send a comma-separated list.
    if ',' in forwarded_proto:
        forwarded_proto = forwarded_proto.split(',')[0].strip()

    is_https = request.is_secure or forwarded_proto == 'https'
    if is_https:
        return None

    # Only redirect safe methods.
    if request.method not in ('GET', 'HEAD'):
        return None

    app.logger.info(
        "[HTTPS REDIRECT] Redirecting to HTTPS (scheme=%s, X-Forwarded-Proto=%s, url=%s)",
        request.scheme,
        forwarded_proto,
        request.url,
    )
    url = request.url.replace('http://', 'https://', 1)
    return redirect(url, code=301)


# Google OAuth Configuration
GOOGLE_CLIENT_SECRET_FILE = os.path.join(
    os.path.dirname(__file__),
    "client_secret.json"
)

# Check if we have environment variables for Google OAuth (production)
if os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET'):
    # Use environment variables (more secure for production)
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    USE_ENV_CREDENTIALS = True
else:
    # Use file-based credentials (for development)
    USE_ENV_CREDENTIALS = False

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

facebook_bp = make_facebook_blueprint(
    client_id=os.getenv("FACEBOOK_APP_ID"),
    client_secret=os.getenv("FACEBOOK_APP_SECRET"),
    scope="email",
    redirect_to="facebook_callback",  # must be HTTPS
)

app.register_blueprint(
    facebook_bp,
    url_prefix="/login"
)  # MUST be before the route below

# Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = "login"


def _is_api_request() -> bool:
    try:
        path = str(getattr(request, 'path', '') or '')
        return path.startswith('/api/') or path.startswith('/path/api/')
    except Exception:
        return False


@login_manager.unauthorized_handler
def _login_unauthorized():
    """Return JSON for API calls instead of an HTML login redirect."""
    if _is_api_request():
        return jsonify(
            {"success": False,
             "error": "Please sign in to use the Job Search Coach."}
        ), 401
    next_path = (request.full_path or request.path or "").strip()
    if next_path.endswith("?"):
        next_path = next_path[:-1]
    return redirect(url_for('login', next=next_path or request.path))


# Define a list of admin email addresses
ADMIN_EMAILS = ["yaronyaronlid@gmail.com"]
EXCLUDED_LOGIN_METRIC_EMAILS = {
    "yaronyaronlid@gmail.com",
    "rlidgi@go.pasadena.edu",
}
EXCLUDED_LOGIN_METRIC_DOMAINS = {
    "resumaticai.com",
}

# Password reset tokens storage
RESET_TOKENS_FILE = "reset_tokens.json"
RESET_TOKEN_EXPIRY_HOURS = 24  # Tokens expire after 24 hours
LOCAL_AUTH_USERS_FILE = "users_auth_local.json"

# Login auditing (email + login timestamp + session duration)
LOGIN_AUDIT_FILE = "login_audit.json"
LOGIN_AUDIT_SESSION_KEY = "login_audit_id"
_LOGIN_AUDIT_VERSION = 1

# Persisting last activity can be useful for interpreting sessions without explicit logout.
# Throttle updates to avoid excessive disk/DB writes.
LOGIN_AUDIT_LAST_ACTIVITY_AT_KEY = 'login_audit_last_activity_at'
LOGIN_AUDIT_LAST_ACTIVITY_WRITE_AT_KEY = 'login_audit_last_activity_write_at'
LOGIN_AUDIT_ACTIVITY_WRITE_THROTTLE_SECONDS = int(
    os.getenv('LOGIN_AUDIT_ACTIVITY_WRITE_THROTTLE_SECONDS', '60') or '60'
)

# Auth session timeouts
# - Idle timeout: log out after N minutes with no authenticated requests.
# These are best-effort guards to reduce risk from unattended sessions.
AUTH_IDLE_TIMEOUT_MINUTES = int(
    os.getenv('AUTH_IDLE_TIMEOUT_MINUTES', '90') or '90'
)
# Absolute timeout is disabled by default (set to >0 to enable).
AUTH_ABSOLUTE_TIMEOUT_HOURS = int(
    os.getenv('AUTH_ABSOLUTE_TIMEOUT_HOURS', '0') or '0'
)
AUTH_SESSION_START_AT_KEY = 'auth_session_start_at'
AUTH_LAST_ACTIVITY_AT_KEY = 'auth_last_activity_at'

# Azure Table Storage (optional) for login auditing.
# If available, this avoids JSON file concurrency issues across workers/instances.
AZURE_LOGIN_AUDIT_TABLE = os.getenv(
    'AZURE_LOGIN_AUDIT_TABLE',
    'LoginAudit'
)
LOGIN_AUDIT_SESSION_PK_KEY = 'login_audit_pk'
LOGIN_AUDIT_SESSION_RK_KEY = 'login_audit_rk'
LOGIN_AUDIT_SESSION_LOGIN_AT_KEY = 'login_audit_login_at'

# Azure Users table: record each login session as a separate row (append-only).
# This keeps the existing profile row (RowKey='profile') intact while allowing multiple sessions per user.
USERS_SESSION_ROWKEY_KEY = 'users_session_rk'
USERS_SESSION_LOGIN_AT_KEY = 'users_session_login_at'
USERS_SESSION_AUDIT_ID_KEY = 'users_session_audit_id'

# Email verification
EMAIL_VERIFY_TOKEN_EXPIRY_HOURS = int(
    os.getenv('EMAIL_VERIFY_TOKEN_EXPIRY_HOURS', '48')
)


class User(UserMixin):
    def __init__(
            self,
            id,
            name,
            email,
            password_hash=None,
            is_new=False,
            created_at=None,
            email_verified=True,
            email_verified_at=None,
            email_verification_sent_at=None,
            welcome_email_sent_at=None,
    ):
        self.id = id
        self.name = name
        self.email = email
        self.password_hash = password_hash
        self.is_new = is_new
        self.created_at = created_at or datetime.now(
            timezone.utc
        ).isoformat()
        self.email_verified = bool(email_verified)
        self.email_verified_at = email_verified_at
        self.email_verification_sent_at = email_verification_sent_at
        self.welcome_email_sent_at = welcome_email_sent_at
        # Determine if the user is an admin based on their email
        self.is_admin = email in ADMIN_EMAILS

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if provided password matches hash"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Convert user to dictionary for JSON storage"""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'password_hash': self.password_hash,
            'created_at': self.created_at,
            'email_verified': getattr(self, 'email_verified', True),
            'email_verified_at': getattr(self, 'email_verified_at', None),
            'email_verification_sent_at': getattr(
                self,
                'email_verification_sent_at',
                None
            ),
            'welcome_email_sent_at': getattr(
                self,
                'welcome_email_sent_at',
                None
            ),
            'is_admin': self.is_admin
        }

    @classmethod
    def from_dict(cls, data):
        """Create user from dictionary"""

        def _coerce_bool(val, default=False):
            if val is None:
                return default
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)):
                return bool(val)
            if isinstance(val, str):
                s = val.strip().lower()
                if s in ('1', 'true', 'yes', 'y', 'on'):
                    return True
                if s in ('0', 'false', 'no', 'n', 'off', ''):
                    return False
            return default

        # Backward-compatibility + security:
        # - Social logins (no password_hash) are treated as verified.
        # - Legacy email/password accounts that predate verification are treated as unverified,
        #   forcing them to confirm their email on next login.
        raw_verified = data.get('email_verified', None)
        if raw_verified is None:
            inferred_verified = not bool(data.get('password_hash'))
        else:
            inferred_verified = _coerce_bool(raw_verified, default=False)

        user = cls(
            id=data['id'],
            name=data['name'],
            email=data['email'],
            password_hash=data.get('password_hash'),
            created_at=data.get('created_at'),
            email_verified=inferred_verified,
            email_verified_at=data.get('email_verified_at'),
            email_verification_sent_at=data.get(
                'email_verification_sent_at'
            ),
            welcome_email_sent_at=data.get('welcome_email_sent_at'),
        )
        return user


@app.before_request
def _enforce_email_verification_gate():
    """If a user is authenticated but not verified, force them to verify before using the site."""
    try:
        if not current_user.is_authenticated:
            return None

        if not _requires_email_verification(current_user):
            return None

        # Allowlist: routes required to complete verification or sign out.
        endpoint = (request.endpoint or '').strip()
        allowed_endpoints = {
            'verify_email',
            'verify_email_token',
            'resend_verification',
            'logout',
            'login',
            'forgot_password',
            'reset_password',
        }
        if endpoint in allowed_endpoints:
            return None

        # Allow static assets
        if endpoint.startswith('static'):
            return None

        if _is_api_request():
            return jsonify(
                {
                    "success": False,
                    "error": "Please verify your email to use the Job Search Coach.",
                }
            ), 403

        return redirect(
            url_for(
                'verify_email',
                email=getattr(current_user, 'email', '')
            )
        )
    except Exception:
        return None


def _requires_email_verification(user: 'User') -> bool:
    """Only require verification for email/password accounts."""
    try:
        is_email_password = bool(getattr(user, 'password_hash', None))
        verified = bool(getattr(user, 'email_verified', True))
        return bool(is_email_password and not verified)
    except Exception:
        return False


def _get_external_url(endpoint: str, **values) -> str:
    """Generate an absolute URL suitable for email links."""
    try:
        return url_for(endpoint, _external=True, **values)
    except Exception:
        # Fallback (very rare): use request.url_root if available.
        try:
            root = str(getattr(request, 'url_root', '') or '').rstrip('/')
            path = url_for(endpoint, _external=False, **values)
            return f"{root}{path}"
        except Exception:
            return url_for(endpoint, _external=False, **values)


def generate_email_verification_token(user: 'User') -> str:
    from itsdangerous import URLSafeTimedSerializer

    serializer = URLSafeTimedSerializer(app.secret_key)
    payload = {
        'user_id': str(user.id),
        'email': str(user.email or '').strip().lower(),
    }
    return serializer.dumps(payload, salt='email-verify')


def confirm_email_verification_token(
        token: str,
        max_age_seconds: int
) -> dict | None:
    from itsdangerous import (
        URLSafeTimedSerializer, BadSignature,
        SignatureExpired,
    )

    serializer = URLSafeTimedSerializer(app.secret_key)
    try:
        return serializer.loads(
            token,
            salt='email-verify',
            max_age=max_age_seconds
        )
    except SignatureExpired:
        return None
    except BadSignature:
        return None
    except Exception:
        return None


def generate_reinstate_paid_offer_token(
        user_id: str,
        subscription_id: str,
        email: str
) -> str:
    """Create a signed token for paid-cancel reinstatement offer links."""
    from itsdangerous import URLSafeTimedSerializer

    serializer = URLSafeTimedSerializer(app.secret_key)
    payload = {
        'user_id': str(user_id or '').strip(),
        'subscription_id': str(subscription_id or '').strip(),
        'email': str(email or '').strip().lower(),
        'v': 1,
    }
    return serializer.dumps(payload, salt='reinstate-paid-offer')


def _reinstate_offer_max_age_seconds() -> int:
    try:
        hours = int(
            (os.getenv(
                "REINSTATE_OFFER_TOKEN_EXPIRY_HOURS"
            ) or "720").strip()
        )
    except Exception:
        hours = 720
    if hours < 1:
        hours = 720
    return hours * 3600


_REINSTATE_OFFER_SESSION_KEY = "reinstate_paid_offer_token"


def _store_reinstate_paid_offer_token_in_session(token: str) -> None:
    try:
        token = str(token or "").strip()
        if token:
            session[_REINSTATE_OFFER_SESSION_KEY] = token
            session.modified = True
    except Exception:
        pass


def confirm_reinstate_paid_offer_token(
        token: str,
        max_age_seconds: int | None = None
) -> dict | None:
    """Validate a signed paid-cancel reinstatement offer token."""
    from itsdangerous import (
        URLSafeTimedSerializer, BadSignature,
        SignatureExpired,
    )

    serializer = URLSafeTimedSerializer(app.secret_key)
    max_age = int(
        max_age_seconds if max_age_seconds is not None else _reinstate_offer_max_age_seconds()
    )
    try:
        return serializer.loads(
            token,
            salt='reinstate-paid-offer',
            max_age=max_age
        )
    except SignatureExpired:
        return None
    except BadSignature:
        return None
    except Exception:
        return None


EMAIL_TRIAL_PLAN_ID = 'trial_10d_email'
EMAIL_TRIAL_INVITE_SALT = 'email-trial-invite'


def _rbi_embedded_checkout_plans() -> tuple[str, ...]:
    return (
        'trial_7d', EMAIL_TRIAL_PLAN_ID, 'monthly_10_95', 'annual_6_95')


def _is_email_trial_plan(plan_id: str) -> bool:
    return _normalize_plan_id(plan_id) == EMAIL_TRIAL_PLAN_ID


def _email_trial_invite_max_age_seconds() -> int:
    try:
        days = int(
            (os.getenv('TRIAL_EMAIL_INVITE_MAX_AGE_DAYS') or '120').strip()
        )
    except Exception:
        days = 120
    if days < 1:
        days = 120
    return days * 86400


def generate_email_trial_invite_token(
        campaign: str = '',
        trial_days: int = 10,
        waive_upfront_fee: bool = True,
) -> str:
    """Create a signed invite token for the mass-email 10-day trial campaign."""
    from itsdangerous import URLSafeTimedSerializer

    serializer = URLSafeTimedSerializer(app.secret_key)
    payload = {
        'plan_id': EMAIL_TRIAL_PLAN_ID,
        'campaign': str(
            campaign or os.getenv(
                'TRIAL_EMAIL_CAMPAIGN'
            ) or 'email-trial-2026'
        ).strip(),
        'trial_days': max(1, int(trial_days or 10)),
        'waive_upfront_fee': bool(waive_upfront_fee),
        'v': 1,
    }
    return serializer.dumps(payload, salt=EMAIL_TRIAL_INVITE_SALT)


def confirm_email_trial_invite_token(
        token: str,
        max_age_seconds: int | None = None
) -> dict | None:
    """Validate a signed mass-email trial invite token."""
    from itsdangerous import (
        URLSafeTimedSerializer, BadSignature,
        SignatureExpired,
    )

    serializer = URLSafeTimedSerializer(app.secret_key)
    max_age = int(
        max_age_seconds if max_age_seconds is not None else _email_trial_invite_max_age_seconds()
    )
    try:
        payload = serializer.loads(
            token,
            salt=EMAIL_TRIAL_INVITE_SALT,
            max_age=max_age
        )
    except SignatureExpired:
        return None
    except BadSignature:
        return None
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get('plan_id') or '').strip() != EMAIL_TRIAL_PLAN_ID:
        return None
    return payload


def _store_email_trial_invite_in_session(invite: dict) -> None:
    try:
        session['email_trial_invite'] = {
            'plan_id': EMAIL_TRIAL_PLAN_ID,
            'campaign': str(invite.get('campaign') or '').strip(),
            'trial_days': max(1, int(invite.get('trial_days') or 10)),
            'waive_upfront_fee': bool(
                invite.get('waive_upfront_fee', True)
            ),
        }
        session.modified = True
    except Exception:
        pass


def _get_email_trial_invite_from_session() -> dict | None:
    try:
        raw = session.get('email_trial_invite') or {}
        if not isinstance(raw, dict):
            return None
        if str(raw.get('plan_id') or '').strip() != EMAIL_TRIAL_PLAN_ID:
            return None
        return raw
    except Exception:
        return None


def _user_can_start_email_trial(user_obj: Optional['User']) -> tuple[
    bool, str]:
    """Return (allowed, reason_code) for the mass-email 10-day trial."""
    if not user_obj or not getattr(user_obj, 'is_authenticated', False):
        return False, 'authentication_required'
    try:
        if is_paid_user(user_obj):
            return False, 'already_subscribed'
    except Exception:
        pass
    if _stripe_enabled():
        try:
            prof = get_user_profile_azure(
                getattr(user_obj, 'id', '')
            ) or {}
            customer_id = str(prof.get('stripe_customer_id') or '').strip()
            if not customer_id:
                email = (getattr(user_obj, 'email', '') or '').strip()
                if email:
                    customer_id = _find_stripe_customer_id_by_email(
                        email,
                        require_subscription_history=True
                    )
            if customer_id:

                res = stripe.Subscription.list(
                    customer=customer_id,
                    status='all',
                    limit=10
                )
                for sub in list(getattr(res, 'data', []) or []):
                    if _stripe_subscription_grants_access(sub):
                        return False, 'already_subscribed'
        except Exception:
            pass
    return True, ''


def build_email_trial_checkout_url(
        invite_token: str,
        base_url: str = ''
) -> str:
    """Build the mass-email checkout URL for a signed invite token."""
    from urllib.parse import quote

    root = (base_url or os.getenv(
        'PUBLIC_SITE_URL'
    ) or 'https://resumaticai.com').strip().rstrip('/')
    token = quote(str(invite_token or '').strip(), safe='')
    return f"{root}/checkout?plan={EMAIL_TRIAL_PLAN_ID}&invite={token}"


def _resolve_email_trial_invite(invite_token: str = '') -> dict | None:
    """Validate invite from query param or session."""
    token = str(invite_token or '').strip()
    invite = confirm_email_trial_invite_token(token) if token else None
    if invite:
        _store_email_trial_invite_in_session(invite)
        return invite
    return _get_email_trial_invite_from_session()


def _should_use_embedded_subscription_checkout(plan_id: str) -> bool:
    """Embedded pending SetupIntent checkout for India monthly/annual only."""
    if not _stripe_enabled():
        return False
    pid = _normalize_plan_id(plan_id)
    if pid in ('trial_7d', EMAIL_TRIAL_PLAN_ID):
        return False
    return _is_india_pricing_region() and pid in (
        'monthly_10_95', 'annual_6_95')


def send_email_verification_email(
        email: str,
        token: str,
        user_name: str,
        next_url: str | None = None
) -> bool:
    """Send email verification link to user."""
    try:
        _load_email_config_if_missing()
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.image import MIMEImage
        from email.mime.multipart import MIMEMultipart
        from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        auth_email = (
                os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip(
            '"'
        ).strip("'")
        # App Service settings sometimes get pasted with surrounding quotes/newlines; tolerate that.
        auth_password = (os.getenv(
            'NEWSLETTER_PASSWORD',
            ''
        ) or '').strip().strip('"').strip("'").replace(' ', '')

        if not auth_email or not auth_password:
            raise ValueError(
                'Email credentials not configured. Set NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD.'
            )

        verify_url = _get_external_url('verify_email_token', token=token)
        try:
            nxt = (next_url or '').strip()
            # Only allow relative paths to avoid open redirects in emailed links.
            if nxt.startswith('/') and not nxt.startswith('//'):
                parts = urlparse(verify_url)
                q = dict(parse_qsl(parts.query, keep_blank_values=True))
                q['next'] = nxt
                verify_url = urlunparse(parts._replace(query=urlencode(q)))
        except Exception:
            pass
        subject = 'Verify your email - ResumaticAI'

        html_body = f"""
        <html>
        <body style=\"font-family: Arial, sans-serif; line-height: 1.6; color: #333;\">
            <div style=\"max-width: 600px; margin: 0 auto; padding: 20px;\">
                <h2 style=\"color: #2563eb;\">Verify your email</h2>
                <p>Hello {user_name},</p>
                <p>Thanks for registering with ResumaticAI. Please verify your email address to finish setting up your account.</p>
                <div style=\"margin: 30px 0;\">
                    <a href=\"{verify_url}\" style=\"background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;\">Verify Email</a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style=\"word-break: break-all; color: #666;\">{verify_url}</p>
                <p>This link will expire in {EMAIL_VERIFY_TOKEN_EXPIRY_HOURS} hours.</p>
                <p>If you didn't create an account, you can ignore this email.</p>
                <hr style=\"border: none; border-top: 1px solid #eee; margin: 20px 0;\">
                <p style=\"color: #666; font-size: 12px;\">ResumaticAI Team</p>
            </div>
        </body>
        </html>
        """

        text_body = f"""
Verify your email - ResumaticAI

Hello {user_name},

Thanks for registering with ResumaticAI. Please verify your email address to finish setting up your account:

{verify_url}

This link will expire in {EMAIL_VERIFY_TOKEN_EXPIRY_HOURS} hours.

If you didn't create an account, you can ignore this email.

ResumaticAI Team
        """.strip()

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"ResumaticAI <{auth_email}>"
        msg['To'] = email
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(auth_email, auth_password)
        server.send_message(msg)
        server.quit()

        logger.info(f"Verification email sent to {email}")
        try:
            record_email_event(
                email_type="verification",
                recipient=email,
                subject=subject,
                status="sent",
                source="automatic",
                metadata={"user_name": str(user_name or "").strip()},
            )
        except Exception:
            pass
        return True
    except Exception:
        # Keep user-facing messaging generic; log full details for ops/debugging.
        # Never log passwords/secrets.
        try:
            logger.error(
                "Verification email failed (smtp_server=%s smtp_port=%s auth_email=%s to=%s)",
                os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
                os.getenv('SMTP_PORT', '587'),
                (os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip(
                    '"'
                ).strip("'"),
                (email or '').strip().lower(),
            )
        except Exception:
            pass
        logger.exception("Error sending verification email")
        try:
            record_email_event(
                email_type="verification",
                recipient=email,
                subject="Verify your email - ResumaticAI",
                status="failed",
                source="automatic",
                metadata={"user_name": str(user_name or "").strip()},
                error="smtp_send_failed",
            )
        except Exception:
            pass
        return False


def send_welcome_email(email: str, user_name: str) -> bool:
    """Send welcome email to a new user.

    This is best-effort: returns True on successful SMTP send, otherwise False.
    """
    try:
        email = (email or '').strip().lower()
        if not email:
            return False

        _load_email_config_if_missing()
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.image import MIMEImage
        from email.mime.multipart import MIMEMultipart
        from urllib.parse import urlencode

        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        auth_email = (
                os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip(
            '"'
        ).strip("'")
        auth_password = (os.getenv(
            'NEWSLETTER_PASSWORD',
            ''
        ) or '').strip().strip('"').strip("'").replace(' ', '')

        # Visible diagnostics (no secrets) to prove which SMTP config is in effect.
        try:
            logging.getLogger().info(
                "send_welcome_email: start (to=%s smtp_server=%s smtp_port=%s auth_email=%s)",
                email,
                smtp_server,
                smtp_port,
                auth_email,
            )
            if not _ON_AZURE:
                print(
                    f"[send_welcome_email] to={email} smtp={smtp_server}:{smtp_port} from={auth_email}"
                )
        except Exception:
            pass

        if not auth_email or not auth_password:
            raise ValueError(
                'Email credentials not configured. Set NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD.'
            )

        try:
            home_url = _get_external_url('index')
        except Exception:
            home_url = ''

        try:
            unsubscribe_url = _get_external_url('unsubscribe')
            # Prefill email on the unsubscribe page.
            if unsubscribe_url:
                unsubscribe_url = f"{unsubscribe_url}?{urlencode({'email': email})}"
        except Exception:
            unsubscribe_url = ''

        site_url = home_url or 'https://resumaticai.com'
        # Avoid WebP in emails (not widely supported). Prefer PNG.
        logo_url = f"{site_url.rstrip('/')}/static/images/logo233_small.png"

        logo_cid = 'resumatic_logo'
        logo_bytes = None
        try:
            logo_path = os.path.join(
                os.path.dirname(__file__),
                'static',
                'images',
                'logo233_small.png'
            )
            with open(logo_path, 'rb') as f:
                logo_bytes = f.read()
        except Exception:
            logo_bytes = None

        logo_src = f"cid:{logo_cid}" if logo_bytes else logo_url

        subject = 'Welcome to ResumaticAI'

        html_body = f"""
<html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="text-align: center; margin-bottom: 16px;">
                <a href="{site_url}" style="text-decoration: none;">
                    <img src="{logo_src}" alt="ResumaticAI" style="max-width: 180px; width: 180px; height: auto;">
                </a>
            </div>
            <p>Hi there,</p>

            <p>Welcome to ResumaticAI. We're really glad you're here.</p>

            <p>We built ResumaticAI because we saw two things:</p>

            <ul>
                <li>AI has become incredibly powerful.</li>
                <li>Most resume tools still feel generic.</li>
            </ul>

            <p>
                Resumes aren't just documents, they're positioning tools. The difference between getting ignored and getting interviews often comes down to clarity, impact, and strategy. ResumaticAI was designed to combine advanced AI with practical resume expertise to help you present your experience in the strongest possible way.
            </p>

            <p>Here's what you can do right now:</p>

            <ul>
                <li>Upload your resume for instant AI-powered feedback</li>
                <li>Strengthen your bullet points with measurable impact</li>
                <li>Tailor your resume to specific job descriptions</li>
                <li>Improve structure, clarity, and ATS compatibility</li>
            </ul>

            <p>
                As we are constantly looking to make improvements to the site, any feedback you can provide at
                <a href="https://resumaticai.com/feedback" style="color: #2563eb;">ResumaticAI.com/feedback</a>
                would help.
            </p>

            <p>
                If you're satisfied with your experience, we'd be grateful if you would consider sharing your feedback on Trustpilot:
                <a href="https://www.trustpilot.com/review/resumaticai.com" style="color: #2563eb;">https://www.trustpilot.com/review/resumaticai.com</a>.
                Your support truly means a lot to us.
            </p>

            <p>
                For a limited time we are offering a free 3-day trial of the premium plan, which you can find on our plans page:
                <a href="https://resumaticai.com/plans" style="color: #2563eb;">https://resumaticai.com/plans</a>.
            </p>

            <p>Let's build a resume that gets you interviews!</p>

            <p>
                Visit:
                <a href="https://resumaticai.com" style="color: #2563eb;">https://resumaticai.com</a>
            </p>

            <p>
                Yaron<br>
                Founder, ResumaticAI
            </p>

            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">

            {f'<p style="color: #666; font-size: 12px;">Newsletter unsubscribe: <a href="{unsubscribe_url}" style="color: #2563eb;">{unsubscribe_url}</a></p>' if unsubscribe_url else ''}
        </div>
    </body>
</html>
        """

        text_body = "\n".join(
            [
                'Hi there,',
                '',
                "Welcome to ResumaticAI. We're really glad you're here.",
                '',
                'We built ResumaticAI because we saw two things:',
                '',
                '• AI has become incredibly powerful.',
                '• Most resume tools still feel generic.',
                '',
                "Resumes aren't just documents — they're positioning tools. The difference between getting ignored and getting interviews often comes down to clarity, impact, and strategy. ResumaticAI was designed to combine advanced AI with practical resume expertise to help you present your experience in the strongest possible way.",
                '',
                "Here's what you can do right now:",
                '',
                '• Upload your resume for instant AI-powered feedback',
                '• Strengthen your bullet points with measurable impact',
                '• Tailor your resume to specific job descriptions',
                '• Improve structure, clarity, and ATS compatibility',
                '',
                'As we are constantly looking to make improvements to the site, any feedback you can provide at',
                'https://resumaticai.com/feedback',
                'would help.',
                '',
                "If you're satisfied with your experience, we'd be grateful if you would consider sharing your feedback on Trustpilot:",
                'https://www.trustpilot.com/review/resumaticai.com',
                'Your support truly means a lot to us.',
                '',
                'For a limited time we are offering a free 3-day trial of the premium plan, which you can find on our plans page:',
                'https://resumaticai.com/plans',
                '',
                "Let's build a resume that gets you interviews!",
                '',
                'Visit: https://resumaticai.com',
                '',
                'Yaron',
                'Founder, ResumaticAI',
                '',
                '---',
                *([
                      f'Newsletter unsubscribe: {unsubscribe_url}'] if unsubscribe_url else []),
                'ResumaticAI Team',
            ]
        ).strip()

        msg_root = MIMEMultipart('related')
        msg_root['Subject'] = subject
        msg_root['From'] = f"ResumaticAI <{auth_email}>"
        msg_root['To'] = email

        msg_alt = MIMEMultipart('alternative')
        msg_alt.attach(MIMEText(text_body, 'plain'))
        msg_alt.attach(MIMEText(html_body, 'html'))
        msg_root.attach(msg_alt)

        if logo_bytes:
            logo_part = MIMEImage(logo_bytes)
            logo_part.add_header('Content-ID', f"<{logo_cid}>")
            logo_part.add_header(
                'Content-Disposition',
                'inline',
                filename='logo.png'
            )
            msg_root.attach(logo_part)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(auth_email, auth_password)
        server.send_message(msg_root)
        server.quit()

        logger.info(f"Welcome email sent to {email}")
        try:
            record_email_event(
                email_type="welcome",
                recipient=email,
                subject=subject,
                status="sent",
                source="automatic",
                metadata={"user_name": str(user_name or "").strip()},
            )
        except Exception:
            pass
        return True
    except Exception:
        # Never log passwords/secrets.
        try:
            logger.error(
                "Welcome email failed (smtp_server=%s smtp_port=%s auth_email=%s to=%s)",
                os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
                os.getenv('SMTP_PORT', '587'),
                (os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip(
                    '"'
                ).strip("'"),
                (email or '').strip().lower(),
            )
        except Exception:
            pass
        logger.exception('Error sending welcome email')
        try:
            record_email_event(
                email_type="welcome",
                recipient=email,
                subject="Welcome to ResumaticAI",
                status="failed",
                source="automatic",
                metadata={"user_name": str(user_name or "").strip()},
                error="smtp_send_failed",
            )
        except Exception:
            pass
        return False


def send_trial_cancellation_reinstate_email(
        email: str,
        user_name: str,
        include_trial_bonus: bool = True
) -> bool:
    """Send CTA email after trial cancellation, encouraging subscription reinstatement."""
    try:
        email = (email or '').strip().lower()
        if not email:
            return False

        _load_email_config_if_missing()
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.image import MIMEImage
        from email.mime.multipart import MIMEMultipart

        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        auth_email = (
                os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip(
            '"'
        ).strip("'")
        auth_password = (os.getenv(
            'NEWSLETTER_PASSWORD',
            ''
        ) or '').strip().strip('"').strip("'").replace(' ', '')
        if not auth_email or not auth_password:
            raise ValueError(
                'Email credentials not configured. Set NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD.'
            )

        reinstate_url = _get_external_url('billing_cancel_page')
        try:
            home_url = _get_external_url('index')
        except Exception:
            home_url = ''
        site_url = home_url or 'https://resumaticai.com'
        logo_url = f"{site_url.rstrip('/')}/static/images/logo233_small.png"
        logo_cid = 'resumatic_logo_trial_cta'
        logo_bytes = None
        try:
            logo_path = os.path.join(
                os.path.dirname(__file__),
                'static',
                'images',
                'logo233_small.png'
            )
            with open(logo_path, 'rb') as f:
                logo_bytes = f.read()
        except Exception:
            logo_bytes = None
        logo_src = f"cid:{logo_cid}" if logo_bytes else logo_url

        display_name = (user_name or '').strip() or 'there'
        bonus_html = (
            "<p style=\"margin: 0 0 16px; color: #334155; font-size: 15px; line-height: 1.6;\">"
            "If you reinstate now, we'll also extend your trial by <strong>2 weeks</strong>."
            "</p>"
            if include_trial_bonus else ""
        )
        bonus_text = "If you reinstate now, we'll also extend your trial by 2 weeks.\n\n" if include_trial_bonus else ""

        subject = "Keep your edge in your job search - Reinstate your trial"
        html_body = f"""\
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #0f172a;">
    <div style="max-width: 620px; margin: 0 auto; padding: 20px;">
      <div style="text-align: center; margin-bottom: 16px;">
        <a href="{site_url}" style="text-decoration: none;">
          <img src="{logo_src}" alt="ResumaticAI" style="max-width: 180px; width: 180px; height: auto;">
        </a>
      </div>
      <h2 style="margin: 0 0 12px; color: #0f172a;">Don't lose momentum, {display_name}</h2>
      <p style="margin: 0 0 16px; color: #334155; font-size: 15px; line-height: 1.6;">
        We strongly believe the service we offer is indispensable in your job search, and we believe with more time to access the service, you will agree.
      </p>
      {bonus_html}
      <p style="margin: 0 0 20px;">
        <a href="{reinstate_url}" style="display: inline-block; background: #047857; color: #ffffff; text-decoration: none; padding: 12px 18px; border-radius: 8px; font-weight: 700;">
          Reinstate subscription
        </a>
      </p>
      <p style="margin: 0; color: #64748b; font-size: 13px;">
        If the button doesn't work, copy and paste this link into your browser:<br/>
        <a href="{reinstate_url}" style="color: #0ea5e9;">{reinstate_url}</a>
      </p>
    </div>
  </body>
</html>
"""
        text_body = (
            f"Don't lose momentum, {display_name}.\n\n"
            "We strongly believe the service we offer is indispensable in your job search, and we believe with more time to access the service, you will agree.\n\n"
            f"{bonus_text}"
            f"Reinstate your subscription: {reinstate_url}\n"
        )

        msg_root = MIMEMultipart('related')
        msg_root['Subject'] = subject
        msg_root['From'] = f"ResumaticAI <{auth_email}>"
        msg_root['To'] = email

        msg_alt = MIMEMultipart('alternative')
        msg_alt.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg_alt.attach(MIMEText(html_body, 'html', 'utf-8'))
        msg_root.attach(msg_alt)

        if logo_bytes:
            logo_part = MIMEImage(logo_bytes)
            logo_part.add_header('Content-ID', f"<{logo_cid}>")
            logo_part.add_header(
                'Content-Disposition',
                'inline',
                filename='logo.png'
            )
            msg_root.attach(logo_part)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(auth_email, auth_password)
        server.send_message(msg_root)
        server.quit()

        logger.info("Trial cancel CTA email sent to %s", email)
        try:
            record_email_event(
                email_type="trial_cancellation_reinstate",
                recipient=email,
                subject=subject,
                status="sent",
                source="automatic",
                metadata={
                    "user_name": str(user_name or "").strip(),
                    "include_trial_bonus": bool(include_trial_bonus),
                },
            )
        except Exception:
            pass
        return True
    except Exception:
        try:
            logger.error(
                "Trial CTA email failed (smtp_server=%s smtp_port=%s auth_email=%s to=%s)",
                os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
                os.getenv('SMTP_PORT', '587'),
                (os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip(
                    '"'
                ).strip("'"),
                (email or '').strip().lower(),
            )
        except Exception:
            pass
        logger.exception(
            "Error sending trial cancellation reinstate CTA email"
        )
        try:
            record_email_event(
                email_type="trial_cancellation_reinstate",
                recipient=email,
                subject="Keep your edge in your job search - Reinstate your trial",
                status="failed",
                source="automatic",
                metadata={
                    "user_name": str(user_name or "").strip(),
                    "include_trial_bonus": bool(include_trial_bonus),
                },
                error="smtp_send_failed",
            )
        except Exception:
            pass
        return False


def send_paid_cancellation_reinstate_email(
        email: str,
        user_name: str,
        user_id: str,
        subscription_id: str
) -> bool:
    """Send cancellation CTA email for users with real paid history."""
    try:
        email = (email or '').strip().lower()
        if not email:
            return False

        _load_email_config_if_missing()
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.image import MIMEImage
        from email.mime.multipart import MIMEMultipart

        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        auth_email = (
                os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip(
            '"'
        ).strip("'")
        auth_password = (os.getenv(
            'NEWSLETTER_PASSWORD',
            ''
        ) or '').strip().strip('"').strip("'").replace(' ', '')
        if not auth_email or not auth_password:
            raise ValueError(
                'Email credentials not configured. Set NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD.'
            )

        try:
            token = generate_reinstate_paid_offer_token(
                user_id=str(user_id or ""),
                subscription_id=str(subscription_id or ""),
                email=email
            )
            reinstate_url = _get_external_url(
                'billing_reinstate_paid_offer',
                token=token
            )
        except Exception:
            reinstate_url = _get_external_url('billing_cancel_page')
        try:
            home_url = _get_external_url('index')
        except Exception:
            home_url = ''
        site_url = home_url or 'https://resumaticai.com'
        logo_url = f"{site_url.rstrip('/')}/static/images/logo233_small.png"
        logo_cid = 'resumatic_logo_paid_cancel_cta'
        logo_bytes = None
        try:
            logo_path = os.path.join(
                os.path.dirname(__file__),
                'static',
                'images',
                'logo233_small.png'
            )
            with open(logo_path, 'rb') as f:
                logo_bytes = f.read()
        except Exception:
            logo_bytes = None
        logo_src = f"cid:{logo_cid}" if logo_bytes else logo_url

        subject = 'Reinstate today for $3.99 - Exclusive 60% savings offer'
        html_body = f"""\
<html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #0f172a;">
        <div style="max-width: 620px; margin: 0 auto; padding: 20px;">
            <div style="text-align: center; margin-bottom: 16px;">
                <a href="{site_url}" style="text-decoration: none;">
                    <img src="{logo_src}" alt="ResumaticAI" style="max-width: 180px; width: 180px; height: auto;">
                </a>
            </div>
            <h2 style="margin: 0 0 12px; color: #0f172a;">Dear Valued Customer,</h2>
            <p style="margin: 0 0 16px; color: #334155; font-size: 15px; line-height: 1.6;">
                We noticed that you've recently canceled your subscription, and we'd love the opportunity to welcome you back.
            </p>
            <p style="margin: 0 0 16px; color: #334155; font-size: 15px; line-height: 1.6;">
                As a special offer, you can reinstate your account today and receive your next month for just <strong>$3.99</strong>, an exclusive savings of over 60% off our regular monthly price.
            </p>
            <p style="margin: 0 0 16px; color: #334155; font-size: 15px; line-height: 1.6;">
                We've made substantial upgrades to our platform, introducing new features, improved AI capabilities, enhanced performance, and most notably a comprehensive Job Dashboard. We're excited about these improvements and would love for you to explore everything that's new.
            </p>
            <p style="margin: 0 0 16px; color: #334155; font-size: 15px; line-height: 1.6;">
                In today's competitive job market, having the right tools can make all the difference. With these recent enhancements, we believe our service has become an indispensable part of a successful job search campaign, helping job seekers create stronger resumes, stand out to employers, and increase their chances of landing interviews.
            </p>
            <p style="margin: 0 0 16px; color: #334155; font-size: 15px; line-height: 1.6;">
                Don't miss this opportunity to experience our upgraded platform at a deeply discounted rate.
            </p>
            <p style="margin: 0 0 20px;">
                <a href="{reinstate_url}" style="display: inline-block; background: #047857; color: #ffffff; text-decoration: none; padding: 12px 18px; border-radius: 8px; font-weight: 700;">
                    Reactivate today for just $3.99 and see what's new.
                </a>
            </p>
            <p style="margin: 0 0 16px; color: #334155; font-size: 15px; line-height: 1.6;">
                We look forward to helping you achieve your career goals.
            </p>
            <p style="margin: 0 0 16px; color: #334155; font-size: 15px; line-height: 1.6;">
                Best regards,<br/>
                The ResumaticAI Team
            </p>
            <p style="margin: 0; color: #64748b; font-size: 13px;">
                If the button doesn't work, copy and paste this link into your browser:<br/>
                <a href="{reinstate_url}" style="color: #0ea5e9;">{reinstate_url}</a>
            </p>
        </div>
    </body>
</html>
"""
        text_body = (
            "Dear Valued Customer,\n\n"
            "We noticed that you've recently canceled your subscription, and we'd love the opportunity to welcome you back.\n\n"
            "As a special offer, you can reinstate your account today and receive your next month for just $3.99, an exclusive savings of over 60% off our regular monthly price.\n\n"
            "We've made substantial upgrades to our platform, introducing new features, improved AI capabilities, enhanced performance, and most notably a comprehensive Job Dashboard. We're excited about these improvements and would love for you to explore everything that's new.\n\n"
            "In today's competitive job market, having the right tools can make all the difference. With these recent enhancements, we believe our service has become an indispensable part of a successful job search campaign, helping job seekers create stronger resumes, stand out to employers, and increase their chances of landing interviews.\n\n"
            "Don't miss this opportunity to experience our upgraded platform at a deeply discounted rate.\n\n"
            "Reactivate today for just $3.99 and see what's new.\n\n"
            f"Reactivation link: {reinstate_url}\n\n"
            "We look forward to helping you achieve your career goals.\n\n"
            "Best regards,\n\n"
            "The ResumaticAI Team\n"
        )

        msg_root = MIMEMultipart('related')
        msg_root['Subject'] = subject
        msg_root['From'] = f"ResumaticAI <{auth_email}>"
        msg_root['To'] = email

        msg_alt = MIMEMultipart('alternative')
        msg_alt.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg_alt.attach(MIMEText(html_body, 'html', 'utf-8'))
        msg_root.attach(msg_alt)

        if logo_bytes:
            logo_part = MIMEImage(logo_bytes)
            logo_part.add_header('Content-ID', f"<{logo_cid}>")
            logo_part.add_header(
                'Content-Disposition',
                'inline',
                filename='logo.png'
            )
            msg_root.attach(logo_part)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(auth_email, auth_password)
        server.send_message(msg_root)
        server.quit()

        logger.info("Paid cancel CTA email sent to %s", email)
        try:
            record_email_event(
                email_type="paid_cancellation_reinstate",
                recipient=email,
                subject=subject,
                status="sent",
                source="automatic",
                metadata={
                    "user_name": str(user_name or "").strip(),
                    "user_id": str(user_id or "").strip(),
                    "subscription_id": str(subscription_id or "").strip(),
                },
            )
        except Exception:
            pass
        return True
    except Exception:
        try:
            logger.error(
                "Paid cancel CTA email failed (smtp_server=%s smtp_port=%s auth_email=%s to=%s)",
                os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
                os.getenv('SMTP_PORT', '587'),
                (os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip(
                    '"'
                ).strip("'"),
                (email or '').strip().lower(),
            )
        except Exception:
            pass
        logger.exception(
            'Error sending paid cancellation reinstate CTA email'
        )
        try:
            record_email_event(
                email_type="paid_cancellation_reinstate",
                recipient=email,
                subject="Reinstate today for $3.99 - Exclusive 60% savings offer",
                status="failed",
                source="automatic",
                metadata={
                    "user_name": str(user_name or "").strip(),
                    "user_id": str(user_id or "").strip(),
                    "subscription_id": str(subscription_id or "").strip(),
                },
                error="smtp_send_failed",
            )
        except Exception:
            pass
        return False


def load_users():
    """Load users from Azure-backed profiles, with local JSON fallback."""
    try:
        collector = globals().get(
            '_collect_registered_users_from_azure_users_table'
        )
        if callable(collector):
            rows, _, _ = collector()
            loaded_users = {}
            for row in rows:
                user_id = str(
                    row.get('id') or row.get('PartitionKey') or ''
                ).strip()
                email = str(row.get('email') or '').strip()
                if not user_id or not email:
                    continue
                user_data = {
                    'id': user_id,
                    'name': str(row.get('name') or '').strip() or
                            email.split('@')[0] or 'User',
                    'email': email,
                    'password_hash': row.get('password_hash'),
                    'created_at': row.get('created_at'),
                    'email_verified': row.get('email_verified'),
                    'email_verified_at': row.get('email_verified_at'),
                    'email_verification_sent_at': row.get(
                        'email_verification_sent_at'
                    ),
                    'welcome_email_sent_at': row.get(
                        'welcome_email_sent_at'
                    ),
                }
                loaded_users[user_id] = User.from_dict(user_data)
            if loaded_users:
                return loaded_users
    except Exception:
        logger.exception("Error loading users from Azure")
    try:
        if os.path.exists(LOCAL_AUTH_USERS_FILE):
            with open(LOCAL_AUTH_USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                loaded_users = {}
                for user_id, user_data in data.items():
                    if not isinstance(user_data, dict):
                        continue
                    try:
                        record = dict(user_data)
                        record['id'] = str(
                            record.get('id') or user_id
                        ).strip()
                        if not record['id'] or not str(
                                record.get('email') or ''
                        ).strip():
                            continue
                        loaded_users[record['id']] = User.from_dict(record)
                    except Exception:
                        continue
                return loaded_users
    except Exception:
        logger.exception("Error loading users from local auth store")
    return {}


def save_users():
    """Persist the in-memory user cache to Azure profiles and local fallback."""
    try:
        for user in users.values():
            upsert_user_profile_azure(user)
    except Exception:
        logger.exception("Error saving users to Azure")
    try:
        payload = {}
        for user_id, user in users.items():
            if not user:
                continue
            payload[str(user_id)] = user.to_dict()
        with open(LOCAL_AUTH_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception:
        logger.exception("Error saving users to local auth store")


def add_user(user):
    """Add a user and persist to Azure-backed storage plus local fallback."""
    if user and not getattr(user, 'password_hash', None):
        user.password_hash = generate_password_hash(
            secrets.token_urlsafe(32)
        )
    users[user.id] = user
    try:
        upsert_user_profile_azure(user)
    except Exception:
        logger.exception("Error upserting user to Azure")
    try:
        save_users()
    except Exception:
        logger.exception("Error persisting users after add_user")
    try:
        logger.info(
            "Added user: %s (%s)",
            getattr(user, 'name', ''),
            getattr(user, 'email', '')
        )
    except Exception:
        pass


def _normalize_email(email: str) -> str:
    try:
        return str(email or '').strip().lower()
    except Exception:
        return ''


def _find_user_by_email(email: str):
    needle = _normalize_email(email)
    if not needle:
        return None
    for _, u in users.items():
        if _normalize_email(getattr(u, 'email', '')) == needle:
            return u
    return None


def _find_azure_user_profile_by_email(email: str):
    needle = _normalize_email(email)
    if not needle:
        return None
    try:
        table_client = get_users_table_client()
        try:
            pager = table_client.query_entities("RowKey eq 'profile'")
        except Exception:
            pager = table_client.list_entities()
        for entity in pager:
            if str(entity.get('RowKey') or '') != 'profile':
                continue
            if _normalize_email(entity.get('email', '')) == needle:
                return dict(entity)
    except Exception:
        pass
    return None


def _get_auth_user_by_email(email: str):
    user = _find_user_by_email(email)
    if user:
        return user

    prof = _find_azure_user_profile_by_email(email)
    if not prof:
        return None

    record = dict(prof)
    record['id'] = str(
        record.get('PartitionKey') or record.get('id') or ''
    ).strip()
    if not record['id'] or not record.get('password_hash'):
        return None

    try:
        user = User.from_dict(record)
        users[user.id] = user
        save_users()
        return user
    except Exception:
        return None


def _resolve_oauth_user(user_id: str, name: str, email: str) -> tuple[
    'User', bool]:
    """Return (user, is_new) for OAuth logins using persistent profile lookup.

    This prevents existing users from being treated as new after process restarts,
    which can otherwise re-trigger one-time welcome email logic.
    """
    uid = str(user_id or '').strip()
    normalized_email = _normalize_email(email)

    existing = users.get(uid)
    if existing:
        if name:
            existing.name = name
        if normalized_email:
            existing.email = normalized_email
        return existing, False

    try:
        prof = get_user_profile_azure(uid) or {}
        if prof and prof.get('email'):
            record = dict(prof)
            record['id'] = uid
            existing = User.from_dict(record)
            if name:
                existing.name = name
            if normalized_email:
                existing.email = normalized_email
            users[uid] = existing
            return existing, False
    except Exception:
        pass

    return User(uid, name, normalized_email, is_new=True), True


def _load_login_audit_store() -> dict:
    """Load login audit store from disk (best-effort)."""
    try:
        if os.path.exists(LOGIN_AUDIT_FILE):
            with open(LOGIN_AUDIT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and isinstance(
                        data.get('sessions'),
                        dict
                ):
                    data.setdefault('version', _LOGIN_AUDIT_VERSION)
                    return data
    except Exception:
        logger.exception("Error loading login audit store")
    return {'version': _LOGIN_AUDIT_VERSION, 'sessions': {}}


def _save_login_audit_store(store: dict) -> None:
    """Save login audit store to disk (best-effort, atomic replace)."""
    try:
        store = store or {'version': _LOGIN_AUDIT_VERSION, 'sessions': {}}
        store.setdefault('version', _LOGIN_AUDIT_VERSION)
        store.setdefault('sessions', {})

        import tempfile

        dir_name = os.path.dirname(
            os.path.abspath(LOGIN_AUDIT_FILE)
        ) or '.'
        with tempfile.NamedTemporaryFile(
                'w',
                delete=False,
                dir=dir_name,
                encoding='utf-8'
        ) as tf:
            json.dump(store, tf, indent=2, ensure_ascii=False)
            tmp_path = tf.name
        os.replace(tmp_path, LOGIN_AUDIT_FILE)
    except Exception:
        logger.exception("Error saving login audit store")


def _parse_iso_datetime(value: str | None) -> datetime | None:
    try:
        raw = str(value or '').strip()
        if not raw:
            return None
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _get_pacific_tzinfo():
    """Return a tzinfo for America/Los_Angeles if possible; otherwise a fixed PST offset."""
    # Prefer stdlib zoneinfo.
    if ZoneInfo is not None:
        try:
            return ZoneInfo('America/Los_Angeles')
        except Exception:
            # On Windows, the IANA timezone database may be missing.
            # If the optional `tzdata` package is installed, ZoneInfo can use it.
            try:
                import tzdata  # noqa: F401

                return ZoneInfo('America/Los_Angeles')
            except Exception:
                pass

    # Python <3.9: try backports.
    try:
        from backports.zoneinfo import \
            ZoneInfo as BackportsZoneInfo  # type: ignore

        return BackportsZoneInfo('America/Los_Angeles')
    except Exception:
        pass

    # Last resort: pytz.
    try:
        import pytz  # type: ignore

        return pytz.timezone('America/Los_Angeles')
    except Exception:
        pass

    # Fallback: fixed PST (no DST awareness).
    return timezone(timedelta(hours=-8), name='PST')


def _format_datetime_pacific(iso_value: str | None) -> str:
    """Format ISO timestamp as YYYY-MM-DD HH:MM:SS TZ in Pacific time (best-effort)."""
    dt = _parse_iso_datetime(iso_value)
    if not dt:
        return ''
    try:
        dt = dt.astimezone(_get_pacific_tzinfo())
        return dt.strftime('%Y-%m-%d %H:%M:%S %Z')
    except Exception:
        try:
            return dt.astimezone(timezone.utc).strftime(
                '%Y-%m-%d %H:%M:%S UTC'
            )
        except Exception:
            return ''


_LOGIN_AUDIT_LOCK = threading.Lock()
_RECENT_LOGIN_AUDIT_AT_BY_USER: dict[str, float] = {}
_RECENT_LOGIN_AUDIT_DEDUPE_SECONDS = int(
    os.getenv('LOGIN_AUDIT_DEDUPE_SECONDS', '45') or '45'
)
_LOGIN_AUDIT_VERIFICATION_DEDUPE_SECONDS = int(
    os.getenv('LOGIN_AUDIT_VERIFICATION_DEDUPE_SECONDS', '300') or '300'
)
_LOGIN_AUDIT_METRICS_DEDUPE_MINUTES = int(
    os.getenv('LOGIN_AUDIT_METRICS_DEDUPE_MINUTES', '5') or '5'
)
_LOGIN_AUDIT_ONBOARDING_WINDOW_MINUTES = int(
    os.getenv('LOGIN_AUDIT_ONBOARDING_WINDOW_MINUTES', '10') or '10'
)


def _login_audit_dedupe_window_seconds(login_method: str) -> float:
    """Return the dedupe window for a login method when deciding whether to record an audit row."""
    method = str(login_method or '').strip().lower()
    if method == 'email_verification':
        return float(
            max(
                _RECENT_LOGIN_AUDIT_DEDUPE_SECONDS,
                _LOGIN_AUDIT_VERIFICATION_DEDUPE_SECONDS
            )
        )
    return float(_RECENT_LOGIN_AUDIT_DEDUPE_SECONDS)


def _should_skip_login_audit(
        *,
        user_id: str,
        email: str,
        login_method: str
) -> bool:
    """Return True when a new login audit row would duplicate a very recent auth event."""
    user_id = str(user_id or '').strip()
    email = _normalize_email(email)
    dedupe_key = user_id or email
    if not dedupe_key:
        return False

    now = datetime.now(timezone.utc)
    now_mono = now.timestamp()
    window_seconds = _login_audit_dedupe_window_seconds(login_method)
    method = str(login_method or '').strip().lower()

    last_at = _RECENT_LOGIN_AUDIT_AT_BY_USER.get(dedupe_key)
    if last_at is not None and (now_mono - last_at) < window_seconds:
        return True

    existing_audit_id = session.get(LOGIN_AUDIT_SESSION_KEY)
    existing_login_at = session.get(LOGIN_AUDIT_SESSION_LOGIN_AT_KEY)
    if existing_audit_id and existing_login_at:
        existing_dt = _parse_iso_datetime(existing_login_at)
        if existing_dt is not None and (
                now - existing_dt).total_seconds() < window_seconds:
            return True

    def _matches_user(rec: dict) -> bool:
        rec_uid = str(rec.get('user_id') or '').strip()
        rec_email = _normalize_email(rec.get('email') or '')
        if user_id and rec_uid == user_id:
            return True
        if email and rec_email == email:
            return True
        return False

    def _recent_duplicate(
            rec_at: datetime | None,
            rec_method: str
    ) -> bool:
        if rec_at is None:
            return False
        elapsed = (now - rec_at).total_seconds()
        if elapsed < 0:
            return False
        rec_method = str(rec_method or '').strip().lower()
        onboarding_window_seconds = max(
            60,
            int(_LOGIN_AUDIT_ONBOARDING_WINDOW_MINUTES) * 60
        )
        if (
                method == 'password'
                and rec_method == 'email_verification'
                and elapsed < onboarding_window_seconds
        ):
            return True
        if elapsed >= window_seconds:
            return False
        if method == 'email_verification' and rec_method == 'email_verification':
            return True
        if method and method == rec_method:
            return True
        return False

    if user_id:
        try:
            prof = get_user_profile_azure(user_id) or {}
            last_login = _parse_iso_datetime(
                _coerce_datetime_iso(prof.get('last_login_at'))
            )
            last_method = str(
                prof.get('last_login_method') or ''
            ).strip().lower()
            if _recent_duplicate(last_login, last_method):
                return True
        except Exception:
            pass

    try:
        with _LOGIN_AUDIT_LOCK:
            store = _load_login_audit_store()
            sessions = store.get('sessions') if isinstance(
                store,
                dict
            ) else {}
            if isinstance(sessions, dict):
                for rec in sessions.values():
                    if not isinstance(rec, dict) or not _matches_user(rec):
                        continue
                    rec_at = _parse_iso_datetime(
                        _coerce_datetime_iso(rec.get('login_at'))
                    )
                    rec_method = str(
                        rec.get('login_method') or ''
                    ).strip().lower()
                    if _recent_duplicate(rec_at, rec_method):
                        return True
    except Exception:
        pass

    return False


def _auth_timeout_seconds() -> tuple[int | None, int | None]:
    """Return (idle_seconds, absolute_seconds) or (None, None) when disabled."""
    try:
        idle_min = int(AUTH_IDLE_TIMEOUT_MINUTES)
    except Exception:
        idle_min = 0
    try:
        abs_hours = int(AUTH_ABSOLUTE_TIMEOUT_HOURS)
    except Exception:
        abs_hours = 0

    idle_seconds = int(
        idle_min * 60
    ) if idle_min and idle_min > 0 else None
    absolute_seconds = int(
        abs_hours * 3600
    ) if abs_hours and abs_hours > 0 else None
    return idle_seconds, absolute_seconds


def _auth_set_session_times(
        *,
        start_iso: str | None = None,
        activity_iso: str | None = None
) -> None:
    """Persist auth session timestamps in the session (best-effort)."""
    try:
        if start_iso and not session.get(AUTH_SESSION_START_AT_KEY):
            session[AUTH_SESSION_START_AT_KEY] = str(start_iso)
        if activity_iso:
            session[AUTH_LAST_ACTIVITY_AT_KEY] = str(activity_iso)
    except Exception:
        return


def _auth_force_logout(*, reason: str) -> Response:
    """Log out the current user and redirect to login with an expiration reason."""
    try:
        # Close audit record if present.
        try:
            _audit_login_end()
        except Exception:
            pass

        # Flask-Login logout.
        try:
            logout_user()
        except Exception:
            pass

        # Preserve Flask-Login remember-cookie clearing semantics if set.
        remember_action = None
        try:
            remember_action = session.get('_remember')
        except Exception:
            remember_action = None

        # Clear our auth timestamps.
        try:
            session.pop(AUTH_SESSION_START_AT_KEY, None)
            session.pop(AUTH_LAST_ACTIVITY_AT_KEY, None)
        except Exception:
            pass

        if remember_action:
            try:
                session['_remember'] = remember_action
            except Exception:
                pass
    finally:
        pass

    # Avoid flash() because the login route clears flashes.
    return redirect(
        url_for(
            'login',
            tab='login',
            expired=str(reason or '').strip() or '1'
        )
    )


def _azure_login_audit_enabled() -> bool:
    """Return True if Azure Table Storage should be used for login auditing."""
    try:
        if (os.getenv('AZURE_STORAGE_CONNECTION_STRING') or '').strip():
            return True
        # Allow managed identity path primarily on Azure.
        if (os.getenv('AZURE_STORAGE_ACCOUNT') or '').strip() and (
                os.getenv('WEBSITE_INSTANCE_ID') or '').strip():
            return True
    except Exception:
        return False
    return False


def _get_login_audit_table_client(create_if_missing: bool = True):
    """Best-effort TableClient for login audit table."""
    connection_string = (
            os.getenv('AZURE_STORAGE_CONNECTION_STRING') or '').strip()
    account = (os.getenv('AZURE_STORAGE_ACCOUNT') or '').strip()
    if not connection_string and not account:
        raise ValueError('Azure storage not configured')

    if connection_string:
        service = TableServiceClient.from_connection_string(
            conn_str=connection_string
        )
    else:
        # Import lazily: azure.identity import can be slow on some Windows hosts.
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        service = TableServiceClient(
            endpoint=f"https://{account}.table.core.windows.net",
            credential=credential
        )

    table_client = service.get_table_client(AZURE_LOGIN_AUDIT_TABLE)
    if create_if_missing:
        try:
            table_client.create_table()
        except Exception:
            pass
    return table_client


def _azure_login_audit_upsert(entity: dict) -> bool:
    """Upsert a login audit entity to Azure (best-effort)."""
    try:
        payload = dict(entity or {})
        for key in ('login_at', 'last_activity_at', 'logout_at'):
            if key in payload and payload[key] is not None:
                payload[key] = _coerce_datetime_iso(payload[key])
        table_client = _get_login_audit_table_client(
            create_if_missing=True
        )
        table_client.upsert_entity(mode=UpdateMode.REPLACE, entity=payload)
        return True
    except Exception:
        logger.exception('Azure login audit upsert failed')
        return False


def _azure_login_audit_get(pk: str, rk: str) -> dict | None:
    try:
        table_client = _get_login_audit_table_client(
            create_if_missing=False
        )
        e = table_client.get_entity(partition_key=pk, row_key=rk)
        return dict(e) if e else None
    except Exception:
        return None


def _azure_login_audit_list(limit: int = 500) -> list[dict]:
    """List login audit sessions and return the most recent rows up to `limit`.

    Azure Table enumeration order is not guaranteed to match "newest first" for
    this use case, so we collect available rows, sort by login_at descending,
    then apply the limit.
    """
    out: list[dict] = []
    table_client = _get_login_audit_table_client(create_if_missing=False)
    try:
        for e in table_client.list_entities():
            if isinstance(e, dict):
                out.append(dict(e))
            else:
                try:
                    out.append(dict(e))
                except Exception:
                    continue
    except Exception:
        # Surface as empty and let caller fallback.
        return []
    try:
        out.sort(
            key=lambda r: (_parse_iso_datetime(
                (r or {}).get('login_at')
            ) or datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )
    except Exception:
        pass
    if limit:
        try:
            out = out[:max(0, int(limit))]
        except Exception:
            pass
    return out


def _table_safe_str(value: object, *, max_len: int = 1024) -> str:
    try:
        s = str(value or '')
    except Exception:
        s = ''
    s = s.replace('\x00', '')
    if max_len and len(s) > int(max_len):
        s = s[: int(max_len)]
    return s


def _best_effort_client_ip() -> str:
    """Best-effort client IP (supports Azure/App Service reverse proxy)."""
    try:
        xff = _table_safe_str(
            request.headers.get('X-Forwarded-For', ''),
            max_len=256
        )
        if xff:
            # XFF can be a comma-separated chain; keep the left-most.
            return (xff.split(',', 1)[0] or '').strip()
    except Exception:
        pass
    try:
        return _table_safe_str(
            getattr(request, 'remote_addr', ''),
            max_len=64
        )
    except Exception:
        return ''


_GEOIP_COUNTRY_SESSION_KEY = 'geoip_country'
_GEOIP_COUNTRY_AT_SESSION_KEY = 'geoip_country_at'


def _best_effort_country_code() -> str:
    """Best-effort 2-letter country code for the current request.

    Prefer edge/CDN headers when available; otherwise fall back to a GeoIP API lookup.
    Returns '' when unknown.
    """
    if not has_request_context():
        return ''

    # Manual override for testing / VPN edge-cases.
    try:
        if str(
                request.args.get('currency') or ''
        ).strip().lower() == 'inr':
            try:
                session[_GEOIP_COUNTRY_SESSION_KEY] = 'IN'
                session[_GEOIP_COUNTRY_AT_SESSION_KEY] = int(time.time())
                session.modified = True
            except Exception:
                pass
            return 'IN'
    except Exception:
        pass

    # Cached in session (avoid GeoIP roundtrips on every request).
    try:
        cached = str(
            session.get(_GEOIP_COUNTRY_SESSION_KEY) or ''
        ).strip().upper()
        cached_at = int(session.get(_GEOIP_COUNTRY_AT_SESSION_KEY) or 0)
        cache_hours = int(
            (os.getenv('GEOIP_CACHE_HOURS') or '24').strip() or '24'
        )
        if cached and cached_at and (time.time() - cached_at) < (
                max(1, cache_hours) * 3600):
            if len(cached) == 2 and cached.isalpha():
                return cached
    except Exception:
        pass

    # Header-based (Cloudflare/CloudFront/etc.)
    try:
        for hdr in ('CF-IPCountry', 'CloudFront-Viewer-Country',
                    'X-AppEngine-Country'):
            v = str(request.headers.get(hdr) or '').strip().upper()
            if len(v) == 2 and v.isalpha():
                try:
                    session[_GEOIP_COUNTRY_SESSION_KEY] = v
                    session[_GEOIP_COUNTRY_AT_SESSION_KEY] = int(
                        time.time()
                    )
                    session.modified = True
                except Exception:
                    pass
                return v
    except Exception:
        pass

    # GeoIP fallback (ipapi.co; no key). Best-effort and failure-tolerant.
    ip = ''
    try:
        ip = str(_best_effort_client_ip() or '').strip()
    except Exception:
        ip = ''
    if not ip:
        return ''
    try:
        ipa = ipaddress.ip_address(ip)
        if ipa.is_private or ipa.is_loopback or ipa.is_link_local or ipa.is_multicast or ipa.is_reserved:
            return ''
    except Exception:
        return ''

    try:
        timeout_seconds = float(
            (os.getenv('GEOIP_TIMEOUT_SECONDS') or '1.5').strip() or '1.5'
        )
    except Exception:
        timeout_seconds = 1.5

    try:
        resp = requests.get(
            f"https://ipapi.co/{ip}/json/",
            timeout=max(0.2, timeout_seconds),
            headers={"Accept": "application/json",
                     "User-Agent": "resumatic/geoip"},
        )
        data = resp.json() if getattr(resp, 'ok', False) else {}
        v = str(
            (data or {}).get('country') or (data or {}).get(
                'country_code'
            ) or ''
        ).strip().upper()
        if len(v) == 2 and v.isalpha():
            try:
                session[_GEOIP_COUNTRY_SESSION_KEY] = v
                session[_GEOIP_COUNTRY_AT_SESSION_KEY] = int(time.time())
                session.modified = True
            except Exception:
                pass
            return v
    except Exception:
        pass
    return ''


def _is_india_pricing_region() -> bool:
    try:
        return _best_effort_country_code() == 'IN'
    except Exception:
        return False


def _plans_price_display_context() -> dict:
    """Marketing copy for /plans cards. INR labels use PLANS_DISPLAY_* env vars when the visitor is in India."""
    base_usd = {
        'currency_mode': 'usd',
        'monthly_strong': '$10.95',
        'annual_strong': '$6.95',
        'annual_equiv': 'Equivalent to $6.95/month.',
        'monthly_pdf_main': '$10',
        'monthly_pdf_decimals': '.95 / month',
        'annual_pdf_main': '$6',
        'annual_pdf_decimals': '.95 / month',
        'note': '',
    }
    if not _is_india_pricing_region():
        return dict(base_usd)
    monthly = (os.getenv('PLANS_DISPLAY_MONTHLY_INR') or '').strip()
    annual_pm = (os.getenv(
        'PLANS_DISPLAY_ANNUAL_PER_MONTH_INR'
    ) or '').strip()
    if monthly and annual_pm:
        return {
            'currency_mode': 'inr',
            'monthly_strong': monthly,
            'annual_strong': annual_pm,
            'annual_equiv': f'Equivalent to {annual_pm}/month.',
            'monthly_pdf_main': monthly,
            'monthly_pdf_decimals': ' / month',
            'annual_pdf_main': annual_pm,
            'annual_pdf_decimals': ' / month',
            'note': '',
        }
    out = dict(base_usd)
    out['note'] = (
        'If you are in India, your card is charged in INR at checkout (exact amount is shown on Stripe).'
    )
    return out


def _azure_users_session_start(
        *,
        user_id: str,
        email: str,
        audit_id: str,
        login_at: str,
        login_method: str,
        row_key: str,
        login_audit_pk: str = '',
        login_audit_rk: str = ''
) -> None:
    """Record a login session row in the Azure Users table (best-effort).

    Writes:
    - MERGE into (PK=user_id, RK='profile') for convenient last-login fields
    - REPLACE into (PK=user_id, RK=<session row_key>) to create an append-only session record
    """
    try:
        # On login we can afford to ensure the table exists.
        table_client = get_users_table_client(create_if_missing=True)

        # Update profile with last-login markers (do not clobber existing profile fields).
        profile_patch = {
            'PartitionKey': str(user_id),
            'RowKey': 'profile',
            'last_login_at': str(login_at or ''),
            'last_login_method': _table_safe_str(login_method, max_len=64),
            'last_session_rowkey': _table_safe_str(row_key, max_len=128),
        }
        if email:
            profile_patch['email'] = _table_safe_str(email, max_len=254)
        try:
            table_client.upsert_entity(
                profile_patch,
                mode=UpdateMode.MERGE
            )
        except Exception:
            pass

        # Insert an append-only session row.
        user_agent = ''
        referer = ''
        try:
            user_agent = _table_safe_str(
                request.headers.get('User-Agent', ''),
                max_len=512
            )
            referer = _table_safe_str(
                request.headers.get('Referer', ''),
                max_len=512
            )
        except Exception:
            user_agent = ''
            referer = ''
        ip = _best_effort_client_ip()

        entity = {
            'PartitionKey': str(user_id),
            'RowKey': str(row_key),
            'record_type': 'session',
            'audit_id': _table_safe_str(audit_id, max_len=64),
            'email': _table_safe_str(email, max_len=254),
            'login_at': _table_safe_str(login_at, max_len=64),
            'last_activity_at': _table_safe_str(login_at, max_len=64),
            'logout_at': '',
            'login_method': _table_safe_str(login_method, max_len=64),
            'ip': _table_safe_str(ip, max_len=64),
            'user_agent': user_agent,
            'referer': referer,
        }
        if login_audit_pk:
            entity['login_audit_pk'] = _table_safe_str(
                login_audit_pk,
                max_len=16
            )
        if login_audit_rk:
            entity['login_audit_rk'] = _table_safe_str(
                login_audit_rk,
                max_len=128
            )

        table_client.upsert_entity(entity, mode=UpdateMode.REPLACE)
    except Exception:
        # Never block login on telemetry persistence.
        return


def _azure_users_session_activity(
        *,
        user_id: str,
        row_key: str,
        activity_at: str
) -> None:
    """Update last_activity_at for a session row (best-effort, MERGE)."""
    try:
        if not user_id or not row_key:
            return
        table_client = get_users_table_client(create_if_missing=False)
        patch = {
            'PartitionKey': str(user_id),
            'RowKey': str(row_key),
            'last_activity_at': _table_safe_str(activity_at, max_len=64),
        }
        table_client.upsert_entity(patch, mode=UpdateMode.MERGE)
    except Exception:
        return


def _azure_users_session_end(
        *,
        user_id: str,
        row_key: str,
        logout_at: str,
        duration_seconds: int | None
) -> None:
    """Close a session row in Users table (best-effort, MERGE)."""
    try:
        if not user_id or not row_key:
            return
        table_client = get_users_table_client(create_if_missing=False)
        patch = {
            'PartitionKey': str(user_id),
            'RowKey': str(row_key),
            'logout_at': _table_safe_str(logout_at, max_len=64),
            'last_activity_at': _table_safe_str(logout_at, max_len=64),
        }
        if duration_seconds is not None:
            try:
                patch['duration_seconds'] = int(duration_seconds)
            except Exception:
                pass
        table_client.upsert_entity(patch, mode=UpdateMode.MERGE)
    except Exception:
        return


def _audit_login_start(user: "User", login_method: str) -> None:
    """Create a login audit record and pin it to the session."""
    try:
        import uuid

        user_id = str(getattr(user, 'id', '') or '')
        email = _normalize_email(getattr(user, 'email', ''))

        if _should_skip_login_audit(
                user_id=user_id,
                email=email,
                login_method=login_method
        ):
            return

        now_mono = datetime.now(timezone.utc).timestamp()
        dedupe_key = user_id or email

        audit_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        login_at = now.isoformat()

        # Generate a per-login session RowKey for the Azure Users table (append-only per session).
        users_session_rk = f"session_{now.strftime('%Y%m%dT%H%M%S%f')}_{audit_id}"
        try:
            session[USERS_SESSION_ROWKEY_KEY] = users_session_rk
            session[USERS_SESSION_LOGIN_AT_KEY] = login_at
            session[USERS_SESSION_AUDIT_ID_KEY] = audit_id
        except Exception:
            pass

        # Initialize auth session timestamps (used for idle/absolute timeouts).
        _auth_set_session_times(start_iso=login_at, activity_iso=login_at)

        # Prefer Azure Table Storage when configured.
        if _azure_login_audit_enabled():
            pk = now.strftime('%Y%m')
            rk = f"{now.strftime('%Y%m%dT%H%M%S%f')}_{audit_id}"
            entity = {
                'PartitionKey': pk,
                'RowKey': rk,
                'audit_id': audit_id,
                'user_id': user_id,
                'email': email,
                'login_at': login_at,
                'last_activity_at': login_at,
                'logout_at': '',
                'login_method': str(login_method or '').strip() or '',
                # duration_seconds will be written on logout
            }
            # Also record this session in the Azure Users table (best-effort).
            try:
                _azure_users_session_start(
                    user_id=user_id,
                    email=email,
                    audit_id=audit_id,
                    login_at=login_at,
                    login_method=str(login_method or '').strip() or '',
                    row_key=users_session_rk,
                    login_audit_pk=pk,
                    login_audit_rk=rk,
                )
            except Exception:
                pass
            if _azure_login_audit_upsert(entity):
                session[LOGIN_AUDIT_SESSION_KEY] = audit_id
                session[LOGIN_AUDIT_SESSION_PK_KEY] = pk
                session[LOGIN_AUDIT_SESSION_RK_KEY] = rk
                session[LOGIN_AUDIT_SESSION_LOGIN_AT_KEY] = login_at
                session[LOGIN_AUDIT_LAST_ACTIVITY_AT_KEY] = login_at
                if dedupe_key:
                    _RECENT_LOGIN_AUDIT_AT_BY_USER[dedupe_key] = now_mono
                return

        # If Azure login audit isn't enabled, still try to record the session in Users table.
        try:
            _azure_users_session_start(
                user_id=user_id,
                email=email,
                audit_id=audit_id,
                login_at=login_at,
                login_method=str(login_method or '').strip() or '',
                row_key=users_session_rk,
            )
        except Exception:
            pass

        # Fallback: JSON file store.
        record = {
            'audit_id': audit_id,
            'user_id': user_id,
            'email': email,
            'login_at': login_at,
            'last_activity_at': login_at,
            'logout_at': None,
            'duration_seconds': None,
            'login_method': str(login_method or '').strip() or None,
        }

        with _LOGIN_AUDIT_LOCK:
            store = _load_login_audit_store()
            sessions = store.get('sessions')
            if not isinstance(sessions, dict):
                sessions = {}
            sessions[audit_id] = record
            store['sessions'] = sessions
            _save_login_audit_store(store)

        session[LOGIN_AUDIT_SESSION_KEY] = audit_id
        session[LOGIN_AUDIT_LAST_ACTIVITY_AT_KEY] = login_at
        if dedupe_key:
            _RECENT_LOGIN_AUDIT_AT_BY_USER[dedupe_key] = now_mono
    except Exception:
        logger.exception("Error starting login audit")


def _audit_login_activity(activity_iso: str) -> None:
    """Update the current login audit record's last activity (best-effort, throttled)."""
    try:
        audit_id = session.get(LOGIN_AUDIT_SESSION_KEY)
        if not audit_id:
            return

        now_dt = _parse_iso_datetime(activity_iso) or datetime.now(
            timezone.utc
        )

        # Throttle writes (in-session).
        try:
            last_write_dt = _parse_iso_datetime(
                session.get(LOGIN_AUDIT_LAST_ACTIVITY_WRITE_AT_KEY)
            )
        except Exception:
            last_write_dt = None
        if last_write_dt is not None:
            try:
                if (now_dt - last_write_dt).total_seconds() < float(
                        LOGIN_AUDIT_ACTIVITY_WRITE_THROTTLE_SECONDS
                ):
                    # Still update the in-memory session key for UI estimates.
                    session[LOGIN_AUDIT_LAST_ACTIVITY_AT_KEY] = str(
                        activity_iso
                    )
                    return
            except Exception:
                pass

        # Best-effort: also update the per-session row in the Azure Users table.
        try:
            uid = str(getattr(current_user, 'id', '') or '').strip()
            users_rk = str(
                session.get(USERS_SESSION_ROWKEY_KEY) or ''
            ).strip()
            if uid and users_rk:
                _azure_users_session_activity(
                    user_id=uid,
                    row_key=users_rk,
                    activity_at=str(activity_iso)
                )
        except Exception:
            pass

        # If this session has Azure PK/RK, update the Azure record.
        pk = str(session.get(LOGIN_AUDIT_SESSION_PK_KEY) or '').strip()
        rk = str(session.get(LOGIN_AUDIT_SESSION_RK_KEY) or '').strip()
        if pk and rk and _azure_login_audit_enabled():
            existing = _azure_login_audit_get(pk, rk) or {}
            merged = dict(existing) if isinstance(existing, dict) else {}
            merged.update(
                {
                    'PartitionKey': pk,
                    'RowKey': rk,
                    'audit_id': str(audit_id),
                    'last_activity_at': str(activity_iso),
                }
            )
            # Ensure required fields exist (Azure upsert replaces entity).
            merged.setdefault(
                'login_at',
                str(
                    session.get(LOGIN_AUDIT_SESSION_LOGIN_AT_KEY) or (
                        merged.get('login_at') if isinstance(
                            merged,
                            dict
                        ) else '') or ''
                )
            )
            merged.setdefault(
                'logout_at',
                (merged.get('logout_at') if isinstance(
                    merged,
                    dict
                ) else '') or ''
            )
            merged.setdefault(
                'email',
                (merged.get('email') if isinstance(
                    merged,
                    dict
                ) else '') or ''
            )
            merged.setdefault(
                'user_id',
                (merged.get('user_id') if isinstance(
                    merged,
                    dict
                ) else '') or ''
            )
            merged.setdefault(
                'login_method',
                (merged.get('login_method') if isinstance(
                    merged,
                    dict
                ) else '') or ''
            )
            _azure_login_audit_upsert(merged)

            session[LOGIN_AUDIT_LAST_ACTIVITY_AT_KEY] = str(activity_iso)
            session[
                LOGIN_AUDIT_LAST_ACTIVITY_WRITE_AT_KEY] = now_dt.isoformat()
            return

        # JSON file store update.
        with _LOGIN_AUDIT_LOCK:
            store = _load_login_audit_store()
            sessions = store.get('sessions')
            if not isinstance(sessions, dict):
                return
            rec = sessions.get(audit_id)
            if not isinstance(rec, dict):
                return
            # Don't touch closed sessions.
            if rec.get('logout_at'):
                return
            rec['last_activity_at'] = str(activity_iso)
            sessions[audit_id] = rec
            store['sessions'] = sessions
            _save_login_audit_store(store)

        session[LOGIN_AUDIT_LAST_ACTIVITY_AT_KEY] = str(activity_iso)
        session[
            LOGIN_AUDIT_LAST_ACTIVITY_WRITE_AT_KEY] = now_dt.isoformat()
    except Exception:
        # Swallow to avoid impacting request handling.
        return


@app.before_request
def _enforce_auth_session_timeouts():
    """Best-effort idle + absolute session timeout enforcement for authenticated users."""
    try:
        if not current_user.is_authenticated:
            return None

        # Don't treat static assets as activity.
        endpoint = str(getattr(request, 'endpoint', '') or '')
        if endpoint.startswith('static'):
            return None

        idle_seconds, absolute_seconds = _auth_timeout_seconds()
        if not idle_seconds and not absolute_seconds:
            return None

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        start_dt = _parse_iso_datetime(
            session.get(AUTH_SESSION_START_AT_KEY)
        )
        last_dt = _parse_iso_datetime(
            session.get(AUTH_LAST_ACTIVITY_AT_KEY)
        )

        # If missing, initialize and allow the request (avoid surprising logouts).
        if start_dt is None:
            _auth_set_session_times(start_iso=now_iso)
            start_dt = now
        if last_dt is None:
            session[AUTH_LAST_ACTIVITY_AT_KEY] = now_iso
            last_dt = now

        if absolute_seconds is not None and start_dt is not None:
            if (now - start_dt).total_seconds() > float(absolute_seconds):
                return _auth_force_logout(reason='absolute')

        if idle_seconds is not None and last_dt is not None:
            if (now - last_dt).total_seconds() > float(idle_seconds):
                return _auth_force_logout(reason='idle')

        # Update last activity for this authenticated request.
        session[AUTH_LAST_ACTIVITY_AT_KEY] = now_iso
        # Persist last activity to the login audit store for admin visibility.
        try:
            _audit_login_activity(now_iso)
        except Exception:
            pass
    except Exception:
        return None
    return None


def _audit_login_end() -> None:
    """Close the current session's login audit record (best-effort)."""
    try:
        audit_id = session.get(LOGIN_AUDIT_SESSION_KEY)
        if not audit_id:
            return

        # If this session has Azure PK/RK, close the Azure record.
        pk = str(session.get(LOGIN_AUDIT_SESSION_PK_KEY) or '').strip()
        rk = str(session.get(LOGIN_AUDIT_SESSION_RK_KEY) or '').strip()
        login_at_iso = str(
            session.get(LOGIN_AUDIT_SESSION_LOGIN_AT_KEY) or ''
        ).strip() or None
        if pk and rk and _azure_login_audit_enabled():
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()

            start_dt = _parse_iso_datetime(login_at_iso)
            if start_dt is None:
                # Best-effort: load from Azure if session data missing.
                existing = _azure_login_audit_get(pk, rk)
                start_dt = _parse_iso_datetime(
                    (existing or {}).get('login_at')
                )

            duration = int(
                max(0, (now - start_dt).total_seconds())
            ) if start_dt is not None else None
            entity = {
                'PartitionKey': pk,
                'RowKey': rk,
                'audit_id': str(audit_id),
                'last_activity_at': now_iso,
                'logout_at': now_iso,
            }
            if duration is not None:
                entity['duration_seconds'] = int(duration)

            # Upsert replaces the entity; include required fields we want preserved.
            existing = _azure_login_audit_get(pk, rk) or {}
            # Merge: prefer existing values for non-updated fields.
            merged = dict(existing)
            merged.update(entity)
            # Ensure minimal required fields exist.
            merged.setdefault('audit_id', str(audit_id))
            merged.setdefault(
                'login_at',
                (existing.get('login_at') if isinstance(
                    existing,
                    dict
                ) else None) or (login_at_iso or '')
            )
            merged.setdefault(
                'email',
                (existing.get('email') if isinstance(
                    existing,
                    dict
                ) else None) or ''
            )
            merged.setdefault(
                'user_id',
                (existing.get('user_id') if isinstance(
                    existing,
                    dict
                ) else None) or ''
            )
            merged.setdefault(
                'login_method',
                (existing.get('login_method') if isinstance(
                    existing,
                    dict
                ) else None) or ''
            )

            _azure_login_audit_upsert(merged)

            # Also close the per-session row in the Azure Users table (best-effort).
            try:
                uid = str(getattr(current_user, 'id', '') or '').strip()
                users_rk = str(
                    session.get(USERS_SESSION_ROWKEY_KEY) or ''
                ).strip()
                if uid and users_rk:
                    _azure_users_session_end(
                        user_id=uid,
                        row_key=users_rk,
                        logout_at=now_iso,
                        duration_seconds=duration
                    )
            except Exception:
                pass

            # Clear session keys regardless (avoid leaking state).
            session.pop(LOGIN_AUDIT_SESSION_KEY, None)
            session.pop(LOGIN_AUDIT_SESSION_PK_KEY, None)
            session.pop(LOGIN_AUDIT_SESSION_RK_KEY, None)
            session.pop(LOGIN_AUDIT_SESSION_LOGIN_AT_KEY, None)
            session.pop(LOGIN_AUDIT_LAST_ACTIVITY_AT_KEY, None)
            session.pop(LOGIN_AUDIT_LAST_ACTIVITY_WRITE_AT_KEY, None)
            session.pop(USERS_SESSION_ROWKEY_KEY, None)
            session.pop(USERS_SESSION_LOGIN_AT_KEY, None)
            session.pop(USERS_SESSION_AUDIT_ID_KEY, None)
            return

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        with _LOGIN_AUDIT_LOCK:
            store = _load_login_audit_store()
            sessions = store.get('sessions')
            if not isinstance(sessions, dict):
                return
            rec = sessions.get(audit_id)
            if not isinstance(rec, dict):
                return
            if rec.get('logout_at'):
                return

            start_dt = _parse_iso_datetime(rec.get('login_at'))
            if start_dt is not None:
                duration = int(max(0, (now - start_dt).total_seconds()))
            else:
                duration = None

            rec['logout_at'] = now_iso
            rec['last_activity_at'] = now_iso
            rec['duration_seconds'] = duration
            sessions[audit_id] = rec
            store['sessions'] = sessions
            _save_login_audit_store(store)

        # Best-effort: close the per-session row in the Azure Users table even when audit is file-based.
        try:
            uid = str(getattr(current_user, 'id', '') or '').strip()
            users_rk = str(
                session.get(USERS_SESSION_ROWKEY_KEY) or ''
            ).strip()
            if uid and users_rk:
                _azure_users_session_end(
                    user_id=uid,
                    row_key=users_rk,
                    logout_at=now_iso,
                    duration_seconds=duration
                )
        except Exception:
            pass

        session.pop(LOGIN_AUDIT_SESSION_KEY, None)
        session.pop(LOGIN_AUDIT_LAST_ACTIVITY_AT_KEY, None)
        session.pop(LOGIN_AUDIT_LAST_ACTIVITY_WRITE_AT_KEY, None)
        session.pop(USERS_SESSION_ROWKEY_KEY, None)
        session.pop(USERS_SESSION_LOGIN_AT_KEY, None)
        session.pop(USERS_SESSION_AUDIT_ID_KEY, None)
    except Exception:
        logger.exception("Error ending login audit")


# Load existing users on startup
users = load_users()
try:
    logger.info("Loaded %s users from persistent storage", len(users))
except Exception:
    # Avoid crashing at import-time on Windows consoles that can't encode emojis/unicode.
    pass


@login_manager.user_loader
def load_user(user_id):
    cached_user = users.get(str(user_id))
    if cached_user:
        return cached_user

    try:
        prof = get_user_profile_azure(str(user_id)) or {}
        if not prof or not prof.get('email'):
            return None
        record = dict(prof)
        record['id'] = str(user_id)
        cached_user = User.from_dict(record)
        users[str(user_id)] = cached_user
        return cached_user
    except Exception:
        return None


@app.route("/login", methods=['GET', 'POST'])
def login():
    def _render_login(*, active_tab: str | None = None):
        """Render the combined Login/Sign-up page with anti-caching headers."""
        resp = make_response(
            render_template("login.html", active_tab=active_tab)
        )
        # Auth pages should not be cached; caching can cause stale JS/UI behavior.
        resp.headers[
            'Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp

    def _desired_active_tab() -> str:
        """Return which auth tab should be shown initially on the login page."""
        try:
            tab = str(request.args.get('tab') or '').strip().lower()
        except Exception:
            tab = ''
        if tab in (
                'register', 'signup', 'sign-up', 'create',
                'create-account'):
            return 'register'
        return 'login'

    if current_user.is_authenticated:
        if _requires_email_verification(current_user):
            return redirect(
                url_for(
                    'verify_email',
                    email=getattr(current_user, 'email', '')
                )
            )
        # If already logged in and a next is provided, honor it.
        _set_auth_next_from_request()
        nxt = _pop_auth_next()
        return redirect(nxt or url_for('index'))

    # Clear any lingering flash messages
    session.pop('_flashes', None)

    # Capture intended return URL for post-auth redirect
    _set_auth_next_from_request()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'login':
            # Handle email/password login
            email = _normalize_email(request.form.get('email', ''))
            password = request.form.get('password', '')

            if not email or not password:
                flash('Please enter both email and password.', 'danger')
                return _render_login(active_tab='login')

            user = _get_auth_user_by_email(email)

            # If the user exists but has no password, they likely signed up via Google/Facebook.
            if user and not getattr(user, 'password_hash', None):
                flash(
                    'This email is linked to a Google/Facebook sign-in. Use that sign-in, or click “Forgot password” to set a password for this email.',
                    'danger'
                )
                return _render_login(active_tab='login')

            if user and user.password_hash and user.check_password(
                    password
            ):
                if _requires_email_verification(user):
                    flash(
                        'Please verify your email before logging in. We can resend the verification email below.',
                        'danger'
                    )
                    return redirect(
                        url_for('verify_email', email=user.email)
                    )

                login_user(user)
                _audit_login_start(user, login_method='password')

                # Best-effort reliability: if the welcome email failed earlier (e.g. SMTP misconfig),
                # retry once on the first successful login after verification.
                try:
                    if (
                            _normalize_email(getattr(user, 'email', ''))
                            and bool(getattr(user, 'email_verified', True))
                            and not getattr(
                        user,
                        'welcome_email_sent_at',
                        None
                    )
                    ):
                        logger.info(
                            "Retrying welcome email on login for %s",
                            _normalize_email(getattr(user, 'email', '')),
                        )
                        sent_ok = send_welcome_email(
                            user.email,
                            getattr(user, 'name', '') or ''
                        )
                        if sent_ok:
                            user.welcome_email_sent_at = datetime.now(
                                timezone.utc
                            ).isoformat()
                            add_user(user)
                        else:
                            logger.warning(
                                "Welcome email retry not sent on login for %s",
                                _normalize_email(
                                    getattr(user, 'email', '')
                                ),
                            )
                except Exception:
                    logger.exception(
                        "Unexpected error during welcome-email retry on login"
                    )

                # Save pending revision if it exists
                pending = session.pop('pending_revision', None)
                if pending:
                    import uuid

                    try:
                        save_resume_revision(
                            user.id,
                            str(uuid.uuid4()),
                            pending['revised_resume'],
                            feedback=pending.get('feedback'),
                            original_resume=pending.get('original_resume'),
                            job_description=pending.get('job_description')
                        )
                    except FreeTierLimitReached:
                        flash(
                            "You've reached the free tier limit (1 revision). Upgrade to save unlimited revisions.",
                            "danger"
                        )
                    except Exception:
                        pass
                flash('You have been successfully logged in!', 'success')
                nxt = _pop_auth_next()
                return redirect(nxt or url_for('my_revisions'))
            else:
                flash('Invalid email or password.', 'danger')
                return _render_login(active_tab='login')

        elif action == 'register':
            # Handle email/password registration
            name = (request.form.get('name', '') or '').strip()
            email = _normalize_email(request.form.get('email', ''))
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')

            # Validation
            if not email or not password:
                flash('Please enter an email and password.', 'danger')
                return _render_login(active_tab='register')

            if len(password) < 8:
                flash(
                    'Password must be at least 8 characters long.',
                    'danger'
                )
                return _render_login(active_tab='register')

            if password != confirm_password:
                flash('Passwords do not match.', 'danger')
                return _render_login(active_tab='register')

            # Check if email already exists
            existing_user = _get_auth_user_by_email(email)
            if existing_user:
                if not getattr(existing_user, 'password_hash', None):
                    flash(
                        'An account with this email already exists via Google/Facebook sign-in. Use that sign-in, or click “Forgot password” to set a password for this email.',
                        'danger'
                    )
                else:
                    flash(
                        'An account with this email already exists. Please login instead.',
                        'danger'
                    )
                return _render_login(active_tab='register')

            # Create new user (requires email verification)
            import uuid

            user_id = f"email_{uuid.uuid4().hex[:16]}"
            user = User(
                user_id,
                name,
                email,
                is_new=True,
                email_verified=False
            )
            user.set_password(password)
            add_user(user)

            # Marketing attribution: record the signup source/ref/utm (best-effort)
            try:
                _append_marketing_signup_csv(
                    user,
                    signup_method='email_password'
                )
            except Exception:
                pass
            try:
                analytics.track_conversion(session, "signup")
            except Exception:
                pass

            # Persist profile to Azure Users table
            try:
                upsert_user_profile_azure(user)
            except Exception:
                pass

            # Send verification email
            token = generate_email_verification_token(user)
            sent_ok = send_email_verification_email(
                user.email,
                token,
                user.name,
                next_url=str(
                    session.get('auth_next') or ''
                ).strip() or None,
            )
            user.email_verification_sent_at = datetime.now(
                timezone.utc
            ).isoformat()
            add_user(user)  # persist sent timestamp + verified flag

            if sent_ok:
                flash(
                    'Account created! Please click verification link sent to your email address to activate account.',
                    'success'
                )
            else:
                flash(
                    'Account created, but we could not send a verification email. Please try resending below or contact support.',
                    'danger'
                )

            nxt = str(session.get('auth_next') or '').strip()
            if nxt and _is_safe_next_url(nxt):
                return redirect(
                    url_for('verify_email', email=user.email, next=nxt)
                )
            return redirect(url_for('verify_email', email=user.email))

    return _render_login(active_tab=_desired_active_tab())


@app.route('/verify-email')
def verify_email():
    """Show verification instructions + resend form."""
    _set_auth_next_from_request()
    email = (request.args.get('email') or '').strip().lower()
    next_url = str(session.get('auth_next') or '').strip()
    return render_template(
        'verify_email.html',
        email=email,
        next_url=next_url
    )


@app.route('/verify-email/<token>')
def verify_email_token(token):
    """Verify email token, mark user verified, then log them in."""
    _set_auth_next_from_request()
    # Local-only debug/testing override: allow forcing a welcome resend.
    try:
        _force_resend_welcome = (
                (not _ON_AZURE)
                and str(
            request.args.get('resend_welcome', '') or ''
        ).strip().lower() in ('1', 'true', 'yes', 'on')
        )
    except Exception:
        _force_resend_welcome = False

    payload = confirm_email_verification_token(
        token,
        max_age_seconds=EMAIL_VERIFY_TOKEN_EXPIRY_HOURS * 3600
    )
    if not payload:
        flash(
            'This verification link is invalid or has expired. Please request a new one.',
            'danger'
        )
        return redirect(url_for('verify_email'))

    user_id = str(payload.get('user_id') or '').strip()
    email = str(payload.get('email') or '').strip().lower()
    user = users.get(user_id)

    if not user or (str(
            getattr(user, 'email', '') or ''
    ).strip().lower() != email):
        flash(
            'We could not verify that account. Please request a new verification email.',
            'danger'
        )
        return redirect(url_for('verify_email', email=email))

    # Diagnostics: prove the handler is running + show gate values.
    try:
        logging.getLogger().info(
            "verify_email_token: entered (user_id=%s email=%s email_verified=%s welcome_email_sent_at=%s)",
            str(getattr(user, 'id', '') or ''),
            _normalize_email(getattr(user, 'email', '')),
            getattr(user, 'email_verified', None),
            getattr(user, 'welcome_email_sent_at', None),
        )
        if not _ON_AZURE:
            print(
                "[verify_email_token] entered user_id=%s email=%s verified=%s welcome_email_sent_at=%s"
                % (
                    str(getattr(user, 'id', '') or ''),
                    _normalize_email(getattr(user, 'email', '')),
                    str(getattr(user, 'email_verified', None)),
                    str(getattr(user, 'welcome_email_sent_at', None)),
                )
            )
    except Exception:
        pass

    was_already_verified = bool(getattr(user, 'email_verified', True))

    # If already verified, just proceed without creating another login audit row.
    if not was_already_verified:
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc).isoformat()
        add_user(user)

    # Send a welcome email once, after verification succeeds.
    # Local debug: allow forcing resend with `?resend_welcome=1`.
    try:
        if _normalize_email(getattr(user, 'email', '')) and (
                _force_resend_welcome or not getattr(
            user,
            'welcome_email_sent_at',
            None
        )):
            logger.info(
                "Attempting welcome email after verification for %s (force_resend=%s)",
                _normalize_email(getattr(user, 'email', '')),
                _force_resend_welcome,
            )
            try:
                logging.getLogger().info(
                    "verify_email_token: welcome gate passed for %s (force_resend=%s)",
                    _normalize_email(getattr(user, 'email', '')),
                    _force_resend_welcome,
                )
                if not _ON_AZURE:
                    print(
                        f"[verify_email_token] welcome gate passed for {_normalize_email(getattr(user, 'email', ''))} force_resend={_force_resend_welcome}"
                    )
            except Exception:
                pass
            sent_ok = send_welcome_email(
                user.email,
                getattr(user, 'name', '') or ''
            )
            if sent_ok:
                user.welcome_email_sent_at = datetime.now(
                    timezone.utc
                ).isoformat()
                add_user(user)
            else:
                logger.warning(
                    "Welcome email not sent after verification for %s",
                    _normalize_email(getattr(user, 'email', '')),
                )
        else:
            try:
                logging.getLogger().info(
                    "verify_email_token: welcome gate SKIPPED (email=%s welcome_email_sent_at=%s)",
                    _normalize_email(getattr(user, 'email', '')),
                    getattr(user, 'welcome_email_sent_at', None),
                )
                if not _ON_AZURE:
                    print(
                        f"[verify_email_token] welcome gate skipped email={_normalize_email(getattr(user, 'email', ''))} welcome_email_sent_at={getattr(user, 'welcome_email_sent_at', None)}"
                    )
            except Exception:
                pass
    except Exception:
        logger.exception(
            "Unexpected error during welcome-email attempt after verification"
        )

    login_user(user)
    if not was_already_verified:
        _audit_login_start(user, login_method='email_verification')

    # Save pending revision if it exists
    pending = session.pop('pending_revision', None)
    if pending:
        import uuid

        try:
            save_resume_revision(
                user.id,
                str(uuid.uuid4()),
                pending['revised_resume'],
                feedback=pending.get('feedback'),
                original_resume=pending.get('original_resume'),
                job_description=pending.get('job_description')
            )
        except FreeTierLimitReached:
            flash(
                "You've reached the free tier limit (1 revision). Upgrade to save unlimited revisions.",
                "danger"
            )
        except Exception:
            pass

    if was_already_verified:
        flash(
            'This email is already verified. You are now logged in.',
            'success'
        )
    else:
        flash(
            'Email verified successfully! You can now use your account.',
            'success'
        )
    nxt = _pop_auth_next()
    return redirect(nxt or url_for('my_revisions'))


@app.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend verification email for an email/password account."""
    email = (request.form.get('email') or '').strip().lower()
    try:
        nxt = (request.form.get('next') or '').strip()
        if nxt and _is_safe_next_url(nxt):
            session['auth_next'] = nxt
    except Exception:
        pass
    if not email:
        flash('Please enter your email address.', 'danger')
        return redirect(url_for('verify_email'))

    # Find user by email
    user = None
    for _, u in users.items():
        if str(getattr(u, 'email', '') or '').strip().lower() == email:
            user = u
            break

    # Always show a generic message to avoid user enumeration.
    generic_msg = 'If an account exists with that email, a verification link has been sent.'

    if not user or not getattr(user, 'password_hash', None):
        flash(generic_msg, 'success')
        return redirect(url_for('verify_email', email=email))

    if getattr(user, 'email_verified', True):
        flash('That email is already verified. You can log in.', 'success')
        return redirect(url_for('login'))

    token = generate_email_verification_token(user)
    sent_ok = send_email_verification_email(
        user.email,
        token,
        user.name,
        next_url=str(session.get('auth_next') or '').strip() or None
    )
    user.email_verification_sent_at = datetime.now(
        timezone.utc
    ).isoformat()
    add_user(user)

    flash(
        generic_msg if sent_ok else 'We could not send a verification email right now. Please try again later.',
        'success' if sent_ok else 'danger'
    )
    return redirect(url_for('verify_email', email=email))


# Password Reset Functions
def load_reset_tokens():
    """Load reset tokens from JSON file"""
    try:
        if os.path.exists(RESET_TOKENS_FILE):
            with open(RESET_TOKENS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading reset tokens: {e}")
        return {}


def save_reset_tokens(tokens):
    """Save reset tokens to JSON file"""
    try:
        with open(RESET_TOKENS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tokens, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving reset tokens: {e}")


def generate_reset_token():
    """Generate a secure random token for password reset"""
    import secrets

    return secrets.token_urlsafe(32)


def send_password_reset_email(email, token, user_name):
    """Send password reset email to user"""
    try:
        _load_email_config_if_missing()
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        auth_email = (
                os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip(
            '"'
        ).strip("'")
        auth_password = (os.getenv(
            'NEWSLETTER_PASSWORD',
            ''
        ) or '').strip().strip('"').strip("'").replace(' ', '')

        if not auth_email or not auth_password:
            raise ValueError(
                'Email credentials not configured. Set NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD.'
            )

        # Generate reset URL
        reset_url = url_for('reset_password', token=token, _external=True)

        # Create email
        subject = 'Reset Your Password - ResumaticAI'
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2563eb;">Reset Your Password</h2>
                <p>Hello {user_name},</p>
                <p>We received a request to reset your password for your ResumaticAI account.</p>
                <p>Click the button below to reset your password:</p>
                <div style="margin: 30px 0;">
                    <a href="{reset_url}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #666;">{reset_url}</p>
                <p>This link will expire in 24 hours.</p>
                <p>If you didn't request a password reset, please ignore this email.</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #666; font-size: 12px;">ResumaticAI Team</p>
            </div>
        </body>
        </html>
        """

        text_body = f"""
Reset Your Password - ResumaticAI

Hello {user_name},

We received a request to reset your password for your ResumaticAI account.

Click the link below to reset your password:
{reset_url}

This link will expire in 24 hours.

If you didn't request a password reset, please ignore this email.

ResumaticAI Team
        """

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"ResumaticAI <{auth_email}>"
        msg['To'] = email

        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(auth_email, auth_password)
        server.send_message(msg)
        server.quit()

        logger.info(f"Password reset email sent to {email}")
        return True
    except Exception as e:
        logger.exception("Error sending password reset email")
        return False


@app.route("/forgot-password", methods=['GET', 'POST'])
def forgot_password():
    """Handle forgot password requests"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = _normalize_email(request.form.get('email', ''))

        if not email:
            flash('Please enter your email address.', 'danger')
            return render_template("forgot_password.html")

        user = _get_auth_user_by_email(email)
        if not user:
            prof = _find_azure_user_profile_by_email(email)
            if prof:
                record = dict(prof)
                record['id'] = str(
                    record.get('PartitionKey') or record.get('id') or ''
                ).strip()
                if record['id']:
                    try:
                        user = User.from_dict(record)
                    except Exception:
                        user = None

        # Redirect back with a generic success indicator (security: don't reveal if email exists)

        if user and _normalize_email(
                getattr(user, 'email', '')
        ):  # Send for any account with a reachable email
            # Generate reset token
            token = generate_reset_token()
            expiry_time = datetime.now(timezone.utc).timestamp() + (
                    RESET_TOKEN_EXPIRY_HOURS * 3600)

            # Save token
            tokens = load_reset_tokens()
            tokens[token] = {
                'user_id': user.id,
                'email': user.email,
                'expires_at': expiry_time
            }
            save_reset_tokens(tokens)

            # Send email
            send_password_reset_email(user.email, token, user.name)

        return redirect(url_for('login', tab='login', reset_sent='1'))

    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=['GET', 'POST'])
def reset_password(token):
    """Handle password reset with token"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    # Load tokens
    tokens = load_reset_tokens()

    if token not in tokens:
        flash(
            'Invalid or expired reset link. Please request a new password reset.',
            'danger'
        )
        return redirect(url_for('forgot_password'))

    token_data = tokens[token]
    current_time = datetime.now(timezone.utc).timestamp()

    # Check if token expired
    if current_time > token_data['expires_at']:
        # Remove expired token
        del tokens[token]
        save_reset_tokens(tokens)
        flash(
            'This reset link has expired. Please request a new password reset.',
            'danger'
        )
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        if not password or not confirm_password:
            flash('Please fill in both password fields.', 'danger')
            return render_template(
                "reset_password.html",
                token=token,
                valid=True
            )

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template(
                "reset_password.html",
                token=token,
                valid=True
            )

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template(
                "reset_password.html",
                token=token,
                valid=True
            )

        # Get user and update password
        user_id = token_data['user_id']
        user = users.get(user_id)
        if not user:
            try:
                prof = get_user_profile_azure(user_id) or {}
                if prof and prof.get('email'):
                    record = dict(prof)
                    record['id'] = str(user_id)
                    user = User.from_dict(record)
            except Exception:
                user = None

        if user:
            user.set_password(password)
            add_user(user)  # Save updated password

            # Remove used token
            del tokens[token]
            save_reset_tokens(tokens)

            flash(
                'Your password has been reset successfully! Please login with your new password.',
                'success'
            )
            return redirect(url_for('login'))
        else:
            flash('User not found. Please contact support.', 'danger')
            return redirect(url_for('login'))

    return render_template("reset_password.html", token=token, valid=True)


@app.route("/logout")
@login_required
def logout():
    _audit_login_end()
    # Clear any OAuth tokens or state
    session.pop('state', None)
    session.pop('google_oauth_token', None)
    session.pop('facebook_oauth_token', None)
    session.pop('pending_revision', None)
    # Clear full session
    session.clear()
    # Log out the user
    logout_user()
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('index'))


def _oauth_ssl_verify_setting():
    """Return requests/google-auth verify= value for local dev SSL issues."""
    insecure_ssl = str(
        os.getenv('LOCAL_DEV_INSECURE_SSL', '') or ''
    ).strip().lower()
    if (not _ON_AZURE) and insecure_ssl in ('1', 'true', 'yes', 'on'):
        return False
    # truststore patches ssl.SSLContext at import; use default verification (True).
    return True


def _apply_oauth_ssl_verify(flow) -> None:
    """Ensure OAuth token exchange uses patched SSL verification."""
    try:
        _ensure_local_truststore_ssl()
        flow.oauth2session.verify = _oauth_ssl_verify_setting()
    except Exception:
        pass


@app.route("/login/google")
def google_login():
    _ensure_local_truststore_ssl()
    # Clear any lingering flash messages
    session.pop('_flashes', None)

    if current_user.is_authenticated:
        return redirect(url_for('index'))

    # Capture intended return URL for post-auth redirect
    _set_auth_next_from_request()

    if USE_ENV_CREDENTIALS:
        # Use environment variables for credentials
        from google_auth_oauthlib.flow import Flow

        client_config = {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": [
                    url_for("google_callback", _external=True)]
            }
        }
        flow = Flow.from_client_config(
            client_config,
            scopes=GOOGLE_SCOPES,
            redirect_uri=url_for("google_callback", _external=True)
        )
    else:
        # Use file-based credentials
        flow = Flow.from_client_secrets_file(
            GOOGLE_CLIENT_SECRET_FILE,
            scopes=GOOGLE_SCOPES,
            redirect_uri=url_for("google_callback", _external=True)
        )

    _apply_oauth_ssl_verify(flow)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account"  # 👈 This line is important
    )
    session["state"] = state
    session.modified = True
    return redirect(auth_url)


# Google OAuth Callback
@app.route("/login/google/authorized")
def google_callback():
    _ensure_local_truststore_ssl()
    if current_user.is_authenticated:
        nxt = _pop_auth_next()
        return redirect(nxt or url_for('my_revisions'))

    oauth_state = str(session.pop("state", None) or "").strip()
    if not oauth_state:
        flash(
            "Your sign-in session expired. Please try Google sign-in again.",
            "danger"
        )
        return redirect(url_for("login"))

    try:
        if USE_ENV_CREDENTIALS:
            client_config = {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": [
                        url_for("google_callback", _external=True)]
                }
            }
            flow = Flow.from_client_config(
                client_config,
                scopes=GOOGLE_SCOPES,
                state=oauth_state,
                redirect_uri=url_for("google_callback", _external=True)
            )
        else:
            flow = Flow.from_client_secrets_file(
                GOOGLE_CLIENT_SECRET_FILE,
                scopes=GOOGLE_SCOPES,
                state=oauth_state,
                redirect_uri=url_for("google_callback", _external=True)
            )

        _apply_oauth_ssl_verify(flow)
        insecure_ssl = str(
            os.getenv('LOCAL_DEV_INSECURE_SSL', '') or ''
        ).strip().lower()
        if (not _ON_AZURE) and insecure_ssl in ('1', 'true', 'yes', 'on'):
            flow.oauth2session.verify = False

        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials

        import time

        _ensure_local_truststore_ssl()
        google_request = google.auth.transport.requests.Request()
        try:
            google_request.session.verify = _oauth_ssl_verify_setting()
        except Exception:
            pass
        max_retries = 3
        user_info = None
        for attempt in range(max_retries):
            try:
                user_info = google.oauth2.id_token.verify_oauth2_token(
                    credentials.id_token,
                    google_request,
                    clock_skew_in_seconds=30,
                )
                break
            except google.auth.exceptions.InvalidValue as e:
                if "Token used too early" in str(
                        e
                ) and attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                raise

        user_id = user_info["sub"]
        user, is_new = _resolve_oauth_user(
            user_id,
            user_info["name"],
            user_info.get("email", "")
        )
        add_user(user)
        try:
            if is_new:
                _append_marketing_signup_csv(
                    user,
                    signup_method='google_oauth'
                )
                analytics.track_conversion(session, "signup")
        except Exception:
            pass
        try:
            if is_new and _normalize_email(
                    getattr(user, 'email', '')
            ) and not getattr(user, 'welcome_email_sent_at', None):
                sent_ok = send_welcome_email(
                    user.email,
                    getattr(user, 'name', '') or ''
                )
                if sent_ok:
                    user.welcome_email_sent_at = datetime.now(
                        timezone.utc
                    ).isoformat()
                    add_user(user)
        except Exception:
            pass
        try:
            if is_new and str(user_id).isdigit():
                _append_google_signup_csv(
                    user.id,
                    user.name,
                    user.email,
                    user.created_at
                )
        except Exception:
            pass
        try:
            upsert_user_profile_azure(user)
        except Exception:
            pass
        login_user(user)
        _audit_login_start(user, login_method='google_oauth')
        pending = session.pop('pending_revision', None)
        if pending:
            import uuid

            try:
                save_resume_revision(
                    user.id,
                    str(uuid.uuid4()),
                    pending['revised_resume'],
                    feedback=pending.get('feedback'),
                    original_resume=pending.get('original_resume'),
                    job_description=pending.get('job_description')
                )
            except FreeTierLimitReached:
                flash(
                    "You've reached the free tier limit (1 revision). Upgrade to save unlimited revisions.",
                    "danger"
                )
            except Exception:
                pass
        nxt = _pop_auth_next()
        return redirect(nxt or url_for('my_revisions'))
    except Exception as e:
        err_name = type(e).__name__
        err_text = str(e or "")
        logger.exception("google_callback oauth exchange failed")
        if "MismatchingStateError" in err_name or "mismatching_state" in err_text.lower():
            flash(
                "Google sign-in could not be verified. Please try again.",
                "danger"
            )
        elif "SSL" in err_name or "certificate verify failed" in err_text.lower():
            flash(
                "Google sign-in failed due to a local SSL certificate issue. Please restart the app and try again.",
                "danger"
            )
        else:
            flash("Google sign-in failed. Please try again.", "danger")
        return redirect(url_for("login"))


@app.route("/login/facebook/authorized")
def facebook_callback():
    if not facebook.authorized:
        flash("Facebook login failed.", "danger")
        return redirect(url_for("login"))
    resp = facebook.get("/me?fields=id,name,email")
    if not resp.ok:
        flash("Failed to fetch Facebook user info.", "danger")
        return redirect(url_for("login"))

    fb_info = resp.json()
    user_id = f"facebook_{fb_info['id']}"
    user, is_new = _resolve_oauth_user(
        user_id,
        fb_info["name"],
        fb_info.get("email", "")
    )
    add_user(user)  # Use add_user to save persistently
    # Marketing attribution + conversion (only for first-time signups; best-effort)
    try:
        if is_new:
            _append_marketing_signup_csv(
                user,
                signup_method='facebook_oauth'
            )
            analytics.track_conversion(session, "signup")
    except Exception:
        pass
    # One-time welcome email for new OAuth signups (best-effort, non-blocking)
    try:
        if is_new and _normalize_email(
                getattr(user, 'email', '')
        ) and not getattr(user, 'welcome_email_sent_at', None):
            sent_ok = send_welcome_email(
                user.email,
                getattr(user, 'name', '') or ''
            )
            if sent_ok:
                user.welcome_email_sent_at = datetime.now(
                    timezone.utc
                ).isoformat()
                add_user(user)
    except Exception:
        pass
    # Persist profile to Azure Users table
    try:
        upsert_user_profile_azure(user)
    except Exception:
        pass
    login_user(user)
    _audit_login_start(user, login_method='facebook_oauth')
    nxt = _pop_auth_next()
    return redirect(nxt or url_for("index"))


from openai import OpenAI

_FEEDBACK_CATEGORIES = ['Content', 'Format', 'Optimization',
                        'Best Practices', 'Application Readiness']


def _canonical_feedback_category(raw: str) -> str:
    s = str(raw or '').strip()
    if not s:
        return ''
    key = s.lower().strip()
    alias = {
        'content': 'Content',
        'format': 'Format',
        'formatting': 'Format',
        'layout': 'Format',
        'optimization': 'Optimization',
        'ats': 'Optimization',
        'ats optimization': 'Optimization',
        'ats-optimization': 'Optimization',
        'best practices': 'Best Practices',
        'bestpractice': 'Best Practices',
        'application readiness': 'Application Readiness',
        'readiness': 'Application Readiness',
        'job readiness': 'Application Readiness',
    }
    # Exact match on canonical names
    for c in _FEEDBACK_CATEGORIES:
        if key == c.lower():
            return c
    # Alias match
    if key in alias:
        return alias[key]
    # Fuzzy contains (helps when model returns "Optimization (ATS)")
    if 'content' in key:
        return 'Content'
    if 'format' in key or 'layout' in key:
        return 'Format'
    if 'optimiz' in key or 'ats' in key:
        return 'Optimization'
    if 'best' in key or 'practice' in key:
        return 'Best Practices'
    if 'readiness' in key or 'application' in key:
        return 'Application Readiness'
    return s


def _normalize_feedback(feedback: object) -> dict:
    """Normalize feedback object so result.html can render reliably."""
    if not isinstance(feedback, dict):
        return {'overall_score': 50,
                'subscores': {c: 50 for c in _FEEDBACK_CATEGORIES},
                'improvement_items': []}

    out = dict(feedback)

    # overall_score
    try:
        overall = int(float(out.get('overall_score', 50)))
    except Exception:
        overall = 50
    overall = max(0, min(100, overall))
    out['overall_score'] = overall

    # subscores can be dict or list
    subs = out.get('subscores', {})
    normalized_subs: dict[str, int] = {}
    if isinstance(subs, dict):
        for k, v in subs.items():
            cat = _canonical_feedback_category(k)
            if not cat:
                continue
            try:
                score = int(float(v))
            except Exception:
                score = overall
            normalized_subs[cat] = max(0, min(100, score))
    elif isinstance(subs, list):
        # accept [{category, score}] style
        for it in subs:
            if not isinstance(it, dict):
                continue
            cat = _canonical_feedback_category(
                it.get('category') or it.get('name') or it.get('Category')
            )
            if not cat:
                continue
            try:
                score = int(float(it.get('score', overall)))
            except Exception:
                score = overall
            normalized_subs[cat] = max(0, min(100, score))

    # Fill missing categories so the UI tabs always render
    for c in _FEEDBACK_CATEGORIES:
        if c not in normalized_subs:
            normalized_subs[c] = overall
    out['subscores'] = normalized_subs

    # improvement_items can be list or dict-by-category
    items = out.get('improvement_items', [])
    normalized_items: list[dict] = []
    if isinstance(items, dict):
        # e.g. {"Content": ["msg1", ...], ...}
        for k, v in items.items():
            cat = _canonical_feedback_category(k)
            if isinstance(v, list):
                for msg in v:
                    normalized_items.append(
                        {
                            'category': cat,
                            'message': str(msg or '').strip(),
                            'severity': 'suggestion',
                            'example_lines': '',
                        }
                    )
    elif isinstance(items, list):
        for it in items:
            if not isinstance(it, dict):
                continue
            cat = _canonical_feedback_category(
                it.get('category') or it.get('Category') or it.get(
                    'category_name'
                ) or it.get('categoryName')
            )
            msg = it.get('message') or it.get('suggestion') or it.get(
                'feedback'
            ) or it.get('text') or ''
            sev = (it.get('severity') or it.get('level') or it.get(
                'importance'
            ) or 'suggestion')
            ex = it.get('example_lines') or it.get('example') or it.get(
                'exampleLines'
            ) or ''
            sev_s = str(sev or '').strip().lower()
            if sev_s not in ('error', 'warning', 'suggestion'):
                sev_s = 'suggestion'
            normalized_items.append(
                {
                    'category': cat or '',
                    'message': str(msg or '').strip(),
                    'severity': sev_s,
                    'example_lines': str(ex or '').strip(),
                }
            )

    # Keep only items with a message; canonicalize categories; default unknown to Content (so they are visible)
    cleaned = []
    for it in normalized_items:
        m = str(it.get('message') or '').strip()
        if not m:
            continue
        c = _canonical_feedback_category(it.get('category'))
        if c not in _FEEDBACK_CATEGORIES:
            c = 'Content'
        cleaned.append(
            {
                'category': c,
                'message': m,
                'severity': it.get('severity') or 'suggestion',
                'example_lines': it.get('example_lines') or '',
            }
        )
    out['improvement_items'] = cleaned

    return out


def revise_resume(resume_text, job_description=None):
    try:
        # Initialize the client inside the function to avoid blocking startup
        # Explicitly pass API key to handle Azure environment
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        # Configure timeout and other parameters for Azure reliability
        client = OpenAI(
            api_key=api_key,
            timeout=60.0,  # 60 second timeout
            max_retries=3  # Retry up to 3 times on transient errors
        )

        # Build the prompt with optional job description
        job_desc_section = ""
        if job_description:
            job_desc_section = f"""
Job Description to tailor the resume towards:
\"\"\"{job_description}\"\"\"
"""

        prompt = f"""You are a resume optimization expert. Analyze the following resume and provide a comprehensive revision.

Resume to analyze:
\"\"\"{resume_text}\"\"\"{job_desc_section}

Provide your response in the following JSON format ONLY (no markdown, no additional text):
{{
  "revised_resume": "The complete revised version of the resume with improved clarity, structure, and professional tone",
  "feedback": {{
    "overall_score": <number between 0-100>,
    "subscores": {{
      "Content": <number between 0-100>,
      "Format": <number between 0-100>,
      "Optimization": <number between 0-100>,
      "Best Practices": <number between 0-100>,
      "Application Readiness": <number between 0-100>
    }},
    "improvement_items": [
      {{
        "category": "<ONE OF: Content | Format | Optimization | Best Practices | Application Readiness>",
        "message": "<improvement suggestion>",
        "severity": "<error|warning|suggestion>",
        "example_lines": "<relevant example from resume>"
      }}
    ]
  }}
}}

Focus on:
1. Improving clarity, structure, and professional tone
2. Enhancing impact of achievements and experiences
3. Optimizing for ATS systems
4. Maintaining consistency in formatting
5. Adding missing elements that would strengthen the resume

Respond with ONLY the JSON object, no markdown formatting or additional text."""

        try:
            response = client.chat.completions.create(
                model="gpt-5.2-2025-12-11",
                messages=[{"role": "user", "content": prompt}]
            )
        except Exception as e:
            error_msg = str(e)
            print(f"OpenAI API Error: {error_msg}")
            logger.error(
                f"OpenAI API Error details: {type(e).__name__}: {error_msg}"
            )
            # Re-raise with more details for debugging
            raise ValueError(
                f"Failed to connect to OpenAI API: {error_msg}"
            )

        raw_content = response.choices[0].message.content
        print("=== GPT RESPONSE ===")
        print(raw_content)

        # Remove markdown backticks if present
        if raw_content.startswith("```"):
            import re

            raw_content = re.sub(r"^```(?:json)?\n", "", raw_content)
            raw_content = re.sub(r"\n```$", "", raw_content)

        try:
            data = json.loads(raw_content)
            if "revised_resume" not in data or "feedback" not in data:
                raise ValueError("Missing required keys in JSON response")
            return data["revised_resume"], _normalize_feedback(
                data["feedback"]
            )
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {str(e)}")
            print(f"Raw content: {raw_content}")
            raise ValueError(
                "Invalid response format from OpenAI. Please try again."
            )
        except KeyError as e:
            print(f"Missing key in response: {str(e)}")
            raise ValueError(
                "Incomplete response from OpenAI. Please try again."
            )

    except Exception as e:
        print("=== ERROR OCCURRED ===")
        _safe_log_exception('revise_resume error', e)
        raise


@app.route("/")
def index():
    # Track the visit with source attribution (only if not already tracked)
    if 'visit_tracked' not in session:
        analytics_obj = globals().get('analytics')
        if analytics_obj is not None and hasattr(
                analytics_obj,
                'track_visit'
        ):
            try:
                source_info = analytics_obj.track_visit(request)
            except Exception as e:
                _safe_log_exception('analytics.track_visit failed', e)
                source_info = {"type": "organic", "source": "fallback",
                               "error": str(e)}
        else:
            source_info = {"type": "organic", "source": "fallback",
                           "error": "analytics_unavailable"}
        session['visit_tracked'] = True
        session['traffic_source'] = source_info
        app.logger.info(
            f"Homepage visit tracked from server-side: {source_info.get('type', 'unknown')}"
        )
    else:
        # Use existing traffic source from session
        source_info = session.get('traffic_source', {'type': 'organic'})
        app.logger.info(
            "Homepage visit already tracked in session, skipping duplicate"
        )

    current_year = datetime.now().year
    scroll_to_form = (
            request.args.get('scroll_to_form', '').lower() == 'true')
    resp = make_response(
        render_template(
            "index.html",
            year=current_year,
            user=current_user,
            scroll_to_form=scroll_to_form
        )
    )
    resp.headers[
        "Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/upload")
def upload():
    if not current_user.is_authenticated:
        try:
            nxt = (request.full_path or request.path or '/').strip()
            if nxt.endswith('?'):
                nxt = nxt[:-1]
        except Exception:
            nxt = '/upload'
        return redirect(url_for('login', next=nxt))
    try:
        _safe_log_event(f"upload GET: pid={os.getpid()} build={_BUILD_ID}")
    except Exception:
        _safe_log_event("upload GET")
    current_year = datetime.now().year
    return render_template(
        "upload.html",
        year=current_year,
        user=current_user
    )


@app.route("/start")
def start():
    # Use a temporary redirect here because browsers can cache 301s very aggressively.
    resp = redirect(url_for('index'), code=302)
    resp.headers[
        'Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route("/get-started")
def get_started():
    """Entry point CTA: let the user choose new resume vs revise existing."""
    current_year = datetime.now().year
    return render_template(
        "get_started.html",
        year=current_year,
        user=current_user
    )


@app.route("/paste-resume")
def paste_resume():
    """Fallback page for users to paste resume text when file parsing fails."""
    current_year = datetime.now().year
    show_error = (request.args.get('error') or '').strip() in (
        '1', 'true', 'yes')
    return render_template(
        "paste_resume.html",
        year=current_year,
        user=current_user,
        show_error=show_error
    )


def _clean_lines(value: str) -> list:
    lines = []
    for raw in (value or '').splitlines():
        s = str(raw).strip()
        if not s:
            continue
        lines.append(s)
    return lines


def _split_skills(value: str) -> list:
    # Accept newline-separated or comma-separated.
    if not value:
        return []
    if '\n' in value:
        parts = _clean_lines(value)
        # Also split any comma-separated lines.
        out = []
        for p in parts:
            if ',' in p:
                out.extend([x.strip() for x in p.split(',') if x.strip()])
            else:
                out.append(p)
        # de-dupe while preserving order
        seen = set()
        deduped = []
        for x in out:
            k = x.lower()
            if k in seen:
                continue
            seen.add(k)
            deduped.append(x)
        return deduped
    return [x.strip() for x in value.split(',') if x.strip()]


_BULLET_PREFIX_RE = re.compile(r'^\s*(?:\u2022|•|[-–—*]|●|◦|▪|·)\s+')


def _auto_bullet_sentences(text: str) -> str:
    """Convert plain sentences into bullet lines.

    If the input already contains bullet prefixes, preserve line structure.
    """
    raw = str(text or '').replace('\r\n', '\n').strip()
    if not raw:
        return ''

    lines = [ln.strip() for ln in raw.split('\n') if ln.strip()]
    if not lines:
        return ''

    if any(_BULLET_PREFIX_RE.match(ln) for ln in lines):
        return '\n'.join(lines)

    joined = ' '.join(lines).strip()
    if not joined:
        return ''

    parts = [p.strip() for p in re.split(r'(?<=[.!?])\s+', joined) if
             p and p.strip()]
    if len(parts) <= 1:
        return f"• {joined}"
    return '\n'.join([f"• {p}" for p in parts])


def _build_compiled_resume_text(structured: dict) -> str:
    name = str(structured.get('name') or '').strip()
    title = str(structured.get('title') or '').strip()
    email = str(structured.get('email') or '').strip()
    phone = str(structured.get('phone') or '').strip()
    location = str(structured.get('location') or '').strip()
    linkedin = str(structured.get('linkedin') or '').strip()
    website = str(structured.get('website') or '').strip()

    lines = []
    if name:
        lines.append(name)
    if title:
        lines.append(title)
    contact_bits = [b for b in [location, email, phone] if b]
    if contact_bits:
        lines.append(' | '.join(contact_bits))
    link_bits = [b for b in [linkedin, website] if b]
    if link_bits:
        lines.append(' | '.join(link_bits))

    summary = str(structured.get('summary') or '').strip()
    if summary:
        lines.append('')
        lines.append('PROFESSIONAL SUMMARY')
        lines.append(summary)

    exp = structured.get('experience') or []
    if isinstance(exp, list) and any(
            (e.get('title') or e.get('company') or e.get(
                'description'
            ) or e.get('duration')) for e in exp if
            isinstance(e, dict)
    ):
        lines.append('')
        lines.append('WORK EXPERIENCE')
        for e in exp:
            if not isinstance(e, dict):
                continue
            role = str(e.get('title') or '').strip()
            company = str(e.get('company') or '').strip()
            duration = str(e.get('duration') or '').strip()
            header = ' — '.join([x for x in [role, company] if x])
            if header:
                if duration:
                    header = f"{header} ({duration})"
                lines.append(header)
            desc = str(e.get('description') or '').strip()
            if desc:
                # Normalize bullets if user used '•'
                for dl in desc.splitlines():
                    dls = dl.strip()
                    if not dls:
                        continue
                    lines.append(dls)
            lines.append('')
        while lines and lines[-1] == '':
            lines.pop()

    edu = structured.get('education') or []
    if isinstance(edu, list) and any(
            (d.get('degree') or d.get('field_of_study') or d.get(
                'institution'
            ) or d.get('year') or d.get('gpa')) for d in edu if
            isinstance(d, dict)
    ):
        lines.append('')
        lines.append('EDUCATION')
        for d in edu:
            if not isinstance(d, dict):
                continue
            degree = str(d.get('degree') or '').strip()
            field_of_study = str(d.get('field_of_study') or '').strip()
            inst = str(d.get('institution') or '').strip()
            year = str(d.get('year') or '').strip()
            gpa = str(d.get('gpa') or '').strip()
            bits = [b for b in [degree] if b]
            if field_of_study and field_of_study.lower() not in degree.lower():
                bits.append(field_of_study)
            if inst:
                bits.append(inst)
            if year:
                bits.append(year)
            if gpa:
                bits.append(f"GPA: {gpa}")
            if bits:
                lines.append(' — '.join(bits))

    certs = structured.get('certifications') or []
    if isinstance(certs, list) and any(
            (c.get('name') or c.get('issuer') or c.get('year')) for c in
            certs if isinstance(c, dict)
    ):
        lines.append('')
        lines.append('CERTIFICATIONS')
        for c in certs:
            if not isinstance(c, dict):
                continue
            name2 = str(c.get('name') or '').strip()
            issuer = str(c.get('issuer') or '').strip()
            year2 = str(c.get('year') or '').strip()
            bits = [b for b in [name2, issuer] if b]
            if year2:
                bits.append(year2)
            if bits:
                lines.append(' — '.join(bits))

    custom_sections = structured.get('custom_sections') or []
    if isinstance(custom_sections, list) and any(
            isinstance(cs, dict) and (cs.get('heading') or cs.get('items'))
            for cs in custom_sections
    ):
        for cs in custom_sections:
            if not isinstance(cs, dict):
                continue
            heading = str(cs.get('heading') or '').strip()
            items = cs.get('items') or []
            if not heading and not items:
                continue
            lines.append('')
            lines.append(heading.upper() if heading else 'ADDITIONAL')
            if isinstance(items, list):
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    it_title = str(it.get('title') or '').strip()
                    it_sub = str(it.get('subtitle') or '').strip()
                    it_date = str(it.get('date') or '').strip()
                    it_content = str(it.get('content') or '').strip()
                    header_bits = [b for b in [it_title, it_sub] if b]
                    header = ' — '.join(header_bits)
                    if header and it_date:
                        header = f"{header} ({it_date})"
                    elif (not header) and it_date:
                        header = it_date
                    if header:
                        lines.append(header)
                    if it_content:
                        for dl in it_content.splitlines():
                            dls = dl.strip()
                            if not dls:
                                continue
                            lines.append(dls)
            lines.append('')
        while lines and lines[-1] == '':
            lines.pop()

    skills = structured.get('skills') or []
    if isinstance(skills, list) and any(str(s).strip() for s in skills):
        lines.append('')
        lines.append('SKILLS')
        cleaned = [str(s).strip() for s in skills if str(s).strip()]
        lines.append(', '.join(cleaned))

    return '\n'.join(lines).strip() + '\n'


@app.route('/resume/new', methods=['GET', 'POST'])
@app.route('/resume/new/', methods=['GET', 'POST'])
@app.route('/create-resume', methods=['GET', 'POST'])
@app.route('/create-resume/', methods=['GET', 'POST'])
def resume_new():
    """Collect standard resume sections and compile into resume text."""
    current_year = datetime.now().year
    if not current_user.is_authenticated:
        try:
            nxt = (request.full_path or request.path or '/').strip()
            if nxt.endswith('?'):
                nxt = nxt[:-1]
        except Exception:
            nxt = url_for('resume_new')
        return redirect(url_for('login', next=nxt))
    if request.method == 'GET':
        return render_template(
            'resume_new.html',
            year=current_year,
            user=current_user
        )

    def _format_month_year(raw_value: str) -> str:
        s = str(raw_value or '').strip()
        if not s:
            return ''
        # Accept HTML <input type="month"> values like "YYYY-MM".
        try:
            dt = datetime.strptime(s, '%Y-%m')
            return dt.strftime('%b %Y')
        except Exception:
            pass
        # Accept full dates like "YYYY-MM-DD" if they sneak in.
        try:
            dt = datetime.strptime(s, '%Y-%m-%d')
            return dt.strftime('%b %Y')
        except Exception:
            pass
        return s

    def _parse_month_start(raw_value: str):
        s = str(raw_value or '').strip()
        if not s:
            return None
        try:
            dt = datetime.strptime(s, '%Y-%m')
            return datetime(dt.year, dt.month, 1)
        except Exception:
            pass
        try:
            dt = datetime.strptime(s, '%Y-%m-%d')
            return datetime(dt.year, dt.month, 1)
        except Exception:
            return None

    def _is_future_month(raw_value: str) -> bool:
        dt = _parse_month_start(raw_value)
        if not dt:
            return False
        now = datetime.now()
        now_month = datetime(now.year, now.month, 1)
        return dt > now_month

    def _format_range(
            from_raw: str,
            to_raw: str,
            is_current: bool = False
    ) -> str:
        start = _format_month_year(from_raw)
        if (not is_current) and _is_future_month(to_raw):
            end_fmt = _format_month_year(to_raw)
            return f"Expected {end_fmt or str(to_raw or '').strip()}".strip()
        end = 'Present' if is_current else _format_month_year(to_raw)
        if start and end:
            return f"{start} – {end}"
        if start and is_current:
            return f"{start} – Present"
        return start or end

    template_choice = (request.form.get('template') or '').strip()

    name = (request.form.get('name') or '').strip()
    if not name:
        flash('Name is required.', 'danger')
        return redirect(url_for('resume_new'))

    if not template_choice:
        flash('Please choose a template first.', 'danger')
        return redirect(url_for('resume_new'))

    job_description = (request.form.get('jobDescription') or '').strip()

    structured = {
        'name': name,
        'title': (request.form.get('title') or '').strip(),
        'email': (request.form.get('email') or '').strip(),
        'phone': (request.form.get('phone') or '').strip(),
        'location': (request.form.get('location') or '').strip(),
        'linkedin': (request.form.get('linkedin') or '').strip(),
        'website': (request.form.get('website') or '').strip(),
        'summary': (request.form.get('summary') or '').strip(),
        'experience': [],
        'education': [],
        'projects': [],
        'certifications': [],
        'skills': _split_skills(request.form.get('skills') or ''),
        'custom_sections': [],
        'template_id': _canonical_template_id(
            template_choice
        ) if template_choice else 'professional',
    }

    exp_titles = request.form.getlist('exp_title')
    exp_companies = request.form.getlist('exp_company')
    exp_durations = request.form.getlist('exp_duration')
    exp_froms = request.form.getlist('exp_from')
    exp_tos = request.form.getlist('exp_to')
    exp_currents = request.form.getlist('exp_current')
    exp_descs = request.form.getlist('exp_description')

    max_exp = max(
        len(exp_titles),
        len(exp_companies),
        len(exp_durations),
        len(exp_froms),
        len(exp_tos),
        len(exp_currents),
        len(exp_descs),
    )

    for i in range(max_exp):
        title = (exp_titles[i] if i < len(exp_titles) else '').strip()
        company = (
            exp_companies[i] if i < len(exp_companies) else '').strip()
        duration = (
            exp_durations[i] if i < len(exp_durations) else '').strip()
        from_raw = (exp_froms[i] if i < len(exp_froms) else '').strip()
        to_raw = (exp_tos[i] if i < len(exp_tos) else '').strip()
        current_raw = (exp_currents[i] if i < len(
            exp_currents
        ) else '').strip().lower()
        is_current = current_raw in ('1', 'true', 'yes', 'on')
        if not duration and any([from_raw, to_raw, is_current]):
            duration = _format_range(
                from_raw,
                to_raw,
                is_current=is_current
            )
        desc = (exp_descs[i] if i < len(exp_descs) else '').strip()
        if desc:
            desc = _auto_bullet_sentences(desc)
        if not any([title, company, duration, desc]):
            continue
        structured['experience'].append(
            {
                'title': title,
                'company': company,
                'duration': duration,
                'description': desc,
            }
        )

    edu_degrees = request.form.getlist('edu_degree')
    edu_years = request.form.getlist('edu_year')
    edu_froms = request.form.getlist('edu_from')
    edu_tos = request.form.getlist('edu_to')
    edu_fields = request.form.getlist('edu_field_of_study')
    edu_insts = request.form.getlist('edu_institution')
    edu_gpas = request.form.getlist('edu_gpa')

    max_edu = max(
        len(edu_degrees),
        len(edu_years),
        len(edu_froms),
        len(edu_tos),
        len(edu_fields),
        len(edu_insts),
        len(edu_gpas),
    )

    for i in range(max_edu):
        degree = (edu_degrees[i] if i < len(edu_degrees) else '').strip()
        year = (edu_years[i] if i < len(edu_years) else '').strip()
        from_raw = (edu_froms[i] if i < len(edu_froms) else '').strip()
        to_raw = (edu_tos[i] if i < len(edu_tos) else '').strip()
        if not year and any([from_raw, to_raw]):
            year = _format_range(from_raw, to_raw, is_current=False)
        field_of_study = (
            edu_fields[i] if i < len(edu_fields) else '').strip()
        inst = (edu_insts[i] if i < len(edu_insts) else '').strip()
        gpa = (edu_gpas[i] if i < len(edu_gpas) else '').strip()
        if not any([degree, year, field_of_study, inst, gpa]):
            continue
        degree_display = degree
        if field_of_study:
            if degree_display:
                if field_of_study.lower() not in degree_display.lower():
                    degree_display = f"{degree_display} in {field_of_study}"
            else:
                degree_display = field_of_study
        structured['education'].append(
            {
                'degree': degree_display,
                'field_of_study': field_of_study,
                'institution': inst,
                'year': year,
                'gpa': gpa,
            }
        )

    cert_names = request.form.getlist('cert_name')
    cert_years = request.form.getlist('cert_year')
    cert_issuers = request.form.getlist('cert_issuer')
    for i in range(
            max(len(cert_names), len(cert_years), len(cert_issuers))
    ):
        cname = (cert_names[i] if i < len(cert_names) else '').strip()
        cyear = (cert_years[i] if i < len(cert_years) else '').strip()
        issuer = (cert_issuers[i] if i < len(cert_issuers) else '').strip()
        if not any([cname, cyear, issuer]):
            continue
        structured['certifications'].append(
            {
                'name': cname,
                'issuer': issuer,
                'year': cyear,
            }
        )

    custom_headings = request.form.getlist('custom_heading')
    custom_contents = request.form.getlist('custom_content')
    for i in range(max(len(custom_headings), len(custom_contents))):
        heading = (
            custom_headings[i] if i < len(custom_headings) else '').strip()
        content = (
            custom_contents[i] if i < len(custom_contents) else '').strip()
        if not any([heading, content]):
            continue
        structured['custom_sections'].append(
            {
                'heading': heading or 'Additional',
                'items': [
                    {
                        'title': '',
                        'subtitle': '',
                        'date': '',
                        'content': content,
                    }
                ],
            }
        )

    compiled_text = _build_compiled_resume_text(structured)

    # Persist immediately so the resume appears in /my_revisions without requiring
    # a subsequent "Save Changes" click in React edit mode.
    source_revision_id = None
    try:
        import hashlib
        import uuid

        structured_hash = None
        try:
            structured_hash = hashlib.sha256(
                (
                        json.dumps(
                            structured,
                            sort_keys=True,
                            ensure_ascii=False
                        )
                        + "\n\n" + str(job_description or '')
                ).encode('utf-8')
            ).hexdigest()
        except Exception:
            structured_hash = None

        if structured_hash:
            prior_hash = str(
                session.get('last_resume_new_hash') or ''
            ).strip()
            prior_revision_id = str(
                session.get('last_resume_new_revision_id') or ''
            ).strip()
            if prior_hash and prior_revision_id and prior_hash == structured_hash:
                # Best-effort reuse: avoids duplicate revisions from accidental double-submit.
                try:
                    table_client = get_table_client()
                    table_client.get_entity(
                        partition_key=str(current_user.id),
                        row_key=str(prior_revision_id)
                    )
                    source_revision_id = prior_revision_id
                except Exception:
                    source_revision_id = None

        if not source_revision_id:
            source_revision_id = str(uuid.uuid4())
            save_resume_revision(
                user_id=current_user.id,
                revision_id=source_revision_id,
                resume_content=compiled_text,
                feedback={},
                original_resume='',
                job_description=job_description,
            )

        # Remember this submission for idempotency within the current session.
        if structured_hash and source_revision_id:
            session['last_resume_new_hash'] = structured_hash
            session['last_resume_new_revision_id'] = source_revision_id
    except FreeTierLimitReached:
        # Still let the user proceed to the template viewer, but do not persist a new revision.
        flash(
            "You've reached the free tier limit (1 revision). Upgrade to save unlimited revisions.",
            "danger"
        )
        source_revision_id = None
        try:
            session.pop('last_resume_new_hash', None)
            session.pop('last_resume_new_revision_id', None)
        except Exception:
            pass
    except Exception as e:
        # Best-effort: if storage fails, keep the flow working.
        try:
            logger.error(
                "resume_new: failed to persist revision: %s",
                str(e)
            )
        except Exception:
            pass
        source_revision_id = None

    # Best-effort: persist an initial structured snapshot for the chosen template so the
    # created resume also has a template version in /my_revisions without needing edit-mode.
    if source_revision_id:
        try:
            template_id = _canonical_template_id(
                template_choice
            ) if template_choice else 'professional'
            snapshot = json.dumps(structured, ensure_ascii=False)
            snapshot_bytes = snapshot.encode('utf-8')

            table_client = get_table_client()
            entity = table_client.get_entity(
                partition_key=str(current_user.id),
                row_key=str(source_revision_id)
            )
            entity['template_id'] = template_id
            entity['template_saved_at'] = datetime.now(
                timezone.utc
            ).isoformat()

            try:
                entity['template_saved_templates'] = json.dumps(
                    [template_id],
                    ensure_ascii=False
                )
            except Exception:
                entity['template_saved_templates'] = ''

            per_plain_prop, per_gz_prop, per_at_prop = _template_snapshot_prop_names(
                template_id
            )
            entity[per_at_prop] = entity['template_saved_at']

            if len(snapshot_bytes) <= 60_000:
                entity['template_structured_resume'] = snapshot
                entity['template_structured_resume_gz_b64'] = ''
                entity[per_plain_prop] = snapshot
                entity[per_gz_prop] = ''
            else:
                import base64
                import gzip

                gz = gzip.compress(snapshot_bytes, compresslevel=9)
                b64 = base64.b64encode(gz).decode('ascii')
                if len(b64.encode('ascii')) <= 60_000:
                    entity['template_structured_resume'] = ''
                    entity['template_structured_resume_gz_b64'] = b64
                    entity[per_plain_prop] = ''
                    entity[per_gz_prop] = b64
            table_client.update_entity(entity, mode=UpdateMode.MERGE)
        except Exception:
            # Do not block the user if template snapshot persistence fails.
            pass

    # Seed the normal template-selection pipeline.
    session['results_data'] = {
        'original_resume': '',
        'revised_resume': compiled_text,
        'feedback': {},
        'job_description': job_description,
        # Let /api/parse-resume-for-template reuse this (avoids an extra OpenAI parsing call).
        'structured_resume': structured,
    }
    if source_revision_id:
        session['results_data']['source_revision_id'] = source_revision_id
    session.pop('template_data', None)
    session.modified = True
    # Auto-continue into the chosen template so users don't have to pick twice.
    return redirect(
        url_for('resume_choose_template', auto_template=template_choice)
    )


@app.route('/resume/new/start')
@app.route('/resume/new/start/')
@app.route('/create-resume-legacy/start')
@app.route('/create-resume-legacy/start/')
def resume_new_start():
    """Start a fresh 'build new resume' attempt.

    Clears any previous results/template snapshot so users always get the template chooser,
    even if they previously built a resume in the same session.
    """
    session.pop('template_data', None)
    session.pop('results_data', None)
    session.pop('pending_revision', None)
    session.modified = True
    return redirect(url_for('resume_new'))


@app.route('/resume/templates')
@app.route('/resume/templates/')
def resume_choose_template():
    current_year = datetime.now().year
    results_data = session.get('results_data') or {}
    resume_text = str(results_data.get('revised_resume') or '')
    if not resume_text.strip():
        flash('Please create a resume first.', 'danger')
        return redirect(url_for('get_started'))
    return render_template(
        'resume_choose_template.html',
        year=current_year,
        user=current_user,
        resume_text=resume_text
    )


@app.route("/plans")
def plans():
    current_year = datetime.now().year
    trial_unavailable = False
    next_url = str(request.args.get('next') or '').strip()
    safe_next_url = next_url if (
            next_url and _is_safe_next_url(next_url)) else ''
    try:
        if getattr(current_user, 'is_authenticated', False):
            trial_unavailable = _trial_already_used_for_user(current_user)
            # If the user just purchased via Stripe Payment Link and webhooks haven't updated Azure yet,
            # try to refresh paid status from Stripe and bounce them back to where they came from.
            try:
                if not is_paid_user(current_user) and _stripe_enabled():
                    if _refresh_paid_status_from_stripe_for_user(
                            current_user
                    ):
                        return redirect(
                            safe_next_url or url_for('my_revisions')
                        )
            except Exception:
                pass
    except Exception:
        trial_unavailable = False
    offer_retention = str(
        request.args.get('offer') or ''
    ).strip().lower() == 'retention'
    if str(request.args.get('reason') or '').strip().lower() == 'pdf':
        flash(
            'PDF downloads are not available on free accounts.',
            'warning'
        )

    raw_plans = _get_active_stripe_plans(force_refresh=True)

    from collections import OrderedDict

    product_groups = OrderedDict()

    for plan in raw_plans:
        # ALLOW trial products with a unit_amount of 0 to pass through
        if plan.get("unit_amount") == 0 and plan.get("role") != "trial":
            continue

        amount_display, suffix_display = _format_plan_price_parts(plan)

        ui_plan = {
            "price_id": plan["price_id"],
            "product_id": plan["product_id"],
            "role": plan["role"],
            # Added role pass-through to template context
            "label": plan["label"],
            "note": plan["note"],
            "micro_note": plan["micro_note"],
            "features": plan["features"],
            "badge": plan["badge"],
            "sort_order": plan["sort_order"],
            "amount_display": amount_display,
            "suffix_display": suffix_display,
            "has_trial": plan["trial_period_days"] > 0 or plan[
                "role"] == "trial",
            "trial_days": plan["trial_period_days"],
            "cta_label": plan["cta_label"] or (
                "Start Free Trial" if (
                        plan["trial_period_days"] > 0 or plan[
                    "role"] == "trial") else "Choose Plan"
            ),
            "interval": plan["interval"],
        }

        group = product_groups.setdefault(
            plan["product_id"],
            {
                "sort_order": plan["sort_order"],
                "monthly": None,
                "annual": None,
            },
        )

        if plan["interval"] == "year":
            group["annual"] = ui_plan
        else:
            group["monthly"] = ui_plan

    product_groups = sorted(
        product_groups.values(),
        key=lambda g: g["sort_order"]
    )
    show_billing_toggle = any(
        g["monthly"] and g["annual"] for g in product_groups
    )

    return render_template(
        "plans.html",
        year=current_year,
        user=current_user,
        trial_unavailable=trial_unavailable,
        offer_retention=offer_retention,
        next_url=safe_next_url,
        product_groups=product_groups,
        show_billing_toggle=show_billing_toggle,
        plan_prices=_plans_price_display_context(),
        trial_hold_days=_get_trial_hold_days(),
        capture_day=max(
            1,
            _get_trial_hold_days() - _get_trial_capture_days_before_end(
                _get_trial_hold_days()
            )
        ),
    )


# ══════════════════════════════════════════════════════════════════════════════════════════
# Dynamic Stripe plan catalog
#
# Plans shown on /plans and sold via /checkout are read directly from Stripe
# Products + Prices. Configure plans entirely in the Stripe Dashboard using this
# metadata convention:
#
#   Product metadata:
#     display             = "1" | "true"                  (required - marks this as a sellable plan)
#     plan_role           = "trial" | "monthly" | "pro"   (required - maps access levels)
#     sort_order          = "0", "1", "2", ...            (optional - left-to-right grid layout priority)
#     badge               = "Best Value"                  (optional - colored ribbon shown on the card)
#     note                = "7-day full access pass"      (optional - card header note; falls back to description)
#     micro_note          = "Free for 7 days. Cancel."    (optional - contextual text directly under the button)
#     features            = "Feature one | Feature two"   (optional - pipe-separated string converted into bullet lists)
#     cta_label           = "Upgrade Now"                 (optional - button text override)
#     trial_days          = "7"                           (required for 'trial' role - explicitly defines standalone trial period length)
#
#   Price Handling Rules:
#     1. Standard Recurring Subscriptions (Monthly/Annual):
#        - Must be configured as type="recurring".
#        - Stripe native recurring intervals ('month', 'year') drive template logic.
#
#     2. Standalone Trial Tier:
#        - Configured as type="one_time" with a unit_amount of 0 (or a trial deposit fee structure).
#        - Must utilize the 'plan_role' = "trial" assignment.
#        - The system automatically classifies it as a monthly-interval layout component to align it cleanly
#          within the desktop toggle grids.
# ══════════════════════════════════════════════════════════════════════════════════════════

_STRIPE_PLAN_CACHE = {"plans": [], "fetched_at": 0.0}
_STRIPE_PLAN_CACHE_TTL_SECONDS = (
    300  # 5 min - Dashboard changes show up without a deploy
)
_DEFAULT_CTA_BY_ROLE = {
    "trial": "Start trial",
    "monthly": "Go monthly",
    "annual": "Go annual",
}


def _normalize_stripe_plan(price) -> Optional[dict]:
    """Build a normalized plan dict from a Stripe Price with its Product expanded."""
    price_id = _stripe_obj_get(price, "id", "UNKNOWN_PRICE")

    try:
        product = _stripe_obj_get(price, "product", None)
        if product is None or isinstance(product, str):
            return None

        if not bool(_stripe_obj_get(product, "active", True)):
            return None

        metadata = dict(_stripe_obj_get(product, "metadata", None) or {})
        price_metadata = dict(
            _stripe_obj_get(price, "metadata", None) or {}
        )

        # Parse role with a safe fallback to "pro"
        role = str(
            metadata.get("plan_role") or price_metadata.get(
                "plan_role"
            ) or "pro"
        ).strip().lower()

        # Flexible display tag check
        display_val = str(metadata.get("display") or "").strip().lower()
        if display_val not in ("1", "true"):
            logger.debug(
                "Plan rejected price_id=%s display=%s role=%s",
                price_id,
                display_val,
                role,
            )
            return None

        # Handle recurring blocks safely for one_time trial prices
        recurring = _stripe_obj_get(price, "recurring", None) or {}
        interval = str(recurring.get("interval") or "").strip().lower()
        interval_count = int(recurring.get("interval_count") or 1)

        # If it's a one_time product and labeled as a trial, default its interval classification
        if not interval and role == "trial":
            interval = "month"  # Keeps it grouped inside the standard monthly template view grid

        # READ TRIAL DAYS FROM METADATA (dashboard replacement rule)
        override = str(
            metadata.get("trial_days") or price_metadata.get(
                "trial_days"
            ) or ""
        ).strip()
        trial_period_days = int(override) if override.isdigit() else 0

        # READ USE TRIAL HOLD
        use_trial_hold_raw = str(
            metadata.get("use_trial_hold") or price_metadata.get(
                "use_trial_hold"
            ) or ""
        ).strip().lower()
        use_trial_hold = use_trial_hold_raw in ("1", "true", "True", "yes")
        trial_hold_ui_raw = str(
            metadata.get("use_trial_hold") or price_metadata.get(
                "use_trial_hold"
            ) or ""
        ).strip().lower()

        trial_hold_ui = trial_hold_ui_raw in ("self", "stripe")

        features_raw = str(metadata.get("features") or "").strip()
        features = [f.strip() for f in features_raw.split("|") if
                    f.strip()]

        try:
            sort_order = int(str(metadata.get("sort_order") or "").strip())
        except Exception:
            sort_order = 999

        return {
            "price_id": str(
                _stripe_obj_get(price, "id", "") or ""
            ).strip(),
            "product_id": str(
                _stripe_obj_get(product, "id", "") or ""
            ).strip(),
            "role": role,
            "label": str(
                _stripe_obj_get(product, "name", "") or ""
            ).strip() or role.title(),
            "note": str(metadata.get("note") or "").strip() or str(
                _stripe_obj_get(product, "description", "") or ""
            ).strip(),
            "micro_note": str(metadata.get("micro_note") or "").strip(),
            "features": features,
            "badge": str(metadata.get("badge") or "").strip(),
            "cta_label": str(metadata.get("cta_label") or "").strip(),
            "unit_amount": int(
                _stripe_obj_get(price, "unit_amount", 0) or 0
            ),
            "currency": str(
                _stripe_obj_get(price, "currency", "usd") or "usd"
            ).lower(),
            "interval": interval,
            "interval_count": interval_count,
            "trial_period_days": trial_period_days,
            "use_trial_hold": use_trial_hold,
            "trial_hold_ui": trial_hold_ui,
            "trial_fee_price_id": str(
                metadata.get("trial_fee_price_id") or ""
            ).strip(),
            "sort_order": sort_order,
        }
    except Exception:
        return None


def _format_plan_price_parts(plan: dict) -> tuple[str, str]:
    """Return (amount_display, suffix_display) for the pricing card, e.g. ('$0.00', '7 Days')."""
    role = plan.get("role") or ""
    # Standard Plan Calculations
    amount = (plan.get("unit_amount") or 0) / 100.0
    currency = str(plan.get("currency") or "usd").upper()
    symbol = "$" if currency == "USD" else (currency + " ")
    interval = plan.get("interval") or "month"
    interval_count = plan.get("interval_count") or 1

    if interval == "year" and interval_count == 1:
        return f"{symbol}{amount / 12.0:,.2f}", "/ month"
    if interval_count == 1:
        return f"{symbol}{amount:,.2f}", f"/ {interval}"
    return f"{symbol}{amount:,.2f}", f"/ {interval_count} {interval}s"


def _fetch_stripe_plans_from_api() -> list:
    """Fetch active recurring Prices (with Products expanded) tagged for display on /plans."""
    plans = []
    if not _stripe_enabled():
        return plans
    try:
        prices = stripe.Price.list(
            active=True,
            # type="recurring",
            expand=["data.product"],
            limit=100,
        )
        print(
            f"DEBUG: Stripe API returned {len(prices.data)} total active recurring prices."
        )
        for price in list(getattr(prices, "data", []) or []):
            plan = _normalize_stripe_plan(price)
            if not plan:
                print(
                    f"DEBUG: Price {price.id} was REJECTED by _normalize_stripe_plan"
                )
                continue
            if not plan.get("price_id"):
                print(
                    f"DEBUG: Plan for {price.id} skipped due to missing price_id"
                )
                continue
            # For trial plans, resolve the optional one-time upfront fee price so the
            # card can display the real amount charged today (not the recurring amount).
            if plan.get("role") == "trial" and plan.get(
                    "trial_fee_price_id"
            ):
                try:
                    fee_price = stripe.Price.retrieve(
                        plan["trial_fee_price_id"]
                    )
                    plan["trial_fee_unit_amount"] = int(
                        getattr(fee_price, "unit_amount", 0) or 0
                    )
                    plan["trial_fee_currency"] = str(
                        getattr(fee_price, "currency", plan["currency"])
                        or plan["currency"]
                    ).lower()
                except Exception:
                    pass
            plans.append(plan)
    except Exception as e:
        logger.error(f"Failed to fetch Stripe plan catalog: {str(e)}")
    plans.sort(
        key=lambda p: (p.get("sort_order", 999), p.get("unit_amount", 0))
    )
    return plans


def _get_active_stripe_plans(force_refresh: bool = False) -> list:
    """Return the cached dynamic plan catalog, refreshed periodically from Stripe."""
    now = time.time()
    stale = (now - _STRIPE_PLAN_CACHE[
        "fetched_at"]) > _STRIPE_PLAN_CACHE_TTL_SECONDS
    if force_refresh or not _STRIPE_PLAN_CACHE["plans"] or stale:
        fresh = _fetch_stripe_plans_from_api()
        if fresh or force_refresh:
            _STRIPE_PLAN_CACHE["plans"] = fresh
            _STRIPE_PLAN_CACHE["fetched_at"] = now
    return _STRIPE_PLAN_CACHE["plans"]


def _get_plan_by_price_id(price_id: str) -> Optional[dict]:
    """Look up a single plan by Stripe Price ID from the cached catalog."""
    pid = (price_id or "").strip()
    if not pid:
        return None
    for plan in _get_active_stripe_plans():
        if plan.get("price_id") == pid:
            return plan
    # Retry once with a forced refresh in case the plan was just created/updated in Stripe.
    for plan in _get_active_stripe_plans(force_refresh=True):
        if plan.get("price_id") == pid:
            return plan
    return None


@app.route("/plans/template-pdf")
def plans_template_pdf():
    current_year = datetime.now().year
    trial_unavailable = False
    next_url = str(request.args.get('next') or '').strip()
    safe_next_url = next_url if (
            next_url and _is_safe_next_url(next_url)) else ''
    try:
        if getattr(current_user, 'is_authenticated', False):
            trial_unavailable = _trial_already_used_for_user(current_user)
            try:
                if not is_paid_user(current_user) and _stripe_enabled():
                    if _refresh_paid_status_from_stripe_for_user(
                            current_user
                    ):
                        return redirect(
                            safe_next_url or url_for('my_revisions')
                        )
            except Exception:
                pass
    except Exception:
        trial_unavailable = False

    return render_template(
        "plans_template_pdf.html",
        year=current_year,
        user=current_user,
        trial_unavailable=trial_unavailable,
        next_url=safe_next_url,
        plan_prices=_plans_price_display_context(),
        trial_hold_days=_get_trial_hold_days(),
        capture_day=max(
            1,
            _get_trial_hold_days() - _get_trial_capture_days_before_end(
                _get_trial_hold_days()
            )
        ),
    )


_TRIAL_STRIPE_PAYMENT_LINK = "https://buy.stripe.com/cNi8wJ4ko0cTewq1cD7Vm09"


def _normalize_plan_id(plan_id: str) -> str:
    """Normalize legacy plan ids to current ones (backward-compatible)."""
    pid = (plan_id or '').strip()
    # Legacy: trial used to be named trial_14d; it is now trial_7d.
    if pid == 'trial_14d':
        return 'trial_7d'
    if pid in ('trial_10d', 'trial_10_day', 'trial_10_days'):
        return EMAIL_TRIAL_PLAN_ID
    return pid


@app.route("/go/trial")
@app.route("/go/trial/")
@login_required
def go_trial():
    return redirect(url_for("checkout", plan="trial_7d"))


@app.route("/go/email-trial")
@app.route("/go/email-trial/")
def go_email_trial():
    """Entry point for mass-email trial links. Requires a signed invite query param."""
    invite_token = str(request.args.get('invite') or '').strip()
    invite = _resolve_email_trial_invite(invite_token)
    if not invite:
        flash(
            "This trial offer link has expired or is invalid. Please use the link from your email.",
            "danger"
        )
        return redirect(url_for("plans"))
    if not getattr(current_user, 'is_authenticated', False):
        return redirect(
            url_for(
                "login",
                next=url_for(
                    "checkout",
                    plan=EMAIL_TRIAL_PLAN_ID,
                    invite=invite_token
                )
            )
        )
    return redirect(
        url_for("checkout", plan=EMAIL_TRIAL_PLAN_ID, invite=invite_token)
    )


def _get_plan_config(plan_id: str) -> Optional[dict]:
    pid = _normalize_plan_id(plan_id)
    if not pid:
        return None
    # Plan IDs must match templates/plans.html
    if pid == 'trial_7d':
        disp = _plans_price_display_context()
        deposit_label = disp.get('monthly_strong') or '$10.95'
        hold_days = _get_trial_hold_days(pid)
        capture_day = max(
            1,
            hold_days - _get_trial_capture_days_before_end(hold_days)
        )
        return {
            'id': pid,
            'label': f'{hold_days}-Day Trial',
            'price': deposit_label,
            'plan_status': 'trial',
            'duration_days': hold_days,
            'trial_deposit_label': deposit_label,
            'trial_capture_day': capture_day,
            'trial_deposit_terms': (
                f'A temporary {deposit_label} authorization hold is placed on your card. '
                f'If you cancel before day {capture_day}, the hold is released and you are not charged. '
                f'If you stay subscribed, the hold is captured on day {capture_day} as your first month\'s subscription payment. '
                f'Cancel on day {hold_days} for a full refund if you were charged.'
            ),
        }
    if pid == EMAIL_TRIAL_PLAN_ID or pid == 'trial_10d_email':
        disp = _plans_price_display_context()
        deposit_label = disp.get('monthly_strong') or '$10.95'
        hold_days = _get_trial_hold_days(pid)
        capture_day = max(
            1,
            hold_days - _get_trial_capture_days_before_end(hold_days)
        )
        return {
            'id': EMAIL_TRIAL_PLAN_ID,
            'label': f'{hold_days}-Day Free Trial',
            'price': deposit_label,
            'plan_status': 'trial',
            'duration_days': hold_days,
            'trial_deposit_label': deposit_label,
            'trial_capture_day': capture_day,
        }
    if pid == 'monthly_10_95':
        disp = _plans_price_display_context()
        price_line = (
            f"{disp['monthly_strong']} / month"
            if disp.get('currency_mode') == 'inr'
            else '$10.95 / month'
        )
        return {
            'id': pid,
            'label': 'Monthly',
            'price': price_line,
            'plan_status': 'monthly',
            'duration_days': 31,
        }
    if pid == 'annual_6_95':
        disp = _plans_price_display_context()
        price_line = (
            f"{disp['annual_strong']} / month (billed annually)"
            if disp.get('currency_mode') == 'inr'
            else '$6.95 / month (billed annually)'
        )
        return {
            'id': pid,
            'label': 'Annual',
            'price': price_line,
            'plan_status': 'annual',
            'duration_days': 365,
        }
    return None


def _stripe_trial_end_ts_for_display() -> int:
    """Return trial end timestamp aligned with the configured trial hold duration."""
    return _stripe_trial_end_ts_for_days(_get_trial_hold_days())


def _stripe_trial_end_ts_for_days(days: int, buffer_hours: int = 1) -> int:
    """Return a Stripe trial_end timestamp for the given number of days."""
    try:
        day_count = max(1, int(days or 1))
    except Exception:
        day_count = 1
    try:
        buffer = max(0, int(buffer_hours or 0))
    except Exception:
        buffer = 1
    return int(time.time()) + ((day_count * 24 + buffer) * 60 * 60)


def _stripe_enabled() -> bool:
    return bool((os.getenv('STRIPE_SECRET_KEY') or '').strip())


def _get_stripe_customer_id_from_azure(user_id: str) -> str:
    try:
        table_client = get_users_table_client()
        e = table_client.get_entity(
            partition_key=str(user_id),
            row_key='profile'
        )
        return str(e.get('stripe_customer_id') or '').strip()
    except Exception:
        return ''


def _get_stripe_subscription_id_from_azure(user_id: str) -> str:
    try:
        table_client = get_users_table_client()
        e = table_client.get_entity(
            partition_key=str(user_id),
            row_key='profile'
        )
        return str(e.get('stripe_subscription_id') or '').strip()
    except Exception:
        return ''


def _fetch_stripe_subscriptions_index() -> dict:
    """Fetch all Stripe subscriptions for admin reconciliation (paginated)."""
    empty = {
        'subscriptions': [],
        'by_id': {},
        'by_customer': {},
        'total': 0,
        'error': None,
    }
    if not _stripe_enabled():
        return empty
    try:
        all_subs = []
        starting_after = None
        while True:
            # Stripe allows max 4 expand levels on list; price.product would be 5.
            params = {'status': 'all', 'limit': 100,
                      'expand': ['data.items.data.price']}
            if starting_after:
                params['starting_after'] = starting_after
            res = stripe.Subscription.list(**params)
            batch = list(getattr(res, 'data', []) or [])
            all_subs.extend(batch)
            if not getattr(res, 'has_more', False) or not batch:
                break
            starting_after = str(
                getattr(batch[-1], 'id', '') or ''
            ).strip()
            if not starting_after:
                break
        by_id: dict[str, object] = {}
        by_customer: dict[str, list] = {}
        for sub in all_subs:
            sid = str(getattr(sub, 'id', '') or '').strip()
            cid = str(getattr(sub, 'customer', '') or '').strip()
            if sid:
                by_id[sid] = sub
            if cid:
                by_customer.setdefault(cid, []).append(sub)
        for cid in by_customer:
            by_customer[cid].sort(
                key=lambda s: int(getattr(s, 'created', 0) or 0),
                reverse=True,
            )
        return {
            'subscriptions': all_subs,
            'by_id': by_id,
            'by_customer': by_customer,
            'total': len(all_subs),
            'error': None,
        }
    except Exception as e:
        try:
            logger.warning(
                'Failed to fetch Stripe subscriptions for admin dashboard: %s',
                str(e)
            )
        except Exception:
            pass
        empty['error'] = str(e)
        return empty


def _match_user_to_stripe_subscriptions(
        prof: Optional[dict],
        stripe_index: dict
) -> tuple[list, str]:
    """Return Stripe subscription objects linked to this Azure profile."""
    if not prof or not stripe_index:
        return [], ''
    sub_id = str(prof.get('stripe_subscription_id') or '').strip()
    cid = str(prof.get('stripe_customer_id') or '').strip()
    matched: list = []
    seen: set[str] = set()

    by_id = stripe_index.get('by_id') or {}
    by_customer = stripe_index.get('by_customer') or {}

    if sub_id and sub_id in by_id:
        matched.append(by_id[sub_id])
        seen.add(sub_id)

    if cid and cid in by_customer:
        for sub in by_customer[cid]:
            sid = str(getattr(sub, 'id', '') or '').strip()
            if sid and sid not in seen:
                matched.append(sub)
                seen.add(sid)

    match_source = ''
    if matched:
        if sub_id and sub_id in seen:
            match_source = 'subscription_id'
        elif cid:
            match_source = 'customer_id'
    return matched, match_source


def _stripe_sub_status_label(sub) -> str:
    status = str(getattr(sub, 'status', '') or '').strip().lower()
    labels = {
        'active': 'Active',
        'trialing': 'Active (Trial)',
        'canceled': 'Canceled',
        'past_due': 'Past Due',
        'unpaid': 'Unpaid',
        'incomplete': 'Incomplete',
        'incomplete_expired': 'Incomplete Expired',
        'paused': 'Paused',
    }
    return labels.get(
        status,
        status.replace('_', ' ').title() or 'Unknown'
    )


def _get_stripe_customer_email_cached(
        customer_id: str,
        cache: dict
) -> str:
    cid = (customer_id or '').strip()
    if not cid:
        return ''
    if cid in cache:
        return cache[cid]
    email = ''
    if _stripe_enabled():
        try:

            cust = stripe.Customer.retrieve(cid)
            email = str(getattr(cust, 'email', '') or '').strip().lower()
        except Exception:
            pass
    cache[cid] = email
    return email


def _build_azure_profile_lookup(users_rows: list) -> dict:
    lookup = {
        'by_uid': {},
        'by_customer': {},
        'by_sub_id': {},
        'by_email': {},
    }
    for row in users_rows:
        uid = str(row.get('id') or row.get('PartitionKey') or '').strip()
        if uid:
            lookup['by_uid'][uid] = row
        cid = str(row.get('stripe_customer_id') or '').strip()
        if cid:
            lookup['by_customer'].setdefault(cid, row)
        sid = str(row.get('stripe_subscription_id') or '').strip()
        if sid:
            lookup['by_sub_id'].setdefault(sid, row)
        email = str(row.get('email') or '').strip().lower()
        if email:
            lookup['by_email'].setdefault(email, row)
    return lookup


def _resolve_azure_profile_for_stripe_sub(
        sub,
        lookup: dict,
        email_cache: dict
) -> tuple[Optional[dict], str]:
    sid = str(getattr(sub, 'id', '') or '').strip()
    cid = str(getattr(sub, 'customer', '') or '').strip()
    if sid and sid in lookup['by_sub_id']:
        return lookup['by_sub_id'][sid], 'subscription_id'
    if cid and cid in lookup['by_customer']:
        return lookup['by_customer'][cid], 'customer_id'
    email = _get_stripe_customer_email_cached(cid, email_cache)
    if email and email in lookup['by_email']:
        return lookup['by_email'][email], 'email'
    return None, ''


def _stripe_sub_period_end_display(sub) -> str:
    end_ts = getattr(sub, 'current_period_end', None)
    if not end_ts:
        return '—'
    try:
        dt = datetime.fromtimestamp(int(end_ts), tz=timezone.utc)
        return dt.astimezone(_get_pacific_tzinfo()).strftime('%b %d, %Y')
    except Exception:
        return '—'


def _build_stripe_price_to_plan_map() -> dict[str, str]:
    """Map Stripe Price IDs from env to internal plan ids."""
    out: dict[str, str] = {}
    for plan_id in _rbi_embedded_checkout_plans():
        try:
            for price_id in _configured_stripe_price_ids_for_plan(plan_id):
                if price_id:
                    out[str(price_id)] = plan_id
        except Exception:
            pass
        try:
            price_id = _get_stripe_price_id(plan_id)
            if price_id:
                out[str(price_id)] = plan_id
        except Exception:
            pass
    return out


def _plan_id_to_product_label(plan_id: str) -> str:
    pid = _normalize_plan_id(plan_id)
    if not pid:
        return ''
    cfg = _get_plan_config(pid)
    if cfg:
        return f"{cfg.get('label') or pid} ({cfg.get('price') or ''})".strip()
    return pid.replace('_', ' ').title()


def _describe_stripe_subscription_product(
        sub,
        price_to_plan: dict[str, str]
) -> str:
    """Human-readable product/plan purchased for a Stripe subscription."""
    try:
        meta = _stripe_obj_get(sub, 'metadata', {}) or {}
        plan_id = _normalize_plan_id(
            str(_stripe_obj_get(meta, 'plan_id', '') or '')
        )
        if plan_id:
            label = _plan_id_to_product_label(plan_id)
            if label:
                return label

        price_id, interval, _interval_count = _get_subscription_price_id_and_recurring(
            sub
        )
        if price_id and price_id in price_to_plan:
            label = _plan_id_to_product_label(price_to_plan[price_id])
            if label:
                return label

        items = _stripe_obj_get(sub, 'items', None)
        items_data = _stripe_obj_get(items, 'data', []) if items else []
        first_item = items_data[0] if items_data else None
        if first_item:
            price = _stripe_obj_get(first_item, 'price', None)
            if price:
                nickname = str(
                    _stripe_obj_get(price, 'nickname', '') or ''
                ).strip()
                if nickname:
                    return nickname
                amount = _stripe_obj_get(price, 'unit_amount', None)
                currency = str(
                    _stripe_obj_get(price, 'currency', '') or ''
                ).upper()
                recurring = _stripe_obj_get(price, 'recurring', None)
                bill_interval = str(
                    _stripe_obj_get(recurring, 'interval', '') or ''
                ).strip() if recurring else interval
                if amount is not None:
                    try:
                        amt = float(amount) / 100.0
                        cur = currency or 'USD'
                        if bill_interval:
                            return f"{cur} {amt:.2f} / {bill_interval}"
                        return f"{cur} {amt:.2f}"
                    except Exception:
                        pass
                product = _stripe_obj_get(price, 'product', None)
                product_name = ''
                if isinstance(product, dict):
                    product_name = str(product.get('name') or '').strip()
                elif product is not None and not isinstance(product, str):
                    product_name = str(
                        _stripe_obj_get(product, 'name', '') or ''
                    ).strip()
                if product_name:
                    if amount is not None:
                        try:
                            amt = float(amount) / 100.0
                            cur = currency or 'USD'
                            if bill_interval:
                                return f"{product_name} ({cur} {amt:.2f} / {bill_interval})"
                            return f"{product_name} ({cur} {amt:.2f})"
                        except Exception:
                            pass
                    return product_name

        if interval == 'year':
            return 'Annual'
        if interval == 'month':
            return 'Monthly'
        if price_id:
            return price_id
    except Exception:
        pass
    return '—'


def _build_stripe_subscription_dashboard_rows(
        stripe_index: dict,
        users_rows: list,
        signup_lookup: dict,
        login_lookup: dict,
        revision_counts: dict,
) -> list[dict]:
    """One dashboard row per Stripe subscription object (matches Stripe dashboard count)."""
    subs = stripe_index.get('subscriptions') or []
    if not subs:
        return []

    lookup = _build_azure_profile_lookup(users_rows)
    email_cache: dict = {}
    price_to_plan = _build_stripe_price_to_plan_map()
    rows: list[dict] = []

    for sub in subs:
        sid = str(getattr(sub, 'id', '') or '').strip()
        cid = str(getattr(sub, 'customer', '') or '').strip()
        stripe_status = str(
            getattr(sub, 'status', '') or ''
        ).strip().lower()
        is_active = stripe_status in ('active', 'trialing')

        prof, match_source = _resolve_azure_profile_for_stripe_sub(
            sub,
            lookup,
            email_cache
        )

        if prof:
            uid = str(
                prof.get('id') or prof.get('PartitionKey') or ''
            ).strip()
            email = str(prof.get('email') or '').strip()
            name = str(prof.get('name') or '').strip()
            paid_until = str(prof.get('paid_until') or '').strip()
            created_at = _resolve_user_signup_date(
                uid,
                prof,
                signup_lookup
            )
            last_login_at, last_login_method = _resolve_user_last_login(
                uid,
                prof,
                login_lookup
            )
            rev_count = revision_counts.get(uid, 0)
            revision_ts = prof.get('revision_Timestamp') or prof.get(
                'revision_timestamp'
            ) or ''
            revision_ts_str = _coerce_datetime_iso(revision_ts)
            azure_linked = True
        else:
            uid = ''
            email = _get_stripe_customer_email_cached(cid, email_cache)
            name = ''
            paid_until = ''
            created_at = ''
            last_login_at = ''
            last_login_method = '—'
            rev_count = 0
            revision_ts_str = ''
            azure_linked = False

        sub_created_ts = int(getattr(sub, 'created', 0) or 0)
        sub_created_iso = ''
        if sub_created_ts:
            sub_created_iso = datetime.fromtimestamp(
                sub_created_ts,
                tz=timezone.utc
            ).isoformat()

        status_label, status_badge = _subscription_status_for_dashboard(
            prof,
            is_active,
            [sub]
        )
        period_end = _stripe_sub_period_end_display(sub)
        if period_end == '—' and paid_until:
            period_end = _format_paid_until(paid_until)

        product_purchased = _describe_stripe_subscription_product(
            sub,
            price_to_plan
        )
        if product_purchased == '—' and prof:
            azure_plan = _normalize_plan_id(
                str(prof.get('plan_status') or '').strip()
            )
            if azure_plan:
                product_purchased = _plan_id_to_product_label(
                    azure_plan
                ) or product_purchased

        rows.append(
            {
                'id': uid or '—',
                'email': email or '—',
                'name': name or '—',
                'product_purchased': product_purchased,
                'plan_status': stripe_status or '—',
                'subscription_status': status_label,
                'status_badge': status_badge,
                'is_active': is_active,
                'stripe_subscription_id': sid or '—',
                'stripe_customer_id': cid or '—',
                'azure_linked': azure_linked,
                'match_source': match_source or (
                    'stripe_only' if not azure_linked else '—'),
                'subscription_created_display': _format_any_datetime_pacific(
                    sub_created_iso
                ) or '—',
                'paid_until_display': period_end,
                'created_at_display': _format_any_datetime_pacific(
                    created_at
                ) or '—',
                'last_login_display': _format_any_datetime_pacific(
                    last_login_at
                ) or '—',
                'last_login_method': last_login_method or '—',
                'revision_count': rev_count,
                'last_revision_display': _format_any_datetime_pacific(
                    revision_ts_str
                ) if revision_ts_str else '—',
                '_sort_active': 0 if is_active else 1,
                '_sort_created': sub_created_ts,
            }
        )

    rows.sort(key=lambda r: r.get('_sort_created') or 0, reverse=True)
    rows.sort(key=lambda r: r.get('_sort_active', 1))
    for r in rows:
        r.pop('_sort_active', None)
        r.pop('_sort_created', None)
    return rows


def _find_stripe_customer_id_by_email(
        email: str,
        require_subscription_history: bool = False,
        allow_ephemeral: bool = False,
) -> str:
    """Best-effort lookup for a reusable Stripe customer id by email.

    By default, skip ephemeral checkout-only customers so abandoned embedded
    flows do not get treated as real billing profiles later.
    """
    e = (email or '').strip()
    if not e or not _stripe_enabled():
        return ''
    try:
        candidates = []
        seen_ids = set()

        def _append_customer_candidates(items) -> None:
            for cust in list(items or []):
                cid = str(getattr(cust, 'id', '') or '').strip()
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    candidates.append(cust)

        # Prefer search when available.
        try:
            res = stripe.Customer.search(query=f"email:'{e}'", limit=10)
            _append_customer_candidates(getattr(res, 'data', []) or [])
        except Exception:
            pass

        # Fallback: list by email.
        try:
            res2 = stripe.Customer.list(email=e, limit=10)
            _append_customer_candidates(getattr(res2, 'data', []) or [])
        except Exception:
            pass

        best_id = ''
        best_score = -1
        for cust in candidates:
            cid = str(getattr(cust, 'id', '') or '').strip()
            if not cid:
                continue
            meta = getattr(cust, 'metadata', None) or _stripe_obj_get(
                cust,
                'metadata',
                {}
            ) or {}
            if isinstance(meta, dict):
                ephemeral_flag = str(
                    meta.get('ephemeral_checkout') or ''
                ).strip()
            else:
                ephemeral_flag = str(
                    getattr(meta, 'ephemeral_checkout', '') or ''
                ).strip()
            has_sub_history = _stripe_customer_has_any_subscription(cid)
            if require_subscription_history and not has_sub_history:
                continue
            if ephemeral_flag == '1' and not allow_ephemeral and not has_sub_history:
                continue
            score = 0
            if has_sub_history:
                score += 100
            if ephemeral_flag != '1':
                score += 10
            if score > best_score:
                best_score = score
                best_id = cid
        if best_id:
            return best_id
    except Exception:
        return ''
    return ''


def _create_or_get_stripe_customer_for_user(
        user,
        persist_profile: bool = True,
        mark_ephemeral: bool = False
) -> str:
    """Find or create a Stripe Customer for the given user and persist the id to Azure profile.

    Returns the customer id or empty string on failure.
    """
    try:
        user_id = str(getattr(user, "id", "") or "")
        email = (getattr(user, "email", "") or "").strip()
        # Check existing profile
        cid = _get_stripe_customer_id_from_azure(user_id)
        if cid:
            return cid

        # Try best-effort lookup by email
        if email:
            found = _find_stripe_customer_id_by_email(email)
            if found:
                if persist_profile:
                    try:
                        table_client = get_users_table_client()
                        entity = {
                            "PartitionKey": str(user_id),
                            "RowKey": "profile",
                            "stripe_customer_id": str(found),
                        }
                        table_client.upsert_entity(
                            entity,
                            mode=UpdateMode.MERGE
                        )
                    except Exception:
                        pass
                return found

        # Create a new Stripe Customer
        if not _stripe_enabled():
            return ''

        customer_metadata = {"user_id": str(user_id)}
        if mark_ephemeral:
            customer_metadata["ephemeral_checkout"] = "1"
        cust = stripe.Customer.create(
            email=email or None,
            metadata=customer_metadata
        )
        customer_id = str(getattr(cust, 'id', '') or '')
        if customer_id and persist_profile:
            try:
                table_client = get_users_table_client()
                entity = {
                    "PartitionKey": str(user_id),
                    "RowKey": "profile",
                    "stripe_customer_id": customer_id,
                }
                table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
            except Exception:
                pass
        return customer_id
    except Exception:
        return ''


def _stripe_metadata_user_id(obj) -> str:
    """Best-effort user_id read from a Stripe object's metadata."""
    meta = getattr(obj, 'metadata', None) or _stripe_obj_get(
        obj,
        'metadata',
        {}
    ) or {}
    if isinstance(meta, dict):
        return str(meta.get('user_id') or '').strip()
    return str(getattr(meta, 'user_id', '') or '').strip()


def _cleanup_ephemeral_stripe_customer(
        customer_id: str,
        user_id: str = ''
) -> None:
    """Best-effort delete of an unpersisted ephemeral Stripe customer after abandoned checkout."""
    cid = str(customer_id or '').strip()
    uid = str(user_id or '').strip()
    if not cid or not _stripe_enabled():
        return
    try:

        cust = stripe.Customer.retrieve(cid)
        deleted = bool(
            getattr(cust, 'deleted', False) or _stripe_obj_get(
                cust,
                'deleted',
                False
            )
        )
        if deleted:
            return
        if _get_stripe_customer_id_from_azure(uid) == cid:
            return
        meta = getattr(cust, 'metadata', None) or _stripe_obj_get(
            cust,
            'metadata',
            {}
        ) or {}
        ephemeral_flag = str(
            meta.get('ephemeral_checkout') or ''
        ).strip() if isinstance(meta, dict) else str(
            getattr(meta, 'ephemeral_checkout', '') or ''
        ).strip()
        owner_uid = _stripe_metadata_user_id(cust)
        if ephemeral_flag != '1' or (
                uid and owner_uid and owner_uid != uid):
            return
        try:
            subs = stripe.Subscription.list(
                customer=cid,
                status='all',
                limit=20
            )
            for sub in list(getattr(subs, 'data', []) or []):
                status = str(
                    getattr(sub, 'status', '') or ''
                ).strip().lower()
                if status not in (
                        'canceled', 'cancelled', 'incomplete_expired'):
                    return
            stripe.Customer.delete(cid)
        except Exception:
            return
    except Exception:
        return


def _abandon_embedded_subscription_checkout(
        subscription_id: str,
        user_id: str
) -> tuple[bool, str]:
    """Best-effort cancel of an incomplete embedded subscription checkout."""
    sid = str(subscription_id or '').strip()
    uid = str(user_id or '').strip()
    if not sid or not uid or not _stripe_enabled():
        return False, 'missing_parameters'
    try:

        sub = stripe.Subscription.retrieve(
            sid,
            expand=['pending_setup_intent']
        )
    except Exception:
        return False, 'subscription_not_found'
    if _stripe_metadata_user_id(sub) != uid:
        return False, 'subscription_mismatch'
    if _stripe_subscription_grants_access(sub):
        return True, 'already_completed'
    customer_id = str(getattr(sub, 'customer', '') or '').strip()
    status = str(getattr(sub, 'status', '') or '').strip().lower()
    if status not in (
            'incomplete', 'trialing', 'past_due', 'unpaid',
            'incomplete_expired'):
        return True, f'ignored_{status or "unknown"}'
    try:
        if status != 'incomplete_expired':
            stripe.Subscription.delete(sid)
    except Exception:
        return False, 'subscription_cancel_failed'
    _cleanup_ephemeral_stripe_customer(customer_id, uid)
    return True, 'cleaned'


def _abandon_trial_hold_checkout(payment_intent_id: str, user_id: str) -> \
        tuple[bool, str]:
    """Best-effort cancel of an embedded trial-hold authorization before activation."""
    pi_id = str(payment_intent_id or '').strip()
    uid = str(user_id or '').strip()
    if not pi_id or not uid or not _stripe_enabled():
        return False, 'missing_parameters'
    try:

        intent = stripe.PaymentIntent.retrieve(pi_id)
    except Exception:
        return False, 'payment_intent_not_found'
    if _stripe_metadata_user_id(intent) != uid:
        return False, 'payment_intent_mismatch'
    customer_id = str(getattr(intent, 'customer', '') or '').strip()
    status = str(getattr(intent, 'status', '') or '').strip().lower()
    if status in ('canceled',):
        _cleanup_ephemeral_stripe_customer(customer_id, uid)
        return True, 'already_canceled'
    if status in (
            'requires_payment_method', 'requires_confirmation',
            'requires_action',
            'processing', 'requires_capture'):
        try:
            stripe.PaymentIntent.cancel(pi_id)
        except Exception:
            return False, 'payment_intent_cancel_failed'
        _cleanup_ephemeral_stripe_customer(customer_id, uid)
        return True, 'cleaned'
    if status == 'succeeded':
        return True, 'already_completed'
    return True, f'ignored_{status or "unknown"}'


def _find_user_id_by_stripe_customer_id(customer_id: str) -> str:
    """Return Azure user id (PartitionKey) for a Stripe customer, or empty string."""
    cid = (customer_id or '').strip()
    if not cid:
        return ''
    try:
        table_client = get_users_table_client()
        for e in table_client.list_entities():
            if e.get('RowKey') != 'profile':
                continue
            if str(e.get('stripe_customer_id') or '') == cid:
                return str(e.get('PartitionKey') or '').strip()
    except Exception:
        pass
    return ''


def _stripe_subscription_grants_access(sub) -> bool:
    """Return True only when a Stripe subscription should unlock product access.

    Trialing subscriptions created with a pending SetupIntent must NOT grant access
    until a default payment method is saved (card confirmed / RBI e-mandate registered).
    """
    if not sub:
        return False
    status = str(
        _stripe_obj_get(sub, 'status', '') or getattr(
            sub,
            'status',
            ''
        ) or ''
    ).strip().lower()
    if status in ('incomplete', 'incomplete_expired'):
        return False
    if status == 'active':
        return True
    if status == 'trialing':
        dpm = _stripe_obj_get(sub, 'default_payment_method', None)
        if not dpm:
            try:
                dpm = getattr(sub, 'default_payment_method', None)
            except Exception:
                dpm = None
        if dpm:
            return True
        pending_si = _stripe_obj_get(sub, 'pending_setup_intent', None)
        if not pending_si:
            try:
                pending_si = getattr(sub, 'pending_setup_intent', None)
            except Exception:
                pending_si = None
        if pending_si:
            return False
        return False
    return False


def _subscription_needs_payment_setup(sub) -> bool:
    """Return True when subscription exists but still needs card/setup confirmation."""
    if not sub:
        return False
    status = str(
        _stripe_obj_get(sub, 'status', '') or getattr(
            sub,
            'status',
            ''
        ) or ''
    ).strip().lower()
    if status == 'incomplete':
        return True
    if status == 'trialing' and not _stripe_subscription_grants_access(
            sub
    ):
        return True
    return False


def _find_resumable_pending_subscription(customer_id: str, plan_id: str):
    """Reuse an incomplete subscription awaiting SetupIntent confirmation (avoid duplicates on refresh)."""
    cid = (customer_id or '').strip()
    pid = _normalize_plan_id(plan_id)
    if not cid or not pid or not _stripe_enabled():
        return None
    try:

        res = stripe.Subscription.list(
            customer=cid,
            status='all',
            limit=20,
            expand=['data.pending_setup_intent']
        )
        candidates = list(getattr(res, 'data', []) or [])
        for sub in sorted(
                candidates,
                key=lambda s: int(getattr(s, 'created', 0) or 0),
                reverse=True
        ):
            if not _subscription_needs_payment_setup(sub):
                continue
            meta = getattr(sub, 'metadata', None) or {}
            sub_plan = ''
            if isinstance(meta, dict):
                sub_plan = str(meta.get('plan_id') or '').strip()
            else:
                sub_plan = str(getattr(meta, 'plan_id', '') or '').strip()
            if sub_plan and _normalize_plan_id(sub_plan) != pid:
                continue
            pending = getattr(sub, 'pending_setup_intent', None)
            if pending and getattr(pending, 'client_secret', None):
                return sub
            try:
                expanded = stripe.Subscription.retrieve(
                    str(getattr(sub, 'id', '') or ''),
                    expand=['pending_setup_intent'],
                )
                pending2 = getattr(expanded, 'pending_setup_intent', None)
                if pending2 and getattr(pending2, 'client_secret', None):
                    return expanded
            except Exception:
                continue
    except Exception:
        return None
    return None


def _persist_stripe_subscription_to_profile(
        user_id: str,
        sub,
        plan_id: str = '',
        force_access: bool = False  # Add this parameter
) -> None:
    """Persist Stripe subscription state to the user's Azure profile."""
    uid = str(user_id or '').strip()
    if not uid or not sub:
        return

    if not force_access and not _stripe_subscription_grants_access(sub):
        return

    try:
        customer_id = str(
            getattr(sub, 'customer', '') or _stripe_obj_get(
                sub,
                'customer',
                ''
            ) or ''
        )
        sub_status = str(
            getattr(sub, 'status', '') or _stripe_obj_get(
                sub,
                'status',
                ''
            ) or ''
        ).lower()

        sub_id = str(
            getattr(sub, 'id', '') or _stripe_obj_get(sub, 'id', '') or ''
        )
        is_trial = sub_status == 'trialing' or _normalize_plan_id(
            plan_id
        ) in ('trial_7d', EMAIL_TRIAL_PLAN_ID)
        status_for_db = "trial" if is_trial else (plan_id or sub_status)

        entity = {
            'PartitionKey': uid,
            'RowKey': 'profile',
            'is_paid': True,
            'plan_status': status_for_db,
            'stripe_customer_id': customer_id,
            'stripe_subscription_id': sub_id,
        }
        if sub_status == 'trialing' or _normalize_plan_id(plan_id) in (
                'trial_7d', EMAIL_TRIAL_PLAN_ID):
            entity['trial_used'] = True
            entity['trial_used_at'] = datetime.now(
                timezone.utc
            ).isoformat()
        try:
            current_period_end = getattr(
                sub,
                'current_period_end',
                None
            ) or _stripe_obj_get(sub, 'current_period_end', None)
            trial_end = getattr(sub, 'trial_end', None) or _stripe_obj_get(
                sub,
                'trial_end',
                None
            )
            ts = current_period_end or trial_end
            if ts:
                entity['paid_until'] = datetime.fromtimestamp(
                    int(ts),
                    tz=timezone.utc
                ).isoformat()
        except Exception:
            pass
        table_client = get_users_table_client()
        table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
    except Exception:
        pass


def _subscription_belongs_to_customer(
        subscription_id: str,
        customer_id: str
) -> bool:
    """Return True if the subscription belongs to the given Stripe customer."""
    sid = (subscription_id or '').strip()
    cid = (customer_id or '').strip()
    if not sid or not cid or not _stripe_enabled():
        return False
    try:

        sub = stripe.Subscription.retrieve(sid)
        return str(getattr(sub, 'customer', '') or '') == cid
    except Exception:
        return False


def _handle_setup_intent_succeeded_webhook(setup_intent: dict) -> None:
    """Activate user access after RBI e-mandate SetupIntent succeeds."""
    customer_id = str(setup_intent.get('customer') or '').strip()
    if not customer_id or not _stripe_enabled():
        return
    user_id = _find_user_id_by_stripe_customer_id(customer_id)
    if not user_id:
        meta = setup_intent.get('metadata') or {}
        user_id = str(meta.get('user_id') or '').strip()
    if not user_id:
        return
    try:

        subs = stripe.Subscription.list(
            customer=customer_id,
            status='all',
            limit=10
        )
        sdata = list(getattr(subs, 'data', []) or [])
        if not sdata:
            return

        def _rank(sub):
            status = str(getattr(sub, 'status', '') or '').strip().lower()
            created = int(getattr(sub, 'created', 0) or 0)
            sr = 0
            if status == 'trialing':
                sr = 3
            elif status == 'active':
                sr = 2
            elif status == 'incomplete':
                sr = 1
            return (sr, created)

        best = sorted(sdata, key=_rank, reverse=True)[0]
        best_status = str(
            getattr(best, 'status', '') or ''
        ).strip().lower()
        if not _stripe_subscription_grants_access(best):
            return
        plan_id = ''
        try:
            meta = getattr(best, 'metadata', None) or {}
            if isinstance(meta, dict):
                plan_id = str(meta.get('plan_id') or '').strip()
            else:
                plan_id = str(getattr(meta, 'plan_id', '') or '').strip()
        except Exception:
            plan_id = ''
        _persist_stripe_subscription_to_profile(
            user_id,
            best,
            plan_id=plan_id
        )
        logger.info(
            f"setup_intent.succeeded: persisted subscription for user {user_id}"
        )
    except Exception as e:
        logger.warning(
            f"setup_intent.succeeded webhook handler error: {str(e)}"
        )


@app.route('/stripe/create-setup-intent', methods=['POST'])
def stripe_create_setup_intent():
    """Deprecated for RBI e-mandate flows.

    Standalone SetupIntents do not register Indian e-mandates correctly.
    Use POST /stripe/create-subscription instead.
    """
    return jsonify(
        {
            'error': 'deprecated',
            'message': 'Use /stripe/create-subscription for RBI-compliant e-mandate registration.',
        }
    ), 410


@app.route('/stripe/create-subscription', methods=['POST'])
def stripe_create_subscription():
    """Create an incomplete subscription with pending SetupIntent (RBI e-mandate flow).

    Expects JSON: { "plan_id": "trial_7d" | "trial_10d_email" | "monthly_10_95" | "annual_6_95" }
    Returns subscription_id and pending_setup_intent_client_secret for confirmSetup.
    """
    if not getattr(current_user, 'is_authenticated', False):
        return jsonify({'error': 'authentication_required'}), 401
    if not _stripe_enabled():
        return jsonify({'error': 'stripe_not_configured'}), 400
    try:
        body = request.get_json(force=True) or {}
        plan_id = _normalize_plan_id(str(body.get('plan_id') or ''))
        if not plan_id:
            return jsonify({'error': 'missing_parameters'}), 400

        if _is_email_trial_plan(plan_id):
            invite = _get_email_trial_invite_from_session()
            if not invite:
                return jsonify(
                    {'error': 'invalid_invite',
                     'message': 'This trial offer link is invalid or expired.'}
                ), 403
            allowed, reason = _user_can_start_email_trial(current_user)
            if not allowed:
                if reason == 'already_subscribed':
                    return jsonify(
                        {'error': 'already_subscribed',
                         'message': 'You already have an active subscription.'}
                    ), 400
                return jsonify({'error': reason or 'not_allowed'}), 400
        elif plan_id == 'trial_7d' and _trial_already_used_for_user(
                current_user
        ):
            return jsonify({'error': 'trial_already_used'}), 400

        # Ensure customer exists
        customer_id = _create_or_get_stripe_customer_for_user(
            current_user,
            persist_profile=False,
            mark_ephemeral=True
        )
        if not customer_id:
            return jsonify({'error': 'customer_creation_failed'}), 500

        price_id = _get_stripe_price_id(plan_id)
        if not price_id:
            return jsonify({'error': 'price_not_configured'}), 400

        if plan_id not in _rbi_embedded_checkout_plans():
            return jsonify({'error': 'invalid_plan'}), 400

        user_id = str(getattr(current_user, 'id', '') or '')
        invite = _get_email_trial_invite_from_session() if _is_email_trial_plan(
            plan_id
        ) else None
        reinstate_from_offer = _consume_reinstate_offer_checkout_from_session()
        subscription_params = {
            'customer': customer_id,
            'items': [{'price': price_id, 'quantity': 1}],
            'payment_behavior': 'default_incomplete',
            'payment_settings': {
                'save_default_payment_method': 'on_subscription'},
            'expand': ['pending_setup_intent'],
            'metadata': {
                'plan_id': plan_id,
                'user_id': user_id,
                'campaign': str((invite or {}).get('campaign') or ''),
            },
        }
        if reinstate_from_offer:
            subscription_params['metadata']['reinstate_from_offer'] = '1'
        if _is_email_trial_plan(plan_id):
            trial_days = max(
                1,
                int((invite or {}).get('trial_days') or 10)
            )
            subscription_params[
                'trial_end'] = _stripe_trial_end_ts_for_days(trial_days)
        elif plan_id == 'trial_7d':
            subscription_params[
                'trial_end'] = _stripe_trial_end_ts_for_display()

        existing = _find_resumable_pending_subscription(
            customer_id,
            plan_id
        )
        if existing:
            sub = existing
        else:
            sub = stripe.Subscription.create(**subscription_params)

        # Return subscription id and pending SetupIntent client_secret (if present)
        pending = getattr(sub, 'pending_setup_intent', None)
        pending_client_secret = ''
        try:
            pending_client_secret = getattr(
                pending,
                'client_secret',
                ''
            ) or ''
        except Exception:
            pending_client_secret = ''
        if not pending_client_secret:
            return jsonify({'error': 'pending_setup_intent_missing'}), 500

        return jsonify(
            {
                'subscription_id': getattr(sub, 'id', ''),
                'pending_setup_intent_client_secret': pending_client_secret,
                'status': getattr(sub, 'status', ''),
                'customer_id': str(customer_id),
            }
        )
    except Exception as e:
        logger.exception('Error creating subscription')
        return jsonify(
            {'error': 'subscription_failed', 'message': str(e)}
        ), 500


@app.route('/stripe/complete-subscription', methods=['POST'])
def stripe_complete_subscription():
    """Finalize subscription after frontend confirms the pending SetupIntent."""
    if not getattr(current_user, 'is_authenticated', False):
        return jsonify({'error': 'authentication_required'}), 401
    if not _stripe_enabled():
        return jsonify({'error': 'stripe_not_configured'}), 400
    try:
        body = request.get_json(force=True) or {}
        subscription_id = str(body.get('subscription_id') or '').strip()
        if not subscription_id:
            return jsonify({'error': 'missing_parameters'}), 400

        sub = stripe.Subscription.retrieve(
            subscription_id,
            expand=['pending_setup_intent',
                    'latest_invoice.payment_intent', 'items.data.price'],
        )
        if _stripe_metadata_user_id(sub) != str(
                getattr(current_user, 'id', '') or ''
        ).strip():
            return jsonify({'error': 'subscription_not_found'}), 404
        if not _stripe_subscription_grants_access(sub):
            return jsonify(
                {
                    'error': 'payment_method_required',
                    'message': 'Please save a payment method to start your trial.',
                    'status': str(getattr(sub, 'status', '') or ''),
                }
            ), 400

        plan_id = ''
        try:
            meta = getattr(sub, 'metadata', None) or {}
            if isinstance(meta, dict):
                plan_id = str(meta.get('plan_id') or '').strip()
            else:
                plan_id = str(getattr(meta, 'plan_id', '') or '').strip()
        except Exception:
            plan_id = ''

        _persist_stripe_subscription_to_profile(
            str(getattr(current_user, 'id', '') or ''),
            sub,
            plan_id=plan_id
        )
        return jsonify(
            {'subscription_id': getattr(sub, 'id', ''),
             'status': getattr(sub, 'status', '')}
        )
    except Exception as e:
        logger.exception('Error completing subscription')
        return jsonify(
            {'error': 'complete_failed', 'message': str(e)}
        ), 500


@app.route('/stripe/create-trial-hold', methods=['POST'])
def stripe_create_trial_hold():
    """Create a manual-capture PaymentIntent for a trial authorization hold."""
    if not getattr(current_user, 'is_authenticated', False):
        return jsonify({'error': 'authentication_required'}), 401
    if not _stripe_enabled():
        return jsonify({'error': 'stripe_not_configured'}), 400

    body = request.get_json(force=True) or {}
    plan_id = _normalize_plan_id(
        str(body.get('plan_id') or 'trial_7d')
    ) or 'trial_7d'
    if not _should_use_trial_authorization_hold(plan_id):
        return jsonify({'error': 'trial_hold_not_available'}), 400

    if _is_email_trial_plan(plan_id):
        if not _get_email_trial_invite_from_session():
            return jsonify(
                {'error': 'invalid_invite',
                 'message': 'This trial offer link is invalid or expired.'}
            ), 403
        allowed, reason = _user_can_start_email_trial(current_user)
        if not allowed:
            if reason == 'already_subscribed':
                return jsonify(
                    {'error': 'already_subscribed',
                     'message': 'You already have an active subscription.'}
                ), 400
            return jsonify({'error': reason or 'not_allowed'}), 400
    elif plan_id == 'trial_7d' and _trial_already_used_for_user(
            current_user
    ):
        return jsonify({'error': 'trial_already_used'}), 400

    try:

        user_id = str(getattr(current_user, 'id', '') or '')
        intent = _create_trial_hold_payment_intent(
            user_id,
            plan_id=plan_id
        )
        if not intent:
            return jsonify({'error': 'payment_intent_failed'}), 500

        return jsonify(
            {
                'clientSecret': getattr(intent, 'client_secret', ''),
                'customerId': str(getattr(intent, 'customer', '') or ''),
                'paymentIntentId': getattr(intent, 'id', ''),
                'amountCents': int(getattr(intent, 'amount', 0) or 0),
                'currency': str(
                    getattr(intent, 'currency', 'usd') or 'usd'
                ),
                'trialHoldDays': _get_trial_hold_days(plan_id),
                'planId': plan_id,
            }
        )
    except Exception as e:
        logger.exception('Error creating trial hold PaymentIntent')
        return jsonify(
            {'error': 'trial_hold_failed', 'message': str(e)}
        ), 500


@app.route('/stripe/activate-trial-hold', methods=['POST'])
def stripe_activate_trial_hold():
    """Activate trial access after the authorization hold is confirmed (requires_capture)."""
    if not getattr(current_user, 'is_authenticated', False):
        return jsonify({'error': 'authentication_required'}), 401
    if not _stripe_enabled():
        return jsonify({'error': 'stripe_not_configured'}), 400

    body = request.get_json(force=True) or {}
    payment_intent_id = str(
        body.get('paymentIntentId') or body.get('payment_intent_id') or ''
    ).strip()
    if not payment_intent_id:
        return jsonify({'error': 'missing_parameters'}), 400

    user_id = str(getattr(current_user, 'id', '') or '')
    ok, reason = _activate_trial_hold(user_id, payment_intent_id)
    if not ok:
        status = 400
        if reason == 'payment_intent_mismatch':
            status = 403
        return jsonify(
            {'error': reason, 'message': 'Payment was not authorized'}
        ), status

    return jsonify({'success': True, 'paymentIntentId': payment_intent_id})


@app.route('/stripe/cancel-trial-hold', methods=['POST'])
def stripe_cancel_trial_hold():
    """Revoke trial-hold access without manually canceling the card authorization."""
    if not getattr(current_user, 'is_authenticated', False):
        return jsonify({'error': 'authentication_required'}), 401
    if not _stripe_enabled():
        return jsonify({'error': 'stripe_not_configured'}), 400

    user_id = str(getattr(current_user, 'id', '') or '')
    prof = get_user_profile_azure(user_id) or {}
    pi_id = str(prof.get('trial_hold_payment_intent_id') or '').strip()
    if not pi_id:
        return jsonify({'error': 'no_active_trial_hold'}), 404

    if not _payment_intent_belongs_to_user(pi_id, user_id):
        return jsonify({'error': 'payment_intent_mismatch'}), 403

    _revoke_trial_hold_profile(user_id, cancelled=True)

    return jsonify({'success': True})


@app.route('/stripe/abandon-checkout', methods=['POST'])
def stripe_abandon_checkout():
    """Best-effort cleanup for embedded checkout that was initialized but not completed."""
    if not getattr(current_user, 'is_authenticated', False):
        return jsonify({'error': 'authentication_required'}), 401
    if not _stripe_enabled():
        return jsonify({'error': 'stripe_not_configured'}), 400

    body = request.get_json(silent=True) or {}
    flow = str(body.get('flow') or '').strip().lower()
    user_id = str(getattr(current_user, 'id', '') or '').strip()

    if flow == 'subscription':
        ok, reason = _abandon_embedded_subscription_checkout(
            str(body.get('subscription_id') or '').strip(),
            user_id,
        )
    elif flow == 'trial_hold':
        ok, reason = _abandon_trial_hold_checkout(
            str(
                body.get('payment_intent_id') or body.get(
                    'paymentIntentId'
                ) or ''
            ).strip(),
            user_id,
        )
    else:
        return jsonify({'error': 'invalid_flow'}), 400

    return jsonify({'success': bool(ok), 'reason': reason})


def _find_trialing_subscription_for_customer(customer_id: str) -> Optional[
    dict]:
    """Return a trialing subscription object (Stripe) for a customer, or None."""
    cid = (customer_id or "").strip()
    if not cid or not _stripe_enabled():
        return None
    try:
        res = stripe.Subscription.list(
            customer=cid,
            status="trialing",
            limit=1
        )
        data = list(getattr(res, "data", []) or [])
        if not data:
            return None
        sub = data[0]
        try:
            sub = stripe.Subscription.retrieve(
                sub.id,
                expand=["items.data"]
            )
        except Exception:
            pass
        return sub
    except Exception:
        return None


def _get_paid_until_from_stripe(subscription_id: str) -> str:
    """Return ISO timestamp (UTC) for next renewal/end using Stripe subscription, or '' if unknown."""
    sid = (subscription_id or '').strip()
    if not sid:
        return ''
    if not _stripe_enabled():
        return ''
    try:

        sub = stripe.Subscription.retrieve(sid)
        # Prefer current_period_end; for trialing subscriptions, trial_end can be useful too.
        trial_end = getattr(sub, 'trial_end', None)
        current_period_end = getattr(sub, 'current_period_end', None)
        ts = current_period_end or trial_end
        if ts:
            return datetime.fromtimestamp(
                int(ts),
                tz=timezone.utc
            ).isoformat()
        return ''
    except Exception:
        return ''


def _add_interval_approx(
        dt: datetime,
        interval: str,
        interval_count: int
) -> datetime:
    """Calendar-accurate interval math without extra deps."""
    c = int(interval_count or 1)
    if c < 1:
        c = 1
    interval = (interval or '').strip().lower()
    if interval == 'year':
        # Add years by adding months to preserve behavior around Feb 29.
        interval = 'month'
        c = 12 * c
    if interval == 'month':
        # Add months while clamping day-of-month to the last valid day.
        month_index = (dt.month - 1) + c
        year = dt.year + (month_index // 12)
        month = (month_index % 12) + 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        return dt.replace(year=year, month=month, day=day)
    if interval == 'week':
        return dt + timedelta(days=7 * c)
    if interval == 'day':
        return dt + timedelta(days=1 * c)
    return dt


def _get_stripe_plan_dates_for_customer(customer_id: str) -> dict:
    """Return best-effort plan date info from Stripe for a customer.

    Output keys:
      - subscription_id
      - status
      - interval_label (e.g. 'Annual'/'Monthly'/'' )
      - next_billing_iso (trial_end if trialing else current_period_end)
            - paid_through_est_iso (trial_end if trialing; else current_period_end)
    """
    cid = (customer_id or '').strip()
    if not cid or not _stripe_enabled():
        return {}
    try:

        subs = stripe.Subscription.list(
            customer=cid,
            status='all',
            limit=20
        )
        data = list(getattr(subs, 'data', []) or [])
        if not data:
            return {}

        def _rank(sub):
            status = str(getattr(sub, 'status', '') or '').lower()
            current_period_end = int(
                getattr(sub, 'current_period_end', 0) or 0
            )
            # Prefer active > trialing > others; then later period end.
            status_rank = 0
            if status == 'active':
                status_rank = 3
            elif status == 'trialing':
                status_rank = 2
            elif status in ('past_due', 'unpaid'):
                status_rank = 1
            return (status_rank, current_period_end)

        best = sorted(data, key=_rank, reverse=True)[0]
        # Re-fetch with expanded price/recurring so interval math works reliably (Stripe list results can be "thin")
        try:
            best = stripe.Subscription.retrieve(
                best.id,
                expand=["items.data.price"]
            )
        except Exception:
            pass
        status = str(getattr(best, 'status', '') or '')
        trial_end = getattr(best, 'trial_end', None)
        current_period_end = getattr(best, 'current_period_end', None)

        # Interval label (use first item). Stripe objects can sometimes deserialize into plain dicts,
        # so handle both dict and StripeObject attribute access.
        interval = ''
        interval_count = 1
        try:
            items = getattr(best, 'items', None)
            items_data = getattr(items, 'data', []) if items else []
            if items_data:
                price = getattr(items_data[0], 'price', None)
                if isinstance(price, dict):
                    recurring = price.get('recurring')
                else:
                    recurring = getattr(
                        price,
                        'recurring',
                        None
                    ) if price else None
                if isinstance(recurring, dict):
                    interval = str(recurring.get('interval') or '')
                    interval_count = int(
                        recurring.get('interval_count') or 1
                    )
                else:
                    interval = str(
                        getattr(recurring, 'interval', '') or ''
                    )
                    interval_count = int(
                        getattr(recurring, 'interval_count', 1) or 1
                    )
        except Exception:
            interval = ''
            interval_count = 1

        interval_label = ''
        if interval == 'year':
            interval_label = 'Annual'
        elif interval == 'month':
            interval_label = 'Monthly'

        next_ts = None
        if str(status).lower() == 'trialing' and trial_end:
            next_ts = int(trial_end)
        elif current_period_end:
            next_ts = int(current_period_end)

        paid_through_est_ts = None
        if str(status).lower() == 'trialing' and trial_end:
            # During trial, access is valid through trial_end (not trial_end + first paid interval).
            paid_through_est_ts = int(trial_end)
        elif current_period_end:
            paid_through_est_ts = int(current_period_end)

        def _ts_to_iso(ts: Optional[int]) -> str:
            try:
                if not ts:
                    return ''
                return datetime.fromtimestamp(
                    int(ts),
                    tz=timezone.utc
                ).isoformat()
            except Exception:
                return ''

        return {
            'subscription_id': str(getattr(best, 'id', '') or ''),
            'status': status,
            'interval_label': interval_label,
            'next_billing_iso': _ts_to_iso(next_ts),
            'paid_through_est_iso': _ts_to_iso(paid_through_est_ts),
        }
    except Exception:
        return {}


def _get_stripe_plan_dates_for_subscription(subscription_id: str) -> dict:
    """Fallback when we only have a subscription id (e.g., profile missing stripe_customer_id)."""
    sid = (subscription_id or '').strip()
    if not sid or not _stripe_enabled():
        return {}
    try:

        sub = stripe.Subscription.retrieve(
            sid,
            expand=["items.data.price"]
        )
        status = str(getattr(sub, 'status', '') or '')
        trial_end = getattr(sub, 'trial_end', None)
        current_period_end = getattr(sub, 'current_period_end', None)
        start_date = getattr(sub, 'start_date', None) or getattr(
            sub,
            'billing_cycle_anchor',
            None
        )

        interval = ''
        interval_count = 1
        try:
            items = getattr(sub, 'items', None)
            items_data = getattr(items, 'data', []) if items else []
            if items_data:
                price = getattr(items_data[0], 'price', None)
                if isinstance(price, dict):
                    recurring = price.get('recurring')
                else:
                    recurring = getattr(
                        price,
                        'recurring',
                        None
                    ) if price else None
                if isinstance(recurring, dict):
                    interval = str(recurring.get('interval') or '')
                    interval_count = int(
                        recurring.get('interval_count') or 1
                    )
                else:
                    interval = str(
                        getattr(recurring, 'interval', '') or ''
                    )
                    interval_count = int(
                        getattr(recurring, 'interval_count', 1) or 1
                    )
        except Exception:
            interval = ''
            interval_count = 1

        interval_label = ''
        if interval == 'year':
            interval_label = 'Annual'
        elif interval == 'month':
            interval_label = 'Monthly'

        next_ts = None
        if str(status).lower() == 'trialing' and trial_end:
            next_ts = int(trial_end)
        elif current_period_end:
            next_ts = int(current_period_end)
        elif start_date and interval:
            try:
                base_dt = datetime.fromtimestamp(
                    int(start_date),
                    tz=timezone.utc
                )
                next_ts = int(
                    _add_interval_approx(
                        base_dt,
                        interval,
                        interval_count
                    ).timestamp()
                )
            except Exception:
                next_ts = int(start_date)

        paid_through_est_ts = None
        if str(status).lower() == 'trialing' and trial_end:
            # During trial, access is valid through trial_end (not trial_end + first paid interval).
            paid_through_est_ts = int(trial_end)
        elif current_period_end:
            paid_through_est_ts = int(current_period_end)
        elif start_date and interval:
            try:
                base_dt = datetime.fromtimestamp(
                    int(start_date),
                    tz=timezone.utc
                )
                paid_through_est_ts = int(
                    _add_interval_approx(
                        base_dt,
                        interval,
                        interval_count
                    ).timestamp()
                )
            except Exception:
                paid_through_est_ts = int(start_date)

        def _ts_to_iso(ts: Optional[int]) -> str:
            try:
                if not ts:
                    return ''
                return datetime.fromtimestamp(
                    int(ts),
                    tz=timezone.utc
                ).isoformat()
            except Exception:
                return ''

        return {
            'subscription_id': str(getattr(sub, 'id', '') or ''),
            'status': status,
            'interval_label': interval_label,
            'next_billing_iso': _ts_to_iso(next_ts),
            'paid_through_est_iso': _ts_to_iso(paid_through_est_ts),
        }
    except Exception:
        return {}


def _get_subscription_price_id_and_recurring(sub_obj) -> tuple[
    str, str, int]:
    """Return (price_id, interval, interval_count) from a subscription object; robust to dict/StripeObject."""
    try:
        items = getattr(sub_obj, 'items', None)
        items_data = getattr(items, 'data', []) if items else []
        first_item = items_data[0] if items_data else None
        # items_data entries can be StripeObjects or dicts
        if isinstance(first_item, dict):
            price = first_item.get('price')
        else:
            price = getattr(
                first_item,
                'price',
                None
            ) if first_item else None
        # Sometimes Stripe returns a bare price id string
        if isinstance(price, str):
            return (price.strip(), '', 1)
        if isinstance(price, dict):
            price_id = str(price.get('id') or '').strip()
            recurring = price.get('recurring')
        else:
            price_id = str(
                getattr(price, 'id', '') or ''
            ).strip() if price else ''
            recurring = getattr(
                price,
                'recurring',
                None
            ) if price else None

        interval = ''
        interval_count = 1
        if isinstance(recurring, dict):
            interval = str(recurring.get('interval') or '').strip()
            interval_count = int(recurring.get('interval_count') or 1)
        else:
            interval = str(
                getattr(recurring, 'interval', '') or ''
            ).strip()
            interval_count = int(
                getattr(recurring, 'interval_count', 1) or 1
            )
        return (price_id, interval, interval_count)
    except Exception:
        return ('', '', 1)


def _stripe_obj_get(obj, key: str, default=None):
    """Safely read key from StripeObject or dict by converting to a raw dictionary."""
    try:
        if obj is None:
            return default

        # If it's a native StripeObject wrapper, convert it safely to a dict first
        if hasattr(obj, "to_dict"):
            obj = obj.to_dict()

        if isinstance(obj, dict):
            return obj.get(key, default)

        return getattr(obj, key, default)
    except Exception:
        return default


def _stripe_schedule_id_from_subscription(sub) -> str:
    """Return subscription schedule id when Stripe manages the subscription via a schedule."""
    sched = _stripe_obj_get(sub, "schedule", None)
    if not sched:
        return ""
    if isinstance(sched, str):
        return sched.strip()
    if isinstance(sched, dict):
        return str(sched.get("id") or "").strip()
    return str(getattr(sched, "id", "") or "").strip()


def _stripe_subscription_cancel_scheduled(sub, schedule=None) -> bool:
    """True when cancellation is scheduled (directly or via subscription schedule)."""
    if bool(_stripe_obj_get(sub, "cancel_at_period_end", False)):
        return True
    if _stripe_obj_get(sub, "cancel_at", None):
        return True
    schedule_id = _stripe_schedule_id_from_subscription(sub)
    if not schedule_id:
        return False
    try:
        if schedule is None:
            schedule = stripe.SubscriptionSchedule.retrieve(schedule_id)
        if str(
                _stripe_obj_get(schedule, "end_behavior", "") or ""
        ).strip().lower() == "cancel":
            return True
    except Exception:
        pass
    return False


def _stripe_subscription_modify(
        subscription_id: str,
        sub=None,
        **modify_params
):
    """Modify subscription; route cancel/reinstate through schedule when required by Stripe."""
    sid = (subscription_id or "").strip()
    if not sid or not modify_params:
        return None
    if sub is None:
        sub = stripe.Subscription.retrieve(sid)

    schedule_id = _stripe_schedule_id_from_subscription(sub)
    touches_cancel = ("cancel_at_period_end" in modify_params) or (
            "cancel_at" in modify_params)
    extra_params = {k: v for k, v in modify_params.items() if
                    k not in ("cancel_at_period_end", "cancel_at")}

    if schedule_id and touches_cancel:
        cancel_at_period_end = modify_params.get("cancel_at_period_end")
        if cancel_at_period_end is True:
            stripe.SubscriptionSchedule.modify(
                schedule_id,
                end_behavior="cancel"
            )
        elif cancel_at_period_end is False:
            stripe.SubscriptionSchedule.modify(
                schedule_id,
                end_behavior="release"
            )
        else:
            stripe.Subscription.modify(sid, **modify_params)
            return None
        if extra_params:
            try:
                return stripe.Subscription.modify(sid, **extra_params)
            except stripe.error.InvalidRequestError as exc:
                logger.warning(
                    "stripe subscription modify extras skipped for schedule-managed sub %s: %s",
                    sid,
                    str(exc)[:240],
                )
        return None

    return stripe.Subscription.modify(sid, **modify_params)


def _stripe_upcoming_invoice(customer_id: str, subscription_id: str):
    """Get upcoming invoice using a method compatible with older stripe python versions."""
    cid = (customer_id or "").strip()
    sid = (subscription_id or "").strip()
    if not cid or not sid:
        return None
    try:
        # Newer stripe versions have stripe.Invoice.upcoming(...)
        if hasattr(stripe, "Invoice") and hasattr(
                stripe.Invoice,
                "upcoming"
        ):
            return stripe.Invoice.upcoming(customer=cid, subscription=sid)
    except Exception:
        pass
    # Fallback: call the endpoint directly
    try:
        return stripe.Invoice._static_request(
            "get",
            "/v1/invoices/upcoming",
            params={"customer": cid, "subscription": sid}
        )
    except Exception:
        return None


def _stripe_subscription_raw(subscription_id: str):
    """Fetch raw subscription JSON via low-level request (works across stripe library versions)."""
    sid = (subscription_id or "").strip()
    if not sid:
        return None
    try:
        return stripe.Subscription._static_request(
            "get",
            f"/v1/subscriptions/{sid}",
            params={}
        )
    except Exception:
        return None


def _stripe_latest_invoice_for_subscription(subscription_id: str):
    """Fetch latest invoice for a subscription (best-effort across stripe versions)."""
    sid = (subscription_id or "").strip()
    if not sid:
        return None
    try:
        if hasattr(stripe, "Invoice") and hasattr(stripe.Invoice, "list"):
            invs = stripe.Invoice.list(subscription=sid, limit=1)
            data = list(getattr(invs, "data", []) or [])
            if data:
                return data[0]
    except Exception:
        pass
    try:
        res = stripe.Invoice._static_request(
            "get",
            "/v1/invoices",
            params={"subscription": sid, "limit": 1}
        )
        data = _stripe_obj_get(res, "data", []) or []
        if data:
            return data[0]
    except Exception:
        return None
    return None


def _stripe_cancellation_paid_history_flags(subscription_id: str) -> dict:
    """Return paid-history flags used for cancellation email targeting."""
    sid = (subscription_id or "").strip()
    out = {
        "eligible": False,
        "reason": "unknown",
        "has_real_paid_history": False,
        "latest_paid_is_real": False,
    }
    if not sid:
        out["reason"] = "missing_subscription_id"
        return out

    invoices = []
    try:
        if hasattr(stripe, "Invoice") and hasattr(stripe.Invoice, "list"):
            invs = stripe.Invoice.list(subscription=sid, limit=24)
            invoices = list(getattr(invs, "data", []) or [])
    except Exception:
        invoices = []

    if not invoices:
        try:
            res = stripe.Invoice._static_request(
                "get",
                "/v1/invoices",
                params={"subscription": sid, "limit": 24}
            )
            invoices = list(_stripe_obj_get(res, "data", []) or [])
        except Exception:
            invoices = []

    if not invoices:
        out["reason"] = "no_invoices"
        return out

    paid_invoices = []
    for inv in invoices:
        if bool(_stripe_obj_get(inv, "paid", False)):
            paid_invoices.append(inv)

    if not paid_invoices:
        out["reason"] = "no_paid_invoices"
        return out

    has_real_paid_history = False
    for inv in paid_invoices:
        try:
            amount_paid = int(_stripe_obj_get(inv, "amount_paid", 0) or 0)
        except Exception:
            amount_paid = 0
        if amount_paid > 0:
            has_real_paid_history = True
            break

    latest_paid = paid_invoices[0]
    try:
        latest_paid_amount = int(
            _stripe_obj_get(latest_paid, "amount_paid", 0) or 0
        )
    except Exception:
        latest_paid_amount = 0
    latest_paid_is_real = latest_paid_amount > 0

    out["has_real_paid_history"] = bool(has_real_paid_history)
    out["latest_paid_is_real"] = bool(latest_paid_is_real)
    out["eligible"] = bool(has_real_paid_history and latest_paid_is_real)

    if out["eligible"]:
        out["reason"] = "eligible"
    elif not has_real_paid_history:
        out["reason"] = "no_real_paid_history"
    elif not latest_paid_is_real:
        out["reason"] = "latest_paid_was_zero"
    else:
        out["reason"] = "ineligible"
    return out


def _stripe_customer_has_any_subscription(customer_id: str) -> bool:
    """Return True if a Stripe customer has *any* subscription history.

    We use this to enforce that the trial offer is one-time.
    Best-effort across stripe-python versions.
    """
    cid = (customer_id or "").strip()
    if not cid or not _stripe_enabled():
        return False
    try:
        # Preferred: include canceled subs
        res = stripe.Subscription.list(customer=cid, status="all", limit=1)
        data = list(getattr(res, "data", []) or [])
        return bool(data)
    except Exception:
        pass
    try:
        # Fallback: at least detect active subs
        res2 = stripe.Subscription.list(customer=cid, limit=1)
        data2 = list(getattr(res2, "data", []) or [])
        return bool(data2)
    except Exception:
        pass
    try:
        # Lowest-level fallback
        res3 = stripe.Subscription._static_request(
            "get",
            "/v1/subscriptions",
            params={"customer": cid, "status": "all", "limit": 1},
        )
        data3 = _stripe_obj_get(res3, "data", []) or []
        return bool(data3)
    except Exception:
        return False


def _stripe_customer_has_trial_payment_history(customer_id: str) -> bool:
    """Return True if a Stripe customer has completed a standalone one-time trial payment session.

    Scans completed Checkout Sessions to catch users attempting to repeat a
    one-time trial tier. Best-effort across multiple stripe-python versions.
    """
    cid = (customer_id or "").strip()
    if not cid or not _stripe_enabled():
        return False

    def _inspect_sessions_data(sessions_list) -> bool:
        """Helper to parse raw or structural checkout lists for trial metadata signals."""
        if not sessions_list:
            return False
        for sess in sessions_list:
            if not sess:
                continue

            # Extract status safely depending on object binding
            status = str(
                (sess.get("status") if isinstance(
                    sess,
                    dict
                ) else getattr(sess, "status", "")) or ""
            ).strip().lower()

            if status == "complete":
                meta = (sess.get("metadata") if isinstance(
                    sess,
                    dict
                ) else getattr(sess, "metadata", {})) or {}
                if not isinstance(meta, dict):
                    try:
                        meta = dict(meta)
                    except Exception:
                        meta = {}

                plan_role = str(
                    meta.get("plan_role") or ""
                ).strip().lower()
                trial_deposit = str(
                    meta.get("trial_deposit_payment") or ""
                ).strip()

                if plan_role == "trial" or trial_deposit == "1":
                    return True
        return False

    # 1. Preferred Strategy: Auto-paging or list lookup via modern SDK
    try:
        res = stripe.checkout.Session.list(customer=cid, limit=20)
        data = list(getattr(res, "data", []) or [])
        if _inspect_sessions_data(data):
            return True
    except Exception:
        pass

    # 2. Fallback Strategy: Direct static request path to circumvent structural variance
    try:
        res2 = stripe.checkout.Session._static_request(
            "get",
            "/v1/checkout/sessions",
            params={"customer": cid, "limit": 20},
        )
        data2 = _stripe_obj_get(res2, "data", []) or []
        if _inspect_sessions_data(data2):
            return True
    except Exception:
        pass

    return False


def _trial_already_used_for_user(user_obj: Optional['User']) -> bool:
    """Return True if the trial should be blocked for this user."""
    try:
        if not user_obj or not getattr(
                user_obj,
                'is_authenticated',
                False
        ):
            return False

        # 0. Development Bypasses
        from flask import session, request

        try:
            host = str(getattr(request, "host", "") or "").lower()
            if (host.startswith("127.0.0.1") or host.startswith(
                    "localhost"
            )) and session.get('dev_bypass_trial_check'):
                return False
        except Exception:
            pass

        # If they're already paid/trialing via our own checks, they shouldn't buy the trial.
        try:
            if is_paid_user(user_obj):
                return True
        except Exception:
            pass

        # ... Rest of your existing implementation stays exactly the same ...

        prof = get_user_profile_azure(getattr(user_obj, 'id', '')) or {}

        # 1. Explicit persisted flags (set by webhook / checkout_complete)
        if bool(prof.get('trial_used', False)):
            return True
        if str(prof.get('trial_used_at') or '').strip():
            return True

        # 2. If the user has any known plan status other than free, treat the trial as already used.
        plan_status = str(prof.get('plan_status') or '').strip().lower()
        if plan_status and plan_status != 'free':
            return True

        # 3. Stripe-side cross-checks
        if _stripe_enabled():
            customer_id = str(prof.get('stripe_customer_id') or '').strip()
            if not customer_id:
                email = (getattr(user_obj, 'email', '') or '').strip()
                if email:
                    customer_id = _find_stripe_customer_id_by_email(
                        email,
                        require_subscription_history=False
                    )

            if customer_id:
                # Check A: Does this customer have standard subscription history?
                if _stripe_customer_has_any_subscription(customer_id):
                    return True

                # Check B: Did this customer purchase the standalone trial payment product?
                if _stripe_customer_has_trial_payment_history(customer_id):
                    return True

        return False
    except Exception:
        return False


def _get_stripe_price_id(plan_id: str) -> Optional[str]:
    """Map internal plan IDs to Stripe Price IDs via env vars."""
    plan_id = _normalize_plan_id(plan_id)

    if plan_id.startswith('price_'):
        return plan_id

    if plan_id in ('trial_7d', EMAIL_TRIAL_PLAN_ID):
        # Trial should be a subscription (auto-converts to monthly unless canceled).
        # Use a recurring monthly price here (or a dedicated trial recurring price).
        if _is_india_pricing_region():
            return (
                    (os.getenv(
                        'STRIPE_PRICE_TRIAL_RECURRING_INR'
                    ) or '').strip()
                    or (os.getenv(
                'STRIPE_PRICE_MONTHLY_10_95_INR'
            ) or '').strip()
                    or (os.getenv(
                'STRIPE_PRICE_TRIAL_RECURRING'
            ) or '').strip()
                    or (os.getenv(
                'STRIPE_PRICE_MONTHLY_10_95'
            ) or '').strip()
                    or None
            )
        return (
                (os.getenv('STRIPE_PRICE_TRIAL_RECURRING') or '').strip()
                or (os.getenv('STRIPE_PRICE_MONTHLY_10_95') or '').strip()
                or None
        )
    if plan_id == 'monthly_10_95':
        if _is_india_pricing_region():
            return (
                    (os.getenv(
                        'STRIPE_PRICE_MONTHLY_10_95_INR'
                    ) or '').strip()
                    or (os.getenv(
                'STRIPE_PRICE_MONTHLY_10_95'
            ) or '').strip()
                    or None
            )
        return (os.getenv(
            'STRIPE_PRICE_MONTHLY_10_95'
        ) or '').strip() or None
    if plan_id == 'annual_6_95':
        if _is_india_pricing_region():
            return (
                    (os.getenv(
                        'STRIPE_PRICE_ANNUAL_6_95_INR'
                    ) or '').strip()
                    or (os.getenv(
                'STRIPE_PRICE_ANNUAL_6_95'
            ) or '').strip()
                    or None
            )
        return (os.getenv(
            'STRIPE_PRICE_ANNUAL_6_95'
        ) or '').strip() or None
    return None


def _configured_stripe_price_ids_for_plan(plan_id: str) -> frozenset:
    """Non-empty Stripe Price IDs from env for this plan (USD + INR), for matching subscriptions to plans."""
    plan_id = _normalize_plan_id(plan_id)
    raw: list[str] = []
    if plan_id == 'monthly_10_95':
        for k in (
                'STRIPE_PRICE_MONTHLY_10_95',
                'STRIPE_PRICE_MONTHLY_10_95_INR'):
            v = (os.getenv(k) or '').strip()
            if v:
                raw.append(v)
    elif plan_id == 'annual_6_95':
        for k in (
                'STRIPE_PRICE_ANNUAL_6_95',
                'STRIPE_PRICE_ANNUAL_6_95_INR'):
            v = (os.getenv(k) or '').strip()
            if v:
                raw.append(v)
    return frozenset(raw)


def _get_stripe_trial_upfront_fee_price_id() -> Optional[str]:
    """Optional one-time fee charged at checkout for email-trial campaigns.

    Legacy env vars STRIPE_PRICE_TRIAL_FEE_1_85* are still supported.
    """
    return _get_stripe_trial_deposit_price_id()


def _get_stripe_trial_deposit_price_id() -> Optional[str]:
    """Optional one-time Stripe Price for the trial deposit (defaults to monthly plan amount)."""
    keys = ['STRIPE_PRICE_TRIAL_DEPOSIT_10_95']
    if _is_india_pricing_region():
        keys = ['STRIPE_PRICE_TRIAL_DEPOSIT_10_95_INR',
                'STRIPE_PRICE_TRIAL_DEPOSIT_10_95'] + keys
    keys.extend(
        ['STRIPE_PRICE_TRIAL_FEE_1_85_INR',
         'STRIPE_PRICE_TRIAL_FEE_1_85'] if _is_india_pricing_region() else [
            'STRIPE_PRICE_TRIAL_FEE_1_85']
    )
    for key in keys:
        value = (os.getenv(key) or '').strip()
        if value:
            return value
    return None


def _get_trial_deposit_amount_cents(plan_id: str = None) -> int:
    """One-time trial deposit amount in cents (defaults to the monthly plan price)."""
    if plan_id:
        plan = _get_plan_by_price_id(plan_id)
        if plan and plan.get('unit_amount') and plan.get(
                'unit_amount'
        ) > 0:
            return plan['unit_amount']

    override = (os.getenv('STRIPE_TRIAL_DEPOSIT_CENTS') or '').strip()
    if override.isdigit():
        return int(override)
    deposit_price_id = _get_stripe_trial_deposit_price_id()
    if deposit_price_id and _stripe_enabled():
        try:

            price = stripe.Price.retrieve(deposit_price_id)
            unit_amount = int(getattr(price, 'unit_amount', 0) or 0)
            if unit_amount > 0:
                return unit_amount
        except Exception:
            pass
    try:
        monthly_price_id = _get_stripe_price_id('monthly_10_95')
        if monthly_price_id and _stripe_enabled():

            price = stripe.Price.retrieve(monthly_price_id)
            unit_amount = int(getattr(price, 'unit_amount', 0) or 0)
            if unit_amount > 0:
                return unit_amount
    except Exception:
        pass
    return 1095


def _build_trial_deposit_line_item(plan_id: str = 'trial_7d') -> dict:
    """Stripe Checkout line item for the trial deposit charged before subscription creation."""
    deposit_price_id = _get_stripe_trial_deposit_price_id()
    if deposit_price_id:
        return {'price': deposit_price_id, 'quantity': 1}

    amount = _get_trial_deposit_amount_cents(plan_id)
    currency = 'inr' if _is_india_pricing_region() else 'usd'
    checkout_name, checkout_description = _trial_checkout_product_copy()
    product_data = {'name': checkout_name}
    if checkout_description:
        product_data['description'] = checkout_description
    return {
        'price_data': {
            'currency': currency,
            'unit_amount': amount,
            'product_data': product_data,
        },
        'quantity': 1,
    }


def _fulfill_trial_deposit_checkout(
        *,
        client_ref: str,
        customer_id: str,
        amount_total: int,
        currency: str,
        payment_intent_id: str,
        plan_id: str = 'trial_7d',
) -> Optional[str]:
    """Create a trialing subscription only after the deposit payment succeeds."""
    uid = str(client_ref or '').strip()
    cid = str(customer_id or '').strip()
    pi_id = str(payment_intent_id or '').strip()
    plan_id = _normalize_plan_id(plan_id) or 'trial_7d'
    if not uid or not cid or not pi_id or amount_total <= 0 or not _stripe_enabled():
        return None

    try:
        subs = stripe.Subscription.list(
            customer=cid,
            status='all',
            limit=20
        )
        for sub in list(getattr(subs, 'data', []) or []):
            meta = getattr(sub, 'metadata', None) or {}
            if isinstance(meta, dict):
                existing_pi = str(
                    meta.get('trial_deposit_payment_intent') or ''
                ).strip()
            else:
                existing_pi = str(
                    getattr(meta, 'trial_deposit_payment_intent', '') or ''
                ).strip()
            if existing_pi and existing_pi == pi_id:
                return str(getattr(sub, 'id', '') or '')
    except Exception:
        pass

    trial_period_days = 7
    if plan_id.startswith("price"):
        plan = _get_plan_by_price_id(plan_id) or {}

        product_id = plan.get("product_id")
        trial_period_days = plan.get("trial_period_days") or 7

        price_id = plan.get("price_id") or product_id
        plan_id = product_id or plan_id
    else:
        price_id = _get_plan_by_price_id(plan_id) or plan_id

    # --- Ensure price_id is a recurring subscription price ---
    if price_id and price_id.startswith("price_"):
        try:
            stripe_price = stripe.Price.retrieve(price_id)
            if stripe_price.type == "one_time":
                # It's a deposit/one-time price. Look up the recurring price for this product.
                target_product_id = stripe_price.product

                # 1. Try to find an active recurring price explicitly
                recurring_prices = stripe.Price.list(
                    product=target_product_id,
                    type="recurring",
                    active=True,
                    limit=1
                )

                if recurring_prices.data:
                    price_id = recurring_prices.data[0].id
                else:
                    # 2. Fallback to the product's default price
                    prod_obj = stripe.Product.retrieve(target_product_id)
                    if getattr(prod_obj, 'default_price', None):
                        price_id = prod_obj.default_price
        except Exception as e:
            logger.warning(
                "Price type safety check failed, proceeding with original price_id: %s",
                str(e)
                )

    if not price_id:
        logger.error(
            'trial deposit fulfillment failed: missing recurring price for %s',
            plan_id
        )
        return None

    subscription_params = {
        'customer': cid,
        'items': [{'price': price_id, 'quantity': 1}],
        # 'trial_end': _stripe_trial_end_ts_for_display(),
        "trial_period_days": trial_period_days,
        'payment_settings': {
            'save_default_payment_method': 'on_subscription'},
        'metadata': {
            'plan_id': plan_id,
            'user_id': uid,
            'trial_deposit_payment_intent': pi_id,
            'trial_deposit_cents': str(int(amount_total)),
            'trial_deposit_currency': str(currency or 'usd').lower(),
            'use_trial_hold': 'true',
        },
    }

    try:
        sub = stripe.Subscription.create(**subscription_params)
    except Exception as e:
        logger.error(
            "Subscription creation failed: %s",
            str(e),
            exc_info=True
        )
        raise

    sub_id = str(getattr(sub, 'id', '') or '')

    try:
        stripe.Customer.create_balance_transaction(
            cid,
            amount=-int(amount_total),
            currency=str(currency or 'usd').lower(),
            description='Trial deposit credit applied to first month if not canceled within 7 days',
        )
    except Exception:
        logger.exception(
            'trial deposit fulfillment: failed to apply customer balance credit'
        )

    _persist_stripe_subscription_to_profile(
        uid,
        sub,
        plan_id=plan_id,
        force_access=True
    )

    return sub_id or None

def _refund_trial_deposit_for_subscription(subscription_id: str) -> tuple[
    bool, str]:
    """Refund the trial deposit when a user cancels during the trial period."""
    sid = str(subscription_id or '').strip()
    if not sid or not _stripe_enabled():
        return False, 'stripe_not_configured'

    try:
        sub = stripe.Subscription.retrieve(sid)
    except Exception:
        return False, 'subscription_not_found'

    meta = getattr(sub, 'metadata', None) or {}
    if isinstance(meta, dict):
        pi_id = str(meta.get('trial_deposit_payment_intent') or '').strip()
        refunded_flag = str(
            meta.get('trial_deposit_refunded') or ''
        ).strip()
        deposit_cents = int(
            str(meta.get('trial_deposit_cents') or '0').strip() or '0'
        )
        currency = str(
            meta.get('trial_deposit_currency') or 'usd'
        ).strip().lower()
    else:
        pi_id = str(
            getattr(meta, 'trial_deposit_payment_intent', '') or ''
        ).strip()
        refunded_flag = str(
            getattr(meta, 'trial_deposit_refunded', '') or ''
        ).strip()
        deposit_cents = int(
            str(
                getattr(meta, 'trial_deposit_cents', '0') or '0'
            ).strip() or '0'
        )
        currency = str(
            getattr(meta, 'trial_deposit_currency', 'usd') or 'usd'
        ).strip().lower()

    if not pi_id:
        return False, 'no_deposit_payment'
    if refunded_flag == '1':
        return True, 'already_refunded'

    try:
        stripe.Refund.create(payment_intent=pi_id)
    except Exception as e:
        logger.warning(
            'trial deposit refund failed for %s: %s',
            sid,
            str(e)
        )
        return False, 'refund_failed'

    customer_id = str(getattr(sub, 'customer', '') or '').strip()
    if customer_id and deposit_cents > 0:
        try:
            stripe.Customer.create_balance_transaction(
                customer_id,
                amount=int(deposit_cents),
                currency=currency or 'usd',
                description='Reversal of trial deposit credit after cancellation within trial period',
            )
        except Exception:
            logger.exception(
                'trial deposit refund: failed to reverse customer balance credit'
            )

    try:
        stripe.Subscription.modify(
            sid,
            metadata={
                'trial_deposit_refunded': '1',
                'trial_deposit_refunded_at': datetime.now(
                    timezone.utc
                ).isoformat(),
            },
        )
    except Exception:
        pass
    return True, 'refunded'


def _get_email_trial_hold_days(invite: Optional[dict] = None) -> int:
    """Trial length from the signed email invite (default 10 days)."""
    raw_invite = invite if invite is not None else _get_email_trial_invite_from_session()
    try:
        return max(
            1,
            min(14, int((raw_invite or {}).get('trial_days') or 10))
        )
    except Exception:
        return 10


def _get_trial_hold_days(plan_id: str = 'trial_7d') -> int:
    """Number of days for a trial authorization hold."""
    plan = _get_plan_by_price_id(plan_id)
    if plan and plan.get("trial_period_days"):
        return plan["trial_period_days"]

    pid = _normalize_plan_id(plan_id) or 'trial_7d'
    if _is_email_trial_plan(pid):
        return _get_email_trial_hold_days()
    raw = (os.getenv('TRIAL_HOLD_DAYS') or os.getenv(
        'TRIAL_DURATION_DAYS'
    ) or '7').strip()
    try:
        return max(1, min(14, int(raw)))
    except Exception:
        return 7


def _get_trial_capture_days_before_end(
        hold_days: Optional[int] = None
) -> int:
    """Days before trial end when the authorization hold is captured."""
    hold = max(
        1,
        int(hold_days if hold_days is not None else _get_trial_hold_days())
    )
    raw = (os.getenv('TRIAL_CAPTURE_DAYS_BEFORE_END') or '1').strip()
    try:
        before_end = max(0, int(raw))
    except Exception:
        before_end = 1
    before_end = min(before_end, max(0, hold - 1))
    # Card authorizations typically expire after ~7 days; capture no later than day 6 of the hold.
    if hold > 7:
        before_end = max(before_end, max(0, hold - 6))
    return before_end


def _trial_hold_capture_at_from_end(
        trial_ends: datetime,
        hold_days: Optional[int] = None
) -> datetime:
    """Return the UTC timestamp when a trial authorization hold should be captured."""
    hold = max(1, int(hold_days or _get_trial_hold_days()))
    return trial_ends - timedelta(
        days=_get_trial_capture_days_before_end(hold)
    )


def _get_trial_hold_capture_at(prof: Optional[dict], sub=None) -> Optional[
    datetime]:
    """Resolve the scheduled capture time for a trial authorization hold."""
    capture_raw = str(
        (prof or {}).get('trial_hold_capture_at') or ''
    ).strip()
    if capture_raw:
        parsed = _parse_iso_dt(capture_raw)
        if parsed is not None:
            return parsed
    meta_capture = ''
    if sub is not None:
        meta_capture = _subscription_metadata_get(
            sub,
            'trial_hold_capture_at'
        )
    if meta_capture:
        parsed = _parse_iso_dt(meta_capture)
        if parsed is not None:
            return parsed
    ends_at = _parse_iso_dt(
        str((prof or {}).get('trial_hold_ends_at') or '').strip()
    )
    if ends_at is None and sub is not None:
        trial_end_ts = _stripe_obj_get(sub, 'trial_end', None)
        if trial_end_ts:
            try:
                ends_at = datetime.fromtimestamp(
                    int(trial_end_ts),
                    tz=timezone.utc
                )
            except Exception:
                ends_at = None
    if ends_at is not None:
        hold_days = 0
        try:
            hold_days = int(
                str(
                    (prof or {}).get('trial_hold_days') or ''
                ).strip() or '0'
            )
        except Exception:
            hold_days = 0
        if hold_days <= 0 and sub is not None:
            try:
                hold_days = int(
                    _subscription_metadata_get(
                        sub,
                        'trial_hold_days',
                        '0'
                    ) or '0'
                )
            except Exception:
                hold_days = 0
        if hold_days <= 0:
            plan_id = ''
            if sub is not None:
                plan_id = _subscription_metadata_get(
                    sub,
                    'plan_id',
                    'trial_7d'
                )
            hold_days = _get_trial_hold_days(plan_id or 'trial_7d')
        return _trial_hold_capture_at_from_end(ends_at, hold_days)
    return None


def _subscription_authorization_hold_captured(sub) -> bool:
    return _subscription_metadata_get(
        sub,
        'authorization_hold_captured'
    ) == '1'


def _subscription_authorization_hold_refunded(sub) -> bool:
    return _subscription_metadata_get(
        sub,
        'authorization_hold_refunded'
    ) == '1'


def _trial_cancel_eligible_for_capture_refund(
        prof: Optional[dict],
        sub=None
) -> bool:
    """True on the final trial day when a post-capture cancellation should be refunded."""
    ref_now = datetime.now(timezone.utc)
    ends_at = _parse_iso_dt(
        str((prof or {}).get('trial_hold_ends_at') or '').strip()
    )
    if ends_at is None and sub is not None:
        trial_end_ts = _stripe_obj_get(sub, 'trial_end', None)
        if trial_end_ts:
            try:
                ends_at = datetime.fromtimestamp(
                    int(trial_end_ts),
                    tz=timezone.utc
                )
            except Exception:
                ends_at = None
    if ends_at is None:
        return False
    capture_at = _get_trial_hold_capture_at(prof, sub)
    if capture_at is not None and ref_now < capture_at:
        return False
    window_start = ends_at - timedelta(days=1)
    return window_start <= ref_now <= (ends_at + timedelta(hours=1))


def _trial_checkout_product_copy(plan_id: str = 'trial_7d') -> tuple[
    str, str]:
    """Title + subtitle for Stripe Checkout (trial is free; amount shown is a hold only)."""
    hold_days = _get_trial_hold_days(plan_id)
    name = (os.getenv('STRIPE_TRIAL_CHECKOUT_NAME') or '').strip()
    if not name:
        zero_label = '₹0.00' if _is_india_pricing_region() else '$0.00'
        name = f'{hold_days} days free trial {zero_label}'
    description = (os.getenv(
        'STRIPE_TRIAL_CHECKOUT_DESCRIPTION'
    ) or '').strip()
    return name, description


def _should_use_trial_authorization_hold(plan_id: str) -> bool:
    """Use a card authorization hold instead of charging/refunding the trial deposit."""
    if not _stripe_enabled():
        return False

    plan = _get_plan_by_price_id(plan_id)
    if plan and plan.get("use_trial_hold") and plan.get(
            "trial_hold_ui",
            ""
    ) == "self":
        return True

    pid = _normalize_plan_id(plan_id)
    return pid in ('trial_7d', EMAIL_TRIAL_PLAN_ID)


def _get_trial_exit_offer_target_cents() -> int:
    """Target net charge for the first paid month after the trial."""
    raw = (os.getenv('TRIAL_EXIT_OFFER_TARGET_CENTS') or '649').strip()
    try:
        target = int(raw)
    except Exception:
        target = 649
    return max(1, target)


def _get_trial_exit_offer_for_user(user_id: str) -> dict:
    """Return the claimed trial-exit offer for the user, if any."""
    uid = str(user_id or '').strip()
    if not uid:
        return {}
    prof = get_user_profile_azure(uid) or {}
    if str(prof.get('trial_exit_offer_active') or '').strip() != '1':
        return {}
    try:
        target_cents = int(
            str(
                prof.get('trial_exit_offer_target_cents') or ''
            ).strip() or '0'
        )
    except Exception:
        target_cents = 0
    if target_cents <= 0:
        target_cents = _get_trial_exit_offer_target_cents()
    return {
        'active': True,
        'target_cents': target_cents,
        'accepted_at': str(
            prof.get('trial_exit_offer_accepted_at') or ''
        ).strip(),
    }


def _should_use_embedded_trial_hold_checkout(plan_id: str) -> bool:
    """Trial hold on our checkout page (Payment Element) when HTTPS or localhost allows it."""
    return _should_use_trial_authorization_hold(
        plan_id
    ) and _request_allows_stripe_embedded_payments()


def _trial_hold_checkout_template_context(
        plan_id: str = 'trial_7d'
) -> dict:
    """Shared copy/pricing for embedded and hosted trial hold checkout."""
    pid = _normalize_plan_id(plan_id) or 'trial_7d'
    checkout_name, checkout_description = _trial_checkout_product_copy(pid)

    plan = _get_plan_by_price_id(pid)
    if plan and plan.get("unit_amount"):
        amount = plan["unit_amount"] / 100.0
        currency = plan.get("currency", "usd").upper()
        symbol = "$" if currency == "USD" else (currency + " ")
        amount_label = f"{symbol}{amount:,.2f}"
    else:
        amount_label = _plans_price_display_context().get(
            'monthly_strong'
        ) or '$10.95'

    zero_label = '₹0.00' if _is_india_pricing_region() else '$0.00'
    hold_days = _get_trial_hold_days(pid)
    capture_days_before_end = _get_trial_capture_days_before_end(hold_days)
    capture_day = max(1, hold_days - capture_days_before_end)
    return {
        'checkout_name': checkout_name,
        'checkout_description': checkout_description,
        'amount_label': amount_label,
        'trial_hold_days': hold_days,
        'trial_capture_day': capture_day,
        'trial_zero_label': zero_label,
        'india_pricing': _is_india_pricing_region(),
        'trial_deposit_terms': (
            f'A temporary {amount_label} authorization hold is placed on your card. '
            f'If you cancel before day {capture_day}, the hold is released and you are not charged. '
            f'If you stay subscribed, the hold is captured on day {capture_day} as your first month\'s payment. '
            f'Cancel on day {hold_days} for a full refund if you were charged.'
        ),
    }


@app.context_processor
def inject_trial_plan_context():
    """Expose configured trial duration to all Jinja templates."""
    try:
        hold_days = _get_trial_hold_days()
        capture_day = max(
            1,
            hold_days - _get_trial_capture_days_before_end()
        )
        trial_plan = _get_plan_config('trial_7d') or {}
        return {
            'trial_hold_days': hold_days,
            'trial_capture_day': capture_day,
            'trial_deposit_terms': str(
                trial_plan.get('trial_deposit_terms') or ''
            ).strip(),
        }
    except Exception:
        return {
            'trial_hold_days': 7,
            'trial_capture_day': 6,
            'trial_deposit_terms': '',
        }


def _request_allows_stripe_embedded_payments() -> bool:
    """Stripe Payment Element requires HTTPS or localhost (not plain HTTP on LAN hostnames)."""
    try:
        proto = str(
            request.headers.get('X-Forwarded-Proto') or ''
        ).strip().lower()
        if request.is_secure or proto == 'https':
            return True
        host = str(request.host or '').split(':')[0].strip().lower()
        if host in ('localhost', '127.0.0.1', '[::1]'):
            return True
    except Exception:
        pass
    return False


def _external_url_scheme() -> str:
    """Prefer HTTPS for Stripe redirect URLs (required outside localhost)."""
    try:
        proto = str(
            request.headers.get('X-Forwarded-Proto') or ''
        ).strip().lower()
        if request.is_secure or proto == 'https':
            return 'https'
        host = str(request.host or '').split(':')[0].strip().lower()
        if host in ('localhost', '127.0.0.1', '[::1]'):
            return str(request.scheme or 'http')
    except Exception:
        pass
    return 'https'


def _create_trial_hold_checkout_session_url(
        user,
        plan_id: str = 'trial_7d'
) -> str:
    """Stripe Hosted Checkout for trial authorization hold (card form on stripe.com over HTTPS)."""
    if not _stripe_enabled():
        return ''
    pid = _normalize_plan_id(plan_id) or 'trial_7d'

    user_id = str(getattr(user, 'id', '') or '').strip()
    email = (getattr(user, 'email', '') or '').strip()
    if not user_id:
        return ''

    hold_days = _get_trial_hold_days(pid)
    _, checkout_blurb = _trial_checkout_product_copy(pid)
    scheme = _external_url_scheme()
    success_url = (
            url_for(
                'checkout_trial_hold_success',
                _external=True,
                _scheme=scheme
            )
            + '?session_id={CHECKOUT_SESSION_ID}'
    )
    cancel_url = url_for(
        'checkout',
        plan=pid,
        _external=True,
        _scheme=scheme
    )

    session_params = {
        'mode': 'payment',
        'customer_creation': 'always',
        'line_items': [_build_trial_deposit_line_item(pid)],
        'client_reference_id': user_id,
        'metadata': {
            'plan_id': pid,
            'trial_hold_checkout': '1',
        },
        'payment_intent_data': {
            'capture_method': 'manual',
            'setup_future_usage': 'off_session',
            'metadata': {
                'purpose': 'trial_hold',
                'plan_id': pid,
                'user_id': user_id,
                'trial_hold_days': str(hold_days),
                'pricing_region': 'in' if _is_india_pricing_region() else 'us',
            },
        },
        'success_url': success_url,
        'cancel_url': cancel_url,
    }
    if email:
        session_params['customer_email'] = email
    if checkout_blurb:
        session_params['custom_text'] = {
            'submit': {'message': checkout_blurb}}
    session = stripe.checkout.Session.create(**session_params)
    return str(getattr(session, 'url', '') or '')


def _trial_hold_currency() -> str:
    """Currency for the trial authorization hold (INR in India, USD elsewhere)."""
    return 'inr' if _is_india_pricing_region() else 'usd'


def _subscription_metadata_get(sub, key: str, default: str = '') -> str:
    """Read a string value from Stripe subscription metadata."""
    try:
        meta = _stripe_obj_get(sub, 'metadata', None) or {}
        if isinstance(meta, dict):
            return str(meta.get(key) or default).strip()
        return str(getattr(meta, key, default) or default).strip()
    except Exception:
        return default


def _get_subscription_authorization_payment_intent_id(sub) -> str:
    """Return the linked authorization-hold PaymentIntent id from subscription metadata."""
    return (
            _subscription_metadata_get(sub, 'authorization_payment_intent')
            or _subscription_metadata_get(sub, 'trial_hold_payment_intent')
            or _subscription_metadata_get(sub, 'trial_deposit_payment_intent')
    )


def _find_subscription_by_authorization_pi(
        customer_id: str,
        payment_intent_id: str
):
    """Find an existing subscription already linked to this authorization PaymentIntent."""
    cid = str(customer_id or '').strip()
    pi_id = str(payment_intent_id or '').strip()
    if not cid or not pi_id or not _stripe_enabled():
        return None

    try:
        subs = stripe.Subscription.list(
            customer=cid,
            status='all',
            limit=20
        )
        for sub in list(getattr(subs, 'data', []) or []):
            if _get_subscription_authorization_payment_intent_id(
                    sub
            ) == pi_id:
                return sub
    except Exception:
        pass
    return None


def _get_active_trial_authorization_payment_intent(
        prof: Optional[dict],
        subscription_id: str = '',
) -> str:
    """Resolve the active trial authorization PaymentIntent from profile or subscription."""
    pi_id = str(
        (prof or {}).get('trial_hold_payment_intent_id') or ''
    ).strip()
    if pi_id:
        return pi_id
    sid = str(
        subscription_id or (prof or {}).get('stripe_subscription_id') or ''
    ).strip()
    if not sid or not _stripe_enabled():
        return ''
    try:

        sub = stripe.Subscription.retrieve(sid)
        return _get_subscription_authorization_payment_intent_id(sub)
    except Exception:
        return ''


def _profile_has_active_trial_hold(
        prof: Optional[dict],
        *,
        now: Optional[datetime] = None
) -> bool:
    """Return True when the user has an active authorization hold granting trial access."""
    if not prof:
        return False
    pi_id = str(prof.get('trial_hold_payment_intent_id') or '').strip()
    if not pi_id:
        return False
    if str(prof.get('trial_hold_cancelled') or '').strip() == '1':
        return False
    ends_at = _parse_iso_dt(
        str(prof.get('trial_hold_ends_at') or '').strip()
    )
    ref_now = now or datetime.now(timezone.utc)
    if ends_at is not None and ends_at < ref_now:
        return False
    return True


def _create_trial_hold_payment_intent(
        user_id: str,
        plan_id: str = 'trial_7d',
        customer_id: str = ''
):
    """Create a manual-capture PaymentIntent for the trial hold amount."""
    cid = str(customer_id or '').strip()
    uid = str(user_id or '').strip()
    pid = _normalize_plan_id(plan_id) or 'trial_7d'
    if not uid or not _stripe_enabled():
        return None

    hold_days = _get_trial_hold_days(pid)
    amount = _get_trial_deposit_amount_cents(pid)
    currency = _trial_hold_currency()
    # Authorization holds require card capture; UPI settles immediately and cannot be held.
    params = {
        'amount': amount,
        'currency': currency,
        'payment_method_types': ['card'],
        'capture_method': 'manual',
        'metadata': {
            'purpose': 'trial_hold',
            'plan_id': pid,
            'user_id': uid,
            'trial_hold_days': str(hold_days),
            'pricing_region': 'in' if _is_india_pricing_region() else 'us',
        },
    }
    if cid:
        params['customer'] = cid
    return stripe.PaymentIntent.create(**params)


def _trial_hold_plan_id_from_intent(intent) -> str:
    """Read the plan id stored on a trial-hold PaymentIntent."""
    meta = getattr(intent, 'metadata', None) or {}
    if isinstance(meta, dict):
        plan_id = str(meta.get('plan_id') or '').strip()
    else:
        plan_id = str(getattr(meta, 'plan_id', '') or '').strip()
    return _normalize_plan_id(plan_id) or 'trial_7d'


def _trial_hold_days_from_intent(intent) -> int:
    """Read trial length from PaymentIntent metadata."""
    meta = getattr(intent, 'metadata', None) or {}
    if isinstance(meta, dict):
        raw_days = str(meta.get('trial_hold_days') or '').strip()
    else:
        raw_days = str(getattr(meta, 'trial_hold_days', '') or '').strip()
    try:
        days = int(raw_days)
    except Exception:
        days = 0
    if days > 0:
        return days
    return _get_trial_hold_days(_trial_hold_plan_id_from_intent(intent))


def _payment_intent_belongs_to_user(
        payment_intent_id: str,
        user_id: str
) -> bool:
    """Verify a PaymentIntent metadata user_id matches the authenticated user."""
    pi_id = str(payment_intent_id or '').strip()
    uid = str(user_id or '').strip()
    if not pi_id or not uid or not _stripe_enabled():
        return False
    try:

        intent = stripe.PaymentIntent.retrieve(pi_id)
        meta = getattr(intent, 'metadata', None) or {}
        if isinstance(meta, dict):
            meta_uid = str(meta.get('user_id') or '').strip()
        else:
            meta_uid = str(getattr(meta, 'user_id', '') or '').strip()
        return meta_uid == uid
    except Exception:
        return False


def _activate_trial_hold(user_id: str, payment_intent_id: str) -> tuple[
    bool, str]:
    """Grant trial access after the card authorization hold succeeds (requires_capture).

    Creates a trialing Stripe subscription linked to the authorization PaymentIntent.
    The hold is captured on the scheduled capture day (default day 6 of a 7-day trial).
    """
    uid = str(user_id or '').strip()
    pi_id = str(payment_intent_id or '').strip()
    if not uid or not pi_id or not _stripe_enabled():
        return False, 'missing_parameters'
    if not _payment_intent_belongs_to_user(pi_id, uid):
        return False, 'payment_intent_mismatch'

    try:
        intent = stripe.PaymentIntent.retrieve(pi_id)
    except Exception:
        return False, 'payment_intent_not_found'

    status = str(getattr(intent, 'status', '') or '').strip().lower()
    if status != 'requires_capture':
        return False, 'not_authorized'

    prof = get_user_profile_azure(uid) or {}
    existing_pi = str(
        prof.get('trial_hold_payment_intent_id') or ''
    ).strip()
    existing_sub_id = str(prof.get('stripe_subscription_id') or '').strip()
    if existing_pi and existing_pi == pi_id and existing_sub_id:
        return True, 'already_active'

    payment_method_id = str(
        getattr(intent, 'payment_method', '') or ''
    ).strip()
    if not payment_method_id:
        return False, 'missing_payment_method'

    amount = int(getattr(intent, 'amount', 0) or 0)
    currency = str(
        getattr(intent, 'currency', 'usd') or 'usd'
    ).strip().lower()
    exit_offer = _get_trial_exit_offer_for_user(uid)
    plan_id = _trial_hold_plan_id_from_intent(intent)
    hold_days = _trial_hold_days_from_intent(intent)
    invite = _get_email_trial_invite_from_session() if _is_email_trial_plan(
        plan_id
    ) else None
    campaign = str((invite or {}).get('campaign') or '').strip()
    customer_id = str(getattr(intent, 'customer', '') or '').strip()
    if not customer_id:
        customer_id = str(prof.get('stripe_customer_id') or '').strip()
    if not customer_id:
        email = str(
            prof.get('email') or getattr(current_user, 'email', '') or ''
        ).strip()
        customer_id = _find_stripe_customer_id_by_email(
            email,
            require_subscription_history=True
        ) if email else ''
    if not customer_id:
        try:
            cust = stripe.Customer.create(
                email=str(
                    prof.get('email') or getattr(
                        current_user,
                        'email',
                        ''
                    ) or ''
                ).strip() or None,
                metadata={'user_id': uid},
            )
            customer_id = str(getattr(cust, 'id', '') or '').strip()
        except Exception:
            logger.exception(
                'trial hold activation: customer creation failed'
            )
            return False, 'customer_creation_failed'
    try:
        stripe.PaymentMethod.attach(
            payment_method_id,
            customer=customer_id
        )
    except Exception:
        # The card may already be attached to this customer after a previous successful attempt.
        pass

    try:
        stripe.Customer.modify(
            customer_id,
            invoice_settings={'default_payment_method': payment_method_id},
        )
    except Exception:
        logger.exception(
            'trial hold activation: failed to set default payment method'
        )

    sub = _find_subscription_by_authorization_pi(customer_id, pi_id)
    if not sub:
        price_id = _get_stripe_price_id(plan_id)
        if not price_id:
            return False, 'price_not_configured'
        sub_metadata = {
            'plan_id': plan_id,
            'user_id': uid,
            'authorization_payment_intent': pi_id,
            'trial_hold_payment_intent': pi_id,
            'trial_hold_days': str(hold_days),
            'trial_exit_offer_active': '1' if exit_offer.get(
                'active'
            ) else '',
            'trial_exit_offer_target_cents': str(
                int(exit_offer.get('target_cents') or 0)
            ) if exit_offer.get('active') else '',
        }
        if campaign:
            sub_metadata['campaign'] = campaign
        try:
            sub = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id, 'quantity': 1}],
                default_payment_method=payment_method_id,
                trial_period_days=hold_days,
                payment_settings={
                    'save_default_payment_method': 'on_subscription'},
                metadata=sub_metadata,
            )
        except Exception:
            logger.exception(
                'trial hold activation: subscription creation failed'
            )
            return False, 'subscription_failed'
    elif exit_offer.get('active') and _subscription_metadata_get(
            sub,
            'trial_exit_offer_active'
    ) != '1':
        try:
            patch_meta = {
                'plan_id': plan_id,
                'user_id': uid,
                'authorization_payment_intent': pi_id,
                'trial_hold_payment_intent': pi_id,
                'trial_hold_days': str(hold_days),
                'trial_exit_offer_active': '1',
                'trial_exit_offer_target_cents': str(
                    int(exit_offer.get('target_cents') or 0)
                ),
            }
            if campaign:
                patch_meta['campaign'] = campaign
            stripe.Subscription.modify(
                str(getattr(sub, 'id', '') or ''),
                metadata=patch_meta,
            )
            sub = stripe.Subscription.retrieve(
                str(getattr(sub, 'id', '') or '')
            )
        except Exception:
            logger.exception(
                'trial hold activation: failed to attach exit offer metadata'
            )

    if not _stripe_subscription_grants_access(sub):
        return False, 'subscription_not_active'

    _persist_stripe_subscription_to_profile(uid, sub, plan_id=plan_id)

    trial_end_ts = getattr(sub, 'trial_end', None)
    if trial_end_ts:
        trial_ends = datetime.fromtimestamp(
            int(trial_end_ts),
            tz=timezone.utc
        )
    else:
        trial_ends = datetime.now(timezone.utc) + timedelta(days=hold_days)
    capture_at = _trial_hold_capture_at_from_end(trial_ends, hold_days)
    sub_id = str(getattr(sub, 'id', '') or '').strip()
    if sub_id:
        try:
            stripe.Subscription.modify(
                sub_id,
                metadata={
                    'trial_hold_capture_at': capture_at.isoformat(),
                    'trial_hold_days': str(hold_days),
                },
            )
        except Exception:
            logger.exception(
                'trial hold activation: failed to persist capture schedule on subscription'
            )

    try:
        table_client = get_users_table_client()
        entity = {
            'PartitionKey': uid,
            'RowKey': 'profile',
            'stripe_customer_id': customer_id,
            'stripe_subscription_id': sub_id,
            'trial_hold_payment_intent_id': pi_id,
            'trial_hold_customer_id': customer_id,
            'trial_hold_ends_at': trial_ends.isoformat(),
            'trial_hold_capture_at': capture_at.isoformat(),
            'trial_hold_days': str(hold_days),
            'trial_hold_amount_cents': str(amount),
            'trial_hold_currency': currency,
            'trial_hold_cancelled': '',
            'trial_used': True,
            'trial_used_at': datetime.now(timezone.utc).isoformat(),
            'trial_exit_offer_active': '1' if exit_offer.get(
                'active'
            ) else '',
            'trial_exit_offer_target_cents': str(
                int(exit_offer.get('target_cents') or 0)
            ) if exit_offer.get('active') else '',
        }
        table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
    except Exception:
        logger.exception(
            'trial hold activation: failed to persist profile'
        )
        return False, 'profile_update_failed'

    return True, 'activated'


def _capture_authorization_hold_for_subscription(
        sub,
        apply_balance: bool = True
) -> tuple[bool, str]:
    """Capture the linked authorization hold when a trialing subscription is about to end."""
    if not sub or not _stripe_enabled():
        return False, 'missing_subscription'

    sub_id = str(_stripe_obj_get(sub, 'id', '') or '').strip()
    status = str(_stripe_obj_get(sub, 'status', '') or '').strip().lower()
    if status != 'trialing':
        return False, 'not_trialing'

    # Never capture if cancellation is already scheduled; let the authorization expire naturally.
    if _stripe_subscription_cancel_scheduled(sub):
        return False, 'cancellation_scheduled'

    if _subscription_metadata_get(
            sub,
            'authorization_hold_captured'
    ) == '1':
        return True, 'already_captured'

    pi_id = _get_subscription_authorization_payment_intent_id(sub)
    if not pi_id:
        return False, 'no_authorization_payment_intent'

    try:
        intent = stripe.PaymentIntent.retrieve(pi_id)
    except Exception:
        return False, 'payment_intent_not_found'

    pi_status = str(getattr(intent, 'status', '') or '').strip().lower()
    captured_intent = intent
    if pi_status == 'requires_capture':
        try:
            captured_intent = stripe.PaymentIntent.capture(pi_id)
        except Exception as e:
            logger.warning(
                'authorization hold capture failed sub=%s pi=%s err=%s',
                sub_id,
                pi_id,
                str(e)
            )
            return False, 'capture_failed'
    elif pi_status != 'succeeded':
        return False, f'unexpected_status_{pi_status}'

    if str(
            getattr(captured_intent, 'status', '') or ''
    ).strip().lower() != 'succeeded':
        return False, 'capture_not_succeeded'

    amount = int(getattr(captured_intent, 'amount', 0) or 0)
    currency = str(
        getattr(captured_intent, 'currency', 'usd') or 'usd'
    ).strip().lower()
    customer_id = str(
        _stripe_obj_get(sub, 'customer', '') or getattr(
            captured_intent,
            'customer',
            ''
        ) or ''
    ).strip()
    offer_target_cents = 0
    if _subscription_metadata_get(sub, 'trial_exit_offer_active') == '1':
        try:
            offer_target_cents = int(
                _subscription_metadata_get(
                    sub,
                    'trial_exit_offer_target_cents',
                    '0'
                ) or '0'
            )
        except Exception:
            offer_target_cents = 0
    refund_cents = 0
    if offer_target_cents > 0 and amount > offer_target_cents:
        refund_cents = int(amount - offer_target_cents)
    if apply_balance and customer_id and amount > 0:
        try:
            stripe.Customer.create_balance_transaction(
                customer_id,
                amount=-amount,
                currency=currency,
                description='Trial authorization captured — credit toward first subscription invoice',
            )
        except Exception:
            logger.exception(
                'authorization hold capture: failed to apply customer balance credit'
            )

    metadata_update = {
        'authorization_hold_captured': '1',
        'authorization_hold_captured_at': datetime.now(
            timezone.utc
        ).isoformat(),
        'authorization_hold_balance_credit_cents': str(amount),
    }
    if refund_cents > 0:
        try:
            stripe.Refund.create(
                payment_intent=pi_id,
                amount=refund_cents,
                metadata={
                    'purpose': 'trial_exit_offer',
                    'subscription_id': sub_id,
                },
            )
            metadata_update['trial_exit_offer_applied'] = '1'
            metadata_update['trial_exit_offer_refund_cents'] = str(
                refund_cents
            )
            metadata_update['trial_exit_offer_applied_at'] = datetime.now(
                timezone.utc
            ).isoformat()
        except Exception:
            logger.exception(
                'authorization hold capture: failed to refund exit offer discount'
            )
            metadata_update['trial_exit_offer_refund_failed'] = '1'
            metadata_update[
                'trial_exit_offer_refund_failed_at'] = datetime.now(
                timezone.utc
            ).isoformat()

    try:
        stripe.Subscription.modify(
            sub_id,
            metadata=metadata_update,
        )
    except Exception:
        pass

    user_id = _subscription_metadata_get(sub, 'user_id')
    if user_id:
        try:
            table_client = get_users_table_client()
            entity = {
                'PartitionKey': user_id,
                'RowKey': 'profile',
                'trial_hold_captured_at': datetime.now(
                    timezone.utc
                ).isoformat(),
                'trial_exit_offer_active': '',
                'trial_exit_offer_refund_cents': str(
                    refund_cents
                ) if refund_cents > 0 else '',
            }
            table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
        except Exception:
            pass

    return True, 'captured'


def _release_authorization_hold_for_subscription(sub) -> tuple[bool, str]:
    """Release an uncaptured authorization hold when a trial subscription is canceled."""
    pi_id = _get_subscription_authorization_payment_intent_id(sub)
    if not pi_id:
        return False, 'no_authorization_payment_intent'
    if _subscription_authorization_hold_captured(sub):
        return True, 'already_captured'
    return _cancel_trial_hold_payment_intent(pi_id)


def _refund_trial_authorization_capture_for_subscription(sub) -> tuple[
    bool, str]:
    """Refund a captured trial authorization hold and reverse the customer balance credit."""
    if not sub or not _stripe_enabled():
        return False, 'missing_subscription'

    sub_id = str(_stripe_obj_get(sub, 'id', '') or '').strip()
    if _subscription_authorization_hold_refunded(sub):
        return True, 'already_refunded'
    if not _subscription_authorization_hold_captured(sub):
        return False, 'not_captured'

    pi_id = _get_subscription_authorization_payment_intent_id(sub)
    if not pi_id:
        return False, 'no_authorization_payment_intent'

    try:
        intent = stripe.PaymentIntent.retrieve(pi_id)
    except Exception:
        return False, 'payment_intent_not_found'

    pi_status = str(getattr(intent, 'status', '') or '').strip().lower()
    if pi_status != 'succeeded':
        return False, f'unexpected_status_{pi_status}'

    amount = int(getattr(intent, 'amount', 0) or 0)
    currency = str(
        getattr(intent, 'currency', 'usd') or 'usd'
    ).strip().lower()
    customer_id = str(
        _stripe_obj_get(sub, 'customer', '') or getattr(
            intent,
            'customer',
            ''
        ) or ''
    ).strip()
    if amount <= 0:
        return False, 'zero_amount'

    already_refunded = 0
    try:
        refunds = stripe.Refund.list(payment_intent=pi_id, limit=20)
        for refund in list(getattr(refunds, 'data', []) or []):
            refund_status = str(
                getattr(refund, 'status', '') or ''
            ).strip().lower()
            if refund_status in ('succeeded', 'pending'):
                already_refunded += int(getattr(refund, 'amount', 0) or 0)
    except Exception:
        logger.exception(
            'trial authorization refund: failed to list existing refunds'
        )

    remaining_refund = max(0, amount - already_refunded)
    if remaining_refund > 0:
        try:
            stripe.Refund.create(
                payment_intent=pi_id,
                amount=remaining_refund,
                metadata={
                    'purpose': 'trial_final_day_cancel',
                    'subscription_id': sub_id,
                },
            )
        except Exception as e:
            logger.warning(
                'trial authorization refund failed sub=%s pi=%s err=%s',
                sub_id,
                pi_id,
                str(e)
            )
            return False, 'refund_failed'

    try:
        credit_cents = int(
            _subscription_metadata_get(
                sub,
                'authorization_hold_balance_credit_cents',
                str(amount)
            ) or amount
        )
    except Exception:
        credit_cents = amount
    if customer_id and credit_cents > 0:
        try:
            stripe.Customer.create_balance_transaction(
                customer_id,
                amount=int(credit_cents),
                currency=currency,
                description='Reversal of trial authorization credit after final-day cancellation',
            )
        except Exception:
            logger.exception(
                'trial authorization refund: failed to reverse customer balance credit'
            )

    metadata_update = {
        'authorization_hold_refunded': '1',
        'authorization_hold_refunded_at': datetime.now(
            timezone.utc
        ).isoformat(),
    }
    try:
        stripe.Subscription.modify(sub_id, metadata=metadata_update)
    except Exception:
        pass

    user_id = _subscription_metadata_get(sub, 'user_id')
    if user_id:
        try:
            table_client = get_users_table_client()
            entity = {
                'PartitionKey': user_id,
                'RowKey': 'profile',
                'trial_hold_refunded_at': datetime.now(
                    timezone.utc
                ).isoformat(),
            }
            table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
        except Exception:
            pass

    return True, 'refunded'


def _cancel_trial_hold_payment_intent(payment_intent_id: str) -> tuple[
    bool, str]:
    """Release an uncaptured authorization hold."""
    pi_id = str(payment_intent_id or '').strip()
    if not pi_id or not _stripe_enabled():
        return False, 'missing_payment_intent'

    try:
        intent = stripe.PaymentIntent.retrieve(pi_id)
    except Exception:
        return False, 'payment_intent_not_found'

    status = str(getattr(intent, 'status', '') or '').strip().lower()
    if status in ('canceled', 'cancelled'):
        return True, 'already_cancelled'
    if status == 'requires_capture':
        try:
            stripe.PaymentIntent.cancel(pi_id)
            return True, 'cancelled'
        except Exception as e:
            logger.warning(
                'trial hold cancel failed for %s: %s',
                pi_id,
                str(e)
            )
            return False, 'cancel_failed'
    if status == 'succeeded':
        return False, 'already_captured'
    return False, f'unexpected_status_{status}'


def _revoke_trial_hold_profile(
        user_id: str,
        *,
        cancelled: bool = True
) -> None:
    """Clear trial-hold access fields from the user profile."""
    uid = str(user_id or '').strip()
    if not uid:
        return
    try:
        table_client = get_users_table_client()
        entity = {
            'PartitionKey': uid,
            'RowKey': 'profile',
            'is_paid': False,
            'plan_status': 'free',
            'paid_until': '',
            'trial_hold_cancelled': '1' if cancelled else '',
            'trial_hold_cancelled_at': datetime.now(
                timezone.utc
            ).isoformat() if cancelled else '',
        }
        table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
    except Exception:
        logger.exception(
            'trial hold revoke: failed to update profile for %s',
            uid
        )


def _capture_trial_hold_and_subscribe(user_id: str) -> tuple[
    bool, str, Optional[str]]:
    """Legacy fallback: capture hold and create subscription for profiles without a Stripe sub.

    New trial signups create a trialing subscription at activation; capture runs on
    customer.subscription.trial_will_end instead.
    """
    uid = str(user_id or '').strip()
    if not uid or not _stripe_enabled():
        return False, 'missing_parameters', None

    prof = get_user_profile_azure(uid) or {}
    existing_sub_id = str(prof.get('stripe_subscription_id') or '').strip()
    if existing_sub_id:

        try:
            sub = stripe.Subscription.retrieve(existing_sub_id)
            ok, reason = _capture_authorization_hold_for_subscription(sub)
            return ok, reason, existing_sub_id
        except Exception:
            return True, 'subscription_already_exists', existing_sub_id

    pi_id = str(prof.get('trial_hold_payment_intent_id') or '').strip()
    customer_id = str(
        prof.get('trial_hold_customer_id') or prof.get(
            'stripe_customer_id'
        ) or ''
    ).strip()
    if not pi_id or not customer_id:
        return False, 'no_active_trial_hold', None
    if str(prof.get('trial_hold_cancelled') or '').strip() == '1':
        return False, 'trial_hold_cancelled', None

    try:
        intent = stripe.PaymentIntent.retrieve(pi_id)
    except Exception:
        return False, 'payment_intent_not_found', None

    status = str(getattr(intent, 'status', '') or '').strip().lower()
    if status == 'succeeded':
        captured_intent = intent
    elif status == 'requires_capture':
        try:
            captured_intent = stripe.PaymentIntent.capture(pi_id)
        except Exception as e:
            logger.warning(
                'trial hold capture failed for %s: %s',
                pi_id,
                str(e)
            )
            return False, 'capture_failed', None
    else:
        return False, f'unexpected_status_{status}', None

    if str(
            getattr(captured_intent, 'status', '') or ''
    ).strip().lower() != 'succeeded':
        return False, 'capture_not_succeeded', None

    payment_method_id = str(
        getattr(captured_intent, 'payment_method', '') or ''
    ).strip()
    if not payment_method_id:
        return False, 'missing_payment_method', None

    try:
        stripe.Customer.modify(
            customer_id,
            invoice_settings={'default_payment_method': payment_method_id},
        )
    except Exception:
        logger.exception(
            'trial hold: failed to set default payment method'
        )

    price_id = _get_stripe_price_id('monthly_10_95')
    if not price_id:
        return False, 'price_not_configured', None

    subscription_params = {
        'customer': customer_id,
        'items': [{'price': price_id}],
        'default_payment_method': payment_method_id,
        'payment_settings': {
            'save_default_payment_method': 'on_subscription'},
        'metadata': {
            'plan_id': 'monthly_10_95',
            'user_id': uid,
            'started_after_trial_hold': 'true',
            'authorization_payment_intent': pi_id,
            'trial_hold_payment_intent': pi_id,
            'authorization_hold_captured': '1',
        },
    }
    try:
        sub = stripe.Subscription.create(**subscription_params)
    except Exception as e:
        logger.exception('trial hold: subscription creation failed')
        return False, f'subscription_failed:{str(e)}', None

    sub_id = str(getattr(sub, 'id', '') or '').strip()
    _persist_stripe_subscription_to_profile(
        uid,
        sub,
        plan_id='monthly_10_95'
    )

    try:
        table_client = get_users_table_client()
        entity = {
            'PartitionKey': uid,
            'RowKey': 'profile',
            'trial_hold_payment_intent_id': pi_id,
            'trial_hold_captured_at': datetime.now(
                timezone.utc
            ).isoformat(),
        }
        table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
    except Exception:
        pass

    return True, 'subscribed', sub_id or None


def _maybe_capture_due_trial_hold_for_user(user_id: str) -> None:
    """Capture a trialing subscription's authorization hold once the scheduled capture time arrives."""
    uid = str(user_id or '').strip()
    if not uid or not _stripe_enabled():
        return

    prof = get_user_profile_azure(uid) or {}
    subscription_id = str(prof.get('stripe_subscription_id') or '').strip()
    if not subscription_id:
        return

    try:
        sub = stripe.Subscription.retrieve(subscription_id)
    except Exception:
        return

    sub_status = str(getattr(sub, 'status', '') or '').strip().lower()
    if sub_status != 'trialing':
        return

    if not _get_subscription_authorization_payment_intent_id(sub):
        return
    if _subscription_authorization_hold_captured(sub):
        return
    if _stripe_subscription_cancel_scheduled(sub):
        return

    capture_at = _get_trial_hold_capture_at(prof, sub)
    if capture_at is None or datetime.now(timezone.utc) < capture_at:
        return

    ok, reason = _capture_authorization_hold_for_subscription(sub)
    logger.info(
        'deferred trial hold capture user_id=%s sub=%s ok=%s reason=%s',
        uid,
        subscription_id,
        bool(ok),
        reason or 'ok',
    )


def _process_trial_hold_lifecycle_for_user(user_id: str) -> None:
    """Release expired holds, capture due holds, or migrate legacy profiles without a Stripe subscription."""
    uid = str(user_id or '').strip()
    if not uid or not _stripe_enabled():
        return

    _maybe_capture_due_trial_hold_for_user(uid)

    prof = get_user_profile_azure(uid) or {}
    pi_id = str(prof.get('trial_hold_payment_intent_id') or '').strip()
    if not pi_id:
        return

    subscription_id = str(prof.get('stripe_subscription_id') or '').strip()

    if subscription_id:
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            sub_status = str(
                getattr(sub, 'status', '') or ''
            ).strip().lower()
            if sub_status == 'trialing' and _get_subscription_authorization_payment_intent_id(
                    sub
            ):
                return
        except Exception:
            pass
        return

    now = datetime.now(timezone.utc)
    ends_at = _parse_iso_dt(
        str(prof.get('trial_hold_ends_at') or '').strip()
    )
    cancelled = str(prof.get('trial_hold_cancelled') or '').strip() == '1'

    try:
        intent = stripe.PaymentIntent.retrieve(pi_id)
    except Exception:
        if cancelled or (ends_at is not None and ends_at < now):
            _revoke_trial_hold_profile(uid, cancelled=cancelled)
        return

    status = str(getattr(intent, 'status', '') or '').strip().lower()

    if cancelled:
        _revoke_trial_hold_profile(uid, cancelled=True)
        return

    if status in ('canceled', 'cancelled'):
        _revoke_trial_hold_profile(uid, cancelled=True)
        return

    if status == 'succeeded' and not subscription_id:
        _capture_trial_hold_and_subscribe(uid)
        return

    if ends_at is not None and ends_at <= now and status == 'requires_capture':
        ok, reason, _sub_id = _capture_trial_hold_and_subscribe(uid)
        if not ok:
            logger.warning(
                'trial hold auto-capture failed user_id=%s reason=%s',
                uid,
                reason
            )
        return

    if status not in ('requires_capture', 'processing', 'requires_action'):
        if ends_at is not None and ends_at < now:
            _revoke_trial_hold_profile(uid, cancelled=False)


def _get_stripe_payment_link(plan_id: str) -> Optional[str]:
    """Optional Stripe Payment Links (non-secret). If set, /checkout can redirect here directly."""
    plan_id = _normalize_plan_id(plan_id)
    defaults = {
        # Provided by user
        'trial_7d': 'https://buy.stripe.com/cNi6oBeZ21gXfAu1cD7Vm02',
        # Updated to latest Stripe-provided monthly link (promo codes configured here)
        'monthly_10_95': 'https://buy.stripe.com/5kQ6oBcQUaRxcoif3t7Vm05',
        'annual_6_95': 'https://buy.stripe.com/aFa9ANdUYgbR9c6bRh7Vm04',
    }
    if plan_id == 'trial_7d':
        # Prefer new env var name if present; fall back to legacy name.
        return (
                (os.getenv('STRIPE_PAYMENTLINK_TRIAL_7D') or '').strip()
                or (os.getenv(
            'STRIPE_PAYMENTLINK_TRIAL_14D'
        ) or '').strip()
                or defaults['trial_7d']
        )
    if plan_id == 'monthly_10_95':
        if _is_india_pricing_region():
            return (
                    (os.getenv(
                        'STRIPE_PAYMENTLINK_MONTHLY_10_95_INR'
                    ) or '').strip()
                    or (os.getenv(
                'STRIPE_PAYMENTLINK_MONTHLY_10_95'
            ) or '').strip()
                    or defaults['monthly_10_95']
            )
        return (os.getenv(
            'STRIPE_PAYMENTLINK_MONTHLY_10_95'
        ) or '').strip() or defaults['monthly_10_95']
    if plan_id == 'annual_6_95':
        if _is_india_pricing_region():
            return (
                    (os.getenv(
                        'STRIPE_PAYMENTLINK_ANNUAL_6_95_INR'
                    ) or '').strip()
                    or (os.getenv(
                'STRIPE_PAYMENTLINK_ANNUAL_6_95'
            ) or '').strip()
                    or defaults['annual_6_95']
            )
        return (os.getenv(
            'STRIPE_PAYMENTLINK_ANNUAL_6_95'
        ) or '').strip() or defaults['annual_6_95']
    return None


def _get_stripe_retention_promo_code() -> Optional[str]:
    """Return the promotion code string for retention offer (e.g. RETENTION50). Used with Payment Links."""
    return (os.getenv('STRIPE_PROMO_CODE_RETENTION') or '').strip() or None


def _get_stripe_retention_coupon_id() -> Optional[str]:
    """Return the coupon ID for retention offer. Used with Checkout Session discounts."""
    return (os.getenv('STRIPE_COUPON_RETENTION') or '').strip() or None


def _get_payment_method_config_for_checkout(plan_id: str) -> dict:
    """Get payment method configuration for Stripe Checkout based on region and plan.

    For India recurring: uses card (3DS required) + UPI if supported.
    Note: RBI mandates are created by Stripe through subscription flow, not metadata.
    Requires Stripe API version 2025-01-27 or later for UPI subscriptions.
    """
    config = {}

    if _is_india_pricing_region() and plan_id in (
            'trial_7d', EMAIL_TRIAL_PLAN_ID, 'monthly_10_95',
            'annual_6_95'):
        # For India recurring subscriptions, enable card (3DS enforced) + UPI
        # Stripe creates mandates through subscription flow for on-session first payment
        # UPI support requires Stripe API 2025+ and account eligibility check
        config['payment_method_types'] = ['card', 'upi']

    return config


def _compute_retention_credit_cents(subscription) -> int:
    """Compute 50% off for one month (applied twice = 50% off for 2 months). Works with flexible billing."""
    try:
        override = (os.getenv(
            'STRIPE_RETENTION_CREDIT_CENTS'
        ) or '').strip()
        if override and override.isdigit():
            return int(override)
    except Exception:
        pass
    # 50% of one month: monthly $5.48, annual $3.48
    DEFAULT_MONTHLY_HALF_CENTS = 548  # 50% of $10.95
    DEFAULT_ANNUAL_HALF_CENTS = 348  # 50% of $6.95
    try:
        price_id, interval, interval_count = _get_subscription_price_id_and_recurring(
            subscription
        )
        items = getattr(subscription, 'items', None)
        items_data = list(
            getattr(items, 'data', []) or []
        ) if items else []
        if not items_data:
            is_annual = interval == 'year' or (
                    interval == 'month' and interval_count == 12)
            return DEFAULT_ANNUAL_HALF_CENTS if is_annual else DEFAULT_MONTHLY_HALF_CENTS
        first = items_data[0]
        price = getattr(first, 'price', None) if not isinstance(
            first,
            dict
        ) else (
            first.get('price') if isinstance(first, dict) else None)
        unit = 0
        if price is not None:
            if isinstance(price, dict):
                unit = int(price.get('unit_amount') or 0)
            elif isinstance(price, str):
                try:
                    p = stripe.Price.retrieve(price)
                    unit = int(getattr(p, 'unit_amount', 0) or 0)
                except Exception:
                    pass
            else:
                unit = int(getattr(price, 'unit_amount', 0) or 0)
        if unit <= 0:
            is_annual = interval == 'year' or (
                    interval == 'month' and interval_count == 12)
            return DEFAULT_ANNUAL_HALF_CENTS if is_annual else DEFAULT_MONTHLY_HALF_CENTS
        # 50% of one month (applied to each of next 2 invoices)
        if interval == 'year' or (
                interval == 'month' and interval_count == 12):
            return (unit // 12) // 2  # half of one month of annual
        return unit // 2  # half of one month of monthly
    except Exception:
        return DEFAULT_MONTHLY_HALF_CENTS


def _apply_reinstate_next_month_price_offer(
        subscription,
        target_price_cents: int = 399
) -> tuple[bool, str, int]:
    """Apply one-time credit so the next monthly invoice is effectively target_price_cents."""
    try:
        target_cents = int(target_price_cents or 0)
    except Exception:
        target_cents = 399
    if target_cents <= 0:
        target_cents = 399

    try:
        sub_id = str(_stripe_obj_get(subscription, "id", "") or "").strip()
        customer_id = str(
            _stripe_obj_get(subscription, "customer", "") or ""
        ).strip()
        if not sub_id or not customer_id:
            return False, "Unable to apply offer: subscription billing details are missing.", 0

        _, interval, interval_count = _get_subscription_price_id_and_recurring(
            subscription
        )
        if str(interval or "").strip().lower() != "month" or int(
                interval_count or 1
        ) != 1:
            return False, "Offer applies only to monthly subscriptions.", 0

        items = _stripe_obj_get(subscription, "items", None)
        items_data = list(
            _stripe_obj_get(items, "data", []) or []
        ) if items is not None else []
        if not items_data:
            return False, "Unable to apply offer: subscription price is unavailable.", 0

        first = items_data[0]
        price = _stripe_obj_get(first, "price", None)
        unit_amount = int(_stripe_obj_get(price, "unit_amount", 0) or 0)
        currency = str(
            _stripe_obj_get(price, "currency", "usd") or "usd"
        ).strip().lower()
        if unit_amount <= 0:
            return False, "Unable to apply offer: invalid subscription amount.", 0
        if currency != "usd":
            return False, "Offer currently supports USD subscriptions only.", 0
        if unit_amount <= target_cents:
            return False, "Your next month is already priced at or below this offer.", 0

        current_period_end = str(
            _stripe_obj_get(subscription, "current_period_end", "") or ""
        ).strip()
        metadata = _stripe_obj_get(subscription, "metadata", {}) or {}
        already_period_end = str(
            _stripe_obj_get(
                metadata,
                "reinstate_offer_399_period_end",
                ""
            ) or ""
        ).strip()
        if current_period_end and already_period_end == current_period_end:
            return True, "Offer already applied to your next month.", 0

        credit_cents = int(unit_amount - target_cents)
        if credit_cents <= 0:
            return False, "Unable to apply offer: discount amount is not positive.", 0

        stripe.Customer.create_balance_transaction(
            customer_id,
            amount=-credit_cents,
            currency=currency,
            description=f"Reinstate offer: next month ${target_cents / 100:.2f}",
        )

        stripe.Subscription.modify(
            sub_id,
            metadata={
                "reinstate_offer_399_period_end": current_period_end,
                "reinstate_offer_399_credit_cents": str(credit_cents),
                "reinstate_offer_399_applied_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            },
        )
        return True, f"Offer applied: your next month will be ${target_cents / 100:.2f}.", credit_cents
    except Exception:
        logger.exception(
            "Failed applying reinstate next-month price offer"
        )
        return False, "Unable to apply the $3.99 next-month offer.", 0


def _apply_reinstate_offer_credit_from_monthly_price(
        customer_id: str,
        target_price_cents: int = 399
) -> tuple[bool, str, int]:
    """Apply $3.99-offer credit using the configured monthly list price."""
    cid = str(customer_id or '').strip()
    if not cid:
        return False, "Unable to apply offer: customer billing details are missing.", 0
    try:
        target_cents = int(target_price_cents or 0)
    except Exception:
        target_cents = 399
    if target_cents <= 0:
        target_cents = 399
    try:

        price_id = _get_stripe_price_id('monthly_10_95')
        if not price_id:
            return False, "Monthly plan price is not configured.", 0
        price = stripe.Price.retrieve(price_id)
        unit_amount = int(_stripe_obj_get(price, 'unit_amount', 0) or 0)
        currency = str(
            _stripe_obj_get(price, 'currency', 'usd') or 'usd'
        ).strip().lower()
        if unit_amount <= 0:
            return False, "Unable to apply offer: invalid subscription amount.", 0
        if currency != 'usd':
            return False, "Offer currently supports USD subscriptions only.", 0
        if unit_amount <= target_cents:
            return False, "Your next month is already priced at or below this offer.", 0
        credit_cents = int(unit_amount - target_cents)
        if credit_cents <= 0:
            return False, "Unable to apply offer: discount amount is not positive.", 0
        stripe.Customer.create_balance_transaction(
            cid,
            amount=-credit_cents,
            currency=currency,
            description=f"Reinstate offer: next month ${target_cents / 100:.2f}",
        )
        return True, f"Offer applied: your next month will be ${target_cents / 100:.2f}.", credit_cents
    except Exception:
        logger.exception(
            "Failed applying reinstate offer credit from monthly price"
        )
        return False, "Unable to apply the $3.99 next-month offer.", 0


_REINSTATE_OFFER_CHECKOUT_SESSION_KEY = "reinstate_offer_checkout"


def _is_reinstate_offer_checkout_request() -> bool:
    try:
        raw = str(
            request.args.get('reinstate_offer') or request.args.get(
                'reinstate'
            ) or ''
        ).strip().lower()
        return raw in ('1', 'true', 'yes')
    except Exception:
        return False


def _mark_reinstate_offer_checkout_in_session() -> None:
    try:
        session[_REINSTATE_OFFER_CHECKOUT_SESSION_KEY] = True
        session.modified = True
    except Exception:
        pass


def _consume_reinstate_offer_checkout_from_session() -> bool:
    try:
        return bool(
            session.pop(_REINSTATE_OFFER_CHECKOUT_SESSION_KEY, False)
        )
    except Exception:
        return False


def _create_reinstate_offer_checkout_url(
        user_id: str,
        customer_id: str
) -> str:
    """Stripe Checkout that always collects a payment method for reinstatement."""
    uid = str(user_id or '').strip()
    cid = str(customer_id or '').strip()
    if not uid or not cid or not _stripe_enabled():
        return ''
    price_id = _get_stripe_price_id('monthly_10_95')
    if not price_id:
        return ''
    try:

        success_url = url_for(
            'my_revisions',
            _external=True,
            _scheme=request.scheme
        ) + "?checkout=success"
        cancel_url = url_for(
            'plans',
            _external=True,
            _scheme=request.scheme
        )
        session_obj = stripe.checkout.Session.create(
            mode='subscription',
            customer=cid,
            payment_method_collection='always',
            line_items=[{'price': price_id, 'quantity': 1}],
            client_reference_id=uid,
            metadata={
                'plan_id': 'monthly_10_95',
                'reinstate_from_offer': '1',
            },
            subscription_data={
                'metadata': {
                    'plan_id': 'monthly_10_95',
                    'user_id': uid,
                    'reinstate_from_offer': '1',
                },
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return str(getattr(session_obj, 'url', '') or '').strip()
    except Exception:
        logger.exception(
            'Failed creating reinstate offer checkout session for customer %s',
            cid
        )
        return ''


def _find_access_granting_subscription_for_customer(customer_id: str):
    cid = str(customer_id or '').strip()
    if not cid or not _stripe_enabled():
        return None
    try:

        subs = stripe.Subscription.list(
            customer=cid,
            status='all',
            limit=20
        )
        eligible = [s for s in list(getattr(subs, 'data', []) or []) if
                    _stripe_subscription_grants_access(s)]
        if not eligible:
            return None

        def _rank(sub):
            status = str(
                _stripe_obj_get(sub, 'status', '') or ''
            ).strip().lower()
            cpe = int(_stripe_obj_get(sub, 'current_period_end', 0) or 0)
            score = 1
            if status == 'active':
                score = 3
            elif status == 'trialing':
                score = 2
            return (score, cpe)

        return sorted(eligible, key=_rank, reverse=True)[0]
    except Exception:
        return None


def _resolve_reinstate_offer_subscription_id(
        user_id: str,
        token_subscription_id: str = '',
        email: str = '',
) -> tuple[str, str]:
    """Resolve which Stripe subscription a signed reinstate offer should target.

    Returns (subscription_id, error_message). error_message is empty on success.
    """
    uid = str(user_id or '').strip()
    token_sid = str(token_subscription_id or '').strip()
    if not uid:
        return '', 'No subscription found to reinstate.'

    customer_id = _get_stripe_customer_id_from_azure(uid)
    if not customer_id:
        customer_id = _find_stripe_customer_id_by_email(
            str(email or '').strip().lower(),
            require_subscription_history=True
        )

    def _belongs(sid: str) -> bool:
        if not sid:
            return False
        if customer_id:
            return _subscription_belongs_to_customer(sid, customer_id)
        try:

            sub = stripe.Subscription.retrieve(sid)
            cust = str(_stripe_obj_get(sub, 'customer', '') or '').strip()
            if not cust:
                return False
            owner = _find_user_id_by_stripe_customer_id(cust)
            return owner == uid
        except Exception:
            return False

    if customer_id and _stripe_enabled():
        active = _find_access_granting_subscription_for_customer(
            customer_id
        )
        if active:
            active_sid = str(
                _stripe_obj_get(active, 'id', '') or ''
            ).strip()
            if active_sid:
                return active_sid, ''

    if token_sid:
        if _belongs(token_sid):
            return token_sid, ''
        return '', 'This offer link does not match your account.'

    azure_sid = _get_stripe_subscription_id_from_azure(uid)
    if azure_sid and _belongs(azure_sid):
        return azure_sid, ''

    if customer_id and _stripe_enabled():
        try:

            subs = stripe.Subscription.list(
                customer=customer_id,
                status='all',
                limit=20
            )
            candidates = list(getattr(subs, 'data', []) or [])
            if candidates:
                latest = sorted(
                    candidates,
                    key=lambda s: int(
                        _stripe_obj_get(s, 'created', 0) or 0
                    ),
                    reverse=True,
                )[0]
                latest_sid = str(
                    _stripe_obj_get(latest, 'id', '') or ''
                ).strip()
                if latest_sid:
                    return latest_sid, ''
        except Exception:
            logger.exception(
                'reinstate offer: unable to list subscriptions for customer %s',
                customer_id
            )

    return '', 'No subscription found to reinstate.'


def _reinstate_paid_offer_subscription(
        user_id: str,
        subscription_id: str
) -> dict:
    """Reinstate a paid-cancel offer for active, scheduled-cancel, or fully canceled subs."""
    uid = str(user_id or '').strip()
    sid = str(subscription_id or '').strip()
    if not uid or not sid:
        return {
            'ok': False,
            'message': 'No subscription found to reinstate.',
            'redirect_url': '',
            'offer_applied': False,
            'reactivated': False,
        }

    try:
        sub = stripe.Subscription.retrieve(
            sid,
            expand=['items.data.price', 'default_payment_method'],
        )
    except Exception:
        logger.exception(
            'reinstate offer: unable to retrieve subscription %s',
            sid
        )
        return {
            'ok': False,
            'message': 'Unable to reinstate subscription. Please try again.',
            'redirect_url': '',
            'offer_applied': False,
            'reactivated': False,
        }

    customer_id = str(_stripe_obj_get(sub, 'customer', '') or '').strip()
    status = str(_stripe_obj_get(sub, 'status', '') or '').strip().lower()
    offer_applied = False
    offer_message = ''
    reactivated = False

    existing_active = _find_access_granting_subscription_for_customer(
        customer_id
    )
    if existing_active:
        active_sid = str(
            _stripe_obj_get(existing_active, 'id', '') or ''
        ).strip()
        if active_sid and active_sid != sid:
            sub = existing_active
            sid = active_sid
            status = str(
                _stripe_obj_get(sub, 'status', '') or ''
            ).strip().lower()
            reactivated = True

    if status in ('active', 'trialing'):
        _stripe_subscription_modify(sid, sub, cancel_at_period_end=False)
        offer_ok, offer_msg, _ = _apply_reinstate_next_month_price_offer(
            sub,
            target_price_cents=399
        )
        offer_applied = bool(offer_ok)
        offer_message = str(offer_msg or '')
        _persist_stripe_subscription_to_profile(
            uid,
            sub,
            plan_id='monthly_10_95'
        )
        msg = 'Subscription reinstated.'
        if offer_message:
            msg = f'{msg} {offer_message}'.strip()
        return {
            'ok': True,
            'message': msg,
            'redirect_url': url_for('settings_page'),
            'offer_applied': offer_applied,
            'reactivated': reactivated,
        }

    if status in ('canceled', 'incomplete_expired'):
        if not customer_id:
            return {
                'ok': False,
                'message': 'Unable to reinstate subscription: billing profile is incomplete.',
                'redirect_url': url_for('settings_page'),
                'offer_applied': False,
                'reactivated': False,
            }
        offer_ok, offer_msg, _ = _apply_reinstate_offer_credit_from_monthly_price(
            customer_id,
            target_price_cents=399
        )
        offer_applied = bool(offer_ok)
        offer_message = str(offer_msg or '')
        msg = 'Please enter your payment details to reactivate your subscription.'
        if offer_message:
            msg = f'{msg} {offer_message}'.strip()
        return {
            'ok': False,
            'message': msg,
            'redirect_url': url_for(
                'checkout',
                plan='monthly_10_95',
                reinstate_offer='1'
            ),
            'offer_applied': offer_applied,
            'reactivated': False,
        }

    return {
        'ok': False,
        'message': 'Your subscription is not active. Please contact support to reactivate.',
        'redirect_url': url_for('checkout', plan='monthly_10_95'),
        'offer_applied': False,
        'reactivated': False,
    }


def _create_invoice_payment_link(customer_id: str, invoice_id: str) -> \
        Optional[str]:
    """Create Stripe Hosted Invoice Payment Page URL for manual payment retry.

    For India recurring payments when mandate expires or bank rejects: allows customer
    to re-authenticate and reestablish the recurring mandate.
    """
    try:

        if not stripe.api_key or not customer_id or not invoice_id:
            return None

        # Retrieve invoice to get the hosted invoice URL
        invoice = stripe.Invoice.retrieve(invoice_id)
        hosted_invoice_url = getattr(invoice, 'hosted_invoice_url', None)
        if hosted_invoice_url:
            return str(hosted_invoice_url)
        return None
    except Exception as e:
        logger.warning(f"Failed to create invoice payment link: {str(e)}")
        return None


def _send_payment_recovery_email(email: str, payment_link: str) -> bool:
    """Send payment recovery email to customer with link to retry payment.

    For India recurring payments: when automatic renewal fails, customer receives
    this email asking them to manually complete payment.
    """
    try:
        email = (email or '').strip().lower()
        if not email or not payment_link:
            return False

        _load_email_config_if_missing()
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        auth_email = (
                os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip(
            '"'
        ).strip("'")
        auth_password = (os.getenv(
            'NEWSLETTER_PASSWORD',
            ''
        ) or '').strip().strip('"').strip("'").replace(' ', '')

        if not auth_email or not auth_password:
            logger.warning(
                'Email credentials not configured for payment recovery email.'
            )
            return False

        msg = MIMEMultipart('alternative')
        msg[
            'Subject'] = 'Action Required: Complete Your Subscription Payment'
        msg['From'] = auth_email
        msg['To'] = email

        # Plain text version
        text_body = f"""
Your subscription payment requires your attention.

Your bank has blocked the automatic payment for your subscription. This is common for recurring payments in India and can usually be resolved in seconds.

To complete your payment and keep your subscription active, please click the link below:

{payment_link}

You'll be prompted to authenticate with your bank and approve the payment. Once completed, your subscription will continue automatically.

If you have any questions or need assistance, please reply to this email.

Thank you!
Resumatic Team
        """

        # HTML version
        html_body = f"""
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2>Action Required: Complete Your Subscription Payment</h2>
    <p>Your subscription payment requires your attention.</p>
    <p>Your bank has blocked the automatic payment for your subscription. This is common for recurring payments in India and can usually be resolved in seconds.</p>
    <p><strong>To complete your payment and keep your subscription active:</strong></p>
    <p style="margin: 20px 0;">
      <a href="{payment_link}" style="display: inline-block; padding: 12px 24px; background-color: #007bff; color: white; text-decoration: none; border-radius: 4px; font-weight: bold;">
        Complete Payment Now
      </a>
    </p>
    <p>You'll be prompted to authenticate with your bank and approve the payment. Once completed, your subscription will continue automatically.</p>
    <p>If you have any questions or need assistance, please reply to this email.</p>
    <p>Thank you!<br/>Resumatic Team</p>
  </body>
</html>
        """

        part1 = MIMEText(text_body, 'plain')
        part2 = MIMEText(html_body, 'html')
        msg.attach(part1)
        msg.attach(part2)

        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(auth_email, auth_password)
            server.send_message(msg)

        logger.info(f"Payment recovery email sent to {email}")
        return True
    except Exception as e:
        logger.error(
            f"Failed to send payment recovery email to {email}: {str(e)}"
        )
        return False


def _redirect_to_stripe_payment_link(
        plan_id: str,
        offer_retention: bool = False
) -> Optional['Response']:
    """Redirect to Stripe Payment Link with useful prefill params so webhook can map back to user."""
    # Trial plans must be subscriptions with pending SetupIntent / Checkout Session, not Payment Links.
    plan_id = _normalize_plan_id(plan_id)
    if plan_id in ('trial_7d', EMAIL_TRIAL_PLAN_ID):
        return None
    link = _get_stripe_payment_link(plan_id)
    if not link:
        return None
    params = {}
    try:
        email = (getattr(current_user, 'email', '') or '').strip()
        if email:
            params['prefilled_email'] = email
    except Exception:
        pass
    # This is the most reliable way for webhook to map checkout back to our user.
    try:
        params['client_reference_id'] = str(
            getattr(current_user, 'id', '') or ''
        )
    except Exception:
        pass
    # Helpful for debugging / analytics
    params['metadata[plan_id]'] = plan_id
    # Retention offer: prefill promotion code so customer gets the discount
    if offer_retention:
        promo = _get_stripe_retention_promo_code()
        if promo:
            params['prefilled_promo_code'] = promo

    sep = '&' if ('?' in link) else '?'
    url = link + (sep + urlencode(params)) if params else link
    return redirect(url, code=303)


@app.route("/checkout")
def checkout():
    """Combined Checkout Entrypoint.

    Unifies the dynamic price-id model with legacy support for email trial invites,
    RBI e-mandates, trial authorization holds, standard Stripe hosted sessions,
    and standalone one-time trial products.
    """

    def _checkout_response(resp):
        try:
            resp.headers[
                'Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp.headers['Pragma'] = 'no-cache'
            resp.headers['Expires'] = '0'
        except Exception:
            pass
        return resp

    # 1. Parse incoming parameters
    invite_token = str(request.args.get('invite') or '').strip()
    plan_arg = str(request.args.get('plan') or '').strip()
    offer_retention = str(
        request.args.get('offer') or ''
    ).strip().lower() == 'retention'
    reinstate_offer = _is_reinstate_offer_checkout_request()

    # Persist a valid email-trial invite before any redirects (e.g. login).
    if invite_token:
        _resolve_email_trial_invite(invite_token)

    # 2. Normalize and look up plan configuration
    plan_id = _normalize_plan_id(plan_arg) or plan_arg
    if not plan_id and _get_email_trial_invite_from_session():
        plan_id = EMAIL_TRIAL_PLAN_ID
    if not plan_id and invite_token and confirm_email_trial_invite_token(
            invite_token
    ):
        plan_id = EMAIL_TRIAL_PLAN_ID

    # Try resolving via modern catalog helper first, falling back to legacy config lookup
    plan = None
    if hasattr(stripe, 'Price') or plan_id.startswith("price_"):
        plan = _get_plan_by_price_id(plan_id)
    if not plan:
        plan = _get_plan_config(plan_id)

    if not plan:
        logger.warning(
            "checkout invalid plan: plan_arg=%r plan_id=%r invite_present=%s session_invite=%s",
            plan_arg,
            plan_id,
            bool(invite_token),
            bool(_get_email_trial_invite_from_session()),
        )
        flash("Please select a valid plan.", "danger")
        return redirect(url_for("plans"))

    # Unify plan identifiers across modern and legacy mappings
    plan_role = plan.get("role") or ""
    price_id = plan.get("price_id") or _get_stripe_price_id(
        plan_id
    ) or plan_id

    # 3. Handle Email Trial Invitations
    if _is_email_trial_plan(plan_id):
        invite = _resolve_email_trial_invite(invite_token)
        if not invite:
            flash(
                "This trial offer link has expired or is invalid. Please use the link from your email.",
                "danger"
            )
            return redirect(url_for("plans"))

    # 4. Authentication Check
    if not current_user.is_authenticated:
        login_next = url_for("checkout", plan=plan_arg)
        if invite_token and _is_email_trial_plan(plan_id):
            login_next = url_for(
                "checkout",
                plan=plan_arg,
                invite=invite_token
            )
        elif reinstate_offer and plan_id in ('monthly_10_95', 'monthly'):
            login_next = url_for(
                "checkout",
                plan=plan_arg,
                reinstate_offer='1'
            )
        return redirect(url_for("login", next=login_next))

    # 5. Enforce One-Time Trial Limits
    if (
            plan_role == "trial" or plan_id == 'trial_7d') and _trial_already_used_for_user(
        current_user
    ):
        flash(
            "The trial subscription is a one-time offer and has already been used on this account. Please choose Monthly or Annual.",
            "warning"
        )
        return redirect(url_for("plans"))

    if _is_email_trial_plan(plan_id):
        allowed, reason = _user_can_start_email_trial(current_user)
        if not allowed:
            flash(
                "You already have an active subscription." if reason == 'already_subscribed' else "This trial offer is not available for your account.",
                "warning"
            )
            return redirect(url_for("my_revisions"))

    # 6. Resolve Existing Customer Identifiers
    existing_customer_id = ""

    if _stripe_enabled():
        try:
            prof = get_user_profile_azure(
                getattr(current_user, "id", "")
            ) or {}

            candidate = (prof.get("stripe_customer_id") or "").strip()

            if candidate.startswith("cus_"):
                existing_customer_id = candidate

            if not existing_customer_id:
                email = (getattr(current_user, "email", "") or "").strip()
                existing_customer_id = _find_stripe_customer_id_by_email(
                    email,
                    require_subscription_history=True
                ) or ""

                if not existing_customer_id:
                    existing_customer_id = ""

        except Exception:
            existing_customer_id = ""

    # 7. Flow: Reinstate Offer Override
    if reinstate_offer and plan_id in ('monthly_10_95', 'monthly'):
        _mark_reinstate_offer_checkout_in_session()
        if _stripe_enabled() and existing_customer_id and not _should_use_embedded_subscription_checkout(
                plan_id
        ):
            try:
                checkout_url = _create_reinstate_offer_checkout_url(
                    str(current_user.id),
                    existing_customer_id
                )
                if checkout_url:
                    return redirect(checkout_url, code=303)
            except Exception:
                logger.exception(
                    "reinstate offer checkout redirect failed"
                )

    # 8. Flow: RBI E-mandate Embedded Setup Checkout (India context)
    if _should_use_embedded_subscription_checkout(plan_id):
        current_year = datetime.now().year
        stripe_pub = (os.getenv('STRIPE_PUBLISHABLE_KEY') or '').strip()
        return _checkout_response(
            make_response(
                render_template(
                    "checkout.html",
                    year=current_year,
                    user=current_user,
                    plan=plan,
                    stripe_enabled=True,
                    stripe_publishable_key=stripe_pub,
                    use_rbi_embedded_checkout=True,
                    reinstate_offer=reinstate_offer,
                )
            )
        )

    # 9. Flow: Trial Authorization Holds
    if _should_use_trial_authorization_hold(plan_id):
        current_year = datetime.now().year
        stripe_pub = (os.getenv('STRIPE_PUBLISHABLE_KEY') or '').strip()
        trial_ctx = _trial_hold_checkout_template_context(plan_id)

        if _should_use_embedded_trial_hold_checkout(plan_id):
            return _checkout_response(
                make_response(
                    render_template(
                        'checkout.html',
                        year=current_year,
                        user=current_user,
                        plan=plan,
                        stripe_enabled=True,
                        stripe_publishable_key=stripe_pub,
                        use_rbi_embedded_checkout=False,
                        use_trial_hold_checkout=True,
                        reinstate_offer=reinstate_offer,
                        **trial_ctx,
                    )
                )
            )

        try:
            checkout_url = _create_trial_hold_checkout_session_url(
                current_user,
                plan_id=plan_id
            )
            if checkout_url:
                resp = make_response(
                    render_template(
                        'checkout_trial_redirect.html',
                        stripe_checkout_url=checkout_url,
                        plan=plan,
                        **trial_ctx,
                    )
                )
                return _checkout_response(resp)
        except Exception:
            logger.exception('trial hold hosted checkout redirect failed')
        flash(
            'Checkout is temporarily unavailable. Please try again.',
            'danger'
        )
        return redirect(url_for('plans'))

    # 10. Flow: Mid-Trial Upgrade Mode
    if _stripe_enabled() and (
            plan_role in ("monthly", "annual") or plan_id in (
            "monthly_10_95", "annual_6_95")) and existing_customer_id:
        try:
            trial_sub = _find_trialing_subscription_for_customer(
                existing_customer_id
            )
            if trial_sub:
                unit_amount = int(plan.get("unit_amount") or 0)
                currency = str(plan.get("currency") or "usd")
                if not price_id or unit_amount <= 0:
                    flash(
                        "Checkout is not configured. Please contact support.",
                        "danger"
                    )
                    return redirect(url_for("plans"))

                success_url = url_for(
                    'my_revisions',
                    _external=True,
                    _scheme=request.scheme
                ) + "?checkout=success"
                cancel_url = url_for(
                    'plans',
                    _external=True,
                    _scheme=request.scheme
                )
                session_obj = stripe.checkout.Session.create(
                    mode="payment",
                    customer=existing_customer_id,
                    line_items=[{
                        "price_data": {
                            "currency": currency,
                            "unit_amount": unit_amount,
                            "product_data": {
                                "name": f"{plan.get('label')} (starts after trial)"},
                        },
                        "quantity": 1,
                    }],
                    client_reference_id=str(current_user.id),
                    metadata={
                        "upgrade_from_trial": "1",
                        "plan_id": plan_id,
                        "plan_role": plan_role,
                        "trial_subscription_id": str(
                            getattr(trial_sub, "id", "") or ""
                        ),
                    },
                    success_url=success_url,
                    cancel_url=cancel_url,
                )
                return redirect(session_obj.url, code=303)
        except Exception as e:
            logger.error(
                f"Stripe trial-upgrade checkout session create failed: {str(e)}"
            )

    # 11. Flow: Stripe Payment Links Override
    if _stripe_enabled() and (
            plan_role in ("monthly", "annual") or plan_id in (
            "monthly_10_95", "annual_6_95")) and not reinstate_offer:
        pl_redirect = _redirect_to_stripe_payment_link(
            plan_id,
            offer_retention=offer_retention
        )
        if pl_redirect:
            return pl_redirect

    if not (reinstate_offer and plan_id in ('monthly_10_95', 'monthly')):
        pl_redirect = _redirect_to_stripe_payment_link(
            plan_id,
            offer_retention=offer_retention
        )
        if pl_redirect:
            return pl_redirect

    # 12. Flow: Native Subscription & Standalone One-Time Trial Stripe Checkout
    if _stripe_enabled():
        if not price_id:
            flash(
                "Checkout is not configured. Please contact support.",
                "danger"
            )
            return redirect(url_for("plans"))

        success_url = url_for(
            'my_revisions',
            _external=True,
            _scheme=request.scheme
        ) + "?checkout=success"
        cancel_url = url_for(
            'plans',
            _external=True,
            _scheme=request.scheme
        )

        try:
            # --- RECURRING TRIAL CHECK ---
            is_recurring = bool(plan.get("interval"))

            # Check for hold enablement regardless of recurring status
            use_hold = plan.get("use_trial_hold") in ["true", True, "True",
                                                      "1", 1]

            # --- STANDALONE TRIAL CONDITION BLOCK ---
            # Use the hold price ID if it exists and the flag is set, otherwise use the passed price_id
            hold_price_id = plan.get("trial_fee_price_id")
            target_price_id = hold_price_id if (
                    use_hold and hold_price_id) else price_id

            if use_hold and hold_price_id:
                # Calculate amount for display (assuming unit_amount is in cents)
                # Fallback to 10.95 if unknown
                cents = plan.get('unit_amount', 1095)
                formatted_price = f"${cents / 100:.2f}"

                # Handle standalone one_time trial items via payment mode (Authorization Hold)
                session_params = {
                    "mode": "payment",
                    "line_items": [
                        {"price": target_price_id, "quantity": 1}
                    ],
                    "client_reference_id": str(current_user.id),
                    "metadata": {
                        "plan_id": plan_id,
                        "plan_role": "trial",
                        "trial_deposit_payment": "1",
                        "original_price_cents": str(cents),
                        # Store price for the webhook later
                    },
                    "success_url": success_url,
                    "cancel_url": cancel_url,
                    "payment_intent_data": {
                        "capture_method": "manual",
                        # This text shows up on their bank statement
                        "description": f"Trial Authorization Hold - {formatted_price}"
                    },
                    # This text shows up on the actual Stripe Checkout page
                    "custom_text": {
                        "after_submit": {
                            "message": (
                                f"You are authorizing a hold of {formatted_price}. "
                                "This is not a charge. The funds will remain on hold "
                                "and will be collected in 7 days. You may cancel "
                                "anytime before then to release the hold."
                            )
                        }
                    },
                }
            else:
                # Standard subscription processing paths (Includes Auto-Rollover Trials)
                subscription_data = None
                line_items = [{"price": price_id, "quantity": 1}]

                email_invite = _get_email_trial_invite_from_session() if _is_email_trial_plan(
                    plan_id
                ) else None

                if _is_email_trial_plan(plan_id):
                    trial_days = max(
                        1,
                        int(
                            (email_invite or {}).get(
                                'trial_days'
                            ) or 10
                        )
                    )
                    subscription_data = {
                        "trial_end": _stripe_trial_end_ts_for_days(
                            trial_days
                        )}
                    if not bool(
                            (email_invite or {}).get(
                                'waive_upfront_fee',
                                True
                            )
                    ):
                        fee_price = _get_stripe_trial_upfront_fee_price_id()
                        if fee_price:
                            line_items.append(
                                {"price": fee_price, "quantity": 1}
                            )
                elif plan_role == "trial":
                    # --- NEW: Handles the trial that rolls into a subscription ---
                    trial_days = int(
                        plan.get("trial_days") or
                        plan.get("trial_period_days") or
                        plan.get("metadata", {}).get("trial_days") or 7
                    )
                    subscription_data = {
                        "trial_period_days": trial_days}

                    fee_price = plan.get("trial_fee_price_id") or ""
                    if fee_price:
                        line_items.append(
                            {"price": fee_price, "quantity": 1}
                        )
                elif plan.get("trial_period_days"):
                    subscription_data = {"trial_period_days": int(
                        plan["trial_period_days"]
                    )}
                    fee_price = plan.get("trial_fee_price_id") or ""
                    if fee_price:
                        line_items.append(
                            {"price": fee_price, "quantity": 1}
                        )

                metadata = {"plan_id": plan_id, "plan_role": plan_role}
                if email_invite and str(
                        email_invite.get('campaign') or ''
                ).strip():
                    metadata["campaign"] = str(
                        email_invite.get('campaign') or ''
                    ).strip()
                if reinstate_offer and plan_id in (
                        'monthly_10_95', 'monthly'):
                    metadata["reinstate_from_offer"] = "1"

                session_params = {
                    "mode": "subscription",
                    "line_items": line_items,
                    "client_reference_id": str(current_user.id),
                    "metadata": metadata,
                    "success_url": success_url,
                    "cancel_url": cancel_url,
                }

                # Assign subscription_data cleanly
                if subscription_data:
                    session_params[
                        "subscription_data"] = subscription_data

            session_params.pop("customer", None)
            session_params.pop("customer_creation", None)
            session_params.pop("customer_email", None)

            if existing_customer_id:
                session_params["customer"] = existing_customer_id
            else:
                session_params[
                    "customer_email"] = current_user.email if current_user.is_authenticated else None
                if session_params["mode"] != "subscription":
                    session_params["customer_creation"] = "always"

            # Pricing and Promotion Options Management
            if plan_role != "trial":
                coupon_id = _get_stripe_retention_coupon_id() if (
                        offer_retention or plan_id in (
                    'monthly_10_95', 'monthly')) else None
                if offer_retention and coupon_id:
                    session_params["discounts"] = [
                        {"coupon": coupon_id}]
                else:
                    session_params["allow_promotion_codes"] = True

            if reinstate_offer and plan_id in (
                    'monthly_10_95', 'monthly'):
                session_params.pop("customer_email", None)
                if existing_customer_id:
                    session_params["customer"] = existing_customer_id
                session_params["payment_method_collection"] = "always"
                session_params["allow_promotion_codes"] = False

            if plan_id == EMAIL_TRIAL_PLAN_ID:
                session_params[
                    "billing_address_collection"] = "required"

            payment_config = _get_payment_method_config_for_checkout(
                plan_id
            )
            if payment_config and 'payment_method_types' in payment_config:
                session_params['payment_method_types'] = \
                    payment_config[
                        'payment_method_types']

            # Clear development bypass flag before moving to live Stripe
            from flask import session

            session.pop('dev_bypass_trial_check', None)

            session_obj = stripe.checkout.Session.create(
                **session_params
            )
            return redirect(session_obj.url, code=303)

        except Exception as e:
            logger.error(
                f"Stripe checkout session create failed: {str(e)}"
            )
            flash(
                "Checkout is temporarily unavailable. Please try again.",
                "danger"
            )
            return redirect(url_for("plans"))

    # 13. System Fallback (No Stripe Enabled)
    current_year = datetime.now().year
    stripe_pub = (os.getenv('STRIPE_PUBLISHABLE_KEY') or '').strip()
    return _checkout_response(
        make_response(
            render_template(
                "checkout.html",
                year=current_year,
                user=current_user,
                plan=plan,
                stripe_enabled=False,
                stripe_publishable_key=stripe_pub,
                use_rbi_embedded_checkout=False
            )
        )
    )


@app.route("/checkout/trial-hold-success")
@login_required
def checkout_trial_hold_success():
    """Return URL after Stripe Hosted Checkout authorizes the trial hold."""
    session_id = str(request.args.get('session_id') or '').strip()
    if not session_id or not _stripe_enabled():
        flash(
            'Trial checkout could not be confirmed. Please try again.',
            'danger'
        )
        return redirect(url_for('plans'))

    user_id = str(getattr(current_user, 'id', '') or '')

    try:
        sess = stripe.checkout.Session.retrieve(
            session_id,
            expand=['payment_intent']
        )
        client_ref = str(
            getattr(sess, 'client_reference_id', '') or ''
        ).strip()
        if client_ref and client_ref != user_id:
            flash(
                'This checkout session does not belong to your account.',
                'danger'
            )
            return redirect(url_for('plans'))

        payment_intent = getattr(sess, 'payment_intent', None)
        pi_id = ''
        if isinstance(payment_intent, str):
            pi_id = payment_intent
        elif payment_intent is not None:
            pi_id = str(getattr(payment_intent, 'id', '') or '')

        if not pi_id:
            flash(
                'Payment authorization was not completed. Please try again.',
                'danger'
            )
            plan_id = str(
                (getattr(sess, 'metadata', None) or {}).get(
                    'plan_id'
                ) or 'trial_7d'
            ).strip()
            return redirect(
                url_for(
                    'checkout',
                    plan=_normalize_plan_id(plan_id) or 'trial_7d'
                )
            )

        ok, reason = _activate_trial_hold(user_id, pi_id)
        if not ok and reason not in ('already_active',):
            flash(
                'Your card was not authorized for the trial. Please try another card.',
                'danger'
            )
            try:
                intent = stripe.PaymentIntent.retrieve(pi_id)
                plan_id = _trial_hold_plan_id_from_intent(intent)
            except Exception:
                plan_id = 'trial_7d'
            return redirect(url_for('checkout', plan=plan_id))

        flash(
            'Your trial has started. A temporary authorization hold may appear on your card.',
            'success'
        )
        return redirect(url_for('my_revisions', checkout='success'))
    except Exception:
        logger.exception('checkout_trial_hold_success failed')
        flash(
            'Trial activation failed. Please contact support if you were charged.',
            'danger'
        )
        return redirect(url_for('plans'))


@app.route("/checkout/subscription-confirm")
@login_required
def checkout_subscription_confirm():
    """Return URL after 3DS confirmSetup for RBI e-mandate subscription setup."""
    subscription_id = str(
        request.args.get("subscription_id") or ""
    ).strip()
    setup_intent_id = str(request.args.get("setup_intent") or "").strip()
    redirect_status = str(
        request.args.get("redirect_status") or ""
    ).strip().lower()

    if setup_intent_id and redirect_status and redirect_status != "succeeded":
        flash(
            "Card authentication did not complete. Please try again.",
            "danger"
        )
        return redirect(url_for("plans"))

    if subscription_id and _stripe_enabled():
        try:
            sub = stripe.Subscription.retrieve(
                subscription_id,
                expand=["items.data.price", "pending_setup_intent"],
            )
            if _stripe_metadata_user_id(sub) == str(
                    getattr(current_user, "id", "") or ""
            ).strip():
                if _stripe_subscription_grants_access(sub):
                    plan_id = ""
                    try:
                        meta = getattr(sub, "metadata", None) or {}
                        if isinstance(meta, dict):
                            plan_id = str(
                                meta.get("plan_id") or ""
                            ).strip()
                        else:
                            plan_id = str(
                                getattr(meta, "plan_id", "") or ""
                            ).strip()
                    except Exception:
                        plan_id = ""
                    _persist_stripe_subscription_to_profile(
                        str(getattr(current_user, "id", "") or ""),
                        sub,
                        plan_id=plan_id
                    )
                    flash(
                        "Payment method saved — your subscription is active.",
                        "success"
                    )
                    return redirect(
                        url_for("my_revisions", checkout="success")
                    )
        except Exception as e:
            logger.warning(
                f"checkout_subscription_confirm error: {str(e)}"
            )

    flash(
        "Payment completed, but we couldn't confirm access yet. If this persists, please contact support.",
        "warning",
    )
    return redirect(url_for("my_revisions"))


@app.route("/checkout/success")
def checkout_success():
    """Stripe success return URL."""
    session_id = str(request.args.get("session_id") or "").strip()

    if not getattr(current_user, "is_authenticated", False):
        return redirect(url_for("login", next=request.full_path))

    if session_id and _stripe_enabled():
        try:
            sess = stripe.checkout.Session.retrieve(
                session_id,
                expand=['payment_intent']
            )
            meta = getattr(sess, 'metadata', None) or {}

            if isinstance(meta, dict):
                trial_deposit = str(
                    meta.get('trial_deposit_payment') or ''
                ).strip()
                plan_role = str(
                    meta.get('plan_role') or ''
                ).strip().lower()
                plan_id = str(meta.get('plan_id') or 'trial_7d').strip()
            else:
                trial_deposit = str(
                    getattr(meta, 'trial_deposit_payment', '') or ''
                ).strip()
                plan_role = str(
                    getattr(meta, 'plan_role', '') or ''
                ).strip().lower()
                plan_id = str(
                    getattr(meta, 'plan_id', 'trial_7d') or 'trial_7d'
                ).strip()

            pay_status = str(
                getattr(sess, 'payment_status', '') or ''
            ).strip().lower()

            # NEW: Extract mode to cleanly separate one-time trials from recurring trials
            mode = str(
                getattr(sess, 'mode', '') or ''
            ).strip().lower()

            # SUPPORT INTERFACE: Standalone one_time product immediate recovery check
            # NEW: Added `mode == 'payment'` constraint
            if (
                    trial_deposit == '1' or plan_role == 'trial') and mode == 'payment' and pay_status == 'paid':
                customer_id = str(
                    getattr(sess, 'customer', '') or ''
                ).strip()
                amount_total = int(getattr(sess, 'amount_total', 0) or 0)
                currency = str(getattr(sess, 'currency', 'usd') or 'usd')
                payment_intent = getattr(sess, 'payment_intent', None)
                payment_intent_id = ''
                if isinstance(payment_intent, str):
                    payment_intent_id = payment_intent
                elif payment_intent is not None:
                    payment_intent_id = str(
                        getattr(payment_intent, 'id', '') or ''
                    )

                if customer_id and payment_intent_id:
                    _fulfill_trial_deposit_checkout(
                        client_ref=str(
                            getattr(current_user, 'id', '') or ''
                        ),
                        customer_id=customer_id,
                        amount_total=amount_total,
                        currency=currency,
                        payment_intent_id=payment_intent_id,
                        plan_id=plan_id,
                    )
        except Exception:
            logger.exception(
                'checkout_success trial deposit fulfillment fallback failed'
            )

    refreshed = False
    try:
        refreshed = bool(
            _refresh_paid_status_from_stripe_for_user(current_user)
        )
    except Exception:
        refreshed = False

    if refreshed or is_paid_user(current_user):
        flash("Payment successful — your access is now active.", "success")
        return redirect(url_for("my_revisions", checkout="success"))

    flash(
        "Payment completed, but we couldn't confirm access yet. If this persists for a few minutes, please contact support.",
        "warning",
    )
    return redirect(url_for("my_revisions"))


@app.route("/checkout/complete", methods=["POST"])
@login_required
def checkout_complete():
    """Simulate purchase completion by updating the Azure Users profile."""
    plan_id = _normalize_plan_id(request.form.get('plan', '').strip())

    # Check catalog helper if active, falling back to basic legacy dictionary check
    plan = None
    if plan_id.startswith("price_"):
        plan = _get_plan_by_price_id(plan_id)
    if not plan:
        plan = _get_plan_config(plan_id)

    if not plan:
        flash("Invalid plan selection.", "danger")
        return redirect(url_for("plans"))

    plan_role = plan.get("role") or ""

    # Enforce one-time trial offer even when running with the placeholder checkout flow.
    if (
            plan_id == 'trial_7d' or plan_role == 'trial') and _trial_already_used_for_user(
        current_user
    ):
        flash(
            "The trial is a one-time offer and has already been used on this account.",
            "warning"
        )
        return redirect(url_for("plans"))

    try:
        duration = int(
            plan.get('duration_days') or plan.get('trial_period_days') or 7
        )
        paid_until = (datetime.now(timezone.utc) + timedelta(
            days=duration
        )).isoformat()
        table_client = get_users_table_client()
        entity = {
            'PartitionKey': str(current_user.id),
            'RowKey': 'profile',
            'is_paid': True,
            'plan_status': plan_role or plan.get('plan_status') or 'trial',
            'paid_until': paid_until,
        }
        if plan_id in (
                'trial_7d', EMAIL_TRIAL_PLAN_ID) or plan_role == 'trial':
            entity['trial_used'] = True
            entity['trial_used_at'] = datetime.now(
                timezone.utc
            ).isoformat()

        table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
        flash(f"You're all set! {plan.get('label')} activated.", "success")
        return redirect(url_for("my_revisions"))
    except Exception as e:
        logger.error(f"checkout_complete error: {str(e)}")
        flash(
            "We couldn't activate your plan. Please try again.",
            "danger"
        )
        return redirect(url_for("plans"))


@app.route("/sw.js")
def service_worker():
    """Serve a harmless no-op service worker script."""
    js = """
self.addEventListener('install', function (event) {
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', function () {});
""".strip()
    resp = make_response(js)
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    resp.headers[
        "Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route('/dev/reset-trial')
@login_required
def dev_reset_trial():
    # Enforce local/development environment safeguards matching settings_page convention
    try:
        host = str(getattr(request, "host", "") or "").lower()
    except Exception:
        host = ""

    is_dev_allowed = bool(
        host.startswith("127.0.0.1")
        or host.startswith("localhost")
        or (os.getenv("ENABLE_SETTINGS_DEBUG") or "").strip() == "1"
    )

    if not is_dev_allowed:
        abort(403)  # Forbidden in production environments

    # --- ADDED: Set the session flag to bypass live Stripe checks ---
    session['dev_bypass_trial_check'] = True

    try:
        table_client = get_users_table_client()
        user_id = str(current_user.id)

        # 1. Fetch current profile entity to see what keys exist
        try:
            profile_entity = table_client.get_entity(
                partition_key=user_id,
                row_key="profile"
            )
        except Exception:
            profile_entity = {}

        # 2. Build explicit update entity resetting all trial, billing, and status fields
        reset_entity = {
            "PartitionKey": user_id,
            "RowKey": "profile",
            "plan_status": "",
            "paid_until": "",
            "stripe_customer_id": "",
            "stripe_subscription_id": ""
        }

        # 3. Dynamic target-cleaning for historical tracking attributes used to flag 'You already used trial'
        possible_trial_flags = [
            "trial_used", "had_trial", "trial_redeemed", "used_trial",
            "has_had_trial", "trial_claimed", "promo_trial_used",
            "trial_used_at"
        ]

        for flag in possible_trial_flags:
            if flag in profile_entity:
                # Set boolean flags to False or delete/overwrite strings
                if isinstance(profile_entity[flag], bool):
                    reset_entity[flag] = False
                else:
                    reset_entity[flag] = ""

        # Fallback: Make sure the common ones are explicitly set to False/empty even if not yet in profile
        reset_entity["trial_used"] = False
        reset_entity["had_trial"] = False
        reset_entity["trial_used_at"] = ""

        # 4. Atomically write changes back to Azure Table Storage via Merge Mode
        table_client.upsert_entity(reset_entity, mode=UpdateMode.MERGE)

        flash(
            "Trial status tracking and live Stripe checks bypassed successfully.",
            "success"
        )
    except Exception as e:
        flash(f"Failed to reset trial parameters: {str(e)}", "danger")

    return redirect(url_for('plans'))


@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    """Combined Stripe webhook handler."""
    # 1. Grab raw bytes immediately. Do not call request.json before this!
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", "")
    webhook_secret = (os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip()

    # --- NEW DEBUG LOGGING ---
    # We safely mask the secret so we don't accidentally leak it into Azure logs
    secret_prefix = webhook_secret[:8] if webhook_secret else "NONE"
    secret_len = len(webhook_secret) if webhook_secret else 0

    logger.info("=== Webhook Debug Start ===")
    logger.info(f"Configured Secret Prefix: {secret_prefix}...")
    logger.info(f"Configured Secret Length: {secret_len} chars")
    logger.info(f"Stripe-Signature Header Present: {bool(sig_header)}")
    if sig_header:
        # Log the first bit of the header (t=timestamp, v1=signature...)
        logger.info(f"Header Structure: {sig_header[:40]}...")
    logger.info(f"Payload Size: {len(payload)} bytes")

    if not webhook_secret:
        logger.error("Webhook failed: STRIPE_WEBHOOK_SECRET is missing.")
        return ("Webhook not configured", 400)

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            webhook_secret
        )
        logger.info("=== Webhook Verified Successfully! ===")

    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Signature Verification Failed: {str(e)}")
        return ("Invalid signature", 400)
    except Exception as e:
        logger.error(f"Unexpected webhook error: {str(e)}")
        return ("Webhook error", 400)

    try:
        etype = _stripe_obj_get(event, "type", "")
        data = _stripe_obj_get(
            _stripe_obj_get(event, "data", {}),
            "object",
            {}
        ) or {}
        if not isinstance(data, dict):
            try:
                if hasattr(data, "to_dict_recursive"):
                    data = data.to_dict_recursive()
                elif hasattr(data, "to_dict"):
                    data = data.to_dict()
                else:
                    data = dict(data)
            except Exception:
                data = {}

        # --- 1. CORE COMPLETION MAPPINGS ---
        if etype == "checkout.session.completed":
            client_ref = data.get("client_reference_id")
            customer_id = data.get("customer")
            subscription_id = data.get("subscription")
            plan_id = (data.get("metadata") or {}).get("plan_id", "")
            plan_role = str(
                (data.get("metadata") or {}).get("plan_role") or ""
            ).strip().lower()

            if not plan_role and plan_id:
                plan_role = (_get_plan_by_price_id(plan_id) or {}).get(
                    "role",
                    ""
                )

            upgrade_from_trial = str(
                (data.get("metadata") or {}).get(
                    "upgrade_from_trial"
                ) or ""
            ).strip()
            trial_subscription_id = str(
                (data.get("metadata") or {}).get(
                    "trial_subscription_id"
                ) or ""
            ).strip()
            mode = str(data.get("mode") or "").strip().lower()

            # Email-matching customer fallback if client_reference_id is omitted
            if not client_ref:
                try:
                    email = ((data.get("customer_details") or {}).get(
                        "email"
                    ) or data.get("customer_email") or "")
                    email = str(email).strip().lower()
                    if email:
                        for uid, u in users.items():
                            if (getattr(
                                    u,
                                    "email",
                                    ""
                            ) or "").strip().lower() == email:
                                client_ref = uid
                                break
                except Exception:
                    pass

            if not client_ref:
                return ("No client_reference_id", 200)

            # Flow: Custom Trial Authorization Hold Checkout
            trial_hold_checkout = str(
                (data.get("metadata") or {}).get(
                    "trial_hold_checkout"
                ) or ""
            ).strip()
            if trial_hold_checkout == "1" and mode == "payment" and customer_id:
                payment_intent_id = str(
                    data.get("payment_intent") or ""
                ).strip()
                if payment_intent_id:
                    _activate_trial_hold(
                        str(client_ref),
                        payment_intent_id
                    )
                return ("OK", 200)

            # Flow: Upfront Trial Deposit / Standalone One-Time Trial Checkout Fulfillment
            trial_deposit_payment = str(
                (data.get("metadata") or {}).get(
                    "trial_deposit_payment"
                ) or ""
            ).strip()
            if (
                    trial_deposit_payment == "1" or plan_role == "trial") and mode == "payment":
                try:
                    amount_total = int(data.get("amount_total") or 0)
                    currency = str(data.get("currency") or "usd")
                except Exception:
                    amount_total = 0
                    currency = "usd"
                payment_intent_id = str(
                    data.get("payment_intent") or ""
                ).strip()
                if payment_intent_id:
                    _fulfill_trial_deposit_checkout(
                        client_ref=str(client_ref),
                        customer_id=str(customer_id),
                        amount_total=amount_total,
                        currency=currency,
                        payment_intent_id=payment_intent_id,
                        plan_id=str(plan_id or "trial_7d"),
                    )
                return ("OK", 200)

            # Unified Flow: Mid-Trial Sub Upgrades
            if (
                    upgrade_from_trial == "1" and mode == "payment" and customer_id and
                    trial_subscription_id and (
                    plan_role in ("monthly", "annual") or plan_id in (
                    "monthly_10_95", "annual_6_95"))):
                try:
                    amount_total = int(data.get("amount_total") or 0)
                    currency = str(data.get("currency") or "usd")
                except Exception:
                    amount_total = 0
                    currency = "usd"

                if amount_total > 0:
                    try:
                        stripe.Customer.create_balance_transaction(
                            customer_id,
                            amount=-amount_total,
                            currency=currency,
                            description=f"Prepayment credit for {plan_id} (paid during trial)",
                        )
                    except Exception:
                        pass

                try:
                    price_id = plan_id
                    if price_id:
                        sub = stripe.Subscription.retrieve(
                            trial_subscription_id,
                            expand=["items.data"]
                        )
                        items = getattr(sub, "items", None)
                        items_data = getattr(
                            items,
                            "data",
                            []
                        ) if items else []
                        item_id = str(
                            getattr(items_data[0], "id", "") or ""
                        ) if items_data else ""
                        if not item_id:
                            try:
                                si = stripe.SubscriptionItem.list(
                                    subscription=trial_subscription_id,
                                    limit=1
                                )
                                si_data = list(
                                    getattr(si, "data", []) or []
                                )
                                if si_data:
                                    item_id = str(
                                        getattr(si_data[0], "id", "") or ""
                                    ).strip()
                            except Exception:
                                item_id = ""
                        if item_id:
                            stripe.Subscription.modify(
                                trial_subscription_id,
                                items=[{"id": item_id, "price": price_id}],
                                proration_behavior="none",
                                metadata={"plan_id": plan_id,
                                          "plan_role": plan_role},
                            )

                        paid_until = ""
                        try:
                            current_period_end = getattr(
                                sub,
                                "current_period_end",
                                None
                            )
                            if current_period_end:
                                paid_until = datetime.fromtimestamp(
                                    int(current_period_end),
                                    tz=timezone.utc
                                ).isoformat()
                        except Exception:
                            paid_until = ""

                        table_client = get_users_table_client()
                        entity = {
                            "PartitionKey": str(client_ref),
                            "RowKey": "profile",
                            "is_paid": True,
                            "plan_status": plan_role or plan_id,
                            "stripe_customer_id": str(customer_id),
                            "stripe_subscription_id": str(
                                trial_subscription_id
                            ),
                        }
                        if paid_until:
                            entity["paid_until"] = paid_until
                        table_client.upsert_entity(
                            entity,
                            mode=UpdateMode.MERGE
                        )
                except Exception:
                    pass

                return ("OK", 200)

            # Standard Flow: Normal Checkout Completions Tracking (Subscriptions Only)
            paid_until = ""
            plan_status = ""
            try:
                if subscription_id and stripe.api_key:
                    sub = stripe.Subscription.retrieve(subscription_id)
                    plan_status = str(getattr(sub, "status", "") or "")
                    current_period_end = getattr(
                        sub,
                        "current_period_end",
                        None
                    )
                    if current_period_end:
                        paid_until = datetime.fromtimestamp(
                            int(current_period_end),
                            tz=timezone.utc
                        ).isoformat()
            except Exception:
                pass

            try:
                table_client = get_users_table_client()
                entity = {
                    "PartitionKey": str(client_ref),
                    "RowKey": "profile",
                    "is_paid": True,
                    # REFINED: Prefer actual Stripe subscription status ('trialing') over metadata
                    "plan_status": (
                            plan_status or plan_role or plan_id or "paid"),
                }
                if plan_role == "trial" or plan_id in (
                        'trial_7d', EMAIL_TRIAL_PLAN_ID):
                    entity["trial_used"] = True
                    entity["trial_used_at"] = datetime.now(
                        timezone.utc
                    ).isoformat()
                if paid_until:
                    entity["paid_until"] = paid_until
                if customer_id:
                    entity["stripe_customer_id"] = str(customer_id)
                if subscription_id:
                    entity["stripe_subscription_id"] = str(subscription_id)
                table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
            except Exception as e:
                logger.error(f"stripe_webhook upsert error: {str(e)}")
                return ("Error", 500)

            # Deduplicate concurrent trials if users check out for a paid tier over an active trial
            try:
                if customer_id and stripe.api_key:
                    subs_trialing = stripe.Subscription.list(
                        customer=customer_id,
                        status="trialing",
                        limit=20
                    )
                    tdata = list(getattr(subs_trialing, "data", []) or [])
                    for s in tdata:
                        sid = str(getattr(s, "id", "") or "")
                        if sid and subscription_id and sid == str(
                                subscription_id
                        ):
                            continue
                        if sid:
                            try:
                                stripe.Subscription.delete(sid)
                            except Exception:
                                pass
            except Exception:
                pass

        # --- 2. RETENTION INVOICING REDUCTIONS ---
        elif etype == "invoice.paid":
            inv = data
            if inv.get("subscription") and (
                    customer_id := str(inv.get("customer") or "").strip()):
                try:
                    cust = stripe.Customer.retrieve(customer_id)
                    meta = dict(getattr(cust, "metadata", None) or {})
                    credit_cents_str = meta.get(
                        "retention_2nd_credit_cents",
                        ""
                    ).strip()
                    if credit_cents_str and credit_cents_str.isdigit():
                        credit_cents = int(credit_cents_str)
                        currency = str(
                            inv.get("currency") or "usd"
                        ).lower()
                        stripe.Customer.create_balance_transaction(
                            customer_id,
                            amount=-credit_cents,
                            currency=currency,
                            description="Retention offer: 50% off month 2 of 2",
                        )
                        meta["retention_2nd_credit_cents"] = ""
                        stripe.Customer.modify(customer_id, metadata=meta)
                        logger.info(
                            f"Applied retention 2nd credit: {credit_cents} cents for customer {customer_id}"
                        )
                except Exception as e:
                    logger.warning(
                        f"retention 2nd credit webhook error: {str(e)}"
                    )

        # --- 3. SPECIALIZED/LEGACY TRIAL MECHANICS ---
        elif etype == "setup_intent.succeeded":
            _handle_setup_intent_succeeded_webhook(data)

        elif etype == "payment_intent.amount_capturable_updated":
            meta = data.get("metadata") or {}
            if str(meta.get("purpose") or "").strip() == "trial_hold":
                user_id = str(meta.get("user_id") or "").strip()
                pi_id = str(data.get("id") or "").strip()
                if user_id and pi_id and str(
                        data.get("status") or ""
                ).strip().lower() == "requires_capture":
                    _activate_trial_hold(user_id, pi_id)

        elif etype == "payment_intent.succeeded":
            meta = data.get("metadata") or {}
            if str(meta.get("purpose") or "").strip() == "trial_hold" and (
                    user_id := str(meta.get("user_id") or "").strip()):
                try:
                    table_client = get_users_table_client()
                    entity = {
                        "PartitionKey": user_id,
                        "RowKey": "profile",
                        "trial_hold_captured_at": datetime.now(
                            timezone.utc
                        ).isoformat(),
                    }
                    table_client.upsert_entity(
                        entity,
                        mode=UpdateMode.MERGE
                    )
                except Exception:
                    pass

        elif etype == "customer.subscription.trial_will_end":
            sub = data
            if str(sub.get("status") or "").strip().lower() == "trialing":
                if _get_subscription_authorization_payment_intent_id(sub):
                    logger.info(
                        "trial_will_end deferred capture skipped sub=%s",
                        str(sub.get("id") or "")
                    )
                else:
                    ok, reason = _capture_authorization_hold_for_subscription(
                        sub
                    )
                    logger.info(
                        "trial_will_end capture sub=%s ok=%s reason=%s",
                        str(sub.get("id") or ""),
                        bool(ok),
                        reason or "ok"
                    )

        # --- 4. RBI INDIA MANDATE EXCEEDED / RECOVERY ROUTINES ---
        elif etype == "invoice.payment_action_required":
            inv = data
            customer_id = str(inv.get("customer") or "").strip()
            invoice_id = str(inv.get("id") or "").strip()
            if customer_id and invoice_id:
                try:
                    table_client = get_users_table_client()
                    for e in table_client.list_entities():
                        if e.get("RowKey") == "profile" and str(
                                e.get("stripe_customer_id") or ""
                        ) == customer_id:
                            if user_email := str(
                                    e.get("email") or ""
                            ).strip():
                                payment_link = _create_invoice_payment_link(
                                    customer_id,
                                    invoice_id
                                )
                                if payment_link:
                                    _send_payment_recovery_email(
                                        user_email,
                                        payment_link
                                    )
                                    logger.info(
                                        f"Sent payment recovery email to {user_email} for invoice {invoice_id}"
                                    )
                            break
                except Exception as e:
                    logger.warning(
                        f"Payment action required webhook error: {str(e)}"
                    )

        elif etype == "invoice.payment_failed":
            logger.warning(
                f"Invoice {str(data.get('id'))} payment failed: {str(data.get('last_payment_error', {}).get('message', 'Unknown error'))}"
            )

            # --- 5. LIFECYCLE SYNC (UPDATES & CANCELLATIONS) ---
            # --- 5. LIFECYCLE SYNC (UPDATES & CANCELLATIONS) ---
        elif etype in (
            "customer.subscription.updated",
            "customer.subscription.deleted"):
            sub = data
            customer_id = sub.get("customer")
            subscription_id = sub.get("id")
            status = sub.get("status")

            # --- CANCELLATION & REFUND
            if status in ("canceled", "unpaid"):
                metadata = _stripe_obj_get(sub, "metadata", {})
                pi_id = metadata.get("trial_deposit_payment_intent")

                processed_refund = False
                if pi_id:
                    try:
                        # Expand the latest charge so we can check amount_refunded
                        pi = stripe.PaymentIntent.retrieve(
                            pi_id,
                            expand=["latest_charge"]
                            )

                        # If the money was already captured, we MUST issue a refund
                        if pi.status == "succeeded" and pi.amount_received > 0:
                            charge = _stripe_obj_get(
                                pi,
                                "latest_charge",
                                {}
                                )
                            amount_refunded = int(
                                _stripe_obj_get(
                                    charge,
                                    "amount_refunded",
                                    0
                                    )
                                )

                            if amount_refunded < pi.amount_received:
                                try:
                                    stripe.Refund.create(
                                        payment_intent=pi_id,
                                        reason="requested_by_customer"
                                    )
                                    logger.info(
                                        f"Refunded captured trial deposit for PI: {pi_id}"
                                        )
                                except stripe.error.InvalidRequestError as refund_err:
                                    # Failsafe: If Stripe already refunded it, ignore this specific error
                                    if "refunded" not in str(
                                            refund_err
                                            ).lower():
                                        raise refund_err

                            processed_refund = True
                    except Exception as e:
                        logger.error(
                            f"Failed to check PI status for refund {pi_id}: {str(e)}"
                            )

                # If it wasn't refunded above, release the hold normally
                if not processed_refund:
                    _release_authorization_hold_for_subscription(sub)
                    logger.info(
                        f"Subscription {subscription_id} canceled/unpaid. Hold released."
                        )

            if etype == "customer.subscription.updated":
                # Ensure we handle the event safely
                previous_attributes = _stripe_obj_get(
                    data,
                    # Note: using 'data' instead of 'event' since 'sub' is 'data' here
                    "previous_attributes",
                    {}
                )

                # Default ok to False to prevent UnboundLocalError
                ok = False

                if status == 'active' and previous_attributes.get(
                        'status'
                        ) == 'trialing':
                    # ASSIGN the result to ok
                    ok, reason = _capture_authorization_hold_for_subscription(
                        sub,
                        apply_balance=False
                    )

                if ok:
                    try:
                        latest_invoice_id = _stripe_obj_get(
                            sub,
                            "latest_invoice",
                            ""
                            )
                        if latest_invoice_id:
                            if isinstance(latest_invoice_id, dict):
                                latest_invoice_id = latest_invoice_id.get(
                                    "id"
                                    )
                            elif getattr(latest_invoice_id, "id", ""):
                                latest_invoice_id = getattr(
                                    latest_invoice_id,
                                    "id",
                                    ""
                                    )

                            if latest_invoice_id:
                                inv = stripe.Invoice.retrieve(
                                    latest_invoice_id
                                    )
                                pi_id = _stripe_obj_get(
                                    inv,
                                    "payment_intent",
                                    ""
                                    )
                                if isinstance(pi_id, dict):
                                    pi_id = pi_id.get("id")
                                elif getattr(pi_id, "id", ""):
                                    pi_id = getattr(pi_id, "id", "")

                                if pi_id and _stripe_obj_get(
                                        inv,
                                        "amount_paid",
                                        0
                                        ) > 0:
                                    stripe.Refund.create(
                                        payment_intent=pi_id,
                                        reason="duplicate",
                                    )
                    except Exception as e:
                        logger.error(
                            f"Error handling invoice refund on trial end: {e}"
                            )

            paid_until = ""
            if current_period_end := sub.get("current_period_end"):
                try:
                    paid_until = datetime.fromtimestamp(
                        int(current_period_end),
                        tz=timezone.utc
                    ).isoformat()
                except Exception:
                    pass

            if customer_id:
                try:
                    table_client = get_users_table_client()

                    # DO NOT USE list_entities(). Use an OData query filter to let Azure do the work.
                    filter_query = f"RowKey eq 'profile' and stripe_customer_id eq '{customer_id}'"
                    matched_entities = table_client.query_entities(
                        query_filter=filter_query
                        )

                    for e in matched_entities:
                        uid = str(e.get("PartitionKey"))
                        entity = {
                            "PartitionKey": uid,
                            "RowKey": "profile",
                            "plan_status": str(status or ""),
                            "is_paid": bool(
                                _stripe_subscription_grants_access(sub)
                                )
                        }
                        if paid_until:
                            entity["paid_until"] = paid_until
                        if subscription_id:
                            # If canceled, clear the subscription ID so the frontend doesn't hang onto it
                            if status in ("canceled", "unpaid"):
                                entity["stripe_subscription_id"] = ""
                            else:
                                entity["stripe_subscription_id"] = str(
                                    subscription_id
                                    )

                        table_client.upsert_entity(
                            entity,
                            mode=UpdateMode.MERGE
                            )
                        break
                except Exception as e:
                    logger.error(
                        f"stripe_webhook subscription sync error: {str(e)}"
                        )

        return ("OK", 200)
    except Exception as e:
        logger.error(f"stripe_webhook error: {str(e)}")
        return ("Error", 500)


@app.route("/billing/portal")
@login_required
def billing_portal():
    """Send the logged-in user to Stripe Customer Portal so they can cancel/manage their plan."""
    if not _stripe_enabled():
        flash("Billing portal is not configured.", "danger")
        return redirect(url_for("plans"))

    customer_id = _get_stripe_customer_id_from_azure(
        getattr(current_user, 'id', '')
    )
    if not customer_id:
        flash(
            "We couldn't find your billing profile yet. If you just purchased, refresh and try again.",
            "danger"
        )
        return redirect(url_for("my_revisions"))

    try:
        return_url = url_for(
            "my_revisions",
            _external=True,
            _scheme=request.scheme
        )
        session_obj = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return redirect(session_obj.url, code=303)
    except Exception as e:
        logger.error(f"billing_portal error: {str(e)}")
        flash("Unable to open billing portal. Please try again.", "danger")
        return redirect(url_for("my_revisions"))


CANCELLATION_FEEDBACK_FILE = "cancellation_feedback.json"


def _append_cancellation_feedback(
        user_id: str,
        subscription_id: str,
        reason: str,
        reason_other: str,
        email: str = ""
) -> None:
    """Append cancellation reason to feedback file (best-effort)."""
    try:
        records = []
        if os.path.exists(CANCELLATION_FEEDBACK_FILE):
            with open(
                    CANCELLATION_FEEDBACK_FILE,
                    "r",
                    encoding="utf-8"
            ) as f:
                data = json.load(f)
                records = list(data.get("records") or [])
        records.append(
            {
                "user_id": str(user_id or ""),
                "subscription_id": str(subscription_id or ""),
                "reason": str(reason or ""),
                "reason_other": str(reason_other or ""),
                "email": str(email or ""),
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        with open(CANCELLATION_FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"records": records},
                f,
                indent=2,
                ensure_ascii=False
            )
    except Exception:
        pass


def _stripe_cancellation_details_from_reason(
        cancel_reason: str,
        cancel_reason_other: str,
        cancel_reason_label: str = ""
) -> Optional[dict]:
    """Return Stripe-native cancellation_details payload.

    Stripe expects:
      - feedback: a limited enum
      - comment: free text

    We map internal UI values to the closest Stripe enum and fall back to 'other'.
    """
    reason = str(cancel_reason or "").strip().lower()
    other = str(cancel_reason_other or "").strip()
    label = str(cancel_reason_label or "").strip()

    if not reason and not other and not label:
        return None

    # Stripe allowed values include (among others): too_expensive, missing_features,
    # switched_service, unused, other.
    feedback_map = {
        "too_expensive": "too_expensive",
        "missing_features": "missing_features",
        "different_service": "switched_service",
        "not_using": "unused",
    }
    feedback = feedback_map.get(reason, "other")

    comment_parts: list[str] = []

    # Preserve the exact UI label text (if provided) so Stripe shows the precise wording.
    # For the "other" option, the label itself isn't very informative if free-text exists.
    if label and (reason != "other" or not other):
        comment_parts.append(label)

    # If our internal reason doesn't match Stripe's enum, preserve it in the comment.
    if reason and reason not in feedback_map and reason != "other":
        comment_parts.append(f"reason={reason}")
    if other:
        comment_parts.append(other)

    comment = " | ".join([p for p in comment_parts if p]).strip()
    if len(comment) > 500:
        comment = comment[:497] + "..."

    out: dict = {"feedback": feedback}
    if comment:
        out["comment"] = comment
    return out


def _stripe_cancellation_metadata_from_reason(
        cancel_reason: str,
        cancel_reason_other: str,
        cancel_reason_label: str = ""
) -> Optional[dict]:
    """Return subscription metadata fields to make cancellation reason visible in Stripe.

    Stripe Dashboard shows Subscription metadata prominently, while `cancellation_details.comment`
    is not always surfaced in the compact UI.
    """
    reason = str(cancel_reason or "").strip().lower()
    other = str(cancel_reason_other or "").strip()
    label = str(cancel_reason_label or "").strip()
    if not reason and not other and not label:
        return None

    # Keep keys short + stable.
    meta: dict[str, str] = {}
    if reason:
        meta["cancellation_reason"] = reason
    if label:
        meta["cancellation_reason_label"] = label
    if other:
        meta["cancellation_reason_other"] = other

    # Stripe metadata value limits are finite; keep within a safe bound.
    for k, v in list(meta.items()):
        s = str(v or "")
        if len(s) > 500:
            meta[k] = s[:497] + "..."

    return meta or None


@app.route("/billing/cancel")
@login_required
def billing_cancel_page():
    """Custom cancellation flow: show incentive modal, then cancel via API."""
    if not _stripe_enabled():
        flash("Billing is not configured.", "danger")
        return redirect(url_for("plans"))

    user_id = getattr(current_user, "id", "")
    prof = get_user_profile_azure(user_id) or {}
    reinstate_trial_bonus_used = bool(
        prof.get("reinstate_trial_bonus_used", False)
    )
    subscription_id = _get_stripe_subscription_id_from_azure(user_id)

    # Trial authorization hold (no subscription yet).
    if not subscription_id and _profile_has_active_trial_hold(prof):
        hold_days = _get_trial_hold_days()
        ends_display = ""
        ends_at = _parse_iso_dt(
            str(prof.get("trial_hold_ends_at") or "").strip()
        )
        if ends_at:
            try:
                ends_display = ends_at.astimezone(timezone.utc).strftime(
                    "%B %d, %Y"
                )
            except Exception:
                ends_display = "end of trial period"
        resp = make_response(
            render_template(
                "billing_cancel.html",
                subscription_id="",
                trial_hold_mode=True,
                interval_label=f"{hold_days}-Day Trial",
                period_end_display=ends_display or "end of trial period",
                cancel_scheduled=False,
                is_trialing=True,
                can_extend_trial_on_reinstate=False,
            )
        )
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        try:
            resp.headers["X-Resumatic-Build"] = str(_BUILD_ID)
        except Exception:
            pass
        return resp

    if not subscription_id:
        flash(
            "No active subscription found. If you just canceled, your access continues until the end of your billing period.",
            "info"
        )
        return redirect(url_for("settings_page"))

    # Fetch subscription details for display

    try:
        sub = stripe.Subscription.retrieve(
            subscription_id,
            expand=["items.data.price"]
        )
        status = str(
            _stripe_obj_get(sub, "status", "") or ""
        ).strip().lower()
        if status not in ("active", "trialing"):
            flash("Your subscription is not active.", "info")
            return redirect(url_for("settings_page"))
        cancel_scheduled = _stripe_subscription_cancel_scheduled(sub)

        current_period_end = _stripe_obj_get(
            sub,
            "current_period_end",
            None
        )
        period_end_display = ""
        if current_period_end:
            try:
                dt = datetime.fromtimestamp(
                    int(current_period_end),
                    tz=timezone.utc
                )
                period_end_display = dt.strftime("%B %d, %Y")
            except Exception:
                period_end_display = "end of billing period"

        interval_label = "Monthly"
        _, interval, interval_count = _get_subscription_price_id_and_recurring(
            sub
        )
        interval = str(interval or "").strip().lower()
        try:
            interval_count = int(interval_count or 1)
        except Exception:
            interval_count = 1
        if interval == "year" or (
                interval == "month" and interval_count == 12):
            interval_label = "Annual"
    except Exception as e:
        logger.exception(
            "billing_cancel_page subscription fetch failed: %s",
            str(e)
        )
        flash(
            "Unable to load subscription details. Please try again.",
            "danger"
        )
        return redirect(url_for("settings_page"))

    sub_metadata = _stripe_obj_get(sub, "metadata", {})

    use_trial_hold = _stripe_obj_get(sub_metadata, "use_trial_hold", "")

    sub_trial_mode = str(use_trial_hold).lower() in ["1", "true"]

    resp = make_response(
        render_template(
            "billing_cancel.html",
            subscription_id=subscription_id,
            interval_label=interval_label,
            period_end_display=period_end_display or "end of billing period",
            cancel_scheduled=bool(cancel_scheduled),
            is_trialing=(status == "trialing"),
            can_extend_trial_on_reinstate=(
                    status == "trialing" and not reinstate_trial_bonus_used),
            trial_hold_mode=sub_trial_mode,
        )
    )
    # Avoid showing stale/cached cancellation UI.
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"

    # Help verify which deployment is serving this page.
    try:
        resp.headers["X-Resumatic-Build"] = str(_BUILD_ID)
    except Exception:
        pass
    return resp

def _apply_retention_offer(subscription_id: str) -> tuple[bool, str]:
    """Apply retention offer: $5.48 off each of next 2 months (works with flexible billing).
    First credit now; second credit added via invoice.paid webhook."""

    sub = stripe.Subscription.retrieve(
        subscription_id,
        expand=["items.data.price"]
    )
    customer_id = str(getattr(sub, "customer", "") or "").strip()
    if not customer_id:
        return False, "Subscription has no customer."
    credit_cents = _compute_retention_credit_cents(sub)
    if credit_cents <= 0:
        return False, "Could not compute retention credit amount."
    currency = "usd"
    try:
        price = getattr(getattr(sub, "items", None), "data", []) or []
        if price:
            p = getattr(price[0], "price", None) if price else None
            if p:
                currency = str(getattr(p, "currency", "usd") or "usd")
    except Exception:
        pass
    stripe.Customer.create_balance_transaction(
        customer_id,
        amount=-credit_cents,
        currency=currency,
        description="Retention offer: 50% off month 1 of 2",
    )
    stripe.Customer.modify(
        customer_id,
        metadata={"retention_2nd_credit_cents": str(credit_cents)},
    )
    _stripe_subscription_modify(
        subscription_id,
        sub,
        cancel_at_period_end=False
    )
    return True, "50% off applied! Your next 2 months will be half price. You keep full access until your current period ends."


@app.route("/billing/apply-retention")
@login_required
def billing_apply_retention():
    """Apply the retention offer to the user's existing subscription. Preserves remaining time."""
    if not _stripe_enabled():
        flash("Billing is not configured.", "danger")
        return redirect(url_for("plans"))

    user_id = getattr(current_user, "id", "")
    subscription_id = _get_stripe_subscription_id_from_azure(user_id)
    if not subscription_id:
        flash("No active subscription found.", "danger")
        return redirect(url_for("settings_page"))

    try:
        success, msg = _apply_retention_offer(subscription_id)
        if success:
            flash(msg, "success")
            return redirect(url_for("settings_page"))
        flash(msg or "Unable to apply offer. Please try again.", "danger")
        return redirect(url_for("billing_cancel_page"))
    except stripe.error.InvalidRequestError as e:
        logger.warning(f"billing_apply_retention Stripe error: {str(e)}")
        flash(
            str(e.user_message) if getattr(
                e,
                "user_message",
                None
            ) else "Unable to apply offer. Please try again.",
            "danger"
        )
        return redirect(url_for("billing_cancel_page"))
    except Exception as e:
        logger.error(f"billing_apply_retention error: {str(e)}")
        flash("Unable to apply the offer. Please try again.", "danger")
        return redirect(url_for("billing_cancel_page"))


@app.route("/api/billing/apply-retention", methods=["POST"])
@login_required
def api_billing_apply_retention():
    """Apply retention offer via API. Returns JSON for use by fetch()."""
    if not _stripe_enabled():
        return jsonify(
            {"success": False, "error": "Billing is not configured."}
        ), 400

    user_id = getattr(current_user, "id", "")
    subscription_id = _get_stripe_subscription_id_from_azure(user_id)
    if not subscription_id:
        return jsonify(
            {"success": False, "error": "No active subscription found."}
        ), 404

    try:
        success, msg = _apply_retention_offer(subscription_id)
        if success:
            return jsonify(
                {
                    "success": True,
                    "message": msg,
                    "redirect_url": url_for("settings_page"),
                }
            )
        return jsonify(
            {"success": False,
             "error": msg or "Unable to apply offer. Please try again."}
        ), 400
    except stripe.error.InvalidRequestError as e:
        logger.warning(
            f"api_billing_apply_retention Stripe error: {str(e)}"
        )
        return jsonify(
            {
                "success": False,
                "error": str(e.user_message) if getattr(
                    e,
                    "user_message",
                    None
                ) else "Unable to apply offer. Please try again.",
            }
        ), 400
    except Exception as e:
        logger.error(f"api_billing_apply_retention error: {str(e)}")
        return jsonify(
            {"success": False,
             "error": "Unable to apply the offer. Please try again."}
        ), 500


@app.route("/api/billing/claim-trial-exit-offer", methods=["POST"])
@login_required
def api_claim_trial_exit_offer():
    """Claim the trial-checkout exit offer for a discounted first paid month."""
    user_id = str(getattr(current_user, "id", "") or "").strip()
    if not user_id:
        return jsonify(
            {"success": False, "error": "Authentication required."}
        ), 401

    target_cents = _get_trial_exit_offer_target_cents()
    try:
        table_client = get_users_table_client()
        entity = {
            "PartitionKey": user_id,
            "RowKey": "profile",
            "trial_exit_offer_active": "1",
            "trial_exit_offer_target_cents": str(target_cents),
            "trial_exit_offer_accepted_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }
        table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
    except Exception:
        logger.exception(
            "claim trial exit offer: failed to persist profile flag"
        )
        return jsonify(
            {"success": False,
             "error": "Unable to save the offer right now."}
        ), 500

    return jsonify(
        {
            "success": True,
            "target_price_cents": target_cents,
            "message": f"Offer applied: if you keep the {_get_trial_hold_days()}-day trial, your first paid month will be ${target_cents / 100:.2f}.",
        }
    )

@app.route("/api/billing/cancel", methods=["POST"])
@login_required
def api_billing_cancel():
    """Cancel subscription via Stripe API. Called after user confirms in custom modal."""
    if not _stripe_enabled():
        return jsonify({"error": "Billing not configured"}), 400

    user_id = getattr(current_user, "id", "")
    prof = get_user_profile_azure(user_id) or {}
    subscription_id = _get_stripe_subscription_id_from_azure(user_id)

    # Cancel trial authorization hold (legacy profile without Stripe subscription).
    if not subscription_id and _profile_has_active_trial_hold(prof):
        data = request.get_json(silent=True) or {}
        cancel_reason = str(data.get("cancel_reason") or "").strip()
        cancel_reason_other = str(
            data.get("cancel_reason_other") or ""
        ).strip()
        pi_id = _get_active_trial_authorization_payment_intent(prof)
        if pi_id:
            _cancel_trial_hold_payment_intent(pi_id)
        _revoke_trial_hold_profile(str(user_id), cancelled=True)
        if cancel_reason or cancel_reason_other:
            try:
                email = str(getattr(current_user, "email", "") or "")
                _append_cancellation_feedback(
                    str(user_id),
                    pi_id or "trial_hold",
                    cancel_reason,
                    cancel_reason_other,
                    email
                )
            except Exception:
                pass
        cta_email_sent = False
        try:
            email = str(
                getattr(current_user, "email", "") or ""
            ).strip().lower()
            name = str(getattr(current_user, "name", "") or "").strip()
            if email:
                cta_email_sent = bool(
                    send_trial_cancellation_reinstate_email(
                        email=email,
                        user_name=name,
                        include_trial_bonus=(not bool(
                            prof.get("reinstate_trial_bonus_used", False)
                        )),
                    )
                )
        except Exception:
            logger.exception("trial hold cancel CTA email failed")
        return jsonify(
            {
                "success": True,
                "cancel_at_period_end": False,
                "trial_hold_cancelled": True,
                "message": "Your trial has been canceled. The card authorization hold will expire automatically.",
                "cta_email_sent": bool(cta_email_sent),
            }
        )

    if not subscription_id:
        return jsonify({"error": "No active subscription found"}), 404

    data = request.get_json(silent=True) or {}
    cancel_at_period_end = data.get("cancel_at_period_end", True)
    cancel_reason = str(data.get("cancel_reason") or "").strip()
    cancel_reason_other = str(
        data.get("cancel_reason_other") or ""
    ).strip()
    cancel_reason_label = str(
        data.get("cancel_reason_label") or ""
    ).strip()
    cancellation_details = _stripe_cancellation_details_from_reason(
        cancel_reason,
        cancel_reason_other,
        cancel_reason_label
    )
    cancellation_metadata = _stripe_cancellation_metadata_from_reason(
        cancel_reason,
        cancel_reason_other,
        cancel_reason_label
    )

    try:
        # Snapshot current subscription status before applying cancellation.
        is_trialing_before_cancel = False
        cta_skip_reason = ""
        paid_cancel_email_attempted = False
        paid_cancel_email_sent = False
        paid_cancel_email_skip_reason = ""
        try:
            sub_before = stripe.Subscription.retrieve(
                subscription_id,
                expand=["items.data.price"]
            )
            status_before = str(
                _stripe_obj_get(sub_before, "status", "") or ""
            ).strip().lower()
            is_trialing_before_cancel = (status_before == "trialing")
        except Exception:
            is_trialing_before_cancel = False
        prof = get_user_profile_azure(user_id) or {}
        reinstate_trial_bonus_used = bool(
            prof.get("reinstate_trial_bonus_used", False)
        )
        paid_cancel_email_eligibility = _stripe_cancellation_paid_history_flags(
            subscription_id
        )
        if not bool(paid_cancel_email_eligibility.get("eligible", False)):
            paid_cancel_email_skip_reason = str(
                paid_cancel_email_eligibility.get(
                    "reason"
                ) or "not_eligible"
            )
        if not is_trialing_before_cancel:
            # Fallback: profile plan status can lag/lead Stripe in edge cases.
            plan_status_prof = str(
                prof.get("plan_status") or ""
            ).strip().lower()
            if plan_status_prof in ("trial", "trialing", "trial_7d"):
                is_trialing_before_cancel = True

        if cancel_at_period_end:
            cta_email_attempted = False
            cta_email_sent = False
            trial_hold_refunded = False
            trial_hold_released = False
            # Best-effort: include cancellation reason so it shows in Stripe.
            try:
                modify_params: dict = {"cancel_at_period_end": True}
                if cancellation_details:
                    modify_params[
                        "cancellation_details"] = cancellation_details
                if cancellation_metadata:
                    modify_params["metadata"] = cancellation_metadata
                _stripe_subscription_modify(
                    subscription_id,
                    sub_before,
                    **modify_params
                )
            except stripe.error.InvalidRequestError as e:
                # If Stripe rejects cancellation_details for any reason, retry without it so
                # the cancellation still succeeds.
                if cancellation_details:
                    logger.warning(
                        "billing_cancel: cancellation_details rejected by Stripe; retrying without. err=%s",
                        str(e),
                    )
                    retry_params: dict = {"cancel_at_period_end": True}
                    if cancellation_metadata:
                        retry_params["metadata"] = cancellation_metadata
                    _stripe_subscription_modify(
                        subscription_id,
                        sub_before,
                        **retry_params
                    )
                else:
                    raise
            if cancel_reason or cancel_reason_other:
                try:
                    email = str(getattr(current_user, "email", "") or "")
                    logger.info(
                        "billing_cancel reason user_id=%s subscription_id=%s reason=%s other=%s",
                        user_id,
                        subscription_id,
                        cancel_reason,
                        cancel_reason_other,
                    )
                    _append_cancellation_feedback(
                        user_id,
                        subscription_id,
                        cancel_reason,
                        cancel_reason_other,
                        email
                    )
                except Exception as e:
                    logger.warning(
                        "billing_cancel feedback save failed: %s",
                        str(e)
                    )
            # Trial-specific CTA: release authorization hold, refund final-day capture, or refund legacy deposit.
            if is_trialing_before_cancel:
                try:
                    hold_pi = _get_active_trial_authorization_payment_intent(
                        prof,
                        subscription_id
                    )
                    if hold_pi and sub_before:
                        if _subscription_authorization_hold_captured(
                                sub_before
                        ):
                            if _trial_cancel_eligible_for_capture_refund(
                                    prof,
                                    sub_before
                            ):
                                refunded_ok, refund_reason = _refund_trial_authorization_capture_for_subscription(
                                    sub_before
                                )
                                trial_hold_refunded = bool(refunded_ok)
                                logger.info(
                                    "billing_cancel trial_hold_refund user_id=%s subscription_id=%s ok=%s reason=%s",
                                    user_id,
                                    subscription_id,
                                    bool(refunded_ok),
                                    refund_reason or "ok",
                                )
                        else:
                            released_ok, release_reason = _release_authorization_hold_for_subscription(
                                sub_before
                            )
                            trial_hold_released = bool(released_ok)
                            logger.info(
                                "billing_cancel trial_hold_release user_id=%s subscription_id=%s ok=%s reason=%s",
                                user_id,
                                subscription_id,
                                bool(released_ok),
                                release_reason or "ok",
                            )
                        _revoke_trial_hold_profile(
                            str(user_id),
                            cancelled=True
                        )
                    else:
                        refunded_ok, refund_reason = _refund_trial_deposit_for_subscription(
                            subscription_id
                        )
                        logger.info(
                            "billing_cancel trial_deposit_refund user_id=%s subscription_id=%s ok=%s reason=%s",
                            user_id,
                            subscription_id,
                            bool(refunded_ok),
                            refund_reason or "ok",
                        )
                except Exception:
                    logger.exception(
                        "billing_cancel trial hold/deposit release failed"
                    )
                try:
                    cta_email_attempted = True
                    email = str(
                        getattr(current_user, "email", "") or ""
                    ).strip().lower()
                    if not email:
                        email = str(
                            prof.get("email") or ""
                        ).strip().lower()
                    name = str(
                        getattr(current_user, "name", "") or ""
                    ).strip()
                    if not email:
                        cta_skip_reason = "missing_email"
                        sent_ok = False
                    else:
                        sent_ok = bool(
                            send_trial_cancellation_reinstate_email(
                                email=email,
                                user_name=name,
                                include_trial_bonus=(
                                    not reinstate_trial_bonus_used),
                            )
                        )
                    cta_email_sent = bool(sent_ok)
                    if (not sent_ok) and (not cta_skip_reason):
                        cta_skip_reason = "smtp_failed_or_rejected"
                    logger.info(
                        "billing_cancel trial_cta user_id=%s attempted=%s sent=%s reason=%s email=%s",
                        user_id,
                        bool(cta_email_attempted),
                        bool(cta_email_sent),
                        cta_skip_reason or "ok",
                        email or "",
                    )
                    try:
                        table_client = get_users_table_client()
                        prev_count_raw = prof.get(
                            "trial_reinstate_cta_sent_count",
                            0
                        )
                        try:
                            prev_count = int(prev_count_raw or 0)
                        except Exception:
                            prev_count = 0
                        entity = {
                            "PartitionKey": str(user_id),
                            "RowKey": "profile",
                            "trial_reinstate_cta_last_attempt_at": datetime.now(
                                timezone.utc
                            ).isoformat(),
                            "trial_reinstate_cta_last_attempt_ok": bool(
                                sent_ok
                            ),
                            "trial_reinstate_cta_sent_count": (
                                    prev_count + 1) if sent_ok else prev_count,
                        }
                        if sent_ok:
                            entity["trial_reinstate_cta_last_sent_at"] = \
                                entity[
                                    "trial_reinstate_cta_last_attempt_at"]
                        table_client.upsert_entity(
                            entity,
                            mode=UpdateMode.MERGE
                        )
                    except Exception:
                        logger.exception(
                            "Failed to persist trial reinstatement CTA email audit fields"
                        )
                except Exception:
                    cta_skip_reason = "exception_during_send"
                    logger.exception(
                        "Failed to send trial reinstatement CTA email"
                    )
            else:
                cta_skip_reason = "not_trialing"

            # Paid-customer CTA: only if user has real paid history and latest paid invoice > 0.
            if bool(paid_cancel_email_eligibility.get("eligible", False)):
                try:
                    paid_cancel_email_attempted = True
                    email = str(
                        getattr(current_user, "email", "") or ""
                    ).strip().lower()
                    if not email:
                        email = str(
                            prof.get("email") or ""
                        ).strip().lower()
                    name = str(
                        getattr(current_user, "name", "") or ""
                    ).strip()
                    if not email:
                        paid_cancel_email_skip_reason = "missing_email"
                        sent_ok = False
                    else:
                        sent_ok = bool(
                            send_paid_cancellation_reinstate_email(
                                email=email,
                                user_name=name,
                                user_id=str(user_id or ""),
                                subscription_id=str(subscription_id or ""),
                            )
                        )
                    paid_cancel_email_sent = bool(sent_ok)
                    if (not sent_ok) and (
                            not paid_cancel_email_skip_reason):
                        paid_cancel_email_skip_reason = "smtp_failed_or_rejected"
                    logger.info(
                        "billing_cancel paid_cta user_id=%s attempted=%s sent=%s reason=%s email=%s",
                        user_id,
                        bool(paid_cancel_email_attempted),
                        bool(paid_cancel_email_sent),
                        paid_cancel_email_skip_reason or "ok",
                        email or "",
                    )
                    try:
                        table_client = get_users_table_client()
                        prev_count_raw = prof.get(
                            "paid_reinstate_offer_email_sent_count",
                            0
                        )
                        try:
                            prev_count = int(prev_count_raw or 0)
                        except Exception:
                            prev_count = 0
                        now_iso = datetime.now(timezone.utc).isoformat()
                        entity = {
                            "PartitionKey": str(user_id),
                            "RowKey": "profile",
                            "paid_reinstate_offer_email_last_attempt_at": now_iso,
                            "paid_reinstate_offer_email_last_attempt_ok": bool(
                                sent_ok
                            ),
                            "paid_reinstate_offer_email_sent_count": (
                                    prev_count + 1) if sent_ok else prev_count,
                        }
                        if sent_ok:
                            entity[
                                "paid_reinstate_offer_email_last_sent_at"] = now_iso
                        table_client.upsert_entity(
                            entity,
                            mode=UpdateMode.MERGE
                        )
                    except Exception:
                        logger.exception(
                            "Failed to persist paid reinstatement offer email audit fields"
                        )
                except Exception:
                    paid_cancel_email_skip_reason = "exception_during_send"
                    logger.exception(
                        "Failed to send paid cancellation CTA email"
                    )
            cancel_message = "Your subscription will cancel at the end of your billing period. You'll keep access until then."
            if trial_hold_refunded:
                cancel_message = "Your trial has been canceled and your recent charge has been refunded."
            elif trial_hold_released:
                cancel_message = "Your trial has been canceled. The card authorization hold has been released."
            return jsonify(
                {
                    "success": True,
                    "cancel_at_period_end": True,
                    "message": cancel_message,
                    "trial_hold_refunded": bool(trial_hold_refunded),
                    "trial_hold_released": bool(trial_hold_released),
                    "cta_email_attempted": bool(cta_email_attempted),
                    "cta_email_sent": bool(cta_email_sent),
                    "cta_skip_reason": cta_skip_reason or "",
                    "paid_cancel_email_attempted": bool(
                        paid_cancel_email_attempted
                    ),
                    "paid_cancel_email_sent": bool(paid_cancel_email_sent),
                    "paid_cancel_email_skip_reason": paid_cancel_email_skip_reason or "",
                }
            )
        else:
            trial_hold_refunded = False
            trial_hold_released = False
            if is_trialing_before_cancel and sub_before:
                try:
                    hold_pi = _get_active_trial_authorization_payment_intent(
                        prof,
                        subscription_id
                    )
                    if hold_pi:
                        if _subscription_authorization_hold_captured(
                                sub_before
                        ):
                            if _trial_cancel_eligible_for_capture_refund(
                                    prof,
                                    sub_before
                            ):
                                refunded_ok, refund_reason = _refund_trial_authorization_capture_for_subscription(
                                    sub_before
                                )
                                trial_hold_refunded = bool(refunded_ok)
                        else:
                            released_ok, release_reason = _release_authorization_hold_for_subscription(
                                sub_before
                            )
                            trial_hold_released = bool(released_ok)
                        _revoke_trial_hold_profile(
                            str(user_id),
                            cancelled=True
                        )
                except Exception:
                    logger.exception(
                        "billing_cancel(immediate) trial hold release/refund failed"
                    )

            # --- START FIX: IMMEDIATE CANCEL REWRITE ---
            # 1. Attach metadata to the active subscription first.
            if cancellation_metadata:
                try:
                    stripe.Subscription.modify(
                        subscription_id,
                        metadata=cancellation_metadata
                    )
                except Exception as e:
                    logger.warning(
                        "billing_cancel: unable to attach cancellation metadata before delete: %s",
                        str(e),
                    )

            # 2. Pass cancellation_details strictly to the delete method.
            delete_kwargs = {}
            if cancellation_details:
                delete_kwargs[
                    "cancellation_details"] = cancellation_details

            stripe.Subscription.delete(
                subscription_id,
                **delete_kwargs
            )

            # 3. Database Cleanup (Orphaned ID Fix):
            # Tell Azure right now that the subscription is gone to fix the settings UI bug.
            try:
                table_client = get_users_table_client()
                entity = {
                    "PartitionKey": str(user_id),
                    "RowKey": "profile",
                    "stripe_subscription_id": "",  # Clear the ID
                    "plan_status": "free",
                    # Force the local status to free
                    "is_paid": False  # Remove paid status immediately
                }
                table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
            except Exception as e:
                logger.error(
                    f"billing_cancel: Failed to clear subscription ID from profile: {str(e)}"
                    )
            # --- END FIX ---

            if cancel_reason or cancel_reason_other:
                try:
                    email = str(getattr(current_user, "email", "") or "")
                    logger.info(
                        "billing_cancel(immediate) reason user_id=%s subscription_id=%s reason=%s other=%s",
                        user_id,
                        subscription_id,
                        cancel_reason,
                        cancel_reason_other,
                    )
                    _append_cancellation_feedback(
                        user_id,
                        subscription_id,
                        cancel_reason,
                        cancel_reason_other,
                        email
                    )
                except Exception as e:
                    logger.warning(
                        "billing_cancel(immediate) feedback save failed: %s",
                        str(e)
                    )

            if bool(paid_cancel_email_eligibility.get("eligible", False)):
                try:
                    paid_cancel_email_attempted = True
                    email = str(
                        getattr(current_user, "email", "") or ""
                    ).strip().lower()
                    if not email:
                        email = str(
                            prof.get("email") or ""
                        ).strip().lower()
                    name = str(
                        getattr(current_user, "name", "") or ""
                    ).strip()
                    if not email:
                        paid_cancel_email_skip_reason = "missing_email"
                        sent_ok = False
                    else:
                        sent_ok = bool(
                            send_paid_cancellation_reinstate_email(
                                email=email,
                                user_name=name,
                                user_id=str(user_id or ""),
                                subscription_id=str(subscription_id or ""),
                            )
                        )
                    paid_cancel_email_sent = bool(sent_ok)
                    if (not sent_ok) and (
                            not paid_cancel_email_skip_reason):
                        paid_cancel_email_skip_reason = "smtp_failed_or_rejected"
                    logger.info(
                        "billing_cancel(immediate) paid_cta user_id=%s attempted=%s sent=%s reason=%s email=%s",
                        user_id,
                        bool(paid_cancel_email_attempted),
                        bool(paid_cancel_email_sent),
                        paid_cancel_email_skip_reason or "ok",
                        email or "",
                    )
                    try:
                        table_client = get_users_table_client()
                        prev_count_raw = prof.get(
                            "paid_reinstate_offer_email_sent_count",
                            0
                        )
                        try:
                            prev_count = int(prev_count_raw or 0)
                        except Exception:
                            prev_count = 0
                        now_iso = datetime.now(timezone.utc).isoformat()
                        entity = {
                            "PartitionKey": str(user_id),
                            "RowKey": "profile",
                            "paid_reinstate_offer_email_last_attempt_at": now_iso,
                            "paid_reinstate_offer_email_last_attempt_ok": bool(
                                sent_ok
                            ),
                            "paid_reinstate_offer_email_sent_count": (
                                    prev_count + 1) if sent_ok else prev_count,
                        }
                        if sent_ok:
                            entity[
                                "paid_reinstate_offer_email_last_sent_at"] = now_iso
                        table_client.upsert_entity(
                            entity,
                            mode=UpdateMode.MERGE
                        )
                    except Exception:
                        logger.exception(
                            "Failed to persist paid reinstatement offer email audit fields (immediate)"
                        )
                except Exception:
                    paid_cancel_email_skip_reason = "exception_during_send"
                    logger.exception(
                        "Failed to send paid cancellation CTA email (immediate)"
                    )
            immediate_message = "Your subscription has been canceled."
            if trial_hold_refunded:
                immediate_message = "Your trial has been canceled and your recent charge has been refunded."
            elif trial_hold_released:
                immediate_message = "Your trial has been canceled. The card authorization hold has been released."
            return jsonify(
                {
                    "success": True,
                    "cancel_at_period_end": False,
                    "message": immediate_message,
                    "trial_hold_refunded": bool(trial_hold_refunded),
                    "trial_hold_released": bool(trial_hold_released),
                    "paid_cancel_email_attempted": bool(
                        paid_cancel_email_attempted
                    ),
                    "paid_cancel_email_sent": bool(paid_cancel_email_sent),
                    "paid_cancel_email_skip_reason": paid_cancel_email_skip_reason or "",
                }
            )
    except stripe.error.InvalidRequestError as e:
        logger.warning(f"api_billing_cancel Stripe error: {str(e)}")
        return jsonify(
            {"error": str(e.user_message) if getattr(
                e,
                "user_message",
                None
            ) else "Invalid request"}
        ), 400
    except Exception as e:
        logger.error(f"api_billing_cancel error: {str(e)}")
        return jsonify(
            {"error": "Unable to cancel subscription. Please try again."}
        ), 500


@app.route("/api/billing/reinstate", methods=["POST"])
@login_required
def api_billing_reinstate():
    """Reinstate a scheduled-for-cancel subscription and extend trial by 2 weeks."""
    if not _stripe_enabled():
        return jsonify(
            {"success": False, "error": "Billing is not configured."}
        ), 400

    user_id = getattr(current_user, "id", "")
    prof = get_user_profile_azure(user_id) or {}
    reinstate_trial_bonus_used = bool(
        prof.get("reinstate_trial_bonus_used", False)
    )
    data = request.get_json(silent=True) or {}
    apply_offer_399 = bool(data.get("apply_offer_399", False))
    subscription_id = _get_stripe_subscription_id_from_azure(user_id)
    if not subscription_id:
        return jsonify(
            {"success": False, "error": "No active subscription found."}
        ), 404

    try:
        if apply_offer_399:
            result = _reinstate_paid_offer_subscription(
                str(user_id or ''),
                subscription_id
            )
            if result.get('ok'):
                if result.get('offer_applied'):
                    try:
                        table_client = get_users_table_client()
                        prev_apply_raw = prof.get(
                            "paid_reinstate_offer_apply_count",
                            0
                        )
                        try:
                            prev_apply = int(prev_apply_raw or 0)
                        except Exception:
                            prev_apply = 0
                        now_iso = datetime.now(timezone.utc).isoformat()
                        table_client.upsert_entity(
                            {
                                "PartitionKey": str(user_id),
                                "RowKey": "profile",
                                "paid_reinstate_offer_apply_count": prev_apply + 1,
                                "paid_reinstate_offer_last_applied_at": now_iso,
                            }, mode=UpdateMode.MERGE
                        )
                    except Exception:
                        logger.exception(
                            "Failed to persist paid reinstatement offer apply audit fields"
                        )
                return jsonify(
                    {
                        "success": True,
                        "message": str(
                            result.get(
                                'message'
                            ) or 'Subscription reinstated successfully.'
                        ),
                        "offer_399_applied": bool(
                            result.get('offer_applied')
                        ),
                        "offer_399_message": str(
                            result.get('message') or ''
                        ),
                        "redirect_url": str(
                            result.get('redirect_url') or url_for(
                                "settings_page"
                            )
                        ),
                    }
                )
            return jsonify(
                {
                    "success": False,
                    "error": str(
                        result.get(
                            'message'
                        ) or 'Unable to reinstate subscription. Please try again.'
                    ),
                    "redirect_url": str(result.get('redirect_url') or ''),
                }
            ), 400

        sub = stripe.Subscription.retrieve(
            subscription_id,
            expand=["items.data.price"]
        )
        status = str(
            _stripe_obj_get(sub, "status", "") or ""
        ).strip().lower()
        if status not in ("active", "trialing"):
            return jsonify(
                {"success": False,
                 "error": "Your subscription is not active."}
            ), 400

        modify_params: dict = {"cancel_at_period_end": False}
        extended_trial = False
        if status == "trialing" and (not reinstate_trial_bonus_used):
            trial_end = _stripe_obj_get(sub, "trial_end", None)
            try:
                if trial_end:
                    trial_end_ts = int(trial_end)
                    now_ts = int(datetime.now(timezone.utc).timestamp())
                    base_ts = max(trial_end_ts, now_ts)
                    # Extend trial by 14 days from the later of current trial_end and now.
                    modify_params["trial_end"] = int(
                        base_ts + (14 * 24 * 60 * 60)
                    )
                    extended_trial = True
            except Exception:
                pass

        _stripe_subscription_modify(subscription_id, sub, **modify_params)

        offer_applied = False
        offer_message = ""
        if apply_offer_399:
            offer_ok, offer_msg, _ = _apply_reinstate_next_month_price_offer(
                sub,
                target_price_cents=399
            )
            offer_applied = bool(offer_ok)
            offer_message = str(offer_msg or "")
            if offer_applied:
                try:
                    table_client = get_users_table_client()
                    prev_apply_raw = prof.get(
                        "paid_reinstate_offer_apply_count",
                        0
                    )
                    try:
                        prev_apply = int(prev_apply_raw or 0)
                    except Exception:
                        prev_apply = 0
                    now_iso = datetime.now(timezone.utc).isoformat()
                    table_client.upsert_entity(
                        {
                            "PartitionKey": str(user_id),
                            "RowKey": "profile",
                            "paid_reinstate_offer_apply_count": prev_apply + 1,
                            "paid_reinstate_offer_last_applied_at": now_iso,
                        }, mode=UpdateMode.MERGE
                    )
                except Exception:
                    logger.exception(
                        "Failed to persist paid reinstatement offer apply audit fields"
                    )
        if extended_trial:
            try:
                table_client = get_users_table_client()
                table_client.upsert_entity(
                    {
                        "PartitionKey": str(user_id),
                        "RowKey": "profile",
                        "reinstate_trial_bonus_used": True,
                        "reinstate_trial_bonus_used_at": datetime.now(
                            timezone.utc
                        ).isoformat(),
                    }, mode=UpdateMode.MERGE
                )
            except Exception:
                pass
        # Track reinstatement events and CTA conversion (best-effort).
        try:
            table_client = get_users_table_client()
            prof_after = get_user_profile_azure(user_id) or {}
            prev_reinstate_raw = prof_after.get(
                "trial_reinstate_conversion_count",
                0
            )
            prev_cta_sent_raw = prof_after.get(
                "trial_reinstate_cta_sent_count",
                0
            )
            try:
                prev_reinstate_count = int(prev_reinstate_raw or 0)
            except Exception:
                prev_reinstate_count = 0
            try:
                prev_cta_sent_count = int(prev_cta_sent_raw or 0)
            except Exception:
                prev_cta_sent_count = 0
            now_iso = datetime.now(timezone.utc).isoformat()
            audit_patch = {
                "PartitionKey": str(user_id),
                "RowKey": "profile",
                "trial_reinstate_conversion_count": prev_reinstate_count + 1,
                "trial_reinstate_last_converted_at": now_iso,
            }
            # Mark as converted-from-CTA when at least one CTA email was sent before.
            if prev_cta_sent_count > 0:
                audit_patch["trial_reinstate_cta_converted"] = True
                if not str(
                        prof_after.get(
                            "trial_reinstate_cta_converted_at"
                        ) or ""
                ).strip():
                    audit_patch[
                        "trial_reinstate_cta_converted_at"] = now_iso
            table_client.upsert_entity(audit_patch, mode=UpdateMode.MERGE)
        except Exception:
            logger.exception(
                "Failed to persist trial reinstatement conversion audit fields"
            )
        msg = "Subscription reinstated successfully."
        if extended_trial:
            msg = "Subscription reinstated successfully. We added 2 weeks to your trial."
        if offer_message:
            msg = f"{msg} {offer_message}".strip()
        return jsonify(
            {
                "success": True,
                "message": msg,
                "offer_399_applied": bool(offer_applied),
                "offer_399_message": offer_message,
                "redirect_url": url_for("settings_page"),
            }
        )
    except stripe.error.InvalidRequestError as e:
        logger.warning(f"api_billing_reinstate Stripe error: {str(e)}")
        return jsonify(
            {
                "success": False,
                "error": str(e.user_message) if getattr(
                    e,
                    "user_message",
                    None
                ) else "Unable to reinstate subscription. Please try again.",
            }
        ), 400
    except Exception as e:
        logger.error(f"api_billing_reinstate error: {str(e)}")
        return jsonify(
            {"success": False,
             "error": "Unable to reinstate subscription. Please try again."}
        ), 500


@app.route("/billing/reinstate-paid-offer")
def billing_reinstate_paid_offer():
    """One-click reinstatement from email with $3.99 next-month offer."""
    if not _stripe_enabled():
        flash("Billing is not configured.", "danger")
        return redirect(url_for("plans"))

    token_arg = str(request.args.get("token") or "").strip()
    if token_arg:
        _store_reinstate_paid_offer_token_in_session(token_arg)

    if not getattr(current_user, "is_authenticated", False):
        return redirect(
            url_for("login", next=url_for("billing_reinstate_paid_offer"))
        )

    token = token_arg or str(
        session.get(_REINSTATE_OFFER_SESSION_KEY) or ""
    ).strip()
    if not token:
        flash("This offer link is invalid.", "danger")
        return redirect(url_for("settings_page"))

    payload = confirm_reinstate_paid_offer_token(token)
    if not payload:
        session.pop(_REINSTATE_OFFER_SESSION_KEY, None)
        flash("This offer link is invalid or has expired.", "danger")
        return redirect(url_for("settings_page"))
    session.pop(_REINSTATE_OFFER_SESSION_KEY, None)

    user_id = str(getattr(current_user, "id", "") or "").strip()
    token_user_id = str(payload.get("user_id") or "").strip()
    if not user_id or (token_user_id and token_user_id != user_id):
        flash("This offer link does not match your account.", "danger")
        return redirect(url_for("settings_page"))

    subscription_id, resolve_err = _resolve_reinstate_offer_subscription_id(
        user_id,
        token_subscription_id=str(
            payload.get("subscription_id") or ""
        ).strip(),
        email=str(
            payload.get("email") or getattr(
                current_user,
                "email",
                ""
            ) or ""
        ).strip(),
    )
    if resolve_err:
        flash(resolve_err, "danger")
        return redirect(url_for("settings_page"))
    if not subscription_id:
        flash("No subscription found to reinstate.", "danger")
        return redirect(url_for("settings_page"))

    try:
        table_client = get_users_table_client()
        prof = get_user_profile_azure(user_id) or {}
        prev_click_raw = prof.get("paid_reinstate_offer_click_count", 0)
        try:
            prev_click = int(prev_click_raw or 0)
        except Exception:
            prev_click = 0
        table_client.upsert_entity(
            {
                "PartitionKey": str(user_id),
                "RowKey": "profile",
                "paid_reinstate_offer_click_count": prev_click + 1,
                "paid_reinstate_offer_last_clicked_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }, mode=UpdateMode.MERGE
        )
    except Exception:
        logger.exception(
            "Failed to persist paid reinstatement offer click audit fields"
        )

    try:
        result = _reinstate_paid_offer_subscription(
            user_id,
            subscription_id
        )
        if result.get('offer_applied'):
            try:
                table_client = get_users_table_client()
                prof = get_user_profile_azure(user_id) or {}
                prev_apply_raw = prof.get(
                    "paid_reinstate_offer_apply_count",
                    0
                )
                try:
                    prev_apply = int(prev_apply_raw or 0)
                except Exception:
                    prev_apply = 0
                now_iso = datetime.now(timezone.utc).isoformat()
                table_client.upsert_entity(
                    {
                        "PartitionKey": str(user_id),
                        "RowKey": "profile",
                        "paid_reinstate_offer_apply_count": prev_apply + 1,
                        "paid_reinstate_offer_last_applied_at": now_iso,
                    }, mode=UpdateMode.MERGE
                )
            except Exception:
                logger.exception(
                    "Failed to persist paid reinstatement offer apply audit fields (link)"
                )

        if result.get('ok'):
            flash(
                str(result.get('message') or 'Subscription reinstated.'),
                "success"
            )
        else:
            flash(
                str(
                    result.get(
                        'message'
                    ) or 'Unable to reinstate subscription. Please try again.'
                ),
                "warning" if result.get('redirect_url') else "danger"
            )
        redirect_target = str(
            result.get('redirect_url') or url_for('settings_page')
        )
        return redirect(redirect_target)
    except stripe.error.InvalidRequestError as e:
        logger.warning(
            "billing_reinstate_paid_offer Stripe error: %s",
            str(e)
        )
        flash(
            str(e.user_message) if getattr(
                e,
                "user_message",
                None
            ) else "Unable to reinstate subscription. Please try again.",
            "danger"
        )
        return redirect(url_for("settings_page"))
    except Exception as e:
        logger.error("billing_reinstate_paid_offer error: %s", str(e))
        flash(
            "Unable to reinstate subscription. Please try again.",
            "danger"
        )
        return redirect(url_for("settings_page"))


@app.route("/results", methods=["POST"])
# login_required
def results_route():
    _safe_print("=== results_route called ===")
    _safe_log_event('results_route POST: start')
    try:
        resume_text = ""

        # Enforce free tier revision limit (1) for authenticated non-paid users.
        if current_user.is_authenticated and (
                not is_paid_user(current_user)):
            try:
                used = len(get_user_revisions(current_user.id))
                if used >= FREE_REVISION_LIMIT:
                    flash(
                        "Free tier includes 1 resume revision. Upgrade to unlock unlimited revisions and PDF downloads.",
                        "danger"
                    )
                    return redirect(url_for("plans", limit="1"))
            except Exception:
                # If counting fails, do not block.
                pass

        # Check if file was uploaded
        if 'resumeFile' in request.files:
            file = request.files['resumeFile']
            if file and file.filename:
                _safe_print(f"Processing uploaded file: {file.filename}")
                _safe_log_event(
                    f"results_route POST: received upload filename={secure_filename(file.filename)}"
                )
                try:
                    resume_text = extract_text_from_file(file)
                    _safe_print(
                        f"Extracted text length: {len(resume_text)}"
                    )
                    _safe_log_event(
                        f"results_route POST: extracted_text_len={len(resume_text)}"
                    )
                    if not resume_text or not resume_text.strip():
                        _safe_print(
                            "Uploaded file parsed but contained no extractable text"
                        )
                        _safe_log_event(
                            'results_route POST: extracted text empty'
                        )
                        return redirect(url_for('paste_resume', error='1'))
                except Exception as e:
                    _safe_log_exception('upload processing failed', e)
                    _safe_log_event(
                        'results_route POST: upload processing failed (see exception block above)'
                    )
                    return redirect(url_for('paste_resume', error='1'))

        # If no file uploaded, check for text input
        if not resume_text:
            resume_text = request.form.get("resume", "").strip()

        # Validate that we have resume content
        if not resume_text:
            flash(
                "Please upload a resume file or paste your resume content",
                'danger'
            )
            return redirect(url_for('index', scroll_to_form='true'))

        # Get job description (optional)
        job_description = request.form.get("jobDescription", "").strip()

        # Process the resume
        _safe_print(
            f"Resume text preview (first 200 chars): {resume_text[:200]}..."
        )
        _safe_print(
            f"Job description preview: {job_description[:100] if job_description else 'None'}..."
        )
        _safe_log_event(
            f"results_route POST: calling revise_resume resume_len={len(resume_text)} jd_len={len(job_description)}"
        )
        revised_resume, feedback = revise_resume(
            resume_text,
            job_description
        )
        _safe_log_event(
            f"results_route POST: revise_resume ok revised_len={len(revised_resume or '')}"
        )
        _safe_print("=== FEEDBACK DATA ===")
        _safe_print(f"Feedback type: {type(feedback)}")
        try:
            _safe_print(json.dumps(feedback, indent=2))
        except Exception:
            _safe_print("<feedback json dump failed>")

        # Save to user account if authenticated
        source_revision_id = None
        if current_user.is_authenticated:
            import uuid

            source_revision_id = str(uuid.uuid4())
            try:
                save_resume_revision(
                    current_user.id,
                    source_revision_id,
                    revised_resume,
                    feedback=feedback,
                    original_resume=resume_text,
                    job_description=job_description
                )
            except FreeTierLimitReached:
                # Still show results, but do not persist a new revision.
                flash(
                    "You've reached the free tier limit (1 revision). Upgrade to save unlimited revisions.",
                    "danger"
                )
                source_revision_id = None
            except Exception:
                source_revision_id = None
        else:
            # Store revision in session for post-signup saving
            session['pending_revision'] = {
                'revised_resume': revised_resume,
                'feedback': feedback,
                'original_resume': resume_text,
                'job_description': job_description
            }

        # Track conversion (resume submission)
        conversion_info = analytics.track_conversion(
            session,
            "resume_submission"
        )
        _safe_print(f"=== CONVERSION TRACKED ===")
        _safe_print(f"Conversion info: {conversion_info}")

        # Store data in session and redirect (Post/Redirect/Get) to prevent resubmission on back
        session['results_data'] = {
            'original_resume': resume_text,
            'revised_resume': revised_resume,
            'feedback': feedback,
            'job_description': job_description,
        }
        if source_revision_id:
            session['results_data'][
                'source_revision_id'] = source_revision_id
        # Ensure session persistence + clear stale template data (prevents old template snapshot confusion)
        session.pop('template_data', None)
        session.modified = True
        # Bust caches (browser/service worker) for /results
        import time

        _safe_log_event('results_route POST: redirecting to results_get')
        return redirect(url_for('results_get', ts=int(time.time())))
    except Exception as e:
        _safe_print("=== ERROR IN revise_resume_route ===")
        _safe_print(f"Error type: {type(e).__name__}")
        _safe_print(f"Error message: {str(e)}")
        _safe_log_exception('results_route error', e)
        _safe_log_event(
            'results_route POST: unhandled exception (see results_route error block above)'
        )
        _safe_print("=== END ERROR DEBUG ===")
        flash(f"Error: {str(e)}", 'danger')
        return redirect(url_for('index'))


@app.route("/results", methods=["GET"])
def results_get():
    _safe_log_event('results_get GET: start')
    data = session.get('results_data', None)
    if not data:
        _safe_log_event('results_get GET: no results_data in session')
        # No data to show; route the user to the paste-resume fallback.
        return redirect(url_for('paste_resume', error='1'))

    try:
        _safe_log_event(
            f"results_get GET: has results_data keys={','.join(sorted([str(k) for k in (data or {}).keys()]))}"
        )
    except Exception:
        _safe_log_event(
            'results_get GET: has results_data (keys unavailable)'
        )
    # Keep data in session for template selection
    # session.pop would remove it, so we use session.get and keep it available
    resp = make_response(
        render_template(
            "result.html",
            original_resume=data.get('original_resume', ''),
            revised_resume=data.get('revised_resume', ''),
            feedback=data.get('feedback', {}),
            job_description=data.get('job_description', ''),
            error=None
        )
    )
    # Transactional page: never cache (prevents showing a previous resume after a new submission)
    resp.headers[
        'Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    resp.headers['Vary'] = 'Cookie'
    return resp


def _canonical_template_id(raw: str) -> str:
    """Convert old/internal template IDs to the current canonical IDs used in UI + URLs.

    Canonical IDs:
    - professional, elegant, creative, boldProfessional, traditional, modern, executive

    Old IDs are kept as aliases for backward compatibility.
    """
    tid = str(raw or '').strip()
    if not tid:
        return 'professional'

    key = tid.lower()

    alias_to_canonical = {
        # Canonical
        'professional': 'professional',
        # "classic" is used in some parts of the UI as a generic label; map it to the maintained ClassicRose template.
        'classic': 'classicRose',
        'elegant': 'classicRose',
        'creative': 'creative2',
        'minimalsidebar': 'minimalSidebar',
        'boldprofessional': 'boldProfessional',
        'bold-professional': 'boldProfessional',
        'bold_professional': 'boldProfessional',
        'traditional': 'traditional',
        # UI label "Contemporary" uses this id in the resume builder carousel.
        'contemporary': 'traditional',
        'modern': 'modern',
        'executive': 'executive',
        # UI label "Stylish" uses this id in the resume builder carousel.
        'stylish': 'minimalSidebar',

        # Old IDs (and dash/underscore variants) -> canonical
        'lavenderclassic': 'classicRose',
        'lavender-classic': 'classicRose',
        'lavender_classic': 'classicRose',

        'popart': 'creative2',
        'pop-art': 'creative2',
        'pop_art': 'creative2',

        'creative2': 'creative2',
        'creative-2': 'creative2',
        'creative_2': 'creative2',

        'classicrose': 'classicRose',
        'classic-rose': 'classicRose',
        'classic_rose': 'classicRose',

        'orangeheader': 'boldProfessional',
        'orange-header': 'boldProfessional',
        'orange_header': 'boldProfessional',

        'bluelineclassic': 'traditional',
        'blue-line-classic': 'traditional',
        'blue_line_classic': 'traditional',

        'cleansidebar': 'modern',
        'clean-sidebar': 'modern',
        'clean_sidebar': 'modern',

        'timelineblue': 'executive',
        'timeline-blue': 'executive',
        'timeline_blue': 'executive',

        'minimal-sidebar': 'minimalSidebar',
        'minimal_sidebar': 'minimalSidebar',

        # Optional/experimental
        'minimal': 'minimal',
        'darksidebarprogress': 'darkSidebarProgress',
        'dark-sidebar-progress': 'darkSidebarProgress',
        'dark_sidebar_progress': 'darkSidebarProgress',
    }
    return alias_to_canonical.get(key, 'professional')


_KNOWN_TEMPLATE_IDS = [
    'professional',
    'elegant',
    'creative',
    'creative2',
    'classicRose',
    'boldProfessional',
    'traditional',
    'modern',
    'executive',
    'minimalSidebar',
    # Optional/experimental
    'minimal',
    'darkSidebarProgress',
]


def _format_template_display_name(raw: str) -> str:
    # Prefer canonical IDs to avoid UI labels drifting when aliases are stored.
    canonical = _canonical_template_id(str(raw or ''))
    display_overrides = {
        # UI labels
        'minimalSidebar': 'Stylish',
        'classicRose': 'Classic',
        'creative2': 'Creative',
        'boldProfessional': 'Bold Professional',
        'traditional': 'Contemporary',
    }
    if canonical in display_overrides:
        return display_overrides[canonical]

    s = str(canonical or raw or '')
    s = re.sub(r'[_-]+', ' ', s)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s)
    s = s.strip()
    if not s:
        return ''
    words = [w for w in re.split(r'\s+', s) if w]
    return ' '.join([w[:1].upper() + w[1:] for w in words])


def _template_snapshot_prop_names(template_id: str):
    tid = _canonical_template_id(template_id)
    # Property names should be simple and stable.
    suffix = re.sub(r'[^A-Za-z0-9]', '_', tid)
    return (
        f'template_structured_resume__{suffix}',
        f'template_structured_resume_gz_b64__{suffix}',
        f'template_saved_at__{suffix}',
    )


def _entity_get_ci(entity: dict, key: str, default=None):
    """Case-insensitive lookup for Azure Table entity properties.

    Some historical entities may have different casing for property names.
    """
    if not isinstance(entity, dict):
        return default
    if key in entity:
        return entity.get(key, default)
    want = str(key).lower()
    for k in entity.keys():
        if str(k).lower() == want:
            return entity.get(k, default)
    return default


def _load_structured_snapshot_for_template(entity: dict, template_id: str):
    """Load a persisted structured resume snapshot for a specific template.

    Returns a dict (structured_resume) or None if no snapshot exists.
    """
    tid = _canonical_template_id(template_id)
    plain_prop, gz_prop, _ = _template_snapshot_prop_names(tid)

    raw_snapshot = str(
        _entity_get_ci((entity or {}), plain_prop, '') or ''
    ).strip()
    raw_snapshot_gz_b64 = str(
        _entity_get_ci((entity or {}), gz_prop, '') or ''
    ).strip()

    # Backward compatibility: older saves stored only one snapshot on the revision entity.
    if not raw_snapshot and not raw_snapshot_gz_b64:
        legacy_tid = _canonical_template_id(
            str(
                _entity_get_ci((entity or {}), 'template_id', '') or ''
            ).strip() or 'professional'
        )
        if legacy_tid == tid:
            raw_snapshot = str(
                _entity_get_ci(
                    (entity or {}),
                    'template_structured_resume',
                    ''
                ) or ''
            ).strip()
            raw_snapshot_gz_b64 = str(
                _entity_get_ci(
                    (entity or {}),
                    'template_structured_resume_gz_b64',
                    ''
                ) or ''
            ).strip()

            # Extra legacy aliases (defensive): camelCase keys from older experiments.
            if not raw_snapshot:
                raw_snapshot = str(
                    _entity_get_ci(
                        (entity or {}),
                        'templateStructuredResume',
                        ''
                    ) or ''
                ).strip()
            if not raw_snapshot_gz_b64:
                raw_snapshot_gz_b64 = str(
                    _entity_get_ci(
                        (entity or {}),
                        'templateStructuredResumeGzB64',
                        ''
                    ) or ''
                ).strip()

    if raw_snapshot:
        try:
            obj = json.loads(raw_snapshot)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    if raw_snapshot_gz_b64:
        try:
            import base64
            import gzip

            decoded = base64.b64decode(raw_snapshot_gz_b64.encode('ascii'))
            inflated = gzip.decompress(decoded).decode('utf-8')
            obj = json.loads(inflated)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


@app.route("/api/resume-drafts", methods=["POST"])
def api_create_resume_draft():
    """Create a resume draft for the /resume/new wizard (TTL-backed)."""
    try:
        if not _same_origin_post():
            return jsonify({"success": False, "error": "Forbidden"}), 403

        data = request.get_json(force=True, silent=True) or {}
        payload = data.get('payload')
        if not isinstance(payload, dict):
            return jsonify(
                {"success": False, "error": "Invalid payload"}
            ), 400

        draft_id = save_payload('resume_draft', payload)
        return jsonify(
            {
                "success": True,
                "draft_id": draft_id,
                "ttl_seconds": int(DEFAULT_TTL_SECONDS),
            }
        ), 200
    except Exception as e:
        logger.error(f"api_create_resume_draft error: {str(e)}")
        _safe_log_exception('api_create_resume_draft error', e)
        return jsonify(
            {"success": False, "error": "Internal server error"}
        ), 500


@app.route(
    "/api/resume-drafts/<draft_id>",
    methods=["GET", "PUT", "DELETE"]
)
def api_resume_draft(draft_id):
    """Get/update/delete a resume draft by id (same-origin for writes)."""
    token = str(draft_id or '').strip()
    if not token:
        return jsonify(
            {"success": False, "error": "Missing draft_id"}
        ), 400

    try:
        if request.method == 'GET':
            payload = load_payload('resume_draft', token)
            if not payload:
                return jsonify(
                    {"success": False, "error": "Not found"}
                ), 404
            return jsonify(
                {"success": True, "draft_id": token, "payload": payload}
            ), 200

        if not _same_origin_post():
            return jsonify({"success": False, "error": "Forbidden"}), 403

        if request.method == 'PUT':
            data = request.get_json(force=True, silent=True) or {}
            payload = data.get('payload')
            if not isinstance(payload, dict):
                return jsonify(
                    {"success": False, "error": "Invalid payload"}
                ), 400
            save_payload('resume_draft', payload, token=token)
            return jsonify({"success": True, "draft_id": token}), 200

        if request.method == 'DELETE':
            delete_payload('resume_draft', token)
            return jsonify({"success": True}), 200

        return jsonify(
            {"success": False, "error": "Method not allowed"}
        ), 405
    except Exception as e:
        logger.error(f"api_resume_draft error: {str(e)}")
        _safe_log_exception('api_resume_draft error', e)
        return jsonify(
            {"success": False, "error": "Internal server error"}
        ), 500


@app.route("/api/parse-resume-for-template", methods=["POST"])
def parse_resume_for_template():
    """Parse resume and store structured data in session for template viewing"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        template_name = _canonical_template_id(
            data.get('template', 'professional')
        )
        requested_source_revision_id = str(
            data.get('source_revision_id') or ''
        ).strip()

        # Validate template name (canonical IDs only)
        valid_templates = {
            'professional',
            'elegant',
            'creative',
            'creative2',
            'classicRose',
            'boldProfessional',
            'traditional',
            'modern',
            'executive',
            'minimalSidebar',
            # Optional/experimental
            'minimal',
            'darkSidebarProgress',
        }
        # Be fail-safe: if anything upstream sends an unexpected template id,
        # default to a safe/known template rather than hard-failing the flow.
        if template_name not in valid_templates:
            template_name = 'professional'

        # Get revised resume from session
        results_data = session.get('results_data') or {}
        if not results_data:
            return jsonify(
                {"success": False, "error": "Resume data not found"}
            ), 404

        # If the client provided a source revision id, and the user is authenticated,
        # validate ownership and attach it to the session so template saves can persist.
        if requested_source_revision_id and current_user.is_authenticated:
            try:
                table_client = get_table_client()
                table_client.get_entity(
                    partition_key=str(current_user.id),
                    row_key=str(requested_source_revision_id),
                )
                results_data['source_revision_id'] = str(
                    requested_source_revision_id
                )
                session['results_data'] = results_data
                session.modified = True
            except Exception:
                # Ignore invalid/non-owned revision ids
                pass

        revised_resume = results_data.get('revised_resume', '')
        if not revised_resume:
            return jsonify(
                {"success": False, "error": "Revised resume not found"}
            ), 404

        # Parse resume to get structured data.
        # If the resume was created via our builder, we already have a structured object.
        structured_resume = None
        try:
            sr = results_data.get('structured_resume') if isinstance(
                results_data,
                dict
            ) else None
            if isinstance(sr, dict) and sr:
                structured_resume = sr
        except Exception:
            structured_resume = None

        if structured_resume is None:
            parsed_result = parse_resume(revised_resume)
            structured_resume = parsed_result.get('resume', {})

        # Store in session for template viewer
        session['template_data'] = {
            'structured_resume': structured_resume,
            'template_name': template_name,
            'revised_resume': revised_resume,
            # Keep original text as fallback
            # Carry the hub linkage through the SPA so template saves can persist.
            'source_revision_id': str(
                results_data.get('source_revision_id') or ''
            ).strip(),
        }
        session.modified = True

        # Best-effort: persist an initial structured snapshot for the chosen template so the
        # revision card in /my_revisions shows the template version immediately, without
        # requiring edit-mode + "Save Changes".
        try:
            source_revision_id = str(
                session.get('template_data', {}).get(
                    'source_revision_id'
                ) or ''
            ).strip()
            if (
                    source_revision_id
                    and getattr(current_user, 'is_authenticated', False)
                    and isinstance(structured_resume, dict)
                    and structured_resume
            ):
                template_id = _canonical_template_id(
                    template_name or 'professional'
                )
                snapshot = json.dumps(
                    structured_resume,
                    ensure_ascii=False
                )
                snapshot_bytes = snapshot.encode('utf-8')

                table_client = get_table_client()
                try:
                    existing = table_client.get_entity(
                        partition_key=str(current_user.id),
                        row_key=str(source_revision_id),
                    )
                except Exception:
                    existing = None

                if existing is not None:
                    existing['template_id'] = template_id
                    existing['template_saved_at'] = datetime.now(
                        timezone.utc
                    ).isoformat()

                    # Track all saved templates for this revision (small JSON list)
                    try:
                        current_list_raw = str(
                            existing.get('template_saved_templates') or ''
                        ).strip()
                        current_list = json.loads(
                            current_list_raw
                        ) if current_list_raw else []
                        if not isinstance(current_list, list):
                            current_list = []
                    except Exception:
                        current_list = []
                    saved_set = set(
                        [
                            _canonical_template_id(t)
                            for t in current_list
                            if str(t or '').strip()
                        ]
                    )
                    saved_set.add(template_id)
                    try:
                        existing['template_saved_templates'] = json.dumps(
                            sorted(saved_set),
                            ensure_ascii=False
                        )
                    except Exception:
                        pass

                    # Store per-template snapshot (allows multiple template versions per revision)
                    per_plain_prop, per_gz_prop, per_at_prop = _template_snapshot_prop_names(
                        template_id
                    )
                    existing[per_at_prop] = existing['template_saved_at']

                    # Azure Table Storage string properties have tight size limits.
                    # Prefer plain JSON when small; otherwise fall back to gzipped base64.
                    if len(snapshot_bytes) <= 60_000:
                        existing['template_structured_resume'] = snapshot
                        existing['template_structured_resume_gz_b64'] = ''
                        existing[per_plain_prop] = snapshot
                        existing[per_gz_prop] = ''
                        table_client.update_entity(
                            existing,
                            mode=UpdateMode.MERGE
                        )
                    else:
                        import base64
                        import gzip

                        gz = gzip.compress(snapshot_bytes, compresslevel=9)
                        b64 = base64.b64encode(gz).decode('ascii')
                        if len(b64.encode('ascii')) <= 60_000:
                            existing['template_structured_resume'] = ''
                            existing[
                                'template_structured_resume_gz_b64'] = b64
                            existing[per_plain_prop] = ''
                            existing[per_gz_prop] = b64
                            table_client.update_entity(
                                existing,
                                mode=UpdateMode.MERGE
                            )
        except Exception:
            # Do not block the user if template snapshot persistence fails.
            pass

        return jsonify(
            {
                "success": True,
                "template": template_name
            }
        )

    except Exception as e:
        logger.error(f"Error parsing resume for template: {str(e)}")
        _safe_log_exception('parse_resume_for_template error', e)
        return jsonify({"success": False, "error": str(e)}), 500


_TRANSLATE_SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)


def _google_translate_request_auth():
    """Return (headers, query_params) for Translation v2: prefer OAuth2 (service account / ADC); optional API key fallback."""
    req = google.auth.transport.requests.Request()

    sa_json = (os.environ.get(
        "GOOGLE_TRANSLATE_SERVICE_ACCOUNT_JSON"
    ) or "").strip()
    if sa_json:
        try:
            info = json.loads(sa_json)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                "GOOGLE_TRANSLATE_SERVICE_ACCOUNT_JSON is not valid JSON."
            ) from e
        if not isinstance(info, dict) or not info.get("private_key"):
            raise RuntimeError(
                "GOOGLE_TRANSLATE_SERVICE_ACCOUNT_JSON must be a full service account key JSON object."
            )
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=_TRANSLATE_SCOPES
        )
        creds.refresh(req)
        return ({"Authorization": f"Bearer {creds.token}"}, {})

    adc_path = (os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS"
    ) or "").strip()
    if adc_path and os.path.isfile(adc_path):
        try:
            creds = service_account.Credentials.from_service_account_file(
                adc_path,
                scopes=_TRANSLATE_SCOPES
            )
            creds.refresh(req)
            return ({"Authorization": f"Bearer {creds.token}"}, {})
        except Exception:
            # Not a service-account JSON file; fall through to Application Default Credentials.
            pass

    try:
        creds, _ = google.auth.default(scopes=_TRANSLATE_SCOPES)
        creds.refresh(req)
        tok = getattr(creds, "token", None) or ""
        if tok:
            return ({"Authorization": f"Bearer {tok}"}, {})
    except Exception:
        pass

    api_key = (os.environ.get("GOOGLE_TRANSLATE_API_KEY") or "").strip()
    if api_key:
        return ({}, {"key": api_key})

    raise RuntimeError(
        "Resume translation needs Google OAuth credentials (API keys are often rejected for Cloud Translation). "
        "Set GOOGLE_APPLICATION_CREDENTIALS to the path of a service account JSON key with the "
        "Cloud Translation API enabled, or set GOOGLE_TRANSLATE_SERVICE_ACCOUNT_JSON to the raw JSON. "
        "See https://cloud.google.com/docs/authentication#service_accounts"
    )


def _call_google_translate_batch(
        texts: list[str],
        target_lang: str,
        source_lang: Optional[str],
        auth_headers: dict,
        auth_params: dict,
) -> list[str]:
    """Translate a list of strings (same order returned)."""
    if not texts:
        return []

    url = "https://translation.googleapis.com/language/translate/v2"
    out: list[str] = []
    batch_size = 80

    for i in range(0, len(texts), batch_size):
        batch = texts[i: i + batch_size]
        params = dict(auth_params)
        headers = {**auth_headers, "Content-Type": "application/json"}
        payload: dict = {"q": batch, "target": target_lang}
        if source_lang:
            sl = str(source_lang).strip().lower()
            if re.match(r"^[a-z]{2,3}(-[a-z]{2,8})?$", sl):
                payload["source"] = sl

        r = requests.post(
            url,
            params=params or None,
            headers=headers,
            json=payload,
            timeout=90
        )
        if not r.ok:
            try:
                err_detail = r.json()
            except Exception:
                err_detail = r.text
            raise RuntimeError(str(err_detail)[:1200])

        data = r.json()
        trans_list = data.get("data", {}).get("translations", [])
        if len(trans_list) != len(batch):
            raise RuntimeError(
                "Translation API returned an unexpected number of segments."
            )

        for t in trans_list:
            txt = t.get("translatedText", "")
            out.append(html_stdlib.unescape(txt))

    return out


def _resume_section_present_for_heading(
        resume: dict,
        section_key: str
) -> bool:
    """Whether the resume has content for a standard section (matches template visibility rules roughly)."""
    sk = str(section_key or "").strip()
    if sk == "summary":
        return bool(str(resume.get("summary") or "").strip())
    if sk == "experience":
        ex = resume.get("experience")
        return isinstance(ex, list) and len(ex) > 0
    if sk == "education":
        ed = resume.get("education")
        return isinstance(ed, list) and len(ed) > 0
    if sk == "projects":
        pr = resume.get("projects")
        return isinstance(pr, list) and len(pr) > 0
    if sk == "certifications":
        ce = resume.get("certifications")
        return isinstance(ce, list) and len(ce) > 0
    if sk == "skills":
        skills = resume.get("skills")
        if isinstance(skills, list):
            return any(str(x or "").strip() for x in skills)
        return bool(str(skills or "").strip())
    if sk == "languages":
        langs = resume.get("languages")
        if isinstance(langs, list):
            return any(str(x or "").strip() for x in langs)
        return bool(str(langs or "").strip())
    if sk == "contact":
        return bool(
            str(resume.get("email") or "").strip()
            or str(resume.get("phone") or "").strip()
            or str(resume.get("location") or "").strip()
            or str(
                resume.get("website") or resume.get("portfolio") or ""
            ).strip()
        )
    if sk == "info":
        links = resume.get("links")
        if isinstance(links, list) and len(links) > 0:
            return True
        return bool(str(resume.get("linkedin") or "").strip())
    if sk == "accomplishments":
        return bool(str(resume.get("accomplishments") or "").strip())
    if sk == "strengths":
        return bool(str(resume.get("strengths") or "").strip())
    return False


# Default English section titles embedded in each template when `section_headings` is unset.
# Keys must match _canonical_template_id() outputs used in URLs.
_SECTION_HEADING_DEFAULTS_EN: dict[str, dict[str, str]] = {
    "professional": {
        "summary": "Professional Summary",
        "experience": "Work History",
        "projects": "Projects",
        "skills": "Skills",
        "languages": "Languages",
        "certifications": "Certifications",
        "education": "Education",
    },
    "executive": {
        "summary": "Professional Summary",
        "experience": "Professional Experience",
        "education": "Education",
        "projects": "Projects",
        "certifications": "Certifications",
        "languages": "Languages",
        "skills": "Core Competencies",
    },
    "classicRose": {
        "summary": "Professional Statement",
        "experience": "Work Experience",
        "projects": "Projects",
        "education": "Education",
        "certifications": "Certifications",
        "languages": "Languages",
        "skills": "Skills",
    },
    "creative2": {
        "education": "Education",
        "experience": "Experience",
        "projects": "Projects",
        "certifications": "Certifications",
        "languages": "Languages",
        "contact": "Contact",
        "skills": "Skills",
    },
    "boldProfessional": {
        "summary": "Professional Summary",
        "experience": "Work History",
        "projects": "Projects",
        "skills": "Skills",
        "certifications": "Certifications",
        "education": "Education",
    },
    "traditional": {
        "summary": "Professional Summary",
        "experience": "Work History",
        "projects": "Projects",
        "skills": "Skills",
        "education": "Education",
    },
    "modern": {
        "summary": "Summary",
        "experience": "Experience",
        "projects": "Projects",
        "education": "Education",
        "skills": "Skills",
        "strengths": "Strengths",
        "languages": "Languages",
        "certifications": "Certifications",
    },
    "minimalSidebar": {
        "summary": "PROFILE",
        "experience": "EMPLOYMENT HISTORY",
        "education": "EDUCATION",
        "projects": "PROJECTS",
        "certifications": "CERTIFICATIONS",
        "skills": "SKILLS",
        "languages": "LANGUAGES",
        "info": "INFO",
    },
    "minimal": {
        "summary": "Professional Summary",
        "experience": "Work History",
        "education": "Education",
        "projects": "Projects",
        "skills": "Skills",
    },
    "darkSidebarProgress": {
        "summary": "Professional Summary",
        "experience": "Work History",
        "education": "Education",
        "projects": "Projects",
        "skills": "Skills",
    },
}


def _inject_section_heading_defaults_for_preview(
        out: dict,
        template_raw: str,
        target_lang: str,
        source_lang: Optional[str],
        auth_headers: dict,
        auth_params: dict,
) -> None:
    """Templates render English fallback titles from code when `section_headings` is missing — inject translated defaults."""
    canonical = _canonical_template_id(template_raw)
    defaults = _SECTION_HEADING_DEFAULTS_EN.get(
        canonical
    ) or _SECTION_HEADING_DEFAULTS_EN.get("professional") or {}

    headings = out.get("section_headings")
    if not isinstance(headings, dict):
        headings = {}
        out["section_headings"] = headings

    pending_keys: list[str] = []
    pending_texts: list[str] = []

    for section_key, english_label in defaults.items():
        if not _resume_section_present_for_heading(out, section_key):
            continue
        existing = headings.get(section_key)
        if isinstance(existing, str) and existing.strip():
            continue
        pending_keys.append(section_key)
        pending_texts.append(english_label)

    if not pending_keys:
        return

    translated_labels = _call_google_translate_batch(
        pending_texts, target_lang, source_lang, auth_headers, auth_params
    )
    for pk, tl in zip(pending_keys, translated_labels):
        headings[pk] = tl


def _translate_resume_strings_google(
        resume: dict,
        target_lang: str,
        source_lang: Optional[str],
        auth_headers: dict,
        auth_params: dict,
) -> dict:
    """Deep-copy resume and translate user-facing string fields via Google Cloud Translation API v2."""

    target_lang = str(target_lang or "").strip().lower()
    if not re.match(r"^[a-z]{2,3}(-[a-z]{2,8})?$", target_lang):
        raise RuntimeError("Invalid target language code.")

    out = copy.deepcopy(resume)
    refs: list[tuple] = []

    SKIP_KEYS = frozenset(
        {
            "email", "phone", "website", "portfolio", "linkedin", "github",
            "accentColor", "primaryColor", "secondaryColor", "template",
        }
    )
    STYLE_SKIP_KEYS = frozenset(
        {"templateViewerSettings", "templateViewerLayout"}
    )

    def looks_like_email(s: str) -> bool:
        s = s.strip()
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s))

    def looks_like_url(s: str) -> bool:
        s = s.strip().lower()
        return s.startswith("http://") or s.startswith(
            "https://"
        ) or s.startswith("www.")

    def looks_like_phone(s: str) -> bool:
        digits = re.sub(r"\D", "", s)
        return len(digits) >= 10 and len(s) <= 28

    def should_translate_string(s: str) -> bool:
        if not isinstance(s, str):
            return False
        t = s.strip()
        if len(t) < 2:
            return False
        if looks_like_email(t):
            return False
        if looks_like_url(t):
            return False
        if looks_like_phone(t):
            return False
        return True

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                ks = str(k)
                if ks in SKIP_KEYS:
                    continue
                if ks == "style" and isinstance(v, dict):
                    for sk, sv in v.items():
                        if sk in STYLE_SKIP_KEYS or sk in SKIP_KEYS:
                            continue
                        if isinstance(sv, str) and should_translate_string(
                                sv
                        ):
                            refs.append((v, sk))
                        elif isinstance(sv, (dict, list)):
                            walk(sv)
                    continue
                if isinstance(v, str) and should_translate_string(v):
                    refs.append((obj, k))
                elif isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str) and should_translate_string(item):
                    refs.append((obj, i))
                elif isinstance(item, (dict, list)):
                    walk(item)

    walk(out)
    if not refs:
        return out

    texts = [parent[key] for parent, key in refs]
    translated_out = _call_google_translate_batch(
        texts,
        target_lang,
        source_lang,
        auth_headers,
        auth_params
    )

    for idx, (parent, key) in enumerate(refs):
        parent[key] = translated_out[idx]

    return out


@app.route("/api/translate-resume", methods=["POST"])
def api_translate_resume():
    """Translate structured resume text for template preview (Google Cloud Translation API)."""
    try:
        body = request.get_json(force=True, silent=True) or {}
        resume = body.get("resume")
        target = str(
            body.get("target") or body.get("target_lang") or ""
        ).strip()
        source = str(body.get("source") or "").strip() or None
        template_raw = str(
            body.get("template") or body.get("template_name") or body.get(
                "template_id"
            ) or ""
        ).strip()

        if not isinstance(resume, dict):
            return jsonify(
                {"success": False, "error": "Invalid resume payload."}
            ), 400
        if not target:
            return jsonify(
                {"success": False, "error": "Missing target language."}
            ), 400

        # Frontend preview uses sentinel values for "no translation" / "reset to English".
        # Treat these as a no-op so older cached bundles never trigger a hard error.
        if target in ("__source__", "__reset_to_english__"):
            return jsonify({"success": True, "resume": resume})

        auth_headers, auth_params = _google_translate_request_auth()
        out = _translate_resume_strings_google(
            resume,
            target,
            source,
            auth_headers,
            auth_params
        )
        _inject_section_heading_defaults_for_preview(
            out,
            template_raw or "professional",
            target,
            source,
            auth_headers,
            auth_params
        )
        return jsonify({"success": True, "resume": out})
    except RuntimeError as e:
        return jsonify({"success": False, "error": str(e)}), 503
    except Exception as e:
        logger.error("translate-resume failed: %s", e)
        _safe_log_exception("translate-resume", e)
        return jsonify(
            {"success": False, "error": "Translation failed."}
        ), 500


@app.route("/api/template-pdf/snapshot", methods=["POST"])
@login_required
def api_template_pdf_snapshot():
    """Store a one-shot resume JSON for the next Playwright PDF render (translated preview, etc.)."""
    try:
        body = request.get_json(force=True, silent=True) or {}
        resume = body.get("resume")
        template_hint = str(
            body.get("template") or body.get("template_name") or body.get(
                "template_id"
            ) or ""
        ).strip()
        if not isinstance(resume, dict):
            return jsonify(
                {"success": False, "error": "Invalid resume payload"}
            ), 400

        token = _pdf_snapshot_store_put(
            resume,
            int(current_user.id),
            template_hint or None
        )
        return jsonify({"success": True, "token": token})
    except Exception as e:
        logger.error("template_pdf snapshot store failed: %s", e)
        return jsonify(
            {"success": False, "error": "Could not store PDF snapshot."}
        ), 500


@app.route("/api/template-data", methods=["GET"])
def get_template_data():
    """Get structured resume data for template viewer"""
    snap_tok = str(request.args.get("pdf_snapshot") or "").strip()
    if snap_tok:
        ent = _pdf_snapshot_store_get(snap_tok)
        if not ent:
            return jsonify(
                {"error": "Invalid or expired PDF snapshot"}
            ), 404
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        try:
            if int(ent.get("uid") or -1) != int(current_user.id):
                return jsonify({"error": "Forbidden"}), 403
        except Exception:
            return jsonify({"error": "Forbidden"}), 403

        template_data = session.get("template_data") or {}
        if not isinstance(template_data, dict):
            template_data = {}
        results_data = session.get("results_data") or {}
        source_revision_id = str(
            (results_data.get("source_revision_id") if isinstance(
                results_data,
                dict
            ) else None)
            or (template_data.get("source_revision_id") if isinstance(
                template_data,
                dict
            ) else None)
            or ""
        ).strip()

        resume_out = ent.get("resume")
        if not isinstance(resume_out, dict):
            return jsonify({"error": "Invalid snapshot resume"}), 404

        tmpl = str(ent.get("template_hint") or "").strip()
        if not tmpl:
            tmpl = str(
                template_data.get("template_name") or "professional"
            )

        return jsonify(
            {
                "success": True,
                "resume": resume_out,
                "template": _canonical_template_id(tmpl),
                "revised_resume": template_data.get(
                    "revised_resume",
                    ""
                ) if isinstance(template_data, dict) else "",
                "source_revision_id": source_revision_id,
            }
        )

    template_data = session.get('template_data')
    if not template_data:
        return jsonify({"error": "Template data not found"}), 404

    results_data = session.get('results_data') or {}
    source_revision_id = str(
        (results_data.get('source_revision_id') if isinstance(
            results_data,
            dict
        ) else None)
        or (template_data.get('source_revision_id') if isinstance(
            template_data,
            dict
        ) else None)
        or ''
    ).strip()

    return jsonify(
        {
            "success": True,
            "resume": template_data['structured_resume'],
            "template": template_data['template_name'],
            "revised_resume": template_data.get('revised_resume', ''),
            "source_revision_id": source_revision_id,
        }
    )


@app.route("/api/template-data", methods=["POST"])
def update_template_data():
    """Update structured resume data for template viewer.

    Always stores into session. If the session is linked to a persisted revision
    (session['results_data']['source_revision_id']), also persists a structured snapshot to
    Azure Table Storage for future reopening/editing.
    """
    try:
        template_data = session.get('template_data')

        data = request.get_json(force=True, silent=True) or {}
        resume = data.get("resume")
        requested_template_name = str(
            data.get('template')
            or data.get('template_name')
            or data.get('templateId')
            or ''
        ).strip()
        is_preview = bool(data.get('preview'))
        requested_source_revision_id = str(
            data.get('source_revision_id') or ''
        ).strip()
        if not isinstance(resume, dict):
            return jsonify(
                {"success": False, "error": "Invalid resume payload"}
            ), 400

        # Allow the client to initialize a preview session even if parse-resume-for-template
        # has not run yet (e.g., live preview in the resume wizard).
        if not template_data:
            results_data = session.get('results_data') or {}
            source_revision_id = str(
                (results_data.get('source_revision_id') if isinstance(
                    results_data,
                    dict
                ) else None)
                or ''
            ).strip()

            template_name = _canonical_template_id(
                requested_template_name or 'professional'
            )
            template_data = {
                'structured_resume': resume,
                'template_name': template_name,
                'revised_resume': str(data.get('revised_resume') or ''),
                'source_revision_id': source_revision_id,
            }
            session['template_data'] = template_data
            session.modified = True
            return jsonify(
                {
                    "success": True,
                    "template": template_name,
                    "persisted_to_hub": False,
                    "persist_reason": "preview" if is_preview else None,
                }
            )

        # Update only the structured resume. Keep template_name and revised_resume intact.
        template_data["structured_resume"] = resume
        if requested_template_name:
            template_data["template_name"] = _canonical_template_id(
                requested_template_name
            )
        session["template_data"] = template_data
        session.modified = True

        # Best-effort persistence back to the stored revision (if any).
        persisted_to_hub = False
        persist_reason = None
        persisted_format = None
        if is_preview:
            persist_reason = 'preview'
        else:
            try:
                if not current_user.is_authenticated:
                    persist_reason = 'not_authenticated'
                else:
                    results_data = session.get('results_data') or {}
                    source_revision_id = str(
                        results_data.get('source_revision_id')
                        or (template_data.get(
                            'source_revision_id'
                        ) if isinstance(template_data, dict) else None)
                        or ''
                    ).strip()

                # If the client provided a source revision id, validate it and prefer it.
                if requested_source_revision_id and requested_source_revision_id != source_revision_id:
                    try:
                        table_client = get_table_client()
                        table_client.get_entity(
                            partition_key=str(current_user.id),
                            row_key=str(requested_source_revision_id),
                        )
                        source_revision_id = str(
                            requested_source_revision_id
                        )
                        # Repair session linkage for subsequent requests.
                        if isinstance(results_data, dict):
                            results_data[
                                'source_revision_id'] = source_revision_id
                            session['results_data'] = results_data
                        if isinstance(template_data, dict):
                            template_data[
                                'source_revision_id'] = source_revision_id
                            session['template_data'] = template_data
                        session.modified = True
                    except Exception:
                        # Ignore invalid/non-owned revision ids.
                        pass

                if not source_revision_id:
                    # Auto-create a new revision for new resumes (created via template builder)
                    # that don't yet have a source_revision_id.
                    import uuid

                    source_revision_id = str(uuid.uuid4())
                    revised_resume = str(
                        template_data.get('revised_resume') or ''
                    )

                    try:
                        # Create a new revision entry in the database
                        save_resume_revision(
                            user_id=current_user.id,
                            revision_id=source_revision_id,
                            resume_content=revised_resume,
                            feedback={},
                            original_resume='',
                            job_description=''
                        )
                        # Update session to track the new revision ID for future saves
                        if isinstance(results_data, dict):
                            results_data[
                                'source_revision_id'] = source_revision_id
                            session['results_data'] = results_data
                        if isinstance(template_data, dict):
                            template_data[
                                'source_revision_id'] = source_revision_id
                            session['template_data'] = template_data
                    except FreeTierLimitReached:
                        # User has hit the free tier limit
                        persist_reason = 'free_tier_limit'
                        source_revision_id = None
                    except Exception as e:
                        logger.error(
                            f"Failed to auto-create revision: {str(e)}"
                        )
                        persist_reason = 'revision_creation_failed'
                        source_revision_id = None

                if source_revision_id:
                    template_id = _canonical_template_id(
                        template_data.get(
                            'template_name'
                        ) or 'professional'
                    )

                    snapshot = json.dumps(resume, ensure_ascii=False)
                    snapshot_bytes = snapshot.encode('utf-8')

                    table_client = get_table_client()
                    try:
                        existing = table_client.get_entity(
                            partition_key=str(current_user.id),
                            row_key=source_revision_id
                        )
                    except Exception:
                        existing = None

                    if existing is None:
                        persist_reason = 'revision_not_found'
                    else:
                        existing['template_id'] = template_id
                        existing['template_saved_at'] = datetime.now(
                            timezone.utc
                        ).isoformat()

                        # Track all saved templates for this revision (small JSON list)
                        try:
                            current_list_raw = str(
                                existing.get(
                                    'template_saved_templates'
                                ) or ''
                            ).strip()
                            current_list = json.loads(
                                current_list_raw
                            ) if current_list_raw else []
                            if not isinstance(current_list, list):
                                current_list = []
                        except Exception:
                            current_list = []
                        saved_set = set(
                            [_canonical_template_id(t) for t in
                             current_list if str(t or '').strip()]
                        )
                        saved_set.add(template_id)
                        try:
                            existing[
                                'template_saved_templates'] = json.dumps(
                                sorted(saved_set),
                                ensure_ascii=False
                            )
                        except Exception:
                            # Best effort; don't block saves
                            pass

                        # Store per-template snapshot (allows multiple template versions per revision)
                        per_plain_prop, per_gz_prop, per_at_prop = _template_snapshot_prop_names(
                            template_id
                        )
                        existing[per_at_prop] = existing[
                            'template_saved_at']

                        # Azure Table Storage string properties have tight size limits.
                        # Prefer plain JSON when small; otherwise fall back to gzipped base64.
                        if len(snapshot_bytes) <= 60_000:
                            existing[
                                'template_structured_resume'] = snapshot
                            existing[
                                'template_structured_resume_gz_b64'] = ''

                            existing[per_plain_prop] = snapshot
                            existing[per_gz_prop] = ''
                            table_client.update_entity(
                                existing,
                                mode=UpdateMode.MERGE
                            )
                            persisted_to_hub = True
                            persisted_format = 'plain'
                        else:
                            import base64
                            import gzip

                            gz = gzip.compress(
                                snapshot_bytes,
                                compresslevel=9
                            )
                            b64 = base64.b64encode(gz).decode('ascii')
                            if len(b64.encode('ascii')) <= 60_000:
                                existing['template_structured_resume'] = ''
                                existing[
                                    'template_structured_resume_gz_b64'] = b64

                                existing[per_plain_prop] = ''
                                existing[per_gz_prop] = b64
                                table_client.update_entity(
                                    existing,
                                    mode=UpdateMode.MERGE
                                )
                                persisted_to_hub = True
                                persisted_format = 'gz_b64'
                            else:
                                persist_reason = 'snapshot_too_large'
                else:
                    if not persist_reason:
                        persist_reason = 'missing_source_revision_id'

            except Exception:
                persisted_to_hub = False
                if not persist_reason:
                    persist_reason = 'exception'

        if persisted_to_hub:
            persist_reason = None

        # Always return canonical template id so clients (e.g. create-resume iframe preview)
        # can navigate to /template-viewer/<id> even when this isn't the first POST in the session.
        resolved_template = _canonical_template_id(
            (template_data.get('template_name') if isinstance(
                template_data,
                dict
            ) else None)
            or 'professional'
        )
        return jsonify(
            {
                "success": True,
                "template": resolved_template,
                "persisted_to_hub": bool(persisted_to_hub),
                "persist_reason": persist_reason,
                "persisted_format": persisted_format,
            }
        )
    except Exception as e:
        logger.error(f"Error updating template data: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/template-pdf/<template_id>", methods=["GET"])
@login_required
def api_template_pdf(template_id):
    """Generate a resume PDF using headless Chromium (Playwright).

    Client-side html2canvas/html2pdf fails on modern Tailwind color functions like oklab/oklch.
    This endpoint renders the existing React template route in Chromium and returns a PDF attachment.
    """
    pdf_snap_tok_cleanup = str(
        request.args.get("pdfSnapshot") or ""
    ).strip()
    step = "start"
    try:
        t0 = time.time()

        def _t() -> int:
            try:
                return int((time.time() - t0) * 1000)
            except Exception:
                return 0

        logger.info(
            "template_pdf start template=%s t=%sms",
            str(template_id or ''),
            _t()
        )
        step = "paid_check"
        paid_flag = bool(is_paid_user(current_user))
        if _stripe_enabled():
            try:
                paid_flag = bool(
                    _refresh_paid_status_from_stripe_for_user(current_user)
                )
            except Exception:
                paid_flag = paid_flag
        if not paid_flag:
            return "Paid plan required.", 402

        template_data = session.get('template_data')
        if not template_data:
            if not pdf_snap_tok_cleanup:
                return "Template data not found in session.", 404
            step = "pdf_snapshot_validate"
            ent = _pdf_snapshot_store_get(pdf_snap_tok_cleanup)
            if not ent:
                return "PDF snapshot expired or invalid.", 404
            try:
                if int(ent.get("uid") or -1) != int(current_user.id):
                    return "Forbidden.", 403
            except Exception:
                return "Forbidden.", 403
        # If the App Service container recycled, OS libs may be missing until startup.sh finishes apt-get.
        # In that case, avoid a confusing TargetClosedError and return a retryable status instead.
        if _ON_AZURE:
            try:
                import ctypes

                required_libs = [
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
                for lib in required_libs:
                    try:
                        ctypes.CDLL(lib)
                    except Exception:
                        missing.append(lib)
                if missing:
                    logger.warning(
                        "template_pdf deps_missing missing=%s",
                        ",".join(missing)
                    )
                    return (
                        "PDF dependencies are still installing on the server. "
                        "Please wait 2–3 minutes and try again.",
                        503,
                    )
            except Exception:
                # If probe fails, continue and let Playwright report the real error.
                pass

        step = "canonicalize"
        canonical = _canonical_template_id(template_id or 'professional')

        # Use public URL. 127.0.0.1 caused deadlock with 1 worker (worker busy can't serve Chromium's request).
        step = "build_target_url"
        base_url = request.host_url.rstrip('/')
        target_url = base_url + url_for(
            'react_app',
            subpath=f"template-download/{canonical}"
        )
        if pdf_snap_tok_cleanup:
            join = "&" if ("?" in target_url) else "?"
            target_url = target_url + join + urlencode(
                {"pdf_snapshot": pdf_snap_tok_cleanup}
            )
        logger.info(
            "template_pdf navigate url=%s t=%sms",
            target_url,
            _t()
        )

        # Style overrides (match TemplateViewer sliders)
        def _clamp(v: float, lo: float, hi: float) -> float:
            try:
                v = float(v)
            except Exception:
                v = float(lo)
            if v < lo:
                return float(lo)
            if v > hi:
                return float(hi)
            return float(v)

        try:
            font_scale = _clamp(
                request.args.get('fontScale', 1.0),
                0.6,
                1.6
            )
            paragraph_gap_px = _clamp(
                request.args.get('paragraphGapPx', 0.0),
                -80,
                300
            )
            spacing_scale = _clamp(
                request.args.get('spacingScale', 1.0),
                0.0,
                6.0
            )
        except Exception:
            font_scale, paragraph_gap_px, spacing_scale = 1.0, 0.0, 1.0
        logger.info(
            "template_pdf style fontScale=%s paragraphGapPx=%s spacingScale=%s t=%sms",
            font_scale,
            paragraph_gap_px,
            spacing_scale,
            _t(),
        )

        _pdf_debug = False
        try:
            _pdf_debug = str(
                request.args.get('debug') or ''
            ).strip().lower() in ('1', 'true', 'yes')
        except Exception:
            _pdf_debug = False
        try:
            _pdf_debug = _pdf_debug or (str(
                os.getenv('PDF_DEBUG') or ''
            ).strip().lower() in ('1', 'true', 'yes'))
        except Exception:
            _pdf_debug = _pdf_debug

        _pdf_debug_dir = None
        _pdf_debug_files = []

        cookies = []
        cookie_base = base_url + "/"
        for name, value in (request.cookies or {}).items():
            try:
                cookies.append(
                    {"name": name, "value": value, "url": cookie_base}
                )
            except Exception:
                pass

        step = "playwright_launch"
        pw = None
        pdf_bytes = b""
        browser = None
        context = None
        try:
            # Azure App Service can be restrictive for Chromium. These flags reduce sandbox/devshm
            # issues and improve stability in containerized environments.
            launch_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--no-zygote",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-background-timer-throttling",
                "--disable-features=site-per-process,IsolateOrigins",
            ]
            launch_kwargs = {"headless": True, "args": launch_args}
            if _ON_AZURE:
                launch_kwargs["chromium_sandbox"] = False

            # Prefer full Chromium if present; otherwise fall back to default.
            chromium_executable_path = None
            if _ON_AZURE:
                try:
                    import glob as _glob

                    browsers_path = (os.getenv(
                        "PLAYWRIGHT_BROWSERS_PATH"
                    ) or "/home/site/wwwroot/ms-playwright").strip()
                    candidates = []
                    candidates += _glob.glob(
                        os.path.join(
                            browsers_path,
                            "chromium-*",
                            "chrome-linux",
                            "chrome"
                        )
                    )
                    candidates += _glob.glob(
                        os.path.join(
                            browsers_path,
                            "chromium-*",
                            "chrome-linux",
                            "chrome-wrapper"
                        )
                    )
                    candidates += _glob.glob(
                        os.path.join(
                            browsers_path,
                            "chromium-*",
                            "**",
                            "chrome"
                        ),
                        recursive=True
                    )
                    candidates = sorted({c for c in candidates if c})
                    if candidates:
                        chromium_executable_path = candidates[0]
                except Exception:
                    chromium_executable_path = None

            if _ON_AZURE and chromium_executable_path:
                launch_kwargs["executable_path"] = chromium_executable_path
                logger.info(
                    "template_pdf chromium_launch exec=%s t=%sms",
                    chromium_executable_path,
                    _t()
                )
            else:
                logger.info(
                    "template_pdf chromium_launch exec=%s t=%sms",
                    "(default)",
                    _t()
                )

            # Reuse Chromium safely by keeping a browser per server thread.
            # This avoids expensive per-request launches while respecting Playwright sync thread affinity.
            browser = _get_pdf_browser_threadlocal(launch_kwargs)
            context = browser.new_context(
                viewport={"width": 816, "height": 1056},
                device_scale_factor=1,
            )
            if cookies:
                context.add_cookies(cookies)

            page = context.new_page()
            # Embed fonts as base64 in CSS so Chromium never waits for a fetch. Matches localhost exactly.
            _fonts_dir = _get_pdf_fonts_dir()
            _font_b64_cache = _get_inter_font_b64_cache()

            def _handle_route(route):
                req = route.request
                url = (req.url or "").lower()
                if "fonts.googleapis.com" in url or "fonts.gstatic.com" in url:
                    route.abort()
                    return
                if "/static/fonts/" in url:
                    try:
                        from urllib.parse import unquote, urlparse

                        parsed = urlparse(req.url)
                        path = unquote(parsed.path)
                        if path.startswith("/static/fonts/"):
                            rel = path[len("/static/fonts/"):].lstrip("/")
                            local_path = os.path.join(_fonts_dir, rel)
                            if rel == "inter.css" and _font_b64_cache:
                                # Serve CSS with base64-embedded fonts (zero fetch, guaranteed load).
                                css_path = os.path.join(
                                    _fonts_dir,
                                    "inter.css"
                                )
                                if os.path.isfile(css_path):
                                    with open(
                                            css_path,
                                            "r",
                                            encoding="utf-8"
                                    ) as f:
                                        css = f.read()
                                    for fname, b64 in _font_b64_cache.items():
                                        css = css.replace(
                                            f"url(/static/fonts/inter/{fname})",
                                            f"url(data:font/woff2;base64,{b64})",
                                        )
                                    route.fulfill(
                                        status=200,
                                        body=css.encode("utf-8"),
                                        content_type="text/css"
                                    )
                                    return
                            elif os.path.isfile(local_path):
                                with open(local_path, "rb") as f:
                                    body = f.read()
                                mime = "font/woff2" if local_path.endswith(
                                    ".woff2"
                                ) else "text/css"
                                route.fulfill(
                                    status=200,
                                    body=body,
                                    content_type=mime
                                )
                                return
                    except Exception as e:
                        logger.warning(
                            "template_pdf font_fulfill url=%s err=%s",
                            req.url,
                            e
                        )
                route.continue_()

            try:
                page.route("**/*", _handle_route)
            except Exception:
                pass
            step = "page_goto"
            page.goto(
                target_url,
                wait_until="domcontentloaded",
                timeout=90000
            )
            logger.info("template_pdf domcontentloaded t=%sms", _t())

            # Prefer the dedicated export root, but be resilient to cached/older frontend builds.
            step = "wait_export_root"
            try:
                page.wait_for_selector(
                    "#templatePrintContent",
                    timeout=8000
                )
            except Exception:
                page.wait_for_selector(".tv-style-root", timeout=60000)
            logger.info("template_pdf selector_ready t=%sms", _t())

            # Give the browser a moment to finish layout and load webfonts/images.
            # Keep waits bounded to avoid long stalls on background connections.
            try:
                page.wait_for_load_state("networkidle", timeout=1500)
            except Exception:
                pass
            step = "wait_fonts_images"
            try:
                page.evaluate(
                    """() => {
                      const fontsReady = (document.fonts && document.fonts.ready) ? document.fonts.ready : Promise.resolve();
                      const imgs = Array.from(document.images || []);
                      const imagesReady = Promise.all(imgs.map(img => img.complete ? true : new Promise(r => {
                        img.addEventListener('load', () => r(true), { once: true });
                        img.addEventListener('error', () => r(true), { once: true });
                      })));
                      return Promise.race([
                        Promise.all([fontsReady, imagesReady]).then(() => true),
                        new Promise(resolve => setTimeout(() => resolve(false), 4000)),
                      ]);
                    }"""
                )
            except Exception:
                pass
            page.wait_for_timeout(80)

            # Print only the resume root without clearing the page.
            # Important: clearing <body> removes TemplateViewer's inline <style> rules that implement
            # the slider-based spacing/font overrides. Instead we render the export node into a
            # dedicated body child (#__pdfMount) and hide everything else at print-time.
            step = "mount_and_css"
            page.evaluate(
                """(a) => {
                      const root = document.getElementById('templatePrintContent') || document.getElementById('templatePrintRoot') || document.querySelector('.tv-style-root');
                      // Apply CSS vars to cloned tv-style-root so the PDF matches slider settings.
                      if (!root) throw new Error('Missing templatePrintRoot');

                      const rootClone = root.cloneNode(true);
                      const tv = (rootClone.classList && rootClone.classList.contains('tv-style-root'))
                        ? rootClone
                        : (rootClone.querySelector ? rootClone.querySelector('.tv-style-root') : null);
                      if (tv && tv.style) {
                        tv.style.setProperty('--tv-font-scale', String(a.fontScale));
                        tv.style.setProperty('--tv-paragraph-gap', `${a.paragraphGapPx}px`);
                        tv.style.setProperty('--tv-space-scale', String(a.spacingScale));
                      }

                                            // Detect template id for PDF-specific per-page backgrounds.
                                            try {
                                                const tmplEl = (rootClone.matches && rootClone.matches('[data-template]'))
                                                    ? rootClone
                                                    : (rootClone.querySelector ? rootClone.querySelector('[data-template]') : null);
                                                const tmpl = tmplEl && tmplEl.getAttribute ? String(tmplEl.getAttribute('data-template') || '').trim() : '';
                                                if (tmpl) document.body.setAttribute('data-pdf-template', tmpl);
                                            } catch (e) {
                                                // ignore
                                            }

                                            // Expose theme vars on :root so page-level fixed backgrounds can use them.
                                            try {
                                                if (tv) {
                                                    // NOTE: `tv` is a clone at this point and may not be connected to the DOM yet.
                                                    // `getComputedStyle()` on disconnected nodes can return empty for custom properties.
                                                    // Prefer inline style values (set by TemplateViewer on #templatePrintContent).
                                                    ['--tv-secondary', '--tv-accent'].forEach((k) => {
                                                        let v = '';
                                                        try {
                                                            v = (tv.style && tv.style.getPropertyValue) ? (tv.style.getPropertyValue(k) || '') : '';
                                                        } catch (e) { v = ''; }
                                                        v = String(v || '').trim();
                                                        if (!v) {
                                                            try {
                                                                const cs = window.getComputedStyle(tv);
                                                                v = String((cs && cs.getPropertyValue) ? (cs.getPropertyValue(k) || '') : '').trim();
                                                            } catch (e) { v = ''; }
                                                        }
                                                        if (v) document.documentElement.style.setProperty(k, v);
                                                    });
                                                }
                                            } catch (e) {
                                                // ignore
                                            }
                      rootClone.style.position = 'relative';
                      rootClone.style.left = '0';
                      rootClone.style.top = '0';
                      // Requirement: keep page 1 top unchanged, but add bottom margin on all pages
                      // and top margin only from page 2 onward.
                      // Use CSS @page and @page:first to achieve this (avoid JS offsets that can clip text).

                      let mount = document.getElementById('__pdfMount');
                      if (!mount) {
                        mount = document.createElement('div');
                        mount.id = '__pdfMount';
                        document.body.appendChild(mount);
                      }
                      mount.innerHTML = '';
                      mount.appendChild(rootClone);
                      try {
                                                mount.style.margin = '0';
                                                mount.style.padding = '0';
                                                mount.style.background = 'transparent';
                        mount.style.position = 'relative';
                        mount.style.left = '0';
                        mount.style.top = '0';
                      } catch (e) {
                        // ignore
                      }

                                            // NOTE: Avoid injecting overlay strips above content.
                                            // They can accidentally cover header text if the wrong element is selected.

                                            // NOTE: Do NOT strip first-page top padding/margins.
                                            // Requirement: page 1 top must remain unchanged.
                                            // Page 2+ breathing room is handled via @page margin-top.

                      const existing = document.getElementById('__pdfOnlyCss');
                      if (existing) existing.remove();
                      const style = document.createElement('style');
                      style.id = '__pdfOnlyCss';
                                            style.textContent = `
                                                /* Use CSS @page margins so we can keep page 1 top unchanged via @page:first. */
                                                @page { size: letter; margin: 0.5in 0in 0.5in 0in !important; }
                                                @page:first { margin-top: 0in !important; }
                        html, body { width: 816px; margin: 0 !important; padding: 0 !important; background: #fff !important; min-height: 0 !important; }
                        * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
                        body > *:not(#__pdfMount) { display: none !important; }

                                                /* Per-page vertical background fills (repeat on each page using position:fixed).
                                                     Fixes last-page short-content sidebars that otherwise stop early. */
                                                body { position: relative !important; }
                                                body::after {
                                                    content: "";
                                                    position: fixed;
                                                    top: 0;
                                                    left: 0;
                                                    right: 0;
                                                    bottom: 0;
                                                    z-index: 0;
                                                    pointer-events: none;
                                                    background: transparent;
                                                }
                                                #__pdfMount { position: relative !important; z-index: 1 !important; }
                                                #__pdfMount { background: transparent !important; }
                                                body[data-pdf-template="clean"]::after {
                                                    background: linear-gradient(to right,
                                                        var(--tv-secondary) 0%,
                                                        var(--tv-secondary) 33.333%,
                                                        #ffffff 33.333%,
                                                        #ffffff 100%
                                                    );
                                                }
                                                body[data-pdf-template="classicrose"]::after {
                                                    background: linear-gradient(to right,
                                                        var(--tv-secondary) 0%,
                                                        var(--tv-secondary) 33.333%,
                                                        #ffffff 33.333%,
                                                        #ffffff 100%
                                                    );
                                                }
                                                body[data-pdf-template="modern"]::after {
                                                    background: linear-gradient(to right,
                                                        #ffffff 0%,
                                                        #ffffff 60%,
                                                        var(--tv-secondary) 60%,
                                                        var(--tv-secondary) 100%
                                                    );
                                                }
                                                body[data-pdf-template="creative2"]::after {
                                                    /* Creative2: match the on-screen template (no full-height left shading) */
                                                    background: #ffffff;
                                                }

                                                /* Allow the per-page background gradient to show through inside the resume.
                                                     Many templates render an opaque white wrapper (bg-white) which would otherwise
                                                     hide the page-level background fills. */
                                                #__pdfMount [data-template="clean"],
                                                #__pdfMount [data-template="classicrose"],
                                                #__pdfMount [data-template="modern"] {
                                                    background: transparent !important;
                                                }
                                                /* Creative2: keep an opaque white card to avoid PDF-only shading artifacts */
                                                #__pdfMount [data-template="creative2"].creative2-template {
                                                    background: #ffffff !important;
                                                }
                                                                /* Use flow-root (BFC) to prevent first-child top-margin collapse which can
                                                                    appear as an unexplained white strip at the top of page 1 in PDFs. */
                                                                #__pdfMount { display: flow-root !important; position: relative !important; left: 0 !important; top: 0 !important; }
                                                                #__pdfMount .tv-style-root { display: flow-root !important; }

                                                                /* PDF seam fix: rounded corners + overflow clipping can create a thin white strip
                                                                    at the top edge when Chromium rasterizes backgrounds into PDF. Disable wrapper
                                                                    rounding/overflow in the PDF output context only. */
                                                                #__pdfMount > * { border-radius: 0 !important; overflow: visible !important; }
                                                                #__pdfMount .tv-style-root > * { border-radius: 0 !important; overflow: visible !important; }
                                                /* NOTE: Top-padding stripping is handled by a JS heuristic above, to avoid
                                                   removing intentional header padding in full-bleed templates. */

                                                                    /* IMPORTANT: Avoid negative top nudges in the PDF-only context.
                                                                      When page 1 is already pulled up to cancel margins, extra negative
                                                                      offsets can push text into the clipped top edge. */


                                                                                                                                /* Creative2: keep the left edge flush so the yellow accent bar touches the page edge. */
                                                                                                                                #__pdfMount [data-template="creative2"].creative2-template { margin: 0 !important; }
                                                                                                                                /* Full-height vertical backgrounds (one-page appearance):
                                                                                                                                     Ensure sidebars/vertical accents reach the page bottom instead of
                                                                                                                                     stopping at the end of content. */
                                                                                                                                #__pdfMount [data-template="clean"] .grid.grid-cols-12 { min-height: 10.5in !important; }
                                                                                                                                #__pdfMount [data-template="creative2"].creative2-template > div.relative { min-height: 10.5in !important; }
                        #__pdfMount, #__pdfMount * {
                          box-shadow: none !important;
                          filter: none !important;
                        }
                        #__pdfMount .shadow,
                        #__pdfMount .shadow-sm,
                        #__pdfMount .shadow-md,
                        #__pdfMount .shadow-lg,
                        #__pdfMount .shadow-xl,
                        #__pdfMount .shadow-2xl {
                          box-shadow: none !important;
                        }
                        /* Apply font/spacing scale from slider settings (vars set on clone via setProperty) */
                        #__pdfMount .tv-style-root p { margin: 0 0 var(--tv-paragraph-gap, 0px) 0 !important; }
                        #__pdfMount .tv-style-root { font-size: calc(1rem * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .text-xs { font-size: calc(0.75rem * var(--tv-font-scale, 1)) !important; line-height: calc(1rem * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .text-sm { font-size: calc(0.875rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.25rem * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .text-base { font-size: calc(1rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.5rem * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .text-lg { font-size: calc(1.125rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.75rem * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .text-xl { font-size: calc(1.25rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.75rem * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .text-2xl { font-size: calc(1.5rem * var(--tv-font-scale, 1)) !important; line-height: calc(2rem * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .text-3xl { font-size: calc(1.875rem * var(--tv-font-scale, 1)) !important; line-height: calc(2.25rem * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .text-4xl { font-size: calc(2.25rem * var(--tv-font-scale, 1)) !important; line-height: calc(2.5rem * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .text-5xl { font-size: calc(3rem * var(--tv-font-scale, 1)) !important; line-height: 1 !important; }
                        #__pdfMount .tv-style-root .text-\\\\[10px\\\\] { font-size: calc(10px * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .text-\\\\[11px\\\\] { font-size: calc(11px * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .text-\\\\[12px\\\\] { font-size: calc(12px * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .text-\\\\[13px\\\\] { font-size: calc(13px * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .text-\\\\[34px\\\\] { font-size: calc(34px * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .text-\\\\[38px\\\\] { font-size: calc(38px * var(--tv-font-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .space-y-10 > :not([hidden]) ~ :not([hidden]) { margin-top: calc(2.5rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .space-y-8 > :not([hidden]) ~ :not([hidden]) { margin-top: calc(2rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .space-y-6 > :not([hidden]) ~ :not([hidden]) { margin-top: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .space-y-5 > :not([hidden]) ~ :not([hidden]) { margin-top: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .space-y-4 > :not([hidden]) ~ :not([hidden]) { margin-top: calc(1rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .space-y-3 > :not([hidden]) ~ :not([hidden]) { margin-top: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .space-y-2 > :not([hidden]) ~ :not([hidden]) { margin-top: calc(0.5rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mb-12 { margin-bottom: calc(3rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mb-10 { margin-bottom: calc(2.5rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mb-8 { margin-bottom: calc(2rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mb-6 { margin-bottom: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mb-5 { margin-bottom: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mb-4 { margin-bottom: calc(1rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mb-3 { margin-bottom: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mb-2 { margin-bottom: calc(0.5rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mb-1 { margin-bottom: calc(0.25rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mt-12 { margin-top: calc(3rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mt-10 { margin-top: calc(2.5rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mt-8 { margin-top: calc(2rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mt-6 { margin-top: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mt-5 { margin-top: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mt-4 { margin-top: calc(1rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mt-3 { margin-top: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mt-2 { margin-top: calc(0.5rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .mt-1 { margin-top: calc(0.25rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .gap-8 { gap: calc(2rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .gap-6 { gap: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .gap-5 { gap: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .gap-4 { gap: calc(1rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .gap-3 { gap: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .gap-2 { gap: calc(0.5rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .pb-4 { padding-bottom: calc(1rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .pb-3 { padding-bottom: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .pb-2 { padding-bottom: calc(0.5rem * var(--tv-space-scale, 1)) !important; }
                        #__pdfMount .tv-style-root .pb-0 { padding-bottom: 0 !important; }
                                                /* Creative template (Creative2): keep pagination stable in Chromium/print.
                                                     IMPORTANT: the main issue is that CSS grid may be treated as non-fragmentable,
                                                     pushing the entire body to the next page. Force a fragmentable layout and only
                                                     keep *individual entries* together. */

                                                /* Creative2 decorative elements are part of the template design.
                                                   Do not hide them in PDF; only ensure they don't affect pagination by
                                                   keeping layout containers fragmentable (rules below). */

                                                                     /* Defensive: if any stale print CSS sets display:none, force them back on.
                                                                         Preserve display:flex for the top-right blocks container. */
                                                    #__pdfMount [data-template="creative2"] .creative2-decorative,
                                                    #__pdfMount .creative2-decorative {
                                                        display: block !important;
                                                    }
                                                    #__pdfMount [data-template="creative2"] .creative2-decorative.flex,
                                                    #__pdfMount .creative2-decorative.flex {
                                                        display: flex !important;
                                                    }

                                                /* Slightly compact typography/padding for PDF */
                                                #__pdfMount [data-template="creative2"] .creative2-template,
                                                #__pdfMount .creative2-template {
                                                    font-size: 0.88em !important;
                                                }
                                                #__pdfMount [data-template="creative2"] .creative2-body,
                                                #__pdfMount .creative2-body {
                                                        /* Preserve template gutter (pl-12/pr-8) so text doesn't hug the left edge */
                                                        padding-top: 0.4rem !important;
                                                        padding-bottom: 0.4rem !important;
                                                        padding-left: 3rem !important;
                                                        padding-right: 2rem !important;
                                                    break-inside: auto !important;
                                                    page-break-inside: auto !important;
                                                }
                                                #__pdfMount [data-template="creative2"] .creative2-body > div:first-child,
                                                #__pdfMount .creative2-body > div:first-child {
                                                    margin-bottom: 0.35rem !important;
                                                }
                                                #__pdfMount [data-template="creative2"] .creative2-summary,
                                                #__pdfMount .creative2-summary {
                                                    margin-top: 0.2rem !important;
                                                    margin-bottom: 0 !important;
                                                    line-height: 1.3 !important;
                                                    max-width: none !important;
                                                    break-after: auto !important;
                                                    page-break-after: auto !important;
                                                }

                                                /* Ensure header/sections are allowed to break so the grid can start on page 1
                                                     even when there is only limited remaining space after the summary. */
                                                #__pdfMount [data-template="creative2"] .creative2-header,
                                                #__pdfMount .creative2-header {
                                                    break-after: auto !important;
                                                    page-break-after: auto !important;
                                                }
                                                #__pdfMount [data-template="creative2"] .creative2-template,
                                                #__pdfMount .creative2-template,
                                                #__pdfMount [data-template="creative2"] .creative2-body,
                                                #__pdfMount .creative2-body {
                                                    break-inside: auto !important;
                                                    page-break-inside: auto !important;
                                                }
                                                #__pdfMount [data-template="creative2"] .creative2-template section,
                                                #__pdfMount .creative2-template section {
                                                    break-before: auto !important;
                                                    page-break-before: auto !important;
                                                    break-after: auto !important;
                                                    page-break-after: auto !important;
                                                    break-inside: auto !important;
                                                    page-break-inside: auto !important;
                                                }

                                                /* Make the main two-column layout fragmentable.
                                                     Use a float-based sidebar for print/PDF so Chromium can paginate
                                                     reliably (CSS grid pagination is inconsistent). */
                                                #__pdfMount [data-template="creative2"] .creative2-grid,
                                                #__pdfMount .creative2-grid {
                                                    display: block !important;
                                                    grid-template-columns: none !important;
                                                    gap: 0 !important;
                                                    break-inside: auto !important;
                                                    page-break-inside: auto !important;
                                                    break-before: auto !important;
                                                    page-break-before: auto !important;
                                                }
                                                #__pdfMount [data-template="creative2"] .creative2-grid::after,
                                                #__pdfMount .creative2-grid::after {
                                                    content: "" !important;
                                                    display: block !important;
                                                    clear: both !important;
                                                }

                                                #__pdfMount [data-template="creative2"] .creative2-grid > aside,
                                                #__pdfMount .creative2-grid > aside {
                                                    float: left !important;
                                                    width: 32% !important;
                                                    max-width: none !important;
                                                    break-inside: auto !important;
                                                    page-break-inside: auto !important;
                                                }
                                                #__pdfMount [data-template="creative2"] .creative2-grid > main,
                                                #__pdfMount .creative2-grid > main {
                                                    display: block !important;
                                                    margin-left: 36% !important;
                                                    max-width: none !important;
                                                    break-inside: auto !important;
                                                    page-break-inside: auto !important;
                                                }

                                                /* In two-column mode, don't add vertical stacking spacing between columns. */
                                                #__pdfMount [data-template="creative2"] .creative2-grid > * + *,
                                                #__pdfMount .creative2-grid > * + * { margin-top: 0 !important; }

                                                /* Allow long entries to split across pages.
                                                     Chromium print often treats flex rows as non-fragmentable,
                                                     which can create large bottom whitespace when an item is bumped.
                                                     Use a float-based marker so content can paginate naturally. */
                                                #__pdfMount [data-template="creative2"] .creative2-item,
                                                #__pdfMount .creative2-item {
                                                    /* flow-root contains internal floats (the bullet marker)
                                                       without clearing the outer floated sidebar column. */
                                                    display: flow-root !important;
                                                    page-break-inside: auto !important;
                                                    break-inside: auto !important;
                                                }
                                                #__pdfMount [data-template="creative2"] .creative2-item > span,
                                                #__pdfMount .creative2-item > span {
                                                    float: left !important;
                                                    margin-right: 0.75rem !important;
                                                }

                                                #__pdfMount [data-template="creative2"] .creative2-template section,
                                                #__pdfMount .creative2-template section { margin-bottom: 0.35rem !important; }
                                                #__pdfMount [data-template="creative2"] .creative2-template section h3,
                                                #__pdfMount .creative2-template section h3 { margin-bottom: 0.15rem !important; }
                                                #__pdfMount [data-template="creative2"] .creative2-template .space-y-4 > * + *,
                                                #__pdfMount .creative2-template .space-y-4 > * + * { margin-top: 0.35rem !important; }
                                                #__pdfMount [data-template="creative2"] .creative2-template .space-y-5 > * + *,
                                                #__pdfMount .creative2-template .space-y-5 > * + * { margin-top: 0.35rem !important; }
                                                #__pdfMount [data-template="creative2"] .creative2-template .space-y-2 > * + *,
                                                #__pdfMount .creative2-template .space-y-2 > * + * { margin-top: 0.2rem !important; }
                      `;

                                                                                        // Debug-only visual markers to prove whether any top whitespace is real layout
                                                                                        // (content pushed down) vs just the PDF viewer's page border.
                                                                                        if (a && a.debug) {
                                                                                                style.textContent += `
                                                                                                    html { background: #fff !important; }
                                                                                                    body::before {
                                                                                                        content: "";
                                                                                                        position: fixed;
                                                                                                        top: 0;
                                                                                                        left: 0;
                                                                                                        right: 0;
                                                                                                        height: 10px;
                                                                                                        background: #ff00ff !important;
                                                                                                        z-index: 2147483647;
                                                                                                    }
                                                                                                    #__pdfMount { outline: 2px solid #ff00ff !important; }
                                                                                                `;
                                                                                        }
                      document.head.appendChild(style);
                    }""",
                {"fontScale": font_scale,
                 "paragraphGapPx": paragraph_gap_px,
                 "spacingScale": spacing_scale, "debug": _pdf_debug},
            )
            logger.info("template_pdf print_css_ready t=%sms", _t())

            # Use print media for PDF so page-break rules apply correctly (Creative template layout).
            try:
                page.emulate_media(media="print")
            except Exception:
                pass

            # Debug (local troubleshooting): log key computed styles/positions for Creative2.
            # Helps identify cases where Chromium treats containers as non-fragmentable and pushes
            # the main content to the next page.
            # If debug mode is enabled, save a screenshot + HTML of the rendered export.
            if _pdf_debug:
                try:
                    _pdf_debug_dir = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        'temp_store',
                        'pdf_debug'
                    )
                    os.makedirs(_pdf_debug_dir, exist_ok=True)

                    safe_id = ''.join(
                        [c for c in str(canonical or 'template') if
                         c.isalnum() or c in ('-', '_')]
                    )
                    ts = int(time.time())
                    shot_path = os.path.join(
                        _pdf_debug_dir,
                        f'{safe_id}-render-{ts}.png'
                    )
                    html_path = os.path.join(
                        _pdf_debug_dir,
                        f'{safe_id}-render-{ts}.html'
                    )

                    # Screenshot the whole page; includes the magenta debug bar at y=0.
                    page.screenshot(path=shot_path, full_page=True)
                    _pdf_debug_files.append(shot_path)

                    try:
                        html = page.content() or ''
                    except Exception:
                        html = ''
                    try:
                        with open(html_path, 'w', encoding='utf-8') as f:
                            f.write(html)
                        _pdf_debug_files.append(html_path)
                    except Exception:
                        pass

                    logger.info(
                        'template_pdf debug_saved dir=%s files=%s t=%sms',
                        _pdf_debug_dir,
                        ';'.join(_pdf_debug_files),
                        _t()
                    )
                except Exception as _e:
                    try:
                        logger.info(
                            'template_pdf debug_save_failed err=%r t=%sms',
                            _e,
                            _t()
                        )
                    except Exception:
                        pass

            if canonical == 'creative2' and _pdf_debug:
                try:
                    page.wait_for_timeout(50)
                    dbg = page.evaluate(
                        """() => {
                            const pick = (sel) => document.querySelector(sel);
                            const box = (el) => {
                                if (!el) return null;
                                const r = el.getBoundingClientRect();
                                return { top: r.top, left: r.left, width: r.width, height: r.height };
                            };
                            const style = (el) => {
                                if (!el) return null;
                                const cs = window.getComputedStyle(el);
                                return {
                                    display: cs.display,
                                    paddingLeft: cs.paddingLeft,
                                    paddingRight: cs.paddingRight,
                                    paddingTop: cs.paddingTop,
                                    paddingBottom: cs.paddingBottom,
                                    breakInside: cs.breakInside || cs.getPropertyValue('break-inside'),
                                    breakBefore: cs.breakBefore || cs.getPropertyValue('break-before'),
                                    breakAfter: cs.breakAfter || cs.getPropertyValue('break-after'),
                                    pageBreakInside: cs.pageBreakInside || cs.getPropertyValue('page-break-inside'),
                                    pageBreakBefore: cs.pageBreakBefore || cs.getPropertyValue('page-break-before'),
                                    pageBreakAfter: cs.pageBreakAfter || cs.getPropertyValue('page-break-after'),
                                };
                            };

                            const mount = pick('#__pdfMount');
                            const tpl = pick('#__pdfMount [data-template="creative2"]');
                            const body = pick('#__pdfMount [data-template="creative2"] .creative2-body');
                            const header = pick('#__pdfMount [data-template="creative2"] .creative2-header');
                            const summary = pick('#__pdfMount [data-template="creative2"] .creative2-summary');
                            const grid = pick('#__pdfMount [data-template="creative2"] .creative2-grid');
                            const aside = pick('#__pdfMount [data-template="creative2"] .creative2-grid > aside');
                            const main = pick('#__pdfMount [data-template="creative2"] .creative2-grid > main');

                            const decos = Array.from(document.querySelectorAll('#__pdfMount [data-template="creative2"] .creative2-decorative'));
                            const decoInfo = decos.slice(0, 12).map((el) => {
                                const cs = window.getComputedStyle(el);
                                return {
                                    box: box(el),
                                    display: cs.display,
                                    position: cs.position,
                                    visibility: cs.visibility,
                                    opacity: cs.opacity,
                                    zIndex: cs.zIndex,
                                    backgroundColor: cs.backgroundColor,
                                    clipPath: cs.clipPath,
                                };
                            });

                            const sheetHrefs = Array.from(document.styleSheets || []).map(s => {
                                try { return s && s.href ? String(s.href) : ''; } catch (e) { return ''; }
                            }).filter(Boolean);

                            return {
                                viewport: { w: window.innerWidth, h: window.innerHeight },
                                mount: { box: box(mount), style: style(mount) },
                                tpl: { box: box(tpl), style: style(tpl) },
                                body: { box: box(body), style: style(body) },
                                header: { box: box(header), style: style(header) },
                                summary: { box: box(summary), style: style(summary) },
                                grid: { box: box(grid), style: style(grid) },
                                aside: { box: box(aside), style: style(aside) },
                                main: { box: box(main), style: style(main) },
                                decorativeCount: decos.length,
                                decorative: decoInfo,
                                styleSheets: { count: (document.styleSheets || []).length, hrefs: sheetHrefs.slice(0, 25) },
                            };
                        }"""
                    )

                    import json as _json

                    try:
                        logger.info(
                            "template_pdf creative2_debug=%s t=%sms",
                            _json.dumps(dbg, ensure_ascii=False)[:5000],
                            _t(),
                        )
                    except Exception as _e:
                        logger.info(
                            "template_pdf creative2_debug_dump_failed err=%r t=%sms",
                            _e,
                            _t()
                        )

                    try:
                        temp_dir = os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            'temp_store'
                        )
                        os.makedirs(temp_dir, exist_ok=True)

                        dbg_path = os.path.join(
                            temp_dir,
                            'creative2-debug.json'
                        )
                        try:
                            _dbg_payload = _json.dumps(
                                dbg,
                                ensure_ascii=False,
                                indent=2,
                                default=str
                            )
                        except Exception as _e:
                            _dbg_payload = _json.dumps(
                                {
                                    "error": repr(_e),
                                    "dbg_type": str(type(dbg)),
                                    "dbg_keys": list(
                                        dbg.keys()
                                    ) if isinstance(
                                        dbg,
                                        dict
                                    ) else None,
                                },
                                ensure_ascii=False,
                                indent=2,
                            )
                        with open(dbg_path, 'w', encoding='utf-8') as f:
                            f.write(_dbg_payload)
                        logger.info(
                            "template_pdf creative2_debug_file=%s t=%sms",
                            dbg_path,
                            _t()
                        )

                        try:
                            import time as _time

                            _shot_ts = int(_time.time())
                        except Exception:
                            _shot_ts = 0

                        # If the previous PNG is open in an image viewer, overwriting can fail on Windows.
                        # Always write a timestamped screenshot, and also try to update the stable filename.
                        shot_path = os.path.join(
                            temp_dir,
                            f'creative2-html-debug-{_shot_ts}.png' if _shot_ts else 'creative2-html-debug-new.png'
                        )
                        page.screenshot(path=shot_path, full_page=True)
                        try:
                            with open(
                                    os.path.join(
                                        temp_dir,
                                        'creative2-html-debug-latest.txt'
                                    ),
                                    'w',
                                    encoding='utf-8'
                            ) as _f:
                                _f.write(os.path.basename(shot_path))
                        except Exception:
                            pass
                        try:
                            stable_path = os.path.join(
                                temp_dir,
                                'creative2-html-debug.png'
                            )
                            page.screenshot(
                                path=stable_path,
                                full_page=True
                            )
                        except Exception:
                            stable_path = None
                        logger.info(
                            "template_pdf creative2_screenshot=%s stable=%s t=%sms",
                            shot_path,
                            stable_path or '',
                            _t(),
                        )
                    except Exception as _e:
                        logger.info(
                            "template_pdf creative2_debug_artifacts_failed err=%r t=%sms",
                            _e,
                            _t()
                        )
                except Exception:
                    pass

            step = "page_pdf"
            # Margins are controlled via CSS @page (supports @page:first).
            # Keep header/debug info about intended margins.
            _pdf_margin_top = "css@page(0.5in; first=0in)"
            _pdf_margin_bottom = "css@page(0.5in)"
            _pdf_margin_left = "css@page(0in)"
            _pdf_margin_right = "css@page(0in)"
            pdf_bytes = page.pdf(
                format="Letter",
                print_background=True,
            )
            logger.info(
                "template_pdf pdf_ready bytes=%s t=%sms",
                len(pdf_bytes or b""),
                _t()
            )
        finally:
            try:
                if context:
                    context.close()
            except Exception:
                pass
            # IMPORTANT: do not close the thread-local browser here; reuse it for subsequent requests.
            # The atexit handler will attempt best-effort cleanup when the worker exits.

        # Make filename unique so PDF viewers don't keep showing an already-open old tab.
        filename = f"resume-{canonical}-{str(_BUILD_ID)}.pdf"
        logger.info("template_pdf done filename=%s t=%sms", filename, _t())
        resp = send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
        # Prevent stale cached PDFs after template/CSS changes.
        try:
            resp.headers[
                "Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        except Exception:
            pass
        try:
            resp.headers["Pragma"] = "no-cache"
        except Exception:
            pass
        try:
            resp.headers["Expires"] = "0"
        except Exception:
            pass

        # Debug/verification headers (safe to leave enabled; useful for confirming which code path is hit).
        try:
            resp.headers["X-Resumatic-Build"] = str(_BUILD_ID)
        except Exception as _e:
            try:
                logger.info(
                    "template_pdf header_set_failed key=%s err=%r",
                    "X-Resumatic-Build",
                    _e
                )
            except Exception:
                pass

        # Surface server-side timing to help diagnose Azure slowness.
        try:
            resp.headers["X-Resumatic-PDF-ms"] = str(_t())
        except Exception:
            pass
        try:
            resp.headers["X-Resumatic-Template-Requested"] = str(
                template_id or ""
            )
        except Exception as _e:
            try:
                logger.info(
                    "template_pdf header_set_failed key=%s err=%r",
                    "X-Resumatic-Template-Requested",
                    _e
                )
            except Exception:
                pass
        try:
            resp.headers["X-Resumatic-Template-Canonical"] = str(
                canonical or ""
            )
        except Exception as _e:
            try:
                logger.info(
                    "template_pdf header_set_failed key=%s err=%r",
                    "X-Resumatic-Template-Canonical",
                    _e
                )
            except Exception:
                pass
        try:
            resp.headers["X-Resumatic-PDF-Margin"] = (
                f"top={_pdf_margin_top}; bottom={_pdf_margin_bottom}; "
                f"left={_pdf_margin_left}; right={_pdf_margin_right}; "
                f"build={str(_BUILD_ID)}; requested={str(template_id or '')}; canonical={str(canonical or '')}"
            )
        except Exception:
            pass

        if _pdf_debug_dir:
            try:
                resp.headers["X-Resumatic-PDF-Debug-Dir"] = str(
                    _pdf_debug_dir
                )
            except Exception:
                pass
        if _pdf_debug_files:
            try:
                resp.headers["X-Resumatic-PDF-Debug-Files"] = ';'.join(
                    [os.path.basename(p) for p in _pdf_debug_files if p]
                )
            except Exception:
                pass
        return resp
    except Exception as e:
        logger.exception(
            "template_pdf failed template=%s step=%s",
            str(template_id or ''),
            str(step or '')
        )
        msg = f"{type(e).__name__}: {str(e) or 'PDF generation failed.'} (step={step})"
        # Missing libs or Chromium launch failure: return 503 so user can retry after startup finishes.
        if any(
                x in msg for x in (
                        ".so", "libglib", "libnss", "libgtk", "libX11",
                        "shared library", "Executable doesn't exist")
        ):
            return (
                "PDF dependencies are still installing on the server. "
                "Please wait 2–3 minutes after deploy and try again.",
                503,
            )
        if "Executable doesn't exist" in msg or "playwright install" in msg:
            msg = msg + " (Try: python -m playwright install chromium)"
        return msg, 500
    finally:
        if pdf_snap_tok_cleanup:
            _pdf_snapshot_store_pop(pdf_snap_tok_cleanup)


@app.route('/api/ai/resume-edit', methods=['POST'])
def api_ai_resume_edit():
    """Rewrite a specific text field using OpenAI.

    Used by:
    - React template viewer edit mode (summary + experience descriptions)
    - Create-resume page (summary + job description helper)
    """
    try:
        payload = request.get_json(force=True, silent=True) or {}
        field_raw = str(payload.get('field') or '')
        field = field_raw.strip().lower()
        text = str(payload.get('text') or '')
        meta = payload.get('meta') or {}
        if not isinstance(meta, dict):
            meta = {}

        # Be tolerant of small client-side variations.
        field_aliases = {
            'custom': 'custom_section',
            'customs': 'custom_section',
            'customsections': 'custom_section',
            'custom_sections': 'custom_section',
            'customsection': 'custom_section',
            'custom_section_content': 'custom_section',
            'additional_section': 'custom_section',
            'additional_sections': 'custom_section',

            'project': 'project_description',
            'projects': 'project_description',
            'project_desc': 'project_description',
            'project_description': 'project_description',
            'projects_description': 'project_description',
        }
        field = field_aliases.get(field, field)

        allowed_fields = {'summary', 'experience_description',
                          'job_description', 'custom_section',
                          'project_description'}
        if field not in allowed_fields:
            return jsonify(
                {
                    "success": False,
                    "error": f"Invalid field: {field_raw.strip() or '(empty)'}",
                }
            ), 400

        text = text.strip()
        if not text:
            return jsonify(
                {"success": False, "error": "Missing text"}
            ), 400
        if len(text) > 12000:
            return jsonify(
                {"success": False, "error": "Text too long"}
            ), 400

        api_key = (os.getenv('OPENAI_API_KEY') or '').strip()
        api_key = api_key.strip('"').strip("'").strip()
        if not api_key:
            return jsonify(
                {"success": False,
                 "error": "OPENAI_API_KEY not configured"}
            ), 500

        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=60.0, max_retries=2)
        model = (os.getenv('OPENAI_RESUME_EDIT_MODEL') or 'gpt-4o').strip()

        if field == 'summary':
            jd = str(meta.get('job_description') or '').strip()
            sys_msg = (
                "You are a resume writing assistant. Rewrite text to be concise, professional, ATS-friendly, and truthful. "
                "Do NOT invent facts, metrics, tools, employers, titles, dates, or credentials. Preserve the user's meaning. "
                "Return ONLY the rewritten summary text (no commentary)."
            )
            user_msg = (
                    "Rewrite this Professional Summary. Keep it 2-4 lines (or 3-5 bullets). "
                    "Prefer strong action verbs and concrete skills mentioned in the original. "
                    "If a job description is provided, you may align wording to it WITHOUT adding new claims.\n\n"
                    + (
                        f"JOB DESCRIPTION (context only):\n{jd}\n\n" if jd else "")
                    + f"SUMMARY:\n{text}"
            )
        elif field == 'job_description':
            sys_msg = (
                "You are a helpful assistant for job seekers. Rewrite job descriptions to be clearer and easier to scan. "
                "Do NOT add requirements or responsibilities that aren't present. Preserve meaning. "
                "Return ONLY the rewritten job description text (no commentary)."
            )
            user_msg = (
                "Rewrite the following job description so it's clean and scannable. "
                "Use short paragraphs and/or bullets. Keep the same responsibilities, requirements, and technologies.\n\n"
                f"JOB DESCRIPTION:\n{text}"
            )
        elif field == 'custom_section':
            heading = str(
                meta.get('heading') or meta.get('section') or ''
            ).strip()
            sys_msg = (
                "You are a resume writing assistant. Rewrite content for a resume section to be concise, ATS-friendly, and truthful. "
                "Do NOT invent facts, metrics, titles, dates, awards, credentials, or organizations. Preserve the user's meaning. "
                "Return ONLY the rewritten content (no commentary)."
            )
            user_msg = (
                    "Rewrite the following resume section content to be more professional and scannable. "
                    "Prefer bullets where appropriate. Keep it consistent with a resume tone.\n\n"
                    + (
                        f"SECTION TITLE (context): {heading}\n\n" if heading else "")
                    + f"ORIGINAL CONTENT:\n{text}"
            )
        elif field == 'project_description':
            title = str(meta.get('title') or '').strip()
            tech = str(
                meta.get('technologies') or meta.get('tech') or ''
            ).strip()
            link = str(meta.get('link') or meta.get('url') or '').strip()
            ctx_bits = [b for b in [title, tech, link] if b]
            ctx = " | ".join(ctx_bits)
            sys_msg = (
                "You are a resume writing assistant. Rewrite project descriptions to be concise, ATS-friendly, and truthful. "
                "Do NOT invent metrics, users, performance claims, timelines, employers, or technologies not mentioned. "
                "Return ONLY the rewritten project description (no commentary)."
            )
            user_msg = (
                    "Rewrite the following project description for a resume. Keep it short and scannable. "
                    "Prefer 2-4 bullets if the original looks like bullets or spans multiple lines; otherwise use 1-2 crisp sentences. "
                    "Keep the same meaning and technologies already mentioned.\n\n"
                    + (f"PROJECT CONTEXT: {ctx}\n\n" if ctx else "")
                    + f"ORIGINAL DESCRIPTION:\n{text}"
            )
        else:
            title = str(
                meta.get('title') or meta.get('role') or ''
            ).strip()
            company = str(
                meta.get('company') or meta.get('organization') or ''
            ).strip()
            dates = str(meta.get('dates') or '').strip()
            context = " · ".join([x for x in [title, company, dates] if x])
            sys_msg = (
                "You are a resume writing assistant. Rewrite experience descriptions into strong, ATS-friendly bullets. "
                "Do NOT invent facts or metrics. If the original lacks metrics, keep it factual without adding numbers. "
                "Return ONLY the rewritten bullets, each starting with '- '."
            )
            user_msg = (
                "Rewrite the following experience description into 3-6 concise bullets. "
                "Keep the same meaning and technologies already mentioned.\n"
                f"ROLE CONTEXT: {context}\n\n"
                f"ORIGINAL DESCRIPTION:\n{text}"
            )

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.4,
            max_tokens=700 if field in {'job_description',
                                        'custom_section'} else (
                600 if field == 'project_description' else 500),
        )

        out = (resp.choices[0].message.content or '').strip()
        if not out:
            return jsonify(
                {"success": False, "error": "Empty AI response"}
            ), 502

        # Safety: keep responses bounded.
        if len(out) > 20000:
            out = out[:20000]
        return jsonify({"success": True, "text": out})

    except Exception as e:
        try:
            logger.error(
                f"AI resume edit failed: {type(e).__name__}: {str(e)}"
            )
        except Exception:
            pass
        return jsonify({"success": False, "error": "AI edit failed"}), 500


def _coach_openai_error_message(exc: Exception) -> str:
    msg = str(exc or '').strip()
    low = msg.lower()
    if 'certificate verify failed' in low or 'connection error' in low:
        return 'Could not reach OpenAI from the server. Check network/SSL configuration and OPENAI_API_KEY.'
    if 'invalid_api_key' in low or 'incorrect api key' in low:
        return 'OpenAI API key is invalid or not configured on the server.'
    if 'model' in low and ('not found' in low or 'does not exist' in low):
        return 'The configured AI model is unavailable. Set OPENAI_JOB_COACH_MODEL to a valid model (e.g. gpt-4o).'
    if msg:
        return f'Job Search Coach error: {msg[:220]}'
    return 'Job Search Coach is temporarily unavailable. Please try again.'


_JOB_COACH_MAX_OUTPUT_TOKENS = 300
_JOB_COACH_MAX_REPLY_CHARS = 2100


def _coach_chat_completion(client, messages):
    """Try the preferred coach model, then fall back to known-good models."""
    models = []
    env_model = (os.getenv('OPENAI_JOB_COACH_MODEL') or '').strip()
    if env_model:
        models.append(env_model)
    for candidate in ('gpt-5.2-2025-12-11', 'gpt-4o', 'gpt-4o-mini'):
        if candidate not in models:
            models.append(candidate)

    last_exc = None
    for model in models:
        try:
            request_kwargs = {"model": model, "messages": messages}
            if model.startswith('gpt-5'):
                request_kwargs[
                    "max_completion_tokens"] = _JOB_COACH_MAX_OUTPUT_TOKENS
            else:
                request_kwargs["temperature"] = 0.5
                request_kwargs["max_tokens"] = _JOB_COACH_MAX_OUTPUT_TOKENS
            resp = client.chat.completions.create(**request_kwargs)
            return resp, model
        except Exception as exc:
            last_exc = exc
            try:
                logger.warning(
                    "Job search coach model %s failed: %s: %s",
                    model,
                    type(exc).__name__,
                    str(exc)[:240]
                )
            except Exception:
                pass
    if last_exc is not None:
        raise last_exc
    raise RuntimeError('No AI model configured for Job Search Coach')


_ADMIN_ASSISTANT_MAX_OUTPUT_TOKENS = 700
_ADMIN_ASSISTANT_MAX_REPLY_CHARS = 4200
_ADMIN_ASSISTANT_MAX_TOOL_CALLS = 6


def _admin_assistant_error_message(exc: Exception) -> str:
    msg = str(exc or '').strip()
    low = msg.lower()
    if 'certificate verify failed' in low or 'connection error' in low:
        return 'Could not reach OpenAI from the server. Check network/SSL configuration and OPENAI_API_KEY.'
    if 'invalid_api_key' in low or 'incorrect api key' in low:
        return 'OpenAI API key is invalid or not configured on the server.'
    if msg:
        return f'Admin assistant error: {msg[:220]}'
    return 'Admin assistant is temporarily unavailable. Please try again.'


def _admin_assistant_chat_completion(client, messages, tools=None):
    """Try the preferred admin model, then fall back to known-good models."""
    models = []
    env_model = (os.getenv('OPENAI_ADMIN_ASSISTANT_MODEL') or '').strip()
    if env_model:
        models.append(env_model)
    for candidate in ('gpt-5.2-2025-12-11', 'gpt-4o', 'gpt-4o-mini'):
        if candidate not in models:
            models.append(candidate)

    last_exc = None
    for model in models:
        try:
            request_kwargs = {"model": model, "messages": messages}
            if tools:
                request_kwargs["tools"] = tools
                request_kwargs["tool_choice"] = "auto"
            if model.startswith('gpt-5'):
                request_kwargs[
                    "max_completion_tokens"] = _ADMIN_ASSISTANT_MAX_OUTPUT_TOKENS
            else:
                request_kwargs["temperature"] = 0.2
                request_kwargs[
                    "max_tokens"] = _ADMIN_ASSISTANT_MAX_OUTPUT_TOKENS
            resp = client.chat.completions.create(**request_kwargs)
            return resp, model
        except Exception as exc:
            last_exc = exc
            try:
                logger.warning(
                    "Admin assistant model %s failed: %s: %s",
                    model,
                    type(exc).__name__,
                    str(exc)[:240]
                )
            except Exception:
                pass
    if last_exc is not None:
        raise last_exc
    raise RuntimeError('No AI model configured for Admin Assistant')


def _read_admin_feedback_rows(limit: int = 100) -> list[dict]:
    rows: list[dict] = []
    safe_limit = max(1, min(int(limit or 100), 200))
    try:
        feedback_path = 'download_feedback.csv'
        if not os.path.exists(feedback_path):
            return rows
        with open(feedback_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(
                    {
                        'timestamp_iso': str(
                            row.get('timestamp_iso') or ''
                        ).strip(),
                        'user_id': str(row.get('user_id') or '').strip(),
                        'user_email': str(
                            row.get('user_email') or ''
                        ).strip(),
                        'rating': str(row.get('rating') or '').strip(),
                        'comment': str(row.get('comment') or '').strip(),
                        'comparison': str(
                            row.get('comparison') or ''
                        ).strip(),
                    }
                )
    except Exception as e:
        try:
            logger.warning(
                "Failed to read admin feedback rows: %s",
                str(e)
            )
        except Exception:
            pass
        return []
    return rows[-safe_limit:][::-1]


def _admin_assistant_slim_user_row(row: dict) -> dict:
    return {
        'user_id': str(
            row.get('user_id') or row.get('id') or row.get(
                'PartitionKey'
            ) or ''
        ).strip(),
        'email': str(row.get('email') or '').strip(),
        'name': str(row.get('name') or '').strip(),
        'provider': str(row.get('provider') or '').strip(),
        'plan_status': str(row.get('plan_status') or '').strip(),
        'is_subscriber': str(row.get('is_subscriber') or '').strip() or (
            'yes' if _profile_indicates_paid(row) else 'no'),
        'sign_up_date': str(row.get('sign_up_date') or '').strip(),
        'last_login_date': str(row.get('last_login_date') or '').strip(),
        'last_login_method': str(
            row.get('last_login_method') or ''
        ).strip(),
        'revision_count': int(
            row.get('revision_count') or row.get('revisions') or 0
        ),
    }


def _admin_assistant_json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        try:
            dt = value if value.tzinfo else value.replace(
                tzinfo=timezone.utc
            )
            return dt.isoformat()
        except Exception:
            return str(value)
    if isinstance(value, (list, tuple)):
        return [_admin_assistant_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _admin_assistant_json_safe(v) for k, v in
                value.items()}
    try:
        if hasattr(value, 'isoformat'):
            return value.isoformat()
    except Exception:
        pass
    return str(value)


def _admin_assistant_row_matches_filters(
        row: dict,
        *,
        search: str = '',
        partition_key: str = '',
        row_key: str = ''
) -> bool:
    pk_filter = str(partition_key or '').strip().lower()
    rk_filter = str(row_key or '').strip().lower()
    needle = str(search or '').strip().lower()
    pk = str(
        row.get('PartitionKey') or row.get('partition_key') or ''
    ).strip().lower()
    rk = str(row.get('RowKey') or row.get('row_key') or '').strip().lower()
    if pk_filter and pk != pk_filter:
        return False
    if rk_filter and rk != rk_filter:
        return False
    if needle:
        try:
            haystack = json.dumps(
                _admin_assistant_json_safe(row),
                ensure_ascii=False,
                default=str
            ).lower()
        except Exception:
            haystack = str(row).lower()
        if needle not in haystack:
            return False
    return True


def _admin_assistant_get_login_audit_rows(
        limit: int = 25,
        offset: int = 0,
        partition_key: str = '',
        row_key: str = '',
        search: str = ''
) -> dict:
    safe_limit = max(1, min(int(limit or 25), 100))
    safe_offset = max(0, int(offset or 0))
    rows = _azure_login_audit_list(
        limit=0
    ) if _azure_login_audit_enabled() else []
    filtered = []
    for row in rows:
        if _admin_assistant_row_matches_filters(
                row,
                search=search,
                partition_key=partition_key,
                row_key=row_key,
        ):
            filtered.append(_admin_assistant_json_safe(dict(row)))
    total = len(filtered)
    page = filtered[safe_offset:safe_offset + safe_limit]
    return {
        'table': AZURE_LOGIN_AUDIT_TABLE,
        'returned': len(page),
        'total_matching_rows': total,
        'offset': safe_offset,
        'limit': safe_limit,
        'has_more': safe_offset + safe_limit < total,
        'rows': page,
    }


def _admin_assistant_get_resume_revision_rows(
        limit: int = 25,
        offset: int = 0,
        partition_key: str = '',
        row_key: str = '',
        search: str = ''
) -> dict:
    safe_limit = max(1, min(int(limit or 25), 100))
    safe_offset = max(0, int(offset or 0))
    out = []
    try:
        table_client = get_table_client(
            'ResumeRevisions',
            create_if_missing=False
        )
        for entity in table_client.list_entities():
            try:
                row = dict(entity) if not isinstance(
                    entity,
                    dict
                ) else dict(entity)
            except Exception:
                continue
            if _admin_assistant_row_matches_filters(
                    row,
                    search=search,
                    partition_key=partition_key,
                    row_key=row_key,
            ):
                out.append(_admin_assistant_json_safe(row))
    except Exception as e:
        return {
            'table': 'ResumeRevisions',
            'returned': 0,
            'total_matching_rows': 0,
            'offset': safe_offset,
            'limit': safe_limit,
            'has_more': False,
            'rows': [],
            'error': str(e)[:220],
        }
    try:
        out.sort(
            key=lambda r: str(
                r.get('timestamp') or r.get('Timestamp') or ''
            ),
            reverse=True,
        )
    except Exception:
        pass
    total = len(out)
    page = out[safe_offset:safe_offset + safe_limit]
    return {
        'table': 'ResumeRevisions',
        'returned': len(page),
        'total_matching_rows': total,
        'offset': safe_offset,
        'limit': safe_limit,
        'has_more': safe_offset + safe_limit < total,
        'rows': page,
    }


def _admin_assistant_normalize_select(select) -> list[str]:
    if isinstance(select, str):
        parts = [p.strip() for p in select.split(',')]
    elif isinstance(select, list):
        parts = [str(p or '').strip() for p in select]
    else:
        parts = []
    out = []
    seen = set()
    for part in parts:
        if not part or part in seen:
            continue
        seen.add(part)
        out.append(part)
    return out[:25]


def _admin_assistant_query_table_rows(
        table_name: str,
        *,
        filter_text: str = '',
        select=None,
        top: int = 25,
        offset: int = 0,
        sort_field: str = ''
) -> dict:
    safe_top = max(1, min(int(top or 25), 100))
    safe_offset = max(0, min(int(offset or 0), 5000))
    safe_filter = str(filter_text or '').strip()
    safe_select = _admin_assistant_normalize_select(select)
    safe_sort_field = str(sort_field or '').strip()

    try:
        if table_name == AZURE_LOGIN_AUDIT_TABLE:
            table_client = _get_login_audit_table_client(
                create_if_missing=False
            )
        else:
            table_client = get_table_client(
                table_name,
                create_if_missing=False
            )

        if safe_filter:
            pager = table_client.query_entities(
                safe_filter,
                select=safe_select or None
            )
        else:
            pager = table_client.list_entities(select=safe_select or None)

        rows = []
        for entity in pager:
            try:
                rows.append(
                    _admin_assistant_json_safe(
                        dict(entity) if not isinstance(
                            entity,
                            dict
                        ) else dict(entity)
                    )
                )
            except Exception:
                continue

        if safe_sort_field:
            try:
                rows.sort(
                    key=lambda r: str(r.get(safe_sort_field) or ''),
                    reverse=True
                )
            except Exception:
                pass

        total = len(rows)
        page = rows[safe_offset:safe_offset + safe_top]
        return {
            'table': table_name,
            'filter': safe_filter,
            'select': safe_select,
            'returned': len(page),
            'total_matching_rows': total,
            'offset': safe_offset,
            'top': safe_top,
            'has_more': safe_offset + safe_top < total,
            'rows': page,
        }
    except Exception as e:
        return {
            'table': table_name,
            'filter': safe_filter,
            'select': safe_select,
            'returned': 0,
            'total_matching_rows': 0,
            'offset': safe_offset,
            'top': safe_top,
            'has_more': False,
            'rows': [],
            'error': str(e)[:300],
        }


def _admin_assistant_find_user_profile(user_identifier: str) -> Optional[
    dict]:
    needle = str(user_identifier or '').strip().lower()
    if not needle:
        return None
    rows, _, _ = _collect_registered_users_from_azure_users_table()
    exact_email = None
    exact_id = None
    partial = None
    for row in rows:
        uid = str(row.get('id') or row.get('PartitionKey') or '').strip()
        email = str(row.get('email') or '').strip()
        name = str(row.get('name') or '').strip()
        if uid.lower() == needle:
            exact_id = row
            break
        if email.lower() == needle:
            exact_email = row
        if partial is None and needle in f"{uid} {email} {name}".lower():
            partial = row
    return exact_id or exact_email or partial


def _admin_assistant_tool_inventory() -> dict:
    return {
        'available_sources': [
            'visit analytics summary',
            'login audit summary and recent sessions',
            'full Azure LoginAudit table rows',
            'registered users from Azure Users table',
            'resume revision counts and per-user recent revisions',
            'full Azure ResumeRevisions table rows',
            'download feedback CSV',
            'subscription and reconciliation dashboard data',
            'Stripe customers, subscriptions, invoices, and charges',
        ],
        'read_only': True,
        'notes': [
            'The assistant uses curated server-side tools, not raw arbitrary table queries.',
            'The assistant can issue controlled read-only Azure Table queries for LoginAudit and ResumeRevisions.',
            'Stripe access is read-only and exposed through curated server-side tools.',
            'Large result sets are summarized or capped to keep responses reliable.',
        ],
    }


def _admin_assistant_get_stats_overview() -> dict:
    analytics_data = analytics.get_full_analytics() or {}
    summary = analytics_data.get('summary') if isinstance(
        analytics_data,
        dict
    ) else {}
    login_audit_sessions, _, _, _ = _load_login_audit_sessions_for_admin()
    login_summary = _build_login_new_vs_returning_summary(
        login_audit_sessions
    )
    feedback_rows = _read_admin_feedback_rows(limit=100)
    return {
        'visit_summary': {
            'total_visits': int((summary or {}).get('total_visits') or 0),
            'facebook_ad_visits': int(
                (summary or {}).get('facebook_ad_visits') or 0
            ),
            'organic_visits': int(
                (summary or {}).get('organic_visits') or 0
            ),
            'total_conversions': int(
                (summary or {}).get('total_conversions') or 0
            ),
            'facebook_ad_conversions': int(
                (summary or {}).get('facebook_ad_conversions') or 0
            ),
            'last_updated': str(
                (summary or {}).get('last_updated') or ''
            ).strip(),
        },
        'login_summary': login_summary,
        'feedback_summary': {
            'recent_feedback_rows_loaded': len(feedback_rows),
            'latest_feedback_timestamp': str(
                feedback_rows[0].get('timestamp_iso') or ''
            ).strip() if feedback_rows else '',
        },
    }


def _admin_assistant_search_users(
        search: str = '',
        plan_status: str = '',
        limit: int = 10
) -> dict:
    safe_limit = max(1, min(int(limit or 10), 25))
    needle = str(search or '').strip().lower()
    plan_filter = str(plan_status or '').strip().lower()
    rows = _collect_registered_users_activity_rows()
    matches = []
    for row in rows:
        row_plan = str(row.get('plan_status') or '').strip().lower()
        if plan_filter and row_plan != plan_filter:
            continue
        haystack = ' '.join(
            [
                str(row.get('user_id') or ''),
                str(row.get('email') or ''),
                str(row.get('name') or ''),
                str(row.get('provider') or ''),
                str(row.get('plan_status') or ''),
            ]
        ).lower()
        if needle and needle not in haystack:
            continue
        matches.append(_admin_assistant_slim_user_row(row))
        if len(matches) >= safe_limit:
            break
    return {
        'query': search,
        'plan_status': plan_status,
        'returned': len(matches),
        'users': matches,
    }


def _admin_assistant_get_user_detail(
        user_identifier: str,
        revision_limit: int = 5
) -> dict:
    safe_limit = max(1, min(int(revision_limit or 5), 10))
    profile = _admin_assistant_find_user_profile(user_identifier)
    if not profile:
        return {'found': False, 'user_identifier': user_identifier}

    uid = str(
        profile.get('id') or profile.get('PartitionKey') or ''
    ).strip()
    signup_lookup = _build_signup_lookup_from_csv()
    login_lookup = _build_last_login_lookup()
    revisions = get_user_revisions(uid) or []
    last_login_at, last_login_method = _resolve_user_last_login(
        uid,
        profile,
        login_lookup
    )
    applications = []
    total_applications = 0
    for rev in revisions:
        apps = rev.get('applications') or []
        total_applications += len(apps)
        for app in apps[:5]:
            applications.append(
                {
                    'revision_name': str(
                        rev.get('revision_name') or ''
                    ).strip(),
                    'company': str(app.get('company') or '').strip(),
                    'role': str(app.get('role') or '').strip(),
                    'status': str(app.get('status') or '').strip(),
                    'date_applied': str(
                        app.get('date_applied') or ''
                    ).strip(),
                    'follow_up_date': str(
                        app.get('follow_up_date') or ''
                    ).strip(),
                }
            )
            if len(applications) >= 10:
                break
        if len(applications) >= 10:
            break

    recent_revisions = []
    for rev in revisions[:safe_limit]:
        recent_revisions.append(
            {
                'revision_id': str(rev.get('revision_id') or '').strip(),
                'revision_name': str(
                    rev.get('revision_name') or ''
                ).strip(),
                'timestamp': _coerce_datetime_iso(rev.get('timestamp')),
                'notes_present': bool(str(rev.get('notes') or '').strip()),
                'job_description_present': bool(
                    str(rev.get('job_description') or '').strip()
                ),
                'applications_count': int(
                    rev.get('applications_count') or 0
                ),
            }
        )

    return {
        'found': True,
        'user': {
            'user_id': uid,
            'email': str(profile.get('email') or '').strip(),
            'name': str(profile.get('name') or '').strip(),
            'provider': str(profile.get('provider') or '').strip(),
            'plan_status': str(profile.get('plan_status') or '').strip(),
            'is_paid': bool(_profile_indicates_paid(profile)),
            'sign_up_date': _format_any_datetime_pacific(
                _resolve_user_signup_date(uid, profile, signup_lookup)
            ),
            'last_login_date': _format_any_datetime_pacific(
                last_login_at
            ) or str(last_login_at or '').strip(),
            'last_login_method': str(last_login_method or '').strip(),
            'revision_count': len(revisions),
            'application_count': total_applications,
        },
        'recent_revisions': recent_revisions,
        'recent_applications': applications,
    }


def _admin_assistant_get_subscription_reconciliation(
        limit: int = 10
) -> dict:
    safe_limit = max(1, min(int(limit or 10), 25))
    dashboard = _collect_admin_dashboard_data()
    subscribers = dashboard.get('subscribers') or []
    return {
        'kpis': dashboard.get('kpis') or {},
        'reconciliation': dashboard.get('reconciliation') or {},
        'sample_subscribers': subscribers[:safe_limit],
    }


def _admin_assistant_stripe_unavailable() -> dict:
    return {
        'available': False,
        'error': 'stripe_not_configured',
        'message': 'Stripe is not configured on the server.',
    }


def _admin_assistant_stripe_object_id(value) -> str:
    if not value:
        return ''
    if isinstance(value, str):
        return value.strip()
    return str(_stripe_obj_get(value, 'id', '') or '').strip()


def _admin_assistant_stripe_timestamp_to_iso(ts) -> str:
    try:
        if ts in (None, ''):
            return ''
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except Exception:
        return ''


def _admin_assistant_stripe_metadata(
        meta,
        max_items: int = 12,
        max_value_len: int = 160
) -> dict:
    if not meta:
        return {}
    try:
        items = meta.items() if isinstance(meta, dict) else dict(
            meta
        ).items()
    except Exception:
        return {}
    out = {}
    for key, value in items:
        safe_key = str(key or '').strip()
        if not safe_key:
            continue
        safe_value = str(value or '').strip()
        if len(safe_value) > max_value_len:
            safe_value = safe_value[:max_value_len].rstrip() + '...'
        out[safe_key] = safe_value
        if len(out) >= max(1, int(max_items or 12)):
            break
    return out


def _admin_assistant_stripe_price_summary(price) -> dict:
    if not price:
        return {}
    recurring = _stripe_obj_get(price, 'recurring', None) or {}
    return {
        'price_id': str(_stripe_obj_get(price, 'id', '') or '').strip(),
        'nickname': str(
            _stripe_obj_get(price, 'nickname', '') or ''
        ).strip(),
        'currency': str(
            _stripe_obj_get(price, 'currency', '') or ''
        ).strip().lower(),
        'unit_amount': int(_stripe_obj_get(price, 'unit_amount', 0) or 0),
        'product_id': _admin_assistant_stripe_object_id(
            _stripe_obj_get(price, 'product', None)
        ),
        'interval': str(
            _stripe_obj_get(recurring, 'interval', '') or ''
        ).strip(),
        'interval_count': int(
            _stripe_obj_get(recurring, 'interval_count', 0) or 0
        ),
    }


def _admin_assistant_stripe_customer_summary(customer) -> dict:
    return {
        'customer_id': str(
            _stripe_obj_get(customer, 'id', '') or ''
        ).strip(),
        'email': str(_stripe_obj_get(customer, 'email', '') or '').strip(),
        'name': str(_stripe_obj_get(customer, 'name', '') or '').strip(),
        'description': str(
            _stripe_obj_get(customer, 'description', '') or ''
        ).strip(),
        'created': _admin_assistant_stripe_timestamp_to_iso(
            _stripe_obj_get(customer, 'created', None)
        ),
        'currency': str(
            _stripe_obj_get(customer, 'currency', '') or ''
        ).strip().lower(),
        'balance': int(_stripe_obj_get(customer, 'balance', 0) or 0),
        'delinquent': bool(_stripe_obj_get(customer, 'delinquent', False)),
        'tax_exempt': str(
            _stripe_obj_get(customer, 'tax_exempt', '') or ''
        ).strip(),
        'metadata': _admin_assistant_stripe_metadata(
            _stripe_obj_get(customer, 'metadata', {}) or {}
        ),
    }


def _admin_assistant_stripe_subscription_summary(sub) -> dict:
    price_to_plan = _build_stripe_price_to_plan_map()
    items = []
    items_data = _stripe_obj_get(
        _stripe_obj_get(sub, 'items', None),
        'data',
        []
    ) or []
    for item in list(items_data)[:5]:
        items.append(
            {
                'item_id': str(
                    _stripe_obj_get(item, 'id', '') or ''
                ).strip(),
                'quantity': int(_stripe_obj_get(item, 'quantity', 0) or 0),
                'price': _admin_assistant_stripe_price_summary(
                    _stripe_obj_get(item, 'price', None)
                ),
            }
        )
    return {
        'subscription_id': str(
            _stripe_obj_get(sub, 'id', '') or ''
        ).strip(),
        'customer_id': _admin_assistant_stripe_object_id(
            _stripe_obj_get(sub, 'customer', None)
        ),
        'status': str(
            _stripe_obj_get(sub, 'status', '') or ''
        ).strip().lower(),
        'product_purchased': _describe_stripe_subscription_product(
            sub,
            price_to_plan
        ),
        'created': _admin_assistant_stripe_timestamp_to_iso(
            _stripe_obj_get(sub, 'created', None)
        ),
        'current_period_start': _admin_assistant_stripe_timestamp_to_iso(
            _stripe_obj_get(sub, 'current_period_start', None)
        ),
        'current_period_end': _admin_assistant_stripe_timestamp_to_iso(
            _stripe_obj_get(sub, 'current_period_end', None)
        ),
        'trial_start': _admin_assistant_stripe_timestamp_to_iso(
            _stripe_obj_get(sub, 'trial_start', None)
        ),
        'trial_end': _admin_assistant_stripe_timestamp_to_iso(
            _stripe_obj_get(sub, 'trial_end', None)
        ),
        'cancel_at_period_end': bool(
            _stripe_obj_get(sub, 'cancel_at_period_end', False)
        ),
        'cancel_at': _admin_assistant_stripe_timestamp_to_iso(
            _stripe_obj_get(sub, 'cancel_at', None)
        ),
        'canceled_at': _admin_assistant_stripe_timestamp_to_iso(
            _stripe_obj_get(sub, 'canceled_at', None)
        ),
        'ended_at': _admin_assistant_stripe_timestamp_to_iso(
            _stripe_obj_get(sub, 'ended_at', None)
        ),
        'schedule_id': _stripe_schedule_id_from_subscription(sub),
        'latest_invoice_id': _admin_assistant_stripe_object_id(
            _stripe_obj_get(sub, 'latest_invoice', None)
        ),
        'default_payment_method_id': _admin_assistant_stripe_object_id(
            _stripe_obj_get(sub, 'default_payment_method', None)
        ),
        'metadata': _admin_assistant_stripe_metadata(
            _stripe_obj_get(sub, 'metadata', {}) or {}
        ),
        'items': items,
    }


def _admin_assistant_stripe_invoice_summary(inv) -> dict:
    lines = _stripe_obj_get(
        _stripe_obj_get(inv, 'lines', None),
        'data',
        []
    ) or []
    line_items = []
    for line in list(lines)[:5]:
        line_items.append(
            {
                'description': str(
                    _stripe_obj_get(line, 'description', '') or ''
                ).strip(),
                'amount': int(_stripe_obj_get(line, 'amount', 0) or 0),
                'currency': str(
                    _stripe_obj_get(line, 'currency', '') or ''
                ).strip().lower(),
                'period_start': _admin_assistant_stripe_timestamp_to_iso(
                    _stripe_obj_get(
                        _stripe_obj_get(line, 'period', None),
                        'start',
                        None
                    )
                ),
                'period_end': _admin_assistant_stripe_timestamp_to_iso(
                    _stripe_obj_get(
                        _stripe_obj_get(line, 'period', None),
                        'end',
                        None
                    )
                ),
            }
        )
    return {
        'invoice_id': str(_stripe_obj_get(inv, 'id', '') or '').strip(),
        'status': str(
            _stripe_obj_get(inv, 'status', '') or ''
        ).strip().lower(),
        'collection_method': str(
            _stripe_obj_get(inv, 'collection_method', '') or ''
        ).strip(),
        'billing_reason': str(
            _stripe_obj_get(inv, 'billing_reason', '') or ''
        ).strip(),
        'currency': str(
            _stripe_obj_get(inv, 'currency', '') or ''
        ).strip().lower(),
        'amount_due': int(_stripe_obj_get(inv, 'amount_due', 0) or 0),
        'amount_paid': int(_stripe_obj_get(inv, 'amount_paid', 0) or 0),
        'amount_remaining': int(
            _stripe_obj_get(inv, 'amount_remaining', 0) or 0
        ),
        'subtotal': int(_stripe_obj_get(inv, 'subtotal', 0) or 0),
        'total': int(_stripe_obj_get(inv, 'total', 0) or 0),
        'paid': bool(_stripe_obj_get(inv, 'paid', False)),
        'attempted': bool(_stripe_obj_get(inv, 'attempted', False)),
        'attempt_count': int(
            _stripe_obj_get(inv, 'attempt_count', 0) or 0
        ),
        'customer_id': _admin_assistant_stripe_object_id(
            _stripe_obj_get(inv, 'customer', None)
        ),
        'subscription_id': _admin_assistant_stripe_object_id(
            _stripe_obj_get(inv, 'subscription', None)
        ),
        'charge_id': _admin_assistant_stripe_object_id(
            _stripe_obj_get(inv, 'charge', None)
        ),
        'payment_intent_id': _admin_assistant_stripe_object_id(
            _stripe_obj_get(inv, 'payment_intent', None)
        ),
        'created': _admin_assistant_stripe_timestamp_to_iso(
            _stripe_obj_get(inv, 'created', None)
        ),
        'period_start': _admin_assistant_stripe_timestamp_to_iso(
            _stripe_obj_get(inv, 'period_start', None)
        ),
        'period_end': _admin_assistant_stripe_timestamp_to_iso(
            _stripe_obj_get(inv, 'period_end', None)
        ),
        'hosted_invoice_url': str(
            _stripe_obj_get(inv, 'hosted_invoice_url', '') or ''
        ).strip(),
        'invoice_pdf': str(
            _stripe_obj_get(inv, 'invoice_pdf', '') or ''
        ).strip(),
        'line_items': line_items,
    }


def _admin_assistant_stripe_charge_summary(charge) -> dict:
    refunds = _stripe_obj_get(
        _stripe_obj_get(charge, 'refunds', None),
        'data',
        []
    ) or []
    refund_rows = []
    for refund in list(refunds)[:5]:
        refund_rows.append(
            {
                'refund_id': str(
                    _stripe_obj_get(refund, 'id', '') or ''
                ).strip(),
                'status': str(
                    _stripe_obj_get(refund, 'status', '') or ''
                ).strip(),
                'amount': int(_stripe_obj_get(refund, 'amount', 0) or 0),
                'currency': str(
                    _stripe_obj_get(refund, 'currency', '') or ''
                ).strip().lower(),
                'created': _admin_assistant_stripe_timestamp_to_iso(
                    _stripe_obj_get(refund, 'created', None)
                ),
            }
        )
    billing_details = _stripe_obj_get(
        charge,
        'billing_details',
        None
    ) or {}
    return {
        'charge_id': str(_stripe_obj_get(charge, 'id', '') or '').strip(),
        'status': str(
            _stripe_obj_get(charge, 'status', '') or ''
        ).strip().lower(),
        'currency': str(
            _stripe_obj_get(charge, 'currency', '') or ''
        ).strip().lower(),
        'amount': int(_stripe_obj_get(charge, 'amount', 0) or 0),
        'amount_captured': int(
            _stripe_obj_get(charge, 'amount_captured', 0) or 0
        ),
        'amount_refunded': int(
            _stripe_obj_get(charge, 'amount_refunded', 0) or 0
        ),
        'paid': bool(_stripe_obj_get(charge, 'paid', False)),
        'captured': bool(_stripe_obj_get(charge, 'captured', False)),
        'refunded': bool(_stripe_obj_get(charge, 'refunded', False)),
        'customer_id': _admin_assistant_stripe_object_id(
            _stripe_obj_get(charge, 'customer', None)
        ),
        'invoice_id': _admin_assistant_stripe_object_id(
            _stripe_obj_get(charge, 'invoice', None)
        ),
        'payment_intent_id': _admin_assistant_stripe_object_id(
            _stripe_obj_get(charge, 'payment_intent', None)
        ),
        'created': _admin_assistant_stripe_timestamp_to_iso(
            _stripe_obj_get(charge, 'created', None)
        ),
        'description': str(
            _stripe_obj_get(charge, 'description', '') or ''
        ).strip(),
        'failure_code': str(
            _stripe_obj_get(charge, 'failure_code', '') or ''
        ).strip(),
        'failure_message': str(
            _stripe_obj_get(charge, 'failure_message', '') or ''
        ).strip(),
        'receipt_url': str(
            _stripe_obj_get(charge, 'receipt_url', '') or ''
        ).strip(),
        'billing_email': str(
            _stripe_obj_get(billing_details, 'email', '') or ''
        ).strip(),
        'refunds': refund_rows,
    }


def _admin_assistant_pick_customer_subscription(customer_id: str):
    cid = str(customer_id or '').strip()
    if not cid or not _stripe_enabled():
        return None
    try:

        res = stripe.Subscription.list(
            customer=cid,
            status='all',
            limit=10,
            expand=['data.items.data.price']
        )
        subs = list(getattr(res, 'data', []) or [])
        if not subs:
            return None
        for sub in subs:
            status = str(
                _stripe_obj_get(sub, 'status', '') or ''
            ).strip().lower()
            if status in ('active', 'trialing', 'past_due', 'unpaid'):
                return sub
        return subs[0]
    except Exception:
        return None


def _admin_assistant_resolve_stripe_context(
        user_identifier: str = '',
        customer_id: str = '',
        subscription_id: str = '',
) -> dict:
    profile = None
    email = ''
    uid = ''
    if user_identifier:
        profile = _admin_assistant_find_user_profile(user_identifier)
        if profile:
            uid = str(
                profile.get('id') or profile.get('PartitionKey') or ''
            ).strip()
            email = str(profile.get('email') or '').strip().lower()

    resolved_customer_id = str(customer_id or '').strip()
    resolved_subscription_id = str(subscription_id or '').strip()

    if not resolved_customer_id and profile:
        resolved_customer_id = str(
            profile.get('stripe_customer_id') or ''
        ).strip()
    if not resolved_subscription_id and profile:
        resolved_subscription_id = str(
            profile.get('stripe_subscription_id') or ''
        ).strip()

    if not resolved_customer_id and email:
        resolved_customer_id = _find_stripe_customer_id_by_email(
            email,
            require_subscription_history=False,
            allow_ephemeral=True,
        )

    if not resolved_subscription_id and resolved_customer_id:
        best_sub = _admin_assistant_pick_customer_subscription(
            resolved_customer_id
        )
        if best_sub is not None:
            resolved_subscription_id = str(
                _stripe_obj_get(best_sub, 'id', '') or ''
            ).strip()

    return {
        'profile_found': bool(profile),
        'user_id': uid,
        'email': email,
        'customer_id': resolved_customer_id,
        'subscription_id': resolved_subscription_id,
    }


def _admin_assistant_search_stripe_customers(
        search: str = '',
        limit: int = 10
) -> dict:
    safe_limit = max(1, min(int(limit or 10), 25))
    needle = str(search or '').strip().lower()
    if not _stripe_enabled():
        return _admin_assistant_stripe_unavailable()

    try:

        candidates = []
        seen = set()

        def _append(customer) -> None:
            cid = str(_stripe_obj_get(customer, 'id', '') or '').strip()
            if cid and cid not in seen:
                seen.add(cid)
                candidates.append(customer)

        if needle.startswith('cus_'):
            try:
                customer = stripe.Customer.retrieve(needle)
                if customer:
                    _append(customer)
            except Exception:
                pass

        if '@' in needle:
            try:
                exact = stripe.Customer.list(
                    email=needle,
                    limit=safe_limit
                )
                for customer in list(getattr(exact, 'data', []) or []):
                    _append(customer)
            except Exception:
                pass

        fetch_limit = min(max(safe_limit * 4, 25), 100)
        if len(candidates) < safe_limit:
            try:
                recent = stripe.Customer.list(limit=fetch_limit)
                for customer in list(getattr(recent, 'data', []) or []):
                    haystack = ' '.join(
                        [
                            str(_stripe_obj_get(customer, 'id', '') or ''),
                            str(
                                _stripe_obj_get(
                                    customer,
                                    'email',
                                    ''
                                ) or ''
                            ),
                            str(
                                _stripe_obj_get(customer, 'name', '') or ''
                            ),
                            str(
                                _stripe_obj_get(
                                    customer,
                                    'description',
                                    ''
                                ) or ''
                            ),
                        ]
                    ).lower()
                    if needle and needle not in haystack:
                        continue
                    _append(customer)
                    if len(candidates) >= safe_limit:
                        break
            except Exception as exc:
                return {
                    'error': f'Unable to search Stripe customers: {str(exc)[:220]}'}

        return {
            'search': search,
            'returned': min(len(candidates), safe_limit),
            'customers': [_admin_assistant_stripe_customer_summary(c) for c
                          in candidates[:safe_limit]],
            'search_window_limited': True,
        }
    except Exception as exc:
        return {
            'error': f'Unable to search Stripe customers: {str(exc)[:220]}'}


def _admin_assistant_get_stripe_customer_detail(
        customer_id: str = '',
        user_identifier: str = ''
) -> dict:
    if not _stripe_enabled():
        return _admin_assistant_stripe_unavailable()

    ctx = _admin_assistant_resolve_stripe_context(
        user_identifier=user_identifier,
        customer_id=customer_id
    )
    cid = str(ctx.get('customer_id') or '').strip()
    if not cid:
        return {
            'found': False,
            'customer_id': customer_id,
            'user_identifier': user_identifier,
            'message': 'No Stripe customer could be resolved from the provided input.',
        }

    try:

        customer = stripe.Customer.retrieve(cid)
        latest_sub = _admin_assistant_pick_customer_subscription(cid)
        return {
            'found': True,
            'resolved_from': ctx,
            'customer': _admin_assistant_stripe_customer_summary(customer),
            'latest_subscription': _admin_assistant_stripe_subscription_summary(
                latest_sub
            ) if latest_sub else None,
        }
    except Exception as exc:
        return {'found': False, 'customer_id': cid,
                'error': str(exc)[:220]}


def _admin_assistant_get_stripe_subscription_detail(
        subscription_id: str = '',
        user_identifier: str = ''
) -> dict:
    if not _stripe_enabled():
        return _admin_assistant_stripe_unavailable()

    ctx = _admin_assistant_resolve_stripe_context(
        user_identifier=user_identifier,
        subscription_id=subscription_id,
    )
    sid = str(ctx.get('subscription_id') or '').strip()
    if not sid:
        return {
            'found': False,
            'subscription_id': subscription_id,
            'user_identifier': user_identifier,
            'message': 'No Stripe subscription could be resolved from the provided input.',
        }

    try:

        sub = stripe.Subscription.retrieve(
            sid,
            expand=['items.data.price', 'latest_invoice']
        )
        latest_invoice = _stripe_obj_get(sub, 'latest_invoice', None)
        if latest_invoice and not isinstance(latest_invoice, str):
            latest_invoice_summary = _admin_assistant_stripe_invoice_summary(
                latest_invoice
            )
        else:
            latest_invoice_obj = _stripe_latest_invoice_for_subscription(
                sid
            )
            latest_invoice_summary = _admin_assistant_stripe_invoice_summary(
                latest_invoice_obj
            ) if latest_invoice_obj else None
        return {
            'found': True,
            'resolved_from': ctx,
            'subscription': _admin_assistant_stripe_subscription_summary(
                sub
            ),
            'latest_invoice': latest_invoice_summary,
        }
    except Exception as exc:
        return {'found': False, 'subscription_id': sid,
                'error': str(exc)[:220]}


def _admin_assistant_list_stripe_invoices(
        customer_id: str = '',
        subscription_id: str = '',
        user_identifier: str = '',
        limit: int = 10,
) -> dict:
    safe_limit = max(1, min(int(limit or 10), 25))
    if not _stripe_enabled():
        return _admin_assistant_stripe_unavailable()

    ctx = _admin_assistant_resolve_stripe_context(
        user_identifier=user_identifier,
        customer_id=customer_id,
        subscription_id=subscription_id,
    )
    cid = str(ctx.get('customer_id') or '').strip()
    sid = str(ctx.get('subscription_id') or '').strip()
    if not cid and not sid:
        return {
            'returned': 0,
            'message': 'No Stripe customer or subscription could be resolved from the provided input.',
            'resolved_from': ctx,
        }

    try:

        params = {'limit': safe_limit,
                  'expand': ['data.charge', 'data.payment_intent']}
        if sid:
            params['subscription'] = sid
        elif cid:
            params['customer'] = cid
        invoices = stripe.Invoice.list(**params)
        rows = [_admin_assistant_stripe_invoice_summary(inv) for inv in
                list(getattr(invoices, 'data', []) or [])]
        return {
            'resolved_from': ctx,
            'returned': len(rows),
            'invoices': rows,
        }
    except Exception as exc:
        return {
            'error': f'Unable to list Stripe invoices: {str(exc)[:220]}'}


def _admin_assistant_list_stripe_charges(
        customer_id: str = '',
        subscription_id: str = '',
        user_identifier: str = '',
        limit: int = 10,
) -> dict:
    safe_limit = max(1, min(int(limit or 10), 25))
    if not _stripe_enabled():
        return _admin_assistant_stripe_unavailable()

    ctx = _admin_assistant_resolve_stripe_context(
        user_identifier=user_identifier,
        customer_id=customer_id,
        subscription_id=subscription_id,
    )
    cid = str(ctx.get('customer_id') or '').strip()
    sid = str(ctx.get('subscription_id') or '').strip()

    try:

        charges = []
        seen = set()

        def _append(charge) -> None:
            charge_id = str(
                _stripe_obj_get(charge, 'id', '') or ''
            ).strip()
            if charge_id and charge_id not in seen:
                seen.add(charge_id)
                charges.append(charge)

        if sid:
            invs = stripe.Invoice.list(
                subscription=sid,
                limit=min(max(safe_limit * 2, 10), 50),
                expand=['data.charge']
            )
            for inv in list(getattr(invs, 'data', []) or []):
                charge_obj = _stripe_obj_get(inv, 'charge', None)
                if charge_obj and not isinstance(charge_obj, str):
                    _append(charge_obj)
                    if len(charges) >= safe_limit:
                        break
                charge_id = _admin_assistant_stripe_object_id(charge_obj)
                if charge_id and len(charges) < safe_limit:
                    try:
                        _append(stripe.Charge.retrieve(charge_id))
                    except Exception:
                        pass
            if not charges and cid:
                res = stripe.Charge.list(customer=cid, limit=safe_limit)
                for charge in list(getattr(res, 'data', []) or []):
                    _append(charge)
        elif cid:
            res = stripe.Charge.list(customer=cid, limit=safe_limit)
            for charge in list(getattr(res, 'data', []) or []):
                _append(charge)
        else:
            return {
                'returned': 0,
                'message': 'No Stripe customer or subscription could be resolved from the provided input.',
                'resolved_from': ctx,
            }

        rows = [_admin_assistant_stripe_charge_summary(c) for c in
                charges[:safe_limit]]
        return {
            'resolved_from': ctx,
            'returned': len(rows),
            'charges': rows,
        }
    except Exception as exc:
        return {
            'error': f'Unable to list Stripe charges: {str(exc)[:220]}'}


def _admin_assistant_get_recent_feedback(limit: int = 10) -> dict:
    safe_limit = max(1, min(int(limit or 10), 25))
    rows = _read_admin_feedback_rows(limit=safe_limit)
    return {
        'returned': len(rows),
        'feedback': rows,
    }


def _admin_assistant_get_recent_logins(
        days: int = 7,
        limit: int = 20
) -> dict:
    safe_days = max(1, min(int(days or 7), 90))
    safe_limit = max(1, min(int(limit or 20), 50))
    sessions_list, _, _, _ = _load_login_audit_sessions_for_admin()
    cutoff = datetime.now(timezone.utc) - timedelta(days=safe_days)
    rows = []
    for rec in sessions_list:
        login_dt = _login_at_from_audit_record(rec)
        if login_dt is None or login_dt < cutoff:
            continue
        rows.append(
            {
                'user_id': str(rec.get('user_id') or '').strip(),
                'email': str(rec.get('email') or '').strip(),
                'login_at': _coerce_datetime_iso(login_dt),
                'login_time_pacific': _format_any_datetime_pacific(
                    login_dt
                ),
                'login_method': str(rec.get('login_method') or '').strip(),
                'last_activity_at': _coerce_datetime_iso(
                    rec.get('last_activity_at')
                ),
                'logout_at': _coerce_datetime_iso(rec.get('logout_at')),
            }
        )
    rows.sort(key=lambda r: str(r.get('login_at') or ''), reverse=True)
    return {
        'days': safe_days,
        'returned': min(len(rows), safe_limit),
        'rows': rows[:safe_limit],
    }


def _admin_assistant_send_email(
        recipient: str,
        subject: str,
        body: str,
        confirm_send: bool = False
) -> dict:
    email = str(recipient or '').strip().lower()
    subj = str(subject or '').strip()
    text_body = str(body or '').strip()
    admin_id = str(getattr(current_user, 'id', '') or '').strip()
    admin_email = str(
        getattr(current_user, 'email', '') or ''
    ).strip().lower()

    if not confirm_send:
        return {
            'sent': False,
            'error': 'confirm_send_required',
            'message': 'The user must explicitly confirm sending before this tool may send email.',
        }
    if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return {'sent': False, 'error': 'invalid_recipient'}
    if not subj:
        return {'sent': False, 'error': 'missing_subject'}
    if not text_body:
        return {'sent': False, 'error': 'missing_body'}
    if len(subj) > 200:
        return {'sent': False, 'error': 'subject_too_long'}
    if len(text_body) > 12000:
        return {'sent': False, 'error': 'body_too_long'}

    try:
        _load_email_config_if_missing()
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        auth_email = (
                os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip(
            '"'
        ).strip("'")
        auth_password = (os.getenv(
            'NEWSLETTER_PASSWORD',
            ''
        ) or '').strip().strip('"').strip("'").replace(' ', '')
        if not auth_email or not auth_password:
            raise ValueError(
                'Email credentials not configured. Set NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD.'
            )

        html_body = (
                "<html><body style=\"font-family: Arial, sans-serif; line-height: 1.6; color: #333;\">"
                + ''.join(
            f"<p>{html_stdlib.escape(line)}</p>" for line in
            text_body.splitlines() if line.strip()
        )
                + "</body></html>"
        )

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subj
        msg['From'] = f"ResumaticAI <{auth_email}>"
        msg['To'] = email
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        server.starttls()
        server.login(auth_email, auth_password)
        server.send_message(msg)
        server.quit()

        try:
            record_email_event(
                email_type="admin_ai_assistant",
                recipient=email,
                subject=subj,
                status="sent",
                source="admin_ai_assistant",
                metadata={
                    "admin_user_id": admin_id,
                    "admin_email": admin_email,
                    "surface": "admin_stats",
                },
            )
        except Exception:
            pass

        return {
            'sent': True,
            'recipient': email,
            'subject': subj,
            'message': 'Email sent successfully.',
        }
    except Exception as exc:
        try:
            record_email_event(
                email_type="admin_ai_assistant",
                recipient=email,
                subject=subj,
                status="failed",
                source="admin_ai_assistant",
                metadata={
                    "admin_user_id": admin_id,
                    "admin_email": admin_email,
                    "surface": "admin_stats",
                },
                error="smtp_send_failed",
            )
        except Exception:
            pass
        return {
            'sent': False,
            'recipient': email,
            'subject': subj,
            'error': str(exc)[:220],
        }


def _admin_assistant_send_batch_email(
        recipients,
        subject: str,
        body: str,
        confirm_send: bool = False,
        campaign_label: str = '',
) -> dict:
    if not confirm_send:
        return {
            'sent': False,
            'error': 'confirm_send_required',
            'message': 'The user must explicitly confirm batch sending before this tool may send email.',
        }

    raw_recipients = recipients if isinstance(recipients, list) else []
    normalized = []
    seen = set()
    for item in raw_recipients:
        email = str(item or '').strip().lower()
        if not email or email in seen:
            continue
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            continue
        seen.add(email)
        normalized.append(email)

    if not normalized:
        return {'sent': False, 'error': 'no_valid_recipients'}
    if len(normalized) > 100:
        return {'sent': False, 'error': 'too_many_recipients',
                'max_allowed': 100}

    subj = str(subject or '').strip()
    text_body = str(body or '').strip()
    if not subj:
        return {'sent': False, 'error': 'missing_subject'}
    if not text_body:
        return {'sent': False, 'error': 'missing_body'}

    results = []
    sent = 0
    failed = 0
    for email in normalized:
        res = _admin_assistant_send_email(
            recipient=email,
            subject=subj,
            body=text_body,
            confirm_send=True,
        )
        results.append(res)
        if res.get('sent'):
            sent += 1
        else:
            failed += 1

    return {
        'sent': failed == 0,
        'campaign_label': str(campaign_label or '').strip(),
        'recipient_count': len(normalized),
        'sent_count': sent,
        'failed_count': failed,
        'results': results[:25],
        'results_truncated': len(results) > 25,
    }


def _admin_assistant_call_tool(name: str, args: dict) -> dict:
    args = args or {}
    if name == 'get_data_inventory':
        return _admin_assistant_tool_inventory()
    if name == 'get_admin_stats_overview':
        return _admin_assistant_get_stats_overview()
    if name == 'search_registered_users':
        return _admin_assistant_search_users(
            search=args.get('search', ''),
            plan_status=args.get('plan_status', ''),
            limit=args.get('limit', 10),
        )
    if name == 'get_user_detail':
        return _admin_assistant_get_user_detail(
            user_identifier=args.get('user_identifier', ''),
            revision_limit=args.get('revision_limit', 5),
        )
    if name == 'get_subscription_reconciliation':
        return _admin_assistant_get_subscription_reconciliation(
            limit=args.get('limit', 10)
        )
    if name == 'search_stripe_customers':
        return _admin_assistant_search_stripe_customers(
            search=args.get('search', ''),
            limit=args.get('limit', 10),
        )
    if name == 'get_stripe_customer_detail':
        return _admin_assistant_get_stripe_customer_detail(
            customer_id=args.get('customer_id', ''),
            user_identifier=args.get('user_identifier', ''),
        )
    if name == 'get_stripe_subscription_detail':
        return _admin_assistant_get_stripe_subscription_detail(
            subscription_id=args.get('subscription_id', ''),
            user_identifier=args.get('user_identifier', ''),
        )
    if name == 'list_stripe_invoices':
        return _admin_assistant_list_stripe_invoices(
            customer_id=args.get('customer_id', ''),
            subscription_id=args.get('subscription_id', ''),
            user_identifier=args.get('user_identifier', ''),
            limit=args.get('limit', 10),
        )
    if name == 'list_stripe_charges':
        return _admin_assistant_list_stripe_charges(
            customer_id=args.get('customer_id', ''),
            subscription_id=args.get('subscription_id', ''),
            user_identifier=args.get('user_identifier', ''),
            limit=args.get('limit', 10),
        )
    if name == 'get_recent_feedback':
        return _admin_assistant_get_recent_feedback(
            limit=args.get('limit', 10)
        )
    if name == 'get_recent_logins':
        return _admin_assistant_get_recent_logins(
            days=args.get('days', 7),
            limit=args.get('limit', 20),
        )
    if name == 'get_login_audit_table_rows':
        return _admin_assistant_get_login_audit_rows(
            limit=args.get('limit', 25),
            offset=args.get('offset', 0),
            partition_key=args.get('partition_key', ''),
            row_key=args.get('row_key', ''),
            search=args.get('search', ''),
        )
    if name == 'get_resume_revision_table_rows':
        return _admin_assistant_get_resume_revision_rows(
            limit=args.get('limit', 25),
            offset=args.get('offset', 0),
            partition_key=args.get('partition_key', ''),
            row_key=args.get('row_key', ''),
            search=args.get('search', ''),
        )
    if name == 'query_login_audit_table':
        return _admin_assistant_query_table_rows(
            AZURE_LOGIN_AUDIT_TABLE,
            filter_text=args.get('filter', ''),
            select=args.get('select', []),
            top=args.get('top', 25),
            offset=args.get('offset', 0),
            sort_field=args.get('sort_field', 'login_at'),
        )
    if name == 'query_resume_revisions_table':
        return _admin_assistant_query_table_rows(
            'ResumeRevisions',
            filter_text=args.get('filter', ''),
            select=args.get('select', []),
            top=args.get('top', 25),
            offset=args.get('offset', 0),
            sort_field=args.get('sort_field', 'timestamp'),
        )
    if name == 'send_admin_email':
        return _admin_assistant_send_email(
            recipient=args.get('recipient', ''),
            subject=args.get('subject', ''),
            body=args.get('body', ''),
            confirm_send=bool(args.get('confirm_send', False)),
        )
    if name == 'send_batch_admin_email':
        return _admin_assistant_send_batch_email(
            recipients=args.get('recipients', []),
            subject=args.get('subject', ''),
            body=args.get('body', ''),
            confirm_send=bool(args.get('confirm_send', False)),
            campaign_label=args.get('campaign_label', ''),
        )
    return {'error': f'Unknown tool: {name}'}


def _admin_assistant_tool_specs() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_data_inventory",
                "description": "List the admin data sources and what the assistant can read.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_admin_stats_overview",
                "description": "Get the high-level visit analytics, login summary, and feedback summary shown around admin stats.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_registered_users",
                "description": "Search registered users by email, name, user ID, provider, or plan status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search": {"type": "string"},
                        "plan_status": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1,
                                  "maximum": 25},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_user_detail",
                "description": "Get one user's profile summary, recent revisions, and recent tracked applications.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_identifier": {"type": "string",
                                            "description": "User ID or exact/partial email"},
                        "revision_limit": {"type": "integer", "minimum": 1,
                                           "maximum": 10},
                    },
                    "required": ["user_identifier"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_subscription_reconciliation",
                "description": "Get subscription KPI and Stripe versus Azure reconciliation data.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1,
                                  "maximum": 25},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_stripe_customers",
                "description": "Search Stripe customers by customer ID, email, name, or description.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search": {"type": "string",
                                   "description": "Customer ID, email, name, or other text to match"},
                        "limit": {"type": "integer", "minimum": 1,
                                  "maximum": 25},
                    },
                    "required": ["search"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_stripe_customer_detail",
                "description": "Get one Stripe customer and their latest subscription using a customer ID or app user identifier.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "user_identifier": {"type": "string",
                                            "description": "App user ID or exact/partial email"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_stripe_subscription_detail",
                "description": "Get one Stripe subscription and its latest invoice using a subscription ID or app user identifier.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subscription_id": {"type": "string"},
                        "user_identifier": {"type": "string",
                                            "description": "App user ID or exact/partial email"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_stripe_invoices",
                "description": "List recent Stripe invoices for a customer, subscription, or app user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "subscription_id": {"type": "string"},
                        "user_identifier": {"type": "string",
                                            "description": "App user ID or exact/partial email"},
                        "limit": {"type": "integer", "minimum": 1,
                                  "maximum": 25},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_stripe_charges",
                "description": "List recent Stripe charges for a customer, subscription, or app user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "subscription_id": {"type": "string"},
                        "user_identifier": {"type": "string",
                                            "description": "App user ID or exact/partial email"},
                        "limit": {"type": "integer", "minimum": 1,
                                  "maximum": 25},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_recent_feedback",
                "description": "Get recent feedback submissions from the admin feedback CSV.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1,
                                  "maximum": 25},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_recent_logins",
                "description": "Get recent login audit rows for the requested number of days.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "minimum": 1,
                                 "maximum": 90},
                        "limit": {"type": "integer", "minimum": 1,
                                  "maximum": 50},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_login_audit_table_rows",
                "description": "Read rows from the full Azure LoginAudit table with optional filters and pagination.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1,
                                  "maximum": 100},
                        "offset": {"type": "integer", "minimum": 0},
                        "partition_key": {"type": "string"},
                        "row_key": {"type": "string"},
                        "search": {"type": "string",
                                   "description": "Substring search across the row JSON"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_resume_revision_table_rows",
                "description": "Read rows from the full Azure ResumeRevisions table with optional filters and pagination.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1,
                                  "maximum": 100},
                        "offset": {"type": "integer", "minimum": 0},
                        "partition_key": {"type": "string"},
                        "row_key": {"type": "string"},
                        "search": {"type": "string",
                                   "description": "Substring search across the row JSON"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_login_audit_table",
                "description": "Run a controlled read-only Azure Table query against the LoginAudit table using filter/select/top semantics.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter": {"type": "string",
                                   "description": "Azure Table/OData filter expression"},
                        "select": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of fields to return",
                        },
                        "top": {"type": "integer", "minimum": 1,
                                "maximum": 100},
                        "offset": {"type": "integer", "minimum": 0},
                        "sort_field": {"type": "string",
                                       "description": "Optional client-side sort field for the returned rows"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_resume_revisions_table",
                "description": "Run a controlled read-only Azure Table query against the ResumeRevisions table using filter/select/top semantics.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter": {"type": "string",
                                   "description": "Azure Table/OData filter expression"},
                        "select": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of fields to return",
                        },
                        "top": {"type": "integer", "minimum": 1,
                                "maximum": 100},
                        "offset": {"type": "integer", "minimum": 0},
                        "sort_field": {"type": "string",
                                       "description": "Optional client-side sort field for the returned rows"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "send_admin_email",
                "description": "Send one admin-triggered email through the configured SMTP account. Use only when the admin explicitly instructs you to send the final email.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "recipient": {"type": "string",
                                      "description": "Single recipient email address"},
                        "subject": {"type": "string"},
                        "body": {"type": "string",
                                 "description": "Plain-text email body"},
                        "confirm_send": {"type": "boolean",
                                         "description": "Set true only when the admin explicitly asked to send the email now"},
                    },
                    "required": ["recipient", "subject", "body",
                                 "confirm_send"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "send_batch_admin_email",
                "description": "Send the same email to an explicit list of targeted recipients. Use only when the admin explicitly asks you to send the final batch now.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "recipients": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Explicit list of recipient email addresses, up to 100",
                        },
                        "subject": {"type": "string"},
                        "body": {"type": "string",
                                 "description": "Plain-text email body sent to all recipients"},
                        "campaign_label": {"type": "string"},
                        "confirm_send": {"type": "boolean",
                                         "description": "Set true only when the admin explicitly asked to send the batch now"},
                    },
                    "required": ["recipients", "subject", "body",
                                 "confirm_send"],
                },
            },
        },
    ]


@app.route('/api/ai/job-search-coach', methods=['POST'])
@app.route('/path/api/ai/job-search-coach', methods=['POST'])
@login_required
def api_job_search_coach():
    """Conversational job-search coach with dashboard context (latest resume + applications)."""
    try:
        if _requires_email_verification(current_user):
            return jsonify(
                {"success": False,
                 "error": "Please verify your email to use the Job Search Coach."}
            ), 403

        payload = request.get_json(force=True, silent=True) or {}
        raw_messages = payload.get('messages')
        if not isinstance(raw_messages, list) or not raw_messages:
            return jsonify(
                {"success": False, "error": "Missing messages"}
            ), 400
        if len(raw_messages) > 30:
            return jsonify(
                {"success": False,
                 "error": "Conversation is too long. Start a new chat."}
            ), 400

        openai_messages = []
        for item in raw_messages[-20:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get('role') or '').strip().lower()
            if role not in ('user', 'assistant'):
                continue
            content = str(item.get('content') or '').strip()
            if not content:
                continue
            if len(content) > 4000:
                content = content[:4000]
            openai_messages.append({"role": role, "content": content})

        if not any(m.get('role') == 'user' for m in openai_messages):
            return jsonify(
                {"success": False, "error": "No user message provided"}
            ), 400

        api_key = (os.getenv('OPENAI_API_KEY') or '').strip().strip(
            '"'
        ).strip("'")
        if not api_key:
            return jsonify(
                {"success": False,
                 "error": "OPENAI_API_KEY not configured"}
            ), 500

        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=90.0, max_retries=2)

        coach_ctx = _build_job_search_coach_context(
            getattr(current_user, 'id', '')
        )
        context_block = _format_job_search_coach_context(coach_ctx)
        system_prompt = (
            "You are Scout, Resumatic AI's Job Search Coach — a practical, encouraging career advisor embedded in the user's "
            "Job Search Dashboard.\n"
            "You automatically receive their latest resume revision and every tracked job application on the dashboard.\n"
            "Use that context to give specific, actionable advice about applications, follow-ups, interview prep, "
            "resume positioning, and prioritization.\n"
            "Rules:\n"
            "- Keep every reply short and scannable: lead with one direct sentence, then at most 3–5 bullets or brief steps.\n"
            "- Stay under ~100 words unless the user explicitly asks for a longer draft (e.g. a full email).\n"
            "- Do not recap the resume or application list; reference only what is needed for your answer.\n"
            "- Reference real companies/roles/statuses from the context when relevant.\n"
            "- Do NOT invent employers, interviews, offers, or resume facts that are not in the context.\n"
            "- If information is missing, ask one clarifying question or suggest one concrete next step.\n"
            "- Email/message drafts: 4–6 sentences max unless the user asks for more; label them clearly as drafts.\n"
            "- If more detail would help, end with one line offering to go deeper on a specific topic.\n"
            "- Do not claim you can change dashboard data; the user updates the dashboard themselves.\n\n"
            f"{context_block}"
        )

        chat_messages = [{"role": "system",
                          "content": system_prompt}] + openai_messages
        resp, model_used = _coach_chat_completion(client, chat_messages)
        reply = (resp.choices[0].message.content or '').strip()
        if not reply:
            return jsonify(
                {"success": False, "error": "Empty AI response"}
            ), 502
        if len(reply) > _JOB_COACH_MAX_REPLY_CHARS:
            reply = (
                    reply[:_JOB_COACH_MAX_REPLY_CHARS].rstrip()
                    + "\n\n*(Reply shortened — ask me to expand any part.)*"
            )

        return jsonify(
            {
                "success": True,
                "reply": reply,
                "model": model_used,
                "context_summary": {
                    "revision_count": coach_ctx.get('revision_count', 0),
                    "application_count": coach_ctx.get(
                        'application_count',
                        0
                    ),
                    "latest_resume_name": (coach_ctx.get(
                        'latest_resume'
                    ) or {}).get('revision_name') or '',
                },
            }
        )
    except Exception as e:
        try:
            logger.error(
                f"Job search coach failed: {type(e).__name__}: {str(e)}"
            )
        except Exception:
            pass
        return jsonify(
            {"success": False, "error": _coach_openai_error_message(e)}
        ), 500


@app.route('/api/ai/admin-stats-assistant', methods=['POST'])
@login_required
def api_admin_stats_assistant():
    """Read-only admin assistant with curated tools for stats, users, revisions, logins, feedback, and email sending."""
    try:
        if not getattr(current_user, "is_admin", False):
            return jsonify({"success": False, "error": "Forbidden"}), 403

        payload = request.get_json(force=True, silent=True) or {}
        raw_messages = payload.get('messages')
        if not isinstance(raw_messages, list) or not raw_messages:
            return jsonify(
                {"success": False, "error": "Missing messages"}
            ), 400
        if len(raw_messages) > 40:
            return jsonify(
                {"success": False,
                 "error": "Conversation is too long. Start a new chat."}
            ), 400

        openai_messages = []
        for item in raw_messages[-40:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get('role') or '').strip().lower()
            if role not in ('user', 'assistant'):
                continue
            content = str(item.get('content') or '').strip()
            if not content:
                continue
            if len(content) > 5000:
                content = content[:5000]
            openai_messages.append({"role": role, "content": content})

        if not any(m.get('role') == 'user' for m in openai_messages):
            return jsonify(
                {"success": False, "error": "No user message provided"}
            ), 400

        api_key = (os.getenv('OPENAI_API_KEY') or '').strip().strip(
            '"'
        ).strip("'")
        if not api_key:
            return jsonify(
                {"success": False,
                 "error": "OPENAI_API_KEY not configured"}
            ), 500

        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=90.0, max_retries=2)

        system_prompt = (
            "You are ResumaticAI's Admin Stats Assistant embedded in the admin statistics page.\n"
            "You help the admin inspect site analytics, Azure user data, revisions, login activity, feedback, Stripe billing data, and subscription reconciliation.\n"
            "You have server-side tools to read curated admin datasets, read Stripe billing data, and send one email or a targeted batch email.\n"
            "You also have controlled read-only query tools for the Azure LoginAudit and ResumeRevisions tables.\n"
            "Rules:\n"
            "- Be concise and operational. Lead with the answer, then short bullets when useful.\n"
            "- Use tools when data is needed; do not guess counts, user details, or subscription state.\n"
            "- For Stripe questions, prefer the dedicated Stripe customer, subscription, invoice, and charge tools instead of guessing from reconciliation data.\n"
            "- For targeted investigation in LoginAudit or ResumeRevisions, prefer the table query tools with filter/select/top semantics.\n"
            "- When you used a tool, mention which source you used in plain language.\n"
            "- Treat all data as sensitive. Only surface the minimum necessary details.\n"
            "- Never claim you changed or deleted data. You are read-only except for the explicit email-sending tool.\n"
            "- Only send an email when the admin explicitly asks you to send it now. If they are still drafting, do not call the send tool.\n"
            "- Before sending, make sure you have a concrete recipient or explicit recipient list, plus a subject and body. If anything is missing, ask for it.\n"
            "- For batch sends, prefer first showing who will receive it and summarizing the audience before sending.\n"
            "- If a tool result is partial or capped, say so.\n"
        )

        tools = _admin_assistant_tool_specs()
        messages = [{"role": "system",
                     "content": system_prompt}] + openai_messages
        model_used = ''

        for _ in range(_ADMIN_ASSISTANT_MAX_TOOL_CALLS):
            resp, model_used = _admin_assistant_chat_completion(
                client,
                messages,
                tools=tools
            )
            msg = resp.choices[0].message
            tool_calls = getattr(msg, 'tool_calls', None) or []
            if not tool_calls:
                reply = str(msg.content or '').strip()
                if not reply:
                    return jsonify(
                        {"success": False, "error": "Empty AI response"}
                    ), 502
                if len(reply) > _ADMIN_ASSISTANT_MAX_REPLY_CHARS:
                    reply = reply[
                            :_ADMIN_ASSISTANT_MAX_REPLY_CHARS].rstrip() + "\n\n*(Reply shortened.)*"
                return jsonify(
                    {"success": True, "reply": reply, "model": model_used}
                )

            assistant_message = {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [],
            }
            for tc in tool_calls:
                assistant_message["tool_calls"].append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )
            messages.append(assistant_message)

            for tc in tool_calls:
                raw_args = tc.function.arguments or '{}'
                try:
                    parsed_args = json.loads(raw_args)
                except Exception:
                    parsed_args = {}
                result = _admin_assistant_call_tool(
                    tc.function.name,
                    parsed_args
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(
                            result,
                            ensure_ascii=False,
                            default=str
                        ),
                    }
                )

        return jsonify(
            {"success": False,
             "error": "Tool-call limit reached. Please narrow the request."}
        ), 400
    except Exception as e:
        try:
            logger.error(
                f"Admin stats assistant failed: {type(e).__name__}: {str(e)}"
            )
        except Exception:
            pass
        return jsonify(
            {"success": False, "error": _admin_assistant_error_message(e)}
        ), 500


@app.route("/termsprivacy")
def termsprivacy():
    return redirect(url_for('terms_privacy'), code=301)


@app.route("/terms_privacy")
def terms_privacy():
    return render_template("terms_privacy.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/discounts")
def discounts():
    current_year = datetime.now().year
    return render_template(
        "discounts.html",
        year=current_year,
        user=current_user if current_user.is_authenticated else None,
    )


@app.route("/about")
def about():
    current_year = datetime.now().year
    return render_template(
        "about.html",
        year=current_year,
        user=current_user if current_user.is_authenticated else None
    )


@app.route("/resume-org-alternative")
def resume_org_alternative():
    current_year = datetime.now().year
    return render_template(
        "resume_org_alternative.html",
        year=current_year,
        user=current_user if current_user.is_authenticated else None,
    )


@app.route("/blog")
def blog():
    current_year = datetime.now().year
    return render_template(
        "blog.html",
        year=current_year,
        user=current_user if current_user.is_authenticated else None
    )


# Blog post metadata for SEO optimization
BLOG_POSTS_METADATA = {
    'ats-optimization': {
        'title': 'How to Beat the ATS in 2025 | ResumaticAI',
        'meta_description': 'Master the art of creating ATS-friendly resumes with our comprehensive guide. Learn how Applicant Tracking Systems work and discover proven strategies to ensure your resume gets past automated screening.',
        'keywords': 'ATS optimization, applicant tracking system, resume keywords, ATS friendly resume, job application tips, resume writing',
        'og_title': 'How to Beat the ATS in 2025 - Complete Guide',
        'og_description': 'Learn proven strategies to create ATS-friendly resumes that pass automated screening systems and get you more job interviews.',
        'og_image': 'https://resumaticai.com/static/images/robot.png'
    },
    'Resume-objective': {
        'title': 'Resume Summary vs. Objective: Which Should You Use in 2025? | ResumaticAI',
        'meta_description': 'Learn the key differences between resume summaries and objectives, and discover which one will help you land more interviews in 2025.',
        'keywords': 'resume summary, resume objective, resume writing tips, career advice, job application, resume format',
        'og_title': 'Resume Summary vs. Objective: 2025 Guide',
        'og_description': 'Discover whether to use a resume summary or objective statement in 2025 to maximize your interview chances.',
        'og_image': 'https://resumaticai.com/static/images/vs.png'
    },
    'Power-words': {
        'title': 'Power Words to Use in Your Resume (And Ones to Avoid) | ResumaticAI',
        'meta_description': 'Discover the most impactful words to use in your resume and learn which overused phrases to avoid to make your application stand out.',
        'keywords': 'resume power words, action verbs, resume writing, job application, career tips, resume optimization',
        'og_title': 'Resume Power Words: What to Use and Avoid',
        'og_description': 'Learn which words will make your resume stand out and which ones to avoid for better job application success.',
        'og_image': 'https://resumaticai.com/static/images/power.jpg'
    },
    'no-experience': {
        'title': 'How to Write a Resume With No Work Experience | ResumaticAI',
        'meta_description': 'Get expert tips on creating a compelling resume when you\'re just starting out, with strategies to highlight your skills and potential.',
        'keywords': 'resume no experience, first resume, entry level resume, student resume, career starter, resume writing',
        'og_title': 'Resume Writing for Beginners: No Experience Needed',
        'og_description': 'Create a compelling resume even without work experience using our expert strategies and tips.',
        'og_image': 'https://resumaticai.com/static/images/noexperience.jpg'
    },
    'resume-format-2025': {
        'title': 'Best Resume Formats for 2025 (With Examples) | ResumaticAI',
        'meta_description': 'Explore the most effective resume formats for 2025, complete with real examples and guidelines for different career stages.',
        'keywords': 'resume format 2025, resume templates, resume examples, resume layout, career stages, resume design',
        'og_title': 'Best Resume Formats for 2025: Complete Guide',
        'og_description': 'Choose the perfect resume format for 2025 with our comprehensive guide and real examples.',
        'og_image': 'https://resumaticai.com/static/images/format.webp'
    },
    'resume-format-2026': {
        'title': 'Best Resume Formats for 2026 (With Examples) | ResumaticAI',
        'meta_description': 'See the best resume formats for 2026 with ATS-friendly examples. Learn when to use reverse-chronological vs. combination formats, how to structure skills, and whether to use PDF or DOCX.',
        'keywords': 'resume format 2026, resume templates, resume examples, resume layout, career stages, resume design',
        'og_title': 'Best Resume Formats for 2026: Complete Guide',
        'og_description': 'ATS-friendly resume formats, layout rules, and examples for 2026.',
        'og_image': 'https://resumaticai.com/static/images/format.webp'
    },
    'toptenmistakes': {
        'title': 'Top 10 Resume Mistakes to Avoid in 2025 | ResumaticAI',
        'meta_description': 'Learn the most common resume mistakes that can cost you job opportunities and how to avoid them in 2025.',
        'keywords': 'resume mistakes, resume errors, job application tips, resume writing, career advice, avoid resume mistakes',
        'og_title': 'Top 10 Resume Mistakes to Avoid in 2025',
        'og_description': 'Don\'t let these common resume mistakes cost you job opportunities. Learn how to avoid them.',
        'og_image': 'https://resumaticai.com/static/images/robot.png'
    },
    'tailorresumejob': {
        'title': 'How to Tailor Your Resume for Each Job Application | ResumaticAI',
        'meta_description': 'Learn proven strategies to customize your resume for each job application to increase your chances of getting interviews and job offers.',
        'keywords': 'tailor resume, customize resume, job application, resume customization, targeted resume, job-specific resume',
        'og_title': 'How to Tailor Your Resume for Each Job Application',
        'og_description': 'Master the art of customizing your resume for each job to maximize your interview chances and career success.',
        'og_image': 'https://resumaticai.com/static/images/robot.png'
    }
}


@app.route("/blog/<post>")
def blog_post(post):
    current_year = datetime.now().year

    # Canonicalize blog slugs to prevent 500s from template mismatches
    # Accept underscores/case-insensitive inputs and redirect to canonical slugs
    canonical_slug_map = {
        # key: normalized (lowercase, hyphens) -> value: canonical file/slug
        "toptenmistakes": "toptenmistakes",
        "ats-optimization": "ats-optimization",
        "resume-objective": "Resume-objective",
        "resume-summary-examples": "Resume-objective",
        "no-experience": "no-experience",
        "power-words": "Power-words",
        "resume-format-2025": "resume-format-2026",
        "resume-format-2026": "resume-format-2026",
        "tailorresumejob": "tailorresumejob",
    }

    requested_slug = post.strip()
    normalized_slug = requested_slug.replace("_", "-").lower()

    if normalized_slug in canonical_slug_map:
        canonical_slug = canonical_slug_map[normalized_slug]
        # Redirect variants to the canonical version for SEO consistency
        if requested_slug != canonical_slug:
            return redirect(
                url_for("blog_post", post=canonical_slug),
                code=301
            )
    else:
        # Unknown slug -> 404 instead of template error 500
        from flask import abort

        abort(404)

    # Get metadata for the blog post using the canonical slug
    post_metadata = BLOG_POSTS_METADATA.get(canonical_slug, {})

    try:
        return render_template(
            f"{canonical_slug}.html",
            year=current_year,
            user=current_user if current_user.is_authenticated else None,
            post_metadata=post_metadata,
        )
    except TemplateNotFound:
        # Fallback: if 2026 slug is requested but template file not present, use 2025 template
        file_slug = canonical_slug
        if canonical_slug == 'resume-format-2026':
            file_slug = 'resume-format-2025'
        return render_template(
            f"{file_slug}.html",
            year=current_year,
            user=current_user if current_user.is_authenticated else None,
            post_metadata=post_metadata,
        )


@app.route("/subscribe", methods=["POST"])
def subscribe():
    email = request.form.get("email")
    referrer = request.referrer or url_for("index")

    if email:
        try:
            # Create subscribers.csv if it doesn't exist
            import os

            if not os.path.exists("subscribers.csv"):
                with open("subscribers.csv", "w") as f:
                    f.write("email\n")  # Header row

            # Check if email already exists
            existing_emails = []
            try:
                with open("subscribers.csv", "r") as f:
                    existing_emails = [line.strip().lower() for line in
                                       f.readlines()]
            except FileNotFoundError:
                pass

            if email.lower() in existing_emails:
                flash(
                    "You're already subscribed to our newsletter!",
                    "info"
                )
            else:
                with open("subscribers.csv", "a") as f:
                    f.write(email + "\n")
                flash(
                    "Thank you for subscribing! You'll receive our latest resume tips and career advice.",
                    "success"
                )

            # Smart redirect based on referrer
            if "/blog" in referrer:
                return redirect(url_for("blog"))
            elif "/thank_you" in referrer:
                return redirect(url_for("thank_you"))
            else:
                return redirect(url_for("thank_you"))
        except Exception as e:
            flash(
                "Something went wrong. Please try again later.",
                "danger"
            )
            print(f"Subscription error: {str(e)}")
            return redirect(referrer)
    else:
        flash("Please enter a valid email address.", "danger")
        return redirect(referrer)


@app.route("/thank_you")
def thank_you():
    return render_template("thank_you.html")


@app.route("/users")
@login_required
def view_users():
    if not current_user.is_authenticated:
        flash("You need to log in to view this page.", "danger")
        return redirect(url_for("login"))

    # Check if the user is an admin
    if not getattr(current_user, "is_admin", False):
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("index"))

    return render_template("users.html", users=users.values())


@app.route("/analytics")
@login_required
def view_analytics():
    """Admin dashboard for viewing Facebook ad performance and site analytics."""
    if not current_user.is_authenticated:
        flash("You need to log in to view this page.", "danger")
        return redirect(url_for("login"))

    # Check if the user is an admin
    if not getattr(current_user, "is_admin", False):
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("index"))

    # Get comprehensive analytics data
    analytics_data = analytics.get_full_analytics()

    return render_template("analytics.html", analytics=analytics_data)


@app.route("/api/track", methods=["POST"])
def track_conversion():
    """API endpoint for tracking conversions and events from Facebook ads."""
    try:
        # Check if this is a duplicate tracking call in the same session
        if 'visit_tracked' in session:
            # Just track the conversion/event without counting as a new visit
            source_info = session.get(
                'traffic_source',
                {'type': 'unknown'}
            )
            app.logger.info(
                "Facebook tracking call - visit already tracked, skipping duplicate"
            )
        else:
            # Track the visit/conversion (first time)
            source_info = analytics.track_visit(request)
            session['visit_tracked'] = True
            session['traffic_source'] = source_info
            app.logger.info(
                f"Facebook tracking - new visit tracked: {source_info.get('type', 'unknown')}"
            )

        # Return JSON response for AJAX calls
        return {
            "status": "success",
            "source_type": source_info.get("type", "unknown"),
            "campaign": source_info.get("campaign", "unknown"),
            "message": "Event tracked successfully"
        }, 200
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }, 500


@app.route("/api/track_visit", methods=["POST"])
def track_visit():
    """API endpoint for tracking legitimate page visits (bot-filtered)."""
    try:
        # Check if visit already tracked in this session to prevent double counting
        if 'visit_tracked' in session:
            app.logger.info(
                "Visit already tracked in session, skipping duplicate API tracking"
            )
            return {
                "status": "success",
                "message": "Visit already tracked in session",
                "duplicate_prevented": True
            }, 200

        # Get JSON data from request
        data = request.get_json()

        if not data:
            return {"status": "error", "message": "No data provided"}, 400

        # Additional server-side bot detection
        user_agent = request.headers.get('User-Agent', '').lower()
        bot_indicators = [
            'bot', 'crawl', 'spider', 'scraper', 'curl', 'wget', 'python',
            'java', 'php', 'ruby', 'go-http', 'apache', 'nginx'
        ]

        # Check if request looks automated
        if any(indicator in user_agent for indicator in bot_indicators):
            return {"status": "ignored", "message": "Bot detected"}, 200

        # Check for required browser headers that bots often miss
        if not request.headers.get('Accept-Language'):
            return {"status": "ignored",
                    "message": "Missing browser headers"}, 200

        # Track the legitimate visit using existing analytics
        source_info = analytics.track_visit(request)
        session['visit_tracked'] = True
        session['traffic_source'] = source_info

        # Log the visit for debugging
        app.logger.info(
            f"API visit tracked: {data.get('page', 'unknown')} from {request.remote_addr} - {source_info.get('type', 'unknown')}"
        )

        return {
            "status": "success",
            "source_type": source_info.get("type", "unknown"),
            "message": "Visit tracked successfully"
        }, 200

    except Exception as e:
        logger.error(f"Error tracking visit: {str(e)}")
        return {
            "status": "error",
            "message": "Internal server error"
        }, 500


@app.route("/api/visit_count", methods=["GET"])
def get_visit_count():
    """API endpoint to retrieve current visit count."""
    try:
        # Get analytics data
        analytics_data = analytics.get_full_analytics()

        # Extract summary data
        summary = analytics_data.get('summary', {})

        return {
            "status": "success",
            "data": {
                "total_visits": summary.get('total_visits', 0),
                "facebook_ad_visits": summary.get('facebook_ad_visits', 0),
                "organic_visits": summary.get('organic_visits', 0),
                "total_conversions": summary.get('total_conversions', 0),
                "facebook_ad_conversions": summary.get(
                    'facebook_ad_conversions',
                    0
                ),
                "last_updated": summary.get('last_updated', 'unknown')
            }
        }, 200

    except Exception as e:
        logger.error(f"Error retrieving visit count: {str(e)}")
        return {
            "status": "error",
            "message": "Failed to retrieve visit count"
        }, 500


def _collect_revision_counts_by_user() -> dict[str, int]:
    """Count resume revisions per user from Azure ResumeRevisions table."""
    counts: dict[str, int] = {}
    try:
        revision_client = get_table_client(
            'ResumeRevisions',
            create_if_missing=False
        )
        pager = revision_client.list_entities(select=["PartitionKey"])
        for entity in pager:
            uid = str(entity.get("PartitionKey") or '').strip()
            if uid:
                counts[uid] = counts.get(uid, 0) + 1
    except Exception as e:
        try:
            logger.warning(
                "admin dashboard: failed to count revisions: %s",
                str(e)
            )
        except Exception:
            pass
    return counts


def _coerce_datetime_iso(val) -> str:
    """Normalize Azure/datetime values to an ISO timestamp string."""
    if val is None:
        return ''
    if hasattr(val, 'isoformat'):
        try:
            dt = val
            if getattr(dt, 'tzinfo', None) is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass
    return str(val or '').strip()


def _login_at_from_audit_record(rec: dict) -> datetime | None:
    """Resolve login timestamp for an audit record, recovering sub-second precision when possible."""
    login_at = _parse_iso_datetime(
        _coerce_datetime_iso(rec.get('login_at'))
    )
    row_key = str(rec.get('row_key') or rec.get('RowKey') or '').strip()
    if not row_key:
        return login_at
    match = re.match(r'^(\d{8}T\d{12})_', row_key)
    if not match:
        return login_at
    try:
        rk_dt = datetime.strptime(
            match.group(1),
            '%Y%m%dT%H%M%S%f'
        ).replace(tzinfo=timezone.utc)
    except Exception:
        return login_at
    if login_at is None:
        return rk_dt
    # RowKey is the source of truth for login time; Azure DateTime round-trips can drop subseconds.
    if abs((rk_dt - login_at).total_seconds()) < 1.0:
        return rk_dt
    return login_at


def _format_pacific_login_time(
        dt: datetime,
        *,
        precise: bool = False
) -> str:
    """Format a login datetime in Pacific time for admin exports."""
    try:
        pacific_dt = dt.astimezone(_get_pacific_tzinfo())
    except Exception:
        pacific_dt = dt
    if precise:
        return pacific_dt.strftime('%Y-%m-%d %H:%M:%S.%f %Z')
    return pacific_dt.strftime('%Y-%m-%d %H:%M:%S %Z')


def _format_any_datetime_pacific(val) -> str:
    """Format a datetime value (object or ISO string) for Pacific display."""
    iso = _coerce_datetime_iso(val)
    if not iso:
        return ''
    return _format_datetime_pacific(iso)


def _build_signup_lookup_from_csv() -> dict[str, str]:
    """user_id -> created_at ISO from google_signups.csv (fallback for older profiles)."""
    lookup: dict[str, str] = {}
    try:
        import csv

        if not os.path.exists('google_signups.csv'):
            return lookup
        with open(
                'google_signups.csv',
                'r',
                encoding='utf-8',
                newline=''
        ) as f:
            for row in csv.DictReader(f):
                uid = str(row.get('user_id') or '').strip()
                ts = str(row.get('timestamp_iso') or '').strip()
                if uid and ts and uid not in lookup:
                    lookup[uid] = ts
    except Exception:
        pass
    return lookup


def _build_last_login_lookup() -> dict[str, dict]:
    """user_id -> latest login info from login audit (Azure table or JSON file)."""
    lookup: dict[str, dict] = {}

    sessions: list[dict] = []
    if _azure_login_audit_enabled():
        try:
            sessions = _azure_login_audit_list(limit=0)
        except Exception:
            sessions = []
    if not sessions:
        try:
            store = _load_login_audit_store()
            raw_sessions = store.get('sessions') if isinstance(
                store,
                dict
            ) else {}
            if isinstance(raw_sessions, dict):
                sessions = [v for v in raw_sessions.values() if
                            isinstance(v, dict)]
        except Exception:
            sessions = []

    for rec in sessions:
        uid = str(rec.get('user_id') or '').strip()
        if not uid:
            continue
        login_at = _coerce_datetime_iso(
            rec.get('last_activity_at') or rec.get('login_at')
        )
        if not login_at:
            continue
        login_dt = _parse_iso_dt(login_at)
        prev = lookup.get(uid)
        prev_dt = _parse_iso_dt(prev.get('login_at')) if prev else None
        if prev is None or (
                login_dt and (prev_dt is None or login_dt > prev_dt)):
            lookup[uid] = {
                'login_at': login_at,
                'login_method': str(rec.get('login_method') or '').strip(),
            }

    # Also scan Azure Users session rows for last_activity_at.
    try:
        table_client = get_users_table_client(create_if_missing=False)
        pager = None
        try:
            pager = table_client.query_entities("record_type eq 'session'")
        except Exception:
            pager = table_client.list_entities()
        for e in pager:
            if str(e.get('record_type') or '') != 'session':
                continue
            uid = str(e.get('PartitionKey') or '').strip()
            if not uid:
                continue
            activity_at = _coerce_datetime_iso(
                e.get('last_activity_at') or e.get('login_at')
            )
            if not activity_at:
                continue
            activity_dt = _parse_iso_dt(activity_at)
            prev = lookup.get(uid)
            prev_dt = _parse_iso_dt(prev.get('login_at')) if prev else None
            if prev is None or (activity_dt and (
                    prev_dt is None or activity_dt > prev_dt)):
                method = str(e.get('login_method') or '').strip()
                if not method and prev:
                    method = str(prev.get('login_method') or '').strip()
                lookup[uid] = {
                    'login_at': activity_at,
                    'login_method': method,
                }
    except Exception:
        pass

    return lookup


def _load_login_audit_sessions_for_admin() -> tuple[
    list[dict], bool, str | None, dict | None]:
    """Load login audit sessions from Azure or JSON in a template-friendly shape."""
    file_present = False
    try:
        file_present = os.path.exists(LOGIN_AUDIT_FILE)
    except Exception:
        file_present = False

    source_label = None
    store = None
    sessions_list: list[dict] = []

    if _azure_login_audit_enabled():
        try:
            rows = _azure_login_audit_list(limit=0)
            for e in rows:
                if not isinstance(e, dict):
                    continue
                sessions_list.append(
                    {
                        'audit_id': str(e.get('audit_id') or ''),
                        'user_id': str(e.get('user_id') or ''),
                        'email': str(e.get('email') or ''),
                        'login_at': _coerce_datetime_iso(
                            e.get('login_at')
                        ),
                        'last_activity_at': _coerce_datetime_iso(
                            e.get('last_activity_at')
                        ),
                        'logout_at': (_coerce_datetime_iso(
                            e.get('logout_at')
                        ) or None),
                        'duration_seconds': e.get(
                            'duration_seconds',
                            None
                        ),
                        'login_method': str(
                            e.get('login_method') or ''
                        ) or None,
                        'row_key': str(e.get('RowKey') or ''),
                    }
                )
            source_label = f"Azure Table: {AZURE_LOGIN_AUDIT_TABLE}"
            store = {'version': _LOGIN_AUDIT_VERSION}
        except Exception:
            sessions_list = []
            source_label = None
            store = None

    if not sessions_list:
        store = _load_login_audit_store()
        raw_sessions = store.get('sessions') if isinstance(
            store,
            dict
        ) else {}
        if not isinstance(raw_sessions, dict):
            raw_sessions = {}
        sessions_list = [v for v in raw_sessions.values() if
                         isinstance(v, dict)]
        if file_present:
            source_label = f"login_audit.json" + (
                f" (v{store.get('version')})" if isinstance(
                    store,
                    dict
                ) and store.get('version') else "")
        else:
            source_label = "login_audit.json (not created yet)"

    sessions_list.sort(
        key=lambda r: (_parse_iso_datetime(
            r.get('login_at')
        ) or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )
    return sessions_list, file_present, source_label, store


def _dedupe_login_audit_sessions(sessions_list: list[dict]) -> list[dict]:
    """Collapse duplicate login audit rows so returning-user metrics stay trustworthy."""
    best_by_key: dict[str, dict] = {}

    def _identity(rec: dict) -> str:
        user_id = str(rec.get('user_id') or '').strip()
        email = _normalize_email(rec.get('email') or '')
        return user_id or email or str(rec.get('audit_id') or '').strip()

    def _score(rec: dict) -> tuple[int, int, str]:
        has_logout = 1 if str(rec.get('logout_at') or '').strip() else 0
        duration = 0
        try:
            duration = int(rec.get('duration_seconds') or 0)
        except Exception:
            duration = 0
        audit_id = str(rec.get('audit_id') or '')
        return (has_logout, duration, audit_id)

    for rec in sessions_list or []:
        if not isinstance(rec, dict):
            continue
        login_at = _login_at_from_audit_record(rec)
        if login_at is None:
            continue
        identity = _identity(rec)
        if not identity:
            continue
        dedupe_key = f"{identity}|{login_at.replace(microsecond=0).isoformat()}"
        prev = best_by_key.get(dedupe_key)
        if prev is None or _score(rec) > _score(prev):
            best_by_key[dedupe_key] = rec

    metrics_window_seconds = max(
        60,
        int(_LOGIN_AUDIT_METRICS_DEDUPE_MINUTES) * 60
    )
    onboarding_window_seconds = max(
        60,
        int(_LOGIN_AUDIT_ONBOARDING_WINDOW_MINUTES) * 60
    )
    collapsed = sorted(
        list(best_by_key.values()),
        key=lambda r: (
                _login_at_from_audit_record(r) or datetime.min.replace(
            tzinfo=timezone.utc
        )),
    )
    kept: list[dict] = []
    last_kept_at_by_identity: dict[str, datetime] = {}
    last_kept_method_by_identity: dict[str, str] = {}

    for rec in collapsed:
        login_at = _login_at_from_audit_record(rec)
        if login_at is None:
            continue
        identity = _identity(rec)
        if not identity:
            kept.append(rec)
            continue

        method = str(rec.get('login_method') or '').strip().lower()
        prev_at = last_kept_at_by_identity.get(identity)
        prev_method = last_kept_method_by_identity.get(identity, '')
        if prev_at is not None:
            delta = (login_at - prev_at).total_seconds()
            if 0 <= delta < onboarding_window_seconds:
                if method == 'password' and prev_method == 'email_verification':
                    continue
            if 0 <= delta < metrics_window_seconds:
                if method == 'email_verification' and prev_method == 'email_verification':
                    continue
                if method and method == prev_method:
                    continue

        kept.append(rec)
        last_kept_at_by_identity[identity] = login_at
        last_kept_method_by_identity[identity] = method

    return kept


def _build_classified_login_events(
        sessions_list: list[dict],
        days: int | None = None
) -> list[dict]:
    """Return login events classified as new or returning, optionally filtered to recent Pacific dates."""
    sessions_list = _dedupe_login_audit_sessions(sessions_list)
    ordered = sorted(
        [s for s in (sessions_list or []) if isinstance(s, dict)],
        key=lambda r: (_parse_iso_datetime(
            r.get('login_at')
        ) or datetime.min.replace(tzinfo=timezone.utc)),
    )

    seen_identities: set[str] = set()
    seen_audit_ids: set[str] = set()
    classified_events: list[dict] = []

    pacific_today = None
    earliest_pacific_date = None
    if days is not None and int(days or 0) > 0:
        try:
            pacific_today = datetime.now(timezone.utc).astimezone(
                _get_pacific_tzinfo()
            ).date()
            earliest_pacific_date = pacific_today - timedelta(
                days=max(int(days) - 1, 0)
            )
        except Exception:
            pacific_today = None
            earliest_pacific_date = None

    def _identity_for_session(rec: dict) -> str:
        user_id = str(rec.get('user_id') or '').strip()
        email = str(rec.get('email') or '').strip().lower()
        if user_id:
            return f"user:{user_id}"
        if email:
            return f"email:{email}"
        audit_id = str(rec.get('audit_id') or '').strip()
        return f"audit:{audit_id}" if audit_id else ""

    def _is_excluded_login_metric_email(email_value: str) -> bool:
        email_norm = _normalize_email(email_value or '')
        if not email_norm:
            return False
        if email_norm in EXCLUDED_LOGIN_METRIC_EMAILS:
            return True
        try:
            domain = email_norm.split('@', 1)[1].strip().lower()
        except Exception:
            domain = ''
        return bool(domain and domain in EXCLUDED_LOGIN_METRIC_DOMAINS)

    for rec in ordered:
        audit_id = str(rec.get('audit_id') or '').strip()
        if audit_id:
            if audit_id in seen_audit_ids:
                continue
            seen_audit_ids.add(audit_id)

        login_at = _login_at_from_audit_record(rec)
        if login_at is None:
            continue
        email = _normalize_email(rec.get('email') or '')
        if _is_excluded_login_metric_email(email):
            continue

        try:
            pacific_dt = login_at.astimezone(_get_pacific_tzinfo())
        except Exception:
            pacific_dt = login_at
        pacific_day = pacific_dt.date().isoformat()

        identity = _identity_for_session(rec)
        login_type = 'returning'
        if identity and identity not in seen_identities:
            seen_identities.add(identity)
            login_type = 'new'

        event = {
            'audit_id': audit_id,
            'user_id': str(rec.get('user_id') or '').strip(),
            'email': email,
            'login_at': login_at.isoformat(),
            'login_date_pacific': pacific_day,
            'login_time_pacific': _format_pacific_login_time(
                login_at,
                precise=True
            ),
            'login_time_pdt': _format_pacific_login_time(
                login_at,
                precise=True
            ),
            'login_time_pdt_precise': _format_pacific_login_time(
                login_at,
                precise=True
            ),
            'login_method': str(rec.get('login_method') or '').strip(),
            'login_type': login_type,
            'identity': identity,
        }
        if earliest_pacific_date is not None:
            try:
                event_date = pacific_dt.date()
            except Exception:
                event_date = None
            if event_date is None or event_date < earliest_pacific_date:
                continue
        classified_events.append(event)

    return classified_events


def _build_login_new_vs_returning_summary(
        sessions_list: list[dict]
) -> dict:
    """Classify recorded login events as first-time or returning by user/email identity."""
    classified_events = _build_classified_login_events(sessions_list)
    total_logins = 0
    new_user_logins = 0
    returning_user_logins = 0
    unique_identities: set[str] = set()
    daily_buckets: dict[str, dict] = {}

    for event in classified_events:
        pacific_day = str(event.get('login_date_pacific') or '').strip()
        identity = str(event.get('identity') or '').strip()
        bucket = daily_buckets.setdefault(
            pacific_day,
            {
                'date': pacific_day,
                'total_logins': 0,
                'new_user_logins': 0,
                'returning_user_logins': 0,
                'unique_identities': set(),
            },
        )

        total_logins += 1
        bucket['total_logins'] += 1
        if identity:
            unique_identities.add(identity)
            bucket['unique_identities'].add(identity)
        if str(event.get('login_type') or '') == 'new':
            new_user_logins += 1
            bucket['new_user_logins'] += 1
        else:
            returning_user_logins += 1
            bucket['returning_user_logins'] += 1

    daily_history = []
    for day_key in sorted(daily_buckets.keys(), reverse=True):
        bucket = daily_buckets.get(day_key) or {}
        daily_history.append(
            {
                'date': day_key,
                'total_logins': int(bucket.get('total_logins', 0) or 0),
                'new_user_logins': int(
                    bucket.get('new_user_logins', 0) or 0
                ),
                'returning_user_logins': int(
                    bucket.get('returning_user_logins', 0) or 0
                ),
                'unique_users': len(
                    bucket.get('unique_identities') or set()
                ),
            }
        )

    return {
        'total_logins': total_logins,
        'new_user_logins': new_user_logins,
        'returning_user_logins': returning_user_logins,
        'unique_users': len(unique_identities),
        'daily_history': daily_history,
    }


def _resolve_user_signup_date(
        uid: str,
        profile: dict,
        signup_lookup: dict[str, str]
) -> str:
    """Best-effort sign-up date from Azure profile, in-memory users, or CSV."""
    created_at = _coerce_datetime_iso(profile.get('created_at'))
    if created_at:
        return created_at
    try:
        mem_user = users.get(uid)
        if mem_user and getattr(mem_user, 'created_at', None):
            return _coerce_datetime_iso(mem_user.created_at)
    except Exception:
        pass
    return signup_lookup.get(uid, '')


def _resolve_user_last_login(
        uid: str,
        profile: dict,
        login_lookup: dict[str, dict]
) -> tuple[str, str]:
    """Best-effort last login from Azure profile or login audit/session stores."""
    profile_login = _coerce_datetime_iso(profile.get('last_login_at'))
    profile_method = str(profile.get('last_login_method') or '').strip()
    audit = login_lookup.get(uid) or {}
    audit_login = audit.get('login_at', '')
    audit_method = audit.get('login_method', '')

    profile_dt = _parse_iso_dt(profile_login)
    audit_dt = _parse_iso_dt(audit_login)
    if audit_dt and (profile_dt is None or audit_dt > profile_dt):
        return audit_login, audit_method or profile_method
    if profile_login:
        return profile_login, profile_method or audit_method
    return audit_login, audit_method


def _collect_registered_users_activity_rows(table_override: str = None) -> \
        list[dict]:
    """Build export rows with sign-up and last-login for all registered users."""
    users_rows, _, _ = _collect_registered_users_from_azure_users_table(
        table_override
    )
    revision_counts = _collect_revision_counts_by_user()
    signup_lookup = _build_signup_lookup_from_csv()
    login_lookup = _build_last_login_lookup()

    rows: list[dict] = []
    for profile in users_rows:
        uid = str(
            profile.get('id') or profile.get('PartitionKey') or ''
        ).strip()
        email = str(profile.get('email') or '').strip()
        name = str(profile.get('name') or '').strip()
        provider = str(profile.get('provider') or '').strip()
        plan_status = str(profile.get('plan_status') or '').strip().lower()
        is_paid = _profile_indicates_paid(profile)

        created_at = _resolve_user_signup_date(uid, profile, signup_lookup)
        last_login_at, last_login_method = _resolve_user_last_login(
            uid,
            profile,
            login_lookup
        )

        rows.append(
            {
                'user_id': uid,
                'email': email,
                'name': name,
                'provider': provider,
                'plan_status': plan_status or (
                    'paid' if is_paid else 'free'),
                'is_subscriber': 'yes' if is_paid else 'no',
                'sign_up_date': _format_any_datetime_pacific(
                    created_at
                ) or created_at or '',
                'sign_up_date_iso': created_at,
                'last_login_date': _format_any_datetime_pacific(
                    last_login_at
                ) or last_login_at or '',
                'last_login_date_iso': last_login_at,
                'last_login_method': last_login_method,
                'revision_count': revision_counts.get(uid, 0),
            }
        )

    rows.sort(key=lambda r: r.get('sign_up_date_iso') or '', reverse=True)
    return rows


def _collect_admin_dashboard_data(table_override: str = None) -> dict:
    """Build KPI summary and subscriber activity for admin dashboard (no full user list)."""
    users_rows, resolved_table, _ = _collect_registered_users_from_azure_users_table(
        table_override
    )
    revision_counts = _collect_revision_counts_by_user()
    signup_lookup = _build_signup_lookup_from_csv()
    login_lookup = _build_last_login_lookup()
    stripe_index = _fetch_stripe_subscriptions_index()

    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    kpis = {
        'total_users': 0,
        'active_subscribers': 0,
        'total_subscriptions_ever': 0,
        'stripe_subscriptions': stripe_index.get('total', 0),
        'matched_subscription_users': 0,
        'trial_users': 0,
        'free_users': 0,
        'canceled_subscribers': 0,
        'signups_7d': 0,
        'signups_30d': 0,
        'active_7d': 0,
        'active_30d': 0,
        'total_revisions': 0,
    }

    subscribers: list[dict] = []
    azure_only_profiles: list[dict] = []

    for row in users_rows:
        uid = str(row.get('id') or row.get('PartitionKey') or '').strip()
        email = str(row.get('email') or '').strip()
        plan_status = str(row.get('plan_status') or '').strip().lower()
        is_paid = _profile_indicates_paid(row)
        ever_subscribed = _profile_ever_had_subscription(row, stripe_index)
        loose_match = _profile_ever_had_subscription_loose(row)
        stored_sub_id = str(
            row.get('stripe_subscription_id') or ''
        ).strip()
        stored_cid = str(row.get('stripe_customer_id') or '').strip()

        created_at = _resolve_user_signup_date(uid, row, signup_lookup)
        last_login_at, _ = _resolve_user_last_login(uid, row, login_lookup)

        created_dt = _parse_iso_dt(created_at)
        last_login_dt = _parse_iso_dt(last_login_at)

        kpis['total_users'] += 1
        kpis['total_revisions'] += revision_counts.get(uid, 0)

        if created_dt and created_dt >= seven_days_ago:
            kpis['signups_7d'] += 1
        if created_dt and created_dt >= thirty_days_ago:
            kpis['signups_30d'] += 1
        if last_login_dt and last_login_dt >= seven_days_ago:
            kpis['active_7d'] += 1
        if last_login_dt and last_login_dt >= thirty_days_ago:
            kpis['active_30d'] += 1

        if is_paid:
            kpis['active_subscribers'] += 1
        elif plan_status in ('trial', 'trialing'):
            kpis['trial_users'] += 1
        elif plan_status in (
                'canceled', 'cancelled', 'past_due', 'unpaid'):
            kpis['canceled_subscribers'] += 1
        else:
            kpis['free_users'] += 1

        if loose_match and not ever_subscribed:
            azure_only_profiles.append(
                {
                    'email': email,
                    'plan_status': plan_status or '—',
                    'stripe_subscription_id': stored_sub_id or '—',
                    'stripe_customer_id': stored_cid or '—',
                    'reason': 'Azure profile marked as subscribed but no matching Stripe subscription',
                }
            )

    subscribers = _build_stripe_subscription_dashboard_rows(
        stripe_index,
        users_rows,
        signup_lookup,
        login_lookup,
        revision_counts,
    )

    if not subscribers and not stripe_index.get('error'):
        # Stripe unavailable: fall back to Azure profiles with a stored subscription id.
        for row in users_rows:
            if not str(row.get('stripe_subscription_id') or '').strip():
                continue
            uid = str(
                row.get('id') or row.get('PartitionKey') or ''
            ).strip()
            email = str(row.get('email') or '').strip()
            name = str(row.get('name') or '').strip()
            plan_status = str(row.get('plan_status') or '').strip().lower()
            is_paid = _profile_indicates_paid(row)
            paid_until = str(row.get('paid_until') or '').strip()
            created_at = _resolve_user_signup_date(uid, row, signup_lookup)
            last_login_at, last_login_method = _resolve_user_last_login(
                uid,
                row,
                login_lookup
            )
            revision_ts = row.get('revision_Timestamp') or row.get(
                'revision_timestamp'
            ) or ''
            revision_ts_str = _coerce_datetime_iso(revision_ts)
            status_label, status_badge = _subscription_status_for_dashboard(
                row,
                is_paid
            )
            azure_plan = _normalize_plan_id(plan_status)
            product_purchased = _plan_id_to_product_label(
                azure_plan
            ) if azure_plan else (plan_status or '—')
            subscribers.append(
                {
                    'id': uid or '—',
                    'email': email or '—',
                    'name': name or '—',
                    'product_purchased': product_purchased,
                    'plan_status': plan_status or '—',
                    'subscription_status': status_label,
                    'status_badge': status_badge,
                    'is_active': is_paid,
                    'stripe_subscription_id': str(
                        row.get('stripe_subscription_id') or ''
                    ).strip() or '—',
                    'stripe_customer_id': str(
                        row.get('stripe_customer_id') or ''
                    ).strip() or '—',
                    'azure_linked': True,
                    'match_source': 'azure_fallback',
                    'subscription_created_display': '—',
                    'paid_until_display': _format_paid_until(
                        paid_until
                    ) if paid_until else '—',
                    'created_at_display': _format_any_datetime_pacific(
                        created_at
                    ) or '—',
                    'last_login_display': _format_any_datetime_pacific(
                        last_login_at
                    ) or '—',
                    'last_login_method': last_login_method or '—',
                    'revision_count': revision_counts.get(uid, 0),
                    'last_revision_display': _format_any_datetime_pacific(
                        revision_ts_str
                    ) if revision_ts_str else '—',
                }
            )

    stripe_active_count = sum(1 for s in subscribers if s.get('is_active'))
    azure_linked_count = sum(
        1 for s in subscribers if s.get('azure_linked')
    )
    stripe_only_count = len(subscribers) - azure_linked_count

    kpis['stripe_subscriptions'] = len(subscribers)
    kpis['matched_subscription_users'] = azure_linked_count
    kpis['stripe_active_subscriptions'] = stripe_active_count

    reconciliation = {
        'stripe_total': stripe_index.get('total', len(subscribers)),
        'listed_subscriptions': len(subscribers),
        'azure_linked': azure_linked_count,
        'stripe_only': stripe_only_count,
        'azure_only_removed': len(azure_only_profiles),
        'stripe_active': stripe_active_count,
        'azure_only_profiles': azure_only_profiles[:20],
        'stripe_error': stripe_index.get('error'),
    }

    return {
        'kpis': kpis,
        'subscribers': subscribers,
        'reconciliation': reconciliation,
        'azure_table': resolved_table,
        'generated_at': _format_datetime_pacific(now.isoformat()),
    }


def _empty_admin_dashboard_data(
        error_message: str = '',
        table_name: str = 'Users'
) -> dict:
    """Fallback dashboard payload so the KPI page still renders on partial failures."""
    return {
        'kpis': {
            'total_users': 0,
            'active_subscribers': 0,
            'total_subscriptions_ever': 0,
            'stripe_subscriptions': 0,
            'matched_subscription_users': 0,
            'trial_users': 0,
            'free_users': 0,
            'canceled_subscribers': 0,
            'signups_7d': 0,
            'signups_30d': 0,
            'active_7d': 0,
            'active_30d': 0,
            'total_revisions': 0,
            'stripe_active_subscriptions': 0,
        },
        'subscribers': [],
        'reconciliation': {
            'stripe_total': 0,
            'listed_subscriptions': 0,
            'azure_linked': 0,
            'stripe_only': 0,
            'azure_only_removed': 0,
            'stripe_active': 0,
            'azure_only_profiles': [],
            'stripe_error': str(error_message or '').strip() or None,
        },
        'azure_table': str(table_name or 'Users'),
        'generated_at': _format_datetime_pacific(
            datetime.now(timezone.utc).isoformat()
        ),
    }


def _admin_users_activity_csv_response(table_override: str = None):
    """Build CSV response for registered-user sign-up and login activity."""
    import csv
    from io import StringIO

    rows = _collect_registered_users_activity_rows(table_override)
    columns = [
        'user_id', 'email', 'name', 'provider', 'plan_status',
        'is_subscriber',
        'sign_up_date', 'last_login_date', 'last_login_method',
        'revision_count',
    ]

    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        writer.writerow({col: row.get(col, '') for col in columns})

    csv_data = buf.getvalue()
    filename = f"registered_users_activity_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'},
    )


def _admin_login_breakdown_csv_response(days: int = 7):
    """Build CSV response for classified login events over the last N Pacific days."""
    import csv
    from io import StringIO

    safe_days = max(1, int(days or 7))
    sessions_list, _, _, _ = _load_login_audit_sessions_for_admin()
    rows = sorted(
        _build_classified_login_events(sessions_list, days=safe_days),
        key=lambda r: str(r.get('login_at') or ''),
        reverse=True,
    )

    columns = [
        'login_date_pacific',
        'login_time_pdt',
        'login_time_pdt_precise',
        'login_time_pacific',
        'email',
        'user_id',
        'login_type',
        'login_method',
        'audit_id',
    ]

    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        writer.writerow({col: row.get(col, '') for col in columns})

    csv_data = buf.getvalue()
    filename = f"login_breakdown_last_{safe_days}_days_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'},
    )


@app.route("/admin/users_activity.csv")
@app.route("/admin/dashboard/users.csv")
@login_required
def admin_users_activity_csv():
    """Download all registered users with sign-up and last-login dates (admin only)."""
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403
    try:
        table_name = (request.args.get('table') or '').strip() or None
        return _admin_users_activity_csv_response(table_name)
    except Exception as e:
        app.logger.error("admin_users_activity_csv error: %s", str(e))
        return jsonify({"error": "Internal server error"}), 500


@app.route("/admin/login_breakdown.csv")
@login_required
def admin_login_breakdown_csv():
    """Download classified new/returning login events for the last N days (admin only)."""
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403
    try:
        days = int((request.args.get('days') or '7').strip() or '7')
    except Exception:
        days = 7
    try:
        return _admin_login_breakdown_csv_response(days=days)
    except Exception as e:
        app.logger.error("admin_login_breakdown_csv error: %s", str(e))
        return jsonify({"error": "Internal server error"}), 500


@app.route("/admin")
@app.route("/admin/")
@login_required
def admin_index():
    """Redirect /admin to the KPI dashboard."""
    if not getattr(current_user, "is_admin", False):
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("index"))
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/dashboard")
@app.route("/admin/dashboard/")
@login_required
def admin_dashboard():
    """Admin KPI dashboard: subscribers, signups, and login activity."""
    if not current_user.is_authenticated:
        flash("You need to log in to view this page.", "danger")
        return redirect(url_for("login"))

    if not getattr(current_user, "is_admin", False):
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("index"))

    try:
        table_name = (request.args.get('table') or '').strip() or None
        export = (request.args.get('export') or '').strip().lower()
        if export in ('users_activity', 'users', 'csv'):
            return _admin_users_activity_csv_response(table_name)
        dashboard = _collect_admin_dashboard_data(table_name)
        login_audit_sessions, _, _, _ = _load_login_audit_sessions_for_admin()
        login_summary = _build_login_new_vs_returning_summary(
            login_audit_sessions
        )
        return render_template(
            "admin_dashboard.html",
            dashboard=dashboard,
            login_summary=login_summary,
            user=current_user,
        )
    except Exception as e:
        app.logger.error("Error loading admin dashboard: %s", str(e))
        err_text = str(e)
        if 'admin_login_breakdown_csv' not in err_text:
            flash(f"Error loading dashboard: {err_text}", "danger")
        table_name = (request.args.get('table') or '').strip() or 'Users'
        return render_template(
            "admin_dashboard.html",
            dashboard=_empty_admin_dashboard_data(err_text, table_name),
            login_summary=_build_login_new_vs_returning_summary([]),
            user=current_user,
        )


@app.route("/admin/stats")
@login_required
def admin_stats():
    """Admin page to view visit statistics."""
    if not current_user.is_authenticated:
        flash("You need to log in to view this page.", "danger")
        return redirect(url_for("login"))

    # Check if the user is an admin
    if not getattr(current_user, "is_admin", False):
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("index"))

    try:
        # Ensure admin form CSRF token exists (used by /admin/stats inline delete form)
        _get_admin_csrf_token()
        # Get comprehensive analytics data
        analytics_data = analytics.get_full_analytics()
        login_audit_sessions, _, _, _ = _load_login_audit_sessions_for_admin()
        login_summary = _build_login_new_vs_returning_summary(
            login_audit_sessions
        )

        # Registered Users are available on /admin/registered_users (Azure table: Users)
        # Load recent feedback submissions from CSV (if present)
        feedback_rows = []
        try:
            import csv

            feedback_path = 'download_feedback.csv'
            if os.path.exists(feedback_path):
                with open(
                        feedback_path,
                        'r',
                        encoding='utf-8',
                        newline=''
                ) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        feedback_rows.append(
                            {
                                'timestamp_iso': row.get(
                                    'timestamp_iso',
                                    ''
                                ),
                                'user_id': row.get('user_id', ''),
                                'user_email': row.get('user_email', ''),
                                'rating': row.get('rating', ''),
                                'comment': row.get('comment', ''),
                                'comparison': row.get('comparison', ''),
                            }
                        )
                # Keep only the last 100, newest first
                feedback_rows = feedback_rows[-100:][::-1]
        except Exception as e:
            app.logger.warning(
                f"Failed to read download_feedback.csv: {str(e)}"
            )

        # Debug logging to help troubleshoot
        app.logger.info(
            f"Analytics data structure: {type(analytics_data)}"
        )
        if isinstance(
                analytics_data,
                dict
        ) and 'summary' in analytics_data:
            app.logger.info(f"Summary data: {analytics_data['summary']}")
        else:
            app.logger.warning(
                f"Unexpected analytics data structure: {analytics_data}"
            )

        return render_template(
            "admin_stats.html",
            analytics=analytics_data,
            user=current_user,
            feedback_rows=feedback_rows,
            login_summary=login_summary
        )
    except Exception as e:
        app.logger.error(f"Error loading statistics: {str(e)}")
        flash(f"Error loading statistics: {str(e)}", "danger")
        return redirect(url_for("index"))


@app.route('/admin/feedback.csv')
@login_required
def admin_feedback_csv():
    """Download raw feedback CSV (admin only)."""
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403
    try:
        path = 'download_feedback.csv'
        if not os.path.exists(path):
            # Return an empty CSV with header for convenience
            from io import StringIO, BytesIO

            buf = StringIO(
                "timestamp_iso,user_id,user_email,rating,comment,comparison\n"
            )
            data = buf.getvalue().encode('utf-8')
            bio = BytesIO(data)
            bio.seek(0)
            return send_file(
                bio,
                mimetype='text/csv',
                as_attachment=True,
                download_name='download_feedback.csv'
            )
        return send_file(
            path,
            mimetype='text/csv',
            as_attachment=True,
            download_name='download_feedback.csv'
        )
    except Exception as e:
        app.logger.error(f"Failed to serve feedback CSV: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/admin/login_audit')
@app.route('/admin/login_audit/')
@login_required
def admin_login_audit():
    """Admin UI for viewing login timestamps + session durations."""
    if not current_user.is_authenticated:
        flash("You need to log in to view this page.", "danger")
        return redirect(url_for("login"))

    if not getattr(current_user, "is_admin", False):
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("index"))

    sessions_list, file_present, source_label, store = _load_login_audit_sessions_for_admin()
    login_summary = _build_login_new_vs_returning_summary(sessions_list)

    sessions_list.sort(
        key=lambda r: (_parse_iso_datetime(
            r.get('login_at')
        ) or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )

    # Pre-format times for display (keep original ISO values intact).
    formatted_sessions: list[dict] = []
    for rec in sessions_list:
        out = dict(rec)
        out['login_time_pst'] = _format_datetime_pacific(
            rec.get('login_at')
        )
        out['last_activity_time_pst'] = _format_datetime_pacific(
            rec.get('last_activity_at') or rec.get('login_at')
        )
        out['logout_time_pst'] = _format_datetime_pacific(
            rec.get('logout_at')
        )

        # If there is no explicit logout, estimate when the idle timeout would have logged them out.
        try:
            idle_seconds, _ = _auth_timeout_seconds()
            if not out.get('logout_at') and idle_seconds:
                last_dt = _parse_iso_datetime(
                    rec.get('last_activity_at') or rec.get('login_at')
                )
                if last_dt is not None:
                    est_dt = last_dt + timedelta(seconds=int(idle_seconds))
                    out['estimated_logout_at'] = est_dt.isoformat()
                    out[
                        'estimated_logout_time_pst'] = _format_datetime_pacific(
                        out.get('estimated_logout_at')
                    )
                else:
                    out['estimated_logout_time_pst'] = ''
            else:
                out['estimated_logout_time_pst'] = ''
        except Exception:
            out['estimated_logout_time_pst'] = ''

        try:
            secs = out.get('duration_seconds', None)
            if secs is None:
                out['duration_minutes'] = None
            else:
                out['duration_minutes'] = round(float(secs) / 60.0, 2)
        except Exception:
            out['duration_minutes'] = None
        formatted_sessions.append(out)

    return render_template(
        'admin_login_audit.html',
        sessions=formatted_sessions,
        login_summary=login_summary,
        store_version=(
            store.get('version') if isinstance(store, dict) else None),
        file_present=file_present,
        source_label=source_label,
    )


@app.route("/admin/cancellation_feedback")
@app.route("/admin/cancellation_feedback/")
@login_required
def admin_cancellation_feedback():
    """Admin UI for viewing subscription cancellation reasons."""
    if not current_user.is_authenticated:
        flash("You need to log in to view this page.", "danger")
        return redirect(url_for("login"))
    if not getattr(current_user, "is_admin", False):
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("index"))

    records = []
    file_present = False
    try:
        if os.path.exists(CANCELLATION_FEEDBACK_FILE):
            file_present = True
            with open(
                    CANCELLATION_FEEDBACK_FILE,
                    "r",
                    encoding="utf-8"
            ) as f:
                data = json.load(f)
                records = list(data.get("records") or [])
        records.reverse()
    except Exception as e:
        logger.warning("Failed to load cancellation feedback: %s", str(e))

    reason_labels = {
        "too_expensive": "Too expensive",
        "found_job": "Found a job / no longer need",
        "different_service": "Using a different service",
        "not_using": "Not using it enough",
        "missing_features": "Missing features I need",
        "technical_issues": "Technical issues",
        "other": "Other",
    }
    for r in records:
        r["reason_label"] = reason_labels.get(
            r.get("reason", ""),
            r.get("reason", "") or "—"
        )
        r["at_pacific"] = _format_datetime_pacific(r.get("at"))

    return render_template(
        "admin_cancellation_feedback.html",
        records=records,
        file_present=file_present,
    )


# Health check endpoint for Azure App Service
@app.route('/path/health', methods=['GET'])
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Azure App Service monitoring"""
    return jsonify(
        {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'service': 'resumatic',
            'build': _BUILD_ID,
            'pid': os.getpid(),
        }
    ), 200


from flask import Response


@app.route('/api/debug/playwright-log', methods=['GET'])
def api_debug_playwright_log():
    """Fetch Playwright install log from /home when Kudu is unreachable.

    Protected by DEBUG_TOKEN query param (set DEBUG_TOKEN in App Service settings).
    """
    try:
        expected = (os.getenv("DEBUG_TOKEN") or "").strip()
        provided = (request.args.get("token") or "").strip()
        if not expected or provided != expected:
            return jsonify({"error": "Forbidden"}), 403

        log_path = (os.getenv(
            "PLAYWRIGHT_INSTALL_LOG"
        ) or "/home/site/wwwroot/playwright-install.log").strip()
        max_bytes = 80_000
        if not os.path.exists(log_path):
            return jsonify(
                {
                    "ok": False,
                    "log_path": log_path,
                    "exists": False,
                }
            ), 200

        size = 0
        try:
            size = int(os.path.getsize(log_path))
        except Exception:
            size = 0

        data = b""
        try:
            with open(log_path, "rb") as f:
                if size > max_bytes:
                    f.seek(-max_bytes, os.SEEK_END)
                data = f.read()
        except Exception as e:
            return jsonify(
                {
                    "ok": False,
                    "log_path": log_path,
                    "exists": True,
                    "error": f"{type(e).__name__}: {str(e)}",
                }
            ), 200

        # Dependency probes for common Chromium/Playwright libs (missing libs cause TargetClosedError).
        deps = {}
        missing_libs = []
        try:
            import ctypes

            def _probe(lib: str):
                try:
                    ctypes.CDLL(lib)
                    return True
                except Exception as e:
                    return f"{type(e).__name__}: {str(e)}"

            probe_list = [
                "libglib-2.0.so.0",
                "libgobject-2.0.so.0",
                "libgio-2.0.so.0",
                "libnss3.so",
                "libnspr4.so",
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
            for lib in probe_list:
                res = _probe(lib)
                deps[lib] = res
                if res is not True:
                    missing_libs.append(lib)
        except Exception as e:
            deps["probe_error"] = f"{type(e).__name__}: {str(e)}"

        # Also list installed browser folders to confirm chromium-* exists.
        browser_fs = {}
        try:
            import glob as _glob

            browsers_path = (os.getenv(
                "PLAYWRIGHT_BROWSERS_PATH"
            ) or "/home/site/wwwroot/ms-playwright").strip()
            browser_fs["browsers_path"] = browsers_path
            browser_fs["entries"] = sorted(
                [p.replace(browsers_path + "/", "") for p in
                 _glob.glob(os.path.join(browsers_path, "*"))]
            )[:200]
        except Exception as e:
            browser_fs["error"] = f"{type(e).__name__}: {str(e)}"

        # If ldd is available, show missing dynamic deps for headless-shell/chromium binaries.
        ldd = {}
        try:
            import subprocess
            import shlex
            import glob as _glob

            browsers_path = (os.getenv(
                "PLAYWRIGHT_BROWSERS_PATH"
            ) or "/home/site/wwwroot/ms-playwright").strip()
            headless_shell = None
            hs_candidates = sorted(
                _glob.glob(
                    os.path.join(
                        browsers_path,
                        "chromium_headless_shell-*",
                        "**",
                        "chrome-headless-shell"
                    ),
                    recursive=True
                )
            )
            if hs_candidates:
                headless_shell = hs_candidates[0]
            chromium_bin = None
            c_candidates = []
            c_candidates += _glob.glob(
                os.path.join(
                    browsers_path,
                    "chromium-*",
                    "chrome-linux",
                    "chrome"
                )
            )
            c_candidates += _glob.glob(
                os.path.join(
                    browsers_path,
                    "chromium-*",
                    "chrome-linux",
                    "chrome-wrapper"
                )
            )
            if c_candidates:
                chromium_bin = sorted(c_candidates)[0]

            def _ldd(path: str):
                if not path:
                    return None
                proc = subprocess.run(
                    ["ldd", path],
                    capture_output=True,
                    text=True,
                    timeout=4,
                )
                out = (proc.stdout or "") + (proc.stderr or "")
                not_found = [ln for ln in out.splitlines() if
                             "not found" in ln]
                return {
                    "path": path,
                    "exit_code": proc.returncode,
                    "not_found": not_found[:50],
                }

            ldd["headless_shell"] = _ldd(headless_shell)
            ldd["chromium"] = _ldd(chromium_bin)
        except Exception as e:
            ldd["error"] = f"{type(e).__name__}: {str(e)}"

        return jsonify(
            {
                "ok": True,
                "log_path": log_path,
                "exists": True,
                "size": size,
                "tail": data.decode("utf-8", errors="replace"),
                "deps": deps,
                "missing_libs": missing_libs,
                "browser_fs": browser_fs,
                "ldd": ldd,
                "playwright_browsers_path": os.getenv(
                    "PLAYWRIGHT_BROWSERS_PATH"
                ),
            }
        ), 200
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {str(e)}"}), 500


@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    """Generate dynamic sitemap with only public pages"""
    pages = []
    lastmod = datetime.now().date().isoformat()

    # Define allowed public endpoints
    public_endpoints = {
        'index': {'priority': '1.0', 'changefreq': 'daily'},
        'about': {'priority': '0.8', 'changefreq': 'monthly'},
        'resume_org_alternative': {'priority': '0.9',
                                   'changefreq': 'weekly'},
        'blog': {'priority': '0.9', 'changefreq': 'weekly'},
        'resume_templates': {'priority': '0.9', 'changefreq': 'weekly'},
        'resume_builder': {'priority': '0.9', 'changefreq': 'weekly'},
        'plans': {'priority': '0.8', 'changefreq': 'monthly'},
        'discounts': {'priority': '0.7', 'changefreq': 'monthly'},
        'get_started': {'priority': '0.7', 'changefreq': 'monthly'},
        'contact': {'priority': '0.7', 'changefreq': 'monthly'},
        'privacy': {'priority': '0.3', 'changefreq': 'yearly'},
        'terms_privacy': {'priority': '0.3', 'changefreq': 'yearly'},
    }

    # Add static pages
    for endpoint, config in public_endpoints.items():
        try:
            url = url_for(endpoint, _external=True, _scheme='https')
            pages.append(
                f"""
                <url>
                    <loc>{url}</loc>
                    <lastmod>{lastmod}</lastmod>
                    <changefreq>{config['changefreq']}</changefreq>
                    <priority>{config['priority']}</priority>
                </url>"""
            )
        except Exception:
            # Skip if endpoint doesn't exist
            continue

    # Add blog posts (assuming they follow the pattern /blog/<post>)
    blog_posts = [
        'toptenmistakes',
        'ats-optimization',
        'Resume-objective',
        'no-experience',
        'Power-words',
        'resume-format-2026',
        'tailorresumejob'
    ]

    for post in blog_posts:
        try:
            url = url_for(
                'blog_post',
                post=post,
                _external=True,
                _scheme='https'
            )
            pages.append(
                f"""
                <url>
                    <loc>{url}</loc>
                    <lastmod>{lastmod}</lastmod>
                    <changefreq>monthly</changefreq>
                    <priority>0.8</priority>
                </url>"""
            )
        except Exception:
            continue

    sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        {''.join(pages)}
    </urlset>"""

    response = Response(sitemap_xml, mimetype='application/xml')
    response.headers[
        'Cache-Control'] = 'public, max-age=86400'  # Cache for 24 hours
    return response


@app.route('/api/feedback/download', methods=['POST'])
@login_required
def feedback_download_api():
    """Collect quick feedback after a logged-in user clicks to download a resume."""
    try:
        data = request.get_json(silent=True) or {}
        rating = str(data.get('rating', '')).strip()
        comment = str(data.get('comment', '')).strip()
        comparison = str(data.get('comparison', '')).strip()
        # Persist minimally to CSV; avoids DB schema work
        import csv
        from datetime import datetime, timezone

        filename = 'download_feedback.csv'
        file_exists = os.path.exists(filename)
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(
                    ['timestamp_iso', 'user_id', 'user_email', 'rating',
                     'comment', 'comparison']
                )
            writer.writerow(
                [
                    datetime.now(timezone.utc).isoformat(),
                    getattr(current_user, 'id', ''),
                    getattr(current_user, 'email', ''),
                    rating,
                    comment[:500],
                    comparison
                ]
            )
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logger.error(f"feedback_download_api error: {str(e)}")
        return jsonify({'status': 'error'}), 500


# Azure Table Storage setup
AZURE_TABLE_NAME = os.getenv('AZURE_TABLE_NAME', 'ResumeRevisions')
AZURE_STORAGE_ACCOUNT = os.getenv('AZURE_STORAGE_ACCOUNT')


def get_table_client(
        table_name: str = None,
        create_if_missing: bool = True
):
    connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    if connection_string:
        service = TableServiceClient.from_connection_string(
            conn_str=connection_string
        )
    else:
        # Import lazily: azure.identity import can be slow on some Windows hosts.
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        service = TableServiceClient(
            endpoint=f"https://{AZURE_STORAGE_ACCOUNT}.table.core.windows.net",
            credential=credential
        )
    table_client = service.get_table_client(table_name or AZURE_TABLE_NAME)
    if create_if_missing:
        try:
            table_client.create_table()
        except Exception:
            pass  # Table may already exist
    return table_client


# Azure Users table helpers
AZURE_USERS_TABLE = os.getenv('AZURE_USERS_TABLE', 'Users')


def get_users_table_client(*, create_if_missing: bool = True):
    return get_table_client(
        AZURE_USERS_TABLE,
        create_if_missing=create_if_missing
    )


def _collect_registered_users_from_azure_users_table(
        table_override: str = None
):
    """Collect user profiles directly from the Azure Users table.

    Expected schema (as written by upsert_user_profile_azure):
      PartitionKey=<user_id>, RowKey='profile', name, email, created_at, is_admin, provider
    """
    tried_tables = []
    if table_override:
        tried_tables = [table_override]
    else:
        env_table = (os.getenv('AZURE_USERS_TABLE') or '').strip()
        if env_table:
            tried_tables.append(env_table)
        # Back-compat / common variants
        tried_tables.extend(['user', 'Users'])

    # de-dupe in order
    seen = set()
    table_names = []
    for t in tried_tables:
        tt = (t or '').strip()
        if not tt or tt in seen:
            continue
        seen.add(tt)
        table_names.append(tt)

    last_error = None

    for table_name in table_names:
        try:
            table_client = get_table_client(
                table_name,
                create_if_missing=False
            )
            results = []
            # Prefer server-side filtering; fallback to client-side filter.
            try:
                pager = table_client.query_entities("RowKey eq 'profile'")
            except Exception:
                pager = table_client.list_entities()
            user_profiles = {}
            for e in pager:
                if str(e.get('RowKey') or '') != 'profile':
                    continue
                uid = str(e.get('PartitionKey') or '').strip()
                if not uid:
                    continue
                # Copy all profile fields
                profile_fields = dict(e)
                profile_fields['id'] = uid
                user_profiles[uid] = profile_fields

            # Join with ResumeRevisions: get all revisions for each user, pick latest
            revision_table_name = 'ResumeRevisions'
            revision_client = get_table_client(
                revision_table_name,
                create_if_missing=False
            )
            user_latest_revision = {}
            try:
                rev_pager = revision_client.list_entities()
                for entity in rev_pager:
                    uid = str(entity.get("PartitionKey") or '').strip()
                    if not uid:
                        continue
                    # Pick latest revision by Timestamp
                    ts = entity.get('Timestamp')
                    prev = user_latest_revision.get(uid)
                    if prev is None or (
                            ts and prev.get('Timestamp') and ts > prev.get(
                        'Timestamp'
                    )):
                        user_latest_revision[uid] = dict(entity)
            except Exception:
                pass

            results = []
            for uid, profile in user_profiles.items():
                merged = dict(profile)
                revision = user_latest_revision.get(uid)
                if revision:
                    for k, v in revision.items():
                        merged[f'revision_{k}'] = v
                merged['revisions'] = sum(
                    1 for r in user_latest_revision if r == uid
                )
                results.append(merged)

            # Build all_keys from the union of all keys across all rows
            all_keys = set()
            for row in results:
                all_keys.update(row.keys())

            if results:
                results.sort(
                    key=lambda r: (r.get('created_at') or ''),
                    reverse=True
                )
                return results, table_name, sorted(all_keys)
        except Exception as e:
            last_error = e
            continue

    if last_error:
        try:
            logger.warning(
                f"Failed to read Azure users table profiles: {str(last_error)}"
            )
        except Exception:
            pass
    return [], (table_names[0] if table_names else (
            os.getenv('AZURE_USERS_TABLE') or 'Users'))


FREE_REVISION_LIMIT = int(os.getenv('FREE_REVISION_LIMIT', '1'))
PAID_EMAILS = set(
    [e.strip().lower() for e in
     (os.getenv('PAID_EMAILS', '') or '').split(',') if e.strip()]
)


class FreeTierLimitReached(Exception):
    pass


def _parse_iso_dt(s: str):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def get_user_profile_azure(user_id: str) -> Optional[dict]:
    try:
        table_client = get_users_table_client()
        return table_client.get_entity(
            partition_key=str(user_id),
            row_key='profile'
        )
    except Exception:
        return None


def _format_paid_until(paid_until_str: str) -> str:
    """Best-effort formatting for paid_until ISO string."""
    s = (paid_until_str or "").strip()
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Show local-ish friendly date; keep time out for simplicity
        return dt.astimezone(timezone.utc).strftime("%b %d, %Y")
    except Exception:
        return s


def _profile_indicates_paid(prof: Optional[dict]) -> bool:
    """Evaluate paid access from a persisted profile entity."""
    try:
        if not prof:
            return False
        if _profile_has_active_trial_hold(prof):
            return True
        if bool(prof.get('is_paid', False)):
            paid_until = _parse_iso_dt(
                str(prof.get('paid_until') or '').strip()
            )
            if paid_until is None:
                return True
            return paid_until >= datetime.now(timezone.utc)
        plan_status = str(prof.get('plan_status') or '').strip().lower()
        if plan_status in ('paid', 'active', 'trial', 'monthly', 'annual'):
            paid_until = _parse_iso_dt(
                str(prof.get('paid_until') or '').strip()
            )
            if paid_until is None:
                return True
            return paid_until >= datetime.now(timezone.utc)
        return False
    except Exception:
        return False


_SUBSCRIPTION_PLAN_STATUSES = frozenset(
    {
        'paid', 'active', 'trialing', 'trial', 'trial_7d',
        'monthly', 'monthly_10_95', 'annual', 'annual_6_95',
        'canceled', 'cancelled', 'past_due', 'unpaid',
        'incomplete', 'incomplete_expired', 'paused',
    }
)


def _profile_ever_had_subscription_loose(prof: Optional[dict]) -> bool:
    """Legacy Azure-only heuristic (can over-count vs Stripe). Used for reconciliation."""
    try:
        if not prof:
            return False
        if str(prof.get('stripe_subscription_id') or '').strip():
            return True
        if str(prof.get('paid_until') or '').strip():
            return True
        plan_status = str(prof.get('plan_status') or '').strip().lower()
        if plan_status in _SUBSCRIPTION_PLAN_STATUSES:
            return True
        if str(
                prof.get('stripe_customer_id') or ''
        ).strip() and plan_status and plan_status != 'free':
            return True
        return False
    except Exception:
        return False


def _profile_ever_had_subscription(
        prof: Optional[dict],
        stripe_index: Optional[dict] = None
) -> bool:
    """True when profile is linked to a real Stripe subscription."""
    try:
        if not prof:
            return False
        if stripe_index is not None and _stripe_enabled() and not stripe_index.get(
                'error'
        ):
            matched, _ = _match_user_to_stripe_subscriptions(
                prof,
                stripe_index
            )
            return bool(matched)
        # Fallback when Stripe API unavailable: require stored subscription id.
        return bool(str(prof.get('stripe_subscription_id') or '').strip())
    except Exception:
        return False


def _subscription_status_for_dashboard(
        prof: Optional[dict],
        is_paid_active: bool,
        stripe_subs: Optional[list] = None,
) -> tuple[str, str]:
    """Return (display label, badge css class) for subscription table."""
    if stripe_subs:
        primary = stripe_subs[0]
        label = _stripe_sub_status_label(primary)
        status = str(getattr(primary, 'status', '') or '').strip().lower()
        if status in ('active', 'trialing'):
            return label, 'badge-trial' if status == 'trialing' else 'badge-subscriber'
        if status in ('canceled', 'cancelled'):
            return 'Canceled', 'badge-canceled'
        if status in ('past_due', 'unpaid'):
            return label, 'badge-canceled'
        return label, 'badge-free'

    plan_status = str(
        (prof or {}).get('plan_status') or ''
    ).strip().lower()
    if is_paid_active:
        if plan_status in ('trial', 'trialing', 'trial_7d'):
            return 'Active (Trial)', 'badge-trial'
        return 'Active', 'badge-subscriber'
    if plan_status in ('canceled', 'cancelled'):
        return 'Canceled', 'badge-canceled'
    if plan_status in ('past_due', 'unpaid'):
        return plan_status.replace('_', ' ').title(), 'badge-canceled'
    if plan_status in ('trial', 'trialing', 'trial_7d'):
        return 'Trial Ended', 'badge-trial'
    if plan_status in ('incomplete', 'incomplete_expired'):
        return plan_status.replace('_', ' ').title(), 'badge-free'
    if plan_status:
        return plan_status.replace('_', ' ').title(), 'badge-free'
    return 'Inactive', 'badge-free'


def is_paid_user(user_obj: Optional['User']) -> bool:
    try:
        if not user_obj or not getattr(
                user_obj,
                'is_authenticated',
                False
        ):
            return False
        if bool(getattr(user_obj, 'is_admin', False)):
            return True
        email = (getattr(user_obj, 'email', '') or '').strip().lower()
        if email and email in PAID_EMAILS:
            return True
        prof = get_user_profile_azure(getattr(user_obj, 'id', ''))
        if not prof:
            return False
        return _profile_indicates_paid(prof)
    except Exception:
        return False


def _refresh_paid_status_from_stripe_for_user(
        user_obj: Optional['User']
) -> bool:
    """Best-effort: infer paid status from Stripe by email/customer and persist to Azure profile.

    This is a safety net for cases where Stripe webhooks are delayed/misconfigured, or when
    Payment Links complete but the webhook hasn't updated Azure yet.
    """
    try:
        if not user_obj or not getattr(
                user_obj,
                'is_authenticated',
                False
        ):
            return False
        if not _stripe_enabled():
            return False

        user_id = str(getattr(user_obj, 'id', '') or '').strip()
        email = str(getattr(user_obj, 'email', '') or '').strip()
        if not user_id or not email:
            return False

        prof = get_user_profile_azure(user_id) or {}
        local_paid_fallback = _profile_indicates_paid(prof)

        try:
            _process_trial_hold_lifecycle_for_user(user_id)
            prof = get_user_profile_azure(user_id) or {}
            local_paid_fallback = _profile_indicates_paid(prof)
        except Exception:
            pass

        stored_customer_id = str(
            prof.get('stripe_customer_id') or ''
        ).strip()
        customer_id = stored_customer_id
        subscription_id = str(
            prof.get('stripe_subscription_id') or ''
        ).strip()

        try:
            if not customer_id:
                customer_id = _find_stripe_customer_id_by_email(email)
        except Exception:
            customer_id = customer_id or ''

        def _paid_until_from_plan_id(plan_id: str) -> str:
            pid = str(plan_id or '').strip()
            plan = _get_plan_config(pid) or {}
            days = int(plan.get('duration_days') or 31)
            if days < 1:
                days = 31
            return (datetime.now(timezone.utc) + timedelta(
                days=days
            )).isoformat()

        # Find best subscription for this customer (active > trialing > others).
        best_sub_id = subscription_id
        best_status = ''
        paid_until = ''
        plan_status_guess = ''
        try:

            best_sub_obj = None
            if best_sub_id:
                best_sub_obj = stripe.Subscription.retrieve(
                    best_sub_id,
                    expand=['pending_setup_intent']
                )
                best_status = str(
                    getattr(best_sub_obj, 'status', '') or ''
                ).strip().lower()
                cpe = getattr(best_sub_obj, 'current_period_end', None)
                if cpe:
                    paid_until = datetime.fromtimestamp(
                        int(cpe),
                        tz=timezone.utc
                    ).isoformat()
            elif customer_id:
                subs = stripe.Subscription.list(
                    customer=customer_id,
                    status='all',
                    limit=10
                )
                sdata = list(getattr(subs, 'data', []) or [])

                def _rank(sub):
                    status = str(
                        getattr(sub, 'status', '') or ''
                    ).strip().lower()
                    cpe = int(getattr(sub, 'current_period_end', 0) or 0)
                    sr = 0
                    if status == 'active':
                        sr = 3
                    elif status == 'trialing':
                        sr = 2
                    elif status in ('past_due', 'unpaid'):
                        sr = 1
                    return (sr, cpe)

                eligible = [s for s in sdata if
                            _stripe_subscription_grants_access(s)]
                if eligible:
                    best_sub_obj = \
                        sorted(eligible, key=_rank, reverse=True)[0]
                    best_sub_id = str(
                        getattr(best_sub_obj, 'id', '') or ''
                    ).strip()
                    best_status = str(
                        getattr(best_sub_obj, 'status', '') or ''
                    ).strip().lower()
                    cpe = getattr(best_sub_obj, 'current_period_end', None)
                    if cpe:
                        paid_until = datetime.fromtimestamp(
                            int(cpe),
                            tz=timezone.utc
                        ).isoformat()
        except Exception:
            # If Stripe is unreachable/misconfigured, don't crash gating.
            return bool(local_paid_fallback)

        paid_flag = bool(
            best_sub_obj and _stripe_subscription_grants_access(
                best_sub_obj
            )
        )

        # Fallback for Payment Links / one-time checkout sessions:
        # If there is no subscription at all, we can grant temporary access based on a recent paid
        # checkout session while waiting for profile/webhook sync. Do not do this when Stripe
        # already reports a subscription state (e.g., canceled), or we can incorrectly re-grant access.
        has_subscription_state = bool(
            (best_sub_id or '').strip() or (best_status or '').strip()
        )
        if (not paid_flag) and customer_id and (
                not has_subscription_state):
            try:

                sessions = stripe.checkout.Session.list(
                    customer=customer_id,
                    limit=10
                )
                sdata = list(getattr(sessions, 'data', []) or [])
                # Prefer the most recent *paid* session.
                sdata = sorted(
                    sdata,
                    key=lambda s: int(getattr(s, 'created', 0) or 0),
                    reverse=True
                )
                now_ts = int(time.time())
                recovery_window_secs = int(
                    os.getenv(
                        'STRIPE_CHECKOUT_RECOVERY_WINDOW_SECS',
                        '21600'
                    ) or '21600'
                )
                if recovery_window_secs < 300:
                    recovery_window_secs = 300
                for s in sdata:
                    status = str(
                        getattr(s, 'status', '') or ''
                    ).strip().lower()
                    pay_status = str(
                        getattr(s, 'payment_status', '') or ''
                    ).strip().lower()
                    mode = str(
                        getattr(s, 'mode', '') or ''
                    ).strip().lower()
                    created_ts = int(getattr(s, 'created', 0) or 0)
                    # One-time Checkout fallback is only for webhook lag shortly after purchase.
                    # Old paid sessions should not grant ongoing access after cancellation.
                    if created_ts <= 0 or (
                            now_ts - created_ts) > recovery_window_secs:
                        continue
                    if status == 'complete' and pay_status in (
                            'paid', 'no_payment_required'):
                        meta = getattr(s, 'metadata', None) or {}
                        plan_id = str(meta.get('plan_id') or '').strip()
                        # If metadata is missing, still treat as paid (default ~monthly duration).
                        plan_status_guess = plan_id or 'paid'
                        paid_until = paid_until or _paid_until_from_plan_id(
                            plan_id or 'monthly_10_95'
                        )
                        paid_flag = True
                        # If this session actually created a subscription, store it too.
                        try:
                            sid = str(
                                getattr(s, 'subscription', '') or ''
                            ).strip()
                            if sid:
                                best_sub_id = sid
                        except Exception:
                            pass
                        break
            except Exception:
                pass

        # Persist back to Azure profile for future requests.
        try:
            table_client = get_users_table_client()
            entity = {"PartitionKey": user_id, "RowKey": "profile"}
            entity["email"] = email
            should_persist_customer_id = bool(stored_customer_id)
            if not should_persist_customer_id and customer_id and (
                    paid_flag
                    or bool(best_sub_id)
                    or bool(plan_status_guess)
                    or bool(best_status)
            ):
                should_persist_customer_id = True
            if should_persist_customer_id and customer_id:
                entity["stripe_customer_id"] = str(customer_id)
            if best_sub_id:
                entity["stripe_subscription_id"] = str(best_sub_id)
            entity["is_paid"] = bool(paid_flag)
            if paid_flag and paid_until:
                entity["paid_until"] = paid_until
            elif not paid_flag:
                entity["paid_until"] = ""
            if paid_flag and paid_until:
                entity["paid_until"] = paid_until
            elif not paid_flag:
                entity["paid_until"] = ""

            raw_status = plan_status_guess or best_status or "active"

            if raw_status.lower() == 'trialing':
                final_status = 'trial'
            else:
                final_status = raw_status

            if paid_flag:
                entity["plan_status"] = final_status
            else:
                entity[
                    "plan_status"] = final_status if final_status != 'active' else 'free'
            table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
        except Exception:
            # Ignore Azure persistence errors; still return the computed paid flag.
            pass

        return bool(paid_flag)
    except Exception:
        return False


def is_paid_user_id(user_id: str) -> bool:
    try:
        u = users.get(str(user_id))
        if u:
            return is_paid_user(u)
        prof = get_user_profile_azure(str(user_id))
        if not prof:
            return False
        if _profile_indicates_paid(prof):
            return True
        email = str(prof.get('email') or '').strip().lower()
        return bool(email and email in PAID_EMAILS)
    except Exception:
        return False


def upsert_user_profile_azure(user_obj: 'User') -> None:
    try:
        table_client = get_users_table_client()
        provider = "google" if str(user_obj.id).isdigit() else (
            "facebook" if str(user_obj.id).startswith(
                "facebook_"
            ) else "other")
        entity = {
            'PartitionKey': str(user_obj.id),
            'RowKey': 'profile',
            'name': user_obj.name or '',
            'email': user_obj.email or '',
            'created_at': user_obj.created_at,
            'is_admin': bool(getattr(user_obj, 'is_admin', False)),
            'provider': provider,
        }
        if getattr(user_obj, 'password_hash', None):
            entity['password_hash'] = user_obj.password_hash
        entity['email_verified'] = bool(
            getattr(user_obj, 'email_verified', True)
        )
        if getattr(user_obj, 'email_verified_at', None):
            entity['email_verified_at'] = user_obj.email_verified_at
        if getattr(user_obj, 'email_verification_sent_at', None):
            entity[
                'email_verification_sent_at'] = user_obj.email_verification_sent_at
        if getattr(user_obj, 'welcome_email_sent_at', None):
            entity[
                'welcome_email_sent_at'] = user_obj.welcome_email_sent_at
        table_client.upsert_entity(entity)
    except Exception as e:
        logger.error(f"Failed to upsert user profile to Azure: {str(e)}")


# Save a revision to Azure Table Storage
def save_resume_revision(
        user_id,
        revision_id,
        resume_content,
        feedback=None,
        original_resume=None,
        notes=None,
        job_description=None
):
    from datetime import datetime, timezone

    # Enforce free tier cap (1 revision) for non-paid users.
    # Note: We enforce here as a safety net; primary gating happens earlier in /results.
    if not is_paid_user_id(user_id):
        try:
            existing = get_user_revisions(user_id)
            if len(existing) >= FREE_REVISION_LIMIT:
                raise FreeTierLimitReached(
                    "Free tier revision limit reached"
                )
        except FreeTierLimitReached:
            raise
        except Exception:
            # If counting fails, do not block saves.
            pass
    table_client = get_table_client()
    entity = {
        'PartitionKey': user_id,
        'RowKey': revision_id,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'resume_content': resume_content,
        'feedback': json.dumps(feedback) if feedback else '',
        'original_resume': original_resume or '',
        'notes': notes or '',
        'job_description': job_description or '',
        # Structured application tracking (list of {company, role, date_applied, status, link})
        'applications': '[]',
    }
    table_client.upsert_entity(entity)


def _parse_applications(raw):
    """Parse stored applications JSON safely into a list of dicts."""
    if not raw:
        return []
    if isinstance(raw, list):
        apps = raw
    else:
        s = str(raw)
        try:
            apps = json.loads(s) if s.strip() else []
        except Exception:
            apps = []
    if not isinstance(apps, list):
        return []
    cleaned = []
    for item in apps:
        if not isinstance(item, dict):
            continue
        entry = {
            'company': str(item.get('company', '') or '')[:120],
            'role': str(item.get('role', '') or '')[:120],
            'date_applied': str(item.get('date_applied', '') or '')[:32],
            'status': str(item.get('status', '') or '')[:40],
            'link': str(item.get('link', '') or '')[:500],
            'notes': str(item.get('notes', '') or '')[:4000],
            'next_action': str(item.get('next_action', '') or '')[:500],
            'follow_up_date': str(item.get('follow_up_date', '') or '')[
                              :32],
            'updated_at': str(item.get('updated_at', '') or '')[:32],
        }
        msgs = item.get('messages')
        if isinstance(msgs, list):
            cleaned_msgs = []
            for m in msgs:
                if not isinstance(m, dict):
                    continue
                body = str(
                    m.get('body') or m.get('rewritten_text') or m.get(
                        'original_text'
                    ) or ''
                ).strip()
                if not body:
                    continue
                cleaned_msgs.append(
                    {
                        'type': str(
                            m.get('type') or m.get('message_type') or ''
                        )[:40],
                        'subject': str(m.get('subject', '') or '')[:200],
                        'body': body[:4000],
                        'created_at': str(m.get('created_at', '') or '')[
                                      :32],
                    }
                )
            if cleaned_msgs:
                entry['messages'] = cleaned_msgs[-20:]
        cleaned.append(entry)
    return cleaned


def _truncate_coach_text(text, max_len=12000):
    s = str(text or '').strip()
    if len(s) <= max_len:
        return s
    return s[:max_len] + "\n...[truncated]"


def _format_revision_timestamp_for_coach(ts):
    if not ts:
        return ''
    try:
        if hasattr(ts, 'isoformat'):
            return ts.isoformat()
        return str(ts)
    except Exception:
        return str(ts or '')


def _build_job_search_coach_context(user_id):
    """Assemble dashboard context: latest resume revision + all tracked applications."""
    revisions = get_user_revisions(user_id) or []
    latest = revisions[0] if revisions else None

    latest_resume = None
    if latest:
        feedback = latest.get('feedback') if isinstance(
            latest.get('feedback'),
            dict
        ) else {}
        latest_resume = {
            'revision_id': str(latest.get('revision_id') or ''),
            'revision_name': str(
                latest.get('revision_name') or ''
            ).strip() or 'Latest resume',
            'created_at': _format_revision_timestamp_for_coach(
                latest.get('timestamp')
            ),
            'job_description': _truncate_coach_text(
                latest.get('job_description') or '',
                6000
            ),
            'resume_content': _truncate_coach_text(
                latest.get('resume_content') or '',
                12000
            ),
            'revision_notes': _truncate_coach_text(
                latest.get('notes') or '',
                2000
            ),
            'feedback_overall_score': feedback.get('overall_score'),
            'template_versions': [
                str(
                    tv.get('template_display_name') or tv.get(
                        'template_id'
                    ) or ''
                ).strip()
                for tv in (latest.get('template_versions') or [])
                if isinstance(tv, dict) and (
                        tv.get('template_display_name') or tv.get(
                    'template_id'
                ))
            ],
        }

    applications = []
    for rev in revisions:
        rev_name = str(
            rev.get('revision_name') or ''
        ).strip() or 'Untitled resume'
        rev_id = str(rev.get('revision_id') or '')
        for idx, app in enumerate(rev.get('applications') or []):
            if not isinstance(app, dict):
                continue
            app_entry = {
                'revision_name': rev_name,
                'revision_id': rev_id,
                'application_index': idx,
                'company': str(app.get('company') or '').strip(),
                'role': str(app.get('role') or '').strip(),
                'date_applied': str(app.get('date_applied') or '').strip(),
                'status': str(app.get('status') or '').strip(),
                'follow_up_date': str(
                    app.get('follow_up_date') or ''
                ).strip(),
                'next_action': str(app.get('next_action') or '').strip(),
                'link': str(app.get('link') or '').strip(),
                'notes': _truncate_coach_text(
                    app.get('notes') or '',
                    1500
                ),
            }
            msgs = app.get('messages') or []
            if isinstance(msgs, list) and msgs:
                app_entry['saved_messages'] = [
                    {
                        'type': str(m.get('type') or '').strip(),
                        'subject': str(m.get('subject') or '').strip(),
                        'body_preview': _truncate_coach_text(
                            m.get('body') or '',
                            400
                        ),
                    }
                    for m in msgs[-5:]
                    if
                    isinstance(m, dict) and (m.get('body') or '').strip()
                ]
            applications.append(app_entry)

    return {
        'latest_resume': latest_resume,
        'applications': applications,
        'application_count': len(applications),
        'revision_count': len(revisions),
    }


def _format_job_search_coach_context(ctx):
    lines = [
        "JOB SEARCH DASHBOARD CONTEXT",
        f"Total resume revisions: {ctx.get('revision_count', 0)}",
        f"Total tracked applications: {ctx.get('application_count', 0)}",
        "",
    ]

    latest = ctx.get('latest_resume')
    if latest:
        lines.extend(
            [
                "LATEST RESUME REVISION (most recent):",
                f"- Name: {latest.get('revision_name')}",
                f"- Revision ID: {latest.get('revision_id')}",
                f"- Created: {latest.get('created_at') or 'unknown'}",
            ]
        )
        score = latest.get('feedback_overall_score')
        if score is not None:
            lines.append(f"- Resume feedback score: {score}")
        templates = latest.get('template_versions') or []
        if templates:
            lines.append(
                f"- Saved template versions: {', '.join(templates)}"
            )
        if latest.get('revision_notes'):
            lines.append(
                f"- Revision notes: {latest.get('revision_notes')}"
            )
        if latest.get('job_description'):
            lines.extend(
                ["- Target job description:",
                 latest.get('job_description')]
            )
        if latest.get('resume_content'):
            lines.extend(
                ["- Resume content:", latest.get('resume_content')]
            )
    else:
        lines.append("LATEST RESUME REVISION: none saved yet.")

    lines.append("")
    apps = ctx.get('applications') or []
    if apps:
        lines.append("TRACKED JOB APPLICATIONS:")
        for i, app in enumerate(apps, start=1):
            lines.append(
                f"{i}. {app.get('company') or 'Unknown company'} — {app.get('role') or 'Unknown role'}"
            )
            lines.append(
                f"   Resume version: {app.get('revision_name')} (revision {app.get('revision_id')})"
            )
            if app.get('status'):
                lines.append(f"   Status: {app.get('status')}")
            if app.get('date_applied'):
                lines.append(f"   Date applied: {app.get('date_applied')}")
            if app.get('follow_up_date'):
                lines.append(
                    f"   Follow-up date: {app.get('follow_up_date')}"
                )
            if app.get('next_action'):
                lines.append(f"   Next action: {app.get('next_action')}")
            if app.get('link'):
                lines.append(f"   Link: {app.get('link')}")
            if app.get('notes'):
                lines.append(f"   Notes: {app.get('notes')}")
            saved = app.get('saved_messages') or []
            for msg in saved:
                label = msg.get('type') or 'message'
                subject = msg.get('subject') or ''
                preview = msg.get('body_preview') or ''
                if subject:
                    lines.append(
                        f"   Saved {label} ({subject}): {preview}"
                    )
                else:
                    lines.append(f"   Saved {label}: {preview}")
    else:
        lines.append("TRACKED JOB APPLICATIONS: none yet.")

    return "\n".join(lines)


# Get all revisions for a user
def get_user_revisions(user_id):
    revisions = []
    try:
        table_client = get_table_client()
        try:
            # Materialize to isolate downstream template rendering from paging/iteration errors.
            entities = list(
                table_client.query_entities(f"PartitionKey eq '{user_id}'")
            )
        except Exception:
            try:
                logger.exception(
                    "get_user_revisions query_entities failed (user_id=%s)",
                    str(user_id)
                )
            except Exception:
                pass
            return []

        for e in entities:
            try:
                timestamp_str = e.get('timestamp')
                if not timestamp_str:
                    timestamp_str = str(e.get('Timestamp')) if e.get(
                        'Timestamp'
                    ) else None
                try:
                    timestamp = datetime.fromisoformat(
                        timestamp_str
                    ) if timestamp_str else None
                    if timestamp and timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                except Exception:
                    timestamp = None

                feedback = {}
                if e.get('feedback'):
                    try:
                        feedback = json.loads(e['feedback'])
                    except Exception:
                        feedback = {}

                # Gather saved template versions (multi-template support)
                template_versions = []
                try:
                    raw_saved = str(
                        e.get('template_saved_templates', '') or ''
                    ).strip()
                    saved_list = json.loads(raw_saved) if raw_saved else []
                    if not isinstance(saved_list, list):
                        saved_list = []
                except Exception:
                    saved_list = []

                candidates = []
                if saved_list:
                    # Preserve stored order if present.
                    for t in saved_list:
                        tid = _canonical_template_id(str(t or '').strip())
                        if tid and tid not in candidates:
                            candidates.append(tid)
                else:
                    candidates = list(_KNOWN_TEMPLATE_IDS)

                seen = set()
                for tid in candidates:
                    plain_prop, gz_prop, at_prop = _template_snapshot_prop_names(
                        tid
                    )
                    if str(e.get(plain_prop, '') or '').strip() or str(
                            e.get(gz_prop, '') or ''
                    ).strip():
                        template_versions.append(
                            {
                                'template_id': tid,
                                'template_display_name': _format_template_display_name(
                                    tid
                                ),
                                'template_saved_at': str(
                                    e.get(at_prop, '') or ''
                                ).strip(),
                            }
                        )
                        seen.add(tid)

                # Backward compatibility: legacy single-snapshot field.
                legacy_has = bool(
                    str(
                        _entity_get_ci(
                            e,
                            'template_structured_resume',
                            ''
                        ) or ''
                    ).strip()
                    or str(
                        _entity_get_ci(
                            e,
                            'template_structured_resume_gz_b64',
                            ''
                        ) or ''
                    ).strip()
                    or str(
                        _entity_get_ci(
                            e,
                            'templateStructuredResume',
                            ''
                        ) or ''
                    ).strip()
                    or str(
                        _entity_get_ci(
                            e,
                            'templateStructuredResumeGzB64',
                            ''
                        ) or ''
                    ).strip()
                )
                legacy_tid = _canonical_template_id(
                    str(
                        _entity_get_ci(e, 'template_id', '') or ''
                    ).strip() or 'professional'
                )
                if legacy_has and legacy_tid not in seen:
                    template_versions.append(
                        {
                            'template_id': legacy_tid,
                            'template_display_name': _format_template_display_name(
                                legacy_tid
                            ),
                            'template_saved_at': str(
                                _entity_get_ci(
                                    e,
                                    'template_saved_at',
                                    ''
                                ) or ''
                            ).strip(),
                        }
                    )

                revision_name = str(
                    _entity_get_ci(e, 'revision_name', '')
                    or _entity_get_ci(e, 'resume_name', '')
                    or _entity_get_ci(e, 'resume_title', '')
                    or ''
                ).strip()

                revisions.append(
                    {
                        'revision_id': e.get('RowKey') or e.get(
                            'rowKey'
                        ) or '',
                        'timestamp': timestamp,
                        'resume_content': e.get('resume_content', ''),
                        'feedback': feedback,
                        'original_resume': e.get('original_resume', ''),
                        'revision_name': revision_name,
                        'notes': e.get('notes', ''),
                        'job_description': e.get('job_description', ''),
                        'applications': _parse_applications(
                            e.get('applications', '')
                        ),
                        # Optional: persisted template edit-mode snapshot
                        'template_id': str(
                            e.get('template_id', '') or ''
                        ).strip(),
                        'template_saved_at': str(
                            e.get('template_saved_at', '') or ''
                        ).strip(),
                        'has_template_snapshot': bool(template_versions),
                        'template_versions': template_versions,
                    }
                )
            except Exception:
                try:
                    rk = str(e.get('RowKey') or e.get('rowKey') or '')
                    logger.exception(
                        "get_user_revisions failed parsing entity (user_id=%s row_key=%s)",
                        str(user_id),
                        rk
                    )
                except Exception:
                    pass
                continue
    except Exception:
        try:
            logger.exception(
                "get_user_revisions failed (user_id=%s)",
                str(user_id)
            )
        except Exception:
            pass
        return []

    utc_min = datetime.min.replace(tzinfo=timezone.utc)
    try:
        revisions.sort(
            key=lambda x: x['timestamp'] or utc_min,
            reverse=True
        )
    except Exception:
        pass

    for r in revisions:
        try:
            apps = r.get('applications') or []
            has_apps = bool(apps)
            has_notes = bool((r.get('notes') or '').strip())
            r['has_applications'] = bool(has_apps or has_notes)
            r['applications_count'] = len(apps)
        except Exception:
            r['has_applications'] = False
            r['applications_count'] = 0
    return revisions


# Route: My Revisions
@app.route('/my_revisions')
@app.route('/my_revisions/', strict_slashes=False)
@login_required
def my_revisions():
    if _requires_email_verification(current_user):
        flash('Please verify your email to access your account.', 'danger')
        return redirect(
            url_for(
                'verify_email',
                email=getattr(current_user, 'email', '')
            )
        )
    revisions = []
    try:
        revisions = get_user_revisions(current_user.id) or []
    except Exception:
        revisions = []
    if revisions == []:
        # Best-effort hint; underlying error is logged in get_user_revisions.
        try:
            if not os.getenv(
                    'AZURE_STORAGE_CONNECTION_STRING'
            ) and not os.getenv('AZURE_STORAGE_ACCOUNT'):
                flash(
                    'Resume history is temporarily unavailable (storage not configured).',
                    'warning'
                )
        except Exception:
            pass
    today_iso = datetime.now(timezone.utc).date().isoformat()
    return render_template(
        'my_revisions.html',
        revisions=revisions,
        user=current_user,
        is_paid=is_paid_user(current_user),
        today_iso=today_iso,
    )


@app.route('/path/my_revisions')
@app.route('/path/my_revisions/', strict_slashes=False)
@login_required
def my_revisions_path():
    # Alias for environments that mount the app under /path.
    return my_revisions()


@app.route('/settings')
@login_required
def settings_page():
    if _requires_email_verification(current_user):
        flash('Please verify your email to access settings.', 'danger')
        return redirect(
            url_for(
                'verify_email',
                email=getattr(current_user, 'email', '')
            )
        )
    if str(request.args.get('canceled') or '').strip() == '1':
        flash(
            'Your subscription has been canceled. You\'ll keep access until the end of your billing period.',
            'success'
        )

    prof = get_user_profile_azure(getattr(current_user, 'id', '')) or {}
    paid_until_raw = str(prof.get('paid_until') or '').strip()
    stored_customer_id = str(prof.get('stripe_customer_id') or '').strip()
    customer_id = stored_customer_id
    subscription_id = str(prof.get('stripe_subscription_id') or '').strip()
    plan_status_raw = str(prof.get('plan_status') or '').strip()
    debug = str(request.args.get('debug') or '').strip() == '1'



    try:
        host = str(getattr(request, "host", "") or "").lower()
    except Exception:
        host = ""
    debug_allowed = bool(
        debug
        and (
                host.startswith("127.0.0.1")
                or host.startswith("localhost")
                or (os.getenv(
            "ENABLE_SETTINGS_DEBUG"
        ) or "").strip() == "1"
        )
    )
    debug_info = None

    paid_flag = bool(is_paid_user(current_user))
    cancel_scheduled = False

    # Sync with Stripe on settings loads so cancellations are reflected quickly even if webhooks lag.
    if _stripe_enabled():
        try:
            _refresh_paid_status_from_stripe_for_user(current_user)
            prof = get_user_profile_azure(
                getattr(current_user, 'id', '')
            ) or prof
            plan_status_raw = str(
                prof.get('plan_status') or plan_status_raw
            ).strip()
            paid_until_raw = str(
                prof.get('paid_until') or paid_until_raw
            ).strip()
            customer_id = str(
                prof.get('stripe_customer_id') or customer_id
            ).strip()
            subscription_id = str(
                prof.get('stripe_subscription_id') or subscription_id
            ).strip()
            paid_flag = bool(is_paid_user(current_user))
        except Exception:
            pass

    # Recovery routines for users with missing DB values
    if _stripe_enabled():
        try:
            if not customer_id:
                customer_id = _find_stripe_customer_id_by_email(
                    (getattr(current_user, 'email', '') or '').strip(),
                    require_subscription_history=False
                )

            # Subscriptions recovery block
            if customer_id and not subscription_id and plan_status_raw not in (
                    'trial', 'trial_7d'):
                subs = stripe.Subscription.list(
                    customer=customer_id,
                    status='all',
                    limit=10
                )
                sdata = list(getattr(subs, 'data', []) or [])

                def _rank(sub):
                    status = str(getattr(sub, 'status', '') or '').lower()
                    cpe = int(getattr(sub, 'current_period_end', 0) or 0)
                    return (
                        3 if status == 'active' else 2 if status == 'trialing' else 1,
                        cpe)

                if sdata:
                    eligible = [s for s in sdata if
                                _stripe_subscription_grants_access(s)]
                    if eligible:
                        best = sorted(eligible, key=_rank, reverse=True)[0]
                        subscription_id = str(
                            getattr(best, 'id', '') or ''
                        ).strip()
                        paid_flag = True

            # Backfill changes safely
            if customer_id or subscription_id:
                table_client = get_users_table_client()
                entity = {"PartitionKey": str(current_user.id),
                          "RowKey": "profile"}
                if customer_id:
                    entity["stripe_customer_id"] = str(customer_id)
                if subscription_id:
                    entity["stripe_subscription_id"] = str(subscription_id)
                table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
        except Exception:
            pass

    # Load defaults assuming standard dates
    stripe_dates = _get_stripe_plan_dates_for_customer(customer_id) if (
            paid_flag and customer_id) else {}
    if paid_flag and not stripe_dates and subscription_id:
        stripe_dates = _get_stripe_plan_dates_for_subscription(
            subscription_id
        )

    next_billing_iso = str(
        stripe_dates.get('next_billing_iso') or ''
    ).strip()
    paid_through_est_iso = str(
        stripe_dates.get('paid_through_est_iso') or ''
    ).strip()
    interval_label = str(stripe_dates.get('interval_label') or '').strip()
    stripe_status = str(stripe_dates.get('status') or '').strip().lower()

    # Determine explicit trial representation across standalone tiers
    is_standalone_trial = plan_status_raw.lower() in ('trial', 'trial_7d')
    if is_standalone_trial:
        interval_label = '7-Day Free Trial'
        if paid_until_raw:
            next_billing_iso = paid_until_raw
            paid_through_est_iso = paid_until_raw

        is_canceled_status = stripe_status in (
        'canceled', 'past_due') or plan_status_raw.lower() == 'canceled'
        if is_canceled_status:
            cancel_scheduled = True

    # Compute values from standard subscriptions if subscription ID is present
    try:
        if paid_flag and subscription_id and _stripe_enabled() and not is_standalone_trial:
            sub_obj = stripe.Subscription.retrieve(
                subscription_id,
                expand=["items.data.price"]
            )
            cancel_scheduled = bool(
                _stripe_subscription_cancel_scheduled(sub_obj)
            )

            si_price_id = ""
            try:
                si = stripe.SubscriptionItem.list(
                    subscription=subscription_id,
                    limit=1,
                    expand=["data.price"]
                )
                si_data = list(getattr(si, "data", []) or [])
                if si_data:
                    p = getattr(si_data[0], "price", None)
                    si_price_id = str(
                        p.get("id") if isinstance(p, dict) else getattr(
                            p,
                            "id",
                            p
                        ) or ""
                    ).strip()
            except Exception:
                pass

            status = str(
                _stripe_obj_get(sub_obj, "status", "") or ""
            ).strip().lower()
            stripe_status = status or stripe_status
            trial_end = _stripe_obj_get(sub_obj, "trial_end", None)
            current_period_end = _stripe_obj_get(
                sub_obj,
                "current_period_end",
                None
            )

            price_id, interval, interval_count = _get_subscription_price_id_and_recurring(
                sub_obj
            )
            if not price_id and si_price_id:
                price_id = si_price_id

            annual_ids = _configured_stripe_price_ids_for_plan(
                'annual_6_95'
            )
            monthly_ids = _configured_stripe_price_ids_for_plan(
                'monthly_10_95'
            )

            if not interval and price_id and price_id in annual_ids:
                interval, interval_count = 'year', 1
            if not interval and price_id and price_id in monthly_ids:
                interval, interval_count = 'month', 1

            if status == "trialing" and trial_end:
                next_ts = int(trial_end)
            else:
                next_ts = int(
                    current_period_end
                ) if current_period_end else None

            if next_ts:
                next_billing_iso = datetime.fromtimestamp(
                    next_ts,
                    tz=timezone.utc
                ).isoformat()
                paid_through_est_iso = next_billing_iso

            if interval == 'year':
                interval_label = 'Annual'
            elif interval == 'month':
                interval_label = 'Monthly'
    except Exception:
        pass

    has_active_access = bool(paid_flag or is_standalone_trial)

    if has_active_access:
        paid_until_raw = paid_through_est_iso or paid_until_raw
    else:
        # Only wipe details if they are truly on the base free plan
        paid_until_raw = ''
        next_billing_iso = ''
        interval_label = ''

    return render_template(
        'settings.html',
        user=current_user,
        email=(getattr(current_user, 'email', '') or '').strip(),
        name=(getattr(current_user, 'name', '') or '').strip(),
        is_paid=has_active_access,
        is_trial=is_standalone_trial or (stripe_status == 'trialing'),
        is_standalone_trial=is_standalone_trial,
        cancel_scheduled=bool(cancel_scheduled),
        plan_status=plan_status_raw,
        interval_label=interval_label,
        next_billing_display=_format_paid_until(next_billing_iso),
        paid_through_display=_format_paid_until(paid_until_raw),
        debug_info=debug_info if debug_allowed else None,
    )


@app.route('/api/me')
def api_me():
    """Lightweight user info for the React frontend (plan gating, limits)."""
    try:
        if not current_user.is_authenticated:
            return jsonify(
                {
                    "is_authenticated": False,
                    "is_paid": False,
                    "free_revision_limit": FREE_REVISION_LIMIT,
                    "revisions_used": 0,
                }
            )
        paid = is_paid_user(current_user)
        # Safety net: if webhooks haven't updated Azure yet, try to recover paid status from Stripe.
        if (not paid) and _stripe_enabled():
            try:
                # Don't hammer Stripe on every poll; cache briefly in session.
                now_ts = int(time.time())
                last_ts = int(session.get('stripe_paid_refresh_at') or 0)
                if now_ts - last_ts > 30:
                    session['stripe_paid_refresh_at'] = now_ts
                    session.modified = True
                    paid = bool(
                        _refresh_paid_status_from_stripe_for_user(
                            current_user
                        )
                    ) or paid
            except Exception:
                pass
        used = 0
        try:
            used = len(get_user_revisions(current_user.id))
        except Exception:
            used = 0
        return jsonify(
            {
                "is_authenticated": True,
                "is_paid": bool(paid),
                "free_revision_limit": FREE_REVISION_LIMIT,
                "revisions_used": used,
            }
        )
    except Exception:
        return jsonify(
            {
                "is_authenticated": False,
                "is_paid": False,
                "free_revision_limit": FREE_REVISION_LIMIT,
                "revisions_used": 0,
            }
        )


@app.route('/view_revision/<revision_id>')
@login_required
def view_revision(revision_id):
    revisions = get_user_revisions(current_user.id)
    rev = next(
        (r for r in revisions if r['revision_id'] == revision_id),
        None
    )
    if not rev:
        flash('Revision not found.', 'danger')
        return redirect(url_for('my_revisions'))

    # Ensure template selection works for saved revisions.
    # The template flow (/api/parse-resume-for-template) reads from session['results_data'].
    # When a user logs out/in, the session is fresh, so we must seed it from the revision
    # being viewed (otherwise template selection fails with "Resume data not found").
    session['results_data'] = {
        'original_resume': rev.get('original_resume', '') or '',
        'revised_resume': rev.get('resume_content', '') or '',
        'feedback': rev.get('feedback', {}) or {},
        'job_description': rev.get('job_description', '') or '',
        'source_revision_id': revision_id,
        'revision_name': rev.get('revision_name', '') or '',
    }
    # Prevent confusion from a previous template snapshot
    session.pop('template_data', None)
    session.modified = True

    return render_template(
        'result.html',
        revised_resume=rev['resume_content'],
        feedback=rev.get('feedback', {}),
        original_resume=rev.get('original_resume', ''),
        revision_name=rev.get('revision_name', '') or '',
        user=current_user
    )


@app.route('/update_revision_name', methods=['GET', 'POST'])
@app.route(
    '/update_revision_name/<revision_id>',
    methods=['GET', 'POST'],
    strict_slashes=False
)
@app.route('/path/update_revision_name', methods=['GET', 'POST'])
@app.route(
    '/path/update_revision_name/<revision_id>',
    methods=['GET', 'POST'],
    strict_slashes=False
)
# Extra robustness: if the browser resolves the relative form action under a trailing-slash
# my_revisions URL, it may post to /my_revisions/update_revision_name/<id>.
@app.route('/my_revisions/update_revision_name', methods=['GET', 'POST'])
@app.route(
    '/my_revisions/update_revision_name/<revision_id>',
    methods=['GET', 'POST'],
    strict_slashes=False
)
@app.route(
    '/path/my_revisions/update_revision_name',
    methods=['GET', 'POST']
)
@app.route(
    '/path/my_revisions/update_revision_name/<revision_id>',
    methods=['GET', 'POST'],
    strict_slashes=False
)
@login_required
def update_revision_name(revision_id=None):
    """Persist a user-defined label for a saved resume revision.

    Accept multiple URL shapes for robustness:
    - /update_revision_name/<revision_id>  (preferred)
    - /update_revision_name/<revision_id>/ (trailing slash)
    - /update_revision_name + revision_id in form/query (fallback)
    """
    wants_json = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in (request.headers.get('Accept') or '')
    )
    try:
        if not revision_id:
            revision_id = (request.form.get(
                'revision_id'
            ) or request.args.get('revision_id') or '').strip()

        if not revision_id:
            if wants_json:
                return jsonify(
                    {'ok': False, 'error': 'Missing revision id'}
                ), 400
            flash(
                'Error updating resume name. Please try again.',
                'danger'
            )
            return redirect(request.referrer or url_for('my_revisions'))

        # We only update on POST; GET requests are redirected back.
        if request.method != 'POST':
            return redirect(request.referrer or url_for('my_revisions'))

        revision_name = (request.form.get('revision_name') or '').strip()
        # Keep this user-facing label short to avoid blowing up card layout.
        revision_name = revision_name[:80]

        table_client = get_table_client()
        entity = table_client.get_entity(
            partition_key=current_user.id,
            row_key=revision_id
        )
        entity['revision_name'] = revision_name
        table_client.update_entity(entity, mode=UpdateMode.MERGE)
        if wants_json:
            return jsonify(
                {'ok': True, 'revision_id': revision_id,
                 'revision_name': revision_name}
            ), 200
    except Exception:
        if wants_json:
            return jsonify(
                {'ok': False,
                 'error': 'Error updating resume name. Please try again.'}
            ), 500
        flash('Error updating resume name. Please try again.', 'danger')
    return redirect(request.referrer or url_for('my_revisions'))


@app.route('/edit_revision_template/<revision_id>')
@login_required
def edit_revision_template(revision_id):
    """Open a saved revision directly in the React template viewer.

    Uses a persisted structured snapshot if available; otherwise falls back to parsing the
    stored revised resume text.
    """
    template_id = str(request.args.get('template') or '').strip() or None
    try:
        table_client = get_table_client()
        entity = table_client.get_entity(
            partition_key=str(current_user.id),
            row_key=str(revision_id)
        )
    except Exception:
        flash('Revision not found.', 'danger')
        return redirect(url_for('my_revisions'))

    resume_text = str(entity.get('resume_content', '') or '')
    job_description = str(entity.get('job_description', '') or '')

    feedback = {}
    if entity.get('feedback'):
        try:
            feedback = json.loads(entity.get('feedback') or '')
        except Exception:
            feedback = {}

    stored_template_id = str(entity.get('template_id', '') or '').strip()
    if not template_id:
        template_id = stored_template_id or 'professional'
    template_id = _canonical_template_id(template_id)

    structured_resume = None
    structured_resume = _load_structured_snapshot_for_template(
        entity,
        template_id
    )
    if structured_resume is None:
        try:
            structured_resume = parse_resume(resume_text).get('resume', {})
        except Exception:
            structured_resume = {}

    # Seed session so React can load + saves persist back to this revision.
    session['results_data'] = {
        'original_resume': str(entity.get('original_resume', '') or ''),
        'revised_resume': resume_text,
        'feedback': feedback,
        'job_description': job_description,
        'source_revision_id': str(revision_id),
    }
    session['template_data'] = {
        'structured_resume': structured_resume,
        'template_name': template_id,
        'revised_resume': resume_text,
        'source_revision_id': str(revision_id),
    }
    session.modified = True
    return redirect(
        url_for('react_app', subpath=f"template-viewer/{template_id}")
    )


@app.route('/download_revision_template_pdf/<revision_id>')
@login_required
def download_revision_template_pdf(revision_id):
    """Download a saved revision as a PDF.

    Uses a download-only React route that auto-downloads (no editor UI, no print dialog).
    """
    template_id = str(request.args.get('template') or '').strip() or None
    try:
        table_client = get_table_client()
        entity = table_client.get_entity(
            partition_key=str(current_user.id),
            row_key=str(revision_id)
        )
    except Exception:
        flash('Revision not found.', 'danger')
        return redirect(url_for('my_revisions'))

    resume_text = str(entity.get('resume_content', '') or '')
    job_description = str(entity.get('job_description', '') or '')

    feedback = {}
    if entity.get('feedback'):
        try:
            feedback = json.loads(entity.get('feedback') or '')
        except Exception:
            feedback = {}

    stored_template_id = str(entity.get('template_id', '') or '').strip()
    if not template_id:
        template_id = stored_template_id or 'professional'
    template_id = _canonical_template_id(template_id)

    structured_resume = None
    structured_resume = _load_structured_snapshot_for_template(
        entity,
        template_id
    )
    if structured_resume is None:
        try:
            structured_resume = parse_resume(resume_text).get('resume', {})
        except Exception:
            structured_resume = {}

    session['results_data'] = {
        'original_resume': str(entity.get('original_resume', '') or ''),
        'revised_resume': resume_text,
        'feedback': feedback,
        'job_description': job_description,
        'source_revision_id': str(revision_id),
    }
    session['template_data'] = {
        'structured_resume': structured_resume,
        'template_name': template_id,
        'revised_resume': resume_text,
        'source_revision_id': str(revision_id),
    }
    session.modified = True

    # Server-side PDF generation (avoids html2canvas issues with OKLAB/OKLCH colors).
    return redirect(url_for('api_template_pdf', template_id=template_id))


@app.route('/update_notes/<revision_id>', methods=['POST'])
@login_required
def update_notes(revision_id):
    try:
        notes = request.form.get('notes', '').strip()

        # Get the current revision to preserve existing data
        table_client = get_table_client()
        entity = table_client.get_entity(
            partition_key=current_user.id,
            row_key=revision_id
        )

        # Update only the notes field
        entity['notes'] = notes
        table_client.update_entity(entity)

        flash('Notes updated successfully!', 'success')
    except Exception as e:
        flash('Error updating notes. Please try again.', 'danger')

    return redirect(url_for('my_revisions'))


@app.route('/application/add/<revision_id>', methods=['POST'])
@login_required
def add_application(revision_id):
    try:
        company = (request.form.get('company') or '').strip()
        role = (request.form.get('role') or '').strip()
        date_applied = (request.form.get('date_applied') or '').strip()
        status = (request.form.get('status') or '').strip()
        link = (request.form.get('link') or '').strip()

        if not any([company, role, date_applied, status, link]):
            flash(
                'Please fill at least one field before adding an application.',
                'danger'
            )
            return redirect(url_for('my_revisions'))

        table_client = get_table_client()
        entity = table_client.get_entity(
            partition_key=current_user.id,
            row_key=revision_id
        )
        apps = _parse_applications(entity.get('applications', ''))
        apps.append(
            {
                'company': company,
                'role': role,
                'date_applied': date_applied,
                'status': status,
                'link': link,
            }
        )
        # Prevent unbounded growth
        apps = apps[-200:]
        entity['applications'] = json.dumps(apps)
        table_client.update_entity(entity, mode=UpdateMode.MERGE)
        flash('Application added!', 'success')
    except Exception:
        flash('Error adding application. Please try again.', 'danger')
    return redirect(url_for('my_revisions'))


@app.route('/application/delete/<revision_id>/<int:idx>', methods=['POST'])
@login_required
def delete_application(revision_id, idx: int):
    try:
        table_client = get_table_client()
        entity = table_client.get_entity(
            partition_key=current_user.id,
            row_key=revision_id
        )
        apps = _parse_applications(entity.get('applications', ''))
        if idx < 0 or idx >= len(apps):
            flash('Application not found.', 'danger')
            return redirect(url_for('my_revisions'))
        apps.pop(idx)
        entity['applications'] = json.dumps(apps)
        table_client.update_entity(entity, mode=UpdateMode.MERGE)
        flash('Application removed.', 'success')
    except Exception:
        flash('Error removing application. Please try again.', 'danger')
    return redirect(url_for('my_revisions'))


@app.route('/application/update/<revision_id>/<int:idx>', methods=['POST'])
@login_required
def update_application_notes(revision_id, idx: int):
    """Update tracked application status, follow-up fields, and notes."""
    try:
        table_client = get_table_client()
        entity = table_client.get_entity(
            partition_key=current_user.id,
            row_key=revision_id
        )
        apps = _parse_applications(entity.get('applications', ''))
        if idx < 0 or idx >= len(apps):
            flash('Application not found.', 'danger')
            return redirect(url_for('my_revisions'))

        app_item = apps[idx] if isinstance(apps[idx], dict) else {}
        if 'status' in request.form:
            app_item['status'] = (request.form.get(
                'status'
            ) or '').strip()[:40]
        if 'follow_up_date' in request.form:
            app_item['follow_up_date'] = (request.form.get(
                'follow_up_date'
            ) or '').strip()[:32]
        if 'next_action' in request.form:
            app_item['next_action'] = (request.form.get(
                'next_action'
            ) or '').strip()[:500]
        if 'notes' in request.form:
            app_item['notes'] = (request.form.get('notes') or '').strip()[
                                :4000]

        app_item['updated_at'] = datetime.now(timezone.utc).isoformat()
        apps[idx] = app_item
        entity['applications'] = json.dumps(apps)
        table_client.update_entity(entity, mode=UpdateMode.MERGE)
        flash('Application updated.', 'success')
    except Exception:
        flash('Error updating application. Please try again.', 'danger')
    return redirect(url_for('my_revisions'))


#############################################
# Admin: Registered Users from Azure Revisions
#############################################

def _collect_registered_users(table_override: str = None):
    """Collect distinct users from Azure Table revisions with counts and basic profile."""
    table_client = get_table_client(table_override)
    counts = {}
    # Ensure we iterate through all pages
    pager = table_client.list_entities(select=["PartitionKey"])
    for entity in pager:
        uid = entity.get("PartitionKey")
        if not uid:
            continue
        counts[uid] = counts.get(uid, 0) + 1

    results = []
    for uid, n in counts.items():
        user_obj = users.get(uid)
        email = getattr(user_obj, "email", "") if user_obj else ""
        name = getattr(user_obj, "name", "") if user_obj else ""
        provider = "google" if str(uid).isdigit() else (
            "facebook" if str(uid).startswith("facebook_") else "other")
        results.append(
            {
                "id": uid,
                "email": email,
                "name": name,
                "provider": provider,
                "revisions": n,
            }
        )

    results.sort(key=lambda x: x["revisions"], reverse=True)
    return results


@app.route('/admin/registered_users.json')
@login_required
def registered_users_json():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403
    table_name = (request.args.get('table') or '').strip() or 'Users'
    users_rows, resolved_table, all_keys = _collect_registered_users_from_azure_users_table(
        table_name
    )
    cta_sent_total = 0
    cta_sent_users = 0
    cta_converted_users = 0
    cta_conversion_events = 0
    paid_offer_sent_total = 0
    paid_offer_sent_users = 0
    paid_offer_click_total = 0
    paid_offer_apply_total = 0
    paid_offer_applied_users = 0
    for row in users_rows:
        try:
            sent_count = int(
                row.get("trial_reinstate_cta_sent_count", 0) or 0
            )
        except Exception:
            sent_count = 0
        try:
            conv_count = int(
                row.get("trial_reinstate_conversion_count", 0) or 0
            )
        except Exception:
            conv_count = 0
        converted_flag = bool(
            row.get("trial_reinstate_cta_converted", False)
        )
        try:
            paid_sent_count = int(
                row.get("paid_reinstate_offer_email_sent_count", 0) or 0
            )
        except Exception:
            paid_sent_count = 0
        try:
            paid_click_count = int(
                row.get("paid_reinstate_offer_click_count", 0) or 0
            )
        except Exception:
            paid_click_count = 0
        try:
            paid_apply_count = int(
                row.get("paid_reinstate_offer_apply_count", 0) or 0
            )
        except Exception:
            paid_apply_count = 0
        cta_sent_total += max(sent_count, 0)
        cta_conversion_events += max(conv_count, 0)
        paid_offer_sent_total += max(paid_sent_count, 0)
        paid_offer_click_total += max(paid_click_count, 0)
        paid_offer_apply_total += max(paid_apply_count, 0)
        if sent_count > 0:
            cta_sent_users += 1
        if paid_sent_count > 0:
            paid_offer_sent_users += 1
        if converted_flag or (sent_count > 0 and conv_count > 0):
            cta_converted_users += 1
        if paid_apply_count > 0:
            paid_offer_applied_users += 1
    cta_user_conversion_rate = (float(cta_converted_users) / float(
        cta_sent_users
    ) * 100.0) if cta_sent_users > 0 else 0.0
    cta_event_conversion_rate = (float(cta_conversion_events) / float(
        cta_sent_total
    ) * 100.0) if cta_sent_total > 0 else 0.0
    paid_offer_click_rate = (float(paid_offer_click_total) / float(
        paid_offer_sent_total
    ) * 100.0) if paid_offer_sent_total > 0 else 0.0
    paid_offer_apply_rate = (float(paid_offer_apply_total) / float(
        paid_offer_sent_total
    ) * 100.0) if paid_offer_sent_total > 0 else 0.0
    return jsonify(
        {
            "table": resolved_table,
            "columns": all_keys,
            "users": users_rows,
            "conversion_summary": {
                "cta_sent_total": cta_sent_total,
                "cta_sent_users": cta_sent_users,
                "cta_converted_users": cta_converted_users,
                "cta_conversion_events": cta_conversion_events,
                "cta_user_conversion_rate": round(
                    cta_user_conversion_rate,
                    1
                ),
                "cta_event_conversion_rate": round(
                    cta_event_conversion_rate,
                    1
                ),
                "paid_offer_sent_total": paid_offer_sent_total,
                "paid_offer_sent_users": paid_offer_sent_users,
                "paid_offer_click_total": paid_offer_click_total,
                "paid_offer_apply_total": paid_offer_apply_total,
                "paid_offer_applied_users": paid_offer_applied_users,
                "paid_offer_click_rate": round(paid_offer_click_rate, 1),
                "paid_offer_apply_rate": round(paid_offer_apply_rate, 1),
            },
        }
    )


def _format_value_pacific_if_datetime(val):
    """Format datetime values to Pacific time for display."""
    if val is None:
        return val
    if hasattr(val, "isoformat"):
        return _format_datetime_pacific(val.isoformat())
    if isinstance(val, str) and ("T" in val or (
            len(val) >= 19 and val[4] == "-" and val[7] == "-")):
        return _format_datetime_pacific(val)
    return val


@app.route('/admin/registered_users')
@login_required
def registered_users_view():
    if not getattr(current_user, "is_admin", False):
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("index"))
    table_name = (request.args.get('table') or '').strip() or 'Users'
    data, resolved_table, all_keys = _collect_registered_users_from_azure_users_table(
        table_name
    )
    for row in data:
        for k in list(row.keys()):
            v = row.get(k)
            if v is not None and (hasattr(v, "isoformat") or (
                    isinstance(v, str) and "T" in v)):
                row[k] = _format_value_pacific_if_datetime(v)
    # CTA conversion summary (trial cancellation reinstate email).
    cta_sent_total = 0
    cta_sent_users = 0
    cta_converted_users = 0
    cta_conversion_events = 0
    paid_offer_sent_total = 0
    paid_offer_sent_users = 0
    paid_offer_click_total = 0
    paid_offer_apply_total = 0
    paid_offer_applied_users = 0
    for row in data:
        sent_raw = row.get("trial_reinstate_cta_sent_count", 0)
        conv_raw = row.get("trial_reinstate_conversion_count", 0)
        converted_flag = bool(
            row.get("trial_reinstate_cta_converted", False)
        )
        paid_sent_raw = row.get("paid_reinstate_offer_email_sent_count", 0)
        paid_click_raw = row.get("paid_reinstate_offer_click_count", 0)
        paid_apply_raw = row.get("paid_reinstate_offer_apply_count", 0)
        try:
            sent_count = int(sent_raw or 0)
        except Exception:
            sent_count = 0
        try:
            conv_count = int(conv_raw or 0)
        except Exception:
            conv_count = 0
        try:
            paid_sent_count = int(paid_sent_raw or 0)
        except Exception:
            paid_sent_count = 0
        try:
            paid_click_count = int(paid_click_raw or 0)
        except Exception:
            paid_click_count = 0
        try:
            paid_apply_count = int(paid_apply_raw or 0)
        except Exception:
            paid_apply_count = 0

        cta_sent_total += max(sent_count, 0)
        cta_conversion_events += max(conv_count, 0)
        paid_offer_sent_total += max(paid_sent_count, 0)
        paid_offer_click_total += max(paid_click_count, 0)
        paid_offer_apply_total += max(paid_apply_count, 0)
        if sent_count > 0:
            cta_sent_users += 1
        if paid_sent_count > 0:
            paid_offer_sent_users += 1
        # Converted user if explicit flag is true or they reinstated after any CTA send.
        if converted_flag or (sent_count > 0 and conv_count > 0):
            cta_converted_users += 1
        if paid_apply_count > 0:
            paid_offer_applied_users += 1

    cta_user_conversion_rate = (float(cta_converted_users) / float(
        cta_sent_users
    ) * 100.0) if cta_sent_users > 0 else 0.0
    cta_event_conversion_rate = (float(cta_conversion_events) / float(
        cta_sent_total
    ) * 100.0) if cta_sent_total > 0 else 0.0
    paid_offer_click_rate = (float(paid_offer_click_total) / float(
        paid_offer_sent_total
    ) * 100.0) if paid_offer_sent_total > 0 else 0.0
    paid_offer_apply_rate = (float(paid_offer_apply_total) / float(
        paid_offer_sent_total
    ) * 100.0) if paid_offer_sent_total > 0 else 0.0

    conversion_summary = {
        "cta_sent_total": cta_sent_total,
        "cta_sent_users": cta_sent_users,
        "cta_converted_users": cta_converted_users,
        "cta_conversion_events": cta_conversion_events,
        "cta_user_conversion_rate": round(cta_user_conversion_rate, 1),
        "cta_event_conversion_rate": round(cta_event_conversion_rate, 1),
        "paid_offer_sent_total": paid_offer_sent_total,
        "paid_offer_sent_users": paid_offer_sent_users,
        "paid_offer_click_total": paid_offer_click_total,
        "paid_offer_apply_total": paid_offer_apply_total,
        "paid_offer_applied_users": paid_offer_applied_users,
        "paid_offer_click_rate": round(paid_offer_click_rate, 1),
        "paid_offer_apply_rate": round(paid_offer_apply_rate, 1),
    }

    return render_template(
        'admin_registered_users.html',
        users=data,
        azure_users_table_name=resolved_table,
        columns=all_keys,
        conversion_summary=conversion_summary,
    )


@app.route('/admin/registered_users.csv')
@login_required
def registered_users_csv():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403
    table_name = (request.args.get('table') or '').strip() or 'Users'
    rows, resolved_table, all_keys = _collect_registered_users_from_azure_users_table(
        table_name
    )
    # Build CSV in-memory
    lines = [','.join([f'"{k}"' for k in all_keys])]
    for r in rows:
        def esc(v):
            s = str(v or "")
            s = s.replace('"', '""')
            return f'"{s}"'

        line = ','.join([esc(r.get(k, '')) for k in all_keys])
        lines.append(line)
    csv_data = "\r\n".join(lines) + "\r\n"
    return Response(
        csv_data, mimetype='text/csv', headers={
            'Content-Disposition': f'attachment; filename=registered_users_{resolved_table}.csv'
        }
    )


@app.route('/admin/registered_users_activity.csv')
@login_required
def registered_users_activity_csv():
    """Download sign-up and last-login activity for all registered users (admin only)."""
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403
    try:
        table_name = (request.args.get('table') or '').strip() or None
        return _admin_users_activity_csv_response(table_name)
    except Exception as e:
        app.logger.error("registered_users_activity_csv error: %s", str(e))
        return jsonify({"error": "Internal server error"}), 500


@app.route('/admin/google_emails.json')
@login_required
def google_emails_json():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403
    # Read directly from persistent users file to include all registered users
    try:
        data = {}
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        emails = sorted(
            {
                (u.get('email') or '').strip().lower()
                for u in data.values()
                if u and u.get('email') and str(u.get('id', '')).isdigit()
            }
        )
        return jsonify({"count": len(emails), "emails": emails})
    except Exception as e:
        logger.error(f"google_emails_json error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/admin/google_emails.csv')
@login_required
def google_emails_csv():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403
    # Read directly from persistent users file to include all registered users
    try:
        data = {}
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        emails = sorted(
            {
                (u.get('email') or '').strip().lower()
                for u in data.values()
                if u and u.get('email') and str(u.get('id', '')).isdigit()
            }
        )
        csv_data = "email\n" + "\n".join(emails) + "\n"
        return Response(
            csv_data, mimetype='text/csv', headers={
                'Content-Disposition': 'attachment; filename=google_emails.csv'
            }
        )
    except Exception as e:
        logger.error(f"google_emails_csv error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


# Admin: Users from Azure Users table
@app.route('/admin/users_azure.json')
@login_required
def users_azure_json():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403
    provider_filter = (request.args.get('provider') or '').strip().lower()
    try:
        table_client = get_users_table_client()
        users_list = []
        for e in table_client.list_entities():
            if e.get('RowKey') != 'profile':
                continue
            provider = (e.get('provider') or '').lower()
            if provider_filter and provider != provider_filter:
                continue
            users_list.append(
                {
                    'id': e.get('PartitionKey'),
                    'name': e.get('name') or '',
                    'email': e.get('email') or '',
                    'provider': provider or 'other',
                    'created_at': e.get('created_at') or '',
                    'is_admin': bool(e.get('is_admin', False)),
                }
            )
        # Sort by created_at desc if present
        from datetime import datetime

        def parse_dt(s):
            try:
                return datetime.fromisoformat(s)
            except Exception:
                return datetime.min

        users_list.sort(
            key=lambda x: parse_dt(x.get('created_at') or ''),
            reverse=True
        )
        return jsonify({"count": len(users_list), "users": users_list})
    except Exception as e:
        logger.error(f"users_azure_json error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/admin/users_azure.csv')
@login_required
def users_azure_csv():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403
    provider_filter = (request.args.get('provider') or '').strip().lower()
    try:
        table_client = get_users_table_client()
        rows = []
        for e in table_client.list_entities():
            if e.get('RowKey') != 'profile':
                continue
            provider = (e.get('provider') or '').lower()
            if provider_filter and provider != provider_filter:
                continue
            rows.append(
                {
                    'id': e.get('PartitionKey'),
                    'name': e.get('name') or '',
                    'email': e.get('email') or '',
                    'provider': provider or 'other',
                    'created_at': e.get('created_at') or '',
                    'is_admin': 'true' if e.get(
                        'is_admin',
                        False
                    ) else 'false',
                }
            )

        def esc(v):
            s = str(v or "")
            if any(c in s for c in [',', '"', '\n', '\r']):
                s = '"' + s.replace('"', '""') + '"'
            return s

        header = ['id', 'name', 'email', 'provider', 'created_at',
                  'is_admin']
        lines = [','.join(header)]
        for r in rows:
            lines.append(','.join([esc(r[h]) for h in header]))
        csv_data = "\n".join(lines) + "\n"
        return Response(
            csv_data, mimetype='text/csv', headers={
                'Content-Disposition': 'attachment; filename=users_azure.csv'
            }
        )
    except Exception as e:
        logger.error(f"users_azure_csv error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/admin/user_sessions_azure.json')
@login_required
def user_sessions_azure_json():
    """Admin-only: list login session rows stored in the Azure Users table.

    Query params:
      - user_id: optional filter (PartitionKey)
      - limit: optional max rows (default 200)
    """
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403

    user_id = str(request.args.get('user_id') or '').strip()
    try:
        limit = int(request.args.get('limit') or 200)
    except Exception:
        limit = 200
    if limit < 1:
        limit = 1
    if limit > 2000:
        limit = 2000

    try:
        table_client = get_users_table_client(create_if_missing=False)
        sessions: list[dict] = []

        # Prefer server-side querying when possible.
        pager = None
        if user_id:
            try:
                pager = table_client.query_entities(
                    f"PartitionKey eq '{user_id}' and record_type eq 'session'"
                )
            except Exception:
                pager = None
        else:
            try:
                pager = table_client.query_entities(
                    "record_type eq 'session'"
                )
            except Exception:
                pager = None

        if pager is None:
            pager = table_client.list_entities()

        for e in pager:
            try:
                if str(e.get('record_type') or '') != 'session':
                    continue
                if user_id and str(
                        e.get('PartitionKey') or ''
                ).strip() != user_id:
                    continue
                sessions.append(
                    {
                        'user_id': str(e.get('PartitionKey') or ''),
                        'row_key': str(e.get('RowKey') or ''),
                        'email': e.get('email') or '',
                        'login_at': e.get('login_at') or '',
                        'last_activity_at': e.get(
                            'last_activity_at'
                        ) or '',
                        'logout_at': e.get('logout_at') or '',
                        'duration_seconds': e.get(
                            'duration_seconds',
                            None
                        ),
                        'login_method': e.get('login_method') or '',
                        'ip': e.get('ip') or '',
                        # Keep UA/referer for debugging; can be large.
                        'user_agent': e.get('user_agent') or '',
                        'referer': e.get('referer') or '',
                        'login_audit_pk': e.get('login_audit_pk') or '',
                        'login_audit_rk': e.get('login_audit_rk') or '',
                    }
                )
            except Exception:
                continue
            if limit and len(sessions) >= limit:
                break

        # Sort by login_at descending (ISO strings are sortable when consistently formatted).
        sessions.sort(
            key=lambda r: str(r.get('login_at') or ''),
            reverse=True
        )
        return jsonify(
            {
                'count': len(sessions),
                'user_id': user_id or None,
                'sessions': sessions,
            }
        )
    except Exception as e:
        logger.error(f"user_sessions_azure_json error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


# Admin: set plan/subscription fields on Azure Users profile (manual override until Stripe is integrated)
@app.route('/admin/set_user_plan', methods=['POST'])
@login_required
def admin_set_user_plan():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    user_id = str((data.get('user_id') or '')).strip()
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400
    # Supported fields
    plan_status = str(
        (data.get('plan_status') or '')
    ).strip().lower()  # free|trial|paid|active|canceled
    paid_until = str(
        (data.get('paid_until') or '')
    ).strip()  # ISO timestamp optional
    is_paid_flag = data.get('is_paid', None)  # boolean optional
    try:
        table_client = get_users_table_client()
        # MERGE upsert: do not clobber existing profile fields
        entity = {
            'PartitionKey': user_id,
            'RowKey': 'profile',
        }
        if plan_status:
            entity['plan_status'] = plan_status
        if paid_until:
            entity['paid_until'] = paid_until
        if isinstance(is_paid_flag, bool):
            entity['is_paid'] = bool(is_paid_flag)
        table_client.upsert_entity(entity)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"admin_set_user_plan error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


def _same_origin_post() -> bool:
    """Best-effort CSRF mitigation for admin POST endpoints (same-origin only)."""
    try:
        from urllib.parse import urlparse

        def host_only(netloc: str) -> str:
            # drop userinfo and port, keep hostname
            nl = (netloc or "").strip()
            if "@" in nl:
                nl = nl.split("@", 1)[1]
            if ":" in nl:
                nl = nl.split(":", 1)[0]
            return nl.lower()

        origin = (request.headers.get('Origin') or '').strip()
        referer = (request.headers.get('Referer') or '').strip()

        # Prefer forwarded host if present (Azure proxy), else fall back.
        req_host = host_only(
            (request.headers.get(
                'X-Forwarded-Host'
            ) or request.host or urlparse(request.host_url).netloc)
        )
        if not req_host:
            req_host = host_only(urlparse(request.host_url).netloc)

        if origin:
            return host_only(urlparse(origin).netloc) == req_host
        if referer:
            return host_only(urlparse(referer).netloc) == req_host
    except Exception:
        pass
    # If we can't determine, allow (keeps local/dev tools working).
    return True


def _get_admin_csrf_token() -> str:
    """Session-backed CSRF token for admin forms (reliable behind Azure proxies)."""
    try:
        tok = str(session.get('admin_csrf') or '').strip()
        if tok:
            return tok
        import secrets

        tok = secrets.token_urlsafe(32)
        session['admin_csrf'] = tok
        session.modified = True
        return tok
    except Exception:
        return ""


def _admin_delete_user_impl(
        email: str,
        user_id: str,
        delete_revisions: bool = True
) -> dict:
    email = (email or '').strip().lower()
    user_id = (user_id or '').strip()
    delete_revisions = True if delete_revisions is None else bool(
        delete_revisions
    )

    if not email and not user_id:
        return {"ok": False, "status": 400,
                "error": "Missing email or user_id"}

    resolved_ids: list[str] = []

    # Always include explicit user_id if provided
    if user_id:
        resolved_ids.append(user_id)

    # 1) Local in-memory users dict (covers email/password + cached oauth users)
    if email:
        for uid, u in list(users.items()):
            u_email = (getattr(u, 'email', '') or '').strip().lower()
            if u_email and u_email == email:
                resolved_ids.append(str(uid))

    # 2) Local persistent auth store file (covers the common "restart resurrects user" case)
    if email:
        try:
            if os.path.exists(USERS_FILE):
                with open(USERS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f) or {}
                for uid, ud in (data or {}).items():
                    e = str((ud or {}).get('email') or '').strip().lower()
                    if e and e == email:
                        resolved_ids.append(str(uid))
        except Exception:
            pass

    # 3) Azure Users table resolve by email (covers production)
    azure_resolve_error = ""
    if email:
        try:
            table_client = get_users_table_client()
            for e in table_client.list_entities():
                if str(e.get('RowKey') or '') != 'profile':
                    continue
                e_email = str(e.get('email') or '').strip().lower()
                if e_email == email:
                    pk = str(e.get('PartitionKey') or '').strip()
                    if pk:
                        resolved_ids.append(pk)
        except Exception as e:
            azure_resolve_error = str(e)

    # De-dupe
    seen = set()
    resolved_ids = [x for x in resolved_ids if
                    x and not (x in seen or seen.add(x))]

    if not resolved_ids:
        return {"ok": False, "status": 404, "error": "User not found",
                "azure_resolve_error": azure_resolve_error}

    deleted_local = 0
    # Remove from runtime dict first
    for uid in resolved_ids:
        if uid in users:
            try:
                users.pop(uid, None)
                deleted_local += 1
            except Exception:
                pass

    # Remove from persistent file by uid AND by email match (defensive)
    deleted_from_file = 0
    file_errors: list[str] = []
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f) or {}
        else:
            data = {}
        changed = False
        for uid in list(data.keys()):
            if str(uid) in resolved_ids:
                data.pop(uid, None)
                deleted_from_file += 1
                changed = True
                continue
            if email:
                e = str(
                    (data.get(uid) or {}).get('email') or ''
                ).strip().lower()
                if e and e == email:
                    data.pop(uid, None)
                    deleted_from_file += 1
                    changed = True
        if changed:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        file_errors.append(str(e))

    # Keep app behavior consistent if server stays up
    try:
        save_users()
    except Exception:
        pass

    # Azure Users profile delete (plan_status, stripe ids, etc live here)
    deleted_azure_profiles = 0
    deleted_azure_profile_errors: list[str] = []
    try:
        table_client = get_users_table_client()
        for uid in resolved_ids:
            try:
                table_client.delete_entity(
                    partition_key=str(uid),
                    row_key='profile'
                )
                deleted_azure_profiles += 1
            except Exception as e:
                deleted_azure_profile_errors.append(f"{uid}: {str(e)}")
            # Delete any other rows for the same PK (rare, but keep clean)
            try:
                for ent in table_client.query_entities(
                        f"PartitionKey eq '{str(uid)}'"
                ):
                    rk = str(ent.get('RowKey') or '').strip()
                    if not rk or rk == 'profile':
                        continue
                    try:
                        table_client.delete_entity(
                            partition_key=str(uid),
                            row_key=rk
                        )
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception as e:
        deleted_azure_profile_errors.append(f"azure_users_table: {str(e)}")

    # Azure ResumeRevisions delete (this is the critical "no old data" part)
    deleted_revisions = 0
    revision_delete_errors: list[str] = []
    if delete_revisions:
        try:
            rev_client = get_table_client(
                'ResumeRevisions',
                create_if_missing=False
            )
            for uid in resolved_ids:
                try:
                    for ent in rev_client.query_entities(
                            f"PartitionKey eq '{str(uid)}'"
                    ):
                        rk = str(ent.get('RowKey') or '').strip()
                        if not rk:
                            continue
                        try:
                            rev_client.delete_entity(
                                partition_key=str(uid),
                                row_key=rk
                            )
                            deleted_revisions += 1
                        except Exception:
                            pass
                except Exception as e:
                    revision_delete_errors.append(f"{uid}: {str(e)}")
        except Exception as e:
            revision_delete_errors.append(f"ResumeRevisions: {str(e)}")

    return {
        "ok": True,
        "status": 200,
        "resolved_user_ids": resolved_ids,
        "deleted_local": deleted_local,
        "deleted_from_file": deleted_from_file,
        "file_errors": file_errors,
        "deleted_azure_profiles": deleted_azure_profiles,
        "deleted_azure_profile_errors": deleted_azure_profile_errors,
        "deleted_revisions": deleted_revisions,
        "revision_delete_errors": revision_delete_errors,
        "delete_revisions": bool(delete_revisions),
    }


@app.route('/admin/delete_user', methods=['GET', 'POST'])
@login_required
def admin_delete_user():
    if not getattr(current_user, "is_admin", False):
        if request.method == 'POST':
            return jsonify({"error": "Forbidden"}), 403
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("index"))

    if request.method == 'GET':
        _get_admin_csrf_token()
        prefill_email = (request.args.get('email') or '').strip()
        prefill_user_id = (request.args.get('user_id') or '').strip()
        return render_template(
            'admin_delete_user.html',
            prefill_email=prefill_email,
            prefill_user_id=prefill_user_id
        )

    # POST
    # Validate CSRF token (do not rely on Origin/Referer — Azure proxies can break it)
    posted_csrf = ""
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        posted_csrf = str(
            payload.get('admin_csrf') or request.headers.get(
                'X-Admin-CSRF'
            ) or ''
        ).strip()
    else:
        posted_csrf = str(request.form.get('admin_csrf') or '').strip()
    expected_csrf = str(session.get('admin_csrf') or '').strip()
    if not expected_csrf or not posted_csrf or posted_csrf != expected_csrf:
        if request.is_json:
            return jsonify({"error": "Forbidden"}), 403
        flash(
            "Forbidden (CSRF check failed). Please refresh and try again.",
            "danger"
        )
        return redirect(url_for("admin_stats"))

    if request.is_json:
        data = request.get_json(silent=True) or {}
        email = str((data.get('email') or '')).strip()
        user_id = str((data.get('user_id') or '')).strip()
        delete_revisions = data.get('delete_revisions', True)
        res = _admin_delete_user_impl(
            email=email,
            user_id=user_id,
            delete_revisions=delete_revisions
        )
        return jsonify(res), int(res.get("status") or 200)

    # HTML form submit
    email = (request.form.get('email') or '').strip()
    user_id = (request.form.get('user_id') or '').strip()
    delete_revisions = bool(
        request.form.get('delete_revisions') in ('1', 'true', 'on', 'yes')
    )
    return_to = (request.form.get('return_to') or '').strip()
    res = _admin_delete_user_impl(
        email=email,
        user_id=user_id,
        delete_revisions=delete_revisions
    )
    if res.get("ok"):
        errs = len(res.get('deleted_azure_profile_errors') or []) + len(
            res.get('revision_delete_errors') or []
        ) + len(res.get('file_errors') or [])
        flash(
            f"Deleted user_id(s): {', '.join(res.get('resolved_user_ids') or [])}. "
            f"Deleted revisions: {res.get('deleted_revisions', 0)}. "
            f"Errors: {errs}",
            "success" if errs == 0 else "warning"
        )
    else:
        flash(f"Delete failed: {res.get('error')}", "danger")
    if return_to and _is_safe_next_url(return_to):
        return redirect(return_to)
    return render_template(
        'admin_delete_user.html',
        prefill_email=email,
        prefill_user_id=user_id,
        result=res
    )


def extract_text_from_file(file):
    """Extract text from uploaded file (PDF or DOCX), using fallback for complex Word docs."""
    try:
        filename = secure_filename(file.filename)
        file_extension = filename.lower().split('.')[-1]
        _safe_print(
            f"Processing file: {filename}, extension: {file_extension}"
        )

        if file_extension == 'pdf':
            text = ""
            try:
                with pdfplumber.open(file) as pdf:
                    _safe_print(f"PDF has {len(pdf.pages)} pages")
                    for page_num, page in enumerate(pdf.pages):
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                            _safe_print(
                                f"Page {page_num + 1}: {len(page_text)} characters extracted"
                            )
            except Exception as e:
                _safe_print(f"pdfplumber failed: {str(e)}, trying PyPDF2")
                file.seek(0)
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    text += page_text + "\n"
                    _safe_print(
                        f"Page {page_num + 1}: {len(page_text)} characters extracted"
                    )

            _safe_print(
                f"Total PDF text extracted: {len(text)} characters"
            )
            return text.strip()

        elif file_extension == 'docx':

            # Try python-docx first
            try:
                doc = Document(file)
                text = ""
                # Create a BytesIO copy for reuse
                file.seek(0)
                docx_buffer = BytesIO(file.read())
                for para_num, paragraph in enumerate(doc.paragraphs):
                    text += paragraph.text + "\n"

                _safe_print(
                    f"Total DOC text extracted: {len(text)} characters"
                )

                # Fallback if too little text
                if len(text.strip()) < 75:
                    _safe_print(
                        "Text too short, falling back to mammoth..."
                    )
                    docx_buffer.seek(0)
                    result = mammoth.extract_raw_text(docx_buffer)
                    text = result.value
                    _safe_print(
                        f"Text extracted using mammoth: {len(text)} characters"
                    )
            except Exception as e:
                _safe_print(
                    f"python-docx failed: {str(e)}, trying mammoth as fallback"
                )
                docx_buffer.seek(0)
                result = mammoth.extract_raw_text(docx_buffer)
                text = result.value
                _safe_print(
                    f"Text extracted using mammoth: {len(text)} characters"
                )

            return text.strip()

        else:
            raise ValueError(f"Unsupported file format: {file_extension}")

    except Exception as e:
        _safe_print(f"Error extracting text from file: {str(e)}")
        _safe_log_exception('extract_text_from_file error', e)
        raise ValueError(f"Failed to extract text from file: {str(e)}")


@app.route('/increment_counter', methods=['POST'])
def increment_counter():
    """API endpoint to increment resume counter (conversion tracking)"""
    try:
        # Use analytics module to track conversion
        conversion_result = analytics.track_conversion(
            session,
            "resume_submission"
        )

        if conversion_result.get("status") == "success":
            # Get updated total conversions count
            analytics_data = analytics.get_full_analytics()
            count = analytics_data.get('summary', {}).get(
                'total_conversions',
                0
            )
            return {"success": True, "count": count}
        else:
            return {"success": False,
                    "error": "Failed to track conversion"}, 500

    except Exception as e:
        return {"success": False, "error": str(e)}, 500


@app.route('/counter')
def counter_page():
    """Display counter page"""
    try:
        # Use the analytics module to get the total conversion count
        analytics_data = analytics.get_full_analytics()
        count = analytics_data.get('summary', {}).get(
            'total_conversions',
            0
        )

        # Fallback to legacy counter.json format if analytics doesn't work
        if count == 0:
            counter_file = 'counter.json'
            if os.path.exists(counter_file):
                with open(counter_file, 'r') as f:
                    data = json.load(f)
                    # Try new format first (total_conversions), then legacy format (count)
                    count = data.get(
                        'total_conversions',
                        data.get('count', 0)
                    )

        return render_template('counter.html', count=count)
    except Exception as e:
        # Log the error for debugging
        print(f"Counter page error: {str(e)}")
        return render_template('counter.html', count=0)


@app.route('/counter.html')
def counter_html_legacy():
    """Redirect old /counter.html URL to the canonical /counter route."""
    return redirect(url_for('counter_page'), code=301)


@app.route('/robots.txt')
def robots_txt():
    """Serve robots.txt file"""
    try:
        response = send_file('robots.txt', mimetype='text/plain')
        if not app.debug:
            response.headers[
                'Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers[
                'Cache-Control'] = 'public, max-age=86400'  # Cache for 24 hours
        return response
    except Exception as e:
        # Fallback content if file is not found
        content = """User-agent: *
Allow: /
Disallow: /admin/
Disallow: /private/

Sitemap: https://resumaticai.com/sitemap.xml
Host: https://resumaticai.com"""
        response = Response(content, mimetype='text/plain')
        if not app.debug:
            response.headers[
                'Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response


@app.route('/sitemap-static.xml')
def sitemap_static():
    """Serve static sitemap.xml file as backup"""
    try:
        response = send_file('sitemap.xml', mimetype='application/xml')
        response.headers[
            'Cache-Control'] = 'public, max-age=86400'  # Cache for 24 hours
        return response
    except Exception as e:
        # Fallback to dynamic sitemap
        return redirect(url_for('sitemap'))


@app.route('/ads.txt')
def ads_txt():
    """Serve ads.txt file"""
    response = send_file('ads.txt', mimetype='text/plain')
    if not app.debug:
        response.headers[
            'Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Cache-Control'] = 'public, max-age=86400'
    return response


@app.route('/llms.txt')
def llms_txt():
    """Serve llms.txt file"""
    response = send_file('llms.txt', mimetype='text/plain')
    # Add security headers to ensure HTTPS preference
    if not app.debug:
        response.headers[
            'Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Cache-Control'] = 'public, max-age=86400'
    return response


@app.route('/subscribers')
@login_required
def subscribers():
    """Show subscribers page with actual subscriber data"""
    # Check if the user is an admin
    if not getattr(current_user, "is_admin", False):
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("index"))

    try:
        subscriber_list = []
        subscriber_count = 0

        # Read subscribers from CSV file
        if os.path.exists("subscribers.csv"):
            with open("subscribers.csv", "r") as f:
                lines = f.readlines()
                # Skip header row if present
                for line in lines[1:] if lines and lines[
                    0].strip().lower() == 'email' else lines:
                    email = line.strip()
                    if email:  # Only add non-empty emails
                        subscriber_list.append(
                            {
                                'email': email,
                                'date_added': 'Unknown'
                                # CSV doesn't store dates
                            }
                        )
                        subscriber_count += 1

        # Sort subscribers alphabetically
        subscriber_list.sort(key=lambda x: x['email'].lower())

        return render_template(
            'subscribers.html',
            subscribers=subscriber_list,
            total_count=subscriber_count,
            user=current_user
        )
    except Exception as e:
        flash(f"Error loading subscribers: {str(e)}", "danger")
        return render_template(
            'subscribers.html',
            subscribers=[],
            total_count=0,
            user=current_user
        )


@app.route('/signup')
def signup():
    """Show signup page"""
    _set_auth_next_from_request()
    next_url = str(session.get('auth_next') or '').strip()
    return render_template('signup.html', next_url=next_url)


# Newsletter Management Routes
@app.route('/admin/newsletter')
@login_required
def newsletter_admin():
    """Newsletter administration dashboard"""
    if not current_user.is_authenticated:
        flash("You need to log in to view this page.", "danger")
        return redirect(url_for("login"))

    # Check if the user is an admin
    if not getattr(current_user, "is_admin", False):
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("index"))

    try:
        # Get newsletter archives
        newsletter_files = []
        email_history = []
        if os.path.exists("newsletters"):
            for filename in os.listdir("newsletters"):
                if filename.endswith(".json"):
                    try:
                        with open(
                                os.path.join("newsletters", filename),
                                "r"
                        ) as f:
                            data = json.load(f)
                        newsletter_files.append(
                            {
                                "filename": filename,
                                "month": data.get("month"),
                                "year": data.get("year"),
                                "subject": data.get("subject"),
                                "generated_at": data.get("generated_at"),
                                "send_stats": data.get("send_stats", {})
                            }
                        )
                    except Exception as e:
                        logger.error(
                            f"Error reading newsletter file {filename}: {str(e)}"
                        )

        # Sort by year and month (newest first)
        newsletter_files.sort(
            key=lambda x: (x.get("year", 0), x.get("month", "")),
            reverse=True
        )

        # Get subscriber count
        subscriber_count = 0
        if os.path.exists("subscribers.csv"):
            with open("subscribers.csv", "r") as f:
                lines = f.readlines()
                subscriber_count = len(
                    [line for line in lines[1:] if line.strip()]
                ) if lines else 0

        email_history = read_email_events(limit=500)

        return render_template(
            'newsletter_admin.html',
            newsletters=newsletter_files,
            subscriber_count=subscriber_count,
            email_history=email_history,
            user=current_user
        )
    except Exception as e:
        flash(f"Error loading newsletter dashboard: {str(e)}", "danger")
        return redirect(url_for("admin_stats"))


@app.route('/admin/newsletter/generate', methods=['POST'])
@login_required
def generate_newsletter():
    """Generate a new newsletter"""
    if not getattr(current_user, "is_admin", False):
        flash(
            "You do not have permission to access this feature.",
            "danger"
        )
        return redirect(url_for("index"))

    try:
        # Get form data
        month = request.form.get('month')
        year_str = request.form.get('year')
        custom_topics_str = request.form.get('custom_topics', '').strip()
        preview_only = request.form.get('preview_only') == 'on'

        # Validate inputs
        if not month or not year_str:
            flash("Please select both month and year.", "danger")
            return redirect(url_for('newsletter_admin'))

        try:
            year = int(year_str)
        except ValueError:
            flash("Invalid year provided.", "danger")
            return redirect(url_for('newsletter_admin'))

        # Parse custom topics
        custom_topics = None
        if custom_topics_str:
            custom_topics = [topic.strip() for topic in
                             custom_topics_str.split(',') if topic.strip()]

        # Initialize newsletter manager
        newsletter_manager = NewsletterManager()

        # Generate newsletter
        result = newsletter_manager.create_and_send_newsletter(
            month=month,
            year=year,
            custom_topics=custom_topics,
            preview_only=preview_only
        )

        if preview_only:
            flash(
                f"Newsletter preview generated for {month} {year}! Check the archives to view it.",
                "success"
            )
        else:
            send_stats = result.get('send_stats', {})
            flash(
                f"Newsletter sent! {send_stats.get('sent', 0)} emails sent successfully, {send_stats.get('failed', 0)} failed.",
                "success"
            )

        return redirect(url_for('newsletter_admin'))

    except Exception as e:
        logger.error(f"Error generating newsletter: {str(e)}")
        flash(f"Error generating newsletter: {str(e)}", "danger")
        return redirect(url_for('newsletter_admin'))


@app.route('/admin/newsletter/preview/<path:filename>')
@login_required
def preview_newsletter(filename):
    """Preview a newsletter"""
    if not getattr(current_user, "is_admin", False):
        flash(
            "You do not have permission to access this feature.",
            "danger"
        )
        return redirect(url_for("index"))

    try:
        # Security check - ensure filename is safe
        safe_filename = secure_filename(filename)
        if not safe_filename.endswith('.html'):
            safe_filename += '.html'

        filepath = os.path.join("newsletters", safe_filename)

        if not os.path.exists(filepath):
            flash("Newsletter not found.", "danger")
            return redirect(url_for('newsletter_admin'))

        return send_file(filepath)

    except Exception as e:
        logger.error(f"Error previewing newsletter: {str(e)}")
        flash("Error loading newsletter preview.", "danger")
        return redirect(url_for('newsletter_admin'))


@app.route('/admin/newsletter/send/<path:filename>', methods=['POST'])
@login_required
def send_existing_newsletter(filename):
    """Send an existing newsletter"""
    if not getattr(current_user, "is_admin", False):
        flash(
            "You do not have permission to access this feature.",
            "danger"
        )
        return redirect(url_for("index"))

    try:
        # Security check
        safe_filename = secure_filename(filename)
        if not safe_filename.endswith('.json'):
            safe_filename += '.json'

        filepath = os.path.join("newsletters", safe_filename)

        if not os.path.exists(filepath):
            flash("Newsletter not found.", "danger")
            return redirect(url_for('newsletter_admin'))

        # Load newsletter data
        with open(filepath, "r") as f:
            newsletter_data = json.load(f)

        # Initialize newsletter manager and send
        newsletter_manager = NewsletterManager()
        send_stats = newsletter_manager.sender.send_newsletter(
            subject=newsletter_data["subject"],
            html_content=newsletter_data["html_content"],
            text_content=newsletter_data["text_content"]
        )

        # Update the newsletter file with send stats
        newsletter_data["send_stats"] = send_stats
        newsletter_data["last_sent"] = datetime.now(
            timezone.utc
        ).isoformat()

        with open(filepath, "w") as f:
            json.dump(newsletter_data, f, indent=2)

        flash(
            f"Newsletter sent! {send_stats.get('sent', 0)} emails sent successfully, {send_stats.get('failed', 0)} failed.",
            "success"
        )

    except Exception as e:
        logger.error(f"Error sending newsletter: {str(e)}")
        flash(f"Error sending newsletter: {str(e)}", "danger")

    return redirect(url_for('newsletter_admin'))


@app.route('/api/newsletter/test', methods=['POST'])
@login_required
def test_newsletter_config():
    """Test newsletter configuration (SMTP settings)"""
    if not getattr(current_user, "is_admin", False):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    try:
        config = NewsletterConfig()

        # Check if credentials are configured
        if not config.sender_email or not config.sender_password:
            return jsonify(
                {
                    "status": "error",
                    "message": "Email credentials not configured. Please add NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD to your .env file."
                }
            ), 400

        # Log the configuration for debugging (without password)
        logger.info(
            f"Testing email config - Email: {config.sender_email}, SMTP: {config.smtp_server}:{config.smtp_port}"
        )

        # Test SMTP connection
        import smtplib

        server = smtplib.SMTP(config.smtp_server, config.smtp_port)
        server.starttls()
        server.login(config.sender_email, config.sender_password)
        server.quit()

        return jsonify(
            {
                "status": "success",
                "message": f"Email configuration is working correctly! Connected to {config.smtp_server} with {config.sender_email}"
            }
        )

    except smtplib.SMTPAuthenticationError as e:
        error_msg = str(e)
        if "Username and Password not accepted" in error_msg:
            return jsonify(
                {
                    "status": "error",
                    "message": "Authentication failed. For Gmail, make sure you're using an App Password, not your regular password. See newsletter_config.txt for setup instructions."
                }
            ), 400
        else:
            return jsonify(
                {
                    "status": "error",
                    "message": f"SMTP Authentication Error: {error_msg}"
                }
            ), 400
    except smtplib.SMTPException as e:
        return jsonify(
            {
                "status": "error",
                "message": f"SMTP Error: {str(e)}"
            }
        ), 400
    except Exception as e:
        logger.error(f"Newsletter config test error: {str(e)}")
        return jsonify(
            {
                "status": "error",
                "message": f"Configuration error: {str(e)}"
            }
        ), 400


@app.route('/api/newsletter/debug', methods=['POST'])
@login_required
def debug_newsletter_config():
    """Debug newsletter configuration"""
    if not getattr(current_user, "is_admin", False):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    try:
        config = NewsletterConfig()

        debug_info = {
            "email_configured": bool(config.sender_email),
            "password_configured": bool(config.sender_password),
            "email_value": config.sender_email if config.sender_email else "Not set",
            "smtp_server": config.smtp_server,
            "smtp_port": config.smtp_port,
            "env_vars": {
                "NEWSLETTER_EMAIL": "Set" if os.getenv(
                    "NEWSLETTER_EMAIL"
                ) else "Not set",
                "NEWSLETTER_PASSWORD": "Set" if os.getenv(
                    "NEWSLETTER_PASSWORD"
                ) else "Not set"
            }
        }

        return jsonify({"status": "success", "debug_info": debug_info})

    except Exception as e:
        return jsonify(
            {"status": "error", "message": f"Debug error: {str(e)}"}
        ), 400


@app.route('/unsubscribe')
def unsubscribe():
    """Unsubscribe page for newsletter"""
    email = (request.args.get('email') or '').strip().lower()
    return render_template('unsubscribe.html', email=email)


@app.route('/unsubscribe', methods=['POST'])
def unsubscribe_post():
    """Process unsubscribe request"""
    email = request.form.get('email', '').strip().lower()

    if not email:
        flash("Please enter your email address.", "danger")
        return redirect(url_for('unsubscribe'))

    try:
        # Read current subscribers
        subscribers = []
        if os.path.exists("subscribers.csv"):
            with open("subscribers.csv", "r") as f:
                subscribers = [line.strip().lower() for line in
                               f.readlines()]

        # Check if email exists
        if email not in subscribers:
            flash(
                "Email address not found in our subscriber list.",
                "info"
            )
            return redirect(url_for('unsubscribe'))

        # Remove email from list
        updated_subscribers = [sub for sub in subscribers if
                               sub != email and sub != 'email']

        # Write back to file
        with open("subscribers.csv", "w") as f:
            f.write("email\n")  # Header
            for subscriber in updated_subscribers:
                if subscriber:  # Skip empty lines
                    f.write(subscriber + "\n")

        flash(
            "You have been successfully unsubscribed from our newsletter.",
            "success"
        )

    except Exception as e:
        logger.error(f"Error unsubscribing email: {str(e)}")
        flash("An error occurred. Please try again later.", "danger")

    return redirect(url_for('unsubscribe'))


def _load_email_config_if_missing() -> None:
    """Load/override SMTP creds from newsletter_config.txt into environment."""
    import os

    try:
        # Respect App Service / process env vars; do not override them from a file.
        # This avoids shipping stale creds and breaking production SMTP.
        already_set = {
            'NEWSLETTER_EMAIL': bool(os.getenv('NEWSLETTER_EMAIL')),
            'NEWSLETTER_PASSWORD': bool(os.getenv('NEWSLETTER_PASSWORD')),
            'SMTP_SERVER': bool(os.getenv('SMTP_SERVER')),
            'SMTP_PORT': bool(os.getenv('SMTP_PORT')),
            'CONTACT_RECIPIENT': bool(os.getenv('CONTACT_RECIPIENT')),
        }
        if os.path.exists('newsletter_config.txt'):
            with open('newsletter_config.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, val = line.split('=', 1)
                        key = key.strip()
                        val = val.strip()
                        if key in already_set and val and not already_set.get(
                                key,
                                False
                        ):
                            os.environ[key] = val
    except Exception as e:
        logger.error(f"Failed to load newsletter_config.txt: {str(e)}")


# Contact form email helper
def send_contact_email(name: str, sender_email: str, message: str) -> None:
    """Send contact form submission to the site owner via SMTP.

    Uses NEWSLETTER_EMAIL/NEWSLETTER_PASSWORD for SMTP auth to avoid duplicating config.
    Recipient defaults to CONTACT_RECIPIENT or the site owner's email.
    """
    import os
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    _load_email_config_if_missing()
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    auth_email = (os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip(
        '"'
    ).strip("'")
    auth_password = (
            os.getenv('NEWSLETTER_PASSWORD', '') or '').strip().strip(
        '"'
    ).strip("'").replace(' ', '')
    recipient = os.getenv(
        'CONTACT_RECIPIENT',
        'yaronyaronlid@gmail.com'
    ).strip()

    if not auth_email or not auth_password:
        raise ValueError(
            'Email credentials not configured. Set NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD.'
        )

    subject = 'New Contact Form Submission - ResumaticAI'
    text_body = (
        f"You have a new contact form submission from ResumaticAI.\n\n"
        f"Name: {name or 'N/A'}\n"
        f"Email: {sender_email or 'N/A'}\n\n"
        f"Message:\n{message or ''}\n"
    )

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = auth_email
    msg['To'] = recipient
    # Prefer plain text; add Reply-To for easy response
    msg.add_header('Reply-To', sender_email or auth_email)
    msg.attach(MIMEText(text_body, 'plain', 'utf-8'))

    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(auth_email, auth_password)
    server.send_message(msg)
    server.quit()


def save_contact_message(
        name: str,
        sender_email: str,
        message: str
) -> None:
    """Persist contact messages locally if email delivery fails."""
    import csv
    from datetime import datetime

    filename = 'contact_messages.csv'
    try:
        file_exists = os.path.exists(filename)
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(
                    ['timestamp_iso', 'name', 'email', 'message']
                )
            writer.writerow(
                [datetime.utcnow().isoformat(), name or '',
                 sender_email or '', message or '']
            )
    except Exception as e:
        logger.error(f'Failed to save contact message fallback: {str(e)}')


# Feedback form email helper
def send_feedback_email(
        sender_email: str,
        rating: str,
        category: str,
        message: str,
        source_url: str = ''
) -> None:
    """Send feedback form submission to the site owner via SMTP.

    Uses the same SMTP auth + recipient as the contact form (CONTACT_RECIPIENT).
    """
    import os
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    _load_email_config_if_missing()
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    auth_email = (os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip(
        '"'
    ).strip("'")
    auth_password = (
            os.getenv('NEWSLETTER_PASSWORD', '') or '').strip().strip(
        '"'
    ).strip("'").replace(' ', '')
    recipient = os.getenv(
        'CONTACT_RECIPIENT',
        'yaronyaronlid@gmail.com'
    ).strip()

    if not auth_email or not auth_password:
        raise ValueError(
            'Email credentials not configured. Set NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD.'
        )

    subject = 'New Feedback Submission - ResumaticAI'
    text_body = (
        f"You have received new feedback from ResumaticAI.\n\n"
        f"Email: {sender_email or 'N/A'}\n"
        f"Rating: {rating or 'N/A'}\n"
        f"Category: {category or 'N/A'}\n"
        f"Source URL: {source_url or 'N/A'}\n\n"
        f"Message:\n{message or ''}\n"
    )

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = auth_email
    msg['To'] = recipient
    msg.add_header('Reply-To', (sender_email or '').strip() or auth_email)
    msg.attach(MIMEText(text_body, 'plain', 'utf-8'))

    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(auth_email, auth_password)
    server.send_message(msg)
    server.quit()


def save_feedback_message(
        sender_email: str,
        rating: str,
        category: str,
        message: str,
        source_url: str = ''
) -> None:
    """Persist feedback messages locally if email delivery fails."""
    import csv
    from datetime import datetime

    filename = 'feedback_messages.csv'
    try:
        file_exists = os.path.exists(filename)
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(
                    ['timestamp_iso', 'email', 'rating', 'category',
                     'message', 'source_url']
                )
            writer.writerow(
                [
                    datetime.utcnow().isoformat(),
                    (sender_email or '').strip(),
                    str(rating or '').strip(),
                    str(category or '').strip(),
                    message or '',
                    str(source_url or '').strip(),
                ]
            )
    except Exception as e:
        logger.error(f'Failed to save feedback message fallback: {str(e)}')


# Contact form route
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        website = request.form.get('website', '')  # honeypot
        try:
            # Basic spam checks: honeypot must be empty, submission must not be too fast (<2s)
            ts_str = request.form.get('_ts', '0')
            try:
                form_ts = int(ts_str)
            except ValueError:
                form_ts = 0
            import time

            now_s = int(time.time())
            # Lower threshold to reduce false positives from autofill
            too_fast = (now_s - form_ts) < 1 if form_ts else False

            if website.strip() or too_fast:
                logger.info(
                    'Contact form blocked by spam checks (honeypot/timing).'
                )
                flash('Thank you for contacting us!', 'success')
                return render_template(
                    'contact.html',
                    form_ts=int(time.time())
                )

            send_contact_email(name, email, message)
            flash(
                'Thank you for contacting us! Your message has been sent.',
                'success'
            )
        except Exception as e:
            logger.error(f"Contact form email failed: {str(e)}")
            # Fallback: persist the message so it's not lost
            try:
                save_contact_message(name, email, message)
                flash(
                    'Thank you for contacting us! We received your message.',
                    'info'
                )
            except Exception:
                flash(
                    'We could not send your message due to a server error. Please try again later.',
                    'danger'
                )
        return render_template('contact.html', form_ts=int(time.time()))
    # GET: set initial timestamp
    import time

    return render_template('contact.html', form_ts=int(time.time()))


# Feedback form route
@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    import time

    if request.method == 'POST':
        sender_email = (request.form.get('email') or '').strip()
        rating = (request.form.get('rating') or '').strip()
        category = (request.form.get('category') or '').strip()
        message = (request.form.get('message') or '').strip()
        source_url = (request.form.get('source_url') or '').strip()
        website = request.form.get('website', '')  # honeypot

        try:
            # Basic spam checks: honeypot must be empty, submission must not be too fast (<1s)
            ts_str = request.form.get('_ts', '0')
            try:
                form_ts = int(ts_str)
            except ValueError:
                form_ts = 0
            now_s = int(time.time())
            too_fast = (now_s - form_ts) < 1 if form_ts else False

            if website.strip() or too_fast:
                logger.info(
                    'Feedback form blocked by spam checks (honeypot/timing).'
                )
                flash('Thank you for your feedback!', 'success')
                return render_template(
                    'feedback.html',
                    form_ts=int(time.time()),
                    source_url=source_url
                )

            # Minimal validation: require either a message or a rating
            if not message and not rating:
                flash(
                    'Please add a message or a rating before submitting.',
                    'danger'
                )
                return render_template(
                    'feedback.html',
                    form_ts=int(time.time()),
                    source_url=source_url
                )

            send_feedback_email(
                sender_email,
                rating,
                category,
                message,
                source_url=source_url
            )
            flash('Thanks! Your feedback has been sent.', 'success')
        except Exception as e:
            logger.error(f"Feedback form email failed: {str(e)}")
            try:
                save_feedback_message(
                    sender_email,
                    rating,
                    category,
                    message,
                    source_url=source_url
                )
                flash('Thanks! We received your feedback.', 'info')
            except Exception:
                flash(
                    'We could not send your feedback due to a server error. Please try again later.',
                    'danger'
                )

        return render_template(
            'feedback.html',
            form_ts=int(time.time()),
            source_url=source_url
        )

    # GET
    source_url = request.args.get('from') or request.referrer or ''
    return render_template(
        'feedback.html',
        form_ts=int(time.time()),
        source_url=source_url
    )


# Offline page route
@app.route('/offline.html')
def offline():
    """Offline page for PWA functionality"""
    return render_template('offline.html')


# 410 Gone for legacy/old thin URLs
@app.route('/index_old')
@app.route('/index_old.html')
@app.route('/indexfiver')
@app.route('/indexfiver.html')
@app.route('/templates.html')
def gone_legacy_urls():
    return Response(
        'This URL has been permanently removed.',
        status=410,
        mimetype='text/plain'
    )


# Minimal site search endpoint to support Sitelinks SearchBox
@app.route('/search')
def site_search():
    query = request.args.get('q', '').strip()
    # Simple, non-indexable helper page for users and bots
    html = f"""<!DOCTYPE html>
<html lang=\"en\"><head><meta charset=\"utf-8\">\n<meta name=\"robots\" content=\"noindex, nofollow\">\n<title>Search | ResumaticAI</title></head>
<body style=\"font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; padding: 24px;\">\n<h1>Search</h1>\n<p>Showing results for: <strong>{query}</strong></p>\n<p>We don't have on-site search yet. Try exploring our <a href=\"/blog\">blog</a> or the <a href=\"/\">homepage</a>.</p>\n</body></html>"""
    return Response(html, mimetype='text/html')


# Explicitly set X-Robots-Tag for low-value or transactional routes
@app.after_request
def add_robots_headers(response):
    try:
        noindex_endpoints = {
            'results_route',
            'login',
            'signup',
            'thank_you',
            'unsubscribe',
            'counter_page',
            'counter_html_legacy',
        }
        noindex_paths = {
            '/results',
            '/login',
            '/signup',
            '/thank_you',
            '/unsubscribe',
            '/counter',
            '/counter.html',
        }
        if (request.endpoint in noindex_endpoints) or (
                request.path in noindex_paths):
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    except Exception:
        pass
    return response


#########################################################
#################TEMPLATES
'''
# --- imports (single set) ---
from flask import Flask, render_template, request, send_file, abort, url_for, redirect, jsonify
from io import BytesIO
import os



# Optional: nicer DOCX output if available
try:
    from docx import Document
except Exception:
    Document = None

# ---- Template registry (IDs match the gallery data) ----
TEMPLATES = {
    "modern-citrus": {"name": "Modern Citrus", "style": "Modern"},
    "modern-slate": {"name": "Modern Slate", "style": "Modern"},
    "modern-aurora": {"name": "Modern Aurora", "style": "Modern"},
    "classic-elegant": {"name": "Classic Elegant", "style": "Classic"},
    "classic-simplicity": {"name": "Classic Simplicity", "style": "Classic"},
    "classic-structure": {"name": "Classic Structure", "style": "Classic"},
    "creative-pastel": {"name": "Creative Pastel", "style": "Creative"},
    "creative-neo": {"name": "Creative Neo", "style": "Creative"},
    "creative-spark": {"name": "Creative Spark", "style": "Creative"},
}

def get_template_or_404(tid: str):
    t = TEMPLATES.get(tid)
    if not t:
        abort(404, f"Unknown template id: {tid}")
    return t

# ---- Pages ----
@app.route("/resume-templates", endpoint="resume_templates")
def resume_templates_view():
    return render_template("resume_templates.html")

@app.route("/builder", endpoint="resume_builder")
def resume_builder():
    tpl = request.args.get("template", "")
    t = TEMPLATES.get(tpl)
    return render_template("builder.html", template_id=tpl, template_meta=t)

# Optional alias if old links use /app/builder
@app.route("/app/builder", endpoint="resume_builder_alias")
def resume_builder_alias():
    qs = request.query_string.decode("utf-8")
    target = url_for("resume_builder")
    return redirect(f"{target}?{qs}" if qs else target, code=302)

# ---- Minimal export endpoints ----
@app.post("/export/docx")
def export_docx():
    data = request.get_json(force=True)
    tpl_id = data.get("template")
    t = get_template_or_404(tpl_id)

    name = data.get("name", "")
    title = data.get("title", "")
    summary = data.get("summary", "")
    exp = data.get("experience", []) or []
    skills = data.get("skills", []) or []

    bio = BytesIO()
    if Document:
        doc = Document()
        doc.add_heading(name or "Your Name", 0)
        if title:
            doc.add_paragraph(title)
        doc.add_paragraph(f"Template: {t['name']} ({t['style']})")
        doc.add_heading("Summary", level=1)
        doc.add_paragraph(summary or "")
        doc.add_heading("Experience", level=1)
        for item in exp:
            p = doc.add_paragraph()
            p.add_run(item.get("role", "Role")).bold = True
            company = item.get("company", "Company")
            years = item.get("years", "")
            p.add_run(f" — {company}" + (f" ({years})" if years else ""))
            for b in item.get("bullets", []):
                doc.add_paragraph(b, style="List Bullet")
        if skills:
            doc.add_heading("Skills", level=1)
            doc.add_paragraph(", ".join(skills))
        doc.save(bio)
    else:
        bio.write(
            f"{name}\n{title}\nTemplate: {t['name']} ({t['style']})\n\nSummary:\n{summary}\n".encode("utf-8")
        )
    bio.seek(0)
    return send_file(
        bio,
        as_attachment=True,
        download_name=f"{tpl_id}.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

@app.post("/export/pdf")
def export_pdf():
    # Tiny placeholder PDF. For production: WeasyPrint / wkhtmltopdf / ReportLab.
    data = request.get_json(force=True)
    tpl_id = data.get("template")
    t = get_template_or_404(tpl_id)
    name = data.get("name", "")
    title = data.get("title", "")
    text = f"{name} — {title} | {t['name']} ({t['style']})".replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    buf = BytesIO()
    buf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    objs = []
    objs.append("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objs.append("2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objs.append("3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 5 0 R >> >> /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n")
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET"
    objs.append(f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n{stream}\nendstream\nendobj\n")
    objs.append("5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    offsets = []
    for o in objs:
        offsets.append(buf.tell())
        buf.write(o.encode("utf-8"))
    xref = buf.tell()
    buf.write(f"xref\n0 {len(objs)+1}\n".encode("utf-8"))
    buf.write(b"0000000000 65535 f \n")
    for off in offsets:
        buf.write(f"{off:010d} 00000 n \n".encode("utf-8"))
    buf.write(f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("utf-8"))
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"{tpl_id}.pdf", mimetype="application/pdf")

import os

@app.route("/", endpoint="home")
def home():
    # Serve index.html if present; otherwise fall back to the gallery
    try:
        return render_template("index.html")
    except TemplateNotFound:
        return redirect(url_for("resume_templates"))

##########################################
'''
from flask import send_from_directory
import os

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_PATH = os.path.join(
    BASE_DIR,
    '610528eb-2434-4e0c-b4c5-1f54f21877ea.html'
)


@app.route('/610528eb-2434-4e0c-b4c5-1f54f21877ea.html')
def serve_file():
    return send_from_directory(
        directory=BASE_DIR,
        path='610528eb-2434-4e0c-b4c5-1f54f21877ea.html'
    )


import os
from flask import send_file

# Schema definitions
RESUME_STRUCTURE_SCHEMA = """
{
    "name": "string",
    "email": "string",
    "phone": "string",
    "location": "string",
    "summary": "string",
    "experience": [
        {
            "title": "string",
            "company": "string",
            "duration": "string",
            "description": "string (bullet points as newline separated text)"
        }
    ],
    "education": [
        {
            "degree": "string",
            "institution": "string",
            "year": "string"
        }
    ],
    "projects": [
        {
            "title": "string",
            "description": "string",
            "technologies": "string (comma separated)",
            "link": "string (optional)"
        }
    ],
    "certifications": [
        {
            "name": "string",
            "issuer": "string",
            "year": "string"
        }
    ],
    "skills": ["string"],
    "custom_sections": [
        {
            "heading": "string (The original section title, e.g. 'Publications', 'Volunteering', 'Awards')",
            "items": [
                {
                    "title": "string (e.g. Award Name or Role)",
                    "subtitle": "string (e.g. Organization or Event)",
                    "date": "string (optional)",
                    "content": "string (Description or details)"
                }
            ]
        }
    ]
}
"""


def parse_resume(revised_resume):
    try:
        # Initialize the client inside the function to avoid blocking startup
        # Explicitly pass API key to handle Azure environment
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        # Configure timeout and other parameters for Azure reliability
        client = OpenAI(
            api_key=api_key,
            timeout=60.0,  # 60 second timeout
            max_retries=3  # Retry up to 3 times on transient errors
        )

        parsing_prompt = f"""
You are a data extraction engine. 
Extract structured data from the following RESUME TEXT into the specified JSON format.

Resume Text:
\"\"\"{revised_resume}\"\"\"

Output Format:
{RESUME_STRUCTURE_SCHEMA}
        
Rules:
1. Extract the content exactly as written in the source text.
2. Map standard sections to standard fields.
3. Map non-standard sections to 'custom_sections'.
4. Return ONLY valid JSON.
"""
        parsing_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system",
                 "content": "You are a data extraction engine. Output only valid JSON."},
                {"role": "user", "content": parsing_prompt}
            ],
            response_format={"type": "json_object"}
        )

        parsing_content = parsing_response.choices[0].message.content

        # Remove markdown backticks if present (similar to revise_resume function)
        if parsing_content.startswith("```"):
            import re

            parsing_content = re.sub(
                r"^```(?:json)?\n",
                "",
                parsing_content
            )
            parsing_content = re.sub(r"\n```$", "", parsing_content)

        try:
            structured_resume = json.loads(parsing_content)
        except json.JSONDecodeError as e:
            logging.error(f"JSON Parse Error in parse_resume: {str(e)}")
            logging.error(
                f"Raw parsing content: {parsing_content[:500]}..."
            )
            raise ValueError(f"Failed to parse resume structure: {str(e)}")
        return {"resume": structured_resume}
    except Exception as e:
        logging.error(f"Error in parse_resume: {str(e)}")
        _safe_log_exception('parse_resume error', e)
        raise


if __name__ == "__main__":
    # Default to a single-process dev server (avoids confusing duplicate side-effects).
    # If you want auto-reload while iterating locally, set `FLASK_USE_RELOADER=1`.
    try:
        use_reloader = str(
            os.getenv('FLASK_USE_RELOADER', '') or ''
        ).strip().lower() in ('1', 'true', 'yes', 'on')
    except Exception:
        use_reloader = False

    try:
        host = str(
            os.getenv('FLASK_HOST', '127.0.0.1') or '127.0.0.1'
        ).strip()
    except Exception:
        host = '127.0.0.1'

    try:
        port = int(str(os.getenv('PORT', '5000') or '5000').strip())
    except Exception:
        port = 5000

    logger.info(
        'Dev server starting (build=%s pid=%s host=%s port=%s reloader=%s)',
        _BUILD_ID,
        os.getpid(),
        host,
        port,
        use_reloader
    )
    app.run(debug=True, host=host, port=port, use_reloader=use_reloader)
