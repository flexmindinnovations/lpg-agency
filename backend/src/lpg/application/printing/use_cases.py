from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from lpg.application.accounting.payment_profile import (
    GetPaymentProfileUseCase,
    build_upi_uri,
)
from lpg.application.printing.amount_in_words import rupees_in_words
from lpg.application.printing.models import (
    CustomerInfo,
    InvoicePrintPayload,
    PaymentInfo,
    PrintLineItem,
    TenantHeader,
)
from lpg.config.logging import get_logger
from lpg.domain.common.gst import GstSplit, state_name_for

if TYPE_CHECKING:
    import uuid

    from lpg.application.accounting.ports import InvoiceRepository
    from lpg.application.common.ports import FileStorage
    from lpg.application.customer.ports import CustomerRepository
    from lpg.application.printing.ports import PrintingEngine
    from lpg.application.tenant.ports import (
        CylinderTypeRepository,
        TenantConfigurationRepository,
        TenantRepository,
    )
    from lpg.domain.accounting.invoice import Invoice
    from lpg.domain.customer.customer import Customer
    from lpg.domain.tenant.tenant import Tenant

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


@dataclass(frozen=True)
class RenderedDocument:
    """A rendered document, ready to stream to the caller."""

    content: bytes
    content_type: str
    filename: str
    key: str


class DocumentNotFoundError(Exception):
    """The document to print does not exist (or is not visible to the caller)."""


class UnsupportedDocumentError(Exception):
    """The requested document type or format cannot be printed."""


class StorageNotConfiguredError(Exception):
    """A stored print job was requested but no file storage is configured."""


