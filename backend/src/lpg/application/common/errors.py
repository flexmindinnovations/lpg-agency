"""Application layer errors.

Distinct from domain errors (a business rule was violated) and from
infrastructure failures (something broke). Each maps to a specific HTTP status
and a stable ``error_code`` in the RFC 7807 response (ADR-021).

The authoritative catalogue of codes is ``docs/data/18-error-catalog.md``.
"""

from __future__ import annotations

from typing import Any


class ApplicationError(Exception):
    """Base class for expected, handleable application failures."""

    error_code: str = "APPLICATION_ERROR"
    http_status: int = 400
    title: str = "Application error"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context = context


class NotFoundError(ApplicationError):
    """The requested resource does not exist, or is not visible to this tenant.

    The two cases are deliberately indistinguishable to the client. Returning
    403 for "exists but belongs to another tenant" and 404 for "does not exist"
    would leak the existence of other tenants' records — a cross-tenant
    information disclosure through status codes alone.
    """

    error_code = "RESOURCE_NOT_FOUND"
    http_status = 404
    title = "Resource not found"


class PermissionDeniedError(ApplicationError):
    """The authenticated principal lacks the required permission."""

    error_code = "PERMISSION_DENIED"
    http_status = 403
    title = "Permission denied"


class AuthenticationError(ApplicationError):
    """No valid credentials were supplied."""

    error_code = "AUTHENTICATION_REQUIRED"
    http_status = 401
    title = "Authentication required"


class TenantContextMissingError(AuthenticationError):
    """No tenant context could be resolved for this request.

    Distinct from a generic authentication failure so infrastructure can log
    and test for it specifically. Phase 2's ``TenantResolver`` implementations
    raise this when their (interim, pre-authentication) resolution mechanism
    finds nothing to resolve from — see ``lpg.infrastructure.tenant``.
    """

    error_code = "TENANT_CONTEXT_MISSING"
    title = "Tenant context could not be resolved"


class ConflictError(ApplicationError):
    """The request conflicts with current state."""

    error_code = "CONFLICT"
    http_status = 409
    title = "Conflict"


class ConcurrencyConflictError(ConflictError):
    """The resource was modified by someone else since it was read.

    Surfaced from the optimistic-concurrency version check. Expected in normal
    operation for the offline-first Driver App, where a device may hold a stale
    copy — the client resolves and retries rather than treating it as an error.
    """

    error_code = "CONCURRENCY_CONFLICT"
    title = "Resource was modified concurrently"


class DuplicateRouteAssignmentError(ConflictError):
    """The order is already assigned to a different active route.

    `Route.assign_order()` only rejects a *duplicate* stop on the *same*
    route; this catches the cross-route case, which needs a repository
    query (`RouteRepository.count_active_routes_for_order`) the aggregate
    itself can't perform.
    """

    error_code = "DUPLICATE_ROUTE_ASSIGNMENT"
    title = "Order already assigned to another active route"


class RouteReconciliationPendingError(ConflictError):
    """A route cannot move `completed -> reconciled` until its vehicle's
    `InventoryLocation` has an *approved* `ReconciliationRecord` (BR-14) —
    Route doesn't reimplement reconciliation, it references Inventory's.
    """

    error_code = "ROUTE_RECONCILIATION_PENDING"
    title = "Vehicle reconciliation has not been approved yet"


class IdempotencyConflictError(ConflictError):
    """The same Idempotency-Key was reused with a different request payload.

    A client retrying its own request must send byte-identical (or at least
    fingerprint-identical) content; reusing a key for a genuinely different
    request is a client bug, not a network retry, and must not silently
    execute against, or replay, unrelated stored state.
    """

    error_code = "IDEMPOTENCY_KEY_CONFLICT"
    title = "Idempotency key reused with a different request"


class RateLimitExceededError(ApplicationError):
    """The caller has exceeded the permitted request rate."""

    error_code = "RATE_LIMIT_EXCEEDED"
    http_status = 429
    title = "Rate limit exceeded"

    def __init__(self, message: str, *, retry_after_seconds: int, **context: Any) -> None:
        super().__init__(message, **context)
        self.retry_after_seconds = retry_after_seconds


