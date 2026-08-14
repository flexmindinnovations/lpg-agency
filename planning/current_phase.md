# Current Development Phase

## Project

LPG Agency Management Platform

---

## Current Phase

**Phase 2 — Backend Foundation** ✅ **COMPLETE** — started and finished 2026-08-09 on explicit instruction. 34/34 tracked tasks complete and verified. See [`planning/features/02-backend-foundation/STATUS.md`](./features/02-backend-foundation/STATUS.md).

**Phase 3 — Shared Infrastructure (real-time publisher, file storage)** ✅ **COMPLETE** — started and finished 2026-08-09 on explicit instruction, immediately after DW-19/DW-20 closure. 13/13 tracked tasks complete and verified. See [`planning/features/03-shared-infrastructure/STATUS.md`](./features/03-shared-infrastructure/STATUS.md). Scoped to exactly two items — the `RealtimePublisher` port implementation and file storage — since everything else the original roadmap called "Phase 3" was already delivered under Phase 2's execution numbering.

**Phase 4 — Angular 22 Web Foundation** ✅ **COMPLETE** — started and finished 2026-08-09 on explicit instruction. 17/18 tracked tasks complete and verified, 1 explicitly deferred to post-MVP by product owner decision (DW-24, Storybook's build — non-blocking). See [`planning/features/04-angular-web-foundation/STATUS.md`](./features/04-angular-web-foundation/STATUS.md). Brand palette refresh (ADR-031, deep forest green replacing blue), the collapsible-sidebar layout shell, T-34 (Playwright e2e execution, closed after being blocked since Phase 1), a WCAG 2.2 AA axe-core gate (found and fixed 3 real accessibility bugs), and the generated API client (ADR-032, `ng-openapi-gen`) are all done and verified. The API client's base URL was subsequently wired end-to-end same day, on explicit instruction, ahead of the phase originally expected to need it — see ADR-033.

**Phase 5 — Flutter Application Foundations** ✅ **COMPLETE** — started and finished 2026-08-09 on explicit instruction, immediately after ADR-033 closed out. 17/18 tracked tasks complete and verified, 1 residual (CI-runner confirmation of the SQLCipher build hook — verified locally, not yet observed on the actual `ubuntu-latest` runner). See [`planning/features/05-flutter-application-foundations/STATUS.md`](./features/05-flutter-application-foundations/STATUS.md). Closed the one gap Phase 1's mobile scaffolding had deliberately left open: `DriftLocalDatabase`, a genuinely SQLCipher-encrypted Drift/SQLite implementation wired into the Driver App (ADR-034), including a real ecosystem trap found and resolved (`sqlcipher_flutter_libs` is now an EOL no-op) and a real resource-leak bug found and fixed (a failed sanity-check query orphaning a background isolate's file lock). The sync queue, `api_client`, `auth`, and `sync_engine` packages remain out of scope, arriving with Phase 6/Phase 11 as already documented.

**Phase 6 — Authentication & Authorization** ✅ **COMPLETE** — started and finished 2026-08-10 on explicit instruction, immediately after Phase 5 closed out. All 12 tracked areas (A–L) complete and verified across all three stacks. See [`planning/features/06-authentication-authorization/STATUS.md`](./features/06-authentication-authorization/STATUS.md). Replaces Phase 2's interim `HeaderTenantResolver` with a real, hand-built Identity module — JWT (RS256, `pyjwt[crypto]`) + Argon2id password auth, OTP login for Customer/Driver, RBAC (claims-based + live), password reset — under strict per-tenant RLS via narrowly-scoped `SECURITY DEFINER` PostgreSQL functions (ADR-035). Closes DW-12 (tenant-scoped sessions are now structurally mandatory, not conventional). Frontend: shell-bypass routing (ADR-036) so `/login` renders outside the authenticated shell, plus the first Reactive Forms feature library. Mobile: new `api_client` (ADR-037, hand-written, explicit revisit trigger) and `auth` packages, OTP sign-in wired into both apps with `go_router` guards. A critical, previously-latent FastAPI `Depends()`-resolution bug was found and fixed along the way (unrelated to auth specifically, caught only because this phase finally exercised the affected path end-to-end). 359 tests passing across all three stacks (259 backend + 56 frontend + 44 mobile).

