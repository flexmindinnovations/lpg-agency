"""harden delivery.route/route_stop and add orders.order.route_stop_id

Revision ID: de56730bb88f
Revises: 500d30960a3e
Create Date: 2026-08-12 23:00:00.000000

Closes the gap left by `500d30960a3e`, which created `delivery.route`/
`route_stop` with **no RLS, no grants, no permission seeding, and no CHECK
constraints** — confirmed by an independent audit (2026-08-12, see
`planning/features/12-delivery-dispatch/STATUS.md`) that also found
`SqlAlchemyRouteRepository.list_routes`/`count_routes`/`get_by_id`/
`get_active_route_for_driver` never filtered by tenant, meaning every route
was visible to every tenant — a live cross-tenant leak with no RLS backstop.

Three concerns:

1. **Harden `delivery.route`** — CHECK constraints, RLS (same null-safe
   predicate as `4f8b2d6a9c1e`/`7c3f1a9e2b4d`), grants, indexes.
   `delivery.route_stop` gets a CHECK constraint, audit columns, and a
   partial unique index, but deliberately **no RLS and no `tenant_id`
   column** — it is scoped transitively through `route` on every access
   path (`SqlAlchemyRouteRepository` always joins `route_stop` to `route`),
   matching `orders.order_line`/`orders.failed_delivery_record`'s own
   precedent of not needing RLS when a parent table already enforces
   tenant isolation on every join path (see `7c3f1a9e2b4d`'s comment).

2. **Permission codes** — `500d30960a3e` never seeded any permission code at
   all (the router used unseeded, ungrantable `delivery:route:read`/`write`
   strings). This migration seeds the real codes: `routes:create`,
   `routes:read`, `routes:manage` (folds plan/assign/load/status-transition
   into one code, matching `orders:dispatch`'s own economy-of-permissions
   precedent), `routes:deliver` (driver-only, mirrors `orders:deliver`).

3. **`orders.order.route_stop_id`** — replaces the Phase 11 interim
   `driver_id`/`vehicle_id` columns on `orders.order`, exactly as
   `7c3f1a9e2b4d`'s own docstring anticipated. Backfilling existing
   `(driver_id, vehicle_id)` pairs into real routes is **not mechanically
   possible** for already-assigned orders — no route ever existed for them.
   Since this environment has no production tenants yet, the backfill is a
   documented no-op, not a data migration: any order already in `assigned`
   or later status loses its driver/vehicle association on this upgrade.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "de56730bb88f"
down_revision: str | None = "500d30960a3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DELIVERY_SCHEMA = "delivery"
_ORDERS_SCHEMA = "orders"
_IDENTITY_SCHEMA = "identity"

_ROUTE_STATUSES = ("planned", "loaded", "in_progress", "completed", "reconciled", "cancelled")
_STOP_STATUSES = ("pending", "en_route", "delivered", "failed", "cancelled")

# `routes:create`/`routes:read` were already seeded as bare codes (no role
# grants) by `fa52b77ec442` (Phase 6) — only `routes:manage`/`routes:deliver`
# are genuinely new codes here. All four get role grants below.
_NEW_PERMISSIONS = ["routes:manage", "routes:deliver"]
_MANAGE_ROLES = ["agency_admin", "manager", "dispatcher"]
_READ_ROLES = ["agency_admin", "manager", "dispatcher", "driver", "warehouse_staff"]
_DELIVER_ROLES = ["driver"]
_CREATE_ROLES = _MANAGE_ROLES

_ROLE_PERMISSION_MATRIX: list[tuple[str, list[str]]] = [
    ("routes:create", _CREATE_ROLES),
    ("routes:read", _READ_ROLES),
    ("routes:manage", _MANAGE_ROLES),
    ("routes:deliver", _DELIVER_ROLES),
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
                EXECUTE format('GRANT USAGE ON SCHEMA {_DELIVERY_SCHEMA} TO %I', app_role);
                EXECUTE format(
                    'GRANT {privileges} ON {_DELIVERY_SCHEMA}.{table} TO %I', app_role
                );
            END IF;
        END
        $$;
    """


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {_DELIVERY_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_DELIVERY_SCHEMA}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_DELIVERY_SCHEMA}_{table}_isolation ON {_DELIVERY_SCHEMA}.{table}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. delivery.route — CHECK constraints
    # ------------------------------------------------------------------
    op.create_check_constraint(
        "ck_route_status", "route", f"status IN {_ROUTE_STATUSES}", schema=_DELIVERY_SCHEMA
    )

    # ------------------------------------------------------------------
    # 2. delivery.route_stop — CHECK constraint + audit columns
    # ------------------------------------------------------------------
    op.create_check_constraint(
        "ck_route_stop_status", "route_stop", f"status IN {_STOP_STATUSES}", schema=_DELIVERY_SCHEMA
    )
    op.add_column(
        "route_stop",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_DELIVERY_SCHEMA,
    )
    op.add_column(
        "route_stop", sa.Column("created_by", sa.Uuid(), nullable=True), schema=_DELIVERY_SCHEMA
    )
    op.add_column(
        "route_stop",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_DELIVERY_SCHEMA,
    )
    op.add_column(
        "route_stop", sa.Column("updated_by", sa.Uuid(), nullable=True), schema=_DELIVERY_SCHEMA
    )

    # ------------------------------------------------------------------
    # 3. Indexes
    # ------------------------------------------------------------------
    op.create_index(
        "idx_route_tenant_status_date",
        "route",
        ["tenant_id", "status", "route_date"],
        schema=_DELIVERY_SCHEMA,
    )
    op.create_index(
        "idx_route_driver_status", "route", ["driver_id", "status"], schema=_DELIVERY_SCHEMA
    )
    op.create_index("idx_route_stop_route_id", "route_stop", ["route_id"], schema=_DELIVERY_SCHEMA)
    op.create_index("idx_route_stop_order_id", "route_stop", ["order_id"], schema=_DELIVERY_SCHEMA)
    # Structural guard against the same order being assigned to two active
    # stops (previously only checked in-memory by `Route.assign_order()` —
    # a TOCTOU gap under concurrent requests).
    op.create_index(
        "uq_route_stop_order_active",
        "route_stop",
        ["order_id"],
        unique=True,
        schema=_DELIVERY_SCHEMA,
        postgresql_where=sa.text("status != 'cancelled'"),
    )

    # ------------------------------------------------------------------
    # 4. Row-Level Security — route only; route_stop is scoped transitively
    #    (see module docstring).
    # ------------------------------------------------------------------
    _enable_rls("route")

    # ------------------------------------------------------------------
    # 5. Grants
    # ------------------------------------------------------------------
    op.execute(_grant(table="route", privileges="SELECT, INSERT, UPDATE"))
    op.execute(_grant(table="route_stop", privileges="SELECT, INSERT, UPDATE"))

    # ------------------------------------------------------------------
    # 6. Permission codes
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
    # 7. Role grants
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

    # ------------------------------------------------------------------
    # 8. orders.order.route_stop_id — replaces driver_id/vehicle_id
    # ------------------------------------------------------------------
    op.add_column(
        "order",
        sa.Column(
            "route_stop_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_DELIVERY_SCHEMA}.route_stop.id"),
            nullable=True,
        ),
        schema=_ORDERS_SCHEMA,
    )
    op.create_index("idx_order_route_stop_id", "order", ["route_stop_id"], schema=_ORDERS_SCHEMA)
    # No backfill — see module docstring. Any order already past `confirmed`
    # loses its interim driver/vehicle association on this upgrade.
    op.drop_index("idx_order_driver_status", table_name="order", schema=_ORDERS_SCHEMA)
    op.drop_column("order", "driver_id", schema=_ORDERS_SCHEMA)
    op.drop_column("order", "vehicle_id", schema=_ORDERS_SCHEMA)


