from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from lpg.domain.customer.onboarding_draft import OnboardingDraftEntry
from lpg.infrastructure.persistence.models.customer import CustomerOnboardingDraftModel

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyOnboardingDraftRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    def _to_domain(self, row: CustomerOnboardingDraftModel) -> OnboardingDraftEntry:
        return OnboardingDraftEntry(
            id=row.id,
            tenant_id=row.tenant_id,
            created_by=row.created_by,
            branch_id=row.branch_id,
            current_step=row.current_step,
            registration_data=dict(row.registration_data or {}),
            address_data=dict(row.address_data or {}),
            kyc_data=dict(row.kyc_data or {}),
            kyc_document_blob_ref=row.kyc_document_blob_ref,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def save(self, draft: OnboardingDraftEntry) -> OnboardingDraftEntry:
        stmt = select(CustomerOnboardingDraftModel).where(
            CustomerOnboardingDraftModel.id == draft.id
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()

        if row is None:
            row = CustomerOnboardingDraftModel(
                id=draft.id,
                tenant_id=draft.tenant_id,
                created_by=draft.created_by,
                branch_id=draft.branch_id,
                current_step=draft.current_step,
                registration_data=draft.registration_data,
                address_data=draft.address_data,
                kyc_data=draft.kyc_data,
                kyc_document_blob_ref=draft.kyc_document_blob_ref,
            )
            self._uow.session.add(row)
        else:
            row.branch_id = draft.branch_id
            row.current_step = draft.current_step
            row.registration_data = draft.registration_data
            row.address_data = draft.address_data
            row.kyc_data = draft.kyc_data
            row.kyc_document_blob_ref = draft.kyc_document_blob_ref
            row.updated_at = datetime.now(UTC)

        await self._uow.session.flush()
        return self._to_domain(row)

    async def get_by_id(
        self, draft_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> OnboardingDraftEntry | None:
        stmt = select(CustomerOnboardingDraftModel).where(
            CustomerOnboardingDraftModel.id == draft_id,
            CustomerOnboardingDraftModel.tenant_id == tenant_id,
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        return self._to_domain(row) if row is not None else None

    async def list_by_user(
        self, tenant_id: uuid.UUID, created_by: uuid.UUID
    ) -> list[OnboardingDraftEntry]:
        stmt = (
            select(CustomerOnboardingDraftModel)
            .where(
                CustomerOnboardingDraftModel.tenant_id == tenant_id,
                CustomerOnboardingDraftModel.created_by == created_by,
            )
            .order_by(CustomerOnboardingDraftModel.updated_at.desc())
        )
        result = await self._uow.session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars()]

    async def delete(self, draft_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        stmt = delete(CustomerOnboardingDraftModel).where(
            CustomerOnboardingDraftModel.id == draft_id,
            CustomerOnboardingDraftModel.tenant_id == tenant_id,
        )
        await self._uow.session.execute(stmt)
