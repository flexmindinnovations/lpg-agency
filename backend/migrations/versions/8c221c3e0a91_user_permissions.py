"""user_permissions

Revision ID: 8c221c3e0a91
Revises: 8c7bdc1e1c73
Create Date: 2026-08-16 22:09:12.255321

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = '8c221c3e0a91'
down_revision: str | None = '8c7bdc1e1c73'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `CREATE TABLE IF NOT EXISTS` rather than `op.create_table`, and a guarded
    # backfill, because this table already existed on the Supabase project —
    # created out of band, with the identical four columns, both FKs and the
    # same PK name, and already carrying 85 rows. An unconditional
    # `op.create_table` aborted the upgrade there with DuplicateTableError, and
    # an unconditional backfill would have inserted 82 duplicate rows on top of
    # the 85 already present (the extra 3 are per-user grants that no
    # role-derived query reproduces). Both statements are now no-ops against a
    # database that already has the table and its data, and unchanged against
    # one that does not.
    op.execute("""
        CREATE TABLE IF NOT EXISTS identity.identity_user_permission (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            permission_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT pk_identity_user_permission PRIMARY KEY (id),
            CONSTRAINT fk_identity_user_permission_permission
                FOREIGN KEY (permission_id) REFERENCES identity.permission (id),
            CONSTRAINT fk_identity_user_permission_identity_user
                FOREIGN KEY (user_id) REFERENCES identity.identity_user (id)
        )
    """)

    # Data migration. `NOT EXISTS` keeps a re-run from double-granting a
    # permission a user already holds; there is no unique constraint on
    # (user_id, permission_id) to lean on.
    op.execute("""
        INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, rp.permission_id, now()
        FROM identity.identity_user u
        JOIN identity.role_permission rp
          ON rp.role_id = (SELECT id FROM identity.role WHERE code = u.role)
        WHERE NOT EXISTS (
            SELECT 1 FROM identity.identity_user_permission existing
            WHERE existing.user_id = u.id AND existing.permission_id = rp.permission_id
        )
    """)
    # Role resolution matches the rest of the tree so `lpg_uat` is not skipped.
    op.execute("""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format(
                    'GRANT SELECT, INSERT, UPDATE, DELETE '
                    'ON TABLE identity.identity_user_permission TO %I', app_role
                );
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.drop_table('identity_user_permission', schema='identity')
