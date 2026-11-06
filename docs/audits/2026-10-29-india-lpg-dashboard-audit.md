# India LPG Compliance and Market-Fit Audit: Angular Dashboard

> **Recorded 2026-11-01 as a point-in-time snapshot.** The findings describe the code as of 2026-10-29. `main` has moved since (GST on orders, per-agency payments, notification settings and more), so a finding may already be fixed; none has been re-checked for this commit.

**Audit date:** 2026-10-29 · **Scope:** `frontend/` dashboard and the backend rules behind it · **Working tree:** uncommitted changes of 2026-10-29 (Payments settings, Warehouse to Godown wording, setup checklist "payments" step) were audited as they stand.

> This is an audit opinion on a software product, not legal, tax or safety advice. Every legal point marked "unverified" or "medium/low confidence" must be confirmed with a chartered accountant (GST, income tax), a PESO consultant (licences), a lawyer (DPDP, Aadhaar) or the OMC area office before the agency relies on it.

## 1. Summary

**Scope.** Every route, screen, report, print, export, notification and setting of the Angular dashboard in `frontend/`, followed into `backend/src/lpg/` where the behaviour is decided. 39 modules and screens were inventoried (section 3). Mobile apps are out of scope. Audit date 2026-10-29.

**Verdict.** The product is unusually careful about the mechanics of Indian tax and identity (GSTIN check digit, place of supply, Verhoeff-checked Aadhaar, 17-digit LPG ID, IFSC and PIN validation, per-line GST snapshots, a refusal to issue a 0% invoice). Its inventory, GRN, reconciliation and cash-handover flows fit how a godown really runs. The gaps are in three places: *who* is taxed at which rate (the LPG-specific rule), *what is allowed to leave the building* (expired documents, over-licence stock, secrets in logs and APIs), and *data-protection handling* that does not exist yet.

**Findings by severity** (68 findings; 0 Critical as written, with SEC-1 escalating to Critical if a non-production environment holds real consumer data and is reachable from the internet):

| Severity | Count | IDs |
|---|---|---|
| Critical | 0 | (SEC-1 is conditional) |
| High | 10 | TAX-1, TAX-2, TAX-3, TAX-4, KYC-1, KYC-2, DSP-1, GDN-1, AUD-1, SEC-1 |
| Medium | 33 | see sections 4 and 5 |
| Low | 25 | see sections 4 and 5 |
| Remove / simplify | 7 candidates | R1 to R7 in section 7 |

Two items in section 5 (XC-8, XC-11) are recorded as "no finding" and are not counted.

**The five things to act on first**

1. **Close the dev OTP endpoints outside local (SEC-1).** `GET /dev/otp-inbox/{phone}` returns any phone's login OTP with no authentication in every environment except `production`, and a delivery-OTP twin defeats proof of delivery. Register them only for `local`.
2. **Stop leaking secrets and Aadhaar (AUD-1, KYC-1, PAY-3).** The audit log stores every column of every row, including `password_hash` and the full bank account number, and serves them to anyone with `audit:read`. The full Aadhaar number is returned unmasked by the API and shown in full on screen. Redact the audit snapshot and mask Aadhaar to the last four digits.
3. **Fix the tax basis for household supply (TAX-1, TAX-2, TAX-8).** GST is chosen by cylinder type, not by buyer category, so a 14.2 kg cylinder sold to a restaurant and to a household takes one rate. The default price basis is GST-exclusive while the OMC's domestic RSP is already tax-inclusive (Charter section 5.3), so a household can be billed above the RSP. The form still allows the abolished 12% and 28% slabs.
4. **Make refunds and returns reportable (TAX-3), and decide on e-invoicing (TAX-4).** Credit notes hold an amount only and never reach GSTR-1. Ask the CA whether the agency is over the e-invoicing threshold; there is no IRN or e-way bill support.
5. **Let the system refuse unsafe operations (DSP-1, GDN-1).** Dispatch happily plans a hazardous-goods trip with an expired licence or lapsed insurance, and a godown can hold more cylinders than its Form F allows. Both are warnings in the calendar today and should be gates with an audited override.

DPDP substantive duties are reported to start on 13 May 2027 (S6), so the consent, retention, erasure, grievance and breach work (KYC-2, XC-1, XC-2) belongs in next quarter's plan, not in the go-live list.

**About the tree.** The Payments settings, Godown wording and setup-checklist change were uncommitted when this audit started and were committed as `189a406f` during it (see section 4 for the note). Findings about them cite that commit.

**About the evidence.** Statements marked "unverified" or confidence L need a CA, PESO consultant, lawyer or the OMC area office. This report is an audit opinion, not legal or tax advice. No test suite was run and the application was not exercised in a browser.

---

## 2. Method and sources

### 2.1 What was read

