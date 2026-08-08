# Data Summary

## Purpose

This document provides a concise overview of the data architecture for the LPG Agency Management Platform.

It helps developers and AI coding agents understand:

- Core business entities
- Domain ownership
- Aggregate boundaries
- Entity relationships
- Data lifecycle
- Business invariants
- Audit strategy
- Multi-tenancy
- Persistence principles

For detailed information refer to:

- docs/data/
- docs/architecture/
- docs/data/ (API design guidelines, contracts, OpenAPI, security, error catalog)

---

# Data Architecture Philosophy

The platform follows Domain Driven Design (DDD).

Data is organized around business domains rather than database tables.

Each bounded context owns its own entities and business rules.

Principles:

- Single Source of Truth
- Aggregate Consistency
- Strong Referential Integrity
- Tenant Isolation
- Auditable Transactions
- Soft Delete by Default

---

# Aggregate Overview

The primary aggregates are:

- Tenant
- Customer
- Booking
- Order
- Delivery
- Inventory
- Vehicle
- Invoice
- Payment
- Complaint
- User

Each aggregate has exactly one Aggregate Root.

External modules interact only through Aggregate Roots.

---

# Core Business Entities

## Tenant

Owns all business data.

Examples:

- Users
- Customers
- Inventory
- Orders
- Payments
- Reports

Every entity belongs to exactly one tenant.

---

## Customer

Represents an LPG consumer.

Owns:

- LPG Connection
- Addresses
- Cylinder Ledger
- Booking History
- Payment History
- Complaint History

---

## Booking

Represents a customer request.

Creates:

- Order
- Inventory Reservation
- Delivery Schedule

---

## Order

Represents a confirmed business transaction.

Tracks:

- Status
- Assigned Driver
- Delivery
- Invoice
- Payment

---

## Delivery

Represents physical fulfillment.

Includes:

- Driver
- Vehicle
- Route
- OTP
- Signature
- Photos
- GPS

---

## Inventory

Represents cylinder stock.

Inventory exists at:

- Warehouse
- Vehicle
- Customer

Inventory is maintained separately for each cylinder type.

---

## Cylinder Ledger

Represents customer cylinder ownership.

Records:

- Delivery
- Return
- Exchange
- Purchase
- Adjustment

Every cylinder movement updates the ledger.

---

## Invoice

Represents billing.

Includes:

- Items
- Taxes
- Discounts
- Total
- Payment Status

---

## Payment

Represents customer payment.

Supports:

- Cash
- UPI
- Card
- Online

Payments reconcile with invoices.

---

## Complaint

Tracks customer issues.

Includes:

- Category
- Priority
- Status
- SLA
- Resolution

---

# Entity Relationships

High-level relationships:

```

Tenant
│
├── Customers
│ ├── Addresses
│ ├── Cylinder Ledger
│ ├── Bookings
│ ├── Payments
│ └── Complaints
│
├── Orders
│ ├── Deliveries
│ ├── Invoices
│ └── Payments
│
├── Inventory
│ ├── Warehouse
│ ├── Vehicle
│ └── Customer
│
└── Users

```

---

# Data Ownership

Each module owns its data.

| Module | Owns |
|----------|------|
| Identity | Users, Roles, Permissions |
| Customer | Customer, Address, LPG Connection |
| Orders | Booking, Order |
| Delivery | Delivery, Route |
| Inventory | Inventory, Stock Movement |
| Accounting | Invoice, Payment |
| Complaint | Complaint |
| Reporting | Read Models |

Other modules should access data through services or APIs, not direct database access.

---

# Data Lifecycle

Typical lifecycle:

Customer

↓

Booking

↓

Order

↓

Inventory Allocation

↓

Delivery

↓

Invoice

↓

Payment

↓

Ledger Update

↓

Reporting

All changes are recorded in audit logs.

---

# Business Invariants

The following rules must always remain true.

- Every entity belongs to one tenant.
- Inventory cannot become negative.
- Customer ledger must remain balanced.
- Every order belongs to one booking.
- Every delivery belongs to one order.
- Every payment references an invoice or outstanding balance.
- Every inventory movement creates an audit record.
- Financial records are immutable after reconciliation.
- Deleted records are soft deleted unless regulations require otherwise.

---

# Multi-Tenant Strategy

The platform uses a shared database.

Rules:

- Every business table contains TenantId.
- Queries are tenant-filtered.
- Cross-tenant access is prohibited.
- Tenant configuration is isolated.

Tenant isolation is mandatory.

---

# Audit Strategy

Every critical operation creates an audit record.

Audit includes:

- User
- Timestamp
- Tenant
- Entity
- Action
- Before State
- After State

Audit records are immutable.

---

# Soft Delete Strategy

Business entities use soft delete where appropriate.

Deleted records:

- Remain available for auditing.
- Are excluded from normal queries.
- Preserve referential integrity.

Reference data may use hard delete only when safe.

---

# Data Validation Principles

Validation occurs at multiple levels:

- Client Validation
- API Validation
- Business Rule Validation
- Database Constraints

Business rules should never rely solely on UI validation.

---

# Database Principles

The application uses PostgreSQL.

Guidelines:

- UUID primary keys
- Foreign key constraints
- Optimized indexes
- Transactions for business operations
- Migrations via Alembic
- JSONB only where appropriate
- Normalized schema for transactional data

---

# Data Security

Sensitive information must be protected.

Examples:

- Passwords
- OTPs
- Tokens
- Personally Identifiable Information (PII)

Never expose internal database models through APIs.

Always use DTOs.

---

# AI Development Guidelines

Before modifying the data model:

1. Read the relevant business documentation.
2. Review aggregate ownership.
3. Verify business invariants.
4. Preserve tenant isolation.
5. Update migrations.
6. Update API contracts if required.
7. Update documentation.

Never:

- Bypass repositories.
- Break aggregate boundaries.
- Duplicate data ownership.
- Modify unrelated entities.
- Remove audit fields.

---

# Related Documentation

Refer to:

- docs/data/
- docs/architecture/
- docs/data/ (API design guidelines, contracts, OpenAPI, security, error catalog)
- docs/business/