"""create inventory schema: location, balance, transaction, GRN, reconciliation

Revision ID: 4f8b2d6a9c1e
Revises: e68103c56ad7
Create Date: 2026-08-11 09:00:00.000000

Delivers:
  - `inventory` PostgreSQL schema
  - `inventory.inventory_location` — one row per warehouse/vehicle (polymorphic
    `location_ref_id`, no physical FK — accepted risk per
    `docs/data/03-database-schema.md`, mitigated at the application layer)
  - `inventory.inventory_balance` — materialized `(location, cylinder_type,
    status) -> quantity` projection, kept in lockstep with
    `inventory_transaction` by the repository writing both in one flush
  - `inventory.inventory_transaction` — append-only ledger (no standard audit
    columns, matching `audit.audit_log`'s precedent; UPDATE/DELETE revoked
    from the app role). Includes a `reason` column (not in the literal doc
    table list) so `POST .../adjustments`' documented `reason` field has
    somewhere durable to land, matching BR-14's mandatory-audit requirement.
  - `inventory.goods_receipt_note` and `inventory.reconciliation_record`
  - One new permission code, `inventory:read`, plus its role grants.
    `inventory:load`, `inventory:adjust` and `reconciliation:approve` were
    already seeded as codes in `fa52b77ec442` (Phase 6); `inventory:adjust`
    and `reconciliation:approve` even already carry grants there matching
    `docs/data/17-api-security.md` §6 exactly — this migration only adds
    `inventory:load`'s missing grants (it had none) and `inventory:read`'s,
    without duplicating what already exists

RLS uses the null-safe predicate (`NULLIF(..., true)`) from
`d4f9a2b8e1c6_create_tenant_cylinder_type.py` rather than Phase 9's plainer
variant — doesn't error when the session var is unset.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "4f8b2d6a9c1e"
down_revision: str | None = "e68103c56ad7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "inventory"
_TENANT_SCHEMA = "tenant"
_IDENTITY_SCHEMA = "identity"

_LOCATION_TYPES = ("warehouse", "vehicle")
_CYLINDER_STATUSES = ("filled", "empty", "damaged", "leakage", "quarantine", "repair", "scrap")
_TRANSACTION_TYPES = (
    "grn_receipt",
    "load",
    "unload",
    "delivery",
    "collection",
    "status_change",
    "adjustment",
    "reconciliation",
)
_SOURCE_OMCS = ("iocl", "bpcl", "hpcl", "other")

# Only inventory:read is genuinely new. inventory:load, inventory:adjust and
# reconciliation:approve were already seeded as permission codes in
# fa52b77ec442 (Phase 6's illustrative catalog) — inventory:adjust and
# reconciliation:approve even already carry role grants there that exactly
# match docs/data/17-api-security.md §6, so this migration must not
# re-insert the permission codes and must not duplicate those grants.
_NEW_PERMISSIONS = ["inventory:read"]

# docs/data/17-api-security.md §6, exact — do not generalize across permissions.
_READ_ROLES = [
    "super_admin",
    "agency_admin",
    "manager",
    "warehouse_staff",
    "dispatcher",
    "accountant",
]
# driver included per 11-api-contracts.md line 126 (route-loading endpoint)
_LOAD_ROLES = ["agency_admin", "manager", "warehouse_staff", "driver"]
_ADJUST_ROLES = ["agency_admin", "manager", "warehouse_staff"]
# no "manager" here, unlike inventory:adjust — §6 is explicit on this difference
_RECONCILE_APPROVE_ROLES = ["agency_admin", "warehouse_staff"]

_NEW_ROLE_PERMISSION_MATRIX: list[tuple[str, list[str]]] = [
    ("inventory:read", _READ_ROLES),
    ("inventory:load", _LOAD_ROLES),
    ("inventory:adjust", _ADJUST_ROLES),
    ("reconciliation:approve", _RECONCILE_APPROVE_ROLES),
]


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


def _revoke_mutation(*, table: str) -> str:
    """Append-only enforcement: the app role may SELECT/INSERT but never UPDATE/DELETE."""
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
    # ------------------------------------------------------------------
    # 1. Schema
    # ------------------------------------------------------------------
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ------------------------------------------------------------------
    # 2. inventory.inventory_location
    # ------------------------------------------------------------------
    op.create_table(
        "inventory_location",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id"), nullable=False
        ),
        sa.Column("location_type", sa.String(length=20), nullable=False),
        sa.Column("location_ref_id", sa.Uuid(), nullable=False),
        *_standard_columns(),
        sa.CheckConstraint(
            f"location_type IN {_LOCATION_TYPES}", name="ck_inventory_location_type"
        ),
        sa.UniqueConstraint(
            "tenant_id", "location_type", "location_ref_id", name="uq_inventory_location_ref"
        ),
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------
    # 3. inventory.inventory_transaction (append-only, created before
    #    inventory_balance so the latter's FK can reference it)
    # ------------------------------------------------------------------
    op.create_table(
        "inventory_transaction",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id"), nullable=False
        ),
        sa.Column(
            "inventory_location_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.inventory_location.id"),
            nullable=False,
        ),
        sa.Column(
            "cylinder_type_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.cylinder_type.id"),
            nullable=False,
        ),
        sa.Column("transaction_type", sa.String(length=20), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reference_order_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("performed_by", sa.Uuid(), nullable=False),
        sa.Column(
            "performed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"transaction_type IN {_TRANSACTION_TYPES}", name="ck_inventory_transaction_type"
        ),
        sa.CheckConstraint(
            f"from_status IS NULL OR from_status IN {_CYLINDER_STATUSES}",
            name="ck_inventory_transaction_from_status",
        ),
        sa.CheckConstraint(
            f"to_status IN {_CYLINDER_STATUSES}", name="ck_inventory_transaction_to_status"
        ),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_transaction_quantity_positive"),
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------
    # 4. inventory.inventory_balance (materialized projection)
    # ------------------------------------------------------------------
    op.create_table(
        "inventory_balance",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id"), nullable=False
        ),
        sa.Column(
            "inventory_location_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.inventory_location.id"),
            nullable=False,
        ),
        sa.Column(
            "cylinder_type_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.cylinder_type.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "last_transaction_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.inventory_transaction.id"),
            nullable=True,
        ),
        *_standard_columns(),
        sa.CheckConstraint(f"status IN {_CYLINDER_STATUSES}", name="ck_inventory_balance_status"),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_balance_quantity_non_negative"),
        sa.UniqueConstraint(
            "inventory_location_id", "cylinder_type_id", "status", name="uq_inventory_balance"
        ),
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------
    # 5. inventory.goods_receipt_note
    # ------------------------------------------------------------------
    op.create_table(
        "goods_receipt_note",
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
        sa.Column(
            "cylinder_type_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.cylinder_type.id"),
            nullable=False,
        ),
        sa.Column("quantity_received", sa.Integer(), nullable=False),
        sa.Column("source_omc", sa.String(length=20), nullable=True),
        sa.Column("received_by", sa.Uuid(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        *_standard_columns(),
        sa.CheckConstraint("quantity_received > 0", name="ck_goods_receipt_note_quantity_positive"),
        sa.CheckConstraint(
            f"source_omc IS NULL OR source_omc IN {_SOURCE_OMCS}",
            name="ck_goods_receipt_note_source_omc",
        ),
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------
    # 6. inventory.reconciliation_record
    # ------------------------------------------------------------------
    op.create_table(
        "reconciliation_record",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id"), nullable=False
        ),
        sa.Column(
            "inventory_location_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.inventory_location.id"),
            nullable=False,
        ),
        sa.Column(
            "cylinder_type_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.cylinder_type.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expected_quantity", sa.Integer(), nullable=False),
        sa.Column("actual_quantity", sa.Integer(), nullable=False),
        sa.Column(
            "variance",
            sa.Integer(),
            sa.Computed("actual_quantity - expected_quantity", persisted=True),
            nullable=False,
        ),
        sa.Column("recorded_by", sa.Uuid(), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *_standard_columns(),
        sa.CheckConstraint(
            f"status IN {_CYLINDER_STATUSES}", name="ck_reconciliation_record_status"
        ),
        sa.CheckConstraint(
            "expected_quantity >= 0", name="ck_reconciliation_record_expected_non_negative"
        ),
        sa.CheckConstraint(
            "actual_quantity >= 0", name="ck_reconciliation_record_actual_non_negative"
        ),
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------
    # 7. Indexes
    # ------------------------------------------------------------------
    op.create_index(
        "idx_inventory_balance_location",
        "inventory_balance",
        ["inventory_location_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_inventory_transaction_location_performed_at",
        "inventory_transaction",
        ["inventory_location_id", "performed_at"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_inventory_transaction_tenant_performed_at",
        "inventory_transaction",
        ["tenant_id", "performed_at"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_grn_warehouse_received_at",
        "goods_receipt_note",
        ["warehouse_id", "received_at"],
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------
    # 8. Row-Level Security
    # ------------------------------------------------------------------
    for table in (
        "inventory_location",
        "inventory_balance",
        "inventory_transaction",
        "goods_receipt_note",
        "reconciliation_record",
    ):
        _enable_rls(table)

    # ------------------------------------------------------------------
    # 9. Grants
    # ------------------------------------------------------------------
    op.execute(_grant(table="inventory_location", privileges="SELECT, INSERT, UPDATE"))
    op.execute(_grant(table="inventory_balance", privileges="SELECT, INSERT, UPDATE"))
    op.execute(_grant(table="inventory_transaction", privileges="SELECT, INSERT, UPDATE"))
    op.execute(_revoke_mutation(table="inventory_transaction"))
    op.execute(_grant(table="goods_receipt_note", privileges="SELECT, INSERT, UPDATE"))
    op.execute(_grant(table="reconciliation_record", privileges="SELECT, INSERT, UPDATE"))

    # ------------------------------------------------------------------
    # 10. Permission codes — only inventory:read is new (see note above)
    # ------------------------------------------------------------------
    permission_table = sa.table(
        "permission",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        schema=_IDENTITY_SCHEMA,
    )
    op.bulk_insert(
        permission_table,
        [
            {
                "id": uuid.uuid4(),
                "code": code,
                "resource": code.split(":")[0],
                "action": code.split(":")[1],
            }
            for code in _NEW_PERMISSIONS
        ],
    )

    # ------------------------------------------------------------------
    # 11. Role grants — resolved by permission code via SELECT, not a
    # locally-tracked id dict, so this works whether the permission row was
    # just inserted above (inventory:read) or already existed from
    # fa52b77ec442 (inventory:load/adjust, reconciliation:approve).
    # ON CONFLICT DO NOTHING makes inventory:adjust/reconciliation:approve's
    # entries here safe no-ops — included for self-documentation that this
    # matrix matches what's already granted, not to re-grant anything.
    # ------------------------------------------------------------------
    for permission_code, role_codes in _NEW_ROLE_PERMISSION_MATRIX:
        for role_code in role_codes:
            op.execute(
                sa.text(f"""
                    INSERT INTO {_IDENTITY_SCHEMA}.role_permission
                        (id, role_id, permission_id, created_at)
                    SELECT gen_random_uuid(), r.id, p.id, now()
                    FROM {_IDENTITY_SCHEMA}.role r, {_IDENTITY_SCHEMA}.permission p
                    WHERE r.code = :role_code AND p.code = :permission_code
                    ON CONFLICT (role_id, permission_id) DO NOTHING
                """).bindparams(
                    role_code=role_code,
                    permission_code=permission_code,
                )
            )


def downgrade() -> None:
    # Only remove what this migration added: inventory:read (permission +
    # grants) and inventory:load's newly-granted role_permission rows. The
    # inventory:load/adjust/reconciliation:approve permission codes, and
    # inventory:adjust/reconciliation:approve's grants, pre-date this
    # migration (fa52b77ec442) and must be left untouched.
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.role_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission
            WHERE code IN ('inventory:read', 'inventory:load')
        )
    """)
    op.execute(f"DELETE FROM {_IDENTITY_SCHEMA}.permission WHERE code = 'inventory:read'")

    for table in (
        "reconciliation_record",
        "goods_receipt_note",
        "inventory_balance",
        "inventory_transaction",
        "inventory_location",
    ):
        op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{table}_isolation ON {_SCHEMA}.{table}")

    op.drop_table("reconciliation_record", schema=_SCHEMA)
    op.drop_table("goods_receipt_note", schema=_SCHEMA)
    op.drop_table("inventory_balance", schema=_SCHEMA)
    op.drop_table("inventory_transaction", schema=_SCHEMA)
    op.drop_table("inventory_location", schema=_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