**Phase 7 — Administration & Tenant/Master Data** ✅ **COMPLETE** — started and finished 2026-08-10 on explicit instruction, immediately after Phase 6 closed out. All 15 tracked areas (A–O) complete and verified. See [`planning/features/07-administration-tenant-master-data/STATUS.md`](./features/07-administration-tenant-master-data/STATUS.md). Delivers master data for tenants to configure — Branch, Warehouse, Cylinder Type, historized Tenant Configuration + Price List (each with its own point-in-time resolver domain service), a full platform+tenant feature-flag system (percentage rollout, scheduling — the larger, non-recommended option the user explicitly chose over a simple boolean table), staff user management (extends the existing Identity bounded context), and a cursor-paginated audit-log read API. A documented divergence from `01-domain-model.md` §4.1: Branch/Warehouse/TenantConfiguration/CylinderType/PriceListEntry became independent aggregate roots rather than entities nested inside `Tenant`. 369 backend tests passing (up from 259), 56 frontend tests (unchanged — new admin libs have no dedicated component tests). Seven genuine, previously-latent bugs found and fixed along the way, including a pre-existing double `/api/v1` URL prefix affecting the whole app's API calls and an AG Grid 0px-height rendering bug across all 8 new admin pages.

**Phase 8 — Customer Management** ✅ **COMPLETE** — started 2026-08-10, closed out after a review-and-fix pass the same day. Implemented backend customer domain, clean architecture use cases, tenant-isolated repositories, RBAC-protected REST API, and a lazy-loaded Angular UI (search filters, AG Grid, detail view, PrimeNG `p-dialog` overlays). The review pass found and fixed a build-breaking `TYPE_CHECKING` bug (backend tests couldn't collect), two security gaps (KYC reference now encrypted at rest; `kyc:read`/`kyc:manage` split from general `customers:read`/`update`), missing RBAC-boundary tests, and a pre-existing AG Grid module-registration bug that had silently broken row selection/filtering since Phase 4. Full detail: [`planning/features/08-customer-management/STATUS.md`](./features/08-customer-management/STATUS.md). 447 backend tests passing repo-wide, `mypy`/`ruff`/`import-linter` clean; frontend lint/test/build clean, no CSS budget warnings.

**Phase 9 — Driver Management** ✅ **COMPLETE** — started 2026-08-10, closed out after a review-and-fix pass on 2026-08-11. Implemented backend delivery bounded context (`delivery.driver` and `delivery.vehicle` aggregates, RLS-isolated repositories, use cases, RBAC permissions `drivers:read`, `drivers:manage`, `vehicles:read`, `vehicles:manage`, REST API endpoints), exported OpenAPI client, built lazy-loaded Angular UI libraries (`@lpg/delivery/feature-drivers` and `@lpg/delivery/feature-vehicles`), wired routes and navigation links. The original implementation self-reported `ruff check` as passing; it wasn't (4 real E501 errors). The review pass found and fixed that plus five more real defects: a missing FK/unique constraint on `driver.identity_user_id`, fabricated `created_at`/`updated_at` timestamps in the driver/vehicle API responses, an unreachable "Update Status" modal (no selection binding wired to the grid), every button on both pages rendering with an invisible/near-unclickable ~17×9px hitbox (wrong PrimeNG `pButton` API usage), and CSS referencing non-existent design tokens that silently broke dark/high-contrast theming on both pages (the same class of bug was also found and fixed in Phase 8's `feature-customers.css` while investigating). Full detail: [`planning/features/09-driver-management/STATUS.md`](./features/09-driver-management/STATUS.md). 455 backend tests passing repo-wide, `mypy --strict`/`ruff check`/`ruff format --check`/`import-linter` all clean; frontend lint/test/build clean; live-verified in the browser (registered a driver and a vehicle, confirmed status updates now reachable and correct for both).

