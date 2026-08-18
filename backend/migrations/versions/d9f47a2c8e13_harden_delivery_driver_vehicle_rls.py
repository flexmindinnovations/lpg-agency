"""harden delivery.driver / delivery.vehicle: null-safe RLS predicate

The last two tenant-scoped tables whose RLS predicate diverges from the
convention, found by `scripts/verify_env_parity.sql`. Their grants and
FORCE RLS are already correct; only the predicate is wrong.

These two are a step worse than the `NULLIF` cases corrected in
`b4d19e7c3a52` and `c5e83f1a7b96`. Those at least passed `missing_ok`:

    tenant_id = (current_setting('app.current_tenant_id', true))::uuid

`c9a1e6b4f7d3` omitted that second argument entirely:

    tenant_id = (current_setting('app.current_tenant_id'))::uuid

With `missing_ok` absent, an unset GUC does not return `''` to fail on the
uuid cast — `current_setting` itself raises `unrecognized configuration
parameter` before the cast is reached. So any connection that has not run
`SET app.current_tenant_id` errors out on *every* query touching drivers or
vehicles, rather than simply returning no rows. Request-scoped traffic always
sets it, which is why this never surfaced; background jobs and domain-event
handlers do not always, and those are precisely the paths where a hard error
is hardest to trace back to its cause.

Both policies move to the standard null-safe form, which degrades to "no rows"
on an unscoped connection.

Revision ID: d9f47a2c8e13
Revises: c5e83f1a7b96
Create Date: 2026-08-17
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "d9f47a2c8e13"
down_revision: str | None = "c5e83f1a7b96"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"

# (table, policy name) — the policy names are per-table here, unlike the shared
# `tenant_isolation` name used by newer schemas.
_TARGETS: tuple[tuple[str, str], ...] = (
    ("driver", "tenant_isolation_driver"),
    ("vehicle", "tenant_isolation_vehicle"),
)


def upgrade() -> None:
    for table, policy in _TARGETS:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON delivery.{table}")
        op.execute(f"""
            CREATE POLICY {policy} ON delivery.{table}
            USING ({_PREDICATE})
            WITH CHECK ({_PREDICATE})
        """)


def downgrade() -> None:
    legacy = "tenant_id = (current_setting('app.current_tenant_id'))::uuid"

    for table, policy in _TARGETS:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON delivery.{table}")
        op.execute(f"""
            CREATE POLICY {policy} ON delivery.{table}
            FOR ALL
            TO PUBLIC
            USING ({legacy})
        """)
