"""add FK and unique constraint on delivery.driver.identity_user_id

Revision ID: e68103c56ad7
Revises: d2e8f4a6c1b9
Create Date: 2026-08-11 00:00:00.000000

The original Phase 9 migration (a1b2c3d4e5f6) created
`delivery.driver.identity_user_id` as a bare nullable `uuid` column with
neither constraint, diverging from `docs/data/03-database-schema.md`'s
documented spec (`FK, unique`). The column stays nullable — a driver
profile is optional at registration and only required to link to an
`identity.identity_user` before that driver can log in to the Driver App
(`docs/data/01-domain-model.md` §4.9, `domain/delivery/driver.py`) — this
migration only adds the missing FK and uniqueness guarantees.
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e68103c56ad7"
down_revision: str = "d2e8f4a6c1b9"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE delivery.driver "
        "ADD CONSTRAINT fk_driver_identity_user "
        "FOREIGN KEY (identity_user_id) "
        "REFERENCES identity.identity_user(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE delivery.driver "
        "ADD CONSTRAINT uq_driver_identity_user UNIQUE (identity_user_id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE delivery.driver DROP CONSTRAINT IF EXISTS uq_driver_identity_user")
    op.execute("ALTER TABLE delivery.driver DROP CONSTRAINT IF EXISTS fk_driver_identity_user")
