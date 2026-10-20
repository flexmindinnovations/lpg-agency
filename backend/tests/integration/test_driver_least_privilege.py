"""DA-05: the `driver` role holds only what the Driver App needs.

A driver token used to reach goods receipts and warehouse reconciliation counts
(`inventory:load`) and could list every customer and driver. Migration
`c48cbf996d8c` removed those grants; this pins the role's exact set so a later
seed migration can't quietly widen it again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration

_DRIVER_PERMISSIONS = {
    "cash_handovers:declare",
    "orders:deliver",
    "orders:dispatch",
    "orders:read",
    "routes:deliver",
    "routes:read",
}


async def test_driver_role_is_least_privilege(
    admin_engine: AsyncEngine, postgres_available: bool
) -> None:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    async with admin_engine.connect() as conn:
        codes = set(
            (
                await conn.execute(
                    text(
                        "SELECT p.code FROM identity.role_permission rp "
                        "JOIN identity.role r ON r.id = rp.role_id "
                        "JOIN identity.permission p ON p.id = rp.permission_id "
                        "WHERE r.code = 'driver'"
                    )
                )
            ).scalars()
        )
    assert codes == _DRIVER_PERMISSIONS
    assert not {c for c in codes if c.startswith(("inventory:", "reconciliation:"))}
