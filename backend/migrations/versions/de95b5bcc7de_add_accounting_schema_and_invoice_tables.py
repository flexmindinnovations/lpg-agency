"""add accounting schema and invoice tables

Revision ID: de95b5bcc7de
Revises: ca542bd9a61e
Create Date: 2026-08-13 18:18:02.366567

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = 'de95b5bcc7de'
down_revision: str | None = 'ca542bd9a61e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS accounting")
    op.create_table('invoice',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('subtotal', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('tax_amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('total_amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.ForeignKeyConstraint(['customer_id'], ['customer.customer.id'], name=op.f('fk_invoice_customer')),
    sa.ForeignKeyConstraint(['order_id'], ['orders.order.id'], name=op.f('fk_invoice_order')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant.id'], name=op.f('fk_invoice_tenant'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_invoice')),
    sa.UniqueConstraint('order_id', name=op.f('uq_invoice_order_id')),
    schema='accounting'
    )
    op.create_table('invoice_line',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('invoice_id', sa.Uuid(), nullable=False),
    sa.Column('cylinder_type_id', sa.Uuid(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('subtotal', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('tax_amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('total_amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.ForeignKeyConstraint(['cylinder_type_id'], ['tenant.cylinder_type.id'], name=op.f('fk_invoice_line_cylinder_type')),
    sa.ForeignKeyConstraint(['invoice_id'], ['accounting.invoice.id'], name=op.f('fk_invoice_line_invoice'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_invoice_line')),
    schema='accounting'
    )


def downgrade() -> None:
    op.drop_table('invoice_line', schema='accounting')
    op.drop_table('invoice', schema='accounting')
    op.execute("DROP SCHEMA IF EXISTS accounting CASCADE")
