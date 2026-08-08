# 07 — API Architecture

## Purpose
Defines REST conventions, resource naming, versioning, pagination/filtering/sorting, error response format, validation, authentication/authorization touchpoints, and OpenAPI standards for the single backend API consumed by all three clients.

## Scope
Applies to the API layer of the FastAPI backend (`03-backend-architecture.md` §14). Detailed security mechanics are in `08-security-architecture.md`.

> **Stack note.** Mechanism references were rebound from ASP.NET Core to FastAPI/Pydantic in Phase 0 (2026-08-09), and JSON field naming corrected to `snake_case` per `docs/data/10-api-design-guidelines.md`. The REST conventions, versioning, pagination, and error-contract *decisions* are unchanged. See ADR-012, ADR-021, ADR-026.

## 1. REST Conventions

- Resource-oriented URLs, plural nouns: `/api/v1/orders`, `/api/v1/customers`, `/api/v1/inventory-locations`.
- Standard HTTP verbs: `GET` (read), `POST` (create / non-idempotent action), `PUT` (full replace — rarely used given CQRS command semantics), `PATCH` (partial update), `DELETE` (soft-delete, per `06-database-architecture.md` §6).
- Sub-resource nesting limited to one level for clarity: `/api/v1/orders/{orderId}/status-history`, `/api/v1/routes/{routeId}/stops`.
- Actions that don't map cleanly to CRUD are modeled as sub-resource POSTs rather than verbs in the URL: `/api/v1/orders/{orderId}/deliver` (not `/api/v1/orders/{orderId}/confirmDelivery`), `/api/v1/orders/{orderId}/cancel`.

## 2. Resource Naming

| Resource | Endpoint Root |
|---|---|
| Customers | `/api/v1/customers` |
| Orders | `/api/v1/orders` |
| Routes | `/api/v1/routes` |
| Inventory Locations | `/api/v1/inventory-locations` |
| Cylinder Ledger (per customer) | `/api/v1/customers/{customerId}/ledger` |
| Invoices | `/api/v1/invoices` |
| Payments | `/api/v1/payments` |
| Complaints | `/api/v1/complaints` |
| Reports | `/api/v1/reports/{reportType}` |
| Tenants (Super Admin only) | `/api/v1/tenants` |

## 3. API Versioning

- **URL-segment versioning** (`/api/v1/...`, `/api/v2/...`) via a versioned FastAPI router prefix, chosen over header-based versioning for discoverability and simpler client-side caching/logging (ADR-009).
- A version is only incremented for breaking changes; additive changes (new optional field, new endpoint) do not require a new version.
- Deprecated versions are supported for a documented minimum window (recommended: 12 months) with `Sunset` HTTP headers announcing removal.

## 4. Pagination

- Cursor-based pagination for high-volume/append-only lists (`LedgerTransaction`, `InventoryTransaction`, `AuditLog` history) to avoid the performance cliff of deep offset pagination.
- Offset-based pagination (`page`, `pageSize`) for smaller, UI-grid-driven lists (Orders, Customers) where users expect page-number navigation, matching the Enterprise Data Grid's pagination UX (`../srs/non-functional.md` §7).
- All paginated responses follow a consistent envelope:

```json
{
  "items": [ ... ],
  "page_info": {
    "total_count": 1450,
    "page_size": 25,
    "current_page": 3,
    "has_next_page": true
  }
}
```

JSON field naming is `snake_case` throughout, per `docs/data/10-api-design-guidelines.md` — Pydantic v2's natural serialization, with no alias configuration and no case translation anywhere in the stack.

## 5. Filtering & Sorting

