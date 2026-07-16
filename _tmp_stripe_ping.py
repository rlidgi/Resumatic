import os
import time

from dotenv import load_dotenv

load_dotenv()
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY") or ""
print("has_key", bool(stripe.api_key))
t0 = time.time()
try:
    prices = stripe.Price.list(active=True, expand=["data.product"], limit=100)
    print("ok", len(prices.data), "sec", round(time.time() - t0, 2))
    for p in list(prices.data)[:12]:
        prod = p.product
        meta = getattr(prod, "metadata", None) or {}
        print(
            p.currency,
            getattr(p, "unit_amount", None),
            "display=" + str(meta.get("display")),
            "role=" + str(meta.get("plan_role")),
        )
except Exception as e:
    print("fail", type(e).__name__, "sec", round(time.time() - t0, 2), str(e)[:200])
