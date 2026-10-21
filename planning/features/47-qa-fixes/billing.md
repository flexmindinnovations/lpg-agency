# QA fixes — billing (invoices, GST, payments, cash, reports, home KPIs)

Branch `qa-fix/billing`. Migration `e7b3c9d1f4a6` (down_revision `c8d4e2f6a1b3`).

## Findings fixed

### DA-06 / DO-15 / CA-15 — GST never silently 0%
- **Change**
  - GST is configured per cylinder type as `hsn_code` and `gst_rate_percent`.
  - Rate resolution order:
    1. the cylinder type's rate;
    2. the legacy tenant config `gst_rate_percent`;
    3. otherwise `GstNotConfiguredError` (422 `GST_NOT_CONFIGURED`).
  - Invoice generation after delivery logs `invoice_held_gst_not_configured` and holds the invoice. Held orders are listed at `GET /invoices/uninvoiced-orders` and issued with `POST /invoices` (permission `invoices:issue`).
  - Payment-link prepayment totals use the same resolution.
  - Admin › Cylinder Types gains HSN and GST columns, a "Set GST" drawer, required GST fields on create, and a warning banner for unclassified types.
  - Invoices shows an "orders waiting for an invoice" panel with an Issue action.
- **Files**
  - Backend: `domain/common/gst.py`, `domain/tenant/cylinder_type.py`, `application/accounting/gst.py`, `application/accounting/use_cases.py`, `application/accounting/online_payments.py`, `application/tenant/cylinder_type.py`, `infrastructure/events/accounting_handlers.py`, `api/v1/routers/admin.py` (`PATCH /admin/cylinder-types/{id}/gst`), `api/v1/routers/invoice.py`.
  - Frontend: `cylinder-types-page.ts`, `feature-invoices.*`.
- **Migration** does not set rates on existing cylinder types, because the docs give the 5%/18% split by class and a migration cannot know each type's class. It only sets HSN 27111900 (LPG, heading 2711 per R16). The demo seed sets Domestic to 5% and Commercial to 18%.
- **Verification**
  - Unit: `tests/unit/test_gst_billing.py` and `test_accounting_use_cases.py::test_refuses_to_invoice_when_gst_is_not_configured`.
  - Integration: `tests/integration/test_gst_invoicing_flow.py` covers hold → classify → issue, tenant scoping, and the driver getting 403.

### DA-13 — valid GST tax invoice (PDF and thermal)
- **Change**
  - Agency business profile on the tenant: legal name, GSTIN (mod-36 checksum, state must match), address, state code, pincode, phone. Set with `PUT /admin/tenant/business-profile`; `GET /admin/gst-states` lists the states.
  - The form is in Settings › Agency.
  - The invoice stores supplier state, place of supply and customer GSTIN.
    - Intra-state supply uses CGST and SGST; SGST takes the odd paisa.
    - Inter-state supply uses IGST.
    - Place of supply is the customer's GSTIN state, else their address state, else the agency state.
  - The invoice line stores HSN, rate, kind and description.
  - The PDF and thermal print show:
    - "TAX INVOICE" when the agency has a GSTIN;
    - supplier GSTIN and state, customer GSTIN and place of supply;
    - HSN and rate per line, and the CGST/SGST or IGST split;
    - total in words (Indian numbering), paid / balance due, and the reverse-charge line.
  - The hardcoded "LPG Agency" name and 18% default are removed. An unnumbered invoice prints "Not numbered" instead of a UUID fragment.
- **Files**: `domain/tenant/tenant.py` (`AgencyBusinessProfile`), `application/tenant/business_profile.py`, `application/printing/{models,use_cases,amount_in_words}.py`, `infrastructure/printing/templates/invoice.html`, `renderers/thermal_renderer.py`, `api/v1/dependencies/printing.py`, `settings/agency/agency-business-profile.ts`.
- **Customer GSTIN**: read defensively with `getattr(customer, "gstin")` in `application/accounting/gst.py::customer_gstin`. Once the orders branch adds `Customer.gstin`, B2B invoices pick it up with no further change.
- **Verification**: `tests/unit/test_printing_engine.py` (GST lines, IGST variant, rupees in words) and the agency settings spec.

