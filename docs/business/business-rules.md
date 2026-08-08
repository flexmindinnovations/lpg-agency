# Business Rules

These are the invariant rules the system must enforce. Rules marked **[Explicit]** are directly stated or directly derivable from the blueprint. Rules marked **[Inferred]** are hidden requirements identified through domain analysis. Rules marked **[Confirmed]** have since been settled by stakeholder decision in `business/decisions.md` and are now binding; where a Confirmed rule supersedes an earlier Inferred one, this is noted.

> **Note:** Several rules below (BR-04, BR-09, BR-14, BR-25) referenced open questions that are now resolved — see the "Confirmed" cross-references added inline.

## 1. Cylinder Ledger Rules

**BR-01 [Explicit]** — Every customer has a running Cylinder Ledger tracking, at minimum: Filled Cylinders Delivered, Empty Cylinders Collected, and Current Balance (filled with customer, empty with customer).

**BR-02 [Explicit]** — A standard refill transaction is an *exchange*: +1 Filled to customer, −1 Empty from customer (per blueprint example: "Refill Delivery +1 / −1").

**BR-03 [Explicit]** — An "Empty Return" transaction (customer returns an empty cylinder without receiving a filled one) is recorded as 0 Filled / +1 Empty.

**BR-04 [Confirmed — D-03]** — The system must prevent (or explicitly flag/require override+reason for) a delivery that would result in a customer's filled-cylinder holding exceeding the maximum permitted cylinders per connection. The cap, along with pricing, taxes, and payment terms, is now parameterized by **Customer Type** (Domestic, Commercial, Industrial, Government) rather than a single agency-wide value.

**BR-05 [Inferred]** — A refill booking should not normally be approved if the customer's current empty-cylinder balance is 0 and no empty cylinder will be surrendered at delivery, unless the agency's policy allows "cylinder-on-advance" (new connection sales) — this needs explicit business confirmation.

**BR-06 [Inferred]** — Every cylinder ledger transaction must be immutable/append-only (never destructively edited) to preserve audit integrity; corrections should be made via offsetting/reversal entries, not edits.

## 2. Order Management Rules

