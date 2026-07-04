"""Generate a signed paid-cancel reinstatement offer link ($3.99 next month).

Usage:
  python scripts/generate_reinstate_offer_link.py --email user@example.com
  python scripts/generate_reinstate_offer_link.py --email user@example.com --user-id email_abc --subscription-id sub_123
  python scripts/generate_reinstate_offer_link.py --email user@example.com --base-url https://resumaticai.com
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import stripe
from app import (
    app,
    generate_reinstate_paid_offer_token,
    _find_azure_user_profile_by_email,
    _get_stripe_subscription_id_from_azure,
    _find_stripe_customer_id_by_email,
)


def _latest_subscription_id(customer_id: str) -> str:
    if not customer_id:
        return ''
    try:
        res = stripe.Subscription.list(customer=customer_id, status='all', limit=10)
        for sub in list(getattr(res, 'data', []) or []):
            sid = str(getattr(sub, 'id', '') or '').strip()
            if sid:
                return sid
    except Exception:
        pass
    return ''


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate a signed reinstate-paid-offer link for a user.')
    parser.add_argument('--email', required=True, help='Account email address')
    parser.add_argument('--user-id', default='', help='Optional Azure user id override')
    parser.add_argument('--subscription-id', default='', help='Optional Stripe subscription id override')
    parser.add_argument('--base-url', default='', help='Site base URL (default: PUBLIC_SITE_URL or https://resumaticai.com)')
    args = parser.parse_args()

    email = str(args.email or '').strip().lower()
    if not email:
        print('Error: --email is required.', file=sys.stderr)
        sys.exit(1)

    with app.app_context():
        user_id = str(args.user_id or '').strip()
        subscription_id = str(args.subscription_id or '').strip()

        if not user_id or not subscription_id:
            prof = _find_azure_user_profile_by_email(email)
            if prof:
                if not user_id:
                    user_id = str(prof.get('PartitionKey') or prof.get('id') or '').strip()
                if not subscription_id:
                    subscription_id = str(prof.get('stripe_subscription_id') or '').strip()
                    if not subscription_id and user_id:
                        subscription_id = _get_stripe_subscription_id_from_azure(user_id)

        if (not user_id or not subscription_id) and _find_stripe_customer_id_by_email:
            stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
            cid = _find_stripe_customer_id_by_email(email)
            if cid:
                try:
                    cust = stripe.Customer.retrieve(cid)
                    if not user_id:
                        user_id = str((getattr(cust, 'metadata', None) or {}).get('user_id') or '').strip()
                except Exception:
                    pass
                if not subscription_id:
                    subscription_id = _latest_subscription_id(cid)

        if not user_id:
            print(f'Error: could not resolve user id for {email}.', file=sys.stderr)
            print('Tip: pass --user-id and --subscription-id from Admin → Registered Users or Stripe.', file=sys.stderr)
            sys.exit(1)
        if not subscription_id:
            print(f'Error: could not resolve subscription id for {email}.', file=sys.stderr)
            print('Tip: pass --subscription-id from the user profile or Stripe.', file=sys.stderr)
            sys.exit(1)

        token = generate_reinstate_paid_offer_token(
            user_id=user_id,
            subscription_id=subscription_id,
            email=email,
        )
        root = (args.base_url or os.getenv('PUBLIC_SITE_URL') or 'https://resumaticai.com').strip().rstrip('/')
        url = f'{root}/billing/reinstate-paid-offer?token={token}'

        print('Reinstate paid offer link:')
        print(url)
        print()
        print(f'User id: {user_id}')
        print(f'Subscription id: {subscription_id}')
        print(f'Email: {email}')


if __name__ == '__main__':
    main()
