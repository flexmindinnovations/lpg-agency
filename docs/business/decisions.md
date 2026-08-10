# Confirmed Decisions Log

## Status
This document records the **confirmed decisions** for every item previously listed in `questions/open-questions.md`. These decisions were supplied by the business/product stakeholder as "recommended enterprise decisions" and are treated from this point forward as **binding requirements**, superseding the corresponding assumptions in `business/assumptions.md` and the open items referenced throughout `/docs`.

Where a decision changes a data model, workflow, or requirement described elsewhere in this SRS, that document has been updated and cross-referenced back here. This file is the single source of truth for "what was decided and why it isn't still an open question."

---

## Critical Decisions

### D-01 (resolves Q-01) — Multi-Tenancy
**Decision:** Build as a **multi-tenant SaaS platform** from Phase 1.
- Each LPG agency is a **Tenant**.
- Full tenant data isolation (logical separation within a shared application/database).
- Every business entity (Customer, Order, Inventory, Invoice, etc.) carries a `tenantId`.
- A **Super Admin** role exists above the tenant level to manage tenant onboarding/configuration.
- **Impact:** All data model documents must now assume a `tenantId` scoping key exists on every entity. This is a foundational architectural change from the single-tenant assumption previously recorded (A-02, now superseded).

### D-02 (resolves Q-02) — Multi-Warehouse / Branch Support
**Decision:** Support multiple **Branches**, **Warehouses**, and **Delivery Hubs** per tenant.
- Inventory belongs to a Warehouse.
- Customers belong to a Branch.
- Drivers belong to a Branch.
- **Impact:** Supersedes A-01 (single-location assumption). `modules/inventory-management.md` and `modules/customer-management.md` data models require a `branchId`/`warehouseId` foreign key.

### D-03 (resolves Q-03) — Customer Types
**Decision:** Support four customer types: **Domestic, Commercial, Industrial, Government.**
- Customer type determines pricing, cylinder holding limits, applicable taxes, and payment terms.
- **Impact:** Supersedes A-03 (which only anticipated Domestic/Commercial). `business-rules.md` BR-04 (holding cap) and pricing logic in `modules/accounting.md` must be parameterized by customer type, not hardcoded to two tiers.

### D-04 (resolves Q-04) — Cylinder Sizes
**Decision:** Support **configurable** cylinder types, with initial examples: 5kg, 10kg, 14.2kg, 19kg, 47.5kg.
- Inventory is tracked **separately per cylinder type** at every level (Warehouse, Vehicle, Customer).
- **Impact:** Supersedes A-04. Every inventory/ledger entity in `modules/inventory-management.md` and `workflows/cylinder-ledger.md` requires a `cylinderTypeId` dimension — this is not a single filled/empty counter pair per location, but one pair **per cylinder type per location**.

### D-05 (resolves Q-05) — Booking Channels
**Decision:** Support Mobile App, Agency Staff, Phone Booking, Walk-in, and (future) WhatsApp/API channels.
- Every order stores a **Booking Source** field.
- **Impact:** Confirms A-05. `modules/order-management.md` Order entity requires a `bookingSource` attribute.

### D-06 (resolves Q-13) — Regulatory Jurisdiction
**Decision:** Initial release targets **India**, with GST support and OMC references to IOCL, BPCL, HPCL. Tax rules are **configurable**, not hardcoded.
- **Impact:** Confirms A-19. `requirements/security.md` §8 (DPDP Act-style data protection) should now be treated as an active requirement, not merely a flagged gap.

---

## High-Priority Decisions

### D-07 (resolves Q-14) — Order State Model
**Decision:** The order lifecycle is expanded to:

```
Draft → Booked → Confirmed → Assigned → Ready for Dispatch →
Out For Delivery → Delivered → Failed Delivery → Cancelled → Closed
```

