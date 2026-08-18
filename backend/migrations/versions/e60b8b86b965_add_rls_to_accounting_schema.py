"""add rls to accounting schema

Revision ID: e60b8b86b965
Revises: de95b5bcc7de
Create Date: 2026-08-13 18:20:30.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = 'e60b8b86b965'
down_revision: str | None = 'de95b5bcc7de'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "accounting"


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


def upgrade() -> None:
    op.execute(_grant(table="invoice", privileges="SELECT, INSERT"))
    op.execute(_revoke_mutation(table="invoice"))

    op.execute(_grant(table="invoice_line", privileges="SELECT, INSERT"))
    op.execute(_revoke_mutation(table="invoice_line"))

    _enable_rls("invoice")
    _enable_rls("invoice_line")

    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_invoice_isolation ON {_SCHEMA}.invoice
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)

    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_invoice_line_isolation ON {_SCHEMA}.invoice_line
        USING (
            EXISTS (
                SELECT 1 FROM {_SCHEMA}.invoice i
                WHERE i.id = invoice_id
                AND i.tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
        )
    """)


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_invoice_line_isolation ON {_SCHEMA}.invoice_line")
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_invoice_isolation ON {_SCHEMA}.invoice")

    op.execute(f"ALTER TABLE {_SCHEMA}.invoice_line NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.invoice_line DISABLE ROW LEVEL SECURITY")

    op.execute(f"ALTER TABLE {_SCHEMA}.invoice NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.invoice DISABLE ROW LEVEL SECURITY")

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
                    'REVOKE ALL ON ALL TABLES IN SCHEMA accounting FROM %I', app_role
                );
            END IF;
        END
        $$;
    """)
