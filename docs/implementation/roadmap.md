# Implementation Roadmap

Phased delivery plan for the LPG Agency Management Platform.

**Authoritative status of what is being worked on right now is [`planning/current_phase.md`](../../planning/current_phase.md), not this document.** This document describes the intended sequence; that one describes reality.

> Created in Phase 0 (2026-08-09), resolving a dangling link in `docs/implementation/README.md`.

---

## Phase Boundaries

Phase 1 and Phase 2 scope are fixed by `docs/business/assumptions.md` A-21 and the confirmed decisions D-01 … D-42. They are not re-litigated here.

### Phase 1 (MVP) — in scope

Everything required to run an LPG agency end to end:

- Multi-tenant SaaS with tenant isolation from day one (D-01, BR-30)
- Multi-branch, multi-warehouse, multi-delivery-hub (D-02)
- Four customer types: Domestic, Commercial, Industrial, Government (D-03)
- Configurable cylinder types across 7 statuses (D-04, D-14)
- Booking via Mobile App, Agency Staff, Phone, Walk-in (D-05)
- Full order lifecycle with partial fulfilment (D-07, D-08)
- Delivery execution with OTP, signature, photo, GPS
- **Offline-first Driver App** (D-24) — a Must-have, not a stretch goal
- Cylinder ledger: exchange vs purchase, returns, adjustments, closure settlement (D-09, D-21)
- Invoice per delivered order, GST, partial payment, refunds, cash handling (D-10, D-11, D-17, D-18)
- Complaint management with SLA tracking (D-20)
- Notifications: SMS, email, push (D-25, D-26)
- Reporting, KPIs, scheduled reports (D-28, D-29)
- **Real-time updates** — order, delivery, assignment, dispatcher, dashboard (ADR-015)
- Printing: thermal, A4, PDF, barcode/QR (D-41)
- **WCAG 2.2 AA** (D-35) — Phase 1, not deferred
- Binding performance SLAs (D-34): API < 300 ms avg, search < 1 s, dashboard < 2 s, reports < 10 s, 500+ concurrent users per tenant

### Phase 2 — explicitly deferred

Per A-21: WhatsApp booking, AI demand forecasting, route optimization, QR/barcode cylinder tracking (D-36), predictive inventory, OMC/distributor integrations, geo-fencing, eKYC, chatbot support, advanced BI dashboards, IoT.

**Phase 1 must remain forward-compatible** where the data model is concerned — for example a nullable cylinder serial number field, per D-36. Forward-compatible data modelling is Phase 1 work; the features themselves are not.

---

## Delivery Sequence

Dependency-ordered. The full roadmap with rationale is in [`planning/current_phase.md`](../../planning/current_phase.md) §Development Roadmap; this is the condensed view.

