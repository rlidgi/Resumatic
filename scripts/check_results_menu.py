from __future__ import annotations

# Validates whether the Results page HTML contains the mobile menu + auth links.
# Run: .venv/Scripts/python.exe scripts/check_results_menu.py

import os
import sys


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from app import app  # noqa: E402


def main() -> None:
    with app.test_client() as client:
        # Seed a minimal results flow (POST -> redirect -> GET)
        resp = client.post(
            "/results",
            data={
                "resume": "Test resume\nExperience: Example\nSkills: Python",
                "jobDescription": "",
            },
            follow_redirects=True,
        )

        html = resp.get_data(as_text=True)
        print("status=", resp.status_code)
        print("html_len=", len(html))

        checks = [
            "id=\"mobileMenu\"",
            "id=\"menuButton\"",
            "Sign In",
            "Free Account",
        ]
        for term in checks:
            print(f"contains({term!r})=", term in html)

        # Print a small snippet for visual confirmation
        idx = html.find("Free Account")
        if idx != -1:
            start = max(0, idx - 250)
            end = min(len(html), idx + 250)
            print("\n--- snippet around 'Free Account' ---")
            print(html[start:end])


if __name__ == "__main__":
    main()
