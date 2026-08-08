# 14 — Sequence Diagrams

## Purpose
Mermaid sequence diagrams for the platform's most business-critical end-to-end flows, at use-case/aggregate/event granularity, reflecting the async FastAPI + SQLAlchemy 2.x + Redis stack.

## Scope
Customer Registration, Authentication, Booking, Cylinder Allocation, Driver Assignment, Delivery, Inventory Update, Payment Collection, Invoice Generation, Complaint Resolution, Notification Flow.

## 1. Customer Registration

```mermaid
sequenceDiagram
    actor C as Customer (App)
    participant API as FastAPI Route
    participant UC as RegisterCustomerUseCase
    participant CustAgg as Customer Aggregate
    participant LedAgg as CylinderLedger Aggregate
    participant DB as PostgreSQL (async session)
    participant EVT as Event Bus (asyncio)
    participant N as Notifications

    C->>API: POST /customers
    API->>UC: register_customer(request)
    UC->>CustAgg: Customer.register(...) [BR-22 uniqueness]
    UC->>LedAgg: CylinderLedger.create(customer_id) [BR-01]
    UC->>DB: commit (single transaction, BR-29)
    UC-->>EVT: CustomerRegistered
    EVT->>N: Welcome message (async, post-commit)
    UC-->>API: 201 Created
```

## 2. Authentication (OTP Flow)

```mermaid
sequenceDiagram
    actor C as Customer
    participant API as FastAPI Route
    participant OTPSvc as OTP Service
    participant Redis as Redis (OTP store + rate limit)
    participant SMS as SMS Provider
    participant DB as PostgreSQL

    C->>API: POST /auth/otp/request {phone_number}
    API->>Redis: Check rate limit (5/hour/number)
    Redis-->>API: OK / 429
    API->>OTPSvc: generate_otp(phone_number)
    OTPSvc->>Redis: Store OTP hash, 5-min TTL
    OTPSvc->>SMS: Send OTP
    API-->>C: 200 OK {otp_request_id}

    C->>API: POST /auth/otp/verify {otp_request_id, otp_code}
    API->>Redis: Validate against stored hash
    Redis-->>API: Valid / Invalid / Expired
    API->>DB: find_or_create_user(phone_number), write audit_log(action=login)
    API-->>C: 200 OK {access_token, refresh_token}
```

## 3. Booking

```mermaid
sequenceDiagram
    actor C as Customer
    participant API as FastAPI Route
    participant UC as CreateOrderUseCase
    participant Redis as Redis (idempotency check)
    participant CLE as CreditLimitEvaluator
    participant CCP as CylinderCapPolicy
    participant OrdAgg as Order Aggregate
    participant DB as PostgreSQL
    participant EVT as Event Bus
    participant N as Notifications

    C->>API: POST /orders (Idempotency-Key)
    API->>Redis: Check idempotency key
    Redis-->>API: Not seen / Cached result
    API->>UC: create_order(request)
    UC->>CLE: check_credit_limit [BR-19]
    CLE-->>UC: OK / 409
    UC->>CCP: check_cylinder_cap [BR-04]
    CCP-->>UC: OK / 409
    UC->>OrdAgg: Order.create(status=booked)
    UC->>DB: commit (BR-29)
    UC->>Redis: Cache result against Idempotency-Key
    UC-->>EVT: BookingCreated
    EVT->>N: Booking confirmation
    UC-->>API: 201 Created
```

## 4. Cylinder Allocation (Route Planning + Vehicle Load)

```mermaid
sequenceDiagram
    actor D as Dispatcher
    participant API as FastAPI Route
    participant UC as CreateRouteUseCase
    participant VCC as VehicleCapacityChecker
    participant RouteAgg as Route Aggregate
    actor WS as Warehouse Staff
    participant LUC as LoadVehicleUseCase
    participant WhInv as InventoryLocation (Warehouse)
    participant VhInv as InventoryLocation (Vehicle)
    participant DB as PostgreSQL

    D->>API: POST /routes {order_ids}
    API->>UC: create_route(request)
    UC->>VCC: check_capacity(orders, vehicle) [BR-09]
    VCC-->>UC: OK / backorder some lines [D-08]
    UC->>RouteAgg: Route.create(stops)
    UC->>DB: commit
    UC-->>API: 201 Created

    WS->>API: POST /routes/{id}/load
    API->>LUC: load_vehicle(request)
    LUC->>WhInv: decrement_stock [BR-12]
    LUC->>VhInv: increment_stock [BR-12]
    LUC->>DB: commit (single transaction, BR-29)
    LUC-->>API: 200 OK
```