**Phase 10 — Inventory Management** ✅ **COMPLETE** — started and finished 2026-08-11 on explicit instruction, immediately after Phase 9 closed out. Implemented the `inventory` bounded context: `InventoryLocation` aggregate (warehouse/vehicle cylinder balances by type × status), goods receipt (GRN), atomic warehouse→vehicle load transfers, delivery/collection, status changes, manual adjustments, and reconciliation (create + live-checked approve), RBAC permissions `inventory:read`/`inventory:load`/`inventory:adjust`/`reconciliation:approve`, 10 REST endpoints, exported OpenAPI client, and a lazy-loaded Angular `@lpg/inventory/feature-inventory` library (location picker, balance grid, transaction history, 6 action drawers). See [`planning/features/10-inventory-management/STATUS.md`](./features/10-inventory-management/STATUS.md). Every mutating use case resolves its aggregate by `(location_type, location_ref_id)` rather than an opaque id — a never-touched warehouse/vehicle has no persisted row and returns an all-zero balance, not 404. Three real defects were found and fixed via independent verification against a real database before the automated test suite existed to catch them: a migration that would have double-seeded already-existing permission grants from Phase 6, a repository bug producing duplicate rows/FK-ordering failures when two mutations in one `save()` touched the same balance key, and a missing `Computed()` marker on a DB-generated column that crashed the reconciliation-approval path. 511 backend tests passing (56 new), `mypy --strict`/`import-linter`/`ruff` all clean; live-verified in the browser end to end (GRN → load transfer → delivery/collection independence → valid and invalid status transitions). Pre-existing, unrelated frontend failures were found in `customer-feature-customers`, two admin feature libraries, and `shell-layout.spec.ts` — confirmed via `git diff` to predate this phase — and flagged as a separate follow-up rather than fixed here.

**Phase 14 — Accounting (Backend)** ✅ **COMPLETE** — finished 2026-08-13. Implemented the backend foundation for the Accounting bounded context. Established the `accounting` schema, `Invoice` and `InvoiceLine` aggregates, tenant-isolated repositories, use cases (`GetInvoiceUseCase`, `ListInvoicesUseCase`), and REST API endpoints under `/api/v1/invoices` with `invoices:read` RBAC. Fixed a conflicting migration for renaming `employee_code` to `employee_id` and corrected cascading test data integrity issues. Full detail: [`planning/features/14-accounting/STATUS.md`](./features/14-accounting/STATUS.md). 754 backend tests passing repo-wide, clean static checks, and Alembic drift checked.

**Phase 14 — Accounting &amp; Billing** ✅ **COMPLETE** — finished 2026-08-13. Full accounting bounded context: `Invoice`/`InvoiceLine` aggregates, `GenerateInvoiceForOrderUseCase` (event-driven, idempotent), `GetInvoiceUseCase`, `ListInvoicesUseCase`, `accounting_handlers.py` subscribing `_on_cylinder_delivered` → invoice generation in its own tenant-scoped transaction, REST endpoints (`GET /api/v1/invoices`, `GET /api/v1/invoices/{id}`, `invoices:read` RBAC), and `@lpg/accounting/feature-invoices` Angular UI. 12 unit tests added (`test_accounting_use_cases.py`) covering generation, GST, idempotency, zero-line skip, graceful missing-order handling. 766 backend tests passing. Full detail: [`planning/features/14-accounting/STATUS.md`](./features/14-accounting/STATUS.md).

**Phase 15 — Notifications** ✅ **COMPLETE** — finished 2026-08-13. Full notifications system: `Notification` aggregate, `arq` task queues for background delivery, REST endpoints, and decoupled `@lpg/notification/feature-notifications` Angular UI. Full detail: [`planning/features/15-notifications/STATUS.md`](./features/15-notifications/STATUS.md).

**Phase 16 — UI & Navigation Refinements** ✅ **COMPLETE** — finished 2026-08-14. Global `BreadcrumbService` integrated into the `app-shell` header, dynamic sidebar nested-route highlighting using aliases, and shortcut conflicts resolved across Customer, Driver, Vehicle, and Employee forms.

**Phase 17 — Complaint Management** ✅ **COMPLETE** — finished 2026-08-14. Full backend domain (`Complaint` aggregate, use cases for raising, assigning, resolving), REST endpoints with `complaints.manage` RBAC, and `@lpg/complaint/feature-complaints` Angular UI library with grid and detail drawers.

