"""Application use cases for driver/vehicle compliance documents.

Kept in its own module (not `use_cases.py`, already 600+ lines) so the
compliance-pack slice is self-contained. Persistence use cases
(add / replace / verify / list) land here alongside the OCR one as the
`compliance_document` table + repository are built.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date  # noqa: TC003
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import NotFoundError
from lpg.domain.delivery.compliance_document_parser import (
    parse_driving_licence,
    parse_vehicle_rc,
)

if TYPE_CHECKING:
    from lpg.application.common.ports import DocumentOcrPort, FileStorage

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
