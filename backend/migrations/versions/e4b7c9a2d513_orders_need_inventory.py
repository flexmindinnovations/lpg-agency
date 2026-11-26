"""orders need inventory: switch Inventory on where Orders is on

Revision ID: e4b7c9a2d513
Revises: d9e1a3b5c7f2
Create Date: 2026-11-26 17:30:00.000000

The module catalog now lists Inventory among what Orders requires
(`lpg.domain.license.modules`): only cylinders in stock can be booked, and stock
is recorded in Inventory. An agency with Orders on and Inventory off would break
that rule, so this switches Inventory on for it. Other agencies are left alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "e4b7c9a2d513"
down_revision: str | None = "d9e1a3b5c7f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The table forces row-level security, so each agency is updated in its turn.
    op.execute(
        """
        DO $$
        DECLARE
            t uuid;
        BEGIN
            FOR t IN SELECT id FROM tenant.tenant LOOP
                PERFORM set_config('app.current_tenant_id', t::text, true);

                INSERT INTO platform.tenant_module_setting AS setting
                    (id, tenant_id, module_key, enabled)
                SELECT gen_random_uuid(), t, 'inventory', true
                WHERE EXISTS (
                    SELECT 1 FROM platform.tenant_module_setting
                    WHERE tenant_id = t AND module_key = 'orders' AND enabled
                )
                ON CONFLICT (tenant_id, module_key) DO UPDATE
                    SET enabled = true, updated_at = now(), version = setting.version + 1
                    WHERE NOT setting.enabled;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END
        $$;
        """
    )


def downgrade() -> None:
    # Which agencies had Inventory off before is not recorded, and Inventory
    # being on is valid under the earlier catalog too.
    pass
