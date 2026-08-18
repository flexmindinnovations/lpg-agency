from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.dependencies.printing import get_printing_use_case
from lpg.application.printing.use_cases import GeneratePrintJobUseCase, PrintFormat, PrintJobCommand

router = APIRouter(prefix="/print-jobs", tags=["Printing"])


class PrintJobRequest(BaseModel):
    document_type: str  # 'invoice'
    document_id: uuid.UUID
    format: str = "pdf"  # 'pdf' or 'thermal'


class PrintJobResponse(BaseModel):
    download_url: str
    format: str
    content_type: str


@router.post(
    "",
    response_model=PrintJobResponse,
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def create_print_job(
    request: PrintJobRequest,
    use_case: Annotated[GeneratePrintJobUseCase, Depends(get_printing_use_case)],
) -> PrintJobResponse:
    """Generate a printable document and return a download URL."""
    try:
        fmt = PrintFormat(request.format)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Unsupported format: {request.format}"
        ) from None

    command = PrintJobCommand(
        document_type=request.document_type,
        document_id=request.document_id,
        output_format=fmt,
    )
    result = await use_case.execute(command)
    return PrintJobResponse(
        download_url=result.download_url,
        format=result.output_format,
        content_type=result.content_type,
    )
