"""Invoice Repository implementation."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.orm import selectinload

from lpg.application.accounting.ports import (
    CashHandoverRegisterEntry,
    CashHandoverRepository,
    CreditNoteRepository,
    InvoiceRepository,
    OnlinePaymentRepository,
    UninvoicedOrder,
)
from lpg.domain.accounting.cash_handover import CashHandover, CashHandoverReview
from lpg.domain.accounting.credit_note import CreditNote
from lpg.domain.accounting.invoice import Invoice, InvoiceLine, Payment, PlaceOfSupply
from lpg.domain.accounting.online_payment import OnlinePayment
from lpg.infrastructure.persistence.models.accounting import (
    CashHandoverModel,
    CashHandoverReviewModel,
    CreditNoteModel,
    InvoiceLineModel,
    InvoiceModel,
    OnlinePaymentModel,
    PaymentModel,
)
from lpg.infrastructure.persistence.models.customer import CustomerModel

if TYPE_CHECKING:
    from datetime import datetime

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
            invoice_number=model.invoice_number,
            customer_id=model.customer_id,
            customer_consumer_number=model.customer_consumer_number,
            order_id=model.order_id,
            order_number=model.order_number,
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
                    hsn_code=line.hsn_code,
                    gst_rate_percent=line.gst_rate_percent,
                    kind=line.line_kind,
                    description=line.description,
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
                    reference=payment.reference,
                )
                for payment in model.payments
            ],
            subtotal=model.subtotal,
            tax_amount=model.tax_amount,
            total_amount=model.total_amount,
            supply=PlaceOfSupply(
                supplier_state_code=model.supplier_state_code,
                place_of_supply_state_code=model.place_of_supply_state_code,
                customer_gstin=model.customer_gstin,
            ),
        )
        # Register for event dispatch
        self._uow.register_aggregate(invoice)
        return invoice

    async def add(self, invoice: Invoice) -> None:
        model = InvoiceModel(
            id=invoice.id,
            tenant_id=invoice.tenant_id,
            invoice_number=invoice.invoice_number,
            customer_id=invoice.customer_id,
            customer_consumer_number=invoice.customer_consumer_number,
            order_id=invoice.order_id,
            order_number=invoice.order_number,
            status=invoice.status,
            issued_at=invoice.issued_at,
            subtotal=invoice.subtotal,
            tax_amount=invoice.tax_amount,
            total_amount=invoice.total_amount,
            supplier_state_code=invoice.supplier_state_code,
            place_of_supply_state_code=invoice.place_of_supply_state_code,
            customer_gstin=invoice.customer_gstin,
            lines=[
                InvoiceLineModel(
                    id=line.id,
                    cylinder_type_id=line.cylinder_type_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    subtotal=line.subtotal,
                    tax_amount=line.tax_amount,
                    total_amount=line.total_amount,
                    hsn_code=line.hsn_code,
                    gst_rate_percent=line.gst_rate_percent,
                    line_kind=line.kind,
                    description=line.description,
                )
                for line in invoice.lines
            ],
            # Non-empty only when a gateway prepayment was applied at
            # generation time (ADR-053) — see `apply_online_payments_to_invoice`.
            payments=[
                PaymentModel(
                    id=payment.id,
                    tenant_id=invoice.tenant_id,
                    invoice_id=invoice.id,
                    method=payment.method,
                    amount=payment.amount,
                    collected_by=payment.collected_by,
                    collected_at=payment.collected_at,
                    reference=payment.reference,
                )
                for payment in invoice.payments
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
                    reference=domain_payment.reference,
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

    def _filtered(
        self,
        stmt: Select[Any],
        *,
        customer_id: uuid.UUID | None,
        order_id: uuid.UUID | None,
        status: str | None,
        issued_from: datetime | None,
        issued_to: datetime | None,
        search: str | None,
    ) -> Select[Any]:
        stmt = stmt.where(InvoiceModel.tenant_id == self._uow._tenant_context.tenant_id)
        if customer_id:
            stmt = stmt.where(InvoiceModel.customer_id == customer_id)
        if order_id:
            stmt = stmt.where(InvoiceModel.order_id == order_id)
        if status:
            stmt = stmt.where(InvoiceModel.status == status)
        if issued_from is not None:
            stmt = stmt.where(InvoiceModel.issued_at >= issued_from)
        if issued_to is not None:
            stmt = stmt.where(InvoiceModel.issued_at < issued_to)
        if search and search.strip():
            # Collapse runs of whitespace so "Meena  Iyer" still matches.
            pattern = "%" + " ".join(search.split()) + "%"
            customer_ids = select(CustomerModel.id).where(CustomerModel.full_name.ilike(pattern))
            stmt = stmt.where(
                or_(
                    InvoiceModel.invoice_number.ilike(pattern),
                    InvoiceModel.order_number.ilike(pattern),
                    InvoiceModel.customer_consumer_number.ilike(pattern),
                    InvoiceModel.customer_id.in_(customer_ids),
                )
            )
        return stmt

    async def list_invoices(
        self,
        skip: int = 0,
        limit: int = 50,
        customer_id: uuid.UUID | None = None,
        order_id: uuid.UUID | None = None,
        status: str | None = None,
        issued_from: datetime | None = None,
        issued_to: datetime | None = None,
        search: str | None = None,
    ) -> list[Invoice]:
        stmt = self._filtered(
            select(InvoiceModel),
            customer_id=customer_id,
            order_id=order_id,
            status=status,
            issued_from=issued_from,
            issued_to=issued_to,
            search=search,
        )
        stmt = (
            stmt.order_by(InvoiceModel.issued_at.desc(), InvoiceModel.id)
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
        issued_from: datetime | None = None,
        issued_to: datetime | None = None,
        search: str | None = None,
    ) -> int:
        stmt = self._filtered(
            select(func.count(InvoiceModel.id)),
            customer_id=customer_id,
            order_id=order_id,
            status=status,
            issued_from=issued_from,
            issued_to=issued_to,
            search=search,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() or 0

    async def customer_names(self, customer_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not customer_ids:
            return {}
        result = await self._session.execute(
            select(CustomerModel.id, CustomerModel.full_name).where(
                CustomerModel.id.in_(customer_ids)
            )
        )
        return {row.id: row.full_name for row in result}

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
        # Partially paid invoices count for what is still owed on them.
        result = await self._session.scalar(
            text("""
                SELECT COALESCE(SUM(i.total_amount - COALESCE(p.paid, 0)), 0)
                FROM accounting.invoice i
                LEFT JOIN LATERAL (
                    SELECT SUM(amount) AS paid FROM accounting.payment WHERE invoice_id = i.id
                ) p ON true
                WHERE i.customer_id = :customer_id
                  AND i.status IN ('issued', 'partially_paid')
            """),
            {"customer_id": customer_id},
        )
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
                handover_number=handover.handover_number,
                driver_id=handover.driver_id,
                route_id=handover.route_id,
                expected_amount=handover.expected_amount,
                actual_amount=handover.actual_amount,
                declared_by=handover.declared_by,
                declared_at=handover.declared_at,
            )
        )
        self._uow.register_aggregate(handover)

    def _to_domain(self, model: CashHandoverModel) -> CashHandover:
        return CashHandover(
            cash_handover_id=model.id,
            tenant_id=model.tenant_id,
            driver_id=model.driver_id,
            route_id=model.route_id,
            expected_amount=model.expected_amount,
            actual_amount=model.actual_amount,
            declared_by=model.declared_by,
            handover_number=model.handover_number,
            declared_at=model.declared_at,
        )

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

    async def count_cash_stops_for_route(self, route_id: uuid.UUID) -> int:
        from sqlalchemy import text

        stmt = text("""
            SELECT COUNT(*)
            FROM delivery.route_stop rs
            JOIN orders.proof_of_delivery pod ON pod.order_id = rs.order_id
            WHERE rs.route_id = :route_id AND pod.payment_method = 'cash'
        """)
        result = await self._session.scalar(stmt, {"route_id": route_id})
        return int(result) if result is not None else 0

    async def get_by_route(self, route_id: uuid.UUID) -> CashHandover | None:
        model = await self._session.scalar(
            select(CashHandoverModel).where(CashHandoverModel.route_id == route_id)
        )
        return self._to_domain(model) if model is not None else None

    async def get_by_id(self, cash_handover_id: uuid.UUID) -> CashHandover | None:
        model = await self._session.get(CashHandoverModel, cash_handover_id)
        return self._to_domain(model) if model is not None else None

    async def list_register(
        self,
        *,
        declared_from: datetime | None = None,
        declared_to: datetime | None = None,
        driver_id: uuid.UUID | None = None,
        review_status: str | None = None,
        limit: int = 200,
    ) -> list[CashHandoverRegisterEntry]:
        # Raw SQL across `delivery`/`tenant`/`identity`, same reasoning as
        # `get_expected_cash_for_route`; every table is under RLS.
        result = await self._session.execute(
            text("""
                SELECT h.id, r.route_date,
                       TRIM(e.first_name || ' ' || e.last_name) AS driver_name,
                       v.registration_number,
                       (SELECT COUNT(*) FROM delivery.route_stop rs
                          JOIN orders.proof_of_delivery pod ON pod.order_id = rs.order_id
                         WHERE rs.route_id = h.route_id AND pod.payment_method = 'cash'
                       ) AS cash_stop_count,
                       COALESCE(
                           NULLIF(TRIM(re.first_name || ' ' || re.last_name), ''), ru.email
                       ) AS reviewer_name
                FROM accounting.cash_handover h
                JOIN delivery.route r ON r.id = h.route_id
                JOIN delivery.driver d ON d.id = h.driver_id
                JOIN tenant.employee e ON e.id = d.employee_id
                LEFT JOIN delivery.vehicle v ON v.id = r.vehicle_id
                LEFT JOIN accounting.cash_handover_review rv ON rv.cash_handover_id = h.id
                LEFT JOIN identity.identity_user ru ON ru.id = rv.reviewed_by
                LEFT JOIN tenant.employee re
                       ON ru.email IS NOT NULL AND LOWER(re.email) = LOWER(ru.email)
                      AND re.is_deleted = false
                WHERE (CAST(:declared_from AS timestamptz) IS NULL
                       OR h.declared_at >= :declared_from)
                  AND (CAST(:declared_to AS timestamptz) IS NULL OR h.declared_at < :declared_to)
                  AND (CAST(:driver_id AS uuid) IS NULL OR h.driver_id = :driver_id)
                  AND (CAST(:review_status AS text) IS NULL
                       OR (:review_status = 'pending' AND rv.id IS NULL)
                       OR rv.outcome = :review_status)
                ORDER BY h.declared_at DESC
                LIMIT :limit
            """),
            {
                "declared_from": declared_from,
                "declared_to": declared_to,
                "driver_id": driver_id,
                "review_status": review_status,
                "limit": limit,
            },
        )
        rows = result.all()
        if not rows:
            return []
        ids = [row.id for row in rows]
        handovers = {
            model.id: self._to_domain(model)
            for model in (
                await self._session.scalars(
                    select(CashHandoverModel).where(CashHandoverModel.id.in_(ids))
                )
            )
        }
        reviews = {
            model.cash_handover_id: self._review_to_domain(model)
            for model in (
                await self._session.scalars(
                    select(CashHandoverReviewModel).where(
                        CashHandoverReviewModel.cash_handover_id.in_(ids)
                    )
                )
            )
        }
        return [
            CashHandoverRegisterEntry(
                handover=handovers[row.id],
                driver_name=row.driver_name,
                vehicle_registration=row.registration_number,
                route_date=row.route_date,
                cash_stop_count=int(row.cash_stop_count),
                review=reviews.get(row.id),
                reviewer_name=row.reviewer_name,
            )
            for row in rows
        ]

    @staticmethod
    def _review_to_domain(model: CashHandoverReviewModel) -> CashHandoverReview:
        return CashHandoverReview(
            id=model.id,
            tenant_id=model.tenant_id,
            cash_handover_id=model.cash_handover_id,
            outcome=model.outcome,
            note=model.note,
            reviewed_by=model.reviewed_by,
            reviewed_at=model.reviewed_at,
        )

    async def add_review(self, review: CashHandoverReview) -> None:
        self._session.add(
            CashHandoverReviewModel(
                id=review.id,
                tenant_id=review.tenant_id,
                cash_handover_id=review.cash_handover_id,
                outcome=review.outcome,
                note=review.note,
                reviewed_by=review.reviewed_by,
                reviewed_at=review.reviewed_at,
            )
        )

    async def get_review(self, cash_handover_id: uuid.UUID) -> CashHandoverReview | None:
        model = await self._session.scalar(
            select(CashHandoverReviewModel).where(
                CashHandoverReviewModel.cash_handover_id == cash_handover_id
            )
        )
        return self._review_to_domain(model) if model is not None else None

    async def cash_awaiting_handover(self) -> Decimal:
        result = await self._session.scalar(
            text("""
                SELECT COALESCE(SUM(pod.amount_collected), 0)
                FROM orders.proof_of_delivery pod
                JOIN delivery.route_stop rs ON rs.order_id = pod.order_id
                WHERE pod.payment_method = 'cash'
                  AND NOT EXISTS (
                      SELECT 1 FROM accounting.cash_handover h WHERE h.route_id = rs.route_id
                  )
            """)
        )
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
            credit_note_number=model.credit_note_number,
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
                credit_note_number=credit_note.credit_note_number,
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

    async def list_for_invoice(self, invoice_id: uuid.UUID) -> list[CreditNote]:
        result = await self._session.scalars(
            select(CreditNoteModel)
            .where(CreditNoteModel.invoice_id == invoice_id)
            .order_by(CreditNoteModel.requested_at)
        )
        return [self._to_domain(model) for model in result]


_UNINVOICED_SQL = """
    SELECT o.id AS order_id, o.order_number, o.customer_id, c.full_name AS customer_name,
           o.status, o.total_amount AS order_total, cr.cancellation_charge,
           COALESCE(cr.approved_at, h.changed_at, o.updated_at) AS occurred_at
    FROM orders.order o
    JOIN customer.customer c ON c.id = o.customer_id
    LEFT JOIN LATERAL (
        SELECT changed_at FROM orders.order_status_history
        WHERE order_id = o.id AND to_status = 'delivered'
        ORDER BY changed_at DESC LIMIT 1
    ) h ON true
    LEFT JOIN LATERAL (
        SELECT cancellation_charge, approved_at FROM orders.cancellation_record
        WHERE order_id = o.id AND approved_by IS NOT NULL AND is_deleted = false
        ORDER BY approved_at DESC LIMIT 1
    ) cr ON true
    WHERE o.is_deleted = false
      AND NOT EXISTS (SELECT 1 FROM accounting.invoice i WHERE i.order_id = o.id)
      AND (
          (o.status IN ('delivered', 'closed') AND EXISTS (
              SELECT 1 FROM orders.order_line ol
              WHERE ol.order_id = o.id AND ol.quantity_delivered > 0
          ))
          OR (o.status = 'cancelled' AND cr.cancellation_charge > 0)
      )
