# Non-Functional Requirements (NFR)

These requirements combine what is explicit in the blueprint (e.g., "Load Testing," "Disaster Recovery") with the enterprise-grade expectations set out in the extended project instructions (accessibility, performance, security posture, etc.). Detailed treatment of Security, Performance, and Accessibility is split into their own documents; this file covers the remaining cross-cutting categories plus a consolidated summary table.

## 1. Reliability & Availability
- The system shall target high availability for the Agency Dashboard and both mobile apps during business hours, with a specific SLA (e.g., 99.9%) to be defined by the business — **not specified in blueprint.**
- The system shall include documented backup and disaster recovery procedures (explicit in blueprint: "Backup Strategy," "Disaster Recovery").
- The system shall use load balancing across application servers (explicit).

## 2. Scalability
- The architecture shall support horizontal scaling of backend services independent of a single agency's data (forward-compatible with the multi-tenant aspiration noted in assumption A-02), even though Phase 1 is single-tenant.
- The system shall remain performant as transaction volume grows (thousands of customers, daily order volumes typical of a mid-size to large LPG agency) — see `requirements/performance.md`.

## 3. Maintainability
- Business logic (especially Cylinder Ledger and Inventory rules) shall be centralized and not duplicated across the three front-ends — each client should call shared backend services rather than re-implementing ledger math.
- The system shall be built using Clean Architecture / SOLID principles per the extended instructions, ensuring modules (Customer, Order, Delivery, Inventory, Accounting, Reporting, Notifications) remain independently testable and replaceable.

## 4. Auditability
- Every mutation to inventory, cylinder ledger, orders, and payments shall be logged with who/when/what/before-after values (ties to BR-28, FR-AD-02).
- Audit logs shall be tamper-evident/append-only.

## 5. Usability
- The interface shall follow a modern, premium SaaS design standard as specified in the extended instructions (referencing Linear, Notion, Stripe Dashboard, Vercel, GitHub, Atlassian, Microsoft Fluent as visual/interaction benchmarks).
- The system shall use a centralized design token system (colors, typography, spacing, elevation) rather than hardcoded values, supporting Light, Dark, and High Contrast themes.
- Enterprise keyboard shortcuts shall be supported on the Dashboard (Ctrl+K global search, Ctrl+N create new, Ctrl+S save, Esc close, / focus search, Alt+Left/Right navigation, Ctrl+P print, Ctrl+Shift+P command palette, arrow-key table navigation, Enter to open, Delete to delete record).

## 6. Printing
- The system shall support a complete printing subsystem: Invoice, Delivery Receipt, Payment Receipt, Cash Receipt, Customer Ledger, Daily/Inventory/Driver/GST reports, with Print Preview, thermal-printer support, A4-printer support, PDF export, and barcode/QR code printing (all explicit in extended instructions).
- Receipt/print templates shall be configurable and reusable rather than hardcoded per document type.

## 7. Data Tables / Enterprise Grid Behavior
- All list/table views in the Dashboard shall support: sorting, filtering, grouping, column chooser, column resize, sticky headers, pagination or infinite scroll, CSV/Excel/PDF export, saved filters/layouts, keyboard navigation, and bulk actions.

## 8. Forms
- Enterprise forms shall support validation, autosave/draft mode, undo/redo, dirty-state tracking, multi-step wizards where applicable, dynamic field dependencies, and consolidated error summaries.

## 9. Deployment & Operations
- CI/CD pipelines shall be used for all three applications (explicit: Azure DevOps / GitHub Actions).
- The system shall include monitoring and alerting for production issues (explicit: "Monitoring" under Deployment).

## 10. Localization (Inferred Gap)
- Given the likely customer base (India-based LPG customers per OMC references), multi-language support for at least the Customer App is a probable requirement not addressed in the blueprint. Flagged in `questions/open-questions.md`.

## 11. Consolidated NFR Summary Table

| Category | Explicit in Blueprint? | Detail Document |
|---|---|---|
| Security | Partially (JWT, RBAC mentioned) | `requirements/security.md` |
| Performance | Partially ("Load Testing" mentioned) | `requirements/performance.md` |
| Accessibility | Not mentioned in blueprint; explicit in extended instructions | `requirements/accessibility.md` |
| Reliability/DR | Explicit | This document, §1 |
| Scalability | Implicit only | This document, §2 |
| Auditability | Not explicit; inferred | This document, §4 |
| Usability/Design System | Explicit in extended instructions only | This document, §5 |
| Printing | Explicit in extended instructions only | This document, §6 |
