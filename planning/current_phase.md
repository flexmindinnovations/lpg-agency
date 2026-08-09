# Current Development Phase

## Project

LPG Agency Management Platform

---

## Current Phase

**Phase 2 — Backend Foundation** ✅ **COMPLETE** — started and finished 2026-08-09 on explicit instruction. 34/34 tracked tasks complete and verified. See [`planning/features/02-backend-foundation/STATUS.md`](./features/02-backend-foundation/STATUS.md).

**Phase 3 — Shared Infrastructure (real-time publisher, file storage)** ✅ **COMPLETE** — started and finished 2026-08-09 on explicit instruction, immediately after DW-19/DW-20 closure. 13/13 tracked tasks complete and verified. See [`planning/features/03-shared-infrastructure/STATUS.md`](./features/03-shared-infrastructure/STATUS.md). Scoped to exactly two items — the `RealtimePublisher` port implementation and file storage — since everything else the original roadmap called "Phase 3" was already delivered under Phase 2's execution numbering.

**Phase 4 — Angular 22 Web Foundation** ✅ **COMPLETE** — started and finished 2026-08-09 on explicit instruction. 17/18 tracked tasks complete and verified, 1 explicitly deferred to post-MVP by product owner decision (DW-24, Storybook's build — non-blocking). See [`planning/features/04-angular-web-foundation/STATUS.md`](./features/04-angular-web-foundation/STATUS.md). Brand palette refresh (ADR-031, deep forest green replacing blue), the collapsible-sidebar layout shell, T-34 (Playwright e2e execution, closed after being blocked since Phase 1), a WCAG 2.2 AA axe-core gate (found and fixed 3 real accessibility bugs), and the generated API client (ADR-032, `ng-openapi-gen`) are all done and verified. The API client's base URL was subsequently wired end-to-end same day, on explicit instruction, ahead of the phase originally expected to need it — see ADR-033.

Phase 5 (Flutter Application Foundations) started 2026-08-09 on explicit instruction, immediately after ADR-033 closed out.

**Still recommended for after Phase 5:** Phase 6 (Authentication) — Phase 2's `HeaderTenantResolver` (interim, header-based, not a security boundary), the not-yet-mandatory tenant-scoped session (DW-12), and Phase 3's excluded WebSocket-subscription-authorization remain **three** separate things waiting specifically on real Authentication existing.

Phase 1 — Repository / Development Foundation — is complete: 64/67 actionable tasks (96%); re-verified fresh on 2026-08-09, 1 item blocked (Playwright e2e execution, deferred to Phase 4). PrimeNG installation & integration (T-68) closed out same day — see [`planning/features/01-repository-foundation/STATUS.md`](./features/01-repository-foundation/STATUS.md).

Phase 0 — Documentation Reconciliation & Technical Baseline — is also complete; see [`planning/features/00-documentation-reconciliation/STATUS.md`](./features/00-documentation-reconciliation/STATUS.md).

---

## Phase Objective

**Phase 1 (complete):** establish the production-ready repository structure and developer tooling for the Angular 22, FastAPI, Flutter, PostgreSQL and Redis applications — foundation only, no business functionality.

Achieved. A developer can clone, run one setup command, and every application starts, every test suite runs, and every quality gate passes — with no business logic present.

---

## Current Repository State

Re-verified fresh 2026-08-09 (Nx cache explicitly bypassed for the frontend recheck; nothing in this section is read from a prior report). Every figure below came from running a command this session.

**The repository now contains working, verified code — and still no business features.** No authentication, no domain aggregates, no business routes or screens. That is deliberate; each arrives in its own phase.

### Built and verified

| Area | State |
|---|---|
| **Backend** (`backend/`) | FastAPI app on Python 3.13.5. Clean Architecture layers, Pydantic settings with production guard rails, discrete Supabase connection keys with URL-encoded `SecretStr` password, structlog with central redaction, correlation IDs, RFC 7807 errors, async SQLAlchemy with a working RLS tenant seam, Redis client, split liveness/readiness probes, Alembic verified against **both** local Docker and **live Supabase**, committed + drift-checked OpenAPI spec. **83 tests pass** (62 unit + 21 integration), 0 skipped. |
| **Frontend** (`frontend/`) | Nx 23.1.1 workspace, **Angular 22.0.8** dashboard. Design tokens, three themes, four shared libraries, AG Grid behind a wrapper (now with 9 tests proving it renders real AG Grid Community, not just that its mapping compiles), RFC 7807 + correlation interceptors, accessible app shell. **36 tests pass** — up from 14; the two shared libraries that had zero coverage on every prior pass are now tested. |
| **Mobile** (`mobile/`) | Melos workspace: `customer_app`, `driver_app`, and `core`/`design_system`/`local_storage` packages. Riverpod, go_router, generated Dart tokens with three themes. **12 tests pass.** |
| **Design tokens** (`design-tokens/`) | One JSON source generating 229 CSS variables, TypeScript constants and Dart constants. Drift-checked in CI. |
| **Local environment** (`infrastructure/`) | Docker Compose: PostgreSQL 17 + Redis 7, non-default ports, healthchecks, init SQL creating **two** application roles (`lpg_app` for dev/test, `lpg_app_uat` for uat), each `NOBYPASSRLS`, `PUBLIC` revoked from `CONNECT` on all three databases so the environment boundary is enforced, not just documented. |
| **Hosted database** | **Supabase** (ADR-027), live-verified this session — see below. |
| **Scripts** (`scripts/`) | setup, dev-up, dev-down, test, lint, format, check, generate-tokens, check_architecture_consistency. |
| **CI** (`.github/workflows/`) | Four path-filtered workflows; validation only, no deployment. |
| **Git** | Working tree clean, latest commit `4a1b109`. |

**131 tests passing overall** (83 backend + 36 frontend + 12 Flutter) — up from 102. Lint, format, type check and boundary contracts pass on all three stacks.

### Supabase — live-verified this session

The user supplied the database password. Verified using the application's actual connection-composition code (`Settings.effective_database_url`), not a hand-rolled test:

- `SELECT current_database(), current_user, version()` → PostgreSQL 17.6, `db=postgres`, `user=postgres`
- Alembic `current`/`heads` both ran cleanly against the live project
- Credential never printed in any command output

**Two things this surfaced, not just a pass:**

1. `postgres` on Supabase has `rolsuper=False` but **`rolbypassrls=True`** — confirms live the risk `.env.prod.example` already documented. DW-19 (provision a dedicated `NOSUPERUSER`/`NOBYPASSRLS` application role) is now concrete, not hypothetical. **Resolved 2026-08-09** — see below.
2. Only `pgcrypto` is installed on the live project; `citext` and `pg_trgm` are not yet enabled (DW-20). Both are available and needed before Phase 2's first migration. **Resolved 2026-08-09** — see below.

### Enforcement that is live

Not conventions — these fail the build:

| Rule | Mechanism | Status |
|---|---|---|
| Clean Architecture dependency direction | `import-linter`, 5 contracts | ✅ 5 kept, 0 broken |
| Full type coverage at boundaries | `mypy --strict` | ✅ 36 files clean |
| Feature libraries never import each other | Nx `enforce-module-boundaries` | ✅ 6 projects clean |
| Design tokens match their single source | Generator `--check` | ✅ |
| OpenAPI spec matches implementation | Export `--check` | ✅ |
| No environment file committed | Repository CI | ✅ |
| Superseded architecture stays superseded | `scripts/check_architecture_consistency.py` in CI | ✅ 273 files, 0 findings |
| Alembic is the sole owner of schema | Repository CI | ✅ |
| No `service_role` key committed | Repository CI | ✅ |

The boundary contracts earned their place on first run: they caught the API layer importing `Database` directly. Fixed properly by depending on the application-layer `HealthCheck` port, with the composition root carrying a declared exception.

### Not started

Authentication · RBAC · every business module · background worker · real-time WebSocket implementation · printing engine · production infrastructure · deployment pipelines · offline sync.

### Verification history

Three rounds, each closing what the previous one left open:

**Round 1 (Docker unavailable):** all Docker-dependent checks blocked; documented honestly as blocked, not complete.

**Round 2 (Docker available):** closed all five — container health, 15 live PostgreSQL integration tests, 6 live Redis integration tests, Alembic against a live local database, `/health/ready` reporting `ready` for the first time. **Found a real bug in the process**: `SET LOCAL app.current_tenant_id = :tenant_id` is a PostgreSQL syntax error — `SET` does not accept bind parameters. That is the one line the entire RLS backstop depends on (ADR-017); it would have failed at Phase 2's first tenant-scoped query. Fixed with `set_config('app.current_tenant_id', :tenant_id, true)`.

**Round 3 — this session (2026-08-09), everything re-run fresh:**

- **T-63 closed** — live Supabase connection verified (password supplied by the user), both application-path and Alembic. See the Supabase section above for what it found.
- **Dev/uat password rotation** verified live from the host (not via `docker compose exec`, which hits `pg_hba.conf`'s loopback `trust` rule and proves nothing about real authentication) — 8/8 checks: each role reaches only its own database, old password rejected, cross-role/cross-database attempts rejected.
- **A latent test-hygiene bug found and fixed**: `backend/.env` now exists on disk (normal setup), and `Settings()` was silently inheriting it in tests and in `scripts/export_openapi.py` — 19 failures, 24 errors, one drift-check failure, none related to the actual change being verified. Fixed with an autouse fixture disabling dotenv in tests, and explicit safe env-var defaults before `export_openapi.py`'s import of the composition root (which builds a module-level `app` singleton with unoverridden settings as an import-time side effect). Verified identical behaviour with `.env` present and absent.
- **Frontend re-verified with Nx cache bypassed** (a cached "passed" is not a re-verification) — surfaced `shared-ui` and `shared-util` at zero tests across every prior pass. Closed rather than deferred: 22 tests added, including one that renders real AG Grid Community in jsdom.

~~Only remaining blocked item: Playwright e2e execution (T-34)~~ — **resolved 2026-08-09, Phase 4.** 27/27 e2e tests passing (chromium/firefox/webkit).

---

## Technology Baseline

Confirmed by the product owner on 2026-08-09. Recorded as ADR-012 … ADR-026.

| Layer | Technology |
|---|---|
| Backend | Python 3.13+, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 |
| Database | PostgreSQL on **Supabase** (managed host only, ADR-027), with Row-Level Security tenant isolation |
| Cache / queue / real-time backplane | Redis |
| Web dashboard | Angular 22, strict TypeScript, **Nx** workspace at `frontend/`, Signals + NgRx SignalStore, **PrimeNG** (primary component library) + Angular CDK (Material selective), Tailwind CSS v4, **AG Grid Community** (default, behind a wrapper; Enterprise optional per feature) — ADR-028, Storybook, Jest, Playwright |
| Mobile | Flutter, Riverpod, Drift SQLite; Driver App offline-first |
| Real-time | FastAPI WebSockets + Redis Pub/Sub — **Phase 1 scope** |
| Boundary enforcement | `import-linter`, `mypy --strict` (backend); Nx `enforce-module-boundaries` (frontend) |
| Container / CI / cloud | Docker, GitHub Actions, Azure |

**Discrepancies: none remaining.** All eight identified in the initial assessment are resolved:

| # | Was | Resolved |
|---|---|---|
| D1 | .NET vs Python backend | Python/FastAPI — ADR-012; .NET preserved under `superseded/` |
| D2 | Angular 20 vs 22; Nx unconfirmed | Angular 22 + Nx at `frontend/` — ADR-018 |
| D3 | Three conflicting state-management positions | Ordered Signals-first rule set — ADR-019 |
| D4 | AG Grid vs Material/PrimeNG | AG Grid Community default (Enterprise optional) behind an abstraction; PrimeNG adopted as primary component library — ADR-020, amended by ADR-028 (2026-08-09) |
| D5 | `{success, error}` vs RFC 7807 | RFC 7807 + `error_code` — ADR-021 |
| D6 | "OpenAPI first" vs "code-first" | Code-first generation, generated spec committed as the client contract — ADR-026 |
| D7 | Azure SignalR, no FastAPI equivalent | FastAPI WebSockets + Redis Pub/Sub — ADR-015 |
| D8 | Azure topology assumed a .NET/SQL stack | Azure confirmed; topology and IaC tool deliberately deferred — ADR-022 |

---

## Architecture Baseline

**Documented, and now partly realised.** The foundation layers below exist in code and are enforced by CI. The business layers above them do not exist yet.

### Documented, with foundation implemented

- **Clean Architecture** — Domain → Application → Infrastructure → API, dependency rule pointing inward, enforced in CI by `import-linter` and `mypy --strict` (`docs/architecture/03-backend-architecture.md`)
- **DDD** — aggregates with single roots, domain events dispatched **after** commit, bounded contexts matching both backend module folders and PostgreSQL schema names
- **Modular monolith** with documented extraction seams (ADR-002)
- **CQRS in-process via explicit application services** — no mediator library; the five former MediatR behaviors re-expressed as FastAPI dependencies and Unit of Work responsibilities (ADR-014)
- **Repository per aggregate root + Unit of Work** — one transaction per command, guaranteeing BR-29
- **Tenant isolation, four layers** — PostgreSQL RLS, `SET LOCAL app.current_tenant_id`, repository scoping, CI tests (ADR-017)
- **REST + WebSockets** — `/api/v1`, RFC 7807 errors, `snake_case` JSON, idempotency keys, optimistic concurrency
- **Real-time** — transport-agnostic publisher port, tenant-namespaced channels, RBAC-authorized subscriptions, at-most-once delivery with REST as the source of truth
- **Background jobs** — separate worker process, jobs as use cases, always tenant-scoped, idempotent
- **Printing** — server-side, block-based, tenant-configurable, renderer-agnostic
- **Frontend** — Nx feature libraries that cannot import each other, Signals-first state, design tokens, PrimeNG as the primary component library, AG Grid Community behind a wrapper (Enterprise optional per feature), WCAG 2.2 AA
- **Testing** — six layers, with tenant isolation as its own suite and boundary contracts as merge-blocking CI checks

### Gaps closed

**Phase 0** closed all nine documentation gaps (A1–A9): folder structure reconciled, docs sub-structure mapped, Python backend layering authored, the MediatR-equivalent designed, tenant isolation unified on PostgreSQL RLS, printing rebound to Python, real-time designed, background jobs designed, boundary enforcement specified.

**Phase 1** turned the load-bearing parts of that into running, enforced code: the layer structure exists and `import-linter` guards it; the RFC 7807 contract is implemented and tested; the RLS tenant seam is wired; the design-token pipeline generates all three platforms from one source; the OpenAPI contract is committed and drift-checked.

Still documentation-only, by design: the Unit of Work, repositories, domain-event dispatcher, background worker, real-time publisher implementation, and printing engine. Each arrives with the phase that needs it.

---

## Documentation Baseline

### Changed in Phase 0

**Preserved (moved, banner added):** `superseded/01-system-architecture-dotnet.md`, `03-backend-architecture-dotnet.md`, `06-database-architecture-dotnet.md`, `09-printing-architecture-dotnet.md`, `13-deployment-dotnet.md`, `14-folder-structure-dotnet.md`, plus `superseded/README.md`.

**Rewritten:** `01-system-architecture.md`, `03-backend-architecture.md`, `04-frontend-architecture.md`, `06-database-architecture.md`, `09-printing-architecture.md`, `13-deployment.md`, `14-folder-structure.md`, `15-architecture-decision-records.md`.

**Created:** `16-realtime-architecture.md`, `docs/README.md`, `docs/adr/README.md`, `docs/implementation/roadmap.md`, `docs/implementation/module-implementation-plan.md`.

**Corrected in place:** `02-domain-driven-design.md`, `07-api-architecture.md`, `08-security-architecture.md`, `10-performance-strategy.md`, `12-observability.md`, `docs/implementation/README.md`, `engineering-standards.md`, `testing-strategy.md`, `docs/adr/decisions.md`, `docs/business/assumptions.md`, `docs/engineering/open-questions.md`, all `knowledge/` summaries, `AGENTS.md`, `README.md`.

### Remaining documentation gaps

1. **`docs/modules/` does not exist** — see Current Repository State above. Consolidation before each module's implementation phase would be worthwhile.
2. **`docs/LPG_Agency_Management_System_Blueprint.pdf` has never been read by an agent.** All markdown is derived from it and is stakeholder-approved; re-deriving from source is a separate verification exercise (DW-01).
3. **Four residual design questions** in `docs/engineering/open-questions.md`, each blocking a later phase, none blocking Phase 1 (DW-02).

---

## Development Roadmap

Unchanged from the assessment, with Phase 0 now complete. Full version with rationale: [`docs/implementation/roadmap.md`](../docs/implementation/roadmap.md).

| # | Phase | Status |
|---|---|---|
| 0 | Documentation Reconciliation & Technical Baseline | ✅ **Complete** |
| 1 | Repository / Development Foundation | ✅ **Complete** |
| 2 | **Backend Foundation** | ✅ **Complete** |
| 3 | Shared Infrastructure (real-time publisher, file storage) | ✅ Complete |
| 4 | Angular 22 Web Foundation | ✅ Complete |
| 5 | Flutter Application Foundations | 🔄 In progress |
| 6 | Authentication & Authorization | Not started |
| 7 | Administration & Tenant/Master Data | Not started |
| 8 | Customer Management | Not started |
| 9 | Inventory Management | Not started |
| 10 | Order Management | Not started |
| 11 | Delivery Management | Not started |
| 12 | Cylinder Ledger | Not started |
| 13 | Accounting & Billing | Not started |
| 14 | Notifications | Not started |
| 15 | Complaint Management | Not started |
| 16 | Reporting & Analytics | Not started |
| 17 | Printing | Not started |
| 18 | Production Hardening | Not started |
| 19 | CI/CD and Deployment | Incremental from phase 1 |
| 20 | Phase 2 / AI capabilities | Deferred per A-21 |

Two sequencing notes carried forward: **real-time and printing cross-cut** rather than being built once at the end, and **Administration precedes Customer Management** because master data is a hard prerequisite.

---

## Current Priority

### Phase 2 — Backend Foundation ✅ Complete

Delivered (full detail: [`planning/features/02-backend-foundation/`](./features/02-backend-foundation/)):

1. **Unit of Work** — `SqlAlchemyUnitOfWork`: transaction boundary, audit-row writing (via a SQLAlchemy `before_flush` hook, generic across every ORM model), post-commit event dispatch (`03-backend-architecture.md` §4).
2. **One illustrative repository + CQRS use case** — `TenantRepository`/`SqlAlchemyTenantRepository`, `RenameTenantCommand`/`RenameTenantUseCase`, exercising the full Command → Application Service → Repository → UoW → domain event seam. Not a business feature (see `PLAN.md`).
3. **Domain-event dispatcher**, in-process, wired into `SqlAlchemyUnitOfWork.commit()`. The transactional-outbox seam remains documented, not built.
4. **Tenant context extension point** — `TenantResolver` protocol + interim `HeaderTenantResolver` (not a security boundary, not wired to any reachable endpoint) + `get_tenant_context`/`get_unit_of_work` FastAPI dependencies. DW-12 (mandatory resolved context) genuinely still depends on Authentication for the JWT — correctly not closed this phase, per the original plan.
5. **First three Alembic migrations** — extensions (`citext`/`pg_trgm`), `tenant.tenant` + self-referential RLS, `audit.audit_log` + RLS + database-enforced immutability. Applied to local DEV/UAT/test, and **now also applied to Supabase PROD** (2026-08-09, DW-19/DW-20 closed).
6. **Tenant-isolation test suite** (`tests/tenant_isolation/`) — two (then three) seeded tenants; read/modify/delete all proven blocked by RLS directly against the `lpg_app` role, symmetrically in both directions, with positive controls proving the negative results are RLS-specific.
7. **Background worker** — ARQ selected (ADR-029, resolves ADR-023/DW-06), worker entry point + job contract + trivial round-trip-proof job.
8. **Idempotency, caching, rate-limiting infrastructure** — all Redis-backed, tenant-aware by key convention. No `RealtimePublisher` implementation yet (ADR-015's port still unwired) — genuinely Phase 3+ scope, not attempted at the time this list was written. **`RealtimePublisher` is now implemented, in Phase 3** (2026-08-09) — see `planning/features/03-shared-infrastructure/STATUS.md`. This numbered list is left as it read at Phase 2 close-out for historical accuracy.

Still no business features. No Customer, Order, Inventory, Delivery, Accounting.

---

## Next Step

~~Await explicit instruction for the next phase.~~ **Phase 3 is now also complete** (2026-08-09) — see the top of this document and `planning/features/03-shared-infrastructure/STATUS.md`. This section (written at Phase 2 close-out) otherwise stands: `planning/features/02-backend-foundation/{PLAN,TASKS,STATUS}.md` remain the complete record of what Phase 2 delivered. Recommendation for what comes after Phase 3: **Phase 6 (Authentication)** over Phase 4/5 — it is what Phase 2's `HeaderTenantResolver`, DW-12, and Phase 3's excluded WebSocket-subscription-authorization are all waiting on.

---

## Blockers

**None blocking Phase 2.**

~~One item remains blocked within Phase 1 itself~~ — **T-34, Playwright e2e execution, resolved 2026-08-09, Phase 4.** 27/27 e2e tests passing.

~~Two items were open but not blocking~~ — **both closed 2026-08-09:**

- **DW-19 — resolved.** `lpg_app` provisioned on Supabase directly (`CREATE ROLE ... NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS INHERIT`), verified live (`rolsuper=false`, `rolbypassrls=false`, `rolcanlogin=true`). `backend/.env`'s application connection now uses `lpg_app`, not `postgres`; `LPG_MIGRATION_DATABASE_URL` carries the superuser DSN for Alembic only, per the existing role-separation design.
- **DW-20 — resolved.** `alembic upgrade head` applied all three pending migrations to Supabase: `citext`/`pg_trgm` now installed, `tenant.tenant` and `audit.audit_log` created with RLS, `lpg_app`'s table grants self-applied correctly via the migrations' own dynamic role-detection logic (SELECT/UPDATE/DELETE on `tenant.tenant`, SELECT/INSERT on `audit.audit_log`).

**One incident during DW-19, self-corrected:** the local dev role-provisioning pattern includes `REVOKE CONNECT ... FROM PUBLIC` to isolate per-database roles — appropriate on local Postgres (separate `lpg_dev`/`lpg_uat`/`lpg_test` databases) but wrong on Supabase, which is a single shared `postgres` database that other Supabase-internal service roles also connect to without an explicit grant. Running it broke the Supabase Management API/MCP tooling's own connectivity for a few minutes; caught immediately via a failed verification call, and reverted (`GRANT CONNECT ... TO PUBLIC`) before any migration or application traffic was affected. No tenant data existed yet (the tables were created moments later in the same session), so there was nothing to expose.

**A second, unrelated finding closed the same session:** Supabase's own security linter flagged `public.alembic_version` (Alembic's bookkeeping table, auto-exposed by PostgREST to the anon API by default) as having RLS disabled. Consistent with ADR-027 ("Supabase is the managed PostgreSQL host and nothing more" — PostgREST is not part of this project's architecture), RLS was enabled on it with no policies, which is the correct deny-all posture for a table nobody should ever query over REST.

---

## Open Questions

**None blocking Phase 1.**

All seven questions from the initial assessment were answered by the product owner on 2026-08-09. Deferred decisions each have a trigger point and none fall in Phase 1:

| Deferred decision | Needed by |
|---|---|
| AG Grid Enterprise licence procurement (only if a feature needs it) | As triggered — no longer a standing Phase 4 blocker |
| Warehouse Staff vs Warehouse Manager (D-38 residual) | Phase 6 |
| KYC document types (pending business/legal) | Phase 8 |
| Inventory counter granularity (D-04/D-14 residual) | Phase 9 |
| Cancellation fee amount/configurability (D-19 residual) | Phase 10 |
| PDF rendering library (WeasyPrint / ReportLab) | Phase 17 |
| Statutory backup retention duration | Phase 18 |
| Azure hosting topology + IaC tool (Bicep / Terraform) | Before production |
| Production object-storage vendor (Azure Blob if Azure is chosen; ADR-030) | Before production, tied to hosting topology |

**Revised 2026-08-09 (same day, out of session): AG Grid Enterprise is no longer a standing procurement blocker.** ADR-028 (amends ADR-020) makes AG Grid Community the default data-grid engine; Enterprise is opt-in per feature, evaluated only when a documented requirement demands it. In its place: **PrimeNG is adopted as the primary Angular UI component library**, and its licence-tier eligibility (Community vs Commercial) needed product-owner confirmation before Phase 4 (DW-22) — a much lower-stakes item than commercial AG Grid procurement, since a Community-tier PrimeNG key already exists.

**DW-22 — resolved 2026-08-09.** PrimeTek's published Community-license eligibility criteria, confirmed directly against `primeui.dev/licenses/community` — an organisation must meet **all** of:
- Under $1M USD annual gross revenue
- Fewer than 5 developers (max 4 developer seats)
- Fewer than 10 total employees
- Never received more than $3M USD in outside funding
- Not a government/tax-funded public entity or public university

Community licenses are valid 12 months, renewable at no cost by reconfirming eligibility, with a 30-day grace period after expiry. **The product owner confirmed fewer than 5 developers and $0 annual revenue** — comfortably within the two most restrictive thresholds for a small team. Employee count and outside-funding history weren't separately itemised but aren't in tension with either confirmed figure. Treated as eligible; worth reconfirming at each 12-month renewal, not just once.

---

## Important Decisions

### Recorded in Phase 0 (ADR-012 … ADR-026)

| ADR | Decision |
|---|---|
| 012 | Python 3.13 + FastAPI backend; .NET architecture superseded, preserved |
| 013 | PostgreSQL as primary relational store (supersedes ADR-005) |
| 014 | Application services with an explicit cross-cutting pipeline (supersedes ADR-004/MediatR) |
| 015 | FastAPI WebSockets + Redis Pub/Sub; real-time is Phase 1 scope (supersedes ADR-007) |
| 016 | Python rendering stack for printing (amends ADR-010); library deferred |
| 017 | PostgreSQL RLS + repository scoping for tenant isolation (amends ADR-003) |
| 018 | Angular 22 + Nx workspace under `frontend/` |
| 019 | Signals-first state management with NgRx SignalStore |
| 020 | AG Grid Enterprise behind an application-level abstraction — *amended by 028, Community now default* |
| 021 | RFC 7807 Problem Details as the API error contract |
| 022 | Azure target cloud; hosting topology and IaC tool deferred |
| 023 | Background job architecture; library deferred |
| 024 | `import-linter` + `mypy --strict` boundary enforcement |
| 025 | Polyglot monorepo layout; `frontend/` not renamed (amends ADR-001) |
| 026 | Code-first OpenAPI, generated spec committed as the frozen client contract |
| 027 | **Supabase as the managed PostgreSQL host only** — amends 013 and 022. Auth, Storage, Realtime and Edge Functions not adopted; Alembic keeps sole ownership of schema |
| 028 | **Hybrid UI strategy** — PrimeNG primary, AG Grid Community default, AG Grid Enterprise optional per feature (amends 020) |

### Decisions that survived the stack change

Worth stating, because the change was narrower than the volume of edited text suggests: ADR-001 (monorepo), ADR-002 (modular monolith), ADR-003 (shared-DB multi-tenancy), ADR-006 (Flutter), ADR-008 (offline-first Driver App only), ADR-009 (URL versioning), ADR-010 (server-rendered printing), and ADR-011 (shared-library accessibility) all stand. What changed was the backend language and framework, the ORM, the relational engine, the in-process mediation mechanism, the real-time transport, and the rendering libraries.

### Binding business decisions (unchanged, discovered in assessment)

Multi-tenant SaaS from Phase 1 (D-01) · multi-branch/warehouse (D-02) · four customer types (D-03) · configurable cylinder types × 7 statuses (D-04, D-14) · offline-first Driver App is a Must-have (D-24) · WCAG 2.2 AA is Phase 1 (D-35) · binding performance SLAs (D-34) · jurisdiction India with GST (D-06) · Phase 1 excludes the AI/integration roadmap but must stay forward-compatible in the data model (A-21, D-36).

---

## Status

**COMPLETE** — for Phase 1. 63 of 66 actionable tasks verified by running the command (95%), re-verified fresh this session with the Nx cache explicitly bypassed. 131 tests passing overall.

One verification remains **blocked**, recorded as blocked rather than complete: a live SQLAlchemy/Alembic connection to Supabase, pending credentials. Phase 1's foundation is fully verified against local PostgreSQL 17 and Redis 7.

**Phase 2 is COMPLETE**, started and finished 2026-08-09. 34/34 tracked tasks verified — see [`planning/features/02-backend-foundation/STATUS.md`](./features/02-backend-foundation/STATUS.md). 182 backend tests passing (up from 83), 230 overall across all three stacks.

---

## Last Updated

2026-08-09
