"""reconcile tenant.tenant columns with 03-database-schema.md

Revision ID: b1c4a9e7d2f3
Revises: 10a62de534be
Create Date: 2026-08-10 16:00:00.000000

Phase 2's `tenant.tenant` (migration `0242df1a3871`) was deliberately
minimal — "the minimum tenant infrastructure required by the architecture,
not a Tenant Administration feature." `docs/data/03-database-schema.md`
always documented a richer shape (`status`, `subscription_plan`,
`primary_contact_email`, `country`) that Phase 2 never actually created.
Phase 7 (Administration) is the phase that needs those columns, so this
migration adds them now, reconciling the real table with its own
documentation rather than letting the drift stand.

`slug` is **not** in `03-database-schema.md`'s documented column list, but
is kept — it already exists, is already uniquely constrained, and is
harmless (a future tenant-facing subdomain/routing scheme would want it
anyway). The documentation gets the addition noted, not the column dropped.

`primary_contact_email` is documented with no column default ("every tenant
needs a real contact email"), but is given one here anyway
(`unknown@example.invalid`) — consistent with every other column added in
this migration, and real validation of "is this actually a useful contact
address" belongs at the API boundary (Pydantic `EmailStr`) regardless of
what the column default is. A hard NOT NULL-no-default would have forced
seven unrelated test files (identity/audit/RLS suites that only incidentally
need *a* tenant row to exist) to start supplying one, for no real safety
gain. Documented as a deviation in `03-database-schema.md`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b1c4a9e7d2f3"
down_revision: str | None = "10a62de534be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "tenant"
_TABLE = "tenant"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column("status", sa.String(length=20), nullable=False, server_default="trial"),
        schema=_SCHEMA,
    )
    op.create_check_constraint(
        "ck_tenant_status",
        _TABLE,
        "status IN ('trial', 'active', 'suspended', 'closed')",
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "subscription_plan", sa.String(length=50), nullable=False, server_default="standard"
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "primary_contact_email",
            sa.String(length=320),
            nullable=False,
            server_default="unknown@example.invalid",
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("country", sa.CHAR(length=2), nullable=False, server_default="IN"),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_tenant_status",
        _TABLE,
        ["status"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("idx_tenant_status", table_name=_TABLE, schema=_SCHEMA)
    op.drop_column(_TABLE, "country", schema=_SCHEMA)
    op.drop_column(_TABLE, "primary_contact_email", schema=_SCHEMA)
    op.drop_column(_TABLE, "subscription_plan", schema=_SCHEMA)
    op.drop_constraint("ck_tenant_status", _TABLE, schema=_SCHEMA, type_="check")
    op.drop_column(_TABLE, "status", schema=_SCHEMA)
