"""add platform console cross-tenant read functions

Revision ID: fdd3afde337c
Revises: f5746de5730e
Create Date: 2026-08-23

The Platform Console plan needs two things no existing `SECURITY DEFINER`
function in this codebase provides: an *authenticated, ongoing* cross-tenant
read (every prior function here — `license_find_by_tenant_id`,
`auth_find_user_by_email`, etc. — is a single pre-auth lookup by unique key,
never a table-wide read), and a genuine "list every tenant" capability,
which doesn't exist anywhere today.

Both `platform.license` and `tenant.tenant` are RLS-scoped by design (the
former verified against `platform.reference_number_sequence`'s precedent in
`92e48f9bf322`, the latter by `0242df1a3871`'s own policy on `id`) — a
`super_admin` session has no `tenant_id` at all, so `app.current_tenant_id`
is never set for it, and under normal RLS that matches *zero* rows, not
every row. `SqlAlchemyLicenseRepository.list_all()`
(`/admin/license` GET-all, soon `/platform/license`) has in fact always
been non-functional as a genuine "every tenant" read for exactly this
reason — RLS silently narrowed it to the caller's own tenant regardless of
caller.

Same trust boundary as every prior `SECURITY DEFINER` function here — narrow,
single-purpose, `REVOKE EXECUTE FROM PUBLIC` + an explicit grant to the
app role — just `SETOF`-returning instead of single-row, and callable
post-auth by a verified `super_admin` (`require_live_platform_permission`)
rather than pre-auth by unique key.

`tenant.tenant_find_status_by_id` is the third function here: a single-row
lookup mirroring `platform.license_find_by_tenant_id` exactly, backing
`RedisTenantStatusChecker`'s cache-miss fallback for the new tenant-
suspension enforcement check (parallel to, not merged with, the license
status check).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "fdd3afde337c"
down_revision: str | None = "f5746de5730e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLATFORM_SCHEMA = "platform"
_TENANT_SCHEMA = "tenant"


def _grant_execute(*, schema: str, function_signature: str) -> str:
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT USAGE ON SCHEMA {schema} TO %I', app_role);
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION {schema}.{function_signature} TO %I', app_role
                );
            END IF;
        END
        $$;
    """


def upgrade() -> None:
    op.execute(f"""
        CREATE FUNCTION {_PLATFORM_SCHEMA}.license_list_all()
        RETURNS SETOF {_PLATFORM_SCHEMA}.license
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_PLATFORM_SCHEMA}, pg_temp
        AS $$
            SELECT * FROM {_PLATFORM_SCHEMA}.license WHERE is_deleted IS FALSE;
        $$;
    """)
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_PLATFORM_SCHEMA}.license_list_all() FROM PUBLIC")
    op.execute(
        _grant_execute(schema=_PLATFORM_SCHEMA, function_signature="license_list_all()")
    )

    op.execute(f"""
        CREATE FUNCTION {_TENANT_SCHEMA}.tenant_list_all()
        RETURNS SETOF {_TENANT_SCHEMA}.tenant
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_TENANT_SCHEMA}, pg_temp
        AS $$
            SELECT * FROM {_TENANT_SCHEMA}.tenant WHERE is_deleted IS FALSE;
        $$;
    """)
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_TENANT_SCHEMA}.tenant_list_all() FROM PUBLIC")
    op.execute(_grant_execute(schema=_TENANT_SCHEMA, function_signature="tenant_list_all()"))

    op.execute(f"""
        CREATE FUNCTION {_TENANT_SCHEMA}.tenant_find_status_by_id(p_tenant_id uuid)
        RETURNS text
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_TENANT_SCHEMA}, pg_temp
        AS $$
            SELECT status FROM {_TENANT_SCHEMA}.tenant WHERE id = p_tenant_id;
        $$;
    """)
    op.execute(
        f"REVOKE EXECUTE ON FUNCTION {_TENANT_SCHEMA}.tenant_find_status_by_id(uuid) FROM PUBLIC"
    )
    op.execute(
        _grant_execute(schema=_TENANT_SCHEMA, function_signature="tenant_find_status_by_id(uuid)")
    )


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {_TENANT_SCHEMA}.tenant_find_status_by_id(uuid)")
    op.execute(f"DROP FUNCTION IF EXISTS {_TENANT_SCHEMA}.tenant_list_all()")
    op.execute(f"DROP FUNCTION IF EXISTS {_PLATFORM_SCHEMA}.license_list_all()")
