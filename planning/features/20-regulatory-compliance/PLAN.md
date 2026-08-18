# Phase 20 — Regulatory & MDG Compliance

**Status:** 🔵 NOT STARTED · **Depends on:** Phases 13 (Accounting), 16 (Reporting)
**Source:** [`docs/research/feature-gap-analysis.md`](../../../docs/research/feature-gap-analysis.md) §2

## Why this precedes the AI phases

These are not features. They are the terms on which a distributorship keeps
operating. The platform today is a competent generic delivery and inventory
system with almost none of the India-specific LPG compliance surface modelled —
so a distributor using it cannot *evidence* compliance during an OMC
inspection, regardless of whether they are actually compliant.

The AI phases depend on this one for real reasons, not sequencing tidiness:
the MDG risk copilot (A13) narrates numbers this phase computes, and TDT
prediction (A1/A3) optimises a metric this phase defines.

## The governing document

**OMC Marketing Discipline Guidelines (MDG) 2022**, effective 01-May-2022 —
the contract that decides whether a distributorship is fined or terminated. It
prescribes operational mechanics at clause level.

> ⚠️ **Version risk, and it is material.** IndianOil's index also lists a
> *"Market Discipline Guidelines-2024"* which could not be retrieved (research
> §7.1). **Every threshold, band and fine percentage in this phase must be
> tenant-configurable reference data, version-stamped with the MDG edition it
> came from — never a constant in code.** Confirm the current edition against
> the tenant's own OMC before go-live.

The same rule applies to every other number here. Research §7 records nine
explicit uncertainties, including that the Indian statutory cylinder retest
interval defers to IS 15975 and is **not** the "5 years" that search results
surface — that figure is US DOT and does not apply.

## Scope

### 1. Weighment (`compliance` schema)

Entirely absent today, and its absence is *itself* a named irregularity.

- Scale registry with certificate expiry (build to **certificate validity**, not to an assumed reverification interval — research §7.6)
- 10% random sample weighing on truck receipt
- 100% weight check before load-out, blocking dispatch
- Per-cylinder weighment records linked to the delivery
- Tare/gross/net with tolerance from Legal Metrology reference data — **do not invent a tolerance** (§7.5)

### 2. Targeted Delivery Time star rating

Quarterly, booking date → delivery date, 5★ down to 1★, with fines scaling on
repeat. **Fully computable from data already in `orders.order_status_history`**
— the platform stores every transition with a timestamp and simply never
aggregates them.

Lands as: a computed quarterly rating, a live in-quarter projection so the
distributor can still act, and per-branch attribution.

### 3. Cylinder identity

The deepest schema change here. The platform tracks *balances by status*, not
*individual cylinders*, which makes statutory-test-due segregation, defective
return traceability and per-cylinder history impossible.

Note this also fixes a detection gap: "unaccounted sale" explicitly includes a
filled-vs-empty mismatch **even when combined stock is correct**, which the
current total-stock reconciliation provably cannot catch.

### 4. Delivery Authentication Code

**Distinct from the platform's own POD OTP.** The OMC issues a separate
6-digit code at a large and growing share of deliveries. The platform must
capture and validate it as a *second* factor alongside its own — without it,
deliveries get cancelled at the door.

### 5. Consumer lifecycle instruments

SV / TV / DGCC / DBC vouchers, and the security-deposit ledger with rate
versioning that they govern. The platform has "deposit tracking" but not the
instruments that legally define it.

> **DBC = Double Bottle Connection**, not delivery-boy commission (research
> §7.9). Any requirement note using the latter sense is wrong.

### 6. Subsidy and eligibility

PAHAL subsidy reconciliation, and PMUY eligibility gating at connection issue.
PMUY mis-issuance is a **Critical** irregularity — termination on first
instance above the case threshold — so this is a hard block in the connection
flow, not a warning.

### 7. Compliance calendar

Registry with lead-time alerting: PESO Form F licence (expires 30 September),
scale certificates, insurance, biennial customer safety inspection, Suraksha
hose replacement. Plus the 12-hour PESO accident notification workflow.

### 8. Cash and UPI settlement

Per-delivery-staff daily settlement with variance at day close. Research names
this the single feature Indian competitors lead with; the platform has invoices
and payments but no daily reconciliation.

## Scope guards — do not over-build

Two things it would be actively wrong to make blanket-mandatory:

- **E-invoicing does not apply to B2C domestic refills.** It applies to B2B/B2G/export above the AATO threshold. Gate it on customer type and tenant turnover.
- **Household LPG supply and empty-cylinder returns are e-way-bill exempt.** Do not force e-way bills onto domestic delivery routes.

## Verification

- Every threshold traceable to a cited clause and an MDG edition stamp
- TDT computed from `order_status_history` reconciles against a hand-calculated quarter
- Weighment blocks dispatch when the scale certificate has expired
- PMUY gating rejects an ineligible connection at the use-case layer, not the UI
- New `compliance` schema passes `verify_env_parity.sql` with zero defects
- Cross-tenant isolation verified as `lpg_app`

## Open questions

Carried from research §7 — all nine remain open. The two that most affect
schema design:

1. **MDG edition** (§7.1) — 2022 vs a possible 2024 revision. Blocks hard-coding any threshold.
2. **OMC portal APIs** (§7.8) — no public evidence of a documented distributor integration API. Design an import/export boundary and assume manual reconciliation until proven otherwise.
