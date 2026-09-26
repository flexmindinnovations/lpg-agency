"""add identity.auth_invalidate_password_reset_tokens() SECURITY DEFINER function

Revision ID: e7d1a3c5f9b2
Revises: d5b9e3a7f1c4
Create Date: 2026-09-26 14:00:00.000000

Agency User Management (Phase 31): when a Super Admin issues a fresh setup link
for an agency admin, that user's older unused links must stop working - a link
sent to the wrong place must not stay usable for the rest of its lifetime.

`identity.password_reset_token` is RLS-protected and, like every other access to
it, is reached through `SECURITY DEFINER` `auth_*` functions rather than a plain
UPDATE (the reset flow is pre-authentication, so no tenant context exists). This
adds the same kind of narrow, single-purpose function: it only ever sets
`used_at` on a user's still-unused tokens. `EXECUTE` is revoked from PUBLIC and
granted only to the application role, like its siblings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "e7d1a3c5f9b2"
down_revision: str | None = "d5b9e3a7f1c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SIGNATURE = "auth_invalidate_password_reset_tokens(uuid)"


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION identity.auth_invalidate_password_reset_tokens(p_user_id uuid)
        RETURNS void
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = identity, pg_temp
        AS $$
            UPDATE identity.password_reset_token
               SET used_at = now()
             WHERE user_id = p_user_id
               AND used_at IS NULL;
        $$;
    """)
    op.execute(f"REVOKE EXECUTE ON FUNCTION identity.{_SIGNATURE} FROM PUBLIC")
    op.execute(f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT USAGE ON SCHEMA identity TO %I', app_role);
                EXECUTE format('GRANT EXECUTE ON FUNCTION identity.{_SIGNATURE} TO %I', app_role);
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS identity.{_SIGNATURE}")
