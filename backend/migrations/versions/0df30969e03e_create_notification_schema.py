"""create notification schema

Revision ID: 0df30969e03e
Revises: e60b8b86b965
Create Date: 2026-08-13 21:48:46.067469

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op
import sqlalchemy as sa


if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = '0df30969e03e'
down_revision: str | None = 'e60b8b86b965'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA notification;")

    op.execute("""
        CREATE TABLE notification.in_app_notification (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            recipient_user_id UUID NOT NULL,
            notification_type VARCHAR(50) NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            reference_type VARCHAR(50),
            reference_id UUID,
            is_read BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ON notification.in_app_notification (tenant_id, recipient_user_id, is_read);")
    
    op.execute("ALTER TABLE notification.in_app_notification ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY tenant_isolation ON notification.in_app_notification
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
    """)

    op.execute("""
        CREATE TABLE notification.notification_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            recipient_user_id UUID NOT NULL,
            notification_type VARCHAR(50) NOT NULL,
            channel VARCHAR(20) NOT NULL,
            recipient_address TEXT,
            subject TEXT,
            body TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'queued',
            reference_type VARCHAR(50),
            reference_id UUID,
            retry_count INT NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    
    op.execute("ALTER TABLE notification.notification_log ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY tenant_isolation ON notification.notification_log
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
    """)

    op.execute("GRANT USAGE ON SCHEMA notification TO lpg_app;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA notification TO lpg_app;")


def downgrade() -> None:
    op.execute("DROP SCHEMA notification CASCADE;")
