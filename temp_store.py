import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_TTL_SECONDS = int(os.getenv('TEMP_STORE_TTL_SECONDS', '21600'))  # 6 hours


def _base_dir() -> Path:
    # Keep it within the app root by default.
    root = os.getenv('TEMP_STORE_DIR')
    if root and str(root).strip():
        return Path(root).expanduser().resolve()
    return (Path(__file__).resolve().parent / 'temp_store').resolve()


def _path_for(kind: str, token: str) -> Path:
    safe_kind = ''.join(c for c in str(kind) if c.isalnum() or c in ('-', '_'))[:40] or 'data'
    safe_token = ''.join(c for c in str(token) if c.isalnum() or c in ('-', '_'))[:80]
    return _base_dir() / safe_kind / f"{safe_token}.json"


def save_payload(kind: str, payload: Dict[str, Any], *, token: Optional[str] = None) -> str:
    """Persist a JSON-serializable payload server-side and return its token."""
    token = token or str(uuid.uuid4())
    path = _path_for(kind, token)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        'created_at': int(time.time()),
        'payload': payload,
    }

    tmp = path.with_suffix('.json.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.replace(path)
    return token


def load_payload(kind: str, token: str, *, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> Optional[Dict[str, Any]]:
    """Load a payload by token; returns None if missing/expired."""
    if not token:
        return None
    path = _path_for(kind, token)
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        created_at = int(data.get('created_at') or 0)
        if created_at and ttl_seconds > 0:
            if int(time.time()) - created_at > int(ttl_seconds):
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
                return None
        payload = data.get('payload')
        return payload if isinstance(payload, dict) else None
    except FileNotFoundError:
        return None
    except Exception:
        return None


def delete_payload(kind: str, token: str) -> None:
    if not token:
        return
    path = _path_for(kind, token)
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
