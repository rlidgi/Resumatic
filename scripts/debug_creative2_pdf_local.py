import json
import sys
import urllib.request
from pathlib import Path

# Ensure the repo root (where app.py lives) is importable when running from scripts/.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Generates a signed Flask session cookie containing:
# - a logged-in admin user (via flask-login's session keys)
# - template_data with a long Creative2 resume
# Then calls the running local server's /api/template-pdf/creative2 endpoint and saves the PDF.


def build_long_resume_structured() -> dict:
    long_bullets = (
        "Led cross-functional initiatives spanning product, engineering, and operations; "
        "improved reliability, reduced cycle time, and standardized delivery practices across teams.\n"
        "Built dashboards and alerting, implemented incident response playbooks, and partnered with stakeholders "
        "to translate ambiguous requirements into measurable milestones.\n"
        "Optimized data pipelines and performance hotspots; conducted root-cause analysis and implemented durable fixes."
    )

    experience = []
    for i in range(1, 10):
        experience.append(
            {
                "title": f"Senior Software Engineer {i}",
                "company": f"Example Company {i}",
                "location": "Remote",
                "dates": f"202{i}-01 – 202{i}-12",
                "description": long_bullets,
            }
        )

    education = []
    for i in range(1, 5):
        education.append(
            {
                "school": f"Example University {i}",
                "degree": "B.S.",
                "field": "Computer Science",
                "dates": f"201{i} – 201{i+1}",
                "location": "CA",
            }
        )

    return {
        "name": "Alex Candidate",
        "title": "Software Engineer",
        "summary": (
            "Full-stack engineer with experience building reliable web products and internal tools. "
            "Strong focus on performance, maintainability, and clear stakeholder communication."
        ),
        "phone": "(555) 555-5555",
        "email": "alex.candidate@example.com",
        "location": "Los Angeles, CA",
        "website": "https://example.com",
        "skills": [
            "Python",
            "TypeScript",
            "React",
            "Flask",
            "PostgreSQL",
            "Azure",
            "CI/CD",
            "Playwright",
            "Monitoring",
            "Testing",
        ],
        "experience": experience,
        "education": education,
        "projects": [
            {
                "name": "Example Project",
                "role": "Owner",
                "dates": "2024",
                "description": "Built a portfolio project demonstrating multi-page PDF export and robust pagination rules.",
            }
        ],
    }


def main() -> int:
    # Import the Flask app so we can generate a correctly signed session cookie.
    import app as appmod

    flask_app = appmod.app

    # Use the existing admin user ID from the running server's Azure-backed user profile.
    admin_user_id = "108278720993144058808"

    structured_resume = build_long_resume_structured()

    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = admin_user_id
            sess["_fresh"] = True
            sess["template_data"] = {
                "structured_resume": structured_resume,
                "template_name": "creative2",
                "revised_resume": "",
                "source_revision_id": "",
            }

        # Make a request so Flask writes the session into the client cookie jar.
        client.get("/")

        session_cookie = None
        try:
            # Flask test client stores cookies in a CookieJar.
            for cookie in client._cookies.values():
                # cookie is a dict keyed by (domain, path, name)
                pass
        except Exception:
            pass

        # Robust extraction from Werkzeug test client cookies
        try:
            # client.get_cookie is available in newer Werkzeug.
            c = client.get_cookie("session")
            if c:
                session_cookie = c.value
        except Exception:
            session_cookie = None

        if not session_cookie:
            # Fall back to manual cookie jar inspection
            try:
                jar = getattr(client, "cookie_jar", None)
                if jar is not None:
                    for c in jar:
                        if getattr(c, "name", "") == "session":
                            session_cookie = getattr(c, "value", None)
                            break
            except Exception:
                session_cookie = None

        if not session_cookie:
            print("ERROR: Could not extract Flask session cookie from test client.")
            return 2

    url = "http://127.0.0.1:5000/api/template-pdf/creative2?fontScale=1&paragraphGapPx=0&spacingScale=1&debug=1"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/pdf",
            "Cookie": f"session={session_cookie}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            status = getattr(resp, "status", None) or 200
            ct = resp.headers.get("content-type", "")
            body = resp.read()
    except Exception as e:
        print(f"ERROR: Request failed: {type(e).__name__}: {e}")
        return 3

    out_path = "temp_store/creative2-debug.pdf"
    try:
        import os

        os.makedirs("temp_store", exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(body)
    except Exception as e:
        print(f"ERROR: Failed writing {out_path}: {type(e).__name__}: {e}")
        return 4

    print(json.dumps({"status": status, "content_type": ct, "bytes": len(body), "saved": out_path}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
