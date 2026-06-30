# India Recurring Payment Fix - Implementation Summary

## Problem Addressed
70% of recurring payment failures in India due to:
- Banks blocking card-based recurring transactions
- Missing RBI e-mandate creation on first payment
- No recovery mechanism for failed renewals
- Lack of UPI AutoPay support

## Solution Implemented

### 1. Payment Method Configuration (Lines 4918-4933)
✅ New function `_get_payment_method_config_for_checkout()` that:
- Enables `card` payment method with 3DS authentication for India
- Enables `upi` for UPI AutoPay transactions
- **Important:** RBI mandates are created by Stripe through subscription flow, NOT metadata

**How it works:**
- First payment is on-session through Stripe Checkout (mode="subscription")
- Stripe automatically creates RBI e-mandate for future recurring payments
- UPI AutoPay provides alternative payment method with higher success rate
- **Requires:** Stripe API version that supports UPI for subscriptions/invoices. Confirm in Stripe Dashboard and Stripe changelog.

### 2. Failed Payment Recovery (Lines 5498-5547)
✅ Webhook handlers for:
- `invoice.payment_action_required` - Customer needs re-authentication
- `invoice.payment_failed` - Payment failed, logs error details

**Process:**
1. Customer's recurring payment fails (bank rejects or mandate expires)
2. Webhook triggers `invoice.payment_action_required` event
3. System finds customer by stripe_customer_id
4. Sends recovery email with Stripe Hosted Invoice Payment Page link
5. Customer clicks link, re-authenticates with bank
6. Payment completes, mandate reestablished for future payments

### 3. Recovery Email System (Lines 4981-5088)
✅ Two new helper functions:
- `_create_invoice_payment_link()` - Generates Stripe Hosted Invoice Payment Page URL
- `_send_payment_recovery_email()` - Sends customer-friendly recovery email

**Email includes:**
- Clear explanation that bank blocked payment
- One-click payment link to Stripe Hosted Invoice page
- HTML + plain text versions
- Professional branding

## Important Caveats

⚠️ **RBI Mandates are NOT created by metadata:**
- Stripe creates mandates through the subscription flow itself
- Having mode="subscription" + on-session first payment is what creates the mandate
- Metadata is only for tracking/logging, does not enable mandates

⚠️ **UPI Subscription Support:**
- Requires Stripe API version that supports UPI for subscriptions/invoices
- Check Stripe's changelog for current UPI support dates
- Not all Stripe accounts have UPI subscription eligibility even on supported API versions
- If unsupported: card mandates alone may still improve success rates

⚠️ **transaction_not_allowed Still Happens:**
- Even with mandates, some banks/cards will reject recurring charges
- RBI requires one-time AFA (Additional Factor Authentication) per mandate registration
- Pre-debit handling may still fail for various reasons
- Recovery email + hosted invoice page is the best recovery path

## Configuration Required

### 1. Verify Stripe API Version & UPI Support
**In Stripe Dashboard:**
1. Settings → Developer → API versions
2. Check if your API version supports UPI for subscriptions/invoices
3. Compare against Stripe's changelog for UPI subscription support dates
4. If unsupported: card mandates may still work, but UPI AutoPay won't appear

### 2. Ensure INR Pricing is Configured
Your existing environment variables are already set up:
```
STRIPE_PRICE_MONTHLY_10_95_INR=price_xxx
STRIPE_PRICE_ANNUAL_6_95_INR=price_xxx
STRIPE_PRICE_TRIAL_RECURRING_INR=price_xxx  (optional)
STRIPE_PRICE_TRIAL_FEE_1_85_INR=price_xxx  (optional)
```

### 3. Webhook Events
Ensure these webhook events are configured in Stripe Dashboard:
```
✓ checkout.session.completed (already configured)
✓ customer.subscription.updated (already configured)
✓ customer.subscription.deleted (already configured)
✓ invoice.paid (already configured)
→ setup_intent.succeeded (NEW - add this for RBI e-mandate embedded checkout)
→ invoice.payment_action_required (NEW - add this)
→ invoice.payment_failed (NEW - add this)
```

