"""Application use cases for driver/vehicle compliance documents.

Kept in its own module (not `use_cases.py`, already 600+ lines) so the
compliance-pack slice is self-contained. Persistence use cases
(add / replace / verify / list) land here alongside the OCR one as the
`compliance_document` table + repository are built.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from dataclasses import dataclass
from datetime import date  # noqa: TC003
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command, Query
from lpg.application.common.errors import ConflictError, NotFoundError
from lpg.domain.delivery.compliance_document import ComplianceDocument
from lpg.domain.delivery.compliance_document_parser import (
    parse_driving_licence,
    parse_vehicle_rc,
)

if TYPE_CHECKING:
    from lpg.application.common.ports import DocumentOcrPort, FileStorage, UnitOfWork
    from lpg.application.delivery.ports import ComplianceDocumentRepository

DocKind = str  # "driving_licence" | "vehicle_rc"


@dataclass(frozen=True, slots=True)
class RecognizeComplianceDocumentCommand(Command):
    blob_ref: str
    doc_kind: DocKind


@dataclass(frozen=True, slots=True)
class RecognizeComplianceDocumentResult:
    """Union of the fields the DL and RC parsers can produce — only the ones
    relevant to `doc_kind` are populated. Every field is a reviewable head
    start, never written straight through (same contract as KYC)."""

    doc_kind: DocKind
    confidence: float
    document_number: str | None
    holder_name: str | None
    # DL
    date_of_birth: date | None = None
    valid_till: date | None = None
    transport_valid_till: date | None = None
    vehicle_classes: tuple[str, ...] = ()
    # RC
    registration_number: str | None = None
    registration_date: date | None = None
    fitness_upto: date | None = None
    insurance_upto: date | None = None
    chassis_number: str | None = None
    engine_number: str | None = None
    fuel_type: str | None = None
    maker_model: str | None = None


class RecognizeComplianceDocumentUseCase:
    """Server-side OCR "second pass" for a driving licence or vehicle RC image
    the client already uploaded via `POST /documents/attachments`. Same shape
    as `RecognizeKycDocumentUseCase` — only the field parser differs by
    `doc_kind`."""

    _VALID_KINDS = frozenset({"driving_licence", "vehicle_rc"})

    def __init__(self, file_storage: FileStorage, ocr: DocumentOcrPort) -> None:
        self._file_storage = file_storage
        self._ocr = ocr

    async def execute(
        self, command: RecognizeComplianceDocumentCommand
    ) -> RecognizeComplianceDocumentResult:
        if command.doc_kind not in self._VALID_KINDS:
            msg = f"Unsupported document kind: '{command.doc_kind}'."
            raise NotFoundError(msg, doc_kind=command.doc_kind)

        image_bytes = await self._file_storage.download(command.blob_ref)
        if image_bytes is None:
            msg = f"No uploaded document found for blob ref {command.blob_ref}."
            raise NotFoundError(msg, blob_ref=command.blob_ref)

        ocr_result = await self._ocr.recognize(image_bytes)

        if command.doc_kind == "driving_licence":
            dl = parse_driving_licence(ocr_result.text)
            return RecognizeComplianceDocumentResult(
                doc_kind=command.doc_kind,
                confidence=ocr_result.confidence,
                document_number=dl.document_number,
                holder_name=dl.holder_name,
                date_of_birth=dl.date_of_birth,
                valid_till=dl.valid_till,
                transport_valid_till=dl.transport_valid_till,
                vehicle_classes=dl.vehicle_classes,
            )

        rc = parse_vehicle_rc(ocr_result.text)
        return RecognizeComplianceDocumentResult(
            doc_kind=command.doc_kind,
            confidence=ocr_result.confidence,
            document_number=rc.document_number,
            holder_name=rc.owner_name,
            registration_number=rc.registration_number,
            registration_date=rc.registration_date,
            valid_till=rc.valid_upto,
            fitness_upto=rc.fitness_upto,
            insurance_upto=rc.insurance_upto,
            chassis_number=rc.chassis_number,
            engine_number=rc.engine_number,
            fuel_type=rc.fuel_type,
            maker_model=rc.maker_model,
        )


# ==========================================================================
# Compliance document persistence
# ==========================================================================


@dataclass(frozen=True, slots=True)
class AddComplianceDocumentCommand(Command):
    tenant_id: uuid.UUID
    owner_type: str
    owner_id: uuid.UUID
    doc_type: str
    document_number: str
    file_ref: str
    issue_date: date | None = None
    expiry_date: date | None = None


class AddComplianceDocumentUseCase:
    """Attach a new compliance document to a driver/vehicle. An owner holds at
    most one live document of each type — a renewal is a `replace`, not a
    second row."""

    def __init__(self, repository: ComplianceDocumentRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: AddComplianceDocumentCommand) -> ComplianceDocument:
        existing = await self._repository.get_for_owner_and_type(
            command.owner_type, command.owner_id, command.doc_type
        )
        if existing is not None:
            msg = (
                f"A '{command.doc_type}' document already exists for this "
                f"{command.owner_type}. Replace it instead of adding a second."
            )
            raise ConflictError(msg, document_id=str(existing.id))

        doc = ComplianceDocument(
            document_id=self._repository.next_id(),
            tenant_id=command.tenant_id,
            owner_type=command.owner_type,
            owner_id=command.owner_id,
            doc_type=command.doc_type,
            document_number=command.document_number,
            file_ref=command.file_ref,
            issue_date=command.issue_date,
            expiry_date=command.expiry_date,
        )
        await self._repository.save(doc)
        await self._unit_of_work.commit()
        return doc


@dataclass(frozen=True, slots=True)
class ReplaceComplianceDocumentCommand(Command):
    document_id: uuid.UUID
    document_number: str
    file_ref: str
    issue_date: date | None = None
    expiry_date: date | None = None


class ReplaceComplianceDocumentUseCase:
    def __init__(self, repository: ComplianceDocumentRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: ReplaceComplianceDocumentCommand) -> ComplianceDocument:
        doc = await self._require(command.document_id)
        doc.replace(
            document_number=command.document_number,
            file_ref=command.file_ref,
            issue_date=command.issue_date,
            expiry_date=command.expiry_date,
        )
        await self._repository.save(doc)
        await self._unit_of_work.commit()
        return doc

    async def _require(self, document_id: uuid.UUID) -> ComplianceDocument:
        doc = await self._repository.get_by_id(document_id)
        if doc is None:
            msg = f"No compliance document visible with id {document_id}."
            raise NotFoundError(msg, document_id=str(document_id))
        return doc


@dataclass(frozen=True, slots=True)
class VerifyComplianceDocumentCommand(Command):
    document_id: uuid.UUID
    verified_by: uuid.UUID
    status: str  # "verified" | "rejected"
    rejection_reason: str | None = None


class VerifyComplianceDocumentUseCase:
    def __init__(self, repository: ComplianceDocumentRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: VerifyComplianceDocumentCommand) -> ComplianceDocument:
        doc = await self._repository.get_by_id(command.document_id)
        if doc is None:
            msg = f"No compliance document visible with id {command.document_id}."
            raise NotFoundError(msg, document_id=str(command.document_id))

        doc.verify(
            status=command.status,
            verified_by=command.verified_by,
            rejection_reason=command.rejection_reason,
        )
        await self._repository.save(doc)
        await self._unit_of_work.commit()
        return doc


@dataclass(frozen=True, slots=True)
class ListComplianceDocumentsForOwnerQuery(Query):
    owner_type: str
    owner_id: uuid.UUID


class ListComplianceDocumentsForOwnerUseCase:
    def __init__(self, repository: ComplianceDocumentRepository) -> None:
        self._repository = repository

    async def execute(
        self, query: ListComplianceDocumentsForOwnerQuery
    ) -> list[ComplianceDocument]:
        return await self._repository.list_by_owner(query.owner_type, query.owner_id)


@dataclass(frozen=True, slots=True)
class ListComplianceDocumentsQuery(Query):
    owner_type: str | None = None
    status: str | None = None
    expiry: str | None = None  # "expiring" | "expired"
    skip: int = 0
    limit: int = 50


class ListComplianceDocumentsUseCase:
    def __init__(self, repository: ComplianceDocumentRepository) -> None:
        self._repository = repository

    async def execute(
        self, query: ListComplianceDocumentsQuery
    ) -> tuple[list[ComplianceDocument], int]:
        docs = await self._repository.list_for_tenant(
            owner_type=query.owner_type,
            status=query.status,
            expiry=query.expiry,
            skip=query.skip,
            limit=query.limit,
        )
        total = await self._repository.count_for_tenant(
            owner_type=query.owner_type,
            status=query.status,
            expiry=query.expiry,
        )
        return docs, total
