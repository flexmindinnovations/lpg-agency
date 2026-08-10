"""The `Warehouse` aggregate — a tenant's physical stock-holding location,
scoped to one branch.

Own aggregate root, same rationale as `Branch` (see that module's docstring)
— Inventory (Phase 9) will foreign-key against this directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

if TYPE_CHECKING:
    import uuid


@dataclass(frozen=True, slots=True)
class WarehouseRenamed(DomainEvent):
    warehouse_id: uuid.UUID | None = None
    new_name: str = ""


class Warehouse(AggregateRoot):
    __slots__ = ("_address_line", "_branch_id", "_name", "_tenant_id")

    def __init__(
        self,
        warehouse_id: uuid.UUID,
        tenant_id: uuid.UUID,
        branch_id: uuid.UUID,
        name: str,
        address_line: str,
        *,
        version: int = 1,
    ) -> None:
        super().__init__(warehouse_id, version=version)
        self._tenant_id = tenant_id
        self._branch_id = branch_id
        self._name = name
        self._address_line = address_line

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def branch_id(self) -> uuid.UUID:
        return self._branch_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def address_line(self) -> str:
        return self._address_line

    def rename(self, new_name: str) -> None:
        stripped = new_name.strip()
        if not stripped:
            msg = "Warehouse name cannot be empty."
            raise InvariantViolation(msg, warehouse_id=str(self.id))

        self._name = stripped
        self.record_event(WarehouseRenamed(warehouse_id=self.id, new_name=stripped))

    def relocate(self, new_address_line: str) -> None:
        stripped = new_address_line.strip()
        if not stripped:
            msg = "Warehouse address cannot be empty."
            raise InvariantViolation(msg, warehouse_id=str(self.id))

        self._address_line = stripped
