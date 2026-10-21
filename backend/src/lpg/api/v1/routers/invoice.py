"""API router for managing invoices."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query

from lpg.api.v1.dependencies.accounting import (
    get_credit_note_number_sequence,
    get_credit_note_repository,
    get_generate_invoice_use_case,
    get_invoice_repository,
    get_uninvoiced_order_reader,
)
from lpg.api.v1.dependencies.customer import get_customer_repository
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.invoice import (
    CreditNoteResponse,
    InvoiceLineResponse,
    InvoicePageResponse,
    InvoiceResponse,
    IssueInvoiceRequest,
    PaymentResponse,
    RecordPaymentRequest,
    RequestRefundRequest,
    UninvoicedOrderResponse,
)
from lpg.application.accounting.ports import (
    CreditNoteNumberSequence,
    CreditNoteRepository,
    InvoiceRepository,
    UninvoicedOrderReader,
)
from lpg.application.accounting.use_cases import (
    ApproveRefundCommand,
    ApproveRefundUseCase,
    GenerateInvoiceForOrderUseCase,
    GetInvoiceQuery,
    GetInvoiceUseCase,
    IssueInvoiceForOrderCommand,
    IssueInvoiceForOrderUseCase,
    ListCreditNotesQuery,
    ListCreditNotesUseCase,
    ListInvoicesQuery,
    ListInvoicesUseCase,
    ListUninvoicedOrdersUseCase,
    RecordPaymentCommand,
    RecordPaymentUseCase,
    RequestRefundCommand,
    RequestRefundUseCase,
    SendInvoiceToCustomerCommand,
    SendInvoiceToCustomerUseCase,
)
from lpg.application.common.ports import UnitOfWork
from lpg.application.customer.ports import CustomerRepository
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.domain.accounting.credit_note import CreditNote
from lpg.domain.accounting.invoice import Invoice
from lpg.domain.common.gst import GstSplit

router = APIRouter(prefix="/invoices", tags=["Invoices"])

_IST = ZoneInfo("Asia/Kolkata")


class _InvoiceScope:
    """Row-scoping for a `customer` principal, same shape and reasoning as
    `order.py`'s `_OrderScope`/`_resolve_scope` -- `invoices:read` is held
    broadly (staff *and* `customer`, for self-service), so a `customer`
    principal must additionally be forced onto their own `customer_id`
    rather than trusting whatever filter/path value was passed. `blocked`
    (no linked customer profile) yields an empty list / 404 downstream,
    never 403 -- matches `_require_own_driver_order`'s documented
    convention (OWASP API1: never let a caller distinguish "not yours"
    from "doesn't exist").
    """

    __slots__ = ("blocked", "customer_id")

    def __init__(self, *, customer_id: uuid.UUID | None = None, blocked: bool = False) -> None:
        self.customer_id = customer_id
        self.blocked = blocked


async def _resolve_scope(
    principal: AuthenticatedPrincipal,
    customer_repository: CustomerRepository,
) -> _InvoiceScope:
    if principal.role != "customer":
        return _InvoiceScope()
    if principal.user_id is None:
        return _InvoiceScope(blocked=True)
    own_customer = await customer_repository.get_by_identity_user_id(principal.user_id)
    if own_customer is None:
        return _InvoiceScope(blocked=True)
    return _InvoiceScope(customer_id=own_customer.id)


def _invoice_to_response(invoice: Invoice, customer_name: str | None = None) -> InvoiceResponse:
    # `Invoice`/`InvoiceLine` only expose `.id` (from `Entity`), while the
    # committed schema names these fields `invoice_id`/`line_id` — the
    # frontend's generated client and `feature-invoices.ts` already depend on
    # that naming, so the fix is here, not a schema rename. Built field-by-
    # field, matching `_order_to_response`'s convention.
    split = invoice.tax_split()
    lines: list[InvoiceLineResponse] = []
    for line in invoice.lines:
        line_split = GstSplit.of(line.tax_amount, inter_state=invoice.is_inter_state)
        lines.append(
            InvoiceLineResponse(
                line_id=line.id,
                cylinder_type_id=line.cylinder_type_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
                subtotal=line.subtotal,
                tax_amount=line.tax_amount,
                total_amount=line.total_amount,
                hsn_code=line.hsn_code,
                gst_rate_percent=line.gst_rate_percent,
                kind=line.kind,
                description=line.description,
                cgst_amount=line_split.cgst,
                sgst_amount=line_split.sgst,
                igst_amount=line_split.igst,
            )
        )
    return InvoiceResponse(
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        tenant_id=invoice.tenant_id,
        customer_id=invoice.customer_id,
        customer_consumer_number=invoice.customer_consumer_number,
        customer_name=customer_name,
        customer_gstin=invoice.customer_gstin,
        order_id=invoice.order_id,
        order_number=invoice.order_number,
        status=invoice.status,
        issued_at=invoice.issued_at,
        lines=lines,
        subtotal=invoice.subtotal,
        tax_amount=invoice.tax_amount,
        total_amount=invoice.total_amount,
        version=invoice.version,
        payments=[
            PaymentResponse(
                payment_id=payment.id,
                method=payment.method,
                amount=payment.amount,
                collected_by=payment.collected_by,
                collected_at=payment.collected_at,
                reference=payment.reference,
            )
            for payment in invoice.payments
        ],
        amount_paid=invoice.amount_paid,
        balance_due=invoice.balance_due,
        supplier_state_code=invoice.supplier_state_code,
        place_of_supply_state_code=invoice.place_of_supply_state_code,
        is_inter_state=invoice.is_inter_state,
        cgst_amount=split.cgst,
        sgst_amount=split.sgst,
        igst_amount=split.igst,
    )


async def _with_customer_name(invoice: Invoice, repository: InvoiceRepository) -> InvoiceResponse:
    names = await repository.customer_names({invoice.customer_id})
    return _invoice_to_response(invoice, names.get(invoice.customer_id))


def _day_start(day: date | None) -> datetime | None:
    """Midnight IST at the start of `day` — an Indian agency's business day."""
    return datetime.combine(day, time.min, tzinfo=_IST) if day is not None else None


