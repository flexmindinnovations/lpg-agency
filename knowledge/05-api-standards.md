# API Summary

## Purpose

This document provides a high-level summary of the API architecture and standards used throughout the LPG Agency Management Platform.

It is intended for developers and AI coding agents before reading the detailed OpenAPI specifications.

For detailed API contracts refer to:

- docs/data/ (API design guidelines, contracts, OpenAPI, security, error catalog)
- docs/architecture/07-api-architecture.md
- docs/data/

---

# API Philosophy

The platform follows an API-First approach, implemented as **code-first generation with contract-first consumption** (ADR-026):

1. Pydantic v2 models and FastAPI route metadata are the **single source of truth**. No hand-maintained YAML.
2. FastAPI generates the OpenAPI 3.1 spec; it is **exported and committed** to `backend/openapi/openapi.json`.
3. Clients (Angular, both Flutter apps) generate typed clients **from that committed artifact** — never from a running server, never hand-written.
4. A CI check fails the build if the committed spec differs from the freshly generated one, so the contract cannot silently drift from the implementation.
5. A change to the committed spec is a **contract change** — visible in the diff, reviewed as such, subject to the versioning rules below.

"API-first" is therefore true where it matters: no client is written against an unspecified API, and the spec is reviewed before clients consume it. It simply is not hand-authored.

> **Clarified in Phase 0 (2026-08-09).** This file and `AGENTS.md` said "OpenAPI First" while `docs/data/12-openapi-specification.md` said "code-first, not spec-first". Both are correct under the workflow above; the reconciliation had never been written down (ADR-026).

All client applications communicate exclusively through REST APIs.

The API serves as the single integration point for:

- Agency Dashboard
- Customer Mobile App
- Driver Mobile App
- Future Integrations
- Third-party Systems

The API contract is considered part of the public interface and must remain stable.

---

# API Design Principles

Every API should be:

- RESTful
- Resource-Oriented
- Stateless
- Predictable
- Consistent
- Secure
- Versioned
- Documented
- Backward Compatible where practical

Every endpoint should represent a business capability.

---

# API Consumers

The platform exposes APIs for:

## Agency Dashboard

Angular 22

Examples

- Customer Management
- Inventory
- Reports
- Administration

---

## Customer Mobile App

Flutter

Examples

- Registration
- Booking
- Payments
- Complaints

---

## Driver Mobile App

Flutter

Examples

- Deliveries
- Vehicle Inventory
- OTP Verification
- Proof of Delivery

---

## External Systems

Future integrations include:

- Payment Gateway
- SMS Provider
- Email Provider
- WhatsApp
- Government LPG Systems
- ERP Systems

---

# API Architecture

```

Client

↓

HTTPS

↓

Authentication

↓

Authorization

↓

Validation

↓

Application Service

↓

Domain

↓

Repository

↓

Database

↓

Response

```

Business logic never belongs in API endpoints.

---

# API Standards

Use:

- REST
- HTTPS
- JSON
- UTF-8
- OpenAPI 3.1

Every endpoint should be documented.

---

# URL Convention

Examples

/api/v1/customers

/api/v1/bookings

/api/v1/orders

/api/v1/deliveries

/api/v1/inventory

/api/v1/payments

/api/v1/reports

Resources should use plural nouns.

---

# HTTP Methods

GET

Read data

POST

Create resources

PUT

Replace entire resource

PATCH

Partial update

DELETE

Soft delete where applicable

Never misuse HTTP methods.

---

# Request Standards

Every request should include:

Authentication

Content-Type

Tenant Context

Correlation ID (when applicable)

Validation

Requests should be strongly typed.

---

# Response Standards

Every response should be:

Consistent

Typed

Documented

JSON field naming is `snake_case` throughout — Pydantic v2's natural serialization, with no case translation anywhere in the stack.

**Success**

The resource is returned directly. There is **no `{"success": true, "data": …}` envelope** — the HTTP status already conveys success, and unwrapping a redundant envelope in three clients is pure ceremony.

```json
{
  "id": "3f2a9c1e-...",
  "customer_type": "domestic",
  "full_name": "...",
  "created_at": "2026-08-09T10:15:00Z"
}
```

**Failure — RFC 7807 Problem Details**

All errors use RFC 7807 Problem Details with `Content-Type: application/problem+json`, extended with a stable machine-readable `error_code` (ADR-021). The authoritative catalogue of codes is `docs/data/18-error-catalog.md`.

```json
{
  "type": "https://api.lpgplatform.com/errors/customer-not-found",
  "title": "Customer not found",
  "status": 404,
  "error_code": "CUSTOMER_NOT_FOUND",
  "detail": "No customer exists with the supplied identifier.",
  "instance": "/api/v1/customers/3f2a9c1e-...",
  "trace_id": "00-4bf9...-..."
}
```

