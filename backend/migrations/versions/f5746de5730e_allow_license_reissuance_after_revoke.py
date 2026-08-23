"""allow license reissuance after revoke

Revision ID: f5746de5730e
Revises: 70666eaa687b
Create Date: 2026-08-23

`platform.license.tenant_id` was a plain UNIQUE column, so `License.revoke()`
(which only sets `revoked_at` — never a soft-delete, and deliberately so:
`ListLicensesUseCase`/the License Issuance page's own audit trail needs every
past key, not just the current one) permanently blocked `IssueLicenseUseCase`
from ever issuing that tenant a replacement: the INSERT hit `uq_license_
tenant_id` and raised a raw, unhandled `IntegrityError`. Confirmed during
manual dev-environment testing — the only way to re-test a revoked tenant was
deleting the old row directly via SQL, which no `super_admin` can do through
any UI or API this feature ships.

**Fix: a partial unique index, not a soft-delete.** `uq_license_tenant_id`
becomes `uq_license_tenant_id_active`, scoped `WHERE revoked_at IS NULL` — a
tenant may have any number of historical revoked license rows, but at most
one non-revoked (current) one at a time. This preserves full license history
for audit/support purposes (the same reason `revoke()` was never a
soft-delete to begin with) rather than the alternative this migration's own
issue considered — having `IssueLicenseUseCase` supersede/hide the old row —
which would have fought the audit trail this table's `is_deleted`/`deleted_
at`/`deleted_by` columns and `ListLicensesUseCase` already exist to support.

**`SqlAlchemyLicenseRepository.get_by_tenant_id` must change to match** (see
that file's own diff, landing alongside this migration): with more than one
row now possible per tenant, "the first row found" is no longer well-defined.
It now orders by `issued_at DESC LIMIT 1` — "the tenant's current or most
recently superseded license" — so `RevokeLicenseUseCase`/status checks still
resolve to the active license when one exists, and correctly fall back to
the most recent revoked one (not `None`, which would misreport a revoked
tenant as merely `PENDING_ACTIVATION`) when none is.

**`platform.license_find_by_tenant_id` needs the identical `ORDER BY ...
LIMIT 1`**, or it breaks outright, not just silently: it's declared `RETURNS
platform.license` (a single row, not `SETOF`) — Postgres raises "query
returned more than one row" at call time the moment any tenant this
migration unblocks (revoked, then reissued) has two rows to choose between,
which would crash login for exactly the tenants this fix exists to help.
`CREATE OR REPLACE FUNCTION` with an unchanged signature keeps its existing
`EXECUTE` grant, so no re-grant is needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "f5746de5730e"
down_revision: str | None = "70666eaa687b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLATFORM_SCHEMA = "platform"


def upgrade() -> None:
    op.drop_constraint(
        "uq_license_tenant_id", "license", schema=_PLATFORM_SCHEMA, type_="unique"
    )
    op.execute(f"""
        CREATE UNIQUE INDEX uq_license_tenant_id_active
        ON {_PLATFORM_SCHEMA}.license (tenant_id)
        WHERE revoked_at IS NULL
    """)

    op.execute(f"""
        CREATE OR REPLACE FUNCTION {_PLATFORM_SCHEMA}.license_find_by_tenant_id(p_tenant_id uuid)
        RETURNS {_PLATFORM_SCHEMA}.license
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_PLATFORM_SCHEMA}, pg_temp
        AS $$
            SELECT * FROM {_PLATFORM_SCHEMA}.license
            WHERE tenant_id = p_tenant_id
            ORDER BY issued_at DESC
            LIMIT 1;
        $$;
    """)


def downgrade() -> None:
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {_PLATFORM_SCHEMA}.license_find_by_tenant_id(p_tenant_id uuid)
        RETURNS {_PLATFORM_SCHEMA}.license
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_PLATFORM_SCHEMA}, pg_temp
        AS $$
            SELECT * FROM {_PLATFORM_SCHEMA}.license WHERE tenant_id = p_tenant_id;
        $$;
    """)

    op.execute(f"DROP INDEX IF EXISTS {_PLATFORM_SCHEMA}.uq_license_tenant_id_active")
    # Fails if any tenant currently holds more than one license row (i.e. was
    # revoked and reissued while this migration was applied) — an accepted,
    # unavoidable downgrade limitation: a plain UNIQUE constraint cannot
    # coexist with the duplicate `tenant_id`s this migration's whole point
    # was to allow.
    op.create_unique_constraint(
        "uq_license_tenant_id", "license", ["tenant_id"], schema=_PLATFORM_SCHEMA
    )
