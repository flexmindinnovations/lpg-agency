"""create order_reminder table

Staff reminders sent to a customer about their order (planning/features/51).
Append-only: one row per message, shown on the order's timeline and counted
for the rate limit. `UPDATE`/`DELETE` are not granted to the app role.

Revision ID: d2b8f4a60c17
Revises: a3f7c1e9d205
Create Date: 2026-10-29
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "d2b8f4a60c17"
down_revision: str | None = "a3f7c1e9d205"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "orders"
_TABLE = "order_reminder"


def _app_role_block(statement: str) -> str:
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT USAGE ON SCHEMA {_SCHEMA} TO %I', app_role);
                EXECUTE format('{statement}', app_role);
            END IF;
        END
        $$;
    """


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {_SCHEMA}.{_TABLE} (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenant.tenant(id) ON DELETE CASCADE,
            order_id uuid NOT NULL REFERENCES orders."order"(id) ON DELETE CASCADE,
            sent_by uuid NOT NULL,
            preset text NOT NULL,
            message text NOT NULL,
            sent_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        f"CREATE INDEX idx_{_SCHEMA}_{_TABLE}_order ON {_SCHEMA}.{_TABLE} (order_id, sent_at)"
    )
    op.execute(_app_role_block(f"GRANT SELECT, INSERT ON {_SCHEMA}.{_TABLE} TO %I"))
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)


def downgrade() -> None:
    op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.{_TABLE}")
