"""Identity application-layer ports.

Same dependency-inversion shape as `application/common/ports.py`'s
`TenantResolver`: the application layer defines the protocol, infrastructure
(Area D) implements it. Application code — the use cases in this package —
depends only on these protocols, never on `argon2`, `pyjwt`, or SQLAlchemy
directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from lpg.application.common.ports import TenantContext

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from lpg.domain.identity.password_reset_token import PasswordResetToken
    from lpg.domain.identity.refresh_token import RefreshToken
    from lpg.domain.identity.user import IdentityUser


@runtime_checkable
class AuthenticatedPrincipal(TenantContext, Protocol):
    """A `TenantContext` carrying enough to authorize the request too.

    Structurally extends `TenantContext` (both are `Protocol`s) — everything
    already depending on `get_tenant_context`/`get_unit_of_work` for
    `tenant_id`/`user_id` needs **zero changes**. `JwtTenantResolver`
    (Area D) returns a concrete type satisfying this richer protocol, and
    nothing downstream has to know the difference.
    """

    @property
    def role(self) -> str: ...

    @property
    def permission_codes(self) -> frozenset[str]: ...

    @property
    def branch_id(self) -> uuid.UUID | None: ...

    @property
    def token_id(self) -> uuid.UUID | None: ...


@runtime_checkable
class PasswordHasher(Protocol):
    """Argon2id password hashing (`08-security-architecture.md` §1).

    The domain layer never imports this — `IdentityUser.password_hash` is an
    opaque, already-hashed string; hashing/verifying happens here, one layer
    removed from the aggregate.
    """

    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...

    def needs_rehash(self, password_hash: str) -> bool:
        """True if `password_hash` was produced with weaker cost parameters
        than the hasher's current settings — lets a login opportunistically
        upgrade an old hash without a separate migration.
        """
        ...


@runtime_checkable
class TokenHasher(Protocol):
    """Hashes an already-high-entropy token (refresh token, reset token).

    Deliberately not `PasswordHasher`: a refresh/reset token is already a
    256-bit random value, so a fast SHA-256 hash is the right tool here —
    Argon2 on every refresh call would burn CPU for no security benefit only
    low-entropy passwords actually need it for.
    """

    def hash(self, token: str) -> str: ...

    def verify(self, token: str, token_hash: str) -> bool: ...


@runtime_checkable
class JwtSigner(Protocol):
    """RS256 access-token issuance and verification.

    `issue_access_token` embeds exactly the claims
    `docs/data/17-api-security.md` §1 specifies (`sub`, `tenant_id`,
    `branch_id`, `role`, `scope`, `exp`, `iat`) — callers pass them as a
    plain dict rather than this protocol knowing about `IdentityUser`,
    keeping the port agnostic of the aggregate shape.
    """

    def issue_access_token(self, claims: dict[str, Any]) -> str: ...

    def decode_access_token(self, token: str) -> dict[str, Any]:
        """Verify the signature and expiry, returning the claims.

        Raises `lpg.application.common.errors.TokenInvalidError` (or a
        subclass) on an invalid, expired, or malformed token — never returns
        unverified claims.
        """
        ...


@runtime_checkable
class OtpStore(Protocol):
    """Generates, stores, and verifies OTP codes (Redis-backed in
    infrastructure — `infrastructure/identity/otp_service.py`). Distinct from
    `OtpDeliveryPort`: this is the storage/verification primitive; delivery
    (SMS) is a separate concern. Rate limiting is enforced one layer up, at
    the API dependency chain (`RateLimiter`'s existing, general-purpose
    infrastructure), not here — this port's job is generate/store/verify
    only.
    """

    async def issue(self, key: str) -> str:
        """Generate a new code, store its salted hash with a TTL, and return
        the plaintext code for the caller to hand to `OtpDeliveryPort`.
        """
        ...

    async def verify(self, key: str, code: str) -> bool:
        """Check `code` against the stored value for `key`. A correct code
        consumes the entry (single-use) and returns `True`; an incorrect
        code returns `False` without consuming it, so the caller can allow a
        few mismatched attempts within the same TTL window.

        Raises `lpg.application.common.errors.OtpExpiredError` if no OTP is
        currently pending for `key` — either it was never requested, or its
        TTL already elapsed.
        """
        ...


@runtime_checkable
class OtpDeliveryPort(Protocol):
    """Delivers an OTP code to a phone number.

    No SMS provider exists in this codebase yet (Phase 14, Notifications) —
    the only implementation today is a logging-only dev adapter
    (`infrastructure/identity/otp_delivery.py`).
    """

    async def send(self, phone_number: str, code: str) -> None: ...


@runtime_checkable
class EmailSender(Protocol):
    """Delivers a password-reset (or other transactional) email.

    Same story as `OtpDeliveryPort`: no real provider exists yet, only a
    logging-only dev adapter. Real delivery is Phase 14 scope.
    """

    async def send(self, to: str, subject: str, body: str) -> None: ...


@runtime_checkable
class IdentityUserRepository(Protocol):
    async def get(self, user_id: uuid.UUID) -> IdentityUser | None: ...

    async def get_by_email(self, email: str) -> IdentityUser | None:
        """`email` is globally unique across tenants
        (`docs/data/03-database-schema.md`), so no tenant_id is needed here —
        unlike `get_by_phone_number`, which is per-tenant.
        """
        ...

    async def get_by_phone_number(
        self, tenant_id: uuid.UUID, phone_number: str
    ) -> IdentityUser | None: ...

    async def save(self, user: IdentityUser) -> None: ...


@runtime_checkable
class StaffUserRepository(Protocol):
    """Admin-side staff-management access to `identity.identity_user` —
    deliberately distinct from `IdentityUserRepository`.

    `IdentityUserRepository` exists for the pre-authentication
    auth-bootstrap paths (login/OTP/refresh) and is built on `SECURITY
    DEFINER` SQL functions, since no tenant context is resolved yet at that
    point (Phase 6). Every use case here runs *after* authentication, with a
    verified `TenantContext` already in hand — so the normal
    repository-plus-RLS pattern every other Phase 7 aggregate uses applies
    directly, no `SECURITY DEFINER` escape hatch needed. RLS naturally
    restricts an admin to their own tenant's staff, which is exactly the
    desired behavior here (unlike auth-bootstrap, which must look a user up
    *before* any tenant is known).
    """

    async def get(self, user_id: uuid.UUID) -> IdentityUser | None: ...

    async def list_for_tenant(
        self, tenant_id: uuid.UUID, *, exclude_roles: frozenset[str]
    ) -> Sequence[IdentityUser]: ...

    async def add(self, user: IdentityUser) -> None: ...

    async def save(self, user: IdentityUser) -> None: ...


@runtime_checkable
class RefreshTokenRepository(Protocol):
    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None: ...

    async def save(self, token: RefreshToken) -> None: ...

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        """Session-wide revocation — the reuse-detection response
        (`docs/data/17-api-security.md` §2: reuse of a rotated token
        triggers "full session revocation").
        """
        ...


@runtime_checkable
class PasswordResetTokenRepository(Protocol):
    async def get_by_token_hash(self, token_hash: str) -> PasswordResetToken | None: ...

    async def save(self, token: PasswordResetToken) -> None: ...


@runtime_checkable
class PermissionRepository(Protocol):
    """Live (non-claim-based) permission lookup, for the four high-sensitivity
    actions `docs/data/17-api-security.md` §7 names (`reconciliation:approve`,
    `credit_notes:approve`, `orders:cancel_approve`, any `super_admin`
    cross-tenant action).
    """

    async def has_permission(self, *, user_id: uuid.UUID, permission_code: str) -> bool: ...

    async def get_permission_codes_for_user(self, user_id: uuid.UUID) -> frozenset[str]:
        """Every permission code granted to `user_id` — embedded in the JWT's
        `scope` claim at issuance (`docs/data/17-api-security.md` §4: "fast,
        no-database-round-trip authorization on standard endpoints").
        """
        ...

    async def get_all_permission_codes(self) -> frozenset[str]:
        """All available permission codes in the system."""
        ...

    async def set_permissions_for_user(
        self, user_id: uuid.UUID, permission_codes: set[str]
    ) -> None:
        """Overwrite the permissions assigned to a user."""
        ...


@runtime_checkable
class TenantSlugResolver(Protocol):
    """Resolves a human-readable agency code (`tenant.slug`) to its UUID.

    `/auth/otp/request` and `/auth/otp/verify` accept either a raw
    `tenant_id` or an agency-code slug from unauthenticated callers (mobile
    clients that don't yet have a tenant UUID cached) — that lookup is one
    SQL call against `tenant.auth_resolve_tenant_id_by_slug`, infrastructure
    the router must not reach for directly.
    """

    async def resolve(self, slug: str) -> uuid.UUID | None: ...
