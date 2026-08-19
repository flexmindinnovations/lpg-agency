"""create credit_note table

R10 (`RefundApproved`): a refund request/approval workflow, tracked as its
own aggregate rather than nested inside `Invoice` — the request and the
approval are two separate HTTP requests, often by two different actors,
the same reasoning `orders.cancellation_record` (`7c3f1a9e2b4d`) is a
standalone table rather than an in-aggregate pending record.

Unlike `accounting.cash_handover`/`payment` (append-only), this table is
mutated exactly once, by approval — same shape as
`orders.cancellation_record`, which documents the identical pattern.
`UPDATE` is granted (not revoked) for that reason; `DELETE` stays revoked.

`credit_notes:request` reuses `11ddf55a78ed`'s role list for
`invoices:record_payment` (`super_admin`, `agency_admin`, `manager`,
`accountant`). `credit_notes:approve` is narrower —
`super_admin`, `agency_admin`, `manager` only, excluding `accountant` —
mirroring `orders:cancel_approve`'s request-vs-approve split (BR-20).

Revision ID: bdd1f778c21a
Revises: 6ae4682bd49d
Create Date: 2026-08-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "bdd1f778c21a"
down_revision: str | None = "6ae4682bd49d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "accounting"
_TABLE = "credit_note"
_REQUEST_ROLES_SQL = "('super_admin', 'agency_admin', 'manager', 'accountant')"
_APPROVE_ROLES_SQL = "('super_admin', 'agency_admin', 'manager')"


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


def _revoke_delete() -> str:
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('REVOKE DELETE ON {_SCHEMA}.{_TABLE} FROM %I', app_role);
            END IF;
        END
        $$;
    """


def _grant_permission(*, code: str, resource: str, action: str, roles_sql: str) -> None:
    op.execute(f"""
        INSERT INTO identity.permission (code, resource, action)
        VALUES ('{code}', '{resource}', '{action}')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute(f"""
        INSERT INTO identity.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM identity.role r
        CROSS JOIN identity.permission p
        WHERE r.code IN {roles_sql}
          AND p.code = '{code}'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)
    # Backfill existing users of those roles — see f3c8a56d29e1's docstring
    # for why a role_permission-only grant applies to nobody who already
    # exists (permission resolution has been per-user only since 8c221c3e0a91).
    op.execute(f"""
        INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, p.id, now()
        FROM identity.identity_user u
        JOIN identity.permission p ON p.code = '{code}'
        WHERE u.role IN {roles_sql}
          AND NOT EXISTS (
              SELECT 1 FROM identity.identity_user_permission existing
              WHERE existing.user_id = u.id AND existing.permission_id = p.id
          )
    """)


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {_SCHEMA}.{_TABLE} (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenant.tenant(id) ON DELETE CASCADE,
            invoice_id uuid NOT NULL REFERENCES {_SCHEMA}.invoice(id) ON DELETE CASCADE,
            amount numeric(14, 2) NOT NULL CHECK (amount > 0),
            reason text NOT NULL,
            requested_by uuid NOT NULL,
            requested_at timestamptz NOT NULL,
            approved_by uuid NULL,
            approved_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK ((approved_by IS NOT NULL) = (approved_at IS NOT NULL))
        )
    """)
    op.execute(
        f"CREATE INDEX idx_{_SCHEMA}_{_TABLE}_invoice ON {_SCHEMA}.{_TABLE} (invoice_id)"
    )

    op.execute(_grant(privileges="SELECT, INSERT, UPDATE"))
    op.execute(_revoke_delete())

    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)

    _grant_permission(
        code="credit_notes:request",
        resource="credit_notes",
        action="request",
        roles_sql=_REQUEST_ROLES_SQL,
    )
    _grant_permission(
        code="credit_notes:approve",
        resource="credit_notes",
        action="approve",
        roles_sql=_APPROVE_ROLES_SQL,
    )


def downgrade() -> None:
    for code in ("credit_notes:request", "credit_notes:approve"):
        op.execute(f"""
            DELETE FROM identity.identity_user_permission
            WHERE permission_id IN (SELECT id FROM identity.permission WHERE code = '{code}')
        """)
        op.execute(f"""
            DELETE FROM identity.role_permission
            WHERE permission_id IN (SELECT id FROM identity.permission WHERE code = '{code}')
        """)
        op.execute(f"DELETE FROM identity.permission WHERE code = '{code}'")

    op.execute(
        f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}"
    )
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} DISABLE ROW LEVEL SECURITY")
    op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.{_TABLE}")
