"""add display name and contact phone to identity users

QA finding DA-30: My Profile could show only the email and a raw role code;
staff had no way to record their name or a contact number. `display_name`
and `contact_phone` are plain profile fields. `contact_phone` is
deliberately separate from `phone_number`, which is the OTP sign-in key for
customer and driver accounts and is unique per tenant: a staff member's
contact number must never become an OTP login, and an agency owner who is also
a customer must be able to use the same number in both places.

Revision ID: a9d2197ebb9b
Revises: 21a625272f0b
Create Date: 2026-10-20 13:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a9d2197ebb9b"
down_revision: str | None = "21a625272f0b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"


def upgrade() -> None:
    op.add_column(
        "identity_user", sa.Column("display_name", sa.String(120), nullable=True), schema=_SCHEMA
    )
    op.add_column(
        "identity_user", sa.Column("contact_phone", sa.String(20), nullable=True), schema=_SCHEMA
    )


def downgrade() -> None:
    op.drop_column("identity_user", "contact_phone", schema=_SCHEMA)
    op.drop_column("identity_user", "display_name", schema=_SCHEMA)