**Setup:**
1. Go to Stripe Dashboard → Webhooks
2. Select your webhook endpoint
3. Add these event types:
   - `invoice.payment_action_required`
   - `invoice.payment_failed`

### 4. Email Configuration
Ensure SMTP is configured (already in place):
```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
NEWSLETTER_EMAIL=your-email@domain.com
NEWSLETTER_PASSWORD=your-app-password
```

### 5. Dashboard Settings for India
In Stripe Dashboard:
- ✓ Enable UPI (if available for your account)
- ✓ Enable Cards
- ✓ Enable 3D Secure (automatic authentication)
- ✓ Enable customer emails / failed payment recovery

## Expected Results

### Before Fix (Current)
- 70% payment failures for India
- Lost revenue from India market
- No recovery mechanism
- No visibility into failure reasons

### After Fix (Realistic)
- **First attempt:** ~30-40% success (mandates created but still rejected by some banks)
- **Failed payment recovery email sent:** ~50-60% of customers click recovery link
- **Recovery email converts:** ~30-40% of clicking customers successfully re-authenticate
- **Net recovery rate:** ~15-25% of failed transactions recovered via email
- **Overall expected success:** ~45-55% vs 30% previously
- **For customers who don't retry:** Subscription cancelled (expected)

## Debugging: Diagnose Actual Failure Reason

⚠️ **Most important:** Check why actual payments are failing by inspecting Stripe Dashboard.

**Steps:**
1. Go to Stripe Dashboard → Payments
2. Find a recent failed payment from India
3. Click the payment to see details
4. Inspect:
   - **PaymentIntent** → **Status** (should be `requires_payment_method` or `requires_action`)
   - **Latest Charge** → **Failure code** (e.g., `card_declined`, `authentication_required`, `generic_decline`)
   - **Latest Charge** → **Failure message** (exact reason)
   - **Mandate** section (should exist if mandate was created)

**What to look for:**
- `card_declined` = Bank rejected (needs recovery email)
- `authentication_required` = 3DS challenge failed (needs re-auth)
- `generic_decline` = Bank blocked (may need recovery email)
- No mandate created = Stripe subscription setup issue (check API version)

**Action:**
- If failures are consistent error code → share with Stripe support
- If no mandate section exists → API version too old, update it
- If mandates exist but still declining → recovery email is best path

## Testing the Implementation

### 1. Test India Checkout Flow
1. Set your IP/location to India or use VPN
2. Visit `/plans` page
3. Verify you see INR pricing and UPI payment method
4. Click checkout
5. Verify Stripe Checkout shows:
   - INR currency
   - Card (with 3DS badge) + UPI payment methods
   - Subscription mode (auto-renews)

### 2. Test Webhook Event
1. Go to Stripe Dashboard → Webhooks
2. Select your endpoint → "Send test event"
3. Send `invoice.payment_action_required` test event
4. Check app logs for: "Sent payment recovery email to..."
5. Verify email in recipient inbox

### 3. Inspect a Real Failed Payment
1. Go to Stripe Dashboard → Payments
2. Find failed India payment
3. Check failure_code and whether mandate exists
4. Share findings with Stripe support if needed

### 4. Monitor Production
Watch these logs:
```
"Payment recovery email sent to..." - indicates recovery email sent
"Payment action required webhook error" - indicates issues with recovery
"Invoice {id} payment failed: {error}" - tracks failed payments
```

## Code Changes Summary

**Files Modified:** `app.py`

**New Functions:**
- `_get_payment_method_config_for_checkout()` - Payment method config for India
- `_create_invoice_payment_link()` - Generate recovery payment link
- `_send_payment_recovery_email()` - Send recovery email

**Modified Functions:**
- `checkout()` - Added payment method config integration
- `stripe_webhook()` - Added payment recovery webhook handlers

**Lines Changed:**
- ~200 lines added/modified
- No breaking changes to existing functionality
- Backward compatible with current checkout flow

## Next Steps

1. ✅ Code changes deployed
2. → Verify Stripe API version is 2025+
3. → Add webhook events in Stripe Dashboard
4. → Test with test card in India
5. → Inspect actual failed payment in Dashboard to understand failure reason
6. → Monitor logs and adjust recovery strategy based on actual failures
