"""GSTR-1 style outward-supply summary for a period (DA-12).

Groups the period's invoice lines the way the return asks for them:

- **B2B** (table 4A) — one row per invoice and rate, for customers with a
  GSTIN;
- **B2C large** (table 5) — inter-state invoices to unregistered customers
  above ₹1,00,000, one row per invoice and rate;
- **B2C small** (table 7) — everything else to unregistered customers,
  summed by place of supply and rate;
- **HSN summary** (table 12) — by HSN code and rate.

Amounts are taken from the invoices as issued; nothing is recomputed. A
line issued before GST was configured per cylinder type has no stored
rate, so its rate is derived from its own tax and taxable value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from lpg.application.reporting.queries.get_daily_sales import check_report_range
from lpg.domain.common.gst import GstSplit, state_name_for, to_cents

if TYPE_CHECKING:
    import uuid
    from datetime import date, datetime

    from lpg.application.reporting.ports import GstInvoiceLineRecord, ReportingRepository

#: GSTR-1 table 5 threshold for an inter-state B2C invoice to be reported
#: individually (₹1 lakh since August 2024).
B2CL_INVOICE_VALUE_THRESHOLD = Decimal("100000")

_ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class GetGstr1ReportQuery:
    tenant_id: uuid.UUID
    start_date: date
    end_date: date


@dataclass(slots=True)
class TaxTotals:
    taxable_value: Decimal = _ZERO
    cgst: Decimal = _ZERO
    sgst: Decimal = _ZERO
    igst: Decimal = _ZERO

    @property
    def total_tax(self) -> Decimal:
        return self.cgst + self.sgst + self.igst

    def add(self, line: GstInvoiceLineRecord) -> None:
        split = GstSplit.of(line.tax_amount, inter_state=_is_inter_state(line))
        self.taxable_value += line.taxable_value
        self.cgst += split.cgst
        self.sgst += split.sgst
        self.igst += split.igst


@dataclass(slots=True)
class Gstr1InvoiceRow:
    """A B2B or B2C-large row: one invoice at one rate."""

    invoice_id: uuid.UUID
    invoice_number: str | None
    invoice_date: datetime
    customer_name: str
    customer_gstin: str | None
    invoice_value: Decimal
    place_of_supply: str
    rate_percent: Decimal
    totals: TaxTotals = field(default_factory=TaxTotals)


@dataclass(slots=True)
class Gstr1B2csRow:
    place_of_supply: str
    rate_percent: Decimal
    totals: TaxTotals = field(default_factory=TaxTotals)


@dataclass(slots=True)
class Gstr1HsnRow:
    hsn_code: str
    rate_percent: Decimal
    quantity: int = 0
    totals: TaxTotals = field(default_factory=TaxTotals)


@dataclass(frozen=True, slots=True)
class Gstr1Report:
    start_date: date
    end_date: date
    invoice_count: int
    b2b: list[Gstr1InvoiceRow]
    b2cl: list[Gstr1InvoiceRow]
    b2cs: list[Gstr1B2csRow]
    hsn: list[Gstr1HsnRow]
    totals: TaxTotals


def _is_inter_state(line: GstInvoiceLineRecord) -> bool:
    return (
        line.supplier_state_code is not None
        and line.place_of_supply_state_code is not None
        and line.supplier_state_code != line.place_of_supply_state_code
    )


def _rate_of(line: GstInvoiceLineRecord) -> Decimal:
    if line.gst_rate_percent is not None:
        return line.gst_rate_percent
    if line.taxable_value == 0:
        return _ZERO
    return to_cents(line.tax_amount * 100 / line.taxable_value)


def _place_of_supply(line: GstInvoiceLineRecord) -> str:
    code = line.place_of_supply_state_code
    name = state_name_for(code)
    return f"{code}-{name}" if code and name else "Not recorded"


class GetGstr1ReportUseCase:
    def __init__(self, reporting_repository: ReportingRepository) -> None:
        self._reporting_repository = reporting_repository

    async def execute(self, query: GetGstr1ReportQuery) -> Gstr1Report:
        check_report_range(query.start_date, query.end_date)
        lines = await self._reporting_repository.get_gst_invoice_lines(
            query.tenant_id, query.start_date, query.end_date
        )

        invoice_rows: dict[tuple[uuid.UUID, Decimal], Gstr1InvoiceRow] = {}
        b2cs: dict[tuple[str, Decimal], Gstr1B2csRow] = {}
        hsn: dict[tuple[str, Decimal], Gstr1HsnRow] = {}
        totals = TaxTotals()
        b2cl_invoices: set[uuid.UUID] = set()

        for line in lines:
            rate = _rate_of(line)
            place = _place_of_supply(line)
            totals.add(line)

            hsn_row = hsn.setdefault(
                (line.hsn_code or "Not set", rate),
                Gstr1HsnRow(hsn_code=line.hsn_code or "Not set", rate_percent=rate),
            )
            hsn_row.quantity += line.quantity
            hsn_row.totals.add(line)

            is_b2cl = (
                line.customer_gstin is None
                and _is_inter_state(line)
                and line.invoice_total > B2CL_INVOICE_VALUE_THRESHOLD
            )
            if line.customer_gstin is not None or is_b2cl:
                if is_b2cl:
                    b2cl_invoices.add(line.invoice_id)
                row = invoice_rows.setdefault(
                    (line.invoice_id, rate),
                    Gstr1InvoiceRow(
                        invoice_id=line.invoice_id,
                        invoice_number=line.invoice_number,
                        invoice_date=line.issued_at,
                        customer_name=line.customer_name,
                        customer_gstin=line.customer_gstin,
                        invoice_value=line.invoice_total,
                        place_of_supply=place,
                        rate_percent=rate,
                    ),
                )
                row.totals.add(line)
            else:
                b2cs_row = b2cs.setdefault(
                    (place, rate), Gstr1B2csRow(place_of_supply=place, rate_percent=rate)
                )
                b2cs_row.totals.add(line)

        by_invoice = sorted(
            invoice_rows.values(), key=lambda row: (row.invoice_date, row.invoice_number or "")
        )
        return Gstr1Report(
            start_date=query.start_date,
            end_date=query.end_date,
            invoice_count=len({line.invoice_id for line in lines}),
            b2b=[row for row in by_invoice if row.invoice_id not in b2cl_invoices],
            b2cl=[row for row in by_invoice if row.invoice_id in b2cl_invoices],
            b2cs=sorted(b2cs.values(), key=lambda row: (row.place_of_supply, row.rate_percent)),
            hsn=sorted(hsn.values(), key=lambda row: (row.hsn_code, row.rate_percent)),
            totals=totals,
        )
