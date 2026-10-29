"""SQLAlchemy `OrderReminderRepository` over `orders.order_reminder`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from lpg.application.order.reminders import OrderReminder

if TYPE_CHECKING:
    import uuid

    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyOrderReminderRepository:
    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    async def add(self, reminder: OrderReminder, tenant_id: uuid.UUID) -> None:
        await self._uow.session.execute(
            text("""
                INSERT INTO orders.order_reminder
                    (id, tenant_id, order_id, sent_by, preset, message, sent_at)
                VALUES (:id, :tenant_id, :order_id, :sent_by, :preset, :message, :sent_at)
            """),
            {
                "id": reminder.id,
                "tenant_id": tenant_id,
                "order_id": reminder.order_id,
                "sent_by": reminder.sent_by,
                "preset": reminder.preset,
                "message": reminder.message,
                "sent_at": reminder.sent_at,
            },
        )

    async def list_for_order(self, order_id: uuid.UUID) -> list[OrderReminder]:
        result = await self._uow.session.execute(
            text("""
                SELECT id, order_id, sent_by, preset, message, sent_at
                FROM orders.order_reminder
                WHERE order_id = :order_id
                ORDER BY sent_at DESC
            """),
            {"order_id": order_id},
        )
        return [
            OrderReminder(
                id=row.id,
                order_id=row.order_id,
                sent_by=row.sent_by,
                preset=row.preset,
                message=row.message,
                sent_at=row.sent_at,
            )
            for row in result
        ]