class ValidationError(ApplicationError):
    """Input failed validation beyond what request-shape checking catches.

    Shape, type and format are handled by Pydantic before a use case runs.
    This covers cross-entity preconditions that require a lookup.
    """

    error_code = "VALIDATION_FAILED"
    http_status = 422
    title = "Validation failed"

    def __init__(
        self, message: str, *, errors: dict[str, list[str]] | None = None, **context: Any
    ) -> None:
        super().__init__(message, **context)
        self.errors = errors or {}


class ServiceUnavailableError(ApplicationError):
    """A required downstream dependency is unavailable."""

    error_code = "SERVICE_UNAVAILABLE"
    http_status = 503
    title = "Service temporarily unavailable"


class InvalidCredentialsError(ApplicationError):
    """Login failed — wrong password, unknown email, or inactive account.

    Distinct from `AuthenticationError` (no credentials supplied at all) and
    deliberately reported identically for "wrong password" and "no such
    user" — the same no-user-enumeration reasoning `NotFoundError` already
    applies to cross-tenant resource lookups.
    """

    error_code = "INVALID_CREDENTIALS"
    http_status = 401
    title = "Invalid credentials"


class AccountLockedError(ApplicationError):
    """Too many consecutive failed logins — see `IdentityUser.record_failed_login`."""

    error_code = "ACCOUNT_LOCKED"
    http_status = 423
    title = "Account temporarily locked"


class RefreshTokenInvalidError(ApplicationError):
    """The refresh token is missing, expired, already rotated, or revoked.

    Also raised (after revoking the whole session) when reuse of an
    already-rotated token is detected — the client cannot distinguish "this
    token was never valid" from "this token was valid but reused," and
    shouldn't be able to.
    """

    error_code = "REFRESH_TOKEN_INVALID"
    http_status = 401
    title = "Session expired or invalid"


class TokenInvalidError(AuthenticationError):
    """An access token failed signature verification, is expired, or is malformed.

    Raised by `JwtSigner.decode_access_token` and, downstream, by
    `JwtTenantResolver` when it cannot resolve a trustworthy principal.
    """

    error_code = "AUTHENTICATION_REQUIRED"
    title = "Access token is invalid or expired"


class ResetTokenExpiredError(ApplicationError):
    """The password-reset link's token TTL has elapsed, or it was already used."""

    error_code = "RESET_TOKEN_EXPIRED"
    http_status = 410
    title = "Password reset link has expired"


class OtpMismatchError(ApplicationError):
    """The OTP code entered does not match what was issued."""

    error_code = "OTP_MISMATCH"
    http_status = 409
    title = "OTP does not match"


class OtpExpiredError(ApplicationError):
    """The OTP's TTL elapsed before it was verified."""

    error_code = "OTP_EXPIRED"
    http_status = 410
    title = "OTP has expired"


class DuplicatePhoneError(ConflictError):
    """A customer with this phone number already exists for the tenant."""

    error_code = "DUPLICATE_PHONE"
    title = "A customer with this phone number already exists."


class DuplicateConsumerNumberError(ConflictError):
    """This Consumer Number is already assigned to another customer (BR-22)."""

    error_code = "DUPLICATE_CONSUMER_NUMBER"
    title = "This Consumer Number is already assigned."


class DuplicateLpgSubsidyIdError(ConflictError):
    """This 17-digit LPG ID is already linked to another customer.

    Distinct from `DuplicateConsumerNumberError` — the LPG ID is the
    nationally-standardized OMC/subsidy identifier, not the agency's own
    locally-assigned Consumer Number.
    """

    error_code = "DUPLICATE_LPG_SUBSIDY_ID"
    title = "This LPG ID is already linked to another customer."


