import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.config.settings import get_settings
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher

USERS_TO_SEED = [
    {"email": "manager@example.com", "role": "manager"},
    {"email": "dispatcher@example.com", "role": "dispatcher"},
    {"email": "accountant@example.com", "role": "accountant"},
    {"email": "warehouse@example.com", "role": "warehouse_staff"}
]

async def main():
    settings = get_settings()

    dsn = settings.migration_database_url
    if not dsn:
        dsn = "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_dev"

    print(f"Connecting to database using DSN: {dsn}")
    engine = create_async_engine(str(dsn))
    hasher = Argon2PasswordHasher(settings)

    default_password = "correct-horse-battery"

    async with engine.begin() as conn:
        print("Checking if tenant exists...")
        tenant_row = await conn.execute(
            text("SELECT id FROM tenant.tenant WHERE slug = 'dev-tenant'")
        )
        tenant_id = tenant_row.scalar()
        if not tenant_id:
            print("Error: tenant not found. Please run seed_dev_user.py first.")
            sys.exit(1)

        for user_info in USERS_TO_SEED:
            email = user_info["email"]
            role_code = user_info["role"]

            # 1. Get role ID
            role_row = await conn.execute(
                text("SELECT id FROM identity.role WHERE code = :code"),
                {"code": role_code}
            )
            role_id = role_row.scalar()
            if not role_id:
                print(f"Error: role '{role_code}' not found.")
                continue

            # 2. Check if user already exists
            user_row = await conn.execute(
                text("SELECT id FROM identity.identity_user WHERE email = :email"),
                {"email": email},
            )
            user_id = user_row.scalar()

            if not user_id:
                print(f"Creating user '{email}' with role '{role_code}'...")
                pw_hash = hasher.hash(default_password)
                user_id = await conn.execute(
                    text(
                        "INSERT INTO identity.identity_user "
                        "(id, tenant_id, email, password_hash, role) "
                        "VALUES "
                        "(gen_random_uuid(), :tenant_id, :email, :password_hash, :role) "
                        "RETURNING id"
                    ),
                    {
                        "tenant_id": tenant_id,
                        "email": email,
                        "password_hash": pw_hash,
                        "role": role_code,
                    },
                )
                user_id = user_id.scalar_one()

                # Link user to role
                await conn.execute(
                    text(
                        "INSERT INTO identity.user_role (id, tenant_id, user_id, role_id) "
                        "VALUES (gen_random_uuid(), :tenant_id, :user_id, :role_id)"
                    ),
                    {"tenant_id": tenant_id, "user_id": user_id, "role_id": role_id},
                )
                print(f"  -> User {email} seeded successfully.")
            else:
                print(f"User '{email}' already exists.")

    await engine.dispose()
    print("\nInitialization script complete.")
    print(f"All created users share the same password: {default_password}")


if __name__ == "__main__":
    asyncio.run(main())
