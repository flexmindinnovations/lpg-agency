# PLAN — Phase 3: Shared Infrastructure (Real-Time Publisher, File Storage)

**Feature ID:** 03-shared-infrastructure
**Phase:** Phase 3
**Type:** Foundation — reusable backend infrastructure, no business domain
**Created:** 2026-08-09
**Depends on:** [Phase 2 — Backend Foundation](../02-backend-foundation/STATUS.md) ✅ Complete

---

## Objective

Close the two shared-infrastructure items Phase 2 deliberately left open: the `RealtimePublisher` port (ADR-015) has no implementation yet, and file storage (D-40) has never been started. Both are cross-cutting seams every future business module will depend on, the same relationship Phase 2 established for Unit of Work, caching, and the background worker.

**Scope note on numbering.** `docs/implementation/roadmap.md`'s original "Phase 3 — Shared Infrastructure" line lists nine items (Unit of Work, base repository, audit logging, domain-event dispatcher, idempotency store, caching, background worker, file storage, rate limiting, real-time publisher). Seven of those nine were actually delivered under Phase 2 in this project's real execution numbering (`planning/features/02-backend-foundation/`). This phase covers only the two that weren't: **file storage** and the **real-time publisher**. No other roadmap item is in scope here.

**No business feature is implemented.** No Customer, Order, Inventory, Delivery, Accounting, Complaint, KYC upload flow. This phase builds the two infrastructure seams; the business use cases that call them arrive with the modules that need them (Phase 8 Customer/KYC, Phase 11 Delivery proof-of-delivery, Phase 13 Accounting/invoices, etc.).

---

## Scope

### Include

| Area | Deliverable |
|---|---|
| Real-time publisher | Concrete `RedisRealtimePublisher` implementing the existing `RealtimePublisher` port (`application/common/ports.py`) over the existing `RedisClient` connection, wired into `AppState`. Round-trip proof test (publish → real subscriber receives it), mirroring Phase 2's `ping` job proof. |
| File storage | New `FileStorage` port (`application/common/ports.py`) — upload / download / delete / exists / presigned-URL, tenant-scoped key convention. Concrete S3-compatible adapter (`aioboto3`) against **MinIO** for local/UAT, per the already-documented local-dev strategy (`docs/architecture/13-deployment.md` §"Local development uses ... a MinIO-compatible object store"). Wired into `AppState`, with a health check. |
| Docker Compose | Add a MinIO service to `infrastructure/docker/docker-compose.yml`, non-default ports (matching the existing Postgres/Redis convention), a dedicated dev bucket. |
| Settings | `LPG_STORAGE_*` configuration (endpoint, credentials, bucket, region), following the existing `LPG_DB_*`/`LPG_REDIS_URL` pattern — discrete, typed, validated at startup. |
| Testing | Integration tests against real Redis (publisher) and real MinIO (storage), matching the project's "real backing service, never a mock" convention. |
| Documentation | An ADR recording the file-storage port shape and the MinIO-for-now / cloud-adapter-later split (hosting topology remains open per ADR-022) — this project's established practice for a new infrastructure decision. |

### Exclude — explicitly out of scope

- **The WebSocket endpoint / connection manager / subscription authorization** (`16-realtime-architecture.md` §3, §5). Subscription authorization is explicitly defined as "checked against the same RBAC permission... required to `GET` the corresponding resource" — that requires real Authentication (Phase 6), which does not exist yet. Building the consumer side now would mean either no authorization (a tenant-isolation defect) or authorization against the interim, explicitly-untrusted `HeaderTenantResolver` (the same reasoning that kept DW-12 open in Phase 2). This phase delivers the **publish** side only — the seam Phase 6+ endpoints call into once they exist.
- **A production cloud object-storage adapter** (Azure Blob or otherwise). Hosting topology is an explicitly deferred decision (ADR-022, "Azure hosting topology + IaC tool... Before production"). Committing to a specific cloud vendor's SDK now would be building ahead of a decision nobody has made. The port is vendor-agnostic; MinIO (S3-compatible) is the real, testable adapter for every environment that exists today (local, UAT, and Supabase-hosted PROD has no object storage of its own — this remains a gap until hosting topology is decided, recorded as discovered work, not silently worked around).
- Any business use case that will eventually call these ports (KYC upload, delivery photo capture, invoice storage, order/delivery status push). Those arrive with their owning modules.
- Authentication, RBAC, tenant administration, and every other business module — unchanged from Phase 2's exclusions.

---

## Architectural Basis

| Decision | Source |
|---|---|
| FastAPI WebSockets + Redis Pub/Sub backplane, `RealtimePublisher` port | ADR-015, `docs/architecture/16-realtime-architecture.md` |
| Cloud object storage for KYC/delivery-photo/invoice/signature storage | D-40 (`docs/business/decisions.md`) |
| MinIO-compatible local dev object store, port-based vendor isolation | `docs/architecture/13-deployment.md` §"Regions & Topology" |
| Hosting topology (and therefore the production storage vendor) deliberately undecided | ADR-022 |
| Ports/adapters, `import-linter`-enforced layering | ADR-024, existing `pyproject.toml` contracts |

Full mechanism detail: `docs/architecture/16-realtime-architecture.md`, `docs/architecture/13-deployment.md`, `docs/architecture/03-backend-architecture.md` (`infrastructure/realtime/`, `infrastructure/storage/` are already named in the folder layout there).

---

## Critical Operational Note

DW-19 and DW-20 (Supabase application role, `citext`/`pg_trgm`) were resolved immediately before this phase started, in the same session — see `planning/current_phase.md`. `backend/.env` on disk now points at Supabase PROD with the `lpg_app` role, not `postgres`. Local implementation and testing for this phase use the Docker Compose stack (`./scripts/dev-up.sh`), exactly like Phase 2, and touch Supabase PROD only where a migration is genuinely required (none are, for this phase — no new tables).
