"""Dependencies for the accounting bounded context."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.identity import get_current_principal
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.accounting.ports import (
    CashHandoverNumberSequence,
    CashHandoverRepository,
    CreditNoteNumberSequence,
    CreditNoteRepository,
    InvoiceRepository,
    UninvoicedOrderReader,
)
from lpg.application.accounting.use_cases import GenerateInvoiceForOrderUseCase
from lpg.application.common.ports import UnitOfWork
from lpg.application.identity.ports import AuthenticatedPrincipal


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


def get_credit_note_number_sequence(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> CreditNoteNumberSequence:
    from lpg.infrastructure.persistence.repositories.reference_number import (
        SqlAlchemyReferenceNumberSequence,
    )

    return SqlAlchemyReferenceNumberSequence(
        unit_of_work,  # type: ignore[arg-type]
        principal.tenant_id,
        entity_type="credit_note",
        prefix="CRN",
        include_year=True,
    )


def get_cash_handover_number_sequence(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> CashHandoverNumberSequence:
    from lpg.infrastructure.persistence.repositories.reference_number import (
        SqlAlchemyReferenceNumberSequence,
    )

    return SqlAlchemyReferenceNumberSequence(
        unit_of_work,  # type: ignore[arg-type]
        principal.tenant_id,
        entity_type="cash_handover",
        prefix="CSH",
    )


def get_uninvoiced_order_reader(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> UninvoicedOrderReader:
    import typing

    from lpg.infrastructure.persistence.repositories.accounting import (
        SqlAlchemyUninvoicedOrderReader,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    uow = typing.cast("SqlAlchemyUnitOfWork", unit_of_work)
    return SqlAlchemyUninvoicedOrderReader(uow)


def get_generate_invoice_use_case(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> GenerateInvoiceForOrderUseCase:
    """The same wiring the post-delivery event handler uses
    (`infrastructure/events/accounting_handlers.py`), for issuing a held
    invoice from the dashboard.
    """
    import typing

    from lpg.config.settings import get_settings
    from lpg.infrastructure.persistence.repositories.accounting import (
        SqlAlchemyInvoiceRepository,
        SqlAlchemyOnlinePaymentRepository,
    )
    from lpg.infrastructure.persistence.repositories.customer import SqlAlchemyCustomerRepository
    from lpg.infrastructure.persistence.repositories.order import (
        SqlAlchemyOrderRepository,
        SqlAlchemyProofOfDeliveryRepository,
    )
    from lpg.infrastructure.persistence.repositories.reference_number import (
        SqlAlchemyReferenceNumberSequence,
    )
    from lpg.infrastructure.persistence.repositories.tenant import (
        SqlAlchemyCylinderTypeRepository,
        SqlAlchemyTenantConfigurationRepository,
        SqlAlchemyTenantRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
    from lpg.infrastructure.security.field_encryption import FernetFieldEncryptor

    uow = typing.cast("SqlAlchemyUnitOfWork", unit_of_work)
    return GenerateInvoiceForOrderUseCase(
        invoice_repository=SqlAlchemyInvoiceRepository(uow),
        order_repository=SqlAlchemyOrderRepository(uow),
        customer_repository=SqlAlchemyCustomerRepository(uow, FernetFieldEncryptor(get_settings())),
        tenant_config_repository=SqlAlchemyTenantConfigurationRepository(uow),
        invoice_number_sequence=SqlAlchemyReferenceNumberSequence(
            uow, principal.tenant_id, entity_type="invoice", prefix="INV", include_year=True
        ),
        cylinder_type_repository=SqlAlchemyCylinderTypeRepository(uow),
        tenant_repository=SqlAlchemyTenantRepository(uow),
        online_payment_repository=SqlAlchemyOnlinePaymentRepository(uow),
        proof_of_delivery_reader=SqlAlchemyProofOfDeliveryRepository(uow),
    )
