"""create payment table

R10 (`PaymentCollected`): `Invoice` gains `record_payment()`, supporting
partial payments — `status` only reaches `paid` once cumulative payments
equal `total_amount`, otherwise `partially_paid`. `INVOICE_STATUSES` has
included both since the invoice schema's first migration, but nothing has
ever transitioned an invoice into either state until now.

Append-only, like `accounting.cash_handover` (`c039189dfbdc`) and
`orders.order_status_history` — a payment is recorded once, never edited
or deleted; a wrong payment gets corrected by whatever refund workflow
`RefundApproved` (also R10) eventually enables, not by mutating this row.

`invoices:record_payment` reuses `b9248bf4b34f`'s exact role list for
`invoices:read` (`super_admin`, `agency_admin`, `manager`, `accountant`) —
the same staff who can already see invoices are the ones who record
payments against them.

Revision ID: 11ddf55a78ed
Revises: c039189dfbdc
Create Date: 2026-08-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "11ddf55a78ed"
down_revision: str | None = "c039189dfbdc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "accounting"
_TABLE = "payment"
_ROLES_SQL = "('super_admin', 'agency_admin', 'manager', 'accountant')"


def _grant(*, privileges: str) -> str:
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
                    'GRANT {privileges} ON {_SCHEMA}.{_TABLE} TO %I', app_role
                );
            END IF;
        END
        $$;
    """


def _revoke_mutation() -> str:
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
                    'REVOKE UPDATE, DELETE ON {_SCHEMA}.{_TABLE} FROM %I', app_role
                );
            END IF;
        END
        $$;
    """


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {_SCHEMA}.{_TABLE} (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenant.tenant(id) ON DELETE CASCADE,
            invoice_id uuid NOT NULL REFERENCES {_SCHEMA}.invoice(id) ON DELETE CASCADE,
            method text NOT NULL
                CHECK (method IN ('cash', 'upi', 'card', 'online_gateway', 'credit')),
            amount numeric(14, 2) NOT NULL CHECK (amount > 0),
            collected_by uuid NOT NULL,
            collected_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        f"CREATE INDEX idx_{_SCHEMA}_{_TABLE}_invoice ON {_SCHEMA}.{_TABLE} (invoice_id)"
    )

    op.execute(_grant(privileges="SELECT, INSERT"))
    op.execute(_revoke_mutation())

    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)

    op.execute("""
        INSERT INTO identity.permission (code, resource, action)
        VALUES ('invoices:record_payment', 'invoices', 'record_payment')
        ON CONFLICT (code) DO NOTHING
    """)

    op.execute(f"""
        INSERT INTO identity.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM identity.role r
        CROSS JOIN identity.permission p
        WHERE r.code IN {_ROLES_SQL}
          AND p.code = 'invoices:record_payment'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)

    # Backfill existing users of those roles — see f3c8a56d29e1's docstring
    # for why a role_permission-only grant applies to nobody who already
    # exists (permission resolution has been per-user only since 8c221c3e0a91).
    op.execute(f"""
        INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, p.id, now()
        FROM identity.identity_user u
        JOIN identity.permission p ON p.code = 'invoices:record_payment'
        WHERE u.role IN {_ROLES_SQL}
          AND NOT EXISTS (
              SELECT 1 FROM identity.identity_user_permission existing
              WHERE existing.user_id = u.id AND existing.permission_id = p.id
          )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM identity.identity_user_permission
        WHERE permission_id IN (
            SELECT id FROM identity.permission WHERE code = 'invoices:record_payment'
        )
    """)
    op.execute("""
        DELETE FROM identity.role_permission
        WHERE permission_id IN (
            SELECT id FROM identity.permission WHERE code = 'invoices:record_payment'
        )
    """)
    op.execute("DELETE FROM identity.permission WHERE code = 'invoices:record_payment'")

    op.execute(
        f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}"
    )
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} DISABLE ROW LEVEL SECURITY")
    op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.{_TABLE}")
