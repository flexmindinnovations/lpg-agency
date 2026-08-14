from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lpg.application.printing.models import InvoicePrintPayload


class PrintingEngine(ABC):
    """Port for the printing engine — infrastructure provides the concrete implementation."""

    @abstractmethod
    def render_invoice_pdf(self, payload: InvoicePrintPayload) -> bytes:
        """Render an invoice to PDF bytes."""

    @abstractmethod
    def render_invoice_thermal(self, payload: InvoicePrintPayload) -> bytes:
        """Render an invoice to thermal receipt bytes (plain text for now)."""

    @abstractmethod
    def generate_qr_code(self, data: str, *, size: int = 200) -> bytes:
        """Generate a QR code PNG image."""

    @abstractmethod
    def generate_barcode(self, data: str) -> bytes:
        """Generate a Code 128 barcode PNG image."""
