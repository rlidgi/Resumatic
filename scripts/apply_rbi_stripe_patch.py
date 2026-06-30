"""One-off patch: RBI e-mandate Stripe flow updates."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app.py"
CHECKOUT = ROOT / "templates" / "checkout.html"
INSTRUCTIONS = ROOT / "STRIPE_SETUP_INTENT_INSTRUCTIONS.md"

HELPERS = '''

def _find_user_id_by_stripe_customer_id(customer_id: str) -> str:
    """Return Azure user id (PartitionKey) for a Stripe customer, or empty string."""
    cid = (customer_id or '').strip()
    if not cid:
        return ''
    try:
        table_client = get_users_table_client()
        for e in table_client.list_entities():
            if e.get('RowKey') != 'profile':
                continue
            if str(e.get('stripe_customer_id') or '') == cid:
                return str(e.get('PartitionKey') or '').strip()
    except Exception:
        pass
    return ''


def _persist_stripe_subscription_to_profile(user_id: str, sub, plan_id: str = '') -> None:
    """Persist Stripe subscription state to the user's Azure profile."""
    uid = str(user_id or '').strip()
    if not uid or not sub:
        return
    try:
        customer_id = str(getattr(sub, 'customer', '') or _stripe_obj_get(sub, 'customer', '') or '')
        sub_status = str(getattr(sub, 'status', '') or _stripe_obj_get(sub, 'status', '') or '').lower()
        sub_id = str(getattr(sub, 'id', '') or _stripe_obj_get(sub, 'id', '') or '')
        entity = {
            'PartitionKey': uid,
            'RowKey': 'profile',
            'is_paid': sub_status in ('active', 'trialing'),
            'plan_status': plan_id or str(getattr(sub, 'status', '') or _stripe_obj_get(sub, 'status', '') or ''),
            'stripe_customer_id': customer_id,
            'stripe_subscription_id': sub_id,
        }
        if sub_status == 'trialing' or _normalize_plan_id(plan_id) == 'trial_7d':
            entity['trial_used'] = True
            entity['trial_used_at'] = datetime.now(timezone.utc).isoformat()
        try:
            current_period_end = getattr(sub, 'current_period_end', None) or _stripe_obj_get(sub, 'current_period_end', None)
            trial_end = getattr(sub, 'trial_end', None) or _stripe_obj_get(sub, 'trial_end', None)
            ts = current_period_end or trial_end
            if ts:
                entity['paid_until'] = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
        except Exception:
            pass
        table_client = get_users_table_client()
        table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
    except Exception:
        pass


def _subscription_belongs_to_customer(subscription_id: str, customer_id: str) -> bool:
    """Return True if the subscription belongs to the given Stripe customer."""
    sid = (subscription_id or '').strip()
    cid = (customer_id or '').strip()
    if not sid or not cid or not _stripe_enabled():
        return False
    try:
        stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
        sub = stripe.Subscription.retrieve(sid)
        return str(getattr(sub, 'customer', '') or '') == cid
    except Exception:
        return False


