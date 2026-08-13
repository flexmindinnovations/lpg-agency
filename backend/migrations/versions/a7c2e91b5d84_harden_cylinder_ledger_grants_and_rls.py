"""harden cylinder ledger: grants and RLS

`d78833da654e` created the `cylinder_ledger` schema but issued no GRANTs and
enabled no row-level security, so:

- the application role could not read or write the schema at all
  ("permission denied for schema cylinder_ledger"), and
- nothing constrained a query to one tenant, which for a table holding every
  customer's outstanding cylinder balance is a cross-tenant data leak.

A separate migration rather than an edit to `d78833da654e`, because that
revision is already applied — applied revisions are never rewritten.

`ledger_transaction` is append-only (it is an audit trail of movements), so
the app role gets SELECT/INSERT and has UPDATE/DELETE revoked, matching
`inventory.inventory_transaction`. `cylinder_ledger` and its `cylinder_balance`
projection both carry mutable state, so they also get UPDATE.

All three tables carry `tenant_id` and so all three get the standard
null-safe RLS predicate.

Revision ID: a7c2e91b5d84
Revises: d78833da654e
Create Date: 2026-08-13
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a7c2e91b5d84"
down_revision: str | None = "d78833da654e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "cylinder_ledger"
_TABLES = ("cylinder_ledger", "cylinder_balance", "ledger_transaction")


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
                EXECUTE format('GRANT USAGE ON SCHEMA {_SCHEMA} TO %I', app_role);
                EXECUTE format(
                    'GRANT {privileges} ON {_SCHEMA}.{table} TO %I', app_role
                );
            END IF;
        END
        $$;
    """


def _revoke_mutation(*, table: str) -> str:
    """Append-only enforcement: SELECT/INSERT allowed, UPDATE/DELETE never."""
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
                    'REVOKE UPDATE, DELETE ON {_SCHEMA}.{table} FROM %I', app_role
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
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)


def upgrade() -> None:
    op.execute(_grant(table="cylinder_ledger", privileges="SELECT, INSERT, UPDATE"))
    op.execute(_grant(table="cylinder_balance", privileges="SELECT, INSERT, UPDATE, DELETE"))
    op.execute(_grant(table="ledger_transaction", privileges="SELECT, INSERT"))
    op.execute(_revoke_mutation(table="ledger_transaction"))

    for table in _TABLES:
        _enable_rls(table)


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{table}_isolation ON {_SCHEMA}.{table}")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} DISABLE ROW LEVEL SECURITY")

    op.execute("""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format(
                    'REVOKE ALL ON ALL TABLES IN SCHEMA cylinder_ledger FROM %I', app_role
                );
            END IF;
        END
        $$;
    """)
