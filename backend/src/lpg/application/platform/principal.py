"""`PlatformPrincipal` — the identity of a verified `super_admin` session.

Deliberately **not** a `TenantContext`/`AuthenticatedPrincipal`
(`application/common/ports.py`, `application/identity/ports.py`) — those
protocols require a real `tenant_id`, and every tenant-scoped use case,
repository, and RLS-backed query in this app trusts that guarantee.
`PlatformPrincipal` has no `tenant_id` field at all, not even optional: it
is structurally impossible to hand one to `get_unit_of_work`/anything
expecting a `TenantContext`. See `infrastructure/identity/
jwt_platform_principal_resolver.py`'s docstring for why this is a parallel
type rather than a nullable field on the existing one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid


class PlatformPrincipal(Protocol):
    """A verified `super_admin` identity — no tenant, no RLS session
    context, only enough to authorize a `/platform/*` request."""

    @property
    def user_id(self) -> uuid.UUID: ...

    @property
    def role(self) -> str: ...

    @property
    def permission_codes(self) -> frozenset[str]: ...

    @property
    def email(self) -> str | None: ...


@dataclass(frozen=True, slots=True)
class JwtPlatformPrincipal:
    """Concrete `PlatformPrincipal` — mirrors `JwtAuthenticatedPrincipal`'s
    placement and shape, minus every tenant-scoped field.

    `email` comes straight off the JWT's `name` claim
    (`application/identity/tokens.py`: `user.email or user.phone_number`),
    not a DB lookup — unlike `/auth/me`, which fetches it live via
    `IdentityUserRepository`. A cross-tenant-null user lookup would need its
    own `SECURITY DEFINER` function (migration `fdd3afde337c`'s pattern) for
    a single display-only field; the claim is already there and exactly as
    trustworthy as every other claim this resolver reads.
    """

    user_id: uuid.UUID
    role: str
    permission_codes: frozenset[str]
    email: str | None = None
