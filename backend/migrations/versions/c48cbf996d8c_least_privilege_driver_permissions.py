"""least-privilege driver permissions

QA finding DA-05: a driver token could post goods receipts and record (and,
before DA-04, apply) warehouse reconciliation counts, because the `driver` role
held `inventory:load`, which gates GRNs, load transfers, van deliveries and
collections, status changes and reconciliation counts. None of those are Driver
App actions: a driver's van load is confirmed through `routes:deliver`
(`POST /routes/{id}/confirm-load`) and every delivery-side inventory movement is
made by the order/route use cases, not by these endpoints.

Reviewing every other driver grant against what the Driver App actually calls:

* `customers:read` let a driver list every customer's name, phone and address
  (`GET /customers`). The app never calls the customer API; stop details come
  from `routes:read`.
* `drivers:read` let a driver list every driver's phone and licence. The app only
  needs `GET /drivers/me`, which now just needs a signed-in driver.
* `vehicles:read` is not used by the app at all.

All four are removed from the role and from every existing driver account (the
permissions are materialised per user since `8c221c3e0a91`). What stays:
`orders:read`, `orders:dispatch`, `orders:deliver` (each scoped to the driver's
own orders in the router), `routes:read`, `routes:deliver`,
`cash_handovers:declare`.

Revision ID: c48cbf996d8c
Revises: 9aee17794c55
Create Date: 2026-10-20 12:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "c48cbf996d8c"
down_revision: str | None = "9aee17794c55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"
_REVOKED = ["inventory:load", "customers:read", "drivers:read", "vehicles:read"]


def upgrade() -> None:
    op.execute(
        sa.text(f"""
            DELETE FROM {_SCHEMA}.role_permission
            WHERE role_id = (SELECT id FROM {_SCHEMA}.role WHERE code = 'driver')
              AND permission_id IN (
                  SELECT id FROM {_SCHEMA}.permission WHERE code = ANY(:codes)
              )
        """).bindparams(codes=_REVOKED)
    )
    op.execute(
        sa.text(f"""
            DELETE FROM {_SCHEMA}.identity_user_permission up
            USING {_SCHEMA}.identity_user u, {_SCHEMA}.permission p
            WHERE up.user_id = u.id
              AND up.permission_id = p.id
              AND u.role = 'driver'
              AND p.code = ANY(:codes)
        """).bindparams(codes=_REVOKED)
    )


def downgrade() -> None:
    op.execute(
        sa.text(f"""
            INSERT INTO {_SCHEMA}.role_permission (id, role_id, permission_id, created_at)
            SELECT gen_random_uuid(), r.id, p.id, now()
            FROM {_SCHEMA}.role r, {_SCHEMA}.permission p
            WHERE r.code = 'driver' AND p.code = ANY(:codes)
            ON CONFLICT DO NOTHING
        """).bindparams(codes=_REVOKED)
    )
    op.execute(
        sa.text(f"""
            INSERT INTO {_SCHEMA}.identity_user_permission
                (id, user_id, permission_id, created_at)
            SELECT gen_random_uuid(), u.id, p.id, now()
            FROM {_SCHEMA}.identity_user u, {_SCHEMA}.permission p
            WHERE u.role = 'driver' AND p.code = ANY(:codes)
            ON CONFLICT DO NOTHING
        """).bindparams(codes=_REVOKED)
    )
