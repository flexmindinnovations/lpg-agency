"""Webhook token -> tenant for per-agency Razorpay webhooks (ADR-067)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.database import Database


class PaymentCredentialTenantResolver:
    """Webhook token -> tenant, through the SECURITY DEFINER function in
    migration `e3a7c1d9b5f2` (the webhook has no tenant until this answers).
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def resolve(self, token: str) -> uuid.UUID | None:
        async for session in self._database.open_session():
            result = await session.execute(
                text("SELECT accounting.payment_credential_resolve_tenant(:token)"),
                {"token": token},
            )
            tenant_id = result.scalar()
            return uuid.UUID(str(tenant_id)) if tenant_id is not None else None
        msg = "Unreachable"
        raise RuntimeError(msg)
