"""create ai.prediction table and ai configure/override permissions

Revision ID: f25f9f8fa701
Revises: 0e01779fc059
Create Date: 2026-09-10

Delivers the first piece of AI Operational Intelligence — Horizon 1
(`planning/features/21-ai-foundation/PLAN.md` §4, `22-ai-operational-
intelligence`):

  - `ai.prediction` — one row every time a heuristic or (later) a trained
    model produces a number shown to a user: the prediction type, the
    subject it is about, the model version that produced it, a hash of the
    inputs, the value, and an optional confidence. Append-only (no
    UPDATE/DELETE grant), same shape as `ai.assistant_run` — a prediction's
    own record is never edited after the fact; a corrected prediction is a
    new row with a new `model_version`/`created_at`. This is what makes any
    displayed number traceable to the exact model that produced it, and
    makes a Horizon-2 heuristic → trained-model swap observable.
  - Two new permission codes: `ai:configure` (set AI feature toggles /
    thresholds) and `ai:override` (override an AI recommendation), granted
    to `super_admin, agency_admin` — the roles that already hold
    `tenant:configure`. Named in `21-ai-foundation/PLAN.md` §5.

Follows `b3e97f4d1c6a_create_ai_schema_assistant_run_table.py` exactly
(the `ai` schema already exists; reuse its `_grant()`, `_enable_rls()`,
`_grant_permission_to_roles()` helpers and the append-only SELECT/INSERT
grant).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "f25f9f8fa701"
down_revision: str | None = "0e01779fc059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "ai"
_TENANT_SCHEMA = "tenant"
_IDENTITY_SCHEMA = "identity"
_TABLE = "prediction"

_CONFIGURE_ROLES = ("super_admin", "agency_admin")


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


def _revoke_permission(permission_code: str) -> None:
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.identity_user_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission WHERE code = '{permission_code}'
        )
    """)
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.role_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission WHERE code = '{permission_code}'
        )
    """)
    op.execute(f"DELETE FROM {_IDENTITY_SCHEMA}.permission WHERE code = '{permission_code}'")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. ai.prediction  (the `ai` schema already exists — b3e97f4d1c6a)
    # ------------------------------------------------------------------
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # e.g. "refill_due", "reorder_signal", "route_sequence" — the kind
        # of thing predicted. Free-form string, not a CHECK: new heuristics
        # add types without a migration.
        sa.Column("prediction_type", sa.String(length=50), nullable=False),
        # What the prediction is about — ("customer", <customer_id>),
        # ("inventory_location", <location_id>), ("route", <route_id>), ...
        sa.Column("subject_type", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        # "<heuristic>_v1" now; a real model id later. The whole point of
        # this column: a displayed number is always attributable.
        sa.Column("model_version", sa.String(length=100), nullable=False),
        # Hash of the feature inputs, so an identical re-computation is
        # recognisable and a changed input is visible.
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_ai_prediction_tenant_type_subject",
        _TABLE,
        ["tenant_id", "prediction_type", "subject_id", "created_at"],
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------
    # 2. Row-Level Security
    # ------------------------------------------------------------------
    _enable_rls(_TABLE)

    # ------------------------------------------------------------------
    # 3. Grants — append-only, no UPDATE/DELETE (a prediction's own record
    #    is never edited; a correction is a new row).
    # ------------------------------------------------------------------
    op.execute(_grant(table=_TABLE, privileges="SELECT, INSERT"))

    # ------------------------------------------------------------------
    # 4. Permission codes
    # ------------------------------------------------------------------
    for code, action in (("ai:configure", "configure"), ("ai:override", "override")):
        op.execute(f"""
            INSERT INTO {_IDENTITY_SCHEMA}.permission (code, resource, action)
            VALUES ('{code}', 'ai', '{action}')
            ON CONFLICT (code) DO NOTHING
        """)
        _grant_permission_to_roles(code, _CONFIGURE_ROLES)


def downgrade() -> None:
    _revoke_permission("ai:override")
    _revoke_permission("ai:configure")
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}")
    op.drop_table(_TABLE, schema=_SCHEMA)