- This **replaces** the simpler 4-state model (New/Pending, Assigned, Delivered, Cancelled) documented in the original `modules/order-management.md`.
- **Impact:** `modules/order-management.md` §3 state machine and `workflows/delivery-flow.md` must be updated (see revised versions). "Failed Delivery" and "Out for Delivery" are now first-class states, resolving the previously flagged gap.

### D-08 (resolves Q-15) — Partial Fulfillment
**Decision:** Partial fulfillment is **allowed**. The system tracks Delivered Quantity, Pending Quantity, and Backorder per order line.
- **Impact:** `modules/order-management.md` Order entity requires per-line quantity tracking rather than a single fulfilled/unfulfilled flag.

### D-09 (resolves Q-35) — Exchange vs. Purchase
**Decision:** Support four cylinder ledger transaction types: **Exchange, New Purchase, Additional Cylinder, Deposit Return.**
- **Impact:** Extends (rather than replaces) the transaction type table in `workflows/cylinder-ledger.md` §3 — "New Purchase" and "Additional Cylinder" are now distinct types, and "Deposit Return" formalizes the connection-closure settlement gap (Q-34).

### D-10 (resolves Q-08) — Invoice Model
**Decision:** One invoice per delivered order in Phase 1; consolidated/periodic invoicing is a **future** (post-Phase-1) capability.
- **Impact:** Confirms A-08 as designed. `modules/accounting.md` §3.1 stands as written, with consolidated invoicing noted as a roadmap item.

### D-11 (resolves Q-32) — Partial Payment
**Decision:** Support Full Payment, Partial Payment, and Credit. Customer credit limit is **configurable** (per customer type, per D-03).
- **Impact:** `modules/accounting.md` and `workflows/payment-flow.md` §6 must support split/partial payment recording against a single invoice, not just Paid/Unpaid.

---

## Medium-Priority Decisions

### D-12 (resolves Q-17) — Failed Delivery
**Decision:** Defined reason codes: Customer unavailable, Wrong address, Payment refused, Vehicle issue, Safety issue. Defined actions: Reschedule, Cancel, Return stock.
- **Impact:** `modules/delivery-management.md` and `workflows/delivery-flow.md` E1 are resolved — "Failed Delivery" (D-07) now has a defined reason-code taxonomy and resolution action set.

### D-13 (resolves Q-18) — Payment Refusal
**Decision:** Driver can accept credit, take the cylinder back, or escalate for manager approval — policy is **configurable** per tenant.
- **Impact:** Resolves `workflows/delivery-flow.md` E-series gap. Ties to D-11 (credit/partial payment support).

### D-14 (resolves Q-11) — Damaged Cylinder
**Decision:** Cylinder status now includes: **Filled, Empty, Damaged, Leakage, Quarantine, Scrap, Repair.** Each is tracked as a distinct movement category.
- **Impact:** Supersedes the binary Filled/Empty model throughout `modules/inventory-management.md` and `workflows/inventory-flow.md`. This is a significant data model expansion — inventory counters are no longer a 2-state pair but a 7-state set per cylinder type per location.

### D-15 (resolves Q-20) — OMC Replenishment
**Decision:** Phase 1 = manual **GRN (Goods Receipt Note)** process. Phase 2 = automatic integration with IOCL/BPCL/HPCL.
- **Impact:** Confirms A-13. `workflows/inventory-flow.md` Stage 1 should be renamed/formalized around a GRN entity rather than a generic "manual/offline process."

### D-16 (resolves Q-21) — Inventory Adjustment Approval
**Decision:** Only **Warehouse Staff** or **Agency Admin** may approve inventory adjustments; audit logging is mandatory.
- **Impact:** Resolves the approver gap in `modules/inventory-management.md` §3.5 and ties directly to BR-28 (audit logging) and the RBAC role list (see D-additional-2 below). Originally written as "Warehouse Manager" before D-38 confirmed the role list; updated here for consistency — see D-38's resolution note.