class WeakPasswordError(ApplicationError):
    """A new password fails the complexity policy (`Settings`-configured).

    The Pydantic request schema's `min_length` catches the common case
    before a use case ever runs; this exists for checks that need a
    lookup a request-shape validator can't perform (e.g. rejecting reuse of
    the current password).
    """

    error_code = "WEAK_PASSWORD"
    http_status = 400
    title = "Password does not meet complexity requirements"


class DuplicateEmployeeCodeError(ConflictError):
    """A driver with this employee code already exists for the tenant."""

    error_code = "DUPLICATE_EMPLOYEE_CODE"
    title = "A driver with this employee code already exists."


class DuplicateRegistrationNumberError(ConflictError):
    """A vehicle with this registration number already exists for the tenant."""

    error_code = "DUPLICATE_REGISTRATION_NUMBER"
    title = "A vehicle with this registration number already exists."


class CylinderCapExceededError(ConflictError):
    """BR-04: this booking would exceed the customer's cylinder holding cap."""

    error_code = "CYLINDER_CAP_EXCEEDED"
    title = "This booking would exceed the customer's cylinder holding cap."


class CreditLimitExceededError(ConflictError):
    """BR-19: outstanding balance plus this order would exceed the customer's credit limit."""

    error_code = "CREDIT_LIMIT_EXCEEDED"
    title = "This order would exceed the customer's credit limit."


class IncompletePodError(ApplicationError):
    """A delivery's Proof of Delivery is present but semantically invalid
    (a blank blob reference, out-of-range GPS) — distinct from a missing
    field entirely, which Pydantic already rejects with 422 before a use
    case ever runs (BR-08).
    """

    error_code = "INCOMPLETE_PROOF_OF_DELIVERY"
    http_status = 400
    title = "Proof of delivery is incomplete."


class LicenseNotActivatedError(ConflictError):
    """No license exists for this tenant yet, or one exists but has never
    been activated — raised at login/refresh, distinct from `LicenseExpiredError`
    so the client can render "activate your license" rather than "renew it".
    """

    error_code = "LICENSE_NOT_ACTIVATED"
    title = "This tenant's license has not been activated."


class LicenseExpiredError(ConflictError):
    """The tenant's license is past its grace period (`BLOCKED`) or has been
    revoked — raised at login/refresh and on every authenticated request via
    `JwtTenantResolver`, since a license can expire mid-session.
    """

    error_code = "LICENSE_EXPIRED"
    title = "This tenant's license has expired."


class LicenseActivationFailedError(ConflictError):
    """The presented activation key does not match this tenant's license, or
    the license is already activated/revoked."""

    error_code = "LICENSE_ACTIVATION_FAILED"
    title = "License activation failed."


class LicenseAlreadyIssuedError(ConflictError):
    """This tenant already holds a non-revoked license — `IssueLicenseUseCase`
    raises this instead of letting the attempt fall through to `platform.
    license`'s partial unique index (`uq_license_tenant_id_active`,
    migration `f5746de5730e`) and surface as a raw `IntegrityError`. Revoke
    the existing license first; reissuing after a revoke is the case that
    index exists to allow."""

    error_code = "LICENSE_ALREADY_ISSUED"
    title = "This tenant already has an active license."


class DeviceLimitReachedError(ConflictError):
    """Registering this device would exceed the license's per-app-type device
    cap (BR: never auto-evicts an existing device — the caller must revoke
    one first)."""

    error_code = "DEVICE_LIMIT_REACHED"
    title = "The device limit for this app has been reached."


class TenantSuspendedError(ConflictError):
    """The tenant's agency has been suspended by a `super_admin` —
    deliberately a **second, independent** check from `LicenseExpiredError`,
    checked at the same three call sites (login, refresh,
    `get_tenant_context`) but never merged with it: a suspended agency and
    a revoked/expired license are different facts about a tenant, decided
    by different actors, and the client should render different guidance
    for each ("this agency has been suspended, contact support" vs.
    "activate/renew your license")."""

    error_code = "TENANT_SUSPENDED"
    title = "This tenant's agency has been suspended."
