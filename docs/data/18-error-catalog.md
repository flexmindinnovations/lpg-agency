# 18 — Error Catalog

## Purpose
Centralizes every API error: code, HTTP status, business meaning, message, recovery suggestion, and related module.

## Scope
Covers all `error_code` values referenced across `11-api-contracts.md` and `13-validation-rules.md`.

## Format
RFC 7807 Problem Details, extended with `error_code` (`10-api-design-guidelines.md` §12):
```json
{ "type": "https://api.lpgplatform.com/errors/{error_code}", "title": "...", "status": 409, "error_code": "...", "detail": "...", "trace_id": "..." }
```
Field-level failures (`REQUEST_VALIDATION_FAILED`, `VALIDATION_FAILED`) additionally carry an `errors` extension: `{"field_name": ["message", ...], ...}`.

## Reconciled 2026-08-09 (Phase 2)
This catalog was authored in Phase 0 against the original SRS business-error vocabulary, before any backend code existed. It has now been checked line-by-line against the actual implementation — `backend/src/lpg/application/common/errors.py`, `backend/src/lpg/domain/common/base.py`, and `backend/src/lpg/api/middleware/problem_details.py` — and corrected. Three real naming/description mismatches were found and fixed (not just additions):

- **`NOT_FOUND` → `RESOURCE_NOT_FOUND`.** The implementation has always used the longer name (`NotFoundError.error_code`); the catalog had the shorter one.
- **`TOO_MANY_REQUESTS` → `RATE_LIMIT_EXCEEDED`.** Same kind of mismatch — `RateLimitExceededError.error_code` is `RATE_LIMIT_EXCEEDED`, not `TOO_MANY_REQUESTS`.
- **`INTERNAL_ERROR` → `INTERNAL_SERVER_ERROR`.** `unhandled_exception_handler` emits `INTERNAL_SERVER_ERROR`.
- **`VALIDATION_FAILED`'s description was wrong, not just its neighbors missing.** The catalog described it as "Pydantic shape validation failure" — that is actually a *different*, previously undocumented code: **`REQUEST_VALIDATION_FAILED`**, emitted automatically for any Pydantic request-model failure. `VALIDATION_FAILED` (`ValidationError`) is the **application layer's** cross-entity precondition check — something that needs a database lookup to evaluate (e.g. "does this customer exist in this tenant"), never a shape/type/format problem. Conflating the two would have sent a client down the wrong recovery path for one of them.

No status code was found to be wrong — every implemented `http_status` matches what its handler actually returns. This was a documentation-only reconciliation; no application code changed.

**On the business-domain codes** (`DUPLICATE_PHONE`, `CREDIT_LIMIT_EXCEEDED`, and the rest below the cross-cutting table): none are implemented yet, and none needed renaming. They remain **exactly what they always were** — application-specific codes that will each become a concrete exception subclassing `BusinessRuleViolation`, `InvariantViolation`, `ConflictError`, or `ApplicationError` (the same pattern `ConcurrencyConflictError` and `IdempotencyConflictError` already use) when the module that owns them is built. This catalog now marks each row's actual implementation status explicitly, so this distinction never has to be re-derived by reading source code again.

## Cross-Cutting Error Codes (Implemented)

Available today, regardless of which business module a request touches. Source: `application/common/errors.py`, `domain/common/base.py`, `api/middleware/problem_details.py`.

