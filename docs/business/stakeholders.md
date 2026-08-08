# Stakeholders & Actors

## 1. Primary Actors (Direct System Users)

### 1.1 Customer (Consumer)
**Definition:** An individual or household holding an active LPG connection with the agency.
**Goals:** Book a refill quickly, know when it will arrive, pay conveniently, track cylinder balance, raise/resolve complaints.
**System Surface:** Customer Mobile App.
**Notes:** May include sub-types not explicitly separated in the blueprint — see `assumptions.md` (Domestic vs. Commercial customer).

### 1.2 Delivery Driver
**Definition:** Agency staff (or contracted delivery personnel) responsible for physically delivering filled cylinders and collecting empty cylinders.
**Goals:** Receive clear delivery assignments, navigate efficiently, confirm delivery with minimal friction, collect payment, avoid inventory disputes at end of shift.
**System Surface:** Driver Mobile App.

### 1.3 Agency Staff / Operator (Back-Office / Call Center)
**Definition:** Employees who process bookings received via phone/walk-in, manage customer master data, and handle day-to-day order processing.
**Goals:** Create/edit orders quickly, assign drivers, resolve customer issues, view stock availability before promising delivery dates.
**System Surface:** Agency Web Dashboard (subset of permissions).
**Note:** Not explicitly named in the blueprint but implicitly required — the blueprint assumes bookings can originate from the Customer App, but real agencies take a large share of orders by phone/walk-in. Flagged in `assumptions.md`.

### 1.4 Warehouse / Inventory Manager
**Definition:** Person(s) responsible for warehouse-level filled/empty cylinder stock, receiving stock from the OMC/bottling plant, and reconciling vehicle loads.
**Goals:** Accurate stock counts, timely replenishment, minimal shrinkage.
**System Surface:** Agency Web Dashboard — Inventory module.
**Note:** Implicit role inferred from "Warehouse inventory" feature; not explicitly named as an actor in the blueprint.

### 1.5 Accountant / Billing Staff
**Definition:** Person(s) responsible for invoicing, payment reconciliation, outstanding balance follow-up, and GST reporting.
**Goals:** Accurate, timely invoices; clear visibility into outstanding dues; simplified statutory reporting.
**System Surface:** Agency Web Dashboard — Accounting module.

### 1.6 Agency Owner / Manager (Admin)
**Definition:** Owner or senior manager of the agency; typically the system administrator.
**Goals:** Real-time visibility into KPIs (orders, revenue, stock, outstanding payments), operational control, staff performance monitoring.
**System Surface:** Agency Web Dashboard — full access, Dashboard/KPI module.

### 1.7 System Administrator (IT/Super Admin)
**Definition:** Technical administrator managing user accounts, roles/permissions, and system configuration.
**Goals:** Secure onboarding/offboarding of staff, correct RBAC configuration, audit trail integrity.
**System Surface:** Agency Web Dashboard — Admin module.
**Note:** Implicit — the blueprint references "Role-based security" and RBAC but does not explicitly define this actor. Flagged for confirmation.

## 2. Secondary / Indirect Stakeholders

### 2.1 Oil Marketing Company (OMC) — e.g., IOCL, BPCL, HPCL
Not a direct system user in Phase 1, but a key external stakeholder: the agency procures filled cylinder stock from the OMC's bottling plant, and OMC integration is explicitly named as a **Phase 2** item ("integration with government LPG distributors").

### 2.2 Payment Gateway Provider
External stakeholder enabling online and possibly in-app UPI/card payments. Named generically ("Payment Gateway") without a specific provider in the blueprint.

### 2.3 Regulatory / Government Bodies
Indirect stakeholder — GST authority (tax compliance), and (inferred, not explicit in blueprint) petroleum/explosives safety regulators governing cylinder handling and storage.

### 2.4 Business/Product Owner Commissioning the System
The party who requested this SRS — responsible for prioritizing the open questions list and approving scope before development begins.

## 3. Actor Interaction Summary

| Actor | Creates Orders | Manages Inventory | Handles Payments | Views Reports | Manages Users |
|---|---|---|---|---|---|
| Customer | Yes (self) | No | Yes (own) | Own history only | No |
| Delivery Driver | No | Updates vehicle stock only | Collects (COD) | Own delivery history | No |
| Agency Staff/Operator | Yes (on behalf of customer) | View only (typically) | View/record | Operational reports | No |
| Warehouse Manager | No | Yes (warehouse/vehicle) | No | Inventory reports | No |
| Accountant | No | No | Yes (full) | Financial reports | No |
| Agency Owner/Admin | Yes (all) | Yes (all) | Yes (all) | All reports | Yes |
| System Admin | No | No | No | Audit logs | Yes |

*This matrix is a working hypothesis derived from the blueprint's module list; it should be validated against real agency org structures (see Open Questions).*

## 4. Actors Explicitly Named in Blueprint vs. Inferred

| Actor | Status |
|---|---|
| Customer | Explicit |
| Delivery Driver | Explicit |
| Agency (generic "dashboard user") | Explicit but roles not broken down |
| Agency Staff/Operator | Inferred |
| Warehouse Manager | Inferred |
| Accountant | Inferred |
| Agency Owner/Admin | Inferred (implied by "Dashboard KPIs" and RBAC mention) |
| System Administrator | Inferred |
| OMC (IOCL/BPCL/HPCL) | Explicit (Phase 2 only) |

## 5. CONFIRMED RBAC Role List (supersedes §3/§4 above — see `business/decisions.md` D-38)

The business has since confirmed the authoritative role list: **Super Admin, Agency Admin, Manager, Warehouse Staff, Dispatcher, Accountant, Driver, Customer.**

Mapping from this document's earlier inferred actors to the confirmed roles:

| Earlier Inferred Actor (§1) | Confirmed Role |
|---|---|
| Agency Owner/Admin | Agency Admin |
| Agency Staff/Operator | Manager / Dispatcher (split — Dispatcher now explicitly named for route/assignment work) |
| Warehouse/Inventory Manager | Warehouse Staff |
| Accountant | Accountant (unchanged) |
| System Administrator | Super Admin (now tenant-spanning, per multi-tenancy decision D-01) |
| Customer | Customer (unchanged) |
| Delivery Driver | Driver (unchanged) |

**Residual, non-blocking question:** whether "Warehouse Staff" (confirmed role list) and "Warehouse Manager" (named as the sole approver for inventory adjustments in D-16) represent the same role or a staff/supervisor tier pair — see `questions/open-questions.md` notes.
