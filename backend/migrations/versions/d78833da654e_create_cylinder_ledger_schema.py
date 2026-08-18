"""create cylinder ledger schema

Revision ID: d78833da654e
Revises: de56730bb88f
Create Date: 2026-08-13 12:43:26.498029

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = 'd78833da654e'
down_revision: str | None = 'de56730bb88f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS cylinder_ledger")

    op.create_table('cylinder_ledger',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('customer_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.Uuid(), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.customer.id'], name=op.f('fk_cylinder_ledger_customer'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant.id'], name=op.f('fk_cylinder_ledger_tenant'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_cylinder_ledger')),
        schema='cylinder_ledger'
    )

    op.create_table('ledger_transaction',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('cylinder_ledger_id', sa.Uuid(), nullable=False),
        sa.Column('cylinder_type_id', sa.Uuid(), nullable=False),
        sa.Column('transaction_type', sa.String(length=30), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('reference_id', sa.Uuid(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('performed_by', sa.Uuid(), nullable=False),
        sa.Column('performed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['cylinder_ledger_id'], ['cylinder_ledger.cylinder_ledger.id'], name=op.f('fk_ledger_transaction_cylinder_ledger'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cylinder_type_id'], ['tenant.cylinder_type.id'], name=op.f('fk_ledger_transaction_cylinder_type')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant.id'], name=op.f('fk_ledger_transaction_tenant'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ledger_transaction')),
        schema='cylinder_ledger'
    )

    op.create_table('cylinder_balance',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('cylinder_ledger_id', sa.Uuid(), nullable=False),
        sa.Column('cylinder_type_id', sa.Uuid(), nullable=False),
        sa.Column('quantity', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('last_transaction_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.Uuid(), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.ForeignKeyConstraint(['cylinder_ledger_id'], ['cylinder_ledger.cylinder_ledger.id'], name=op.f('fk_cylinder_balance_cylinder_ledger'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cylinder_type_id'], ['tenant.cylinder_type.id'], name=op.f('fk_cylinder_balance_cylinder_type')),
        sa.ForeignKeyConstraint(['last_transaction_id'], ['cylinder_ledger.ledger_transaction.id'], name=op.f('fk_cylinder_balance_ledger_transaction')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant.id'], name=op.f('fk_cylinder_balance_tenant'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_cylinder_balance')),
        schema='cylinder_ledger'
    )


def downgrade() -> None:
    op.drop_table('cylinder_balance', schema='cylinder_ledger')
    op.drop_table('ledger_transaction', schema='cylinder_ledger')
    op.drop_table('cylinder_ledger', schema='cylinder_ledger')
    op.execute("DROP SCHEMA IF EXISTS cylinder_ledger")