| Error Code | HTTP Status | Message | Business Meaning | Recovery Suggestion | Source |
|---|---|---|---|---|---|
| `RESOURCE_NOT_FOUND` | 404 | "No customer exists with the supplied identifier." *(example — `detail` is set per call site)* | Resource doesn't exist, or exists but isn't visible to the caller's tenant — **deliberately indistinguishable**, so a cross-tenant read can't be inferred from status code alone | Verify the resource ID | `NotFoundError` |
| `PERMISSION_DENIED` | 403 | "Missing permission: {permission}." | RBAC/permission failure | Contact an administrator for access | `PermissionDeniedError` |
| `AUTHENTICATION_REQUIRED` | 401 | "Authentication is required." | No valid credentials were supplied | Log in / supply valid credentials | `AuthenticationError` |
| `TENANT_CONTEXT_MISSING` | 401 | "Required header 'X-Debug-Tenant-Id' was not supplied." *(Phase 2 interim resolver; message changes once JWT-based resolution lands in Phase 6)* | No tenant context could be resolved for the request | Supply a valid tenant context / re-authenticate | `TenantContextMissingError` (subclasses `AuthenticationError`) |
| `CONCURRENCY_CONFLICT` | 409 | "This record was modified by someone else. Please refresh and try again." | Optimistic concurrency — stale `version` on write | Refetch the resource and reapply the change | `ConcurrencyConflictError` |
| `IDEMPOTENCY_KEY_CONFLICT` | 409 | "This Idempotency-Key was already used with a different request." | The same `Idempotency-Key` was reused with a different request fingerprint | Use a new Idempotency-Key for a genuinely different request; retry the original request unchanged to replay its result | `IdempotencyConflictError` |
| `RATE_LIMIT_EXCEEDED` | 429 | "Rate limit exceeded for {key}." | Caller exceeded the permitted request rate for the current window | Wait for the `retry_after_seconds` duration | `RateLimitExceededError` — **foundation only; not yet wired to any endpoint** (Phase 2) |
| `VALIDATION_FAILED` | 422 | (message set per call site) | **Application-layer** precondition failure requiring a lookup (e.g. a referenced entity must exist) — never a shape/type/format problem | Fix indicated fields and resubmit | `ValidationError` |
| `REQUEST_VALIDATION_FAILED` | 422 | "One or more fields failed validation." | **Pydantic** request-shape validation failure (type, format, required field) — caught before any application code runs | Fix indicated fields and resubmit | `validation_error_handler` (`RequestValidationError`) |
| `SERVICE_UNAVAILABLE` | 503 | (message set per call site) | A required downstream dependency is unreachable | Retry shortly | `ServiceUnavailableError` |
| `METHOD_NOT_ALLOWED` | 405 | (framework-supplied) | Wrong HTTP method for this route | Check the API documentation for the correct method | `http_exception_handler` (raw `HTTPException`) |
| `HTTP_ERROR` | *(varies)* | (framework-supplied) | Fallback for a raw `HTTPException` whose status isn't one of the mapped cases above | Depends on the status code returned | `http_exception_handler` (fallback branch) |
| `BUSINESS_RULE_VIOLATION` | 409 | (message set per raised instance) | A named business rule was violated — the **base** domain error code | See the specific business-domain code actually raised (below), once modules implement one | `BusinessRuleViolation` — **base class**; no module raises a concrete subclass yet |
| `INVARIANT_VIOLATION` | 409 | (message set per raised instance) | An aggregate invariant would be broken (inventory going negative, a ledger not balancing, etc.) — the **base** domain error code | Depends on the invariant | `InvariantViolation` — **base class**; no module raises a concrete subclass yet |
| `INTERNAL_SERVER_ERROR` | 500 | "An unexpected error occurred. Quote the trace_id when reporting this." | Unhandled exception — **never leaks internal detail** (no stack trace, no exception message, no SQL) | Retry; contact support with the `trace_id` if it persists | `unhandled_exception_handler` (catch-all) |

`ApplicationError` (`APPLICATION_ERROR`, 400) and `ConflictError` (`CONFLICT`, 409) are **abstract bases** — every real error raises a named subclass, so these two codes should never appear in a live response. Listed here only so a future reader doesn't wonder why they're missing.

## Business-Domain Error Codes (Reserved — Not Yet Implemented)

None of the rows below have a corresponding exception class yet — **no business module exists** (Phase 2 delivered backend infrastructure only). Each is reserved for the module that will implement it, following the same pattern already established above: a concrete subclass of `BusinessRuleViolation`, `InvariantViolation`, `ConflictError`, or `ApplicationError`, each carrying its own `error_code`/`http_status`/`title`. None needed renaming during this reconciliation — they simply don't exist as code yet, which is expected at this stage, not a defect.

