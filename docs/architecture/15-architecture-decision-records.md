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

## Deferred Decisions

Decisions deliberately left open, each with a defined trigger point:

| Item | Decide by | Reference |
|---|---|---|
| Azure hosting topology (Container Apps vs App Service vs other) and IaC tool (Bicep vs Terraform) | Before production deployment | ADR-022 · DW-05 |
| PDF rendering library (WeasyPrint vs ReportLab) | Phase 17 — Printing | ADR-016 · DW-07 |
| AG Grid Enterprise licence procurement (only if a future feature needs it) | As triggered — no longer a standing Phase 4 blocker | ADR-020 · ADR-028 · DW-08 |
| Supabase production tier (lower tiers pause idle projects) | Before production | ADR-027 · DW-05 |
| Production object-storage vendor (Azure Blob if Azure is chosen; an S3-compatible managed service reuses the existing adapter as-is) | Before production, tied to the hosting-topology decision | ADR-030 · ADR-022 |

## Review Cadence
ADRs are reviewed at each major phase gate and annually thereafter in production. Superseded decisions are marked **Superseded**, with a link to the new ADR, never deleted — preserving the historical reasoning trail this document exists to provide. The Phase 0 supersessions above are the first application of that policy; the superseded architecture documents themselves are preserved under [`superseded/`](./superseded/README.md).
