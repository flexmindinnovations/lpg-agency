"""add last_stale_notified_at to orders.order

Revision ID: bc77a5343b06
Revises: b2e5f8a1c904
Create Date: 2026-09-09 17:32:51.606216

Stale-unassigned-order alert (order-to-delivery fulfillment automation,
ADR-046's own survey) — a plain nullable dedupe timestamp, the exact same
shape as `compliance.compliance_document.last_expiry_notified_at`
(`d2e3f4051a6c_create_compliance_document_table.py`): set only after a
notification for this order's staleness has actually been enqueued, so
the hourly cron's own `WHERE last_stale_notified_at IS NULL OR <
notified_cutoff` guard doesn't re-notify every run for an order still
awaiting manual assignment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "bc77a5343b06"
down_revision: str | None = "b2e5f8a1c904"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "orders"
_TABLE = "order"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column("last_stale_notified_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(_TABLE, "last_stale_notified_at", schema=_SCHEMA)
