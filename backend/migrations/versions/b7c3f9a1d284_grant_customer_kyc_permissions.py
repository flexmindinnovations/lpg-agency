"""grant customer role kyc:read and kyc:manage permissions

`kyc:read`/`kyc:manage` were granted only to `agency_admin`/`manager`
(`c9a1e6b4f7d3_add_kyc_permission_codes.py`) -- the `customer` role has
neither, so there's no self-service KYC upload path today even though the
domain logic and endpoints already support it.

`kyc:manage` also gates `POST /{customer_id}/kyc/{doc_id}/verify` (staff
approving/rejecting a document) -- granting it to `customer` would let a
customer verify their own document, which defeats the point of
verification. That's handled in the router (`customer.py`'s `verify_kyc`
now hard-blocks `principal.role == "customer"` regardless of permission),
not by withholding the permission grant -- `submit_kyc`/`list_kyc_documents`
legitimately need the same code for a customer's own self-service path.

Revision ID: b7c3f9a1d284
Revises: d4e8f21a9c56
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b7c3f9a1d284"
down_revision: str | None = "d4e8f21a9c56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLES_SQL = "('customer')"
_PERMISSIONS_SQL = "('kyc:read', 'kyc:manage')"


def upgrade() -> None:
    op.execute(f"""
        INSERT INTO identity.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM identity.role r
        CROSS JOIN identity.permission p
        WHERE r.code IN {_ROLES_SQL}
          AND p.code IN {_PERMISSIONS_SQL}
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)

    # Backfill existing customer users — see the accountant/driver
    # equivalents (`d4e8f21a9c56`, `76aa61425c66`) for why this step is
    # necessary and not optional: permission resolution is per-user,
    # materialized at account-creation time, never read live from
    # role_permission.
    op.execute(f"""
        INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, p.id, now()
        FROM identity.identity_user u
        JOIN identity.permission p ON p.code IN {_PERMISSIONS_SQL}
        WHERE u.role IN {_ROLES_SQL}
          AND NOT EXISTS (
              SELECT 1 FROM identity.identity_user_permission existing
              WHERE existing.user_id = u.id AND existing.permission_id = p.id
          )
    """)


def downgrade() -> None:
    op.execute(f"""
        DELETE FROM identity.identity_user_permission
        WHERE permission_id IN (SELECT id FROM identity.permission WHERE code IN {_PERMISSIONS_SQL})
          AND user_id IN (SELECT id FROM identity.identity_user WHERE role IN {_ROLES_SQL})
    """)
    op.execute(f"""
        DELETE FROM identity.role_permission
        WHERE permission_id IN (SELECT id FROM identity.permission WHERE code IN {_PERMISSIONS_SQL})
          AND role_id IN (SELECT id FROM identity.role WHERE code IN {_ROLES_SQL})
    """)
