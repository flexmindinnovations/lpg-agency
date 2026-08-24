"""allow platform (tenant-less) audit log entries

Revision ID: 63c55035ebbb
Revises: 03dd1af6ff59
Create Date: 2026-08-24

`audit.audit_log.tenant_id` has always been nullable with no foreign key
(`40065f2b4dc3_create_audit_schema_and_audit_log_table_.py`) — the schema
already anticipated a "no tenant" audit event. Its RLS policy never did:
`tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid`
means a session with **no** `app.current_tenant_id` set at all (a genuinely
unscoped session — the shape `get_platform_unit_of_work_factory`
(`api/v1/dependencies/platform.py`) opens for `tenant_id=None` calls, i.e.
every list-all read AND every platform-wide write with no target tenant,
like creating a platform feature flag) can **never** satisfy this
predicate: SQL's `x = NULL` is never `TRUE`, not even when `x` is itself
`NULL`. Confirmed live: `POST /platform/feature-flags` 500s with
`InsufficientPrivilegeError: new row violates row-level security policy for
table "audit_log"` the moment its `UnitOfWork.commit()` flushes and
`AuditRecorder` tries to write the audit row — this was never exercisable
before this migration's feature, since every prior caller of `get_unit_of_
work` always had a real tenant (D-01: only `super_admin` has none, and
`super_admin` sessions couldn't reach any `UnitOfWork`-backed endpoint at
all until now).

**Fix**: the policy now also allows a row whose `tenant_id` is the
reserved "platform" sentinel (`00000000-0000-0000-0000-000000000000` — the
nil UUID, never a real `tenant.tenant.id` since those are always `gen_
random_uuid()`-generated) — but *only* when the current session's own
`app.current_tenant_id` is unset. That second condition is what keeps this
narrow: an ordinary tenant-scoped session always has a real
`app.current_tenant_id`, so it can never satisfy the new branch and gains
no new visibility into — or ability to forge — platform-level audit rows.
Only `get_platform_unit_of_work_factory`'s genuinely unscoped session
(`Database.open_session(tenant_id=None)`) can ever write or read one.

The nil-UUID sentinel (not `NULL` itself, despite the column already being
nullable) is a deliberate choice: `TenantContext.tenant_id`
(`application/common/ports.py`) is `uuid.UUID`, not `uuid.UUID | None` —
changing that shared protocol to accommodate one audit-log edge case would
ripple into every tenant-scoped use case and repository in this codebase
for no benefit (Platform Console plan's own D-1 makes the same call for
`PlatformPrincipal` vs. a nullable field on `AuthenticatedPrincipal`). The
sentinel keeps `RequestTenantContext`/`AuditRecorder` completely unchanged;
only this one RLS predicate needed to learn about it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "63c55035ebbb"
down_revision: str | None = "03dd1af6ff59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "audit"
_TABLE = "audit_log"
_POLICY = "rls_audit_log_tenant_isolation"
#: Never a real `tenant.tenant.id` — those are always `gen_random_uuid()`.
#: Mirrors the literal in `api/v1/dependencies/platform.py`'s
#: `get_platform_unit_of_work_factory` — keep both in sync if this ever
#: changes.
_PLATFORM_SENTINEL_TENANT_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS {_POLICY} ON {_SCHEMA}.{_TABLE}")
    op.execute(f"""
        CREATE POLICY {_POLICY}
        ON {_SCHEMA}.{_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            OR (
                tenant_id = '{_PLATFORM_SENTINEL_TENANT_ID}'::uuid
                AND NULLIF(current_setting('app.current_tenant_id', true), '') IS NULL
            )
        )
    """)


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS {_POLICY} ON {_SCHEMA}.{_TABLE}")
    op.execute(f"""
        CREATE POLICY {_POLICY}
        ON {_SCHEMA}.{_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)
