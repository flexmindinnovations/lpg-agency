# Functional Requirements

Requirements are grouped by module and numbered `FR-<Module>-<n>`. Each is traceable to blueprint content (Explicit), identified as a hidden requirement (Inferred), or now **Confirmed** via stakeholder decision (`business/decisions.md`). Priority: **M**ust-have, **S**hould-have, **C**ould-have (MoSCoW). Priorities below have been updated where a confirmed decision changed them from the original draft (see inline notes).

## 1. Customer Management (CM)
| ID | Requirement | Source | Priority |
|---|---|---|---|
| FR-CM-01 | System shall allow customer self-registration via mobile number + OTP. | Explicit | M |
| FR-CM-02 | System shall allow staff to create a customer profile on behalf of a customer. | Inferred | M |
| FR-CM-03 | System shall maintain a unique Consumer Number per customer. | Explicit | M |
| FR-CM-04 | System shall capture and track KYC document status (Pending/Verified/Rejected/Expired). | Explicit | M |
| FR-CM-05 | System shall support multiple delivery addresses per customer. | Inferred | S |
| FR-CM-06 | System shall display a customer's real-time filled/empty cylinder balance. | Explicit | M |
| FR-CM-07 | System shall prevent hard deletion of customer records (soft-deactivate only). | Inferred | M |

## 2. Order Management (OM)
| ID | Requirement | Source | Priority |
|---|---|---|---|
| FR-OM-01 | System shall allow customers to book a refill via the Customer App. | Explicit | M |
| FR-OM-02 | System shall allow staff to create bookings on behalf of customers. | Inferred | M |
| FR-OM-03 | System shall track order status through New/Pending, Assigned, Delivered, Cancelled states. | Explicit | M |
| FR-OM-04 | System shall support a "Failed Delivery" outcome distinct from Cancelled. | Inferred | M |
| FR-OM-05 | System shall validate customer outstanding balance before confirming a new booking. | Inferred | M |
| FR-OM-06 | System shall validate customer cylinder holding cap before confirming a new booking (if configured). | Inferred | S |
| FR-OM-07 | System shall allow customers to track live order status. | Explicit | M |
| FR-OM-08 | System shall allow cancellation of Pending and Assigned orders with inventory de-allocation on cancel. | Explicit/Inferred | M |

## 3. Delivery Management (DM)
| ID | Requirement | Source | Priority |
|---|---|---|---|
| FR-DM-01 | System shall allow staff to plan delivery routes by grouping orders. | Explicit | M |
| FR-DM-02 | System shall allow assignment of a driver and vehicle to a route. | Explicit | M |
| FR-DM-03 | System shall validate vehicle stock sufficiency before allowing order assignment. | Inferred | S |
| FR-DM-04 | System shall record vehicle loading events (filled/empty quantities loaded). | Explicit | M |
| FR-DM-05 | Driver App shall display assigned deliveries with navigation to customer location. | Explicit | M |
| FR-DM-06 | System shall require OTP, signature, photo, and GPS capture to confirm delivery. | Explicit | M |
| FR-DM-07 | System shall automatically update vehicle inventory after each delivery. | Explicit | M |
| FR-DM-08 | Driver App shall support payment collection via Cash, UPI, and Card. | Explicit | M |
| FR-DM-09 | System shall support end-of-shift vehicle and cash reconciliation, mandatory daily even with multi-day vehicle stock carry-over. | Confirmed (D-16, D-31) | M |
| FR-DM-10 | Driver App shall be **offline-first**, with automatic synchronization and timestamp/optimistic-concurrency conflict resolution. | Confirmed (D-24) — **priority raised from Should-have to Must-have** | **M** |
| FR-DM-11 | System shall capture a defined reason code (Customer unavailable/Wrong address/Payment refused/Vehicle issue/Safety issue) for every Failed Delivery, with resolution action (Reschedule/Cancel/Return stock). | Confirmed (D-12) | M |

## 4. Inventory Management (IM)
| ID | Requirement | Source | Priority |
|---|---|---|---|
| FR-IM-01 | System shall track filled/empty cylinder stock at Warehouse, Vehicle, and Customer levels. | Explicit | M |
| FR-IM-02 | System shall maintain a complete, immutable transaction history for all inventory movements. | Explicit | M |
| FR-IM-03 | System shall prevent any inventory counter from going negative. | Inferred | M |
| FR-IM-04 | System shall support low-stock alerting at the Warehouse level. | Inferred | S |
| FR-IM-05 | System shall support inventory reconciliation with variance capture and mandatory-reason adjustments. | Explicit/Inferred | M |
| FR-IM-06 | System shall support a full 7-state cylinder status model (Filled/Empty/Damaged/Leakage/Quarantine/Scrap/Repair), tracked per cylinder type per location. | Confirmed (D-14) — **priority raised to Must-have** | **M** |
| FR-IM-07 | System shall support a manual GRN (Goods Receipt Note) process for receiving filled stock from the OMC in Phase 1. | Confirmed (D-15) | M |
| FR-IM-08 | System shall restrict inventory adjustment approval to Warehouse Manager/Staff or Agency Admin roles, with mandatory audit logging. | Confirmed (D-16) | M |

