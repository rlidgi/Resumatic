# Production Setup (Azure + Stripe Live Mode)

This project runs a Flask app (`app.py`) with Stripe subscriptions and Azure Table Storage.

## 1) Safety first (rotate leaked secrets)

If any secrets were ever pasted into chat, committed, or shared, rotate them before going live:

- Stripe: rotate **secret keys** and create a new **webhook signing secret** for the production webhook endpoint.
- OpenAI: rotate the API key.
- Google/Facebook OAuth: rotate client secrets if exposed.
- Azure Storage: rotate connection string/key if exposed.

## 2) Choose your Azure hosting type

This repo includes both:

- `startup.sh` + `Procfile` (typical for Linux App Service / container-style startup)
- `web.config` (typical for Windows App Service + wfastcgi)

If you are on **Linux App Service**, set the Startup Command to run `startup.sh` (or let your deployment pipeline invoke it).
If you are on **Windows App Service**, `web.config` is used and `startup.sh` may be ignored.

## 3) Azure App Service configuration (recommended)

In App Service → **Configuration** → **Application settings** set these (values are examples):

### Core app
- `FLASK_SECRET_KEY` = strong random (required)
- `SCM_DO_BUILD_DURING_DEPLOYMENT` = `true` (already in `.deployment`)
- `WEBSITES_PORT` = `8000` (Linux) or set `PORT` if your platform uses that

### Stripe (LIVE mode)
Set all Stripe values to **live** keys/IDs (not `sk_test` / `price_test` / `buy.stripe.com/test_...`).

- `STRIPE_SECRET_KEY` = `sk_live_...`
- `STRIPE_PUBLISHABLE_KEY` = `pk_live_...` (required for India embedded checkout / Payment Element)
- `STRIPE_WEBHOOK_SECRET` = `whsec_...` (from the production webhook endpoint)
- `STRIPE_PRICE_MONTHLY_10_95` = `price_...` (live price)
- `STRIPE_PRICE_ANNUAL_6_95` = `price_...` (live price)
- `STRIPE_PRICE_TRIAL_FEE_1_85` = `price_...` (live one-time price, optional)
- `STRIPE_PRICE_TRIAL_RECURRING` = `price_...` (optional; otherwise monthly price is used)

Optional (used as fallback):
- `STRIPE_PAYMENTLINK_MONTHLY_10_95` = `https://buy.stripe.com/...` (live)
- `STRIPE_PAYMENTLINK_ANNUAL_6_95` = `https://buy.stripe.com/...` (live)
- `STRIPE_PAYMENTLINK_TRIAL_7D` = `https://buy.stripe.com/...` (live)
	- (Legacy supported) `STRIPE_PAYMENTLINK_TRIAL_14D`

Retention offer (cancel-flow incentive):
- `STRIPE_COUPON_RETENTION` = coupon ID (e.g. `retention_50`) for Checkout Session API (classic billing only)
- `STRIPE_PROMO_CODE_RETENTION` = promotion code string (e.g. `RETENTION50`) for Payment Links
- For flexible billing, the cancel-page "Claim 50% off" uses customer balance credit (no env var needed; optional `STRIPE_RETENTION_CREDIT_CENTS` to override the auto-calculated amount)  

### Storage
- `AZURE_STORAGE_CONNECTION_STRING` = production storage account connection string

### OpenAI
- `OPENAI_API_KEY` = production key

### OAuth (ensure production redirect URIs)
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `FACEBOOK_APP_ID`
- `FACEBOOK_APP_SECRET`

## 4) Stripe production webhook

In Stripe Dashboard (Live mode) create a webhook endpoint:

- Endpoint URL: `https://<your-domain>/stripe/webhook`

Select events that match your implementation. Typical subscription setup uses:

- `checkout.session.completed`
- `setup_intent.succeeded` (required for India RBI e-mandate embedded checkout)
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `customer.subscription.trial_will_end` (optional; deferred capture is used for authorization-hold trials)
- `payment_intent.amount_capturable_updated` (activates trial after card authorization hold)
- `payment_intent.succeeded` (optional; records hold capture timestamp)
- `invoice.paid`
- `invoice.payment_failed`
- `invoice.payment_action_required` (India payment recovery emails)

### Trial authorization hold (standard 7-day trial)

The `/checkout?plan=trial_7d` flow places a **manual-capture** hold for the monthly plan amount (default $10.95) without charging the card. After the hold is authorized, the app creates a **trialing** Stripe subscription. The hold is captured on the scheduled capture day (default day 6 of 7) and a customer balance credit is applied toward the first invoice. Cancel before capture to release the hold; cancel on the final trial day after capture for a refund.

Optional env vars:

- `TRIAL_HOLD_DAYS` = `7` (default)
- `TRIAL_CAPTURE_DAYS_BEFORE_END` = `1` (capture on day 6 when hold is 7 days)
- `STRIPE_TRIAL_DEPOSIT_CENTS` = override hold amount in cents (default: monthly price)

Copy the signing secret into `STRIPE_WEBHOOK_SECRET`.

## 5) Go-live validation checklist

1) Deploy to production slot/app.
2) Visit `/plans` → purchase **monthly** with a real card (or Stripe test card only if still in test mode).
3) Confirm you land on `checkout.stripe.com` and return to your app.
4) Confirm `/settings` shows correct:
	- Paid through
	- Next billing date
5) Confirm webhook logs show the checkout + subscription events arriving.
6) For trial: start `/checkout?plan=trial_7d`, confirm a pending hold (not a charge), cancel during trial and confirm the hold is released, or let trial end and confirm capture + first invoice.

## 6) Notes on billing-cycle alignment

Stripe can align subscription billing to a calendar day depending on your Stripe settings.
If Stripe returns `billing_cycle_anchor/start_date` without `current_period_end` for a brand-new subscription,
the app computes the end of the first period as `start + 1 month` (calendar-accurate).

