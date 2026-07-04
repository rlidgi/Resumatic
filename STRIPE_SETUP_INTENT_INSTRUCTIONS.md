# RBI e-mandate subscription flow (Stripe)

Indian subscribers must use a **subscription-owned pending SetupIntent** (not a standalone SetupIntent).

When a visitor is detected in India (`country code IN`), `/checkout` uses the embedded flow for **monthly and annual** plans only. **Trials** (standard 7-day and email 10-day) redirect to **Stripe hosted Checkout** with card + UPI for India.

## Server: create subscription with pending setup

POST `/stripe/create-subscription` (authenticated)

Body: `{ "plan_id": "trial_7d" | "monthly_10_95" | "annual_6_95" }`

Response:
```json
{
  "subscription_id": "sub_...",
  "pending_setup_intent_client_secret": "seti_..._secret_...",
  "status": "incomplete"
}
```

The server creates the subscription with:
- `payment_behavior: default_incomplete`
- `payment_settings.save_default_payment_method: on_subscription`
- `expand: ['pending_setup_intent']`
- `trial_period_days: 7` (trial plan only)

## Client: confirmSetup with Payment Element

```javascript
const resp = await fetch('/stripe/create-subscription', {
  method: 'POST',
  credentials: 'same-origin',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ plan_id: 'trial_7d' }),
});
const { pending_setup_intent_client_secret, subscription_id } = await resp.json();

const elements = stripe.elements({ clientSecret: pending_setup_intent_client_secret });
elements.create('payment').mount('#payment-element');

await stripe.confirmSetup({
  elements,
  confirmParams: {
    return_url: 'https://yourdomain.com/checkout/subscription-confirm?subscription_id=' + subscription_id,
  },
});
```

Then POST `/stripe/complete-subscription` with `{ "subscription_id": "sub_..." }` if the user was not redirected for 3DS.

## Webhook

Add `setup_intent.succeeded` to your Stripe webhook endpoint.

## Entry points

- `/checkout?plan=trial_7d` or `trial_10d_email` — Stripe Checkout redirect (RBI-safe subscription mode)
- `/checkout?plan=monthly_10_95` or `annual_6_95` — India: embedded SetupIntent; elsewhere: Payment Link / Checkout
- `/go/trial` — redirects to `/checkout?plan=trial_7d`

## Mass-email 10-day trial

Generate a signed link (requires production `FLASK_SECRET_KEY`):

```bash
python scripts/generate_email_trial_link.py --campaign email-trial-jun-2026
```

Email URL format:

```
https://resumaticai.com/checkout?plan=trial_10d_email&invite=SIGNED_TOKEN
```

India users get the same Stripe Checkout subscription flow as the standard trial on `/plans` (card + UPI, billing address required).

## Deprecated

`POST /stripe/create-setup-intent` returns HTTP 410. Do not use standalone SetupIntents for Indian recurring billing.