### D-17 (resolves Q-09) — Refund Workflow
**Decision:** Defined flow: Customer Request → Manager Approval → Credit Note → Refund → Ledger Update.
- **Impact:** Resolves `modules/accounting.md` §3.7 gap. A **CreditNote** entity (already anticipated in the conceptual data model) is now a required, not optional, part of Phase 1 scope.

### D-18 (resolves Q-22) — Cash Shortfall
**Decision:** Defined flow: Driver Declaration → Investigation → Approval → Adjustment Entry → Audit Log.
- **Impact:** Resolves `modules/accounting.md` §8 gap.

### D-19 (resolves Q-16) — Cancellation Policy
**Decision:** Free cancellation before dispatch; cancellation after dispatch requires Manager Approval and may incur a cancellation charge.
- **Impact:** Resolves `modules/order-management.md` §9 gap. "Dispatch" corresponds to the new "Ready for Dispatch" / "Out for Delivery" states from D-07.

### D-20 (resolves Q-28) — Complaint Management Module
**Decision:** Build as a **dedicated module** (not just a notification trigger source), with Categories, Priority, SLA, Assignment, Escalation, Resolution, and Customer Feedback capture.
- **Impact:** This elevates Complaint Management from a flagged gap in `modules/notifications.md` §8 to a full new module. See `modules/complaint-management.md` (new document, added below in the module list).

### D-21 (resolves Q-34) — Connection Closure Settlement
**Decision:** Defined steps: Return cylinders → Verify ledger → Refund deposit → Close account → Archive customer.
- **Impact:** Resolves `workflows/cylinder-ledger.md` §8 gap and formalizes the "Deposit Return" transaction type from D-09.

---

## Lower-Priority Decisions

### D-22 (resolves Q-06) — Route Model
**Decision:** One Driver + One Vehicle + One Route per shift; multiple shifts per day are supported.

### D-23 (resolves Q-07) — Fleet Ownership
**Decision:** Support Agency-owned vehicles, third-party vehicles, rental vehicles, and (future) gig drivers.

### D-24 (resolves Q-19 / Q-12) — Offline Mode
**Decision:** **Mandatory**, offline-first architecture for the Driver App, with automatic synchronization and conflict resolution based on server timestamps and optimistic concurrency.
- **Impact:** This elevates offline support from "Should-have" (FR-DM-10, S priority) to **Must-have**. `requirements/functional.md` priority updated accordingly (see revised table).

### D-25 (resolves Q-25) — Notification Channels
**Decision:** Push, SMS, Email supported in Phase 1; WhatsApp deferred to Phase 2.

### D-26 (resolves Q-26) — Reminder Logic
**Decision:** Configurable reminder interval (examples given: 30/45/60 days), based on customer consumption pattern.

### D-27 (resolves Q-27) — Multi-Language
**Decision:** Phase 1 supports **English, Hindi, Marathi**; additional languages added later.

### D-28 (resolves Q-23) — Report Scheduling
**Decision:** Support Daily/Weekly/Monthly scheduled reports, delivered via Email, in PDF and Excel formats.

### D-29 (resolves Q-24) — KPI Definitions
**Decision:** Confirmed KPI set: On-time Delivery %, Average Delivery Time, Driver Productivity, Revenue, Inventory Accuracy, Customer Satisfaction, Outstanding Collections.

### D-30 (resolves Q-29) — Loaded Empty Cylinders
**Decision:** The empties loaded onto a vehicle at shift start represent pre-positioned stock for operational flexibility, emergency exchanges, or empties carried over from a previous trip. Vehicle inventory tracks Filled and Empty as two independently meaningful counters, not just placeholders.
- **Impact:** Resolves the ambiguity flagged in `workflows/inventory-flow.md` Stage 2.

### D-31 (resolves Q-30) — Vehicle Carry-Over
**Decision:** **Allowed.** Vehicle inventory remains open until reconciled; **daily reconciliation is mandatory** regardless of carry-over.
- **Impact:** Resolves `workflows/inventory-flow.md` Stage 4 / E3 gap.