def _handle_setup_intent_succeeded_webhook(setup_intent: dict) -> None:
    """Activate user access after RBI e-mandate SetupIntent succeeds."""
    customer_id = str(setup_intent.get('customer') or '').strip()
    if not customer_id or not _stripe_enabled():
        return
    user_id = _find_user_id_by_stripe_customer_id(customer_id)
    if not user_id:
        meta = setup_intent.get('metadata') or {}
        user_id = str(meta.get('user_id') or '').strip()
    if not user_id:
        return
    try:
        stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
        subs = stripe.Subscription.list(customer=customer_id, status='all', limit=10)
        sdata = list(getattr(subs, 'data', []) or [])
        if not sdata:
            return

        def _rank(sub):
            status = str(getattr(sub, 'status', '') or '').strip().lower()
            created = int(getattr(sub, 'created', 0) or 0)
            sr = 0
            if status == 'trialing':
                sr = 3
            elif status == 'active':
                sr = 2
            elif status == 'incomplete':
                sr = 1
            return (sr, created)

        best = sorted(sdata, key=_rank, reverse=True)[0]
        best_status = str(getattr(best, 'status', '') or '').strip().lower()
        if best_status not in ('trialing', 'active'):
            return
        plan_id = ''
        try:
            meta = getattr(best, 'metadata', None) or {}
            if isinstance(meta, dict):
                plan_id = str(meta.get('plan_id') or '').strip()
            else:
                plan_id = str(getattr(meta, 'plan_id', '') or '').strip()
        except Exception:
            plan_id = ''
        _persist_stripe_subscription_to_profile(user_id, best, plan_id=plan_id)
        logger.info(f"setup_intent.succeeded: persisted subscription for user {user_id}")
    except Exception as e:
        logger.warning(f"setup_intent.succeeded webhook handler error: {str(e)}")

'''

OLD_SETUP_INTENT = '''@app.route('/stripe/create-setup-intent', methods=['POST'])
def stripe_create_setup_intent():
    """Create a Stripe SetupIntent for the current user and return the `client_secret`.

    Frontend should confirm the SetupIntent (Payment Element or Card Element) and then
    call a server endpoint to create the subscription using the saved payment method.
    """
    if not getattr(current_user, 'is_authenticated', False):
        return jsonify({'error': 'authentication_required'}), 401
    if not _stripe_enabled():
        return jsonify({'error': 'stripe_not_configured'}), 400
    try:
        stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
        customer_id = _create_or_get_stripe_customer_for_user(current_user)
        if not customer_id:
            return jsonify({'error': 'customer_creation_failed'}), 500

        # Create a SetupIntent for off-session usage (saved for future recurring charges)
        si = stripe.SetupIntent.create(customer=customer_id, usage='off_session')
        client_secret = getattr(si, 'client_secret', '') or ''
        return jsonify({'client_secret': client_secret, 'customer_id': customer_id})
    except Exception as e:
        logger.exception('Error creating SetupIntent')
        return jsonify({'error': 'setup_intent_failed', 'message': str(e)}), 500
'''

NEW_SETUP_INTENT = '''@app.route('/stripe/create-setup-intent', methods=['POST'])
def stripe_create_setup_intent():
    """Deprecated for RBI e-mandate flows.

    Standalone SetupIntents do not register Indian e-mandates correctly.
    Use POST /stripe/create-subscription instead.
    """
    return jsonify({
        'error': 'deprecated',
        'message': 'Use /stripe/create-subscription for RBI-compliant e-mandate registration.',
    }), 410
'''

OLD_CREATE_SUB_START = '''@app.route('/stripe/create-subscription', methods=['POST'])
def stripe_create_subscription():
    """Create a subscription for the current user using a confirmed PaymentMethod.

    Expects JSON: { "plan_id": "trial_7d", "payment_method": "pm_..." }
    The payment method should have been confirmed client-side via SetupIntent.
    '''
OLD_CREATE_SUB_MID = '''        subscription_params = {
            'customer': customer_id,
            'items': [{'price': price_id, 'quantity': 1}],
            'payment_behavior': 'default_incomplete',
            'expand': ['pending_setup_intent'],
        }
'''
NEW_CREATE_SUB_START = '''@app.route('/stripe/create-subscription', methods=['POST'])
def stripe_create_subscription():
    """Create an incomplete subscription with pending SetupIntent (RBI e-mandate flow).

    Expects JSON: { "plan_id": "trial_7d" | "monthly_10_95" | "annual_6_95" }
    Returns subscription_id and pending_setup_intent_client_secret for confirmSetup.
    '''
NEW_CREATE_SUB_MID = '''        if plan_id not in ('trial_7d', 'monthly_10_95', 'annual_6_95'):
            return jsonify({'error': 'invalid_plan'}), 400

        user_id = str(getattr(current_user, 'id', '') or '')
        subscription_params = {
            'customer': customer_id,
            'items': [{'price': price_id, 'quantity': 1}],
            'payment_behavior': 'default_incomplete',
            'payment_settings': {'save_default_payment_method': 'on_subscription'},
            'expand': ['pending_setup_intent'],
            'metadata': {'plan_id': plan_id, 'user_id': user_id},
        }
