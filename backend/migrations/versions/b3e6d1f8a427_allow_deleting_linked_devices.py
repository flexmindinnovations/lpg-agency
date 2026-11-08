"""let the application role delete a linked device

An agency admin can now delete a phone's record for good (ADR-073). The
application role only had SELECT, INSERT and UPDATE on
`platform.linked_device`; this adds DELETE. Row-level security still confines
every delete to the caller's own agency, and the phone's refresh tokens go with
it (`identity.refresh_token.device_id` is `ON DELETE CASCADE`).

Revision ID: b3e6d1f8a427
Revises: a9d4c2e7b816
Create Date: 2026-11-08 17:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b3e6d1f8a427"
down_revision: str | None = "a9d4c2e7b816"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _change(verb: str, preposition: str) -> str:
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format(
                    '{verb} DELETE ON platform.linked_device {preposition} %I', app_role
                );
            END IF;
        END
        $$;
    """


def upgrade() -> None:
    op.execute(_change("GRANT", "TO"))


def downgrade() -> None:
    op.execute(_change("REVOKE", "FROM"))
