"""one cash handover per route

`cash_handover` (`c039189dfbdc`) indexed `route_id` but never made it
unique, so a driver could declare the same route repeatedly — each a new
append-only row. BR-32 is one handover per completed route; the app now
also checks `CashHandoverRepository.get_by_route` before declaring and
returns `409 CONFLICT`, but this constraint is the backstop.

Revision ID: a7f1c93e6b20
Revises: f3a9c1e07b42
Create Date: 2026-09-02
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a7f1c93e6b20"
down_revision: str | None = "f3a9c1e07b42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Collapse any pre-existing duplicates (the bug this constraint closes):
    # keep the first declared handover per route, drop the rest. The table is
    # append-only and was never meant to hold more than one row per route, so
    # nothing references the discarded ids.
    op.execute("""
        DELETE FROM accounting.cash_handover c
        USING accounting.cash_handover keep
        WHERE c.route_id = keep.route_id
          AND (keep.declared_at, keep.id) < (c.declared_at, c.id)
    """)
    op.execute(
        "ALTER TABLE accounting.cash_handover "
        "ADD CONSTRAINT uq_cash_handover_route UNIQUE (route_id)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE accounting.cash_handover DROP CONSTRAINT uq_cash_handover_route"
    )
