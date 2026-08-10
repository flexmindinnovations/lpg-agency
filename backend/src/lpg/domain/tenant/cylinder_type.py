"""The `CylinderType` aggregate — a tenant's catalog of cylinder sizes.

Own aggregate root, same rationale as `Branch`/`Warehouse`. Never hard-deleted
— deactivated only, since Inventory (Phase 9) will foreign-key against this
and a cylinder type that ever existed must stay resolvable for historical
inventory/order records.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

if TYPE_CHECKING:
    import uuid
    from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CylinderTypeRenamed(DomainEvent):
    cylinder_type_id: uuid.UUID | None = None
    new_name: str = ""


class CylinderType(AggregateRoot):
    __slots__ = ("_is_active", "_name", "_tenant_id", "_weight_kg")

    def __init__(
        self,
        cylinder_type_id: uuid.UUID,
        tenant_id: uuid.UUID,
        name: str,
        weight_kg: Decimal,
        *,
        is_active: bool = True,
        version: int = 1,
    ) -> None:
        super().__init__(cylinder_type_id, version=version)
        self._tenant_id = tenant_id
        self._name = name
        self._weight_kg = weight_kg
        self._is_active = is_active

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def weight_kg(self) -> Decimal:
        return self._weight_kg

    @property
    def is_active(self) -> bool:
        return self._is_active

    def rename(self, new_name: str) -> None:
        stripped = new_name.strip()
        if not stripped:
            msg = "Cylinder type name cannot be empty."
            raise InvariantViolation(msg, cylinder_type_id=str(self.id))

        self._name = stripped
        self.record_event(CylinderTypeRenamed(cylinder_type_id=self.id, new_name=stripped))

    def adjust_weight(self, new_weight_kg: Decimal) -> None:
        if new_weight_kg <= 0:
            msg = "Cylinder weight must be greater than zero."
            raise InvariantViolation(msg, cylinder_type_id=str(self.id))

        self._weight_kg = new_weight_kg

    def activate(self) -> None:
        self._is_active = True

    def deactivate(self) -> None:
        self._is_active = False
