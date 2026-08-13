"""add identity_user_id column, FK and unique constraint on customer.customer

Revision ID: f5fe6c4bc92b
Revises: 7106277bdd91
Create Date: 2026-08-12 00:00:00.000000

Order Management (`orders`, next phase) needs to resolve "which customer is
this?" from the JWT's `identity_user_id` claim for `orders:read`/`orders:create`
self-scoping — the same lookup `delivery.driver.identity_user_id` already
supports for drivers (see `e68103c56ad7`). `customer.customer` has never had
this column; this migration adds it fresh, nullable (a customer profile can
exist — created by staff, phone/walk-in booking — before it is ever linked to
a customer's own login) with the identical FK/unique shape as the driver
precedent.
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5fe6c4bc92b"
down_revision: str = "7106277bdd91"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.execute("ALTER TABLE customer.customer ADD COLUMN identity_user_id uuid")
    op.execute(
        "ALTER TABLE customer.customer "
        "ADD CONSTRAINT fk_customer_identity_user "
        "FOREIGN KEY (identity_user_id) "
        "REFERENCES identity.identity_user(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE customer.customer "
        "ADD CONSTRAINT uq_customer_identity_user UNIQUE (identity_user_id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE customer.customer DROP CONSTRAINT IF EXISTS uq_customer_identity_user")
    op.execute("ALTER TABLE customer.customer DROP CONSTRAINT IF EXISTS fk_customer_identity_user")
    op.execute("ALTER TABLE customer.customer DROP COLUMN IF EXISTS identity_user_id")