| Area | Read |
|---|---|
| Project context | `AGENTS.md`, `planning/MODULE_STATUS.md` (first 650 of 1,101 lines, which covers the master table, C1 to C12 and the 2026-08 to 2026-10 additions), `docs/business/glossary.md`, `business-rules.md`, `assumptions.md`, first 40 lines of `decisions.md`, `complaint-management.md` |
| Inventory | `frontend/apps/dashboard/src/app/app.routes.ts`, `shell/shell-layout.ts`, `settings/` (payments, agency, sections), `frontend/libs/*/feature-*` directories and their route files |
| Tax engine | `backend/src/lpg/domain/common/gst.py`, `application/accounting/gst.py`, `application/accounting/use_cases.py`, `domain/accounting/invoice.py`, `domain/accounting/credit_note.py`, `application/reporting/queries/get_gstr1_report.py`, `infrastructure/persistence/repositories/reporting.py`, `infrastructure/persistence/repositories/reference_number.py`, `application/printing/*`, `infrastructure/printing/templates/invoice.html` |
| Payments (today's change) | `application/accounting/payment_profile.py`, `payment_verification.py`, `api/v1/routers/payment_profile.py`, `infrastructure/payments/ifsc_directory.py`, `frontend/apps/dashboard/src/app/settings/payments/payment-settings.ts`, `application/tenant/setup_progress.py` |
| Customer, KYC, orders | `domain/customer/customer.py`, `identifiers.py`, `api/v1/schemas/customer.py`, `routers/customer.py`, `domain/order/booking_limits.py`, `api/v1/schemas/order.py` |
| Fleet, compliance | `domain/delivery/compliance_document.py`, `application/delivery/use_cases.py`, `domain/compliance/scale.py`, `cylinder_unit.py`, `tdt_rating.py` |
| Security | `infrastructure/persistence/audit.py`, `routers/dev_tools.py`, `infrastructure/identity/otp_delivery.py`, `config/settings.py`, `application/identity/*` (lockout, password length) |
| Frontend behaviour | cylinder types, tenant configuration, inventory, customers, GST filing, invoice drawer, formatters (`libs/shared/ui/src/lib/format/format.ts`, `libs/shared/util/src/lib/date-format.ts`) |

Not read in full, and so not audited at line level: the Flutter apps (out of scope), the generated API client, every spec file, `docs/` beyond the five files above, and lines 650 to 1,101 of `MODULE_STATUS.md`. Modules the report calls "inventory only" were classified from routes, nav, `MODULE_STATUS.md` and a skim of the code, not read end to end (Dispatch screen internals, Complaints screen internals, Notifications screen, Platform Console pages, Feature Flags, License pages, Design System page, Command palette).

The test suites were not run and the application was not exercised in a browser. All "what the code does" statements come from reading source.

### 2.2 What was checked online (checked 2026-10-29)

| # | Point | Source seen | Result | Confidence |
|---|---|---|---|---|
| S1 | GST slab structure from 22 Sep 2025: 5% merit, 18% standard, 40% de-merit; 12% and 28% removed | GST Council, 56th meeting press release, PDF fetched from `gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau_0.pdf` (text extracted and read: "Merit Rate of 5%", "de-merit rate of 40%", changes "with effect from 22nd September 2025"). The same release lists LPG only for motor vehicles (8703), not for cylinders | Confirmed from the primary release. LPG cylinders are not in the list of rate changes | High |
| S2 | LPG for household domestic consumers and for NDEC customers of IOCL/HPCL/BPCL: 5%; other petroleum gases of heading 2711: 18% | CBIC Notification 9/2025-Central Tax (Rate) dated 17 Sep 2025, effective 22 Sep 2025, as reproduced in CMA Knowledge schedule tables (Schedule I entries 208 and 209 at 5%; Schedule II entry 30 at 18%, excluding the LPG in entries 208 and 209). Earlier: Notification 01/2024-Central Tax (Rate), 4 Jan 2024 (taxguru summary) | The CBIC PDF itself could not be fetched (certificate error), so this is from a secondary reproduction of the notification | Medium |
| S3 | E-invoicing for aggregate turnover above ₹5 crore (Notification 10/2023-CT, from 1 Aug 2023); reporting within 30 days for ₹10 crore and above from 1 Apr 2025 | Search summaries of tax-portal articles (not CBIC text) | Consistent across sources, none official | Medium |
| S4 | E-way bill exempt for "LPG for supply to household and NDEC customers" (rule 138(14) Annexure) and for empty LPG cylinders moved other than for supply (Notification 26/2018-CT) | Search summaries of tax blogs | Official Annexure text not read | Medium |
| S5 | Cash receipt of ₹2 lakh or more in a day from one person: Section 269ST of the Income-tax Act 1961, penalty equals the amount (s.271DA); reported to continue as Section 186 of the Income-tax Act 2025 from 1 Apr 2026 | Search summaries only | The 2025 Act section number is not confirmed from the Act or a CBDT table | Medium on the rule, low on the new section number |
| S6 | DPDP Rules 2025 notified 13 Nov 2025. Institutional provisions in force; consent-manager rule 4 from 13 Nov 2026; notice, consent, security, breach, children, data-principal rights from 13 May 2027 (18 months). Proposal to cut 18 months to 12 was floated 22 Jan 2026 and, per trackers, not gazetted as of Oct 2026. Logs and personal data to be kept at least one year. Breach: to the Board and to affected people without delay, detailed report to the Board within 72 hours. CERT-In: 6 hours | AZB & Partners client alert (19 Nov 2025) and compliance trackers | Not read from the Gazette. Re-check the Gazette before relying on the May 2027 date | Medium |
| S7 | LPG retest: first at 10 years from manufacture, then every 5 years, through PESO-approved repairers | Government Lok Sabha reply (eparlib) as surfaced by search; it names IS 16054 for statutory testing, not IS 15975 | The code cites "Rule 35 with IS 15975" (`domain/compliance/cylinder_unit.py:19`), which I could not confirm | 10/5-year cycle: high. Rule and IS numbers: unverified |
| S8 | Gas Cylinders Rules 2016: godown storage licence is **Form F**; the Gas Cylinders (Amendment) Rules 2026 changed the NOC requirement for Form F (local-body NOC instead of district NOC), reported 5 May 2026 | Search summaries (lexplosion, an Assam government letter). Licence validity and exact rule number not found | Form F name: medium. Validity, quantity thresholds: unverified | Medium/low |
| S9 | **IOCL Citizen Charter on Marketing of Petroleum Products, September 2026**, read in full for the LPG chapter | `iocl.com/download/CitizenCharterofLPG21092026.pdf`, downloaded and text-extracted | See the findings that cite "Charter §5.3". It states: the RSP charged is inclusive of applicable taxes and home delivery charges; extra delivery charges only if approved by the State Government in consultation with the OMCs, and they must be shown separately in the cash memo; refill delivery endeavoured within seven working days; leakage complaints attended within 4 hours (emergency 1906); biometric Aadhaar authentication can be done by delivery personnel at delivery; termination voucher and deposit refund within one working day; PNG and LPG duplication rules (MoPNG notifications dated 24 Mar 2026 and 25 May 2026) | High (primary, OMC) |
| S10 | Legal Metrology: distributors must give delivery staff a check weigher; consumers may ask for weighing at delivery; state pages give one-year validity for platform scales | News report and state department pages | Rule text not read | Low/medium |
| S11 | Four Labour Codes in force from 21 Nov 2025; central rules and state rules still being finalised | KPMG flash note, trackers | Reported dates differ between sources | Medium |
| S12 | Aadhaar: regulation 6 of the Aadhaar (Sharing of Information) Regulations 2016 bars publishing or displaying an Aadhaar number; UIDAI promotes masked Aadhaar (last four digits); Aadhaar Data Vault expected for stored numbers | UIDAI FAQ and Regulations PDF links as surfaced by search; regulation text itself not read | Medium |
| S13 | Security deposits for a 14.2 kg domestic cylinder: ₹2,200 (IOCL, HPCL), ₹1,450 (BPCL), regulator ₹250 or ₹150 | Search summaries of OMC FAQs | The distributor's rate board is authoritative | Low/medium |

### 2.3 Could not verify

PESO licence validity and storage-quantity limits; the Gas Cylinders Rules 2016 rule numbers for retest and filling; Legal Metrology rule numbers and verification interval for check weighers; the current Marketing Discipline Guidelines (MDG) text (the code cites MDG 2022 and an "unconfirmed 2024 revision"); whether DAC is mandatory for every domestic delivery in the agency's OMC; Income-tax Act 2025 section numbers; the exact GST treatment of distributor commission, regulator and hose sales and new-connection charges; whether private entities may store the full Aadhaar number for OMC KYC. Each is carried into Open questions.

---

## 3. Module inventory

Status key: **working** = implemented and reachable; **partial** = reachable but material capability missing or unverified; **stub** = placeholder or not wired. Permission codes are from `app.routes.ts`. Status comes from `MODULE_STATUS.md` plus the code read; the dashboard has not been run in a browser for this audit.

| # | Module | Route | Permission | Purpose | Status |
|---|---|---|---|---|---|
| 1 | Sign-in, forgot and set password | `/login`, `/reset-password`, `/set-password` | none | Staff email and password sign-in, password reset and invitation links | working |
| 2 | License gate | `/license-required` | none | Blocks a tenant without an active platform licence | working |
| 3 | Home dashboard and setup checklist | `/` | any signed-in | Operational snapshot, refill-due list, new-agency setup steps | working |
| 4 | My Profile | `/settings/account` | any signed-in | Own name, phone, password | working |
| 5 | Agency settings (GST business profile) | `/settings/agency` | `tenant:read` | Supplier legal name, address, state, GSTIN, phone | working |
| 6 | Tenant configuration | `/settings/configuration` | `tenant:configure` | Free-form key/value tenant settings (GST fallback rate, prices include GST, cancellation fee, credit limit, AI, OMC rate ingestion, WhatsApp) | partial |
| 7 | Payments settings (new today) | `/settings/payments` | `tenant:configure` | Bank account, UPI ID, IFSC and UPI checks, invoice footer | partial |
| 8 | TDT rating configuration | `/settings/configuration/tdt-rating` | `tenant:configure` | OMC delivery-time star bands and fine schedule (tenant-entered) | partial |
| 9 | Feature flags (tenant) | `/settings/feature-flags` | `feature_flags:manage_tenant` | Per-tenant feature toggles | working |
| 10 | License | `/settings/license` | `license:manage_tenant` | Plan and licence status for the tenant | working |
| 11 | Linked devices | `/settings/license/devices` | `license:manage_tenant` | Devices tied to the licence | working |
| 12 | Customers and onboarding wizard | `/customers` | `customers:read` (not driver) | Consumer register, KYC documents with OCR, addresses, approval, closure | partial |
| 13 | Customer cylinder ledger | `/ledger/:customerId` | `ledger:read` | Per-consumer filled and empty cylinder balance | working |
| 14 | Orders | `/orders` | `orders:read` | Refill booking, assignment, cancellation, delivery proof (OTP, DAC) | working |
| 15 | Dispatch | `/dispatch` | `routes:read` | Route planning, load and dispatch, reconciliation, cash handover declaration | working |
| 16 | Complaints | `/complaints` | `complaints.manage` | Raise, assign, resolve complaints with SLA | partial |
| 17 | Invoices | `/invoices` | `invoices:read` | Invoice list, payments, credit notes, UPI QR, PDF and thermal print, send | partial |
| 18 | Cash handovers and cash book | `/cash-handovers`, `/cash-handovers/book` | `cash_handovers:review` | Driver cash declared versus counted; day's collections by mode | partial |
| 19 | Drivers | `/drivers` | `drivers:read` (not driver) | Driver register, licence, compliance documents | working |
| 20 | Vehicles | `/vehicles` | `vehicles:read` (not driver) | Fleet register, RC, insurance, fitness, PUC, PESO transport licence | working |
| 21 | Inventory | `/inventory` | `inventory:read` | Stock by location and status, GRN, transfers, adjustments, reconciliation, return to OMC, reorder policy | working |
| 22 | Godowns (was "Warehouses") | `/admin/warehouses` | `tenant:configure` | Storage locations | partial |
| 23 | Scales | `/scales` | `weighment:record` | Godown weighing scale registry and certificate expiry | working |
| 24 | Cylinder units | `/cylinder-units` | `cylinder_units:read` | Per-serial cylinder registry, custody, test due date | partial |
| 25 | Compliance calendar | `/compliance-calendar` | `compliance:read` | Expiry calendar for Form F, insurance, driver and vehicle documents | partial |
| 26 | Branches | `/admin/branches` | `tenant:configure` | Agency branches | working |
| 27 | Cylinder types | `/admin/cylinder-types` | `tenant:configure` | Sizes, HSN, GST rate | partial |
| 28 | Pricing | `/admin/price-lists` | `tenant:configure` | Price by cylinder type and customer type, OMC rate proposals | working |
| 29 | Users and roles | `/admin/users` | `users:manage` | Staff logins and permission editor | working |
| 30 | Employees | `/admin/employees` | `users:manage` | Staff directory; creates logins | partial |
| 31 | Audit log | `/admin/audit-log` | `audit:read` | Before and after states of data changes | partial |
| 32 | Reports (daily sales, driver performance, consumption, GSTR-1, TDT rating) | `/reports/*` | `reports:read` | Five reports with CSV export | partial |
| 33 | AI Command Center | `/ai-assistant` | `ai:read` | Question box over three read-only operational tools | partial |
| 34 | Notifications | `/notifications` plus bell and drawer | any signed-in | In-app notification list | working |
| 35 | Platform: Agencies | `/platform/agencies` | `tenant:manage_platform` | Vendor console: create agency, suspend, user recovery | working |
| 36 | Platform: Licenses | `/platform/licenses` | `license:manage_platform` | Issue and activate licences | working |
| 37 | Platform: Feature flags | `/platform/feature-flags` | `feature_flags:manage_platform` | Global flags | working |
| 38 | Design system | `/design-system` | none | Internal component reference | working (internal) |
| 39 | Command palette, no-access and not-found pages | global | n/a | Navigation helpers | working |

**39 modules and screens**: 34 tenant-facing (rows 1 to 34, including sign-in and the licence gate), 3 vendor Platform Console modules (rows 35 to 37) and 2 system or internal screens (rows 38 and 39).


> **Which tree was audited.** When this audit began, the Payments verification, setup-checklist and Godown changes were uncommitted in the working tree. During the audit they were committed to branch `feat/payment-setup-verification` as `189a406f` and the checkout moved back to `main`. Citations marked `@189a406f` are lines in that commit (the state I read). Every other citation is unchanged between that commit and `main`.

---

## 4. Findings by module

Finding columns: **ID**, claim, evidence (`path:line`), rule or norm touched, **Sev**, **Conf** (confidence in the legal or factual point: H, M, L), recommended fix. "Code" means I read it; "inferred" means I did not trace it end to end.

### 4.1 Tax engine, Cylinder Types, Pricing, Invoices (modules 5, 6, 17, 27, 28)

**What it does today.** An invoice is generated automatically from a delivered order (`application/accounting/use_cases.py:186-380`). Each line takes its HSN and GST rate from the *cylinder type* (`application/accounting/gst.py:103-142`), computes CGST+SGST or IGST from the agency state against the customer's GSTIN or address state (`gst.py:162-195`, `domain/common/gst.py:141-157`), and rounds to paise half-up. GSTIN is validated with check digit and state match (`domain/common/gst.py:86-103`, `domain/tenant/tenant.py:97-110`). Prices are GST-exclusive unless a tenant flag says otherwise. Invoice numbers are `INV-<year>-<6 digits>`. Cancelled invoices are excluded from GSTR-1. A GSTR-1 style summary (B2B 4A, B2C large 5, B2C small 7, HSN 12) is produced as CSV. The PDF has supplier block, GSTIN, place of supply, HSN, rate, CGST/SGST or IGST, amount in words and a "reverse charge: no" line.

**Market fit.** Strong on the mechanics a CA checks first: GSTIN checksum, place of supply, no 0% fall-back (`gst.py:1-10`), a per-line snapshot of HSN and rate. Weak on the LPG-specific rule that drives the sale: the rate depends on *who* buys, not on the cylinder.

| ID | Finding | Evidence | Rule / norm | Sev | Conf | Fix |
|---|---|---|---|---|---|---|
| TAX-1 | GST rate and HSN are attached to the cylinder type only. The same 14.2 kg cylinder sold to a household (5%) and to a restaurant (18%) takes one rate, so one of them is mis-taxed unless the agency invents separate "14.2 kg domestic" and "14.2 kg commercial" types. Nothing stops a domestic type being sold to a Commercial customer. A tenant-wide legacy `gst_rate_percent` silently fills any type that has no rate. | `application/accounting/gst.py:103-142`; `domain/tenant/cylinder_type.py:28-36,95-101` (no category field); the price list is per type and customer type (`domain/tenant/price_list.py:22,40-48`) but tax is not | Notification 9/2025-CT(Rate): 5% only "for supply to household domestic consumers" and NDEC customers; other 2711 supplies 18% (S2) | High | M | Decide the rate from (cylinder type, customer type, NDEC flag). At minimum add a category on the cylinder type and refuse an order line whose category does not match the customer type. Remove the legacy tenant-wide fall-back. |
| TAX-2 | Default pricing basis is GST-exclusive: the price-list amount is before GST and the invoice adds GST on top. For domestic LPG the OMC Retail Selling Price is already inclusive of taxes and delivery. An agency that keys the RSP into Pricing and leaves the default bills the household RSP plus 5%, above the RSP. The flag is one tenant-wide switch, so a tenant selling RSP-based domestic gas and ex-GST commercial gas cannot be right for both. | `application/accounting/gst.py:78-100` (docstring: default False, "the product owner's choice"); `tenant-configuration-page.ts:45-49`; Charter section 5.3 (S9): "RSP ... inclusive of applicable taxes and home delivery charges" | LPG Control Order and OMC MDG: nothing over the cash-memo price may be recovered (MDG text not read) | High | M | Make inclusive versus exclusive a property of the price-list row (customer type), default inclusive for Domestic. Add a pre-save check that a domestic price is not above the OMC-notified RSP for the city (the OMC rate ingestion already holds these). Confirm with the product owner: the current default was a stated choice. |
| TAX-3 | Credit notes carry an amount and a reason only. There is no taxable value, no tax split, no link to invoice lines, no printable credit note (print supports only `invoice` and the cylinder label), and the GSTR-1 summary has no credit-note table. A refund therefore cannot reduce output tax in the return. | `domain/accounting/credit_note.py:38-100`; `application/printing/use_cases.py:126-128`; `application/reporting/queries/get_gstr1_report.py:1-14` | CGST Act s.34 (credit note reported in the return); rule 53 content | High | H | Store taxable value and tax per credit note, proportional to the invoice lines; add a credit-note PDF and a credit/debit-note table in the GSTR-1 view and export. |
| TAX-4 | No e-invoice (IRN and QR) and no e-way bill. For an agency above ₹5 crore turnover, B2B invoices to GST-registered commercial and institutional customers need an IRN. A consignment of commercial cylinders above the e-way threshold needs an e-way bill (household and NDEC LPG is exempt, S4). Neither is mentioned in code or docs. | repo grep for IRN, e-invoice, e-way: only HSN-rule comments; `invoice.html:211-212` prints plain "TAX INVOICE / Original for recipient" | Notification 10/2023-CT (S3); CGST rule 138 | High | M | Add a tenant switch "e-invoicing applicable". When on, call an IRP or GSP at issue time, store IRN and ack date, print the QR. Decide with the CA whether to integrate or export JSON for a GSP. |
| TAX-5 | GSTR-1 support is a CSV per table. There is no portal-ready JSON, no GSTR-3B totals, no document-series summary (table 13), no credit or debit notes. | `gst-filing.ts:106-110`; `gst-filing.html` (four tables only) | GSTR-1 and 3B filing | Medium | M | Add GSTR-1 JSON export for the offline tool, a 3B summary (outward taxable value, tax by head) and a document-series table. |
| TAX-6 | The invoice PDF has no round-off line and no supplier signature block; the footer says "No signature required". It prints once as "Original for recipient". Amounts use western grouping (`1,234,567.00`). | `invoice.html:300,403,212`; `application/printing/models.py:58-85` (no round-off field) | CGST Rules r.46 (supplier signature or digital signature, waived for e-invoice; triplicate for goods invoices) | Medium | M | Add an authorised signatory or digital signature, copy labels for B2B goods invoices, a round-off line to the nearest rupee, and lakh grouping. Confirm the r.46 signature point with the CA. |
| TAX-7 | An agency with no GSTIN still issues an "INVOICE" with tax columns once rates exist. An unregistered supplier cannot collect GST and must issue a bill of supply. | `invoice.html:211`; no GSTIN check in `gst.py`; `AgencyBusinessProfile.gstin` is optional (`domain/tenant/tenant.py:47-52`) | CGST Act s.31(3)(c), s.9 | Medium | M | When the agency GSTIN is blank, title the document "Bill of Supply" and force tax to zero, or block invoicing until the profile is complete. |
| TAX-8 | Valid GST slabs have changed. The backend accepts any rate from 0 to 28 and the form says "The highest GST rate is 28%". Since 22 Sep 2025 the slabs are 0/5/18/40 (S1); 12% and 28% no longer exist, yet both pass validation. | `domain/common/gst.py:62,114-118`; `cylinder-types-page.ts:233` | GST rate notifications (S1) | Medium | H | Replace the 0-28 range with an allow-list (0, 5, 18, and 40 only if ever needed) and fix the form text. |
| TAX-9 | The default HSN offered for every cylinder type is `27111900`. The notified entries for LPG cite tariff item 2711 19 10. | `cylinder-types-page.ts:39`; S2 | HSN on invoice and GSTR-1 table 12 | Low | L | Ask the CA whether `27111910` should be the default. |
| TAX-10 | The invoice number is `INV-<calendar year of UTC now>-<counter>`. The counter never resets, so the series is consecutive, but the year token is the calendar year in UTC, not the Indian financial year. A January to March invoice carries the wrong FY label and the token flips at 05:30 IST. | `infrastructure/persistence/repositories/reference_number.py:75-78`; `api/v1/dependencies/accounting.py:157` | CGST Rules r.46(b): consecutive serial, unique per financial year, up to 16 characters | Low | H | Use the Indian FY label (for example `2026-27`), reset per FY, keep it to 16 characters or fewer. |
| TAX-11 | No delivery or handling charge, and no preferred-time-delivery fee, can be invoiced as a separate line. Only supply and cancellation-charge lines exist. The Charter requires any approved extra delivery charge to appear separately on the cash memo. | `domain/accounting/invoice.py:215` (`INVOICE_LINE_KINDS`); Charter section 5.3 (S9) | LPG Control Order; OMC charter | Medium | M | Add a line kind `delivery_charge`, gated by a state-approved amount in tenant configuration, taxed with the supply. |
| TAX-12 | The document says "Invoice", not "Cash Memo". The glossary lists the swap as awaiting sign-off. The OMC charter says emergency numbers are printed on the cash memo. | `docs/business/glossary.md:47`; Charter section 8 (S9) | OMC practice | Low | M | Print "Cash Memo / Tax Invoice" for B2C refill sales and add the OMC emergency and toll-free numbers to the footer. |
| TAX-13 | Invoices are generated after the delivery event (`issued_at` is the delivered time). For goods the invoice is due at or before removal. For a doorstep cylinder sale a same-day post-delivery invoice is common practice, but an auditor may ask. | `application/accounting/use_cases.py:223-262` | CGST Act s.31(1) | Low | L | Ask the CA; if needed, issue at dispatch for B2B. |

**Missing.** Debit notes; cancelling an issued B2B invoice with a credit note and audited reason; GSTR-3B totals; TDS and TCS handling (probably not applicable to a retail distributor, confirm with the CA).

**Candidates to remove or simplify.** The tenant-wide `gst_rate_percent` configuration key and its "GST Rate (%)" editor (see 4.8): superseded by per-type rates, still used as a silent fall-back (`gst.py:131-141`).

### 4.2 Payments settings, Cash handovers and Cash book (modules 7, 18)

**What it does today (the change under review).** A Payments page (`@189a406f payment-settings.ts`) stores the agency's bank account, UPI ID and invoice footer as one historised tenant-configuration value (`payment_profile.py:1-8`). New in the change: an account-number confirmation field, an IFSC check against the public `ifsc.razorpay.com` directory with auto-fill of bank and branch, a "Verify UPI ID" button, and a setup-checklist step "payments". The UPI QR for an order or invoice is a `upi://pay` deep link with the amount filled in (`payment_profile.py:118-134`). The cash book is a daily summary: collections by mode and what became of driver cash.

**Market fit.** The IFSC check and the double entry of the account number address the commonest operational error (a mistyped account on every invoice). The UPI check is honest in its own note, but the button name and the green tick say more than the code proves.

| ID | Finding | Evidence | Rule / norm | Sev | Conf | Fix |
|---|---|---|---|---|---|---|
| PAY-1 | "Verify UPI ID" checks the pattern and whether the handle is in a hard-coded list of about 50 handles. It never asks a bank or PSP whether the VPA exists or whose it is (`account_confirmed` is always false). The result line "Valid format. @ybl is issued by PhonePe" reads as confirmation. A wrong VPA is printed on every invoice and QR. | `payment_verification.py:21-88`, `payment-settings.ts:234-251,433`, `routers/payment_profile.py:124-170` (all @189a406f) | NPCI and PSP VPA validation | Medium | H | Rename to "Check UPI ID". Show "not verified" until a PSP VPA lookup or Rs 1 penny-drop confirms the payee name. Until then, make the page's own advice (scan the QR once from another app) a setup-checklist step. |
| PAY-2 | Bank "verification" is IFSC existence only. There is no account-holder name match (penny drop). If the directory is unreachable the save proceeds ("the code looks right"). An IFSC of one bank can be saved beside the name of another bank. | `payment_verification.py:104-133`, `routers/payment_profile.py:98-121` (@189a406f) | Payment accuracy | Low | H | Cross-check the bank name from the IFSC against the typed bank name and warn on a mismatch. |
| PAY-3 | The full bank account number is stored in tenant configuration as plain JSON, returned in clear by `GET /payment-profile` to **any signed-in user, including the customer role** (it is printed on invoices anyway), and copied into the audit log on every save (AUD-1). | `application/accounting/payment_profile.py:51-61`; `routers/payment_profile.py:87-95` (@189a406f); `infrastructure/persistence/audit.py:70-73` | DPDP security safeguards (from May 2027) | Medium | M | Return the account number masked to roles that do not manage payments; keep the full number for print only. Exclude `payment_profile` values from audit snapshots. |
| PAY-4 | The QR is a per-order UPI link on the agency's own VPA with `pa`, `pn`, `am`, `tn`, `tr` but no merchant category code. If the VPA is a personal savings VPA, apps and banks may treat receipts as person-to-person, with limits and scrutiny. Payment is recorded by hand; nothing reconciles the bank statement to the QR. | `payment_profile.py:118-134` (@189a406f); `Payment.reference` is free text (`domain/accounting/invoice.py:134-141`) | NPCI and RBI P2M versus P2P rules (not verified) | Medium | L | Ask the agency's bank for a merchant VPA or dynamic merchant QR. Treat the Razorpay payment-link path (module 31 in `MODULE_STATUS.md`) as the reconciled option and the manual QR as the fallback. |
| PAY-5 | The form accepts up to 22 digits and spaces for the account number; the API accepts 9 to 18 digits. A 19 to 22 digit number passes the form and fails on save with only a toast. | `payment-settings.ts:37` (@189a406f); `payment_profile.py:36` | Form accuracy | Low | H | Align the pattern to 9 to 18 digits after stripping spaces. |
| CASH-1 | No guard for cash receipts of ₹2 lakh or more from one person in a day. Commercial, industrial and government customers can be billed and paid in cash without a warning. | repo grep for `269` and `cash_limit`: no hits; cash is in `STAFF_PAYMENT_METHODS` (`domain/accounting/invoice.py:208-210`) | Income-tax Act s.269ST, reported as s.186 of the 2025 Act (S5): ₹2 lakh per person per day, per transaction or per event; penalty equals the amount | Medium | M | Warn at 50% of the limit and block at ₹2 lakh aggregate cash per customer per day, with an audited override reason. Ask the CA for the correct section reference. |
| CASH-2 | The "Cash book" is a collections summary, not a cash book: no opening and closing balance, no payments out (expenses, advances, bank deposits), no bank-deposit tie-out. | `cash-book.ts:44-64`; `application/accounting/ports.py:163-182` | Books of account | Medium | H | Rename to "Daily collections", or build the missing half: opening cash, payments out, bank deposits, closing cash, difference. |

Driver cash accountability works as designed and is a strength: cash collected per route, counted handover, shortfall, accept or dispute (BR-32; `application/accounting/use_cases.py:509-640,813-880`). Add a daily cut-off and a limit on cash a driver may hold overnight.

**Missing.** Cheque details (number, bank, date, bounce handling), UTR matching, bank-statement import, daily bank-deposit record.

**Candidates to remove or simplify.** None. The cash-book name is the issue, not the feature.

### 4.3 Customers, KYC and the Cylinder Ledger (modules 12, 13)

**What it does today.** A staff wizard registers a customer, can OCR an Aadhaar or PAN photo, takes an address with PIN code, a GSTIN for business customers and the 17-digit LPG ID, and runs approval. KYC documents (Aadhaar, PAN, voter id, driving licence, passport) are stored with Verhoeff, PAN and licence format checks and the number encrypted at rest. The ledger tracks cylinders per customer. A closure endpoint ends a connection.

**Market fit.** Identifier validation is better than most products (`domain/customer/identifiers.py:24-120`). The consumer record misses OMC attributes that matter at an inspection, and data-protection handling is absent.

| ID | Finding | Evidence | Rule / norm | Sev | Conf | Fix |
|---|---|---|---|---|---|---|
| KYC-1 | The full 12-digit Aadhaar number is returned unmasked by the API to everyone with `kyc:read` (which the router docstring says includes the customer role) and printed in full in the customer detail drawer. It is encrypted only at rest. | `api/v1/schemas/customer.py:50-58`; `api/v1/routers/customer.py:473-516`; `feature-customers.html:338`; `infrastructure/persistence/repositories/customer.py:355-372` | Aadhaar Act and Regulations (reg. 6, no display or publication of the number); UIDAI masked-Aadhaar practice (S12); DPDP security safeguards | High | M | Show only the last 4 digits in API and UI. Keep the full number only if a documented legal basis requires it, in a separate vault-style store, revealed behind an explicit action that writes an audit entry. Prefer storing the card image and a reference to storing the number. |
| KYC-2 | No notice, consent record, purpose, retention period, erasure or data-principal request handling anywhere in the dashboard or backend. Closure is a soft status change; KYC documents and phone numbers live forever. | repo grep: no `consent` in dashboard code, no retention or purge job (`application/ai/ports.py:120` is the only retention mention) | DPDP Act ss.5-8, 12-13 and the Rules (substantive duties from about 13 May 2027, S6); IT SPDI Rules 2011 meanwhile | High | M | Design now: notice text at onboarding in English and the customer's language, consent or legitimate-use basis per purpose, a consent ledger, a retention schedule, an export and erasure workflow, and a grievance-officer field in Agency settings. |
| KYC-3 | Reads of KYC documents are not audited. The audit trail is a SQLAlchemy `before_flush` hook, so it records creates, updates and deletes only. | `infrastructure/persistence/audit.py:145-165`; `routers/customer.py:494-516` | DPDP Rule 6 (access logs kept one year, S6); Aadhaar security | Medium | M | Write an access-log row whenever KYC details or images are viewed, with user, customer and reason. |
| KYC-4 | Connection closure does not verify that cylinders were returned, does not check the cylinder ledger is zero, and has no security-deposit refund or termination-voucher step. It reads only the invoice balance and records it. BR-34 says closure requires those checks in order. | `domain/customer/customer.py:555-578`; `application/customer/use_cases.py:510-522`; `docs/business/business-rules.md` BR-34 | Charter section 5.4 and its table (S9): termination voucher and deposit refund within one working day | Medium | H | Block closure while the ledger shows cylinders held; record the deposit refund as a ledger transaction with a document number; print a termination voucher. |
| KYC-5 | The customer record lacks fields an OMC inspector and a DBTL query ask for: connection type (single or double bottle, domestic or NDEC, PMUY), subsidised flag, biometric Aadhaar authentication (e-KYC) status, equipment issued (cylinders, regulator, hose), security deposit paid and date. The LPG ID is stored as `lpg_subsidy_id`. | `api/v1/schemas/customer.py:79-95,107-108` | Charter sections 5.1 and 5.9 (S9) | Medium | M | Add these fields, or state that the OMC portal stays the record and this system holds only the delivery view (OQ-1). |
| KYC-6 | The agency generates its own consumer number (`NextConsumerNumberResponse`). Real consumer numbers are issued by the OMC. The field is free text up to 50 characters with no format check. | `api/v1/schemas/customer.py:98,138-139,186` | OMC consumer numbering | Low | L | Take the OMC consumer number as input for existing consumers and mark generated numbers as internal. |
| KYC-7 | Mobile numbers are normalised to +91 but not checked for a valid Indian mobile prefix (6 to 9) after normalisation. | `domain/common/phone.py:22-39` | Local fit | Low | H | Reject +91 numbers that are not 10 digits starting 6 to 9. |
| KYC-8 | The KYC photo OCR runs in the backend (RapidOCR). Whether images leave the country was not traced. | `infrastructure/ocr/rapidocr_adapter.py` | DPDP cross-border transfer | Low | L | Confirm in the data-flow note that OCR is local. |

**Missing.** Consumer transfer and termination vouchers (TV, TTV); duplicate-connection detection across households; PNG and LPG duplication check (MoPNG notices dated 24 Mar and 25 May 2026, Charter section 5.5); preferred-time-delivery option.

**Candidates to remove or simplify.** None. Keep the OCR, but make it opt-in per agency until KYC-2 is designed.

### 4.4 Orders and Dispatch (modules 14, 15)

**What it does today.** Staff book refills (booking source stored). The system checks holding limit and credit limit when configured. The order is assigned to a route; the driver loads (with an optional weighment gate) and delivers with the platform's own delivery OTP, GPS and the optional OMC DAC; the invoice follows. Failed delivery, reschedule, amend and cancel-with-approval exist.

| ID | Finding | Evidence | Rule / norm | Sev | Conf | Fix |
|---|---|---|---|---|---|---|
| ORD-1 | No refill-interval rule, no annual subsidised-cylinder cap, no PNG-and-LPG duplication check. The holding limit is "unlimited" unless the agency configured one, and an unreadable value also means unlimited. The OMC portal is the real gatekeeper, so a booking accepted here may be refused there. | `domain/order/booking_limits.py:1-35`; Charter section 5.5 (S9) | OMC refill rules; MoPNG notices of 24 Mar and 25 May 2026 | Medium | M | Decide whether this system is the booking record or a mirror (OQ-1). If the record, add the interval and cap per OMC rules by customer type. If a mirror, show the OMC booking number on the order. |
| ORD-2 | The OMC Delivery Authentication Code is a manually keyed, optional field validated as "six digits" only; it never gates delivery. The platform's own OTP gates delivery, so a consumer can receive two codes. | `api/v1/schemas/order.py:216-233`; `application/order/use_cases.py:842` | OMC DAC practice (mandatory scope unverified) | Medium | L | Make DAC required per OMC area setting, store the OMC order id beside it, and avoid a second code to the consumer where the OMC enforces DAC. |
| ORD-3 | The cancellation fee is one flat amount for every customer type, households included. | `domain/order/cancellation_fee.py`; `tenant-configuration-page.ts:50-54` | OMC and consumer-protection norms (a household cancellation fee is not something the Charter provides for; not verified) | Medium | L | Ask the OMC area office; apply fees by customer type. |
| DSP-1 | Route planning and dispatch do not check the driver's licence or the vehicle's insurance, fitness, PUC or PESO transport licence. Expiry is only notified by a nightly job and shown in the calendar. A driver with an expired licence or a vehicle with lapsed insurance can be planned and dispatched with a load of cylinders. | `application/delivery/use_cases.py:598-620` (`PlanRouteUseCase` checks only that the crew is free); `:866-1045` (load and dispatch check stock and weighment only); `domain/delivery/compliance_document.py:1-60` | Motor Vehicles Act (licence, insurance, fitness, pollution); hazardous-goods driver endorsement; PESO vehicle approval | High | M | Block plan and dispatch when a required document is expired or unverified, with a manager override that records a reason. Make the required list per vehicle and driver a tenant setting. |
| DSP-2 | No per-vehicle weighing instrument or check-weigher register. The Scales module is bound to a godown. Distributors are expected to equip delivery staff with a verified weighing instrument, and consumers may ask for weighing at delivery. | `domain/compliance/scale.py:1-30` (warehouse-bound); S10 | Legal Metrology (Packaged Commodities) Rules 2011 and state verification rules (unverified) | Medium | L | Allow a scale to be assigned to a vehicle or crew, add verification-due alerts, and link a short-delivery complaint to the weighing result. |
| DSP-3 | Vehicle registration number and driving licence number have no format validation (for example `MH12AB1234`, BH series, `MH12 20110012345`). A customer DL pattern already exists. | `domain/delivery/vehicle.py`, `domain/delivery/driver.py` (no pattern); `domain/customer/identifiers.py:85` | Local fit | Low | H | Reuse the existing patterns. |
| DSP-4 | No accident, leakage, fire or near-miss register and no reporting workflow. The only link is the complaint category "GasLeakSafety". | `domain/complaint/value_objects.py:9-12`; `compliance_document.py:55-58` ("accident-notification workflow" deferred) | Gas Cylinders Rules accident reporting and PLI Act claims (clauses unverified) | Medium | L | Add an incident register with date, place, vehicle, injuries, report-to-PESO and OMC status, and attachments. |

**Missing.** Preferred-time delivery; delivery challan for goods in transit; e-way bill for commercial consignments (TAX-4); cylinder seal and tamper check; delivery-staff biometric Aadhaar authentication option recorded on the order (Charter section 5.9); route km and delivery-charge slabs.

**Candidates to remove or simplify.** None.

### 4.5 Drivers and Vehicles (modules 19, 20)

**What it does today.** Registration requires a driving licence or RC document. A compliance panel attaches driving licence, hazmat endorsement, TREM card, training certificate, RC, insurance, fitness, PUC and PESO transport licence with expiry and verified status. A nightly job notifies expiry.

**Market fit.** A good document list for a hazardous-goods fleet. The documents inform; they do not control (DSP-1).

| ID | Finding | Evidence | Rule / norm | Sev | Conf | Fix |
|---|---|---|---|---|---|---|
| FLT-1 | The driver record has no date of birth or age check, no medical fitness and no police verification field. | `domain/delivery/driver.py:109-120` | Motor Vehicles Act age rules; OMC delivery-staff verification norms (unverified) | Low | L | Ask the OMC area office what verification it expects for delivery staff. |
| FLT-2 | Vehicle capacity is a unit count with no link to the PESO-approved quantity for that vehicle. | `domain/delivery/vehicle.py:116-121` | PESO vehicle approval (unverified) | Low | L | Store the approved cylinder count from the PESO transport licence and block loads above it. |

**Candidates to remove or simplify.** None.


### 4.6 Inventory, Godowns, Scales, Cylinder Units, Compliance Calendar, TDT rating (modules 8, 21 to 25)

**What it does today.** Inventory handles stock by godown, vehicle and customer; cylinder condition (filled, empty, damaged, leakage, quarantine, scrap, repair); a GRN with OMC, challan, invoice and truck number and a weighment sample; load transfer; delivery and collection; adjustments with reasons; reconciliation with approve and reject; return to OMC; and a daily stock register (opening, receipts, issues, closing). Scales hold a certificate expiry. Cylinder Units hold per-serial identity with a statutory test due date. The Compliance Calendar collects expiries of Form F, tenant insurance, and driver and vehicle documents.

**Market fit.** The inventory flow matches how an Indian godown works and is the strongest module. The compliance modules are real, but some rule numbers in comments need checking and the registers are narrower than a PESO inspection.

| ID | Finding | Evidence | Rule / norm | Sev | Conf | Fix |
|---|---|---|---|---|---|---|
| GDN-1 | A godown has no licensed quantity, licence number, validity or capacity field. Stock is never compared to the Form F licensed limit, so a godown can hold more cylinders than its licence allows with no warning. | `domain/tenant/warehouse.py` (no capacity or licence fields); `warehouses-page.ts`; Form F is only a document type (`domain/delivery/compliance_document.py:62-65`) | Gas Cylinders Rules 2016 licence conditions, Form F (S8) | High | M | Add licensed quantity by cylinder category to the godown, show utilisation on Inventory, warn at 90% and block receipt above 100% with an audited override. |
| GDN-2 | The Compliance Calendar covers Form F and insurance only; fire NOC, trade or Shops licence, Legal Metrology registration, pollution consent and the biennial safety inspection are explicitly deferred. | `compliance_document.py:55-58,62-68`; `MODULE_STATUS.md` row 20 | PESO, fire-safety law, Shops and Establishments Act (state-specific) | Medium | M | Add document types for these, owner = godown or tenant. |
| CYL-1 | Source comments cite "Rule 26", "Rule 35" and "IS 15975" for the retest rule. The 10-year first test and 5-year repeat match a government Lok Sabha reply (S7), but that reply names IS 16054 for statutory testing. The rule numbers and the IS number could not be confirmed. | `domain/compliance/cylinder_unit.py:14-27,86-92` | GCR 2016 retest; standard citation | Low | L | Re-check against the Gas Cylinders Rules text and correct the comments and any user-visible label. |
| CYL-2 | The per-serial registry is not wired into the bulk flows (GRN, load, delivery). Staff register serials by hand in a separate screen, in parallel with bulk counts, and in practice the OMC fills and tests cylinders. | `cylinder_unit.py:34-44` (bulk integration deferred) | Operational burden | Medium | M | See section 7. Keep behind a feature flag until a scan-based GRN and delivery flow exists. |
| TDT-1 | TDT star bands and fine percentages are tenant-entered, and the aggregate formula and consecutive-quarter rule are marked "UNCONFIRMED against the actual MDG clause text". The report screen can show a star rating that looks official. | `domain/compliance/tdt_rating.py:5-24,134-141,187`; `MODULE_STATUS.md` row 20 | OMC TDT scheme (circular not seen) | Medium | M | Label the report "Indicative, not the OMC's rating" until the bands are copied from the OMC circular for the agency's OMC and edition. |
| SCL-1 | The scale record is bound to a godown and holds a certificate expiry; it does not record the Legal Metrology verification date, stamp number or verifying authority. | `domain/compliance/scale.py:1-30` | Legal Metrology Act 2009 (verification and stamping, S10) | Low | L | Add stamp number and verification date so an inspector's question can be answered from the screen. |
| STK-1 | The GRN captures OMC challan, invoice and truck number, but nothing compares the quantity on the OMC invoice with the quantity received to raise a short-supply claim. | `feature-inventory.html:326-420` | OMC supply claims | Low | L | Add "invoice quantity" and compute short receipt on the GRN. |

**Missing.** A cylinder movement register in the form the OMC inspects; a defective-cylinder and leakage return slip to the OMC with a claim number; reconciliation between OMC dispatch statements and receipts.

### 4.7 Complaints (module 16)

**What it does today.** Staff raise, assign and resolve complaints with category (short delivery, damaged cylinder, billing, driver conduct, late delivery, gas leak or safety, other). The SLA comes from priority: Critical 4 hours, High 24, Medium 48, Low 72. Gas-leak and safety complaints are forced to Critical.

| ID | Finding | Evidence | Rule / norm | Sev | Conf | Fix |
|---|---|---|---|---|---|---|
| CPL-1 | The SLA table is hard-coded though the module spec and BR-31 say it should be tenant-configurable. Critical at 4 hours matches the Charter leakage target (S9). | `domain/complaint/complaint.py:184-195`; `docs/business/complaint-management.md` section 2.3 | Consumer Protection Act; OMC charter table | Low | M | Move to tenant configuration and add the escalation chain. |
| CPL-2 | A gas-leak complaint raised on the dashboard produces a record and an SLA but no on-screen instruction to call the OMC emergency number 1906, and no OMC escalation or reference field. | `domain/complaint/value_objects.py:9-12`; Charter section 8 (S9) | Safety; OMC emergency service | Medium | M | Show the emergency numbers on the gas-leak form and store an OMC reference. |
| CPL-3 | Short-weight and short-delivery complaints do not capture a re-weigh result or the cylinder serial. | `domain/complaint/value_objects.py:5` | Legal Metrology | Low | L | Add weight and serial fields to those categories. |

**Candidates to remove or simplify.** None.

### 4.8 Administration: Users, Employees, Audit log, Branches, Configuration, Flags, Licence (modules 6, 9, 10, 11, 26, 29 to 31)

**What it does today.** Staff users get a role (agency admin, manager, godown staff, dispatcher, accountant) and an editable permission set. Passwords need 12 characters and lock after 5 failures for 15 minutes; access tokens last 15 minutes (`config/settings.py:244-262`). Audit rows record who changed what, with before and after.

| ID | Finding | Evidence | Rule / norm | Sev | Conf | Fix |
|---|---|---|---|---|---|---|
| AUD-1 | The audit snapshot copies **every mapped column** of every audited row into `before_state` and `after_state`, with no redaction, and the Audit Log API returns both to anyone with `audit:read`. That includes the user row's `password_hash` and the full bank account number inside `payment_profile` on every save. | `infrastructure/persistence/audit.py:70-73,145-165`; `infrastructure/persistence/models/identity.py:84`; `api/v1/schemas/admin.py:370-371`; `api/v1/routers/admin.py:1387-1388` | OWASP A02 and A09; DPDP security safeguards | High | H | Add a per-table allow-list of audited columns; never snapshot `password_hash`, token or OTP hashes, encrypted KYC fields or payment details. Purge existing rows. |
| USR-1 | No second factor for any staff account, including accountant and agency admin accounts that can see KYC, bank details and cash. | grep for MFA or TOTP in backend: no hits; `application/identity/login.py` | IT Act s.43A "reasonable security"; CERT-In practice | Medium | M | Offer TOTP or SMS second factor; require it for agency admin and accountant. |
| USR-2 | "Users & Roles" and "Employees" both sit under `users:manage` and overlap: registering an employee also creates a login, inviting a user creates a login without an employee record. Wages, PF/ESI numbers, joining date and attendance are not stored anywhere. | `app.routes.ts:397-425`; `domain/tenant_admin/employee.py:99-120` (name, phone, email, role, branch only) | PF, ESI, minimum wages, Shops and Establishments registers; Labour Codes in force from 21 Nov 2025 (S11) | Medium | H | Decide whether Employees is a payroll-lite register or a staff directory. If a directory, merge it into Users. If HR, add joining date, UAN and ESIC numbers, wage and leave. |
| CFG-1 | Tenant configuration is a free-form key and value editor, so business-critical switches (prices include GST, weighment gate) are typed as text and parsed leniently ("true", "yes", "1", "inclusive"). `MODULE_STATUS.md` records a Python `bool("false") is True` bug already hit once. | `application/accounting/gst.py:78-100`; `tenant-configuration-page.ts:39-62`; `MODULE_STATUS.md` row 21 | Configuration safety | Low | M | Replace with typed controls (switch, number, select) for keys the product owns. |

**Missing.** Grievance officer name and contact (DPDP), data-retention settings, and an agency profile holding PAN, OMC name, distributor code and sales area.

### 4.9 Reports, AI Command Center, Notifications (modules 32 to 34)

| ID | Finding | Evidence | Rule / norm | Sev | Conf | Fix |
|---|---|---|---|---|---|---|
| RPT-1 | Five reports exist (daily sales, driver performance, consumption, GSTR-1, TDT). Missing for a distributor: customer outstanding ageing, sales-and-stock statement against OMC receipts, cylinder movement register, PMUY and subsidy statements, daily cash memo register, GSTR-3B summary. | `libs/reporting/feature-reports/src/lib/lib.routes.ts:1-35` | Audit and OMC inspection | Medium | M | Add ageing, stock versus OMC receipts and cash memo register first. |
| RPT-2 | No Indian financial-year (April to March) presets in report filters. | `report-filters.ts`; grep for financial year: none | Local fit | Low | H | Add This FY, Last FY and Quarter presets. |
| AI-1 | The AI Command Center has three read-only tools (today's delivery status, inventory overview, open-complaint summary), numbers the Home dashboard already shows (`feature-ai-assistant.ts:215-236` repeats Home figures). It sends tenant aggregates to an external model (Gemini or Claude through the gateway). | `application/ai/tools.py:104,117,129`; `feature-ai-assistant.ts:215-236`; `home.ts:615-663` | DPDP processor terms; cross-border transfer | Medium | M | Keep behind the feature flag, out of the primary nav until it answers something Home does not. Name the processor and location in the privacy notice. |
| NOT-1 | SMS goes through MSG91 using DLT-registered templates, the correct Indian route. There is no customer channel preference, no STOP handling and no consent record for WhatsApp messaging. | `infrastructure/channels/sms_channel.py:8,41,72`; `application/whatsapp/*` (no opt-in logic) | TRAI DLT rules; DPDP consent (from May 2027); WhatsApp business policy | Medium | M | Record opt-in per channel and honour opt-out. |

### 4.10 Home, sign-in, licence gate, Platform Console (modules 1 to 3, 35 to 37)

| ID | Finding | Evidence | Rule / norm | Sev | Conf | Fix |
|---|---|---|---|---|---|---|
| SEC-1 | `GET /dev/otp-inbox/{phone}` is unauthenticated and returns the current login OTP of any phone number. It is registered in **every environment except `production`** (`dev`, `uat`, `qa`, `staging` included), and in dev delivery mode the OTP is also logged in clear with the phone number. `/dev/orders/{id}/delivery-otp` returns the delivery OTP to any user holding `orders:deliver`, defeating proof of delivery. Anyone who can reach a staging or UAT API holding real consumer records can sign in as any customer or driver. | `api/v1/routers/dev_tools.py:20-65`; `api/app.py:367`; `infrastructure/identity/otp_delivery.py:43-52,66`; `config/settings.py:22,457` | OWASP A01 and A07; IT Act s.43A; DPDP safeguards | High (Critical if any non-production deployment holds real consumer data and is internet-reachable) | H | Register dev tools only when `environment == "local"`; stop stashing OTPs in Redis in other environments; add a deployment check that `/dev/*` returns 404 outside local. |
| HOME-1 | The setup checklist ticks "gst" when the legacy tenant-wide `gst_rate_percent` configuration exists, not when cylinder types carry HSN and rate (which invoicing needs) and not when the agency GSTIN is on file. A tenant can show a green checklist while every delivery is held un-invoiced. The step "payments" turns green on an unverified entry. | `application/tenant/setup_progress.py:98-103` (@189a406f); docstring `:1-10` still says "0% GST" | Operations | Medium | H | Compute "gst" from: all active cylinder types classified AND business profile saved. Add steps for the PESO licence and insurance documents. |
| PLT-1 | Agency setup and recovery links are returned in the API response and logged; using a reset link does not revoke existing sessions. | `planning/MODULE_STATUS.md` rows 26 and 27, "Known gaps" | OWASP session handling | Medium | M | Revoke sessions on reset, stop logging links, send by email once a provider exists. |

### 4.11 Warehouse to Godown wording change (reviewed as asked)

The change is right in direction and matches the glossary (`docs/business/glossary.md:37-47`). The sidebar, route breadcrumb and page title read "Godowns" (`@189a406f shell-layout.ts:276`, `app.routes.ts:366`). Still showing "warehouse" to users on the dashboard:

| Where | Text |
|---|---|
| `feature-compliance-calendar.html:23` | "warehouse licences" |
| `feature-compliance-calendar.html:58` | "No warehouses registered yet." |
| `feature-cylinder-units.html:300` | label "Receiving warehouse" |
| Cylinder-unit custody values | value `warehouse` (`feature-cylinder-units.ts:91`) likely shows as "Warehouse" through the sentence-case helper (inferred) |
| License issuance | app type `warehouse_app` (`license-issuance-page.ts:35`), vendor-console label |
| Backend messages, invoice and print documents, mobile apps | acknowledged in the glossary as still to do |

Severity **Low** (LOC-3). Fix by searching the user-visible word, not the identifiers. The route stays `/admin/warehouses`, correct under the glossary rule that routes and field names keep English.


---

## 5. Cross-cutting findings

The tax-engine findings are TAX-1 to TAX-13 in 4.1 and are not repeated here. Data-protection findings already listed: KYC-1 to KYC-3, KYC-8, PAY-3, AUD-1, SEC-1, AI-1, NOT-1.

| ID | Area | Finding | Evidence | Rule / norm | Sev | Conf | Fix |
|---|---|---|---|---|---|---|---|
| XC-1 | Data protection | No personal-data-breach workflow. The product has no incident record, no template for the Data Protection Board report (without delay, detailed report within 72 hours) and no CERT-In 6-hour reporting step. "breach" appears in code only as a stock term. | repo grep for `breach` (inventory files only) | DPDP Rule 7 (from May 2027) and CERT-In Directions 2022 (S6) | Medium | M | Add a security-incident register and a runbook with named owners; include it in the agency admin guide. |
| XC-2 | Data protection | No grievance officer or contact in Agency settings or on any customer-facing screen. | repo grep for `grievance`: no hits | DPDP Act s.8(10) and Rules (S6); Consumer Protection Act | Medium | M | Add grievance officer name, email and phone to the agency profile and print them on the invoice footer. |
| XC-3 | Data protection | A customer record has a date of birth but there is no age check; a minor's connection or login is not detected. | `api/v1/schemas/customer.py:85,104` | DPDP Act s.9 (children, verifiable parental consent) | Low | L | Reject registration under 18 for the account holder, or record guardian details. |
| XC-4 | Roles and permissions | Maker-checker is not enforced for refunds. A credit note can be approved by the same user who requested it; approval records the user but does not compare. Approval also does not itself change invoice status or create a refund payment record (inferred; handler not read). | `domain/accounting/credit_note.py:122-135`; `application/accounting/use_cases.py:699-722` | Internal control; BR-20 (customer request, manager approval) | Medium | H | Reject approval when `approved_by == requested_by`, and add the same rule to cash-handover review. |
| XC-5 | Roles and permissions | Permission codes mix styles (`complaints.manage` with a dot, everything else with a colon). Cosmetic but a source of mistakes when roles are edited. | `app.routes.ts:332`; `shell-layout.ts:239` | Maintainability | Low | H | Rename in a migration with a compatibility alias. |
| XC-6 | Localisation | No internationalisation framework (no `@angular/localize`, no Transloco). All screens, print documents, SMS bodies and validation messages are English. Delivery staff and counter staff of most agencies work in Hindi, Marathi, Gujarati, Tamil or another regional language. | `frontend/package.json` has no i18n package; no `i18n=` attributes in templates | Local fit | Medium | H | Choose a library now, extract strings, and start with Hindi and Marathi for the invoice, SMS and driver-facing text. |
| XC-7 | Localisation | Lakh and crore grouping is inconsistent. Grids use `Intl en-IN` (correct, `format.ts:13-26`). The invoice drawer uses Angular's `currency:'INR'` pipe with no locale registered, so it prints `₹1,234,567.00` (24 usages, e.g. `invoice-detail-drawer.html:48,52,57`). Dispatch and price list print raw `₹{{ value }}`. The invoice PDF uses western grouping (`invoice.html:300`). | as listed | Local fit; the glossary says "number grouping is being checked" | Low | H | Register `en-IN` as `LOCALE_ID` or route every amount through `formatCurrencyInr`; do the same in the PDF template. |
| XC-8 | Localisation | Dates display as "20 Oct 2026" and "20/10/2026" inputs; this is acceptable and consistent. Reports have no financial-year presets (RPT-2). Placeholders and demo text use Indian examples (+91, "Street, Sector, Village"). | `libs/shared/util/src/lib/date-format.ts:1-60` | Local fit | n/a | n/a | n/a |
| LOC-3 | Localisation | Residual "warehouse" wording after the Godown change (list in 4.11). | 4.11 | Glossary | Low | H | Search and replace the user-visible word. |
| XC-9 | Accessibility | WCAG 2.2 AA is a Phase 1 requirement (AGENTS.md). The shell has a skip link and about 90 `aria-` attributes in templates. No automated accessibility run (axe or Lighthouse) was seen in the audit; spec files were not run here. | `app-shell.component.ts:56`; template grep | WCAG 2.2 AA | Low | L | Run an axe pass on each module in CI and record the result in `MODULE_STATUS.md`. Not verified. |
| XC-10 | Error handling | Global handlers exist (problem-details interceptor, toast service). Unknown OMC or IFSC outages degrade to "you can still save" (Payments). That is sensible for IFSC but means the setup checklist can turn green on an unverified entry (HOME-1). | `app.config.ts`; `payment-settings.ts` (@189a406f) | Operations | Low | M | Distinguish "saved" from "verified" in the checklist. |
| XC-11 | Tenant isolation | Row-level security is used on tenant tables and covered by tests per `MODULE_STATUS.md`. I did not re-test it. The audit and platform-console code paths that deliberately bypass the tenant context (SECURITY DEFINER functions) were noted but not reviewed. | `MODULE_STATUS.md` C-items and rows 26 and 27 | DPDP; multi-tenant SaaS | n/a | n/a | Keep the existing isolation tests as release gates. |

Positive findings worth keeping: password length 12 and 5-attempt lockout (`config/settings.py:260-262`), 15-minute access tokens, masked phone numbers in SMS logs (`sms_channel.py:65,135`), encrypted KYC numbers at rest, a hard refusal to invoice without a GST rate, GSTIN check digit and state match, and the nightly compliance-expiry notifications.

---

## 6. Missing capabilities (ranked)

Statutory or operational features an Indian LPG agency needs that no dashboard module provides. Rank 1 is the most urgent.

| Rank | Capability | Why it matters | Where it would live |
|---|---|---|---|
| 1 | Customer-category-aware GST (household 5%, NDEC 5%, commercial 18%) with RSP-inclusive pricing for domestic | Every invoice depends on it (TAX-1, TAX-2) | Cylinder Types, Pricing, Invoices |
| 2 | Credit and debit notes with tax in GSTR-1 and printable PDFs | Returns and refunds (TAX-3) | Invoices, Reports |
| 3 | Security deposit ledger and termination or transfer vouchers | Customer money held and returned on closure (KYC-4, KYC-5); no `deposit` field exists anywhere in the product | Customers, Ledger, Invoices |
| 4 | Block dispatch on expired driver or vehicle documents | Safety and legal duty on every trip (DSP-1) | Dispatch |
| 5 | Licensed godown quantity and utilisation warning | PESO licence compliance (GDN-1) | Godowns, Inventory |
| 6 | E-invoicing (IRN, QR) and e-way bill support for B2B commercial supply | Conditional on turnover and customer mix (TAX-4) | Invoices |
| 7 | Consent, notice, retention, erasure and grievance handling | DPDP duties (KYC-2, XC-2) | Customers, Agency settings |
| 8 | Incident, accident and leakage register with PESO and OMC reporting | Safety and PLI claims (DSP-4) | Compliance |
| 9 | Ageing of outstanding balances and a real cash book | Credit control and audit (CASH-2, RPT-1) | Reports, Cash |
| 10 | Delivery charge and preferred-time-delivery lines, state-approved | OMC rule (TAX-11) | Invoices, Pricing |
| 11 | Check-weigher register per vehicle and short-weight evidence | Legal Metrology (DSP-2, CPL-3) | Fleet, Complaints |
| 12 | Regional-language UI and print (Hindi, Marathi first) | Daily use by staff (XC-6) | Whole dashboard |
| 13 | Payroll-lite fields (UAN, ESIC, wage) or a clear decision to leave HR out | Labour compliance (USR-2) | Employees |
| 14 | OMC-side reconciliation (dispatch statements, defective returns, claims) | Margin protection (STK-1) | Inventory |

---

## 7. Removal and simplification candidates

Nothing is marked "remove" on a hunch. Each row says what evidence exists and what keeping it costs.

| # | Candidate | Evidence | Cost of keeping | Recommendation |
|---|---|---|---|---|
| R1 | Tenant-wide `gst_rate_percent` configuration key and "GST Rate (%)" editor | Superseded by per-type HSN and rate (`gst.py:103-142`); still silently applies to unclassified types (`gst.py:131-141`); drives the setup checklist's "gst" tick (HOME-1) | Wrong tax for the wrong customer category if left set; misleading checklist | **Remove** after migrating any tenant that still depends on it. |
| R2 | Per-serial Cylinder Units registry (module 24) | Not wired into GRN, load or delivery (`cylinder_unit.py:34-44`); the OMC fills and tests cylinders; no scan flow exists | Manual double entry for staff, a second source of truth beside bulk counts | **Simplify**: hide behind a feature flag. Reconsider when a scan-based GRN exists. Keep the due-for-test warning idea for received empties. |
| R3 | AI Command Center (module 33) as a sidebar item | Three read-only tools returning figures Home already shows (`tools.py:104,117,129`; `feature-ai-assistant.ts:215-236`) | External model processing of tenant data for no new insight; DPDP processor paperwork | **Simplify**: feature-flag off by default; revisit with tools that answer questions Home cannot (ageing, stock versus OMC). |
| R4 | Employees module (module 30) as separate from Users | Both under `users:manage`; Employees holds name, phone, email, role, branch only (`employee.py:99-120`) | Two places to create a person and two lists to keep in step | **Merge** into Users, or **extend** into real HR fields (USR-2). Decide before go-live. |
| R5 | "Cash book" label (module 18) | It is a collections summary (CASH-2) | Auditors will look for a cash book and find none | **Rename** or complete. |
| R6 | Design System page (module 38) in production builds | Internal reference with no tenant data (`app.routes.ts:220-229`), reached from the profile menu | Surface area and bundle weight in a production tenant app | **Remove from production** or gate to super admin. |
| R7 | Tenant-visible Feature Flags and Linked Devices pages (modules 9, 11) | Vendor-commercial controls shown inside the agency's Settings | Confusing to agency staff; harmless | Keep, but consider moving under License as one page. |

---

## 8. Open questions

### For the product owner

| # | Question | Why it blocks a conclusion |
|---|---|---|
| OQ-1 | Is this system the **record** for consumers, bookings, DAC and cash memos, or a **mirror** of the OMC's own distributor portal (Indane, HP Gas, Bharat Gas)? | If a mirror, KYC-5, ORD-1 and ORD-2 reduce to "show the OMC reference"; if the record, they become Critical-path features. |
| OQ-2 | The default of GST-exclusive pricing was recorded as the product owner's choice. Does it hold for domestic LPG, where the OMC RSP is tax-inclusive? | TAX-2 depends on the answer. |
| OQ-3 | Which OMCs and which states will the first agencies be in? | Delivery-charge approvals, DAC mandates and PESO circle differ by state and OMC. |
| OQ-4 | Do staging or UAT environments ever hold real consumer data or sit on the open internet? | Decides whether SEC-1 is High or Critical. |
| OQ-5 | Will the Employees module become HR or stay a directory? | USR-2 and R4. |
| OQ-6 | Which languages must the first release support? | XC-6 sizing. |

### For the chartered accountant

| # | Question |
|---|---|
| CA-1 | Confirm the 5% (household and NDEC) versus 18% (other 2711 supplies) split as of 22 Sep 2025 against the CBIC notification text, and the correct default HSN (`27111900` or `27111910`). |
| CA-2 | Is e-invoicing mandatory for a typical agency's B2B invoices at current turnover, and from which date? Is an e-way bill needed for commercial cylinder consignments in the agency's state, and at what value? |
| CA-3 | Is the invoice signature requirement (rule 46) met by the "computer-generated, no signature required" footer for non-e-invoice supplies? Triplicate copies for B2B? |
| CA-4 | GST treatment of delivery charge, preferred-time-delivery fee, regulator and hose sale, new-connection charges and security deposits; and of distributor commission from the OMC. |
| CA-5 | The Income-tax Act 2025 section that replaces s.269ST, and whether the cash guard (CASH-1) should also cover payments to suppliers (the old s.269T and s.40A(3) equivalents). |
| CA-6 | Credit-note and refund treatment in GSTR-1 for B2C domestic supplies. |

### For a PESO consultant

| # | Question |
|---|---|
| PE-1 | Form F validity, renewal timing, the maximum quantity wording on the licence, and the amended NOC position after the Gas Cylinders (Amendment) Rules 2026. |
| PE-2 | PESO approvals needed for each delivery vehicle, the required driver endorsement and training, and the correct rule numbers for retest and filling (CYL-1). |
| PE-3 | Accident and near-miss reporting duties and timelines for a distributor (DSP-4). |

### For a lawyer

| # | Question |
|---|---|
| LG-1 | Lawful basis and storage limits for the full Aadhaar number at a distributor (KYC-1); whether an OMC or government requirement covers it. |
| LG-2 | DPDP readiness plan against the 13 May 2027 date, including processor terms with the SMS, WhatsApp, Razorpay and AI vendors, and children's data. Re-check the Gazette for any change to the 18-month date. |
| LG-3 | Whether a household cancellation fee is permitted (ORD-3). |

### For the OMC area office

| # | Question |
|---|---|
| OMC-1 | Is DAC mandatory for every domestic delivery in this sales area (ORD-2)? |
| OMC-2 | Which weighing instruments and verification do delivery staff need (DSP-2)? |
| OMC-3 | Are the current TDT star bands and fine schedule published for the agency's edition of the MDG (TDT-1)? |
| OMC-4 | Which records must the agency keep on paper or in the OMC portal, and which may be kept only in this system? |

---

## 9. Recommended roadmap

### Before go-live

1. Close SEC-1: dev OTP endpoints only in `local`.
2. Stop the audit log recording `password_hash`, payment details and encrypted KYC fields (AUD-1); purge existing rows.
3. Mask Aadhaar in the API and UI (KYC-1).
4. Fix the tax basis for household supply: RSP-inclusive default for Domestic, rate by customer category, slab allow-list 0/5/18/40 (TAX-1, TAX-2, TAX-8). Remove the legacy tenant-wide rate (R1).
5. Credit notes with tax and in GSTR-1 (TAX-3).
6. Block dispatch on expired driver or vehicle documents with an audited override (DSP-1).
7. Rename "Verify UPI ID" to "Check UPI ID" and mask the account number outside payment roles (PAY-1, PAY-3).
8. Make the setup checklist's "gst" step reflect cylinder-type classification and the agency GSTIN (HOME-1).
9. Decide OQ-1 and OQ-4 with the owner; confirm CA-1 to CA-3 in writing.

### Next quarter

1. Customer-category on cylinder type and block mismatched sales; delivery-charge line (TAX-1, TAX-11).
2. DPDP programme: notice, consent ledger, retention, erasure, grievance officer, breach runbook (KYC-2, XC-1, XC-2). Re-check the Gazette in November 2026 and again before May 2027.
3. E-invoicing and e-way bill, if CA-2 says they apply (TAX-4).
4. Licensed godown quantity and utilisation (GDN-1); incident register (DSP-4).
5. Security deposit ledger and termination voucher; closure checks (KYC-4, KYC-5).
6. Refund maker-checker (XC-4); cash receipt guard (CASH-1); real cash book (CASH-2).
7. MFA for admin and accountant (USR-1); KYC read audit (KYC-3).
8. Hindi and Marathi for invoice, SMS and driver-facing text (XC-6).
9. GSTR-1 JSON, GSTR-3B summary, ageing and stock-versus-OMC reports (TAX-5, RPT-1).

### Later

1. Merchant UPI and reconciled collections (PAY-4).
2. Per-vehicle check-weigher register, Legal Metrology fields on scales (DSP-2, SCL-1).
3. Employee HR fields or merge into Users (USR-2).
4. Fire NOC, trade licence and other calendar items (GDN-2).
5. Scan-based GRN and delivery, then revive the Cylinder Units registry (R2).
6. Financial-year report presets, lakh grouping everywhere, remaining Godown wording (RPT-2, XC-7, LOC-3).

