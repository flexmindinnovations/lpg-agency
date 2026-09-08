"""add qr_code to compliance cylinder unit table

Revision ID: b2e5f8a1c904
Revises: b3e97f4d1c6a
Create Date: 2026-09-08 23:00:00.000000

Delivers QR/Bar Code tracking support to Cylinder Identity:
  - Adds `qr_code` (VARCHAR(128), NOT NULL) to `compliance.cylinder_unit`.
  - Backfills existing rows with 'CYL-' || serial_number.
  - Adds unique constraint `uq_compliance_cylinder_unit_qr` on (tenant_id, qr_code).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b2e5f8a1c904"
down_revision: str | None = "b3e97f4d1c6a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "compliance"
_TABLE = "cylinder_unit"
_CONSTRAINT_NAME = "uq_compliance_cylinder_unit_qr"


def upgrade() -> None:
    # 1. Add column as nullable
    op.add_column(
        _TABLE,
        sa.Column("qr_code", sa.String(length=128), nullable=True),
        schema=_SCHEMA,
    )

    # 2. Backfill existing rows
    op.execute(
        sa.text(
            f"UPDATE {_SCHEMA}.{_TABLE} "
            "SET qr_code = 'CYL-' || serial_number "
            "WHERE qr_code IS NULL"
        )
    )

    # 3. Alter column to NOT NULL
    op.alter_column(
        _TABLE,
        "qr_code",
        nullable=False,
        schema=_SCHEMA,
    )

    # 4. Add unique constraint per tenant
    op.create_unique_constraint(
        _CONSTRAINT_NAME,
        _TABLE,
        ["tenant_id", "qr_code"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        _CONSTRAINT_NAME,
        _TABLE,
        type_="unique",
        schema=_SCHEMA,
    )
    op.drop_column(_TABLE, "qr_code", schema=_SCHEMA)
