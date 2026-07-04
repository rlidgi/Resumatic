import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any


EMAIL_AUDIT_FILE = "sent_email_log.jsonl"
_EMAIL_AUDIT_LOCK = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def record_email_event(
    *,
    email_type: str,
    recipient: str,
    subject: str,
    status: str,
    source: str = "system",
    metadata: dict[str, Any] | None = None,
    error: str = "",
) -> dict[str, Any]:
    entry = {
        "id": uuid.uuid4().hex,
        "timestamp": _utc_now_iso(),
        "email_type": str(email_type or "").strip() or "unknown",
        "recipient": _normalize_email(recipient),
        "subject": str(subject or "").strip(),
        "status": str(status or "").strip().lower() or "unknown",
        "source": str(source or "").strip() or "system",
        "error": str(error or "").strip(),
        "metadata": metadata if isinstance(metadata, dict) else {},
    }

    line = json.dumps(entry, ensure_ascii=False)
    with _EMAIL_AUDIT_LOCK:
        with open(EMAIL_AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    return entry


def read_email_events(limit: int = 250) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    if not os.path.exists(EMAIL_AUDIT_FILE):
        return []

    events: list[dict[str, Any]] = []
    with _EMAIL_AUDIT_LOCK:
        with open(EMAIL_AUDIT_FILE, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                if isinstance(payload, dict):
                    events.append(payload)

    events.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return events[:limit]
