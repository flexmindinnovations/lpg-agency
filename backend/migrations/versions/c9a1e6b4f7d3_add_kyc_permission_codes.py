"""add distinct kyc permission codes

Revision ID: c9a1e6b4f7d3
Revises: 4f4645fda65e
Create Date: 2026-08-10 21:00:00.000000

Additive only — existing rows in `identity.permission`/`identity.role_permission`
are never edited in place (established by `fa52b77ec442`'s own seed data).

`docs/data/17-api-security.md` §10 documents that KYC documents are more
sensitive PII than a general customer profile and must be gated by a
permission "distinct from general `customers:read`" — `4f4645fda65e`
(Phase 8's customer schema migration) shipped without this, reusing
`customers:read`/`customers:update` for KYC submit/verify/view. This
migration adds the two missing codes and narrows the role grant relative to
`customers:read` (dispatcher/accountant/driver do not get KYC access):

- `kyc:read` — view a customer's KYC documents (`agency_admin`, `manager`)
- `kyc:manage` — submit/verify a customer's KYC documents (`agency_admin`, `manager`)
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "c9a1e6b4f7d3"
down_revision: str | None = "4f4645fda65e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"

_NEW_PERMISSIONS = [
    "kyc:read",
    "kyc:manage",
]

_NEW_ROLE_PERMISSION_MATRIX: list[tuple[str, list[str]]] = [
    ("kyc:read", ["agency_admin", "manager"]),
    ("kyc:manage", ["agency_admin", "manager"]),
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


def downgrade() -> None:
    codes_literal = ", ".join(f"'{code}'" for code in _NEW_PERMISSIONS)
    op.execute(f"""
        DELETE FROM {_SCHEMA}.role_permission
        WHERE permission_id IN (
            SELECT id FROM {_SCHEMA}.permission WHERE code IN ({codes_literal})
        )
    """)
    op.execute(f"DELETE FROM {_SCHEMA}.permission WHERE code IN ({codes_literal})")
