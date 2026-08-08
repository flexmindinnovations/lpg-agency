# Business Domain Summary

## Purpose

This document provides a concise overview of the LPG Agency Management business domain.

It serves as the primary business context for developers and AI coding agents before reading the detailed specifications.

This document intentionally summarizes the business. It does **not** replace the detailed documentation located under:

- docs/business/
- docs/srs/
- docs/data/
- docs/architecture/

---

# Scope

This document explains:

- What business the platform supports
- Who uses the platform
- Major business capabilities
- Core business concepts
- Business terminology
- Business objectives
- High-level workflows

Detailed implementation, APIs, database schemas, UI designs, and engineering standards are documented elsewhere.

---

# Business Overview

The LPG Agency Management Platform digitizes the complete lifecycle of LPG cylinder distribution for one or more LPG distributors operating as independent tenants within a cloud-native SaaS platform.

The platform provides an end-to-end operational system that manages:

- Customer lifecycle
- LPG connections
- Cylinder bookings
- Order processing
- Delivery execution
- Warehouse inventory
- Vehicle inventory
- Customer cylinder ledger
- Financial transactions
- Accounting
- Complaint management
- Notifications
- Operational reporting
- Administration

The platform is designed to replace manual registers, spreadsheets, and disconnected desktop software with a centralized enterprise solution.

---

# Business Objectives

The primary business goals are:

- Digitize all agency operations
- Reduce manual work
- Improve inventory accuracy
- Improve delivery efficiency
- Maintain accurate customer cylinder balances
- Improve financial reconciliation
- Reduce operational costs
- Increase customer satisfaction
- Enable operational visibility through dashboards and reports
- Provide a scalable foundation for future AI-driven capabilities

---

# Business Capabilities

The platform provides the following core business capabilities:

### Customer Management

- Customer registration
- KYC management
- LPG connection management
- Address management
- Customer ledger
- Customer history

---

### Order Management

- Booking creation
- Order confirmation
- Order assignment
- Order tracking
- Order cancellation
- Rescheduling

---

### Delivery Management

- Driver assignment
- Route execution
- Proof of delivery
- OTP verification
- Signature capture
- Photo capture
- GPS tracking

---

### Inventory Management

- Warehouse inventory
- Vehicle inventory
- Customer-held cylinders
- Cylinder transfers
- Inventory reconciliation
- Stock adjustments

---

### Accounting

- Invoice generation
- Payment collection
- Credit management
- Outstanding balances
- GST calculation
- Cash reconciliation

---

### Reporting

- Operational reports
- Inventory reports
- Financial reports
- Driver performance
- Customer analytics
- Audit reports

---

### Administration

- User management
- Roles
- Permissions
- Tenant configuration
- Printing configuration
- Reference data management

---

# Primary Actors

## Customer

The customer is the recipient of LPG services.

Primary responsibilities:

- Register
- Authenticate
- Book cylinders
- Track deliveries
- View invoices
- View ledger
- Make payments
- Raise complaints

---

## Driver

Responsible for delivery execution.

Responsibilities:

- View assigned deliveries
- Navigate routes
- Deliver cylinders
- Collect empty cylinders
- Verify customer using OTP
- Capture signature
- Capture delivery photographs
- Collect payments

---

## Dispatcher

Coordinates deliveries.

Responsibilities:

- Assign drivers
- Schedule deliveries
- Track delivery progress
- Manage delivery queues

---

## Warehouse Staff

Responsible for warehouse operations.

Responsibilities:

- Receive stock
- Load vehicles
- Receive returned cylinders
- Perform inventory reconciliation
- Record adjustments

---

## Accountant

Responsible for financial operations.

Responsibilities:

- Generate invoices
- Record payments
- Manage customer balances
- Produce GST reports
- Perform financial reconciliation

---

## Manager

Responsible for operational oversight.

Responsibilities:

- Monitor KPIs
- Review reports
- Approve adjustments
- Supervise staff

---

## Agency Administrator

Responsible for tenant administration.

Responsibilities:

- User management
- Role management
- System configuration
- Security settings
- Tenant branding

---

## Super Administrator

Platform administrator.

Responsibilities:

- Tenant onboarding
- License management
- Global configuration
- Platform monitoring

---

# Business Glossary

## LPG Connection

A registered business relationship between a customer and an LPG agency authorizing LPG cylinder purchases.

---

## Booking

A customer request for one or more LPG cylinders.

A booking becomes an order after validation.

---

## Order

A confirmed booking progressing through fulfillment.

---

## Delivery

The process of supplying filled cylinders to a customer while collecting empty cylinders when applicable.

