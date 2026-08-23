from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.identity import get_current_principal
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.common.ports import UnitOfWork
from lpg.application.customer.ports import (
    ConsumerNumberSequence,
    CustomerRepository,
    DocumentOcrPort,
    OnboardingDraftRepository,
)
from lpg.application.identity.ports import AuthenticatedPrincipal


def get_customer_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CustomerRepository:
    from lpg.config.settings import get_settings
    from lpg.infrastructure.persistence.repositories.customer import SqlAlchemyCustomerRepository
    from lpg.infrastructure.security.field_encryption import FernetFieldEncryptor

    field_encryptor = FernetFieldEncryptor(get_settings())
    return SqlAlchemyCustomerRepository(unit_of_work, field_encryptor)  # type: ignore[arg-type]


def get_consumer_number_sequence(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> ConsumerNumberSequence:
    from lpg.infrastructure.persistence.repositories.customer import (
        SqlAlchemyConsumerNumberSequence,
    )

    return SqlAlchemyConsumerNumberSequence(unit_of_work, principal.tenant_id)  # type: ignore[arg-type]


def get_onboarding_draft_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OnboardingDraftRepository:
    from lpg.infrastructure.persistence.repositories.onboarding_draft import (
        SqlAlchemyOnboardingDraftRepository,
    )

    return SqlAlchemyOnboardingDraftRepository(unit_of_work)  # type: ignore[arg-type]


def get_document_ocr_port() -> DocumentOcrPort:
    from lpg.infrastructure.ocr.rapidocr_adapter import RapidOcrDocumentAdapter

    return RapidOcrDocumentAdapter()
