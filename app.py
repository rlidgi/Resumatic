from flask import Flask, request, render_template, redirect, url_for, session, flash, send_file, send_from_directory, jsonify, Response, make_response, abort
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
import time
import re
import threading
import atexit
import threading
import atexit


# Import newsletter system
from newsletter import NewsletterManager, NewsletterConfig

try:
    from analytics import analytics
except Exception as _analytics_import_error:
    class _NoopAnalytics:
        def track_visit(self, request_obj):
            return {"type": "organic", "source": "fallback", "error": str(_analytics_import_error)}

        def track_conversion(self, session_data, conversion_type="resume_submission"):
            return {"status": "skipped", "reason": "analytics_unavailable", "type": conversion_type}

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
import google.auth.transport.requests
import google.oauth2.credentials
import google.oauth2.id_token

from flask_dance.contrib.facebook import make_facebook_blueprint, facebook
from flask_login import LoginManager, login_required, login_user, logout_user, UserMixin, current_user
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None  # type: ignore
import calendar
import openai
import os
import json
from docx import Document
import stripe
import csv
from azure.data.tables import TableServiceClient, UpdateMode
from azure.identity import DefaultAzureCredential
from urllib.parse import urlparse, urljoin
from urllib.parse import urlencode
from flask_session import Session
import re

app = Flask(__name__)

# App Service runs behind a reverse proxy. Trust standard forwarding headers so
# Flask sees the correct scheme/host (important for redirects and health probes).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

@app.route("/react")
@app.route("/react/<path:subpath>")
def react_app(subpath=None):
    """Legacy /react alias retained only as a redirect to the new create-resume flow."""
    return redirect(url_for("imported_resume_builder"), code=301)


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

    requested = os.path.normpath(str(subpath)).replace("\\", "/").lstrip("/")
    if requested.startswith(".."):
        abort(404)

    file_abs = os.path.join(builder_root, requested)
    if os.path.isfile(file_abs):
        return send_from_directory(builder_root, requested)

    abort(404)


#####################
# ---- Make `current_user` available in all Jinja templates ----
try:
    from flask_login import LoginManager, current_user as flask_login_current_user, AnonymousUserMixin

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





# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Local debugging aid (Windows-safe): write exception traces to a file next to app.py.
# This avoids rare Windows console/stderr write errors that can mask the real exception.
try:
    _LOCAL_ERRORS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_errors.log')
except Exception:
    _LOCAL_ERRORS_PATH = 'local_errors.log'

# Create the file early so it's easy to locate during debugging.
try:
    with open(_LOCAL_ERRORS_PATH, 'a', encoding='utf-8', errors='backslashreplace') as _f:
        from datetime import datetime
        _f.write(f"\n[{datetime.utcnow().isoformat()}Z] local_errors.log initialized\n")
except Exception:
    pass


def _safe_log_exception(context: str, exc: Exception | None = None) -> None:
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

        with open(_LOCAL_ERRORS_PATH, 'a', encoding='utf-8', errors='backslashreplace') as f:
            f.write(f"\n[{datetime.utcnow().isoformat()}Z] {context}\n")
            if exc is not None:
                f.write(f"{type(exc).__name__}: {exc}\n")
                tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
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

        with open(_LOCAL_ERRORS_PATH, 'a', encoding='utf-8', errors='backslashreplace') as f:
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
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY') or 'a-very-secret-random-key'

# Local-dev ergonomics: auto-reload templates/static caching unless running on Azure App Service.
_ON_AZURE = bool(os.getenv('WEBSITE_HOSTNAME') or os.getenv('WEBSITE_INSTANCE_ID'))

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
logger.info('ResumaticAI boot (build=%s pid=%s on_azure=%s)', _BUILD_ID, os.getpid(), _ON_AZURE)

# ---- Playwright browser reuse (per-worker) ----
# Launching Chromium is expensive; reuse a single browser per Gunicorn worker for PDF generation.
_PDF_BROWSER_LOCK = threading.Lock()
_PDF_PW = None
_PDF_BROWSER = None


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

# Azure SDK HTTP logging can drown out app logs (especially in Azure Log Stream).
# Default to quiet; allow overriding via standard logging config if needed.
try:
    logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
    logging.getLogger('azure.monitor.opentelemetry.exporter.export._base').setLevel(logging.WARNING)
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
# Uses filesystem storage (safe for a single App Service instance); cookie stores only a small session id.
try:
    home_dir = (os.getenv('HOME') or '').strip()
    if home_dir:
        # App Service common root: /home/site/wwwroot (Linux) or D:\home\site\wwwroot (Windows)
        session_dir = os.path.join(home_dir, 'site', 'wwwroot', '.flask_session')
    else:
        session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.flask_session')
    os.makedirs(session_dir, exist_ok=True)

    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = session_dir
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    # Only mark cookies Secure when running on Azure HTTPS; avoid breaking local http://127.0.0.1
    app.config['SESSION_COOKIE_SECURE'] = bool(_ON_AZURE)

    Session(app)
except Exception as e:
    logger.warning(f"Server-side session setup failed; falling back to cookie sessions: {type(e).__name__}: {str(e)}")


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
        return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc
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

        filename = os.getenv('MARKETING_SIGNUPS_CSV', 'marketing_signups.csv')
        file_exists = os.path.exists(filename)
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
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
                ])

            writer.writerow([
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
            ])
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



def _append_google_signup_csv(user_id: str, name: str, email: str, created_at_iso: str) -> None:
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
                writer.writerow(['timestamp_iso', 'user_id', 'name', 'email'])
            writer.writerow([created_at_iso or datetime.now(timezone.utc).isoformat(), user_id or '', name or '', (email or '').strip().lower()])
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

    forwarded_proto = (request.headers.get('X-Forwarded-Proto') or '').lower().strip()
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
GOOGLE_CLIENT_SECRET_FILE = os.path.join(os.path.dirname(__file__), "client_secret.json")

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


app.register_blueprint(facebook_bp, url_prefix="/login")  # MUST be before the route below


# Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Define a list of admin email addresses
ADMIN_EMAILS = ["yaronyaronlid@gmail.com"]

# User storage file
USERS_FILE = "users_data.json"

# Password reset tokens storage
RESET_TOKENS_FILE = "reset_tokens.json"
RESET_TOKEN_EXPIRY_HOURS = 24  # Tokens expire after 24 hours

# Login auditing (email + login timestamp + session duration)
LOGIN_AUDIT_FILE = "login_audit.json"
LOGIN_AUDIT_SESSION_KEY = "login_audit_id"
_LOGIN_AUDIT_VERSION = 1

# Persisting last activity can be useful for interpreting sessions without explicit logout.
# Throttle updates to avoid excessive disk/DB writes.
LOGIN_AUDIT_LAST_ACTIVITY_AT_KEY = 'login_audit_last_activity_at'
LOGIN_AUDIT_LAST_ACTIVITY_WRITE_AT_KEY = 'login_audit_last_activity_write_at'
LOGIN_AUDIT_ACTIVITY_WRITE_THROTTLE_SECONDS = int(os.getenv('LOGIN_AUDIT_ACTIVITY_WRITE_THROTTLE_SECONDS', '60') or '60')

# Auth session timeouts
# - Idle timeout: log out after N minutes with no authenticated requests.
# These are best-effort guards to reduce risk from unattended sessions.
AUTH_IDLE_TIMEOUT_MINUTES = int(os.getenv('AUTH_IDLE_TIMEOUT_MINUTES', '45') or '45')
# Absolute timeout is disabled by default (set to >0 to enable).
AUTH_ABSOLUTE_TIMEOUT_HOURS = int(os.getenv('AUTH_ABSOLUTE_TIMEOUT_HOURS', '0') or '0')
AUTH_SESSION_START_AT_KEY = 'auth_session_start_at'
AUTH_LAST_ACTIVITY_AT_KEY = 'auth_last_activity_at'

# Azure Table Storage (optional) for login auditing.
# If available, this avoids JSON file concurrency issues across workers/instances.
AZURE_LOGIN_AUDIT_TABLE = os.getenv('AZURE_LOGIN_AUDIT_TABLE', 'LoginAudit')
LOGIN_AUDIT_SESSION_PK_KEY = 'login_audit_pk'
LOGIN_AUDIT_SESSION_RK_KEY = 'login_audit_rk'
LOGIN_AUDIT_SESSION_LOGIN_AT_KEY = 'login_audit_login_at'

# Azure Users table: record each login session as a separate row (append-only).
# This keeps the existing profile row (RowKey='profile') intact while allowing multiple sessions per user.
USERS_SESSION_ROWKEY_KEY = 'users_session_rk'
USERS_SESSION_LOGIN_AT_KEY = 'users_session_login_at'
USERS_SESSION_AUDIT_ID_KEY = 'users_session_audit_id'

# Email verification
EMAIL_VERIFY_TOKEN_EXPIRY_HOURS = int(os.getenv('EMAIL_VERIFY_TOKEN_EXPIRY_HOURS', '48'))



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
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
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
            'email_verification_sent_at': getattr(self, 'email_verification_sent_at', None),
            'welcome_email_sent_at': getattr(self, 'welcome_email_sent_at', None),
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
            email_verification_sent_at=data.get('email_verification_sent_at'),
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

        return redirect(url_for('verify_email', email=getattr(current_user, 'email', '')))
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


def confirm_email_verification_token(token: str, max_age_seconds: int) -> dict | None:
    from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
    serializer = URLSafeTimedSerializer(app.secret_key)
    try:
        return serializer.loads(token, salt='email-verify', max_age=max_age_seconds)
    except SignatureExpired:
        return None
    except BadSignature:
        return None
    except Exception:
        return None


