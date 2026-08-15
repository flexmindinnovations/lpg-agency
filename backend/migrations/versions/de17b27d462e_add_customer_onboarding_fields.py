"""Add customer onboarding fields

Revision ID: de17b27d462e
Revises: bab6ab8f401f
Create Date: 2026-08-14 22:49:02.937718

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = 'de17b27d462e'
down_revision: str | None = 'bab6ab8f401f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Customer table changes
    op.add_column('customer', sa.Column('contact_person', sa.String(length=200), nullable=True), schema='customer')
    op.add_column('customer', sa.Column('alternate_mobile', sa.String(length=20), nullable=True), schema='customer')
    op.add_column('customer', sa.Column('email', sa.String(length=200), nullable=True), schema='customer')
    op.add_column('customer', sa.Column('date_of_birth', sa.Date(), nullable=True), schema='customer')
    op.alter_column('customer', 'consumer_number',
               existing_type=sa.VARCHAR(length=50),
               nullable=True,
               schema='customer')
    op.alter_column('customer', 'status',
               existing_type=sa.VARCHAR(length=50),
               server_default='onboarding',
               schema='customer')

    # CustomerAddress table changes
    op.add_column('customer_address', sa.Column('line_1', sa.Text(), nullable=False, server_default=''), schema='customer')
    op.add_column('customer_address', sa.Column('line_2', sa.Text(), nullable=True), schema='customer')
    op.add_column('customer_address', sa.Column('landmark', sa.String(length=200), nullable=True), schema='customer')
    op.add_column('customer_address', sa.Column('area', sa.String(length=200), nullable=True), schema='customer')
    op.add_column('customer_address', sa.Column('city', sa.String(length=100), nullable=True), schema='customer')
    op.add_column('customer_address', sa.Column('district', sa.String(length=100), nullable=True), schema='customer')
    op.add_column('customer_address', sa.Column('state', sa.String(length=100), nullable=True), schema='customer')
    op.add_column('customer_address', sa.Column('pincode', sa.String(length=20), nullable=True), schema='customer')
    op.add_column('customer_address', sa.Column('address_type', sa.String(length=50), server_default='delivery', nullable=False), schema='customer')
    
    # We must populate line_1 with existing address_line data before dropping it
    op.execute("UPDATE customer.customer_address SET line_1 = address_line")
    op.drop_column('customer_address', 'address_line', schema='customer')

    # KycDocument table changes
    op.add_column('kyc_document', sa.Column('document_number', sa.String(length=100), nullable=False, server_default=''), schema='customer')
    op.add_column('kyc_document', sa.Column('file_url', sa.Text(), nullable=True), schema='customer')
    op.add_column('kyc_document', sa.Column('issue_date', sa.Date(), nullable=True), schema='customer')
    op.add_column('kyc_document', sa.Column('expiry_date', sa.Date(), nullable=True), schema='customer')
    op.add_column('kyc_document', sa.Column('rejection_reason', sa.Text(), nullable=True), schema='customer')
    
    # We must populate document_number with existing doc_reference data before dropping it
    op.execute("UPDATE customer.kyc_document SET document_number = doc_reference")
    op.drop_column('kyc_document', 'doc_reference', schema='customer')


def downgrade() -> None:
    # KycDocument table changes
    op.add_column('kyc_document', sa.Column('doc_reference', sa.Text(), nullable=False, server_default=''), schema='customer')
    op.execute("UPDATE customer.kyc_document SET doc_reference = document_number")
    op.drop_column('kyc_document', 'rejection_reason', schema='customer')
    op.drop_column('kyc_document', 'expiry_date', schema='customer')
    op.drop_column('kyc_document', 'issue_date', schema='customer')
    op.drop_column('kyc_document', 'file_url', schema='customer')
    op.drop_column('kyc_document', 'document_number', schema='customer')

    # CustomerAddress table changes
    op.add_column('customer_address', sa.Column('address_line', sa.Text(), nullable=False, server_default=''), schema='customer')
    op.execute("UPDATE customer.customer_address SET address_line = line_1")
    op.drop_column('customer_address', 'address_type', schema='customer')
    op.drop_column('customer_address', 'pincode', schema='customer')
    op.drop_column('customer_address', 'state', schema='customer')
    op.drop_column('customer_address', 'district', schema='customer')
    op.drop_column('customer_address', 'city', schema='customer')
    op.drop_column('customer_address', 'area', schema='customer')
    op.drop_column('customer_address', 'landmark', schema='customer')
    op.drop_column('customer_address', 'line_2', schema='customer')
    op.drop_column('customer_address', 'line_1', schema='customer')

    # Customer table changes
    op.alter_column('customer', 'status',
               existing_type=sa.VARCHAR(length=50),
               server_default='active',
               schema='customer')
    op.alter_column('customer', 'consumer_number',
               existing_type=sa.VARCHAR(length=50),
               nullable=False,
               schema='customer')
    op.drop_column('customer', 'date_of_birth', schema='customer')
    op.drop_column('customer', 'email', schema='customer')
    op.drop_column('customer', 'alternate_mobile', schema='customer')
    op.drop_column('customer', 'contact_person', schema='customer')
