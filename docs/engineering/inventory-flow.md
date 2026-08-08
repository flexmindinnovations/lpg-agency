# Workflow: Inventory Flow

## 1. Overview
Describes how filled and empty cylinder stock moves through the entire system across its lifecycle: OMC → Warehouse → Vehicle → Customer → Vehicle → Warehouse → OMC. This is the physical/inventory counterpart to the financial and delivery workflows, and directly implements the blueprint's "Cylinder Inventory Logic" section.

## 2. Actors
Warehouse Manager, Delivery Driver, Customer, (external) OMC, System.

## 3. Stock Movement Stages

### Stage 1 — Replenishment (Warehouse ← OMC)
- Agency receives filled cylinders from the OMC bottling plant; sends previously collected empties back for refilling.
- **Not detailed in blueprint** — treated as a manual/offline process in Phase 1 (assumption A-13), with the system providing a simple "Receive Stock" / "Send for Refill" recording capability so warehouse counts stay accurate, even if the OMC-side integration itself is Phase 2.
- Increases Warehouse filled count; decreases Warehouse empty count (cylinders sent out for refill should arguably move to an "In Transit to OMC" sub-status rather than disappear — **gap, see Open Questions**).

### Stage 2 — Vehicle Loading (Vehicle ← Warehouse)
- Per `workflows/delivery-flow.md` Phase B. Warehouse filled decreases, Vehicle filled increases; Warehouse empty capacity reserved for return decreases as empties are pre-loaded (if driver carries empty racks) — **exact mechanics of "10 Empty" loaded in the blueprint's example are ambiguous** (are these empties being delivered out, or space reserved for collection? Treated here as capacity/placeholder, not a delivery of empties to customers — flagged as ambiguous in Open Questions).

### Stage 3 — Delivery Exchange (Customer ⇄ Vehicle)
- Per `workflows/delivery-flow.md` Phase C and `workflows/cylinder-ledger.md`. Vehicle filled decreases by cylinders delivered; Vehicle empty increases by cylinders collected. Customer filled increases; Customer empty decreases (net of the exchange).

### Stage 4 — Vehicle Unload (Warehouse ← Vehicle)
- Per `workflows/delivery-flow.md` Phase D. Remaining vehicle filled stock and all collected empties return to Warehouse. Vehicle filled/empty counts reset toward zero (or held over if a vehicle serves multiple shifts without full unload — **not addressed, Open Question**).

### Stage 5 — Reconciliation
- Per `modules/inventory-management.md` §3.5. Periodic physical stock-take at Warehouse (and potentially spot-checks at Vehicle level) compared against system-recorded counts.

## 4. State Diagram (Conceptual)

```
        Stage1            Stage2              Stage3                Stage4
OMC  <---------->  WAREHOUSE  <---------->  VEHICLE  <---------->  CUSTOMER
     (filled in,             (filled out,             (filled out,
      empty out)              empty in on               empty in on
                               unload)                   delivery)
```

## 5. Data Consistency Requirement
At any point in time, for a given cylinder type:

```
Total cylinders (filled+empty) at OMC + Warehouse + Vehicle(s) + Customer(s)
= Total cylinders owned/leased by the agency (a roughly constant number,
  changing only via new cylinder purchases, losses, or write-offs)
```

This invariant is not explicitly stated in the blueprint but is the natural business-level truth the entire inventory design must uphold, and is the basis for meaningful reconciliation reporting.

## 6. Exception Flows
- **E1 — Stock discrepancy found during reconciliation**: Requires an approved Adjustment transaction with mandatory reason, tied to an approver (BR-28, audit logging).
- **E2 — Cylinder marked damaged/unusable at any stage**: No home in current model (see `modules/inventory-management.md` §3.6 gap) — recommend adding a `Damaged` sub-status parallel to Filled/Empty.
- **E3 — Vehicle stock never fully unloaded (multi-day route)**: Reconciliation logic must handle carried-over balances rather than assuming daily reset to zero.

## 7. Open Items
See `questions/open-questions.md` Q-20 (OMC replenishment detail), Q-29 (loaded-empty ambiguity), Q-30 (multi-day vehicle stock carryover), Q-11 (damaged cylinder status).
