"""create identity refresh_token and password_reset_token tables

Revision ID: 10a62de534be
Revises: fa52b77ec442
Create Date: 2026-08-10 09:05:00.000000

Split from `fa52b77ec442` deliberately: session/token data has a very
different write pattern (high-volume, append-heavy, short-lived rows) from
that migration's low-change reference and account data.

Both tables: `tenant_id` denormalized from the owning user (nullable, since
a Super Admin's tokens have none either), RLS applied, `SELECT, INSERT,
UPDATE` grants only — rotation/revocation/consumption are `UPDATE`s, and
neither table is ever hard-deleted (rows age out via TTL-driven cleanup in
a later phase, not this one).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "10a62de534be"
down_revision: str | None = "fa52b77ec442"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"
_TENANT_RLS_PREDICATE = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)


def _grant(*, table: str) -> str:
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
                EXECUTE format(
                    'GRANT SELECT, INSERT, UPDATE ON {_SCHEMA}.{table} TO %I', app_role
                );
            END IF;
        END
        $$;
    """


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{table}_isolation ON {_SCHEMA}.{table}
        USING ({_TENANT_RLS_PREDICATE})
    """)


def upgrade() -> None:
    op.create_table(
        "refresh_token",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.identity_user.id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.Uuid(), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_identity_refresh_token_hash"),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_identity_refresh_token_user",
        "refresh_token",
        ["user_id"],
        schema=_SCHEMA,
    )
    _enable_rls("refresh_token")
    op.execute(_grant(table="refresh_token"))

    op.create_table(
        "password_reset_token",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.identity_user.id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_identity_password_reset_token_hash"),
        schema=_SCHEMA,
    )
    _enable_rls("password_reset_token")
    op.execute(_grant(table="password_reset_token"))

    # -- Auth-bootstrap SECURITY DEFINER functions ---------------------------
    # Same reasoning as fa52b77ec442's identity_user functions: a refresh
    # token is presented *before* any tenant context can be established from
    # it (that's what redeeming it does), so its own RLS policy can't apply
    # yet either. `token_hash` is a SHA-256 of a 256-bit random value —
    # cryptographically unguessable, so an exact-hash-match lookup leaks
    # nothing by being tenant-unscoped; a wrong guess simply returns no row.
    op.execute(f"""
        CREATE FUNCTION {_SCHEMA}.auth_find_refresh_token_by_hash(p_token_hash text)
        RETURNS {_SCHEMA}.refresh_token
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_SCHEMA}, pg_temp
        AS $$
            SELECT * FROM {_SCHEMA}.refresh_token WHERE token_hash = p_token_hash;
        $$;
    """)
    # Upsert: `LoginUseCase`/`VerifyOtpUseCase` insert a new row;
    # `RefreshTokenUseCase` updates an existing one (rotation) and inserts
    # the replacement — both go through this one function.
    op.execute(f"""
        CREATE FUNCTION {_SCHEMA}.auth_save_refresh_token(
            p_id uuid,
            p_tenant_id uuid,
            p_user_id uuid,
            p_token_hash text,
            p_issued_at timestamptz,
            p_expires_at timestamptz,
            p_rotated_at timestamptz,
            p_revoked_at timestamptz,
            p_replaced_by_id uuid
        )
        RETURNS void
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_SCHEMA}, pg_temp
        AS $$
            INSERT INTO {_SCHEMA}.refresh_token (
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
    op.execute(f"""
        CREATE FUNCTION {_SCHEMA}.auth_revoke_all_refresh_tokens_for_user(p_user_id uuid)
        RETURNS void
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_SCHEMA}, pg_temp
        AS $$
            UPDATE {_SCHEMA}.refresh_token
            SET revoked_at = now()
            WHERE user_id = p_user_id AND revoked_at IS NULL;
        $$;
    """)
    op.execute(f"""
        CREATE FUNCTION {_SCHEMA}.auth_find_password_reset_token_by_hash(p_token_hash text)
        RETURNS {_SCHEMA}.password_reset_token
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_SCHEMA}, pg_temp
        AS $$
            SELECT * FROM {_SCHEMA}.password_reset_token WHERE token_hash = p_token_hash;
        $$;
    """)
    op.execute(f"""
        CREATE FUNCTION {_SCHEMA}.auth_save_password_reset_token(
            p_id uuid,
            p_tenant_id uuid,
            p_user_id uuid,
            p_token_hash text,
            p_expires_at timestamptz,
            p_used_at timestamptz
        )
        RETURNS void
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_SCHEMA}, pg_temp
        AS $$
            INSERT INTO {_SCHEMA}.password_reset_token (
                id, tenant_id, user_id, token_hash, expires_at, used_at
            )
            VALUES (p_id, p_tenant_id, p_user_id, p_token_hash, p_expires_at, p_used_at)
            ON CONFLICT (id) DO UPDATE SET used_at = EXCLUDED.used_at;
        $$;
    """)
    # PostgreSQL grants EXECUTE on a new function to PUBLIC by default — see
    # fa52b77ec442's identical note. Revoke before granting back explicitly.
    op.execute(
        f"REVOKE EXECUTE ON FUNCTION {_SCHEMA}.auth_find_refresh_token_by_hash(text) FROM PUBLIC"
    )
    op.execute(f"""
        REVOKE EXECUTE ON FUNCTION {_SCHEMA}.auth_save_refresh_token(
            uuid, uuid, uuid, text, timestamptz, timestamptz, timestamptz, timestamptz, uuid
        ) FROM PUBLIC
    """)
    op.execute(f"""
        REVOKE EXECUTE ON FUNCTION {_SCHEMA}.auth_revoke_all_refresh_tokens_for_user(uuid)
        FROM PUBLIC
    """)
    op.execute(f"""
        REVOKE EXECUTE ON FUNCTION {_SCHEMA}.auth_find_password_reset_token_by_hash(text)
        FROM PUBLIC
    """)
    op.execute(f"""
        REVOKE EXECUTE ON FUNCTION {_SCHEMA}.auth_save_password_reset_token(
            uuid, uuid, uuid, text, timestamptz, timestamptz
        ) FROM PUBLIC
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
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION '
                    '{_SCHEMA}.auth_find_refresh_token_by_hash(text) TO %I',
                    app_role
                );
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION {_SCHEMA}.auth_save_refresh_token('
                    'uuid, uuid, uuid, text, timestamptz, timestamptz, timestamptz, '
                    'timestamptz, uuid) TO %I',
                    app_role
                );
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION '
                    '{_SCHEMA}.auth_revoke_all_refresh_tokens_for_user(uuid) TO %I',
                    app_role
                );
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION '
                    '{_SCHEMA}.auth_find_password_reset_token_by_hash(text) TO %I',
                    app_role
                );
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION {_SCHEMA}.auth_save_password_reset_token('
                    'uuid, uuid, uuid, text, timestamptz, timestamptz) TO %I',
                    app_role
                );
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute(
        f"DROP FUNCTION IF EXISTS {_SCHEMA}.auth_save_password_reset_token("
        "uuid, uuid, uuid, text, timestamptz, timestamptz)"
    )
    op.execute(f"DROP FUNCTION IF EXISTS {_SCHEMA}.auth_find_password_reset_token_by_hash(text)")
    op.execute(f"DROP FUNCTION IF EXISTS {_SCHEMA}.auth_revoke_all_refresh_tokens_for_user(uuid)")
    op.execute(
        f"DROP FUNCTION IF EXISTS {_SCHEMA}.auth_save_refresh_token("
        "uuid, uuid, uuid, text, timestamptz, timestamptz, timestamptz, timestamptz, uuid)"
    )
    op.execute(f"DROP FUNCTION IF EXISTS {_SCHEMA}.auth_find_refresh_token_by_hash(text)")
    op.execute(
        f"DROP POLICY IF EXISTS rls_{_SCHEMA}_password_reset_token_isolation "
        f"ON {_SCHEMA}.password_reset_token"
    )
    op.drop_table("password_reset_token", schema=_SCHEMA)
    op.execute(
        f"DROP POLICY IF EXISTS rls_{_SCHEMA}_refresh_token_isolation ON {_SCHEMA}.refresh_token"
    )
    op.drop_table("refresh_token", schema=_SCHEMA)
