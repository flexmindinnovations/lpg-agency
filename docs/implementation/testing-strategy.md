# Testing Strategy

This document defines the comprehensive testing strategy for the LPG Agency Management Platform, ensuring the delivery of a high-quality, reliable, and robust system. Quality is a shared responsibility across the entire team.

## Guiding Principles

- **Test Pyramid:** We will follow the testing pyramid model, emphasizing a large base of fast unit tests, a smaller layer of integration tests, and a minimal set of slow end-to-end tests.
- **Automation First:** All tests that can be automated, will be. Manual testing will be reserved for exploratory testing and user acceptance testing (UAT).
- **Test for Business Rules:** Testing will be heavily focused on validating the critical business invariants defined in `docs/business/business-rules.md` and the domain model.
- **Shift-Left Testing:** Testing is not a phase at the end but an activity that occurs throughout the development lifecycle.

## Testing Layers

### 1. Unit Tests
- **Purpose:** To verify the smallest pieces of code (functions, methods, classes) in isolation.
- **Scope:**
  - **Backend:** Domain aggregate invariants (e.g., `CylinderLedger` balance cannot be negative), domain services, application layer logic. Mocks will be used for repositories and external services.
  - **Frontend:** Presentational components (dumb components), pipes, and utility functions.
  - **Mobile:** Logic within Riverpod notifiers, domain entities, and individual widgets.
- **Tools:** `pytest` (Backend), **`Jest`** (Frontend), `flutter_test` (Mobile).
- **Execution:** Run automatically on every commit and PR.

### 2. Integration Tests
- **Purpose:** To verify that different components of the system work together as expected.
- **Scope:**
  - **Backend:** Testing API endpoints from the HTTP request down to the database. These tests run against a **real PostgreSQL instance** — never SQLite or a mock, since Row-Level Security policies and PostgreSQL-specific types must actually be exercised — within a transaction rolled back after each test. This is the primary method for testing the correctness of CQRS commands and queries.
  - **Tenant isolation:** a dedicated suite seeding two tenants and asserting that every cross-tenant access attempt returns nothing. BR-30 is the highest-severity failure mode in the system, so it gets its own suite rather than being an assertion buried in other tests.
  - **Mobile (Driver App):** Critically, testing the **offline-first sync engine**. This involves simulating offline/online state transitions and verifying data is correctly queued, synced, and resolved.
- **Tools:** `pytest` with `HTTPX` (Backend), `patrol`/`integration_test` (Mobile).
- **Execution:** Run automatically on every PR.

### 3. End-to-End (E2E) Tests
- **Purpose:** To simulate a real user journey through the entire application stack (frontend -> backend -> database).
- **Scope:** A small number of critical "happy path" scenarios:
  1.  A customer books an order via the mobile app.
  2.  An agency staff member assigns the order to a driver.
  3.  A driver confirms the delivery via the driver app.
  4.  The customer's ledger and agency's inventory are correctly updated.
  5.  An invoice is generated and visible in the dashboard.
- **Tools:** **`Playwright`** (Web Dashboard), `Patrol` (Mobile Apps). *Corrected in Phase 0 — Playwright is the confirmed E2E tool per `AGENTS.md`; Cypress is not used.*
- **Execution:** Run on a schedule (e.g., nightly) against the Staging environment.

### 4. Performance Tests
- **Purpose:** To ensure the system meets the performance SLAs defined in D-34.
- **Scope:**
  - API response times under load.
  - Database query performance, especially for the `CylinderLedger` and `InventoryTransaction` tables which will grow large.
  - Frontend dashboard load times.
- **Tools:** `k6`, `JMeter`, or a similar load testing tool.
- **Execution:** Run manually before major releases and on a schedule against the Staging environment.

### 5. Manual & Exploratory Testing
- **Purpose:** To find bugs that automated tests might miss, and to verify the user experience.
- **Scope:**
  - New features before release.
  - Complex user workflows.
  - UI/UX issues and accessibility checks (WCAG 2.2 AA).
  - User Acceptance Testing (UAT) with stakeholders on the Staging environment.
- **Execution:** Performed before promoting a build from Staging to Production.

### 6. Specialized Testing
- **Purpose:** To verify cross-cutting concerns that are critical to the platform's integrity and security.
- **Scope:**
  - **Security Testing:**
    - **Penetration Testing:** Performed by a third party before major releases to identify vulnerabilities.
    - **Static/Dynamic Analysis (SAST/DAST):** Integrated into the CI/CD pipeline to catch common security issues automatically.
    - **RBAC Policy Verification:** A dedicated set of integration tests to ensure that users with a specific role (e.g., `Driver`) cannot access endpoints reserved for another role (e.g., `Agency Admin`), as defined in D-38.
  - **Architecture Compliance Testing:**
    - **Backend:** `import-linter` contracts plus `mypy --strict`, run in CI as merge-blocking checks, enforce Clean Architecture rules — the Domain layer importing nothing outward, no SQLAlchemy outside `infrastructure/`, no FastAPI outside `api/`, and bounded-context modules not importing each other's internals. Complemented by a test over the SQLAlchemy model registry asserting every tenant-scoped model declares `tenant_id`. This mitigates the "modular monolith discipline risk" identified in `docs/architecture/01-system-architecture.md` §9. Full rule list in `docs/architecture/03-backend-architecture.md` §12.2 (ADR-024).
    - **Multi-Tenancy Isolation:** A critical set of integration tests that create data for two separate tenants (`TenantA`, `TenantB`) and verify that a user from `TenantA` can *never* read, update, or delete data belonging to `TenantB`. This directly tests business rule BR-30.
- **Execution:** Security and architecture tests are run automatically on every PR. Penetration testing is manual and scheduled.

## Test Data Management

A set of scripts will be created to seed the development and staging databases with realistic, but anonymized, data that covers various scenarios (e.g., customers with complex ledger histories, different order statuses, etc.).