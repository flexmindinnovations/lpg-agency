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

## Error Catalog

| Error Code | HTTP Status | Message | Business Meaning | Recovery Suggestion | Related Module |
|---|---|---|---|---|---|
| `VALIDATION_FAILED` | 400 | "One or more fields are invalid." | Pydantic shape validation failure | Fix indicated fields and resubmit | Cross-Cutting |
| `DUPLICATE_PHONE` | 409 | "A customer with this phone number already exists." | Phone uniqueness (tenant-scoped) | Search for the existing customer instead | Customer |
| `DUPLICATE_CONSUMER_NUMBER` | 409 | "This Consumer Number is already assigned." | BR-22 | Verify the Consumer Number or contact support | Customer |
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
| `CONCURRENCY_CONFLICT` | 409 | "This record was modified by someone else. Please refresh and try again." | Optimistic concurrency (stale version) | Refetch the resource and reapply the change | Cross-Cutting |
| `ACCOUNT_LOCKED` | 423 | "Account temporarily locked due to repeated failed login attempts." | Brute-force protection | Wait 15 minutes or use password reset | Authentication |
| `INVALID_CREDENTIALS` | 401 | "Email or password is incorrect." | Auth failure | Retry or use password reset | Authentication |
| `REFRESH_TOKEN_INVALID` | 401 | "Session expired or invalid. Please log in again." | Refresh rotation/reuse detection | Re-authenticate | Authentication |
| `RESET_TOKEN_EXPIRED` | 410 | "This password reset link has expired." | Reset token TTL elapsed | Request a new reset link | Authentication |
| `WEAK_PASSWORD` | 400 | "Password does not meet complexity requirements." | Shape validation | Use a stronger password | Authentication |
| `TOO_MANY_REQUESTS` | 429 | "Too many requests. Please try again later." | Rate limiting | Wait for the Retry-After duration | Cross-Cutting |
| `PERMISSION_DENIED` | 403 | "You do not have permission to perform this action." | RBAC/permission failure | Contact an administrator for access | Cross-Cutting |
| `NOT_FOUND` | 404 | "The requested resource was not found." | Resource doesn't exist or isn't in caller's tenant | Verify the resource ID | Cross-Cutting |
| `FILE_TYPE_NOT_ALLOWED` | 400 | "This file type is not supported." | File validation | Upload a supported file type (PDF/JPG/PNG) | Customer / Delivery |
| `FILE_TOO_LARGE` | 400 | "File exceeds the maximum allowed size." | File validation | Compress or resize the file | Customer / Delivery |
| `MALWARE_DETECTED` | 400 | "This file could not be accepted." | File-scan rejection (validation gap flagged for formalization) | Upload a different file; contact support if this persists | Customer / Delivery |
| `CANCELLATION_CHARGE_REQUIRED` | 402* | "A cancellation charge applies to this action." | D-19 (*modeled as a confirmation step via `confirm_charge: true`, not a hard payment block) | Confirm the charge to proceed | Order Management |
| `SLA_ALREADY_ASSIGNED` | 409 | "This complaint already has an SLA assigned." | BR-33 — set once at creation | N/A — informational, should not normally surface | Complaint Management |
| `INTERNAL_ERROR` | 500 | "An unexpected error occurred." | Unhandled exception | Retry; contact support with the trace_id if it persists | Cross-Cutting |

## Best Practices
- Every error code is stable across API versions.
- `detail` messages are human-readable and safe to display; never leak internal implementation details (stack traces, SQL, internal IDs beyond what the user already has).
- `trace_id` is always present, enabling support staff to jump directly to the distributed trace for any reported error.
- FastAPI's default `422` for Pydantic validation errors is remapped to `400` with `error_code: VALIDATION_FAILED` via a global exception handler, for consistency with this catalog.

## Risks
- **Error code sprawl**: mitigated by requiring a catalog-update review (new code vs. reuse an existing one) as part of the Definition of Done for any new validation/business rule.

## Alternatives Considered
- Generic HTTP status codes only, no `error_code` — rejected; insufficient for client-side differentiated error handling (e.g., distinguishing `CREDIT_LIMIT_EXCEEDED` from `CYLINDER_CAP_EXCEEDED`, both `409`).

## Future Scalability
- The catalog format extends directly to Phase 2 features and integration-specific errors (`20-integration-contracts.md`) without structural change.
