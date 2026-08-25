import { test, expect, type Page } from '@playwright/test';

/**
 * Drives the full order lifecycle for real — no mocked auth/API, unlike
 * `accessibility-auth.spec.ts` — against a real backend and a real Postgres/
 * Redis, so it needs real fixtures to exist first. See
 * `planning/order-to-delivery-e2e-checklist.md` for the one-time setup this
 * depends on:
 *
 *   1. `backend/scripts/seed_demo_data.py` has been run at least once
 *      (customers, cylinder types, price lists, branches).
 *   2. `backend/scripts/seed_e2e_driver.py` has been run at least once — it
 *      creates a driver login (`e2e.driver@example.com`) whose
 *      `delivery.driver` row is actually linked via `identity_user_id`.
 *      Pre-existing demo drivers are NOT usable for the Deliver step: the
 *      backend's ownership check (`_require_own_driver_order`,
 *      `api/v1/routers/order.py`) 404s unless the driver row's
 *      `identity_user_id` matches the logged-in user, and demo-seeded driver
 *      rows leave that column NULL.
 *   3. The backend is running with `LPG_ENVIRONMENT` not `production` (true
 *      for local dev) — the `/dev/otp-inbox/{phone}` endpoint this test uses
 *      to read the delivery OTP is only registered outside production
 *      (`api/app.py`).
 *
 * `orders:deliver` is driver-role-only (admin/agency_admin does not hold
 * it), so Depart/Deliver run as a second login, not the admin session that
 * does the rest — see the permission table in the checklist for why.
 */

const BASE_URL = process.env['BASE_URL'] || 'http://localhost:4200';
const API_BASE_URL = process.env['API_BASE_URL'] || 'http://localhost:8000';

const ADMIN = { email: 'admin@example.com', password: 'correct-horse-battery' };
const DRIVER = { email: 'e2e.driver@example.com', password: 'correct-horse-battery' };

// Fixtures from `seed_demo_data.py` + `seed_e2e_driver.py`. If these stop
// resolving, re-run those two scripts — see the module doc comment above.
const CUSTOMER_NAME = 'Meena Iyer';
const CUSTOMER_PHONE = '+919848012002';
const DRIVER_LABEL = 'EMP-E2E-DRIVER';
const VEHICLE_REG = 'TS07UB4412';
const CYLINDER_TYPE = 'Domestic 14.2kg';

// 1x1 transparent PNG — just needs to be a real, decodable image file for
// the delivery-photo upload; content is never inspected by the backend.
const TINY_PNG_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';

async function login(page: Page, email: string, password: string): Promise<void> {
  await page.goto(`${BASE_URL}/login`);
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL((url) => !url.pathname.includes('/login'));
}

/** Asserts the order's status pill (`.order-title-row p-tag`, next to the
 * order number) shows `label` — more robust than matching a toast message,
 * which can auto-dismiss before the assertion runs, and unambiguous unlike
 * plain `getByText`, which would also match the same word in the Timeline
 * section below. */
async function expectOrderStatus(page: Page, label: string): Promise<void> {
  await expect(page.locator('.order-title-row').getByText(label, { exact: true })).toBeVisible();
}

async function logout(page: Page): Promise<void> {
  // Whatever drawer/dialog was just used (Load Vehicle, the Deliver drawer,
  // ...) can still be mid-close-animation (mask fade-out) right as the next
  // action starts, intercepting the very next click. Wait for it to clear
  // before doing anything — every call site hits this, not just one.
  await page.locator('.p-drawer-mask').waitFor({ state: 'hidden', timeout: 5000 }).catch(() => undefined);
  await page.getByRole('button', { name: /Account menu/i }).click();
  await page.getByRole('menuitem', { name: 'Sign Out' }).click();
  await page.waitForURL((url) => url.pathname.includes('/login'));
}

/** Clicks a `pButton` by its exact visible label, matched on the inner
 * `.p-button-label` span rather than the button's computed accessible name
 * — every `pButtonIcon`+`pButtonLabel` button's accessible name picks up a
 * leading space (the icon isn't `aria-hidden`, so its empty text
 * alternative still gets joined with a separator space per the accname
 * spec), which trips up both `exact: true` string matches and regex
 * matches inconsistently. Also sidesteps "Deliver" being a substring of
 * "Failed Delivery" that a loose name match would ambiguously catch. */
function buttonWithLabel(page: Page, label: string) {
  return page.locator(`button:has(span.p-button-label:text-is("${label}"))`);
}

/** Opens a PrimeNG `p-select`/`p-autocomplete` trigger and picks the option
 * matching `name`. Works for both — the option list is a `role="option"`
 * item either way, and Playwright's accessible-name computation falls back
 * to visible text when there's no explicit `aria-label` (true for `p-select`
 * options; `p-autocomplete` options do carry one). */
async function choosePrimeOption(page: Page, trigger: string, name: string | RegExp): Promise<void> {
  await page.locator(trigger).click();
  await page.getByRole('option', { name }).click();
}

