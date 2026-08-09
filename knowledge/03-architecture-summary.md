# Architecture Summary

## Purpose

This document provides a high-level architectural overview of the LPG Agency Management Platform.

It is intended for developers and AI coding agents to quickly understand the system architecture before reading the detailed architecture documents.

For detailed information refer to:

- docs/architecture/
- docs/adr/
- docs/data/
- docs/engineering/

---

# Scope

This document summarizes:

- Architectural vision
- Architectural principles
- System structure
- Application boundaries
- Layer responsibilities
- Domain boundaries
- Data flow
- Request flow
- Multi-tenancy
- Security
- Scalability
- Cross-cutting concerns

It does not replace the detailed architecture documentation.

---

# Architecture Vision

The LPG Agency Management Platform is designed as a modern, cloud-native, enterprise SaaS application capable of serving multiple LPG distributors through a single deployable platform.

The architecture prioritizes:

- Simplicity
- Maintainability
- Scalability
- Security
- Performance
- Testability
- Accessibility
- AI-assisted development

The system should remain maintainable for at least the next ten years.

---

# Architecture Principles

The platform follows these architectural principles:

- Clean Architecture
- Domain Driven Design (DDD)
- SOLID Principles
- Feature-Based Organization
- API First
- Multi-Tenant SaaS
- Modular Monolith (initially)
- Event-Driven Communication (where appropriate)
- Cloud-Native Design
- OpenAPI First
- Security by Design
- Accessibility by Design
- Design Token Driven UI

---

# High-Level Architecture

```
                   Customers
                       │
                       ▼
              Customer Mobile App
                   (Flutter)
                       │
                       ▼
        REST / HTTPS  +  WebSocket
                       ▲
                       │
Agency Dashboard ◄──── FastAPI ────► Driver Mobile App
 (Angular 22 / Nx)      │             (Flutter)
                        │
                Application Layer
                        │
                  Domain Layer
                        │
              Infrastructure Layer
                        │
           PostgreSQL + Redis + Storage
                        │
              Background Worker (same codebase)
```

The backend acts as the single source of truth for all business operations.

**Code location:** backend in `backend/`, Angular in `frontend/` (Nx workspace), Flutter apps in `mobile/`. See `docs/architecture/14-folder-structure.md`.

> **Phase 0 note (2026-08-09).** An earlier ASP.NET Core / EF Core / MediatR / Azure SQL / SignalR architecture was superseded; the documents are preserved under `docs/architecture/superseded/`. See ADR-012 … ADR-026.

---

# Applications

## Agency Dashboard

Technology

- Angular 22 in an Nx workspace at `frontend/`
- TypeScript (strict)
- Angular Signals, with NgRx SignalStore for justified shared state
- Angular Material + Angular CDK
- Tailwind CSS v4 (design-token driven)
- PrimeNG as the primary UI component library; AG Grid Community (Enterprise optional per feature) behind an application-level wrapper (ADR-028)

Purpose

Operational management of the LPG agency.

---

## Customer Mobile Application

Technology

Flutter

Purpose

Customer self-service.

---

## Driver Mobile Application

Technology

Flutter

Purpose

Delivery execution.

---

## Backend Platform

Technology

Python FastAPI

Purpose

Business rules, APIs, integrations, authentication, reporting and printing.

---

# Architectural Layers

The backend follows Clean Architecture.

## Presentation Layer

Responsibilities

- REST APIs
- Authentication
- Validation
- Request mapping
- Response formatting

Business logic is never implemented here.

---

## Application Layer

Responsibilities

- Use Cases
- Commands
- Queries
- Application Services
- Ports (Protocols) that Infrastructure implements
- Transaction orchestration via Unit of Work

Coordinates business operations. CQRS is an in-process pattern implemented with **explicit application services** — there is no mediator library (ADR-014). Cross-cutting concerns are delivered by FastAPI dependencies and the Unit of Work, not by a dispatch pipeline:

| Concern | Mechanism |
|---|---|
| Validation | Pydantic v2 models + domain invariants inside aggregates |
| Tenant scoping | Request-scoped dependency + `SET LOCAL app.current_tenant_id` + PostgreSQL RLS |
| Audit logging | SQLAlchemy session hooks, written in the Unit of Work commit path |
| Transaction | Unit of Work as a request-scoped async context manager |
| Performance | ASGI timing middleware + per-use-case timing |

---

## Domain Layer

Responsibilities

- Business Rules
- Aggregates
- Entities
- Value Objects
- Domain Services
- Domain Events

The Domain Layer is independent of frameworks.

---

## Infrastructure Layer

Responsibilities

- Database
- Redis
- File Storage
- Notifications
- Email
- SMS
- External APIs
- Printing

Provides implementations for interfaces defined by the Domain and Application layers.

---

# Bounded Contexts

The platform is divided into the following business contexts:

- Identity & Access
- Customer Management
- Order Management
- Delivery Management
- Inventory Management
- Cylinder Ledger
- Accounting & Billing
- Complaint Management
- Notifications
- Reporting & Analytics
- Administration

Each context owns its business rules and data.

---

# Request Flow

