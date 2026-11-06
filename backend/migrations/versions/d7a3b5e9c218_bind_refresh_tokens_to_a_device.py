"""bind refresh tokens to the phone they were issued to

Device registration and access control (ADR-071). A refresh token issued to a
Driver or Admin app session now remembers which `platform.linked_device` it
belongs to, so that blocking or removing the phone can end exactly that
phone's sessions, and a refresh token presented from a different phone can be
refused.

`identity.refresh_token` is reached only through `SECURITY DEFINER` functions
(tokens are redeemed before any tenant context exists, and their `tenant_id`
column is always NULL), so this migration replaces the save function with one
that also takes the device, and adds one narrow function that revokes every
live token of one device. Tokens issued before this change have no device and
behave exactly as before.

Revision ID: d7a3b5e9c218
Revises: c4e8a1f7d305
Create Date: 2026-11-05
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "d7a3b5e9c218"
down_revision: str | None = "c4e8a1f7d305"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_S = "identity"
_OLD_SIG = "uuid, uuid, uuid, text, timestamptz, timestamptz, timestamptz, timestamptz, uuid"
_NEW_SIG = f"{_OLD_SIG}, uuid"

_GRANT = """
    DO $$
    DECLARE
        app_role text := CASE current_database()
            WHEN 'lpg_uat' THEN 'lpg_app_uat'
            ELSE 'lpg_app'
        END;
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
            EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO %%I', '{signature}', app_role);
        END IF;
    END
    $$;
"""


def _grant(signature: str) -> str:
    return _GRANT.format(signature=signature).replace("%%I", "%I")


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE {_S}.refresh_token
        ADD COLUMN device_id uuid REFERENCES platform.linked_device(id) ON DELETE CASCADE
    """)
    op.execute(
        f"CREATE INDEX idx_identity_refresh_token_device ON {_S}.refresh_token (device_id) "
        "WHERE device_id IS NOT NULL"
    )

    op.execute(f"DROP FUNCTION {_S}.auth_save_refresh_token({_OLD_SIG})")
    op.execute(f"""
        CREATE FUNCTION {_S}.auth_save_refresh_token(
            p_id uuid,
            p_tenant_id uuid,
            p_user_id uuid,
            p_token_hash text,
            p_issued_at timestamptz,
            p_expires_at timestamptz,
            p_rotated_at timestamptz,
            p_revoked_at timestamptz,
            p_replaced_by_id uuid,
            p_device_id uuid
        )
        RETURNS void
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_S}, pg_temp
        AS $$
            INSERT INTO {_S}.refresh_token (
                id, tenant_id, user_id, token_hash, issued_at, expires_at,
                rotated_at, revoked_at, replaced_by_id, device_id
            )
            VALUES (
                p_id, p_tenant_id, p_user_id, p_token_hash, p_issued_at, p_expires_at,
                p_rotated_at, p_revoked_at, p_replaced_by_id, p_device_id
            )
            ON CONFLICT (id) DO UPDATE SET
                rotated_at = EXCLUDED.rotated_at,
                revoked_at = EXCLUDED.revoked_at,
                replaced_by_id = EXCLUDED.replaced_by_id;
        $$;
    """)
    op.execute(f"""
        CREATE FUNCTION {_S}.auth_revoke_all_refresh_tokens_for_device(p_device_id uuid)
        RETURNS void
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_S}, pg_temp
        AS $$
            UPDATE {_S}.refresh_token
            SET revoked_at = now()
            WHERE device_id = p_device_id AND revoked_at IS NULL;
        $$;
    """)
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_S}.auth_save_refresh_token({_NEW_SIG}) FROM PUBLIC")
    op.execute(
        f"REVOKE EXECUTE ON FUNCTION {_S}.auth_revoke_all_refresh_tokens_for_device(uuid) "
        "FROM PUBLIC"
    )
    op.execute(_grant(f"{_S}.auth_save_refresh_token({_NEW_SIG})"))
    op.execute(_grant(f"{_S}.auth_revoke_all_refresh_tokens_for_device(uuid)"))


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {_S}.auth_revoke_all_refresh_tokens_for_device(uuid)")
    op.execute(f"DROP FUNCTION IF EXISTS {_S}.auth_save_refresh_token({_NEW_SIG})")
    op.execute(f"""
        CREATE FUNCTION {_S}.auth_save_refresh_token(
            p_id uuid, p_tenant_id uuid, p_user_id uuid, p_token_hash text,
            p_issued_at timestamptz, p_expires_at timestamptz, p_rotated_at timestamptz,
            p_revoked_at timestamptz, p_replaced_by_id uuid
        )
        RETURNS void
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_S}, pg_temp
        AS $$
            INSERT INTO {_S}.refresh_token (
                id, tenant_id, user_id, token_hash, issued_at, expires_at,
                rotated_at, revoked_at, replaced_by_id
            )
            VALUES (
                p_id, p_tenant_id, p_user_id, p_token_hash, p_issued_at, p_expires_at,
                p_rotated_at, p_revoked_at, p_replaced_by_id
            )
            ON CONFLICT (id) DO UPDATE SET
                rotated_at = EXCLUDED.rotated_at,
                revoked_at = EXCLUDED.revoked_at,
                replaced_by_id = EXCLUDED.replaced_by_id;
        $$;
    """)
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_S}.auth_save_refresh_token({_OLD_SIG}) FROM PUBLIC")
    op.execute(_grant(f"{_S}.auth_save_refresh_token({_OLD_SIG})"))
    op.execute(f"DROP INDEX IF EXISTS {_S}.idx_identity_refresh_token_device")
    op.execute(f"ALTER TABLE {_S}.refresh_token DROP COLUMN device_id")
