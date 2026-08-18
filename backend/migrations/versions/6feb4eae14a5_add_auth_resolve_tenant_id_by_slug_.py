"""Add auth_resolve_tenant_id_by_slug SECURITY DEFINER function

Revision ID: 6feb4eae14a5
Revises: 1f25cb7394d7
Create Date: 2026-08-15 12:32:40.569533

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = '6feb4eae14a5'
down_revision: str | None = '1f25cb7394d7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A SECURITY DEFINER function to allow the unauthenticated auth flow to look up
    # a tenant's UUID by its slug. This bypasses the RLS on tenant.tenant which
    # otherwise hides all rows when app.current_tenant_id is not set.
    op.execute("""
        CREATE FUNCTION tenant.auth_resolve_tenant_id_by_slug(p_slug text)
        RETURNS uuid
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = tenant, pg_temp
        AS $$
            SELECT id FROM tenant.tenant
            WHERE slug = p_slug AND is_deleted = false;
        $$;
    """)
    # lpg_app gets EXECUTE only
    op.execute("""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT EXECUTE ON FUNCTION tenant.auth_resolve_tenant_id_by_slug(text) TO %I', app_role);
            END IF;
        END
        $$;
    """)

def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS tenant.auth_resolve_tenant_id_by_slug(text)")
