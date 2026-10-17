"""Maps a WhatsApp Business phone number id to its tenant, through the
`tenant.whatsapp_resolve_tenant_id` SECURITY DEFINER function (migration
`a9c2e4f6b8d1`). Same shape as `SqlAlchemyTenantSlugResolver`."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.database import Database


class SqlAlchemyWhatsAppTenantResolver:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def resolve(self, phone_number_id: str) -> uuid.UUID | None:
        async for session in self._database.open_session():
            result = await session.execute(
                text("SELECT tenant.whatsapp_resolve_tenant_id(:phone_number_id)"),
                {"phone_number_id": phone_number_id},
            )
            tenant_id = result.scalar()
            return uuid.UUID(str(tenant_id)) if tenant_id is not None else None

        raise RuntimeError("Unreachable")
