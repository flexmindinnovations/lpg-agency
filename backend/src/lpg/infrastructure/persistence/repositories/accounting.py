"""Invoice Repository implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lpg.application.accounting.ports import InvoiceRepository
from lpg.domain.accounting.invoice import Invoice, InvoiceLine
from lpg.infrastructure.persistence.models.accounting import InvoiceLineModel, InvoiceModel

if TYPE_CHECKING:
    import uuid

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

    async def get_by_id(self, invoice_id: uuid.UUID) -> Invoice | None:
        stmt = (
            select(InvoiceModel)
            .where(InvoiceModel.id == invoice_id)
            .options(selectinload(InvoiceModel.lines))
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
            .options(selectinload(InvoiceModel.lines))
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
            .options(selectinload(InvoiceModel.lines))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)