"""


class SqlAlchemyUninvoicedOrderReader:
    """Implements `UninvoicedOrderReader` with one query over `orders`,
    `customer` and `accounting` (all under RLS).
    """

    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._session = uow.session

    @staticmethod
    def _to_entry(row: Any) -> UninvoicedOrder:
        return UninvoicedOrder(
            order_id=row.order_id,
            order_number=row.order_number,
            customer_id=row.customer_id,
            customer_name=row.customer_name,
            status=row.status,
            occurred_at=row.occurred_at,
            order_total=row.order_total,
            cancellation_charge=row.cancellation_charge,
        )

    async def list_uninvoiced(self, *, limit: int = 100) -> list[UninvoicedOrder]:
        result = await self._session.execute(
            text(_UNINVOICED_SQL + " ORDER BY occurred_at DESC LIMIT :limit"), {"limit": limit}
        )
        return [self._to_entry(row) for row in result]

    async def get_uninvoiced(self, order_id: uuid.UUID) -> UninvoicedOrder | None:
        result = await self._session.execute(
            text(_UNINVOICED_SQL + " AND o.id = :order_id"), {"order_id": order_id}
        )
        row = result.first()
        return self._to_entry(row) if row is not None else None


class SqlAlchemyOnlinePaymentRepository(OnlinePaymentRepository):
    """SQLAlchemy implementation of ``OnlinePaymentRepository``.

    Single-row reads lock the row (`FOR UPDATE`): they are only used on the
    mutation paths (webhook, refresh), and a gateway can deliver the same
    event twice concurrently — without the lock both deliveries could apply
    the same money to the invoice.
    """

    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow
        self._session = uow.session

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    def _to_domain(self, model: OnlinePaymentModel) -> OnlinePayment:
        payment = OnlinePayment(
            online_payment_id=model.id,
            tenant_id=model.tenant_id,
            order_id=model.order_id,
            customer_id=model.customer_id,
            invoice_id=model.invoice_id,
            amount=model.amount,
            currency=model.currency,
            provider=model.provider,
            provider_link_id=model.provider_link_id,
            short_url=model.short_url,
            status=model.status,
            created_by=model.created_by,
            created_at=model.created_at,
            expires_at=model.expires_at,
            provider_payment_id=model.provider_payment_id,
            payment_method=model.payment_method,
            paid_at=model.paid_at,
            applied_payment_id=model.applied_payment_id,
            version=model.version,
        )
        self._uow.register_aggregate(payment)
        return payment

    async def add(self, payment: OnlinePayment) -> None:
        self._session.add(
            OnlinePaymentModel(
                id=payment.id,
                tenant_id=payment.tenant_id,
                order_id=payment.order_id,
                customer_id=payment.customer_id,
                invoice_id=payment.invoice_id,
                amount=payment.amount,
                currency=payment.currency,
                provider=payment.provider,
                provider_link_id=payment.provider_link_id,
                short_url=payment.short_url,
                status=payment.status,
                created_by=payment.created_by,
                created_at=payment.created_at,
                expires_at=payment.expires_at,
                version=payment.version,
            )
        )
        self._uow.register_aggregate(payment)

    async def save(self, payment: OnlinePayment) -> None:
        model = await self._session.get(OnlinePaymentModel, payment.id)
        if model is None:
            msg = f"Cannot save changes to online payment {payment.id}: no existing row found."
            raise ValueError(msg)
        model.status = payment.status
        model.invoice_id = payment.invoice_id
        model.provider_payment_id = payment.provider_payment_id
        model.payment_method = payment.payment_method
        model.paid_at = payment.paid_at
        model.applied_payment_id = payment.applied_payment_id
        model.version = model.version + 1

    async def _get_locked(self, *criteria: Any) -> OnlinePayment | None:
        stmt = select(OnlinePaymentModel).where(*criteria).with_for_update()
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if model is None else self._to_domain(model)

    async def get_by_id(self, online_payment_id: uuid.UUID) -> OnlinePayment | None:
        return await self._get_locked(OnlinePaymentModel.id == online_payment_id)

    async def get_by_provider_link_id(self, provider_link_id: str) -> OnlinePayment | None:
        return await self._get_locked(OnlinePaymentModel.provider_link_id == provider_link_id)

    async def list_for_order(self, order_id: uuid.UUID) -> list[OnlinePayment]:
        stmt = (
            select(OnlinePaymentModel)
            .where(OnlinePaymentModel.order_id == order_id)
            .order_by(OnlinePaymentModel.created_at.desc())
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [self._to_domain(model) for model in models]
