"""grant_missing_permissions_to_admin

Revision ID: a631835ec588
Revises: a907e81bc74c
Create Date: 2026-08-15 22:19:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a631835ec588'
down_revision: str | None = 'a907e81bc74c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS_TO_GRANT = [
    "complaints:create",
    "complaints:read",
    "complaints:resolve",
    "drivers:read",
    "drivers:manage",
    "vehicles:read",
    "vehicles:manage",
    "users:manage",
    "kyc:manage",
    "kyc:read"
]

def upgrade() -> None:
    # Get role IDs
    for role_name in ['agency_admin', 'super_admin']:
        for perm in PERMISSIONS_TO_GRANT:
            op.execute(
                sa.text("""
                    INSERT INTO identity.role_permission (id, role_id, permission_id)
                    SELECT gen_random_uuid(), r.id, p.id
                    FROM identity.role r
                    CROSS JOIN identity.permission p
                    WHERE r.code = :role_name AND p.code = :perm
                    ON CONFLICT ON CONSTRAINT uq_identity_role_permission DO NOTHING
                """).bindparams(role_name=role_name, perm=perm)
            )

def downgrade() -> None:
    for role_name in ['agency_admin', 'super_admin']:
        for perm in PERMISSIONS_TO_GRANT:
            op.execute(
                sa.text("""
                    DELETE FROM identity.role_permission rp
                    USING identity.role r, identity.permission p
                    WHERE rp.role_id = r.id AND rp.permission_id = p.id
                    AND r.code = :role_name AND p.code = :perm
                """).bindparams(role_name=role_name, perm=perm)
            )
