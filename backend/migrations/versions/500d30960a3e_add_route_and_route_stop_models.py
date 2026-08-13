"""add route and route_stop models

Revision ID: 500d30960a3e
Revises: 7c3f1a9e2b4d
Create Date: 2026-08-12 20:38:46.446449

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = '500d30960a3e'
down_revision: str | None = '7c3f1a9e2b4d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "route",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("driver_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), nullable=False),
        sa.Column("route_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="planned", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["tenant.branch.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["driver_id"], ["delivery.driver.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["delivery.vehicle.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="delivery",
    )
    op.create_table(
        "route_stop",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("route_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("otp_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("signature_url", sa.String(), nullable=True),
        sa.Column("photo_url", sa.String(), nullable=True),
        sa.Column("gps_lat", sa.Float(), nullable=True),
        sa.Column("gps_lon", sa.Float(), nullable=True),
        sa.Column("failure_reason", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.order.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["route_id"], ["delivery.route.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="delivery",
    )


def downgrade() -> None:
    op.drop_table("route_stop", schema="delivery")
    op.drop_table("route", schema="delivery")
