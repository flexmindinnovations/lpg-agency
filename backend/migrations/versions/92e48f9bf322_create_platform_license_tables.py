"""create platform.license, platform.license_feature_override, and
platform.linked_device tables

Revision ID: 92e48f9bf322
Revises: b8d4f1a9c6e3
Create Date: 2026-08-22 17:00:00.000000

Tenant license activation (see `lpg.domain.license.license`'s module
docstring for the full design).

**`platform.license` and `platform.linked_device` are normal RLS-scoped
tenant tables**, despite living in the `platform` schema — verified against
`platform.reference_number_sequence` (also `platform`-schema, also has a
`tenant_id` column, also RLS-scoped) rather than assumed from
`platform.feature_flag`'s different situation (which has no `tenant_id`
column at all, so RLS genuinely does not apply there). The `platform`
schema is a *persistence-location* convention here, never an RLS-exemption
signal on its own — `backend/scripts/verify_env_parity.sql` enforces this
mechanically for every table with a `tenant_id` column, regardless of schema.

That still leaves one genuine gap RLS can't close on its own:
`LoginUseCase`/`RefreshTokenUseCase` must read a tenant's license status
*before* any JWT/tenant context — and therefore before any
`app.current_tenant_id` session variable — exists. This is the exact
chicken-and-egg problem `identity.identity_user`'s own RLS policy already
has (see `fa52b77ec442`'s "Auth-bootstrap SECURITY DEFINER functions"
section) and it's solved the same way here: one narrow, unique-key-scoped
`SECURITY DEFINER` function (`platform.license_find_by_tenant_id`), not a
table-wide RLS bypass.

`platform.license_feature_override` has no `tenant_id` column (scoped via
`license_id` instead) and is therefore correctly outside RLS's scope
entirely — the same shape `identity.role_permission` already has.

No `CHECK` constraint on `plan_tier`/`app_type` — validated against a
code-defined catalog (`PLAN_TIER_FEATURE_CATALOG`/`RECOGNIZED_APP_TYPES`),
the same "fixed catalog in code, not in the database" choice
`tenant.tenant_configuration`'s `config_key` already makes, so a new tier or
app type never needs a migration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "92e48f9bf322"
down_revision: str | None = "b8d4f1a9c6e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLATFORM_SCHEMA = "platform"
_TENANT_SCHEMA = "tenant"
_TENANT_RLS_PREDICATE = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)


def _grant(*, table: str, privileges: str) -> str:
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT USAGE ON SCHEMA {_PLATFORM_SCHEMA} TO %I', app_role);
                EXECUTE format(
                    'GRANT {privileges} ON {_PLATFORM_SCHEMA}.{table} TO %I', app_role
                );
            END IF;
        END
        $$;
    """


def _grant_execute(*, function_signature: str) -> str:
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
                    'GRANT EXECUTE ON FUNCTION {_PLATFORM_SCHEMA}.{function_signature} TO %I',
                    app_role
                );
            END IF;
        END
        $$;
    """


def _full_audit_columns() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "license",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("key_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(length=20), nullable=False),
        sa.Column("plan_tier", sa.String(length=30), nullable=False),
        sa.Column("validity_period_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "device_caps",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_full_audit_columns(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        schema=_PLATFORM_SCHEMA,
    )
    op.execute(f"ALTER TABLE {_PLATFORM_SCHEMA}.license ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_PLATFORM_SCHEMA}.license FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_PLATFORM_SCHEMA}_license_isolation
        ON {_PLATFORM_SCHEMA}.license
        USING ({_TENANT_RLS_PREDICATE})
    """)
    op.execute(_grant(table="license", privileges="SELECT, INSERT, UPDATE"))

    op.create_table(
        "license_feature_override",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "license_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_PLATFORM_SCHEMA}.license.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feature_key", sa.String(length=100), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        *_full_audit_columns(),
        sa.UniqueConstraint(
            "license_id", "feature_key", name="uq_license_feature_override_license_feature"
        ),
        schema=_PLATFORM_SCHEMA,
    )
    # No tenant_id column (scoped via license_id instead) — genuinely
    # outside RLS's scope, the same shape identity.role_permission has.
    op.execute(_grant(table="license_feature_override", privileges="SELECT, INSERT, UPDATE"))

    op.create_table(
        "linked_device",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "license_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_PLATFORM_SCHEMA}.license.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("app_type", sa.String(length=30), nullable=False),
        sa.Column("device_identifier", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_full_audit_columns(),
        sa.UniqueConstraint(
            "tenant_id",
            "app_type",
            "device_identifier",
            name="uq_linked_device_tenant_app_identifier",
        ),
        schema=_PLATFORM_SCHEMA,
    )
    op.create_index(
        "idx_linked_device_tenant_app",
        "linked_device",
        ["tenant_id", "app_type"],
        schema=_PLATFORM_SCHEMA,
    )
    op.execute(f"ALTER TABLE {_PLATFORM_SCHEMA}.linked_device ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_PLATFORM_SCHEMA}.linked_device FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_PLATFORM_SCHEMA}_linked_device_isolation
        ON {_PLATFORM_SCHEMA}.linked_device
        USING ({_TENANT_RLS_PREDICATE})
    """)
    op.execute(_grant(table="linked_device", privileges="SELECT, INSERT, UPDATE"))

    # -- Pre-auth SECURITY DEFINER function ----------------------------------
    #
    # `platform.license`'s own RLS policy (above) requires
    # `app.current_tenant_id` to already be set — but the license status
    # check inside LoginUseCase/RefreshTokenUseCase runs *before* any tenant
    # context exists (the same chicken-and-egg problem `fa52b77ec442`'s
    # `auth_find_user_by_email` already solves for identity_user). One
    # narrow, unique-key-scoped SECURITY DEFINER function — never an
    # arbitrary query — moves the security boundary to "the exact shape of
    # this one function" rather than a table-wide bypass. `lpg_app` gets
    # EXECUTE only, never direct unscoped table access for this path.
    op.execute(f"""
        CREATE FUNCTION {_PLATFORM_SCHEMA}.license_find_by_tenant_id(p_tenant_id uuid)
        RETURNS {_PLATFORM_SCHEMA}.license
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_PLATFORM_SCHEMA}, pg_temp
        AS $$
            SELECT * FROM {_PLATFORM_SCHEMA}.license WHERE tenant_id = p_tenant_id;
        $$;
    """)
    op.execute(
        f"REVOKE EXECUTE ON FUNCTION {_PLATFORM_SCHEMA}.license_find_by_tenant_id(uuid) FROM PUBLIC"
    )
    op.execute(_grant_execute(function_signature="license_find_by_tenant_id(uuid)"))


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {_PLATFORM_SCHEMA}.license_find_by_tenant_id(uuid)")
    op.execute(
        f"DROP POLICY IF EXISTS rls_{_PLATFORM_SCHEMA}_linked_device_isolation "
        f"ON {_PLATFORM_SCHEMA}.linked_device"
    )
    op.drop_index(
        "idx_linked_device_tenant_app", table_name="linked_device", schema=_PLATFORM_SCHEMA
    )
    op.drop_table("linked_device", schema=_PLATFORM_SCHEMA)
    op.drop_table("license_feature_override", schema=_PLATFORM_SCHEMA)
    op.execute(
        f"DROP POLICY IF EXISTS rls_{_PLATFORM_SCHEMA}_license_isolation "
        f"ON {_PLATFORM_SCHEMA}.license"
    )
    op.drop_table("license", schema=_PLATFORM_SCHEMA)
