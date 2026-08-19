"""Invoice Repository implementation."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lpg.application.accounting.ports import (
    CashHandoverRepository,
    CreditNoteRepository,
    InvoiceRepository,
)
from lpg.domain.accounting.credit_note import CreditNote
from lpg.domain.accounting.invoice import Invoice, InvoiceLine, Payment
from lpg.infrastructure.persistence.models.accounting import (
    CashHandoverModel,
    CreditNoteModel,
    InvoiceLineModel,
    InvoiceModel,
    PaymentModel,
)

if TYPE_CHECKING:
    from lpg.domain.accounting.cash_handover import CashHandover
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyInvoiceRepository(InvoiceRepository):
    """SQLAlchemy implementation of ``InvoiceRepository``."""

    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow
        self._session = uow.session

    def _to_domain(self, model: InvoiceModel) -> Invoice:
        invoice = Invoice(
            invoice_id=model.id,
            tenant_id=model.tenant_id,
            customer_id=model.customer_id,
            order_id=model.order_id,
            status=model.status,
            issued_at=model.issued_at,
            lines=[
                InvoiceLine(
                    line_id=line.id,
                    cylinder_type_id=line.cylinder_type_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    subtotal=line.subtotal,
                    tax_amount=line.tax_amount,
                    total_amount=line.total_amount,
                )
                for line in model.lines
            ],
            payments=[
                Payment(
                    payment_id=payment.id,
                    method=payment.method,
                    amount=payment.amount,
                    collected_by=payment.collected_by,
                    collected_at=payment.collected_at,
                )
                for payment in model.payments
            ],
            subtotal=model.subtotal,
            tax_amount=model.tax_amount,
            total_amount=model.total_amount,
        )
        # Register for event dispatch
        self._uow.register_aggregate(invoice)
        return invoice

    async def add(self, invoice: Invoice) -> None:
        model = InvoiceModel(
            id=invoice.id,
            tenant_id=invoice.tenant_id,
            customer_id=invoice.customer_id,
            order_id=invoice.order_id,
            status=invoice.status,
            issued_at=invoice.issued_at,
            subtotal=invoice.subtotal,
            tax_amount=invoice.tax_amount,
            total_amount=invoice.total_amount,
            lines=[
                InvoiceLineModel(
                    id=line.id,
                    cylinder_type_id=line.cylinder_type_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    subtotal=line.subtotal,
                    tax_amount=line.tax_amount,
                    total_amount=line.total_amount,
                )
                for line in invoice.lines
            ],
        )
        self._session.add(model)
        self._uow.register_aggregate(invoice)

    async def save(self, invoice: Invoice) -> None:
        """Update-only — `add()` handles the initial insert. Called after
        `get_by_id()` on the same in-memory object, which already
        registered it for event dispatch — do not re-register here, or
        `collect_events()` would walk it twice and double-dispatch every
        event (the exact class of bug R10 fixed for `Complaint`/
        `NotificationLog`, avoided here by construction).

        `session.get(..., options=...)` rather than a bare `session.get()`
        for the same reason `SqlAlchemyComplaintRepository.save()` now
        does: `AsyncSession`'s identity map holds objects weakly, so a
        bare `get()` could return a freshly-refetched instance with
        `.payments` unloaded, and a later bare attribute access on that
        would lazy-load outside any greenlet-bridged `await`.
        """
        model = await self._session.get(
            InvoiceModel, invoice.id, options=(selectinload(InvoiceModel.payments),)
        )
        if model is None:
            msg = f"Cannot save changes to invoice {invoice.id}: no existing row found."
            raise ValueError(msg)

        model.status = invoice.status

        existing_payment_ids = {payment.id for payment in model.payments}
        for domain_payment in invoice.payments:
            if domain_payment.id in existing_payment_ids:
                continue
            model.payments.append(
                PaymentModel(
                    id=domain_payment.id,
                    tenant_id=invoice.tenant_id,
                    invoice_id=invoice.id,
                    method=domain_payment.method,
                    amount=domain_payment.amount,
                    collected_by=domain_payment.collected_by,
                    collected_at=domain_payment.collected_at,
                )
            )

    async def get_by_id(self, invoice_id: uuid.UUID) -> Invoice | None:
        stmt = (
            select(InvoiceModel)
            .where(InvoiceModel.id == invoice_id)
            .options(selectinload(InvoiceModel.lines), selectinload(InvoiceModel.payments))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_domain(model)

    async def list_invoices(
        self,
        skip: int = 0,
        limit: int = 50,
        customer_id: uuid.UUID | None = None,
        order_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[Invoice]:
        stmt = select(InvoiceModel).where(
            InvoiceModel.tenant_id == self._uow._tenant_context.tenant_id
        )
        if customer_id:
            stmt = stmt.where(InvoiceModel.customer_id == customer_id)
        if order_id:
            stmt = stmt.where(InvoiceModel.order_id == order_id)
        if status:
            stmt = stmt.where(InvoiceModel.status == status)

        stmt = (
            stmt.order_by(InvoiceModel.issued_at.desc())
            .offset(skip)
            .limit(limit)
            .options(selectinload(InvoiceModel.lines), selectinload(InvoiceModel.payments))
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def count_invoices(
        self,
        customer_id: uuid.UUID | None = None,
        order_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> int:
        from sqlalchemy import func

        stmt = select(func.count(InvoiceModel.id)).where(
            InvoiceModel.tenant_id == self._uow._tenant_context.tenant_id
        )
        if customer_id:
            stmt = stmt.where(InvoiceModel.customer_id == customer_id)
        if order_id:
            stmt = stmt.where(InvoiceModel.order_id == order_id)
        if status:
            stmt = stmt.where(InvoiceModel.status == status)

        result = await self._session.execute(stmt)
        return result.scalar_one() or 0

    async def get_by_order_id(self, tenant_id: uuid.UUID, order_id: uuid.UUID) -> Invoice | None:
        stmt = (
            select(InvoiceModel)
            .where(
                InvoiceModel.tenant_id == tenant_id,
                InvoiceModel.order_id == order_id,
            )
            .options(selectinload(InvoiceModel.lines), selectinload(InvoiceModel.payments))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def get_outstanding_balance(self, customer_id: uuid.UUID) -> Decimal:
        from sqlalchemy import func

        stmt = select(func.coalesce(func.sum(InvoiceModel.total_amount), 0)).where(
            InvoiceModel.customer_id == customer_id,
            InvoiceModel.status == "issued",
        )
        result = await self._session.scalar(stmt)
        return Decimal(result) if result is not None else Decimal("0")


class SqlAlchemyCashHandoverRepository(CashHandoverRepository):
    """SQLAlchemy implementation of ``CashHandoverRepository``."""

    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow
        self._session = uow.session

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def add(self, handover: CashHandover) -> None:
        self._session.add(
            CashHandoverModel(
                id=handover.id,
                tenant_id=handover.tenant_id,
                driver_id=handover.driver_id,
                route_id=handover.route_id,
                expected_amount=handover.expected_amount,
                actual_amount=handover.actual_amount,
                declared_by=handover.declared_by,
                declared_at=handover.declared_at,
            )
        )
        self._uow.register_aggregate(handover)

    async def get_expected_cash_for_route(self, route_id: uuid.UUID) -> Decimal:
        from sqlalchemy import text

        # Raw SQL, not the ORM — this crosses into `delivery`/`orders`
        # schemas the same way `SqlAlchemyReportingRepository` does, rather
        # than importing those modules' ORM models into `accounting`.
        # Both `delivery.route_stop` and `orders.proof_of_delivery` carry
        # their own RLS policy, so tenant scoping is enforced there, not
        # restated here — same reasoning `get_by_id` above already relies on.
        stmt = text("""
            SELECT COALESCE(SUM(pod.amount_collected), 0)
            FROM delivery.route_stop rs
            JOIN orders.proof_of_delivery pod ON pod.order_id = rs.order_id
            WHERE rs.route_id = :route_id AND pod.payment_method = 'cash'
        """)
        result = await self._session.scalar(stmt, {"route_id": route_id})
        return Decimal(result) if result is not None else Decimal("0")


class SqlAlchemyCreditNoteRepository(CreditNoteRepository):
    """SQLAlchemy implementation of ``CreditNoteRepository``."""

    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow
        self._session = uow.session

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    def _to_domain(self, model: CreditNoteModel) -> CreditNote:
        credit_note = CreditNote(
            credit_note_id=model.id,
            tenant_id=model.tenant_id,
            invoice_id=model.invoice_id,
            amount=model.amount,
            reason=model.reason,
            requested_by=model.requested_by,
            requested_at=model.requested_at,
            approved_by=model.approved_by,
            approved_at=model.approved_at,
        )
        self._uow.register_aggregate(credit_note)
        return credit_note

    async def add(self, credit_note: CreditNote) -> None:
        self._session.add(
            CreditNoteModel(
                id=credit_note.id,
                tenant_id=credit_note.tenant_id,
                invoice_id=credit_note.invoice_id,
                amount=credit_note.amount,
                reason=credit_note.reason,
                requested_by=credit_note.requested_by,
                requested_at=credit_note.requested_at,
            )
        )
        self._uow.register_aggregate(credit_note)

    async def save(self, credit_note: CreditNote) -> None:
        """Persist the one mutation this aggregate ever undergoes —
        approval. Called after `get_by_id()` on the same in-memory object,
        which already registered it for event dispatch — do not
        re-register here (see `SqlAlchemyInvoiceRepository.save()`'s
        docstring for why that would double-dispatch every event).
        """
        model = await self._session.get(CreditNoteModel, credit_note.id)
        if model is None:
            msg = f"Cannot save changes to credit note {credit_note.id}: no existing row found."
            raise ValueError(msg)

        model.approved_by = credit_note.approved_by
        model.approved_at = credit_note.approved_at

    async def get_by_id(self, credit_note_id: uuid.UUID) -> CreditNote | None:
        stmt = select(CreditNoteModel).where(CreditNoteModel.id == credit_note_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)
