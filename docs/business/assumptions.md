# Assumptions

This document lists assumptions made while transforming the blueprint into this SRS. Per the governing instruction, assumptions are **stated explicitly rather than silently baked into requirements**, and each was originally cross-referenced to a corresponding item in `docs/engineering/open-questions.md`.

> **Update:** All open questions have since been resolved by stakeholder decision — see `business/decisions.md`. Assumptions below are now marked **SUPERSEDED** where a confirmed decision replaced them, or **CONFIRMED** where the decision matched the original assumption. This document is retained for historical traceability (to show what was assumed vs. what was ultimately decided).

## 1. Business Model Assumptions

- **A-01 [SUPERSEDED by D-02]**: Originally assumed single-location/single-warehouse for Phase 1. **Decision: multi-branch, multi-warehouse, multi-delivery-hub support is now required from Phase 1.**
- **A-02 [SUPERSEDED by D-01]**: Originally assumed single-tenant. **Decision: the platform is now confirmed as a full multi-tenant SaaS from Phase 1**, with tenant-level data isolation as a foundational architectural requirement (BR-30).
- **A-03 [SUPERSEDED by D-03]**: Originally assumed two customer types (Domestic/Commercial). **Decision: four types are confirmed — Domestic, Commercial, Industrial, Government** — each driving pricing, cylinder limits, taxes, and payment terms.
- **A-04 [SUPERSEDED by D-04]**: Originally assumed a small, implicit set of cylinder sizes. **Decision: cylinder types are fully configurable** (initial examples: 5kg, 10kg, 14.2kg, 19kg, 47.5kg), with inventory tracked separately per type at every location.

## 2. Actor & Process Assumptions

- **A-05 [CONFIRMED by D-05]**: Bookings can be created via Mobile App, Agency Staff, Phone, or Walk-in (WhatsApp/API deferred to Phase 2). Every order now stores a **Booking Source** attribute.
- **A-06 [CONFIRMED by D-22]**: One Driver + One Vehicle + One Route per shift, with multiple shifts per day supported.
- **A-07 [SUPERSEDED by D-23]**: Originally assumed an owned-fleet-only model. **Decision: agency-owned, third-party, rental, and (future) gig-driver vehicles are all supported.**

## 3. Financial Assumptions

- **A-08 [CONFIRMED by D-10]**: One invoice per delivered order in Phase 1; consolidated/periodic invoicing is a confirmed future (post-Phase-1) capability, not Phase 1 scope.
- **A-09 [CONFIRMED, unchanged]**: Prices are configured centrally (now per-tenant, per BR-31) and historical invoices lock in the price at time of transaction.
- **A-10 [SUPERSEDED by D-17]**: Originally assumed a loosely-defined manual refund process. **Decision: a specific workflow is confirmed — Customer Request → Manager Approval → Credit Note → Refund → Ledger Update.**
- **A-11 [CONFIRMED, unchanged]**: GST rates remain configurable (now explicitly tenant-configurable per BR-31).

## 4. Inventory Assumptions

- **A-12 [SUPERSEDED by D-02]**: See A-01 — multiple warehouses per tenant/branch are now supported.
- **A-13 [CONFIRMED by D-15]**: Confirmed as manual **GRN (Goods Receipt Note)** process in Phase 1; automatic IOCL/BPCL/HPCL integration is Phase 2.
- **A-14 [CONFIRMED by D-36]**: Full barcode/QR scanning workflows remain Phase 2, but Phase 1 must prepare the data model for it (e.g., a nullable cylinder serial number field), per D-36.
- **A-15 [SUPERSEDED by D-14]**: **Decision: a full 7-state cylinder status model is now confirmed** — Filled, Empty, Damaged, Leakage, Quarantine, Scrap, Repair — replacing the binary Filled/Empty model throughout the inventory and ledger design.

## 5. Technical/Non-Functional Assumptions

- **A-16 [CONFIRMED, unchanged]**: This SRS remains scoped to business/functional requirements only; technology stack choices belong in architecture documents.
- **A-17 [CONFIRMED and strengthened by D-34/D-35]**: Enterprise-grade NFR targets are now **binding with specific numbers**: API < 300ms average, search < 1s, dashboard < 2s, reports < 10s, 500+ concurrent users per tenant, and WCAG 2.2 AA required in Phase 1 (not deferred).
- **A-18 [CONFIRMED and elevated by D-24]**: Offline capability for the Driver App is now confirmed as **mandatory, offline-first architecture** with automatic sync and optimistic-concurrency conflict resolution — elevated from an assumption to a Must-have requirement (see `docs/engineering/open-questions.md` notes on the resulting scope/timeline implication).

## 6. Regulatory Assumptions

- **A-19 [CONFIRMED by D-06]**: Target jurisdiction is confirmed as **India** for the initial release, with GST and IOCL/BPCL/HPCL relevance confirmed; tax rules are tenant-configurable.
- **A-20 [CONFIRMED, unchanged]**: KYC document types remain to be supplied by business/legal; not respecified by the recent decisions.

## 7. Scope Boundary Assumptions

- **A-21**: Phase 1 scope (per blueprint) excludes: WhatsApp booking, AI demand forecasting, route optimization, QR/barcode tracking, predictive inventory, OMC/distributor integrations, geo-fencing, eKYC, chatbot support, and advanced BI dashboards — all explicitly deferred to "Phase 2" in the blueprint. This SRS documents Phase 2 items only where relevant for forward-compatible data modeling, not as Phase 1 functional requirements.
