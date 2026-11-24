"""create platform.tenant_module_setting

Revision ID: c5a8f2d1b9e7
Revises: b3e6d1f8a427
Create Date: 2026-11-24 19:00:00.000000

Which dashboard modules a super admin has switched on or off for an agency
(`lpg.domain.license.modules`). Every module is on by default, so a row only
exists where a super admin has chosen. A normal RLS-scoped tenant table (like
`platform.linked_device`): the agency reads its own rows, and a super admin
writes through a unit of work scoped to the target tenant.

Deliberately not tied to `platform.license`: an agency may have no licence
issued and still needs its modules shown or hidden.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "c5a8f2d1b9e7"
down_revision: str | None = "b3e6d1f8a427"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "tenant_module_setting"
_RLS_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenant.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module_key", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.UniqueConstraint(
            "tenant_id", "module_key", name="uq_tenant_module_setting_tenant_module"
        ),
        schema="platform",
    )
    op.execute(f"ALTER TABLE platform.{_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE platform.{_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_platform_{_TABLE}_isolation
        ON platform.{_TABLE}
        USING ({_RLS_PREDICATE})
    """)
    op.execute(f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT USAGE ON SCHEMA platform TO %I', app_role);
                EXECUTE format(
                    'GRANT SELECT, INSERT, UPDATE ON platform.{_TABLE} TO %I', app_role
                );
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS rls_platform_{_TABLE}_isolation ON platform.{_TABLE}")
    op.drop_table(_TABLE, schema="platform")
