"""add is_active to tenant.branch and tenant.warehouse

Revision ID: 0e01779fc059
Revises: bc77a5343b06
Create Date: 2026-09-09 15:20:00.000000

Dashboard-polish deactivation work — mirrors `tenant.cylinder_type.
is_active` exactly (same column shape, same "deactivated, never hard
deleted" rationale: `Branch`/`Warehouse` are FK-referenced by orders,
routes, drivers, vehicles, and warehouses with `ondelete="CASCADE"` in
several places, so a hard delete would cascade-destroy that history —
deactivation is the only safe removal path). Not the existing
`is_deleted`/`deleted_at`/`deleted_by` columns already on both tables —
those are dead boilerplate copied onto every `tenant.*` model in this
file and used by no repository or use case anywhere in this codebase
(confirmed directly: `CylinderTypeModel` carries the same unused triplet
alongside its own real, working `is_active`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0e01779fc059"
down_revision: str | None = "bc77a5343b06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "tenant"


def upgrade() -> None:
    op.add_column(
        "branch",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        schema=_SCHEMA,
    )
    op.add_column(
        "warehouse",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("warehouse", "is_active", schema=_SCHEMA)
    op.drop_column("branch", "is_active", schema=_SCHEMA)
