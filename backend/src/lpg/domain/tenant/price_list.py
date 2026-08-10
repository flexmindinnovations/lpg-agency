"""`PriceListEntry` — one historized price point — and
`EffectivePriceResolver`, the domain service that picks the price in effect
for a branch (or the tenant-wide default) at a point in time.

Append-only, same rationale as `TenantConfiguration` — see that module's
docstring. `branch_id=None` means a tenant-wide default; a non-`None` value
overrides it for that one branch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, InvariantViolation

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import datetime
    from decimal import Decimal

CUSTOMER_TYPES = frozenset({"domestic", "commercial", "industrial", "government"})


class PriceListEntry(AggregateRoot):
    __slots__ = (
        "_branch_id",
        "_customer_type",
        "_cylinder_type_id",
        "_effective_from",
        "_price",
        "_tenant_id",
    )

    def __init__(
        self,
        entry_id: uuid.UUID,
        tenant_id: uuid.UUID,
        cylinder_type_id: uuid.UUID,
        customer_type: str,
        price: Decimal,
        effective_from: datetime,
        *,
        branch_id: uuid.UUID | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(entry_id, version=version)
        if customer_type not in CUSTOMER_TYPES:
            msg = f"'{customer_type}' is not a recognized customer type."
            raise InvariantViolation(msg, customer_type=customer_type)
        if price <= 0:
            msg = "Price must be greater than zero."
            raise InvariantViolation(msg, price=str(price))

        self._tenant_id = tenant_id
        self._cylinder_type_id = cylinder_type_id
        self._customer_type = customer_type
        self._branch_id = branch_id
        self._price = price
        self._effective_from = effective_from

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def cylinder_type_id(self) -> uuid.UUID:
        return self._cylinder_type_id

    @property
    def customer_type(self) -> str:
        return self._customer_type

    @property
    def branch_id(self) -> uuid.UUID | None:
        return self._branch_id

    @property
    def price(self) -> Decimal:
        return self._price

    @property
    def effective_from(self) -> datetime:
        return self._effective_from

    @property
    def is_tenant_wide_default(self) -> bool:
        return self._branch_id is None


class EffectivePriceResolver:
    """Resolves the price in effect for a cylinder type x customer type,
    at a branch (or the tenant-wide default), at a point in time.

    Pure domain logic, no I/O — the repository loads every entry matching
    the cylinder type + customer type; this picks the right one. A
    branch-specific override always wins over the tenant-wide default when
    both exist for the same point in time.
    """

    @staticmethod
    def resolve(
        entries: Sequence[PriceListEntry],
        *,
        cylinder_type_id: uuid.UUID,
        customer_type: str,
        branch_id: uuid.UUID | None,
        at: datetime,
    ) -> PriceListEntry | None:
        applicable = [
            entry
            for entry in entries
            if entry.cylinder_type_id == cylinder_type_id
            and entry.customer_type == customer_type
            and entry.effective_from <= at
        ]
        if not applicable:
            return None

        if branch_id is not None:
            branch_specific = [entry for entry in applicable if entry.branch_id == branch_id]
            if branch_specific:
                return max(branch_specific, key=lambda entry: entry.effective_from)

        tenant_wide = [entry for entry in applicable if entry.is_tenant_wide_default]
        if not tenant_wide:
            return None
        return max(tenant_wide, key=lambda entry: entry.effective_from)
