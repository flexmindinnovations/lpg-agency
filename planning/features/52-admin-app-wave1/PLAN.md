# 52 — Admin app Wave 1: revamp, navigation, live dashboard, search, and the owner's daily modules

## Why
The dashboard (web) is the full agency console; the Admin app (Android) covers orders, dispatch, fleet, approvals and alerts only. An owner on the move cannot see a customer's balance, an invoice, a complaint, stock or the cash book. The app also looks dated, its bottom bar holds six crowded tabs, the dashboard tiles are static, there is no search, and a shortage of free vans or drivers dead-ends the Send out flow.

## Decisions
- **Wave 1 modules (phone-friendly daily work):** Customers (with ledger), Invoices (view, send, UPI QR, record payment), Complaints, Stock, Cash book.
- **Web-only (not ported):** platform console, feature flags, licence and devices, audit log, full reports/GSTR data, bulk master-data setup.
- **Wave 2 (later):** pricing, users and roles, employees, compliance alerts.
- The shared `design_system` package also serves the Customer and Driver apps, so restyling is **additive and Admin-specific** (new widgets in `admin_app`), not a global token change.
- Same backend and RBAC as the dashboard: each screen is hidden unless the signed-in staff member holds the permission the web page needs.

## Phases (each ends with analyze + tests green and a run on the emulator)
**A. Foundation**
1. Navigation: 4 bottom tabs (Home, Orders, Dispatch, More). Alerts is a bell with badge in the app bar. Search icon in the app bar. "More" lists everything else, grouped.
2. Look and feel: refreshed hierarchy, icon set usage (Lucide stays), surfaces, spacing, a consistent app bar, empty/loading/error states.
3. Dashboard: live, tappable tiles that open the filtered screen behind each number; refreshes on realtime events and on a timer.
4. Search: one global search (orders, customers, invoices, complaints) plus search in each list.
5. Vans and drivers blocking Send out: show why, and give a way forward (add a van/driver, see which trips hold them, add the order to an open trip, free the van).
6. App icon and in-app logo for the Admin app.

**B. Modules, one at a time, end to end (API -> screen -> actions -> tests -> emulator)**
1. Customers + ledger
2. Invoices (+ UPI QR, record payment)
3. Complaints
4. Stock
5. Cash book

## Risks
- Backend list endpoints must support staff scope, search and status filters; gaps are recorded in TASKS and fixed in the backend with tests.
- Hand-written `api_client` (ADR-037): new methods need model tests.
- The emulator cannot verify push notifications or real UPI apps.
