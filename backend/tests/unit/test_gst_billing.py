"""Unit tests for GST tax invoicing, payments and cash review (QA DA-06,
DA-07, DA-12, DA-13, DA-33, DO-14). No database required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.application.accounting.gst import (
    GstNotConfiguredError,
    resolve_gst_classes,
    resolve_place_of_supply,
)
from lpg.application.accounting.use_cases import (
    GenerateInvoiceForOrderUseCase,
    RecordPaymentCommand,
    RecordPaymentUseCase,
)
from lpg.application.common.errors import ValidationError
from lpg.application.reporting.ports import GstInvoiceLineRecord
from lpg.application.reporting.queries.get_gstr1_report import (
    GetGstr1ReportQuery,
    GetGstr1ReportUseCase,
)
from lpg.domain.accounting.cash_handover import CashHandover, CashHandoverReview
from lpg.domain.accounting.invoice import Invoice, InvoiceLine, PlaceOfSupply
from lpg.domain.common.base import InvariantViolation
from lpg.domain.common.gst import (
    GstSplit,
    compute_line_tax,
    gstin_check_character,
    normalize_gstin,
    normalize_hsn_code,
    state_code_for,
    validate_gst_rate,
)
from lpg.domain.order.order import OrderLine

NOW = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)

# ---------------------------------------------------------------------------
# Domain: GST primitives
# ---------------------------------------------------------------------------


class TestGstPrimitives:
    @pytest.mark.parametrize("gstin", ["27AAACT2727Q1ZW", "27aaacr5055k1z7 "])
    def test_accepts_valid_gstin(self, gstin: str) -> None:
        assert normalize_gstin(gstin) == gstin.strip().upper()

    def test_rejects_gstin_with_wrong_check_digit(self) -> None:
        with pytest.raises(InvariantViolation, match="check digit"):
            normalize_gstin("27AAACT2727Q1ZX")

    def test_rejects_gstin_with_unknown_state(self) -> None:
        body = "99AAACT2727Q1Z"
        with pytest.raises(InvariantViolation, match="state code"):
            normalize_gstin(body + gstin_check_character(body))

    @pytest.mark.parametrize("code", ["2711", "271119", "27111900"])
    def test_accepts_hsn_of_4_6_or_8_digits(self, code: str) -> None:
        assert normalize_hsn_code(code) == code

    @pytest.mark.parametrize("code", ["271", "27111", "2711190A"])
    def test_rejects_malformed_hsn(self, code: str) -> None:
        with pytest.raises(InvariantViolation):
            normalize_hsn_code(code)

    @pytest.mark.parametrize("rate", [Decimal("-1"), Decimal("28.01")])
    def test_rejects_rate_outside_slabs(self, rate: Decimal) -> None:
        with pytest.raises(InvariantViolation):
            validate_gst_rate(rate)

    @pytest.mark.parametrize(
        ("given", "expected"),
        [("36", "36"), ("Telangana", "36"), ("tamil nadu", "33"), ("Atlantis", None)],
    )
    def test_state_code_from_code_or_name(self, given: str, expected: str | None) -> None:
        assert state_code_for(given) == expected

    def test_line_tax_rounds_half_up_to_paise(self) -> None:
        # 905.50 x 5% = 45.275 -> 45.28
        assert compute_line_tax(Decimal("905.50"), Decimal("5")) == Decimal("45.28")

    def test_intra_state_split_gives_sgst_the_odd_paisa(self) -> None:
        split = GstSplit.of(Decimal("45.27"), inter_state=False)
        assert (split.cgst, split.sgst, split.igst) == (
            Decimal("22.64"),
            Decimal("22.63"),
            Decimal("0.00"),
        )
        assert split.cgst + split.sgst == Decimal("45.27")

    def test_inter_state_is_all_igst(self) -> None:
        split = GstSplit.of(Decimal("45.27"), inter_state=True)
        assert (split.cgst, split.sgst, split.igst) == (
            Decimal("0.00"),
            Decimal("0.00"),
            Decimal("45.27"),
        )


# ---------------------------------------------------------------------------
# Domain: invoice
# ---------------------------------------------------------------------------


def _line(subtotal: str, tax: str, *, kind: str = "supply") -> InvoiceLine:
    return InvoiceLine(
        line_id=uuid.uuid4(),
        cylinder_type_id=uuid.uuid4(),
        quantity=1,
        unit_price=Decimal(subtotal),
        subtotal=Decimal(subtotal),
        tax_amount=Decimal(tax),
        total_amount=Decimal(subtotal) + Decimal(tax),
        hsn_code="27111900",
        gst_rate_percent=Decimal("5"),
        kind=kind,
    )


def _invoice(*, supplier: str | None, destination: str | None) -> Invoice:
    return Invoice.generate_for_delivered_order(
        invoice_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        invoice_number="INV-2026-000001",
        customer_id=uuid.uuid4(),
        order_id=uuid.uuid4(),
        delivered_at=NOW,
        lines=[_line("100.00", "5.01"), _line("200.00", "10.00")],
        supply=PlaceOfSupply(
            supplier_state_code=supplier,
            place_of_supply_state_code=destination,
            customer_gstin=None,
        ),
    )


class TestInvoiceTaxSplit:
    def test_same_state_is_cgst_and_sgst(self) -> None:
        invoice = _invoice(supplier="36", destination="36")
        split = invoice.tax_split()
        assert not invoice.is_inter_state
        assert split.igst == Decimal("0.00")
        assert split.cgst + split.sgst == invoice.tax_amount

    def test_other_state_is_igst(self) -> None:
        invoice = _invoice(supplier="36", destination="27")
        assert invoice.is_inter_state
        assert invoice.tax_split().igst == invoice.tax_amount

    def test_balance_due_drops_with_payments(self) -> None:
        invoice = _invoice(supplier="36", destination="36")
        invoice.record_payment(
            payment_id=uuid.uuid4(),
            method="cheque",
            amount=Decimal("100.00"),
            collected_by=uuid.uuid4(),
            collected_at=NOW,
            reference="000123",
        )
        assert invoice.status == "partially_paid"
        assert invoice.balance_due == invoice.total_amount - Decimal("100.00")
        assert invoice.payments[0].reference == "000123"


# ---------------------------------------------------------------------------
# Application: GST resolution
# ---------------------------------------------------------------------------


def _cylinder_repo(rates: dict[uuid.UUID, Decimal | None]) -> MagicMock:
    def _get(cylinder_type_id: uuid.UUID) -> MagicMock:
        cylinder = MagicMock(hsn_code="27111900", gst_rate_percent=rates[cylinder_type_id])
        cylinder.name = f"type-{rates[cylinder_type_id]}"
        return cylinder

    repo = MagicMock()
    repo.get = AsyncMock(side_effect=_get)
    return repo


def _empty_config_repo() -> MagicMock:
    repo = MagicMock()
    repo.list_for_tenant_and_key = AsyncMock(return_value=[])
    return repo


class TestResolveGst:
    async def test_cylinder_type_rate_wins(self) -> None:
        domestic, commercial = uuid.uuid4(), uuid.uuid4()
        classes = await resolve_gst_classes(
            cylinder_type_repository=_cylinder_repo(
                {domestic: Decimal("5"), commercial: Decimal("18")}
            ),
            tenant_config_repository=_empty_config_repo(),
            tenant_id=uuid.uuid4(),
            cylinder_type_ids=[domestic, commercial],
            at=NOW,
        )
        assert classes[domestic].rate_percent == Decimal("5")
        assert classes[commercial].rate_percent == Decimal("18")

    async def test_unconfigured_type_blocks_with_its_name(self) -> None:
        unknown = uuid.uuid4()
        with pytest.raises(GstNotConfiguredError, match="type-None"):
            await resolve_gst_classes(
                cylinder_type_repository=_cylinder_repo({unknown: None}),
                tenant_config_repository=_empty_config_repo(),
                tenant_id=uuid.uuid4(),
                cylinder_type_ids=[unknown],
                at=NOW,
            )

    async def test_place_of_supply_defaults_to_agency_state(self) -> None:
        tenant = MagicMock()
        tenant.business_profile = MagicMock(state_code="36")
        repo = MagicMock(get=AsyncMock(return_value=tenant))
        customer = MagicMock(addresses=[], gstin=None)
        supply = await resolve_place_of_supply(
            tenant_repository=repo, tenant_id=uuid.uuid4(), customer=customer
        )
        assert supply.supplier_state_code == "36"
        assert supply.place_of_supply_state_code == "36"
        assert not supply.is_inter_state

    async def test_place_of_supply_follows_customer_gstin(self) -> None:
        tenant = MagicMock()
        tenant.business_profile = MagicMock(state_code="36")
        repo = MagicMock(get=AsyncMock(return_value=tenant))
        customer = MagicMock(addresses=[], gstin="27aaact2727q1zw")
        supply = await resolve_place_of_supply(
            tenant_repository=repo, tenant_id=uuid.uuid4(), customer=customer
        )
        assert supply.customer_gstin == "27AAACT2727Q1ZW"
        assert supply.place_of_supply_state_code == "27"
        assert supply.is_inter_state


# ---------------------------------------------------------------------------
# Application: cancellation charge (DO-14)
# ---------------------------------------------------------------------------


class TestCancellationChargeInvoice:
    async def test_charge_is_taxed_at_the_highest_line_rate(self) -> None:
        domestic, commercial = uuid.uuid4(), uuid.uuid4()
        order = MagicMock()
        order.id = uuid.uuid4()
        order.customer_id = uuid.uuid4()
        order.order_number = "ORD-1"
        order.lines = [
            OrderLine(
                line_id=uuid.uuid4(),
                cylinder_type_id=type_id,
                quantity_ordered=1,
                quantity_delivered=0,
                unit_price=Decimal("900.00"),
            )
            for type_id in (domestic, commercial)
        ]
        invoice_repo = MagicMock(get_by_order_id=AsyncMock(return_value=None), add=AsyncMock())
        sequence = MagicMock(next=AsyncMock(return_value="INV-2026-000002"))
        use_case = GenerateInvoiceForOrderUseCase(
            invoice_repository=invoice_repo,
            order_repository=MagicMock(get_by_id=AsyncMock(return_value=order)),
            tenant_config_repository=_empty_config_repo(),
            customer_repository=MagicMock(get_by_id=AsyncMock(return_value=None)),
            invoice_number_sequence=sequence,
            cylinder_type_repository=_cylinder_repo(
                {domestic: Decimal("5"), commercial: Decimal("18")}
            ),
            tenant_repository=MagicMock(get=AsyncMock(return_value=None)),
        )

        invoice = await use_case.execute_cancellation_charge(
            uuid.uuid4(), order.id, Decimal("50"), NOW
        )

        assert invoice is not None
        (line,) = invoice.lines
        assert line.kind == "cancellation_charge"
        assert line.cylinder_type_id == commercial
        assert line.subtotal == Decimal("50.00")
        assert line.tax_amount == Decimal("9.00")
        invoice_repo.add.assert_awaited_once()

    async def test_no_charge_no_invoice(self) -> None:
        invoice_repo = MagicMock(get_by_order_id=AsyncMock(return_value=None), add=AsyncMock())
        use_case = GenerateInvoiceForOrderUseCase(
            invoice_repository=invoice_repo,
            order_repository=MagicMock(),
            tenant_config_repository=_empty_config_repo(),
            customer_repository=MagicMock(),
            invoice_number_sequence=MagicMock(),
            cylinder_type_repository=MagicMock(),
            tenant_repository=MagicMock(),
        )
        result = await use_case.execute_cancellation_charge(
            uuid.uuid4(), uuid.uuid4(), Decimal("0"), NOW
        )
        assert result is None
        invoice_repo.add.assert_not_called()


# ---------------------------------------------------------------------------
# Application: record payment (DA-07)
# ---------------------------------------------------------------------------


def _payment_command(
    method: str, amount: str = "10.00", reference: str | None = None
) -> RecordPaymentCommand:
    return RecordPaymentCommand(
        invoice_id=uuid.uuid4(),
        method=method,
        amount=Decimal(amount),
        collected_by=uuid.uuid4(),
        collected_at=NOW,
        reference=reference,
    )


class TestRecordPayment:
    def _use_case(self, invoice: Invoice | None) -> tuple[RecordPaymentUseCase, MagicMock]:
        repo = MagicMock(get_by_id=AsyncMock(return_value=invoice), save=AsyncMock())
        uow = MagicMock(commit=AsyncMock())
        return RecordPaymentUseCase(repo, uow), repo

    async def test_cheque_needs_a_reference(self) -> None:
        use_case, _ = self._use_case(_invoice(supplier="36", destination="36"))
        with pytest.raises(ValidationError) as raised:
            await use_case.execute(_payment_command("cheque"))
        assert "reference" in raised.value.errors

    async def test_gateway_and_credit_are_not_staff_methods(self) -> None:
        use_case, _ = self._use_case(_invoice(supplier="36", destination="36"))
        for method in ("online_gateway", "credit"):
            with pytest.raises(ValidationError):
                await use_case.execute(_payment_command(method))

    async def test_overpayment_is_refused(self) -> None:
        invoice = _invoice(supplier="36", destination="36")
        use_case, repo = self._use_case(invoice)
        with pytest.raises(ValidationError) as raised:
            await use_case.execute(_payment_command("cash", amount="10000.00"))
        assert "amount" in raised.value.errors
        repo.save.assert_not_called()

    async def test_bank_transfer_with_utr_is_recorded(self) -> None:
        invoice = _invoice(supplier="36", destination="36")
        use_case, repo = self._use_case(invoice)
        await use_case.execute(_payment_command("bank_transfer", reference="UTR123"))
        repo.save.assert_awaited_once()
        assert invoice.payments[-1].reference == "UTR123"


# ---------------------------------------------------------------------------
# Domain: cash handover review (DA-33)
# ---------------------------------------------------------------------------


def _handover(*, expected: str, actual: str, declared_by: uuid.UUID) -> CashHandover:
    return CashHandover.declare(
        cash_handover_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        driver_id=uuid.uuid4(),
        route_id=uuid.uuid4(),
        expected_amount=Decimal(expected),
        actual_amount=Decimal(actual),
        declared_by=declared_by,
        handover_number="CSH000001",
    )


class TestCashHandoverReview:
    def test_accepts_a_balanced_handover(self) -> None:
        handover = _handover(expected="500", actual="500", declared_by=uuid.uuid4())
        review = CashHandoverReview.record(
            review_id=uuid.uuid4(),
            handover=handover,
            outcome="accepted",
            note=None,
            reviewed_by=uuid.uuid4(),
        )
        assert review.cash_handover_id == handover.id

    def test_short_handover_needs_a_note_to_accept(self) -> None:
        handover = _handover(expected="500", actual="450", declared_by=uuid.uuid4())
        with pytest.raises(InvariantViolation, match="short"):
            CashHandoverReview.record(
                review_id=uuid.uuid4(),
                handover=handover,
                outcome="accepted",
                note="  ",
                reviewed_by=uuid.uuid4(),
            )

    def test_dispute_needs_a_note(self) -> None:
        handover = _handover(expected="500", actual="500", declared_by=uuid.uuid4())
        with pytest.raises(InvariantViolation):
            CashHandoverReview.record(
                review_id=uuid.uuid4(),
                handover=handover,
                outcome="disputed",
                note=None,
                reviewed_by=uuid.uuid4(),
            )

    def test_declarer_cannot_verify_own_handover(self) -> None:
        declarer = uuid.uuid4()
        handover = _handover(expected="500", actual="500", declared_by=declarer)
        with pytest.raises(InvariantViolation, match="cannot also verify"):
            CashHandoverReview.record(
                review_id=uuid.uuid4(),
                handover=handover,
                outcome="accepted",
                note=None,
                reviewed_by=declarer,
            )


# ---------------------------------------------------------------------------
# Application: GSTR-1 grouping (DA-12)
# ---------------------------------------------------------------------------


def _gst_line(
    *,
    invoice_id: uuid.UUID,
    rate: str | None,
    taxable: str,
    tax: str,
    gstin: str | None = None,
    destination: str = "36",
    invoice_total: str = "1000",
) -> GstInvoiceLineRecord:
    return GstInvoiceLineRecord(
        invoice_id=invoice_id,
        invoice_number="INV-1",
        issued_at=NOW,
        customer_name="Asha",
        customer_gstin=gstin,
        supplier_state_code="36",
        place_of_supply_state_code=destination,
        invoice_total=Decimal(invoice_total),
        hsn_code="27111900",
        gst_rate_percent=Decimal(rate) if rate is not None else None,
        quantity=1,
        taxable_value=Decimal(taxable),
        tax_amount=Decimal(tax),
    )


class TestGstr1Report:
    async def test_groups_b2b_b2cl_b2cs_and_hsn(self) -> None:
        b2b, b2cs_a, b2cs_b, b2cl = (uuid.uuid4() for _ in range(4))
        lines = [
            _gst_line(
                invoice_id=b2b, rate="18", taxable="1000", tax="180", gstin="36AAACT2727Q1ZW"
            ),
            _gst_line(invoice_id=b2cs_a, rate="5", taxable="900", tax="45"),
            # Legacy line without a stored rate: derived from its own tax.
            _gst_line(invoice_id=b2cs_b, rate=None, taxable="100", tax="5"),
            _gst_line(
                invoice_id=b2cl,
                rate="18",
                taxable="200000",
                tax="36000",
                destination="27",
                invoice_total="236000",
            ),
        ]
        repo = MagicMock(get_gst_invoice_lines=AsyncMock(return_value=lines))

        report = await GetGstr1ReportUseCase(repo).execute(
            GetGstr1ReportQuery(
                tenant_id=uuid.uuid4(), start_date=date(2026, 10, 1), end_date=date(2026, 10, 31)
            )
        )

        assert report.invoice_count == 4
        assert [row.invoice_id for row in report.b2b] == [b2b]
        assert [row.invoice_id for row in report.b2cl] == [b2cl]
        assert report.b2cl[0].totals.igst == Decimal("36000")
        (b2cs_row,) = report.b2cs
        assert b2cs_row.rate_percent == Decimal("5")
        assert b2cs_row.totals.taxable_value == Decimal("1000")
        assert b2cs_row.totals.cgst + b2cs_row.totals.sgst == Decimal("50")
        assert {(row.hsn_code, row.rate_percent) for row in report.hsn} == {
            ("27111900", Decimal("5")),
            ("27111900", Decimal("18")),
        }
        assert report.totals.total_tax == Decimal("36230")
