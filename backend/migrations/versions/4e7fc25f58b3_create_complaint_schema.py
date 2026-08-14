"""create complaint schema

Revision ID: 4e7fc25f58b3
Revises: b9248bf4b34f
Create Date: 2026-08-14 15:04:29.033313

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op
import sqlalchemy as sa


if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = '4e7fc25f58b3'
down_revision: str | None = 'b9248bf4b34f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA complaint;")

    op.execute("""
        CREATE TABLE complaint.complaint (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            customer_id UUID NOT NULL,
            order_id UUID,
            category VARCHAR(50) NOT NULL,
            priority VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL,
            description TEXT NOT NULL,
            sla_due_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by UUID,
            updated_by UUID,
            CONSTRAINT fk_complaint_tenant FOREIGN KEY (tenant_id) REFERENCES tenant.tenant(id)
        );
    """)
    op.execute("CREATE INDEX ON complaint.complaint (tenant_id, customer_id);")
    op.execute("CREATE INDEX ON complaint.complaint (tenant_id, status);")
    
    op.execute("ALTER TABLE complaint.complaint ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY tenant_isolation ON complaint.complaint
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
    """)

    op.execute("""
        CREATE TABLE complaint.complaint_assignment (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            complaint_id UUID NOT NULL REFERENCES complaint.complaint(id) ON DELETE CASCADE,
            assigned_to UUID NOT NULL,
            assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by UUID
        );
    """)
    
    op.execute("ALTER TABLE complaint.complaint_assignment ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY tenant_isolation ON complaint.complaint_assignment
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
    """)

    op.execute("""
        CREATE TABLE complaint.complaint_resolution (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            complaint_id UUID NOT NULL REFERENCES complaint.complaint(id) ON DELETE CASCADE,
            outcome VARCHAR(50) NOT NULL,
            resolution_notes TEXT NOT NULL,
            resolved_by UUID NOT NULL,
            resolved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    
    op.execute("ALTER TABLE complaint.complaint_resolution ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY tenant_isolation ON complaint.complaint_resolution
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
    """)

    op.execute("GRANT USAGE ON SCHEMA complaint TO lpg_app;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA complaint TO lpg_app;")


def downgrade() -> None:
    op.execute("DROP SCHEMA complaint CASCADE;")
