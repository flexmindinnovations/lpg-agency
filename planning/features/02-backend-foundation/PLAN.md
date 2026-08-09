# PLAN — Phase 2: Backend Foundation

**Feature ID:** 02-backend-foundation
**Phase:** Phase 2
**Type:** Foundation — reusable backend infrastructure, no business domain
**Created:** 2026-08-09
**Depends on:** [Phase 1 — Repository / Development Foundation](../01-repository-foundation/STATUS.md) ✅ Complete

---

## Objective

Build the reusable backend infrastructure every future business module (Phase 6 onward) will sit on: Unit of Work, repository architecture, application-service/CQRS pattern, domain events, background-worker foundation, Redis infrastructure, idempotency, rate-limiting foundation, audit foundation, and the first real Alembic migration (tenant schema + RLS), verified with two seeded tenants.

**No business feature is implemented.** No Customer, Order, Inventory, Delivery, Accounting, Complaint. No authentication, no JWT issuance, no RBAC, no tenant administration. Those arrive in Phase 6+ behind their own plans.

Success is concrete: a future module can implement a real aggregate, repository, use case, and migration by *following the pattern already proven here*, not by inventing the pattern.

---

## Scope

### Include

| Area | Deliverable |
|---|---|
| Database foundation | Confirm/extend async engine, session factory, connection pooling, DEV/UAT/PROD configuration verified |
| Tenant context | Request → TenantContext → Application Service → Repository → PostgreSQL seam, with an explicit extension point for Phase 6 auth |
| Unit of Work | Concrete `SqlAlchemyUnitOfWork` implementing the existing `UnitOfWork` port — commit/rollback, audit-row seam, post-commit event dispatch |
| Repository architecture | `Protocol` ports (inner layers) + one illustrative SQLAlchemy repository implementation (infrastructure) — architectural example only, no business repository |
| Application services / CQRS | Command/Query base types, an application-service base, one illustrative use case exercising the full seam |
| Domain events | In-process dispatcher, handler registration, post-commit dispatch — infrastructure only, no business events |
| Background worker foundation | ADR decision (ARQ vs Dramatiq vs Celery per ADR-023/DW-06), worker process skeleton, tenant-scoped/idempotent/observable/retry-safe contract — no business jobs |
| Redis infrastructure | Cache port implementation, reusable pub/sub helper — no business usage |
| Idempotency | `Idempotency-Key` → fingerprint → stored result → replay, Redis-backed, tenant-aware |
| Rate limiting foundation | Reusable infrastructure (token bucket via Redis), not wired to aggressive limits yet |
| Error architecture | Verify existing RFC 7807 / domain / application / infrastructure exception layering is complete |
| Observability | Verify structured logging, correlation ID, tenant context, request duration remain wired through the pipeline |
| Audit foundation | `audit.audit_log` table + repository-level write path (actor, tenant, action, entity, entity_id, timestamp, correlation_id, metadata) |
| Database extensions | Alembic migration enabling `citext` and `pg_trgm` (already present locally; needed on hosted Supabase) |
| Tenant schema + RLS | First real migration: `tenant.tenant` table only, with RLS policy, verified with two seeded tenants (read/modify/delete isolation) |
| Testing | Tests for every item above, using real PostgreSQL/Redis integration tests per existing convention |
| OpenAPI | Verify generation, RFC 7807, correlation ID, health endpoints, versioning, drift-check remain green |
| Frontend/mobile regression | Confirm no unrelated regression after backend work |

### Exclude — explicitly out of scope

Authentication · Login · Registration · OTP · JWT issuance · Refresh tokens · RBAC · User management · Tenant administration · Customer management · Cylinder management · Inventory · Booking · Orders · Delivery · Payments · Accounting · Complaints · Notifications · Reporting · Printing UI/business workflows.

`identity.identity_user`, `customer.customer`, and every other business table are **not created**. Only `tenant.tenant` (the minimum needed to prove the tenant-scoping seam and RLS with two real rows) is created this phase.

---

## Architectural Basis — ADRs This Phase Implements