### DA-07 / DO-16 — Invoices screen
- **Change**
  - Server paging (25/50/100) with status, date range (IST) and search over invoice/order/consumer number and customer name.
  - Indian date format, a customer name column and a balance-due column.
  - The drawer shows paid, balance, GSTIN, place of supply, GST split and payment history (method + reference).
  - Record payment drawer: cash, UPI, card, cheque, bank transfer. A reference is required for cheque and bank transfer. Overpaying returns 422.
  - Send payment link. A 503 shows "Online payments are not set up…".
  - Refund / credit note: request, list, and approve (with `credit_notes:approve`).
  - Export CSV.
- **API**
  - `GET /invoices` gains `issued_from`, `issued_to` and `search`.
  - `InvoiceResponse` gains `balance_due`, `customer_name`, `customer_gstin`, state codes, `is_inter_state` and cgst/sgst/igst.
  - `PaymentResponse.reference`.
  - `GET /invoices/{id}/credit-notes`.
  - `RecordPaymentRequest.reference`.
  - Payment methods add `cheque` and `bank_transfer`. Staff cannot record `online_gateway` or `credit`.
- **Verification**: unit `TestRecordPayment` and the feature-invoices spec (paging params, cheque needs a reference).

### DO-14 (billing side) — cancellation charge invoiced
- **Contract**
  - `BookingCancelled.cancellation_charge` is the amount configured in `cancellation_fee_amount`. It is read on the same basis as the price list: before GST, with GST added on top (the default), or GST-inclusive when `prices_include_gst` is true. See the pricing-basis follow-up.
  - When it is greater than 0, the accounting handler issues one invoice with a single `cancellation_charge` line (quantity 1).
  - The line is taxed at the highest rate and HSN among the order's lines (consideration for the related supply).
  - If GST is not configured, the invoice is held and appears in the uninvoiced list via `orders.cancellation_record`.
- **Verification**: `TestCancellationChargeInvoice`.

### DA-10, DA-11, DA-12, DA-35, DA-37 — Reports
- **Change**
  - Reports are computed live, on IST business days, by RLS-scoped SQL (no stale UTC materialized views).
  - Daily Sales: branch name and taxable value, one row per day per branch, a totals strip, branch filter.
  - Driver Performance: driver name and code, branch, failed stops, cash due / handed over / accuracy, branch filter.
  - Shared filter bar: date range with 7-day / 30-day / this-month presets, branch, and Export CSV. The range is capped at one year.
  - New `GET /reporting/gst/gstr1` GSTR-1 report:
    - B2B (4A), B2C large (5, inter-state above ₹1 lakh), B2C small (7) by place and rate, and HSN summary (12);
    - each with CGST/SGST/IGST.
  - The GST tab now shows it, with a CSV per table.
  - Grids use page size 25 with no fixed widths (DA-35). The TDT tab uses page size 10.
  - TDT: the booked time falls back to the order's created time. The empty state now distinguishes "no qualifying orders" from "star bands not configured".
- **Files**: `application/reporting/*`, `infrastructure/persistence/repositories/reporting.py`, `repositories/compliance.py`, `libs/reporting/**`.
- **Verification**: unit `TestGstr1Report` and `istDate` spec; integration `test_reporting_endpoints_smoke.py`, run against `lpg_test_billing`.

### DA-14 — Export buttons
- **Change**: `DataGridComponent.exportCsv(fileName)` exports visible columns, current filter and sort, with formatted values (AG Grid Community). Wired on Branches, Warehouses, Cylinder Types, Pricing, Users and Tenant Configuration. Also used on Invoices, Reports and Cash Handovers.

