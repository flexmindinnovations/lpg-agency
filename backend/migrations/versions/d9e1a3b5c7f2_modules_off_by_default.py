"""modules are off by default: keep every existing agency's modules on

Revision ID: d9e1a3b5c7f2
Revises: c5a8f2d1b9e7
Create Date: 2026-11-25 13:00:00.000000

Until now every module was on unless a super admin switched it off. The model
is now the other way round: a module is on only where an `enabled` row says so
(`lpg.domain.license.modules`). So agencies that already exist keep exactly what
they have today: this writes an `enabled = true` row for every module that has
no row yet, and leaves any row a super admin already wrote (including the
switched-off ones) alone. Agencies created after this start with nothing on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "d9e1a3b5c7f2"
down_revision: str | None = "c5a8f2d1b9e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of the catalog's keys at this revision (the migration must keep
# meaning the same thing if the catalog later changes).
_MODULE_KEYS = (
    "customers",
    "orders",
    "complaints",
    "drivers",
    "vehicles",
    "dispatch",
    "inventory",
    "scales",
    "cylinder_units",
    "compliance_calendar",
    "invoices",
    "cash_handovers",
    "reports",
    "ai_command_center",
)


def upgrade() -> None:
    values = ", ".join(f"('{key}')" for key in _MODULE_KEYS)
    op.execute(
        f"""
        DO $$
        DECLARE
            t uuid;
        BEGIN
            FOR t IN SELECT id FROM tenant.tenant LOOP
                PERFORM set_config('app.current_tenant_id', t::text, true);

                INSERT INTO platform.tenant_module_setting (id, tenant_id, module_key, enabled)
                SELECT gen_random_uuid(), t, k.module_key, true
                FROM (VALUES {values}) AS k(module_key)
                ON CONFLICT (tenant_id, module_key) DO NOTHING;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END
        $$;
        """
    )


def downgrade() -> None:
    # The previous model reads only `enabled = false` rows as "off"; the rows this
    # migration added are all `true`, so they are inert there and are left in place.
    pass
