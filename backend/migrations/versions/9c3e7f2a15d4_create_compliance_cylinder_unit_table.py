"""create compliance cylinder unit table

Revision ID: 9c3e7f2a15d4
Revises: c7f4a2e9b6d1
Create Date: 2026-09-08 00:00:00.000000

Delivers Cylinder Identity (`planning/features/20-regulatory-compliance`
subsystem 3, PLAN.md's own words: "the deepest schema change here"):
  - `compliance.cylinder_unit` — one row per individually identified
    cylinder: serial, tenant-catalog type, manufacture date, owner OMC,
    condition status (the same vocabulary `inventory.inventory_location`
    already uses, but tracked per-unit here instead of as a bulk count),
    polymorphic custody (`warehouse`/`vehicle`/`customer`/`bottling_plant`
    — a unit can be at a customer's premises, which `inventory_location`
    cannot model at all today), and the two fields that make Rule 26 (Gas
    Cylinders Rules 2016) and MDG 2022 cl. 1.4(b) evidenceable:
    `last_tested_at`/`test_due_date`.
  - Two new permission codes: `cylinder_units:manage` (register/test/
    custody/condition/receive/retire) and `cylinder_units:read` (registry
    visibility — deliberately wider, includes `dispatcher`, since dispatch
    staff plausibly want visibility into due-for-test units even though
    the route-level load-out gate itself is deferred to a future slice —
    see ADR-042).

Mutable (a unit's condition/custody/test dates change many times over its
life) — `GRANT SELECT, INSERT, UPDATE`, matching `compliance.scale`'s own
grant shape (`d8b300ef303f`), not `weighment_record`'s append-only
`REVOKE UPDATE, DELETE` pattern. Does **not** create the `compliance`
schema (already exists) or drop it on downgrade (siblings `scale`/
`weighment_record` would break) — same second-migration pattern
`6a7d486aa8ec` already established.

`cylinder_type_id` is a real FK to `tenant.cylinder_type.id`, mirroring the
live FK `compliance.weighment_record.cylinder_type_id` already establishes.
`custody_ref_id` is intentionally NOT an FK — it polymorphically points at
`tenant.warehouse`/`delivery.vehicle`/`customer.customer`/nothing
(`bottling_plant`), the same accepted-risk convention
`inventory.inventory_location.location_ref_id` and
`compliance.weighment_record.reference_id` already use, mitigated at the
application layer, not the database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "9c3e7f2a15d4"
down_revision: str | None = "c7f4a2e9b6d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "compliance"
_TENANT_SCHEMA = "tenant"
_IDENTITY_SCHEMA = "identity"
_TABLE = "cylinder_unit"

# Same vocabulary as `domain.inventory.inventory_location.CYLINDER_STATUSES`
# — kept in sync manually, there being no shared constant reachable from a
# migration (same caveat `d8b300ef303f`'s own `_MAX_LEAST_COUNT_GRAMS` makes).
_CONDITION_STATUSES = ("filled", "empty", "damaged", "leakage", "quarantine", "repair", "scrap")
_CUSTODY_TYPES = ("warehouse", "vehicle", "customer", "bottling_plant")

_MANAGE_ROLES = ("agency_admin", "manager", "warehouse_staff")
_READ_ROLES = ("agency_admin", "manager", "warehouse_staff", "dispatcher")


def _standard_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    ]


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


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{table}_isolation ON {_SCHEMA}.{table}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)


def _grant_permission_to_roles(permission_code: str, role_codes: tuple[str, ...]) -> None:
    roles_sql = "(" + ", ".join(f"'{r}'" for r in role_codes) + ")"
    op.execute(f"""
        INSERT INTO {_IDENTITY_SCHEMA}.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM {_IDENTITY_SCHEMA}.role r
        CROSS JOIN {_IDENTITY_SCHEMA}.permission p
        WHERE r.code IN {roles_sql}
          AND p.code = '{permission_code}'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)
    op.execute(f"""
        INSERT INTO {_IDENTITY_SCHEMA}.identity_user_permission
            (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, p.id, now()
        FROM {_IDENTITY_SCHEMA}.identity_user u
        JOIN {_IDENTITY_SCHEMA}.permission p ON p.code = '{permission_code}'
        WHERE u.role IN {roles_sql}
          AND NOT EXISTS (
              SELECT 1 FROM {_IDENTITY_SCHEMA}.identity_user_permission existing
              WHERE existing.user_id = u.id AND existing.permission_id = p.id
          )
    """)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. compliance.cylinder_unit
    # ------------------------------------------------------------------
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id"), nullable=False
        ),
        sa.Column(
            "cylinder_type_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.cylinder_type.id"),
            nullable=False,
        ),
        sa.Column("serial_number", sa.String(length=100), nullable=False),
        sa.Column("manufacture_date", sa.Date(), nullable=True),
        sa.Column("owner_omc", sa.String(length=100), nullable=True),
        sa.Column("condition_status", sa.String(length=20), nullable=False),
        sa.Column("custody_type", sa.String(length=20), nullable=False),
        sa.Column("custody_ref_id", sa.Uuid(), nullable=True),
        sa.Column("last_tested_at", sa.Date(), nullable=True),
        sa.Column("test_due_date", sa.Date(), nullable=True),
        sa.Column("is_retired", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_standard_columns(),
        sa.CheckConstraint(
            f"condition_status IN {_CONDITION_STATUSES}",
            name="ck_compliance_cylinder_unit_condition_status",
        ),
        sa.CheckConstraint(
            f"custody_type IN {_CUSTODY_TYPES}", name="ck_compliance_cylinder_unit_custody_type"
        ),
        sa.CheckConstraint(
            "(custody_type = 'bottling_plant') = (custody_ref_id IS NULL)",
            name="ck_compliance_cylinder_unit_custody_ref_consistency",
        ),
        sa.UniqueConstraint(
            "tenant_id", "serial_number", name="uq_compliance_cylinder_unit_serial"
        ),
        schema=_SCHEMA,
    )

    op.create_index(
        "idx_compliance_cylinder_unit_test_due_date",
        _TABLE,
        ["test_due_date"],
        schema=_SCHEMA,
        postgresql_where=sa.text("NOT is_deleted AND NOT is_retired"),
    )
    op.create_index(
        "idx_compliance_cylinder_unit_custody",
        _TABLE,
        ["custody_type", "custody_ref_id"],
        schema=_SCHEMA,
        postgresql_where=sa.text("NOT is_deleted"),
    )
    op.create_index(
        "idx_compliance_cylinder_unit_cylinder_type",
        _TABLE,
        ["cylinder_type_id"],
        schema=_SCHEMA,
        postgresql_where=sa.text("NOT is_deleted"),
    )

    # ------------------------------------------------------------------
    # 2. Row-Level Security
    # ------------------------------------------------------------------
    _enable_rls(_TABLE)

    # ------------------------------------------------------------------
    # 3. Grants
    # ------------------------------------------------------------------
    op.execute(_grant(table=_TABLE, privileges="SELECT, INSERT, UPDATE"))

    # ------------------------------------------------------------------
    # 4. Permission codes
    # ------------------------------------------------------------------
    op.execute(f"""
        INSERT INTO {_IDENTITY_SCHEMA}.permission (code, resource, action)
        VALUES
            ('cylinder_units:manage', 'cylinder_units', 'manage'),
            ('cylinder_units:read', 'cylinder_units', 'read')
        ON CONFLICT (code) DO NOTHING
    """)
    _grant_permission_to_roles("cylinder_units:manage", _MANAGE_ROLES)
    _grant_permission_to_roles("cylinder_units:read", _READ_ROLES)


def downgrade() -> None:
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.identity_user_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission
            WHERE code IN ('cylinder_units:manage', 'cylinder_units:read')
        )
    """)
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.role_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission
            WHERE code IN ('cylinder_units:manage', 'cylinder_units:read')
        )
    """)
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.permission
        WHERE code IN ('cylinder_units:manage', 'cylinder_units:read')
    """)

    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}")
    op.drop_table(_TABLE, schema=_SCHEMA)
