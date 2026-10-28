"""cash handover: denominations, variance reason, UPI expected

ADR-066. Three nullable columns on the append-only `accounting.cash_handover`:

* `denominations` - JSON object of note value -> count the driver counted
  (`{"500": 4, "100": 3}`); when present it adds up to `actual_amount`.
* `variance_reason` - why the cash differs from what the deliveries say.
* `upi_expected` - UPI collected at the doorstep on the same route, shown
  beside the cash for the mode split. Informational; never part of the
  cash comparison.

Existing rows and old clients are unaffected.

Revision ID: a3f7c1e9d205
Revises: 7bc2ddcd8ed9
Create Date: 2026-10-28
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a3f7c1e9d205"
down_revision: str | None = "7bc2ddcd8ed9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cash_handover",
        sa.Column("denominations", postgresql.JSONB(), nullable=True),
        schema="accounting",
    )
    op.add_column(
        "cash_handover", sa.Column("variance_reason", sa.Text(), nullable=True), schema="accounting"
    )
    op.add_column(
        "cash_handover",
        sa.Column("upi_expected", sa.Numeric(12, 2), nullable=True),
        schema="accounting",
    )


def downgrade() -> None:
    op.drop_column("cash_handover", "upi_expected", schema="accounting")
    op.drop_column("cash_handover", "variance_reason", schema="accounting")
    op.drop_column("cash_handover", "denominations", schema="accounting")