## 5. Driver Assignment

```mermaid
sequenceDiagram
    actor D as Dispatcher
    participant API as FastAPI Route
    participant UC as AssignDriverUseCase
    participant RouteAgg as Route Aggregate
    participant DrvAgg as Driver Aggregate
    participant DB as PostgreSQL
    participant EVT as Event Bus
    participant N as Notifications

    D->>API: POST /routes {driver_id, vehicle_id}
    API->>UC: assign_driver(request)
    UC->>DrvAgg: check_status [must be active, not on_leave]
    DrvAgg-->>UC: OK / 409
    UC->>RouteAgg: Route.assign_driver(driver_id, vehicle_id)
    UC->>DB: commit
    UC-->>EVT: OrderAssigned (a.k.a. DriverAssigned)
    EVT->>N: Notify driver + customer
    UC-->>API: 200 OK
```

## 6. Delivery

```mermaid
sequenceDiagram
    actor Dr as Driver (App, possibly offline)
    participant Sync as Sync Queue (Drift local DB)
    participant API as FastAPI Route
    participant Redis as Redis (idempotency)
    participant UC as ConfirmDeliveryUseCase
    participant OrdAgg as Order Aggregate
    participant Ledger as CylinderLedger Aggregate
    participant Inv as InventoryLocation Aggregate
    participant DB as PostgreSQL
    participant EVT as Event Bus
    participant Acc as Accounting
    participant N as Notifications

    Dr->>Sync: Confirm delivery (offline-tolerant)
    Sync->>API: POST /orders/{id}/deliver (Idempotency-Key)
    API->>Redis: Check idempotency key
    Redis-->>API: Not seen / Cached result (short-circuit if seen)
    API->>UC: confirm_delivery(request)
    UC->>OrdAgg: Order.confirm_delivery(pod) [BR-08]
    UC->>Inv: record_delivery [BR-13]
    UC->>Ledger: record_exchange [BR-02, BR-05]
    UC->>DB: commit (single transaction, BR-29)
    UC->>Redis: Cache result against Idempotency-Key (7-day TTL)
    UC-->>EVT: CylinderDelivered
    EVT->>Acc: Generate Invoice [D-10]
    EVT->>N: Delivery notification
    UC-->>API: 200 OK
    API-->>Sync: Result cached, sync queue entry marked complete
```

## 7. Inventory Update (Adjustment)

```mermaid
sequenceDiagram
    actor WS as Warehouse Staff
    participant API as FastAPI Route
    participant Perm as Live Permission Check (D-16)
    participant UC as AdjustInventoryUseCase
    participant InvAgg as InventoryLocation Aggregate
    participant DB as PostgreSQL
    participant EVT as Event Bus
    participant N as Notifications

    WS->>API: POST /inventory-locations/{id}/adjustments
    API->>Perm: Verify WarehouseManager/AgencyAdmin [D-16]
    Perm-->>API: Authorized / 403
    API->>UC: adjust_inventory(request)
    UC->>InvAgg: record_transaction(from_status, to_status, qty) [BR-15]
    UC->>DB: commit (BR-29)
    UC-->>EVT: InventoryAdjusted
    EVT->>N: Variance alert (if large)
    UC-->>API: 200 OK
```

## 8. Payment Collection

```mermaid
sequenceDiagram
    actor Dr as Driver
    participant API as FastAPI Route
    participant UC as RecordPaymentUseCase
    participant Inv as Invoice Aggregate
    participant DB as PostgreSQL
    participant EVT as Event Bus
    participant N as Notifications
    participant Rpt as Reporting

    Dr->>API: POST /invoices/{id}/payments
    API->>UC: record_payment(request)
    UC->>Inv: record_payment(method, amount) [D-11]
    Inv-->>UC: partially_paid or paid
    UC->>DB: commit (BR-29)
    UC-->>EVT: PaymentCollected
    EVT->>N: Receipt confirmation
    EVT->>Rpt: Update revenue aggregates
    UC-->>API: 201 Created
```