- Filtering via query string, one parameter per filterable field: `GET /api/v1/orders?status=Delivered&branchId=...&fromDate=...`.
- Complex/combined filters (as needed by the Data Grid's "saved filters" feature) accepted via a structured `filter` query parameter using a documented mini-query-language (OData `$filter` subset), rather than an unbounded set of ad-hoc parameters.
- Sorting via `sort` parameter, comma-separated, `-` prefix for descending: `?sort=-requestedDate,customerName`.

## 6. Error Responses

- **RFC 7807 Problem Details** for all error responses, served with `Content-Type: application/problem+json` and extended with a stable, machine-readable `error_code` (ADR-021). The authoritative catalogue of codes is `docs/data/18-error-catalog.md`:

```json
{
  "type": "https://api.lpgplatform.com/errors/insufficient-ledger-balance",
  "title": "Insufficient cylinder ledger balance",
  "status": 409,
  "error_code": "LEDGER_INSUFFICIENT_BALANCE",
  "detail": "Customer has 0 empty cylinders; refill exchange requires at least 1.",
  "instance": "/api/v1/orders/9f2c.../deliver",
  "trace_id": "00-4bf9...-..."
}
```

- `trace_id` correlates to distributed tracing (`12-observability.md`), enabling support staff to jump from a customer-reported error directly to the relevant trace.
- Validation errors use the Problem Details `errors` extension (field → list of messages), populated from Pydantic v2 validation output and consumed directly by the Dashboard's form error-summary component (`../srs/non-functional.md` §8) and the mobile apps' form validation.
- **Success responses return the resource directly**, not wrapped in a `{"success": true, "data": …}` envelope — the HTTP status already conveys success, and unwrapping a redundant envelope in three clients is pure ceremony (ADR-021).

## 7. Validation

- Request-shape validation (required fields, format, length, range) via **Pydantic v2 request models** at the API layer (`03-backend-architecture.md` §9), returning `400` with field-level errors in the RFC 7807 `errors` extension before any domain logic executes. Domain invariants are enforced separately, inside aggregates, and are the actual guarantee.
- Business-rule validation (e.g., credit limit, cylinder cap) surfaces as domain exceptions mapped to `409`/`422` with specific `error_code`s (§6), distinct from shape validation, so clients can differentiate "fix your input" from "this action isn't currently allowed."

## 8. Authentication & Authorization (Summary — full detail in `08-security-architecture.md`)

- Every request (except login/OTP/public health-check endpoints) requires a valid JWT bearer token.
- Tenant context is resolved from a claim in the JWT (`tenant_id`), never from a client-supplied header/parameter, to prevent tenant-spoofing.
- Authorization enforced via **FastAPI dependencies** that resolve the authenticated principal and assert the required permission before the route handler executes, mapped to the confirmed RBAC role/permission model (D-38). The same permission definitions govern WebSocket subscription authorization (`16-realtime-architecture.md` §5), so the two cannot drift apart.

## 9. Idempotency

- Mutating endpoints likely to be retried by the offline-first Driver App (D-24) accept an `Idempotency-Key` header; the API persists a short-lived record of `(TenantId, IdempotencyKey) → Result` so a retried request returns the original result rather than double-applying (critical for `/orders/{id}/deliver`, `/payments`).

## 10. OpenAPI Standards

- OpenAPI 3.1 spec **auto-generated by FastAPI** from Pydantic v2 models and route metadata — code-first, never hand-maintained YAML (ADR-026, `docs/data/12-openapi-specification.md`).
- Every endpoint documented with: summary, description, request/response models, all possible `error_code`s, authentication, and example payloads. Because the spec *is* generated from this metadata, incomplete route metadata is an incomplete contract — not merely poor documentation.
- The generated spec is **exported as a build artifact and committed** to `backend/openapi/openapi.json`. A CI check fails the build if the committed spec differs from the freshly generated one, so the contract can never silently drift from the implementation.
- That committed artifact is what generates: (a) the Dashboard's typed API client, (b) the mobile `api_client` package (`05-mobile-architecture.md` §1), and (c) contract tests in CI. **Clients are never generated from a running server.**
- A change to the committed spec is a **contract change**: visible in the pull-request diff, reviewed as such, and subject to the versioning rules in §3.

## 11. Best Practices
- No breaking changes without a version bump.
- Consistent envelope/error shape across all endpoints (no ad-hoc response formats).
- All list endpoints paginated by default — no unbounded `GET /orders` returning the entire tenant's history.

## 12. Risks
- **OData filter language complexity**: a full `$filter` implementation can become a query-injection or performance risk if not carefully scoped — mitigated by whitelisting filterable fields per endpoint rather than allowing arbitrary expression trees.
- **Idempotency store growth**: mitigated with a TTL-based cleanup (e.g., 7-day retention) on the idempotency-key store, since retries beyond that window are treated as new operations by design.

## 13. Alternatives Considered
- **GraphQL** — considered for its flexible querying, especially useful for the Dashboard's varied Data Grid views; deferred for Phase 1 in favor of REST's simplicity, caching characteristics, and the team's existing familiarity; revisit if the Dashboard's data-fetching needs become significantly more complex/varied than REST comfortably serves.
- **Header-based API versioning** — rejected in favor of URL-segment versioning for simpler debugging/logging/caching (see §3).

## 14. Future Improvements
- Consider a BFF (Backend-for-Frontend) layer per client if the three clients' data-shaping needs diverge significantly enough that a single API surface becomes awkward.
- Evaluate GraphQL for the Reporting/Dashboard KPI surface specifically, where flexible, client-driven querying could reduce over-fetching.
