# Feature Map

## Purpose

This document provides a high-level map of every business feature within the LPG Agency Management Platform.

It helps developers and AI coding agents understand:

- What features exist
- Module ownership
- Feature dependencies
- Implementation sequence
- Business priority

For detailed requirements, refer to the documentation under:

- docs/business/
- docs/srs/
- docs/data/
- docs/ui/

---

# Feature Hierarchy

The platform consists of the following business domains.

```
Platform
│
├── Identity & Access
├── Customer Management
├── Order Management
├── Delivery Management
├── Inventory Management
├── Cylinder Ledger
├── Accounting & Billing
├── Complaint Management
├── Notifications
├── Reporting & Analytics
├── Administration
└── Platform Services
```

---

# Feature Dependencies

```
Identity
    │
    ▼
Administration
    │
    ▼
Customer Management
    │
    ▼
Inventory
    │
    ▼
Orders
    │
    ▼
Delivery
    │
    ▼
Accounting
    │
    ▼
Reports
```

Identity is required by every module.

Inventory is a dependency for Orders and Delivery.

Accounting depends on Orders and Payments.

Reports depend on all operational modules.

---

# Identity & Access

Purpose

Authentication and authorization.

Major Features

- Login
- Logout
- Refresh Token
- Forgot Password
- Reset Password
- User Management
- Role Management
- Permission Management
- Session Management
- Tenant Management

Dependencies

None

Priority

Critical

---

# Customer Management

Purpose

Manage customers and LPG connections.

Major Features

- Customer Registration
- Customer Search
- Customer Details
- Customer Ledger
- Address Management
- KYC
- Connection Management
- Customer History

Dependencies

Identity

Priority

Critical

---

# Inventory Management

Purpose

Track all cylinder inventory.

Major Features

- Warehouse Inventory
- Vehicle Inventory
- Cylinder Transfers
- Stock Adjustment
- Stock Reconciliation
- Stock Audit
- Inventory History

Dependencies

Identity

Priority

Critical

---

# Order Management

Purpose

Manage LPG bookings.

Major Features

- Booking
- Order Creation
- Order Assignment
- Order Status
- Cancellation
- Rescheduling
- Order Tracking

Dependencies

Customer

Inventory

Priority

Critical

---

# Delivery Management

Purpose

Manage delivery operations.

Major Features

- Driver Assignment
- Vehicle Loading
- Route
- Delivery Execution
- Proof of Delivery
- OTP Verification
- Signature
- Photo
- GPS

Dependencies

Orders

Inventory

Priority

Critical

---

# Cylinder Ledger

Purpose

Track customer cylinder ownership.

Major Features

- Ledger Transactions
- Exchange History
- Purchase History
- Adjustments
- Customer Balance

Dependencies

Customer

Inventory

Delivery

Priority

Critical

---

# Accounting & Billing

Purpose

Manage financial operations.

Major Features

- Invoice Generation
- Payment Collection
- Outstanding Balance
- Credit Notes
- GST
- Cash Collection
- Reconciliation

Dependencies

Orders

Delivery

Customer

Priority

Critical

---

# Complaint Management

Purpose

Handle customer complaints.

Major Features

- Complaint Registration
- Assignment
- Escalation
- SLA Tracking
- Resolution
- Customer Feedback

Dependencies

Customer

Priority

Medium

---

# Notifications

Purpose

Send customer and staff notifications.

Major Features

- SMS
- Email
- Push Notification
- Reminder Scheduling
- Delivery Updates
- Payment Notifications

Dependencies

Identity

Orders

Delivery

Priority

Medium

---

# Reporting & Analytics

Purpose

Generate operational and financial reports.

Major Features

- Dashboard KPIs
- Financial Reports
- Inventory Reports
- Driver Reports
- Customer Reports
- Audit Reports
- Export

Dependencies

All Modules

Priority

Medium

---

# Administration

Purpose

Manage application configuration.

Major Features

- User Management
- Tenant Configuration
- Master Data
- Printing Configuration
- Themes
- Feature Flags
- Audit Logs

Dependencies

Identity

Priority

High

---

# Platform Services

Shared services used across all modules.

Includes

- Authentication
- Authorization
- Audit Logging
- Printing
- Notifications
- File Storage
- Search
- Caching
- Configuration
- Background Jobs
- Scheduler

---

# Cross-Module Dependencies

| Module | Depends On |
|----------|------------|
| Customer | Identity |
| Inventory | Identity |
| Orders | Customer, Inventory |
| Delivery | Orders, Inventory |
| Ledger | Customer, Delivery |
| Accounting | Orders, Delivery |
| Reports | All Modules |
| Notifications | Identity, Orders |
| Administration | Identity |

---

# Recommended Development Order

Phase 1

- Identity & Access
- Shared Infrastructure

Phase 2

- Customer Management

Phase 3

- Inventory Management

Phase 4

- Order Management

Phase 5

- Delivery Management

Phase 6

- Cylinder Ledger

Phase 7

- Accounting

Phase 8

- Notifications

Phase 9

- Reporting

Phase 10

- Administration

Phase 11

- AI Features

---

# Future Enhancements

Planned capabilities include:

- AI Demand Forecasting
- Route Optimization
- WhatsApp Booking
- QR / Barcode Tracking
- IoT Integration
- Customer Consumption Analytics
- Predictive Inventory Planning

---

# AI Implementation Guidance

When implementing a feature:

1. Read the relevant business documentation.
2. Review feature dependencies.
3. Verify required modules are already implemented.
4. Reuse existing services.
5. Follow architecture and engineering standards.
6. Write tests.
7. Update documentation if required.

Never implement a dependent feature before its prerequisite modules are complete.

---

# Related Documentation

Refer to:

- docs/business/
- docs/srs/
- docs/architecture/
- docs/data/
- docs/ui/
- docs/engineering/