## 9. Invoice Generation

```mermaid
sequenceDiagram
    participant EVT as Event Bus
    participant IGH as GenerateInvoiceHandler (subscriber to CylinderDelivered)
    participant TCR as TenantConfigurationResolver
    participant Redis as Redis (config cache, read-through)
    participant InvAgg as Invoice Aggregate
    participant DB as PostgreSQL
    participant EVT2 as Event Bus

    EVT->>IGH: CylinderDelivered
    IGH->>TCR: resolve GST rate in effect [BR-31]
    TCR->>Redis: cache lookup
    Redis-->>TCR: hit / miss (falls back to DB on miss)
    IGH->>InvAgg: Invoice.create(lines, tax) [BR-16, D-10]
    IGH->>DB: commit (unique constraint on order_id, BR-17)
    IGH-->>EVT2: InvoiceGenerated
```

## 10. Complaint Resolution

```mermaid
sequenceDiagram
    actor C as Customer
    participant API as FastAPI Route
    participant UC as RaiseComplaintUseCase
    participant Sla as SlaCalculator
    participant CxAgg as Complaint Aggregate
    participant DB as PostgreSQL
    participant EVT as Event Bus
    participant N as Notifications
    participant Scanner as SLA Breach Scanner (scheduled job)
    actor Staff as Assigned Staff

    C->>API: POST /complaints
    API->>UC: raise_complaint(request)
    UC->>Sla: compute_sla_due_at(category, priority) [BR-33]
    UC->>CxAgg: Complaint.create(...)
    UC->>DB: commit
    UC-->>EVT: ComplaintRaised
    EVT->>N: Notify assigned staff
    UC-->>API: 201 Created

    loop every 15 min
        Scanner->>DB: query breaching complaints (partial index, idx_complaint_open_sla)
        Scanner->>CxAgg: Complaint.escalate()
        Scanner-->>EVT: ComplaintSlaBreached
        EVT->>N: Escalation alert
    end

    Staff->>API: POST /complaints/{id}/resolve
    API->>CxAgg: Complaint.resolve(outcome)
    CxAgg-->>EVT: ComplaintResolved
    EVT->>N: Request customer feedback
```

## 11. Notification Flow

```mermaid
sequenceDiagram
    participant EVT as Event Bus
    participant NH as Notification Handler (subscriber)
    participant Tmpl as Template Resolver
    participant Chan as Channel Router (Push/SMS/Email)
    participant Prov as Provider (FCM/SMS Gateway/Email)
    participant DB as PostgreSQL (notification_log)

    EVT->>NH: e.g. CylinderDelivered
    NH->>Tmpl: Resolve template + language (D-27)
    NH->>Chan: Route by tenant-configured channel preference (D-25)
    Chan->>Prov: Send
    alt Success
        Prov-->>DB: log status=sent/delivered
        DB-->>EVT: NotificationSent
    else Failure
        Prov-->>DB: log status=failed
        DB->>NH: Trigger retry (09-domain-events.md retry policy)
    end
```

## Best Practices
- Every diagram shows the transaction/commit boundary explicitly (single "commit" per use case), reinforcing BR-29.
- Security-sensitive live permission checks (D-16-style) are shown as distinct steps, never folded silently into "commit."
- Idempotency checks (Redis) are shown explicitly wherever a client-originated action is plausibly retried (Booking, Delivery), matching `09-domain-events.md`'s idempotency-first design principle.

## Risks
- Diagrams simplify by omitting FastAPI dependency-injection wiring and SQLAlchemy session lifecycle details for readability — the actual async session-per-request pattern still applies to every flow shown.

## Alternatives Considered
- One exhaustive UI-to-DB diagram per flow — rejected in favor of the current use-case→aggregate→DB→event abstraction level.

## Future Scalability
- These diagrams remain valid if bounded contexts are later extracted into separate FastAPI services — only the "Event Bus" step changes from in-process `asyncio` to Redis Streams (`09-domain-events.md` Future Scalability).
