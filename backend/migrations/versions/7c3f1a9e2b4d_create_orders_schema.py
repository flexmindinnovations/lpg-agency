"""create orders schema: order, order_line, status history, failed delivery,
cancellation record, proof of delivery

Revision ID: 7c3f1a9e2b4d
Revises: 95eff999e568
Create Date: 2026-08-12 09:00:00.000000

Delivers:
  - `orders` PostgreSQL schema
  - `orders.order` — the aggregate root, 10-state lifecycle (BR-07,
    `docs/data/08-state-machines.md` §2)
  - `orders.order_line` — per-cylinder-type line items
  - `orders.order_status_history` — append-only transition ledger (no
    standard audit columns, matching `audit.audit_log`/
    `inventory.inventory_transaction`'s precedent; UPDATE/DELETE revoked)
  - `orders.failed_delivery_record` — append-only, one row per failed
    delivery attempt (D-12)
  - `orders.cancellation_record` — mutated exactly once by `approve()`
    (D-19); keeps normal audit columns unlike the other four tables
  - `orders.proof_of_delivery` — append-only, exactly one row per order (BR-08)
  - Four new permission codes (`orders:confirm`, `orders:assign`,
    `orders:dispatch`, `orders:close`) plus their role grants, and the
    previously-ungranted role grants for the pre-existing `orders:read`/
    `orders:cancel` codes (seeded with no grants in `fa52b77ec442`) — the
    already-granted `orders:create`/`orders:cancel_approve`/`orders:deliver`
    are untouched.

PHASE 11 MIGRATION DEBT — read before touching `driver_id`/`vehicle_id`:
`orders.order.driver_id`/`vehicle_id` are an interim simplification. The
real target is a `route_stop_id` FK into `delivery.route_stop`, which does
not exist yet (Delivery/Route Management is Phase 11). When Phase 11 lands:
add `delivery.route_stop`, add `orders.order.route_stop_id`, backfill it
from the existing `(driver_id, vehicle_id)` pair (join through whatever
route/stop was actually created for that assignment), then drop
`driver_id`/`vehicle_id` from `orders.order`. Do not repeat this
column-pair shape anywhere else — it is accepted risk for this phase only,
mirroring `inventory.inventory_location.location_ref_id`'s own precedent
but with real FKs (a strictly safer variant, since `driver_id`/`vehicle_id`
reference existing, already-created tables).

RLS uses the same null-safe predicate (`NULLIF(..., true)`) as
`4f8b2d6a9c1e_create_inventory_schema.py`.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "7c3f1a9e2b4d"
down_revision: str | None = "95eff999e568"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "orders"
_TENANT_SCHEMA = "tenant"
_CUSTOMER_SCHEMA = "customer"
_DELIVERY_SCHEMA = "delivery"
_IDENTITY_SCHEMA = "identity"

_ORDER_STATUSES = (
    "draft",
    "booked",
    "confirmed",
    "assigned",
    "ready_for_dispatch",
    "out_for_delivery",
    "delivered",
    "failed_delivery",
    "cancelled",
    "closed",
)
_BOOKING_SOURCES = ("mobile_app", "staff", "phone", "walk_in", "whatsapp", "api")
_PAYMENT_METHODS = ("cash", "upi", "card", "online_gateway", "credit")
_FAILED_DELIVERY_REASONS = (
    "customer_unavailable",
    "wrong_address",
    "payment_refused",
    "vehicle_issue",
    "safety_issue",
)
_FAILED_DELIVERY_RESOLUTIONS = ("reschedule", "cancel", "return_stock")

# orders:create/:read/:cancel/:cancel_approve/:deliver were already seeded as
# codes in fa52b77ec442 (Phase 6). Only these four are genuinely new.
_NEW_PERMISSIONS = ["orders:confirm", "orders:assign", "orders:dispatch", "orders:close"]

_ALL_ROLES = [
    "super_admin",
    "agency_admin",
    "manager",
    "warehouse_staff",
    "dispatcher",
    "accountant",
    "driver",
    "customer",
]
_CONFIRM_ROLES = ["agency_admin", "manager", "dispatcher"]
_ASSIGN_ROLES = ["agency_admin", "manager", "dispatcher"]
# driver self-triggers "depart" — this permission folds dispatch/depart/reschedule together.
_DISPATCH_ROLES = ["agency_admin", "manager", "dispatcher", "driver"]
_CLOSE_ROLES = ["agency_admin", "manager"]
# fa52b77ec442 seeded these two codes with no grants at all — filled in here.
_READ_ROLES = _ALL_ROLES
_CANCEL_ROLES = ["agency_admin", "manager", "dispatcher", "customer"]

_ROLE_PERMISSION_MATRIX: list[tuple[str, list[str]]] = [
    ("orders:confirm", _CONFIRM_ROLES),
    ("orders:assign", _ASSIGN_ROLES),
    ("orders:dispatch", _DISPATCH_ROLES),
    ("orders:close", _CLOSE_ROLES),
    ("orders:read", _READ_ROLES),
    ("orders:cancel", _CANCEL_ROLES),
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
    # 2. orders.order
    # ------------------------------------------------------------------
    op.create_table(
        "order",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.branch.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_CUSTOMER_SCHEMA}.customer.id"),
            nullable=False,
        ),
        sa.Column(
            "address_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_CUSTOMER_SCHEMA}.customer_address.id"),
            nullable=False,
        ),
        sa.Column("delivery_address_line", sa.Text(), nullable=False),
        sa.Column("delivery_latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("delivery_longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("booking_source", sa.String(length=20), nullable=False),
        sa.Column("payment_method_preference", sa.String(length=20), nullable=True),
        sa.Column("requested_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Interim — see the Phase 11 migration debt note in this file's docstring.
        sa.Column(
            "driver_id", sa.Uuid(), sa.ForeignKey(f"{_DELIVERY_SCHEMA}.driver.id"), nullable=True
        ),
        sa.Column(
            "vehicle_id", sa.Uuid(), sa.ForeignKey(f"{_DELIVERY_SCHEMA}.vehicle.id"), nullable=True
        ),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=True),
        *_standard_columns(),
        sa.CheckConstraint(f"status IN {_ORDER_STATUSES}", name="ck_order_status"),
        sa.CheckConstraint(f"booking_source IN {_BOOKING_SOURCES}", name="ck_order_booking_source"),
        sa.CheckConstraint(
            f"payment_method_preference IS NULL OR payment_method_preference IN {_PAYMENT_METHODS}",
            name="ck_order_payment_method_preference",
        ),
        sa.CheckConstraint(
            "total_amount IS NULL OR total_amount >= 0", name="ck_order_total_non_negative"
        ),
        sa.CheckConstraint(
            "delivery_latitude IS NULL OR delivery_latitude BETWEEN -90 AND 90",
            name="ck_order_delivery_latitude_range",
        ),
        sa.CheckConstraint(
            "delivery_longitude IS NULL OR delivery_longitude BETWEEN -180 AND 180",
            name="ck_order_delivery_longitude_range",
        ),
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------
    # 3. orders.order_line
    # ------------------------------------------------------------------
    op.create_table(
        "order_line",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.order.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cylinder_type_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.cylinder_type.id"),
            nullable=False,
        ),
        sa.Column("quantity_ordered", sa.Integer(), nullable=False),
        sa.Column("quantity_delivered", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("quantity_pending", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "quantity_collected_empty", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("is_backordered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.CheckConstraint("quantity_ordered > 0", name="ck_order_line_quantity_ordered_positive"),
        sa.CheckConstraint(
            "quantity_delivered >= 0", name="ck_order_line_quantity_delivered_non_negative"
        ),
        sa.CheckConstraint(
            "quantity_pending >= 0", name="ck_order_line_quantity_pending_non_negative"
        ),
        sa.CheckConstraint(
            "quantity_collected_empty >= 0",
            name="ck_order_line_quantity_collected_empty_non_negative",
        ),
        sa.CheckConstraint(
            "quantity_delivered + quantity_pending <= quantity_ordered",
            name="ck_order_line_delivered_plus_pending_within_ordered",
        ),
        sa.CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0", name="ck_order_line_unit_price_non_negative"
        ),
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------
    # 4. orders.order_status_history (append-only)
    # ------------------------------------------------------------------
    op.create_table(
        "order_status_history",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.order.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            f"from_status IS NULL OR from_status IN {_ORDER_STATUSES}",
            name="ck_order_status_history_from_status",
        ),
        sa.CheckConstraint(
            f"to_status IN {_ORDER_STATUSES}", name="ck_order_status_history_to_status"
        ),
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------
    # 5. orders.failed_delivery_record (append-only)
    # ------------------------------------------------------------------
    op.create_table(
        "failed_delivery_record",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.order.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason_code", sa.String(length=30), nullable=False),
        sa.Column("resolution_action", sa.String(length=20), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"reason_code IN {_FAILED_DELIVERY_REASONS}",
            name="ck_failed_delivery_record_reason_code",
        ),
        sa.CheckConstraint(
            f"resolution_action IS NULL OR resolution_action IN {_FAILED_DELIVERY_RESOLUTIONS}",
            name="ck_failed_delivery_record_resolution_action",
        ),
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------
    # 6. orders.cancellation_record (normal audit columns — mutated once by approve)
    # ------------------------------------------------------------------
    op.create_table(
        "cancellation_record",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.order.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cancelled_by", sa.Uuid(), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("cancellation_charge", sa.Numeric(12, 2), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *_standard_columns(),
        sa.CheckConstraint(
            "cancellation_charge IS NULL OR cancellation_charge >= 0",
            name="ck_cancellation_record_charge_non_negative",
        ),
        sa.CheckConstraint(
            "(approved_by IS NOT NULL) = (approved_at IS NOT NULL)",
            name="ck_cancellation_record_approval_pair",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "uq_cancellation_record_pending_per_order",
        "cancellation_record",
        ["order_id"],
        unique=True,
        schema=_SCHEMA,
        postgresql_where=sa.text("approved_by IS NULL"),
    )

    # ------------------------------------------------------------------
    # 7. orders.proof_of_delivery (append-only, one row per order)
    # ------------------------------------------------------------------
    op.create_table(
        "proof_of_delivery",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.order.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("otp_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signature_blob_ref", sa.Text(), nullable=False),
        sa.Column("photo_blob_ref", sa.Text(), nullable=False),
        sa.Column("gps_lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("gps_lng", sa.Numeric(9, 6), nullable=False),
        sa.Column("payment_method", sa.String(length=20), nullable=False),
        sa.Column("amount_collected", sa.Numeric(12, 2), nullable=False),
        sa.Column("recorded_by", sa.Uuid(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("gps_lat BETWEEN -90 AND 90", name="ck_proof_of_delivery_gps_lat_range"),
        sa.CheckConstraint(
            "gps_lng BETWEEN -180 AND 180", name="ck_proof_of_delivery_gps_lng_range"
        ),
        sa.CheckConstraint(
            f"payment_method IN {_PAYMENT_METHODS}", name="ck_proof_of_delivery_payment_method"
        ),
        sa.CheckConstraint(
            "amount_collected >= 0", name="ck_proof_of_delivery_amount_collected_non_negative"
        ),
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------
    # 8. Indexes
    # ------------------------------------------------------------------
    op.create_index(
        "idx_order_tenant_status_date",
        "order",
        ["tenant_id", "status", "requested_date"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_order_tenant_customer", "order", ["tenant_id", "customer_id"], schema=_SCHEMA
    )
    op.create_index(
        "idx_order_tenant_branch_status",
        "order",
        ["tenant_id", "branch_id", "status"],
        schema=_SCHEMA,
    )
    op.create_index("idx_orderline_order_id", "order_line", ["order_id"], schema=_SCHEMA)
    op.create_index(
        "idx_order_metadata_gin", "order", ["metadata"], schema=_SCHEMA, postgresql_using="gin"
    )
    op.create_index(
        "idx_order_driver_status",
        "order",
        ["driver_id", "status"],
        schema=_SCHEMA,
        postgresql_where=sa.text("driver_id IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # 9. Row-Level Security
    # ------------------------------------------------------------------
    for table in ("order", "cancellation_record", "proof_of_delivery"):
        _enable_rls(table)
    # order_line and failed_delivery_record/order_status_history don't carry
    # tenant_id directly — scoped transitively through orders.order via FK,
    # matching inventory_transaction's own precedent of not needing RLS when
    # a parent table already enforces tenant isolation on every join path.

    # ------------------------------------------------------------------
    # 10. Grants
    # ------------------------------------------------------------------
    op.execute(_grant(table="order", privileges="SELECT, INSERT, UPDATE"))
    op.execute(_grant(table="order_line", privileges="SELECT, INSERT, UPDATE"))
    op.execute(_grant(table="order_status_history", privileges="SELECT, INSERT"))
    op.execute(_revoke_mutation(table="order_status_history"))
    op.execute(_grant(table="failed_delivery_record", privileges="SELECT, INSERT"))
    op.execute(_revoke_mutation(table="failed_delivery_record"))
    op.execute(_grant(table="cancellation_record", privileges="SELECT, INSERT, UPDATE"))
    op.execute(_grant(table="proof_of_delivery", privileges="SELECT, INSERT"))
    op.execute(_revoke_mutation(table="proof_of_delivery"))

    # ------------------------------------------------------------------
    # 11. Permission codes — only the four orders:confirm/assign/dispatch/close are new
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
    # 12. Role grants — resolved by permission code via SELECT so this works
    # whether the code was just inserted above or already existed from
    # fa52b77ec442 (orders:read/orders:cancel had no grants there at all;
    # orders:create/orders:cancel_approve/orders:deliver already do —
    # ON CONFLICT DO NOTHING makes re-listing those two harmless, but they
    # are deliberately NOT re-listed here to avoid implying they're new).
    # ------------------------------------------------------------------
    for permission_code, role_codes in _ROLE_PERMISSION_MATRIX:
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
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.role_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission
            WHERE code IN ('orders:confirm', 'orders:assign', 'orders:dispatch', 'orders:close')
        )
    """)
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.role_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission
            WHERE code IN ('orders:read', 'orders:cancel')
        )
    """)
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.permission
        WHERE code IN ('orders:confirm', 'orders:assign', 'orders:dispatch', 'orders:close')
    """)

    for table in ("proof_of_delivery", "cancellation_record", "order"):
        op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{table}_isolation ON {_SCHEMA}.{table}")

    op.drop_table("proof_of_delivery", schema=_SCHEMA)
    op.drop_table("cancellation_record", schema=_SCHEMA)
    op.drop_table("failed_delivery_record", schema=_SCHEMA)
    op.drop_table("order_status_history", schema=_SCHEMA)
    op.drop_table("order_line", schema=_SCHEMA)
    op.drop_table("order", schema=_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
