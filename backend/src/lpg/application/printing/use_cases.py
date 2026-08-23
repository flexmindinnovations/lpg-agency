from __future__ import annotations

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
    import uuid

    from lpg.application.accounting.ports import InvoiceRepository
    from lpg.application.common.ports import FileStorage
    from lpg.application.customer.ports import CustomerRepository
    from lpg.application.printing.ports import PrintingEngine
    from lpg.application.tenant.ports import CylinderTypeRepository
    from lpg.domain.customer.customer import Customer

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
        customer_repository: CustomerRepository,
        cylinder_type_repository: CylinderTypeRepository,
        storage: FileStorage,
    ) -> None:
        self._engine = printing_engine
        self._invoice_repo = invoice_repository
        self._customer_repo = customer_repository
        self._cylinder_type_repo = cylinder_type_repository
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

        customer = await self._customer_repo.get_by_id(invoice.customer_id)
        customer_info = self._build_customer_info(customer, invoice.customer_id)

        # Resolve each distinct cylinder type once, even if it appears on
        # multiple lines.
        cylinder_type_names: dict[uuid.UUID, str] = {}
        for line in invoice.lines:
            if line.cylinder_type_id not in cylinder_type_names:
                cylinder_type = await self._cylinder_type_repo.get(line.cylinder_type_id)
                fallback = f"Cylinder Type {str(line.cylinder_type_id)[:8]}"
                name = cylinder_type.name if cylinder_type else fallback
                cylinder_type_names[line.cylinder_type_id] = name

        # Assemble the fully-resolved print payload
        payload = InvoicePrintPayload(
            # Legacy fallback only for pre-backfill rows still missing the
            # persisted number — every invoice generated after this
            # migration series always has one.
            invoice_number=invoice.invoice_number or f"INV-{str(invoice.id)[:8].upper()}",
            tenant_header=TenantHeader(
                agency_name="LPG Agency",  # TODO: resolve from tenant config
            ),
            customer=customer_info,
            line_items=[
                PrintLineItem(
                    description=cylinder_type_names[line.cylinder_type_id],
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
            # Wrapped as a print-ready HTML page (Print/Close controls,
            # receipt-styled `<pre>`) rather than raw `text/plain` — see
            # `render_invoice_thermal_html`. The underlying plain-text
            # layout (`render_invoice_thermal`) stays the source of truth
            # for a future raw ESC/POS byte-stream path to a real printer.
            thermal_bytes = self._engine.render_invoice_thermal_html(payload)
            key = f"print-jobs/{invoice.id}.html"
            content_type = "text/html"
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

    @staticmethod
    def _build_customer_info(customer: Customer | None, customer_id: uuid.UUID) -> CustomerInfo:
        if customer is None:
            return CustomerInfo(name=f"Customer {str(customer_id)[:8]}")

        address = next((a for a in customer.addresses if a.is_primary), None) or next(
            iter(customer.addresses), None
        )
        address_line = ""
        if address is not None:
            parts = [address.line_1, address.line_2, address.city, address.state, address.pincode]
            address_line = ", ".join(p for p in parts if p)

        return CustomerInfo(
            name=customer.full_name,
            consumer_number=customer.consumer_number or "",
            address=address_line,
            phone=customer.phone_number,
        )
