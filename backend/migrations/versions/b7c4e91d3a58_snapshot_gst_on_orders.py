"""snapshot GST on orders

An order now keeps, with each line's unit price, the GST rate quoted and
whether the prices included GST, so the amount a customer pays (price plus
GST when prices are exclusive) is fixed when the order is priced
(planning/features/55). Both columns are nullable: orders priced earlier
have no snapshot and keep reporting their total as before.

Revision ID: b7c4e91d3a58
Revises: d2b8f4a60c17
Create Date: 2026-10-30
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b7c4e91d3a58"
down_revision: str | None = "d2b8f4a60c17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "orders"


def upgrade() -> None:
    op.add_column(
        "order",
        sa.Column("prices_include_gst", sa.Boolean(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "order_line",
        sa.Column("gst_rate_percent", sa.Numeric(5, 2), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("order_line", "gst_rate_percent", schema=_SCHEMA)
    op.drop_column("order", "prices_include_gst", schema=_SCHEMA)