Every request follows the same lifecycle.

```
Client

↓

API Endpoint

↓

Validation

↓

Authentication

↓

Authorization

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

Business logic should never exist in controllers or repositories.

---

# Data Flow

The backend is the single source of truth.

```
Client

↓

REST API

↓

Application Layer

↓

Domain

↓

Repository

↓

PostgreSQL

↓

Redis Cache (optional)

↓

Response
```

Every state-changing operation updates the appropriate audit records.

---

# Authentication & Authorization

Authentication

- JWT Access Token
- Refresh Token
- Secure Password Storage
- OTP (where applicable)

Authorization

- Role-Based Access Control (RBAC)
- Permission-based authorization
- Tenant-aware access control

Every request executes within an authenticated tenant context.

---

# Multi-Tenancy

The platform is designed as a shared application supporting multiple LPG agencies.

Principles

- Every business record belongs to one tenant.
- Tenant isolation is mandatory.
- Shared infrastructure.
- Shared application.
- Shared database with tenant isolation.
- Cross-tenant access is prohibited.

**How it is enforced — four layers, in this order (ADR-017):**

1. **PostgreSQL Row-Level Security** policy on every tenant-scoped table — the backstop that holds even when application code is wrong.
2. `SET LOCAL app.current_tenant_id` issued at the start of every request transaction, from the verified JWT claim.
3. Repository scoping — the session factory yields no session without a tenant context.
4. CI: boundary tests plus cross-tenant integration tests that must return nothing.

Layer 1 is what makes this defense in *depth* rather than defense in repetition — it protects raw SQL, reporting queries, and future BI connections automatically. The application's database role must not hold `BYPASSRLS`.

---

# Cross-Cutting Concerns

The following concerns apply to every module.

- Authentication
- Authorization
- Validation
- Logging
- Auditing
- Error Handling
- Notifications
- Printing
- Configuration
- Caching
- Monitoring
- Localization
- Accessibility

These concerns should be implemented consistently.

---

# Security Overview

Security principles include:

- Least Privilege
- RBAC
- JWT Authentication
- Input Validation
- Output Encoding
- Audit Logging
- Secure Secrets Management
- HTTPS Only
- OWASP Top 10 Compliance
- Tenant Isolation

---

# Performance Strategy

The platform should prioritize:

- Async APIs
- Lazy Loading
- Pagination
- Server-side Filtering
- Optimized Database Queries
- Redis Caching
- Background Processing
- Virtual Scrolling
- Image Optimization

Performance should be measured continuously.

---

# Scalability Strategy

The architecture should support:

- Additional tenants
- Increased users
- Additional modules
- Future microservice extraction
- Horizontal scaling
- Cloud-native deployment

The initial deployment uses a Modular Monolith with clearly defined module boundaries.

---

# Observability

Every important operation should be observable.

Include

- Structured Logging
- Correlation IDs
- Audit Logs
- Metrics
- Distributed Tracing
- Health Checks
- Performance Monitoring

---

# Architecture Constraints

The following rules must never be violated.

- Business logic must not exist in routers.
- Business logic must not exist in UI components.
- Database access must occur through repositories.
- Domain layer must not depend on infrastructure — no SQLAlchemy, no FastAPI, no framework imports.
- Every request must execute within tenant context.
- All APIs require validation.
- Every important transaction must be auditable.
- Design Tokens must be used by all UI components.
- Accessibility requirements must always be respected.
- Domain events are dispatched **after** commit, never before.
- One transaction per command — Order, Ledger, and Inventory commit together or not at all (BR-29).

These are enforced in CI, not by convention: `import-linter` contracts and `mypy --strict` on the backend, Nx `enforce-module-boundaries` on the frontend. A rule that depends on vigilance is a rule that erodes.

---

# Real-Time

Live updates are Phase 1 scope, delivered over **FastAPI WebSockets with a Redis Pub/Sub backplane** (ADR-015): order status, delivery status, driver assignment, dispatcher operations, dashboard metrics.

- Published behind a transport-agnostic port — domain and application code never import WebSocket or Redis types.
- Channels are tenant-namespaced, constructed server-side from the verified JWT claim. A client never names a channel.
- Subscriptions are authorized against the same RBAC permissions as the equivalent REST endpoint.
- **Real-time is an enhancement, never the source of truth.** Every client can reconstruct state from the REST API.

Detail: `docs/architecture/16-realtime-architecture.md`.

---

# Related Documentation

For implementation details refer to:

- docs/architecture/
- docs/data/
- docs/ui/
- docs/engineering/
- docs/adr/

---

# AI Implementation Guidance

Before implementing any feature:

1. Read this document.
2. Read the Business Domain Summary.
3. Read the relevant feature documentation.
4. Inspect existing code.
5. Reuse existing modules where possible.
6. Follow Engineering Standards.
7. Respect Architecture Decision Records.
8. Write tests.
9. Update documentation when architectural behavior changes.

Never:

- Invent architecture.
- Duplicate business logic.
- Bypass architectural layers.
- Break tenant isolation.
- Ignore accessibility.
- Ignore security.
- Ignore audit requirements.