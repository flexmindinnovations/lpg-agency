# 10 — API Design Guidelines

## Purpose
Defines REST API standards for the FastAPI backend: design principles, naming, versioning, pagination/filtering/sorting/searching, bulk operations, optimistic concurrency, idempotency, caching, rate limiting, validation, authentication, authorization, OpenAPI standards, and RFC 7807 error responses.

## Scope
Applies to every endpoint in `11-api-contracts.md`. Implementation-independent — describes contracts and conventions, not FastAPI code.

## Design Decisions
- **OpenAPI-first mindset, code-first generation**: the team writes Pydantic v2 models and FastAPI route signatures as the source of truth; FastAPI auto-generates the OpenAPI spec from them (`12-openapi-specification.md`) — "OpenAPI-first" here means the *spec's structure and conventions* are designed deliberately up front (this document), not that YAML is hand-authored before code.

## 1. REST Design Principles
- Resource-oriented URLs, plural nouns (`/customers`, `/orders`).
- Sub-resource nesting limited to one level (`/orders/{order_id}/status-history`).
- Actions without a clean CRUD mapping are sub-resource POSTs (`/orders/{order_id}/deliver`, not a verb in the base path).
- Async all the way — every FastAPI path operation is `async def`, every database call non-blocking (SQLAlchemy 2.x async engine), so the API never blocks the event loop on I/O.

## 2. Naming Standards
| Element | Convention | Example |
|---|---|---|
| Path segments | kebab-case, plural | `/inventory-locations` |
| Query parameters | snake_case (matches Python/Pydantic convention) | `?branch_id=...` |
| JSON fields | snake_case (matches Pydantic v2 default, no camelCase aliasing needed unless a client explicitly requires it) | `"customer_type"` |
| Route function names (design intent) | verb_noun | `create_order`, `list_orders` |
| Error codes | SCREAMING_SNAKE_CASE | `CREDIT_LIMIT_EXCEEDED` |

**Design Decision:** JSON fields use `snake_case`, not `camelCase` — a deliberate deviation from the earlier .NET-stack convention, since Pydantic v2's default serialization is snake_case and forcing camelCase would require alias configuration on every model for no functional benefit; Angular/TypeScript clients adapt via a thin serialization-layer convention (documented in the frontend architecture, out of scope here) rather than forcing the backend to bend to a frontend naming preference.

## 3. Versioning
- URL-path versioning: `/api/v1/...`, `/api/v2/...`.
- Version increments only for breaking changes; additive changes never require a bump.
- Deprecated versions supported for a minimum 12-month window with a `Sunset` header.

## 4. Pagination
- **Offset-based** (`page`, `page_size`, default 25, max 100) for UI-grid-driven lists (AG Grid Enterprise on the Dashboard expects page-number navigation).
- **Cursor-based** (`cursor`, `limit`) for high-volume append-only history (`ledger_transaction`, `inventory_transaction`, `audit_log`), avoiding the performance cliff of deep offset pagination.
- Standard envelope:
```json
{ "items": [...], "page_info": { "total_count": 1450, "page_size": 25, "current_page": 3, "has_next_page": true } }
```

## 5. Filtering
- One query parameter per filterable field (`?status=delivered&branch_id=...`).
- Complex/combined filters via a whitelisted filter-expression subset for AG Grid's "saved filters" feature — never an unbounded arbitrary expression tree.

## 6. Sorting
- `?sort=field_name` ascending, `?sort=-field_name` descending, comma-separated for multi-field.

## 7. Searching
- Field-specific search via dedicated query parameters.
- Free-text search (`?q=...`) on `customer.full_name` uses PostgreSQL native full-text search (`04-database-indexing.md` §6) — no external search service needed at Phase 1 scale.

## 8. Bulk Operations
- Bulk endpoints (e.g., `POST /orders/bulk-cancel`) accept an array of IDs + a shared action payload, return a **per-item result array** (not all-or-nothing) so a partial failure in a 200-item bulk cancel doesn't block the 199 that succeeded.
- Bulk endpoints are always rate-limited more strictly than single-item endpoints (`§13`) and always asynchronous for large batches (returns `202 Accepted` + job ID, polled via `GET /jobs/{job_id}`) once the batch exceeds a configurable threshold (e.g., 50 items).

