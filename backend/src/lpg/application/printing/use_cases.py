from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from lpg.application.printing.models import (
    CustomerInfo,
    InvoicePrintPayload,
    PrintLineItem,
    TenantHeader,
)
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.application.accounting.ports import InvoiceRepository
    from lpg.application.common.ports import FileStorage
    from lpg.application.printing.ports import PrintingEngine

_logger = get_logger(__name__)


class PrintFormat(StrEnum):
    PDF = "pdf"
    THERMAL = "thermal"


@dataclass(frozen=True)
class PrintJobCommand:
    document_type: str
    document_id: uuid.UUID
    output_format: PrintFormat


@dataclass(frozen=True)
class PrintJobResult:
    download_url: str
    output_format: str
    content_type: str


class GeneratePrintJobUseCase:
    def __init__(
        self,
        *,
        printing_engine: PrintingEngine,
        invoice_repository: InvoiceRepository,
        storage: FileStorage,
    ) -> None:
        self._engine = printing_engine
        self._invoice_repo = invoice_repository
        self._storage = storage

    async def execute(self, command: PrintJobCommand) -> PrintJobResult:
        if command.document_type == "invoice":
            return await self._render_invoice(command)
        msg = f"Unsupported document type: {command.document_type}"
        raise ValueError(msg)

    async def _render_invoice(self, command: PrintJobCommand) -> PrintJobResult:
        invoice = await self._invoice_repo.get_by_id(command.document_id)
        if invoice is None:
            msg = f"Invoice {command.document_id} not found"
            raise ValueError(msg)

        # Assemble the fully-resolved print payload
        payload = InvoicePrintPayload(
            invoice_number=f"INV-{str(invoice.id)[:8].upper()}",
            tenant_header=TenantHeader(
                agency_name="LPG Agency",  # TODO: resolve from tenant config
            ),
            customer=CustomerInfo(
                name=f"Customer {str(invoice.customer_id)[:8]}",  # TODO: resolve from customer repo
            ),
            line_items=[
                PrintLineItem(
                    description=f"Cylinder Type {str(line.cylinder_type_id)[:8]}",  # TODO: resolve name
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    subtotal=line.subtotal,
                    tax_amount=line.tax_amount,
                    total_amount=line.total_amount,
                )
                for line in invoice.lines
            ],
            subtotal=invoice.subtotal,
            tax_amount=invoice.tax_amount,
            total_amount=invoice.total_amount,
            payment_status=invoice.status,
            issued_at=invoice.issued_at,
            qr_code_data=f"lpg-invoice:{invoice.id}",
        )

        if command.output_format == PrintFormat.PDF:
            pdf_bytes = self._engine.render_invoice_pdf(payload)
            key = f"print-jobs/{invoice.id}.pdf"
            content_type = "application/pdf"
            await self._storage.upload(key, pdf_bytes, content_type=content_type)
        elif command.output_format == PrintFormat.THERMAL:
            thermal_bytes = self._engine.render_invoice_thermal(payload)
            key = f"print-jobs/{invoice.id}.txt"
            content_type = "text/plain"
            await self._storage.upload(key, thermal_bytes, content_type=content_type)
        else:
            msg = f"Unsupported format: {command.output_format}"  # type: ignore[unreachable]
            raise ValueError(msg)

        download_url = await self._storage.url(key, expires_seconds=300)

        _logger.info(
            "print_job_completed",
            document_type=command.document_type,
            document_id=str(command.document_id),
            format=command.output_format,
        )

        return PrintJobResult(
            download_url=download_url,
            output_format=command.output_format.value,
            content_type=content_type,
        )
