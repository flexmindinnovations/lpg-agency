"""Update customer status check constraint

Revision ID: 8c7bdc1e1c73
Revises: a631835ec588
Create Date: 2026-08-15 22:20:08.570370

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op
import sqlalchemy as sa


if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = '8c7bdc1e1c73'
down_revision: str | None = 'a631835ec588'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE customer.customer DROP CONSTRAINT ck_customer_chk_customer_status")
    op.execute("ALTER TABLE customer.customer ADD CONSTRAINT ck_customer_chk_customer_status CHECK (status IN ('onboarding', 'active', 'inactive', 'blocked', 'closed'))")

def downgrade() -> None:
    op.execute("ALTER TABLE customer.customer DROP CONSTRAINT ck_customer_chk_customer_status")
    op.execute("ALTER TABLE customer.customer ADD CONSTRAINT ck_customer_chk_customer_status CHECK (status IN ('active', 'inactive', 'blocked', 'closed'))")
