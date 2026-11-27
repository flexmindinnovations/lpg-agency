"""order other empties: empties collected of sizes that are not on the order

Revision ID: f5c8d1a4b926
Revises: e4b7c9a2d513
Create Date: 2026-11-27 12:00:00.000000

A driver can take back empties from earlier deliveries, including a size that is
not on today's order. Empties of an ordered size stay on the order line; the
other sizes are listed here as `[{"cylinder_type_id": ..., "quantity": ...}]`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "f5c8d1a4b926"
down_revision: str | None = "e4b7c9a2d513"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "order",
        sa.Column(
            "other_empties",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        schema="orders",
    )


def downgrade() -> None:
    op.drop_column("order", "other_empties", schema="orders")
