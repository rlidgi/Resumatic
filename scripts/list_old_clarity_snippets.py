import glob
import os


def main() -> int:
    templates_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
    paths = sorted(glob.glob(os.path.join(templates_root, "**", "*.html"), recursive=True))

    include_needle = '{% include "_clarity.html" %}'
    inline_marker = '"sjihir10df"'

    remaining: list[str] = []
    for path in paths:
        if os.path.basename(path) == "_clarity.html":
            continue
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        if inline_marker in txt and include_needle not in txt:
            remaining.append(os.path.relpath(path, os.path.dirname(templates_root)).replace("\\", "/"))

    print("templates with inline Clarity (no include):", len(remaining))
    for p in remaining:
        print(" -", p)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
