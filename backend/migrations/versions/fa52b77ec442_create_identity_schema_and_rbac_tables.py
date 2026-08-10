"""create identity schema and RBAC reference tables

Revision ID: fa52b77ec442
Revises: 40065f2b4dc3
Create Date: 2026-08-10 09:00:00.000000

Phase 6 (Authentication & Authorization). Five tables:

- `identity.role`, `identity.permission` — Platform-Global reference data
  (`docs/data/05-reference-data.md` §8/§9), seeded here per that doc's own
  rule ("Platform-Global reference data changes ship via Alembic migration +
  code review"). No `tenant_id`, no RLS — identical to every tenant, by
  definition.
- `identity.role_permission` — seeded with exactly the 9-row representative
  matrix from `docs/data/17-api-security.md` §6, expanded per role. The
  "(self)"/"(own)" qualifiers on some matrix cells are row-level scoping
  beyond what a role→permission grant can express — that's each business
  feature's own query-filtering concern when it's built (Phase 8+), not this
  table's job. **Not a complete matrix** — the doc itself calls it
  "illustrative, not exhaustive"; further grants arrive with each business
  phase as its own permission-gated endpoints are built, not invented here
  speculatively.
- `identity.identity_user`, `identity.user_role` — tenant-scoped, RLS
  applied. `identity_user.tenant_id` is nullable — null only for Super Admin
  (`docs/data/03-database-schema.md`), the same documented exception
  `audit.audit_log` already established for a table that must not force a
  tenant context prematurely.

Migration 2 (`10a62de534be`) covers `identity.refresh_token` and
`identity.password_reset_token` separately — session/token data has a very
different write pattern (high-volume, append-heavy) from this migration's
low-change reference and account data.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "fa52b77ec442"
down_revision: str | None = "40065f2b4dc3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"

# D-38's confirmed 8-role list (docs/business/decisions.md).
_ROLES: list[tuple[str, str]] = [
    ("super_admin", "Super Admin"),
    ("agency_admin", "Agency Admin"),
    ("manager", "Manager"),
    ("warehouse_staff", "Warehouse Staff"),
    ("dispatcher", "Dispatcher"),
    ("accountant", "Accountant"),
    ("driver", "Driver"),
    ("customer", "Customer"),
]

# docs/data/05-reference-data.md §9's representative permission catalog,
# decomposed into individual (resource, action) codes.
_PERMISSIONS: list[str] = [
    "customers:create",
    "customers:read",
    "customers:update",
    "orders:create",
    "orders:read",
    "orders:cancel",
    "orders:cancel_approve",
    "orders:deliver",
    "routes:create",
    "routes:read",
    "inventory:load",
    "inventory:adjust",
    "reconciliation:approve",
    "ledger:read",
    "ledger:write",
    "invoices:read",
    "payments:create",
    "credit_notes:request",
    "credit_notes:approve",
    "complaints:create",
    "complaints:read",
    "complaints:resolve",
    "reports:read",
    "reports:export",
    "tenant:configure",
]

# docs/data/17-api-security.md §6's 9-row representative matrix, expanded
# into (permission, [roles]) pairs. Row-scoping qualifiers ("(self)",
# "(own)") are dropped here — see module docstring.
_ROLE_PERMISSION_MATRIX: list[tuple[str, list[str]]] = [
    ("customers:create", ["agency_admin", "manager", "dispatcher", "customer"]),
    ("orders:create", ["agency_admin", "manager", "dispatcher", "customer"]),
    ("orders:cancel_approve", ["agency_admin", "manager"]),
    ("orders:deliver", ["driver"]),
    ("inventory:adjust", ["agency_admin", "manager", "warehouse_staff"]),
    ("reconciliation:approve", ["agency_admin", "warehouse_staff"]),
    ("credit_notes:approve", ["agency_admin", "manager"]),
    ("ledger:read", ["agency_admin", "manager", "accountant", "customer"]),
    ("tenant:configure", ["super_admin", "agency_admin"]),
]


def _standard_columns() -> list[sa.Column]:
    """The audit-column set every table in this codebase carries
    (`docs/data/03-database-schema.md` §"Every table carries these"),
    matching `0242df1a3871`/`40065f2b4dc3`'s exact shape.
    """
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    ]


def _grant(*, table: str, privileges: str) -> str:
    """The dynamic per-database role-detection grant block, identical shape
    to `0242df1a3871`/`40065f2b4dc3` — resolved from `current_database()`
    rather than hardcoded so one migration applies correctly on
    lpg_dev/lpg_test (`lpg_app`) and lpg_uat (`lpg_app_uat`) alike.
    """
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT USAGE ON SCHEMA {_SCHEMA} TO %I', app_role);
                EXECUTE format(
                    'GRANT {privileges} ON {_SCHEMA}.{table} TO %I', app_role
                );
            END IF;
        END
        $$;
    """