---

## Filled Cylinder

A cylinder available for customer delivery.

---

## Empty Cylinder

A cylinder returned by a customer awaiting refill.

---

## Exchange

Replacement of one empty cylinder with one filled cylinder.

---

## Customer Cylinder Ledger

The running record of cylinders currently held by a customer.

---

## Inventory Ledger

The historical record of every inventory movement.

---

## Warehouse Inventory

Current stock physically available in the warehouse.

---

## Vehicle Inventory

Current stock assigned to a delivery vehicle.

---

## Proof of Delivery (POD)

Evidence confirming successful delivery.

Examples:

- OTP verification
- Customer signature
- Delivery photograph
- GPS location

---

## Tenant

An independent LPG distributor using the platform.

Every tenant owns:

- Customers
- Inventory
- Users
- Financial records
- Reports
- Configuration

No tenant can access another tenant's data.

---

# Business Success Metrics

The platform should continuously improve:

Operational KPIs

- Booking processing time
- Delivery completion rate
- Inventory accuracy
- Driver productivity
- Order fulfillment rate

Financial KPIs

- Outstanding collections
- Payment reconciliation accuracy
- Invoice generation time

Customer KPIs

- Complaint resolution time
- Customer satisfaction
- Repeat booking rate

Platform KPIs

- System availability
- API response times
- Audit completeness
- Tenant isolation compliance

## Core Business Principles

The following principles define the operational foundation of the LPG Agency Management Platform.

These principles should never be violated by application logic.

---

### Inventory Accuracy

The system must always know the exact quantity of:

- Filled cylinders in warehouse
- Empty cylinders in warehouse
- Filled cylinders in vehicles
- Empty cylinders in vehicles
- Filled cylinders with customers
- Empty cylinders returned by customers

Inventory must always reconcile.

Negative inventory is never allowed.

---

### Customer Cylinder Ledger Accuracy

Every customer has an individual cylinder ledger.

Every cylinder movement must update the ledger.

Examples:

- Delivery
- Return
- Exchange
- Purchase
- Adjustment

The ledger must always remain auditable.

---

### Financial Accuracy

The financial subsystem must always maintain consistency between:

- Invoices
- Payments
- Outstanding balances
- Credit notes
- GST calculations
- Cash collections

Financial records should never become inconsistent.

---

### Auditability

Every critical business transaction must be traceable.

Examples include:

- Customer changes
- Inventory adjustments
- Payments
- Invoice modifications
- User management
- Configuration changes
- Permission changes

Audit history should never be deleted.

---

### Tenant Isolation

Every business object belongs to exactly one tenant.

Examples:

- Customer
- Booking
- Inventory
- Invoice
- Payment
- User

Cross-tenant data access is prohibited.

---

## Business Invariants

The following rules must always remain true.

- Inventory cannot become negative.
- Every booking belongs to exactly one customer.
- Every order belongs to one booking.
- Every delivery belongs to one order.
- Every invoice belongs to one tenant.
- Every payment references a valid invoice or outstanding balance.
- Every inventory movement creates an audit record.
- Every cylinder movement updates the customer ledger.
- Every authenticated user belongs to one tenant.
- Every API request executes within a tenant context.
- Deleted business records use soft delete unless regulatory requirements demand permanent deletion.

---

# Core Modules

The application is organized into the following business modules.

### Identity & Access

Responsibilities

- Authentication
- Authorization
- Roles
- Permissions
- User Management
- Session Management

---

### Customer Management

Responsibilities

- Customer Registration
- KYC
- LPG Connections
- Addresses
- Customer Ledger
- Customer History

---

### Order Management

Responsibilities

- Booking
- Order Processing
- Assignment
- Scheduling
- Cancellation
- Status Tracking

---

### Delivery Management

Responsibilities

- Driver Assignment
- Route Execution
- Proof of Delivery
- OTP Verification
- Signature Capture
- Photo Capture
- GPS Tracking

---

### Inventory Management

Responsibilities

- Warehouse Inventory
- Vehicle Inventory
- Cylinder Transfers
- Reconciliation
- Stock Adjustments

---

### Cylinder Ledger

Responsibilities

- Track customer cylinder ownership
- Record cylinder transactions
- Maintain historical movement

---

### Accounting & Billing

Responsibilities

- Invoices
- Payments
- Outstanding Balances
- Credit Notes
- GST
- Cash Reconciliation

---

### Complaint Management

Responsibilities

- Complaint Registration
- Assignment
- SLA Tracking
- Resolution
- Customer Feedback

---

