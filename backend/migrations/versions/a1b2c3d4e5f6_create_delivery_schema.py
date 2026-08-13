"""create delivery schema: driver and vehicle tables with RLS and permissions

Revision ID: a1b2c3d4e5f6
Revises: c9a1e6b4f7d3
Create Date: 2026-08-10 22:00:00.000000

Delivers:
  - `delivery` PostgreSQL schema
  - `delivery.driver` table with RLS
  - `delivery.vehicle` table with RLS
  - Four permission codes: drivers:read, drivers:manage, vehicles:read, vehicles:manage
  - Role grants matching docs/data/17-api-security.md §6

Phase 9 scope only — route/route_stop/proof_of_delivery arrive in a later phase.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str = "c9a1e6b4f7d3"
branch_labels: None = None
depends_on: None = None

_DELIVERY_SCHEMA = "delivery"
_IDENTITY_SCHEMA = "identity"

_NEW_PERMISSIONS = [
    "drivers:read",
    "drivers:manage",
    "vehicles:read",
    "vehicles:manage",
]

# Roles that get :manage access (includes :read implicitly via the matrix below)
_MANAGE_ROLES = ["super_admin", "agency_admin", "manager", "dispatcher"]
# Roles that get :read only
_READ_ONLY_ROLES = ["warehouse_staff", "accountant", "driver"]

_NEW_ROLE_PERMISSION_MATRIX: list[tuple[str, list[str]]] = [
    ("drivers:read", _MANAGE_ROLES + _READ_ONLY_ROLES),
    ("drivers:manage", _MANAGE_ROLES),
    ("vehicles:read", _MANAGE_ROLES + _READ_ONLY_ROLES),
    ("vehicles:manage", _MANAGE_ROLES),
]


def _grant(*, table: str, privileges: str) -> str:
    """Dynamic role-detection grant block for PostgreSQL permission assignment."""
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT USAGE ON SCHEMA {_DELIVERY_SCHEMA} TO %I', app_role);
                EXECUTE format(
                    'GRANT {privileges} ON {_DELIVERY_SCHEMA}.{table} TO %I', app_role
                );
            END IF;
        END
        $$;
    """


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create delivery schema
    # ------------------------------------------------------------------
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_DELIVERY_SCHEMA}")

    # ------------------------------------------------------------------
    # 2. delivery.driver
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE delivery.driver (
            id                  uuid        NOT NULL DEFAULT gen_random_uuid(),
            tenant_id           uuid        NOT NULL REFERENCES tenant.tenant(id) ON DELETE CASCADE,
            branch_id           uuid        NOT NULL REFERENCES tenant.branch(id) ON DELETE CASCADE,
            identity_user_id    uuid,
            employee_code       text        NOT NULL,
            license_number      text        NOT NULL,
            license_expiry_date date,
            status              text        NOT NULL DEFAULT 'active'
                                CONSTRAINT ck_driver_status
                                CHECK (status IN ('active','on_leave','inactive')),
            created_at          timestamptz NOT NULL DEFAULT now(),
            created_by          uuid,
            updated_at          timestamptz NOT NULL DEFAULT now(),
            updated_by          uuid,
            is_deleted          boolean     NOT NULL DEFAULT false,
            deleted_at          timestamptz,
            deleted_by          uuid,
            version             integer     NOT NULL DEFAULT 1,
            CONSTRAINT pk_driver PRIMARY KEY (id),
            CONSTRAINT uq_driver_tenant_employee_code UNIQUE (tenant_id, employee_code)
        )
    """)

    # ------------------------------------------------------------------
    # 3. delivery.vehicle
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE delivery.vehicle (
            id                  uuid        NOT NULL DEFAULT gen_random_uuid(),
            tenant_id           uuid        NOT NULL REFERENCES tenant.tenant(id) ON DELETE CASCADE,
            branch_id           uuid        NOT NULL REFERENCES tenant.branch(id) ON DELETE CASCADE,
            registration_number text        NOT NULL,
            make                text        NOT NULL,
            model               text        NOT NULL,
            ownership_type      text        NOT NULL DEFAULT 'owned'
                                CONSTRAINT ck_vehicle_ownership CHECK (
                                    ownership_type IN ('owned','third_party','rental','gig')
                                ),
            capacity_units      integer     NOT NULL
                                CONSTRAINT ck_vehicle_capacity CHECK (capacity_units > 0),
            status              text        NOT NULL DEFAULT 'active'
                                CONSTRAINT ck_vehicle_status
                                CHECK (status IN ('active','maintenance','inactive')),
            created_at          timestamptz NOT NULL DEFAULT now(),
            created_by          uuid,
            updated_at          timestamptz NOT NULL DEFAULT now(),
            updated_by          uuid,
            is_deleted          boolean     NOT NULL DEFAULT false,
            deleted_at          timestamptz,
            deleted_by          uuid,
            version             integer     NOT NULL DEFAULT 1,
            CONSTRAINT pk_vehicle PRIMARY KEY (id),
            CONSTRAINT uq_vehicle_tenant_registration UNIQUE (tenant_id, registration_number)
        )
    """)

    # ------------------------------------------------------------------
    # 4. Indexes
    # ------------------------------------------------------------------
    op.execute(
        "CREATE INDEX idx_driver_tenant_status ON delivery.driver (tenant_id, status) "
        "WHERE is_deleted = false"
    )
    op.execute(
        "CREATE INDEX idx_driver_tenant_branch ON delivery.driver (tenant_id, branch_id) "
        "WHERE is_deleted = false"
    )
    op.execute(
        "CREATE INDEX idx_vehicle_tenant_status ON delivery.vehicle (tenant_id, status) "
        "WHERE is_deleted = false"
    )

    # ------------------------------------------------------------------
    # 5. Row-Level Security
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE delivery.driver ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE delivery.vehicle ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE delivery.driver FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE delivery.vehicle FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY tenant_isolation_driver ON delivery.driver
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_vehicle ON delivery.vehicle
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)

    # ------------------------------------------------------------------
    # 6. Apply Grants to lpg_app / lpg_app_uat
    # ------------------------------------------------------------------
    op.execute(_grant(table="driver", privileges="SELECT, INSERT, UPDATE"))
    op.execute(_grant(table="vehicle", privileges="SELECT, INSERT, UPDATE"))

    # ------------------------------------------------------------------
    # 7. Permission codes — exact same pattern as c9a1e6b4f7d3
    # ------------------------------------------------------------------
    permission_table = sa.table(
        "permission",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        schema=_IDENTITY_SCHEMA,
    )
    permission_ids = {code: uuid.uuid4() for code in _NEW_PERMISSIONS}
    op.bulk_insert(
        permission_table,
        [
            {
                "id": permission_ids[code],
                "code": code,
                "resource": code.split(":")[0],
                "action": code.split(":")[1],
            }
            for code in _NEW_PERMISSIONS
        ],
    )

    # ------------------------------------------------------------------
    # 8. Role grants
    # ------------------------------------------------------------------
    for permission_code, role_codes in _NEW_ROLE_PERMISSION_MATRIX:
        for role_code in role_codes:
            op.execute(
                sa.text(f"""
                    INSERT INTO {_IDENTITY_SCHEMA}.role_permission
                        (id, role_id, permission_id, created_at)
                    SELECT gen_random_uuid(), r.id, :permission_id, now()
                    FROM {_IDENTITY_SCHEMA}.role r
                    WHERE r.code = :role_code
                """).bindparams(
                    permission_id=permission_ids[permission_code],
                    role_code=role_code,
                )
            )


def downgrade() -> None:
    codes_literal = ", ".join(f"'{code}'" for code in _NEW_PERMISSIONS)
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.role_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission WHERE code IN ({codes_literal})
        )
    """)
    op.execute(f"DELETE FROM {_IDENTITY_SCHEMA}.permission WHERE code IN ({codes_literal})")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_driver ON delivery.driver")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_vehicle ON delivery.vehicle")
    op.execute("DROP TABLE IF EXISTS delivery.vehicle")
    op.execute("DROP TABLE IF EXISTS delivery.driver")
    op.execute("DROP SCHEMA IF EXISTS delivery CASCADE")
