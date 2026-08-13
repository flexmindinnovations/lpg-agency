"""Add display names to audit log

Revision ID: 7106277bdd91
Revises: b3f7c1d9e4a2
Create Date: 2026-08-11 23:12:47.197253

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = '7106277bdd91'
down_revision: str | None = 'b3f7c1d9e4a2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('audit_log', sa.Column('actor_display_name', sa.String(length=200), nullable=True), schema='audit')
    op.add_column('audit_log', sa.Column('entity_display_name', sa.String(length=200), nullable=True), schema='audit')


def downgrade() -> None:
    op.drop_column('audit_log', 'entity_display_name', schema='audit')
    op.drop_column('audit_log', 'actor_display_name', schema='audit')