'''

OLD_PENDING_CHECK = '''        try:
            pending_client_secret = getattr(pending, 'client_secret', '') or ''
        except Exception:
            pending_client_secret = ''

        # Persist minimal stripe_customer_id for lookup; full subscription persistence happens in completion endpoint
        try:
            table_client = get_users_table_client()
            entity = {
                'PartitionKey': str(getattr(current_user, 'id', '') or ''),
                'RowKey': 'profile',
                'stripe_customer_id': str(customer_id),
            }
            table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
        except Exception:
            pass

        return jsonify({'subscription_id': getattr(sub, 'id', ''), 'pending_setup_intent_client_secret': pending_client_secret, 'status': getattr(sub, 'status', '')})
'''

NEW_PENDING_CHECK = '''        try:
            pending_client_secret = getattr(pending, 'client_secret', '') or ''
        except Exception:
            pending_client_secret = ''
        if not pending_client_secret:
            return jsonify({'error': 'pending_setup_intent_missing'}), 500

        try:
            table_client = get_users_table_client()
            entity = {
                'PartitionKey': user_id,
                'RowKey': 'profile',
                'stripe_customer_id': str(customer_id),
            }
            table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
        except Exception:
            pass

        return jsonify({
            'subscription_id': getattr(sub, 'id', ''),
            'pending_setup_intent_client_secret': pending_client_secret,
            'status': getattr(sub, 'status', ''),
        })
'''

OLD_COMPLETE = '''    @app.route('/stripe/complete-subscription', methods=['POST'])
    def stripe_complete_subscription():
        """Finalize subscription after frontend confirms the pending SetupIntent.

        Expects JSON: { "subscription_id": "sub_..." }
        This will retrieve subscription, persist stripe ids to Azure profile, and return status.
        """
        if not getattr(current_user, 'is_authenticated', False):
            return jsonify({'error': 'authentication_required'}), 401
        if not _stripe_enabled():
            return jsonify({'error': 'stripe_not_configured'}), 400
        try:
            body = request.get_json(force=True) or {}
            subscription_id = str(body.get('subscription_id') or '').strip()
            if not subscription_id:
                return jsonify({'error': 'missing_parameters'}), 400

            stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
            sub = stripe.Subscription.retrieve(subscription_id, expand=['pending_setup_intent', 'latest_invoice.payment_intent', 'items.data.price'])

            # Persist Stripe ids and paid_until/trial flags
            try:
                customer_id = str(getattr(sub, 'customer', '') or '')
                table_client = get_users_table_client()
                entity = {
                    'PartitionKey': str(getattr(current_user, 'id', '') or ''),
                    'RowKey': 'profile',
                    'is_paid': True,
                    'plan_status': str(getattr(sub, 'status', '') or ''),
                    'stripe_customer_id': customer_id,
                    'stripe_subscription_id': str(getattr(sub, 'id', '') or ''),
                }
                # Mark trial used if present
                try:
                    # If trialing, mark trial_used
                    if str(getattr(sub, 'status', '') or '').lower() == 'trialing':
                        entity['trial_used'] = True
                        entity['trial_used_at'] = datetime.now(timezone.utc).isoformat()
                except Exception:
                    pass
                # paid_until from current_period_end or trial_end
                try:
                    current_period_end = getattr(sub, 'current_period_end', None)
                    trial_end = getattr(sub, 'trial_end', None)
                    ts = current_period_end or trial_end
                    if ts:
                        entity['paid_until'] = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
                except Exception:
                    pass
                table_client.upsert_entity(entity, mode=UpdateMode.MERGE)
            except Exception:
                pass

            return jsonify({'subscription_id': getattr(sub, 'id', ''), 'status': getattr(sub, 'status', '')})
        except Exception as e:
            logger.exception('Error completing subscription')
            return jsonify({'error': 'complete_failed', 'message': str(e)}), 500
