# Module: Complaint Management

> **Status:** This module did not exist in the original blueprint or the first draft of this SRS — it was identified there only as a Customer App feature name with no defined workflow (see `modules/notifications.md` §8, historical). Per stakeholder decision `business/decisions.md` D-20, it is now elevated to a full dedicated module.

## 1. Purpose
Provides structured intake, tracking, and resolution of customer complaints (e.g., short delivery, quality issues, billing disputes, driver conduct), with defined SLAs and escalation — directly supporting the blueprint's original "Complaint management" feature reference and the business objective of improved customer experience.

## 2. Features

### 2.1 Complaint Intake
- Customer raises a complaint via the Customer App, referencing an order/invoice/delivery where applicable, or as a general complaint.
- Staff may also log a complaint on a customer's behalf (phone-reported issues).

### 2.2 Categorization & Priority
- Each complaint is assigned a **Category** (e.g., Short Delivery, Damaged Cylinder, Billing Dispute, Driver Conduct, Late Delivery, Other) and a **Priority** (e.g., Low/Medium/High/Critical) at creation (BR-33).
- Category taxonomy is tenant-configurable, consistent with BR-31.

### 2.3 SLA Management
- Each category/priority combination has a target resolution time (SLA).
- System must be able to report SLA breaches (ties to `modules/reporting.md` and the Reporting module's KPI set, D-29).

### 2.4 Assignment
- Complaints are assigned to a responsible staff member (e.g., Manager, Dispatcher, or Accountant depending on category) — assignment rules are tenant-configurable.

### 2.5 Escalation
- Unresolved complaints nearing or breaching SLA are automatically escalated (e.g., to Agency Admin) — specific escalation chain/timing to be defined during design phase.

### 2.6 Resolution & Customer Feedback
- Staff records resolution notes and outcome (e.g., Resolved, Compensated, Rejected).
- Customer is prompted for feedback/satisfaction rating on resolution — feeds the "Customer Satisfaction" KPI (D-29).

## 3. Data Entities (Conceptual)
- **Complaint**: id, tenantId, customerId, referenceOrderId (nullable), category, priority, description, status (Open/Assigned/In Progress/Resolved/Escalated/Closed), slaDueAt, createdAt
- **ComplaintAssignment**: complaintId, assignedTo, assignedAt
- **ComplaintResolution**: complaintId, resolutionNotes, outcome, resolvedBy, resolvedAt
- **ComplaintFeedback**: complaintId, satisfactionRating, comments, submittedAt

## 4. Business Rules Applied
BR-33 (SLA assignment mandatory at creation).

## 5. Dependencies
- **Depends on:** Customer Management (customer identity), Order Management (order/delivery reference), Notifications (status-change alerts to customer, per `modules/notifications.md`).
- **Depended on by:** Reporting (SLA breach reports, Customer Satisfaction KPI).

## 6. Edge Cases
- Complaint references a delivery that is later found to be correctly fulfilled (false complaint) — needs a "Rejected" outcome distinct from "Resolved."
- Complaint escalated multiple times without resolution — needs a cap/final-escalation-tier definition (design-phase detail, not yet specified).
- Complaint tied to a driver conduct issue — may need to feed into Driver Performance reporting (`modules/reporting.md`) as a negative signal; exact linkage not yet defined.

## 7. Open Items (Design-Phase, Non-Blocking)
- Exact SLA durations per category/priority.
- Escalation chain and timing.
- Whether compensation (credit note, discount) issued through a resolved complaint ties back into the Accounting refund workflow (`modules/accounting.md` §3.7, D-17) — likely yes, should be confirmed during design.
