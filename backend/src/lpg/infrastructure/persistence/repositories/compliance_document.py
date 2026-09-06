"""SQLAlchemy implementation of ComplianceDocumentRepository.

All queries are tenant-scoped via Row-Level Security on
`delivery.compliance_document`. Implements
`lpg.application.delivery.ports.ComplianceDocumentRepository`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import Select, func, select

from lpg.domain.delivery.compliance_document import ComplianceDocument
from lpg.infrastructure.persistence.models.delivery import ComplianceDocumentModel

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyComplianceDocumentRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def _to_domain(self, row: ComplianceDocumentModel) -> ComplianceDocument:
        doc = ComplianceDocument(
            document_id=row.id,
            tenant_id=row.tenant_id,
            owner_type=row.owner_type,
            owner_id=row.owner_id,
            doc_type=row.doc_type,
            document_number=row.document_number,
            file_ref=row.file_ref,
            issue_date=row.issue_date,
            expiry_date=row.expiry_date,
            verification_status=row.verification_status,
            rejection_reason=row.rejection_reason,
            verified_by=row.verified_by,
            verified_at=row.verified_at,
            version=row.version,
        )
        doc.clear_events()
        self._uow.register_aggregate(doc)
        return doc

    def _sync_row(self, row: ComplianceDocumentModel, doc: ComplianceDocument) -> None:
        row.document_number = doc.document_number
        row.file_ref = doc.file_ref
        row.issue_date = doc.issue_date
        row.expiry_date = doc.expiry_date
        row.verification_status = doc.verification_status
        row.rejection_reason = doc.rejection_reason
        row.verified_by = doc.verified_by
        row.verified_at = doc.verified_at
        row.updated_at = datetime.now(UTC)
        row.version = doc.version

    # ------------------------------------------------------------------
    # Repository methods
    # ------------------------------------------------------------------

    async def save(self, doc: ComplianceDocument) -> None:
        stmt = select(ComplianceDocumentModel).where(ComplianceDocumentModel.id == doc.id)
        row = (await self._uow.session.execute(stmt)).scalars().first()
        if row is None:
            self._uow.session.add(
                ComplianceDocumentModel(
                    id=doc.id,
                    tenant_id=doc.tenant_id,
                    owner_type=doc.owner_type,
                    owner_id=doc.owner_id,
                    doc_type=doc.doc_type,
                    document_number=doc.document_number,
                    file_ref=doc.file_ref,
                    issue_date=doc.issue_date,
                    expiry_date=doc.expiry_date,
                    verification_status=doc.verification_status,
                    rejection_reason=doc.rejection_reason,
                    verified_by=doc.verified_by,
                    verified_at=doc.verified_at,
                )
            )
        else:
            self._sync_row(row, doc)

    async def get_by_id(self, document_id: uuid.UUID) -> ComplianceDocument | None:
        stmt = select(ComplianceDocumentModel).where(
            ComplianceDocumentModel.id == document_id,
            ComplianceDocumentModel.is_deleted.is_(False),
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        return self._to_domain(row) if row is not None else None

    async def get_for_owner_and_type(
        self, owner_type: str, owner_id: uuid.UUID, doc_type: str
    ) -> ComplianceDocument | None:
        """The single live document of a given type for an owner (there is at
        most one — `replace` supersedes in place)."""
        stmt = select(ComplianceDocumentModel).where(
            ComplianceDocumentModel.owner_type == owner_type,
            ComplianceDocumentModel.owner_id == owner_id,
            ComplianceDocumentModel.doc_type == doc_type,
            ComplianceDocumentModel.is_deleted.is_(False),
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        return self._to_domain(row) if row is not None else None

    async def list_by_owner(self, owner_type: str, owner_id: uuid.UUID) -> list[ComplianceDocument]:
        stmt = (
            select(ComplianceDocumentModel)
            .where(
                ComplianceDocumentModel.owner_type == owner_type,
                ComplianceDocumentModel.owner_id == owner_id,
                ComplianceDocumentModel.is_deleted.is_(False),
            )
            .order_by(ComplianceDocumentModel.doc_type)
        )
        rows = (await self._uow.session.execute(stmt)).scalars().all()
        return [self._to_domain(row) for row in rows]

    def _list_for_tenant_stmt(
        self,
        *,
        owner_type: str | None,
        status: str | None,
        expiry: str | None,
    ) -> Select[tuple[ComplianceDocumentModel]]:
        stmt = select(ComplianceDocumentModel).where(ComplianceDocumentModel.is_deleted.is_(False))
        if owner_type:
            stmt = stmt.where(ComplianceDocumentModel.owner_type == owner_type)
        if status:
            stmt = stmt.where(ComplianceDocumentModel.verification_status == status)

        today = datetime.now(UTC).date()
        if expiry == "expired":
            stmt = stmt.where(ComplianceDocumentModel.expiry_date < today)
        elif expiry == "expiring":
            stmt = stmt.where(
                ComplianceDocumentModel.expiry_date >= today,
                ComplianceDocumentModel.expiry_date <= today + timedelta(days=30),
            )
        return stmt

    async def list_for_tenant(
        self,
        *,
        owner_type: str | None = None,
        status: str | None = None,
        expiry: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ComplianceDocument]:
        stmt = (
            self._list_for_tenant_stmt(owner_type=owner_type, status=status, expiry=expiry)
            .order_by(ComplianceDocumentModel.expiry_date.asc().nullslast())
            .offset(skip)
            .limit(limit)
        )
        rows = (await self._uow.session.execute(stmt)).scalars().all()
        return [self._to_domain(row) for row in rows]

    async def count_for_tenant(
        self,
        *,
        owner_type: str | None = None,
        status: str | None = None,
        expiry: str | None = None,
    ) -> int:
        inner = self._list_for_tenant_stmt(
            owner_type=owner_type, status=status, expiry=expiry
        ).subquery()
        stmt = select(func.count()).select_from(inner)
        return (await self._uow.session.execute(stmt)).scalar_one()

    async def list_expiring(self, within_days: int = 30) -> list[ComplianceDocument]:
        """Documents whose expiry falls inside the next `within_days` and that
        have not had an "expiring" notification enqueued within that window —
        the nightly cron's work list."""
        today = datetime.now(UTC).date()
        horizon = today + timedelta(days=within_days)
        notified_cutoff = datetime.now(UTC) - timedelta(days=within_days)
        stmt = (
            select(ComplianceDocumentModel)
            .where(
                ComplianceDocumentModel.is_deleted.is_(False),
                ComplianceDocumentModel.expiry_date.is_not(None),
                ComplianceDocumentModel.expiry_date <= horizon,
                (ComplianceDocumentModel.last_expiry_notified_at.is_(None))
                | (ComplianceDocumentModel.last_expiry_notified_at < notified_cutoff),
            )
            .order_by(ComplianceDocumentModel.expiry_date)
        )
        rows = (await self._uow.session.execute(stmt)).scalars().all()
        return [self._to_domain(row) for row in rows]

    async def mark_expiry_notified(self, document_id: uuid.UUID) -> None:
        stmt = select(ComplianceDocumentModel).where(ComplianceDocumentModel.id == document_id)
        row = (await self._uow.session.execute(stmt)).scalars().first()
        if row is not None:
            row.last_expiry_notified_at = datetime.now(UTC)

    async def soft_delete(self, document_id: uuid.UUID) -> None:
        stmt = select(ComplianceDocumentModel).where(ComplianceDocumentModel.id == document_id)
        row = (await self._uow.session.execute(stmt)).scalars().first()
        if row is not None:
            row.is_deleted = True
            row.deleted_at = datetime.now(UTC)
