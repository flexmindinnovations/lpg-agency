"""create messaging schema whatsapp tables

Revision ID: a9c2e4f6b8d1
Revises: a9e4c7b2d1f6
Create Date: 2026-10-17

Delivers, for the WhatsApp customer assistant (ADR-055):
  - `messaging` PostgreSQL schema — new bounded context for customer
    messaging channels.
  - `messaging.whatsapp_message` — every WhatsApp message in and out, per
    tenant. Append-only (`SELECT, INSERT`). The unique
    `(tenant_id, direction, wa_message_id)` constraint is the inbound
    deduplication key: Meta retries webhook deliveries, and a retried message
    must be answered once. Outbound rows whose send failed have a NULL
    `wa_message_id`, which never conflicts.
  - `messaging.whatsapp_conversation` — one row per (tenant, customer phone)
    holding conversation state; today only the pending order quote the
    assistant is waiting for the customer to confirm.
  - `tenant.whatsapp_resolve_tenant_id(text)` — SECURITY DEFINER lookup from a
    WhatsApp Business phone number id to the tenant whose current
    `whatsapp_phone_number_id` Tenant Configuration value it is. The webhook
    is unauthenticated and has no tenant until this answers, the same
    bootstrap problem `auth_resolve_tenant_id_by_slug` solves. Returns NULL
    unless exactly one live tenant claims the number, so a misconfigured
    duplicate can never route one agency's customers to another.

Follows `b3e97f4d1c6a_create_ai_schema_assistant_run_table.py`'s pattern (the
null-safe `NULLIF(...)` RLS predicate, the dynamic-role `_grant()` helper).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a9c2e4f6b8d1"
down_revision: str | None = "a9e4c7b2d1f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "messaging"
_TENANT_SCHEMA = "tenant"
_MESSAGE_TABLE = "whatsapp_message"
_CONVERSATION_TABLE = "whatsapp_conversation"
_RESOLVER = "whatsapp_resolve_tenant_id"


def _app_role_block(statements: str) -> str:
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                {statements}
            END IF;
        END
        $$;
    """


def _grant(*, table: str, privileges: str) -> str:
    return _app_role_block(f"""
                EXECUTE format('GRANT USAGE ON SCHEMA {_SCHEMA} TO %I', app_role);
                EXECUTE format('GRANT {privileges} ON {_SCHEMA}.{table} TO %I', app_role);
    """)


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{table}_isolation ON {_SCHEMA}.{table}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    op.create_table(
        _MESSAGE_TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("phone_number", sa.String(length=20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("wa_message_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "direction IN ('inbound', 'outbound')", name="ck_whatsapp_message_direction"
        ),
        sa.CheckConstraint(
            "status IN ('received', 'sent', 'failed')", name="ck_whatsapp_message_status"
        ),
        sa.UniqueConstraint(
            "tenant_id", "direction", "wa_message_id", name="uq_whatsapp_message_wa_id"
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_whatsapp_message_tenant_phone_created",
        _MESSAGE_TABLE,
        ["tenant_id", "phone_number", "created_at"],
        schema=_SCHEMA,
    )

    op.create_table(
        _CONVERSATION_TABLE,
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("phone_number", sa.String(length=20), primary_key=True),
        sa.Column("pending_quote", postgresql.JSONB(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )

    _enable_rls(_MESSAGE_TABLE)
    _enable_rls(_CONVERSATION_TABLE)
    op.execute(_grant(table=_MESSAGE_TABLE, privileges="SELECT, INSERT"))
    op.execute(_grant(table=_CONVERSATION_TABLE, privileges="SELECT, INSERT, UPDATE"))

    op.execute(f"""
        CREATE FUNCTION {_TENANT_SCHEMA}.{_RESOLVER}(p_phone_number_id text)
        RETURNS uuid
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = tenant, pg_temp
        AS $$
            WITH latest AS (
                SELECT DISTINCT ON (c.tenant_id) c.tenant_id, c.config_value
                FROM tenant.tenant_configuration c
                WHERE c.config_key = 'whatsapp_phone_number_id'
                  AND c.effective_from <= now()
                ORDER BY c.tenant_id, c.effective_from DESC
            ),
            matches AS (
                SELECT l.tenant_id
                FROM latest l
                JOIN tenant.tenant t ON t.id = l.tenant_id
                WHERE t.is_deleted = false
                  AND t.status <> 'closed'
                  AND l.config_value #>> '{{}}' = p_phone_number_id
            )
            SELECT tenant_id FROM matches
            WHERE (SELECT count(*) FROM matches) = 1;
        $$;
    """)
    op.execute(
        _app_role_block(f"""
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION {_TENANT_SCHEMA}.{_RESOLVER}(text) TO %I',
                    app_role
                );
    """)
    )


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {_TENANT_SCHEMA}.{_RESOLVER}(text)")
    for table in (_CONVERSATION_TABLE, _MESSAGE_TABLE):
        op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{table}_isolation ON {_SCHEMA}.{table}")
        op.drop_table(table, schema=_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
