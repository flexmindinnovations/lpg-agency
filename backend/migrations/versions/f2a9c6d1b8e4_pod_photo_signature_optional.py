"""make the proof-of-delivery signature and photo optional

A driver who cannot capture a signature or photo (no camera permission, object
storage unavailable, nobody to sign) must still be able to complete a delivery.
The OTP and GPS stamp remain the required proof, so only these two columns lose
NOT NULL.

Revision ID: f2a9c6d1b8e4
Revises: e7d1a3c5f9b2
Create Date: 2026-10-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f2a9c6d1b8e4"
down_revision = "e7d1a3c5f9b2"
branch_labels = None
depends_on = None

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
    # Rows recorded without an attachment get an empty reference so NOT NULL can return.
    for column in _COLUMNS:
        op.execute(
            sa.text(f"UPDATE orders.proof_of_delivery SET {column} = '' WHERE {column} IS NULL")
        )
        op.alter_column(
            "proof_of_delivery",
            column,
            existing_type=sa.Text(),
            nullable=False,
            schema="orders",
        )
