# 15 — Architecture Decision Records (ADRs)

## Purpose
Records the **why** behind every major architectural decision made across `docs/architecture/`, in standard ADR format (Context, Decision, Consequences, Alternatives), so future engineers understand the reasoning — not just the outcome — even a decade from now.

## Format
Each ADR: **Status** (Accepted / Amended / Superseded), **Context**, **Decision**, **Consequences**, **Alternatives Considered**.

Superseded ADRs keep their original text **verbatim and unedited**. A supersession block is added above the original, naming the replacing ADR and explaining why the decision changed. Nothing is deleted. Amended ADRs keep their decision but restate the enforcement mechanism where the technology changed underneath it.

## Reading Order
ADR-001 … ADR-011 were written during the original architecture phase. ADR-012 … ADR-026 were added during **Phase 0 — Documentation Reconciliation (2026-08-09)**, when the backend stack was confirmed as Python/FastAPI/PostgreSQL and the remaining open technology decisions were settled. If you only read one section, read the [Summary Table](#summary-table).

---

## ADR-001: Monorepo for Backend + All Three Clients

**Status:** Accepted — *amended by [ADR-025](#adr-025-polyglot-monorepo-layout-amends-adr-001) (physical layout)*

**Context:** The platform consists of a backend and three clients (Dashboard, Customer App, Driver App) that share contracts (API/OpenAPI), design tokens, and release cadence concerns. A small team (per SRS team structure: ~10 people) needs to coordinate cross-cutting changes efficiently.

**Decision:** Use a single monorepo housing backend, Dashboard (Nx), and mobile (Flutter workspace).

**Consequences:** Atomic cross-cutting PRs; single CI/CD system to maintain; requires disciplined build tooling (Nx affected-detection, path-filtered GitHub Actions) to keep CI times reasonable as the repo grows (`14-folder-structure.md`).

**Alternatives Considered:** Polyrepo — rejected due to coordination overhead for a small team building tightly-coupled contract-sharing clients; revisit if teams grow and gain independent release cadences.

---

## ADR-002: Modular Monolith over Microservices (Phase 1)

**Status:** Accepted — *amended 2026-08-09: deployable unit is a FastAPI application, not ASP.NET Core*

> **Amendment note (Phase 0, 2026-08-09):** The decision — one deployable application, internally structured by Clean Architecture layers and DDD bounded contexts — is **unchanged and stack-independent**. Only the runtime changed: the single deployable is a **FastAPI application** (per [ADR-012](#adr-012-python-313--fastapi-as-the-backend-platform)), and cross-module communication uses an in-process domain-event dispatcher (per [ADR-014](#adr-014-application-services-with-an-explicit-cross-cutting-pipeline-supersedes-adr-004)) rather than in-process MediatR. Module-boundary enforcement moves from NetArchTest to Python import-linter (per [ADR-024](#adr-024-architecture-boundary-enforcement-in-python)).

**Context:** The SRS defines 11 bounded contexts (`02-domain-driven-design.md`). Microservices would allow independent scaling/deployment per context but introduce distributed-systems complexity (network calls, eventual consistency, distributed transactions) that a small team must operate.

**Decision:** Build a single deployable ASP.NET Core application internally structured by Clean Architecture layers and DDD bounded contexts (modules), not as separate services.

**Consequences:** Lower operational overhead; in-process MediatR for cross-module communication (no network hop); strong transactional consistency for the Cylinder Ledger/Inventory invariants (BR-01–BR-15, BR-29) without distributed-transaction complexity. Requires enforced module boundaries (architecture tests, `03-backend-architecture.md` §1) to prevent the modules from becoming entangled — the primary risk of this pattern.

**Alternatives Considered:** Microservices from day one — rejected as premature for Phase 1 team size and unstabilized bounded contexts; documented extraction path if specific modules (Reporting, Notifications) later demonstrate independent scaling needs (`01-system-architecture.md` §11).

---

## ADR-003: Shared Database, Discriminator-Column Multi-Tenancy

**Status:** Accepted — *amended by [ADR-017](#adr-017-postgresql-rls--repository-scoping-for-tenant-isolation-amends-adr-003) (enforcement mechanism)*

> **Amendment note (Phase 0, 2026-08-09):** The decision — shared database, shared schema, `tenant_id` discriminator, defense in depth — is **unchanged**. The enforcement layers were rebound from EF Core Global Query Filters + SQL Server RLS to **SQLAlchemy repository scoping + PostgreSQL Row-Level Security**, and the pipeline-level scoping moved from a MediatR behavior to a FastAPI request-scoped dependency. See [ADR-017](#adr-017-postgresql-rls--repository-scoping-for-tenant-isolation-amends-adr-003).

**Context:** D-01 confirms the platform is multi-tenant SaaS from Phase 1. Multi-tenancy can be implemented via shared-schema-with-discriminator, schema-per-tenant, or database-per-tenant.

**Decision:** Shared Azure SQL database, shared schema, `TenantId` discriminator column on every tenant-scoped table, enforced via EF Core Global Query Filters + SQL Server Row-Level Security + pipeline-level scoping (`06-database-architecture.md` §2).

**Consequences:** Lower operational overhead (single set of migrations/backups/monitoring) at expected initial tenant scale; requires defense-in-depth tenant-isolation enforcement (multiple layers, since a single missed filter is a data-leak risk) and dedicated isolation tests in CI.

**Alternatives Considered:** Database-per-tenant — rejected for Phase 1 due to higher DevOps overhead; documented as the scale-out path for large/contractually-isolated tenants (`06-database-architecture.md`).

---

## ADR-004: CQRS via In-Process MediatR (Not Event Sourcing)

> ### ⛔ SUPERSEDED
> **Superseded on:** 2026-08-09 · **By:** [ADR-014 — Application Services with an Explicit Cross-Cutting Pipeline](#adr-014-application-services-with-an-explicit-cross-cutting-pipeline-supersedes-adr-004)
>
> **Why superseded:** MediatR is a .NET library. It does not exist in Python, and no direct equivalent is warranted. The *substance* of this decision survives entirely — CQRS as an in-process pattern against a single database, no event sourcing in Phase 1 — and so does the deferred-not-rejected stance on event sourcing for the Cylinder Ledger. What changed is only the mechanism that carried it: five MediatR `IPipelineBehavior` implementations became explicit FastAPI dependencies and an application-service decorator chain. Those five behaviors encoded real business rules (BR-28 audit logging, BR-30 tenant scoping) and were deliberately re-expressed, not dropped.

**Status:** Superseded

**Context:** The system needs clear read/write separation for maintainability and query performance, without the operational complexity of a fully event-sourced system, given the ledger/inventory domains already carry natural transactional-integrity requirements best served by conventional relational transactions initially.

**Decision:** CQRS as an in-process pattern (MediatR commands/queries against the same database), not full event sourcing or physically separate read/write stores.

**Consequences:** Simpler mental model and lower infrastructure cost for Phase 1; a documented, compatible seam exists for a future move toward event sourcing for the Cylinder Ledger specifically, since its transaction log already resembles an event stream (`02-domain-driven-design.md` §10).

**Alternatives Considered:** Event Sourcing for Cylinder Ledger — deferred, not rejected outright; revisit once the team has operational experience with the simpler model and a concrete need (e.g., temporal replay/audit requirements beyond what the append-only transaction table already provides) emerges.

---

## ADR-005: Azure SQL Database over Cosmos DB

> ### ⛔ SUPERSEDED
> **Superseded on:** 2026-08-09 · **By:** [ADR-013 — PostgreSQL as the Primary Relational Store](#adr-013-postgresql-as-the-primary-relational-store-supersedes-adr-005)
>
> **Why superseded:** The *reasoning* in this ADR is correct and was carried forward unchanged — the Cylinder Ledger and Inventory domains genuinely require multi-row, multi-table ACID transactions and strong relational integrity, and a NoSQL store genuinely is a poor fit. What changed is which relational engine: **PostgreSQL**, not Azure SQL, per `AGENTS.md` and the PostgreSQL-native physical schema in `docs/data/03-database-schema.md`. The rejection of Cosmos DB stands on the original grounds.

**Status:** Superseded

**Context:** The Cylinder Ledger and Inventory domains require strict multi-row, multi-table transactional consistency (a delivery confirmation must atomically update Order, Ledger, and Inventory — BR-29) and strong relational integrity (foreign keys, check constraints preventing negative balances).

**Decision:** Azure SQL Database (relational) as the primary data store, not Cosmos DB or another NoSQL store.

**Consequences:** Native ACID transactions across aggregates within a request; requires more deliberate multi-tenant sharding/partitioning planning than a NoSQL store's typically simpler horizontal partitioning story (mitigated by the documented scale-out path in `06-database-architecture.md` §8–9).

**Alternatives Considered:** Cosmos DB — rejected; while it offers simpler global distribution, its eventual-consistency defaults and weaker cross-partition transactional guarantees are a poor fit for the ledger's correctness-critical invariants.

---

## ADR-006: Flutter for Both Mobile Apps

**Status:** Accepted — unaffected by the backend stack change

**Context:** Two mobile apps (Customer, Driver) are needed across Android and iOS, with a small team.

**Decision:** Single Flutter codebase (shared packages, per-app targets — `05-mobile-architecture.md` §1), matching the SRS's explicit technology direction.

**Consequences:** One codebase/skillset serves both apps and both platforms; strong offline/local-storage ecosystem (Drift/SQLite) supports the mandatory offline-first Driver App requirement (D-24).

**Alternatives Considered:** Native (Kotlin/Swift) — rejected; doubles engineering effort for a 2-Flutter-developer team allocation (per SRS team structure) building three total client apps across two platforms.

---

## ADR-007: Azure SignalR Service for Real-Time Updates

> ### ⛔ SUPERSEDED
> **Superseded on:** 2026-08-09 · **By:** [ADR-015 — FastAPI WebSockets with a Redis Pub/Sub Backplane](#adr-015-fastapi-websockets-with-a-redis-pubsub-backplane-supersedes-adr-007)
>
> **Why superseded:** SignalR is a .NET real-time framework, and Azure SignalR Service is its managed backplane; neither applies to a FastAPI backend. The *requirement* is unchanged and was in fact **confirmed as Phase 1 scope** during Phase 0 — live order status, delivery status, driver assignment, dispatcher operations, and dashboard updates. The horizontal-scalability reasoning also survives intact: real-time fan-out must not be bound to a single API instance. The replacement achieves it with FastAPI WebSockets and a Redis Pub/Sub backplane, using Redis the platform already operates rather than adding a managed service. The rejection of client polling stands on the original grounds.

**Status:** Superseded

**Context:** Customers need live order/delivery status tracking (`modules/order-management.md` §4.4); the API must scale horizontally (multiple stateless instances).

**Decision:** SignalR with the Azure SignalR Service backplane (not in-process SignalR), so real-time connections are managed independently of API instance count/lifecycle.

**Consequences:** True horizontal scalability for real-time features; slightly higher infrastructure cost/complexity than in-process SignalR, justified by the confirmed 500+ concurrent users/tenant scaling target (D-34).

**Alternatives Considered:** Polling from clients instead of push — rejected; higher latency, higher unnecessary API load, and a worse UX than the SRS's real-time tracking expectation.

---

## ADR-008: Offline-First Architecture for the Driver App (Not Customer App)

**Status:** Accepted — unaffected by the backend stack change

**Context:** D-24 confirms mandatory offline-first architecture for the Driver App specifically, given field delivery conditions with unreliable connectivity; the Customer App has no equivalent explicit requirement.

**Decision:** Full offline-first design (local DB, sync queue, conflict resolution — `05-mobile-architecture.md` §3) for the Driver App; a simpler cache-and-refresh pattern for the Customer App.

**Consequences:** Significant engineering investment concentrated where it matters most (field delivery reliability directly protects revenue and customer trust); avoids over-engineering the Customer App, which typically operates in areas with better connectivity.

**Alternatives Considered:** Offline-first for both apps uniformly — rejected as unnecessary scope/cost for the Customer App given no confirmed business requirement; the residual open item in `docs/engineering/open-questions.md` around this elevation's schedule impact is specifically about the Driver App, reinforcing that this is the higher-stakes app.

---

## ADR-009: URL-Segment API Versioning

**Status:** Accepted — unaffected by the backend stack change

**Context:** Three independently-releasing clients consume the same API; backward compatibility across mobile app store rollout windows (`13-deployment.md`) is essential.

**Decision:** `/api/v1/...` URL-segment versioning (`07-api-architecture.md` §3), incrementing only for breaking changes.

**Consequences:** Simple to reason about, debug, and log; older mobile app versions continue functioning against `v1` while a `v2` rolls out gradually to app stores. Requires discipline in defining what constitutes a "breaking" vs. "additive" change.

**Alternatives Considered:** Header-based versioning — rejected for weaker discoverability/debuggability versus URL-segment versioning.

---

## ADR-010: Server-Rendered, Template-Based Printing Engine

**Status:** Accepted — *amended by [ADR-016](#adr-016-python-rendering-stack-for-the-printing-engine-amends-adr-010) (rendering libraries)*

> **Amendment note (Phase 0, 2026-08-09):** The decision — one server-side, tenant-configurable, block-based template engine serving thermal, A4, and PDF from a single template definition — is **unchanged and remains Accepted**. Only the rendering libraries were rebound from .NET (QuestPDF, ZXing.Net, QRCoder) to Python equivalents. See [ADR-016](#adr-016-python-rendering-stack-for-the-printing-engine-amends-adr-010).

**Context:** The SRS requires printing across many document types (invoice, receipts, ledger, multiple report types) and multiple output formats (thermal, A4, PDF), consumed by the Dashboard and indirectly by mobile.

**Decision:** A single, tenant-configurable, block-based template engine rendered server-side (`09-printing-architecture.md`), rather than per-document-type client-rendered layouts.

**Consequences:** One engine to maintain, consistent output regardless of originating client, easy extension for Phase 2's cylinder-level QR/barcode labels; requires careful template-editor design to prevent tenants from removing legally-required fields (GST breakdown).

**Alternatives Considered:** Client-side print CSS per document type — rejected; would duplicate layout logic across Dashboard and mobile and per output format.

---

## ADR-011: Shared Component Library as the Accessibility Enforcement Mechanism

**Status:** Accepted — unaffected by the backend stack change

**Context:** D-35 confirms WCAG 2.2 AA is a Phase 1 launch requirement, applied across a large surface area of Dashboard screens/features.

**Decision:** Concentrate accessibility implementation in `libs/shared/ui` (`04-frontend-architecture.md` §5, `11-accessibility-strategy.md` §2) so feature teams inherit compliance rather than re-implementing it, backed by automated (axe-core in CI) and manual (screen-reader) testing gates.

**Consequences:** Consistent compliance quality across features; concentrates risk (and testing investment) in a smaller, well-understood surface area (the shared library) rather than spreading it thin across every feature team.

**Alternatives Considered:** Per-feature accessibility ownership — rejected for inconsistent quality and duplicated effort.

---
---

# Phase 0 Decisions (2026-08-09)

The following ADRs were recorded during Phase 0 — Documentation Reconciliation, when the backend stack was confirmed and the outstanding technology questions were settled by the product owner.

---

## ADR-012: Python 3.13 + FastAPI as the Backend Platform

**Status:** Accepted

**Context:** The repository carried two complete, internally consistent, mutually exclusive backend architectures. `docs/architecture/` (authored first) specified ASP.NET Core 8 / C# / EF Core / MediatR / Azure SQL. `AGENTS.md`, `knowledge/`, and all 20 documents in `docs/data/` — including a complete PostgreSQL physical schema with SQLAlchemy-specific design notes — specified Python 3.13 / FastAPI / SQLAlchemy 2.x / PostgreSQL.

`AGENTS.md` declares itself authoritative on conflict. No application code had been written against either stack, so the cost of the decision was entirely documentary.

**Decision:** The backend platform is **Python 3.13+ / FastAPI / SQLAlchemy 2.x / Alembic / Pydantic v2 / PostgreSQL / Redis**. The ASP.NET Core architecture is superseded. The superseded documents are preserved under `docs/architecture/superseded/` rather than deleted.

**Consequences:**
- Six architecture documents (`01`, `03`, `06`, `09`, `13`, `14`) required full rewrites; the remainder needed only mechanism rebinding.
- ADR-004, ADR-005, and ADR-007 are superseded (their reasoning largely survives; their mechanisms do not).
- The Python ecosystem brings the AI/ML libraries relevant to the documented Phase 2 roadmap (demand forecasting, route optimization) into the same runtime as the business logic.
- FastAPI's Pydantic-driven OpenAPI generation makes the API contract a by-product of correctly-typed code rather than a separately maintained artifact — see [ADR-026](#adr-026-code-first-openapi-generation-with-the-generated-spec-as-the-frozen-client-contract).
- **Cost:** Python has no direct equivalent to MediatR's pipeline behaviors or NetArchTest's boundary assertions. Both had to be designed explicitly (ADR-014, ADR-024) rather than adopted off the shelf. This is real work that the .NET stack would have provided ready-made.
- Static typing is opt-in rather than enforced by the compiler; strict `mypy` in CI is therefore not optional but load-bearing.

**Alternatives Considered:**
- **Keep ASP.NET Core** and supersede the `docs/data/` layer instead — rejected. It would contradict `AGENTS.md`'s explicit authority, discard a complete and more recent PostgreSQL schema design, and reverse a direction the product owner has confirmed.
- **Run both** (e.g. .NET for transactional modules, Python for analytics) — rejected outright for Phase 1: two runtimes, two dependency ecosystems, two deployment pipelines, and a distributed transaction boundary through the middle of the Cylinder Ledger, for a team of ten.

---

## ADR-013: PostgreSQL as the Primary Relational Store (supersedes ADR-005)

**Status:** Accepted · **Supersedes:** ADR-005 · *amended by [ADR-027](#adr-027-supabase-as-the-managed-postgresql-host-amends-adr-013-adr-022) (host named)*

> **Amendment note (2026-08-09):** The engine decision — PostgreSQL, via SQLAlchemy 2.x with Alembic migrations — is **unchanged**. ADR-027 names **Supabase** as the managed host and reaffirms that **Alembic remains the sole owner of schema**: Supabase's own migration tooling must not be used.

**Context:** ADR-005 correctly established that the Cylinder Ledger and Inventory domains require multi-row, multi-table ACID transactions and strong relational integrity, and correctly rejected Cosmos DB on those grounds. That analysis is unaffected by the backend language. What it got wrong, relative to the confirmed stack, was the engine.

**Decision:** **PostgreSQL** is the primary relational store, accessed via SQLAlchemy 2.x with Alembic migrations. The authoritative physical schema is `docs/data/03-database-schema.md`, which is already PostgreSQL-native.

**Consequences:**
- Native features the design already depends on: Row-Level Security for tenant isolation (ADR-017), `gen_random_uuid()` for offline-safe client-generated IDs (required by the offline-first Driver App), `timestamptz`, `JSONB` for audit before/after state, GIN/`tsvector` full-text search for customer lookup, and partial indexes.
- Full-text search comes for free, removing a search-service dependency the design would otherwise have acquired later (noted in `docs/data/04-database-indexing.md`).
- Heap storage means UUID primary keys carry none of the clustered-index fragmentation penalty they would on SQL Server — the UUID-PK decision costs less here than it would have.
- No vendor lock-in to a single cloud's managed SQL offering; PostgreSQL runs identically in Docker locally and on any cloud's managed Postgres.
- Optimistic concurrency must be application-managed (`version` column via SQLAlchemy's `version_id_col`), since PostgreSQL has no native `rowversion`.
- **Cost:** connection pooling under a horizontally-scaled async application needs deliberate attention (server-side pooling, e.g. PgBouncer, is likely required at scale) in a way Azure SQL's model would have handled differently.

**Alternatives Considered:** Cosmos DB or another NoSQL store — rejected, on the original ADR-005 grounds, which remain valid. Azure SQL — superseded by ADR-012's language change; retaining SQL Server behind a Python ORM would have meant giving up RLS ergonomics, `JSONB`, and native full-text search for no compensating benefit.

---

## ADR-014: Application Services with an Explicit Cross-Cutting Pipeline (supersedes ADR-004)

**Status:** Accepted · **Supersedes:** ADR-004

**Context:** ADR-004 chose CQRS as an in-process pattern, implemented through MediatR, with five `IPipelineBehavior` implementations providing cross-cutting concerns uniformly: validation, tenant scoping, audit logging, transaction management, and performance logging. Two of those five encode binding business rules — BR-30 (tenant scoping) and BR-28 (audit logging) — so they could not simply be dropped along with the library.

Python has MediatR-style dispatch libraries, but adopting one would add an indirection layer that FastAPI's own dependency-injection system already provides more idiomatically and more legibly.

**Decision:** Retain **CQRS as an in-process pattern** — commands mutate through aggregates, queries read through optimized read paths, both against the same database, no event sourcing in Phase 1. Implement it with **explicit application services** (one per use case) invoked directly by thin routers, with cross-cutting concerns delivered by two complementary mechanisms:

| Original MediatR behavior | Replacement mechanism |
|---|---|
| `ValidationBehavior` | Pydantic v2 request models (shape/format) + explicit domain-invariant checks inside aggregates |
| `TenantScopingBehavior` | Request-scoped FastAPI dependency resolving tenant from the JWT, setting `app.current_tenant_id` on the transaction, plus repository-level scoping — see ADR-017 |
| `AuditLoggingBehavior` | SQLAlchemy session event hooks (`before_flush`) capturing before/after state, plus explicit audit writes in the Unit of Work commit path |
| `TransactionBehavior` | Unit of Work as a request-scoped async context manager; one transaction per command |
| `PerformanceLoggingBehavior` | ASGI middleware timing every request, plus per-use-case timing in the application-service decorator |

Full detail in `03-backend-architecture.md`.

**Consequences:**
- Control flow is directly readable — a router calls a named service which calls named collaborators. New engineers trace a request without learning a dispatch abstraction. This directly addresses the risk ADR-004's own document flagged ("MediatR pipeline overuse… can obscure control flow for new engineers").
- Cross-cutting concerns are no longer guaranteed by a single pipeline registration. Tenant scoping and transaction management must be structurally impossible to bypass rather than merely conventional — enforced through the session factory (a session cannot be obtained without a tenant context) and by boundary tests (ADR-024).
- The deferred-not-rejected stance on event sourcing for the Cylinder Ledger carries over unchanged.
- Trade-off accepted: slightly more explicit wiring per use case, in exchange for legibility and no dispatch-library dependency.

**Alternatives Considered:**
- **A Python mediator library** (e.g. a `mediatr`-style package) — rejected; it would replicate MediatR's indirection cost without MediatR's ecosystem maturity, and FastAPI's DI already covers the need.
- **Decorators alone for all five concerns** — rejected for transaction and tenant scoping specifically; a decorator can be forgotten, whereas a session factory that refuses to produce an unscoped session cannot.

---

## ADR-015: FastAPI WebSockets with a Redis Pub/Sub Backplane (supersedes ADR-007)

**Status:** Accepted · **Supersedes:** ADR-007

**Context:** Real-time updates are **confirmed Phase 1 scope**: order status, delivery status, driver assignment, dispatcher operational updates, and dashboard live updates. ADR-007's core constraint remains true — the API runs as multiple stateless instances, so a client connected to instance A must receive an event raised on instance B. Azure SignalR Service solved this for .NET; it is not applicable to FastAPI.

**Decision:** **FastAPI native WebSockets** for client connections, with **Redis Pub/Sub** as the cross-instance backplane. Publication happens behind a transport-agnostic `RealtimePublisher` interface, so the transport can evolve (to SSE, to a managed service, to a broker) without touching domain or application code.

Channels are namespaced by tenant — `tenant:{tenant_id}:...` — and subscription is authorized per connection against the same RBAC permissions as the equivalent REST endpoint. Cross-tenant subscription is structurally impossible.

**Consequences:**
- Uses infrastructure the platform already operates. Redis is already committed for caching, sessions, and rate limiting; the backplane adds no new managed service, no new vendor, and no new cost line.
- Cloud-portable — nothing here binds to Azure, consistent with ADR-022 deliberately leaving hosting topology open.
- WebSocket connections are stateful, which constrains horizontal scaling in a way stateless HTTP does not: the hosting platform must support long-lived connections and sticky-free fan-out, and connection count becomes a first-class capacity metric (`12-observability.md`).
- Redis Pub/Sub is fire-and-forget with no delivery guarantee. This is acceptable because **real-time push is an enhancement, never the source of truth** — every client can reconstruct correct state from the REST API, and the mobile apps already do so on reconnect. Any future requirement for guaranteed delivery means Redis Streams or a real broker, not a patch to this design.
- Redis becomes a availability dependency for real-time features specifically; its failure degrades live updates to polling rather than breaking core operations.

**Alternatives Considered:**
- **Server-Sent Events (SSE)** — genuinely close, and simpler (plain HTTP, automatic reconnection). Rejected as the primary transport because it is unidirectional, and the Driver and Dispatcher flows benefit from a bidirectional channel. Retained as the natural fallback behind the same abstraction where a browser or proxy blocks WebSockets.
- **Client polling** — rejected on ADR-007's original grounds: higher latency, wasted API load, worse UX.
- **A managed real-time service** (Azure Web PubSub, Pusher, Ably) — rejected for Phase 1; it adds vendor cost and lock-in for a problem Redis already solves at this scale.

---

## ADR-016: Python Rendering Stack for the Printing Engine (amends ADR-010)

**Status:** Accepted · **Amends:** ADR-010 · **Library selection: deferred**

**Context:** ADR-010's architectural decision — one server-side, tenant-configurable, block-based template engine — stands. Its .NET rendering libraries (QuestPDF for PDF, ZXing.Net/QRCoder for codes) do not.

**Decision:** Keep the engine architecture unchanged. Rebind rendering to Python:

| Concern | Direction |
|---|---|
| A4 / PDF | HTML+CSS intermediate rendered to PDF by a Python renderer. Candidates: **WeasyPrint** (CSS Paged Media, strong typographic control) or **ReportLab** (programmatic layout). |
| Thermal (58/80 mm) | ESC/POS byte-stream generation from the same block model — no HTML intermediate. |
| Barcode / QR | Python `qrcode` and `python-barcode` (Code 128 per `knowledge/08-printing-summary.md`). |

**The specific PDF library is deliberately not selected in Phase 0.** The choice hinges on rendering fidelity for GST-compliant invoice layouts and multi-page report pagination, which is an empirical question best answered by a spike against real templates during Phase 17 (Printing). Recorded as DW-07 in the Phase 0 task list.

**Consequences:**
- The block-based template model is renderer-agnostic by design, so the deferral costs nothing — the template definitions, `DocumentType` composition, preview pipeline, and caching policy are all independent of which library produces the bytes.
- The HTML+CSS intermediate for A4/PDF means print layouts can reuse the design-token vocabulary, keeping printed output visually consistent with the Dashboard.
- WeasyPrint carries native system dependencies (Pango, Cairo), which affects the container image. This is a deployment consideration to weigh during the spike, not a blocker.

**Alternatives Considered:** Headless-browser rendering (Playwright/Chromium to PDF) — high fidelity, but a heavy runtime dependency for a server-side batch capability, and Playwright is already committed for E2E testing where that weight is justified. Kept as a fallback if neither candidate meets fidelity requirements.

---

## ADR-017: PostgreSQL RLS + Repository Scoping for Tenant Isolation (amends ADR-003)

**Status:** Accepted · **Amends:** ADR-003

**Context:** ADR-003's decision — shared database, shared schema, `tenant_id` discriminator, defense in depth — is unchanged and remains correct. Its four enforcement layers were EF Core Global Query Filters, SQL Server RLS, a MediatR `TenantScopingBehavior`, and NetArchTest assertions. All four mechanisms are .NET-specific. BR-30 does not care which mechanism enforces it, but it does require that *something* does, at more than one layer.

**Decision:** Four equivalent layers, PostgreSQL/Python-native:

| # | Layer | Mechanism |
|---|---|---|
| 1 | Database | **PostgreSQL Row-Level Security** policies on every tenant-scoped table, predicated on `current_setting('app.current_tenant_id')` |
| 2 | Session | `SET LOCAL app.current_tenant_id = '<uuid>'` issued at the start of every request transaction by a FastAPI dependency, from the verified JWT claim |
| 3 | Application | Repositories are constructed with a tenant context; the session factory does not produce a session without one |
| 4 | CI | Boundary tests (ADR-024) asserting every tenant-scoped model declares `tenant_id`, plus integration tests that attempt cross-tenant reads and assert they return nothing |

The ordering matters: layer 1 is the backstop that holds even if application code is wrong, which is the property that makes this defense in depth rather than defense in repetition.

**Consequences:**
- Stronger than the superseded design in one specific respect: because RLS is predicated on a session variable rather than on the ORM, it protects **raw SQL, reporting queries, and future BI tool connections** automatically — the exact bypass path the original document worried about.
- The application's PostgreSQL role must not hold `BYPASSRLS`. Migrations and administrative jobs run under a separate role. This is a deployment requirement, not merely a convention.
- Every request must set the session variable before any query, making it a hard requirement of the request lifecycle rather than a per-query concern.
- The RLS-predicate-vs-application-filter drift risk noted in the superseded document is materially reduced, since the predicate is defined once in migrations rather than mirrored in ORM configuration.

**Alternatives Considered:** Application-layer filtering only — rejected; a single forgotten `WHERE tenant_id = ...` is a cross-tenant data breach, and this is precisely the class of bug that defense in depth exists to survive. Schema-per-tenant — rejected on ADR-003's original operational-overhead grounds.

---

## ADR-018: Angular 22 + Nx Workspace under `frontend/`

**Status:** Accepted

**Context:** `AGENTS.md` and `knowledge/` specified Angular 22 without naming a workspace tool. `docs/architecture/04-frontend-architecture.md` specified Angular 20 and an Nx monorepo with `enforce-module-boundaries`. The version conflict needed resolving, and Nx needed to be either confirmed or dropped, since it determines the entire frontend folder structure and cannot be retrofitted cheaply.

**Decision:** **Angular 22** with strict TypeScript, in an **Nx workspace rooted at `frontend/`**. The repository folder is **`frontend/`** and is not renamed to `dashboard/`; the Nx application inside it may be named `dashboard`.

Nx is adopted specifically for its `enforce-module-boundaries` lint rule and affected-project detection.

**Consequences:**
- Feature libraries cannot import each other directly — the lint rule makes the bounded-context isolation from `02-domain-driven-design.md` mechanically enforced on the frontend, mirroring what import-linter does on the backend (ADR-024). This is the main reason Nx earns its complexity here.
- Affected-project detection keeps monorepo CI times bounded as the workspace grows (the risk ADR-001 flagged).
- The workspace can host a future second Angular application (e.g. a customer web portal) without restructuring.
- **Cost:** Nx is a real abstraction over the Angular CLI with its own upgrade cadence, generators, and failure modes. For a single application it is arguably over-tooling; the boundary enforcement and the documented 8-feature-library structure are what justify it.
- Angular 22 is a deliberate choice to build on current APIs (signal-based `input()`/`output()`, modern control flow, deferred loading) rather than starting two major versions behind.

**Alternatives Considered:**
- **Plain Angular CLI workspace** — simpler, one less tool. Rejected because module-boundary enforcement would fall back to code review, and the whole point of the feature-library structure is that boundaries hold without vigilance.
- **Micro-frontends (Module Federation)** — rejected for Phase 1, on the original document's grounds: Nx's library modularity provides the internal boundaries without independent-deployment complexity.

---

## ADR-019: Signals-First State Management with NgRx SignalStore

**Status:** Accepted

**Context:** Three documents gave three different answers. `AGENTS.md`/`knowledge/09` said Signals-first with RxJS confined to HTTP, WebSockets, timers, and streams. `docs/architecture/04` said Signals plus NgRx SignalStore for shared feature state. `docs/implementation/engineering-standards.md` said "NgRx or Elf" with `async`-pipe-first templates, `@Input()`/`@Output()` decorators, and Cypress — a materially older position that conflicts with signal-based component APIs.

Left unresolved, each feature would pick a different pattern.

**Decision:** A single ordered rule set:

1. **Angular Signals** for local and component state. This is the default and covers most cases.
2. **NgRx SignalStore** for complex feature-level or shared application state where centralized reactive state is genuinely justified — a list with server-side filter/sort/pagination, state shared across sibling routes, state that must survive navigation.
3. **No classic NgRx** Store/Actions/Reducers/Effects unless a documented architectural need exists and is recorded as an ADR.
4. **RxJS** for HTTP streams, WebSocket streams, debounced input, complex async orchestration, and interop with libraries that emit Observables. Convert to Signals at the boundary with `toSignal()` so templates stay signal-based.
5. **Never** introduce a state-management library for simple component state.

**Consequences:**
- One decision procedure, applied per situation, rather than three competing defaults.
- Rule 2 is a judgement call by design. The guard against sprawl is that reaching for SignalStore requires a stated reason at review time, not that the rule is mechanical.
- `docs/implementation/engineering-standards.md` required correction on three counts: state library, template idiom, and component test tooling (Cypress → Playwright + Storybook, per `AGENTS.md`).
- **TanStack Query is not adopted.** The superseded frontend document floated it as optional for Reporting. Adding a fourth state mechanism alongside Signals, SignalStore, and RxJS contradicts the intent of this ADR; SignalStore covers the caching and refetch needs at Phase 1 scale.

**Alternatives Considered:** Signals-only, no SignalStore — attractively simple, rejected because hand-rolled shared state for the larger feature modules reproduces SignalStore badly. Classic NgRx — rejected for boilerplate disproportionate to the need, on the original document's grounds.

---

## ADR-020: AG Grid Enterprise Behind an Application-Level Abstraction

**Status:** Accepted

**Context:** `AGENTS.md` and `knowledge/02` mandate AG Grid Enterprise. The superseded frontend document instead prescribed Angular CDK + Material with "PrimeNG only where beneficial," and never mentioned AG Grid. The enterprise-grid requirements in `docs/srs/non-functional.md` §7 and `docs/ui/14-data-grid-guidelines.md` (grouping, column chooser, saved views, export, virtualization at scale) are substantial, and AG Grid Enterprise is a **commercial, paid-licence** product — so the choice carries a procurement dependency, not just a technical one.

**Decision:** **AG Grid Enterprise is the standard enterprise data-grid implementation**, subject to three binding constraints:

1. It is **encapsulated behind application-level reusable grid components** in `libs/shared/ui`.
2. Feature libraries **must not** import AG Grid types or call AG Grid APIs directly. They configure the wrapper through an application-defined column/dataset contract.
3. The **commercial licence requirement is documented** and the licence key is supplied as environment configuration, never committed.

The architecture must remain replaceable if licensing or product requirements change.

**Consequences:**
- Constraint 2 is what makes constraint 3 meaningful. A grid abstraction that leaks AG Grid types is not replaceable, regardless of intent — so this is a lint-and-review concern, not a naming convention.
- PrimeNG is **not** adopted. With AG Grid for data grids and Angular Material + CDK for interaction primitives, it has no remaining role, and a third component library would fragment the design-token implementation.
- Accessibility remains enforced at the wrapper layer per ADR-011 — AG Grid's own a11y behaviour is verified once, in the shared component, not per feature.
- **Open dependency:** licence procurement is unconfirmed (recorded as DW-08). This blocks Phase 4 (Angular Foundation), not Phase 0 or 1.
- The wrapper adds indirection that will occasionally feel like friction when a feature wants a niche AG Grid capability. That friction is the mechanism working as intended; the escape hatch is to extend the wrapper's contract, not to bypass it.

**Alternatives Considered:** Angular Material table + CDK virtual scroll — no licence cost, but would mean building grouping, column management, and saved views by hand; rejected as a larger long-term cost than the licence. PrimeNG DataTable — rejected; a third component library for one capability.

---

## ADR-021: RFC 7807 Problem Details as the API Error Contract

**Status:** Accepted

**Context:** `knowledge/05-api-standards.md` specified a `{"success": false, "error": {"code", "message"}}` envelope. `knowledge/09-engineering-standards.md`, `docs/data/10-api-design-guidelines.md` §12, `docs/data/18-error-catalog.md`, and `docs/implementation/engineering-standards.md` all specified RFC 7807 Problem Details. Four sources to one, and the detailed error catalogue — the document an implementer would actually work from — was on the RFC 7807 side.

**Decision:** **RFC 7807 Problem Details, extended with `error_code`**, is the single error contract for every endpoint, with `Content-Type: application/problem+json`. `docs/data/18-error-catalog.md` is the authoritative catalogue of error codes. `knowledge/05-api-standards.md` is corrected.

**Consequences:**
- A documented internet standard rather than a bespoke envelope: HTTP status carries the category, `type`/`title`/`detail`/`instance` carry the human- and machine-readable context, and the `error_code` extension carries the platform-specific code that clients branch on.
- Success responses return the resource directly, not wrapped in `{"success": true, "data": ...}` — the HTTP status already conveys success, and unwrapping a redundant envelope in three clients is pure ceremony.
- Field-level validation failures use the `errors` extension, populated from Pydantic v2 validation output.
- Consistent with `snake_case` JSON naming, already decided in `docs/data/10-api-design-guidelines.md`.

**Alternatives Considered:** The `{success, error}` envelope — rejected; it duplicates information HTTP already carries and is not interoperable with tooling that understands `application/problem+json`.

---

## ADR-022: Azure as Target Cloud, Hosting Topology Deliberately Deferred

**Status:** Accepted (direction) · **Topology and IaC tool: deferred** · *amended by [ADR-027](#adr-027-supabase-as-the-managed-postgresql-host-amends-adr-013-adr-022) (database host)*

> **Amendment note (2026-08-09):** The **database no longer maps to Azure Database for PostgreSQL** — it is hosted on Supabase (ADR-027). Everything else in this ADR stands: Azure remains the target for application hosting, the topology and IaC tool remain deferred, and object storage, secrets and CI/CD map as described below.

**Context:** The superseded deployment document committed to a full Azure topology — App Service Premium v3, Azure Functions, Azure SignalR, Azure SQL Elastic Pool, Bicep IaC — all of which followed from the .NET and SQL Server decisions. With those superseded, the equivalent choices reopen. Committing to a specific topology now, with no running code, no measured load, and no operational experience, would be guessing.

**Decision:** **Azure remains the target cloud.** The specific hosting topology (Azure Container Apps vs App Service vs other container hosting) and the IaC tool (Bicep vs Terraform) are **explicitly deferred** to a dedicated deployment architecture decision, to be taken before production deployment.

Phase 0 establishes only the **Azure-compatible architectural direction**:

- The backend is a containerized ASGI application — deployable to any Azure container host, and identical locally under Docker.
- PostgreSQL maps to Azure Database for PostgreSQL Flexible Server.
- Redis maps to Azure Cache for Redis, serving cache, sessions, rate limiting, and the real-time backplane (ADR-015).
- Object storage maps to Azure Blob Storage (D-40), with per-category containers and short-lived signed URLs.
- Secrets map to Azure Key Vault, accessed by managed identity — never in source control or pipeline variables.
- CI/CD is GitHub Actions.
- Four environments — Dev, QA, Staging, Production — provisioned identically by IaC, differing only in scale and secrets.

**Consequences:**
- Nothing in the application architecture binds to a specific Azure hosting product, so the deferred decision stays genuinely open rather than being pre-empted by implementation.
- Containerization makes local development and production topologically similar from the start, which is worth more at this stage than a committed topology.
- The one constraint the deferral must respect: **WebSocket support and long-lived connections** are required by ADR-015, which rules out any host that cannot sustain them.
- **Recorded as DW-05.** This must be decided before production, and the decision needs its own ADR.

**Alternatives Considered:** Committing now to Container Apps + Terraform — rejected as premature; the trade-offs depend on operational factors (scaling behaviour, cost at real load, team familiarity) that are not yet observable. Cloud-agnostic Kubernetes from day one — rejected as disproportionate operational overhead for a modular monolith and a team of ten.

---

## ADR-023: Background Job Architecture (Conceptual; Library Deferred)

**Status:** Accepted (architecture) · **Library selection: deferred**

**Context:** The superseded backend document assigned scheduled and deferred work to Azure Functions (timer-triggered) and Hangfire (on-demand). Both are .NET/Azure-bound. The workload itself is unchanged and well-specified: refill reminders (D-26), scheduled reports (D-28), complaint SLA breach scanning (D-20), low-stock alerts (FR-IM-04), daily reconciliation prompts (D-31), and notification retries.

**Decision:** Define the architecture; defer the library.

**Architecture:**
- Jobs are **application-layer use cases**, invoked by a worker process — never logic that exists only inside a scheduler. The same use case is callable from an API request, a test, or a job runner.
- The worker is a **separate process from the API**, sharing the same codebase and domain layer, so long-running work never competes with request latency.
- Redis is the broker/queue substrate, consistent with ADR-022's portability goal.
- Every job runs inside a tenant context (ADR-017) — a job that iterates tenants sets the context per tenant, never running unscoped.
- Jobs are **idempotent** and safe to retry; scheduled jobs tolerate double-firing.
- Job outcomes are observable: success/failure rate, duration, and queue depth are first-class metrics (`12-observability.md`), and a scheduled job failing silently is itself an incident — the SLA breach scanner protects a customer-facing guarantee.

**Library selection is deferred** to Phase 2 (Backend Foundation), with a spike over **ARQ** (async-native, Redis-backed, minimal), **Dramatiq** (simple, robust), and **Celery** (mature, heavyweight, largest ecosystem). The decision hinges on async-native ergonomics and operational simplicity at this scale, and does not affect anything designed above. Recorded as DW-06.

**Consequences:**
- The deferral is safe precisely because jobs are use cases: swapping runners changes the invocation shim, not business logic.
- A separate worker process means one more deployable unit and one more thing to monitor — accepted, because the alternative (in-process background tasks) makes API latency hostage to batch work.
- FastAPI's built-in `BackgroundTasks` is suitable only for trivial post-response side effects, never for the scheduled/durable workload above.

**Alternatives Considered:** Cloud-managed scheduling (Azure Functions timers) — rejected for Phase 1; it splits business logic across two runtimes and two deployment models, and binds to a hosting decision ADR-022 deliberately defers. In-process `asyncio` scheduling — rejected; work is lost on restart and duplicated across instances.

---

## ADR-024: Architecture-Boundary Enforcement in Python

**Status:** Accepted

**Context:** ADR-002's modular monolith and the Clean Architecture dependency rule are only real if something enforces them. The superseded design used NetArchTest/ArchUnitNET in CI, explicitly *"not just convention."* That mechanism does not exist in Python, and the risk it mitigated — boundary erosion into a big ball of mud, foreclosing the future extraction path — is unchanged.

**Decision:** Enforce boundaries in CI with **`import-linter`** contracts, complemented by strict `mypy` and targeted tests:

| Rule | Enforced by |
|---|---|
| Domain imports nothing from application, infrastructure, or api | import-linter layered contract |
| Application imports domain only; never infrastructure or api | import-linter layered contract |
| Bounded-context modules do not import each other's internals | import-linter independence contract |
| No SQLAlchemy import outside infrastructure | import-linter forbidden contract |
| No FastAPI import outside the api layer | import-linter forbidden contract |
| Every tenant-scoped model declares `tenant_id` | targeted test over the model registry |
| Cross-tenant reads return nothing | integration test with two seeded tenants |
| Full type coverage at layer boundaries | `mypy --strict` in CI |

These run on every pull request and are merge-blocking, exactly as the architecture tests were in the superseded design.

**Consequences:**
- The dependency rule becomes mechanical rather than a review-time judgement, which is the only way it survives contributor turnover.
- Contracts must be written and maintained alongside the module structure — a real if modest cost, and the direct replacement for what NetArchTest would have provided ready-made (a cost noted honestly in ADR-012).
- Together with Nx `enforce-module-boundaries` on the frontend (ADR-018), both halves of the codebase enforce module isolation the same way, for the same reason.

**Alternatives Considered:** Convention plus code review — rejected on ADR-002's own reasoning; boundary erosion is gradual, individually defensible, and invisible until it is expensive. Custom AST checks — rejected; import-linter already covers the needed contract types.

---

## ADR-025: Polyglot Monorepo Layout (amends ADR-001)

**Status:** Accepted · **Amends:** ADR-001

**Context:** ADR-001's monorepo decision stands. Its physical layout in the superseded folder-structure document did not match the repository: it named the web folder `/dashboard` (the repository has `frontend/`), used .NET solution/project names for the backend, and described a `/docs` sub-structure (`/modules`, `/workflows`, `/requirements`, `/questions`) that never existed.

**Decision:** The confirmed top-level layout is:

```
backend/         FastAPI application (Clean Architecture layers)
frontend/        Nx workspace containing the Angular 22 dashboard application
mobile/          Flutter workspace: customer app, driver app, shared packages
docs/            Detailed specifications
knowledge/       Concise summaries for developers and AI agents
planning/        Current phase and per-feature PLAN/TASKS/STATUS
infrastructure/  Infrastructure as code (created in a later phase)
scripts/         Local dev setup, seed data, code generation
.github/         CI/CD workflow definitions
```

**No existing top-level directory is renamed.** `frontend/` stays `frontend/`. The Nx *application* inside it may be named `dashboard`; the *folder* is not.

**Consequences:**
- Documentation paths now match reality, which is the point — every cross-reference in the architecture set depends on it.
- `infrastructure/`, `scripts/`, and `.github/` do not yet exist and are created in later phases as they acquire content; they are documented here so their location is not improvised.
- The folder-name-vs-app-name distinction is a small deliberate inconsistency, accepted because renaming an existing directory to satisfy a document is the wrong direction of accommodation.

**Alternatives Considered:** Renaming `frontend/` to `dashboard/` for documentation consistency — rejected by explicit decision; the documents were corrected instead.

---

## ADR-026: Code-First OpenAPI Generation, with the Generated Spec as the Frozen Client Contract

**Status:** Accepted

**Context:** `AGENTS.md`, `knowledge/02`, `knowledge/05`, and `docs/implementation/engineering-standards.md` all describe the platform as "OpenAPI First" and state that clients consume typed clients generated from the spec. `docs/data/12-openapi-specification.md` states the opposite as explicitly: *"Code-first, not spec-first"* — Pydantic models and route decorators are the source of truth, and FastAPI generates `/openapi.json`.

These are reconcilable, but the reconciliation was never written down, so an implementer could reasonably have built either workflow.

**Decision:** **Code-first generation; contract-first consumption.**

1. Pydantic v2 models and FastAPI route metadata are the **single source of truth**. No hand-maintained YAML.
2. The generated `openapi.json` is **exported as a build artifact** on every backend build and **committed** to the repository.
3. Clients (Angular, both Flutter apps) generate typed API clients from that committed artifact — never from a running server, never hand-written.
4. A **CI check fails the build if the committed spec differs from the freshly generated one**, so the artifact can never silently drift from the implementation.
5. A change to the committed spec is a **contract change**: visible in the diff, reviewed as such, and subject to the versioning rules in ADR-009.

"OpenAPI first" is therefore true where it matters — no client is written against an unspecified API, and the spec is reviewed before clients consume it. It simply is not hand-authored.

**Consequences:**
- Eliminates the failure mode of spec-first workflows: a hand-maintained document drifting from the code it describes. The CI check makes drift impossible rather than merely discouraged.
- Contract changes become visible in pull-request diffs, which is exactly what "the contract is part of the public interface" requires operationally.
- The discipline lands on **code quality**: route metadata, response models, error responses, and examples must be complete, because they *are* the contract. `docs/data/12-openapi-specification.md` §2–6 defines those conventions.
- **Cost:** designing an API means writing Pydantic models rather than sketching YAML. In practice this is a fair trade, since the models are needed regardless.

**Alternatives Considered:** True spec-first (author YAML, generate server stubs) — rejected; it fights FastAPI's design, and the drift risk it introduces is worse than the design-discipline benefit it offers. Generating clients from a running server — rejected; makes client builds depend on a live environment and leaves no reviewable contract artifact.

---

## ADR-027: Supabase as the Managed PostgreSQL Host (amends ADR-013, ADR-022)

**Status:** Accepted · **Amends:** ADR-013 (engine unchanged, host named), ADR-022 (database no longer maps to Azure)

**Context:** ADR-013 chose PostgreSQL and ADR-022 named Azure as the target cloud, expecting the database to map to Azure Database for PostgreSQL Flexible Server — while deliberately deferring the *application* hosting topology. A Supabase project has since been provisioned (`ayqphthelemlnbtnknkp`) and its MCP server added at project scope.

Supabase is a platform, not only a database host: it bundles Auth, Storage, Realtime, Edge Functions and its own migration tooling, each of which overlaps a decision this project has already made. Adopting it wholesale would supersede ADR-012, ADR-015, D-37/D-38 and D-40 and would amount to a re-architecture.

**Decision:** Supabase is adopted as the **managed PostgreSQL host, and nothing more**.

| Concern | Owner | Unchanged ADR |
|---|---|---|
| Database engine and hosting | **Supabase** (managed PostgreSQL) | ADR-013 engine stands; host named here |
| Schema and migrations | **Alembic** | ADR-013 |
| Backend and API | **FastAPI** | ADR-012 |
| Authentication and RBAC | **The platform's own Identity module** | D-37, D-38 |
| Real-time | **FastAPI WebSockets + Redis Pub/Sub** | ADR-015 |
| Object storage | **Azure Blob Storage** | D-40 |
| Background jobs | **Separate worker process, Redis queue** | ADR-023 |
| Application hosting | **Azure**, topology still deferred | ADR-022 |

**Supabase Auth, Storage, Realtime, and Edge Functions are not adopted.** Using them later is a decision requiring its own ADR, because each supersedes a confirmed decision rather than complementing it.

### Two constraints that must hold

These are the failure modes this decision introduces. Both are cheap to respect now and expensive to unpick later.

**1. Alembic is the sole owner of schema.**

Supabase ships its own migration system, a SQL editor, and an MCP `apply_migration` tool. **None of them may be used to change schema.** Two migration systems on one database produce a schema that neither can reliably describe, and the damage surfaces as a failed deploy in an environment nobody was watching.

Practically:
- Every DDL change goes through an Alembic migration, reviewed and applied by the pipeline (ADR-013, `06-database-architecture.md` §10).
- The Supabase SQL editor and the MCP's `apply_migration` are for **reading and diagnosis only**.
- `supabase/migrations/` is not created and must stay absent.

**2. `service_role` must never be the application's connection.**

Supabase issues a `service_role` key that **bypasses Row-Level Security by design**. ADR-017 makes PostgreSQL RLS the backstop that holds when application code is wrong; a connection that bypasses RLS removes that backstop entirely and silently.

Practically:
- The application connects as a **dedicated role that is `NOSUPERUSER` and `NOBYPASSRLS`**, exactly as the local Docker environment already provisions `lpg_app`.
- The `service_role` key and the `postgres` superuser are for migrations and administration only, never for request-path connections.
- A CI check should assert the application's configured role cannot bypass RLS. Recorded as DW-18.

**Consequences:**

- **Verified compatible.** Every extension ADR-013 depends on is available: `pgcrypto` (already installed), `citext`, `pg_trgm`. Note they live in the `extensions` schema on Supabase, not `public`, so migrations must reference them accordingly.
- **`SET LOCAL` was the right call.** Supabase pools connections through Supavisor; transaction-mode pooling is compatible with `SET LOCAL` but not with session-level state. ADR-017 chose `SET LOCAL` for exactly this reason and needs no change — a decision made for one reason paying off for another.
- **Local development is unaffected.** Docker Compose PostgreSQL 17 remains the local environment (`infrastructure/`). Keeping a local database means tests do not depend on network access or a shared remote, and preserves the environment parity Phase 1 established.
- **Vendor exposure is bounded to hosting.** Because only managed Postgres is used, migrating to another managed PostgreSQL is a connection-string change plus a data migration — not a rewrite. That is the entire point of declining the platform features.
- **Options this opens, deliberately not taken now:** `pgmq` and `pg_cron` are available and are plausible alternatives to a Redis-backed job queue (ADR-023); `pg_partman` supports the partitioning path in `06-database-architecture.md` §11; `pgaudit` and `pgtap` are relevant to BR-28 auditing and tenant-isolation testing. Each would need its own decision.
- **Cost:** Supabase's free and lower tiers pause or throttle idle projects, which is fine for development and unsuitable for production. Production tier selection is part of the deferred deployment decision (DW-05).

**Alternatives Considered:**
- **Azure Database for PostgreSQL Flexible Server** — the original ADR-022 expectation. Not rejected on merit; Supabase was provisioned and offers a faster path to a working hosted database. Remains the fallback, and the connection-string-level coupling keeps that fallback cheap.
- **Supabase as a full platform** — explicitly declined. It would supersede five confirmed decisions and reshape Phases 2 and 6, for benefits the project has not established it needs.
- **Supabase for Auth only, alongside the custom Identity module** — declined; two identity systems is worse than either one.

---

## Summary Table

| ADR | Decision | Status |
|---|---|---|
| 001 | Monorepo | Accepted — amended by 025 |
| 002 | Modular monolith (not microservices) | Accepted — amended (FastAPI runtime) |
| 003 | Shared DB, discriminator multi-tenancy | Accepted — amended by 017 |
| 004 | CQRS via in-process MediatR | ⛔ **Superseded by 014** |
| 005 | Azure SQL (not Cosmos DB) | ⛔ **Superseded by 013** |
| 006 | Flutter for both mobile apps | Accepted |
| 007 | Azure SignalR Service | ⛔ **Superseded by 015** |
| 008 | Offline-first Driver App only | Accepted |
| 009 | URL-segment API versioning | Accepted |
| 010 | Server-rendered printing engine | Accepted — amended by 016 |
| 011 | Shared-library accessibility enforcement | Accepted |
| 012 | Python 3.13 + FastAPI backend | Accepted |
| 013 | PostgreSQL primary relational store | Accepted (supersedes 005) — amended by 027 |
| 014 | Application services + explicit cross-cutting pipeline | Accepted (supersedes 004) |
| 015 | FastAPI WebSockets + Redis Pub/Sub | Accepted (supersedes 007) |
| 016 | Python rendering stack for printing | Accepted (amends 010); library deferred |
| 017 | PostgreSQL RLS + repository tenant scoping | Accepted (amends 003) |
| 018 | Angular 22 + Nx under `frontend/` | Accepted |
| 019 | Signals-first + NgRx SignalStore | Accepted |
| 020 | AG Grid Enterprise behind an abstraction | Accepted; licence procurement open |
| 021 | RFC 7807 error contract | Accepted |
| 022 | Azure target cloud; topology deferred | Accepted (direction only) — amended by 027 |
| 023 | Background job architecture | Accepted; library deferred |
| 024 | Python architecture-boundary enforcement | Accepted |
| 025 | Polyglot monorepo layout | Accepted (amends 001) |
| 026 | Code-first OpenAPI, generated spec as contract | Accepted |
| 027 | Supabase as managed PostgreSQL host **only** | Accepted (amends 013, 022) |

## Deferred Decisions

Decisions deliberately left open, each with a defined trigger point:

| Item | Decide by | Reference |
|---|---|---|
| Azure hosting topology (Container Apps vs App Service vs other) and IaC tool (Bicep vs Terraform) | Before production deployment | ADR-022 · DW-05 |
| Background job library (ARQ vs Dramatiq vs Celery) | Phase 2 — Backend Foundation | ADR-023 · DW-06 |
| PDF rendering library (WeasyPrint vs ReportLab) | Phase 17 — Printing | ADR-016 · DW-07 |
| AG Grid Enterprise licence procurement | Before Phase 4 — Angular Foundation | ADR-020 · DW-08 |
| Supabase production tier (lower tiers pause idle projects) | Before production | ADR-027 · DW-05 |

## Review Cadence
ADRs are reviewed at each major phase gate and annually thereafter in production. Superseded decisions are marked **Superseded**, with a link to the new ADR, never deleted — preserving the historical reasoning trail this document exists to provide. The Phase 0 supersessions above are the first application of that policy; the superseded architecture documents themselves are preserved under [`superseded/`](./superseded/README.md).