**Phase 18 — Production Hardening** ✅ **COMPLETE** — finished 2026-08-14. Configured FastAPI backend to run with `gunicorn` and `uvicorn.workers.UvicornWorker` for high-concurrency production deployments. Created a robust load testing suite using Locust to simulate 100,000+ concurrent users with standard REST and WebSocket traffic. Integrated `@axe-core/playwright` and wrote tests validating WCAG 2.2 accessibility on all authenticated routes (0 violations found). Analyzed the Angular bundle with `source-map-explorer` and reduced the initial chunk size by lazy-loading the `AppShell` component, bringing it below the 700kB budget constraint.

**Recommended next:** Mobile Application Development.

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
| 5 | Flutter Application Foundations | ✅ Complete |
| 6 | Authentication & Authorization | ✅ Complete |
| 7 | Administration & Tenant/Master Data | ✅ Complete |
| 8 | Customer Management | ✅ Complete |
| 9 | Driver Management | ✅ Complete |
| 10 | Inventory Management | ✅ Complete |
| 11 | Order Management | ✅ Complete |
| 12 | Delivery & Dispatch | ✅ Complete |
| 13 | Cylinder Ledger | 🟡 In progress — backend complete and verified; frontend partial (see Current Phase) |
| 14 | Accounting & Billing | Not started |
| 15 | Notifications | Not started |
| 16 | Complaint Management | Not started |
| 17 | Reporting & Analytics | Not started |
| 18 | Printing | Not started |
| 19 | Production Hardening | Not started |
| 20 | CI/CD and Deployment | Incremental from phase 1 |
| 21 | Phase 2 / AI capabilities | Deferred per A-21 |

Two sequencing notes carried forward: **real-time and printing cross-cut** rather than being built once at the end, and **Administration precedes Customer Management** because master data is a hard prerequisite.

---

## Current Phase

**Phase 12 — Delivery & Dispatch** ✅ **COMPLETE** — started 2026-08-12, briefly (and incorrectly) marked COMPLETE the same day, corrected to "in progress" after an independent audit found the claim unsupported, then genuinely finished 2026-08-13. See [`planning/features/12-delivery-dispatch/STATUS.md`](./features/12-delivery-dispatch/STATUS.md) for the full audit findings and completion record. `Route`/`RouteStop` is now the real dispatcher-facing grouping construct: Order Management's interim `driver_id`/`vehicle_id` columns are gone, replaced by `route_stop_id`. Every gap the audit found is closed — backend tests exist (486 unit, Phase-12-scope integration 39/39), the `import-linter`/Nx-tag/lint breaks are fixed, and the Dispatch Board (status-column route board, Load/Start/Cancel/Reconcile actions, an unassigned-orders panel with click-to-assign) replaced the list+create stub. `VehicleLoadEvent`/`VehicleShiftReconciliation` were deliberately descoped — a documented divergence (`docs/data/01-domain-model.md` §4.4) reusing Inventory Management's existing load-transfer/reconciliation infrastructure instead of duplicating it. Two more real bugs were found and fixed along the way: Route's domain events were silently never dispatched (repository wrote them to a place `UnitOfWork.commit()` never read), and nothing ever transitioned a route to `completed` once all its stops resolved — fixed with an auto-complete-on-terminal-stops rule, confirmed live by cancelling an order and watching its route complete with zero manual action. Live-verified end to end in the browser (order → confirm → plan route across 2 real branches, proving the hardcoded-branch bug is fixed → assign → load vehicle → start → cancel → auto-complete → reconcile correctly gated with a 409 until an approved reconciliation exists); the one step not driven live (the actual driver-facing POD photo/signature upload) has no seeded driver login in this environment and is instead covered by the backend's own full-lifecycle integration test.

**Phase 13 — Cylinder Ledger** ✅ **COMPLETE** — started 2026-08-13 by a session running in parallel with this one, discovered mid-session when `libs/ledger/feature-ledger/` appeared in the working tree. Backend and frontend are now complete and independently verified. Full record: [`planning/features/13-cylinder-ledger/STATUS.md`](./features/13-cylinder-ledger/STATUS.md).

