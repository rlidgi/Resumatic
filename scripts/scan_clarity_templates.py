import glob
import os


def main() -> int:
    templates_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
    paths = sorted(glob.glob(os.path.join(templates_root, "**", "*.html"), recursive=True))

    needle = "https://www.clarity.ms/tag/"
    include_needle = '{% include "_clarity.html" %}'
    extends_base_needle = '{% extends "base.html" %}'

    missing: list[str] = []
    for path in paths:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        if needle not in txt and include_needle not in txt and extends_base_needle not in txt:
            missing.append(os.path.relpath(path, os.path.dirname(templates_root)).replace("\\", "/"))

    print("templates total:", len(paths))
    print("missing clarity:", len(missing))
    for p in missing:
        print(" -", p)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
