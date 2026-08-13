"""extend inventory.inventory_transaction with reservation/reservation_release

Revision ID: 95eff999e568
Revises: f5fe6c4bc92b
Create Date: 2026-08-12 00:10:00.000000

Order Management (`orders`, next phase) reserves vehicle Filled stock at
order assignment (BR-09) rather than waiting until delivery, so a second
order can't also claim the same physical cylinders — and releases that
reservation on cancellation (BR-10). Both are modeled as new
`InventoryLocation` domain methods (`reserve()`/`release_reservation()`,
same debit/credit-Filled shape as the existing `record_delivery()`/
`record_collection()`) producing two new `inventory_transaction_type`
values. No new table, no new column, no new permission — this migration
only widens the existing CHECK constraint.
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "95eff999e568"
down_revision: str = "f5fe6c4bc92b"
branch_labels: None = None
depends_on: None = None

_SCHEMA = "inventory"
_TABLE = "inventory_transaction"
# The declared `name="ck_inventory_transaction_type"` in the original
# migration (`4f8b2d6a9c1e`) already embeds the table name, and this
# codebase's `Base.metadata.naming_convention` (`ck_%(table_name)s_
# %(constraint_name)s`) prepends it a second time — the constraint's real
# name on disk is the doubled form below (verified against a live database,
# not assumed from the migration source).
_CONSTRAINT = "ck_inventory_transaction_ck_inventory_transaction_type"

_ORIGINAL_TYPES = (
    "grn_receipt",
    "load",
    "unload",
    "delivery",
    "collection",
    "status_change",
    "adjustment",
    "reconciliation",
)
_EXTENDED_TYPES = (*_ORIGINAL_TYPES, "reservation", "reservation_release")


def upgrade() -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} DROP CONSTRAINT {_CONSTRAINT}")
    op.execute(
        f"ALTER TABLE {_SCHEMA}.{_TABLE} "
        f"ADD CONSTRAINT {_CONSTRAINT} CHECK (transaction_type IN {_EXTENDED_TYPES})"
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} DROP CONSTRAINT {_CONSTRAINT}")
    op.execute(
        f"ALTER TABLE {_SCHEMA}.{_TABLE} "
        f"ADD CONSTRAINT {_CONSTRAINT} CHECK (transaction_type IN {_ORIGINAL_TYPES})"
    )
