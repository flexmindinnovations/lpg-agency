"""The `Tenant` aggregate — the tenant registry root.

Phase 2 introduced this as a Repository/CQRS/Domain-Event proof, deliberately
minimal (rename only, no lifecycle, no create/delete use case — see
`0242df1a3871`'s migration docstring for why tenant provisioning stays an
elevated/seed operation). Phase 7 (Administration) extends it with the real
lifecycle `03-database-schema.md` always documented — `status`,
`subscription_plan`, `primary_contact_email`, `country` — reconciled onto the
table by migration `b1c4a9e7d2f3`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

if TYPE_CHECKING:
    import uuid


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
