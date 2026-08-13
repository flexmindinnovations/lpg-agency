import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.config.settings import get_settings
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher


async def main():
    settings = get_settings()
    hasher = Argon2PasswordHasher(settings)

    # Check Supabase
    print("Checking Supabase...")
    dsn = settings.migration_database_url
    engine = create_async_engine(str(dsn))
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT password_hash FROM identity.identity_user "
                    "WHERE email='admin@example.com'"
                )
            )
        ).one()
        pw_hash = row[0]
        print("Hash in DB:", pw_hash)
        print("Verification:", hasher.verify("correct-horse-battery", pw_hash))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
