"""create accounting.payment_gateway_credential

Per-agency Razorpay credentials (ADR-067). Each agency has its own
Razorpay account, so the key pair and webhook secret cannot be platform
environment variables. One row per tenant:

- `key_id` is stored in the clear (it is shown, masked, in the dashboard and
  is not a secret on its own); `key_secret_encrypted` and
  `webhook_secret_encrypted` are Fernet ciphertext (the same
  `LPG_KYC_ENCRYPTION_KEY` that protects KYC references).
- `webhook_token` is an opaque random value forming the agency's own webhook
  URL, so the unauthenticated webhook can find the tenant — and therefore
  the webhook secret to verify the signature with — before it trusts
  anything in the body.
- `accounting.payment_credential_resolve_tenant(text)` is the SECURITY
  DEFINER lookup from that token to the tenant, the same bootstrap pattern as
  `tenant.whatsapp_resolve_tenant_id`.

Row-level security confines every other access to the caller's own tenant.
`DELETE` is granted: an agency may remove its keys and fall back to the
platform default.

Revision ID: e3a7c1d9b5f2
Revises: d2b8f4a60c17
Create Date: 2026-10-31
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "e3a7c1d9b5f2"
down_revision: str | None = "d2b8f4a60c17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "accounting"
_TABLE = "payment_gateway_credential"
_RESOLVER = "payment_credential_resolve_tenant"


def _app_role_block(statement: str) -> str:
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
                EXECUTE format('{statement}', app_role);
            END IF;
        END
        $$;
    """


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {_SCHEMA}.{_TABLE} (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL UNIQUE REFERENCES tenant.tenant(id) ON DELETE CASCADE,
            provider text NOT NULL DEFAULT 'razorpay',
            key_id text NOT NULL,
            key_secret_encrypted text NOT NULL,
            webhook_secret_encrypted text,
            webhook_token text NOT NULL UNIQUE,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            updated_by uuid,
            version integer NOT NULL DEFAULT 1
        )
    """)
    op.execute(_app_role_block(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {_SCHEMA}.{_TABLE} TO %I"))
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)

    op.execute(f"""
        CREATE FUNCTION {_SCHEMA}.{_RESOLVER}(p_token text)
        RETURNS uuid
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = accounting, pg_temp
        AS $$
            SELECT c.tenant_id
            FROM accounting.{_TABLE} c
            JOIN tenant.tenant t ON t.id = c.tenant_id
            WHERE c.webhook_token = p_token
              AND t.is_deleted = false
              AND t.status <> 'closed';
        $$;
    """)
    op.execute(_app_role_block(f"GRANT EXECUTE ON FUNCTION {_SCHEMA}.{_RESOLVER}(text) TO %I"))


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {_SCHEMA}.{_RESOLVER}(text)")
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}")
    op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.{_TABLE}")
