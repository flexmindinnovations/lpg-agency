from __future__ import annotations

import uuid  # noqa: TC003
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from lpg.application.common.ports import UnitOfWork

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lpg.domain.complaint.ports import ComplaintRepository


@runtime_checkable
class ComplaintUnitOfWork(UnitOfWork, Protocol):
    @property
    def complaints(self) -> ComplaintRepository: ...


class ComplaintNumberSequence(Protocol):
    """Generates the next tenant-scoped, human-readable complaint number
    (`CMP000001`). Backed by the shared `SqlAlchemyReferenceNumberSequence`
    — never manually overridden, so no collision-check is needed by the
    caller.
    """

    async def next(self) -> str: ...


@dataclass(frozen=True, slots=True)
class StaffMember:
    """Someone a complaint can be assigned to (DO-18)."""

    user_id: uuid.UUID
    name: str
    role: str
    email: str | None


@dataclass(frozen=True, slots=True)
class ComplaintCustomer:
    customer_id: uuid.UUID
    full_name: str
    phone_number: str
    consumer_number: str | None


@dataclass(frozen=True, slots=True)
class ComplaintOrder:
    order_id: uuid.UUID
    order_number: str | None
    customer_id: uuid.UUID


class ComplaintDirectory(Protocol):
    """Read-only lookups the complaint screens and checks need: who the
    customer is, which order, and who can take the complaint. Everything is
    limited to the caller's tenant (RLS plus an explicit tenant filter)."""

    async def assignable_staff(self, tenant_id: uuid.UUID) -> list[StaffMember]:
        """Active staff of the tenant allowed to work complaints."""
        ...

    async def customers(
        self, customer_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, ComplaintCustomer]: ...

    async def orders(self, order_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, ComplaintOrder]: ...

    async def staff_names(
        self, tenant_id: uuid.UUID, user_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, str]: ...
