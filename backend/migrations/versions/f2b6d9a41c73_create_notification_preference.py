"""create notification.notification_preference

Per-agency notification settings (ADR-068). The catalogue
(`infrastructure/notification/catalog.py`) says what each event does by
default; a row here is an agency's override for one event type. Each
channel column is nullable: NULL means "use the catalogue default", so a
default that changes later reaches agencies that never touched the event.

Row-level security confines every access to the caller's own tenant.

Revision ID: f2b6d9a41c73
Revises: b7c4e91d3a58
Create Date: 2026-11-01
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "f2b6d9a41c73"
down_revision: str | None = "b7c4e91d3a58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "notification"
_TABLE = "notification_preference"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {_SCHEMA}.{_TABLE} (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenant.tenant(id) ON DELETE CASCADE,
            notification_type text NOT NULL,
            in_app boolean,
            push boolean,
            sms boolean,
            email boolean,
            updated_at timestamptz NOT NULL DEFAULT now(),
            updated_by uuid,
            UNIQUE (tenant_id, notification_type)
        )
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
                EXECUTE format('GRANT USAGE ON SCHEMA {_SCHEMA} TO %I', app_role);
                EXECUTE format(
                    'GRANT SELECT, INSERT, UPDATE, DELETE ON {_SCHEMA}.{_TABLE} TO %I', app_role
                );
            END IF;
        END
        $$;
    """)
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}")
    op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.{_TABLE}")
