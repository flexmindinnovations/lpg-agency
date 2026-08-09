# Engineering Standards

This document codifies the engineering standards and conventions for the LPG Agency Management Platform. Adherence to these standards is mandatory to ensure code quality, maintainability, and consistency across the platform. These rules supplement the high-level rules in `AGENTS.md`.

## General Principles

1.  **Follow Clean Architecture:** The separation between Domain, Application, and Infrastructure layers is non-negotiable. Domain logic must be pure and framework-independent.
2.  **DDD is Law:** Use the Ubiquitous Language from `docs/architecture/02-domain-driven-design.md`. Aggregates, entities, and value objects must be modeled as described. Communication between aggregates happens via Domain Events, not direct calls.
3.  **OpenAPI First:** The OpenAPI spec is the contract. The frontend and mobile teams consume typed clients generated from this spec. The backend team is responsible for keeping it accurate and versioned.
4.  **No Hardcoded Values:** Business rules, connection strings, API keys, and UI labels must be configurable. Use environment variables and tenant configuration tables (D-42). Colors and styles must come from design tokens (`docs/ui/09-design-tokens.md`).
5.  **Immutability by Default:** Value objects and DTOs should be immutable wherever possible. In Python, use frozen dataclasses or Pydantic models with `allow_mutation=False`. In TypeScript, use `readonly`.

## Backend (Python / FastAPI)

- **Dependency Injection:** Use FastAPI's built-in DI system. Services and repositories are injected into the application layer.
- **Async Everywhere:** All I/O operations (database, network calls) must be `async`. Use `asyncpg` for PostgreSQL and `aiohttp` for external API calls.
- **Repository Pattern:** Repositories are defined per-aggregate. They abstract the persistence logic (SQLAlchemy). The application layer interacts with repository interfaces, not SQLAlchemy directly.
- **Unit of Work:** All operations within a single use case (command) must be executed within a single transactional unit of work to ensure atomicity, especially when modifying multiple aggregates.
- **Error Handling:** Use custom exception classes for domain/application errors, which are mapped to RFC 7807 ProblemDetails in a middleware layer. Do not leak raw database or framework exceptions to the client.
- **Logging:** Use structured logging (e.g., JSON format). Every log entry must include a `traceId` and `tenantId` where applicable.
- **Testing:**
  - **Unit Tests:** For domain logic, services, and helpers. Must not touch the database or network.
  - **Integration Tests:** For API endpoints, testing the full flow from request to database persistence within a test transaction that is rolled back.

## Frontend (Angular 22 / Nx / Tailwind CSS v4)

> **Corrected in Phase 0 (2026-08-09).** This section previously specified "NgRx or Elf", `async`-pipe-first templates, `@Input()`/`@Output()` decorators, and Cypress — a position predating the confirmed Signals-first direction. Reconciled per ADR-018, ADR-019, ADR-020. Full detail in `docs/architecture/04-frontend-architecture.md`.

- **Workspace:** Nx workspace rooted at `frontend/`, with `enforce-module-boundaries` preventing feature libraries from importing each other. Cross-feature communication goes through `shared/data-access` or router navigation.
- **Component Structure:** Container/presentational split. Containers own state and data fetching; presentational components are pure and use **signal-based `input()` / `output()`**, not the `@Input()` / `@Output()` decorators.
- **State Management:** Signals-first, applied as an ordered rule set (ADR-019):
  1. **Angular Signals** for local/component state — the default.
  2. **NgRx SignalStore** for complex feature-level or shared state where centralized reactive state is justified.
  3. **No classic NgRx** Store/Actions/Reducers unless a documented need is recorded as an ADR. **Elf is not used.**
  4. **RxJS** for HTTP, WebSocket streams, debounced input, and async orchestration — converted to Signals at the boundary via `toSignal()`.
  5. Never introduce a state library for simple component state.
- **Templates:** Signal-based and declarative. Modern control flow (`@if`, `@for`, `@switch`), computed signals instead of expressions in templates. The `async` pipe is not the default idiom; RxJS is converted to signals at the data-access boundary.
- **Reactive Forms:** Use Angular's Reactive Forms for all form-based input, with custom validators for complex business rules. Client validation is a UX affordance — the server validates independently and is the guarantee.
- **Data Grid:** AG Grid — **Community by default, Enterprise optional per documented feature requirement** (ADR-028) — **only through the shared wrapper components** in `libs/shared/ui`. Feature libraries must never import AG Grid types or call its APIs directly (ADR-020). Whichever tier a licence applies to, the key comes from environment configuration and is never committed.
- **Component library:** PrimeNG is the primary Angular UI component library (ADR-028); Angular CDK remains available for low-level primitives; Angular Material is used selectively. Both PrimeNG and AG Grid must consume the centralized design-token system wherever their theming APIs allow — no vendor-specific hardcoded styling values.
- **Styling:** Tailwind CSS v4 utility classes mapped to design tokens. No raw hex or px values anywhere. No custom CSS files unless a complex pattern genuinely cannot be expressed otherwise.
- **API Client:** Generated from the committed OpenAPI spec (ADR-026) — never hand-written.
- **Accessibility:** WCAG 2.2 AA (D-35). Accessibility defects are functional defects.
- **Testing:**
  - **Unit (Jest):** services, pipes, validators, presentational components.
  - **Component (Storybook + Testing Library):** shared UI components across all states and all three themes.
  - **E2E (Playwright):** critical user journeys. **Cypress is not used.**
  - **Accessibility (axe-core):** merge-blocking in CI.

## Mobile (Flutter)

- **Architecture:** Adhere to the layered Clean Architecture described in `docs/architecture/05-mobile-architecture.md`.
- **State Management:** Use Riverpod (code-generation flavor) for dependency injection and state management.
- **Offline-First (Driver App):** This is a critical requirement. All data mutations must be written to the local `Drift` database first and queued for synchronization. The UI must be optimistic.
- **Idempotency:** Every sync operation sent to the backend MUST include the `Idempotency-Key` header.
- **Navigation:** Use `go_router` for all navigation and deep-linking.
- **Testing:**
  - **Widget Tests:** For all individual widgets and screens.
  - **Integration Tests:** Crucially, for the offline sync and conflict resolution flows.

## Code Reviews

- All code must be peer-reviewed via Pull Requests before merging to `main`.
- A PR must be linked to a work item (e.g., a Jira ticket).
- The PR description should explain *what* the change is and *why* it's being made.
- CI checks (build, lint, tests) must pass before a PR can be merged.