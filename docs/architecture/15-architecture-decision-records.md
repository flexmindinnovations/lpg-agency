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

**Status:** Accepted · *amended by [ADR-028](#adr-028-hybrid-ui-component-strategy-primeng-primary-ag-grid-community-default-ag-grid-enterprise-optional-amends-adr-020) (component-library strategy)*

> **Amendment note (2026-08-09):** The core replaceability mechanism decided here — AG Grid encapsulated behind an application-level wrapper in `libs/shared/ui`, feature libraries never importing AG Grid types directly, the licence key never committed — is **unchanged and remains binding**. What changed: AG Grid Enterprise is no longer adopted as "the standard" by default. **AG Grid Community is now the default grid engine**; AG Grid Enterprise becomes an **optional, per-instance upgrade**, enabled only when a documented feature requirement needs an Enterprise-only capability and a licence is available. **PrimeNG is adopted** as the primary Angular UI component library, reversing this ADR's "PrimeNG is not adopted" consequence below. See [ADR-028](#adr-028-hybrid-ui-component-strategy-primeng-primary-ag-grid-community-default-ag-grid-enterprise-optional-amends-adr-020) for the full hybrid decision, the PrimeNG licensing analysis, and the design-token integration requirement. The text below is preserved verbatim as the original decision record.

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
- PostgreSQL is hosted on **Supabase** (amended by ADR-027 — originally expected to map to Azure Database for PostgreSQL Flexible Server).
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

**Status:** Accepted (architecture) · **Library selection: deferred** · *resolved by [ADR-029](#adr-029-arq-as-the-background-job-library-resolves-adr-023s-deferral)*

> **Resolution note (2026-08-09, Phase 2):** The architecture below is unchanged and remains binding. The deferred library selection is resolved: **ARQ**. See ADR-029 for the spike outcome and reasoning.

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

## ADR-028: Hybrid UI Component Strategy — PrimeNG Primary, AG Grid Community Default, AG Grid Enterprise Optional (amends ADR-020)

**Status:** Accepted · **Amends:** ADR-020

**Context:** ADR-020 adopted AG Grid Enterprise as the standard data-grid implementation and, as a direct consequence, dropped PrimeNG: *"With AG Grid for grids and Angular Material + CDK for interaction primitives, it has no remaining role, and a third component library would fragment the design-token implementation."* That reasoning held given a single-library assumption where AG Grid Enterprise covered grids and Material/CDK covered everything else.

The product owner has since confirmed a **valid PrimeNG licence** exists and wants PrimeNG restored as the platform's primary UI component library, with AG Grid narrowed to a data-grid-only role and its Enterprise tier made conditional rather than standard.

**A licence key was found hardcoded in `frontend/apps/dashboard/src/app/app.config.ts`** as an unreferenced constant, during this review — a real, uncommitted secret in a tracked source file. It was removed before it could enter git history, per the same rule ADR-020 itself established for the AG Grid licence key (*"the licence key is supplied as environment configuration, never committed"*). The key decodes (JWT payload, not verified cryptographically here) to a **Community-tier, dev-type** PrimeUI licence issued 2026-07-18, expiring 2027-07-18 — consistent with the free tier, not a paid Commercial licence.

**PrimeNG's licensing model is corrected here, not assumed.** Checked directly against the npm registry and the package's own `LICENSE.md` (`primeng@22.0.0`, `license: "SEE LICENSE IN LICENSE.md"` — not an SPDX-free identifier): current-generation PrimeNG ships under a proprietary **PrimeUI License** with two tiers — a free **Community License** for organisations/individuals meeting PrimeTek's eligibility criteria, and a paid **Commercial License** otherwise. This is **not MIT**, correcting an assumption present nowhere in this repository's committed documentation but worth stating plainly so it is never asserted later. Whether this organisation qualifies for the Community tier is a licensing/eligibility question only the product owner can answer — this ADR does not resolve it, and treats the existing key as unverified with respect to eligibility until confirmed.

**Decision:** Adopt a **hybrid UI component strategy**, replacing ADR-020's single-library standard:

1. **PrimeNG is the primary Angular UI component library** for forms, inputs, overlays, navigation, and general-purpose components.
2. **AG Grid Community is the default complex data-grid engine.** It remains encapsulated behind the existing `libs/shared/ui` wrapper (ADR-020 constraints 1–2 carry forward unchanged).
3. **AG Grid Enterprise is optional**, enabled only per-instance when a documented feature requirement identifies an Enterprise-only capability (server-side row model at scale, range selection, Excel export, pivoting, etc.) **and** a licence is available. Enabling it is a feature-level decision made against a documented requirement, not a platform default.
4. **Angular CDK remains available** for low-level accessibility, overlay, drag/drop, scrolling, and interaction primitives — unchanged from ADR-020/ADR-011.
5. **Angular Material may be used selectively** where it provides a superior primitive or integration not otherwise covered; it is no longer the primary visual component library.
6. **Tailwind CSS v4 remains the layout/utility layer**, unchanged.
7. **Design tokens (`libs/shared/design-tokens`) remain the single source of visual truth.** PrimeNG and AG Grid **must consume the centralized token system wherever their theming APIs allow** — PrimeNG via `@primeuix/themes`' CSS-custom-property-based preset system (which can be bound to the existing token output rather than a separate PrimeNG theme file), AG Grid via its CSS custom-property theming API (Theming API, not legacy Sass themes). **No vendor-specific styling values may be hardcoded into application styles** — the same rule §7 of `04-frontend-architecture.md` already applies to raw hex/px values applies equally to PrimeNG- or AG Grid-specific tokens.

**Version selected:** `primeng@22.0.0`, whose peer dependencies (`@angular/core`, `@angular/cdk`, `@angular/common`, `@angular/forms`, `@angular/router`, `@angular/platform-browser`, all `^22.0.0`) match the installed Angular 22.0.8 / Angular CDK 22.1.1 exactly. Paired with `@primeuix/themes@3.0.0` for token-based theming and `primeicons` for iconography. **Not yet installed** — this ADR authorises the direction; the dependency addition, theme-token wiring, and first PrimeNG component happen in Phase 4 (Angular Web Foundation) implementation, not in Phase 0/1 documentation work.

**Consequences:**
- **The AG Grid wrapper's replaceability guarantee, and its constraints, are unaffected.** Constraint 2 from ADR-020 (feature libraries never import AG Grid types directly) is exactly what makes narrowing AG Grid's default tier from Enterprise to Community a two-line configuration change rather than a rewrite — the abstraction is doing the job it was built for.
- **DW-08 is resolved, not merely deferred.** ADR-020 recorded AG Grid Enterprise licence procurement as an unconfirmed dependency blocking Phase 4. Since AG Grid Community — not Enterprise — is now the default, there is no standing licence-procurement blocker. Enterprise licence procurement becomes a **per-feature decision**, triggered only if a future feature's documented requirements genuinely need an Enterprise-only capability, evaluated at that time against the actual requirement rather than provisioned speculatively.
- **A third component library returns, deliberately.** ADR-020's fragmentation concern is addressed structurally, not dismissed: the token-consumption requirement (Decision point 7) is what prevents PrimeNG and AG Grid from each carrying their own hardcoded visual language. If either library's theming API cannot express a given token faithfully, that is a real constraint to document per-component when it is hit — not a reason to hardcode around it.
- **Accessibility enforcement is unaffected.** ADR-011's shared-library concentration strategy still applies: PrimeNG components used across features should be wrapped or configured centrally in `libs/shared/ui` where they carry accessibility-relevant behaviour, the same way the AG Grid wrapper already concentrates grid accessibility. `docs/architecture/11-accessibility-strategy.md` had already anticipated PrimeNG's possible return in its third-party component audit language — that anticipation is now realised rather than contradicted.
- ~~PrimeNG licence eligibility remains an open item for the product owner, not engineering.~~ **DW-22 resolved 2026-08-09.** The Community-tier key found in source is dev-type; PrimeTek's published criteria (`primeui.dev/licenses/community`) require **all** of: under $1M USD annual gross revenue, fewer than 5 developers (4-seat cap), fewer than 10 total employees, and never more than $3M USD in outside funding. The product owner confirmed fewer than 5 developers and $0 annual revenue — both comfortably within threshold, and the two figures most likely to disqualify a small team. Employee count and outside-funding history were not separately itemised but are not in tension with either confirmed figure. Community-tier is treated as eligible; licenses run 12 months, renewable at no cost by reconfirming eligibility, with a 30-day grace period after expiry — worth reconfirming at each renewal, not just once.
- **Licence key handling mirrors AG Grid's existing rule exactly.** Whichever tier applies, the PrimeNG licence key is supplied as build-time environment configuration from the secret store and is **never committed** — the same constraint ADR-020 established for AG Grid, now applied consistently to both vendor licences. The exact PrimeNG API for supplying a licence key at bootstrap (a provider function vs. an environment-read at app init) was not confirmed against current PrimeNG docs during this review and must be verified before Phase 4 wiring, not assumed.
- **No functional or test-affecting change to the existing frontend.** `frontend/libs/shared/ui/src/lib/data-grid/data-grid.component.ts` and its AG Grid Community usage are unchanged; this ADR is a documentation and direction change only. Phase 2 remains not started.

**Alternatives Considered:**
- **Leave ADR-020 as-is (AG Grid Enterprise standard, PrimeNG dropped)** — rejected; the product owner has a business reason (an existing licence, a preference for PrimeNG's component breadth) that the original single-library assumption didn't anticipate.
- **Adopt PrimeNG for everything, including data grids (`p-table`/`p-treeTable`), dropping AG Grid entirely** — rejected; AG Grid's Community tier already meets the documented grid requirements (`docs/ui/14-data-grid-guidelines.md`) more directly for grouping/virtualization-at-scale than PrimeNG's table components, and the existing wrapper investment (with its 9 passing tests proving real AG Grid Community rendering) would be discarded for no functional gain.
- **Make AG Grid Enterprise a blanket default again "just in case"** — rejected; that reintroduces DW-08's speculative procurement dependency for capabilities no current feature has requested, which is exactly what the Community-default reverses.
- **Skip the design-token consumption requirement and let PrimeNG ship its own default theme** — rejected; it would reintroduce the visual fragmentation ADR-020 originally worried about, just with PrimeNG's default look instead of a hand-rolled one.

> **Implementation note (2026-08-09, same day, Phase 1 close-out — T-68):** The "Not yet installed" line above is superseded. PrimeNG is installed (`primeng@22.0.0`, `@primeuix/themes@3.0.0`, `primeicons@8.0.0`) and wired: `LpgPrimeNgPreset` (`libs/shared/design-tokens/src/lib/primeng-preset.ts`) binds every PrimeNG semantic/primitive token to the existing design-token custom properties, `providePrimeNG()` is registered in `apps/dashboard/src/app/app.config.ts`, and the previously-open "exact PrimeNG API for supplying a licence key" question is resolved: `providePrimeNG({ license })`, a plain string input, fed from a git-ignored `prime-license.ts` (template: `prime-license.example.ts`) — never committed, absence never fails the build. Brought forward from Phase 4 to Phase 1 close-out on explicit instruction, not a phase-ordering change to this ADR's own reasoning. **While implementing this, a pre-existing Phase 1 defect was found and fixed** (unrelated to PrimeNG's own correctness): `styles.css` and the AG Grid wrapper referenced `var(--semantic-color-*)`-prefixed custom properties the token generator has never emitted (real names are the bare `--color-*`/`--spacing-*`/`--radius-*`); every such reference had resolved to nothing since the original Phase 1 commit. Full record: [`planning/features/01-repository-foundation/TASKS.md`](../../planning/features/01-repository-foundation/TASKS.md) (T-68) and [`STATUS.md`](../../planning/features/01-repository-foundation/STATUS.md).

---

## ADR-029: ARQ as the Background Job Library (resolves ADR-023's deferral)

**Status:** Accepted · **Resolves:** ADR-023's deferred library selection (DW-06)

**Context:** ADR-023 fixed the background-job *architecture* — jobs as application-layer use cases, a separate worker process, Redis as the broker, per-tenant context, idempotent/retry-safe — and deferred only which library runs it, pending a Phase 2 spike over three candidates: **ARQ** (async-native, Redis-backed, minimal), **Dramatiq** (simple, robust), **Celery** (mature, heavyweight, largest ecosystem). The decision was scoped to hinge on "async-native ergonomics and operational simplicity at this scale."

That framing turns out to answer itself once stated precisely. Every other piece of this backend is async-first and non-negotiably so: FastAPI, SQLAlchemy 2.x's async engine, asyncpg, the Redis client, the WebSocket/Pub/Sub real-time layer (ADR-015). A job library whose own execution model is synchronous forces one of two costs onto every job: wrapping each task body in `asyncio.run()` (a new event loop per job, unable to share connection pools with the rest of the process) or adopting a sync ORM/driver path solely for jobs (a second persistence stack to maintain). Neither is "operationally simple" at this scale; both are exactly the kind of friction ADR-012 already paid down once by choosing an async stack throughout.

**Decision:** **ARQ** is the background job library.

| Candidate | Execution model | Broker | Verdict |
|---|---|---|---|
| **ARQ** | Native `asyncio` — a job is `async def job(ctx, ...)`, run directly on the event loop | Redis (already committed, ADR-015) | **Selected** |
| Dramatiq | Threads/processes calling sync task functions | Redis or RabbitMQ (would add a broker if not Redis) | Rejected — sync-first; async work needs a wrapper per task |
| Celery | Prefork worker pool, sync-first, with an async story that exists but is not its native model | Redis, RabbitMQ, or others | Rejected — heaviest operationally (broker + optional result backend + worker pool tuning) for a benefit (ecosystem maturity, exotic routing) this platform's job list doesn't need |

Concretely: ARQ jobs are plain `async def` functions receiving a context dict, run on ARQ's own asyncio event loop in the worker process — no thread pool, no process pool, no second connection-pooling story. It depends on nothing but `redis` (already a hard dependency) and integrates directly with the same `asyncpg`/SQLAlchemy async session machinery every other part of this codebase already uses. Scheduled (cron-style) jobs are a first-class ARQ feature, covering the Refill Reminder / Scheduled Report / SLA Breach Scanner / Low Stock Alert / Reconciliation Reminder triggers from ADR-023's job table without an additional scheduler process.

**Consequences:**
- **No new infrastructure dependency.** ARQ's broker is the same Redis instance already serving cache, sessions, rate limiting, and the real-time Pub/Sub backplane — consistent with ADR-015's "no new managed service" reasoning, extended here to jobs.
- **A job function looks like every other function in this codebase** — `async def`, awaiting the same repositories, the same Unit of Work, the same tenant-scoping seam (ADR-017). There is no second calling convention for background code to learn.
- **Smaller ecosystem than Celery.** Accepted deliberately: the job list ADR-023 documents (six triggers, all in-house) does not need Celery's routing/canvas/multi-broker breadth, and that breadth is exactly the operational surface area this decision avoids paying for.
- **Worker process is still separate from the API** (ADR-023 unchanged) — `arq.worker.run_worker` is its own entry point, deployed and scaled independently.
- **No business job is implemented by this decision.** Phase 2 delivers the worker skeleton and the job-function contract (tenant-scoped, idempotent, observable, retry-safe); the six real jobs arrive with the phases that need them.

**Alternatives Considered:**
- **Dramatiq** — genuinely close second; simpler operationally than Celery. Rejected on the async-mismatch grounds above — its actor model expects synchronous callables, and this platform has no synchronous data-access path to hand it.
- **Celery** — rejected; the most mature option, but its operational surface (broker + optional separate result backend + prefork worker tuning + a sync-first execution model requiring `asgiref`-style bridging for async work) is disproportionate to six well-specified, in-house jobs run by a small team, and duplicates infrastructure ADR-015 already committed to (Redis) if a different broker were chosen for Celery's sake.
- **FastAPI `BackgroundTasks`** — not a candidate; ADR-023 already rejected it for anything beyond trivial post-response side effects, since it has no persistence, no retry, and dies with the worker process.
- **Cloud-managed scheduling (Azure Functions timers)** — rejected on ADR-023's original grounds: splits business logic across two runtimes and binds to a hosting decision ADR-022 deliberately still defers.

---

## ADR-030: S3-Compatible File Storage Port, MinIO for Every Environment That Exists Today

**Status:** Accepted

**Context:** D-40 requires cloud object storage for KYC documents, delivery photos, signatures, and invoices. `docs/architecture/13-deployment.md` had already sketched the shape — object storage sits behind a port, and "local development uses Docker Compose with PostgreSQL, Redis, and a MinIO-compatible object store, so local and deployed topologies stay structurally similar" — but nothing had been built. Phase 3 (`planning/features/03-shared-infrastructure/`) closes it.

The complication: `13-deployment.md` also names **Azure Blob Storage** as the illustrative production target, but hosting topology itself is explicitly undecided (ADR-022, "Azure hosting topology + IaC tool... Before production"). Azure Blob does not speak the S3 protocol natively. Building an Azure-SDK-specific adapter now would mean committing engineering effort to a vendor nobody has actually chosen yet — the same speculative-commitment problem ADR-022 itself was written to avoid.

**Decision:** A vendor-agnostic `FileStorage` protocol (`application/common/ports.py` — `upload`, `download`, `delete`, `exists`, presigned `url`), with **one concrete adapter today**: `S3CompatibleFileStorage` (`infrastructure/storage/client.py`), built on `aioboto3` against **MinIO**. MinIO runs in Docker Compose for local and UAT, exactly as `13-deployment.md` already anticipated. Bucket existence is ensured idempotently on connect (`head_bucket` → `create_bucket` on miss), mirroring the `CREATE EXTENSION IF NOT EXISTS` pattern the database migrations already use — a developer starting from a fresh MinIO volume needs no manual setup step.

**No production adapter is built yet.** `.env.prod.example`'s storage section is deliberately empty with a comment explaining why — filling it in against a real bucket before the hosting-topology decision is made would be the same premature-commitment problem restated. Whatever gets chosen (Azure Blob via its own SDK, or an S3-compatible managed service that lets `S3CompatibleFileStorage` be reused as-is) is a second, later adapter behind the same port.

**Consequences:**
- **The port, not the vendor, is the actual deliverable.** Domain and application code that will eventually call `FileStorage` (Phase 8 KYC, Phase 11 delivery photos, Phase 13 invoices) depend only on the protocol — a future production adapter is additive, not a rewrite.
- **`aioboto3` matches the codebase's async-everywhere posture** (ADR-029's reasoning applied here too) — no sync boto3 call wrapped in a thread pool, no second connection-pooling story.
- **MinIO is a genuinely real backing service for tests, never a mock** — `tests/integration/test_file_storage.py` uploads, downloads, and fetches a real presigned URL over HTTP against a real container, the same "real PostgreSQL/Redis, never SQLite/a mock" discipline `docs/implementation/testing-strategy.md` already establishes for the rest of the backend.
- **Presigned URLs, not proxied downloads, are the retrieval path** — the API process never streams object bytes for anything but small/cached content, keeping large files off its own bandwidth and memory.
- **A new discovered-work item, not a silent gap:** production object storage remains unresolved until hosting topology is decided (added to the Deferred Decisions table below, alongside ADR-022 itself).

**Alternatives Considered:**
- **Build the Azure Blob adapter now, since `13-deployment.md` already named it** — rejected; hosting topology is explicitly still open, and Azure Blob's SDK is a different API surface than S3, meaning this work would be thrown away if a different vendor (or a different cloud entirely) is eventually chosen.
- **A local filesystem adapter for dev/test instead of MinIO** — rejected; `13-deployment.md` had already committed to MinIO specifically so local and deployed topologies "stay structurally similar," and a filesystem adapter would test a code path (`open()`/`os.path`) the production adapter never uses, which is exactly the gap real-backing-service testing exists to close.
- **Defer the port itself until a vendor is chosen** — rejected; the port is cheap to define and unblocks every future business module's design (KYC upload, delivery photo capture) from waiting on an infrastructure decision that is genuinely unrelated to their own logic.

---

## ADR-031: Brand Colour Moves from Blue to Deep Forest Green

**Status:** Accepted

**Context:** The platform's `color-action-primary` had been blue (`primitive.color.blue.600`/`.400`) since Phase 1, chosen as a conventional, accessible default rather than a deliberate brand choice — nothing in `docs/business/` or the SRS specifies a brand colour. Ahead of Phase 4 (Angular Web Foundation), the product owner shared design/colour-palette inspiration (a set of high-saturation pairings — Aureolin/Bistre, Cream Vanilla/Cherry Cola, Lime Green/Vibrant Red, Butter/Green) and asked for a refreshed direction appropriate to a B2B gas agency platform.

Most of the supplied palettes were rejected on concrete, product-specific grounds, not taste:
- **Vibrant Red / Cherry Cola as a brand colour** would collide with `color-status-danger`, which is already red — in a platform tracking flammable-gas cylinders, a primary "Create Order" button and a safety/leak alert reading as the same signal is a real defect, not a style question.
- **Lime Green / Aureolin yellow** fail WCAG AA contrast as button fills or text without heavy darkening, and are fatiguing across an 8-hour dispatcher shift on a screen that is stared at all day, unlike a marketing hero banner.
- **Butter cream + deep forest green** was the one pairing that is genuinely enterprise-usable as supplied — the green has real contrast headroom and reads as stable/trustworthy rather than loud.

**Decision:** `color-action-primary` (and its hover/focus-ring derivatives) moves to a new primitive scale, `forest` — a deep, deliberately blue-shifted green, distinct from `primitive.color.green` (kept, unchanged, for `color-status-success`). A new `cream` primitive and a new semantic pairing, `color-highlight-background`/`color-highlight-color` (forest + cream), covers active/selected states such as the active sidebar item — the pairing the supplied inspiration actually showed, applied to a highlight role rather than as a default surface. Full values and contrast ratios: `docs/ui/10-color-system.md` §2–3.

High-contrast mode's `color-action-primary` **stays pure blue** (`hcBlue`, unchanged) rather than switching to a high-contrast green. High-contrast mode exists specifically to serve low-vision and colour-vision-deficient users; pure blue is the better-tested, more universally distinguishable choice on the protanopia/deuteranopia (red-green) confusion axis, independent of whatever the brand hue is in light/dark mode.

**Consequences:**
- **Zero code changes outside `design-tokens/tokens.json`.** The PrimeNG preset (`primeng-preset.ts`) derives its entire palette from `var(--color-action-primary)` via `color-mix()`, and the AG Grid wrapper and every component style reference semantic/component tokens, never a hex value directly — this is the token architecture (ADR — see `04-frontend-architecture.md` §7) paying for itself exactly as intended. Verified live: light/dark/high-contrast themes, PrimeNG buttons/tabs/dialog, all correct with no component touched.
- **Blue is no longer overloaded.** It previously meant both "brand" and "info" simultaneously; it now means `color-status-info` only, which is a clearer signal, not a loss.
- **Tenant branding (D-31, `10-color-system.md` §5) is unaffected.** A tenant's own configured primary colour already overrides only `color-action-primary` and its derived states, never status/surface/text tokens — the platform default changing brand colour doesn't touch that mechanism.
- **The blue-shift in `forest` is a deliberate colour-vision-deficiency mitigation, not just an aesthetic choice** — a green with a higher blue channel sits further from the pure red/green confusion line than a yellow-leaning "grass" green would, making it more distinguishable from `color-status-danger` (red) for red-green colour-blind users even though both are nominally "green-ish" and "reddish" respectively.

**Alternatives Considered:**
- **Adopt one of the high-saturation palettes as supplied** — rejected per the Context section above; each has a concrete accessibility or semantic-collision problem for this specific product, not a subjective taste objection.
- **Use `primitive.color.green` (already existing, used for `color-status-success`) as the new brand colour too** — rejected; a brand button and a success toast in the identical hue is the same collision problem red-as-brand would have created, just with the other status colour.
- **Keep blue** — rejected; the product owner explicitly asked for a refreshed direction, and blue was never a deliberate brand choice to begin with, just Phase 1's accessible default.

---

## ADR-032: `ng-openapi-gen` for the Generated Angular API Client

**Status:** Accepted

**Context:** ADR-026 established the contract discipline — Pydantic/FastAPI generate `openapi.json`, it is committed as a build artifact, and clients generate typed code from *that* artifact, never hand-written or generated from a live server — but never named a specific generator tool for the Angular client. Phase 4 (`docs/implementation/roadmap.md`'s "generated API client" line item) closes that gap. At the time of this decision, the committed spec (`backend/openapi/openapi.json`, OpenAPI 3.1.0) describes only the two health-check endpoints — no business API surface exists yet (Phase 6+).

**Decision:** **`ng-openapi-gen`** (config: `frontend/ng-openapi-gen.json`, script: `npm run generate:api-client`), generating into `libs/shared/data-access/src/lib/generated/` (re-exported from the library's public `index.ts`, alongside the hand-written interceptors already there).

The deciding factor: `ng-openapi-gen`'s generated functions accept an injected `HttpClient` and call `http.request(...)` directly — meaning every generated call flows through the *same* Angular `HttpClient` pipeline as everything else in the app, including `correlationIdInterceptor` and `problemDetailsInterceptor` (already registered in `app.config.ts`). A generator that ships its own `fetch`/`axios` instance (several popular ones do) would bypass both silently — a generated call would carry no correlation ID and would not translate RFC 7807 error responses the way every other call in this codebase does.

**Not wired into `app.config.ts` yet.** `provideApiConfiguration(rootUrl)` needs a real backend base URL, and this codebase currently has no established pattern for supplying one from the Angular app (no `environment.ts` files, no dev-server proxy config) — inventing one now, for a client with no consumer, would be guessing at frontend deployment architecture that hasn't been decided. That wiring belongs with whichever phase makes the first real API call (Phase 6, most likely), when there is an actual base URL (and CORS/proxy story) to configure against.

**Consequences:**
- **Regeneration is a script, not automatic.** `npm run generate:api-client` must be re-run after a backend contract change, same manual step the token pipeline (`node scripts/generate-tokens.mjs`) already requires — deliberately not wired into a pre-build hook, so a spec change is a visible, reviewable diff rather than something that silently changes on every install.
- **Generated code is committed**, matching the same philosophy ADR-026 applies to the spec itself: `libs/shared/data-access/src/lib/generated/**` is real, checked-in code (`/* DO NOT EDIT */`), excluded from ESLint and Prettier (it is not held to hand-written-code style rules) but still reviewed in diffs when it changes.
- **Currently generates almost nothing** — 3 models and 1 service function, for the two health endpoints. That is expected, not a shortfall of this decision; the tool and the wiring are proven correct now, cheaply, against a real (if small) spec, rather than deferred until a large business API surface makes a wrong tool choice expensive to unwind.

**Alternatives Considered:**
- **`@hey-api/openapi-ts`** — actively maintained, generates a modern client, but defaults to its own `fetch`-based client rather than Angular's `HttpClient`; making it interceptor-compatible would mean writing and maintaining a custom Angular `HttpClient` adapter for it. Rejected in favour of a generator that is `HttpClient`-native by default.
- **`openapi-typescript`** — generates types only, no request functions. Rejected; it would still require hand-writing every service method, which is most of the work a generator exists to remove.
- **Generating from a live running server instead of the committed spec** — rejected outright; ADR-026 already settled this, and doing otherwise here would quietly reopen a decision this ADR depends on staying closed.

---

## ADR-033: Angular `fileReplacements` for Frontend Environment Configuration (resolves ADR-032's deferral)

**Status:** Accepted

**Context:** ADR-032 generated the API client but deliberately left it unwired, since no frontend environment-config pattern existed yet and inventing one for a client with no consumer would have meant guessing at deployment architecture. That gap is now being closed directly (ahead of the phase originally expected to need it), so the generated client can be exercised end-to-end as soon as a real endpoint exists.

**Decision:** Use Angular's own `fileReplacements` mechanism (`@angular/build:application`'s `production` build configuration in `apps/dashboard/project.json`), not a runtime-fetched config file or a bespoke injection token.

- `apps/dashboard/src/environments/environment.model.ts` — the shared `Environment` interface (`production: boolean`, `apiUrl: string`), kept in its own file. It cannot live inside `environment.ts` itself: `fileReplacements` swaps the *entire contents* of `environment.ts` for `environment.prod.ts` in production builds, so a type re-exported from `environment.ts` would vanish under that swap the moment the importing file and the defining file collapsed into the same file (this was caught by a real production build failure — `TS2724` — during implementation, not anticipated up front).
- `apps/dashboard/src/environments/environment.ts` — dev default, `apiUrl: 'http://localhost:8000/api/v1'` (absolute, since the backend's local dev instance runs on its own port, not behind the Angular dev server; the backend's `LPG_CORS_ORIGINS` dev default already allows `http://localhost:4200` for this).
- `apps/dashboard/src/environments/environment.prod.ts` — `apiUrl: '/api/v1'`, a same-origin **relative** path, not a real domain. ADR-022 leaves production hosting topology undecided; a relative path assumes the SPA and API share an origin (directly, or behind a reverse proxy routing `/api/*` to the backend) without committing to infrastructure nobody has chosen yet. Revisit when ADR-022 resolves.
- `app.config.ts` — `provideApiConfiguration(environment.apiUrl)` added to the provider list, alongside the existing `provideHttpClient`/interceptor registration, so every generated client call is configured with the right root URL per build.

**No separate frontend "uat" environment file.** The backend's DEV/UAT/PROD split (ADR-027 era work) is a *database and deployed-instance* split; it does not imply a distinct frontend build target. A frontend "uat" configuration would still point at whatever backend instance is running wherever it's deployed — there is no separate frontend artifact to build until frontend hosting per environment is actually decided. Two configurations (`development`, `production`) match what exists today; a third can be added trivially via the same `fileReplacements` mechanism if a real need appears.

**Why `fileReplacements` over a runtime-loaded `config.json`:** a build-time swap keeps the API base URL known and typed at compile time, requires no extra network round-trip before the app can make its first real call, and is the mechanism Angular ships and documents for exactly this purpose — no bespoke loader to write or maintain. The tradeoff (a rebuild is required to change the URL) is acceptable: this codebase already rebuilds per environment for other reasons (this is a monorepo with backend/frontend versioned together, not a "build once, promote the same artifact" pipeline).

**Consequences:**
- Verified both ways: `nx build dashboard --configuration=development` embeds `http://localhost:8000/api/v1` in the output bundle; `nx build dashboard --configuration=production` embeds `/api/v1` with no trace of the dev URL. Production bundle size (647.67kb) stays under the 660kb budget set in ADR-028-era work.
- `Environment`'s split into its own file is a small extra indirection future contributors need to know about — documented in the doc-comment on `environment.model.ts` itself, not just here.
- The generated API client (ADR-032) is now live end-to-end (configured, injectable, interceptor-covered) even though it still only has health-check endpoints to call — same "prove it cheaply now" reasoning ADR-032 already applied to the generator choice itself.

**Alternatives Considered:**
- **Runtime-fetched `assets/config.json`** — would allow changing the API URL without a rebuild (useful for a "build once, deploy many" pipeline). Rejected for now: this monorepo doesn't have that pipeline, and it adds an async load gate before the app can be considered configured, for a benefit this project doesn't currently need. Revisit if ADR-022's eventual hosting story turns out to need it.
- **A single environment file with runtime `window.location`-based branching** — rejected; it would make production behaviour depend on where the app happens to be loaded from rather than on an explicit, reviewable build configuration.

---

## ADR-034: SQLCipher-Encrypted Drift via `package:sqlite3`'s Build-Hook Source Selection (implements 05-mobile-architecture.md §7)

**Status:** Accepted

**Context:** Phase 5 (Flutter Application Foundations) closes the one concrete gap left in `mobile/packages/local_storage`: `05-mobile-architecture.md` §7 and ADR-006/ADR-008 already fixed the requirement — the Driver App's on-device database must be Drift/SQLite, encrypted at rest via SQLCipher — but no implementation existed, only a `LocalDatabase` interface and a `NoopLocalDatabase` placeholder with a doc comment saying, correctly, "a no-op implementation used until Drift is wired in." The sync queue and conflict resolution that also live in `05-mobile-architecture.md` §3 are explicitly **not** part of this: `local_storage`'s own doc comment scopes those to Phase 11, once the Driver App has real offline features to drive them, and this ADR does not build them — the schema added here is one foundation table, not business data.

**A real ecosystem trap surfaced during implementation, not anticipated up front:** the obvious dependency, `sqlcipher_flutter_libs`, resolves today to version `0.7.0+eol` — its own README states plainly that "starting from version 0.7.0, this package no longer does anything," because `package:sqlite3` moved from bundling native libraries via Flutter asset bundling (the `0.6.x`-era mechanism `sqlcipher_flutter_libs` patched into) to Dart's newer build-hooks system for `sqlite3` v3.x, which `drift: ^2.34.3` now requires (`sqlite3: ^3.4.0`). Downgrading to the old `sqlite3` v2.x + `sqlcipher_flutter_libs` v0.6.x combination to dodge this was considered and rejected — it would mean pinning `drift` itself to a stale major version, trading one ecosystem risk for a worse one (an unmaintained core dependency).

**Decision:** Use `package:sqlite3`'s build-hook `source: sqlcipher` selection instead — declared as a `hooks.user_defines` block in **both** `local_storage/pubspec.yaml` (so the package's own tests exercise it) and `driver_app/pubspec.yaml` (hooks resolve against the root package of whatever is actually being built, so the app declaring it is not optional):

```yaml
hooks:
  user_defines:
    sqlite3:
      source: sqlcipher
```

`DriftLocalDatabase` (`local_storage/lib/src/drift_local_database.dart`) wraps a Drift `NativeDatabase.createInBackground`, setting `PRAGMA key = "x'<hex>'"` in the `setup` callback. The 256-bit key is generated once with `Random.secure()` and held in platform secure storage (Keychain/Keystore) via `flutter_secure_storage` — never written to disk in plaintext, never sent to the server. `loadEncryptionKey` and `resolveFile` are injectable constructor parameters (defaulting to secure storage and `path_provider`'s app-support directory respectively), specifically so unit tests exercise the real SQLCipher-encrypted file on a real temp directory without touching a platform channel.

**Verified, not assumed** — four tests in `local_storage/test/drift_local_database_test.dart` prove the encryption is real, not just configured:
1. Open/write/read/close with a key round-trips correctly.
2. Data persists correctly across a close-and-reopen with the same key.
3. **The file on disk does not start with SQLite's plaintext magic header** (`"SQLite format 3 "`) and does not contain the inserted plaintext value anywhere in its raw bytes — the actual proof of encryption at rest, not just that a passphrase was supplied somewhere.
4. **Opening the same file with the wrong key fails** — surfaced a genuine SQLCipher HMAC page-decryption failure (`hmac check failed for pgno=1`), the real cryptographic signal, not a mocked one.

**A real bug found and fixed along the way:** the first version of `open()` let a failed sanity-check query (`SELECT 1`, used to fail loudly on a bad key rather than lazily on some unrelated later call) leave the `NativeDatabase.createInBackground` background isolate running, orphaned, still holding its file handle open — the wrong-key test above kept failing its cleanup step until this was fixed by explicitly closing the executor on that failure path before rethrowing. Left unfixed, a wrong/corrupted key on a real device would have leaked an isolate and a file lock on every failed unlock attempt, not just in tests.

**Consequences:**
- **The generated Drift code (`app_database.g.dart`) is committed**, not gitignored — a `.gitignore` exception was added specifically for it. `.github/workflows/mobile-ci.yml` has no `build_runner` step; without committing the generated file, a fresh checkout wouldn't compile at all. This matches the same "generated code is committed" philosophy ADR-026/ADR-032 already apply on the backend (OpenAPI spec) and frontend (Angular API client) — not a new precedent, an extension of an existing one.
- Verified locally (Windows, `flutter test`) for `local_storage` and `driver_app` (wired via a Riverpod provider, opened in `main()` before the first frame — see `driver_app/lib/main.dart`). **Not yet verified on the `ubuntu-latest` CI runner** (`.github/workflows/mobile-ci.yml`) — the hooks mechanism worked locally without any experimental flag being explicitly enabled, but Linux is a different platform for the underlying binary the hook downloads; the next CI run of this change is the actual confirmation, and this line should be removed once it goes green.
- The Customer App does **not** get `DriftLocalDatabase` — per ADR-008, it uses simple cache-and-refresh, not offline-first, and has no `local_storage` dependency to begin with.
- `SchemaMetadata`, the one table added, is a foundation table only (a key/value pair), not a preview of the real Phase 11 schema — deliberately, to keep this phase infrastructure-only, matching how Phase 2 built one illustrative repository rather than real business tables.

**Alternatives Considered:**
- **Pin `sqlite3` to v2.x + `sqlcipher_flutter_libs` v0.6.x** — rejected: forces pinning `drift` to a stale major version too, and the old Flutter-asset-bundling mechanism is exactly what the ecosystem has moved away from.
- **`source: sqlite3mc`** (SQLite3MultipleCiphers) instead of `source: sqlcipher` — a real, more permissively-licensed alternative the same hook supports, and one that even offers an SQLCipher-compatible cipher mode. Rejected only to keep fidelity with `05-mobile-architecture.md` §7's explicit wording ("SQLCipher"); worth reconsidering if SQLCipher's licensing (BSD with a commercial option; the bundled build links OpenSSL) ever becomes a real constraint.
- **Full Dart native-assets/hooks experimental flag path** (`flutter config --enable-native-assets`, custom source builds) — unnecessary; the pre-built `source: sqlcipher` binaries the hook downloads already cover this project's target platforms without any custom compilation.

---

## ADR-035: JWT (RS256, `pyjwt[crypto]`) and Argon2id for Phase 6 Authentication, with SECURITY DEFINER Functions Resolving Tenant Before Auth

**Status:** Accepted

**Context:** Phase 6 replaces Phase 2's interim `HeaderTenantResolver` (never a security boundary, never wired to a reachable endpoint) with real authentication. `17-api-security.md` §1 had left the JWT library as an open "python-jose or PyJWT-equivalent" choice; password hashing wasn't named at all. A harder problem than picking libraries turned out to be architectural: this platform's tenant isolation is PostgreSQL RLS (ADR-017), enforced even against the table owner via `FORCE ROW LEVEL SECURITY`. Login has to look up a user **by email or phone, before any tenant context exists to scope the query by** — a chicken-and-egg problem RLS creates by design.

**Decision — libraries:** `pyjwt[crypto]` (RS256, asymmetric — private key held only by the auth-issuing service) for JWT signing; `argon2-cffi` (Argon2id) for password hashing, cost parameters configurable via `Settings`, not hardcoded. `Sha256TokenHasher` (stdlib, not Argon2) hashes refresh/reset tokens specifically — they're already 256-bit random values, so a fast hash is correct and Argon2 there would only burn CPU with no security benefit.

**Decision — the login lookup problem:** narrowly-scoped **`SECURITY DEFINER`** PostgreSQL functions, one per unique-key-based operation (`auth_find_user_by_email`, `auth_find_user_by_phone`, plus one each for the credential-mutation paths login/refresh/reset actually need — recording a login, rotating a password hash). Each function is owned by the migration/admin role, has `SET search_path` pinned (preventing search-path hijacking), and has `EXECUTE` **explicitly revoked from `PUBLIC`** before being granted only to `lpg_app`/`lpg_app_uat` — PostgreSQL grants `EXECUTE` to `PUBLIC` by default on a new function, which would otherwise let any future role bypass RLS through it. Application code never runs as a role with `BYPASSRLS`; the function itself is the one deliberate, narrowly-scoped seam, not a general escape hatch.

**A non-obvious PostgreSQL behavior this decision depends on, verified directly (`docker exec psql`) before relying on it in code:** `SELECT * FROM function_returning_composite()` always returns exactly one row — an all-`NULL` row on no match, never zero rows. Every repository method built on these functions checks for `NULL`, not for an empty result set.

**Consequences:**
- **Identity use cases (`login.py`, `otp_verify.py`, `refresh_token.py`, `logout.py`, `password_reset.py`) deliberately do not use `UnitOfWork`** — each repository write self-commits via one `SECURITY DEFINER` call, and none of these flows have the multi-aggregate atomicity requirement BR-29's delivery-confirmation example describes. This is a documented divergence from Phase 2's `RenameTenantUseCase` precedent, not an oversight.
- Refresh-token rotation follows the reuse-detection shape `IdempotencyService` already established: presenting an already-rotated token triggers `revoke_all_for_user` — full session revocation, not just rejection of the one reused token.
- Live (non-claims) permission re-checks are reserved for four high-sensitivity actions (`reconciliation:approve`, `credit_notes:approve`, `orders:cancel_approve`, any `super_admin` cross-tenant action) — every other authorization decision trusts the JWT `scope` claim, matching `17-api-security.md` §4's stated "fast, no-database-round-trip" intent.
- **A critical, previously-latent FastAPI bug was found and fixed while building this**, unrelated to auth specifically but discovered only because Phase 6 finally exercised the affected code path end-to-end: `from __future__ import annotations` combined with `TYPE_CHECKING`-only imports of a type referenced inside `Annotated[X, Depends(...)]` breaks `typing.get_type_hints()` for the **whole** function's signature — FastAPI silently falls back to treating every parameter as a required query field (a 422 "Field required" on every dependency, with nothing pointing at the actual cause). Found via a genuine end-to-end HTTP smoke test, not a mocked one. Fixed in every affected router/dependency module (`api/v1/routers/auth.py`, `api/v1/dependencies/identity.py`, `dependencies/tenant.py`) and proactively in `dependencies/unit_of_work.py`, which had the identical latent bug since Phase 2, just never triggered because no router had used it yet. A scoped `ruff` per-file-ignore for `TC001`/`TC002`/`TC003` in these two directories exists specifically so the linter's own "move this behind `TYPE_CHECKING`" suggestion can never silently reintroduce this.

**Alternatives Considered:**
- **`python-jose`** — rejected in favor of `pyjwt[crypto]`, already a transitive dependency via `redis`, actively maintained, and the simpler API for this project's single-issuer RS256 use case.
- **A superuser or `BYPASSRLS` role for the login lookup** — rejected outright: defeats the entire RLS tenant-isolation model (ADR-017) for the sake of one query, and every future query run as that role would inherit the same blanket bypass.
- **Resolving tenant from a subdomain/header before login, then scoping the lookup normally** — rejected for this phase: no subdomain/tenant-bootstrapping mechanism exists yet in either the Dashboard or the mobile apps (the OTP login screens' plain "Tenant ID" text field is the explicit placeholder for this), and email login is meant to work without the client already knowing its tenant.

---

## ADR-036: Shell-Bypass Routing for Unauthenticated Routes — Component-less Parent Route, Not a Route-Aware Shell

**Status:** Accepted

**Context:** `app.html` unconditionally wrapped every route in `<lpg-app-shell>` (`04-frontend-architecture.md`'s "app-agnostic, data-driven" shell design) — correct until Phase 6 needed a route, `/login`, that must render **without** the sidebar/top-bar chrome, and without requiring a session to reach it at all.

**Decision:** `app.html` becomes a bare `<router-outlet />`. A new component-less parent route, `ShellLayout` (`apps/dashboard/src/app/shell/shell-layout.ts`), hosts what `app.html` used to — `<lpg-app-shell [navGroups]="navGroups"><router-outlet /></lpg-app-shell>` — and every existing route becomes its child, gated by a new `authGuard`. `/login` (and its `forgot-password`/`reset-password` siblings, `libs/auth/feature-login`) is declared as a **sibling** route outside `ShellLayout`, and declared **first** in `app.routes.ts`'s route array — Angular's router tries top-level routes in declaration order, and `ShellLayout`'s own catch-all child route (`**` → `NotFound`) would otherwise swallow `/login` before the dedicated sibling route ever got a chance to match, since `ShellLayout`'s parent path (`''`) consumes zero segments as a prefix match.

**Consequences:**
- `AppShellComponent` itself needed **zero changes** — it stays exactly as data-driven and route-agnostic as `04-frontend-architecture.md` already specified; the routing restructure is what changed, not the shell.
- The four shell-chrome tests (skip link, landmarks, theme trigger) that used to target `App` directly now target `ShellLayout` in isolation (`shell/shell-layout.spec.ts`) — `App`'s own spec shrinks to a one-line "renders a bare router outlet" smoke test plus route-structure assertions.
- `authGuard` (`libs/shared/data-access/src/lib/auth.guard.ts`) is the one new thing every existing (and future) route under `ShellLayout` picks up automatically, by virtue of being nested under it — no per-route `canActivate` needed beyond the one on `ShellLayout`'s own route config.

**Alternatives Considered:**
- **Make `AppShellComponent` itself route-aware** (e.g. an `@Input() showChrome` toggled by a route data flag) — rejected: breaks the shell's documented app-agnostic design goal (ADR-018's stated intent of the shell library eventually hosting a second Angular app), and pushes routing knowledge into a `type:ui` library that has no business knowing about routes at all.
- **A `NoShellLayout` no-op wrapper component instead of a bare `app.html`** — considered for symmetry with `ShellLayout`, rejected as unnecessary indirection; a plain `<router-outlet />` at the root needs no wrapping component of its own.

---

## ADR-037: Hand-Written Flutter `api_client` for Phase 6, Deferring Spec-Generation

**Status:** Accepted — explicit revisit trigger set

**Context:** ADR-026/ADR-032 established "generated is the contract" for the Angular Dashboard (`ng-openapi-gen` against the committed OpenAPI spec). Phase 6 needs an equivalent HTTP client for the Flutter apps' ~8 `/auth/*` endpoints, and no Dart/Flutter OpenAPI-generator tooling was evaluated or selected — doing that evaluation for eight endpoints would be disproportionate effort against the actual surface area being covered.

**Decision:** A hand-written, thin `dio`-based wrapper (`mobile/packages/api_client`) — `ApiClient` owns the configured `Dio` instance and a bearer-attach-plus-one-silent-refresh-and-retry interceptor (the mobile counterpart of the Dashboard's `authInterceptor`), and `AuthApi` hand-writes one method per `/auth/*` route, each returning `core`'s `Result<T>` rather than throwing. Request/response shapes (`TokenPair`, `Principal`) are plain hand-written classes mirroring the backend's Pydantic schemas field-for-field, not generated from the OpenAPI spec.

**Consequences:**
- **This ADR is its own revisit trigger**: once a business-domain phase (Customer, Order, Delivery) adds a comparably wide endpoint surface to what the mobile apps consume, re-evaluate Dart/Flutter OpenAPI-generator tooling the way `ng-openapi-gen` was evaluated for Angular — this is a temporary, phase-scoped divergence from ADR-026/032's philosophy, not a reversal of it.
- `ApiClient`'s `getAccessToken`/`refreshAccessToken`/`onSessionExpired` are constructor-injected closures rather than a direct dependency on `auth`'s `TokenStorage`/`AuthRepository` — `auth` depends on `api_client`, never the reverse; `mobile/apps/*/lib/main.dart` is where the two are wired together.
- A real Dio-specific behavior had to be designed around, not just discovered: `dio.fetch()` on retry re-runs the **entire** interceptor chain, including `onRequest` — unlike the Dashboard's RxJS interceptor, where `next()` continues only the remaining chain from the interceptor's own position. `refreshAccessToken`'s implementation must persist the new token to the same store `getAccessToken` reads from **before** returning it, or the retry silently reattaches the stale token. Documented inline in `ApiClient`'s `onError` handler and exercised directly in `api_client_test.dart`.

**Alternatives Considered:**
- **`openapi_generator` (Dart/Flutter OpenAPI generator)** — rejected for this phase only, not permanently: the tooling evaluation and generator-output review it would need isn't justified for eight endpoints; revisit per the trigger above.
- **A single monolithic `AuthService` class combining HTTP calls, token storage, and Riverpod state** — rejected in favor of the three-package/three-layer split (`api_client` → `auth`'s `AuthRepository` → `auth`'s `AuthController`), matching this codebase's existing preference for testable layers over one convenient class (mirrors the backend's application/infrastructure separation).

---

## ADR-038: `ComplianceDocument` as a Standalone Aggregate, Not a Driver/Vehicle Child Entity

**Status:** Accepted

**Context:** The Driver & Vehicle Compliance Pack (`docs/research/feature-gap-analysis.md` D24 · `planning/features/20-regulatory-compliance`) needed to model statutory documents — driving licence, DL hazmat endorsement, TREM card, driver training certificate for a driver; RC, insurance, fitness, PUC, PESO transport licence for a vehicle. Both owner kinds need identical behavior: add, replace (renewal resets verification to pending), verify/reject, list, and a tenant-wide "expiring/expired" query feeding both the dashboard's Expiry filter and the nightly notification cron. Modelling this as a child entity nested inside `Driver` and again inside `Vehicle` would mean two near-duplicate collections, two sets of child-mutation methods on two otherwise-unrelated aggregates, and two repository code paths for what is, behaviourally, one concept with a two-value discriminator.

**Decision:** `ComplianceDocument` is its own `AggregateRoot`, keyed by `(owner_type, owner_id)` rather than living inside `Driver`/`Vehicle`. One domain module (`domain/delivery/compliance_document.py`), one repository (`ComplianceDocumentRepository` / `SqlAlchemyComplianceDocumentRepository`), one table (`delivery.compliance_document`), one set of endpoints reused by both owner kinds (`GET/POST /drivers/{id}/documents` and `/vehicles/{id}/documents` are thin wrappers over the same use cases; `PUT/POST /compliance-documents/{id}` and `GET /compliance-documents` are owner-agnostic). `doc_types_for_owner()` and `REQUIRED_DOC_TYPE_FOR_OWNER` are the only places owner-specific behaviour lives, both pure lookups with no branching duplicated elsewhere.

**Consequences:**
- Registering a driver or a vehicle is a two-step flow (upload the scan → `POST /drivers|vehicles` with the resulting `blob_ref` + required fields) rather than the document being an optional afterthought — `RegisterDriverUseCase`/`RegisterVehicleUseCase` create the owner aggregate **and** its required `ComplianceDocument` (`driving_licence` / `vehicle_rc`) in the same `UnitOfWork`, so a driver or vehicle can never exist in the system without its one mandatory compliance document already on file.
- The frontend gets one shared `lpg-compliance-documents-panel` component (`frontend/libs/shared/ui`) instead of two near-identical ones — it takes a `docTypeOptions` list and owner-scoped uploader/mutator functions as inputs, the same "endpoint-agnostic, functions as inputs" shape `lpg-document-upload` already established.
- The nightly `check_compliance_expiry` cron (Part E) and the dashboard's tenant-wide `GET /compliance-documents?expiry=` filter both query one table with one `owner_type` discriminator column, rather than needing a `UNION` (or two separate queries merged in application code) across a driver-documents table and a vehicle-documents table.
- The cost: every query that wants "this driver's documents" filters on `(owner_type='driver', owner_id=...)` instead of a natural foreign key — acceptable here since the owner-id index (`idx_delivery_compliance_document_owner`) makes that filter as cheap as a foreign-key lookup, and the alternative (two child-entity collections) would have duplicated the add/replace/verify domain logic instead of just this one composite index.

**Alternatives Considered:**
- **Child entity on `Driver`, and a second one on `Vehicle`** — rejected: doubles the domain logic (add/replace/verify) and the repository code for behaviour that is identical except for which four-vs-five-member `doc_type` set is valid, and would need a `UNION` (or two merged queries) everywhere the dashboard or the expiry cron needs a tenant-wide, owner-kind-agnostic view.
- **A generic polymorphic "attachment" table with no `doc_type` domain vocabulary** — rejected: verification lifecycle (pending → verified / pending → rejected → pending-on-replace), the no-expiry exception for a TREM card, and the "required document type per owner" rule are real domain invariants (`ComplianceDocument._validate_dates`, `REQUIRED_DOC_TYPE_FOR_OWNER`) that belong in the aggregate, not left to callers to enforce ad hoc against an untyped blob reference.

---

## ADR-039: Batch-Level Weighment Records, Not Per-Cylinder Serial Tracking

**Status:** Accepted

**Context:** The Weighment subsystem (`docs/research/feature-gap-analysis.md` R1 · `planning/features/20-regulatory-compliance`) implements the two checks MDG 2022 requires — a 10% random sample at goods receipt (cl. 1.2(iv)) and a 100% check before load-out (cl. 1.4(c)(d)). The phase's own `PLAN.md` describes this as "per-cylinder weighment records linked to the delivery," which would mean a `WeighmentRecord` referencing individual cylinder serials. No cylinder-serial identity exists yet anywhere in the system — that is subsystem 3 of this same phase ("Cylinder Identity"), the plan document's own words calling it "the deepest schema change here," and explicitly a later, separate slice of work. Weighment could not wait for it: an agency with no working scale evidence at all is itself an MDG irregularity regardless of what else is missing, making Weighment the phase's own Tier 0 (cheap effort, high consequence) priority.

**Decision:** `WeighmentRecord` (`domain/compliance/weighment_record.py`) records against `(cylinder_type_id, reference_type, reference_id)` — a goods-receipt note or a route — carrying `total_cylinders_in_batch`, `cylinders_checked`, and `underweight_cylinder_count` as counts, not a list of cylinder serials. A record answers "how many of this cylinder type were checked, out of how many in this batch, and how many failed" — the literal shape of evidence the MDG clauses ask for — without needing an identity that doesn't exist yet.

**Consequences:**
- The 100% load-out gate (ADR-040) can enforce "every cylinder type on the manifest has a passing check" by comparing `cylinders_checked == total_cylinders_in_batch` per `(cylinder_type_id, route_id)` — a count comparison, not a join against a serial-tracked inventory that doesn't exist.
- `underweight_cylinder_count` is a count, not a set of specific serials to segregate — MDG's own remedy ("segregate and return in the same truck," R1) is satisfied by the count triggering a `fail` result and downstream staff attention; today's system has no cylinder-serial reference to attach a segregation instruction to individually. Same reasoning `compute_weighment_result()` documents inline.
- The upgrade path is additive, not a redesign: once Cylinder Identity lands, a `cylinder_serial_ids: list[str] | None` column can be added to `WeighmentRecord` (nullable, so every record made before that migration stays valid exactly as recorded) without touching `total_cylinders_in_batch`/`cylinders_checked`/`underweight_cylinder_count`, the load-out gate's comparison, or any endpoint contract already shipped.
- The cost accepted now: a `WeighmentRecord` cannot answer "was cylinder serial X specifically checked" — only "N of this type were checked in this batch, M failed." Acceptable because no other part of the system can answer that question yet either; per-cylinder audit granularity is a real future improvement, not a regression from an existing capability.

**Alternatives Considered:**
- **Defer Weighment until Cylinder Identity ships, then build both together** — rejected: makes the phase's own highest-priority, cheapest item wait on its own hardest item for no domain reason: the MDG checks this implements don't require per-serial identity to be evidenced correctly.
- **Add a placeholder `cylinder_serial_ids` column now, populated with synthetic IDs** — rejected: synthetic identity is worse than no identity — it would look queryable and traceable without being either, and would need its own migration to unwind once real cylinder serials exist.

---

## ADR-040: Weighment Load-Out Gate as Tenant-Opt-In Configuration, Not Unconditional

**Status:** Accepted

**Context:** MDG 2022 cl. 1.4(c)(d) requires 100% of cylinders checked before dispatch — a real, hard requirement, not a soft default. The natural implementation wires this straight into `LoadVehicleForRouteUseCase`'s `planned → loaded` transition, raising `WeighmentCheckRequiredError` (409) when a manifest cylinder type has no passing `load_out_full_check` record for the route. Wiring it in unconditionally, however, was verified — not assumed — to break production: running the full backend test suite (not just the new Weighment unit tests) after that first wiring showed 3 pre-existing integration tests failing where they previously passed (`test_order_endpoints_smoke.py` ×2, `test_route_endpoints_smoke.py` ×1), each now getting a 409 on a `planned → loaded` transition that used to succeed. That is concrete proof, not speculation, that shipping the gate unconditionally would immediately block every tenant's real dispatch workflow on deploy — no existing tenant has ever recorded a weighment, since the feature is new.

**Decision:** `LoadVehicleForRouteUseCase` resolves a `weighment_gate_enabled` `TenantConfiguration` key (default: **not set / off**) before enforcing the check — `_weighment_gate_enabled(tenant_id)` short-circuits to "allowed" whenever the flag is off, or whenever the use case wasn't constructed with both a `WeighmentRecordRepository` and a `TenantConfigurationRepository` (the same optional-dependency, backward-compatible-constructor idiom already used elsewhere in this codebase for additive preconditions). A tenant enables enforcement deliberately, once it has scales registered and staff trained on the workflow — the same "resolve from tenant configuration, default off" pattern this repo already uses for other rollout-sensitive behaviour, not a new idiom invented for this feature.

**Consequences:**
- Every existing tenant's dispatch workflow is unaffected on deploy — the 3 previously-broken integration tests pass again with the flag left at its default, verified directly rather than assumed.
- A tenant that wants the MDG requirement enforced in the software (not just followed on paper) can turn it on once ready, and 5 dedicated unit tests cover the matrix this creates: gate off + no record (allowed), gate on + no record (blocked), gate on + failing record (blocked), gate on + passing record (allowed), and no repositories wired at all (allowed, defensive default).
- The cost accepted: the software does not *force* MDG compliance for a tenant that never turns the flag on — enforcement is opt-in, matching how the rest of this rollout (and the tenant-configuration idiom generally) treats a hard regulatory requirement that the software can evidence but not compel a paper-only agency to adopt on a specific date. This was surfaced to and decided by the user directly, not assumed unilaterally, once the test failures made the alternative's real-world cost concrete rather than theoretical.

**Alternatives Considered:**
- **Ship the gate unconditionally, fix the 3 broken tests to route around it** — rejected: the tests weren't wrong, they were the first real evidence the change breaks production dispatch for every tenant with zero weighment history; "fixing" them would have hidden that fact rather than resolved it.
- **Keep the gate's code but never wire it into the use case's DI** — rejected: would ship dead code with no path to ever actually enforce the MDG requirement without a further release, for no benefit over a config flag that's off by default and equally safe.

---

## ADR-041: TDT Star Rating as a `domain/compliance` Module, with a Two-Pass Repository Query for Cross-Quarter Correctness

**Status:** Accepted

**Context:** TDT (Targeted Delivery Time) — the OMC's quarterly delivery-turnaround rating, booking date → delivery date, 5★ down to 1★, fines scaling on repeat sub-threshold quarters (`planning/features/20-regulatory-compliance/PLAN.md` §2) — is "fully computable from data already in `orders.order_status_history`," confirmed directly against the live schema: `OrderStatusHistoryModel` already records every `to_status` transition with a timestamp, append-only, and the order state machine already has real `booked`/`delivered` statuses. Two placement questions needed resolving before any code: which bounded context owns the domain logic, and how to query `order_status_history` for a quarter without corrupting exactly the slow-delivery cases the feature exists to catch.

**Decision (placement):** `domain/compliance/tdt_rating.py`, sibling to `weighment_record.py`, not `application/reporting`. `application/reporting`'s existing queries (`get_driver_performance.py` et al.) are one-line passthroughs to a nightly-refreshed materialized view — zero domain logic, nothing unit-testable without a database. TDT needs real domain logic (banding a day-count into a star against tenant-configured thresholds, a fine-percent lookup) with a named future-change risk — the MDG-edition question — pulled into free functions (`compute_star_for_order`, `compute_quarterly_rating`, `compute_fine_percent`) specifically so a future edition changing a threshold is a `TenantConfiguration` value change (no code change), and a future edition changing the *banding rule itself* is a one-function change, exactly `compute_weighment_result()`'s documented reasoning (ADR-039's own sibling module). TDT also needs a **live in-quarter projection**, which a nightly-stale materialized view cannot serve — the new `TdtRatingRepository` queries `order_status_history` directly instead, scoped to the current quarter, a small bounded slice.

Every band threshold and fine percentage is tenant-configured, MDG-edition-stamped reference data (`TenantConfiguration` keys `tdt_star_rating_bands`/`tdt_fine_schedule`, each embedding its own `mdg_edition` string) — never a hardcoded constant, since which MDG edition applies (2022 vs. an unconfirmed later revision) is a genuine open question this codebase cannot resolve by reading code (`PLAN.md`'s own open-questions list, item 1). Both keys resolve as of the *quarter's end date*, not "now," via `GetEffectiveTenantConfigurationQuery`'s existing `at` parameter — so a closed quarter's published rating stays reproducible even if the tenant edits its band config afterward; the live projection resolves "now" within the still-open quarter under the same rule, not a special case.

**Decision (query correctness):** `order_status_history` has **no `tenant_id` column and no RLS of its own** — confirmed via migration `7c3f1a9e2b4d`'s own comment ("scoped transitively through orders.order via FK"), the same precedent `inventory.inventory_transaction` already established. Every TDT query joins through the RLS-protected `orders.order` table for tenant isolation, verified by a dedicated cross-tenant-leak test (`TestTdtRatingCrossTenantIsolation`), not left to implicit RLS-suite coverage.

A single filtered query — `WHERE changed_at BETWEEN quarter_start AND quarter_end` applied before aggregating each order's `booked`/`delivered` timestamps — would silently drop a `booked` transition that falls in an *earlier* quarter than its matching `delivered` transition, corrupting exactly the slow-delivery cases this feature exists to catch (an order booked in month 1 of a quarter but delivered after month-end would be miscounted, or its true multi-quarter delay hidden). `SqlAlchemyTdtRatingRepository.get_fulfillment_records` instead runs two passes: a subquery finds every order with a `delivered` transition inside the requested window, then an *unfiltered* aggregation recovers each such order's true `booked_at` from its entire history, not just the rows inside the window. Regression-tested directly (`test_an_order_booked_in_a_prior_quarter_still_counts_its_true_gap`).

**Consequences:**
- The domain module is fully unit-testable with zero database (21 tests, `test_domain_tdt_rating.py`), and the two use cases (`GetQuarterlyTdtRatingUseCase`, `GetLiveTdtProjectionUseCase`) share one code path — the live projection is the quarterly use case called with `current_quarter_bounds(today)` instead of caller-supplied bounds, not a duplicated implementation.
- `_aggregate_overall_stars` (simple arithmetic mean of per-order stars, rounded and clamped 1-5) and the fine-schedule "which quarters count as low" determination are explicitly flagged in their own docstrings as **unconfirmed** against the actual MDG clause text — isolated as their own functions for exactly the same one-function-change reason as every other rule in this module, not because the formula is settled.
- The frontend's generic "Set a configuration value" single-line input (Tenant Config page) cannot reasonably edit either key's array-of-objects shape, so a dedicated structured sub-form (`compliance/feature-tdt-rating`) was built instead, reached via a link from that page rather than a new top-level nav entry — the same "don't force a generic editor onto structured data" reasoning, applied on the frontend.
- The cost accepted: TDT rating cannot be computed for an order that was cancelled or never delivered within the queried window — `HAVING delivered_at IS NOT NULL` (the same "delivered/undelivered" boundary Weighment's own load-out gate already draws) excludes them from this pass entirely, an explicit open policy question (below), not a silent assumption.

**Alternatives Considered:**
- **`application/reporting`, alongside `get_driver_performance.py`** — rejected: that module's queries are deliberately dumb passthroughs to a nightly materialized view; TDT needs real domain logic and a live (not nightly-stale) projection, both of which that pattern cannot serve without becoming a different pattern in the same file.
- **Filter `order_status_history` by the quarter window before aggregating booked/delivered per order** — rejected after being caught during design review, before it ever reached a test failure: it silently drops or corrupts exactly the slow-delivery, cross-quarter cases the feature exists to catch. The two-pass design fixes this and is covered by a dedicated regression test.
- **Hardcode MDG 2022's day-thresholds as constants, ship the tenant-config keys later** — rejected: the applicable edition is explicitly unconfirmed (`PLAN.md` open question 1); hardcoding a guess would bake in exactly the assumption this module's own docstrings warn against, for a feature whose only purpose is a fine calculation a tenant might be legally on the hook for.

---

## ADR-042: `CylinderUnit` as a New `compliance` Aggregate, Not an Extension of `InventoryLocation`

**Status:** Accepted

**Context:** Cylinder Identity (`planning/features/20-regulatory-compliance/PLAN.md` §3, its own words: "the deepest schema change here") needed to model individual, serially-identified cylinders — today, `InventoryLocation` (`domain/inventory/inventory_location.py`) tracks cylinders **only** as bulk counts by `(cylinder_type_id, status)`, confirmed directly: zero per-serial identity exists anywhere in this codebase. That gap makes two regulatory requirements structurally impossible to evidence: Rule 26, Gas Cylinders Rules 2016 (a cylinder may not be charged/filled while its periodical retest is due) and MDG 2022 cl. 1.4(b) (a due-for-test cylinder must be segregated and returned to the bottling plant, not filled or delivered) — `docs/research/feature-gap-analysis.md` R3, D1. **The exact statutory retest interval is not known** — Rule 35(1) defers to IS 15975, which prior research never retrieved (§7, item 2); the commonly-quoted "5 years" is US DOT/49 CFR, not Indian LPG cylinders.

**Decision (placement):** `domain/compliance/cylinder_unit.py`, sibling to `scale.py` and `weighment_record.py`, not `domain/inventory`. Structurally, `CylinderUnit` is the closest analog to `Scale` — identity (serial, cylinder type) and a compliance-relevant date (`test_due_date`) live on **one** aggregate, the same way `Scale` holds `asset_tag` and `certificate_expiry_date` together rather than the `ComplianceDocument`-style split (a driver/vehicle's licence document is a separable, swappable attachment; a cylinder's own retest due date is intrinsic to the unit, not swappable). This mirrors ADR-038/039's own reasoning for keeping a compliance-specific serialized-asset concept out of the bounded context it's physically adjacent to but conceptually distinct from — `CylinderUnit` references `tenant.cylinder_type` and a `(custody_type, custody_ref_id)` polymorphic location (matching `WeighmentRecord`'s own no-FK precedent, extended to four custody kinds — `warehouse`/`vehicle`/`customer`/`bottling_plant` — since a unit can sit at a customer's premises, which `InventoryLocation` cannot model at all) without importing or mutating `InventoryLocation` itself.

**Decision (scope):** a narrow, additive slice — matching every prior Phase 20 slice's own restraint (D24, Weighment, TDT rating all shipped this way). `CylinderUnit` is a new, independent registry; it does not touch `RecordGoodsReceiptUseCase`, `LoadTransferUseCase`, `DeliverOrderUseCase`, `LoadVehicleForRouteUseCase`, or reconciliation — all confirmed unchanged. Wiring per-unit custody into those bulk flows (so every delivery captures exactly which serial a customer received) needs a serial-carrying load manifest, which doesn't exist today (`LoadVehicleLine`/`LoadedLine` carry only `(cylinder_type_id, quantity)`) — a materially larger integration, deferred to a future slice, not attempted here. This plan's real regulatory teeth is instead the unit-level `receive()` command: an **application-layer** 409 (`CylinderDueForStatutoryTestError`), checked by `ReceiveCylinderUnitUseCase` itself before the domain command runs — matching `LoadVehicleForRouteUseCase`'s own precedent for an MDG-rule block (application-layer check, `ConflictError`, 409) rather than `Scale`/`InventoryLocation`'s domain-invariant pattern (422), since a due-for-test cylinder is a *valid request that conflicts with current state*, not a malformed one.

**Consequences:**
- `CylinderUnit`'s condition-status transition graph (`_CONDITION_TRANSITIONS`) is a deliberate **fork**, not an import, of `InventoryLocation`'s own private `_STATUS_TRANSITIONS` — that graph encodes bulk-*balance* semantics specifically (its own docstring explains `filled⇄empty` is absent there because "a different physical unit leaving to the customer" doesn't apply to a bulk counter the same way). A single serialized unit's graph legitimately differs: `filled → empty` is modelled (a unit really is delivered, later returned, as the same cylinder), and `repair → empty` (not `repair → filled`) — a repaired unit re-enters the fillable pool empty and must go through the same Rule-26-gated `receive()` as any other empty unit, not implicitly re-charged. `CYLINDER_STATUSES` itself (the public value vocabulary) **is** imported, so the two graphs can never drift on what a valid status even is, only on which moves are legal.
- `is_due_for_test()` treats a unit with no `test_due_date` on file (never tested) as **not** due — a deliberate, documented policy choice, not a researched answer, so the registry stays usable for onboarding existing bulk stock without requiring a first test before every unit can even be registered. A real gap against Rule 26's intent, carried forward as an open question, not silently resolved.
- `retire()` is a distinct, permanent `is_retired` flag, not an overload of `condition_status='scrap'` — a scrapped-but-tracked unit and a retired-from-the-registry unit are different things, and Rule 27's lifetime-record requirement means a retired unit's row must stay individually queryable (confirmed live: it drops out of the default listing but `GET /cylinder-units/{id}` still returns it).
- `WeighmentRecord.cylinder_serial_ids` — already anticipated by ADR-039 as a future column once Cylinder Identity lands — is **not** added by this slice; a natural next step, not built now.
- The cost accepted: no route-level load-out hard gate exists yet for due-for-test units (the manifest gap above) — a tenant relying solely on route loading, never on the unit-level `receive()` flow, gets no automatic block. The registry's due-status filter (`due_soon`/`overdue`) is a manual worklist for this gap today, not a substitute for the future gate.

**Alternatives Considered:**
- **Extend `InventoryLocation` with a per-unit serial list** — rejected: conflates the bulk-balance model with per-unit identity, the exact reason ADR-039 gave for keeping Weighment batch-level rather than per-serial in the first place.
- **A generic polymorphic "asset" table spanning scales, cylinders, and future serialized things** — rejected, same reasoning ADR-038 gave against a generic "attachment" table: real domain invariants (the condition-transition graph, the custody-consistency check, the Rule-26 gate) belong on a typed aggregate, not left to callers to enforce ad hoc against an untyped blob.
- **A route-level load-out hard gate now, alongside the unit-level one** — rejected: bulk load manifests don't carry serials yet, so a route-level block would have to key off *some* units being tracked while most bulk stock isn't — an ambiguous, likely-surprising trigger condition, the same category of risk ADR-040 found the hard way with Weighment's own unconditional gate. Deferred until a real serial manifest exists.

---

## ADR-043: Delivery Authentication Code as an Optional, Non-Gating POD Field — No Domain-Layer Change

**Status:** Accepted

**Context:** Delivery Authentication Code (`planning/features/20-regulatory-compliance/PLAN.md` §4) — the OMC issues its own separate 6-digit code to the consumer's mobile at a large and growing share of deliveries (`docs/research/feature-gap-analysis.md` R13, coverage 53%→~90%), explicitly distinct from this platform's own internal delivery OTP, which already exists and already gates `out_for_delivery → delivered` (`OtpStore.verify()`, checked in `DeliverOrderUseCase.execute()` before `order.deliver()` runs). Unlike every other Phase 20 slice (D24, Weighment, TDT rating, Cylinder Identity — each a new, independent, additive registry), this one **modifies an existing, working, production flow**: `DeliverOrderUseCase`, the `orders.proof_of_delivery` table, and both delivery-capture UIs (Angular dashboard, Flutter driver app — the latter confirmed as the actual primary delivery-capture surface in production use).

**Decision (no domain change):** `Order.deliver()` (`domain/order/order.py`) takes no POD/OTP/DAC parameters at all — its own docstring states "POD completeness (OTP, signature, photo, GPS) is validated by the use case, not here." `dac_code` slots in exactly where the existing signature/photo/gps/payment/amount fields already sit: pure persistence into `ProofOfDeliveryEntry`, written *after* the state transition already succeeded. Zero domain-layer changes were needed or made.

**Decision (optional, never gates delivery):** DAC coverage is ~90%, not 100% — gating on it, the way the internal OTP gates, would incorrectly block the roughly one-in-ten deliveries that legitimately have none. `dac_code` is nullable throughout every layer (DB column, `ProofOfDeliveryEntry`, `DeliverOrderCommand`, both frontend forms) and the only validation applied is format (`^\d{6}$`, DB `CHECK` + Pydantic `pattern`) — never authenticity. This platform has no OMC portal API to check a DAC against (`PLAN.md`'s own open question elsewhere: "no public evidence of a documented distributor integration API... assume manual reconciliation"), so "validate" here is scoped explicitly to shape, not correctness.

**Decision (three stacks in lockstep, not silently):** the field is threaded through the backend, the Angular dashboard's Deliver drawer, and the Flutter driver app in the same commit sequence, because a delivery recorded from either UI must carry it the same way. The Flutter side needed particular care: `packages/sync_engine/lib/src/sync_coordinator.dart` replays a queued offline operation by `jsonDecode`-ing its stored payload and POSTing it verbatim later — the hand-built JSON map in `delivery_mutations.dart`'s `_queueDelivery` **is** the eventual HTTP body, not a re-serialization of a typed model. `dacCode` had to be added to that map explicitly, separately from the typed `ProofOfDeliverySubmission` object `_deliverInline` (the online path) constructs — missing either one would silently drop DAC for exactly one of the two paths, with no error anywhere. Both paths are covered by dedicated tests asserting the field's presence (or, when omitted, its absence — never a sent `null`) in the actual outgoing payload.

**Consequences:**
- A `dac_coverage` reporting metric was scoped out of this slice, not built. The one existing precedent for a similar percentage-style column, `cash_accuracy` on the Driver Performance report, was found on inspection to be a hardcoded `1.0` literal in `rpt.mv_driver_performance_daily`'s refresh SQL — a stub, not a real computed value — so there was no safe pattern to extend. A real `dac_coverage` aggregate means touching that materialized view's refresh SQL, a separate, higher-risk change to a used, nightly-refreshed artifact; left as an explicit, named next step.
- The dashboard's Deliver drawer turned out, while verifying this change live, to require the `driver` role's own `orders:deliver` permission — the same role that (by this codebase's own design) cannot freely browse the staff-facing order-detail page by ID. This is a pre-existing characteristic of the role/permission model, not something this slice introduced or changed; noted here only because it shaped how the frontend change was verified (a real submitted request confirmed reaching the backend with `dac_code` included, rejected only on this unrelated, pre-existing permission dimension — the full authorized round-trip is proven by the backend integration test instead).

**Alternatives Considered:**
- **Gate delivery on a present-and-valid DAC, same as the internal OTP** — rejected: would incorrectly block the ~10% of deliveries with no OMC-issued code, a regression the moment this shipped for any tenant not yet at full OMC rollout.
- **Attempt authenticity validation against an OMC system** — rejected: no such integration exists or is documented as available anywhere in this codebase's research; would be inventing a check this platform cannot actually perform.
- **Build the `dac_coverage` KPI in the same slice** — rejected: the only extension point (`cash_accuracy`) is itself unverified stub logic; conflating "ship the capture" with "fix a pre-existing reporting stub and add a new real metric on top of it" would have doubled this slice's risk for a benefit (a KPI) the roadmap ranks separately from capture itself.

---

## ADR-044: Compliance Calendar Licence Registry as Two New `ComplianceDocument` Owner Types, Not a New Aggregate

**Status:** Accepted

**Context:** `planning/features/20-regulatory-compliance/PLAN.md` §7 bundles several regulatory items in one prose paragraph: PESO Form F (explosive-storage licence, per warehouse) and insurance renewal tracking — both roadmap item #4, Tier 0 — alongside biennial safety inspection (roadmap item #22, Tier 1, its own "inspection job" domain concept per research row D13) and the 12-hour accident-notification workflow (roadmap item #23, Tier 1, R5/R18). This is the same PLAN.md tiering-vs-prose-bundling pattern found and split three times already this phase (Weighment, TDT rating — ADR-041, Cylinder Identity — ADR-042). This slice builds **only** the Tier-0 licence-expiry registry, deferring the rest.

**Decision (extend, don't duplicate):** `ComplianceDocument` (`domain/delivery/compliance_document.py`, D24/ADR-038) was already a generic aggregate keyed by `(owner_type, owner_id)`, with its repository, application use cases (Add/Replace/Verify/List), and the nightly `check_compliance_expiry` expiry cron all confirmed fully generic over `owner_type` before writing any code. Only three owner-type-specific spots needed widening: the DB `CHECK` constraint (`compliance_document_owner_type_check`, verified live via `docker exec lpg-postgres psql` before and after the migration), the domain `COMPLIANCE_OWNER_TYPES` frozenset (a binary `if/else` `doc_types_for_owner()` dispatch became a dict lookup, now exhaustive-safe for 4 owner types instead of 2), and the API schema `ComplianceOwnerType` Literal. A new aggregate would have duplicated all of the above for no behavioral difference — the same reasoning ADR-038 itself already established for driver vs. vehicle.

**Decision (owners):** `warehouse` → the existing `Warehouse` master-data aggregate (`admin.py`'s `GET/POST /admin/warehouses`), not `InventoryLocation` (a stock-ledger construct that happens to share the string `"warehouse"` as one of its `location_type` values) — `Warehouse.id` is the correct, already-listable identity for a *licence*, as opposed to a *stock position*. `tenant` → the caller's own `principal.tenant_id`, no picker needed; the aggregate still allows multiple documents/renewals over time per owner, same as any other.

**Decision (new endpoints, existing gates left alone):** four new thin wrapper endpoints (`GET`/`POST /warehouses/{id}/documents`, `GET`/`POST /tenant/documents`) mirror the existing driver/vehicle wrappers exactly, reusing the existing generic use cases verbatim — zero new application-layer code. They are gated by two new permissions, `compliance:manage`/`compliance:read`, granted only to `super_admin, agency_admin, manager` (the same role set as the existing `compliance:verify`) — these are admin-tier licences, not day-to-day operational documents like a driver's licence. The existing generic `PUT /compliance-documents/{id}` (replace) and `POST /compliance-documents/{id}/verify` endpoints are reused unchanged for the new owner types too, since neither has an owner-type check inside it; their current gates (`drivers:manage`, `compliance:verify`) were deliberately left untouched rather than narrowed, because `drivers:manage`/`drivers:read` are granted much more broadly (`dispatcher`, and `warehouse_staff`/`accountant`/`driver` respectively — confirmed via `a1b2c3d4e5f6_create_delivery_schema.py`'s role matrix) and narrowing them would have risked locking out current driver/vehicle-page callers for a benefit (tighter warehouse/tenant document permissions) achievable more narrowly by just not reusing those gates on the *new* endpoints.

**Decision (frontend reuses the panel wholesale):** the new Compliance Calendar page does not build a bespoke grid — it hosts `<lpg-compliance-documents-panel>` twice, exactly the way the driver and vehicle detail drawers already do (a warehouse picker driving one panel instance, plus a second, always-visible instance for the tenant's own documents). The panel was already fully endpoint-agnostic via its `documents`/`docTypeOptions`/`managePermission`/`uploader`/`addDocument`/`replaceDocument`/`verifyDocument` inputs, confirmed by reading it in full before deciding — this reduced the frontend slice to two new service methods plus a thin page, not a new registry component.

**Consequences:**
- `dispatcher` can technically replace or verify a warehouse/tenant compliance document without holding the new `compliance:manage`/`compliance:verify`-adjacent grant, because the shared generic replace endpoint's gate (`drivers:manage`) is broader than `compliance:manage`'s role set. This is a known, pre-existing-pattern-consistent minor looseness (the same trade the driver/vehicle endpoints already accept for each other), not a regression introduced here, and is named explicitly rather than fixed by touching a shared gate.
- Biennial safety inspection (D13), the 12-hour accident/insurance-claim workflow (R5/R18), fire NOC / trade licence (mentioned only in the broader D7 research row, not in PLAN.md §7's own text), and a `dac_coverage`-style calendar completeness KPI are all explicitly deferred, not silently dropped.

**Alternatives Considered:**
- **A new `WarehouseComplianceDocument`/`TenantComplianceDocument` aggregate** — rejected: would duplicate the repository, all four use cases, and the expiry cron's owner-iteration logic for zero behavioral difference; ADR-038 already settled this question for driver vs. vehicle and nothing about warehouse/tenant changes the answer.
- **Narrow the existing generic replace/list endpoints' gates to `compliance:manage`/`compliance:read`** — rejected: `drivers:manage`/`drivers:read` are granted far more broadly (dispatcher; warehouse_staff, accountant, driver), so narrowing would lock out current driver/vehicle-page callers who hold the broader permission but not the new, narrower one.
- **Build a bespoke Compliance Calendar grid/drawer component** — rejected: `<lpg-compliance-documents-panel>` already does everything the page needs and is proven in production on two other owner types; a bespoke component would duplicate its add/replace/verify/reject form logic for no new capability.

---

## ADR-045: AI Model Gateway as a Provider-Agnostic Tool-Calling Port, Gemini as the First Adapter, a Fixed Read-Only Tool Registry as the First Consumer

**Status:** Accepted

**Context:** The user supplied a full target architecture for an "AI-native" evolution of this platform: events tell the system what happened; AI reasons and orchestrates; tools — never raw database access — execute through existing domain services and RBAC exactly as if a human had typed the same request into the UI; existing domain events communicate the result. The user's own document's §35 "Recommended First Implementation" — confirmed as the chosen scope via `AskUserQuestion` over two alternative framings — is exactly what this slice builds: an AI Orchestrator, a Tool Registry of read-only tools, Gemini as the first provider behind a swappable abstraction, an AI audit trail, and a read-only "AI Command Center" page. Nothing in this slice mutates anything — no approval/risk engine is needed yet, because no tool can write. This is Phase 21's substrate (`21-ai-foundation`) and, narrowed hard, a safer precursor to Phase 23's A12 "Internal analytics copilot" (`23-ai-assistive-interfaces`) — not A12 itself: instead of text-to-SQL over a curated semantic layer, the model picks from a **fixed menu of vetted, pre-built tools**, which removes SQL-generation/injection risk entirely at the cost of being less open-ended.

**Decision (tool-calling port, not a plain-generation one):** `ModelGatewayPort` (`application/ai/ports.py`) has exactly one method, `run_with_tools()`, taking a `tool_executor` callback the *application layer* supplies — the adapter drives Gemini's native function-calling loop internally but never knows what a "tool" means business-wise, keeping the hexagonal boundary correct (infrastructure speaks only the wire protocol; the application layer owns what each tool actually does). No plain non-tool `generate()` method was added — YAGNI; add one only when a future feature (e.g. a deferred structured-output classifier) actually needs it. `GeminiModelGateway` (`infrastructure/ai/gemini_adapter.py`) was built against the real installed `google-genai` SDK, not guessed — its turn/role shape (append the model's own function-call turn, then a `role="user"` turn carrying the function response) was confirmed by reading the SDK's own internal automatic-function-calling reference implementation (`google.genai.chats`), not invented. `infrastructure/ai/factory.py`'s `get_model_gateway()` is the entire "provider configurable" story: it picks the adapter class from `Settings.ai_provider` (only `"gemini"` implemented; an unknown value raises rather than silently falling back), the same swap-by-config-plus-new-adapter-class shape `FileStorage`/`DocumentOcrPort` already prove for storage/OCR.

**Decision (kill switch and budget checked in the use case, never the port):** `AskAiAssistantUseCase` checks `ai_gateway_enabled` (a new `TenantConfiguration` key, default-off) and the effective daily token budget *before* the gateway is ever touched — mirrors `weighment_gate_enabled`'s check-in-the-use-case shape (ADR-040) exactly, not baked into a lower layer. Both checks, and the budget ceiling's default (`DEFAULT_AI_DAILY_TOKEN_BUDGET = 100_000`, overridable per tenant via `ai_daily_token_budget`), read through the existing `GetEffectiveTenantConfigurationUseCase` — no new resolution mechanism.

**Decision (per-tool permission filtering is the real prompt-injection defense):** each `ToolDefinition` in the static `TOOL_REGISTRY` (`application/ai/tools.py`) declares a `required_permission`; the orchestrator filters the registry against the calling principal's actual grants *before* Gemini ever sees a tool exists, and a hallucinated or out-of-grant tool-call name is rejected by the `tool_executor` closure, never executed — exactly the backend-gate-not-system-prompt-wording defense the user's own architecture document specifies. `ai:read` (new permission, granted only to `super_admin, agency_admin, manager`) gates the endpoint itself; each tool's own permission (`orders:read`, `inventory:read`, `complaints.manage` — all pre-existing) gates that specific tool's visibility, so a principal missing one still gets an answer built from whichever tools they do hold.

**Decision (three read-only tools, zero-argument, mostly thin wraps):** `get_inventory_overview` and `get_open_complaints_summary` wrap existing repository methods that had no use case of their own yet (`InventoryLocationRepository.get_balance_summary()`; `ComplaintRepository.count_complaints()` called three times, once per non-terminal status, since the repository takes one status at a time). `get_today_delivery_status` is the one genuinely new query — no existing use case answers "today's order-status counts" or "delayed" at all — narrowed to `stale_out_for_delivery_count` (orders still `out_for_delivery` from *before* today, the clearest "should have finished, didn't" signal) rather than a fuller staleness sweep across every non-terminal status. Every tool is zero-argument, removing parameter-schema/argument-validation surface entirely for this slice; parameterized tools are a natural, easy follow-up once this pattern is proven. Branch-level scoping was deliberately left out — branch-scoping for orders/routes today lives in two different *private* router functions (`order.py`'s `_resolve_scope`, `route.py`'s `_resolve_read_scope`) with no reusable application-layer helper, and inventory/complaints have no branch concept at all — so these tools are correctly tenant-wide (RLS-isolated) but not further narrowed by branch.

**Decision (append-only run ledger, no bespoke audit path):** `ai.assistant_run` (one row per `POST /ai/ask` call: question, tools used, provider/model, token/latency accounting, status) is a plain frozen entity — same "not an `AggregateRoot`" shape as `WeighmentRecord`/`ProofOfDeliveryEntry` — written via a normal repository `add()` inside a UoW, which rides `AuditRecorder`'s existing generic `before_flush` hook for a free audit trail. It deliberately does **not** store prompt/response text bodies: full prompt/response capture for evaluation is Phase 21's own later scope, and a genuine DPDP retention-policy question given complaint/order text can carry customer-identifying content — not just a schema decision to make casually.

**Consequences:**
- **A real bug was caught by live verification, not by any automated test written before it was found.** The generic Tenant Configuration "Set Value" admin form has no dedicated toggle for `ai_gateway_enabled` (a plain text-value input, same as every other scalar key) — it persists whatever string an operator types, so `config_value` can genuinely be the *string* `"false"`, not the JSON boolean `false`. A naive `bool(config_value)` reads that as truthy (`bool("false") is True` in Python — it only checks for a non-empty string), so a tenant "disabled" through the real UI was actually still answering questions. Caught during the plan's own live-verification step (set the flag to `"false"` through the real admin page, asked a question, got a real answer instead of the disabled message), fixed with a dedicated `_is_truthy_config_value()` helper (string-aware: `"false"/"0"/"no"/""` are falsy) plus a regression test asserting the literal string `"false"` disables the gateway. This class of bug is a live risk for `weighment_gate_enabled` too (same generic-form, same `bool()`-cast shape, ADR-040) — it has simply never been exercised there yet, since no dev-environment row for that key exists. Named here, not fixed there — out of scope for this slice.
- `ai_gateway_enabled`/`ai_daily_token_budget` were added to the frontend's `RECOGNIZED_CONFIG_KEYS`/`CONFIG_KEY_INFO` catalog (`tenant-configuration-page.ts`) so an admin can actually discover and set them through the existing generic page — the catalog is a curated allow-list for the "Set Value" dropdown, not dynamically sourced from the backend's own recognized-key set, and was found to already be several keys behind the backend before this slice (only 3 of roughly 10 backend-recognized keys were listed). Only this slice's own two keys were added; the pre-existing gap for other features' keys is named, not retroactively fixed.
- The Gemini model name is a moving target: the adapter was originally built against `gemini-2.0-flash` (a name that seemed current at implementation time) and only discovered to be retired — with the real current model, `gemini-3.6-flash`, named directly in the provider's own 404 response — during live verification with a real API key. `Settings.gemini_model`'s default was corrected before this shipped; a wrong model name degrades to `disabled_reason: "provider_error"` (never a raw 500), so a future rename is a config change, not an incident.
- The system prompt explicitly asks for plain text, not markdown (`_SYSTEM_PROMPT`'s own instruction) — the AI Command Center's answer is rendered as plain text, and Gemini's default `**bold**`/`### heading` markdown style read as literal asterisks and hash marks in the UI before this instruction was added; confirmed live before and after.

**Alternatives Considered:**
- **A generic `generate()` method on the port, with tool declarations as an optional parameter** — rejected: every consumer this slice has needs tools; a generation-only path with no consumer is speculative surface, added only when a real feature needs it.
- **Budget/kill-switch checks inside the Gemini adapter** — rejected: would make the check provider-specific (every future adapter would need to reimplement it) and breaks the established `weighment_gate_enabled` precedent of checking tenant configuration in the use case, not a lower layer.
- **A DB-backed, admin-configurable tool registry** — rejected for this slice: three tools, all read-only, all zero-argument, is small enough that a static, code-reviewed list is the safer and simpler choice; a dynamic registry is real added complexity (who can register a tool? what's the authorization model for *that*?) with no current requirement driving it.
- **Full Phase 21 evaluation harness (golden datasets, adversarial suite) in this slice** — rejected: this is genuinely larger, separate scope: a real evaluation pipeline needs curated test data and a defined pass/fail bar this slice has no reason to invent yet. The run ledger captures enough (tokens, latency, status, tools used) to bootstrap one later.

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
| 020 | AG Grid Enterprise behind an abstraction | Accepted — amended by 028, Community now default |
| 021 | RFC 7807 error contract | Accepted |
| 022 | Azure target cloud; topology deferred | Accepted (direction only) — amended by 027 |
| 023 | Background job architecture | Accepted (architecture) — resolved by 029 (library: ARQ) |
| 024 | Python architecture-boundary enforcement | Accepted |
| 025 | Polyglot monorepo layout | Accepted (amends 001) |
| 026 | Code-first OpenAPI, generated spec as contract | Accepted |
| 027 | Supabase as managed PostgreSQL host **only** | Accepted (amends 013, 022) |
| 028 | Hybrid UI strategy — PrimeNG primary, AG Grid Community default, Enterprise optional | Accepted (amends 020) |
| 029 | ARQ as the background job library | Accepted (resolves 023's deferral) |
| 030 | S3-compatible file storage port, MinIO for every environment that exists today | Accepted |
| 031 | Brand colour moves from blue to deep forest green | Accepted |
| 032 | `ng-openapi-gen` for the generated Angular API client | Accepted |
| 033 | Angular `fileReplacements` for frontend environment configuration | Accepted (resolves 032's deferral) |
| 034 | SQLCipher-encrypted Drift via `package:sqlite3`'s build-hook source selection | Accepted (implements 05-mobile-architecture.md §7) |
| 035 | JWT (RS256, `pyjwt[crypto]`) + Argon2id; `SECURITY DEFINER` functions resolve tenant before auth | Accepted |
| 036 | Shell-bypass routing for unauthenticated routes — component-less parent route | Accepted |
| 037 | Hand-written Flutter `api_client` for Phase 6, deferring spec-generation | Accepted (explicit revisit trigger) |
| 038 | `ComplianceDocument` as a standalone aggregate, not a Driver/Vehicle child entity | Accepted |
| 039 | Batch-level weighment records, not per-cylinder serial tracking | Accepted |
| 040 | Weighment load-out gate as tenant-opt-in configuration, not unconditional | Accepted |
| 041 | TDT star rating as a `domain/compliance` module, two-pass repository query for cross-quarter correctness | Accepted |
| 042 | `CylinderUnit` as a new `domain/compliance` aggregate, not an `InventoryLocation` extension | Accepted |
| 043 | Delivery Authentication Code as an optional, non-gating POD field — no domain-layer change | Accepted |
| 044 | Compliance Calendar licence registry as two new `ComplianceDocument` owner types, not a new aggregate | Accepted |
| 045 | AI Model Gateway as a provider-agnostic tool-calling port, Gemini as the first adapter, a fixed read-only tool registry as the first consumer | Accepted |

## Deferred Decisions

Decisions deliberately left open, each with a defined trigger point:

| Item | Decide by | Reference |
|---|---|---|
| Azure hosting topology (Container Apps vs App Service vs other) and IaC tool (Bicep vs Terraform) | Before production deployment | ADR-022 · DW-05 |
| PDF rendering library (WeasyPrint vs ReportLab) | Phase 17 — Printing | ADR-016 · DW-07 |
| AG Grid Enterprise licence procurement (only if a future feature needs it) | As triggered — no longer a standing Phase 4 blocker | ADR-020 · ADR-028 · DW-08 |
| Supabase production tier (lower tiers pause idle projects) | Before production | ADR-027 · DW-05 |
| Production object-storage vendor (Azure Blob if Azure is chosen; an S3-compatible managed service reuses the existing adapter as-is) | Before production, tied to the hosting-topology decision | ADR-030 · ADR-022 |
| WebSocket connection/subscription authorization (Phase 3's `RealtimePublisher` was built without it — needed real Authentication first) | Immediate fast-follow after Phase 6, not tied to a later numbered phase | ADR-015 · ADR-035 |
| MFA for Super Admin | Post-MVP (SRS recommends, doesn't require, for this role only) | 08-security-architecture.md |
| Entra ID SSO — schema seam exists (`identity_user.sso_subject`/`sso_provider`), no working OAuth flow | When an Azure AD app registration and hosting decision exist | ADR-022 |

## Review Cadence
ADRs are reviewed at each major phase gate and annually thereafter in production. Superseded decisions are marked **Superseded**, with a link to the new ADR, never deleted — preserving the historical reasoning trail this document exists to provide. The Phase 0 supersessions above are the first application of that policy; the superseded architecture documents themselves are preserved under [`superseded/`](./superseded/README.md).
