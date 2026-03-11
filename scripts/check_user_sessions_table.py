import os
import sys
from datetime import datetime, timezone
import uuid


def main() -> int:
    # Ensure repo root is on sys.path so we can import app.py from scripts/.
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # Importing app loads .env via load_dotenv() and provides get_users_table_client.
    import app  # noqa: F401

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/check_user_sessions_table.py <user_id> [--insert] [--simulate-audit]")
        print("  python scripts/check_user_sessions_table.py --all [--limit N]")
        return 2

    arg1 = str(sys.argv[1]).strip()
    insert = any(a.strip().lower() == '--insert' for a in sys.argv[2:])
    simulate_audit = any(a.strip().lower() == '--simulate-audit' for a in sys.argv[2:])
    list_all = arg1.strip().lower() == '--all'

    limit = 50
    for i, a in enumerate(sys.argv[2:], start=2):
        if str(a).strip().lower() == '--limit' and i + 1 < len(sys.argv):
            try:
                limit = int(sys.argv[i + 1])
            except Exception:
                limit = 50
    if limit < 1:
        limit = 1
    if limit > 2000:
        limit = 2000

    user_id = '' if list_all else arg1
    user_id = str(user_id).strip()
    if not list_all and not user_id:
        print("Missing user_id")
        return 2

    tc = app.get_users_table_client(create_if_missing=False)

    if list_all:
        # Try server-side filter; fall back to client-side scan.
        rows = []
        try:
            pager = tc.query_entities("record_type eq 'session'")
        except Exception:
            pager = tc.list_entities()
        for e in pager:
            try:
                if str(e.get('record_type') or '') != 'session':
                    continue
                rows.append(dict(e))
            except Exception:
                continue
            if limit and len(rows) >= limit:
                break

        rows.sort(key=lambda r: str(r.get('login_at') or ''), reverse=True)
        print("Session rows sample:")
        print("Count (sampled):", len(rows))
        for r in rows[:limit]:
            print(
                "-",
                str(r.get('PartitionKey') or ''),
                str(r.get('RowKey') or ''),
                str(r.get('login_at') or ''),
                str(r.get('logout_at') or ''),
                str(r.get('login_method') or ''),
            )
        return 0

    # Per-user mode
    if simulate_audit:
        # Run the exact code path used by real logins in a request context.
        class _U:
            pass

        u = _U()
        u.id = user_id
        u.email = "manual@test.local"
        u.name = "Manual Test"
        try:
            with app.app.test_request_context('/'):
                app._audit_login_start(u, login_method='simulate_audit')
            print("Simulated _audit_login_start executed.")
        except Exception as e:
            print("FAILED to simulate _audit_login_start:", type(e).__name__, str(e))

    if insert:
        now = datetime.now(timezone.utc)
        rk = f"session_manual_{now.strftime('%Y%m%dT%H%M%S%f')}_{uuid.uuid4().hex}"
        entity = {
            'PartitionKey': user_id,
            'RowKey': rk,
            'record_type': 'session',
            'audit_id': 'manual',
            'email': 'manual@test.local',
            'login_at': now.isoformat(),
            'last_activity_at': now.isoformat(),
            'logout_at': '',
            'login_method': 'manual_insert',
        }
        try:
            # Use the same UpdateMode enum as app.py.
            tc.upsert_entity(entity, mode=app.UpdateMode.REPLACE)
            print("Inserted test session row:", rk)
        except Exception as e:
            print("FAILED to insert test session row:", type(e).__name__, str(e))

    q = "PartitionKey eq '{}'".format(user_id)
    rows = list(tc.query_entities(q))
    row_keys = sorted({str(r.get("RowKey") or "") for r in rows})

    session_row_keys = [rk for rk in row_keys if rk.startswith("session_")]
    session_count_by_record_type = sum(
        1 for r in rows if str(r.get("record_type") or "") == "session"
    )

    print("PartitionKey:", user_id)
    print("Total rows:", len(rows))
    print("Has profile row:", "profile" in row_keys)
    print("Session rows (RowKey startswith session_):", len(session_row_keys))
    print("Session rows (record_type == session):", session_count_by_record_type)
    if session_row_keys:
        print("Session RowKeys (first 25):")
        for rk in session_row_keys[:25]:
            print("  ", rk)
    else:
        # Print a small sample of row keys for debugging.
        print("RowKeys sample (first 30):")
        for rk in row_keys[:30]:
            print("  ", rk)

    # Also print profile last login markers, if present.
    try:
        prof = tc.get_entity(partition_key=user_id, row_key="profile")
        print("Profile.last_login_at:", prof.get("last_login_at", ""))
        print("Profile.last_session_rowkey:", prof.get("last_session_rowkey", ""))
    except Exception as e:
        print("Could not load profile row:", type(e).__name__, str(e))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