**BR-07 [Explicit]** — Orders progress through defined states: New/Pending → Assigned → Delivered, with a Cancelled branch (per blueprint's dashboard order categories).

**BR-08 [Inferred]** — An order cannot be marked "Delivered" without a completed Proof of Delivery (OTP + signature/photo + GPS), since these are explicitly listed as delivery confirmation requirements.

**BR-09 [Inferred, partially Confirmed — D-08]** — An order should not be assignable to a driver/vehicle whose current vehicle inventory has insufficient filled cylinder stock to fulfill it. Where stock is insufficient, **partial fulfillment is now permitted** (D-08): the order may be assigned with a partial line-item allocation, generating a Backorder for the remainder rather than blocking assignment entirely.

**BR-10 [Inferred]** — Cancellation of an order after driver assignment (but before delivery) must trigger reversal/return of any provisional inventory allocation.

## 3. Inventory Rules

**BR-11 [Explicit]** — Inventory is tracked at three levels: Warehouse, Vehicle, and Customer.

**BR-12 [Explicit]** — When a driver loads a vehicle, filled and empty cylinder counts increase on the vehicle and must be relieved from warehouse stock correspondingly (implied by the driver example: "Driver loads: 50 Filled, 10 Empty").

**BR-13 [Explicit]** — After each delivery, vehicle stock automatically updates: Filled decreases by cylinders delivered, Empty increases by cylinders collected (per blueprint's worked example: Filled 50→35 after delivering 15; Empty 10→24 after collecting 14).

**BR-14 [Confirmed — D-16, D-31]** — Vehicle inventory may legitimately carry over across multiple days without a full unload (D-31), but **daily reconciliation is mandatory regardless of carry-over**. Any variance must be reportable and can only be approved/adjusted by a Warehouse Manager or Agency Admin, with mandatory audit logging (D-16).

**BR-15 [Confirmed — D-14, D-15]** — Cylinder status now spans seven states, not two: **Filled, Empty, Damaged, Leakage, Quarantine, Scrap, Repair.** Empty cylinders returned to the warehouse are received via a **manual GRN (Goods Receipt Note)** process in Phase 1 before being sent for OMC refill (Phase 2: automated IOCL/BPCL/HPCL integration).

## 4. Accounting & Payment Rules

**BR-16 [Explicit]** — The system must generate GST-compliant sales invoices (blueprint names "GST reports" and "Sales invoices" but does not define tax calculation rules).

**BR-17 [Inferred]** — Every delivered order must generate exactly one invoice (or be explicitly linked to a consolidated periodic invoice, if the agency supports that model) — the 1:1 vs. consolidated model is not specified in the blueprint.

**BR-18 [Explicit]** — Payment can be collected via Cash, UPI, or Card at time of delivery (driver app), or online in advance (customer app "online payment integration").

**BR-19 [Confirmed — D-11]** — Outstanding balance for a customer must be visible before a new booking is confirmed. The system supports Full Payment, Partial Payment, and Credit, governed by a **per-customer, tenant-configurable credit limit**.

**BR-20 [Confirmed — D-17]** — Payment reversals/refunds follow a defined workflow: Customer Request → Manager Approval → Credit Note → Refund → Ledger Update.

## 5. Customer & KYC Rules

**BR-21 [Explicit]** — Customers must be KYC-verified (blueprint lists "KYC management" as a Customer Management feature) — specific KYC document requirements are not defined and must be sourced from regional regulation.

**BR-22 [Inferred]** — A customer record must be uniquely linked to one Consumer Number; the system should prevent duplicate consumer number mapping to more than one active customer profile.

## 6. Delivery & Driver Rules

**BR-23 [Explicit]** — Delivery confirmation requires OTP verification, customer signature, and photo proof, plus GPS capture (all four explicitly named in blueprint).

**BR-24 [Inferred]** — A driver should not be assigned deliveries exceeding the physical/loaded capacity of their vehicle — not explicit, but implied by the vehicle-loading example.

**BR-25 [Confirmed — D-29]** — Driver/agency performance KPIs are now defined: On-time Delivery %, Average Delivery Time, Driver Productivity, Revenue, Inventory Accuracy, Customer Satisfaction, Outstanding Collections.

## 7. Notification Rules

**BR-26 [Explicit]** — Customers receive "notifications and reminders" (blueprint names this feature but does not define triggers/cadence).

**BR-27 [Inferred]** — At minimum the following notification triggers should exist (subject to confirmation): booking confirmed, driver assigned/en route, delivery completed (with invoice), payment received, complaint status change, low balance/refill reminder based on average consumption interval.

## 8. Cross-Cutting / Data Integrity Rules

**BR-28 [Inferred]** — All monetary and inventory-affecting actions must be recorded in an audit log capturing who/when/what/before-after values (ties to "Audit Logs" under Security in the extended instructions, and to RBAC).

**BR-29 [Inferred]** — All ledger and inventory mutations must be transactional (all-or-nothing) to prevent partial updates (e.g., a delivery that updates vehicle stock but fails to update the customer ledger).

## 9. New Rules from Confirmed Decisions (see `business/decisions.md`)

**BR-30 [Confirmed — D-01]** — Every business entity (Customer, Order, Inventory, Invoice, etc.) must carry a `tenantId`, and no query or mutation may cross tenant boundaries under any circumstance. This is the foundational data-isolation rule for the multi-tenant architecture.

**BR-31 [Confirmed — D-42]** — Business-configuration values (GST rates, cylinder holding limits, cancellation policies, reminder intervals, credit limits) must be stored as tenant-scoped configuration, never hardcoded, since D-01 establishes multiple tenants with potentially different regional/regulatory needs.

**BR-32 [Confirmed — D-18]** — A driver-declared cash shortfall must follow: Declaration → Investigation → Approval → Adjustment Entry → Audit Log. No shortfall may be silently written off outside this workflow.

**BR-33 [Confirmed — D-20]** — Every customer complaint must be categorized, prioritized, and assigned an SLA at creation; SLA breach must be detectable/reportable (supports the new Complaint Management module — see `modules/complaint-management.md`).

**BR-34 [Confirmed — D-21, D-09]** — Connection closure requires, in order: cylinder return verification → cylinder ledger zero-balance confirmation → deposit refund (via the "Deposit Return" transaction type) → account closure → customer archival (soft, not hard delete, per FR-CM-07).
