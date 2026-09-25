"""Create the platform's first `super_admin` (no tenant) with a random password.

Production bootstrap: unlike `seed_dev_user.py` it embeds no credentials, never
touches a tenant, and needs the elevated migration DSN explicitly (no dev
fallback). Idempotent: an existing user with the same email is left untouched,
so re-running can never reset a password.

    docker compose -f docker-compose.prod.yml run --rm --no-deps migrate \
        python scripts/bootstrap_super_admin.py --email super_admin@example.com

The generated password is printed once, to stdout, and stored nowhere.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.config.settings import get_settings
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher

ROLE_CODE = "super_admin"


async def main(email: str) -> int:
    settings = get_settings()
    dsn = settings.migration_database_url
    if not dsn:
        print(
            "LPG_MIGRATION_DATABASE_URL is not set; refusing to guess a database.", file=sys.stderr
        )
        return 2

    engine = create_async_engine(str(dsn))
    hasher = Argon2PasswordHasher(settings)
    password = secrets.token_urlsafe(18)

    async with engine.begin() as conn:
        role_id = (
            await conn.execute(
                text("SELECT id FROM identity.role WHERE code = :c"), {"c": ROLE_CODE}
            )
        ).scalar()
        if role_id is None:
            print(f"Role '{ROLE_CODE}' not found - have migrations been run?", file=sys.stderr)
            return 2

        existing = (
            await conn.execute(
                text("SELECT id FROM identity.identity_user WHERE lower(email) = lower(:e)"),
                {"e": email},
            )
        ).scalar()
        if existing is not None:
            print(f"User {email} already exists (id {existing}); nothing changed.")
            return 0

        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), NULL, :e, :h, :r) RETURNING id"
                ),
                {"e": email, "h": hasher.hash(password), "r": ROLE_CODE},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.user_role (id, tenant_id, user_id, role_id) "
                "VALUES (gen_random_uuid(), NULL, :u, :r)"
            ),
            {"u": user_id, "r": role_id},
        )

    await engine.dispose()
    print(f"Created {ROLE_CODE} {email} (id {user_id})")
    print(f"Password (shown once, not stored): {password}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    sys.exit(asyncio.run(main(parser.parse_args().email)))
