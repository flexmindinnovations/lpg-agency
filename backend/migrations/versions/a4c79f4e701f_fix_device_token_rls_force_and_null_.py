"""fix notification.device_token RLS: FORCE + null-safe predicate

`f3a9c1e07b42_create_device_token_table.py` enabled RLS on
`notification.device_token` but never FORCEd it — the table's owning role
(`lpg_admin`/migration role) bypasses RLS entirely by default unless FORCE
is set, so a query run as the owning role saw every tenant's device tokens
regardless of `app.current_tenant_id`. Its policy predicate was also missing
the null-safe `NULLIF(...)` wrapper every other table's RLS policy uses
(e.g. `d8b300ef303f_create_compliance_schema_scale_table.py`'s `_enable_rls`
helper) — `current_setting('app.current_tenant_id', true)` returns `''`,
not NULL, when the GUC was never set, and `''::uuid` raises
`invalid input syntax for type uuid` instead of the policy safely evaluating
to false and returning zero rows for an unscoped session.

Found by `scripts/verify_env_parity.sql` while verifying an unrelated
migration (Weighment Part 1) — this table predates that work and was never
touched by it; fixed here as its own scoped migration.

Revision ID: a4c79f4e701f
Revises: 6a7d486aa8ec
Create Date: 2026-09-07 19:28:49.125263

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a4c79f4e701f"
down_revision: str | None = "6a7d486aa8ec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "notification"
_TABLE = "device_token"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY")

    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.{_TABLE}")
    op.execute(f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.{_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)


def downgrade() -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} NO FORCE ROW LEVEL SECURITY")

    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.{_TABLE}")
    op.execute(f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.{_TABLE}
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)
