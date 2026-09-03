"""route load manifest + driver load-confirmation

Van-load confirmation (phase 27, D-24 §2). `delivery.route` gains:
- `loaded_lines` — JSONB `[{cylinder_type_id, quantity}]`, snapshotted when
  `LoadVehicleForRouteUseCase` moves the route `planned -> loaded`;
- `load_confirmed_at` — set when the driver confirms the van matches the
  manifest (`POST /routes/{id}/confirm-load`). Nullable, soft — not a gate
  on departing.

Revision ID: b3e1d7a24f90
Revises: a7f1c93e6b20
Create Date: 2026-09-03
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b3e1d7a24f90"
down_revision: str | None = "a7f1c93e6b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "route",
        sa.Column("loaded_lines", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="delivery",
    )
    op.add_column(
        "route",
        sa.Column("load_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        schema="delivery",
    )


def downgrade() -> None:
    op.drop_column("route", "load_confirmed_at", schema="delivery")
    op.drop_column("route", "loaded_lines", schema="delivery")