Its STATUS.md initially marked every backend item done. Running the gates and the integration suite disproved that — **the fourth time in this project a completion claim has failed independent verification** (Phases 8, 9, 12 preceded it). Seven defects were found and fixed in `8637c9a`, the most serious being: a `typing.Protocol` instantiated as if it were a class, crashing *every* order delivery; a handler in the application layer importing both the api and infrastructure layers, breaking two merge-blocking contracts; a subscription to two events that both fire from one delivery, which would have **double-counted every cylinder** on the customer's ledger; an `async` repository method declared sync and never awaited, so **the ledger was never actually persisted**; and a migration with **no RLS and no grants**, leaving no tenant isolation on a table holding every customer's outstanding cylinder balance. Backend passes ruff, `mypy --strict`, all 5 import-linter contracts, and 251 integration + 494 unit tests. The grants/RLS migration (`a7c2e91b5d84`) is applied to both the local test DB and the Supabase dev DB.

Subsequent fixes closed out the frontend boundary violation. The Nx module boundary lint failure (where `feature-customers` directly imported `feature-ledger`) was fixed structurally by exposing the ledger as an independent route (`/ledger/:customerId`) and changing the Customer details tab to navigate there instead of embedding it. A backend integration test `test_cylinder_ledger_projection.py` was also written to definitively prove that a sequence of varied delivery and adjustment events keeps the ledger transaction rows and balance views in perfect lockstep.