def _enable_rls(table: str, *, using: str) -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{table}_isolation ON {_SCHEMA}.{table}
        USING ({using})
    """)


_TENANT_RLS_PREDICATE = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # -- Reference data: role, permission, role_permission (Platform-Global,
    # no tenant_id, no RLS) --------------------------------------------------
    op.create_table(
        "role",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        *_standard_columns(),
        sa.UniqueConstraint("code", name="uq_identity_role_code"),
        schema=_SCHEMA,
    )

    op.create_table(
        "permission",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("resource", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        *_standard_columns(),
        sa.UniqueConstraint("code", name="uq_identity_permission_code"),
        schema=_SCHEMA,
    )

    op.create_table(
        "role_permission",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "role_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.role.id"),
            nullable=False,
        ),
        sa.Column(
            "permission_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.permission.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_identity_role_permission"),
        schema=_SCHEMA,
    )

    # -- Tenant-scoped: identity_user, user_role (RLS applied) ---------------
    op.create_table(
        "identity_user",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        # Nullable: null only for Super Admin, who operates above tenant
        # scope (D-01) — same documented exception audit.audit_log uses.
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("branch_id", sa.Uuid(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone_number", sa.String(length=20), nullable=True),
        sa.Column("password_hash", sa.String(length=200), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        # The deferred Entra ID SSO seam (D-37's "optional" clause) — schema
        # only, no working OAuth flow in this phase.
        sa.Column("sso_subject", sa.String(length=200), nullable=True),
        sa.Column("sso_provider", sa.String(length=50), nullable=True),
        *_standard_columns(),
        schema=_SCHEMA,
    )
    # email: unique where present, no tenant qualifier — globally unique
    # (docs/data/03-database-schema.md).
    op.create_index(
        "uq_identity_identity_user_email",
        "identity_user",
        ["email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
        schema=_SCHEMA,
    )
    # phone_number: unique per tenant.
    op.create_index(
        "uq_identity_identity_user_tenant_phone",
        "identity_user",
        ["tenant_id", "phone_number"],
        unique=True,
        postgresql_where=sa.text("phone_number IS NOT NULL"),
        schema=_SCHEMA,
    )
    _enable_rls("identity_user", using=_TENANT_RLS_PREDICATE)

    op.create_table(
        "user_role",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        # Denormalized from the owning user, same convention
        # `identity.refresh_token` (migration 2) uses — lets RLS apply
        # directly on this table without a join.
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.identity_user.id"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.role.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "role_id", name="uq_identity_user_role"),
        schema=_SCHEMA,
    )
    _enable_rls("user_role", using=_TENANT_RLS_PREDICATE)

    # -- Grants ---------------------------------------------------------------
    # Reference data: read-only for the application role — RBAC
    # administration (editing role/permission/role_permission) is Phase 7
    # scope, not this phase's.
    op.execute(_grant(table="role", privileges="SELECT"))
    op.execute(_grant(table="permission", privileges="SELECT"))
    op.execute(_grant(table="role_permission", privileges="SELECT"))
    # identity_user: no DELETE — deactivation only, matching the reference
    # -data convention ("soft-delete/deactivation only, never hard-delete").
    op.execute(_grant(table="identity_user", privileges="SELECT, INSERT, UPDATE"))
    # user_role: SELECT only in this phase — role assignment is admin/seed
    # -only until Phase 7's user-management UI exists.
    op.execute(_grant(table="user_role", privileges="SELECT"))

    # -- Seed data --------------------------------------------------------
    role_table = sa.table(
        "role",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        schema=_SCHEMA,
    )
    role_ids = {code: uuid.uuid4() for code, _name in _ROLES}
    op.bulk_insert(
        role_table,
        [{"id": role_ids[code], "code": code, "name": name} for code, name in _ROLES],
    )

    permission_table = sa.table(
        "permission",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        schema=_SCHEMA,
    )
    permission_ids = {code: uuid.uuid4() for code in _PERMISSIONS}
    op.bulk_insert(
        permission_table,
        [
            {
                "id": permission_ids[code],
                "code": code,
                "resource": code.split(":")[0],
                "action": code.split(":")[1],
            }
            for code in _PERMISSIONS
        ],
    )

    role_permission_table = sa.table(
        "role_permission",
        sa.column("id", sa.Uuid()),
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
        schema=_SCHEMA,
    )
    role_permission_rows = [
        {
            "id": uuid.uuid4(),
            "role_id": role_ids[role_code],
            "permission_id": permission_ids[permission_code],
        }
        for permission_code, role_codes in _ROLE_PERMISSION_MATRIX
        for role_code in role_codes
    ]
    op.bulk_insert(role_permission_table, role_permission_rows)

    # -- Auth-bootstrap SECURITY DEFINER functions ---------------------------
    #
    # `identity_user`'s own RLS policy (above) requires `app.current_tenant_id`
    # to already be set — but login/OTP/refresh are exactly the requests that
    # *establish* tenant context, so no such session variable can exist yet
    # for them (a chicken-and-egg problem the migration's own RLS predicate
    # cannot resolve). `lpg_app`/`lpg_app_uat` are NOSUPERUSER/NOBYPASSRLS by
    # design (DW-19) and must stay that way — broadening their own privileges
    # to read/write this table directly would defeat that.
    #
    # The standard PostgreSQL-idiomatic answer: narrow `SECURITY DEFINER`
    # functions, owned by the migration/admin role, each doing exactly one
    # unique-key-scoped operation (never an arbitrary query) — the security
    # boundary moves from "the calling role's row visibility" to "the exact
    # shape of this one function", which is auditable in a way a session
    # -variable bypass flag would not be. `SET search_path` is pinned on each
    # to prevent search-path hijacking. `lpg_app` gets `EXECUTE` only — never
    # direct table access for these auth-bootstrap paths.
    op.execute(f"""
        CREATE FUNCTION {_SCHEMA}.auth_find_user_by_email(p_email text)
        RETURNS {_SCHEMA}.identity_user
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_SCHEMA}, pg_temp
        AS $$
            SELECT * FROM {_SCHEMA}.identity_user
            WHERE email = p_email AND is_deleted = false;
        $$;
    """)
    op.execute(f"""
        CREATE FUNCTION {_SCHEMA}.auth_find_user_by_phone(p_tenant_id uuid, p_phone text)
        RETURNS {_SCHEMA}.identity_user
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_SCHEMA}, pg_temp
        AS $$
            SELECT * FROM {_SCHEMA}.identity_user
            WHERE tenant_id = p_tenant_id AND phone_number = p_phone AND is_deleted = false;
        $$;
    """)
    op.execute(f"""
        CREATE FUNCTION {_SCHEMA}.auth_find_user_by_id(p_user_id uuid)
        RETURNS {_SCHEMA}.identity_user
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_SCHEMA}, pg_temp
        AS $$
            SELECT * FROM {_SCHEMA}.identity_user
            WHERE id = p_user_id AND is_deleted = false;
        $$;
    """)
    # One combined write function — `record_failed_login`,
    # `record_successful_login` and `change_password_hash` (the three
    # `IdentityUser` domain methods that mutate auth-bookkeeping state) all
    # funnel through here, always supplying the full new values for these
    # four columns rather than each getting its own narrower function. Bumps
    # `updated_at`/`version` like every other write in this codebase.
    op.execute(f"""
        CREATE FUNCTION {_SCHEMA}.auth_update_user_auth_state(
            p_user_id uuid,
            p_failed_login_count int,
            p_locked_until timestamptz,
            p_password_hash text
        )
        RETURNS void
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = {_SCHEMA}, pg_temp
        AS $$
            UPDATE {_SCHEMA}.identity_user
            SET failed_login_count = p_failed_login_count,
                locked_until = p_locked_until,
                password_hash = p_password_hash,
                updated_at = now(),
                version = version + 1
            WHERE id = p_user_id;
        $$;
    """)
    # PostgreSQL grants EXECUTE on a new function to PUBLIC by default —
    # verified against a real database, not assumed. Left unrevoked, *any*
    # role able to connect (a future read-only reporting role, for instance)
    # could call these RLS-bypassing functions directly. Revoke first, then
    # grant back explicitly to only the one application role that needs it.
    op.execute(f"""
        REVOKE EXECUTE ON FUNCTION {_SCHEMA}.auth_find_user_by_email(text) FROM PUBLIC
    """)
    op.execute(f"""
        REVOKE EXECUTE ON FUNCTION {_SCHEMA}.auth_find_user_by_phone(uuid, text) FROM PUBLIC
    """)
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_SCHEMA}.auth_find_user_by_id(uuid) FROM PUBLIC")
    op.execute(f"""
        REVOKE EXECUTE ON FUNCTION
        {_SCHEMA}.auth_update_user_auth_state(uuid, int, timestamptz, text)
        FROM PUBLIC
    """)
    # Same single dynamic-role-detection shape as `_grant()` — exactly one of
    # `lpg_app`/`lpg_app_uat` is resolved per database, never both attempted
    # unconditionally (which would fail outright on a database where one of
    # them doesn't exist).
    op.execute(f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION {_SCHEMA}.auth_find_user_by_email(text) TO %I',
                    app_role
                );
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION {_SCHEMA}.auth_find_user_by_phone(uuid, text) '
                    'TO %I',
                    app_role
                );
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION {_SCHEMA}.auth_find_user_by_id(uuid) TO %I',
                    app_role
                );
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION '
                    '{_SCHEMA}.auth_update_user_auth_state(uuid, int, timestamptz, text) '
                    'TO %I',
                    app_role
                );
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute(
        f"DROP FUNCTION IF EXISTS {_SCHEMA}.auth_update_user_auth_state"
        "(uuid, int, timestamptz, text)"
    )
    op.execute(f"DROP FUNCTION IF EXISTS {_SCHEMA}.auth_find_user_by_id(uuid)")
    op.execute(f"DROP FUNCTION IF EXISTS {_SCHEMA}.auth_find_user_by_phone(uuid, text)")
    op.execute(f"DROP FUNCTION IF EXISTS {_SCHEMA}.auth_find_user_by_email(text)")
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_user_role_isolation ON {_SCHEMA}.user_role")
    op.execute(
        f"DROP POLICY IF EXISTS rls_{_SCHEMA}_identity_user_isolation ON {_SCHEMA}.identity_user"
    )
    op.drop_table("user_role", schema=_SCHEMA)
    op.drop_table("identity_user", schema=_SCHEMA)
    op.drop_table("role_permission", schema=_SCHEMA)
    op.drop_table("permission", schema=_SCHEMA)
    op.drop_table("role", schema=_SCHEMA)
