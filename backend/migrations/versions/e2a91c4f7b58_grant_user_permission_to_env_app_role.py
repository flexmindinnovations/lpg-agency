"""grant identity.identity_user_permission to the per-environment app role

`8c221c3e0a91` ended with a literal `GRANT ... TO lpg_app`. Because `lpg_app`
is a cluster-level role it exists in every database on the local Postgres
instance, so the statement succeeded on `lpg_uat` — it simply granted to the
wrong role. `lpg_app_uat`, the role the application actually connects as
there, got nothing, and every query touching user permissions in UAT would
have failed with "permission denied for table identity_user_permission".

`8c221c3e0a91` has since been corrected to resolve the role the same way the
rest of the tree does, but it had already run on `lpg_uat`, so that fix cannot
apply itself retroactively. This migration closes the gap.

`identity_user_permission` carries no `tenant_id`, which is why
`scripts/verify_env_parity.sql` did not flag it — that query only considered
tenant-scoped tables. It now checks grants across every application table
regardless, and this was the only table it found missing.

Revision ID: e2a91c4f7b58
Revises: d9f47a2c8e13
Create Date: 2026-08-17
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "e2a91c4f7b58"
down_revision: str | None = "d9f47a2c8e13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "identity.identity_user_permission"


def upgrade() -> None:
    op.execute(f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT USAGE ON SCHEMA identity TO %I', app_role);
                EXECUTE format(
                    'GRANT SELECT, INSERT, UPDATE, DELETE ON {_TABLE} TO %I', app_role
                );
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    # Only revokes from the per-environment role. `lpg_app`'s grant on a
    # non-UAT database was made by `8c221c3e0a91` and is that migration's to
    # undo, not this one's.
    op.execute(f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('REVOKE ALL ON {_TABLE} FROM %I', app_role);
            END IF;
        END
        $$;
    """)
