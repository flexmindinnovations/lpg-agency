"""customer gstin, cancellation-request rejection, editable order lines

QA fixes (planning/features/47-qa-fixes/orders.md):

- `customer.customer.gstin` (DO-02): the GST number of a commercial,
  industrial or government customer, printed on B2B tax invoices. Format and
  check character are validated in the domain (`domain/customer/
  identifiers.py`); the column only bounds the length.
- `orders.cancellation_record.rejected_by/rejected_at/rejection_reason`
  (DO-14): a Manager can now decline a post-dispatch cancellation request
  instead of only approving it. A request is pending while it is neither
  approved nor rejected, so the one-pending-request-per-order partial unique
  index is rebuilt to exclude rejected rows — otherwise a declined request
  would block the customer from ever asking again.
- `DELETE` on `orders.order_line` for the application role (DO-13): staff
  can now edit a booking before it is put on a trip, which may drop a
  cylinder type from it. Only `Order.amend()` (booked/confirmed orders)
  removes lines.

Revision ID: 7bc2ddcd8ed9
Revises: c8d4e2f6a1b3
Create Date: 2026-10-20
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "7bc2ddcd8ed9"
down_revision: str | None = "e7b3c9d1f4a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PENDING_INDEX = "uq_cancellation_record_pending_per_order"


def _order_line_delete(statement: str) -> str:
    """`GRANT`/`REVOKE DELETE ON orders.order_line` for the application role,
    resolved the same way the orders-schema migration grants it."""
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('{statement} DELETE ON orders.order_line %s %I',
                    CASE WHEN '{statement}' = 'GRANT' THEN 'TO' ELSE 'FROM' END, app_role);
            END IF;
        END
        $$;
    """


def upgrade() -> None:
    op.add_column(
        "customer",
        sa.Column("gstin", sa.String(length=15), nullable=True),
        schema="customer",
    )

    op.add_column(
        "cancellation_record",
        sa.Column("rejected_by", sa.Uuid(), nullable=True),
        schema="orders",
    )
    op.add_column(
        "cancellation_record",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        schema="orders",
    )
    op.add_column(
        "cancellation_record",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        schema="orders",
    )
    op.create_check_constraint(
        op.f("ck_cancellation_record_rejection_pair"),
        "cancellation_record",
        "(rejected_by IS NOT NULL) = (rejected_at IS NOT NULL)",
        schema="orders",
    )
    op.create_check_constraint(
        op.f("ck_cancellation_record_single_decision"),
        "cancellation_record",
        "approved_by IS NULL OR rejected_by IS NULL",
        schema="orders",
    )
    op.drop_index(_PENDING_INDEX, table_name="cancellation_record", schema="orders")
    op.create_index(
        _PENDING_INDEX,
        "cancellation_record",
        ["order_id"],
        unique=True,
        schema="orders",
        postgresql_where=sa.text("approved_by IS NULL AND rejected_by IS NULL"),
    )
    op.execute(_order_line_delete("GRANT"))


def downgrade() -> None:
    op.execute(_order_line_delete("REVOKE"))
    # Rejected requests would collide with the narrower index; they are
    # decided and carry no pending state, so drop them first.
    op.execute("DELETE FROM orders.cancellation_record WHERE rejected_by IS NOT NULL")
    op.drop_index(_PENDING_INDEX, table_name="cancellation_record", schema="orders")
    op.create_index(
        _PENDING_INDEX,
        "cancellation_record",
        ["order_id"],
        unique=True,
        schema="orders",
        postgresql_where=sa.text("approved_by IS NULL"),
    )
    op.drop_constraint(
        op.f("ck_cancellation_record_single_decision"), "cancellation_record", schema="orders"
    )
    op.drop_constraint(
        op.f("ck_cancellation_record_rejection_pair"), "cancellation_record", schema="orders"
    )
    op.drop_column("cancellation_record", "rejection_reason", schema="orders")
    op.drop_column("cancellation_record", "rejected_at", schema="orders")
    op.drop_column("cancellation_record", "rejected_by", schema="orders")
    op.drop_column("customer", "gstin", schema="customer")