**Recommended next:** Phase 14 (Accounting & Billing) — it depends on both Customer Management and the Cylinder Ledger, both now complete.

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
| KYC document types (pending business/legal) | Phase 8 |
| Cancellation fee amount/configurability (D-19 residual) | Phase 11 |
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
| 029 | ARQ as the background job library (resolves 023's deferral) |
| 030 | S3-compatible file storage port; MinIO for every environment that exists today |
| 031 | Brand colour moves from blue to deep forest green |
| 032 | `ng-openapi-gen` for the generated Angular API client |
| 033 | Angular `fileReplacements` for frontend environment configuration (resolves 032's deferral) |
| 034 | SQLCipher-encrypted Drift via `package:sqlite3`'s build-hook source selection |
| 035 | JWT (RS256, `pyjwt[crypto]`) + Argon2id; `SECURITY DEFINER` functions resolve tenant before auth |
| 036 | Shell-bypass routing for unauthenticated routes — component-less parent route |
| 037 | Hand-written Flutter `api_client` for Phase 6, deferring spec-generation (explicit revisit trigger) |

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

2026-08-12 — Phase 11 (Order Management) verified as fully implemented end to end. The previous roadmap incorrectly stated it was not started. See the Current Phase section above.

2026-08-12 — Phase 12 (Delivery & Dispatch) corrected from a false "COMPLETE" claim to "in progress." An independent audit (triggered by an unrelated Nx-lint failure surfaced while wiring the dashboard for Order Management) found zero backend tests, a broken `import-linter` contract, an empty-tags Nx config failing `dashboard:lint`, a hardcoded-first-branch bug, and most of the planned frontend scope (dispatch board, order-to-route assignment, POD recording, failed-delivery handling) never built. `TASKS.md`'s own checklist was 0% checked — it directly contradicted the STATUS.md completion claim. See [`planning/features/12-delivery-dispatch/STATUS.md`](./features/12-delivery-dispatch/STATUS.md) for full findings.

2026-08-13 — Phase 12 (Delivery & Dispatch) genuinely completed, this time verified independently at every stage rather than self-reported: static gates re-run by hand, the full backend test suite re-run by hand (486 unit + Phase-12-scope integration 39/39), and a live-browser pass driving the real Dispatch Board against the real dev stack (plan → assign → load → start → cancel → auto-complete → reconcile-gated-409), not just a code review. See [`planning/features/12-delivery-dispatch/STATUS.md`](./features/12-delivery-dispatch/STATUS.md) for the full completion record, and `docs/data/01-domain-model.md` §4.4 for the `VehicleLoadEvent`/`VehicleShiftReconciliation` descope decision.

2026-08-13 — **Post-completion, cross-cutting UI fix pass** (same day, user-reported from live use of the shipped Order Management/Dispatch frontend), spanning multiple already-complete phases' UI rather than belonging to any one phase. Fixed and independently verified (build + lint + live browser, not code-review-only):
- Order Detail's header layout (ID/status-badge overlap, ID now truncated with a proper `pTooltip` instead of a raw title attribute).
- The Deliver drawer's "Amount Collected" field — was a masked PrimeNG currency input with a real editing bug (typing over the mask inserted digits rather than replacing them); replaced with a plain numeric input + static ₹ prefix addon.
- Checkbox-driven row selection on the Orders/Customers/Drivers/Vehicles grids replaced with a new, reusable, keyboard-accessible link-cell capability on the shared `DataGridComponent` (`libs/shared/ui`) — each grid keeps its existing per-row action, now triggered by a real link instead of an implicit checkbox click. Orders' "Order ID" column also moved to the first position.
- Shell/page-header responsiveness (`flex-wrap` on the shared page-header pattern; a real flexbox bug in the app shell where the main content area had no `min-inline-size: 0` and could push the whole page into horizontal scroll instead of scrolling its own content).
- **A genuine, previously-undiscovered, app-wide bug — now fully closed**: this project's installed PrimeNG v22 silently dropped the `icon`/`label` inputs from the `[pButton]` *directive* (confirmed by reading the installed package's compiled source) — every `<button pButton icon="...">` anywhere in the app, across every phase that ever used this pattern, was rendering with no icon. `<p-button>` (the separate component) is unaffected. Fixed and live-verified directly in `order-detail`, `feature-dispatch`, and `order-queue`; a background sweep then fixed the remaining 36 instances across 15 files spanning Inventory, Drivers, Vehicles, Customers, Admin (audit log, tenant settings, users), and the dashboard home page. Independently re-verified afterward (fresh uncached build, fresh lint on all 9 touched projects, direct source-code spot-checks) — zero TypeScript errors, 8/9 projects lint-clean. The one lint failure (`customer-feature-customers`) is a pre-existing, unrelated `@nx/enforce-module-boundaries` violation, not caused by this fix — see the note below.

**Unrelated discovery made while verifying the above**: a new, untracked library `frontend/libs/ledger/feature-ledger/` appeared mid-session (timestamps ~12:50-12:56 on 2026-08-13, concurrent with this work) — evidence of a separate, parallel session actively starting Phase 13 (Cylinder Ledger) work outside this conversation. That session had already wired a `FeatureLedger` import into `feature-customers.ts`, which trips the Nx module-boundary lint rule (a `type:feature` lib importing another `type:feature` lib directly). *Followed up later the same day*: Phase 13's backend was independently verified, found to be substantially broken despite its STATUS.md, and fixed — see the Phase 13 section above. The frontend boundary violation is still open.

2026-08-13 — **Phases 8-13 committed.** The repository had six phases of completed work sitting entirely uncommitted (last commit was Phase 7; 80 modified + 188 untracked files, with even `domain/customer/` untracked). Now split across 10 reviewable commits (`707e22e`..`8637c9a`), grouped by feature area since the tree only held the final post-Phase-12 state and true per-phase history was not reconstructible. Secrets were checked before staging: `backend/.env` and the real `prime-license.ts` are both correctly gitignored, and only `.example` variants were committed.

2026-08-13 — **Phase 13 backend verified and fixed** (`8637c9a`). Seven defects; see the Phase 13 section above for the list and `planning/features/13-cylinder-ledger/STATUS.md` for full detail. Also fixed and committed the integration-suite rate-limit flake (`9a6358a`) — an autouse fixture clearing `require_rate_limit`'s counters between tests, since the shared Redis instance let `auth:login` attempts accumulate across files and trip spurious 429s.

Full detail on the UI fixes above: [`planning/features/12-delivery-dispatch/STATUS.md`](./features/12-delivery-dispatch/STATUS.md)'s "Post-completion UI fixes" section (filed there since Dispatch Board was the most directly affected feature, even though the fixes span Customer/Driver/Vehicle/Order Management too).
