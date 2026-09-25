"""add tenant.tenant_provision() SECURITY DEFINER function

Revision ID: d5b9e3a7f1c4
Revises: c4a8d6f2e9b3
Create Date: 2026-09-25 12:00:00.000000

Agency Provisioning (Phase 30): a Super Admin creating a new agency.

`tenant.tenant`'s RLS policy predicates on `id = app.current_tenant_id`, and
`0242df1a3871`'s docstring is explicit that this makes an INSERT impossible
through any tenant-scoped connection — before a tenant exists there is no
session context that could satisfy the check. That was correct for Phase 2
and is why provisioning was left as a seed operation; it is also why a
production database had no way to get its first agency.

Same resolution the Platform Console already uses for cross-tenant reads
(`fdd3afde337c`): a narrow, single-purpose `SECURITY DEFINER` function —
here an INSERT of exactly one row, nothing else — with `EXECUTE` revoked
from PUBLIC and granted only to the application role. It is reachable only
through the `/platform/*` dependency chain (a verified, live-checked
`super_admin`), never from a tenant-scoped route.

The `uq_tenant_slug` unique constraint is left to fire naturally: the caller
turns the resulting unique violation into a 409.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "d5b9e3a7f1c4"
down_revision: str | None = "c4a8d6f2e9b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SIGNATURE = "tenant_provision(uuid, text, text, text, text, text, text, uuid)"


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION tenant.tenant_provision(
            p_id uuid,
            p_name text,
            p_slug text,
            p_status text,
            p_subscription_plan text,
            p_primary_contact_email text,
            p_country text,
            p_created_by uuid
        )
        RETURNS void
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = tenant, pg_temp
        AS $$
            INSERT INTO tenant.tenant (
                id, name, slug, status, subscription_plan,
                primary_contact_email, country, created_by
            )
            VALUES (
                p_id, p_name, p_slug, p_status, p_subscription_plan,
                p_primary_contact_email, p_country, p_created_by
            );
        $$;
    """)
    op.execute(f"REVOKE EXECUTE ON FUNCTION tenant.{_SIGNATURE} FROM PUBLIC")
    op.execute(f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT USAGE ON SCHEMA tenant TO %I', app_role);
                EXECUTE format('GRANT EXECUTE ON FUNCTION tenant.{_SIGNATURE} TO %I', app_role);
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS tenant.{_SIGNATURE}")
