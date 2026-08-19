"""create cash_handover table

R10 (`CashShortfallDeclared`): a driver declares the cash they're handing
over at the end of a route; `expected_amount` is computed from real COD
delivery data (`orders.proof_of_delivery.amount_collected` for
`payment_method = 'cash'` stops on that route), not entered by hand.
Append-only — a handover is a one-time declaration, never edited or
withdrawn, same reasoning as `orders.order_status_history` and
`orders.failed_delivery_record`.

`cash_handovers:declare` is new — driver-initiated in the common case, but
also usable by dispatcher/manager/agency_admin during reconciliation
review. No separate "own driver only" scoping is enforced at this
permission level (unlike the driver-ownership checks Order's endpoints do)
— deliberately kept simple for a first cut; narrowing to self-only for the
`driver` role is a reasonable follow-up, not attempted here.

Revision ID: c039189dfbdc
Revises: 76aa61425c66
Create Date: 2026-08-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "c039189dfbdc"
down_revision: str | None = "76aa61425c66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "accounting"
_TABLE = "cash_handover"
_ROLES_SQL = "('driver', 'dispatcher', 'manager', 'agency_admin')"


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
            driver_id uuid NOT NULL REFERENCES delivery.driver(id) ON DELETE CASCADE,
            route_id uuid NOT NULL REFERENCES delivery.route(id) ON DELETE CASCADE,
            expected_amount numeric(12, 2) NOT NULL CHECK (expected_amount >= 0),
            actual_amount numeric(12, 2) NOT NULL CHECK (actual_amount >= 0),
            declared_by uuid NOT NULL,
            declared_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        f"CREATE INDEX idx_{_SCHEMA}_{_TABLE}_tenant_driver "
        f"ON {_SCHEMA}.{_TABLE} (tenant_id, driver_id)"
    )
    op.execute(
        f"CREATE INDEX idx_{_SCHEMA}_{_TABLE}_route ON {_SCHEMA}.{_TABLE} (route_id)"
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
        VALUES ('cash_handovers:declare', 'cash_handovers', 'declare')
        ON CONFLICT (code) DO NOTHING
    """)

    op.execute(f"""
        INSERT INTO identity.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM identity.role r
        CROSS JOIN identity.permission p
        WHERE r.code IN {_ROLES_SQL}
          AND p.code = 'cash_handovers:declare'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)

    # Backfill existing users of those roles — see f3c8a56d29e1's docstring
    # for why a role_permission-only grant applies to nobody who already
    # exists (permission resolution has been per-user only since 8c221c3e0a91).
    op.execute(f"""
        INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, p.id, now()
        FROM identity.identity_user u
        JOIN identity.permission p ON p.code = 'cash_handovers:declare'
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
            SELECT id FROM identity.permission WHERE code = 'cash_handovers:declare'
        )
    """)
    op.execute("""
        DELETE FROM identity.role_permission
        WHERE permission_id IN (
            SELECT id FROM identity.permission WHERE code = 'cash_handovers:declare'
        )
    """)
    op.execute("DELETE FROM identity.permission WHERE code = 'cash_handovers:declare'")

    op.execute(
        f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}"
    )
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} DISABLE ROW LEVEL SECURITY")
    op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.{_TABLE}")
