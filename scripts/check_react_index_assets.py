import os
import re
import sys
from urllib.parse import urlparse


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INDEX_HTML = os.path.join(ROOT, "static", "react", "index.html")


ASSET_RE = re.compile(r"(?:src|href)=\"([^\"]+)\"")


def url_to_path(u: str) -> str | None:
    u = (u or "").strip()
    if not u:
        return None
    parsed = urlparse(u)
    path = parsed.path or ""
    # Only validate local static assets.
    if not path.startswith("/static/react/"):
        return None
    rel = path.lstrip("/")
    return os.path.join(ROOT, *rel.split("/"))


def main() -> int:
    if not os.path.exists(INDEX_HTML):
        print(f"ERROR: missing {INDEX_HTML}")
        return 2

    html = open(INDEX_HTML, "r", encoding="utf-8").read()
    urls = [m.group(1) for m in ASSET_RE.finditer(html)]

    checked: list[tuple[str, str]] = []
    missing: list[tuple[str, str]] = []

    for u in urls:
        p = url_to_path(u)
        if not p:
            continue
        checked.append((u, p))
        if not os.path.exists(p):
            missing.append((u, p))

    if not checked:
        print("WARN: no /static/react/ asset references found in index.html")
        return 0

    if missing:
        print("ERROR: index.html references missing assets:")
        for u, p in missing:
            print(f"- {u} -> {p}")
        return 1

    print("OK: all assets referenced by static/react/index.html exist on disk")
    for u, p in checked:
        print(f"- {u} -> {os.path.relpath(p, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