| # | Phase | Depends on | Notes |
|---|---|---|---|
| 0 | Documentation Reconciliation & Technical Baseline | — | Documentation only. **Current phase.** |
| 1 | Repository / Foundation | 0 | `.gitignore`, first commit, monorepo skeleton, Docker Compose (PostgreSQL + Redis), lint/format configs, minimal CI |
| 2 | Backend Foundation | 1 | FastAPI skeleton, Clean Architecture layers, SQLAlchemy async, Alembic baseline, RFC 7807 middleware, structured logging, tenant context + RLS wiring, test harness, `import-linter` contracts |
| 3 | Shared Infrastructure (backend) | 2 | Unit of Work, base repository, audit logging, domain-event dispatcher, idempotency store, caching, background worker, file storage, rate limiting, real-time publisher |
| 4 | Angular 22 Web Foundation | 1 (2 for live API) | Nx workspace, design tokens, theme system, shared UI library (PrimeNG-based), AG Grid Community wrapper, layout shell, interceptors, generated API client, Storybook, Jest, Playwright, axe-core gate |
| 5 | Flutter Application Foundations | 2 | Melos workspace, shared packages, Riverpod, go_router, Drift schema + encrypted storage, both app shells |
| 6 | Authentication & Authorization | 3, 4, 5 | Login/logout/refresh, password reset, OTP, JWT, RBAC (D-37, D-38), tenant resolution, guards on all clients, security tests |
| 7 | Administration & Tenant/Master Data | 6 | Tenant, branch, warehouse, cylinder types, pricing/tax config (D-42), user management, feature flags, audit log viewer |
| 8 | Customer Management | 7 | Registration, search, addresses, KYC, connections, four customer types (D-03) |
| 9 | Inventory Management | 7 | Warehouse + vehicle inventory per type × status, transfers, adjustments, GRN (D-15), reconciliation (D-16) |
| 10 | Order Management | 8, 9 | Booking (D-05), lifecycle (D-07), partial fulfilment (D-08), assignment, cancellation (D-19), tracking |
| 11 | Delivery Management | 10 | Assignment (D-22, D-23), loading, execution, OTP/signature/photo/GPS, failed delivery (D-12), payment refusal (D-13), **Driver App offline sync (D-24)** |
| 12 | Cylinder Ledger | 8, 9, 11 | Transactions, exchange vs purchase (D-09), returns, adjustments, balance, closure settlement (D-21) |
| 13 | Accounting & Billing | 10, 11, 12 | Invoicing (D-10), GST, payments (D-11), credit notes, refunds (D-17), cash collection/shortfall (D-18), collections (D-33) |
| 14 | Notifications | 6, 10, 11 | SMS, email, push, reminders (D-25, D-26) |
| 15 | Complaint Management | 8 | Registration, assignment, escalation, SLA, resolution, feedback (D-20) |
| 16 | Reporting & Analytics | 8–14 | KPIs (D-29), financial/inventory/driver/customer/audit reports, export, scheduling (D-28) |
| 17 | Printing | 13, 16 | Template engine, tenant branding, thermal/A4/PDF, barcode/QR, preview, print audit (D-41) |
| 18 | Production Hardening | all | Performance against D-34, WCAG 2.2 AA audit (D-35), security review, observability, load testing, data migration |
| 19 | CI/CD and Deployment | 1 onward | Per-stack workflows, IaC, four environments, release automation, rollback |
| 20 | Phase 2 / AI Capabilities | 18 | Deferred per A-21 |

### Two sequencing notes

**Real-time and printing cross-cut.** Both appear as numbered phases, but neither is built once at the end. Real-time infrastructure lands in phase 3 and each feature publishes its own events as it ships. Receipts and invoices are built alongside Delivery and Accounting; phase 17 completes the engine, templates, and tenant configuration.

**Administration precedes Customer Management.** This deviates from the sequence in `knowledge/10-feature-map.md`, which places Customer Management first. Tenant, branch, warehouse, and cylinder-type reference data are hard prerequisites for Customer, Inventory, and Orders — building customers before the master data they reference means building it twice.

---

## Phase Gates

A phase is complete only when its features meet the Definition of Done in `AGENTS.md`: business requirements satisfied, architecture consistent, build succeeding, tests passing, accessibility verified, documentation updated, and `PLAN.md` / `TASKS.md` / `STATUS.md` current.

ADRs are reviewed at each major phase gate (`docs/architecture/15-architecture-decision-records.md` §Review Cadence).

## Deferred Decisions with Phase Triggers

| Decision | Must be resolved by |
|---|---|
| Background job library (ARQ / Dramatiq / Celery) | Phase 2 |
| Inventory counter granularity (D-04/D-14 residual) | Phase 9 |
| Cancellation fee amount and configurability (D-19 residual) | Phase 10 |
| Warehouse Staff vs Warehouse Manager role identity (D-38 residual) | Phase 6 |
| KYC document types (A-20, pending business/legal) | Phase 8 |
| PDF rendering library (WeasyPrint / ReportLab) | Phase 17 |
| Statutory backup retention duration | Phase 18 |
| Azure hosting topology + IaC tool | Before production (phase 19) |

Full detail in `planning/features/00-documentation-reconciliation/TASKS.md` §Discovered Work and `docs/architecture/15-architecture-decision-records.md` §Deferred Decisions.