| Decision | Source |
|---|---|
| Python 3.13 + FastAPI + SQLAlchemy 2.x + Alembic + Pydantic v2 | ADR-012 |
| PostgreSQL, hosted on Supabase (PROD only — DEV/UAT are local Docker) | ADR-013, ADR-027 |
| Application services, explicit cross-cutting pipeline, no mediator library | ADR-014 |
| PostgreSQL RLS + repository scoping, four-layer defense in depth | ADR-017 |
| Background job architecture (conceptual); library selection resolved this phase | ADR-023 |
| RFC 7807 Problem Details error contract | ADR-021 |
| `import-linter` + `mypy --strict` boundary enforcement | ADR-024 |

Full mechanism detail: `docs/architecture/03-backend-architecture.md`, `docs/architecture/06-database-architecture.md`.

---

## Critical Operational Note — DEV / UAT / PROD

Verified by inspection before any implementation work:

- **DEV** = local Docker PostgreSQL, database `lpg_dev`, role `lpg_app` (`NOSUPERUSER`, `NOBYPASSRLS`). Already running and healthy (`lpg-postgres` container).
- **UAT** = local Docker PostgreSQL, database `lpg_uat`, role `lpg_app_uat` — same instance, separate database and credential, same engine/extension parity as production.
- **PROD** = the real hosted Supabase project (`ayqphthelemlnbtnknkp`), reached only via `LPG_DB_HOST=db.ayqphthelemlnbtnknkp.supabase.co` / the transaction pooler.
- `citext` and `pg_trgm` are **already installed locally** (DEV and UAT, via `infrastructure/docker/postgres/init/01-init.sql`). They are **not yet installed on the hosted Supabase PROD project** (confirmed live in Phase 1; only `pgcrypto` is present there).

**`backend/.env` currently on disk is configured for PROD** — `LPG_ENVIRONMENT=production`, pointing at the real Supabase host with the `postgres` superuser credential, left over from Phase 1's live-connection verification. `Settings()` reads this file automatically via `pydantic-settings`' `env_file=".env"`, so **any ad hoc command that constructs `Settings()` without controlling the environment would target the live Supabase project.**

**Working rule for this phase:** every database operation (migrations, tests, manual verification) targets **local Docker DEV/UAT explicitly** via environment variables passed to that specific command — never the ambient `backend/.env`. The existing test suite already does this correctly (`conftest.py`'s `_no_real_dotenv` autouse fixture, `integration_settings` fixture). `backend/.env` itself is left untouched — it is the user's own local, git-ignored file, and overwriting it is not this phase's call to make. The tenant-schema-and-RLS migration is applied to **local DEV and UAT only**. It is **not applied to the hosted Supabase PROD project** in this phase — the citext/pg_trgm and tenant-schema migrations against PROD are recorded as follow-up items requiring explicit go-ahead, per the instruction to "verify PROD only when explicitly safe."

---

## Non-Goals / Explicit Deferrals

- **Tenant-scoped session dependency that *requires* a resolved context** (closing DW-12) genuinely depends on Authentication for the JWT (Phase 6). This phase provides the extension point (a `Protocol` and an explicit, clearly-labeled optional parameter) but cannot make it mandatory without authentication existing.
- **Transactional outbox** for domain events (durable cross-process dispatch) is a documented future seam (`03-backend-architecture.md` §6), not built this phase — in-process, post-commit, synchronous dispatch is the Phase 1/Phase 2 design.
- **Business jobs** (refill reminders, SLA breach scanner, etc.) are not implemented — only the worker architecture and library choice.

---

## Verification Strategy

Every task follows AGENTS.md Step 5: build succeeds, lint passes (`ruff`), types pass (`mypy --strict`), architecture boundaries pass (`import-linter`), tests pass (`pytest`, including new integration tests against local Docker PostgreSQL/Redis) — before being marked complete in `TASKS.md`. No task is marked complete from code inspection alone.

Final phase-level verification re-runs the full backend suite, the architecture-consistency checker, and a frontend/mobile regression pass, exactly as Phase 1 did.