'''

NEW_COMPLETE = '''@app.route('/stripe/complete-subscription', methods=['POST'])
def stripe_complete_subscription():
    """Finalize subscription after frontend confirms the pending SetupIntent."""
    if not getattr(current_user, 'is_authenticated', False):
        return jsonify({'error': 'authentication_required'}), 401
    if not _stripe_enabled():
        return jsonify({'error': 'stripe_not_configured'}), 400
    try:
        body = request.get_json(force=True) or {}
        subscription_id = str(body.get('subscription_id') or '').strip()
        if not subscription_id:
            return jsonify({'error': 'missing_parameters'}), 400

        stripe.api_key = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
        customer_id = _create_or_get_stripe_customer_for_user(current_user)
        if not customer_id or not _subscription_belongs_to_customer(subscription_id, customer_id):
            return jsonify({'error': 'subscription_not_found'}), 404

        sub = stripe.Subscription.retrieve(
            subscription_id,
            expand=['pending_setup_intent', 'latest_invoice.payment_intent', 'items.data.price'],
        )
        sub_status = str(getattr(sub, 'status', '') or '').lower()
        if sub_status not in ('trialing', 'active'):
            return jsonify({'error': 'subscription_not_ready', 'status': sub_status}), 400

        plan_id = ''
        try:
            meta = getattr(sub, 'metadata', None) or {}
            if isinstance(meta, dict):
                plan_id = str(meta.get('plan_id') or '').strip()
            else:
                plan_id = str(getattr(meta, 'plan_id', '') or '').strip()
        except Exception:
            plan_id = ''

        _persist_stripe_subscription_to_profile(str(getattr(current_user, 'id', '') or ''), sub, plan_id=plan_id)
        return jsonify({'subscription_id': getattr(sub, 'id', ''), 'status': getattr(sub, 'status', '')})
    except Exception as e:
        logger.exception('Error completing subscription')
        return jsonify({'error': 'complete_failed', 'message': str(e)}), 500
'''

CHECKOUT_INDIA_INSERT = '''    # India (RBI e-mandate): use embedded subscription + pending SetupIntent flow.
    if _stripe_enabled() and _is_india_pricing_region() and plan_id in ('trial_7d', 'monthly_10_95', 'annual_6_95'):
        current_year = datetime.now().year
        stripe_pub = (os.getenv('STRIPE_PUBLISHABLE_KEY') or '').strip()
        return render_template(
            "checkout.html",
            year=current_year,
            user=current_user,
            plan=plan,
            stripe_enabled=True,
            stripe_publishable_key=stripe_pub,
            use_rbi_embedded_checkout=True,
        )

'''

WEBHOOK_INSERT = '''        if etype == "setup_intent.succeeded":
            _handle_setup_intent_succeeded_webhook(data)

'''

CONFIRM_ROUTE = '''

