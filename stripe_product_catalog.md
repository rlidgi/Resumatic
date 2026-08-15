# Dynamic Stripe Plan Catalog

Plans shown on `/plans` and sold via `/checkout` are dynamically generated from Stripe **Products + Prices**.

All configuration is handled directly in the Stripe Dashboard using a standardized metadata convention.

---

## Product Metadata Schema

Configure the following fields on the **Stripe Product metadata**:

### Required Fields

- `display = "1" | "true"`  
  Marks the product as **visible and sellable** in the pricing page.

- `plan_role = "trial" | "monthly" | "pro"`  
  Defines the access level / plan category.

### Optional Fields

- `sort_order = "0", "1", "2", ...`  
  Controls left-to-right ordering in the pricing grid.

- `badge = "Best Value"`  
  Displays a highlighted ribbon on the pricing card.

- `note = "7-day full access pass"`  
  Short descriptive label shown near the plan title.  
  Falls back to Stripe product `description` if empty.

- `micro_note = "Free for 7 days. Cancel anytime."`  
  Contextual helper text shown under the primary CTA button.

- `features = "Feature one | Feature two"`  
  Pipe-separated string converted into a bullet list on the UI.

- `cta_label = "Upgrade Now"`  
  Overrides default button text.

- `trial_days = "7"`  
  Required when `plan_role = "trial"`, or when a product includes a trial period.  
  Defines the explicit trial duration in days used for UI display and billing logic.

- `use_trial_hold = "true"`  
  Signals that this product uses a temporary authorization hold.

- `trial_fee_price_id = "price_..."`  
  The specific Stripe `price_id` for the trial hold fee.

- `trial_hold_ui = "stripe"`  
  Defines the UI handling method for the trial hold.

- `deposit_amount = "1095"`  
  The numerical amount (in cents) for the trial authorization hold.

---

## Price Handling Rules

### 1. Standard Recurring Subscriptions (Monthly / Annual)

- Must be configured as:
  - `type = "recurring"`
- Stripe-native fields control billing logic:
  - `interval = month | year`
  - `interval_count`

The UI automatically adapts:
- Monthly → `/month`
- Annual → normalized to `/month` equivalent display

### 2. Standalone Trial Tier

Used for free or introductory access offers.

- Must be configured as:
  - `type = "one_time"`
  - `unit_amount = 0` (or the specific hold amount, e.g., 1095)
- Must include:
  - `plan_role = "trial"`

### Behavior

- Automatically treated as a **trial product**
- Rendered inside the same grid layout as subscriptions
- Displayed with:
  - Trial duration label (`trial_days`)
  - Optional micro-note
- CTA behavior is dynamically adjusted (e.g., “Start Free Trial”)

---

## UI Behavior Summary

- Products with `display != "1"` are ignored
- Only active Stripe prices are fetched
- Products are grouped by `product_id`
- Each product may render:
  - Monthly plan
  - Annual plan
  - Trial plan (if applicable)

---

## Notes

This system is fully **Stripe-driven**:

- No plans are hardcoded in the backend
- All pricing, labels, and marketing text originate from Stripe metadata
- The UI is a rendering layer only