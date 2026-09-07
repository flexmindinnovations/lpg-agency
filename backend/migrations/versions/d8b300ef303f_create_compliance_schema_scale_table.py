"""create compliance schema scale table

Revision ID: d8b300ef303f
Revises: d2e3f4051a6c
Create Date: 2026-09-07 17:02:57.991068

Delivers, for Weighment Part 1 (`planning/features/20-regulatory-compliance`
subsystem 1, MDG 2022 cl. 1.2):
  - `compliance` PostgreSQL schema — new bounded context
  - `compliance.scale` — the scale (weighing-instrument) registry: one row
    per working scale at a warehouse, with its calibration certificate and
    expiry. Mutable (a certificate gets renewed in place, matching
    `delivery.compliance_document`'s `replace()` idiom) — `GRANT SELECT,
    INSERT, UPDATE`, no append-only enforcement (that's `weighment_record`,
    added in a later migration once the goods-receipt/load-out capture use
    cases land).
  - Two new permission codes: `weighment:manage` (register/recalibrate a
    scale) and `weighment:record` (log a weighment check — not used by any
    table yet in this migration, added now so both permissions exist before
    the endpoints that need them land across two migrations, avoiding a
    second permission-grant migration for the same feature).

Follows `4f8b2d6a9c1e_create_inventory_schema.py`'s pattern (the newer,
preferred style: `op.create_table` + a shared `_standard_columns()` helper,
the null-safe `NULLIF(...)` RLS predicate, and the dynamic-role `_grant()`
helper) rather than `d2e3f4051a6c`'s raw-SQL style — but keeps that
migration's `ON CONFLICT`-based permission insert + `identity_user_permission`
backfill, which is the more defensive of the two patterns.

`warehouse_id` is a real FK to `tenant.warehouse.id` — matching
`inventory.goods_receipt_note.warehouse_id`, not `inventory_location`'s
polymorphic `location_ref_id` (a scale genuinely only ever lives at a
warehouse, never a vehicle, so there's no polymorphism to model).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "d8b300ef303f"
down_revision: str | None = "d2e3f4051a6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "compliance"
_TENANT_SCHEMA = "tenant"
_IDENTITY_SCHEMA = "identity"
_TABLE = "scale"

_SCALE_STATUSES = ("active", "inactive")

# MDG 2022 cl. 1.2(ii)(iii) — same figure as `domain/compliance/scale.py`'s
# `MAX_LEAST_COUNT_GRAMS`; kept in sync manually, there being no shared
# constant reachable from a migration.
_MAX_LEAST_COUNT_GRAMS = 10

_MANAGE_ROLES = ("agency_admin", "manager", "warehouse_staff")
_RECORD_ROLES = ("agency_admin", "manager", "warehouse_staff")


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
    # 1. Schema
    # ------------------------------------------------------------------
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ------------------------------------------------------------------
    # 2. compliance.scale
    # ------------------------------------------------------------------
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id"), nullable=False
        ),
        sa.Column(
            "warehouse_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.warehouse.id"),
            nullable=False,
        ),
        sa.Column("asset_tag", sa.String(length=100), nullable=False),
        sa.Column("make", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("least_count_grams", sa.Integer(), nullable=False),
        sa.Column("certificate_ref", sa.String(), nullable=False),
        sa.Column("certificate_expiry_date", sa.Date(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")
        ),
        *_standard_columns(),
        sa.CheckConstraint(f"status IN {_SCALE_STATUSES}", name="ck_compliance_scale_status"),
        sa.CheckConstraint(
            "least_count_grams > 0", name="ck_compliance_scale_least_count_positive"
        ),
        sa.CheckConstraint(
            f"least_count_grams <= {_MAX_LEAST_COUNT_GRAMS}",
            name="ck_compliance_scale_least_count_max",
        ),
        sa.UniqueConstraint(
            "tenant_id", "warehouse_id", "asset_tag", name="uq_compliance_scale_asset_tag"
        ),
        schema=_SCHEMA,
    )

    op.create_index(
        "idx_compliance_scale_warehouse",
        _TABLE,
        ["warehouse_id"],
        schema=_SCHEMA,
        postgresql_where=sa.text("NOT is_deleted"),
    )
    op.create_index(
        "idx_compliance_scale_certificate_expiry",
        _TABLE,
        ["certificate_expiry_date"],
        schema=_SCHEMA,
        postgresql_where=sa.text("NOT is_deleted"),
    )

    # ------------------------------------------------------------------
    # 3. Row-Level Security
    # ------------------------------------------------------------------
    _enable_rls(_TABLE)

    # ------------------------------------------------------------------
    # 4. Grants
    # ------------------------------------------------------------------
    op.execute(_grant(table=_TABLE, privileges="SELECT, INSERT, UPDATE"))

    # ------------------------------------------------------------------
    # 5. Permission codes — weighment:manage used by this migration's own
    #    endpoints; weighment:record is seeded now too (both land together)
    #    but not granted to any table until the goods-receipt/load-out
    #    capture migration.
    # ------------------------------------------------------------------
    op.execute(f"""
        INSERT INTO {_IDENTITY_SCHEMA}.permission (code, resource, action)
        VALUES
            ('weighment:manage', 'weighment', 'manage'),
            ('weighment:record', 'weighment', 'record')
        ON CONFLICT (code) DO NOTHING
    """)
    _grant_permission_to_roles("weighment:manage", _MANAGE_ROLES)
    _grant_permission_to_roles("weighment:record", _RECORD_ROLES)


def downgrade() -> None:
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.identity_user_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission
            WHERE code IN ('weighment:manage', 'weighment:record')
        )
    """)
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.role_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission
            WHERE code IN ('weighment:manage', 'weighment:record')
        )
    """)
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.permission
        WHERE code IN ('weighment:manage', 'weighment:record')
    """)

    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}")
    op.drop_table(_TABLE, schema=_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