@app.route("/checkout/subscription-confirm")
@login_required
def checkout_subscription_confirm():
    """Return URL after 3DS confirmSetup for RBI e-mandate subscription setup."""
    subscription_id = str(request.args.get("subscription_id") or "").strip()
    setup_intent_id = str(request.args.get("setup_intent") or "").strip()
    redirect_status = str(request.args.get("redirect_status") or "").strip().lower()

    if setup_intent_id and redirect_status and redirect_status != "succeeded":
        flash("Card authentication did not complete. Please try again.", "danger")
        return redirect(url_for("plans"))

    if subscription_id and _stripe_enabled():
        try:
            stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
            customer_id = _create_or_get_stripe_customer_for_user(current_user)
            if customer_id and _subscription_belongs_to_customer(subscription_id, customer_id):
                sub = stripe.Subscription.retrieve(subscription_id, expand=["items.data.price"])
                sub_status = str(getattr(sub, "status", "") or "").lower()
                if sub_status in ("trialing", "active"):
                    plan_id = ""
                    try:
                        meta = getattr(sub, "metadata", None) or {}
                        if isinstance(meta, dict):
                            plan_id = str(meta.get("plan_id") or "").strip()
                        else:
                            plan_id = str(getattr(meta, "plan_id", "") or "").strip()
                    except Exception:
                        plan_id = ""
                    _persist_stripe_subscription_to_profile(
                        str(getattr(current_user, "id", "") or ""), sub, plan_id=plan_id
                    )
                    flash("Payment method saved — your subscription is active.", "success")
                    return redirect(url_for("my_revisions", checkout="success"))
        except Exception as e:
            logger.warning(f"checkout_subscription_confirm error: {str(e)}")

    flash(
        "Payment completed, but we couldn't confirm access yet. If this persists, please contact support.",
        "warning",
    )
    return redirect(url_for("my_revisions"))

'''


def patch_app(text: str) -> str:
    if '_find_user_id_by_stripe_customer_id' not in text:
        anchor = "@app.route('/stripe/create-setup-intent', methods=['POST'])"
        if anchor not in text:
            raise SystemExit('anchor for helpers not found')
        text = text.replace(anchor, HELPERS + anchor)

    for old, new, label in [
        (OLD_SETUP_INTENT, NEW_SETUP_INTENT, 'setup-intent'),
        (OLD_CREATE_SUB_START, NEW_CREATE_SUB_START, 'create-sub doc'),
        (OLD_CREATE_SUB_MID, NEW_CREATE_SUB_MID, 'create-sub params'),
        (OLD_PENDING_CHECK, NEW_PENDING_CHECK, 'pending check'),
        (OLD_COMPLETE, NEW_COMPLETE, 'complete-sub'),
    ]:
        if old not in text:
            raise SystemExit(f'missing block: {label}')
        text = text.replace(old, new, 1)

    if CHECKOUT_INDIA_INSERT.strip() not in text:
        anchor = '    # Upgrade during trial:'
        if anchor not in text:
            raise SystemExit('checkout india anchor not found')
        text = text.replace(anchor, CHECKOUT_INDIA_INSERT + anchor, 1)

    if WEBHOOK_INSERT.strip() not in text:
        anchor = '        # India payment recovery: customer needs to re-authenticate'
        if anchor not in text:
            raise SystemExit('webhook anchor not found')
        text = text.replace(anchor, WEBHOOK_INSERT + anchor, 1)

    if 'def checkout_subscription_confirm' not in text:
        anchor = '@app.route("/checkout/success")'
        if anchor not in text:
            raise SystemExit('confirm route anchor not found')
        text = text.replace(anchor, CONFIRM_ROUTE + anchor, 1)

    return text


CHECKOUT_HTML = '''<!DOCTYPE html>
<html lang="en">

<head>
    {% include "_clarity.html" %}
    {% include "_gtm.html" %}

    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Checkout | Resumatic AI</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>