Field-level validation failures use the Problem Details `errors` extension, populated from Pydantic v2 validation output.

> **Corrected in Phase 0 (2026-08-09).** This file previously specified a `{success, error}` envelope, contradicting `knowledge/09-engineering-standards.md`, `docs/data/10-api-design-guidelines.md` §12, `docs/data/18-error-catalog.md`, and `docs/implementation/engineering-standards.md`, all of which specify RFC 7807. Resolved in favour of RFC 7807 (ADR-021).

---

# Authentication

The platform uses:

- JWT Access Token
- Refresh Token

Future support:

- OAuth2
- Azure AD
- Multi-factor Authentication

All secured endpoints require authentication.

---

# Real-Time

REST is not the only channel. Live updates are delivered over **FastAPI WebSockets with a Redis Pub/Sub backplane** (ADR-015, `docs/architecture/16-realtime-architecture.md`), covering order status, delivery status, driver assignment, dispatcher operations, and dashboard metrics.

WebSocket subscriptions are authorized against the **same RBAC permissions** as the equivalent REST endpoint, and channels are tenant-namespaced server-side from the verified JWT claim — a client never names a channel.

Real-time is an **enhancement, never the source of truth**. Every client can reconstruct correct state from the REST API, and must do so on connect and reconnect.

---

# Authorization

Authorization is Role-Based.

Examples

- Super Admin
- Agency Admin
- Manager
- Dispatcher
- Warehouse Staff
- Accountant
- Driver
- Customer

Permissions are enforced at the API layer.

---

# Validation

Validation occurs at multiple levels.

- Client
- API
- Business Rules
- Database

Never rely only on client validation.

---

# Error Handling

The platform uses RFC 7807 Problem Details for every error response (see Response Standards above).

Categories include:

- Validation Errors
- Business Errors
- Authentication Errors
- Authorization Errors
- Resource Not Found
- Conflict Errors
- Infrastructure Errors

Never expose internal implementation details.

---

# Pagination

Collections should support pagination.

Recommended parameters

page

pageSize

Responses should include:

- Total Count
- Current Page
- Page Size
- Total Pages

Avoid returning excessively large datasets.

---

# Filtering

Collections should support filtering.

Examples

Customer Name

Status

Date Range

Payment Status

Driver

Vehicle

Filtering should remain consistent across modules.

---

# Sorting

Support sorting on appropriate fields.

Examples

Name

Created Date

Updated Date

Status

Sorting should be deterministic.

---

# Searching

Support keyword search where applicable.

Examples

Customer

Booking

Invoice

Complaint

Search should be server-side.

---

# API Versioning

Use URL-based versioning.

Example

/api/v1/

Breaking changes require a new version.

Avoid unnecessary version proliferation.

---

# Idempotency

Operations such as payment processing and order creation should support idempotency where appropriate.

Clients may send an Idempotency-Key for retry-safe operations.

---

# Concurrency

Use optimistic concurrency where applicable.

Detect conflicting updates before overwriting data.

---

# Rate Limiting

Protect APIs from abuse.

Examples

Authentication

OTP

Payments

Public APIs

Administrative APIs

Rate limits should be configurable.

---

# File Uploads

Support uploads for:

- KYC Documents
- Customer Photos
- Proof of Delivery
- Driver Signatures
- Reports

Validate:

- File Type
- File Size
- Virus Scanning (future)

---

# Printing APIs

Support generation of:

- Invoice
- Delivery Receipt
- Payment Receipt
- Customer Ledger
- Inventory Reports
- Driver Reports

Output formats include:

- PDF
- Thermal Printer
- A4
- Barcode
- QR Code

---

# API Security

Every endpoint should:

- Validate authentication
- Validate authorization
- Validate tenant ownership
- Validate input
- Log important actions
- Protect sensitive information

Security is mandatory.

---

# OpenAPI

Every endpoint must include:

- Summary
- Description
- Request Model
- Response Model
- Error Responses
- Authentication
- Examples

OpenAPI documentation should always remain synchronized with implementation.

---

# API Lifecycle

Every new API follows:

Business Requirement

↓

Design

↓

OpenAPI Contract

↓

Implementation

↓

Testing

↓

Documentation

↓

Release

Contract changes should be reviewed before implementation.

---

# AI Development Guidelines

Before implementing an API:

1. Read the relevant business documentation.
2. Review API contracts.
3. Validate business rules.
4. Reuse existing patterns.
5. Follow response standards.
6. Add OpenAPI documentation.
7. Write tests.

Never:

- Expose database models.
- Return inconsistent responses.
- Skip validation.
- Break API compatibility.
- Ignore authorization.
- Duplicate endpoints.

---

# Related Documentation

Refer to:

- docs/data/ (API design guidelines, contracts, OpenAPI, security, error catalog)
- docs/architecture/07-api-architecture.md
- docs/data/
- docs/engineering/
- docs/business/