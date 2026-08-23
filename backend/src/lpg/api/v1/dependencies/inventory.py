"""FastAPI dependency providers for the inventory bounded context."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.identity import get_current_principal
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.common.ports import UnitOfWork
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.inventory.ports import (
    GoodsReceiptNoteRepository,
    GrnNumberSequence,
    InventoryLocationRepository,
    ReconciliationRecordRepository,
)


def get_inventory_location_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> InventoryLocationRepository:
    from lpg.infrastructure.persistence.repositories.inventory import (
        SqlAlchemyInventoryLocationRepository,
    )

    return SqlAlchemyInventoryLocationRepository(unit_of_work)  # type: ignore[arg-type]


def get_goods_receipt_note_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> GoodsReceiptNoteRepository:
    from lpg.infrastructure.persistence.repositories.inventory import (
        SqlAlchemyGoodsReceiptNoteRepository,
    )

    return SqlAlchemyGoodsReceiptNoteRepository(unit_of_work)  # type: ignore[arg-type]


def get_grn_number_sequence(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> GrnNumberSequence:
    from lpg.infrastructure.persistence.repositories.reference_number import (
        SqlAlchemyReferenceNumberSequence,
    )

    return SqlAlchemyReferenceNumberSequence(
        unit_of_work,  # type: ignore[arg-type]
        principal.tenant_id,
        entity_type="grn",
        prefix="GRN",
    )


def get_reconciliation_record_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ReconciliationRecordRepository:
    from lpg.infrastructure.persistence.repositories.inventory import (
        SqlAlchemyReconciliationRecordRepository,
    )

    return SqlAlchemyReconciliationRecordRepository(unit_of_work)  # type: ignore[arg-type]