### D-32 (resolves Q-31) — UPI/Card Devices
**Decision:** Support QR payment, POS machine, UPI apps, payment gateway APIs, and cash.

### D-33 (resolves Q-33) — Collections Process
**Decision:** Defined flow: Outstanding → Reminder → Follow-up → Collection → (optional) Legal Hold.

### D-34 (resolves Q-36) — Performance SLA
**Decision:** Confirmed targets:
- API response < 300ms (average)
- Search < 1 second
- Dashboard load < 2 seconds
- Reports < 10 seconds
- Support 500+ concurrent users **per tenant**
- Horizontal scaling enabled
- **Impact:** Supersedes the "proposed, needs confirmation" targets in `requirements/performance.md` §2 — these are now binding SLAs.

### D-35 (resolves Q-37) — Accessibility
**Decision:** WCAG 2.2 AA compliance is **required in Phase 1** (not deferred).
- **Impact:** Resolves the open timing question in `requirements/accessibility.md` §6 — Phase 1 scope now formally includes full AA compliance.

### D-36 (resolves Q-10) — QR/Barcode Tracking
**Decision:** Phase 1 prepares the **data model only** (i.e., entities should be QR/barcode-ready — e.g., a nullable `cylinderSerialNumber` field — even though scanning workflows are not built). Full scanning/individual cylinder tracking remains Phase 2.

---

## Additional Architectural Decisions (Not Tied to a Specific Prior Question)

### D-37 — Authentication
JWT with Refresh Tokens; OTP for customer login; optional Azure AD / Microsoft Entra ID SSO for agency staff.

### D-38 — Authorization / RBAC Roles (Confirmed Role List)
**Super Admin, Agency Admin, Manager, Warehouse Staff, Dispatcher, Accountant, Driver, Customer.** Exactly 8 roles.
- **Impact:** This is now the authoritative role list, superseding the provisional role list in `business/stakeholders.md` §3 and `requirements/security.md` §2. Note "Dispatcher" is a newly named role (previously implicit within "Agency Staff/Operator") and "Warehouse Staff" replaces the more general "Warehouse Manager" as the operational role.
- **Residual naming question — resolved 2026-08-10 (product owner decision, ahead of Phase 6 implementation):** "Warehouse Staff" and "Warehouse Manager" are **the same role, renamed** — not a staff/supervisor tier pair. D-16's approval authority for inventory adjustments belongs to Warehouse Staff (updated above). The `identity.role` seed data and the permission matrix (`docs/data/17-api-security.md` §6) use exactly 8 roles, "Warehouse Staff" only — no separate "Warehouse Manager" row.

### D-39 — Audit Logging Scope
All financial transactions, inventory adjustments, login events, and administrative changes must be logged — confirms and slightly broadens BR-28 to explicitly include login events.

### D-40 — File Storage
Invoices, KYC documents, delivery photos, and signatures are stored in **cloud object storage**.

### D-41 — Printing
Confirms `requirements/non-functional.md` §6 in full: thermal (58mm/80mm specifically), A4, PDF export, configurable receipt templates, barcode and QR code printing.

### D-42 — Configurability
Business rules — GST rates, cylinder holding limits, cancellation policies, reminder intervals, credit limits — must be **configurable per tenant**, not hardcoded. This is a direct consequence of D-01 (multi-tenancy) and should be treated as a cross-cutting design constraint across every module.

---

## Cross-Reference Summary

| Original Question | Decision ID | Status |
|---|---|---|
| Q-01 through Q-37 (all) | D-01 through D-36 | **Resolved** |
| Additional (auth, RBAC, storage, printing, configurability) | D-37 through D-42 | **Resolved** |

All items in `questions/open-questions.md` are now marked Resolved with a pointer to this document. See that file for the updated status table.
