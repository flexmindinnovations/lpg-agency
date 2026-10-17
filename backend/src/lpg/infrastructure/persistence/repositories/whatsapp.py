"""SQLAlchemy implementation of
`lpg.application.whatsapp.ports.WhatsAppConversationRepository` (ADR-054).

Tenant-scoped by RLS on the `messaging.*` tables; `tenant_id` is still
written explicitly on insert, from the Unit of Work's tenant context, because
RLS checks it but does not fill it in.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from lpg.application.whatsapp.ports import ConversationEntry, PendingOrderQuote
from lpg.infrastructure.persistence.models.whatsapp import (
    WhatsAppConversationModel,
    WhatsAppMessageModel,
)

if TYPE_CHECKING:
    from lpg.application.whatsapp.ports import InboundWhatsAppMessage
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyWhatsAppConversationRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    @property
    def _tenant_id(self) -> uuid.UUID:
        return self._uow.tenant_context.tenant_id

    async def record_inbound(self, message: InboundWhatsAppMessage) -> bool:
        stmt = (
            pg_insert(WhatsAppMessageModel)
            .values(
                id=uuid.uuid4(),
                tenant_id=self._tenant_id,
                direction="inbound",
                phone_number=message.from_phone,
                body=message.text,
                wa_message_id=message.wa_message_id,
                status="received",
            )
            .on_conflict_do_nothing(constraint="uq_whatsapp_message_wa_id")
            .returning(WhatsAppMessageModel.id)
        )
        result = await self._uow.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def record_outbound(
        self, *, to_phone: str, body: str, wa_message_id: str | None, status: str
    ) -> None:
        self._uow.session.add(
            WhatsAppMessageModel(
                id=uuid.uuid4(),
                tenant_id=self._tenant_id,
                direction="outbound",
                phone_number=to_phone,
                body=body,
                wa_message_id=wa_message_id,
                status=status,
            )
        )

    async def list_recent(
        self, phone: str, *, since: datetime, limit: int
    ) -> list[ConversationEntry]:
        stmt = (
            select(WhatsAppMessageModel)
            .where(
                WhatsAppMessageModel.phone_number == phone,
                WhatsAppMessageModel.created_at >= since,
            )
            .order_by(WhatsAppMessageModel.created_at.desc(), WhatsAppMessageModel.id.desc())
            .limit(limit)
        )
        rows = (await self._uow.session.execute(stmt)).scalars().all()
        return [
            ConversationEntry(
                direction="inbound" if row.direction == "inbound" else "outbound",
                body=row.body,
                created_at=row.created_at,
            )
            for row in reversed(rows)
        ]

    async def get_pending_quote(self, phone: str) -> PendingOrderQuote | None:
        stmt = select(WhatsAppConversationModel.pending_quote).where(
            WhatsAppConversationModel.phone_number == phone
        )
        raw = (await self._uow.session.execute(stmt)).scalar_one_or_none()
        return _quote_from_json(raw) if raw else None

    async def set_pending_quote(self, phone: str, quote: PendingOrderQuote | None) -> None:
        payload = _quote_to_json(quote) if quote is not None else None
        now = datetime.now(UTC)
        stmt = (
            pg_insert(WhatsAppConversationModel)
            .values(
                tenant_id=self._tenant_id,
                phone_number=phone,
                pending_quote=payload,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["tenant_id", "phone_number"],
                set_={"pending_quote": payload, "updated_at": now},
            )
        )
        await self._uow.session.execute(stmt)


def _quote_to_json(quote: PendingOrderQuote) -> dict[str, Any]:
    return {
        "cylinder_type_id": str(quote.cylinder_type_id),
        "cylinder_type_name": quote.cylinder_type_name,
        "quantity": quote.quantity,
        "address_id": str(quote.address_id),
        "address_line": quote.address_line,
        "latitude": quote.latitude,
        "longitude": quote.longitude,
        "requested_date": quote.requested_date.isoformat(),
        "payment_method": quote.payment_method,
        "estimated_unit_price": (
            str(quote.estimated_unit_price) if quote.estimated_unit_price is not None else None
        ),
        "quoted_at": quote.quoted_at.isoformat(),
    }


def _quote_from_json(raw: dict[str, Any]) -> PendingOrderQuote:
    price = raw.get("estimated_unit_price")
    return PendingOrderQuote(
        cylinder_type_id=uuid.UUID(raw["cylinder_type_id"]),
        cylinder_type_name=raw["cylinder_type_name"],
        quantity=int(raw["quantity"]),
        address_id=uuid.UUID(raw["address_id"]),
        address_line=raw["address_line"],
        latitude=raw.get("latitude"),
        longitude=raw.get("longitude"),
        requested_date=date.fromisoformat(raw["requested_date"]),
        payment_method=raw["payment_method"],
        estimated_unit_price=Decimal(price) if price is not None else None,
        quoted_at=datetime.fromisoformat(raw["quoted_at"]),
    )