def downgrade() -> None:
    op.add_column(
        "order",
        sa.Column(
            "driver_id", sa.Uuid(), sa.ForeignKey(f"{_DELIVERY_SCHEMA}.driver.id"), nullable=True
        ),
        schema=_ORDERS_SCHEMA,
    )
    op.add_column(
        "order",
        sa.Column(
            "vehicle_id", sa.Uuid(), sa.ForeignKey(f"{_DELIVERY_SCHEMA}.vehicle.id"), nullable=True
        ),
        schema=_ORDERS_SCHEMA,
    )
    op.create_index(
        "idx_order_driver_status",
        "order",
        ["driver_id", "status"],
        schema=_ORDERS_SCHEMA,
        postgresql_where=sa.text("driver_id IS NOT NULL"),
    )
    op.drop_index("idx_order_route_stop_id", table_name="order", schema=_ORDERS_SCHEMA)
    op.drop_column("order", "route_stop_id", schema=_ORDERS_SCHEMA)

    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.role_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission
            WHERE code IN ('routes:create', 'routes:read', 'routes:manage', 'routes:deliver')
        )
    """)
    # routes:create/routes:read are owned by fa52b77ec442 — only the two
    # codes this migration actually inserted are deleted here.
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.permission
        WHERE code IN ('routes:manage', 'routes:deliver')
    """)

    op.execute(
        f"DROP POLICY IF EXISTS rls_{_DELIVERY_SCHEMA}_route_isolation ON {_DELIVERY_SCHEMA}.route"
    )

    op.drop_index("uq_route_stop_order_active", table_name="route_stop", schema=_DELIVERY_SCHEMA)
    op.drop_index("idx_route_stop_order_id", table_name="route_stop", schema=_DELIVERY_SCHEMA)
    op.drop_index("idx_route_stop_route_id", table_name="route_stop", schema=_DELIVERY_SCHEMA)
    op.drop_index("idx_route_driver_status", table_name="route", schema=_DELIVERY_SCHEMA)
    op.drop_index("idx_route_tenant_status_date", table_name="route", schema=_DELIVERY_SCHEMA)

    op.drop_column("route_stop", "updated_by", schema=_DELIVERY_SCHEMA)
    op.drop_column("route_stop", "updated_at", schema=_DELIVERY_SCHEMA)
    op.drop_column("route_stop", "created_by", schema=_DELIVERY_SCHEMA)
    op.drop_column("route_stop", "created_at", schema=_DELIVERY_SCHEMA)
    op.drop_constraint("ck_route_stop_status", "route_stop", schema=_DELIVERY_SCHEMA, type_="check")
    op.drop_constraint("ck_route_status", "route", schema=_DELIVERY_SCHEMA, type_="check")
