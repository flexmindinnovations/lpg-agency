# 08 — State Machines

## Purpose
Complete lifecycle state diagrams for every stateful entity — the authoritative reference for valid transitions. Any transition not shown is invalid and must be rejected by the Domain layer.

## Scope
Customer, Booking, Order, Delivery (Route/RouteStop), Inventory (Cylinder Status), Cylinder Ledger, Invoice, Payment, Complaint, Notification, Driver, Vehicle.

## 1. Customer State Machine

```mermaid
stateDiagram-v2
    [*] --> draft: registration started
    draft --> kyc_pending: profile submitted
    kyc_pending --> kyc_verified: documents approved
    kyc_pending --> kyc_rejected: documents rejected
    kyc_rejected --> kyc_pending: resubmitted
    kyc_verified --> active: connection issued
    active --> inactive: no activity / staff action
    inactive --> active: reactivated
    active --> blocked: policy violation / fraud flag
    blocked --> active: unblocked after review
    active --> closed: BR-34 settlement sequence complete
    inactive --> closed: BR-34 settlement sequence complete
    closed --> [*]
```

## 2. Booking / Order State Machine (D-07)

*Booking and Order share one lifecycle — no separate Booking table (`01-domain-model.md` §4.3).*

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> booked: submit
    draft --> [*]: abandon (hard delete permitted)
    booked --> confirmed: BR-04 + BR-19 checks pass
    booked --> cancelled: cancel (free, pre-dispatch)
    confirmed --> assigned: route planning (BR-09)
    confirmed --> cancelled: cancel (free)
    assigned --> ready_for_dispatch: vehicle loaded
    assigned --> cancelled: cancel (free)
    ready_for_dispatch --> out_for_delivery: driver departs
    ready_for_dispatch --> cancelled: cancel (free)
    out_for_delivery --> delivered: POD complete (BR-08)
    out_for_delivery --> failed_delivery: delivery attempt failed
    out_for_delivery --> cancelled: cancel (requires Manager approval, D-19)
    failed_delivery --> ready_for_dispatch: reschedule
    failed_delivery --> cancelled: cancel (requires Manager approval)
    delivered --> closed: invoice fully settled
    cancelled --> [*]
    closed --> [*]
```

## 3. Delivery — Route State Machine

```mermaid
stateDiagram-v2
    [*] --> planned
    planned --> loaded: vehicle_load_event recorded (BR-12)
    loaded --> in_progress: first stop departs
    in_progress --> completed: all stops resolved
    completed --> reconciled: reconciliation approved (BR-14, D-16)
    reconciled --> [*]
```

## 4. Delivery — RouteStop State Machine

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> en_route: driver navigating
    en_route --> delivered: POD complete
    en_route --> failed: delivery attempt failed
    delivered --> [*]
    failed --> [*]
```

## 5. Inventory — Cylinder Status State Machine (7-state, D-14)

```mermaid
stateDiagram-v2
    [*] --> filled: GRN received / repair completed
    filled --> empty: customer delivery + collection (exchange)
    empty --> filled: sent for refill via GRN cycle (D-15)
    empty --> damaged: inspection finds damage
    empty --> leakage: inspection finds leak
    filled --> leakage: leak discovered pre-delivery
    damaged --> quarantine: flagged for review
    leakage --> quarantine: flagged for review
    quarantine --> repair: deemed repairable
    quarantine --> scrap: deemed unrepairable
    repair --> filled: repaired and refilled
    scrap --> [*]: removed permanently
```

## 6. Cylinder Ledger — Customer Balance Transitions

```mermaid
stateDiagram-v2
    [*] --> no_connection
    no_connection --> active_balance: initial_connection (+N Filled)
    active_balance --> active_balance: exchange (+1F/-1E)
    active_balance --> active_balance: empty_return (+1E)
    active_balance --> active_balance: new_purchase (+1F)
    active_balance --> active_balance: additional_cylinder (+1F)
    active_balance --> zero_balance: deposit_return
    zero_balance --> connection_closed: connection_closure (BR-34)
    connection_closed --> [*]
```

**Guard:** Exchange requires current Empty ≥ 1 (BR-05); no transition may drive Filled or Empty below 0.

## 7. Invoice / Payment State Machine (D-11)

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> issued: delivery confirmed (D-10)
    issued --> partially_paid: payment received, sum < total
    issued --> paid: payment received, sum == total
    partially_paid --> paid: remaining balance paid
    paid --> closed: settlement period complete
    issued --> refunded: credit note fully refunded (D-17)
    partially_paid --> refunded: credit note fully refunded
    paid --> refunded: post-payment refund approved
    closed --> [*]
    refunded --> [*]
```

## 8. Complaint State Machine (D-20)

```mermaid
stateDiagram-v2
    [*] --> open
    open --> assigned: staff assignment
    assigned --> in_progress: work started
    in_progress --> resolved: resolution recorded
    in_progress --> escalated: SLA breach or manual escalation
    escalated --> in_progress: re-assigned after escalation review
    resolved --> closed: customer feedback received or timeout
    closed --> [*]
```

## 9. Notification State Machine

```mermaid
stateDiagram-v2
    [*] --> queued: triggering event published
    queued --> sent: delivered to provider
    sent --> delivered: provider confirms (where supported)
    sent --> failed: provider error
    failed --> retrying: automatic retry (09-domain-events.md retry policy)
    retrying --> sent: retry succeeded
    retrying --> dead_lettered: retry budget exhausted
    delivered --> [*]
    dead_lettered --> [*]
```

## 10. Driver State Machine

```mermaid
stateDiagram-v2
    [*] --> onboarded: profile + license created
    onboarded --> active: verification complete
    active --> on_leave: leave recorded
    on_leave --> active: leave ended
    active --> inactive: deactivated by staff
    inactive --> active: reactivated
    inactive --> [*]: offboarded (soft-deleted, never hard-deleted)
```

## 11. Vehicle State Machine

```mermaid
stateDiagram-v2
    [*] --> registered
    registered --> active: passed inspection
    active --> maintenance: scheduled/unscheduled maintenance
    maintenance --> active: maintenance complete
    active --> retired: decommissioned
    maintenance --> retired: decommissioned during maintenance
    retired --> [*]
```

## Best Practices
- Every state machine enforced inside the aggregate's own methods, never via direct attribute mutation — database CHECK constraints are a backstop only.
- Invalid transitions raise a specific domain exception mapped to `409 Conflict` with a stable `error_code`.

## Risks
- State machine/code drift — mitigated by Domain-layer unit tests (pytest) enumerating every valid and several invalid transitions per aggregate.

## Alternatives Considered
- Generic configurable workflow engine — rejected for Phase 1 as unnecessary complexity given transitions are well-understood and stable.

## Future Scalability
- Should tenant-customizable workflows emerge, the explicit-method-per-transition design would evolve toward a data-driven state-transition table stored in `tenant_configuration`.
