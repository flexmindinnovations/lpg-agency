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
from lpg.domain.common.gst import normalize_hsn_code, validate_gst_rate

if TYPE_CHECKING:
    import uuid
    from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CylinderTypeRenamed(DomainEvent):
    cylinder_type_id: uuid.UUID | None = None
    new_name: str = ""


class CylinderType(AggregateRoot):
    """A cylinder size the agency sells, with its GST classification.

    `hsn_code` and `gst_rate_percent` are the tax treatment of selling this
    product (BR-16): domestic LPG and commercial LPG attract different GST
    rates, so the rate belongs to the product, not to the tenant. Both are
    tenant-configured (BR-31) and start unset — invoice generation refuses a
    cylinder type with no rate rather than issuing a 0% invoice.
    """

    __slots__ = (
        "_gst_rate_percent",
        "_hsn_code",
        "_is_active",
        "_name",
        "_tenant_id",
        "_weight_kg",
    )

    def __init__(
        self,
        cylinder_type_id: uuid.UUID,
        tenant_id: uuid.UUID,
        name: str,
        weight_kg: Decimal,
        *,
        is_active: bool = True,
        hsn_code: str | None = None,
        gst_rate_percent: Decimal | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(cylinder_type_id, version=version)
        self._tenant_id = tenant_id
        self._name = name
        self._weight_kg = weight_kg
        self._is_active = is_active
        self._hsn_code = hsn_code
        self._gst_rate_percent = gst_rate_percent

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

    @property
    def hsn_code(self) -> str | None:
        return self._hsn_code

    @property
    def gst_rate_percent(self) -> Decimal | None:
        return self._gst_rate_percent

    @property
    def is_gst_configured(self) -> bool:
        return self._hsn_code is not None and self._gst_rate_percent is not None

    def classify_for_gst(self, *, hsn_code: str, gst_rate_percent: Decimal) -> None:
        """Set the HSN code and GST rate invoices for this product use.
        Applies to invoices issued from now on; issued invoices keep the
        rate and HSN they were issued with.
        """
        self._hsn_code = normalize_hsn_code(hsn_code)
        self._gst_rate_percent = validate_gst_rate(gst_rate_percent)

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
