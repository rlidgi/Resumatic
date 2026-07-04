"""Run an end-to-end Stripe subscription creation test using the Flask app test client.

This script:
- Creates a temporary user and logs in via the app's /login endpoint.
- Calls POST /stripe/create-subscription with plan_id=trial_7d.
- Prints the JSON response.

WARNING: This will use STRIPE_SECRET_KEY from your environment (.env) and may create real Stripe objects.
"""
import os
import sys
import uuid
import time
import json

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, User, add_user, users

TEST_EMAIL = f"e2e_test_{int(time.time())}@resumaticai.com"
TEST_PASSWORD = "TestPass123!"

print("Creating temporary user:", TEST_EMAIL)
user_id = f"email_{uuid.uuid4().hex[:16]}"
user = User(user_id, "E2E Test", TEST_EMAIL, is_new=True, email_verified=True)
user.set_password(TEST_PASSWORD)
add_user(user)

with app.test_client() as c:
    # Login
    print("Logging in via /login ...")
    resp = c.post('/login', data={'action': 'login', 'email': TEST_EMAIL, 'password': TEST_PASSWORD}, follow_redirects=True)
    print('Login status_code:', resp.status_code)
    # Now create subscription
    print('Creating subscription (trial_7d) ...')
    sub_resp = c.post('/stripe/create-subscription', json={'plan_id': 'trial_7d'})
    print('Create-subscription status:', sub_resp.status_code)
    try:
        print(json.dumps(sub_resp.get_json(), indent=2))
    except Exception:
        print('Non-json response:')
        print(sub_resp.data.decode('utf-8'))

print('Done')
