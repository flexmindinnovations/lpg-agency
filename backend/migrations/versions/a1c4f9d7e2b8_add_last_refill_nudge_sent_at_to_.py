"""add last_refill_nudge_sent_at to customer.customer

Revision ID: a1c4f9d7e2b8
Revises: e3d5c5bb9389
Create Date: 2026-09-11 10:00:00.000000

Refill-due proactive nudge (AI Operational Intelligence, Horizon 1 Stage
2) — a plain nullable dedupe timestamp, the exact same shape as
`orders.order.last_stale_notified_at`
(`bc77a5343b06_add_last_stale_notified_at_to_orders_.py`) and
`compliance.compliance_document.last_expiry_notified_at`: set only after a
`refill_due_customer` notification has actually been enqueued for this
customer, so the daily cron's own dedupe guard doesn't re-nudge on every
run while a customer's predicted refill date is still inside the lead
window. Deliberately infrastructure-only, not a `Customer` domain field —
`last_stale_notified_at` isn't part of the `Order` aggregate either (see
that migration's own docstring); this is bookkeeping for the cron, not a
business invariant of the customer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a1c4f9d7e2b8"
down_revision: str | None = "e3d5c5bb9389"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "customer"
_TABLE = "customer"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column("last_refill_nudge_sent_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(_TABLE, "last_refill_nudge_sent_at", schema=_SCHEMA)
