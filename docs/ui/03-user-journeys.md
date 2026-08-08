# 03 — User Journeys

## Purpose
Maps the end-to-end experience across all three apps for each major workflow, grounded in the approved state machines (`docs/data/08-state-machines.md`) and workflows (`docs/engineering/*.md`). These are UX journeys, not new business logic — every step below maps to an existing state transition or API endpoint.

## 1. Customer Registration

| Step | App | Screen | Notes |
|---|---|---|---|
| 1 | Customer App | Splash → Phone Entry | Single field, large touch target |
| 2 | Customer App | OTP Verification | Auto-read OTP where platform permits, 6-digit input with auto-advance |
| 3 | Customer App | Profile Setup | Name, Customer Type (if self-selectable), primary address with map pin |
| 4 | Customer App | KYC Upload (optional at this stage) | Camera capture or file picker, clear "why we need this" copy |
| 5 | Customer App | Home Screen | Lands on Home with cylinder balance (0 initially) and "Book your first refill" CTA |

**Staff-assisted variant** (Dashboard): Dispatcher/Staff searches for existing customer by phone first (prevents duplicates, BR-22), then opens "New Customer" drawer form if not found — same fields, denser layout.

## 2. Booking

| Step | App | Screen |
|---|---|---|
| 1 | Customer App | Home → "Book Refill" |
| 2 | Customer App | Cylinder & quantity selection (shows current balance inline) |
| 3 | Customer App | Address confirmation (defaults to primary) |
| 4 | Customer App | Payment method selection (Pay Now / Pay on Delivery) |
| 5 | Customer App | Order Confirmation screen with live status stepper |
| 6 | Dashboard | Order appears in Dispatcher's "New/Pending" queue in real time |

Staff-assisted booking on the Dashboard follows the same field set, one screen (not a multi-step wizard), since staff move faster with everything visible at once.

## 3. Delivery

| Step | App | Screen |
|---|---|---|
| 1 | Dashboard | Dispatcher builds a Route from the Order Queue (drag or multi-select + "Add to Route") |
| 2 | Dashboard | Assign Driver + Vehicle |
| 3 | Driver App | Route appears on Driver's "Today" screen, ordered stops |
| 4 | Driver App | Vehicle Load confirmation (Warehouse Staff or Driver, at shift start) |
| 5 | Driver App | Per-stop: Navigate → Arrive → Confirm Delivery (OTP + Signature + Photo + GPS) |
| 6 | Customer App | Real-time status updates: Assigned → Out for Delivery → Delivered, with push notifications |
| 7 | Driver App | Payment collection screen (if COD) |
| 8 | Driver App | End-of-shift Reconciliation screen |

## 4. Inventory

| Step | App | Screen |
|---|---|---|
| 1 | Dashboard | Warehouse Staff records GRN receipt from OMC (manual entry, D-15) |
| 2 | Dashboard | Warehouse Staff views real-time stock balance by cylinder type/status |
| 3 | Driver App | Vehicle load recorded at shift start |
| 4 | Dashboard/Driver App | Damaged/leaking cylinder flagged mid-shift (Driver) or at warehouse (Staff) — quick "Report Issue" action |
| 5 | Dashboard | Reconciliation review + approval (Warehouse Manager/Agency Admin, D-16) |

## 5. Payments

| Step | App | Screen |
|---|---|---|
| 1 | Driver App | Payment collection at delivery (Cash/UPI/Card) |
| 2 | Customer App | Online prepayment at booking (optional path) |
| 3 | Dashboard | Accountant reviews Invoices/Payments list, filters by status |
| 4 | Dashboard | Accountant initiates a Credit Note request; Manager approves from their queue |
| 5 | Customer App | Customer views/downloads invoice from Order History |

## 6. Reporting

| Step | App | Screen |
|---|---|---|
| 1 | Dashboard | Any staff role opens Reports module, selects report type |
| 2 | Dashboard | Filters (date range, branch) applied, live preview |
| 3 | Dashboard | Export (CSV/Excel/PDF) triggers async job (`docs/data/11-api-contracts.md`), download link appears when ready |
| 4 | Dashboard | Agency Owner sees the same KPIs surfaced as Dashboard widgets, no navigation required |

## 7. Complaints

| Step | App | Screen |
|---|---|---|
| 1 | Customer App | "Raise a Complaint" from Order History or Home |
| 2 | Customer App | Category + description form, optional photo attachment |
| 3 | Dashboard | Complaint appears in assigned staff's queue with SLA countdown visible |
| 4 | Dashboard | Staff resolves or escalates; escalation surfaces to Manager automatically |
| 5 | Customer App | Push notification on status change; feedback prompt (satisfaction rating) on resolution |

## 8. Administration

| Step | App | Screen |
|---|---|---|
| 1 | Dashboard | Agency Admin opens Settings → Tenant Configuration |
| 2 | Dashboard | Adjusts GST rate, cylinder caps, credit limits, cancellation policy, reminder intervals (BR-31) |
| 3 | Dashboard | Staff Management: invite/deactivate users, assign roles |
| 4 | Dashboard | Branch/Warehouse management (multi-branch tenants, D-02) |
| 5 | Dashboard | Reference data management (Cylinder Types, Complaint Categories, Tax Types — tenant-scoped per `docs/data/05-reference-data.md`) |

## Cross-Journey UX Principles
- Every journey that spans multiple apps (Booking → Delivery → Payment) has a **visible, consistent status representation** across apps — the Order state machine's terminology (Confirmed, Out for Delivery, Delivered) is never renamed or reworded differently between Customer App and Dashboard.
- Every journey ends at a clear terminal state screen (Order Confirmation, Delivery Complete, Report Ready) — no journey silently trails off without confirming completion to the user.
- Approval-gated steps (D-16, D-17, D-19) always surface in the approver's queue with a one-click approve/reject path — never buried in a detail screen the approver has to know to look for.

## Risks
- Journeys spanning Driver App offline states need explicit UX for "queued, will sync" (see `21-empty-error-success-states.md` for the offline-state pattern) so a Driver never wonders whether an action actually registered.

## Future Scalability
- WhatsApp booking (Phase 2, D-25) will insert a new entry point into the Booking journey without altering the confirmation/tracking steps downstream — journeys are designed with entry-point-agnostic downstream steps for this reason.