def send_email_verification_email(email: str, token: str, user_name: str, next_url: str | None = None) -> bool:
    """Send email verification link to user."""
    try:
        _load_email_config_if_missing()
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        auth_email = (os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip('"').strip("'")
        # App Service settings sometimes get pasted with surrounding quotes/newlines; tolerate that.
        auth_password = (os.getenv('NEWSLETTER_PASSWORD', '') or '').strip().strip('"').strip("'").replace(' ', '')

        if not auth_email or not auth_password:
            raise ValueError('Email credentials not configured. Set NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD.')

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
        return True
    except Exception:
        # Keep user-facing messaging generic; log full details for ops/debugging.
        # Never log passwords/secrets.
        try:
            logger.error(
                "Verification email failed (smtp_server=%s smtp_port=%s auth_email=%s to=%s)",
                os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
                os.getenv('SMTP_PORT', '587'),
                (os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip('"').strip("'"),
                (email or '').strip().lower(),
            )
        except Exception:
            pass
        logger.exception("Error sending verification email")
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
        from email.mime.multipart import MIMEMultipart
        from urllib.parse import urlencode

        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        auth_email = (os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip('"').strip("'")
        auth_password = (os.getenv('NEWSLETTER_PASSWORD', '') or '').strip().strip('"').strip("'").replace(' ', '')

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
                print(f"[send_welcome_email] to={email} smtp={smtp_server}:{smtp_port} from={auth_email}")
        except Exception:
            pass

        if not auth_email or not auth_password:
            raise ValueError('Email credentials not configured. Set NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD.')

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

        subject = 'Welcome to ResumaticAI'

        html_body = f"""
        <html>
        <body style=\"font-family: Arial, sans-serif; line-height: 1.6; color: #333;\">
            <div style=\"max-width: 600px; margin: 0 auto; padding: 20px;\">
                <p>Hi there,</p>
                <p>Welcome to ResumaticAI. We're really glad you’re here.</p>
                
                <p>We built ResumaticAI because we saw two things:</p>
                <ul>
                    <li>AI has become incredibly powerful.</li>
                    <li>Most resume tools still feel generic.</li>
                </ul>
                <p>Resumes aren’t just documents, they’re positioning tools. The difference between getting ignored and getting interviews often comes down to clarity, impact, and strategy. ResumaticAI was designed to combine advanced AI with practical resume expertise to help you present your experience in the strongest possible way.</p>
                <p>Here’s what you can do right now:</p>
                <ul>
                    <li>Upload your resume for instant AI-powered feedback</li>
                    <li>Strengthen your bullet points with measurable impact</li>
                    <li>Tailor your resume to specific job descriptions</li>
                    <li>Improve structure, clarity, and ATS compatibility</li>
                </ul>
                <p>We’ve recently launched and are actively improving the platform. Your feedback genuinely helps shape what we build next. If you have suggestions, questions, or ideas, just reply to this email.</p>
                <p>Ready to get started?</p>
                <p>Visit: <a href=\"https://resumaticai.com\" style=\"color: #2563eb;\">https://resumaticai.com</a></p>
                <p>Let’s build a resume that gets you interviews.</p>
                <p>Yaron<br>Founder, ResumaticAI</p>
                <hr style=\"border: none; border-top: 1px solid #eee; margin: 20px 0;\">
                {f'<p style="color: #666; font-size: 12px;">Newsletter unsubscribe: <a href="{unsubscribe_url}" style="color: #2563eb;">{unsubscribe_url}</a></p>' if unsubscribe_url else ''}
                <p style=\"color: #666; font-size: 12px;\">ResumaticAI Team</p>
            </div>
        </body>
        </html>
        """

        text_body = "\n".join(
            [
                'Hi there,',
                '',
                "Welcome to ResumaticAI — We're really glad you’re here.",
                '',
                'We built ResumaticAI because we saw two things:',
                '',
                '• AI has become incredibly powerful.',
                '• Most resume tools still feel generic.',
                '',
                "Resumes aren’t just documents — they’re positioning tools. The difference between getting ignored and getting interviews often comes down to clarity, impact, and strategy. ResumaticAI was designed to combine advanced AI with practical resume expertise to help you present your experience in the strongest possible way.",
                '',
                "Here’s what you can do right now:",
                '',
                '• Upload your resume for instant AI-powered feedback',
                '• Strengthen your bullet points with measurable impact',
                '• Tailor your resume to specific job descriptions',
                '• Improve structure, clarity, and ATS compatibility',
                '',
                "We’ve recently launched and are actively improving the platform. Your feedback genuinely helps shape what we build next. If you have suggestions, questions, or ideas, just reply to this email — I read every message personally.",
                '',
                'Ready to get started?',
                '',
                'Visit: https://resumaticai.com',
                '',
                "Let’s build a resume that gets you interviews.",
                '',
                'Yaron',
                'Founder, ResumaticAI',
                '',
                '---',
                *([f'Newsletter unsubscribe: {unsubscribe_url}'] if unsubscribe_url else []),
                'ResumaticAI Team',
            ]
        ).strip()

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

        logger.info(f"Welcome email sent to {email}")
        return True
    except Exception:
        # Never log passwords/secrets.
        try:
            logger.error(
                "Welcome email failed (smtp_server=%s smtp_port=%s auth_email=%s to=%s)",
                os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
                os.getenv('SMTP_PORT', '587'),
                (os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip('"').strip("'"),
                (email or '').strip().lower(),
            )
        except Exception:
            pass
        logger.exception('Error sending welcome email')
        return False

def load_users():
    """Load users from JSON file"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
                return {user_id: User.from_dict(user_data) for user_id, user_data in users_data.items()}
        return {}
    except Exception as e:
        logger.exception("Error loading users")
        return {}

def save_users():
    """Save users to JSON file"""
    try:
        users_data = {user_id: user.to_dict() for user_id, user in users.items()}
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.exception("Error saving users")



def add_user(user):
    """Add a user and save to persistent storage"""
    users[user.id] = user
    save_users()
    try:
        logger.info("Added user: %s (%s)", getattr(user, 'name', ''), getattr(user, 'email', ''))
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


def _load_login_audit_store() -> dict:
    """Load login audit store from disk (best-effort)."""
    try:
        if os.path.exists(LOGIN_AUDIT_FILE):
            with open(LOGIN_AUDIT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get('sessions'), dict):
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

        dir_name = os.path.dirname(os.path.abspath(LOGIN_AUDIT_FILE)) or '.'
        with tempfile.NamedTemporaryFile('w', delete=False, dir=dir_name, encoding='utf-8') as tf:
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
        from backports.zoneinfo import ZoneInfo as BackportsZoneInfo  # type: ignore

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
            return dt.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        except Exception:
            return ''


_LOGIN_AUDIT_LOCK = threading.Lock()


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

    idle_seconds = int(idle_min * 60) if idle_min and idle_min > 0 else None
    absolute_seconds = int(abs_hours * 3600) if abs_hours and abs_hours > 0 else None
    return idle_seconds, absolute_seconds


def _auth_set_session_times(*, start_iso: str | None = None, activity_iso: str | None = None) -> None:
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
    return redirect(url_for('login', tab='login', expired=str(reason or '').strip() or '1'))


def _azure_login_audit_enabled() -> bool:
    """Return True if Azure Table Storage should be used for login auditing."""
    try:
        if (os.getenv('AZURE_STORAGE_CONNECTION_STRING') or '').strip():
            return True
        # Allow managed identity path primarily on Azure.
        if (os.getenv('AZURE_STORAGE_ACCOUNT') or '').strip() and (os.getenv('WEBSITE_INSTANCE_ID') or '').strip():
            return True
    except Exception:
        return False
    return False


def _get_login_audit_table_client(create_if_missing: bool = True):
    """Best-effort TableClient for login audit table."""
    connection_string = (os.getenv('AZURE_STORAGE_CONNECTION_STRING') or '').strip()
    account = (os.getenv('AZURE_STORAGE_ACCOUNT') or '').strip()
    if not connection_string and not account:
        raise ValueError('Azure storage not configured')

    if connection_string:
        service = TableServiceClient.from_connection_string(conn_str=connection_string)
    else:
        credential = DefaultAzureCredential()
        service = TableServiceClient(endpoint=f"https://{account}.table.core.windows.net", credential=credential)

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
        table_client = _get_login_audit_table_client(create_if_missing=True)
        table_client.upsert_entity(mode=UpdateMode.REPLACE, entity=entity)
        return True
    except Exception:
        logger.exception('Azure login audit upsert failed')
        return False


def _azure_login_audit_get(pk: str, rk: str) -> dict | None:
    try:
        table_client = _get_login_audit_table_client(create_if_missing=False)
        e = table_client.get_entity(partition_key=pk, row_key=rk)
        return dict(e) if e else None
    except Exception:
        return None


def _azure_login_audit_list(limit: int = 500) -> list[dict]:
    """List recent-ish login audit sessions (client-side sorted + limited)."""
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
            if limit and len(out) >= int(limit):
                break
    except Exception:
        # Surface as empty and let caller fallback.
        return []
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
        xff = _table_safe_str(request.headers.get('X-Forwarded-For', ''), max_len=256)
        if xff:
            # XFF can be a comma-separated chain; keep the left-most.
            return (xff.split(',', 1)[0] or '').strip()
    except Exception:
        pass
    try:
        return _table_safe_str(getattr(request, 'remote_addr', ''), max_len=64)
    except Exception:
        return ''


def _azure_users_session_start(*, user_id: str, email: str, audit_id: str, login_at: str, login_method: str, row_key: str, login_audit_pk: str = '', login_audit_rk: str = '') -> None:
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
            table_client.upsert_entity(profile_patch, mode=UpdateMode.MERGE)
        except Exception:
            pass

        # Insert an append-only session row.
        user_agent = ''
        referer = ''
        try:
            user_agent = _table_safe_str(request.headers.get('User-Agent', ''), max_len=512)
            referer = _table_safe_str(request.headers.get('Referer', ''), max_len=512)
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
            entity['login_audit_pk'] = _table_safe_str(login_audit_pk, max_len=16)
        if login_audit_rk:
            entity['login_audit_rk'] = _table_safe_str(login_audit_rk, max_len=128)

        table_client.upsert_entity(entity, mode=UpdateMode.REPLACE)
    except Exception:
        # Never block login on telemetry persistence.
        return


def _azure_users_session_activity(*, user_id: str, row_key: str, activity_at: str) -> None:
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


def _azure_users_session_end(*, user_id: str, row_key: str, logout_at: str, duration_seconds: int | None) -> None:
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

        audit_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        email = _normalize_email(getattr(user, 'email', ''))
        user_id = str(getattr(user, 'id', '') or '')
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
    except Exception:
        logger.exception("Error starting login audit")


def _audit_login_activity(activity_iso: str) -> None:
    """Update the current login audit record's last activity (best-effort, throttled)."""
    try:
        audit_id = session.get(LOGIN_AUDIT_SESSION_KEY)
        if not audit_id:
            return

        now_dt = _parse_iso_datetime(activity_iso) or datetime.now(timezone.utc)

        # Throttle writes (in-session).
        try:
            last_write_dt = _parse_iso_datetime(session.get(LOGIN_AUDIT_LAST_ACTIVITY_WRITE_AT_KEY))
        except Exception:
            last_write_dt = None
        if last_write_dt is not None:
            try:
                if (now_dt - last_write_dt).total_seconds() < float(LOGIN_AUDIT_ACTIVITY_WRITE_THROTTLE_SECONDS):
                    # Still update the in-memory session key for UI estimates.
                    session[LOGIN_AUDIT_LAST_ACTIVITY_AT_KEY] = str(activity_iso)
                    return
            except Exception:
                pass

        # Best-effort: also update the per-session row in the Azure Users table.
        try:
            uid = str(getattr(current_user, 'id', '') or '').strip()
            users_rk = str(session.get(USERS_SESSION_ROWKEY_KEY) or '').strip()
            if uid and users_rk:
                _azure_users_session_activity(user_id=uid, row_key=users_rk, activity_at=str(activity_iso))
        except Exception:
            pass

        # If this session has Azure PK/RK, update the Azure record.
        pk = str(session.get(LOGIN_AUDIT_SESSION_PK_KEY) or '').strip()
        rk = str(session.get(LOGIN_AUDIT_SESSION_RK_KEY) or '').strip()
        if pk and rk and _azure_login_audit_enabled():
            existing = _azure_login_audit_get(pk, rk) or {}
            merged = dict(existing) if isinstance(existing, dict) else {}
            merged.update({
                'PartitionKey': pk,
                'RowKey': rk,
                'audit_id': str(audit_id),
                'last_activity_at': str(activity_iso),
            })
            # Ensure required fields exist (Azure upsert replaces entity).
            merged.setdefault('login_at', str(session.get(LOGIN_AUDIT_SESSION_LOGIN_AT_KEY) or (merged.get('login_at') if isinstance(merged, dict) else '') or ''))
            merged.setdefault('logout_at', (merged.get('logout_at') if isinstance(merged, dict) else '') or '')
            merged.setdefault('email', (merged.get('email') if isinstance(merged, dict) else '') or '')
            merged.setdefault('user_id', (merged.get('user_id') if isinstance(merged, dict) else '') or '')
            merged.setdefault('login_method', (merged.get('login_method') if isinstance(merged, dict) else '') or '')
            _azure_login_audit_upsert(merged)

            session[LOGIN_AUDIT_LAST_ACTIVITY_AT_KEY] = str(activity_iso)
            session[LOGIN_AUDIT_LAST_ACTIVITY_WRITE_AT_KEY] = now_dt.isoformat()
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
        session[LOGIN_AUDIT_LAST_ACTIVITY_WRITE_AT_KEY] = now_dt.isoformat()
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

        start_dt = _parse_iso_datetime(session.get(AUTH_SESSION_START_AT_KEY))
        last_dt = _parse_iso_datetime(session.get(AUTH_LAST_ACTIVITY_AT_KEY))

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
        login_at_iso = str(session.get(LOGIN_AUDIT_SESSION_LOGIN_AT_KEY) or '').strip() or None
        if pk and rk and _azure_login_audit_enabled():
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()

            start_dt = _parse_iso_datetime(login_at_iso)
            if start_dt is None:
                # Best-effort: load from Azure if session data missing.
                existing = _azure_login_audit_get(pk, rk)
                start_dt = _parse_iso_datetime((existing or {}).get('login_at'))

            duration = int(max(0, (now - start_dt).total_seconds())) if start_dt is not None else None
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
            merged.setdefault('login_at', (existing.get('login_at') if isinstance(existing, dict) else None) or (login_at_iso or ''))
            merged.setdefault('email', (existing.get('email') if isinstance(existing, dict) else None) or '')
            merged.setdefault('user_id', (existing.get('user_id') if isinstance(existing, dict) else None) or '')
            merged.setdefault('login_method', (existing.get('login_method') if isinstance(existing, dict) else None) or '')

            _azure_login_audit_upsert(merged)

            # Also close the per-session row in the Azure Users table (best-effort).
            try:
                uid = str(getattr(current_user, 'id', '') or '').strip()
                users_rk = str(session.get(USERS_SESSION_ROWKEY_KEY) or '').strip()
                if uid and users_rk:
                    _azure_users_session_end(user_id=uid, row_key=users_rk, logout_at=now_iso, duration_seconds=duration)
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
            users_rk = str(session.get(USERS_SESSION_ROWKEY_KEY) or '').strip()
            if uid and users_rk:
                _azure_users_session_end(user_id=uid, row_key=users_rk, logout_at=now_iso, duration_seconds=duration)
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
    return users.get(user_id)

@app.route("/login", methods=['GET', 'POST'])
def login():
    def _render_login(*, active_tab: str | None = None):
        """Render the combined Login/Sign-up page with anti-caching headers."""
        resp = make_response(render_template("login.html", active_tab=active_tab))
        # Auth pages should not be cached; caching can cause stale JS/UI behavior.
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp

    def _desired_active_tab() -> str:
        """Return which auth tab should be shown initially on the login page."""
        try:
            tab = str(request.args.get('tab') or '').strip().lower()
        except Exception:
            tab = ''
        if tab in ('register', 'signup', 'sign-up', 'create', 'create-account'):
            return 'register'
        return 'login'

    if current_user.is_authenticated:
        if _requires_email_verification(current_user):
            return redirect(url_for('verify_email', email=getattr(current_user, 'email', '')))
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
            
            user = _find_user_by_email(email)

            # If the user exists but has no password, they likely signed up via Google/Facebook.
            if user and not getattr(user, 'password_hash', None):
                flash('This email is linked to a Google/Facebook sign-in. Use that sign-in, or click “Forgot password” to set a password for this email.', 'danger')
                return _render_login(active_tab='login')
            
            if user and user.password_hash and user.check_password(password):
                if _requires_email_verification(user):
                    flash('Please verify your email before logging in. We can resend the verification email below.', 'danger')
                    return redirect(url_for('verify_email', email=user.email))

                login_user(user)
                _audit_login_start(user, login_method='password')

                # Best-effort reliability: if the welcome email failed earlier (e.g. SMTP misconfig),
                # retry once on the first successful login after verification.
                try:
                    if (
                        _normalize_email(getattr(user, 'email', ''))
                        and bool(getattr(user, 'email_verified', True))
                        and not getattr(user, 'welcome_email_sent_at', None)
                    ):
                        logger.info(
                            "Retrying welcome email on login for %s",
                            _normalize_email(getattr(user, 'email', '')),
                        )
                        sent_ok = send_welcome_email(user.email, getattr(user, 'name', '') or '')
                        if sent_ok:
                            user.welcome_email_sent_at = datetime.now(timezone.utc).isoformat()
                            add_user(user)
                        else:
                            logger.warning(
                                "Welcome email retry not sent on login for %s",
                                _normalize_email(getattr(user, 'email', '')),
                            )
                except Exception:
                    logger.exception("Unexpected error during welcome-email retry on login")

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
                        flash("You've reached the free tier limit (2 revisions). Upgrade to save unlimited revisions.", "danger")
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
                flash('Password must be at least 8 characters long.', 'danger')
                return _render_login(active_tab='register')
            
            if password != confirm_password:
                flash('Passwords do not match.', 'danger')
                return _render_login(active_tab='register')
            
            # Check if email already exists
            existing_user = _find_user_by_email(email)
            if existing_user:
                if not getattr(existing_user, 'password_hash', None):
                    flash('An account with this email already exists via Google/Facebook sign-in. Use that sign-in, or click “Forgot password” to set a password for this email.', 'danger')
                else:
                    flash('An account with this email already exists. Please login instead.', 'danger')
                return _render_login(active_tab='register')
            
            # Create new user (requires email verification)
            import uuid
            user_id = f"email_{uuid.uuid4().hex[:16]}"
            user = User(user_id, name, email, is_new=True, email_verified=False)
            user.set_password(password)
            add_user(user)

            # Marketing attribution: record the signup source/ref/utm (best-effort)
            try:
                _append_marketing_signup_csv(user, signup_method='email_password')
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
                next_url=str(session.get('auth_next') or '').strip() or None,
            )
            user.email_verification_sent_at = datetime.now(timezone.utc).isoformat()
            add_user(user)  # persist sent timestamp + verified flag

            if sent_ok:
                flash('Account created! Please click verification link sent to your email address to activate account.', 'success')
            else:
                flash('Account created, but we could not send a verification email. Please try resending below or contact support.', 'danger')

            nxt = str(session.get('auth_next') or '').strip()
            if nxt and _is_safe_next_url(nxt):
                return redirect(url_for('verify_email', email=user.email, next=nxt))
            return redirect(url_for('verify_email', email=user.email))

    return _render_login(active_tab=_desired_active_tab())


@app.route('/verify-email')
def verify_email():
    """Show verification instructions + resend form."""
    _set_auth_next_from_request()
    email = (request.args.get('email') or '').strip().lower()
    next_url = str(session.get('auth_next') or '').strip()
    return render_template('verify_email.html', email=email, next_url=next_url)


@app.route('/verify-email/<token>')
def verify_email_token(token):
    """Verify email token, mark user verified, then log them in."""
    _set_auth_next_from_request()
    # Local-only debug/testing override: allow forcing a welcome resend.
    try:
        _force_resend_welcome = (
            (not _ON_AZURE)
            and str(request.args.get('resend_welcome', '') or '').strip().lower() in ('1', 'true', 'yes', 'on')
        )
    except Exception:
        _force_resend_welcome = False

    payload = confirm_email_verification_token(token, max_age_seconds=EMAIL_VERIFY_TOKEN_EXPIRY_HOURS * 3600)
    if not payload:
        flash('This verification link is invalid or has expired. Please request a new one.', 'danger')
        return redirect(url_for('verify_email'))

    user_id = str(payload.get('user_id') or '').strip()
    email = str(payload.get('email') or '').strip().lower()
    user = users.get(user_id)

    if not user or (str(getattr(user, 'email', '') or '').strip().lower() != email):
        flash('We could not verify that account. Please request a new verification email.', 'danger')
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

    # If already verified, just proceed.
    if not getattr(user, 'email_verified', True):
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc).isoformat()
        add_user(user)

    # Send a welcome email once, after verification succeeds.
    # Local debug: allow forcing resend with `?resend_welcome=1`.
    try:
        if _normalize_email(getattr(user, 'email', '')) and (_force_resend_welcome or not getattr(user, 'welcome_email_sent_at', None)):
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
                    print(f"[verify_email_token] welcome gate passed for {_normalize_email(getattr(user, 'email', ''))} force_resend={_force_resend_welcome}")
            except Exception:
                pass
            sent_ok = send_welcome_email(user.email, getattr(user, 'name', '') or '')
            if sent_ok:
                user.welcome_email_sent_at = datetime.now(timezone.utc).isoformat()
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
        logger.exception("Unexpected error during welcome-email attempt after verification")

    login_user(user)
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
            flash("You've reached the free tier limit (2 revisions). Upgrade to save unlimited revisions.", "danger")
        except Exception:
            pass

    flash('Email verified successfully! You can now use your account.', 'success')
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
    sent_ok = send_email_verification_email(user.email, token, user.name, next_url=str(session.get('auth_next') or '').strip() or None)
    user.email_verification_sent_at = datetime.now(timezone.utc).isoformat()
    add_user(user)

    flash(generic_msg if sent_ok else 'We could not send a verification email right now. Please try again later.', 'success' if sent_ok else 'danger')
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
        auth_email = (os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip('"').strip("'")
        auth_password = (os.getenv('NEWSLETTER_PASSWORD', '') or '').strip().strip('"').strip("'").replace(' ', '')
        
        if not auth_email or not auth_password:
            raise ValueError('Email credentials not configured. Set NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD.')
        
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
        
        user = _find_user_by_email(email)
        
        # Redirect back with a generic success indicator (security: don't reveal if email exists)
        
        if user and _normalize_email(getattr(user, 'email', '')):  # Send for any account with a reachable email
            # Generate reset token
            token = generate_reset_token()
            expiry_time = datetime.now(timezone.utc).timestamp() + (RESET_TOKEN_EXPIRY_HOURS * 3600)
            
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
        flash('Invalid or expired reset link. Please request a new password reset.', 'danger')
        return redirect(url_for('forgot_password'))
    
    token_data = tokens[token]
    current_time = datetime.now(timezone.utc).timestamp()
    
    # Check if token expired
    if current_time > token_data['expires_at']:
        # Remove expired token
        del tokens[token]
        save_reset_tokens(tokens)
        flash('This reset link has expired. Please request a new password reset.', 'danger')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not password or not confirm_password:
            flash('Please fill in both password fields.', 'danger')
            return render_template("reset_password.html", token=token, valid=True)
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template("reset_password.html", token=token, valid=True)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template("reset_password.html", token=token, valid=True)
        
        # Get user and update password
        user_id = token_data['user_id']
        user = users.get(user_id)
        
        if user:
            user.set_password(password)
            add_user(user)  # Save updated password
            
            # Remove used token
            del tokens[token]
            save_reset_tokens(tokens)
            
            flash('Your password has been reset successfully! Please login with your new password.', 'success')
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


@app.route("/login/google")
def google_login():
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
                "redirect_uris": [url_for("google_callback", _external=True)]
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
    
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account"  # 👈 This line is important
    )
    session["state"] = state
    return redirect(auth_url)





# Google OAuth Callback
@app.route("/login/google/authorized")
def google_callback():
    if current_user.is_authenticated:
        nxt = _pop_auth_next()
        return redirect(nxt or url_for('my_revisions'))
    
    if USE_ENV_CREDENTIALS:
        # Use environment variables for credentials
        client_config = {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": [url_for("google_callback", _external=True)]
            }
        }
        flow = Flow.from_client_config(
            client_config,
            scopes=GOOGLE_SCOPES,
            state=session["state"],
            redirect_uri=url_for("google_callback", _external=True)
        )
    else:
        # Use file-based credentials
        flow = Flow.from_client_secrets_file(
            GOOGLE_CLIENT_SECRET_FILE,
            scopes=GOOGLE_SCOPES,
            state=session["state"],
            redirect_uri=url_for("google_callback", _external=True)
        )

    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    
    # Add clock skew tolerance for token verification with retry logic
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            user_info = google.oauth2.id_token.verify_oauth2_token(
                credentials.id_token, 
                google.auth.transport.requests.Request(),
                clock_skew_in_seconds=30  # Allow 30 seconds clock skew
            )
            break  # Success, exit retry loop
        except google.auth.exceptions.InvalidValue as e:
            if "Token used too early" in str(e) and attempt < max_retries - 1:
                # Wait 2 seconds and retry
                time.sleep(2)
                continue
            else:
                raise  # Re-raise if not a timing issue or max retries reached
    user_id = user_info["sub"]
    is_new = user_id not in users
    user = User(user_id, user_info["name"], user_info.get("email", ""), is_new=is_new)
    add_user(user)  # Use add_user to save persistently
    # Marketing attribution + conversion (only for first-time signups; best-effort)
    try:
        if is_new:
            _append_marketing_signup_csv(user, signup_method='google_oauth')
            analytics.track_conversion(session, "signup")
    except Exception:
        pass
    # One-time welcome email for new OAuth signups (best-effort, non-blocking)
    try:
        if is_new and _normalize_email(getattr(user, 'email', '')) and not getattr(user, 'welcome_email_sent_at', None):
            sent_ok = send_welcome_email(user.email, getattr(user, 'name', '') or '')
            if sent_ok:
                user.welcome_email_sent_at = datetime.now(timezone.utc).isoformat()
                add_user(user)
    except Exception:
        pass
    # Record only first-time Google signups
    try:
        if is_new and str(user_id).isdigit():
            _append_google_signup_csv(user.id, user.name, user.email, user.created_at)
    except Exception:
        pass
    # Persist profile to Azure Users table
    try:
        upsert_user_profile_azure(user)
    except Exception:
        pass
    login_user(user)
    _audit_login_start(user, login_method='google_oauth')
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
            flash("You've reached the free tier limit (2 revisions). Upgrade to save unlimited revisions.", "danger")
        except Exception:
            pass
    nxt = _pop_auth_next()
    return redirect(nxt or url_for('my_revisions'))
    

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
    is_new = user_id not in users
    user = User(user_id, fb_info["name"], fb_info.get("email", ""), is_new=is_new)
    add_user(user)  # Use add_user to save persistently
    # Marketing attribution + conversion (only for first-time signups; best-effort)
    try:
        if is_new:
            _append_marketing_signup_csv(user, signup_method='facebook_oauth')
            analytics.track_conversion(session, "signup")
    except Exception:
        pass
    # One-time welcome email for new OAuth signups (best-effort, non-blocking)
    try:
        if is_new and _normalize_email(getattr(user, 'email', '')) and not getattr(user, 'welcome_email_sent_at', None):
            sent_ok = send_welcome_email(user.email, getattr(user, 'name', '') or '')
            if sent_ok:
                user.welcome_email_sent_at = datetime.now(timezone.utc).isoformat()
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

_FEEDBACK_CATEGORIES = ['Content', 'Format', 'Optimization', 'Best Practices', 'Application Readiness']


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
        return {'overall_score': 50, 'subscores': {c: 50 for c in _FEEDBACK_CATEGORIES}, 'improvement_items': []}

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
            cat = _canonical_feedback_category(it.get('category') or it.get('name') or it.get('Category'))
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
                    normalized_items.append({
                        'category': cat,
                        'message': str(msg or '').strip(),
                        'severity': 'suggestion',
                        'example_lines': '',
                    })
    elif isinstance(items, list):
        for it in items:
            if not isinstance(it, dict):
                continue
            cat = _canonical_feedback_category(
                it.get('category') or it.get('Category') or it.get('category_name') or it.get('categoryName')
            )
            msg = it.get('message') or it.get('suggestion') or it.get('feedback') or it.get('text') or ''
            sev = (it.get('severity') or it.get('level') or it.get('importance') or 'suggestion')
            ex = it.get('example_lines') or it.get('example') or it.get('exampleLines') or ''
            sev_s = str(sev or '').strip().lower()
            if sev_s not in ('error', 'warning', 'suggestion'):
                sev_s = 'suggestion'
            normalized_items.append({
                'category': cat or '',
                'message': str(msg or '').strip(),
                'severity': sev_s,
                'example_lines': str(ex or '').strip(),
            })

    # Keep only items with a message; canonicalize categories; default unknown to Content (so they are visible)
    cleaned = []
    for it in normalized_items:
        m = str(it.get('message') or '').strip()
        if not m:
            continue
        c = _canonical_feedback_category(it.get('category'))
        if c not in _FEEDBACK_CATEGORIES:
            c = 'Content'
        cleaned.append({
            'category': c,
            'message': m,
            'severity': it.get('severity') or 'suggestion',
            'example_lines': it.get('example_lines') or '',
        })
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
            logger.error(f"OpenAI API Error details: {type(e).__name__}: {error_msg}")
            # Re-raise with more details for debugging
            raise ValueError(f"Failed to connect to OpenAI API: {error_msg}")

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
            return data["revised_resume"], _normalize_feedback(data["feedback"])
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {str(e)}")
            print(f"Raw content: {raw_content}")
            raise ValueError("Invalid response format from OpenAI. Please try again.")
        except KeyError as e:
            print(f"Missing key in response: {str(e)}")
            raise ValueError("Incomplete response from OpenAI. Please try again.")

    except Exception as e:
        print("=== ERROR OCCURRED ===")
        _safe_log_exception('revise_resume error', e)
        raise



@app.route("/")
def index():
    # Track the visit with source attribution (only if not already tracked)
    if 'visit_tracked' not in session:
        analytics_obj = globals().get('analytics')
        if analytics_obj is not None and hasattr(analytics_obj, 'track_visit'):
            try:
                source_info = analytics_obj.track_visit(request)
            except Exception as e:
                _safe_log_exception('analytics.track_visit failed', e)
                source_info = {"type": "organic", "source": "fallback", "error": str(e)}
        else:
            source_info = {"type": "organic", "source": "fallback", "error": "analytics_unavailable"}
        session['visit_tracked'] = True
        session['traffic_source'] = source_info
        app.logger.info(f"Homepage visit tracked from server-side: {source_info.get('type', 'unknown')}")
    else:
        # Use existing traffic source from session
        source_info = session.get('traffic_source', {'type': 'organic'})
        app.logger.info("Homepage visit already tracked in session, skipping duplicate")
    
    current_year = datetime.now().year
    scroll_to_form = (request.args.get('scroll_to_form', '').lower() == 'true')
    return render_template("index.html", year=current_year, user=current_user, scroll_to_form=scroll_to_form)


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
    return render_template("upload.html", year=current_year, user=current_user)


@app.route("/start")
def start():
    # Use a temporary redirect here because browsers can cache 301s very aggressively.
    resp = redirect(url_for('index'), code=302)
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route("/get-started")
def get_started():
    """Entry point CTA: let the user choose new resume vs revise existing."""
    current_year = datetime.now().year
    return render_template("get_started.html", year=current_year, user=current_user)


@app.route("/paste-resume")
def paste_resume():
    """Fallback page for users to paste resume text when file parsing fails."""
    current_year = datetime.now().year
    show_error = (request.args.get('error') or '').strip() in ('1', 'true', 'yes')
    return render_template("paste_resume.html", year=current_year, user=current_user, show_error=show_error)


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

    parts = [p.strip() for p in re.split(r'(?<=[.!?])\s+', joined) if p and p.strip()]
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
    if isinstance(exp, list) and any((e.get('title') or e.get('company') or e.get('description') or e.get('duration')) for e in exp if isinstance(e, dict)):
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
    if isinstance(edu, list) and any((d.get('degree') or d.get('field_of_study') or d.get('institution') or d.get('year') or d.get('gpa')) for d in edu if isinstance(d, dict)):
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
    if isinstance(certs, list) and any((c.get('name') or c.get('issuer') or c.get('year')) for c in certs if isinstance(c, dict)):
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
    if isinstance(custom_sections, list) and any(isinstance(cs, dict) and (cs.get('heading') or cs.get('items')) for cs in custom_sections):
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


@app.route('/resume/templates')
@app.route('/resume/templates/')
def resume_choose_template():
    current_year = datetime.now().year
    results_data = session.get('results_data') or {}
    resume_text = str(results_data.get('revised_resume') or '')
    if not resume_text.strip():
        flash('Please create a resume first.', 'danger')
        return redirect(url_for('get_started'))
    return render_template('resume_choose_template.html', year=current_year, user=current_user, resume_text=resume_text)

@app.route("/plans")
def plans():
    current_year = datetime.now().year
    trial_unavailable = False
    next_url = str(request.args.get('next') or '').strip()
    try:
        if getattr(current_user, 'is_authenticated', False):
            trial_unavailable = _trial_already_used_for_user(current_user)
            # If the user just purchased via Stripe Payment Link and webhooks haven't updated Azure yet,
            # try to refresh paid status from Stripe and bounce them back to where they came from.
            try:
                if not is_paid_user(current_user) and _stripe_enabled():
                    if _refresh_paid_status_from_stripe_for_user(current_user):
                        return redirect(next_url or url_for('my_revisions'))
            except Exception:
                pass
    except Exception:
        trial_unavailable = False
    offer_retention = str(request.args.get('offer') or '').strip().lower() == 'retention'
    if str(request.args.get('reason') or '').strip().lower() == 'pdf':
        flash('PDF downloads are not available on free accounts.', 'warning')
    return render_template(
        "plans.html",
        year=current_year,
        user=current_user,
        trial_unavailable=trial_unavailable,
        offer_retention=offer_retention,
    )


def _get_plan_config(plan_id: str) -> Optional[dict]:
    pid = (plan_id or '').strip()
    if not pid:
        return None
    # Plan IDs must match templates/plans.html
    if pid == 'trial_14d':
        return {
            'id': pid,
            'label': '2-Week Trial',
            'price': '$1.85',
            'plan_status': 'trial',
            'duration_days': 14,
        }
    if pid == 'monthly_10_95':
        return {
            'id': pid,
            'label': 'Monthly',
            'price': '$10.95 / month',
            'plan_status': 'monthly',
            'duration_days': 31,
        }
    if pid == 'annual_6_95':
        return {
            'id': pid,
            'label': 'Annual',
            'price': '$6.95 / month (billed annually)',
            'plan_status': 'annual',
            'duration_days': 365,
        }
    return None


def _stripe_enabled() -> bool:
    return bool((os.getenv('STRIPE_SECRET_KEY') or '').strip())


def _get_stripe_customer_id_from_azure(user_id: str) -> str:
    try:
        table_client = get_users_table_client()
        e = table_client.get_entity(partition_key=str(user_id), row_key='profile')
        return str(e.get('stripe_customer_id') or '').strip()
    except Exception:
        return ''


def _get_stripe_subscription_id_from_azure(user_id: str) -> str:
    try:
        table_client = get_users_table_client()
        e = table_client.get_entity(partition_key=str(user_id), row_key='profile')
        return str(e.get('stripe_subscription_id') or '').strip()
    except Exception:
        return ''


def _find_stripe_customer_id_by_email(email: str) -> str:
    """Best-effort lookup for Stripe customer id by email (helps when webhook/profile hasn't saved ids yet)."""
    e = (email or '').strip()
    if not e or not _stripe_enabled():
        return ''
    try:
        stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
        # Prefer search when available
        try:
            res = stripe.Customer.search(query=f"email:'{e}'", limit=1)
            data = list(getattr(res, 'data', []) or [])
            if data:
                return str(getattr(data[0], 'id', '') or '').strip()
        except Exception:
            pass
        # Fallback: list by email
        res2 = stripe.Customer.list(email=e, limit=1)
        data2 = list(getattr(res2, 'data', []) or [])
        if data2:
            return str(getattr(data2[0], 'id', '') or '').strip()
    except Exception:
        return ''
    return ''


def _find_trialing_subscription_for_customer(customer_id: str) -> Optional[dict]:
    """Return a trialing subscription object (Stripe) for a customer, or None."""
    cid = (customer_id or "").strip()
    if not cid or not _stripe_enabled():
        return None
    try:
        stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
        res = stripe.Subscription.list(customer=cid, status="trialing", limit=1)
        data = list(getattr(res, "data", []) or [])
        if not data:
            return None
        sub = data[0]
        try:
            sub = stripe.Subscription.retrieve(sub.id, expand=["items.data"])
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
        stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
        sub = stripe.Subscription.retrieve(sid)
        # Prefer current_period_end; for trialing subscriptions, trial_end can be useful too.
        trial_end = getattr(sub, 'trial_end', None)
        current_period_end = getattr(sub, 'current_period_end', None)
        ts = current_period_end or trial_end
        if ts:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
        return ''
    except Exception:
        return ''


def _add_interval_approx(dt: datetime, interval: str, interval_count: int) -> datetime:
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
        stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
        subs = stripe.Subscription.list(customer=cid, status='all', limit=20)
        data = list(getattr(subs, 'data', []) or [])
        if not data:
            return {}

        def _rank(sub):
            status = str(getattr(sub, 'status', '') or '').lower()
            current_period_end = int(getattr(sub, 'current_period_end', 0) or 0)
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
            best = stripe.Subscription.retrieve(best.id, expand=["items.data.price"])
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
                    recurring = getattr(price, 'recurring', None) if price else None
                if isinstance(recurring, dict):
                    interval = str(recurring.get('interval') or '')
                    interval_count = int(recurring.get('interval_count') or 1)
                else:
                    interval = str(getattr(recurring, 'interval', '') or '')
                    interval_count = int(getattr(recurring, 'interval_count', 1) or 1)
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
                return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
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
        stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
        sub = stripe.Subscription.retrieve(sid, expand=["items.data.price"])
        status = str(getattr(sub, 'status', '') or '')
        trial_end = getattr(sub, 'trial_end', None)
        current_period_end = getattr(sub, 'current_period_end', None)
        start_date = getattr(sub, 'start_date', None) or getattr(sub, 'billing_cycle_anchor', None)

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
                    recurring = getattr(price, 'recurring', None) if price else None
                if isinstance(recurring, dict):
                    interval = str(recurring.get('interval') or '')
                    interval_count = int(recurring.get('interval_count') or 1)
                else:
                    interval = str(getattr(recurring, 'interval', '') or '')
                    interval_count = int(getattr(recurring, 'interval_count', 1) or 1)
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
                base_dt = datetime.fromtimestamp(int(start_date), tz=timezone.utc)
                next_ts = int(_add_interval_approx(base_dt, interval, interval_count).timestamp())
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
                base_dt = datetime.fromtimestamp(int(start_date), tz=timezone.utc)
                paid_through_est_ts = int(_add_interval_approx(base_dt, interval, interval_count).timestamp())
            except Exception:
                paid_through_est_ts = int(start_date)

        def _ts_to_iso(ts: Optional[int]) -> str:
            try:
                if not ts:
                    return ''
                return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
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

def _get_subscription_price_id_and_recurring(sub_obj) -> tuple[str, str, int]:
    """Return (price_id, interval, interval_count) from a subscription object; robust to dict/StripeObject."""
    try:
        items = getattr(sub_obj, 'items', None)
        items_data = getattr(items, 'data', []) if items else []
        first_item = items_data[0] if items_data else None
        # items_data entries can be StripeObjects or dicts
        if isinstance(first_item, dict):
            price = first_item.get('price')
        else:
            price = getattr(first_item, 'price', None) if first_item else None
        # Sometimes Stripe returns a bare price id string
        if isinstance(price, str):
            return (price.strip(), '', 1)
        if isinstance(price, dict):
            price_id = str(price.get('id') or '').strip()
            recurring = price.get('recurring')
        else:
            price_id = str(getattr(price, 'id', '') or '').strip() if price else ''
            recurring = getattr(price, 'recurring', None) if price else None

        interval = ''
        interval_count = 1
        if isinstance(recurring, dict):
            interval = str(recurring.get('interval') or '').strip()
            interval_count = int(recurring.get('interval_count') or 1)
        else:
            interval = str(getattr(recurring, 'interval', '') or '').strip()
            interval_count = int(getattr(recurring, 'interval_count', 1) or 1)
        return (price_id, interval, interval_count)
    except Exception:
        return ('', '', 1)

def _stripe_obj_get(obj, key: str, default=None):
    """Safely read key from StripeObject or dict (some stripe versions return dict-like objects)."""
    try:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        # StripeObject supports .get in many versions
        if hasattr(obj, "get"):
            return obj.get(key, default)
        return getattr(obj, key, default)
    except Exception:
        return default

def _stripe_upcoming_invoice(customer_id: str, subscription_id: str):
    """Get upcoming invoice using a method compatible with older stripe python versions."""
    cid = (customer_id or "").strip()
    sid = (subscription_id or "").strip()
    if not cid or not sid:
        return None
    try:
        # Newer stripe versions have stripe.Invoice.upcoming(...)
        if hasattr(stripe, "Invoice") and hasattr(stripe.Invoice, "upcoming"):
            return stripe.Invoice.upcoming(customer=cid, subscription=sid)
    except Exception:
        pass
    # Fallback: call the endpoint directly
    try:
        return stripe.Invoice._static_request("get", "/v1/invoices/upcoming", params={"customer": cid, "subscription": sid})
    except Exception:
        return None

def _stripe_subscription_raw(subscription_id: str):
    """Fetch raw subscription JSON via low-level request (works across stripe library versions)."""
    sid = (subscription_id or "").strip()
    if not sid:
        return None
    try:
        return stripe.Subscription._static_request("get", f"/v1/subscriptions/{sid}", params={})
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
        res = stripe.Invoice._static_request("get", "/v1/invoices", params={"subscription": sid, "limit": 1})
        data = _stripe_obj_get(res, "data", []) or []
        if data:
            return data[0]
    except Exception:
        return None
    return None


def _stripe_customer_has_any_subscription(customer_id: str) -> bool:
    """Return True if a Stripe customer has *any* subscription history.

    We use this to enforce that the trial offer is one-time.
    Best-effort across stripe-python versions.
    """
    cid = (customer_id or "").strip()
    if not cid or not _stripe_enabled():
        return False
    try:
        stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    except Exception:
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


def _trial_already_used_for_user(user_obj: Optional['User']) -> bool:
    """Return True if the trial should be blocked for this user.

    Enforces one-time offer at the application layer. This is necessarily best-effort:
    it reliably blocks repeat purchases for the same account and attempts to also block
    repeat purchases for the same Stripe customer/email.
    """
    try:
        if not user_obj or not getattr(user_obj, 'is_authenticated', False):
            return False

        # If they're already paid/trialing via our own checks, they shouldn't buy the trial.
        try:
            if is_paid_user(user_obj):
                return True
        except Exception:
            pass

        prof = get_user_profile_azure(getattr(user_obj, 'id', '')) or {}

        # Explicit persisted flags (set by webhook / checkout_complete)
        if bool(prof.get('trial_used', False)):
            return True
        if str(prof.get('trial_used_at') or '').strip():
            return True

        # If the user has any known plan status other than free, treat the trial as already used.
        plan_status = str(prof.get('plan_status') or '').strip().lower()
        if plan_status and plan_status != 'free':
            return True

        # Stripe-side: block if the customer/email has any subscription history.
        if _stripe_enabled():
            customer_id = str(prof.get('stripe_customer_id') or '').strip()
            if not customer_id:
                email = (getattr(user_obj, 'email', '') or '').strip()
                if email:
                    customer_id = _find_stripe_customer_id_by_email(email)
            if customer_id and _stripe_customer_has_any_subscription(customer_id):
                return True

        return False
    except Exception:
        return False

def _get_stripe_price_id(plan_id: str) -> Optional[str]:
    """Map internal plan IDs to Stripe Price IDs via env vars."""
    if plan_id == 'trial_14d':
        # Trial should be a subscription (auto-converts to monthly unless canceled).
        # Use a recurring monthly price here (or a dedicated trial recurring price).
        return (
            (os.getenv('STRIPE_PRICE_TRIAL_RECURRING') or '').strip()
            or (os.getenv('STRIPE_PRICE_MONTHLY_10_95') or '').strip()
            or None
        )
    if plan_id == 'monthly_10_95':
        return (os.getenv('STRIPE_PRICE_MONTHLY_10_95') or '').strip() or None
    if plan_id == 'annual_6_95':
        return (os.getenv('STRIPE_PRICE_ANNUAL_6_95') or '').strip() or None
    return None


def _get_stripe_trial_upfront_fee_price_id() -> Optional[str]:
    """Optional one-time fee charged at checkout for the trial (e.g. $1.85).

    Create a one-time Price in Stripe and set STRIPE_PRICE_TRIAL_FEE_1_85 to its price_ id.
    """
    return (os.getenv('STRIPE_PRICE_TRIAL_FEE_1_85') or '').strip() or None


def _get_stripe_payment_link(plan_id: str) -> Optional[str]:
    """Optional Stripe Payment Links (non-secret). If set, /checkout can redirect here directly."""
    defaults = {
        # Provided by user
        'trial_14d': 'https://buy.stripe.com/cNi6oBeZ21gXfAu1cD7Vm02',
        # Updated to latest Stripe-provided monthly link (promo codes configured here)
        'monthly_10_95': 'https://buy.stripe.com/5kQ6oBcQUaRxcoif3t7Vm05',
        'annual_6_95': 'https://buy.stripe.com/aFa9ANdUYgbR9c6bRh7Vm04',
    }
    if plan_id == 'trial_14d':
        return (os.getenv('STRIPE_PAYMENTLINK_TRIAL_14D') or '').strip() or defaults['trial_14d']
    if plan_id == 'monthly_10_95':
        return (os.getenv('STRIPE_PAYMENTLINK_MONTHLY_10_95') or '').strip() or defaults['monthly_10_95']
    if plan_id == 'annual_6_95':
        return (os.getenv('STRIPE_PAYMENTLINK_ANNUAL_6_95') or '').strip() or defaults['annual_6_95']
    return None


def _get_stripe_retention_promo_code() -> Optional[str]:
    """Return the promotion code string for retention offer (e.g. RETENTION50). Used with Payment Links."""
    return (os.getenv('STRIPE_PROMO_CODE_RETENTION') or '').strip() or None


def _get_stripe_retention_coupon_id() -> Optional[str]:
    """Return the coupon ID for retention offer. Used with Checkout Session discounts."""
    return (os.getenv('STRIPE_COUPON_RETENTION') or '').strip() or None


def _compute_retention_credit_cents(subscription) -> int:
    """Compute 50% off for one month (applied twice = 50% off for 2 months). Works with flexible billing."""
    try:
        override = (os.getenv('STRIPE_RETENTION_CREDIT_CENTS') or '').strip()
        if override and override.isdigit():
            return int(override)
    except Exception:
        pass
    # 50% of one month: monthly $5.48, annual $3.48
    DEFAULT_MONTHLY_HALF_CENTS = 548   # 50% of $10.95
    DEFAULT_ANNUAL_HALF_CENTS = 348    # 50% of $6.95
    try:
        price_id, interval, interval_count = _get_subscription_price_id_and_recurring(subscription)
        items = getattr(subscription, 'items', None)
        items_data = list(getattr(items, 'data', []) or []) if items else []
        if not items_data:
            is_annual = interval == 'year' or (interval == 'month' and interval_count == 12)
            return DEFAULT_ANNUAL_HALF_CENTS if is_annual else DEFAULT_MONTHLY_HALF_CENTS
        first = items_data[0]
        price = getattr(first, 'price', None) if not isinstance(first, dict) else (first.get('price') if isinstance(first, dict) else None)
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
            is_annual = interval == 'year' or (interval == 'month' and interval_count == 12)
            return DEFAULT_ANNUAL_HALF_CENTS if is_annual else DEFAULT_MONTHLY_HALF_CENTS
        # 50% of one month (applied to each of next 2 invoices)
        if interval == 'year' or (interval == 'month' and interval_count == 12):
            return (unit // 12) // 2  # half of one month of annual
        return unit // 2  # half of one month of monthly
    except Exception:
        return DEFAULT_MONTHLY_HALF_CENTS


def _redirect_to_stripe_payment_link(plan_id: str, offer_retention: bool = False) -> Optional['Response']:
    """Redirect to Stripe Payment Link with useful prefill params so webhook can map back to user."""
    # Trial must be a subscription with a 14-day trial and auto-convert to monthly unless canceled.
    # If Trial is a one-time Payment Link, it cannot auto-renew. So do NOT use a Payment Link for trial.
    if plan_id == 'trial_14d':
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
        params['client_reference_id'] = str(getattr(current_user, 'id', '') or '')
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
    """Checkout entrypoint.

    If STRIPE_SECRET_KEY is configured, creates a Stripe Checkout Session and redirects to Stripe.
    Otherwise falls back to the placeholder confirmation page.
    """
    plan_id = request.args.get('plan', '').strip()
    offer_retention = str(request.args.get('offer') or '').strip().lower() == 'retention'
    plan = _get_plan_config(plan_id)
    if not plan:
        flash("Please select a valid plan.", "danger")
        return redirect(url_for("plans"))

    if not current_user.is_authenticated:
        # Require login so we can unlock paid features for the correct user.
        return redirect(url_for("login", next=request.full_path))

    # Enforce: 2-week trial is a one-time offer.
    if plan_id == 'trial_14d' and _trial_already_used_for_user(current_user):
        flash("The 2-week trial is a one-time offer and has already been used on this account. Please choose Monthly or Annual.", "warning")
        return redirect(url_for("plans"))

    # Upgrade during trial:
    # Charge the customer now (so they enter card + pay immediately), but keep the trial time.
    # We do this by charging a one-time amount now and then applying it as a customer-balance credit,
    # while updating the existing trial subscription to the target plan (annual/monthly).
    if _stripe_enabled() and plan_id in ("monthly_10_95", "annual_6_95"):
        try:
            prof = get_user_profile_azure(getattr(current_user, "id", "")) or {}
            customer_id = str(prof.get("stripe_customer_id") or "").strip()
            if not customer_id:
                customer_id = _find_stripe_customer_id_by_email((getattr(current_user, "email", "") or "").strip())
            if customer_id:
                trial_sub = _find_trialing_subscription_for_customer(customer_id)
                if trial_sub:
                    price_id = _get_stripe_price_id(plan_id)
                    if not price_id:
                        flash("Checkout is not configured. Please contact support.", "danger")
                        return redirect(url_for("plans"))
                    stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
                    price = stripe.Price.retrieve(price_id)
                    unit_amount = int(getattr(price, "unit_amount", 0) or 0)
                    currency = str(getattr(price, "currency", "usd") or "usd")
                    if unit_amount <= 0:
                        flash("Checkout is not configured. Please contact support.", "danger")
                        return redirect(url_for("plans"))

                    success_url = url_for('my_revisions', _external=True, _scheme=request.scheme) + "?checkout=success"
                    cancel_url = url_for('plans', _external=True, _scheme=request.scheme)
                    session_obj = stripe.checkout.Session.create(
                        mode="payment",
                        customer=customer_id,
                        line_items=[
                            {
                                "price_data": {
                                    "currency": currency,
                                    "unit_amount": unit_amount,
                                    "product_data": {"name": f"{plan.get('label')} (starts after trial)"},
                                },
                                "quantity": 1,
                            }
                        ],
                        client_reference_id=str(current_user.id),
                        metadata={
                            "upgrade_from_trial": "1",
                            "plan_id": plan_id,
                            "trial_subscription_id": str(getattr(trial_sub, "id", "") or ""),
                        },
                        success_url=success_url,
                        cancel_url=cancel_url,
                    )
                    return redirect(session_obj.url, code=303)
        except Exception:
            pass

    # For brand-new Monthly/Annual purchases, prefer Stripe Payment Links.
    # This keeps promo-code behavior consistent with what you configure in Stripe.
    if _stripe_enabled() and plan_id in ("monthly_10_95", "annual_6_95"):
        pl_redirect = _redirect_to_stripe_payment_link(plan_id, offer_retention=offer_retention)
        if pl_redirect:
            return pl_redirect

    # For other plans (or if Payment Links are configured later), still allow Payment Link redirects.
    pl_redirect = _redirect_to_stripe_payment_link(plan_id, offer_retention=offer_retention)
    if pl_redirect:
        return pl_redirect

    # Alternative: Real Stripe Checkout flow via API (requires secret key + price ids).
    if _stripe_enabled():
        price_id = _get_stripe_price_id(plan_id)
        if not price_id:
            flash("Checkout is not configured. Please contact support.", "danger")
            return redirect(url_for("plans"))

        stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()

        # Build absolute URLs
        success_url = url_for('my_revisions', _external=True, _scheme=request.scheme) + "?checkout=success"
        cancel_url = url_for('plans', _external=True, _scheme=request.scheme)
        try:
            subscription_data = None
            line_items = [{"price": price_id, "quantity": 1}]
            if plan_id == 'trial_14d':
                # 14-day trial that converts into the recurring monthly subscription unless canceled
                subscription_data = {"trial_period_days": 14}
                # Optional one-time upfront trial fee (e.g. $1.85)
                fee_price = _get_stripe_trial_upfront_fee_price_id()
                if fee_price:
                    line_items.append({"price": fee_price, "quantity": 1})

            session_params = {
                "mode": "subscription",
                "line_items": line_items,
                "customer_email": (getattr(current_user, 'email', '') or None),
                "client_reference_id": str(current_user.id),
                "metadata": {"plan_id": plan_id},
                "subscription_data": subscription_data,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "allow_promotion_codes": True,
            }
            # Retention offer: pre-apply coupon when user came from cancel flow
            if offer_retention:
                coupon_id = _get_stripe_retention_coupon_id()
                if coupon_id:
                    session_params["discounts"] = [{"coupon": coupon_id}]
            session_obj = stripe.checkout.Session.create(**session_params)
            return redirect(session_obj.url, code=303)
        except Exception as e:
            logger.error(f"Stripe checkout session create failed: {str(e)}")
            flash("Checkout is temporarily unavailable. Please try again.", "danger")
            return redirect(url_for("plans"))

    # Fallback placeholder confirmation page (no Stripe configured)
    current_year = datetime.now().year
    return render_template("checkout.html", year=current_year, user=current_user, plan=plan)


@app.route("/checkout/complete", methods=["POST"])
@login_required
def checkout_complete():
    """Simulate purchase completion by updating the Azure Users profile.

    This makes plan links functional without integrating a payment processor yet.
    """
    plan_id = request.form.get('plan', '').strip()
    plan = _get_plan_config(plan_id)
    if not plan:
        flash("Invalid plan selection.", "danger")
        return redirect(url_for("plans"))

    # Enforce one-time trial offer even when running with the placeholder checkout flow.
    if plan_id == 'trial_14d' and _trial_already_used_for_user(current_user):
        flash("The 2-week trial is a one-time offer and has already been used on this account.", "warning")
        return redirect(url_for("plans"))

    try:
        paid_until = (datetime.now(timezone.utc) + timedelta(days=int(plan.get('duration_days') or 0))).isoformat()
        table_client = get_users_table_client()
        entity = {
            'PartitionKey': str(current_user.id),
            'RowKey': 'profile',
            'is_paid': True,
            'plan_status': plan.get('plan_status') or 'paid',
            'paid_until': paid_until,
        }
        if plan_id == 'trial_14d':
            entity['trial_used'] = True
            entity['trial_used_at'] = datetime.now(timezone.utc).isoformat()
        table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
        flash(f"You're all set! {plan.get('label')} activated.", "success")
        return redirect(url_for("my_revisions"))
    except Exception as e:
        logger.error(f"checkout_complete error: {str(e)}")
        flash("We couldn't activate your plan. Please try again.", "danger")
        return redirect(url_for("plans"))


@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    """Stripe webhook handler.

    Required env vars:
    - STRIPE_SECRET_KEY
    - STRIPE_WEBHOOK_SECRET
    - STRIPE_PRICE_MONTHLY_10_95 / STRIPE_PRICE_ANNUAL_6_95

    Trial setup (to auto-convert to monthly unless canceled):
    - STRIPE_PRICE_TRIAL_RECURRING (optional, otherwise uses STRIPE_PRICE_MONTHLY_10_95)
    - STRIPE_PRICE_TRIAL_FEE_1_85 (optional one-time fee price)
    """
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", "")
    webhook_secret = (os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip()
    if not webhook_secret:
        return ("Webhook not configured", 400)

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception as e:
        logger.error(f"stripe_webhook signature error: {str(e)}")
        return ("Invalid signature", 400)

    try:
        # Stripe python SDK versions vary in whether webhook events are dicts or StripeObjects.
        # Normalize here so the rest of the handler can safely use .get(...) on plain dicts.
        etype = _stripe_obj_get(event, "type", "")
        data = _stripe_obj_get(_stripe_obj_get(event, "data", {}), "object", {}) or {}
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

        # We primarily rely on checkout.session.completed to map the customer to our user_id.
        if etype == "checkout.session.completed":
            client_ref = data.get("client_reference_id")
            customer_id = data.get("customer")
            subscription_id = data.get("subscription")
            plan_id = (data.get("metadata") or {}).get("plan_id", "")
            upgrade_from_trial = str((data.get("metadata") or {}).get("upgrade_from_trial") or "").strip()
            trial_subscription_id = str((data.get("metadata") or {}).get("trial_subscription_id") or "").strip()
            mode = str(data.get("mode") or "").strip().lower()

            # Fallback mapping: if client_reference_id wasn't present, try to find user by email.
            if not client_ref:
                try:
                    email = (
                        (data.get("customer_details") or {}).get("email")
                        or data.get("customer_email")
                        or ""
                    )
                    email = str(email).strip().lower()
                    if email:
                        for uid, u in users.items():
                            if (getattr(u, "email", "") or "").strip().lower() == email:
                                client_ref = uid
                                break
                except Exception:
                    pass

            if not client_ref:
                return ("No client_reference_id", 200)

            # Special case: trial upgrade where we charged up-front (payment mode) and need to:
            # 1) credit the customer balance so the first subscription invoice at trial end is covered
            # 2) update the existing trial subscription to the selected plan (annual/monthly)
            if upgrade_from_trial == "1" and mode == "payment" and customer_id and trial_subscription_id and plan_id in ("monthly_10_95", "annual_6_95"):
                stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
                try:
                    amount_total = int(data.get("amount_total") or 0)
                    currency = str(data.get("currency") or "usd")
                except Exception:
                    amount_total = 0
                    currency = "usd"

                # Apply customer balance credit equal to the amount paid now.
                # This will be applied automatically to the subscription invoice at trial end.
                try:
                    if amount_total > 0:
                        stripe.Customer.create_balance_transaction(
                            customer_id,
                            amount=-amount_total,
                            currency=currency,
                            description=f"Prepayment credit for {plan_id} (paid during trial)",
                        )
                except Exception:
                    pass

                # Update the existing trial subscription to the target plan (keeps the same trial_end).
                try:
                    price_id = _get_stripe_price_id(plan_id)
                    if price_id:
                        sub = stripe.Subscription.retrieve(trial_subscription_id, expand=["items.data"])
                        items = getattr(sub, "items", None)
                        items_data = getattr(items, "data", []) if items else []
                        item_id = str(getattr(items_data[0], "id", "") or "") if items_data else ""
                        if not item_id:
                            try:
                                si = stripe.SubscriptionItem.list(subscription=trial_subscription_id, limit=1)
                                si_data = list(getattr(si, "data", []) or [])
                                if si_data:
                                    item_id = str(getattr(si_data[0], "id", "") or "").strip()
                            except Exception:
                                item_id = ""
                        if item_id:
                            stripe.Subscription.modify(
                                trial_subscription_id,
                                items=[{"id": item_id, "price": price_id}],
                                proration_behavior="none",
                                metadata={"plan_id": plan_id},
                            )
                        # Update Azure profile (paid_until stays at trial end until renewal)
                        paid_until = ""
                        try:
                            current_period_end = getattr(sub, "current_period_end", None)
                            if current_period_end:
                                paid_until = datetime.fromtimestamp(int(current_period_end), tz=timezone.utc).isoformat()
                        except Exception:
                            paid_until = ""
                        try:
                            table_client = get_users_table_client()
                            entity = {
                                "PartitionKey": str(client_ref),
                                "RowKey": "profile",
                                "is_paid": True,
                                "plan_status": plan_id,
                                "stripe_customer_id": str(customer_id),
                                "stripe_subscription_id": str(trial_subscription_id),
                            }
                            if paid_until:
                                entity["paid_until"] = paid_until
                            table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
                        except Exception:
                            pass
                except Exception:
                    pass

                return ("OK", 200)

            # Fetch subscription to compute paid_until
            stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
            paid_until = ""
            plan_status = ""
            try:
                if subscription_id and stripe.api_key:
                    sub = stripe.Subscription.retrieve(subscription_id)
                    plan_status = str(getattr(sub, "status", "") or "")
                    current_period_end = getattr(sub, "current_period_end", None)
                    if current_period_end:
                        paid_until = datetime.fromtimestamp(int(current_period_end), tz=timezone.utc).isoformat()
            except Exception:
                pass

            try:
                table_client = get_users_table_client()
                entity = {
                    "PartitionKey": str(client_ref),
                    "RowKey": "profile",
                    "is_paid": True,
                    "plan_status": (plan_id or plan_status or "paid"),
                }
                if str(plan_id or '').strip() == 'trial_14d':
                    # Persist one-time trial usage flag.
                    entity["trial_used"] = True
                    entity["trial_used_at"] = datetime.now(timezone.utc).isoformat()
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

            # If the customer previously started a trial subscription, and then purchased a paid plan,
            # Stripe Payment Links/Checkout can result in multiple subscriptions. To avoid double-billing,
            # cancel any other *trialing* subscriptions for this customer (keep the newly purchased one).
            try:
                if customer_id and stripe.api_key:
                    subs_trialing = stripe.Subscription.list(customer=customer_id, status="trialing", limit=20)
                    tdata = list(getattr(subs_trialing, "data", []) or [])
                    for s in tdata:
                        sid = str(getattr(s, "id", "") or "")
                        if sid and subscription_id and sid == str(subscription_id):
                            continue
                        if sid:
                            try:
                                stripe.Subscription.delete(sid)
                            except Exception:
                                pass
            except Exception:
                pass

        # Retention offer: add second 50% credit when first invoice after offer is paid
        if etype == "invoice.paid":
            stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
            inv = data
            if not inv.get("subscription"):
                pass  # Skip non-subscription invoices
            else:
                customer_id = str(inv.get("customer") or "").strip()
                if customer_id:
                    try:
                        cust = stripe.Customer.retrieve(customer_id)
                        meta = dict(getattr(cust, "metadata", None) or {})
                        credit_cents_str = meta.get("retention_2nd_credit_cents", "").strip()
                        if credit_cents_str and credit_cents_str.isdigit():
                            credit_cents = int(credit_cents_str)
                            currency = str(inv.get("currency") or "usd").lower()
                            stripe.Customer.create_balance_transaction(
                                customer_id,
                                amount=-credit_cents,
                                currency=currency,
                                description="Retention offer: 50% off month 2 of 2",
                            )
                            meta["retention_2nd_credit_cents"] = ""
                            stripe.Customer.modify(customer_id, metadata=meta)
                            logger.info(f"Applied retention 2nd credit: {credit_cents} cents for customer {customer_id}")
                    except Exception as e:
                        logger.warning(f"retention 2nd credit webhook error: {str(e)}")

        # Keep subscription status in sync (cancel/expire)
        if etype in ("customer.subscription.updated", "customer.subscription.deleted"):
            stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
            sub = data
            customer_id = sub.get("customer")
            subscription_id = sub.get("id")
            status = sub.get("status")
            current_period_end = sub.get("current_period_end")
            paid_until = ""
            if current_period_end:
                try:
                    paid_until = datetime.fromtimestamp(int(current_period_end), tz=timezone.utc).isoformat()
                except Exception:
                    paid_until = ""

            # Find user by stripe_customer_id in Azure Users table
            if customer_id:
                try:
                    table_client = get_users_table_client()
                    # scan profiles (small scale). For large scale, add an index.
                    for e in table_client.list_entities():
                        if e.get("RowKey") != "profile":
                            continue
                        if str(e.get("stripe_customer_id") or "") == str(customer_id):
                            uid = str(e.get("PartitionKey"))
                            entity = {"PartitionKey": uid, "RowKey": "profile"}
                            entity["plan_status"] = str(status or "")
                            if paid_until:
                                entity["paid_until"] = paid_until
                            # Consider user paid only if active/trialing
                            entity["is_paid"] = str(status or "").lower() in ("active", "trialing")
                            if subscription_id:
                                entity["stripe_subscription_id"] = str(subscription_id)
                            table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
                            break
                except Exception as e:
                    logger.error(f"stripe_webhook subscription sync error: {str(e)}")
                    # do not fail webhook

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

    stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
    customer_id = _get_stripe_customer_id_from_azure(getattr(current_user, 'id', ''))
    if not customer_id:
        flash("We couldn't find your billing profile yet. If you just purchased, refresh and try again.", "danger")
        return redirect(url_for("my_revisions"))

    try:
        return_url = url_for("my_revisions", _external=True, _scheme=request.scheme)
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


def _append_cancellation_feedback(user_id: str, subscription_id: str, reason: str, reason_other: str, email: str = "") -> None:
    """Append cancellation reason to feedback file (best-effort)."""
    try:
        records = []
        if os.path.exists(CANCELLATION_FEEDBACK_FILE):
            with open(CANCELLATION_FEEDBACK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                records = list(data.get("records") or [])
        records.append({
            "user_id": str(user_id or ""),
            "subscription_id": str(subscription_id or ""),
            "reason": str(reason or ""),
            "reason_other": str(reason_other or ""),
            "email": str(email or ""),
            "at": datetime.now(timezone.utc).isoformat(),
        })
        with open(CANCELLATION_FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump({"records": records}, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _stripe_cancellation_details_from_reason(cancel_reason: str, cancel_reason_other: str, cancel_reason_label: str = "") -> Optional[dict]:
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


def _stripe_cancellation_metadata_from_reason(cancel_reason: str, cancel_reason_other: str, cancel_reason_label: str = "") -> Optional[dict]:
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
    subscription_id = _get_stripe_subscription_id_from_azure(user_id)
    if not subscription_id:
        flash("No active subscription found. If you just canceled, your access continues until the end of your billing period.", "info")
        return redirect(url_for("settings_page"))

    # Fetch subscription details for display
    stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    try:
        sub = stripe.Subscription.retrieve(subscription_id, expand=["items.data.price"])
        status = str(_stripe_obj_get(sub, "status", "") or "").strip().lower()
        if status not in ("active", "trialing"):
            flash("Your subscription is not active.", "info")
            return redirect(url_for("settings_page"))

        current_period_end = _stripe_obj_get(sub, "current_period_end", None)
        period_end_display = ""
        if current_period_end:
            try:
                dt = datetime.fromtimestamp(int(current_period_end), tz=timezone.utc)
                period_end_display = dt.strftime("%B %d, %Y")
            except Exception:
                period_end_display = "end of billing period"

        interval_label = "Monthly"
        si_data = list(getattr(getattr(sub, "items", None), "data", []) or [])
        if si_data:
            p = getattr(si_data[0], "price", None) or (si_data[0] if isinstance(si_data[0], dict) else {}).get("price")
            if p:
                interval = str(_stripe_obj_get(p, "recurring", {}).get("interval", "") or "").lower()
                interval_count = int(_stripe_obj_get(p, "recurring", {}).get("interval_count", 1) or 1)
                if interval == "year" or (interval == "month" and interval_count == 12):
                    interval_label = "Annual"
    except Exception as e:
        logger.error(f"billing_cancel_page subscription fetch: {str(e)}")
        flash("Unable to load subscription details. Please try again.", "danger")
        return redirect(url_for("settings_page"))

    resp = make_response(render_template(
        "billing_cancel.html",
        subscription_id=subscription_id,
        interval_label=interval_label,
        period_end_display=period_end_display or "end of billing period",
    ))
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
    stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    sub = stripe.Subscription.retrieve(subscription_id, expand=["items.data.price"])
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
    stripe.Subscription.modify(subscription_id, cancel_at_period_end=False)
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
        flash(str(e.user_message) if getattr(e, "user_message", None) else "Unable to apply offer. Please try again.", "danger")
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
        return jsonify({"success": False, "error": "Billing is not configured."}), 400

    user_id = getattr(current_user, "id", "")
    subscription_id = _get_stripe_subscription_id_from_azure(user_id)
    if not subscription_id:
        return jsonify({"success": False, "error": "No active subscription found."}), 404

    try:
        success, msg = _apply_retention_offer(subscription_id)
        if success:
            return jsonify({
                "success": True,
                "message": msg,
                "redirect_url": url_for("settings_page"),
            })
        return jsonify({"success": False, "error": msg or "Unable to apply offer. Please try again."}), 400
    except stripe.error.InvalidRequestError as e:
        logger.warning(f"api_billing_apply_retention Stripe error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e.user_message) if getattr(e, "user_message", None) else "Unable to apply offer. Please try again.",
        }), 400
    except Exception as e:
        logger.error(f"api_billing_apply_retention error: {str(e)}")
        return jsonify({"success": False, "error": "Unable to apply the offer. Please try again."}), 500


@app.route("/api/billing/cancel", methods=["POST"])
@login_required
def api_billing_cancel():
    """Cancel subscription via Stripe API. Called after user confirms in custom modal."""
    if not _stripe_enabled():
        return jsonify({"error": "Billing not configured"}), 400

    user_id = getattr(current_user, "id", "")
    subscription_id = _get_stripe_subscription_id_from_azure(user_id)
    if not subscription_id:
        return jsonify({"error": "No active subscription found"}), 404

    data = request.get_json(silent=True) or {}
    cancel_at_period_end = data.get("cancel_at_period_end", True)
    cancel_reason = str(data.get("cancel_reason") or "").strip()
    cancel_reason_other = str(data.get("cancel_reason_other") or "").strip()
    cancel_reason_label = str(data.get("cancel_reason_label") or "").strip()
    cancellation_details = _stripe_cancellation_details_from_reason(cancel_reason, cancel_reason_other, cancel_reason_label)
    cancellation_metadata = _stripe_cancellation_metadata_from_reason(cancel_reason, cancel_reason_other, cancel_reason_label)

    stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    try:
        if cancel_at_period_end:
            # Best-effort: include cancellation reason so it shows in Stripe.
            try:
                modify_params: dict = {"cancel_at_period_end": True}
                if cancellation_details:
                    modify_params["cancellation_details"] = cancellation_details
                if cancellation_metadata:
                    modify_params["metadata"] = cancellation_metadata
                stripe.Subscription.modify(subscription_id, **modify_params)
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
                    stripe.Subscription.modify(subscription_id, **retry_params)
                else:
                    raise
            if cancel_reason or cancel_reason_other:
                try:
                    email = str(getattr(current_user, "email", "") or "")
                    logger.info(
                        "billing_cancel reason user_id=%s subscription_id=%s reason=%s other=%s",
                        user_id, subscription_id, cancel_reason, cancel_reason_other,
                    )
                    _append_cancellation_feedback(user_id, subscription_id, cancel_reason, cancel_reason_other, email)
                except Exception as e:
                    logger.warning("billing_cancel feedback save failed: %s", str(e))
            return jsonify({
                "success": True,
                "cancel_at_period_end": True,
                "message": "Your subscription will cancel at the end of your billing period. You'll keep access until then.",
            })
        else:
            # Immediate cancel. To keep the reason/explanation visible in Stripe Dashboard, first attach
            # it to the subscription (metadata + cancellation_details) then delete.
            if cancellation_details or cancellation_metadata:
                try:
                    modify_params: dict = {}
                    if cancellation_details:
                        modify_params["cancellation_details"] = cancellation_details
                    if cancellation_metadata:
                        modify_params["metadata"] = cancellation_metadata
                    if modify_params:
                        stripe.Subscription.modify(subscription_id, **modify_params)
                except Exception as e:
                    logger.warning(
                        "billing_cancel: unable to attach cancellation reason before delete: %s",
                        str(e),
                    )
            stripe.Subscription.delete(subscription_id)

            if cancel_reason or cancel_reason_other:
                try:
                    email = str(getattr(current_user, "email", "") or "")
                    logger.info(
                        "billing_cancel(immediate) reason user_id=%s subscription_id=%s reason=%s other=%s",
                        user_id, subscription_id, cancel_reason, cancel_reason_other,
                    )
                    _append_cancellation_feedback(user_id, subscription_id, cancel_reason, cancel_reason_other, email)
                except Exception as e:
                    logger.warning("billing_cancel(immediate) feedback save failed: %s", str(e))
            return jsonify({
                "success": True,
                "cancel_at_period_end": False,
                "message": "Your subscription has been canceled.",
            })
    except stripe.error.InvalidRequestError as e:
        logger.warning(f"api_billing_cancel Stripe error: {str(e)}")
        return jsonify({"error": str(e.user_message) if getattr(e, "user_message", None) else "Invalid request"}), 400
    except Exception as e:
        logger.error(f"api_billing_cancel error: {str(e)}")
        return jsonify({"error": "Unable to cancel subscription. Please try again."}), 500


@app.route("/results", methods=["POST"])
#login_required
def results_route():
    _safe_print("=== results_route called ===")
    _safe_log_event('results_route POST: start')
    try:
        resume_text = ""
        
        # Enforce free tier revision limit (2) for authenticated non-paid users.
        if current_user.is_authenticated and (not is_paid_user(current_user)):
            try:
                used = len(get_user_revisions(current_user.id))
                if used >= FREE_REVISION_LIMIT:
                    flash("Free tier includes 2 resume revisions. Upgrade to unlock unlimited revisions and PDF downloads.", "danger")
                    return redirect(url_for("plans", limit="1"))
            except Exception:
                # If counting fails, do not block.
                pass
        
        # Check if file was uploaded
        if 'resumeFile' in request.files:
            file = request.files['resumeFile']
            if file and file.filename:
                _safe_print(f"Processing uploaded file: {file.filename}")
                _safe_log_event(f"results_route POST: received upload filename={secure_filename(file.filename)}")
                try:
                    resume_text = extract_text_from_file(file)
                    _safe_print(f"Extracted text length: {len(resume_text)}")
                    _safe_log_event(f"results_route POST: extracted_text_len={len(resume_text)}")
                    if not resume_text or not resume_text.strip():
                        _safe_print("Uploaded file parsed but contained no extractable text")
                        _safe_log_event('results_route POST: extracted text empty')
                        return redirect(url_for('paste_resume', error='1'))
                except Exception as e:
                    _safe_log_exception('upload processing failed', e)
                    _safe_log_event('results_route POST: upload processing failed (see exception block above)')
                    return redirect(url_for('paste_resume', error='1'))
        
        # If no file uploaded, check for text input  
        if not resume_text:
            resume_text = request.form.get("resume", "").strip()
        
        # Validate that we have resume content
        if not resume_text:
            flash("Please upload a resume file or paste your resume content", 'danger')
            return redirect(url_for('index', scroll_to_form='true'))
        
        # Get job description (optional)
        job_description = request.form.get("jobDescription", "").strip()
        
        # Process the resume
        _safe_print(f"Resume text preview (first 200 chars): {resume_text[:200]}...")
        _safe_print(f"Job description preview: {job_description[:100] if job_description else 'None'}...")
        _safe_log_event(f"results_route POST: calling revise_resume resume_len={len(resume_text)} jd_len={len(job_description)}")
        revised_resume, feedback = revise_resume(resume_text, job_description)
        _safe_log_event(f"results_route POST: revise_resume ok revised_len={len(revised_resume or '')}")
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
                flash("You've reached the free tier limit (2 revisions). Upgrade to save unlimited revisions.", "danger")
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
        conversion_info = analytics.track_conversion(session, "resume_submission")
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
            session['results_data']['source_revision_id'] = source_revision_id
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
        _safe_log_event('results_route POST: unhandled exception (see results_route error block above)')
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
        _safe_log_event('results_get GET: has results_data (keys unavailable)')
    # Keep data in session for template selection
    # session.pop would remove it, so we use session.get and keep it available
    resp = make_response(render_template(
        "result.html",
        original_resume=data.get('original_resume', ''),
        revised_resume=data.get('revised_resume', ''),
        feedback=data.get('feedback', {}),
        job_description=data.get('job_description', ''),
        error=None
    ))
    # Transactional page: never cache (prevents showing a previous resume after a new submission)
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
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
        'modern': 'modern',
        'executive': 'executive',

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
        'minimalSidebar': 'Clean',
        'classicRose': 'Classic',
        'creative2': 'Creative',
        'boldProfessional': 'Bold Professional',
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

    raw_snapshot = str(_entity_get_ci((entity or {}), plain_prop, '') or '').strip()
    raw_snapshot_gz_b64 = str(_entity_get_ci((entity or {}), gz_prop, '') or '').strip()

    # Backward compatibility: older saves stored only one snapshot on the revision entity.
    if not raw_snapshot and not raw_snapshot_gz_b64:
        legacy_tid = _canonical_template_id(str(_entity_get_ci((entity or {}), 'template_id', '') or '').strip() or 'professional')
        if legacy_tid == tid:
            raw_snapshot = str(_entity_get_ci((entity or {}), 'template_structured_resume', '') or '').strip()
            raw_snapshot_gz_b64 = str(_entity_get_ci((entity or {}), 'template_structured_resume_gz_b64', '') or '').strip()

            # Extra legacy aliases (defensive): camelCase keys from older experiments.
            if not raw_snapshot:
                raw_snapshot = str(_entity_get_ci((entity or {}), 'templateStructuredResume', '') or '').strip()
            if not raw_snapshot_gz_b64:
                raw_snapshot_gz_b64 = str(_entity_get_ci((entity or {}), 'templateStructuredResumeGzB64', '') or '').strip()

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


@app.route("/api/parse-resume-for-template", methods=["POST"])
def parse_resume_for_template():
    """Parse resume and store structured data in session for template viewing"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        template_name = _canonical_template_id(data.get('template', 'professional'))
        requested_source_revision_id = str(data.get('source_revision_id') or '').strip()

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
            return jsonify({"success": False, "error": "Resume data not found"}), 404

        # If the client provided a source revision id, and the user is authenticated,
        # validate ownership and attach it to the session so template saves can persist.
        if requested_source_revision_id and current_user.is_authenticated:
            try:
                table_client = get_table_client()
                table_client.get_entity(
                    partition_key=str(current_user.id),
                    row_key=str(requested_source_revision_id),
                )
                results_data['source_revision_id'] = str(requested_source_revision_id)
                session['results_data'] = results_data
                session.modified = True
            except Exception:
                # Ignore invalid/non-owned revision ids
                pass
        
        revised_resume = results_data.get('revised_resume', '')
        if not revised_resume:
            return jsonify({"success": False, "error": "Revised resume not found"}), 404
        
        # Parse resume to get structured data.
        # If the resume was created via our builder, we already have a structured object.
        structured_resume = None
        try:
            sr = results_data.get('structured_resume') if isinstance(results_data, dict) else None
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
            'revised_resume': revised_resume,  # Keep original text as fallback
            # Carry the hub linkage through the SPA so template saves can persist.
            'source_revision_id': str(results_data.get('source_revision_id') or '').strip(),
        }
        session.modified = True
        
        return jsonify({
            "success": True,
            "template": template_name
        })
        
    except Exception as e:
        logger.error(f"Error parsing resume for template: {str(e)}")
        _safe_log_exception('parse_resume_for_template error', e)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/template-data", methods=["GET"])
def get_template_data():
    """Get structured resume data for template viewer"""
    template_data = session.get('template_data')
    if not template_data:
        return jsonify({"error": "Template data not found"}), 404

    results_data = session.get('results_data') or {}
    source_revision_id = str(
        (results_data.get('source_revision_id') if isinstance(results_data, dict) else None)
        or (template_data.get('source_revision_id') if isinstance(template_data, dict) else None)
        or ''
    ).strip()
    
    return jsonify({
        "success": True,
        "resume": template_data['structured_resume'],
        "template": template_data['template_name'],
        "revised_resume": template_data.get('revised_resume', ''),
        "source_revision_id": source_revision_id,
    })


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
        requested_source_revision_id = str(data.get('source_revision_id') or '').strip()
        if not isinstance(resume, dict):
            return jsonify({"success": False, "error": "Invalid resume payload"}), 400

        # Allow the client to initialize a preview session even if parse-resume-for-template
        # has not run yet (e.g., live preview in the resume wizard).
        if not template_data:
            results_data = session.get('results_data') or {}
            source_revision_id = str(
                (results_data.get('source_revision_id') if isinstance(results_data, dict) else None)
                or ''
            ).strip()

            template_name = _canonical_template_id(requested_template_name or 'professional')
            template_data = {
                'structured_resume': resume,
                'template_name': template_name,
                'revised_resume': str(data.get('revised_resume') or ''),
                'source_revision_id': source_revision_id,
            }
            session['template_data'] = template_data
            session.modified = True
            return jsonify({
                "success": True,
                "template": template_name,
                "persisted_to_hub": False,
                "persist_reason": "preview" if is_preview else None,
            })

        # Update only the structured resume. Keep template_name and revised_resume intact.
        template_data["structured_resume"] = resume
        if requested_template_name:
            template_data["template_name"] = _canonical_template_id(requested_template_name)
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
                        or (template_data.get('source_revision_id') if isinstance(template_data, dict) else None)
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
                        source_revision_id = str(requested_source_revision_id)
                        # Repair session linkage for subsequent requests.
                        if isinstance(results_data, dict):
                            results_data['source_revision_id'] = source_revision_id
                            session['results_data'] = results_data
                        if isinstance(template_data, dict):
                            template_data['source_revision_id'] = source_revision_id
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
                    revised_resume = str(template_data.get('revised_resume') or '')
                    
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
                            results_data['source_revision_id'] = source_revision_id
                            session['results_data'] = results_data
                        if isinstance(template_data, dict):
                            template_data['source_revision_id'] = source_revision_id
                            session['template_data'] = template_data
                    except FreeTierLimitReached:
                        # User has hit the free tier limit
                        persist_reason = 'free_tier_limit'
                        source_revision_id = None
                    except Exception as e:
                        logger.error(f"Failed to auto-create revision: {str(e)}")
                        persist_reason = 'revision_creation_failed'
                        source_revision_id = None
                
                if source_revision_id:
                    template_id = _canonical_template_id(template_data.get('template_name') or 'professional')

                    snapshot = json.dumps(resume, ensure_ascii=False)
                    snapshot_bytes = snapshot.encode('utf-8')

                    table_client = get_table_client()
                    try:
                        existing = table_client.get_entity(partition_key=str(current_user.id), row_key=source_revision_id)
                    except Exception:
                        existing = None

                    if existing is None:
                        persist_reason = 'revision_not_found'
                    else:
                        existing['template_id'] = template_id
                        existing['template_saved_at'] = datetime.now(timezone.utc).isoformat()

                        # Track all saved templates for this revision (small JSON list)
                        try:
                            current_list_raw = str(existing.get('template_saved_templates') or '').strip()
                            current_list = json.loads(current_list_raw) if current_list_raw else []
                            if not isinstance(current_list, list):
                                current_list = []
                        except Exception:
                            current_list = []
                        saved_set = set([_canonical_template_id(t) for t in current_list if str(t or '').strip()])
                        saved_set.add(template_id)
                        try:
                            existing['template_saved_templates'] = json.dumps(sorted(saved_set), ensure_ascii=False)
                        except Exception:
                            # Best effort; don't block saves
                            pass

                        # Store per-template snapshot (allows multiple template versions per revision)
                        per_plain_prop, per_gz_prop, per_at_prop = _template_snapshot_prop_names(template_id)
                        existing[per_at_prop] = existing['template_saved_at']

                        # Azure Table Storage string properties have tight size limits.
                        # Prefer plain JSON when small; otherwise fall back to gzipped base64.
                        if len(snapshot_bytes) <= 60_000:
                            existing['template_structured_resume'] = snapshot
                            existing['template_structured_resume_gz_b64'] = ''

                            existing[per_plain_prop] = snapshot
                            existing[per_gz_prop] = ''
                            table_client.update_entity(existing, mode=UpdateMode.MERGE)
                            persisted_to_hub = True
                            persisted_format = 'plain'
                        else:
                            import base64
                            import gzip
                            gz = gzip.compress(snapshot_bytes, compresslevel=9)
                            b64 = base64.b64encode(gz).decode('ascii')
                            if len(b64.encode('ascii')) <= 60_000:
                                existing['template_structured_resume'] = ''
                                existing['template_structured_resume_gz_b64'] = b64

                                existing[per_plain_prop] = ''
                                existing[per_gz_prop] = b64
                                table_client.update_entity(existing, mode=UpdateMode.MERGE)
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

        return jsonify({
            "success": True,
            "persisted_to_hub": bool(persisted_to_hub),
            "persist_reason": persist_reason,
            "persisted_format": persisted_format,
        })
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
    step = "start"
    try:
        t0 = time.time()
        def _t() -> int:
            try:
                return int((time.time() - t0) * 1000)
            except Exception:
                return 0

        logger.info("template_pdf start template=%s t=%sms", str(template_id or ''), _t())
        step = "paid_check"
        paid_flag = bool(is_paid_user(current_user))
        if _stripe_enabled():
            try:
                paid_flag = bool(_refresh_paid_status_from_stripe_for_user(current_user))
            except Exception:
                paid_flag = paid_flag
        if not paid_flag:
            return "Paid plan required.", 402

        template_data = session.get('template_data')
        if not template_data:
            return "Template data not found in session.", 404
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
                    logger.warning("template_pdf deps_missing missing=%s", ",".join(missing))
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
        target_url = base_url + url_for('imported_resume_builder')
        logger.info("template_pdf navigate url=%s t=%sms", target_url, _t())

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
            font_scale = _clamp(request.args.get('fontScale', 1.0), 0.6, 1.6)
            paragraph_gap_px = _clamp(request.args.get('paragraphGapPx', 0.0), -80, 300)
            spacing_scale = _clamp(request.args.get('spacingScale', 1.0), 0.0, 6.0)
        except Exception:
            font_scale, paragraph_gap_px, spacing_scale = 1.0, 0.0, 1.0
        logger.info(
            "template_pdf style fontScale=%s paragraphGapPx=%s spacingScale=%s t=%sms",
            font_scale,
            paragraph_gap_px,
            spacing_scale,
            _t(),
        )

        cookies = []
        cookie_base = base_url + "/"
        for name, value in (request.cookies or {}).items():
            try:
                cookies.append({"name": name, "value": value, "url": cookie_base})
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
                    browsers_path = (os.getenv("PLAYWRIGHT_BROWSERS_PATH") or "/home/site/wwwroot/ms-playwright").strip()
                    candidates = []
                    candidates += _glob.glob(os.path.join(browsers_path, "chromium-*", "chrome-linux", "chrome"))
                    candidates += _glob.glob(os.path.join(browsers_path, "chromium-*", "chrome-linux", "chrome-wrapper"))
                    candidates += _glob.glob(os.path.join(browsers_path, "chromium-*", "**", "chrome"), recursive=True)
                    candidates = sorted({c for c in candidates if c})
                    if candidates:
                        chromium_executable_path = candidates[0]
                except Exception:
                    chromium_executable_path = None

            if _ON_AZURE and chromium_executable_path:
                launch_kwargs["executable_path"] = chromium_executable_path
                logger.info("template_pdf chromium_launch exec=%s t=%sms", chromium_executable_path, _t())
            else:
                logger.info("template_pdf chromium_launch exec=%s t=%sms", "(default)", _t())

            # Launch fresh Chromium per request. Reuse caused "Cannot switch to a different thread"
            # when Gunicorn's other threads handled subsequent PDF requests.
            from playwright.sync_api import sync_playwright
            pw = sync_playwright().start()
            browser = pw.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                viewport={"width": 816, "height": 1056},
                device_scale_factor=1,
            )
            if cookies:
                context.add_cookies(cookies)

            page = context.new_page()
            # Embed fonts as base64 in CSS so Chromium never waits for a fetch. Matches localhost exactly.
            _static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
            _fonts_dir = os.path.join(_static_dir, "fonts")
            import base64
            _font_b64_cache = {}
            for name in ("inter-latin-400-normal.woff2", "inter-latin-500-normal.woff2",
                         "inter-latin-600-normal.woff2", "inter-latin-700-normal.woff2"):
                p = os.path.join(_fonts_dir, "inter", name)
                if os.path.isfile(p):
                    with open(p, "rb") as f:
                        _font_b64_cache[name] = base64.b64encode(f.read()).decode("ascii")

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
                                css_path = os.path.join(_fonts_dir, "inter.css")
                                if os.path.isfile(css_path):
                                    with open(css_path, "r", encoding="utf-8") as f:
                                        css = f.read()
                                    for fname, b64 in _font_b64_cache.items():
                                        css = css.replace(
                                            f"url(/static/fonts/inter/{fname})",
                                            f"url(data:font/woff2;base64,{b64})",
                                        )
                                    route.fulfill(status=200, body=css.encode("utf-8"), content_type="text/css")
                                    return
                            elif os.path.isfile(local_path):
                                with open(local_path, "rb") as f:
                                    body = f.read()
                                mime = "font/woff2" if local_path.endswith(".woff2") else "text/css"
                                route.fulfill(status=200, body=body, content_type=mime)
                                return
                    except Exception as e:
                        logger.warning("template_pdf font_fulfill url=%s err=%s", req.url, e)
                route.continue_()
            try:
                page.route("**/*", _handle_route)
            except Exception:
                pass
            step = "page_goto"
            page.goto(target_url, wait_until="domcontentloaded", timeout=90000)
            logger.info("template_pdf domcontentloaded t=%sms", _t())

            # Prefer the dedicated export root, but be resilient to cached/older frontend builds.
            step = "wait_export_root"
            try:
                page.wait_for_selector("#templatePrintContent", timeout=8000)
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
                      rootClone.style.position = 'relative';
                      rootClone.style.left = '0';
                      rootClone.style.top = '0';

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
                        mount.style.background = '#fff';
                        mount.style.position = 'relative';
                        mount.style.left = '0';
                        mount.style.top = '0';
                      } catch (e) {
                        // ignore
                      }

                      const existing = document.getElementById('__pdfOnlyCss');
                      if (existing) existing.remove();
                      const style = document.createElement('style');
                      style.id = '__pdfOnlyCss';
                                            style.textContent = `
                                                /* Page margins are controlled by Playwright page.pdf(...) to ensure consistency in Chromium PDF output. */
                                                @page { size: letter; }
                        html, body { width: 816px; margin: 0 !important; padding: 0 !important; background: #fff !important; min-height: 0 !important; }
                        * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
                        body > *:not(#__pdfMount) { display: none !important; }
                                                #__pdfMount { display: block !important; position: relative !important; left: 0 !important; top: 0 !important; }
                                                /* Many templates have an outer wrapper with top padding/margin (e.g., Tailwind p-8).
                                                     That padding only applies at the start of the document, making page 1 look like it
                                                     has a larger top margin than page 2+. Strip only the TOP spacing from the wrapper
                                                     and rely on the PDF page margin for consistent per-page top whitespace. */
                                                #__pdfMount > *:first-child {
                                                    page-break-before: avoid !important;
                                                    margin-top: 0 !important;
                                                    padding-top: 0 !important;
                                                }
                                                /* Some templates apply their outer padding on a nested wrapper instead of the exported root.
                                                   Strip top spacing on the first nested wrapper(s) as well so page 1 matches page 2+. */
                                                #__pdfMount > *:first-child > :first-of-type {
                                                    margin-top: 0 !important;
                                                    padding-top: 0 !important;
                                                }
                                                #__pdfMount > *:first-child > :first-of-type > :first-of-type {
                                                    margin-top: 0 !important;
                                                    padding-top: 0 !important;
                                                }
                                                #__pdfMount > *:first-child > :first-of-type > :first-of-type > :first-of-type {
                                                    margin-top: 0 !important;
                                                    padding-top: 0 !important;
                                                }
                                                                                                                                /* Creative2: keep the left edge flush so the yellow accent bar touches the page edge. */
                                                                                                                                #__pdfMount [data-template="creative2"].creative2-template { margin: 0 !important; }
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
                      document.head.appendChild(style);
                    }""",
                {"fontScale": font_scale, "paragraphGapPx": paragraph_gap_px, "spacingScale": spacing_scale},
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
            _pdf_debug = False
            try:
                _pdf_debug = str(request.args.get('debug') or '').strip().lower() in ('1', 'true', 'yes')
            except Exception:
                _pdf_debug = False
            try:
                _pdf_debug = _pdf_debug or (str(os.getenv('PDF_DEBUG') or '').strip().lower() in ('1', 'true', 'yes'))
            except Exception:
                _pdf_debug = _pdf_debug

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
                        logger.info("template_pdf creative2_debug_dump_failed err=%r t=%sms", _e, _t())

                    try:
                        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_store')
                        os.makedirs(temp_dir, exist_ok=True)

                        dbg_path = os.path.join(temp_dir, 'creative2-debug.json')
                        try:
                            _dbg_payload = _json.dumps(dbg, ensure_ascii=False, indent=2, default=str)
                        except Exception as _e:
                            _dbg_payload = _json.dumps(
                                {
                                    "error": repr(_e),
                                    "dbg_type": str(type(dbg)),
                                    "dbg_keys": list(dbg.keys()) if isinstance(dbg, dict) else None,
                                },
                                ensure_ascii=False,
                                indent=2,
                            )
                        with open(dbg_path, 'w', encoding='utf-8') as f:
                            f.write(_dbg_payload)
                        logger.info("template_pdf creative2_debug_file=%s t=%sms", dbg_path, _t())

                        try:
                            import time as _time
                            _shot_ts = int(_time.time())
                        except Exception:
                            _shot_ts = 0

                        # If the previous PNG is open in an image viewer, overwriting can fail on Windows.
                        # Always write a timestamped screenshot, and also try to update the stable filename.
                        shot_path = os.path.join(temp_dir, f'creative2-html-debug-{_shot_ts}.png' if _shot_ts else 'creative2-html-debug-new.png')
                        page.screenshot(path=shot_path, full_page=True)
                        try:
                            with open(os.path.join(temp_dir, 'creative2-html-debug-latest.txt'), 'w', encoding='utf-8') as _f:
                                _f.write(os.path.basename(shot_path))
                        except Exception:
                            pass
                        try:
                            stable_path = os.path.join(temp_dir, 'creative2-html-debug.png')
                            page.screenshot(path=stable_path, full_page=True)
                        except Exception:
                            stable_path = None
                        logger.info(
                            "template_pdf creative2_screenshot=%s stable=%s t=%sms",
                            shot_path,
                            stable_path or '',
                            _t(),
                        )
                    except Exception as _e:
                        logger.info("template_pdf creative2_debug_artifacts_failed err=%r t=%sms", _e, _t())
                except Exception:
                    pass

            step = "page_pdf"
            _pdf_margin_top = "0.32in"
            _pdf_margin_bottom = "0.32in"
            _pdf_margin_left = "0in"
            _pdf_margin_right = "0in"
            pdf_bytes = page.pdf(
                format="Letter",
                print_background=True,
                # Small top/bottom page margins for all templates.
                # Use inch units for maximum compatibility with Chromium's PDF output.
                margin={
                    "top": _pdf_margin_top,
                    "right": _pdf_margin_right,
                    "bottom": _pdf_margin_bottom,
                    "left": _pdf_margin_left,
                },
            )
            logger.info("template_pdf pdf_ready bytes=%s t=%sms", len(pdf_bytes or b""), _t())
        finally:
            try:
                if context:
                    context.close()
            except Exception:
                pass
            try:
                if browser:
                    browser.close()
            except Exception:
                pass
            try:
                if pw:
                    pw.stop()
            except Exception:
                pass

        filename = f"resume-{canonical}.pdf"
        logger.info("template_pdf done filename=%s t=%sms", filename, _t())
        resp = send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
        # Prevent stale cached PDFs after template/CSS changes.
        try:
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
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
                logger.info("template_pdf header_set_failed key=%s err=%r", "X-Resumatic-Build", _e)
            except Exception:
                pass
        try:
            resp.headers["X-Resumatic-Template-Requested"] = str(template_id or "")
        except Exception as _e:
            try:
                logger.info("template_pdf header_set_failed key=%s err=%r", "X-Resumatic-Template-Requested", _e)
            except Exception:
                pass
        try:
            resp.headers["X-Resumatic-Template-Canonical"] = str(canonical or "")
        except Exception as _e:
            try:
                logger.info("template_pdf header_set_failed key=%s err=%r", "X-Resumatic-Template-Canonical", _e)
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
        return resp
    except Exception as e:
        logger.exception("template_pdf failed template=%s step=%s", str(template_id or ''), str(step or ''))
        msg = f"{type(e).__name__}: {str(e) or 'PDF generation failed.'} (step={step})"
        # Missing libs or Chromium launch failure: return 503 so user can retry after startup finishes.
        if any(x in msg for x in (".so", "libglib", "libnss", "libgtk", "libX11", "shared library", "Executable doesn't exist")):
            return (
                "PDF dependencies are still installing on the server. "
                "Please wait 2–3 minutes after deploy and try again.",
                503,
            )
        if "Executable doesn't exist" in msg or "playwright install" in msg:
            msg = msg + " (Try: python -m playwright install chromium)"
        return msg, 500


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

        allowed_fields = {'summary', 'experience_description', 'job_description', 'custom_section', 'project_description'}
        if field not in allowed_fields:
            return jsonify({
                "success": False,
                "error": f"Invalid field: {field_raw.strip() or '(empty)'}",
            }), 400

        text = text.strip()
        if not text:
            return jsonify({"success": False, "error": "Missing text"}), 400
        if len(text) > 12000:
            return jsonify({"success": False, "error": "Text too long"}), 400

        api_key = (os.getenv('OPENAI_API_KEY') or '').strip()
        api_key = api_key.strip('"').strip("'").strip()
        if not api_key:
            return jsonify({"success": False, "error": "OPENAI_API_KEY not configured"}), 500

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
                + (f"JOB DESCRIPTION (context only):\n{jd}\n\n" if jd else "")
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
            heading = str(meta.get('heading') or meta.get('section') or '').strip()
            sys_msg = (
                "You are a resume writing assistant. Rewrite content for a resume section to be concise, ATS-friendly, and truthful. "
                "Do NOT invent facts, metrics, titles, dates, awards, credentials, or organizations. Preserve the user's meaning. "
                "Return ONLY the rewritten content (no commentary)."
            )
            user_msg = (
                "Rewrite the following resume section content to be more professional and scannable. "
                "Prefer bullets where appropriate. Keep it consistent with a resume tone.\n\n"
                + (f"SECTION TITLE (context): {heading}\n\n" if heading else "")
                + f"ORIGINAL CONTENT:\n{text}"
            )
        elif field == 'project_description':
            title = str(meta.get('title') or '').strip()
            tech = str(meta.get('technologies') or meta.get('tech') or '').strip()
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
            title = str(meta.get('title') or meta.get('role') or '').strip()
            company = str(meta.get('company') or meta.get('organization') or '').strip()
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
            max_tokens=700 if field in {'job_description', 'custom_section'} else (600 if field == 'project_description' else 500),
        )

        out = (resp.choices[0].message.content or '').strip()
        if not out:
            return jsonify({"success": False, "error": "Empty AI response"}), 502

        # Safety: keep responses bounded.
        if len(out) > 20000:
            out = out[:20000]
        return jsonify({"success": True, "text": out})

    except Exception as e:
        try:
            logger.error(f"AI resume edit failed: {type(e).__name__}: {str(e)}")
        except Exception:
            pass
        return jsonify({"success": False, "error": "AI edit failed"}), 500

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
    return render_template("about.html", year=current_year, user=current_user if current_user.is_authenticated else None)

@app.route("/blog")
def blog():
    current_year = datetime.now().year
    return render_template("blog.html", year=current_year, user=current_user if current_user.is_authenticated else None)

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
            return redirect(url_for("blog_post", post=canonical_slug), code=301)
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
                    existing_emails = [line.strip().lower() for line in f.readlines()]
            except FileNotFoundError:
                pass
            
            if email.lower() in existing_emails:
                flash("You're already subscribed to our newsletter!", "info")
            else:
                with open("subscribers.csv", "a") as f:
                    f.write(email + "\n")
                flash("Thank you for subscribing! You'll receive our latest resume tips and career advice.", "success")
            
            # Smart redirect based on referrer
            if "/blog" in referrer:
                return redirect(url_for("blog"))
            elif "/thank_you" in referrer:
                return redirect(url_for("thank_you"))
            else:
                return redirect(url_for("thank_you"))
        except Exception as e:
            flash("Something went wrong. Please try again later.", "danger")
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
            source_info = session.get('traffic_source', {'type': 'unknown'})
            app.logger.info("Facebook tracking call - visit already tracked, skipping duplicate")
        else:
            # Track the visit/conversion (first time)
            source_info = analytics.track_visit(request)
            session['visit_tracked'] = True
            session['traffic_source'] = source_info
            app.logger.info(f"Facebook tracking - new visit tracked: {source_info.get('type', 'unknown')}")
        
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
            app.logger.info("Visit already tracked in session, skipping duplicate API tracking")
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
            return {"status": "ignored", "message": "Missing browser headers"}, 200
        
        # Track the legitimate visit using existing analytics
        source_info = analytics.track_visit(request)
        session['visit_tracked'] = True
        session['traffic_source'] = source_info
        
        # Log the visit for debugging
        app.logger.info(f"API visit tracked: {data.get('page', 'unknown')} from {request.remote_addr} - {source_info.get('type', 'unknown')}")
        
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
                "facebook_ad_conversions": summary.get('facebook_ad_conversions', 0),
                "last_updated": summary.get('last_updated', 'unknown')
            }
        }, 200
        
    except Exception as e:
        logger.error(f"Error retrieving visit count: {str(e)}")
        return {
            "status": "error", 
            "message": "Failed to retrieve visit count"
        }, 500

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

        # Registered Users are available on /admin/registered_users (Azure table: Users)
        # Load recent feedback submissions from CSV (if present)
        feedback_rows = []
        try:
            import csv
            feedback_path = 'download_feedback.csv'
            if os.path.exists(feedback_path):
                with open(feedback_path, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        feedback_rows.append({
                            'timestamp_iso': row.get('timestamp_iso', ''),
                            'user_id': row.get('user_id', ''),
                            'user_email': row.get('user_email', ''),
                            'rating': row.get('rating', ''),
                            'comment': row.get('comment', ''),
                            'comparison': row.get('comparison', ''),
                        })
                # Keep only the last 100, newest first
                feedback_rows = feedback_rows[-100:][::-1]
        except Exception as e:
            app.logger.warning(f"Failed to read download_feedback.csv: {str(e)}")
        
        # Debug logging to help troubleshoot
        app.logger.info(f"Analytics data structure: {type(analytics_data)}")
        if isinstance(analytics_data, dict) and 'summary' in analytics_data:
            app.logger.info(f"Summary data: {analytics_data['summary']}")
        else:
            app.logger.warning(f"Unexpected analytics data structure: {analytics_data}")
        
        return render_template("admin_stats.html", 
                             analytics=analytics_data, 
                             user=current_user,
                             feedback_rows=feedback_rows)
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
            buf = StringIO("timestamp_iso,user_id,user_email,rating,comment,comparison\n")
            data = buf.getvalue().encode('utf-8')
            bio = BytesIO(data)
            bio.seek(0)
            return send_file(bio, mimetype='text/csv', as_attachment=True, download_name='download_feedback.csv')
        return send_file(path, mimetype='text/csv', as_attachment=True, download_name='download_feedback.csv')
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

    file_present = False
    try:
        file_present = os.path.exists(LOGIN_AUDIT_FILE)
    except Exception:
        file_present = False

    source_label = None
    store = None
    sessions_list: list[dict] = []

    # Prefer Azure Table Storage when available.
    if _azure_login_audit_enabled():
        try:
            rows = _azure_login_audit_list(limit=1000)
            # Normalize Azure entities into the same shape used by templates.
            for e in rows:
                if not isinstance(e, dict):
                    continue
                sessions_list.append({
                    'audit_id': str(e.get('audit_id') or ''),
                    'user_id': str(e.get('user_id') or ''),
                    'email': str(e.get('email') or ''),
                    'login_at': str(e.get('login_at') or ''),
                    'last_activity_at': str(e.get('last_activity_at') or ''),
                    'logout_at': (str(e.get('logout_at') or '') or None),
                    'duration_seconds': e.get('duration_seconds', None),
                    'login_method': str(e.get('login_method') or '') or None,
                })
            source_label = f"Azure Table: {AZURE_LOGIN_AUDIT_TABLE}"
            store = {'version': _LOGIN_AUDIT_VERSION}
        except Exception:
            sessions_list = []
            source_label = None
            store = None

    # Fallback: JSON file store.
    if not sessions_list:
        store = _load_login_audit_store()
        raw_sessions = store.get('sessions') if isinstance(store, dict) else {}
        if not isinstance(raw_sessions, dict):
            raw_sessions = {}
        sessions_list = [v for v in raw_sessions.values() if isinstance(v, dict)]
        if file_present:
            source_label = f"login_audit.json" + (f" (v{store.get('version')})" if isinstance(store, dict) and store.get('version') else "")
        else:
            source_label = "login_audit.json (not created yet)"

    sessions_list.sort(
        key=lambda r: (_parse_iso_datetime(r.get('login_at')) or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )

    # Pre-format times for display (keep original ISO values intact).
    formatted_sessions: list[dict] = []
    for rec in sessions_list:
        out = dict(rec)
        out['login_time_pst'] = _format_datetime_pacific(rec.get('login_at'))
        out['last_activity_time_pst'] = _format_datetime_pacific(rec.get('last_activity_at') or rec.get('login_at'))
        out['logout_time_pst'] = _format_datetime_pacific(rec.get('logout_at'))

        # If there is no explicit logout, estimate when the idle timeout would have logged them out.
        try:
            idle_seconds, _ = _auth_timeout_seconds()
            if not out.get('logout_at') and idle_seconds:
                last_dt = _parse_iso_datetime(rec.get('last_activity_at') or rec.get('login_at'))
                if last_dt is not None:
                    est_dt = last_dt + timedelta(seconds=int(idle_seconds))
                    out['estimated_logout_at'] = est_dt.isoformat()
                    out['estimated_logout_time_pst'] = _format_datetime_pacific(out.get('estimated_logout_at'))
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
        store_version=(store.get('version') if isinstance(store, dict) else None),
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
            with open(CANCELLATION_FEEDBACK_FILE, "r", encoding="utf-8") as f:
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
        r["reason_label"] = reason_labels.get(r.get("reason", ""), r.get("reason", "") or "—")
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
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'resumatic',
        'build': _BUILD_ID,
        'pid': os.getpid(),
    }), 200


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

        log_path = (os.getenv("PLAYWRIGHT_INSTALL_LOG") or "/home/site/wwwroot/playwright-install.log").strip()
        max_bytes = 80_000
        if not os.path.exists(log_path):
            return jsonify({
                "ok": False,
                "log_path": log_path,
                "exists": False,
            }), 200

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
            return jsonify({
                "ok": False,
                "log_path": log_path,
                "exists": True,
                "error": f"{type(e).__name__}: {str(e)}",
            }), 200

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
            browsers_path = (os.getenv("PLAYWRIGHT_BROWSERS_PATH") or "/home/site/wwwroot/ms-playwright").strip()
            browser_fs["browsers_path"] = browsers_path
            browser_fs["entries"] = sorted(
                [p.replace(browsers_path + "/", "") for p in _glob.glob(os.path.join(browsers_path, "*"))]
            )[:200]
        except Exception as e:
            browser_fs["error"] = f"{type(e).__name__}: {str(e)}"

        # If ldd is available, show missing dynamic deps for headless-shell/chromium binaries.
        ldd = {}
        try:
            import subprocess
            import shlex
            import glob as _glob

            browsers_path = (os.getenv("PLAYWRIGHT_BROWSERS_PATH") or "/home/site/wwwroot/ms-playwright").strip()
            headless_shell = None
            hs_candidates = sorted(_glob.glob(os.path.join(browsers_path, "chromium_headless_shell-*", "**", "chrome-headless-shell"), recursive=True))
            if hs_candidates:
                headless_shell = hs_candidates[0]
            chromium_bin = None
            c_candidates = []
            c_candidates += _glob.glob(os.path.join(browsers_path, "chromium-*", "chrome-linux", "chrome"))
            c_candidates += _glob.glob(os.path.join(browsers_path, "chromium-*", "chrome-linux", "chrome-wrapper"))
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
                not_found = [ln for ln in out.splitlines() if "not found" in ln]
                return {
                    "path": path,
                    "exit_code": proc.returncode,
                    "not_found": not_found[:50],
                }

            ldd["headless_shell"] = _ldd(headless_shell)
            ldd["chromium"] = _ldd(chromium_bin)
        except Exception as e:
            ldd["error"] = f"{type(e).__name__}: {str(e)}"

        return jsonify({
            "ok": True,
            "log_path": log_path,
            "exists": True,
            "size": size,
            "tail": data.decode("utf-8", errors="replace"),
            "deps": deps,
            "missing_libs": missing_libs,
            "browser_fs": browser_fs,
            "ldd": ldd,
            "playwright_browsers_path": os.getenv("PLAYWRIGHT_BROWSERS_PATH"),
        }), 200
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
            pages.append(f"""
                <url>
                    <loc>{url}</loc>
                    <lastmod>{lastmod}</lastmod>
                    <changefreq>{config['changefreq']}</changefreq>
                    <priority>{config['priority']}</priority>
                </url>""")
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
            url = url_for('blog_post', post=post, _external=True, _scheme='https')
            pages.append(f"""
                <url>
                    <loc>{url}</loc>
                    <lastmod>{lastmod}</lastmod>
                    <changefreq>monthly</changefreq>
                    <priority>0.8</priority>
                </url>""")
        except Exception:
            continue

    sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        {''.join(pages)}
    </urlset>"""

    response = Response(sitemap_xml, mimetype='application/xml')
    response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache for 24 hours
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
                writer.writerow(['timestamp_iso', 'user_id', 'user_email', 'rating', 'comment', 'comparison'])
            writer.writerow([
                datetime.now(timezone.utc).isoformat(),
                getattr(current_user, 'id', ''),
                getattr(current_user, 'email', ''),
                rating,
                comment[:500],
                comparison
            ])
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logger.error(f"feedback_download_api error: {str(e)}")
        return jsonify({'status': 'error'}), 500

# Azure Table Storage setup
AZURE_TABLE_NAME = os.getenv('AZURE_TABLE_NAME', 'ResumeRevisions')
AZURE_STORAGE_ACCOUNT = os.getenv('AZURE_STORAGE_ACCOUNT')

def get_table_client(table_name: str = None, create_if_missing: bool = True):
    connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    if connection_string:
        service = TableServiceClient.from_connection_string(conn_str=connection_string)
    else:
        credential = DefaultAzureCredential()
        service = TableServiceClient(endpoint=f"https://{AZURE_STORAGE_ACCOUNT}.table.core.windows.net", credential=credential)
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
    return get_table_client(AZURE_USERS_TABLE, create_if_missing=create_if_missing)

def _collect_registered_users_from_azure_users_table(table_override: str = None):
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
            table_client = get_table_client(table_name, create_if_missing=False)
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
            revision_client = get_table_client(revision_table_name, create_if_missing=False)
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
                    if prev is None or (ts and prev.get('Timestamp') and ts > prev.get('Timestamp')):
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
                merged['revisions'] = sum(1 for r in user_latest_revision if r == uid)
                results.append(merged)

            # Build all_keys from the union of all keys across all rows
            all_keys = set()
            for row in results:
                all_keys.update(row.keys())

            if results:
                results.sort(key=lambda r: (r.get('created_at') or ''), reverse=True)
                return results, table_name, sorted(all_keys)
        except Exception as e:
            last_error = e
            continue

    if last_error:
        try:
            logger.warning(f"Failed to read Azure users table profiles: {str(last_error)}")
        except Exception:
            pass
    return [], (table_names[0] if table_names else (os.getenv('AZURE_USERS_TABLE') or 'Users'))

FREE_REVISION_LIMIT = int(os.getenv('FREE_REVISION_LIMIT', '2'))
PAID_EMAILS = set([e.strip().lower() for e in (os.getenv('PAID_EMAILS', '') or '').split(',') if e.strip()])

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
        return table_client.get_entity(partition_key=str(user_id), row_key='profile')
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
        if bool(prof.get('is_paid', False)):
            paid_until = _parse_iso_dt(str(prof.get('paid_until') or '').strip())
            if paid_until is None:
                return True
            return paid_until >= datetime.now(timezone.utc)
        plan_status = str(prof.get('plan_status') or '').strip().lower()
        if plan_status in ('paid', 'active', 'trial', 'monthly', 'annual'):
            paid_until = _parse_iso_dt(str(prof.get('paid_until') or '').strip())
            if paid_until is None:
                return True
            return paid_until >= datetime.now(timezone.utc)
        return False
    except Exception:
        return False

def is_paid_user(user_obj: Optional['User']) -> bool:
    try:
        if not user_obj or not getattr(user_obj, 'is_authenticated', False):
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


def _refresh_paid_status_from_stripe_for_user(user_obj: Optional['User']) -> bool:
    """Best-effort: infer paid status from Stripe by email/customer and persist to Azure profile.

    This is a safety net for cases where Stripe webhooks are delayed/misconfigured, or when
    Payment Links complete but the webhook hasn't updated Azure yet.
    """
    try:
        if not user_obj or not getattr(user_obj, 'is_authenticated', False):
            return False
        if not _stripe_enabled():
            return False

        user_id = str(getattr(user_obj, 'id', '') or '').strip()
        email = str(getattr(user_obj, 'email', '') or '').strip()
        if not user_id or not email:
            return False

        prof = get_user_profile_azure(user_id) or {}
        local_paid_fallback = _profile_indicates_paid(prof)
        customer_id = str(prof.get('stripe_customer_id') or '').strip()
        subscription_id = str(prof.get('stripe_subscription_id') or '').strip()

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
            return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

        # Find best subscription for this customer (active > trialing > others).
        best_sub_id = subscription_id
        best_status = ''
        paid_until = ''
        plan_status_guess = ''
        try:
            stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
            if best_sub_id:
                sub = stripe.Subscription.retrieve(best_sub_id)
                best_status = str(getattr(sub, 'status', '') or '').strip().lower()
                cpe = getattr(sub, 'current_period_end', None)
                if cpe:
                    paid_until = datetime.fromtimestamp(int(cpe), tz=timezone.utc).isoformat()
            elif customer_id:
                subs = stripe.Subscription.list(customer=customer_id, status='all', limit=10)
                sdata = list(getattr(subs, 'data', []) or [])

                def _rank(sub):
                    status = str(getattr(sub, 'status', '') or '').strip().lower()
                    cpe = int(getattr(sub, 'current_period_end', 0) or 0)
                    sr = 0
                    if status == 'active':
                        sr = 3
                    elif status == 'trialing':
                        sr = 2
                    elif status in ('past_due', 'unpaid'):
                        sr = 1
                    return (sr, cpe)

                if sdata:
                    best = sorted(sdata, key=_rank, reverse=True)[0]
                    best_sub_id = str(getattr(best, 'id', '') or '').strip()
                    best_status = str(getattr(best, 'status', '') or '').strip().lower()
                    cpe = getattr(best, 'current_period_end', None)
                    if cpe:
                        paid_until = datetime.fromtimestamp(int(cpe), tz=timezone.utc).isoformat()
        except Exception:
            # If Stripe is unreachable/misconfigured, don't crash gating.
            return bool(local_paid_fallback)

        paid_flag = best_status in ('active', 'trialing')

        # Fallback for Payment Links / one-time checkout sessions:
        # If there is no subscription at all, we can grant temporary access based on a recent paid
        # checkout session while waiting for profile/webhook sync. Do not do this when Stripe
        # already reports a subscription state (e.g., canceled), or we can incorrectly re-grant access.
        has_subscription_state = bool((best_sub_id or '').strip() or (best_status or '').strip())
        if (not paid_flag) and customer_id and (not has_subscription_state):
            try:
                stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
                sessions = stripe.checkout.Session.list(customer=customer_id, limit=10)
                sdata = list(getattr(sessions, 'data', []) or [])
                # Prefer the most recent *paid* session.
                sdata = sorted(sdata, key=lambda s: int(getattr(s, 'created', 0) or 0), reverse=True)
                now_ts = int(time.time())
                recovery_window_secs = int(os.getenv('STRIPE_CHECKOUT_RECOVERY_WINDOW_SECS', '21600') or '21600')
                if recovery_window_secs < 300:
                    recovery_window_secs = 300
                for s in sdata:
                    status = str(getattr(s, 'status', '') or '').strip().lower()
                    pay_status = str(getattr(s, 'payment_status', '') or '').strip().lower()
                    mode = str(getattr(s, 'mode', '') or '').strip().lower()
                    created_ts = int(getattr(s, 'created', 0) or 0)
                    # One-time Checkout fallback is only for webhook lag shortly after purchase.
                    # Old paid sessions should not grant ongoing access after cancellation.
                    if created_ts <= 0 or (now_ts - created_ts) > recovery_window_secs:
                        continue
                    if status == 'complete' and pay_status in ('paid', 'no_payment_required'):
                        meta = getattr(s, 'metadata', None) or {}
                        plan_id = str(meta.get('plan_id') or '').strip()
                        # If metadata is missing, still treat as paid (default ~monthly duration).
                        plan_status_guess = plan_id or 'paid'
                        paid_until = paid_until or _paid_until_from_plan_id(plan_id or 'monthly_10_95')
                        paid_flag = True
                        # If this session actually created a subscription, store it too.
                        try:
                            sid = str(getattr(s, 'subscription', '') or '').strip()
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
            if customer_id:
                entity["stripe_customer_id"] = str(customer_id)
            if best_sub_id:
                entity["stripe_subscription_id"] = str(best_sub_id)
            entity["is_paid"] = bool(paid_flag)
            if paid_flag and paid_until:
                entity["paid_until"] = paid_until
            elif not paid_flag:
                entity["paid_until"] = ""
            if paid_flag:
                entity["plan_status"] = plan_status_guess or best_status or "active"
            else:
                entity["plan_status"] = best_status or "free"
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
        provider = "google" if str(user_obj.id).isdigit() else ("facebook" if str(user_obj.id).startswith("facebook_") else "other")
        entity = {
            'PartitionKey': str(user_obj.id),
            'RowKey': 'profile',
            'name': user_obj.name or '',
            'email': user_obj.email or '',
            'created_at': user_obj.created_at,
            'is_admin': bool(getattr(user_obj, 'is_admin', False)),
            'provider': provider,
        }
        table_client.upsert_entity(entity)
    except Exception as e:
        logger.error(f"Failed to upsert user profile to Azure: {str(e)}")

# Save a revision to Azure Table Storage
def save_resume_revision(user_id, revision_id, resume_content, feedback=None, original_resume=None, notes=None, job_description=None):
    from datetime import datetime, timezone
    # Enforce free tier cap (2 revisions) for non-paid users.
    # Note: We enforce here as a safety net; primary gating happens earlier in /results.
    if not is_paid_user_id(user_id):
        try:
            existing = get_user_revisions(user_id)
            if len(existing) >= FREE_REVISION_LIMIT:
                raise FreeTierLimitReached("Free tier revision limit reached")
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
        cleaned.append({
            'company': str(item.get('company', '') or '')[:120],
            'role': str(item.get('role', '') or '')[:120],
            'date_applied': str(item.get('date_applied', '') or '')[:32],
            'status': str(item.get('status', '') or '')[:40],
            'link': str(item.get('link', '') or '')[:500],
        })
    return cleaned

# Get all revisions for a user
def get_user_revisions(user_id):
    revisions = []
    try:
        table_client = get_table_client()
        try:
            # Materialize to isolate downstream template rendering from paging/iteration errors.
            entities = list(table_client.query_entities(f"PartitionKey eq '{user_id}'"))
        except Exception:
            try:
                logger.exception("get_user_revisions query_entities failed (user_id=%s)", str(user_id))
            except Exception:
                pass
            return []

        for e in entities:
            try:
                timestamp_str = e.get('timestamp')
                if not timestamp_str:
                    timestamp_str = str(e.get('Timestamp')) if e.get('Timestamp') else None
                try:
                    timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else None
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
                    raw_saved = str(e.get('template_saved_templates', '') or '').strip()
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
                    plain_prop, gz_prop, at_prop = _template_snapshot_prop_names(tid)
                    if str(e.get(plain_prop, '') or '').strip() or str(e.get(gz_prop, '') or '').strip():
                        template_versions.append({
                            'template_id': tid,
                            'template_display_name': _format_template_display_name(tid),
                            'template_saved_at': str(e.get(at_prop, '') or '').strip(),
                        })
                        seen.add(tid)

                # Backward compatibility: legacy single-snapshot field.
                legacy_has = bool(
                    str(_entity_get_ci(e, 'template_structured_resume', '') or '').strip()
                    or str(_entity_get_ci(e, 'template_structured_resume_gz_b64', '') or '').strip()
                    or str(_entity_get_ci(e, 'templateStructuredResume', '') or '').strip()
                    or str(_entity_get_ci(e, 'templateStructuredResumeGzB64', '') or '').strip()
                )
                legacy_tid = _canonical_template_id(str(_entity_get_ci(e, 'template_id', '') or '').strip() or 'professional')
                if legacy_has and legacy_tid not in seen:
                    template_versions.append({
                        'template_id': legacy_tid,
                        'template_display_name': _format_template_display_name(legacy_tid),
                        'template_saved_at': str(_entity_get_ci(e, 'template_saved_at', '') or '').strip(),
                    })

                revision_name = str(
                    _entity_get_ci(e, 'revision_name', '')
                    or _entity_get_ci(e, 'resume_name', '')
                    or _entity_get_ci(e, 'resume_title', '')
                    or ''
                ).strip()

                revisions.append({
                    'revision_id': e.get('RowKey') or e.get('rowKey') or '',
                    'timestamp': timestamp,
                    'resume_content': e.get('resume_content', ''),
                    'feedback': feedback,
                    'original_resume': e.get('original_resume', ''),
                    'revision_name': revision_name,
                    'notes': e.get('notes', ''),
                    'job_description': e.get('job_description', ''),
                    'applications': _parse_applications(e.get('applications', '')),
                    # Optional: persisted template edit-mode snapshot
                    'template_id': str(e.get('template_id', '') or '').strip(),
                    'template_saved_at': str(e.get('template_saved_at', '') or '').strip(),
                    'has_template_snapshot': bool(template_versions),
                    'template_versions': template_versions,
                })
            except Exception:
                try:
                    rk = str(e.get('RowKey') or e.get('rowKey') or '')
                    logger.exception("get_user_revisions failed parsing entity (user_id=%s row_key=%s)", str(user_id), rk)
                except Exception:
                    pass
                continue
    except Exception:
        try:
            logger.exception("get_user_revisions failed (user_id=%s)", str(user_id))
        except Exception:
            pass
        return []

    utc_min = datetime.min.replace(tzinfo=timezone.utc)
    try:
        revisions.sort(key=lambda x: x['timestamp'] or utc_min, reverse=True)
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
        return redirect(url_for('verify_email', email=getattr(current_user, 'email', '')))
    revisions = []
    try:
        revisions = get_user_revisions(current_user.id) or []
    except Exception:
        revisions = []
    if revisions == []:
        # Best-effort hint; underlying error is logged in get_user_revisions.
        try:
            if not os.getenv('AZURE_STORAGE_CONNECTION_STRING') and not os.getenv('AZURE_STORAGE_ACCOUNT'):
                flash('Resume history is temporarily unavailable (storage not configured).', 'warning')
        except Exception:
            pass
    return render_template('my_revisions.html', revisions=revisions, user=current_user, is_paid=is_paid_user(current_user))


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
        return redirect(url_for('verify_email', email=getattr(current_user, 'email', '')))
    if str(request.args.get('canceled') or '').strip() == '1':
        flash('Your subscription has been canceled. You\'ll keep access until the end of your billing period.', 'success')
    prof = get_user_profile_azure(getattr(current_user, 'id', '')) or {}
    paid_until_raw = str(prof.get('paid_until') or '').strip()
    customer_id = str(prof.get('stripe_customer_id') or '').strip()
    subscription_id = str(prof.get('stripe_subscription_id') or '').strip()
    plan_status_raw = str(prof.get('plan_status') or '').strip()
    debug = str(request.args.get('debug') or '').strip() == '1'
    # Avoid exposing Stripe/customer diagnostics in production.
    # Enable only for localhost or when explicitly allowed via env var.
    try:
        host = str(getattr(request, "host", "") or "").lower()
    except Exception:
        host = ""
    debug_allowed = bool(
        debug
        and (
            host.startswith("127.0.0.1")
            or host.startswith("localhost")
            or (os.getenv("ENABLE_SETTINGS_DEBUG") or "").strip() == "1"
        )
    )
    debug_info = None

    paid_flag = bool(is_paid_user(current_user))
    cancel_scheduled = False
    # Sync with Stripe on settings loads so cancellations are reflected quickly even if webhooks lag.
    if _stripe_enabled():
        try:
            paid_flag = bool(_refresh_paid_status_from_stripe_for_user(current_user))
            prof = get_user_profile_azure(getattr(current_user, 'id', '')) or prof
            plan_status_raw = str(prof.get('plan_status') or plan_status_raw).strip()
            paid_until_raw = str(prof.get('paid_until') or paid_until_raw).strip()
            customer_id = str(prof.get('stripe_customer_id') or customer_id).strip()
            subscription_id = str(prof.get('stripe_subscription_id') or subscription_id).strip()
        except Exception:
            pass

    # If webhook hasn't populated Stripe ids yet (or paid flag is stale), recover them via email lookup.
    # This allows newly-purchased users to see accurate plan dates immediately.
    if _stripe_enabled():
        try:
            if not customer_id:
                customer_id = _find_stripe_customer_id_by_email((getattr(current_user, 'email', '') or '').strip())
            if customer_id and not subscription_id:
                stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
                subs = stripe.Subscription.list(customer=customer_id, status='all', limit=10)
                sdata = list(getattr(subs, 'data', []) or [])
                # Prefer active > trialing > others; then later period end
                def _rank(sub):
                    status = str(getattr(sub, 'status', '') or '').lower()
                    cpe = int(getattr(sub, 'current_period_end', 0) or 0)
                    sr = 0
                    if status == 'active':
                        sr = 3
                    elif status == 'trialing':
                        sr = 2
                    elif status in ('past_due', 'unpaid'):
                        sr = 1
                    return (sr, cpe)
                if sdata:
                    best = sorted(sdata, key=_rank, reverse=True)[0]
                    subscription_id = str(getattr(best, 'id', '') or '').strip() or subscription_id
                    best_status = str(getattr(best, 'status', '') or '').strip().lower()
                    if best_status in ('active', 'trialing'):
                        paid_flag = True

            # Backfill ids to Azure so future loads are fast/stable.
            if customer_id or subscription_id:
                try:
                    table_client = get_users_table_client()
                    entity = {"PartitionKey": str(current_user.id), "RowKey": "profile"}
                    if customer_id:
                        entity["stripe_customer_id"] = str(customer_id)
                    if subscription_id:
                        entity["stripe_subscription_id"] = str(subscription_id)
                    # If Stripe indicates an active/trialing sub, reflect that.
                    if paid_flag:
                        entity["is_paid"] = True
                    table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
                except Exception:
                    pass
        except Exception:
            pass

    # Stripe-derived dates (handles upgrades where Azure still reflects the trial subscription)
    stripe_dates = _get_stripe_plan_dates_for_customer(customer_id) if paid_flag else {}
    if paid_flag and not stripe_dates and subscription_id:
        stripe_dates = _get_stripe_plan_dates_for_subscription(subscription_id)
    next_billing_iso = str(stripe_dates.get('next_billing_iso') or '').strip()
    paid_through_est_iso = str(stripe_dates.get('paid_through_est_iso') or '').strip()
    interval_label = str(stripe_dates.get('interval_label') or '').strip()
    stripe_status = str(stripe_dates.get('status') or '').strip().lower()

    # Strongest source of truth: compute directly from the stored Stripe subscription_id.
    # This avoids cases where precomputed stripe_dates degrade to "trial end" due to missing interval info.
    try:
        if paid_flag and subscription_id and _stripe_enabled():
            stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
            sub_obj = stripe.Subscription.retrieve(subscription_id, expand=["items.data.price"])
            # If a user has already scheduled cancellation (cancel_at_period_end), keep them paid
            # through the period end, but hide the cancel button in Settings.
            try:
                cancel_scheduled = bool(_stripe_obj_get(sub_obj, "cancel_at_period_end", False)) or bool(_stripe_obj_get(sub_obj, "cancel_at", None))
            except Exception:
                cancel_scheduled = False
            # Always try SubscriptionItem.list to reliably get price/recurring
            # (some Stripe responses omit items.data even with expand).
            si_err = ""
            si_count = 0
            si_price_id = ""
            try:
                si = stripe.SubscriptionItem.list(subscription=subscription_id, limit=10, expand=["data.price"])
                si_data = list(getattr(si, "data", []) or [])
                si_count = len(si_data)
                if si_data:
                    p = getattr(si_data[0], "price", None)
                    if isinstance(p, str):
                        si_price_id = p.strip()
                    elif isinstance(p, dict):
                        si_price_id = str(p.get("id") or "").strip()
                    else:
                        si_price_id = str(getattr(p, "id", "") or "").strip() if p else ""
            except Exception as e:
                si_err = f"{type(e).__name__}: {str(e)}"

            # Stripe can sometimes return plain dicts; handle both dict and StripeObject.
            status = str(_stripe_obj_get(sub_obj, "status", "") or "").strip().lower()
            stripe_status = status or stripe_status
            trial_end = _stripe_obj_get(sub_obj, "trial_end", None)
            current_period_end = _stripe_obj_get(sub_obj, "current_period_end", None)
            current_period_start = _stripe_obj_get(sub_obj, "current_period_start", None)
            billing_cycle_anchor = _stripe_obj_get(sub_obj, "billing_cycle_anchor", None)
            start_date = _stripe_obj_get(sub_obj, "start_date", None)

            # Determine price + interval early so all fallbacks can use it.
            price_id, interval, interval_count = _get_subscription_price_id_and_recurring(sub_obj)
            if not price_id and si_price_id:
                price_id = si_price_id

            annual_pid = _get_stripe_price_id('annual_6_95') or ''
            monthly_pid = _get_stripe_price_id('monthly_10_95') or ''
            # Infer interval if Stripe didn't provide recurring info
            if not interval and price_id and annual_pid and price_id == annual_pid:
                interval, interval_count = 'year', 1
            if not interval and price_id and monthly_pid and price_id == monthly_pid:
                interval, interval_count = 'month', 1

            # Some Stripe setups can surface an "active" subscription where current_period_end is not populated
            # in our retrieved object. Fallback to upcoming invoice period_end for accurate renewal timing.
            inv_err = ""
            inv_period_end = None
            inv_next_payment_attempt = None
            raw_sub_cpe = None
            raw_sub_billing_anchor = None
            raw_sub_current_period_start = None
            raw_sub_start_date = None
            raw_sub_err = ""
            latest_inv_period_end = None
            latest_inv_err = ""
            sanity_applied = False
            sanity_prev_cpe = None
            sanity_new_cpe = None
            if not current_period_end and status in ("active", "trialing"):
                try:
                    inv = _stripe_upcoming_invoice(customer_id, subscription_id)
                    inv_period_end = _stripe_obj_get(inv, "period_end", None)
                    inv_next_payment_attempt = _stripe_obj_get(inv, "next_payment_attempt", None)
                    if inv_period_end:
                        current_period_end = inv_period_end
                except Exception as e:
                    inv_err = f"{type(e).__name__}: {str(e)}"
            # Final fallback: fetch raw subscription JSON and read current_period_end directly.
            if not current_period_end:
                try:
                    raw_sub = _stripe_subscription_raw(subscription_id)
                    raw_sub_cpe = _stripe_obj_get(raw_sub, "current_period_end", None)
                    raw_sub_billing_anchor = _stripe_obj_get(raw_sub, "billing_cycle_anchor", None)
                    raw_sub_current_period_start = _stripe_obj_get(raw_sub, "current_period_start", None)
                    raw_sub_start_date = _stripe_obj_get(raw_sub, "start_date", None)
                    if raw_sub_cpe:
                        current_period_end = raw_sub_cpe
                except Exception:
                    raw_sub_err = "raw_subscription_fetch_failed"

            # Fallback: use latest invoice period_end if available
            if not current_period_end:
                try:
                    latest_inv = _stripe_latest_invoice_for_subscription(subscription_id)
                    latest_inv_period_end = _stripe_obj_get(latest_inv, "period_end", None)
                    if not latest_inv_period_end:
                        # Sometimes invoice line has period.end
                        lines = _stripe_obj_get(latest_inv, "lines", None)
                        ldata = _stripe_obj_get(lines, "data", []) if lines else []
                        if ldata:
                            period = _stripe_obj_get(ldata[0], "period", None)
                            latest_inv_period_end = _stripe_obj_get(period, "end", None) if period else None
                    if latest_inv_period_end:
                        current_period_end = latest_inv_period_end
                except Exception as e:
                    latest_inv_err = f"{type(e).__name__}: {str(e)}"

            # If Stripe has already collected payment for the *next* period, the subscription's
            # current_period_end can remain at the end of the current period until the period rolls.
            # For UX, treat a PAID renewal invoice line period.end as the effective paid-through date.
            latest_inv_paid = None
            latest_inv_status = ""
            latest_inv_line_period_end = None
            latest_inv_line_period_start = None
            try:
                if "latest_inv" in locals() and latest_inv is not None:
                    latest_inv_paid = _stripe_obj_get(latest_inv, "paid", None)
                    latest_inv_status = str(_stripe_obj_get(latest_inv, "status", "") or "").strip().lower()
                    lines_obj = _stripe_obj_get(latest_inv, "lines", None)
                    ldata = _stripe_obj_get(lines_obj, "data", []) if lines_obj else []
                    if ldata:
                        period_obj = _stripe_obj_get(ldata[0], "period", None)
                        if period_obj:
                            latest_inv_line_period_start = _stripe_obj_get(period_obj, "start", None)
                            latest_inv_line_period_end = _stripe_obj_get(period_obj, "end", None)
            except Exception:
                pass

            # Final fallback: approximate from billing_cycle_anchor/current_period_start + interval.
            if not current_period_end:
                try:
                    base_ts = None
                    for candidate in (
                        current_period_start,
                        start_date,
                        billing_cycle_anchor,
                        raw_sub_current_period_start,
                        raw_sub_start_date,
                        raw_sub_billing_anchor,
                    ):
                        if candidate:
                            base_ts = int(candidate)
                            break
                    if base_ts:
                        base_dt = datetime.fromtimestamp(base_ts, tz=timezone.utc)
                        if interval:
                            current_period_end = int(_add_interval_approx(base_dt, interval, interval_count).timestamp())
                except Exception:
                    pass

            # Sanity check: sometimes we end up with a "period end" equal to the billing anchor (or not in the future),
            # which makes the UI show today's date. For active subscriptions, ensure period_end is in the future.
            try:
                if status == "active" and interval and current_period_end:
                    now_ts = int(datetime.now(timezone.utc).timestamp())
                    cpe = int(current_period_end)
                    sanity_prev_cpe = cpe
                    anchor_ts = None
                    try:
                        for candidate in (
                            current_period_start,
                            start_date,
                            billing_cycle_anchor,
                            raw_sub_current_period_start,
                            raw_sub_start_date,
                            raw_sub_billing_anchor,
                        ):
                            if candidate:
                                anchor_ts = int(candidate)
                                break
                    except Exception:
                        anchor_ts = None
                    # If cpe is not meaningfully after anchor, or it's already due/expired, recompute.
                    if (anchor_ts is not None and cpe <= (anchor_ts + 60)) or (cpe <= (now_ts + 300)):
                        base_for_calc = anchor_ts if anchor_ts is not None else now_ts
                        base_dt = datetime.fromtimestamp(int(base_for_calc), tz=timezone.utc)
                        current_period_end = int(_add_interval_approx(base_dt, interval, interval_count).timestamp())
                        sanity_applied = True
                        sanity_new_cpe = int(current_period_end)
            except Exception:
                pass

            # Apply invoice-paid extension AFTER sanity checks so we don't regress the period.
            effective_period_end = current_period_end
            try:
                if status == "active" and effective_period_end and latest_inv_line_period_end:
                    # Consider invoice "paid" only when Stripe says so.
                    inv_paid_bool = bool(latest_inv_paid is True or latest_inv_status == "paid")
                    if inv_paid_bool:
                        inv_line_end_int = int(latest_inv_line_period_end)
                        eff_int = int(effective_period_end)
                        if inv_line_end_int > eff_int:
                            effective_period_end = inv_line_end_int
            except Exception:
                pass

            # Compute next_billing / paid_through from subscription directly.
            next_ts = None
            if status == "trialing" and trial_end:
                next_ts = int(trial_end)
            elif effective_period_end:
                next_ts = int(effective_period_end)

            if next_ts:
                next_billing_iso = datetime.fromtimestamp(int(next_ts), tz=timezone.utc).isoformat()

            if status == "trialing" and trial_end:
                base = datetime.fromtimestamp(int(trial_end), tz=timezone.utc)
                # During trial, access is valid through trial_end.
                paid_through_est_iso = base.isoformat()
            elif effective_period_end:
                paid_through_est_iso = datetime.fromtimestamp(int(effective_period_end), tz=timezone.utc).isoformat()

            if interval == 'year':
                interval_label = interval_label or 'Annual'
                plan_status_raw = plan_status_raw or 'annual_6_95'
            elif interval == 'month':
                interval_label = interval_label or 'Monthly'
                plan_status_raw = plan_status_raw or 'monthly_10_95'

            if debug_allowed:
                # also show what Stripe returned around items
                sub_items_len = 0
                try:
                    sub_items_len = len(list(getattr(getattr(sub_obj, "items", None), "data", []) or []))
                except Exception:
                    sub_items_len = 0

                def _ts_to_iso_str(ts_val) -> str:
                    try:
                        if not ts_val:
                            return ""
                        return datetime.fromtimestamp(int(ts_val), tz=timezone.utc).isoformat()
                    except Exception:
                        return ""

                latest_inv_id = ""
                latest_inv_line_period_start = None
                latest_inv_line_period_end = None
                try:
                    # Prefer already-fetched latest invoice if available; otherwise fetch best-effort.
                    if "latest_inv" not in locals() or latest_inv is None:
                        latest_inv = _stripe_latest_invoice_for_subscription(subscription_id)
                    latest_inv_id = str(_stripe_obj_get(latest_inv, "id", "") or "").strip()
                    lines_obj = _stripe_obj_get(latest_inv, "lines", None)
                    ldata = _stripe_obj_get(lines_obj, "data", []) if lines_obj else []
                    if ldata:
                        period_obj = _stripe_obj_get(ldata[0], "period", None)
                        if period_obj:
                            latest_inv_line_period_start = _stripe_obj_get(period_obj, "start", None)
                            latest_inv_line_period_end = _stripe_obj_get(period_obj, "end", None)
                except Exception:
                    pass

                debug_info = {
                    "settings_debug_version": "sanitycheck_v3",
                    "runtime_app_file": __file__,
                    "runtime_app_mtime_utc": datetime.fromtimestamp(os.path.getmtime(__file__), tz=timezone.utc).isoformat() if os.path.exists(__file__) else "",
                    "runtime_cwd": os.getcwd(),
                    "runtime_python": getattr(__import__('sys'), 'executable', ''),
                    "runtime_request_host": str(request.host_url or ''),
                    "azure_plan_status": str(prof.get("plan_status") or ""),
                    "azure_paid_until": str(prof.get("paid_until") or ""),
                    "stripe_customer_id": customer_id,
                    "stripe_subscription_id": subscription_id,
                    "stripe_status": status,
                    "stripe_trial_end": str(trial_end or ""),
                    "stripe_current_period_end": str(current_period_end or ""),
                    "stripe_current_period_start": str(current_period_start or ""),
                    "stripe_billing_cycle_anchor": str(billing_cycle_anchor or ""),
                    "stripe_start_date": str(start_date or ""),
                    "stripe_upcoming_invoice_period_end": str(inv_period_end or ""),
                    "stripe_upcoming_invoice_next_payment_attempt": str(inv_next_payment_attempt or ""),
                    "stripe_upcoming_invoice_error": inv_err,
                    "stripe_raw_subscription_current_period_end": str(raw_sub_cpe or ""),
                    "stripe_raw_subscription_billing_cycle_anchor": str(raw_sub_billing_anchor or ""),
                    "stripe_raw_subscription_current_period_start": str(raw_sub_current_period_start or ""),
                    "stripe_raw_subscription_start_date": str(raw_sub_start_date or ""),
                    "stripe_raw_subscription_error": raw_sub_err,
                    "stripe_latest_invoice_period_end": str(latest_inv_period_end or ""),
                    "stripe_latest_invoice_id": latest_inv_id,
                    "stripe_latest_invoice_line_period_start": str(latest_inv_line_period_start or ""),
                    "stripe_latest_invoice_line_period_end": str(latest_inv_line_period_end or ""),
                    "stripe_latest_invoice_line_period_start_iso": _ts_to_iso_str(latest_inv_line_period_start),
                    "stripe_latest_invoice_line_period_end_iso": _ts_to_iso_str(latest_inv_line_period_end),
                    "stripe_latest_invoice_status": str(latest_inv_status or ""),
                    "stripe_latest_invoice_paid": str(latest_inv_paid if latest_inv_paid is not None else ""),
                    "stripe_effective_period_end": str(effective_period_end or ""),
                    "stripe_effective_period_end_iso": _ts_to_iso_str(effective_period_end),
                    "stripe_latest_invoice_error": latest_inv_err,
                    "stripe_sanity_applied": str(sanity_applied),
                    "stripe_sanity_prev_cpe": str(sanity_prev_cpe or ""),
                    "stripe_sanity_new_cpe": str(sanity_new_cpe or ""),
                    "stripe_item_price_id": price_id,
                    "stripe_subscription_items_len": str(sub_items_len),
                    "stripe_subscriptionitem_list_count": str(si_count),
                    "stripe_subscriptionitem_list_error": si_err,
                    "stripe_subscriptionitem_price_id": si_price_id,
                    "env_annual_price_id": annual_pid,
                    "env_monthly_price_id": monthly_pid,
                    "computed_interval": interval,
                    "computed_interval_count": str(interval_count),
                    "computed_next_billing_iso": next_billing_iso,
                    "computed_paid_through_iso": paid_through_est_iso,
                }
    except Exception:
        pass

    # Note: For trialing subscriptions, it's expected that paid_through == next_billing == trial_end.

    # Back-compat: keep paid_until_display populated (prefer Stripe paid-through estimate if it exists)
    if paid_flag:
        paid_until_raw = paid_through_est_iso or paid_until_raw
        if not paid_until_raw:
            # Older fallback: if we only have subscription_id stored, try it.
            sub_id = _get_stripe_subscription_id_from_azure(getattr(current_user, 'id', ''))
            paid_until_raw = _get_paid_until_from_stripe(sub_id) or paid_until_raw
    else:
        # Free users should not show stale billing dates from previously canceled subscriptions.
        paid_until_raw = ''
        next_billing_iso = ''
        interval_label = ''
    return render_template(
        'settings.html',
        user=current_user,
        email=(getattr(current_user, 'email', '') or '').strip(),
        name=(getattr(current_user, 'name', '') or '').strip(),
        is_paid=paid_flag,
        cancel_scheduled=bool(cancel_scheduled),
        plan_status=plan_status_raw,
        interval_label=interval_label,
        next_billing_display=_format_paid_until(next_billing_iso),
        paid_through_display=_format_paid_until(paid_until_raw),
        debug_info=debug_info,
    )

@app.route('/api/me')
def api_me():
    """Lightweight user info for the React frontend (plan gating, limits)."""
    try:
        if not current_user.is_authenticated:
            return jsonify({
                "is_authenticated": False,
                "is_paid": False,
                "free_revision_limit": FREE_REVISION_LIMIT,
                "revisions_used": 0,
            })
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
                    paid = bool(_refresh_paid_status_from_stripe_for_user(current_user)) or paid
            except Exception:
                pass
        used = 0
        try:
            used = len(get_user_revisions(current_user.id))
        except Exception:
            used = 0
        return jsonify({
            "is_authenticated": True,
            "is_paid": bool(paid),
            "free_revision_limit": FREE_REVISION_LIMIT,
            "revisions_used": used,
        })
    except Exception:
        return jsonify({
            "is_authenticated": False,
            "is_paid": False,
            "free_revision_limit": FREE_REVISION_LIMIT,
            "revisions_used": 0,
        })

@app.route('/view_revision/<revision_id>')
@login_required
def view_revision(revision_id):
    revisions = get_user_revisions(current_user.id)
    rev = next((r for r in revisions if r['revision_id'] == revision_id), None)
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
@app.route('/update_revision_name/<revision_id>', methods=['GET', 'POST'], strict_slashes=False)
@app.route('/path/update_revision_name', methods=['GET', 'POST'])
@app.route('/path/update_revision_name/<revision_id>', methods=['GET', 'POST'], strict_slashes=False)

# Extra robustness: if the browser resolves the relative form action under a trailing-slash
# my_revisions URL, it may post to /my_revisions/update_revision_name/<id>.
@app.route('/my_revisions/update_revision_name', methods=['GET', 'POST'])
@app.route('/my_revisions/update_revision_name/<revision_id>', methods=['GET', 'POST'], strict_slashes=False)
@app.route('/path/my_revisions/update_revision_name', methods=['GET', 'POST'])
@app.route('/path/my_revisions/update_revision_name/<revision_id>', methods=['GET', 'POST'], strict_slashes=False)
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
            revision_id = (request.form.get('revision_id') or request.args.get('revision_id') or '').strip()

        if not revision_id:
            if wants_json:
                return jsonify({'ok': False, 'error': 'Missing revision id'}), 400
            flash('Error updating resume name. Please try again.', 'danger')
            return redirect(request.referrer or url_for('my_revisions'))

        # We only update on POST; GET requests are redirected back.
        if request.method != 'POST':
            return redirect(request.referrer or url_for('my_revisions'))

        revision_name = (request.form.get('revision_name') or '').strip()
        # Keep this user-facing label short to avoid blowing up card layout.
        revision_name = revision_name[:80]

        table_client = get_table_client()
        entity = table_client.get_entity(partition_key=current_user.id, row_key=revision_id)
        entity['revision_name'] = revision_name
        table_client.update_entity(entity, mode=UpdateMode.MERGE)
        if wants_json:
            return jsonify({'ok': True, 'revision_id': revision_id, 'revision_name': revision_name}), 200
    except Exception:
        if wants_json:
            return jsonify({'ok': False, 'error': 'Error updating resume name. Please try again.'}), 500
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
        entity = table_client.get_entity(partition_key=str(current_user.id), row_key=str(revision_id))
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
    structured_resume = _load_structured_snapshot_for_template(entity, template_id)
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
    return redirect(url_for('imported_resume_builder'))


@app.route('/download_revision_template_pdf/<revision_id>')
@login_required
def download_revision_template_pdf(revision_id):
    """Download a saved revision as a PDF.

    Uses a download-only React route that auto-downloads (no editor UI, no print dialog).
    """
    template_id = str(request.args.get('template') or '').strip() or None
    try:
        table_client = get_table_client()
        entity = table_client.get_entity(partition_key=str(current_user.id), row_key=str(revision_id))
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
    structured_resume = _load_structured_snapshot_for_template(entity, template_id)
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
        entity = table_client.get_entity(partition_key=current_user.id, row_key=revision_id)
        
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
            flash('Please fill at least one field before adding an application.', 'danger')
            return redirect(url_for('my_revisions'))

        table_client = get_table_client()
        entity = table_client.get_entity(partition_key=current_user.id, row_key=revision_id)
        apps = _parse_applications(entity.get('applications', ''))
        apps.append({
            'company': company,
            'role': role,
            'date_applied': date_applied,
            'status': status,
            'link': link,
        })
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
        entity = table_client.get_entity(partition_key=current_user.id, row_key=revision_id)
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
        provider = "google" if str(uid).isdigit() else ("facebook" if str(uid).startswith("facebook_") else "other")
        results.append({
            "id": uid,
            "email": email,
            "name": name,
            "provider": provider,
            "revisions": n,
        })

    results.sort(key=lambda x: x["revisions"], reverse=True)
    return results

@app.route('/admin/registered_users.json')
@login_required
def registered_users_json():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403
    table_name = (request.args.get('table') or '').strip() or 'Users'
    users_rows, resolved_table, all_keys = _collect_registered_users_from_azure_users_table(table_name)
    return jsonify({"table": resolved_table, "columns": all_keys, "users": users_rows})

def _format_value_pacific_if_datetime(val):
    """Format datetime values to Pacific time for display."""
    if val is None:
        return val
    if hasattr(val, "isoformat"):
        return _format_datetime_pacific(val.isoformat())
    if isinstance(val, str) and ("T" in val or (len(val) >= 19 and val[4] == "-" and val[7] == "-")):
        return _format_datetime_pacific(val)
    return val


@app.route('/admin/registered_users')
@login_required
def registered_users_view():
    if not getattr(current_user, "is_admin", False):
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("index"))
    table_name = (request.args.get('table') or '').strip() or 'Users'
    data, resolved_table, all_keys = _collect_registered_users_from_azure_users_table(table_name)
    for row in data:
        for k in list(row.keys()):
            v = row.get(k)
            if v is not None and (hasattr(v, "isoformat") or (isinstance(v, str) and "T" in v)):
                row[k] = _format_value_pacific_if_datetime(v)
    return render_template('admin_registered_users.html', users=data, azure_users_table_name=resolved_table, columns=all_keys)

@app.route('/admin/registered_users.csv')
@login_required
def registered_users_csv():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403
    table_name = (request.args.get('table') or '').strip() or 'Users'
    rows, resolved_table, all_keys = _collect_registered_users_from_azure_users_table(table_name)
    # Build CSV in-memory
    lines = [','.join([f'"{k}"' for k in all_keys])]
    for r in rows:
        def esc(v):
            s = str(v or "")
            s = s.replace('"','""')
            return f'"{s}"'
        line = ','.join([esc(r.get(k, '')) for k in all_keys])
        lines.append(line)
    csv_data = "\r\n".join(lines) + "\r\n"
    return Response(csv_data, mimetype='text/csv', headers={
        'Content-Disposition': f'attachment; filename=registered_users_{resolved_table}.csv'
    })

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
        emails = sorted({
            (u.get('email') or '').strip().lower()
            for u in data.values()
            if u and u.get('email') and str(u.get('id', '')).isdigit()
        })
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
        emails = sorted({
            (u.get('email') or '').strip().lower()
            for u in data.values()
            if u and u.get('email') and str(u.get('id', '')).isdigit()
        })
        csv_data = "email\n" + "\n".join(emails) + "\n"
        return Response(csv_data, mimetype='text/csv', headers={
            'Content-Disposition': 'attachment; filename=google_emails.csv'
        })
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
            users_list.append({
                'id': e.get('PartitionKey'),
                'name': e.get('name') or '',
                'email': e.get('email') or '',
                'provider': provider or 'other',
                'created_at': e.get('created_at') or '',
                'is_admin': bool(e.get('is_admin', False)),
            })
        # Sort by created_at desc if present
        from datetime import datetime
        def parse_dt(s):
            try:
                return datetime.fromisoformat(s)
            except Exception:
                return datetime.min
        users_list.sort(key=lambda x: parse_dt(x.get('created_at') or ''), reverse=True)
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
            rows.append({
                'id': e.get('PartitionKey'),
                'name': e.get('name') or '',
                'email': e.get('email') or '',
                'provider': provider or 'other',
                'created_at': e.get('created_at') or '',
                'is_admin': 'true' if e.get('is_admin', False) else 'false',
            })
        def esc(v):
            s = str(v or "")
            if any(c in s for c in [',','"','\n','\r']):
                s = '"' + s.replace('"','""') + '"'
            return s
        header = ['id','name','email','provider','created_at','is_admin']
        lines = [','.join(header)]
        for r in rows:
            lines.append(','.join([esc(r[h]) for h in header]))
        csv_data = "\n".join(lines) + "\n"
        return Response(csv_data, mimetype='text/csv', headers={
            'Content-Disposition': 'attachment; filename=users_azure.csv'
        })
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
                pager = table_client.query_entities("record_type eq 'session'")
            except Exception:
                pager = None

        if pager is None:
            pager = table_client.list_entities()

        for e in pager:
            try:
                if str(e.get('record_type') or '') != 'session':
                    continue
                if user_id and str(e.get('PartitionKey') or '').strip() != user_id:
                    continue
                sessions.append({
                    'user_id': str(e.get('PartitionKey') or ''),
                    'row_key': str(e.get('RowKey') or ''),
                    'email': e.get('email') or '',
                    'login_at': e.get('login_at') or '',
                    'last_activity_at': e.get('last_activity_at') or '',
                    'logout_at': e.get('logout_at') or '',
                    'duration_seconds': e.get('duration_seconds', None),
                    'login_method': e.get('login_method') or '',
                    'ip': e.get('ip') or '',
                    # Keep UA/referer for debugging; can be large.
                    'user_agent': e.get('user_agent') or '',
                    'referer': e.get('referer') or '',
                    'login_audit_pk': e.get('login_audit_pk') or '',
                    'login_audit_rk': e.get('login_audit_rk') or '',
                })
            except Exception:
                continue
            if limit and len(sessions) >= limit:
                break

        # Sort by login_at descending (ISO strings are sortable when consistently formatted).
        sessions.sort(key=lambda r: str(r.get('login_at') or ''), reverse=True)
        return jsonify({
            'count': len(sessions),
            'user_id': user_id or None,
            'sessions': sessions,
        })
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
    plan_status = str((data.get('plan_status') or '')).strip().lower()  # free|trial|paid|active|canceled
    paid_until = str((data.get('paid_until') or '')).strip()  # ISO timestamp optional
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
        req_host = host_only((request.headers.get('X-Forwarded-Host') or request.host or urlparse(request.host_url).netloc))
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


def _admin_delete_user_impl(email: str, user_id: str, delete_revisions: bool = True) -> dict:
    email = (email or '').strip().lower()
    user_id = (user_id or '').strip()
    delete_revisions = True if delete_revisions is None else bool(delete_revisions)

    if not email and not user_id:
        return {"ok": False, "status": 400, "error": "Missing email or user_id"}

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
    resolved_ids = [x for x in resolved_ids if x and not (x in seen or seen.add(x))]

    if not resolved_ids:
        return {"ok": False, "status": 404, "error": "User not found", "azure_resolve_error": azure_resolve_error}

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
                e = str((data.get(uid) or {}).get('email') or '').strip().lower()
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
                table_client.delete_entity(partition_key=str(uid), row_key='profile')
                deleted_azure_profiles += 1
            except Exception as e:
                deleted_azure_profile_errors.append(f"{uid}: {str(e)}")
            # Delete any other rows for the same PK (rare, but keep clean)
            try:
                for ent in table_client.query_entities(f"PartitionKey eq '{str(uid)}'"):
                    rk = str(ent.get('RowKey') or '').strip()
                    if not rk or rk == 'profile':
                        continue
                    try:
                        table_client.delete_entity(partition_key=str(uid), row_key=rk)
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
            rev_client = get_table_client('ResumeRevisions', create_if_missing=False)
            for uid in resolved_ids:
                try:
                    for ent in rev_client.query_entities(f"PartitionKey eq '{str(uid)}'"):
                        rk = str(ent.get('RowKey') or '').strip()
                        if not rk:
                            continue
                        try:
                            rev_client.delete_entity(partition_key=str(uid), row_key=rk)
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
        return render_template('admin_delete_user.html', prefill_email=prefill_email, prefill_user_id=prefill_user_id)

    # POST
    # Validate CSRF token (do not rely on Origin/Referer — Azure proxies can break it)
    posted_csrf = ""
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        posted_csrf = str(payload.get('admin_csrf') or request.headers.get('X-Admin-CSRF') or '').strip()
    else:
        posted_csrf = str(request.form.get('admin_csrf') or '').strip()
    expected_csrf = str(session.get('admin_csrf') or '').strip()
    if not expected_csrf or not posted_csrf or posted_csrf != expected_csrf:
        if request.is_json:
            return jsonify({"error": "Forbidden"}), 403
        flash("Forbidden (CSRF check failed). Please refresh and try again.", "danger")
        return redirect(url_for("admin_stats"))

    if request.is_json:
        data = request.get_json(silent=True) or {}
        email = str((data.get('email') or '')).strip()
        user_id = str((data.get('user_id') or '')).strip()
        delete_revisions = data.get('delete_revisions', True)
        res = _admin_delete_user_impl(email=email, user_id=user_id, delete_revisions=delete_revisions)
        return jsonify(res), int(res.get("status") or 200)

    # HTML form submit
    email = (request.form.get('email') or '').strip()
    user_id = (request.form.get('user_id') or '').strip()
    delete_revisions = bool(request.form.get('delete_revisions') in ('1', 'true', 'on', 'yes'))
    return_to = (request.form.get('return_to') or '').strip()
    res = _admin_delete_user_impl(email=email, user_id=user_id, delete_revisions=delete_revisions)
    if res.get("ok"):
        errs = len(res.get('deleted_azure_profile_errors') or []) + len(res.get('revision_delete_errors') or []) + len(res.get('file_errors') or [])
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
    return render_template('admin_delete_user.html', prefill_email=email, prefill_user_id=user_id, result=res)

def extract_text_from_file(file):
    """Extract text from uploaded file (PDF or DOCX), using fallback for complex Word docs."""
    try:
        filename = secure_filename(file.filename)
        file_extension = filename.lower().split('.')[-1]
        _safe_print(f"Processing file: {filename}, extension: {file_extension}")

        if file_extension == 'pdf':
            text = ""
            try:
                with pdfplumber.open(file) as pdf:
                    _safe_print(f"PDF has {len(pdf.pages)} pages")
                    for page_num, page in enumerate(pdf.pages):
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                            _safe_print(f"Page {page_num + 1}: {len(page_text)} characters extracted")
            except Exception as e:
                _safe_print(f"pdfplumber failed: {str(e)}, trying PyPDF2")
                file.seek(0)
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    text += page_text + "\n"
                    _safe_print(f"Page {page_num + 1}: {len(page_text)} characters extracted")

            _safe_print(f"Total PDF text extracted: {len(text)} characters")
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
            
                _safe_print(f"Total DOC text extracted: {len(text)} characters")

                # Fallback if too little text
                if len(text.strip()) < 75:
                    _safe_print("Text too short, falling back to mammoth...")
                    docx_buffer.seek(0)
                    result = mammoth.extract_raw_text(docx_buffer)
                    text = result.value
                    _safe_print(f"Text extracted using mammoth: {len(text)} characters")
            except Exception as e:
                _safe_print(f"python-docx failed: {str(e)}, trying mammoth as fallback")
                docx_buffer.seek(0)
                result = mammoth.extract_raw_text(docx_buffer)
                text = result.value
                _safe_print(f"Text extracted using mammoth: {len(text)} characters")

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
        conversion_result = analytics.track_conversion(session, "resume_submission")
        
        if conversion_result.get("status") == "success":
            # Get updated total conversions count
            analytics_data = analytics.get_full_analytics()
            count = analytics_data.get('summary', {}).get('total_conversions', 0)
            return {"success": True, "count": count}
        else:
            return {"success": False, "error": "Failed to track conversion"}, 500
            
    except Exception as e:
        return {"success": False, "error": str(e)}, 500

@app.route('/counter')
def counter_page():
    """Display counter page"""
    try:
        # Use the analytics module to get the total conversion count
        analytics_data = analytics.get_full_analytics()
        count = analytics_data.get('summary', {}).get('total_conversions', 0)
        
        # Fallback to legacy counter.json format if analytics doesn't work
        if count == 0:
            counter_file = 'counter.json'
            if os.path.exists(counter_file):
                with open(counter_file, 'r') as f:
                    data = json.load(f)
                    # Try new format first (total_conversions), then legacy format (count)
                    count = data.get('total_conversions', data.get('count', 0))
        
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
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache for 24 hours
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
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

@app.route('/sitemap-static.xml')
def sitemap_static():
    """Serve static sitemap.xml file as backup"""
    try:
        response = send_file('sitemap.xml', mimetype='application/xml')
        response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache for 24 hours
        return response
    except Exception as e:
        # Fallback to dynamic sitemap
        return redirect(url_for('sitemap'))

@app.route('/ads.txt')
def ads_txt():
    """Serve ads.txt file"""
    response = send_file('ads.txt', mimetype='text/plain')
    if not app.debug:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Cache-Control'] = 'public, max-age=86400'
    return response

@app.route('/llms.txt')
def llms_txt():
    """Serve llms.txt file"""
    response = send_file('llms.txt', mimetype='text/plain')
    # Add security headers to ensure HTTPS preference
    if not app.debug:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
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
                for line in lines[1:] if lines and lines[0].strip().lower() == 'email' else lines:
                    email = line.strip()
                    if email:  # Only add non-empty emails
                        subscriber_list.append({
                            'email': email,
                            'date_added': 'Unknown'  # CSV doesn't store dates
                        })
                        subscriber_count += 1
        
        # Sort subscribers alphabetically
        subscriber_list.sort(key=lambda x: x['email'].lower())
        
        return render_template('subscribers.html', 
                             subscribers=subscriber_list, 
                             total_count=subscriber_count,
                             user=current_user)
    except Exception as e:
        flash(f"Error loading subscribers: {str(e)}", "danger")
        return render_template('subscribers.html', 
                             subscribers=[], 
                             total_count=0,
                             user=current_user)

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
        if os.path.exists("newsletters"):
            for filename in os.listdir("newsletters"):
                if filename.endswith(".json"):
                    try:
                        with open(os.path.join("newsletters", filename), "r") as f:
                            data = json.load(f)
                        newsletter_files.append({
                            "filename": filename,
                            "month": data.get("month"),
                            "year": data.get("year"),
                            "subject": data.get("subject"),
                            "generated_at": data.get("generated_at"),
                            "send_stats": data.get("send_stats", {})
                        })
                    except Exception as e:
                        logger.error(f"Error reading newsletter file {filename}: {str(e)}")

        # Sort by year and month (newest first)
        newsletter_files.sort(key=lambda x: (x.get("year", 0), x.get("month", "")), reverse=True)

        # Get subscriber count
        subscriber_count = 0
        if os.path.exists("subscribers.csv"):
            with open("subscribers.csv", "r") as f:
                lines = f.readlines()
                subscriber_count = len([line for line in lines[1:] if line.strip()]) if lines else 0

        return render_template('newsletter_admin.html', 
                             newsletters=newsletter_files, 
                             subscriber_count=subscriber_count,
                             user=current_user)
    except Exception as e:
        flash(f"Error loading newsletter dashboard: {str(e)}", "danger")
        return redirect(url_for("admin_stats"))

@app.route('/admin/newsletter/generate', methods=['POST'])
@login_required
def generate_newsletter():
    """Generate a new newsletter"""
    if not getattr(current_user, "is_admin", False):
        flash("You do not have permission to access this feature.", "danger")
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
            custom_topics = [topic.strip() for topic in custom_topics_str.split(',') if topic.strip()]

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
            flash(f"Newsletter preview generated for {month} {year}! Check the archives to view it.", "success")
        else:
            send_stats = result.get('send_stats', {})
            flash(f"Newsletter sent! {send_stats.get('sent', 0)} emails sent successfully, {send_stats.get('failed', 0)} failed.", "success")

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
        flash("You do not have permission to access this feature.", "danger")
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
        flash("You do not have permission to access this feature.", "danger")
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
        newsletter_data["last_sent"] = datetime.now(timezone.utc).isoformat()
        
        with open(filepath, "w") as f:
            json.dump(newsletter_data, f, indent=2)

        flash(f"Newsletter sent! {send_stats.get('sent', 0)} emails sent successfully, {send_stats.get('failed', 0)} failed.", "success")

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
            return jsonify({
                "status": "error", 
                "message": "Email credentials not configured. Please add NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD to your .env file."
            }), 400

        # Log the configuration for debugging (without password)
        logger.info(f"Testing email config - Email: {config.sender_email}, SMTP: {config.smtp_server}:{config.smtp_port}")

        # Test SMTP connection
        import smtplib
        server = smtplib.SMTP(config.smtp_server, config.smtp_port)
        server.starttls()
        server.login(config.sender_email, config.sender_password)
        server.quit()

        return jsonify({
            "status": "success", 
            "message": f"Email configuration is working correctly! Connected to {config.smtp_server} with {config.sender_email}"
        })

    except smtplib.SMTPAuthenticationError as e:
        error_msg = str(e)
        if "Username and Password not accepted" in error_msg:
            return jsonify({
                "status": "error", 
                "message": "Authentication failed. For Gmail, make sure you're using an App Password, not your regular password. See newsletter_config.txt for setup instructions."
            }), 400
        else:
            return jsonify({
                "status": "error", 
                "message": f"SMTP Authentication Error: {error_msg}"
            }), 400
    except smtplib.SMTPException as e:
        return jsonify({
            "status": "error", 
            "message": f"SMTP Error: {str(e)}"
        }), 400
    except Exception as e:
        logger.error(f"Newsletter config test error: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": f"Configuration error: {str(e)}"
        }), 400

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
                "NEWSLETTER_EMAIL": "Set" if os.getenv("NEWSLETTER_EMAIL") else "Not set",
                "NEWSLETTER_PASSWORD": "Set" if os.getenv("NEWSLETTER_PASSWORD") else "Not set"
            }
        }
        
        return jsonify({"status": "success", "debug_info": debug_info})

    except Exception as e:
        return jsonify({"status": "error", "message": f"Debug error: {str(e)}"}), 400

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
                subscribers = [line.strip().lower() for line in f.readlines()]
        
        # Check if email exists
        if email not in subscribers:
            flash("Email address not found in our subscriber list.", "info")
            return redirect(url_for('unsubscribe'))
        
        # Remove email from list
        updated_subscribers = [sub for sub in subscribers if sub != email and sub != 'email']
        
        # Write back to file
        with open("subscribers.csv", "w") as f:
            f.write("email\n")  # Header
            for subscriber in updated_subscribers:
                if subscriber:  # Skip empty lines
                    f.write(subscriber + "\n")
        
        flash("You have been successfully unsubscribed from our newsletter.", "success")
        
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
                        if key in already_set and val and not already_set.get(key, False):
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
    auth_email = (os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip('"').strip("'")
    auth_password = (os.getenv('NEWSLETTER_PASSWORD', '') or '').strip().strip('"').strip("'").replace(' ', '')
    recipient = os.getenv('CONTACT_RECIPIENT', 'yaronyaronlid@gmail.com').strip()

    if not auth_email or not auth_password:
        raise ValueError('Email credentials not configured. Set NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD.')

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


def save_contact_message(name: str, sender_email: str, message: str) -> None:
    """Persist contact messages locally if email delivery fails."""
    import csv
    from datetime import datetime
    filename = 'contact_messages.csv'
    try:
        file_exists = os.path.exists(filename)
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp_iso', 'name', 'email', 'message'])
            writer.writerow([datetime.utcnow().isoformat(), name or '', sender_email or '', message or ''])
    except Exception as e:
        logger.error(f'Failed to save contact message fallback: {str(e)}')


# Feedback form email helper
def send_feedback_email(sender_email: str, rating: str, category: str, message: str, source_url: str = '') -> None:
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
    auth_email = (os.getenv('NEWSLETTER_EMAIL', '') or '').strip().strip('"').strip("'")
    auth_password = (os.getenv('NEWSLETTER_PASSWORD', '') or '').strip().strip('"').strip("'").replace(' ', '')
    recipient = os.getenv('CONTACT_RECIPIENT', 'yaronyaronlid@gmail.com').strip()

    if not auth_email or not auth_password:
        raise ValueError('Email credentials not configured. Set NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD.')

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


def save_feedback_message(sender_email: str, rating: str, category: str, message: str, source_url: str = '') -> None:
    """Persist feedback messages locally if email delivery fails."""
    import csv
    from datetime import datetime
    filename = 'feedback_messages.csv'
    try:
        file_exists = os.path.exists(filename)
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp_iso', 'email', 'rating', 'category', 'message', 'source_url'])
            writer.writerow([
                datetime.utcnow().isoformat(),
                (sender_email or '').strip(),
                str(rating or '').strip(),
                str(category or '').strip(),
                message or '',
                str(source_url or '').strip(),
            ])
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
                logger.info('Contact form blocked by spam checks (honeypot/timing).')
                flash('Thank you for contacting us!', 'success')
                return render_template('contact.html', form_ts=int(time.time()))

            send_contact_email(name, email, message)
            flash('Thank you for contacting us! Your message has been sent.', 'success')
        except Exception as e:
            logger.error(f"Contact form email failed: {str(e)}")
            # Fallback: persist the message so it's not lost
            try:
                save_contact_message(name, email, message)
                flash('Thank you for contacting us! We received your message.', 'info')
            except Exception:
                flash('We could not send your message due to a server error. Please try again later.', 'danger')
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
                logger.info('Feedback form blocked by spam checks (honeypot/timing).')
                flash('Thank you for your feedback!', 'success')
                return render_template('feedback.html', form_ts=int(time.time()), source_url=source_url)

            # Minimal validation: require either a message or a rating
            if not message and not rating:
                flash('Please add a message or a rating before submitting.', 'danger')
                return render_template('feedback.html', form_ts=int(time.time()), source_url=source_url)

            send_feedback_email(sender_email, rating, category, message, source_url=source_url)
            flash('Thanks! Your feedback has been sent.', 'success')
        except Exception as e:
            logger.error(f"Feedback form email failed: {str(e)}")
            try:
                save_feedback_message(sender_email, rating, category, message, source_url=source_url)
                flash('Thanks! We received your feedback.', 'info')
            except Exception:
                flash('We could not send your feedback due to a server error. Please try again later.', 'danger')

        return render_template('feedback.html', form_ts=int(time.time()), source_url=source_url)

    # GET
    source_url = request.args.get('from') or request.referrer or ''
    return render_template('feedback.html', form_ts=int(time.time()), source_url=source_url)

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
    return Response('This URL has been permanently removed.', status=410, mimetype='text/plain')

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
        if (request.endpoint in noindex_endpoints) or (request.path in noindex_paths):
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
FILE_PATH = os.path.join(BASE_DIR, '610528eb-2434-4e0c-b4c5-1f54f21877ea.html')


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
                {"role": "system", "content": "You are a data extraction engine. Output only valid JSON."},
                {"role": "user", "content": parsing_prompt}
            ],
            response_format={"type": "json_object"}
        )

        parsing_content = parsing_response.choices[0].message.content
        
        # Remove markdown backticks if present (similar to revise_resume function)
        if parsing_content.startswith("```"):
            import re
            parsing_content = re.sub(r"^```(?:json)?\n", "", parsing_content)
            parsing_content = re.sub(r"\n```$", "", parsing_content)
            
        try:
            structured_resume = json.loads(parsing_content)
        except json.JSONDecodeError as e:
            logging.error(f"JSON Parse Error in parse_resume: {str(e)}")
            logging.error(f"Raw parsing content: {parsing_content[:500]}...")
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
        use_reloader = str(os.getenv('FLASK_USE_RELOADER', '') or '').strip().lower() in ('1', 'true', 'yes', 'on')
    except Exception:
        use_reloader = False

    try:
        host = str(os.getenv('FLASK_HOST', '127.0.0.1') or '127.0.0.1').strip()
    except Exception:
        host = '127.0.0.1'

    try:
        port = int(str(os.getenv('PORT', '5000') or '5000').strip())
    except Exception:
        port = 5000

    logger.info('Dev server starting (build=%s pid=%s host=%s port=%s reloader=%s)', _BUILD_ID, os.getpid(), host, port, use_reloader)
    app.run(debug=True, host=host, port=port, use_reloader=use_reloader)

