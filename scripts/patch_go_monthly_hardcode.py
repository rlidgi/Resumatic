from __future__ import annotations

from pathlib import Path

NEW_URL = "https://buy.stripe.com/cNi8wJ4ko0cTewq1cD7Vm09"


def main() -> int:
    path = Path(__file__).resolve().parents[1] / "app.py"
    text = path.read_text(encoding="utf-8", errors="replace")

    start = text.find('@app.route("/go/monthly")')
    if start < 0:
        raise SystemExit("ERROR: /go/monthly route start not found")

    marker = '\n\nCANCELLATION_FEEDBACK_FILE = "cancellation_feedback.json"'
    end = text.find(marker, start)
    if end < 0:
        raise SystemExit("ERROR: cancellation marker not found after /go/monthly")

    new_block = (
        '@app.route("/go/monthly")\n'
        '@login_required\n'
        'def go_monthly_payment_link():\n'
        '    """Logged-in-only redirect to the Stripe Monthly Payment Link."""\n'
        f'    return redirect("{NEW_URL}", code=303)\n'
    )

    updated = text[:start] + new_block + text[end:]
    path.write_text(updated, encoding="utf-8", newline="\n")

    print("WROTE: updated /go/monthly to hardcoded link")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