class GeneratePrintJobUseCase:
    def __init__(
        self,
        *,
        printing_engine: PrintingEngine,
        invoice_repository: InvoiceRepository,
        customer_repository: CustomerRepository,
        cylinder_type_repository: CylinderTypeRepository,
        tenant_repository: TenantRepository,
        storage: FileStorage | None,
        tenant_config_repository: TenantConfigurationRepository | None = None,
    ) -> None:
        self._tenant_config_repo = tenant_config_repository
        self._engine = printing_engine
        self._invoice_repo = invoice_repository
        self._customer_repo = customer_repository
        self._cylinder_type_repo = cylinder_type_repository
        self._tenant_repo = tenant_repository
        self._storage = storage

    async def execute(self, command: PrintJobCommand) -> PrintJobResult:
        """Render, store in file storage and return a short-lived download URL."""
        if self._storage is None:
            msg = "File storage is not configured on this server."
            raise StorageNotConfiguredError(msg)
        rendered = await self.render(command)
        await self._storage.upload(
            rendered.key, rendered.content, content_type=rendered.content_type
        )
        download_url = await self._storage.url(rendered.key, expires_seconds=300)
        _logger.info(
            "print_job_completed",
            document_type=command.document_type,
            document_id=str(command.document_id),
            format=command.output_format,
        )
        return PrintJobResult(
            download_url=download_url,
            output_format=command.output_format.value,
            content_type=rendered.content_type,
        )

    async def render(self, command: PrintJobCommand) -> RenderedDocument:
        """Render the document in memory. Needs no file storage."""
        if command.document_type == "invoice":
            return await self._render_invoice(command)
        msg = f"Unsupported document type: {command.document_type}"
        raise UnsupportedDocumentError(msg)

    async def _render_invoice(self, command: PrintJobCommand) -> RenderedDocument:
        invoice = await self._invoice_repo.get_by_id(command.document_id)
        if invoice is None:
            msg = "Invoice not found"
            raise DocumentNotFoundError(msg)

        customer = await self._customer_repo.get_by_id(invoice.customer_id)
        customer_info = self._build_customer_info(
            customer, invoice.customer_id, gstin=invoice.customer_gstin
        )
        tenant = await self._tenant_repo.get(invoice.tenant_id)
        split = invoice.tax_split()
        payload = InvoicePrintPayload(
            invoice_number=invoice.invoice_number or "Not numbered",
            tenant_header=self._build_tenant_header(tenant),
            customer=customer_info,
            line_items=await self._build_line_items(invoice),
            subtotal=invoice.subtotal,
            cgst_amount=split.cgst,
            sgst_amount=split.sgst,
            igst_amount=split.igst,
            tax_amount=invoice.tax_amount,
            total_amount=invoice.total_amount,
            total_in_words=rupees_in_words(invoice.total_amount),
            payment_info=await self._build_payment_info(invoice),
            place_of_supply=self._place_of_supply(invoice.place_of_supply_state_code),
            is_inter_state=invoice.is_inter_state,
            amount_paid=invoice.amount_paid,
            balance_due=invoice.balance_due,
            payment_status=invoice.status,
            issued_at=invoice.issued_at,
            qr_code_data=f"lpg-invoice:{invoice.id}",
        )
        stem = invoice.invoice_number or str(invoice.id)

        if command.output_format == PrintFormat.PDF:
            return RenderedDocument(
                content=self._engine.render_invoice_pdf(payload),
                content_type="application/pdf",
                filename=f"{stem}.pdf",
                key=f"print-jobs/{invoice.id}.pdf",
            )
        if command.output_format == PrintFormat.THERMAL:
            # Wrapped as a print-ready HTML page (Print/Close controls,
            # receipt-styled `<pre>`) rather than raw `text/plain` - see
            # `render_invoice_thermal_html`. The underlying plain-text
            # layout (`render_invoice_thermal`) stays the source of truth
            # for a future raw ESC/POS byte-stream path to a real printer.
            return RenderedDocument(
                content=self._engine.render_invoice_thermal_html(payload),
                content_type="text/html; charset=utf-8",
                filename=f"{stem}.html",
                key=f"print-jobs/{invoice.id}.html",
            )
        msg = f"Unsupported format: {command.output_format}"  # type: ignore[unreachable]
        raise UnsupportedDocumentError(msg)

    async def _build_payment_info(self, invoice: Invoice) -> PaymentInfo:
        if self._tenant_config_repo is None:
            return PaymentInfo()
        profile = await GetPaymentProfileUseCase(self._tenant_config_repo).execute(
            invoice.tenant_id
        )
        upi_uri = ""
        if (
            profile.has_upi
            and invoice.balance_due > 0
            and invoice.status
            in (
                "issued",
                "partially_paid",
            )
        ):
            label = invoice.invoice_number or str(invoice.id)
            upi_uri = build_upi_uri(
                profile,
                amount=invoice.balance_due,
                note=f"Invoice {label}",
                reference=label,
            )
        return PaymentInfo(
            account_holder=profile.account_holder,
            bank_name=profile.bank_name,
            account_number=profile.account_number,
            ifsc=profile.ifsc,
            branch=profile.branch,
            upi_id=profile.upi_id,
            upi_uri=upi_uri,
            footer_note=profile.invoice_footer_note,
        )

    async def _build_line_items(self, invoice: Invoice) -> list[PrintLineItem]:
        # Resolve each distinct cylinder type once, even if it appears on
        # multiple lines.
        names: dict[uuid.UUID, str] = {}
        for line in invoice.lines:
            if line.cylinder_type_id not in names:
                cylinder_type = await self._cylinder_type_repo.get(line.cylinder_type_id)
                names[line.cylinder_type_id] = (
                    cylinder_type.name if cylinder_type else "LPG cylinder"
                )
        items: list[PrintLineItem] = []
        for line in invoice.lines:
            split = GstSplit.of(line.tax_amount, inter_state=invoice.is_inter_state)
            name = names[line.cylinder_type_id]
            items.append(
                PrintLineItem(
                    description=f"{line.description} ({name})" if line.description else name,
                    hsn_code=line.hsn_code or "",
                    gst_rate_percent=line.gst_rate_percent,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    subtotal=line.subtotal,
                    cgst_amount=split.cgst,
                    sgst_amount=split.sgst,
                    igst_amount=split.igst,
                    tax_amount=line.tax_amount,
                    total_amount=line.total_amount,
                )
            )
        return items

    @staticmethod
    def _build_tenant_header(tenant: Tenant | None) -> TenantHeader:
        profile = tenant.business_profile if tenant is not None else None
        if profile is None:
            # Unconfigured agency: print what is known, never a made-up name.
            return TenantHeader(agency_name=tenant.name if tenant is not None else "")
        return TenantHeader(
            agency_name=profile.legal_name,
            address_line_1=profile.address_line_1,
            address_line_2=profile.address_line_2 or "",
            city=profile.city,
            state=profile.state_name,
            state_code=profile.state_code,
            pincode=profile.pincode,
            gstin=profile.gstin or "",
            phone=profile.phone or "",
        )

    @staticmethod
    def _place_of_supply(state_code: str | None) -> str:
        name = state_name_for(state_code)
        return f"{state_code}-{name}" if state_code and name else ""

    @staticmethod
    def _build_customer_info(
        customer: Customer | None, customer_id: uuid.UUID, *, gstin: str | None = None
    ) -> CustomerInfo:
        if customer is None:
            return CustomerInfo(name=f"Customer {str(customer_id)[:8]}", gstin=gstin or "")

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
            gstin=gstin or "",
        )
