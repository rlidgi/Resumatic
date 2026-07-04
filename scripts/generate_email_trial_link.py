"""Generate a signed mass-email 10-day trial checkout link.

Usage:
  python scripts/generate_email_trial_link.py
  python scripts/generate_email_trial_link.py --campaign email-trial-jun-2026
  python scripts/generate_email_trial_link.py --base-url https://resumaticai.com
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, build_email_trial_checkout_url, generate_email_trial_invite_token


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate a signed 10-day email trial checkout link.')
    parser.add_argument('--campaign', default='', help='Campaign name stored in Stripe metadata')
    parser.add_argument('--trial-days', type=int, default=10, help='Trial length in days (default: 10)')
    parser.add_argument('--base-url', default='', help='Site base URL (default: PUBLIC_SITE_URL or https://resumaticai.com)')
    parser.add_argument('--short', action='store_true', help='Also print /go/email-trial?invite=... shortcut URL')
    args = parser.parse_args()

    with app.app_context():
        token = generate_email_trial_invite_token(
            campaign=args.campaign,
            trial_days=args.trial_days,
            waive_upfront_fee=True,
        )
        checkout_url = build_email_trial_checkout_url(token, base_url=args.base_url)
        print('Mass-email trial link (use this in your email):')
        print(checkout_url)
        if args.short:
            root = (args.base_url or os.getenv('PUBLIC_SITE_URL') or 'https://resumaticai.com').strip().rstrip('/')
            print('\nShortcut URL:')
            print(f'{root}/go/email-trial?invite={token}')


if __name__ == '__main__':
    main()
