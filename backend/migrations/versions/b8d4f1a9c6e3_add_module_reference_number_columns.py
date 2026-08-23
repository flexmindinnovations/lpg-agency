"""add module reference number columns

Revision ID: b8d4f1a9c6e3
Revises: f3a7c2e8d4b1
Create Date: 2026-08-21 12:15:00.000000

Adds the human-readable reference number column to every module covered by
this migration series — `invoice_number` (+ denormalized `order_number`/
`customer_consumer_number` for the invoice drawer/PDF), `order_number`,
`complaint_number`, `credit_note_number`, `handover_number`, `grn_number`.

All columns are nullable at the DB level even though the domain layer treats
them as required for newly-created rows going forward — existing rows
predate this migration and get a number via a one-time backfill script
(`scripts/backfill_reference_numbers.py`), not via a NOT NULL default here.
Postgres treats NULL as distinct in a unique index, so pre-backfill legacy
rows never collide with each other or with freshly-generated numbers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b8d4f1a9c6e3"
down_revision: str | None = "f3a7c2e8d4b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Invoice — own number plus two denormalized read-convenience fields
    # (order_number, customer_consumer_number) resolved once at generation
    # time so the invoice detail view/PDF never needs a join.
    op.add_column(
        "invoice",
        sa.Column("invoice_number", sa.String(length=20), nullable=True),
        schema="accounting",
    )
    op.add_column(
        "invoice",
        sa.Column("order_number", sa.String(length=20), nullable=True),
        schema="accounting",
    )
    op.add_column(
        "invoice",
        sa.Column("customer_consumer_number", sa.String(length=20), nullable=True),
        schema="accounting",
    )
    op.create_index(
        "uq_invoice_tenant_invoice_number",
        "invoice",
        ["tenant_id", "invoice_number"],
        unique=True,
        schema="accounting",
    )

    op.add_column(
        "credit_note",
        sa.Column("credit_note_number", sa.String(length=20), nullable=True),
        schema="accounting",
    )
    op.create_index(
        "uq_credit_note_tenant_credit_note_number",
        "credit_note",
        ["tenant_id", "credit_note_number"],
        unique=True,
        schema="accounting",
    )

    op.add_column(
        "cash_handover",
        sa.Column("handover_number", sa.String(length=20), nullable=True),
        schema="accounting",
    )
    op.create_index(
        "uq_cash_handover_tenant_handover_number",
        "cash_handover",
        ["tenant_id", "handover_number"],
        unique=True,
        schema="accounting",
    )

    op.add_column(
        "order", sa.Column("order_number", sa.String(length=20), nullable=True), schema="orders"
    )
    op.create_index(
        "uq_order_tenant_order_number",
        "order",
        ["tenant_id", "order_number"],
        unique=True,
        schema="orders",
    )

    op.add_column(
        "complaint",
        sa.Column("complaint_number", sa.String(length=20), nullable=True),
        schema="complaint",
    )
    op.create_index(
        "uq_complaint_tenant_complaint_number",
        "complaint",
        ["tenant_id", "complaint_number"],
        unique=True,
        schema="complaint",
    )

    op.add_column(
        "goods_receipt_note",
        sa.Column("grn_number", sa.String(length=20), nullable=True),
        schema="inventory",
    )
    op.create_index(
        "uq_goods_receipt_note_tenant_grn_number",
        "goods_receipt_note",
        ["tenant_id", "grn_number"],
        unique=True,
        schema="inventory",
    )


def downgrade() -> None:
    op.drop_index(
        "uq_goods_receipt_note_tenant_grn_number",
        table_name="goods_receipt_note",
        schema="inventory",
    )
    op.drop_column("goods_receipt_note", "grn_number", schema="inventory")

    op.drop_index(
        "uq_complaint_tenant_complaint_number", table_name="complaint", schema="complaint"
    )
    op.drop_column("complaint", "complaint_number", schema="complaint")

    op.drop_index("uq_order_tenant_order_number", table_name="order", schema="orders")
    op.drop_column("order", "order_number", schema="orders")

    op.drop_index(
        "uq_cash_handover_tenant_handover_number",
        table_name="cash_handover",
        schema="accounting",
    )
    op.drop_column("cash_handover", "handover_number", schema="accounting")

    op.drop_index(
        "uq_credit_note_tenant_credit_note_number", table_name="credit_note", schema="accounting"
    )
    op.drop_column("credit_note", "credit_note_number", schema="accounting")

    op.drop_index("uq_invoice_tenant_invoice_number", table_name="invoice", schema="accounting")
    op.drop_column("invoice", "customer_consumer_number", schema="accounting")
    op.drop_column("invoice", "order_number", schema="accounting")
    op.drop_column("invoice", "invoice_number", schema="accounting")
