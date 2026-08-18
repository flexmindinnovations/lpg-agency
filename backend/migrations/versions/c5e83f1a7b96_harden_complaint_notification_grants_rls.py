"""harden complaint + notification: grants, FORCE RLS, null-safe policies

An environment-parity sweep across `lpg_dev`, `lpg_test` and `lpg_uat` found the
`complaint` and `notification` schemas to be the only tenant-scoped tables in
the database still diverging from the convention every other schema follows.
This is the same class of defect already corrected for `delivery.route`
(Phase 12), the `cylinder_ledger` schema (`a7c2e91b5d84`) and `tenant.employee`
(`b4d19e7c3a52`) — the sixth occurrence, which is why the parity query that
found it is now checked in as `scripts/verify_env_parity.sql`.

Three deviations are corrected here, across all five tables:

1. **`GRANT` hardcoded the role name, or was missing entirely.**
   `4e7fc25f58b3` wrote `GRANT ... TO lpg_app` literally, so `lpg_uat` — whose
   application role is `lpg_app_uat` — got nothing and every complaint query
   there failed with "permission denied". `e60b8b86b965` granted nothing at all
   for the `notification` schema. Both now use the `CASE current_database()`
   role resolution `4f8b2d6a9c1e` established, which also makes the migration a
   no-op where the app role does not exist.
2. **`FORCE ROW LEVEL SECURITY` missing** on all five tables — RLS was enabled
   but the table owner silently bypassed it.
3. **Policy predicate was not null-safe.** `(current_setting(
   'app.current_tenant_id', true))::uuid` yields `''::uuid` when the setting is
   unset, which *raises* rather than evaluating to NULL. The `NULLIF(...)` form
   used everywhere else degrades to "no rows" instead of erroring on an
   unscoped connection (background jobs, event handlers).

The new policies also spell out `WITH CHECK` explicitly. This is a readability
change, *not* a security fix: on a `FOR ALL` policy Postgres already reuses the
`USING` expression as the write-side check when `WITH CHECK` is omitted, which
was verified directly rather than assumed — as `lpg_app`, an INSERT naming
another tenant is rejected with "new row violates row-level security policy"
under the old `USING`-only policy. (Verify this as the *application* role, never
as `lpg_admin`: that role is a superuser with `rolbypassrls`, so it ignores RLS
entirely and makes any such test come back falsely green.) Stating the clause
explicitly means a later edit narrowing `FOR ALL` to `FOR SELECT` cannot quietly
drop the write-side check.

Revision ID: c5e83f1a7b96
Revises: b4d19e7c3a52
Create Date: 2026-08-17
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "c5e83f1a7b96"
down_revision: str | None = "b4d19e7c3a52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_POLICY = "tenant_isolation"

# (schema, table). All five are tenant-scoped and all five are read *and*
# written by the application, so each takes SELECT/INSERT/UPDATE — the same
# grant set `4e7fc25f58b3` intended for `complaint` before the role name was
# hardcoded. No DELETE anywhere: nothing in this application hard-deletes a
# complaint or a notification.
_TABLES: tuple[tuple[str, str], ...] = (
    ("complaint", "complaint"),
    ("complaint", "complaint_assignment"),
    ("complaint", "complaint_resolution"),
    ("notification", "in_app_notification"),
    ("notification", "notification_log"),
)

_SCHEMAS = ("complaint", "notification")

_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"


def _role_block(body: str) -> str:
    """Wrap `body` so it runs only where the environment's app role exists."""
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                {body}
            END IF;
        END
        $$;
    """


def upgrade() -> None:
    grants = "".join(
        f"EXECUTE format('GRANT USAGE ON SCHEMA {schema} TO %I', app_role);"
        for schema in _SCHEMAS
    ) + "".join(
        f"EXECUTE format("
        f"'GRANT SELECT, INSERT, UPDATE ON {schema}.{table} TO %I', app_role);"
        for schema, table in _TABLES
    )
    op.execute(_role_block(grants))

    for schema, table in _TABLES:
        op.execute(f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {schema}.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS {_POLICY} ON {schema}.{table}")
        op.execute(f"""
            CREATE POLICY {_POLICY} ON {schema}.{table}
            USING ({_PREDICATE})
            WITH CHECK ({_PREDICATE})
        """)


def downgrade() -> None:
    legacy = "tenant_id = (current_setting('app.current_tenant_id', true))::uuid"

    for schema, table in _TABLES:
        op.execute(f"DROP POLICY IF EXISTS {_POLICY} ON {schema}.{table}")
        op.execute(f"""
            CREATE POLICY {_POLICY} ON {schema}.{table}
            FOR ALL
            TO PUBLIC
            USING ({legacy})
        """)
        op.execute(f"ALTER TABLE {schema}.{table} NO FORCE ROW LEVEL SECURITY")

    revokes = "".join(
        f"EXECUTE format('REVOKE ALL ON {schema}.{table} FROM %I', app_role);"
        for schema, table in _TABLES
    )
    op.execute(_role_block(revokes))