<body class="bg-gradient-to-br from-gray-50 via-white to-indigo-50 min-h-screen">
    <header class="bg-white/90 backdrop-blur-sm border-b border-gray-200 sticky top-0 z-10">
        <div class="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
            <a href="/" class="flex items-center gap-3">
                <img src="{{ url_for('static', filename='images/logo23_small.png') }}" alt="Resumatic AI"
                    class="w-10 h-10 object-contain" />
                <div class="font-semibold text-gray-900">Resumatic AI</div>
            </a>
            <div class="text-sm text-gray-600">
                Signed in as <span class="font-semibold text-gray-900">{{ user.email or user.name }}</span>
            </div>
        </div>
    </header>

    <main class="max-w-5xl mx-auto px-4 py-8">
        {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
        <div class="mb-6 space-y-3">
            {% for category, message in messages %}
            <div
                class="p-4 rounded-lg border {% if category == 'success' %}bg-green-50 border-green-200 text-green-800{% else %}bg-red-50 border-red-200 text-red-800{% endif %}">
                {{ message }}
            </div>
            {% endfor %}
        </div>
        {% endif %}
        {% endwith %}

        <div class="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
            <section class="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
                <div
                    class="inline-flex items-center px-3 py-1 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-800 text-xs font-semibold">
                    Secure checkout
                </div>
                <h1 class="mt-3 text-2xl font-extrabold text-gray-900">Confirm your plan</h1>
                {% if use_rbi_embedded_checkout %}
                <p class="mt-2 text-gray-600">
                    Add your card to start your subscription. Indian cards require bank authentication (3DS) to register
                    the RBI e-mandate for recurring billing.
                </p>
                {% else %}
                <p class="mt-2 text-gray-600">
                    This is a placeholder checkout to make plan links functional.
                    For production, connect Stripe Checkout + webhooks.
                </p>
                {% endif %}

                <div class="mt-6 rounded-xl border border-gray-200 bg-gray-50 p-4">
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="text-sm font-semibold text-gray-900">{{ plan.label }}</div>
                            <div class="text-xs text-gray-600">Unlock unlimited revisions + PDF downloads</div>
                        </div>
                        <div class="text-sm font-bold text-gray-900">{{ plan.price }}</div>
                    </div>
                </div>

                {% if stripe_enabled and use_rbi_embedded_checkout %}
                <div class="mt-6" id="stripe-checkout-container">
                    <input type="hidden" id="plan-id" value="{{ plan.id }}" />
                    <div id="payment-element" class="p-4 bg-white rounded-lg border border-gray-200"></div>
                    <div id="payment-errors" class="text-sm text-red-600 mt-2"></div>
                    <button id="pay-button"
                        class="mt-4 w-full inline-flex items-center justify-center px-4 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold hover:from-indigo-700 hover:to-purple-700 shadow-sm disabled:opacity-60">
                        {% if plan.id == 'trial_7d' %}Save card &amp; start trial{% else %}Subscribe now{% endif %}
                    </button>
                    <a href="/plans"
                        class="mt-3 block text-center text-sm text-gray-600 hover:text-gray-900 hover:underline underline-offset-2">Back
                        to plans</a>
                </div>
                <script src="https://js.stripe.com/v3/"></script>
                <script>
                    (function () {
                        const publishableKey = "{{ stripe_publishable_key }}";
                        if (!publishableKey) return;

                        const stripe = Stripe(publishableKey);
                        const payButton = document.getElementById('pay-button');
                        const paymentErrors = document.getElementById('payment-errors');
                        const planId = document.getElementById('plan-id').value;
                        let elements = null;
                        let subscriptionId = '';

                        async function initializeCheckout() {
                            payButton.disabled = true;
                            paymentErrors.textContent = '';
                            const resp = await fetch('/stripe/create-subscription', {
                                method: 'POST',
                                credentials: 'same-origin',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ plan_id: planId })
                            });
                            const data = await resp.json();
                            if (!resp.ok) {
                                paymentErrors.textContent = data.message || data.error || 'Failed to initialize subscription.';
                                payButton.disabled = false;
                                return;
                            }

                            const clientSecret = data.pending_setup_intent_client_secret;
                            subscriptionId = data.subscription_id;
                            if (!clientSecret) {
                                paymentErrors.textContent = 'Missing payment setup. Please refresh and try again.';
                                payButton.disabled = false;
                                return;
                            }

                            elements = stripe.elements({ clientSecret });
                            const paymentElement = elements.create('payment');
                            paymentElement.mount('#payment-element');
                            payButton.disabled = false;
                        }

                        payButton.addEventListener('click', async function (e) {
                            e.preventDefault();
                            if (!elements || !subscriptionId) return;
                            payButton.disabled = true;
                            paymentErrors.textContent = '';

                            const returnUrl = window.location.origin
                                + '/checkout/subscription-confirm?subscription_id='
                                + encodeURIComponent(subscriptionId);

                            const result = await stripe.confirmSetup({
                                elements,
                                confirmParams: {
                                    return_url: returnUrl,
                                    payment_method_data: {
                                        billing_details: { email: '{{ user.email or "" }}' }
                                    }
                                }
                            });

                            if (result.error) {
                                paymentErrors.textContent = result.error.message || 'Card setup failed.';
                                payButton.disabled = false;
                                return;
                            }

                            const completeResp = await fetch('/stripe/complete-subscription', {
                                method: 'POST',
                                credentials: 'same-origin',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ subscription_id: subscriptionId })
                            });
                            const completeData = await completeResp.json();
                            if (!completeResp.ok) {
                                paymentErrors.textContent = completeData.message || completeData.error || 'Subscription finalization failed.';
                                payButton.disabled = false;
                                return;
                            }

                            window.location.href = '/my_revisions?checkout=success';
                        });

                        initializeCheckout();
                    })();
                </script>
                {% else %}
                <form class="mt-6" method="POST" action="/checkout/complete">
                    <input type="hidden" name="plan" value="{{ plan.id }}" />
                    <button type="submit"
                        class="w-full inline-flex items-center justify-center px-4 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold hover:from-indigo-700 hover:to-purple-700 shadow-sm">
                        Complete purchase
                    </button>
                    <a href="/plans"
                        class="mt-3 block text-center text-sm text-gray-600 hover:text-gray-900 hover:underline underline-offset-2">
                        Back to plans
                    </a>
                </form>
                {% endif %}
            </section>

            <aside class="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 h-fit">
                <h2 class="text-sm font-semibold text-gray-900">What you'll get</h2>
                <ul class="mt-3 space-y-2 text-sm text-gray-700">
                    <li class="flex items-start gap-2"><span class="text-green-600 font-bold">✓</span> Unlimited resume
                        revisions</li>
                    <li class="flex items-start gap-2"><span class="text-green-600 font-bold">✓</span> PDF downloads in
                        templates</li>
                    <li class="flex items-start gap-2"><span class="text-green-600 font-bold">✓</span> Job Search Hub
                        dashboard</li>
                </ul>
                {% if use_rbi_embedded_checkout %}
                <p class="mt-4 text-xs text-gray-500">
                    Your bank may send pre-debit notifications before recurring charges. Charges above ₹15,000 may
                    require additional authentication per RBI rules.
                </p>
                {% else %}
                <p class="mt-4 text-xs text-gray-500">
                    Note: This page currently simulates subscription activation by updating your user profile.
                </p>
                {% endif %}
            </aside>
        </div>
    </main>
</body>

</html>
'''

INSTRUCTIONS_MD = '''# RBI e-mandate subscription flow (Stripe)

India recurring subscriptions must use a **subscription-owned pending SetupIntent**, not a standalone SetupIntent.

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

## Client: confirmSetup with Payment Element

```javascript
const resp = await fetch('/stripe/create-subscription', { method: 'POST', ... });
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

Add `setup_intent.succeeded` to your Stripe webhook endpoint. The app persists subscription access when the e-mandate setup completes.

## Deprecated

`POST /stripe/create-setup-intent` returns HTTP 410. Do not use standalone SetupIntents for Indian recurring billing.
'''


def main():
    app_text = APP.read_text(encoding='utf-8')
    app_text = patch_app(app_text)
    APP.write_text(app_text, encoding='utf-8')
    CHECKOUT.write_text(CHECKOUT_HTML, encoding='utf-8')
    INSTRUCTIONS.write_text(INSTRUCTIONS_MD, encoding='utf-8')
    print('Patched app.py, checkout.html, STRIPE_SETUP_INTENT_INSTRUCTIONS.md')


if __name__ == '__main__':
    main()