## 5. Accounting (AC)
| ID | Requirement | Source | Priority |
|---|---|---|---|
| FR-AC-01 | System shall generate a GST-compliant invoice upon order delivery. | Explicit | M |
| FR-AC-02 | System shall support online prepayment via integrated payment gateway. | Explicit | M |
| FR-AC-03 | System shall support COD payment recording (Cash/UPI/Card). | Explicit | M |
| FR-AC-04 | System shall maintain per-customer outstanding balance. | Explicit | M |
| FR-AC-05 | System shall support driver cash reconciliation and handover tracking. | Inferred | M |
| FR-AC-06 | System shall generate GST and general ledger reports. | Explicit | M |
| FR-AC-07 | System shall support invoice download/print by customers. | Explicit | M |
| FR-AC-08 | System shall support a refund/credit-note workflow: Customer Request → Manager Approval → Credit Note → Refund → Ledger Update. | Confirmed (D-17) — **priority raised to Must-have** | **M** |
| FR-AC-09 | System shall support partial payment and configurable per-customer credit limits. | Confirmed (D-11) | M |
| FR-AC-10 | System shall support a driver cash-shortfall workflow: Declaration → Investigation → Approval → Adjustment Entry → Audit Log. | Confirmed (D-18) | M |

## 6. Reporting (RP)
| ID | Requirement | Source | Priority |
|---|---|---|---|
| FR-RP-01 | System shall provide a Daily Sales report. | Explicit | M |
| FR-RP-02 | System shall provide a Cylinder Movement report. | Explicit | M |
| FR-RP-03 | System shall provide an Inventory Reconciliation report. | Explicit | M |
| FR-RP-04 | System shall provide a Driver Performance report. | Explicit | S |
| FR-RP-05 | System shall provide a Customer Consumption Analysis report. | Explicit | S |
| FR-RP-06 | System shall display real-time dashboard KPIs, role-scoped by user permission. | Explicit/Inferred | M |
| FR-RP-07 | System shall support export of reports to CSV/Excel/PDF. | Inferred | S |

## 7. Notifications (NT)
| ID | Requirement | Source | Priority |
|---|---|---|---|
| FR-NT-01 | System shall notify customers on booking confirmation, delivery, and payment events. | Inferred | M |
| FR-NT-02 | System shall support refill reminder notifications based on consumption pattern. | Inferred | S |
| FR-NT-03 | System shall alert staff on low warehouse stock and failed deliveries. | Inferred | S |
| FR-NT-04 | System shall log all sent notifications with delivery status. | Inferred | S |

## 8. Administration
| ID | Requirement | Source | Priority |
|---|---|---|---|
| FR-AD-01 | System shall support role-based access control (RBAC) for dashboard users, with the confirmed role set: Super Admin, Agency Admin, Manager, Warehouse Staff, Dispatcher, Accountant, Driver, Customer. | Explicit/Confirmed (D-38) | M |
| FR-AD-02 | System shall maintain an audit log of all data-mutating actions, financial transactions, inventory adjustments, login events, and administrative changes. | Confirmed (D-39) | M |
| FR-AD-03 | System administrator shall be able to create/deactivate staff accounts and assign roles. | Inferred | M |
| FR-AD-04 | System shall support a Super Admin role for tenant onboarding/configuration, above the tenant level. | Confirmed (D-01) | M |
| FR-AD-05 | Business-configuration values (GST rates, cylinder limits, cancellation policy, reminder intervals, credit limits) shall be stored per-tenant, not hardcoded. | Confirmed (D-42, BR-31) | M |

## 9. Complaint Management (CX) — New Module (D-20)
| ID | Requirement | Source | Priority |
|---|---|---|---|
| FR-CX-01 | System shall allow customers and staff to raise complaints, categorized and prioritized at creation. | Confirmed (D-20) | M |
| FR-CX-02 | System shall assign an SLA per category/priority and support escalation on breach. | Confirmed (D-20) | M |
| FR-CX-03 | System shall support complaint resolution recording and post-resolution customer satisfaction feedback. | Confirmed (D-20) | S |

See `modules/complaint-management.md` for full detail.

## 10. Multi-Tenancy & Multi-Branch (New Cross-Cutting Requirements, D-01/D-02)
| ID | Requirement | Source | Priority |
|---|---|---|---|
| FR-MT-01 | Every business entity shall carry a `tenantId`; no operation may cross tenant boundaries. | Confirmed (D-01, BR-30) | M |
| FR-MT-02 | System shall support multiple Branches, Warehouses, and Delivery Hubs per tenant. | Confirmed (D-02) | M |

## 11. Phase 2 Features (Still Deferred — Listed for Completeness, Not Phase 1 Requirements)
AI-based demand forecasting; route optimization; automatic QR/barcode cylinder-level scanning workflows (data model prepared in Phase 1 per D-36); predictive inventory planning; automated OMC/distributor system integrations (IOCL/BPCL/HPCL — manual GRN in Phase 1 per D-15); geo-fencing; eKYC; chatbot support; advanced BI dashboards; WhatsApp booking/notification channel; consolidated/periodic invoicing.
