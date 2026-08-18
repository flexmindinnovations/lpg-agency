"""harden tenant.employee: grants, FORCE RLS, null-safe policy

`ca542bd9a61e` created `tenant.employee` and enabled RLS but never granted
anything to the application role, so every query against it failed with
"permission denied for table employee" — surfacing as a 500 on
`GET /api/v1/employees` (e.g. opening the Register Driver drawer). This is
an application-role privilege problem, not an RBAC one: the request passed
`require_permission("users:read")` and only then hit the database.

Three further deviations from the convention every other tenant table
follows are corrected here:

1. **No GRANT** — `lpg_app` could not SELECT/INSERT/UPDATE the table, and had
   no USAGE on `tenant.employee_code_seq`, so employee creation would have
   failed on `nextval` even once reads were fixed.
2. **`FORCE ROW LEVEL SECURITY` missing** — `tenant.branch` and
   `tenant.warehouse` both force it; without it the table owner silently
   bypasses tenant isolation.
3. **Policy predicate was not null-safe.** It used
   `(current_setting('app.current_tenant_id', true))::uuid`; when the setting
   is unset that yields `''`, and `''::uuid` *raises* rather than evaluating
   to NULL. Every other policy in this database uses the
   `NULLIF(current_setting(...), '')::uuid` form, which degrades to "no rows"
   instead of erroring on an unscoped connection (background jobs, event
   handlers).

Revision ID: b4d19e7c3a52
Revises: 8c221c3e0a91
Create Date: 2026-08-17
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b4d19e7c3a52"
down_revision: str | None = "8c221c3e0a91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "tenant"
_TABLE = "employee"
_SEQUENCE = "employee_code_seq"
_POLICY = "employee_tenant_isolation_policy"


def upgrade() -> None:
    # 1. Grants — same role-resolution idiom as 4f8b2d6a9c1e, so the migration
    #    is a no-op on a database where the app role does not exist.
    op.execute(f"""
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
                    'GRANT SELECT, INSERT, UPDATE ON {_SCHEMA}.{_TABLE} TO %I', app_role
                );
                EXECUTE format(
                    'GRANT USAGE, SELECT ON SEQUENCE {_SCHEMA}.{_SEQUENCE} TO %I', app_role
                );
            END IF;
        END
        $$;
    """)

    # 2. Force RLS so the table owner cannot bypass isolation either.
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY")

    # 3. Replace the policy with the null-safe predicate.
    op.execute(f"DROP POLICY IF EXISTS {_POLICY} ON {_SCHEMA}.{_TABLE}")
    op.execute(f"""
        CREATE POLICY {_POLICY} ON {_SCHEMA}.{_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS {_POLICY} ON {_SCHEMA}.{_TABLE}")
    op.execute(f"""
        CREATE POLICY {_POLICY} ON {_SCHEMA}.{_TABLE}
        FOR ALL
        TO PUBLIC
        USING (tenant_id = (current_setting('app.current_tenant_id', true))::uuid)
        WITH CHECK (tenant_id = (current_setting('app.current_tenant_id', true))::uuid)
    """)
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} NO FORCE ROW LEVEL SECURITY")

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
                    'REVOKE ALL ON {_SCHEMA}.{_TABLE} FROM %I', app_role
                );
                EXECUTE format(
                    'REVOKE ALL ON SEQUENCE {_SCHEMA}.{_SEQUENCE} FROM %I', app_role
                );
            END IF;
        END
        $$;
    """)