## 9. Optimistic Concurrency
- Every resource carries a `version` integer (`03-database-schema.md`); updates require the client to echo the last-read `version` (via `If-Match: "<version>"` header or a body field).
- Stale version → `409 CONCURRENCY_CONFLICT`.

## 10. Idempotency
- Mutating endpoints likely to be retried (especially the offline-first Driver App) accept an `Idempotency-Key` header.
- Server persists `(tenant_id, idempotency_key) → result` in Redis (chosen over a PostgreSQL table for this specific purpose since it's a natural TTL-based cache use case, not durable business data — `19-data-migration.md` doesn't need to know about it) with a 7-day TTL; a retried request returns the original result.

## 11. Caching
- `GET` endpoints for relatively static reference data (`05-reference-data.md`) support `ETag`/`Cache-Control`, backed by a **Redis read-through cache** at the repository layer for the same reference data (cylinder types, tenant configuration) — a documented use of Redis beyond idempotency-key storage.
- Tenant-scoped, frequently-changing data (Orders, Ledger balances) is never cached — Ledger/Inventory reads always hit PostgreSQL directly, since staleness there directly undermines the "system should always know exact customer holdings" requirement.

## 12. Error Handling — RFC 7807 Problem Details
```json
{ "type": "https://api.lpgplatform.com/errors/{error_code}", "title": "...", "status": 409, "error_code": "...", "detail": "...", "trace_id": "..." }
```
- FastAPI's exception handlers translate every domain exception to this shape uniformly — implemented as global exception handlers registered once, not per-route try/except blocks.
- Full catalog: `18-error-catalog.md`.

## 13. Rate Limiting
- Redis-backed sliding-window rate limiting, per-tenant and per-user, tuned separately for OTP-request endpoints (aggressive), standard CRUD (generous), bulk/export endpoints (strict).
- `429 Too Many Requests` with `Retry-After` header.

## 14. Validation
- **Pydantic v2** request models are the shape-validation layer — every endpoint's request body is a Pydantic model with field constraints (length, format, range) expressed declaratively; validation failures return `400` with Pydantic's field-level error detail translated into the RFC 7807 `errors` extension.
- Business-rule validation happens in the Domain layer (`07-business-rules.md`), surfaced as `409` — a clean separation between "is this request well-formed" (Pydantic, fast, no DB access) and "is this action currently allowed" (Domain, may require DB access).

## 15. Authentication
- `Authorization: Bearer <JWT>` required on every endpoint except OTP-request/login/health checks.
- Full detail: `17-api-security.md`.

## 16. Authorization
- Permission-key-driven (FastAPI dependency-injected permission checker), matching the catalog in `05-reference-data.md` §9.
- High-sensitivity actions get a live database permission re-check, not JWT-claim-only trust.

## 17. OpenAPI Standards
- FastAPI auto-generates OpenAPI 3.1 from Pydantic models and route metadata; every route includes a `summary`, `description`, `tags`, and explicit `responses=` mapping covering every possible status code (not just the happy path) — full detail `12-openapi-specification.md`.

## Best Practices
- No breaking changes without a version bump.
- Consistent envelope/error shape across all modules.
- Action sub-resources (not generic `PATCH {status}`) for state transitions.

## Risks
- Bulk operation partial-failure handling adds response-shape complexity — mitigated by a consistent per-item-result envelope applied to every bulk endpoint, never ad-hoc per feature.
- Redis as both cache and idempotency-store and rate-limiter increases Redis's blast radius if it becomes unavailable — mitigated by designing every Redis-dependent feature to **fail open or gracefully degrade** (e.g., rate limiting fails open rather than blocking all traffic if Redis is briefly unreachable; idempotency-key checks fail closed only for the specific retried request, not the whole API).

## Alternatives Considered
- GraphQL — deferred for Phase 1 in favor of REST's simplicity/caching/team familiarity; revisit for the Reporting/KPI surface if over-fetching becomes a real problem.
- camelCase JSON fields — rejected per §2's design decision.

## Future Scalability
- A BFF (Backend-for-Frontend) per client becomes worth considering if the three clients' data-shaping needs diverge significantly from a single API surface.
