# Order-to-Delivery: Manual End-to-End Checklist

Walks a single order through every stage the Angular Dashboard supports —
placing it, confirming, assigning a driver/vehicle, dispatching, departing,
delivering (OTP + proof of delivery), auto-invoicing, and closing — so you
can click through the real thing once, start to finish.

There's also an automated version of this same walk:
`frontend/apps/dashboard-e2e/src/order-to-delivery-workflow.spec.ts`. Run it with:

```bash
cd frontend
npx playwright test --config=apps/dashboard-e2e/playwright.config.mts src/order-to-delivery-workflow.spec.ts --project=chromium
```

## One-time setup

1. Backend running locally (`.claude/backend-dev.bat` or `uv run uvicorn lpg.api.app:app --reload`), `LPG_ENVIRONMENT` not `production`.
2. Postgres + Redis up, migrations applied.
3. `backend/scripts/seed_demo_data.py` has been run at least once — gives you branches, cylinder types, price lists, customers, and a base set of drivers/vehicles.
4. `backend/scripts/seed_e2e_driver.py` has been run at least once:
   ```bash
   cd backend
   .venv/Scripts/python.exe scripts/seed_e2e_driver.py
   ```
   Creates a driver login (`e2e.driver@example.com` / `correct-horse-battery`, employee code `EMP-E2E-DRIVER`, Hyderabad Central branch) whose `delivery.driver` row is actually linked to a real login. **This step is not optional** — every driver row `seed_demo_data.py` creates leaves `identity_user_id` NULL, and the backend's ownership check on Deliver (`_require_own_driver_order`) 404s for any driver that isn't linked. There is no way to link one after the fact through the UI; only at driver-registration time.
5. Frontend dev server running (`npx nx run dashboard:serve`), reachable at `http://localhost:4200`.

## Logins used in this walk

| Role | Email | Password | Why this login |
|---|---|---|---|
| Admin (`agency_admin`) | `admin@example.com` | `correct-horse-battery` | Everything except Deliver — `orders:deliver` is driver-role-only |
| Driver | `e2e.driver@example.com` | `correct-horse-battery` | Depart + Deliver — also ownership-scoped to *this* driver's own assignment |

---

## 1. Create the order (as Admin)

1. Log in as `admin@example.com`.
2. Go to **Orders** → **New Booking**.
3. Search the customer field for a customer, e.g. **Meena Iyer** (`+919848012002`, Hyderabad Central) — pick one that's `active` + KYC `verified`, in the same branch as the driver you'll assign later.
4. Pick her delivery address (single option, auto-fills once she's selected).
5. Leave **Booking Source** as `Staff` and **Requested Delivery Date** as the default (today).
6. Under **Cylinders**, pick a type with a configured price for her customer type — e.g. **Domestic 14.2kg** — quantity `1` (default).
7. Click **Create Booking**.

**Expect:** redirected to `/orders/{id}`, status **Booked**, Total Amount "Not confirmed yet".

## 2. Confirm

Click **Confirm**.

**Expect:** status → **Confirmed**, Total Amount now shows the priced total (e.g. ₹905.50), Timeline gains a `Booked → Confirmed` row.

## 3. Assign driver & vehicle

1. Click **Assign**.
2. **Driver**: pick the one labeled `EMP-E2E-DRIVER — E2E Driver`.
3. **Vehicle**: pick the active vehicle in that branch (`TS07UB4412`).
4. Click the drawer's **Assign** button.

**Expect:** status → **Assigned**, toast "Order assigned to driver and vehicle."

> If the driver dropdown shows blank rows instead of names, the fix in
> `order-detail.ts`/`.html` (driver options resolved via `AdminEmployeeService`,
> see commit adding `driverOptions`) hasn't been picked up — rebuild the
> dashboard app.

## 4. Dispatch

Click **Dispatch**.

**Expect:** status → **Ready For Dispatch**.

## 5. Depart (switch to the driver login)

`orders:deliver` — which both Depart and Deliver require in the UI — is
driver-role-only. Sign out of the admin session and log in as
`e2e.driver@example.com`, then navigate back to the same order
(`/orders/{id}`, same URL as before).

Click **Depart**.

**Expect:** status → **Out For Delivery**. A delivery OTP is generated and
"sent" to the customer's phone — in local dev there's no real SMS provider,
so it's only logged (`otp_delivery_dev_mode` in the backend's structured
logs, `event=otp_delivery_dev_mode`, field `code`). Find it either:
- In the backend's console output, or
- Via the dev-only endpoint: `GET http://localhost:8000/api/v1/dev/otp-inbox/%2B919848012002` (URL-encode the `+`) — only registered outside production, returns `{"code": "..."}`.

## 6. Deliver

Click **Deliver**. In the drawer:

1. **Delivery OTP** — paste the code from step 5.
2. **Quantities** — leave Delivered/Empties Collected at their defaults (pre-filled from the order line).
3. **Payment Method** — pick `Cash` (or whatever fits).
4. **Amount Collected** — enter the order total (e.g. `905.50`).
5. **Signature** — draw anything on the pad, click **Save Signature** (look for the green "Saved" check).
6. **Delivery Photo** — upload any image file, wait for the green "Uploaded" check.
7. **GPS** — click **Use Current Location**, allow the browser's location prompt if asked.
8. Once all three proof-of-delivery items show green checks, **Confirm Delivery** becomes enabled — click it.

**Expect:** status → **Delivered**.

## 7. Invoice — verify it appeared automatically

There is **no manual "Generate Invoice" step** — an invoice is created the
instant delivery succeeds (a domain-event handler on `CylinderDelivered`).

Go to **Invoices** and confirm a new invoice for the customer (e.g. **Meena
Iyer**) appears, with a total matching what was collected.

## 8. Close the order (switch back to Admin)

`orders:close` is admin/manager-only. Sign out of the driver session, log
back in as `admin@example.com`, return to the order.

Click **Close Order**.

**Expect:** status → **Closed** (terminal state).

## 9. Optional: Cash Handover

Not part of the Order state machine (nothing blocks Close if this is
skipped) — a separate reconciliation record for the driver's shift, done
from the **Dispatch** board rather than the order itself:

1. Go to **Dispatch**, find the route the assignment created for this driver/vehicle/day.
2. Once the route is `completed`, open it and click **Declare Cash Handover**.
3. Enter **Cash Amount Handed Over** — the expected amount is computed server-side from real cash-payment proof-of-delivery records, never trusted from the form; the result shows expected vs. actual, colored green (matched) or amber (shortfall).

---

## Known rough edges hit while building this checklist

- **Driver dropdown blank labels (fixed):** the Assign drawer's driver select used to render every row with no visible text (`optionLabel="employee_code"`, a field `DriverResponse` doesn't have) — indistinguishable drivers. Fixed by resolving each driver's linked employee and building a real label client-side.
- **Demo-seeded drivers can't Deliver:** `delivery.driver` rows from `seed_demo_data.py` all have `identity_user_id = NULL`. There's no API to link one after registration — only at `POST /drivers` creation time. `seed_e2e_driver.py` exists specifically to produce one that's usable end to end.
- **Depart button permission mismatch:** `order-detail.html` gates the Depart/Reschedule buttons on `orders:deliver`, but the backend's `/depart` and `/reschedule` endpoints actually require `orders:dispatch`. They happen to line up correctly for the `driver` role (has both), so this doesn't break the flow above — but a role with `orders:deliver` and not `orders:dispatch` would see a button that 403s. Worth a closer look if a new role is introduced between those two permissions.
