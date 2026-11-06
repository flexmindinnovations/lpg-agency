"""add a profile picture reference to identity users

A signed-in staff member can set a profile picture (planning feature 62).
`avatar_ref` is the object-storage key of the picture - always under the
user's own `tenant/{tenant_id}/` prefix - never a URL: a time-limited URL is
generated each time the profile is read, so a leaked link stops working.

Revision ID: e4b7a1c9d3f2
Revises: d7a3b5e9c218
Create Date: 2026-11-06 12:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "e4b7a1c9d3f2"
down_revision: str | None = "d7a3b5e9c218"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"


def upgrade() -> None:
    op.add_column(
        "identity_user", sa.Column("avatar_ref", sa.String(300), nullable=True), schema=_SCHEMA
    )


def downgrade() -> None:
    op.drop_column("identity_user", "avatar_ref", schema=_SCHEMA)
