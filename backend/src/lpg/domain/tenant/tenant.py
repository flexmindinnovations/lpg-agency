"""The `Tenant` aggregate — the tenant registry root.

Phase 2 introduced this as a Repository/CQRS/Domain-Event proof, deliberately
minimal (rename only, no lifecycle, no create/delete use case — see
`0242df1a3871`'s migration docstring for why tenant provisioning stays an
elevated/seed operation). The Platform Console plan wires the lifecycle
methods below (`activate`/`suspend`/`reactivate`/`close`) into real use
cases (`application/tenant/manage_lifecycle.py`) for the first time — the
`status`/`subscription_plan`/`primary_contact_email`/`country` columns
`03-database-schema.md` always documented were reconciled onto the table by
migration `b1c4a9e7d2f3`, well before anything actually called these
methods.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

#: An agency's `slug` is also its future subdomain (`<slug>.example.com`), so
#: it must be a valid, lowercase DNS label: letters/digits/single hyphens,
#: never starting or ending with a hyphen. Deliberately stricter than the
#: legacy dev slug (`DEV123456`) so a later subdomain rollout needs no
#: data migration.
SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
SLUG_MIN_LENGTH = 3
SLUG_MAX_LENGTH = 40
NAME_MAX_LENGTH = 120

#: Hostnames that would collide with platform infrastructure once slugs
#: become subdomains.
RESERVED_SLUGS = frozenset(
    {"www", "api", "app", "admin", "platform", "mail", "static", "assets", "support", "status"}
)

_SLUG_RE = re.compile(SLUG_PATTERN)
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")


@dataclass(frozen=True, slots=True)
class TenantProvisioned(DomainEvent):
    """Recorded when a Super Admin creates a new agency (`Tenant.provision`)."""

    tenant_id: uuid.UUID | None = None
    slug: str = ""


@dataclass(frozen=True, slots=True)
class TenantRenamed(DomainEvent):
    """Recorded when a tenant's display name changes.

    An illustrative event, not a real business notification — nothing
    subscribes to this in Phase 2. It exists to prove aggregates record
    events and the Unit of Work dispatches them post-commit (`03-backend
    -architecture.md` §6), the mechanism every real business event will use.
    """

    tenant_id: uuid.UUID | None = None
    new_name: str = ""


@dataclass(frozen=True, slots=True)
class TenantStatusChanged(DomainEvent):
    """Recorded on every lifecycle transition — `activate()`/`suspend()`/
    `reactivate()`/`close()` — so a future notification/audit consumer has
    one event to subscribe to rather than four.
    """

    tenant_id: uuid.UUID | None = None
    old_status: str = ""
    new_status: str = ""


class Tenant(AggregateRoot):
    """The tenant registry root.

    Lifecycle (`01-domain-model.md` §4.1): ``trial`` → ``active`` ⇄
    ``suspended`` → ``closed``. ``closed`` is terminal — never hard-deleted,
    never reopened; provisioning a genuinely new tenant is the only way
    forward from there.
    """

    __slots__ = (
        "_country",
        "_name",
        "_primary_contact_email",
        "_slug",
        "_status",
        "_subscription_plan",
    )

    def __init__(
        self,
        tenant_id: uuid.UUID,
        name: str,
        slug: str,
        *,
        status: str = "trial",
        subscription_plan: str = "standard",
        primary_contact_email: str,
        country: str = "IN",
        version: int = 1,
    ) -> None:
        super().__init__(tenant_id, version=version)
        self._name = name
        self._slug = slug
        self._status = status
        self._subscription_plan = subscription_plan
        self._primary_contact_email = primary_contact_email
        self._country = country

    @classmethod
    def provision(
        cls,
        *,
        name: str,
        slug: str,
        primary_contact_email: str,
        subscription_plan: str = "standard",
        country: str = "IN",
    ) -> Tenant:
        """Create a brand-new agency in the `trial` state.

        The one place a tenant's identity fields are validated, so every entry
        point (API, scripts, tests) gets the same rules. Input is normalised
        first (whitespace trimmed, slug and email lower-cased) because callers
        should not have to pre-clean what they are about to be rejected for.
        """
        clean_name = name.strip()
        if not clean_name or len(clean_name) > NAME_MAX_LENGTH:
            msg = f"Agency name must be 1-{NAME_MAX_LENGTH} characters."
            raise InvariantViolation(msg)

        clean_slug = slug.strip().lower()
        if not SLUG_MIN_LENGTH <= len(clean_slug) <= SLUG_MAX_LENGTH or not _SLUG_RE.match(
            clean_slug
        ):
            msg = (
                f"Agency code must be {SLUG_MIN_LENGTH}-{SLUG_MAX_LENGTH} characters: lowercase "
                "letters, digits and single hyphens, not starting or ending with a hyphen."
            )
            raise InvariantViolation(msg, slug=clean_slug)
        if clean_slug in RESERVED_SLUGS:
            msg = f"Agency code '{clean_slug}' is reserved."
            raise InvariantViolation(msg, slug=clean_slug)

        clean_email = primary_contact_email.strip().lower()
        if "@" not in clean_email or clean_email.startswith("@") or clean_email.endswith("@"):
            msg = "A valid primary contact email is required."
            raise InvariantViolation(msg)

        clean_country = country.strip().upper()
        if not _COUNTRY_RE.match(clean_country):
            msg = "Country must be a two-letter ISO 3166-1 code."
            raise InvariantViolation(msg, country=clean_country)

        tenant = cls(
            uuid.uuid4(),
            clean_name,
            clean_slug,
            status="trial",
            subscription_plan=subscription_plan.strip() or "standard",
            primary_contact_email=clean_email,
            country=clean_country,
        )
        tenant.record_event(TenantProvisioned(tenant_id=tenant.id, slug=clean_slug))
        return tenant

    @property
    def name(self) -> str:
        return self._name

    @property
    def slug(self) -> str:
        return self._slug

    @property
    def status(self) -> str:
        return self._status

    @property
    def subscription_plan(self) -> str:
        return self._subscription_plan

    @property
    def primary_contact_email(self) -> str:
        return self._primary_contact_email

    @property
    def country(self) -> str:
        return self._country

    def rename(self, new_name: str) -> None:
        """Change the tenant's display name.

        The one behaviour this aggregate has, deliberately — enough to prove
        a domain method enforcing an invariant, mutating state, and recording
        an event, without building out anything resembling tenant
        administration.
        """
        stripped = new_name.strip()
        if not stripped:
            msg = "Tenant name cannot be empty."
            raise InvariantViolation(msg, tenant_id=str(self.id))

        self._name = stripped
        self.record_event(TenantRenamed(tenant_id=self.id, new_name=stripped))

    def activate(self) -> None:
        """`trial` → `active` — the tenant's first real activation."""
        self._transition_to("active", allowed_from={"trial"})

    def suspend(self) -> None:
        """`active` → `suspended`."""
        self._transition_to("suspended", allowed_from={"active"})

    def reactivate(self) -> None:
        """`suspended` → `active`."""
        self._transition_to("active", allowed_from={"suspended"})

    def close(self) -> None:
        """Any non-terminal status → `closed`. Terminal — never reopened."""
        self._transition_to("closed", allowed_from={"trial", "active", "suspended"})

    def _transition_to(self, new_status: str, *, allowed_from: set[str]) -> None:
        if self._status not in allowed_from:
            msg = f"Cannot move a {self._status} tenant to {new_status}."
            raise InvariantViolation(msg, tenant_id=str(self.id))

        old_status = self._status
        self._status = new_status
        self.record_event(
            TenantStatusChanged(tenant_id=self.id, old_status=old_status, new_status=new_status)
        )
