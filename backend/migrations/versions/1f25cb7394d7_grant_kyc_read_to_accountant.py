"""grant kyc read to accountant

Revision ID: 1f25cb7394d7
Revises: de17b27d462e
Create Date: 2026-08-15 11:32:04.741061

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op
import sqlalchemy as sa


if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = '1f25cb7394d7'
down_revision: str | None = 'de17b27d462e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


from typing import TYPE_CHECKING
import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = '1f25cb7394d7'
down_revision: str | None = 'de17b27d462e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"

def upgrade() -> None:
    # Grant kyc:read to accountant and dispatcher
    for role_code in ["accountant", "dispatcher"]:
        op.execute(
            sa.text(f"""
                INSERT INTO {_SCHEMA}.role_permission (id, role_id, permission_id, created_at)
                SELECT gen_random_uuid(), r.id, p.id, now()
                FROM {_SCHEMA}.role r, {_SCHEMA}.permission p
                WHERE r.code = :role_code AND p.code = 'kyc:read'
                ON CONFLICT DO NOTHING
            """).bindparams(role_code=role_code)
        )

def downgrade() -> None:
    for role_code in ["accountant", "dispatcher"]:
        op.execute(
            sa.text(f"""
                DELETE FROM {_SCHEMA}.role_permission
                WHERE role_id = (SELECT id FROM {_SCHEMA}.role WHERE code = :role_code)
                  AND permission_id = (SELECT id FROM {_SCHEMA}.permission WHERE code = 'kyc:read')
            """).bindparams(role_code=role_code)
        )