| Error Code | HTTP Status | Message | Business Meaning | Recovery Suggestion | Reserved For |
|---|---|---|---|---|---|
| `DUPLICATE_PHONE` **[Implemented, Phase 8]** | 409 | "A customer with this phone number already exists." | Phone uniqueness (tenant-scoped) | Search for the existing customer instead | Customer |
| `DUPLICATE_CONSUMER_NUMBER` **[Implemented, Phase 8]** | 409 | "This Consumer Number is already assigned." | BR-22 | Verify the Consumer Number or contact support | Customer |
| `LEDGER_NOT_SETTLED` | 409 | "Customer's cylinder ledger balance must be settled before closure." | BR-34 | Complete cylinder return / deposit refund first | Cylinder Ledger |
| `CREDIT_LIMIT_EXCEEDED` | 409 | "This booking would exceed the customer's credit limit." | BR-19 | Collect outstanding payment or request a credit limit override | Accounting |
| `CYLINDER_CAP_EXCEEDED` | 409 | "This booking would exceed the customer's cylinder holding cap." | BR-04 | Confirm an empty-cylinder return alongside this booking | Order Management |
| `INVALID_STATE_TRANSITION` | 409 | "This action is not valid for the resource's current state." | State machine violation | Refresh and check current status before retrying | Order Management |
| `OTP_MISMATCH` | 409 | "The OTP entered does not match." | BR-08/BR-23 or login OTP mismatch | Re-enter the OTP or request a new one | Delivery / Authentication |
| `OTP_EXPIRED` | 410 | "The OTP has expired." | 5-minute OTP window elapsed | Request a new OTP | Authentication |
| `INSUFFICIENT_VEHICLE_STOCK` | 409 | "Vehicle does not have sufficient stock for this delivery." | BR-09 | Reduce quantity or reschedule remainder as backorder | Delivery / Inventory |
| `INSUFFICIENT_STOCK` | 409 | "This location does not have sufficient stock for this operation." | Inventory non-negative invariant | Verify actual stock or record a GRN/adjustment first | Inventory |
| `INSUFFICIENT_LEDGER_BALANCE` | 409 | "Customer does not have sufficient empty cylinders for an exchange." | BR-05 | Use a New Purchase transaction instead, or verify actual holding | Cylinder Ledger |
| `INVALID_STATUS_TRANSITION` | 409 | "This cylinder status change is not permitted." | BR-15 | Verify current status; use the correct intermediate transition | Inventory |
| `APPROVAL_REQUIRED` | 403 | "This action requires Manager approval." | D-19 | Escalate to a user holding the approval permission | Order Management |
| `DUPLICATE_INVOICE` | 409 | "An invoice already exists for this order." | BR-17, D-10 | Retrieve the existing invoice instead | Accounting |
| `OVERPAYMENT` | 409 | "This payment would exceed the invoice's remaining balance." | Payment/invoice reconciliation | Reduce the payment amount or verify invoice balance | Accounting |
| `ACCOUNT_LOCKED` | 423 | "Account temporarily locked due to repeated failed login attempts." | Brute-force protection | Wait 15 minutes or use password reset | Authentication |
| `INVALID_CREDENTIALS` | 401 | "Email or password is incorrect." | Auth failure — distinct from `AUTHENTICATION_REQUIRED` (missing credentials) | Retry or use password reset | Authentication |
| `REFRESH_TOKEN_INVALID` | 401 | "Session expired or invalid. Please log in again." | Refresh rotation/reuse detection | Re-authenticate | Authentication |
| `RESET_TOKEN_EXPIRED` | 410 | "This password reset link has expired." | Reset token TTL elapsed | Request a new reset link | Authentication |
| `WEAK_PASSWORD` | 400 | "Password does not meet complexity requirements." | Shape validation | Use a stronger password | Authentication |
| `FILE_TYPE_NOT_ALLOWED` | 400 | "This file type is not supported." | File validation | Upload a supported file type (PDF/JPG/PNG) | Customer / Delivery |
| `FILE_TOO_LARGE` | 400 | "File exceeds the maximum allowed size." | File validation | Compress or resize the file | Customer / Delivery |
| `MALWARE_DETECTED` | 400 | "This file could not be accepted." | File-scan rejection (validation gap flagged for formalization) | Upload a different file; contact support if this persists | Customer / Delivery |
| `CANCELLATION_CHARGE_REQUIRED` | 402* | "A cancellation charge applies to this action." | D-19 (*modeled as a confirmation step via `confirm_charge: true`, not a hard payment block) | Confirm the charge to proceed | Order Management |
| `SLA_ALREADY_ASSIGNED` | 409 | "This complaint already has an SLA assigned." | BR-33 — set once at creation | N/A — informational, should not normally surface | Complaint Management |

## Best Practices
- Every error code is stable across API versions.
- `detail` messages are human-readable and safe to display; never leak internal implementation details (stack traces, SQL, internal IDs beyond what the user already has).
- `trace_id` is always present, enabling support staff to jump directly to the distributed trace for any reported error.
- **Two different codes exist for "validation failed" — use the right one when implementing a new check.** `REQUEST_VALIDATION_FAILED` is automatic (Pydantic shape/type/format); raise `ValidationError` (`VALIDATION_FAILED`) only for a precondition that genuinely needs a database lookup to evaluate. Conflating them was this catalog's own bug until this reconciliation — don't reintroduce it in code.
- When implementing a business-domain code (the second table), subclass `BusinessRuleViolation`/`InvariantViolation` (domain layer, invariant broken) or `ConflictError`/`ApplicationError` (application layer, precondition), matching how `ConcurrencyConflictError` and `IdempotencyConflictError` already do it — never hand-roll a new base.

## Risks
- **Error code sprawl**: mitigated by requiring a catalog-update review (new code vs. reuse an existing one) as part of the Definition of Done for any new validation/business rule.
- **Catalog drift from implementation**: this reconciliation found three real naming mismatches and one wrong description that had stood since Phase 0. No automated check currently enforces catalog-vs-implementation agreement (`docs/data/18-error-catalog.md` isn't parsed by any test). Recorded as a follow-up worth considering: a CI check asserting every `error_code` string literal in `backend/src/` appears in this file, and vice versa.

## Alternatives Considered
- Generic HTTP status codes only, no `error_code` — rejected; insufficient for client-side differentiated error handling (e.g., distinguishing `CREDIT_LIMIT_EXCEEDED` from `CYLINDER_CAP_EXCEEDED`, both `409`).
- Merging `VALIDATION_FAILED` and `REQUEST_VALIDATION_FAILED` into one code — rejected during this reconciliation; a client needs to tell "the request shape is wrong before any business logic ran" apart from "the request was well-formed but violates a business precondition", and the existing implementation already draws this line correctly — the catalog was simply not documenting it.

## Future Scalability
- The catalog format extends directly to future business-module features and integration-specific errors (`20-integration-contracts.md`) without structural change — each new module adds rows to the Business-Domain table and flips their status from reserved to implemented as its exceptions are written.
