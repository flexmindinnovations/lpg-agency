"""add dac_code to proof of delivery

Delivery Authentication Code (Phase 20 subsystem 4, `planning/features/
20-regulatory-compliance/PLAN.md` §4). The OMC issues its own separate
6-digit code to the consumer's mobile at a large and growing share of
deliveries (`docs/research/feature-gap-analysis.md` R13) — distinct from
this platform's own internal delivery OTP, which continues to be the only
thing that gates `out_for_delivery -> delivered`. `dac_code` is optional
(coverage is ~90%, not 100%) and format-validated only (6 digits) — this
platform has no OMC portal API to check a DAC's authenticity against.

Revision ID: f4a8c2d9e6b1
Revises: 9c3e7f2a15d4
Create Date: 2026-09-08
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "f4a8c2d9e6b1"
down_revision: str | None = "9c3e7f2a15d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "proof_of_delivery",
        sa.Column("dac_code", sa.String(length=6), nullable=True),
        schema="orders",
    )
    op.create_check_constraint(
        "ck_proof_of_delivery_dac_code_format",
        "proof_of_delivery",
        "dac_code IS NULL OR dac_code ~ '^[0-9]{6}$'",
        schema="orders",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_proof_of_delivery_dac_code_format", "proof_of_delivery", schema="orders"
    )
    op.drop_column("proof_of_delivery", "dac_code", schema="orders")