### DA-33 — Cash handover register
- **Change**
  - `GET /cash-handovers` (permission `cash_handovers:review`), filterable by date, driver and status, returns driver, vehicle, cash stops, expected, handed over, shortfall, excess and review.
  - `POST /cash-handovers/{id}/review` (accepted | disputed). The review is append-only, one per handover. Rules:
    - a dispute needs a note;
    - accepting a short handover needs a note;
    - the person who declared the handover cannot review it.
  - New page `/cash-handovers` with an "Accounting › Cash Handovers" nav entry.
- **Verification**: unit `TestCashHandoverReview`.

### DO-28 / DA-36 — Home
- **Change**
  - `GET /dashboard/operations` (permission `reports:read`) returns:
    - bookings today, open orders by status, delivered and failed today, pending cancellations;
    - open complaints and low-stock locations;
    - outstanding and overdue invoices (included only with `invoices:read`), invoices on hold;
    - cash with drivers and handovers to verify (included only with cash permissions).
  - Home shows a "Today's operations" tile row.
  - Recent Activity shows the entity display name and "by actor".
  - The price card is retitled "Cylinder Prices", with the customer type and "No price set".
  - Chart labels are sentence case.

### DA-31 — invoice numbers
- **Change**
  - The migration numbers NULL-number invoices per tenant from the `invoice` reference sequence, oldest first (`INV-YYYY-NNNNNN`), and advances the counter.
  - The demo seed now:
    - numbers its invoices the same way;
    - sets the agency profile and cylinder GST;
    - writes HSN and rate on invoice lines;
    - writes payments for paid invoices;
    - writes `booked` history rows (fixes DA-37's zero TDT).
- **Verification**: downgrade, then NULL two numbers, then upgrade on `lpg_test_billing`. The invoices were numbered 000006–000007 and next_value became 8.

### Follow-up — pricing basis: GST-exclusive by default, inclusive opt-in
- **Decision**: the product owner chose **exclusive**. GST is added on top of the Pricing amount. This replaces the first follow-up, which had made inclusive the default.
- **Flag**: the tenant configuration key `prices_include_gst`. If it is absent, prices are **exclusive**. Only an explicit `true`, `"true"`, `"yes"`, `"1"`, `"inclusive"` or `1` turns inclusive on; anything else stays exclusive. No migration (jsonb config).
  - Resolved by `resolve_prices_include_gst` in `application/accounting/gst.py`, at the delivery or cancellation time.
  - Listed in Configuration as "Prices Include GST". That page keeps a hand-written key catalogue, so it was added there.
- **Exclusive (default)**: per line, taxable = price x qty, and tax = taxable x rate, rounded half-up to paise.
  - Payment-link prepayments are price x qty + GST.
  - The cancellation charge is the taxable value, with GST added on top.
- **Inclusive (opt-in)** uses `split_inclusive` in `domain/common/gst.py`:
  - taxable = to_cents(price x qty / (1 + rate)), and tax = price x qty - taxable, so taxable + tax == price x qty to the paisa;
  - payment links are price x qty;
  - the cancellation charge is the total.
- **Print**: PDF and thermal print the stored amounts. On an inclusive invoice, the PDF's Rate column reads "Rate (incl. GST)" and both formats add "Prices include GST". This is detected from the stored amounts, so exclusive invoices print as before.
- **GSTR-1**: no change. It reads the stored per-line taxable value, tax and rate.
- **New Booking and customer app**: the booking price, the order total (dashboard order detail and queue column "Total (excl. GST)") and the customer app's price and order total are labelled "+ GST". The order total is price x qty; the invoice and payment link carry the GST.
  - Label caveat: the frontend does not read the flag, so a tenant that opts into inclusive would still see "+ GST". Making the label follow the flag needs the flag exposed to staff and customers. This is deferred.
- **Seed**: demo invoices are exclusive (GST on top).
- **Existing invoices** keep their stored amounts.
- **Verification**:
  - unit `TestInclusivePricing` checks the split sweep and the flag parsing (default exclusive);
  - the parametrised invoice-line test covers absent, true, "true", false and "false";
  - the cancellation-charge test covers exclusive and inclusive;
  - the prepayment tests cover exclusive (945.00) and inclusive (900.00);
  - the print test;
  - integration `test_gst_invoicing_flow.py`: 900.00 + 22.50 + 22.50 = 945.00;
  - the online-payment smoke link is 945.00.

## Test results
- **Pricing-basis follow-up (exclusive default)**:
  - backend unit 1295 passed; mypy, ruff and import-linter are clean;
  - integration (gst flow, online payment, invoice smoke and RBAC, customer smoke) on `lpg_test_billing`: 41 passed;
  - lint and test pass for admin-feature-tenant-settings and order-feature-orders;
  - the customer-app Dart edits are string-only; Flutter is not available here, so they were not run;
  - no API change, so the client was not regenerated.
- **Backend unit**: 1265 passed. `mypy --strict` is clean (386 files), ruff is clean, and import-linter keeps 7 contracts with 0 broken.
- **Integration**
  - Run against `lpg_test_billing`: the new `test_gst_invoicing_flow.py` passes 3/3.
  - The relevant existing suites (invoice smoke/RBAC, cash handover, reporting, dashboard, admin, online payment) were run from temporary copies pointed at my DB: 66 passed after the test updates in this branch.
- **Frontend**
  - `nx build dashboard` succeeds.
  - lint and test pass for shared-ui, shared-data-access, feature-invoices, reporting-*, admin-feature-tenant-settings, admin-feature-users and dashboard.

## Deferred
- **Existing invoices issued at 0%** are not re-taxed. Correcting them needs a supplementary invoice or debit note per CGST s.34. That is a product and accounting decision.
- **Pricing basis**: decided as exclusive by default; `prices_include_gst` = true is opt-in (see the follow-up above). The "+ GST" price labels do not yet follow the flag.
- **Customer GSTIN capture** is owned by the orders/customers branch. Billing reads it if present.
- **Stock register, ageing, cash book and DBTL reports** (rest of DA-12) are out of scope.
- **Seed re-runs on a later day** fail at routes and ledger rows: `route_date` is matched as a timestamp. This was already the case before this branch and was left alone.
- **Page Export on Employees, Inventory and Audit Log**: `exportCsv` is ready to wire, but those pages are outside this scope.

## Merge notes
- Run `chore(api): regenerate client` again after merging other branches that change the API.
- `home.ts` edits are additive: an operations section above the KPI row, activity text, price labels and chart labels. Expect small conflicts with the realtime and auth edits to the same file.
- The data-grid change only adds an `exportCsv` method. Merge it with the ui branch's `[error]`/`(retry)` inputs.
- `CashHandoverReviewModel` cites migration `e7b3c9d1f4a6`. If another branch also uses down_revision `c8d4e2f6a1b3`, add an Alembic merge revision.
- `pyproject.toml` import-linter `ignore_imports` gained entries for `dependencies.accounting` and `dependencies.dashboard`.

## ADR draft
**ADR-0xx: GST is configured per cylinder type; invoices are held, not issued at 0%.**
- **Context**
  - One tenant-wide GST rate cannot be right for both domestic (5%) and commercial (18%) LPG.
  - A missing rate silently produced 0% tax invoices.
- **Decision**
  - `tenant.cylinder_type` carries the HSN code and GST rate. The tenant-wide `gst_rate_percent` remains a fallback only.
  - When no rate resolves, invoice generation raises `GST_NOT_CONFIGURED`, and the order stays uninvoiced, visible and issuable from the Invoices screen once configured.
  - The invoice snapshots supplier state, place of supply, customer GSTIN, and HSN and rate per line, so a later configuration change never rewrites an issued invoice.
  - CGST/SGST versus IGST is derived from the snapshot.
  - Price-list amounts (and the cancellation charge) are before GST, and GST is added on top, unless the tenant sets `prices_include_gst` to true. In that case the taxable value is derived per line, rounded to paise, so the invoice total equals price x qty.
- **Consequences**
  - Agencies must classify cylinder types before invoicing.
  - Seed and demo data set rates explicitly.
  - Existing 0% invoices need an accounting correction outside the system.
