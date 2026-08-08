# Open Questions — Status Tracker

## Status: All Questions Resolved

Every question originally listed in this document has been answered by the business/product stakeholder. Full decision detail, rationale, and downstream document impact for each item lives in **`docs/business/decisions.md`**. This file is retained as a historical tracker and index — use it to quickly find the resolution status and jump to the relevant decision.

## Resolution Index

| ID | Question (Short) | Resolved By | Priority (Original) |
|---|---|---|---|
| Q-01 | Multi-tenancy | D-01 | Critical |
| Q-02 | Multi-warehouse/branch support | D-02 | Critical |
| Q-03 | Customer/connection types | D-03 | Critical |
| Q-04 | Cylinder size/SKU granularity | D-04 | Critical |
| Q-13 | Regulatory jurisdiction | D-06 | Critical |
| Q-14 | Order state model | D-07 | High |
| Q-15 | Partial order fulfillment | D-08 | High |
| Q-05 | Booking channels | D-05 | High |
| Q-35 | Exchange vs. new-purchase distinction | D-09 | High |
| Q-08 | Invoicing model | D-10 | High |
| Q-32 | Deferred/partial payment policy | D-11 | High |
| Q-17 | Failed delivery handling | D-12 | Medium |
| Q-18 | Payment refusal at doorstep | D-13 | Medium |
| Q-11 | Damaged cylinder handling | D-14 | Medium |
| Q-20 | OMC replenishment process | D-15 | Medium |
| Q-21 | Reconciliation authority/workflow | D-16 | Medium |
| Q-09 | Refund workflow | D-17 | Medium |
| Q-22 | Cash shortfall handling | D-18 | Medium |
| Q-16 | Cancellation policy | D-19 | Medium |
| Q-28 | Complaint management scope | D-20 | Medium |
| Q-34 | Connection closure settlement | D-21 | Medium |
| Q-06 | Route/shift model | D-22 | Lower |
| Q-07 | Fleet ownership model | D-23 | Lower |
| Q-19 / Q-12 | Offline mode requirement | D-24 | Lower |
| Q-25 | Notification channels | D-25 | Lower |
| Q-26 | Reminder trigger logic | D-26 | Lower |
| Q-27 | Multi-language requirement | D-27 | Lower |
| Q-23 | Report scheduling | D-28 | Lower |
| Q-24 | KPI formula definitions | D-29 | Lower |
| Q-29 | Loaded-empty ambiguity | D-30 | Lower |
| Q-30 | Multi-day vehicle stock carryover | D-31 | Lower |
| Q-31 | UPI/Card device integration model | D-32 | Lower |
| Q-33 | Collections process | D-33 | Lower |
| Q-36 | Performance SLAs | D-34 | Lower |
| Q-37 | Accessibility scope/timing | D-35 | Lower |
| Q-10 | Cylinder-level (barcode/QR) tracking timing | D-36 | Lower |

## Notes on Resolution Quality

These are **stakeholder-provided architectural recommendations**, not facts extracted from the original blueprint PDF — the blueprint itself was silent on nearly all of them. They are documented here as binding decisions because the business has explicitly adopted them, but a few carry residual implementation questions that should be tracked as **new, narrower, design-phase questions** rather than reopening the original business questions:

- **D-04 / D-14 (cylinder types × 7 statuses)**: The inventory data model now needs one counter per (cylinder type × status × location) combination — this is a meaningfully larger schema than originally scoped. Confirm this granularity doesn't need further collapsing for Phase 1 (e.g., is "Quarantine" truly distinct from "Damaged" for a first release, or can they be merged and split later?).
- **D-19 (cancellation charge)**: "Possible cancellation charge" — the fee amount/percentage and whether it's tenant-configurable is not yet specified.
- **D-24 (offline-first Driver App)**: Elevating this to Must-have is a significant engineering scope increase; recommend confirming this doesn't slip Phase 1 timeline before committing to it as a hard launch blocker.
- **D-38 (RBAC role rename)**: "Warehouse Manager" (original) vs. "Warehouse Staff" (new) — confirm whether these are the same role renamed, or two distinct roles (staff + a supervisory manager tier), since the decision text uses "Warehouse Staff" in the role list but "Warehouse Manager" in D-16's approval authority.

These follow-up items are minor and do not block proceeding to system design.
