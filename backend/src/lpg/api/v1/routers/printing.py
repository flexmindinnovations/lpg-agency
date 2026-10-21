from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.dependencies.printing import get_printing_use_case
from lpg.application.printing.use_cases import (
    DocumentNotFoundError,
    GeneratePrintJobUseCase,
    PrintFormat,
    PrintJobCommand,
    StorageNotConfiguredError,
    UnsupportedDocumentError,
)

router = APIRouter(prefix="/print-jobs", tags=["Printing"])


class PrintJobRequest(BaseModel):
    document_type: str  # 'invoice'
    document_id: uuid.UUID
    format: str = "pdf"  # 'pdf' or 'thermal'


class PrintJobResponse(BaseModel):
    download_url: str
    format: str
    content_type: str


def _command(request: PrintJobRequest) -> PrintJobCommand:
    try:
        fmt = PrintFormat(request.format)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Unsupported format: {request.format}"
        ) from None
    return PrintJobCommand(
        document_type=request.document_type,
        document_id=request.document_id,
        output_format=fmt,
    )


@router.post(
    "/document",
    response_class=Response,
    responses={
        200: {
            "description": "The rendered document itself (PDF, or an HTML receipt for thermal).",
            "content": {"application/pdf": {}, "text/html": {}},
        }
    },
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def render_print_document(
    request: PrintJobRequest,
    use_case: Annotated[GeneratePrintJobUseCase, Depends(get_printing_use_case)],
) -> Response:
    """Render a printable document and return it directly. Needs no file storage."""
    command = _command(request)
    try:
        rendered = await use_case.render(command)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return Response(
        content=rendered.content,
        media_type=rendered.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{rendered.filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "",
    response_model=PrintJobResponse,
    deprecated=True,
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def create_print_job(
    request: PrintJobRequest,
    use_case: Annotated[GeneratePrintJobUseCase, Depends(get_printing_use_case)],
) -> PrintJobResponse:
    """Render, store in file storage and return a download URL.

    Deprecated: use ``POST /print-jobs/document``, which needs no file storage.
    """
    command = _command(request)
    try:
        result = await use_case.execute(command)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except StorageNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    return PrintJobResponse(
        download_url=result.download_url,
        format=result.output_format,
        content_type=result.content_type,
    )
