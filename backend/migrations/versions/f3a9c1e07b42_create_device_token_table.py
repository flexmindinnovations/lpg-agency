"""create notification.device_token table

Push-notification delivery targets. One row per (user, device installation)
-- the FCM registration token, plus the platform so the send path can shape
the payload (Android data-only vs. iOS notification+content-available).

`token` is globally unique: FCM reissues a token to whichever app instance
most recently registered it, so a collision means the device moved accounts
and the old owner's row must yield. The register endpoint upserts on
`token` for exactly this reason.

Revision ID: f3a9c1e07b42
Revises: e91a4c2f5b76
Create Date: 2026-08-31
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "f3a9c1e07b42"
down_revision: str | None = "e91a4c2f5b76"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE notification.device_token (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            recipient_user_id UUID NOT NULL,
            token TEXT NOT NULL,
            platform VARCHAR(16) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT device_token_token_key UNIQUE (token),
            CONSTRAINT device_token_platform_check
                CHECK (platform IN ('android', 'ios', 'web'))
        );
    """)
    op.execute(
        "CREATE INDEX ON notification.device_token (tenant_id, recipient_user_id);"
    )

    op.execute("ALTER TABLE notification.device_token ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY tenant_isolation ON notification.device_token
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
    """)

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE "
        "ON notification.device_token TO lpg_app;"
    )


def downgrade() -> None:
    op.execute("DROP TABLE notification.device_token;")
