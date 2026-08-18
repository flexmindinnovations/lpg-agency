"""`SqlAlchemyTenantSlugResolver` implements
`application/identity/ports.py::TenantSlugResolver` (Area D).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.database import Database


class SqlAlchemyTenantSlugResolver:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def resolve(self, slug: str) -> uuid.UUID | None:
        async for session in self._database.open_session():
            result = await session.execute(
                text("SELECT tenant.auth_resolve_tenant_id_by_slug(:slug)"), {"slug": slug}
            )
            tenant_id = result.scalar()
            return uuid.UUID(str(tenant_id)) if tenant_id is not None else None

        raise RuntimeError("Unreachable")
