"""Dependencies for the accounting bounded context."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.accounting.ports import (
    CashHandoverRepository,
    CreditNoteRepository,
    InvoiceRepository,
)
from lpg.application.common.ports import UnitOfWork


def get_invoice_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> InvoiceRepository:
    import typing

    from lpg.infrastructure.persistence.repositories.accounting import (
        SqlAlchemyInvoiceRepository,
    )

    # In a real app we might not instantiate repositories directly like this
    # without type narrowing, but since UnitOfWork is a protocol and we know
    # it's SqlAlchemyUnitOfWork at runtime, we can cast it if needed, or pass
    # it in. SqlAlchemyInvoiceRepository accepts SqlAlchemyUnitOfWork. To keep
    # things clean in the API layer, we just type ignore or cast.
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    uow = typing.cast("SqlAlchemyUnitOfWork", unit_of_work)
    return SqlAlchemyInvoiceRepository(uow)


def get_cash_handover_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CashHandoverRepository:
    import typing

    from lpg.infrastructure.persistence.repositories.accounting import (
        SqlAlchemyCashHandoverRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    uow = typing.cast("SqlAlchemyUnitOfWork", unit_of_work)
    return SqlAlchemyCashHandoverRepository(uow)


def get_credit_note_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CreditNoteRepository:
    import typing

    from lpg.infrastructure.persistence.repositories.accounting import (
        SqlAlchemyCreditNoteRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    uow = typing.cast("SqlAlchemyUnitOfWork", unit_of_work)
    return SqlAlchemyCreditNoteRepository(uow)
