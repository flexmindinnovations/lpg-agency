"""make proof of delivery signature and photo optional

The driver may now record a delivery without the customer's signature
and/or a delivery photo (`planning/features/39-optional-delivery-proof/`).
The internal delivery OTP still gates `out_for_delivery -> delivered`, and
GPS, payment method and amount remain mandatory.

Revision ID: b7e1d3f5a2c9
Revises: a9c2e4f6b8d1
Create Date: 2026-10-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b7e1d3f5a2c9"
down_revision: str | None = "a9c2e4f6b8d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("signature_blob_ref", "photo_blob_ref")


def upgrade() -> None:
    for column in _COLUMNS:
        op.alter_column(
            "proof_of_delivery",
            column,
            existing_type=sa.Text(),
            nullable=True,
            schema="orders",
        )


def downgrade() -> None:
    # Rows recorded without a signature/photo have no value to restore; an
    # empty string keeps them while re-imposing NOT NULL.
    for column in _COLUMNS:
        op.execute(f"UPDATE orders.proof_of_delivery SET {column} = '' WHERE {column} IS NULL")
        op.alter_column(
            "proof_of_delivery",
            column,
            existing_type=sa.Text(),
            nullable=False,
            schema="orders",
        )
