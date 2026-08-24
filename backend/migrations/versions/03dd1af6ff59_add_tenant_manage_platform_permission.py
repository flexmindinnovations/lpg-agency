"""add tenant:manage_platform permission code

Revision ID: 03dd1af6ff59
Revises: fdd3afde337c
Create Date: 2026-08-23

One new permission code for the Platform Console's Agency Management
capability: `tenant:manage_platform` — list every tenant, suspend/
reactivate/close any tenant (`super_admin` only, **live-checked** — same
sensitivity tier `license:manage_platform`/`feature_flags:manage_platform`
use; suspending an agency is at least as consequential as revoking a
license).

**Backfills `identity.identity_user_permission`, not just `role_permission`**
— mirrors `70666eaa687b`'s exact 3-step pattern (permission -> role_permission
-> backfill existing users), the established convention since `8c221c3e0a91`:
permission resolution at login/token-issue time is per-user only and never
re-consults `role_permission`, so skipping the backfill silently grants the
new code to nobody who already exists.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "03dd1af6ff59"
down_revision: str | None = "fdd3afde337c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"

_NEW_PERMISSIONS = [
    "tenant:manage_platform",
]

_NEW_ROLE_PERMISSION_MATRIX: list[tuple[str, list[str]]] = [
    ("tenant:manage_platform", ["super_admin"]),
]


def upgrade() -> None:
    permission_table = sa.table(
        "permission",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        schema=_SCHEMA,
    )
    permission_ids = {code: uuid.uuid4() for code in _NEW_PERMISSIONS}
    op.bulk_insert(
        permission_table,
        [
            {
                "id": permission_ids[code],
                "code": code,
                "resource": code.split(":")[0],
                "action": code.split(":")[1],
            }
            for code in _NEW_PERMISSIONS
        ],
    )

    for permission_code, role_codes in _NEW_ROLE_PERMISSION_MATRIX:
        for role_code in role_codes:
            op.execute(
                sa.text(f"""
                    INSERT INTO {_SCHEMA}.role_permission (id, role_id, permission_id, created_at)
                    SELECT gen_random_uuid(), r.id, :permission_id, now()
                    FROM {_SCHEMA}.role r
                    WHERE r.code = :role_code
                """).bindparams(permission_id=permission_ids[permission_code], role_code=role_code)
            )

            # Backfill existing users of that role — see module docstring.
            op.execute(
                sa.text(f"""
                    INSERT INTO {_SCHEMA}.identity_user_permission
                        (id, user_id, permission_id, created_at)
                    SELECT gen_random_uuid(), u.id, :permission_id, now()
                    FROM {_SCHEMA}.identity_user u
                    WHERE u.role = :role_code
                      AND NOT EXISTS (
                          SELECT 1 FROM {_SCHEMA}.identity_user_permission existing
                          WHERE existing.user_id = u.id AND existing.permission_id = :permission_id
                      )
                """).bindparams(permission_id=permission_ids[permission_code], role_code=role_code)
            )


def downgrade() -> None:
    codes_literal = ", ".join(f"'{code}'" for code in _NEW_PERMISSIONS)
    op.execute(f"""
        DELETE FROM {_SCHEMA}.identity_user_permission
        WHERE permission_id IN (
            SELECT id FROM {_SCHEMA}.permission WHERE code IN ({codes_literal})
        )
    """)
    op.execute(f"""
        DELETE FROM {_SCHEMA}.role_permission
        WHERE permission_id IN (
            SELECT id FROM {_SCHEMA}.permission WHERE code IN ({codes_literal})
        )
    """)
    op.execute(f"DELETE FROM {_SCHEMA}.permission WHERE code IN ({codes_literal})")
