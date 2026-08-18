from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.accounting import get_invoice_repository
from lpg.application.accounting.ports import InvoiceRepository
from lpg.application.printing.use_cases import GeneratePrintJobUseCase
from lpg.infrastructure.printing.engine import Xhtml2pdfPrintingEngine


async def get_printing_use_case(
    invoice_repo: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
) -> GeneratePrintJobUseCase:
    from lpg.api.app import get_app_state

    state = get_app_state()
    engine = Xhtml2pdfPrintingEngine()
    if state.storage is None:
        raise RuntimeError("Storage is not configured")
    return GeneratePrintJobUseCase(
        printing_engine=engine,
        invoice_repository=invoice_repo,
        storage=state.storage,
    )
