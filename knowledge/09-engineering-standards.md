# Engineering Standards

## Purpose

This document defines the engineering standards for the LPG Agency Management Platform.

Every developer and AI coding agent must follow these standards to ensure the codebase remains consistent, maintainable, scalable, secure, and production-ready.

For detailed implementation guidelines refer to:

- docs/engineering/
- docs/architecture/
- docs/ui/

---

# Engineering Philosophy

The project prioritizes:

- Simplicity
- Maintainability
- Readability
- Reusability
- Performance
- Security
- Accessibility
- Testability

Code is written for long-term maintenance rather than short-term delivery.

---

# General Principles

Always follow:

- SOLID
- Clean Architecture
- Domain Driven Design
- Composition over Inheritance
- DRY
- KISS
- YAGNI

Never introduce unnecessary complexity.

---

# Repository Organization

Organize code by feature.

Prefer:

Customer

Inventory

Orders

Delivery

Accounting

Reporting

Avoid organizing by file type.

---

# Naming Standards

Use meaningful names.

Good

CustomerService

AssignDriverUseCase

InventoryRepository

Bad

Helper

Manager

Util

CommonService

Avoid abbreviations unless universally understood.

---

# File Naming

Use kebab-case.

Examples

customer-list.component.ts

customer.routes.ts

inventory.service.ts

payment.repository.py

---

# Angular Standards

The project uses Angular 22.

Always use:

- Standalone Components
- Standalone Directives
- Standalone Pipes
- Signals
- Computed Signals
- Effects where appropriate
- inject() instead of constructor injection where suitable
- Functional Route Guards
- Functional Interceptors
- Lazy-loaded feature routes
- Strict TypeScript
- Modern template control flow
- Deferred loading when appropriate

Avoid:

- NgModules for application features
- Template business logic
- Two-way binding where explicit state management is clearer
- any
- Deep component nesting

Prefer:

Signals for local UI state

RxJS only for:

- HTTP
- WebSockets
- Streams
- Timers

Keep components focused on presentation.

Business logic belongs in services or application facades.

State management follows the ordered rule set in ADR-019: Signals by default; NgRx SignalStore for justified complex or shared feature state; no classic NgRx without a documented need; RxJS at HTTP/WebSocket/async boundaries, converted to Signals via `toSignal()`; never a state library for simple component state.

The workspace is **Nx**, rooted at `frontend/`. Feature libraries may never import each other directly — enforced by the `enforce-module-boundaries` lint rule.

Data grids use **AG Grid — Community by default, Enterprise optional per feature — only through the shared wrapper components** in `libs/shared/ui`. Feature libraries must never import AG Grid types or call its APIs directly (ADR-020, amended by ADR-028). **PrimeNG is the primary Angular UI component library**; both PrimeNG and AG Grid must consume the centralized design-token system wherever their theming APIs allow.

---

# Angular Component Rules

Every component should have one responsibility.

Maximum responsibilities:

- Render UI
- Raise events
- Display validation

Avoid:

Database logic

Business calculations

API orchestration

Complex state management

---

# Angular Template Rules

Templates should remain declarative.

Avoid:

Nested conditions

Long expressions

Business calculations

Method chains

Use computed signals instead.

---

# Angular Styling Rules

Always use:

Design Tokens

Tailwind utilities

Angular Material theming

Never:

Hardcode colors

Hardcode spacing

Hardcode typography

Hardcode shadows

---

# FastAPI Standards

The backend uses:

Python 3.13+

FastAPI

SQLAlchemy 2.x

Pydantic v2

Alembic

Redis

The application is async-first.

Use:

async def

Annotated dependencies

Dependency Injection

Type hints everywhere

Repository Pattern

Application Services

Keep routers thin.

Business logic belongs in the Application and Domain layers.

**Layer rules, enforced in CI by `import-linter` and `mypy --strict` (ADR-024):**

- Domain imports nothing from application, infrastructure, or api — plain Python only.
- Application imports domain only, and defines ports (`Protocol`) that infrastructure implements.
- No SQLAlchemy import outside `infrastructure/`.
- No FastAPI import outside `api/`.
- Bounded-context modules do not import each other's internals.

**Async all the way.** A single blocking call inside an async handler stalls the event loop for every concurrent request on that instance — the least visible and highest-impact regression available in this stack.

Cross-cutting concerns are delivered by FastAPI dependencies and the Unit of Work, not by a mediator pipeline (ADR-014). The two that must never be bypassed — tenant scoping and transaction management — are made structurally unavoidable: the session factory does not yield a session without a tenant context.

---

# Python Standards

Use:

PEP 8

PEP 257

Type hints

Dataclasses where appropriate

Enums instead of magic strings

Constants instead of magic numbers

Never:

Use wildcard imports

Suppress exceptions silently

Ignore typing

---

# API Standards

REST APIs only.

Every endpoint should:

Validate input

Validate authorization

Return typed responses

Document OpenAPI

Return RFC7807-compatible errors

Use pagination for collections.

---

# Database Standards

All persistence must use repositories.

Never:

Write raw SQL unless necessary

Bypass repositories

Expose ORM models directly to API clients

Every table should include:

Primary Key

Audit Fields

Tenant Identifier

Soft Delete support where applicable

---

# Error Handling

Never swallow exceptions.

Always:

Log errors

Return meaningful messages

Use centralized exception handling

Separate business errors from infrastructure errors.

---

# Logging

Use structured logging.

Every log should include:

Timestamp

Trace ID

Tenant ID

User ID (when available)

Log Levels:

DEBUG

INFO

WARNING

ERROR

CRITICAL

Never log:

Passwords

Tokens

Secrets

Sensitive personal information

---

# Security

Always:

Validate input

Authorize every request

Sanitize output

Protect secrets

Enforce tenant isolation

Use HTTPS

Follow OWASP recommendations.

---

# Performance

Prefer:

Async APIs

Pagination

Caching

Lazy loading

Virtual scrolling

Optimized SQL

Background jobs for long-running work

Avoid:

N+1 queries

Blocking I/O

Unnecessary API calls

Large payloads

---

# Testing

Every business feature should include:

Unit Tests

Integration Tests

API Tests

Component Tests

End-to-End Tests where appropriate

Critical business logic must never be left untested.

---

# Accessibility

Every UI change must satisfy:

Keyboard Navigation

Focus Management

ARIA Labels

Screen Reader Support

Color Contrast

Semantic HTML

WCAG 2.2 AA

Accessibility defects are considered functional defects.

---

# Documentation

Update documentation whenever:

Architecture changes

Business rules change

API contracts change

Database schema changes

Configuration changes

Documentation is part of the feature.

---

# Git Standards

Use:

Feature branches

Small commits

Meaningful commit messages

Pull Requests

Code Reviews

Squash merge unless project policy specifies otherwise.

---

# AI Coding Standards

Before writing code:

1. Read AGENTS.md
2. Read the relevant knowledge documents.
3. Read the detailed documentation.
4. Inspect existing implementation.
5. Reuse existing code before creating new code.

AI agents must never:

Invent business rules

Duplicate business logic

Ignore architecture

Break tenant isolation

Bypass repositories

Ignore accessibility

Ignore tests

Introduce unnecessary dependencies

---

# Definition of Good Code

Good code is:

Readable

Predictable

Testable

Reusable

Documented

Secure

Accessible

Observable

Performant

Maintainable

The simplest correct solution is preferred over the most clever solution.

---

# Related Documentation

Refer to:

- docs/engineering/
- docs/architecture/
- docs/ui/
- docs/data/