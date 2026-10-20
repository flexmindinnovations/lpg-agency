"""sync tenant status and plan with the licence

QA finding DA-28: the Agencies list and Settings > Agency showed "Trial /
Standard" for an agency whose licence was "Active / Premium" - the two were
stored separately and never kept in step. From now on activating a licence (or
changing its plan tier) updates the tenant (`Tenant.apply_license`); this
brings existing agencies with an activated, unrevoked licence into line once.
Suspended and closed agencies keep their status.

Revision ID: 21a625272f0b
Revises: c48cbf996d8c
Create Date: 2026-10-20 12:30:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "21a625272f0b"
down_revision: str | None = "c48cbf996d8c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE tenant.tenant t
        SET subscription_plan = l.plan_tier,
            status = CASE WHEN t.status = 'trial' THEN 'active' ELSE t.status END
        FROM platform.license l
        WHERE l.tenant_id = t.id
          AND l.activated_at IS NOT NULL
          AND l.revoked_at IS NULL
    """)


def downgrade() -> None:
    # Data alignment only: the previous, contradictory values are not worth
    # restoring and are not recorded anywhere.
    pass
