# Workflow: Cylinder Ledger

## 1. Overview
This is the system's most business-critical workflow. The blueprint explicitly states: *"System should always know exact customer holdings... This is the most important module."* This document formalizes that logic into an auditable, transactional workflow.

## 2. Core Concept
Every customer has a running ledger of two counters — **Filled Cylinders Held** and **Empty Cylinders Held** — plus an immutable, append-only transaction history that explains how those counters reached their current values. The counters are *derived* (computed/materialized) from the transaction history, not independently editable — this is essential for auditability (BR-06).

## 3. Transaction Types (per blueprint's worked example, plus inferred completions)

| Transaction Type | Filled Δ | Empty Δ | Source | Status |
|---|---|---|---|---|
| Initial Connection | +N | 0 | New customer signup with N cylinders | Explicit (example: Initial 2/0) |
| Refill Delivery (standard exchange) | +1 | −1 | Delivery Confirmation | Explicit |
| Empty Return (no refill) | 0 | +1 | Customer returns empty without booking a refill | Explicit |
| New Cylinder Purchase (no exchange) | +1 | 0 | Customer buys an additional cylinder outright | Inferred — needed to distinguish from standard exchange (see `workflows/customer-booking.md` E4) |
| Connection Closure / Final Settlement | −(remaining) | −(remaining) | Customer surrenders all cylinders on account closure | Inferred gap — not addressed in blueprint |
| Lost/Damaged Cylinder Write-off | −1 or n/a | −1 or n/a | Administrative adjustment | Inferred gap |

## 4. Worked Example (from Blueprint, Reproduced for Traceability)

| Transaction | Filled | Empty |
|---|---|---|
| Initial | 2 | 0 |
| Refill Delivery | +1 | −1 |
| Empty Return | 0 | +1 |

Resulting customer holding after these three transactions, per the blueprint's example: **Filled = 2, Empty = 1.**

*(Trace: Initial sets Filled=2, Empty=0. Refill Delivery: Filled=2+1=3, Empty=0−1=−1 — this produces a negative empty balance, which is logically invalid on its own. This confirms the blueprint's transactions are illustrative and sequence-dependent on real preceding state rather than a strict literal cumulative sum starting from zero; the system's actual ledger engine must never allow Empty (or Filled) to go negative, and must validate that a "Refill Delivery" transaction only executes when the customer's actual current Empty balance ≥ 1, consistent with BR-05.)*

This inconsistency in the source blueprint's illustrative numbers is called out explicitly here rather than silently reconciled, per the governing instruction to state gaps rather than assume.

## 5. Business Rules Governing the Ledger
BR-01 through BR-06 (see `business/business-rules.md`), plus the non-negative-balance invariant identified above.

## 6. Process Flow

1. A triggering event occurs (delivery confirmed, empty returned at the door, admin adjustment, etc.) in the originating module (Delivery Management, Order Management, or Admin).
2. The originating module calls the Cylinder Ledger to record a new **CylinderLedgerTransaction** (append-only).
3. The Ledger validates the transaction against current balances (e.g., cannot deduct more empties than the customer currently holds).
4. If valid, the transaction is persisted and the customer's materialized balance (Filled/Empty) is updated within the same atomic operation (BR-29 — no partial updates).
5. If invalid, the transaction is rejected and the originating action (e.g., marking an order "Delivered") must also fail/roll back — the ledger and order status must never diverge.
6. The updated balance is immediately reflected to: Customer App (balance view), Agency Dashboard (customer inventory view), and Reporting (consumption analysis).

## 7. Data Entities (Conceptual)
- **CylinderLedgerTransaction**: id, customerId, transactionType, filledDelta, emptyDelta, referenceOrderId (nullable), performedBy, performedAt, notes
- **CustomerCylinderBalance** (materialized): customerId, filledCount, emptyCount, lastTransactionId, updatedAt

## 8. Edge Cases
- Concurrent transactions for the same customer (e.g., a correction and a delivery happening near-simultaneously) — requires locking/serialization per customer to prevent race conditions.
- Historical balance queries ("what was this customer's balance on a given date") — requires point-in-time reconstruction from the transaction log, not just the current materialized balance.
- Ledger correction after an error is discovered — must be a new offsetting transaction (e.g., "Correction: −1 Filled, reason: duplicate delivery entry"), never an edit/delete of the original (BR-06).
- Connection closure with an outstanding cylinder imbalance (customer owes empties or agency owes a deposit refund) — settlement process not defined in blueprint (Open Question).

## 9. Related Modules
`modules/inventory-management.md`, `modules/customer-management.md`, `modules/delivery-management.md`, `modules/order-management.md`.

## 10. Open Items
See `questions/open-questions.md` Q-34 (connection closure settlement), Q-35 (new-purchase vs. exchange distinction confirmation).