### Notifications

Responsibilities

- SMS
- Email
- Push Notifications
- Future WhatsApp Integration

---

### Reporting & Analytics

Responsibilities

- Operational Reports
- Financial Reports
- Inventory Reports
- Customer Reports
- Driver Reports
- Audit Reports
- KPI Dashboards

---

### Administration

Responsibilities

- Tenant Configuration
- Printing Configuration
- Reference Data
- Themes
- Feature Flags

---

# High-Level Business Workflow

```
Customer Registration
        │
        ▼
LPG Connection Verification
        │
        ▼
Cylinder Booking
        │
        ▼
Order Creation
        │
        ▼
Inventory Allocation
        │
        ▼
Driver Assignment
        │
        ▼
Vehicle Loading
        │
        ▼
Delivery Execution
        │
        ▼
OTP / Signature / Photo Verification
        │
        ▼
Payment Collection
        │
        ▼
Invoice Generation
        │
        ▼
Inventory Update
        │
        ▼
Customer Ledger Update
        │
        ▼
Financial Reconciliation
        │
        ▼
Operational Reporting
```

---

# Business Lifecycle Overview

## Customer Lifecycle

```
Prospective Customer
        │
        ▼
Registered
        │
        ▼
KYC Verified
        │
        ▼
Active
        │
        ▼
Suspended
        │
        ▼
Closed
```

---

## Order Lifecycle

```
Booking Created
        │
        ▼
Confirmed
        │
        ▼
Inventory Allocated
        │
        ▼
Driver Assigned
        │
        ▼
Loaded
        │
        ▼
Out For Delivery
        │
        ▼
Delivered
        │
        ▼
Completed
```

---

## Delivery Lifecycle

```
Assigned
        │
        ▼
Accepted
        │
        ▼
Loaded
        │
        ▼
In Transit
        │
        ▼
Delivered
        │
        ▼
Verified
        │
        ▼
Closed
```

---

## Payment Lifecycle

```
Pending
        │
        ▼
Collected
        │
        ▼
Verified
        │
        ▼
Reconciled
        │
        ▼
Closed
```

---

# Major Business Entities

Core business entities include:

- Tenant
- Branch
- Warehouse
- Customer
- LPG Connection
- Address
- Booking
- Order
- Delivery
- Driver
- Vehicle
- Cylinder Type
- Inventory
- Inventory Transaction
- Customer Cylinder Ledger
- Invoice
- Payment
- Complaint
- Notification
- User
- Role
- Permission
- Audit Log

Refer to the Data Architecture documentation for detailed relationships.

---

# Operational Constraints

Business operations must respect the following constraints:

- Drivers can only access assigned deliveries.
- Inventory adjustments require authorization.
- Payments cannot exceed outstanding balances.
- Suspended customers cannot create bookings.
- Customer cylinder limits must be enforced.
- Vehicle inventory cannot exceed vehicle capacity.
- Financial periods may be locked after reconciliation.
- Tenant administrators cannot access platform-level settings.

---

# External Integrations

Current integrations include:

- Payment Gateway
- SMS Provider
- Email Provider
- Push Notification Service

Future integrations include:

- WhatsApp Business API
- IOCL
- BPCL
- HPCL
- Barcode Scanners
- QR Code Scanners
- ERP Systems
- Accounting Software
- GPS Services

---

# Future Business Capabilities

Planned roadmap:

- AI Demand Forecasting
- Delivery Route Optimization
- Predictive Inventory Planning
- Customer Consumption Analytics
- QR / Barcode Cylinder Tracking
- IoT-enabled Cylinder Monitoring
- Government LPG System Integration
- AI-powered Business Insights

---

# AI Implementation Workflow

Before implementing any feature:

1. Read this document.
2. Read the relevant knowledge summaries.
3. Read the corresponding detailed documentation in `docs/`.
4. Review the architecture and ADRs if architectural decisions are involved.
5. Inspect existing implementation before writing new code.
6. Reuse existing components and services whenever possible.
7. Follow Engineering Standards and Design Tokens.
8. Implement only the requested feature.
9. Write or update automated tests.
10. Update documentation if business behavior changes.

Never:

- Invent business rules.
- Duplicate business logic.
- Violate tenant isolation.
- Bypass authorization.
- Ignore accessibility requirements.
- Ignore audit logging.
- Ignore error handling.
- Introduce unnecessary technical debt.

---

# Related Documentation

For additional details, refer to:

- `docs/business/`
- `docs/srs/`
- `docs/architecture/`
- `docs/data/`
- `docs/ui/`
- `docs/engineering/`