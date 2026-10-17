"""create online_payment table

Razorpay online payments (ADR-053). One row per payment-gateway attempt for
an order: a hosted payment link, its status (`created -> paid | expired |
cancelled`) and, once paid, the `accounting.payment` row it was applied to
on the order's invoice.

Unlike `accounting.payment` (append-only), this row is updated in place as
the gateway reports progress, so the app role gets `UPDATE` too. `DELETE`
stays revoked — an attempt is a financial record, never erased.

`provider_link_id` is unique: it is what webhooks are matched on.

`payments:create` lets a caller create or refresh a payment link. Granted to
`customer` (self-service, scoped to their own orders by the router) and to
the staff who already handle money: `super_admin`, `agency_admin`,
`manager`, `accountant`, `dispatcher`.

Revision ID: a9e4c7b2d1f6
Revises: e7d1a3c5f9b2
Create Date: 2026-10-17
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a9e4c7b2d1f6"
down_revision: str | None = "e7d1a3c5f9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "accounting"
_TABLE = "online_payment"
_PERMISSION = "payments:create"
_ROLES_SQL = "('super_admin', 'agency_admin', 'manager', 'accountant', 'dispatcher', 'customer')"


def _app_role_block(statement: str) -> str:
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
                EXECUTE format('{statement}', app_role);
            END IF;
        END
        $$;
    """


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {_SCHEMA}.{_TABLE} (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenant.tenant(id) ON DELETE CASCADE,
            order_id uuid NOT NULL REFERENCES orders."order"(id) ON DELETE CASCADE,
            customer_id uuid NOT NULL,
            invoice_id uuid REFERENCES {_SCHEMA}.invoice(id) ON DELETE SET NULL,
            amount numeric(14, 2) NOT NULL CHECK (amount > 0),
            currency text NOT NULL,
            provider text NOT NULL,
            provider_link_id text NOT NULL UNIQUE,
            short_url text NOT NULL,
            status text NOT NULL
                CHECK (status IN ('created', 'paid', 'expired', 'cancelled')),
            provider_payment_id text,
            payment_method text,
            paid_at timestamptz,
            applied_payment_id uuid,
            expires_at timestamptz,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            version integer NOT NULL DEFAULT 1
        )
    """)
    op.execute(f"CREATE INDEX idx_{_SCHEMA}_{_TABLE}_order ON {_SCHEMA}.{_TABLE} (order_id)")

    op.execute(_app_role_block(f"GRANT SELECT, INSERT, UPDATE ON {_SCHEMA}.{_TABLE} TO %I"))
    op.execute(_app_role_block(f"REVOKE DELETE ON {_SCHEMA}.{_TABLE} FROM %I"))

    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)

    op.execute(f"""
        INSERT INTO identity.permission (code, resource, action)
        VALUES ('{_PERMISSION}', 'payments', 'create')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute(f"""
        INSERT INTO identity.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM identity.role r
        CROSS JOIN identity.permission p
        WHERE r.code IN {_ROLES_SQL}
          AND p.code = '{_PERMISSION}'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)
    # Backfill existing users of those roles — permission resolution is
    # per-user (see f3c8a56d29e1's docstring), so a role grant alone reaches
    # nobody who already exists.
    op.execute(f"""
        INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, p.id, now()
        FROM identity.identity_user u
        JOIN identity.permission p ON p.code = '{_PERMISSION}'
        WHERE u.role IN {_ROLES_SQL}
          AND NOT EXISTS (
              SELECT 1 FROM identity.identity_user_permission existing
              WHERE existing.user_id = u.id AND existing.permission_id = p.id
          )
    """)


def downgrade() -> None:
    for table in ("identity_user_permission", "role_permission"):
        op.execute(f"""
            DELETE FROM identity.{table}
            WHERE permission_id IN (
                SELECT id FROM identity.permission WHERE code = '{_PERMISSION}'
            )
        """)
    op.execute(f"DELETE FROM identity.permission WHERE code = '{_PERMISSION}'")
    op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.{_TABLE}")
