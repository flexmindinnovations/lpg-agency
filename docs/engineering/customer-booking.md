# Workflow: Customer Booking (Refill Request)

## 1. Overview
End-to-end flow of a customer requesting a cylinder refill, from initiation through order confirmation. Covers both self-service (Customer App) and staff-assisted (phone/walk-in) paths.

## 2. Actors
Customer, (optionally) Agency Staff/Operator, System.

## 3. Preconditions
- Customer has an active, KYC-verified account with a mapped Consumer Number.
- Customer's outstanding balance is within policy limits (BR-19) — *policy threshold not yet defined, see Open Questions*.

## 4. Main Flow (Customer Self-Service)

1. Customer logs into the Customer App (OTP authentication).
2. Customer selects "Book Refill."
3. System displays customer's current cylinder balance and delivery address(es).
4. Customer selects cylinder type/quantity (if multiple types supported — see A-04) and confirms delivery address.
5. Customer selects preferred delivery date/time window (if the agency supports scheduling — not explicit in blueprint, treated as inferred UX necessity).
6. Customer selects payment method: pay online now, or pay on delivery (Cash/UPI/Card via driver).
7. System validates:
   a. Customer's outstanding balance against agency credit policy (BR-19).
   b. Customer's current cylinder holding against the maximum permitted cap, if configured (BR-04).
8. System creates the Order in **New/Pending** status.
9. System sends booking confirmation notification to customer (Notifications module).
10. Order appears in Agency Dashboard's "New/Pending" queue for route assignment.

## 5. Alternate Flow (Staff-Assisted Booking)
Steps 1–2 are replaced by: Agency Staff searches for the customer by phone/Consumer Number in the Dashboard and initiates booking on their behalf. Steps 3–10 proceed identically, with `createdBy = staff` recorded on the order (per `modules/order-management.md` data model).

## 6. Postconditions
- Order exists in Pending status, visible for route planning.
- Customer/staff receives confirmation.

## 7. Exception Flows
- **E1 — Outstanding balance exceeds policy limit**: Booking is blocked or flagged for manager override. *(Exact behavior — hard block vs. soft warning — is an open question; blueprint does not specify.)*
- **E2 — Customer holding cap exceeded**: Booking blocked unless an empty-cylinder return is scheduled as part of the same request (standard exchange model) — this is effectively the default case (BR-02), not really an exception, but worth calling out for clarity.
- **E3 — No delivery capacity available for requested date/zone**: System should surface next available date rather than silently failing — **not addressed in blueprint**, inferred UX requirement.
- **E4 — Customer has zero empty cylinders and requests a refill without returning one**: Only valid for new-connection cylinder purchase; system must distinguish "refill exchange" from "new cylinder sale" bookings (gap — see `business/assumptions.md` A-05 area and Open Questions).

## 8. Related Business Rules
BR-02, BR-04, BR-05, BR-19 (see `business/business-rules.md`).

## 9. Related Modules
`modules/order-management.md`, `modules/customer-management.md`, `modules/notifications.md`.