test.describe('Order to delivery — full workflow', () => {
  test.setTimeout(180_000);

  test('places an order and drives it through delivery, invoicing, and close', async ({
    page,
    context,
  }) => {
    await context.grantPermissions(['geolocation']);
    await context.setGeolocation({ latitude: 17.4058, longitude: 78.489 });

    // ------------------------------------------------------------------
    // Admin: create -> confirm -> assign -> dispatch
    // ------------------------------------------------------------------
    await login(page, ADMIN.email, ADMIN.password);

    await page.goto(`${BASE_URL}/orders`);
    await page.getByRole('button', { name: 'New Booking' }).click();

    // `lpg-customer-autocomplete`'s `inputId="create_customer"` is a plain
    // (non-bound) HTML attribute, not the component's `[inputId]` — the
    // real rendered input keeps the component's own default id.
    await page.locator('#customer_autocomplete').fill('Meena');
    await page.getByRole('option', { name: CUSTOMER_NAME }).click();

    // Match the address text itself, not a catch-all regex — the customer
    // autocomplete's own just-selected suggestion option can still linger in
    // the DOM/accessibility tree at this point, and `/./ ` would ambiguously
    // match both it and the real address option.
    await choosePrimeOption(page, '#create_address', /Basheerbagh/);
    await choosePrimeOption(page, '.line-row__type', CYLINDER_TYPE);
    // Booking source (defaults to "Staff") and requested date (defaults to
    // now) are left as-is — both already valid.

    await page.getByRole('button', { name: 'Create Booking' }).click();
    await page.waitForURL(/\/orders\/[0-9a-f-]{36}$/);
    const orderUrl = page.url();

    // Not `exact: true` — every `pButtonIcon`+`pButtonLabel` button computes
    // an accessible name with a leading space (the icon isn't `aria-hidden`,
    // so its empty text alternative still gets joined with a separator
    // space per the accname spec) — harmless for real screen-reader users,
    // but fails exact matching. No ambiguity risk here: "Confirm" is the
    // only button with that substring at this point in the flow.
    await page.getByRole('button', { name: 'Confirm' }).click();
    await expectOrderStatus(page, 'Confirmed');

    await page.getByRole('button', { name: 'Assign' }).click(); // see the leading-space note above
    await choosePrimeOption(page, '#assign_driver', new RegExp(DRIVER_LABEL));
    await choosePrimeOption(page, '#assign_vehicle', VEHICLE_REG);
    // Disambiguate from the "Assign" trigger button that opened this drawer
    // — the drawer's own submit is the only `type="submit"` button on the page.
    await page.locator('button[type="submit"]', { hasText: 'Assign' }).click();
    await expectOrderStatus(page, 'Assigned');

    await page.getByRole('button', { name: 'Dispatch' }).click();
    await expectOrderStatus(page, 'Ready For Dispatch');

    // ------------------------------------------------------------------
    // Dispatch Board: Load Vehicle -> Start Route. Assigning a driver +
    // vehicle to an order (above) finds an already-open (still "planned")
    // Route for that driver+vehicle+day, or plans a new one — it does NOT
    // reuse a route that's already moved past "planned" (loaded/in_progress
    // routes are for a *different, earlier* batch of orders) — but
    // `Route.record_proof_of_delivery` requires "in_progress" (409 "Cannot
    // record POD: route is in status 'planned'." otherwise, domain/delivery/
    // route.py), reachable only from here, never from the Order screen.
    // Nothing in the Order Detail UI hints this second, separate step is
    // still needed before a driver can actually deliver.
    //
    // Because a second test run *today* can have an earlier run's route for
    // the same driver+vehicle sitting in a later column, scope to the
    // "Planned" column specifically — a plain `.route-card` search matching
    // only on vehicle text could otherwise grab that older, already-past-
    // planned route instead of the one this order's stop actually landed on.
    // ------------------------------------------------------------------
    await page.goto(`${BASE_URL}/dispatch`);
    const plannedColumn = page
      .locator('.route-column')
      .filter({ has: page.locator('.route-column__header', { hasText: 'Planned' }) });
    await plannedColumn.locator('.route-card', { hasText: VEHICLE_REG }).first().click();

    // Not `.isVisible()` — it's a synchronous, non-retrying check, and right
    // after the click above the drawer is still mid-open-animation with its
    // `@if (selectedRoute(); as route)` content not yet rendered. A bare
    // `.isVisible()` call here can resolve `false` before the button ever
    // exists, silently skipping this entire block — which is exactly what
    // produced the 409 "Cannot record POD: route is in status 'planned'."
    // failures seen in earlier runs (Load Vehicle/Start Route never ran).
    // `waitFor` actually waits, and the `.catch` keeps this conditional for
    // the case where the route sensibly has no Load Vehicle step to do.
    const hasLoadVehicle = await buttonWithLabel(page, 'Load Vehicle')
      .waitFor({ state: 'visible', timeout: 5_000 })
      .then(() => true)
      .catch(() => false);
    if (hasLoadVehicle) {
      await buttonWithLabel(page, 'Load Vehicle').click();
      await choosePrimeOption(page, '#load_warehouse', /Hyderabad Central/);
      // No `id`/`inputId` on either control inside a load line — scope by
      // the repeating row's class instead (same reasoning as
      // `.line-row__qty` on the Create Booking form).
      await page.locator('.load-line p-select').first().click();
      await page.getByRole('option', { name: CYLINDER_TYPE }).click();
      await page.locator('.load-line p-inputnumber input').first().fill('10');
      await page.locator('button[type="submit"]', { hasText: 'Load' }).click();
    }
    const hasStartRoute = await page
      .getByRole('button', { name: 'Start Route' })
      .waitFor({ state: 'visible', timeout: 5_000 })
      .then(() => true)
      .catch(() => false);
    if (hasStartRoute) {
      await page.getByRole('button', { name: 'Start Route' }).click();
    }
    // The Route Detail drawer never gets an explicit close — it's still
    // open (modal mask genuinely up, not just animating) when the next step
    // tries to interact with anything else, blocking every click after it
    // for the rest of the test. Dismiss it before moving on.
    //
    // Not `keyboard.press('Escape')`: PrimeNG's drawer only honors Escape
    // when its z-index matches the topmost overlay tracked by ZIndexUtils
    // (`bindDocumentEscapeListener`, primeng-drawer.mjs) — if a toast from
    // the just-clicked Start Route/Load button is still registered above
    // it, Escape silently no-ops and the mask never clears, which is what
    // produced the 180s "Account menu" timeout seen in earlier runs (300+
    // retries against a mask that was never going away). The drawer's own
    // close button calls `close()` directly, skipping that check.
    await page.locator('.p-drawer-close-button').first().click();
    await page.locator('.p-drawer-mask').waitFor({ state: 'hidden', timeout: 10_000 });

    // ------------------------------------------------------------------
    // Driver: depart -> deliver (orders:deliver is driver-role-only, and
    // additionally ownership-scoped to this specific driver's own stop)
    // ------------------------------------------------------------------
    await logout(page);
    await login(page, DRIVER.email, DRIVER.password);
    await page.goto(orderUrl);

    await page.getByRole('button', { name: 'Depart' }).click();
    await expectOrderStatus(page, 'Out For Delivery');

    // The dev-only OTP inbox (`api/v1/routers/dev_tools.py`) stashes the
    // plaintext code `LoggingOtpDelivery` "sends" — the real OTP store only
    // ever persists a salted hash, so this is the only way to read it back.
    const otpResponse = await page.request.get(
      `${API_BASE_URL}/api/v1/dev/otp-inbox/${encodeURIComponent(CUSTOMER_PHONE)}`,
    );
    expect(otpResponse.ok()).toBeTruthy();
    const { code: otp } = (await otpResponse.json()) as { code: string };

    // Not a `getByRole` name match — "Deliver" is also a substring of
    // "Failed Delivery" (the button right next to it), and both a regex and
    // `exact: true` name match failed unpredictably against this button's
    // leading-space accessible name (see `buttonWithLabel`'s doc comment).
    await buttonWithLabel(page, 'Deliver').click();
    await page.locator('#deliver_otp').fill(otp);
    // Delivered/empties-collected quantities default to the ordered amounts.
    await choosePrimeOption(page, '#deliver_payment_method', /Cash/i);
    // Unlike `#create_requested_date` (a plain `id=` on the `<p-datepicker>`
    // host, needing `.querySelector('input')`), this field uses `inputId`,
    // a real `p-inputnumber` `@Input()` that's applied directly to the
    // inner native `<input>` — no nested query needed.
    await page.locator('#deliver_amount_collected').fill('905.50');

    const signaturePad = page.locator('.signature-pad');
    const box = await signaturePad.boundingBox();
    if (!box) throw new Error('Signature pad did not render.');
    await page.mouse.move(box.x + 20, box.y + 20);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width - 20, box.y + box.height - 20, { steps: 5 });
    await page.mouse.up();
    await page.getByRole('button', { name: 'Save Signature' }).click();
    await expect(page.getByText('Saved')).toBeVisible();

    await page
      .locator('#deliver_photo')
      .setInputFiles({ name: 'delivery.png', mimeType: 'image/png', buffer: Buffer.from(TINY_PNG_BASE64, 'base64') });
    await expect(page.getByText('Uploaded')).toBeVisible();

    await page.getByRole('button', { name: 'Use Current Location' }).click();
    await expect(page.getByText(/17\.4/)).toBeVisible();

    await page.getByRole('button', { name: 'Confirm Delivery' }).click();
    await expectOrderStatus(page, 'Delivered');

    // ------------------------------------------------------------------
    // Admin: close the order, then confirm the invoice was auto-created
    // (GenerateInvoiceForOrderUseCase runs as a domain-event handler on
    // CylinderDelivered — there's no manual "create invoice" step).
    // ------------------------------------------------------------------
    await logout(page);
    await login(page, ADMIN.email, ADMIN.password);
    await page.goto(orderUrl);

    await page.getByRole('button', { name: 'Close Order' }).click();
    await expectOrderStatus(page, 'Closed');

    await page.goto(`${BASE_URL}/invoices`);
    await expect(page.getByText(CUSTOMER_NAME).first()).toBeVisible();
  });
});