@router.get(
    "",
    response_model=InvoicePageResponse,
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def list_invoices(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    customer_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    status: str | None = None,
    issued_from: Annotated[date | None, Query(description="First day, inclusive (IST)")] = None,
    issued_to: Annotated[date | None, Query(description="Last day, inclusive (IST)")] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> InvoicePageResponse:
    """List invoices, newest first. `search` matches the invoice, order and
    consumer numbers and the customer's name.
    """
    scope = await _resolve_scope(principal, customer_repository)
    if scope.blocked:
        return InvoicePageResponse(items=[], total=0, page=page, page_size=page_size)
    if scope.customer_id is not None:
        customer_id = scope.customer_id

    use_case = ListInvoicesUseCase(repository)
    skip = (page - 1) * page_size
    items, total = await use_case.execute(
        ListInvoicesQuery(
            skip=skip,
            limit=page_size,
            customer_id=customer_id,
            order_id=order_id,
            status=status,
            issued_from=_day_start(issued_from),
            issued_to=_day_start(issued_to + timedelta(days=1) if issued_to else None),
            search=search,
        )
    )

    names = await repository.customer_names({invoice.customer_id for invoice in items})
    return InvoicePageResponse(
        items=[_invoice_to_response(invoice, names.get(invoice.customer_id)) for invoice in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/uninvoiced-orders",
    response_model=list[UninvoicedOrderResponse],
    dependencies=[Depends(require_permission("invoices:issue"))],
)
async def list_uninvoiced_orders(
    reader: Annotated[UninvoicedOrderReader, Depends(get_uninvoiced_order_reader)],
) -> list[UninvoicedOrderResponse]:
    """Invoices on hold: delivered orders with no invoice, and approved
    cancellations whose charge was never billed — almost always because GST
    was not configured at the time (DA-06, DO-14).
    """
    entries = await ListUninvoicedOrdersUseCase(reader).execute()
    return [
        UninvoicedOrderResponse(
            order_id=entry.order_id,
            order_number=entry.order_number,
            customer_id=entry.customer_id,
            customer_name=entry.customer_name,
            status=entry.status,
            occurred_at=entry.occurred_at,
            order_total=entry.order_total,
            cancellation_charge=entry.cancellation_charge,
        )
        for entry in entries
    ]


@router.post(
    "",
    response_model=InvoiceResponse,
    status_code=201,
    dependencies=[Depends(require_permission("invoices:issue"))],
)
async def issue_invoice(
    request: IssueInvoiceRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    reader: Annotated[UninvoicedOrderReader, Depends(get_uninvoiced_order_reader)],
    generator: Annotated[GenerateInvoiceForOrderUseCase, Depends(get_generate_invoice_use_case)],
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> InvoiceResponse:
    """Issue a held invoice for a delivered order or a billed cancellation.
    Fails with `GST_NOT_CONFIGURED` (422) while a cylinder type on the
    order still has no GST rate.
    """
    invoice = await IssueInvoiceForOrderUseCase(reader, generator, unit_of_work).execute(
        IssueInvoiceForOrderCommand(
            tenant_id=principal.tenant_id,
            order_id=request.order_id,
            issued_at=datetime.now(UTC),
        )
    )
    return await _with_customer_name(invoice, repository)


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def get_invoice(
    invoice_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
) -> InvoiceResponse:
    """Get a specific invoice by ID."""
    scope = await _resolve_scope(principal, customer_repository)
    if scope.blocked:
        raise HTTPException(status_code=404, detail="Invoice not found")

    use_case = GetInvoiceUseCase(repository)
    invoice = await use_case.execute(GetInvoiceQuery(invoice_id=invoice_id))
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if scope.customer_id is not None and invoice.customer_id != scope.customer_id:
        # 404, not 403 — see `_InvoiceScope`'s docstring.
        raise HTTPException(status_code=404, detail="Invoice not found")
    return await _with_customer_name(invoice, repository)


@router.post(
    "/{invoice_id}/payments",
    response_model=InvoiceResponse,
    status_code=201,
    dependencies=[Depends(require_permission("invoices:record_payment"))],
)
async def record_payment(
    invoice_id: uuid.UUID,
    request: RecordPaymentRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> InvoiceResponse:
    """Record a payment received at the office against an invoice (R10,
    `PaymentCollected`, BR-18/D-11): cash, UPI, card, cheque or bank
    transfer, with its reference. Supports partial payments — `status` only
    reaches `paid` once cumulative payments equal `total_amount`; more than
    the balance due is refused.
    """
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    use_case = RecordPaymentUseCase(repository, unit_of_work)
    invoice = await use_case.execute(
        RecordPaymentCommand(
            invoice_id=invoice_id,
            method=request.method,
            amount=request.amount,
            collected_by=principal.user_id,
            collected_at=datetime.now(UTC),
            reference=request.reference,
        )
    )
    return await _with_customer_name(invoice, repository)


@router.post(
    "/{invoice_id}/send",
    response_model=InvoiceResponse,
    summary="Send an invoice to the customer",
    dependencies=[Depends(require_permission("invoices:issue"))],
)
async def send_invoice(
    invoice_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> InvoiceResponse:
    """Send an issued invoice to the customer by e-mail and push. Can be
    repeated (a reminder); a cancelled invoice is refused.
    """
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    use_case = SendInvoiceToCustomerUseCase(repository, unit_of_work)
    invoice = await use_case.execute(
        SendInvoiceToCustomerCommand(invoice_id=invoice_id, sent_by=principal.user_id)
    )
    return await _with_customer_name(invoice, repository)


def _credit_note_to_response(credit_note: CreditNote) -> CreditNoteResponse:
    return CreditNoteResponse.model_validate(credit_note)


@router.get(
    "/{invoice_id}/credit-notes",
    response_model=list[CreditNoteResponse],
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def list_credit_notes(
    invoice_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    credit_note_repository: Annotated[CreditNoteRepository, Depends(get_credit_note_repository)],
) -> list[CreditNoteResponse]:
    """Refunds requested and approved against this invoice (BR-20)."""
    scope = await _resolve_scope(principal, customer_repository)
    invoice = None if scope.blocked else await repository.get_by_id(invoice_id)
    if invoice is None or (
        scope.customer_id is not None and invoice.customer_id != scope.customer_id
    ):
        raise HTTPException(status_code=404, detail="Invoice not found")
    notes = await ListCreditNotesUseCase(credit_note_repository).execute(
        ListCreditNotesQuery(invoice_id=invoice_id)
    )
    return [_credit_note_to_response(note) for note in notes]


@router.post(
    "/{invoice_id}/refunds",
    response_model=CreditNoteResponse,
    status_code=201,
    dependencies=[Depends(require_permission("credit_notes:request"))],
)
async def request_refund(
    invoice_id: uuid.UUID,
    request: RequestRefundRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    credit_note_repository: Annotated[CreditNoteRepository, Depends(get_credit_note_repository)],
    invoice_repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    credit_note_number_sequence: Annotated[
        CreditNoteNumberSequence, Depends(get_credit_note_number_sequence)
    ],
) -> CreditNoteResponse:
    """Request a refund against an invoice (R10, BR-20). Not yet approved —
    `amount` cannot exceed the invoice's actual `amount_paid`.
    """
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    use_case = RequestRefundUseCase(
        credit_note_repository, invoice_repository, unit_of_work, credit_note_number_sequence
    )
    credit_note = await use_case.execute(
        RequestRefundCommand(
            invoice_id=invoice_id,
            amount=request.amount,
            reason=request.reason,
            requested_by=principal.user_id,
        )
    )
    return _credit_note_to_response(credit_note)


@router.post(
    "/{invoice_id}/refunds/{credit_note_id}/approve",
    response_model=CreditNoteResponse,
    dependencies=[Depends(require_permission("credit_notes:approve"))],
)
async def approve_refund(
    invoice_id: uuid.UUID,
    credit_note_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    credit_note_repository: Annotated[CreditNoteRepository, Depends(get_credit_note_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CreditNoteResponse:
    """Approve a previously-requested refund (R10, `RefundApproved`, BR-20).

    `invoice_id` is validated against the credit note's own `invoice_id` —
    a credit note requested against one invoice cannot be approved through
    a different invoice's nested URL.
    """
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    use_case = ApproveRefundUseCase(credit_note_repository, unit_of_work)
    credit_note = await use_case.execute(
        ApproveRefundCommand(
            invoice_id=invoice_id, credit_note_id=credit_note_id, approved_by=principal.user_id
        )
    )
    return _credit_note_to_response(credit_note)
