"""Generic document endpoints — pre-upload a scanned document and run a
server-side OCR "second pass" over it.

Shared infrastructure for every "read a document image" flow. Customer KYC
keeps its own `/customers/kyc-attachments*` endpoints (Aadhaar/PAN specific);
driver/vehicle compliance (driving licence, RC) uses these.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from lpg.api.v1.dependencies.customer import get_document_ocr_port
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.order import get_file_storage
from lpg.api.v1.schemas.document import (
    DocumentAttachmentResponse,
    RecognizeComplianceDocumentRequest,
    RecognizeComplianceDocumentResponse,
)
from lpg.application.common.ports import DocumentOcrPort, FileStorage
from lpg.application.delivery.compliance_use_cases import (
    RecognizeComplianceDocumentCommand,
    RecognizeComplianceDocumentUseCase,
)
from lpg.application.identity.ports import AuthenticatedPrincipal

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/attachments",
    response_model=DocumentAttachmentResponse,
    status_code=201,
    dependencies=[Depends(require_permission("documents:upload"))],
)
async def upload_document_attachment(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
    file: Annotated[UploadFile, File()],
) -> DocumentAttachmentResponse:
    """Pre-upload a document image, staged under a tenant-scoped key so it can
    be captured and OCR'd before the owning record exists (same reasoning as
    `upload_kyc_attachment`)."""
    key = f"tenant/{principal.tenant_id}/compliance-staging/{uuid.uuid4()}_{file.filename}"
    data = await file.read()
    await file_storage.upload(key, data, content_type=file.content_type)
    return DocumentAttachmentResponse(blob_ref=key)


@router.post(
    "/recognize",
    response_model=RecognizeComplianceDocumentResponse,
    dependencies=[Depends(require_permission("documents:upload"))],
)
async def recognize_document(
    request: RecognizeComplianceDocumentRequest,
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
    ocr: Annotated[DocumentOcrPort, Depends(get_document_ocr_port)],
) -> RecognizeComplianceDocumentResponse:
    """Re-read an already-uploaded driving licence / RC image with the heavier
    server-side OCR model and parse it for the fields the register/edit form
    needs. Degrades to "number only" on a low-quality scan — never blocks."""
    use_case = RecognizeComplianceDocumentUseCase(file_storage, ocr)
    result = await use_case.execute(
        RecognizeComplianceDocumentCommand(blob_ref=request.blob_ref, doc_kind=request.doc_kind)
    )
    return RecognizeComplianceDocumentResponse(
        doc_kind=result.doc_kind,
        confidence=result.confidence,
        document_number=result.document_number,
        holder_name=result.holder_name,
        date_of_birth=result.date_of_birth,
        valid_till=result.valid_till,
        transport_valid_till=result.transport_valid_till,
        vehicle_classes=list(result.vehicle_classes),
        registration_number=result.registration_number,
        registration_date=result.registration_date,
        fitness_upto=result.fitness_upto,
        insurance_upto=result.insurance_upto,
        chassis_number=result.chassis_number,
        engine_number=result.engine_number,
        fuel_type=result.fuel_type,
        maker_model=result.maker_model,
    )
