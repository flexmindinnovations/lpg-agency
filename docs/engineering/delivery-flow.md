# Workflow: Delivery Flow

## 1. Overview
End-to-end flow from route planning through delivery confirmation and end-of-shift reconciliation.

## 2. Actors
Agency Staff (Route Planner), Warehouse Manager, Delivery Driver, Customer, System.

## 3. Preconditions
- Sufficient Pending orders exist for planning.
- Vehicle and driver are available (not on maintenance/leave).
- Warehouse has sufficient filled-cylinder stock.

## 4. Main Flow

### Phase A — Route Planning (Agency Dashboard)
1. Staff opens Route Planning view; sees Pending orders (optionally grouped by zone).
2. Staff selects orders to include in a route and assigns a driver + vehicle.
3. System validates the vehicle's planned load will cover the order set's cylinder demand (BR-09).
4. Route is created; all included orders transition from **Pending → Assigned** (BR-07).

### Phase B — Vehicle Loading (Warehouse)
5. Warehouse Manager (or driver) loads the vehicle with filled cylinders and takes empty containers for the route (example from blueprint: 50 Filled / 10 Empty).
6. System records a VehicleLoadEvent; Warehouse inventory decreases and Vehicle inventory increases correspondingly (BR-12).

### Phase C — Delivery Execution (Driver App)
7. Driver opens the Driver App, views assigned route/stops in sequence.
8. Driver navigates to each stop (Route Navigation).
9. At each stop:
   a. Driver confirms cylinders to deliver and empties to collect for that order.
   b. Customer verifies via OTP.
   c. Customer provides digital signature.
   d. Driver captures photo proof.
   e. System captures GPS location.
   f. Payment is collected if COD (Cash/UPI/Card).
10. System validates all four Proof-of-Delivery elements are present (BR-08, BR-23), then transitions the order **Assigned → Delivered**.
11. System updates: Vehicle inventory (BR-13), Customer Cylinder Ledger (see `workflows/cylinder-ledger.md`), generates Invoice (`modules/accounting.md`), and sends delivery-confirmation notification to customer.

### Phase D — End of Shift
12. Driver returns to warehouse with remaining filled stock and collected empties.
13. System/staff performs shift reconciliation: compares expected vs. actual vehicle stock and expected vs. actual cash collected (BR-14).
14. Any variance is logged for review (`modules/inventory-management.md` §3.5, `modules/accounting.md` §3.4).
15. Driver hands over collected cash to cashier; CashHandover record created.

## 5. Postconditions
- All deliverable orders in the route are Delivered, Failed, or remain Assigned (carried to next shift) — **carry-over handling is a gap, see Open Questions.**
- Vehicle, Warehouse, and Customer inventory levels are all consistent and reconciled.
- Cash collected matches recorded COD payments (or variance is logged).

## 6. Exception Flows
- **E1 — Customer unavailable at delivery**: No defined state exists in the blueprint's 4-state order model (see `modules/order-management.md` gap analysis). Recommended: introduce a "Failed Delivery" outcome with reason code and automatic reschedule/requeue.
- **E2 — OTP/signature capture fails due to connectivity**: Requires offline capture with later sync (assumption A-18) — needs explicit confirmation as a Phase 1 requirement given cost/complexity.
- **E3 — Customer disputes cylinder count at doorstep**: No dispute-resolution process defined in blueprint; recommend a "flag for review" action available to the driver.
- **E4 — Vehicle breakdown mid-route**: Remaining stops need reassignment to another vehicle/driver — process undefined in blueprint.
- **E5 — Insufficient stock discovered mid-route** (e.g., damaged cylinder found): Needs an inventory Adjustment transaction with reason capture.

## 7. Related Business Rules
BR-07, BR-08, BR-09, BR-12, BR-13, BR-14, BR-23, BR-24.

## 8. Related Modules
`modules/delivery-management.md`, `modules/order-management.md`, `modules/inventory-management.md`, `modules/accounting.md`.
