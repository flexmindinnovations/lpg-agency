"""create ai schema assistant_run table

Revision ID: b3e97f4d1c6a
Revises: a7c4e9f21b8d
Create Date: 2026-09-08

Delivers, for the AI Model Gateway substrate + the read-only AI Command
Center (ADR-045):
  - `ai` PostgreSQL schema — new bounded context, the reserved home for
    every future AI-adjacent table (Phase 21's own PLAN.md names a feature
    store here too, not built in this slice).
  - `ai.assistant_run` — one row per `POST /ai/ask` call: the question, which
    tools were consulted, provider/model, token/latency accounting, and
    outcome status. Append-only (no update/delete grant) — a run's own
    history is never edited after the fact. Written via a normal repository
    `save()` inside a UoW, which rides `AuditRecorder`'s existing generic
    `before_flush` hook for a free audit trail — no bespoke audit-write path
    needed.
  - One new permission code: `ai:read` (use the AI Command Center), granted
    to `super_admin, agency_admin, manager` — mirrors `compliance:verify`'s
    role set exactly. Deliberately **not** granted to `dispatcher`/`driver`/
    `customer`: this surfaces cross-domain aggregate data (orders,
    inventory, complaints), a narrower default than any single existing
    domain permission.

Follows `d8b300ef303f_create_compliance_schema_scale_table.py`'s pattern
(`_standard_columns()`, the null-safe `NULLIF(...)` RLS predicate, the
dynamic-role `_grant()` helper, `ON CONFLICT`-based permission insert +
`identity_user_permission` backfill).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b3e97f4d1c6a"
down_revision: str | None = "a7c4e9f21b8d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "ai"
_TENANT_SCHEMA = "tenant"
_IDENTITY_SCHEMA = "identity"
_TABLE = "assistant_run"

_RUN_STATUSES = ("success", "gateway_disabled", "budget_exceeded", "provider_error")
_READ_ROLES = ("super_admin", "agency_admin", "manager")


def _standard_columns() -> list[sa.Column]:
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


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{table}_isolation ON {_SCHEMA}.{table}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)


def _grant_permission_to_roles(permission_code: str, role_codes: tuple[str, ...]) -> None:
    roles_sql = "(" + ", ".join(f"'{r}'" for r in role_codes) + ")"
    op.execute(f"""
        INSERT INTO {_IDENTITY_SCHEMA}.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM {_IDENTITY_SCHEMA}.role r
        CROSS JOIN {_IDENTITY_SCHEMA}.permission p
        WHERE r.code IN {roles_sql}
          AND p.code = '{permission_code}'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)
    op.execute(f"""
        INSERT INTO {_IDENTITY_SCHEMA}.identity_user_permission
            (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, p.id, now()
        FROM {_IDENTITY_SCHEMA}.identity_user u
        JOIN {_IDENTITY_SCHEMA}.permission p ON p.code = '{permission_code}'
        WHERE u.role IN {roles_sql}
          AND NOT EXISTS (
              SELECT 1 FROM {_IDENTITY_SCHEMA}.identity_user_permission existing
              WHERE existing.user_id = u.id AND existing.permission_id = p.id
          )
    """)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Schema
    # ------------------------------------------------------------------
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ------------------------------------------------------------------
    # 2. ai.assistant_run
    # ------------------------------------------------------------------
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column(
            "tools_used", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tool_turns", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(f"status IN {_RUN_STATUSES}", name="ck_ai_assistant_run_status"),
        schema=_SCHEMA,
    )

    op.create_index(
        "idx_ai_assistant_run_tenant_created",
        _TABLE,
        ["tenant_id", "created_at"],
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------
    # 3. Row-Level Security
    # ------------------------------------------------------------------
    _enable_rls(_TABLE)

    # ------------------------------------------------------------------
    # 4. Grants — append-only, no UPDATE/DELETE (a run's own record is
    #    never edited after the fact).
    # ------------------------------------------------------------------
    op.execute(_grant(table=_TABLE, privileges="SELECT, INSERT"))

    # ------------------------------------------------------------------
    # 5. Permission code
    # ------------------------------------------------------------------
    op.execute(f"""
        INSERT INTO {_IDENTITY_SCHEMA}.permission (code, resource, action)
        VALUES ('ai:read', 'ai', 'read')
        ON CONFLICT (code) DO NOTHING
    """)
    _grant_permission_to_roles("ai:read", _READ_ROLES)


def downgrade() -> None:
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.identity_user_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission WHERE code = 'ai:read'
        )
    """)
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.role_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission WHERE code = 'ai:read'
        )
    """)
    op.execute(f"DELETE FROM {_IDENTITY_SCHEMA}.permission WHERE code = 'ai:read'")

    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}")
    op.drop_table(_TABLE, schema=_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
