import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.config.settings import get_settings
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher


async def main():
    settings = get_settings()

    # We must connect with migration/admin privileges to bypass RLS and insert tenants/roles
    dsn = settings.migration_database_url
    if not dsn:
        print(
            "LPG_MIGRATION_DATABASE_URL not set in environment or .env. "
            "Trying default dev admin DSN..."
        )
        dsn = "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_dev"

    print(f"Connecting to database using DSN: {dsn}")
    engine = create_async_engine(str(dsn))
    hasher = Argon2PasswordHasher(settings)

    default_email = "admin@example.com"
    default_password = "correct-horse-battery"  # noqa: S105 - dev-seed-only, not a real secret

    async with engine.begin() as conn:
        # 1. Ensure tenant exists
        print("Checking if tenant exists...")
        tenant_row = await conn.execute(
            text("SELECT id FROM tenant.tenant WHERE slug = 'dev-tenant'")
        )
        tenant_id = tenant_row.scalar()
        if not tenant_id:
            print("Creating default tenant 'dev-tenant'...")
            tenant_id = await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug) "
                    "VALUES (gen_random_uuid(), 'Dev Agency Tenant', 'dev-tenant') "
                    "RETURNING id"
                )
            )
            tenant_id = tenant_id.scalar_one()
        else:
            print(f"Using existing tenant: {tenant_id}")

        # 2. Get role ID for agency_admin
        print("Fetching role ID for agency_admin...")
        role_row = await conn.execute(
            text("SELECT id FROM identity.role WHERE code = 'agency_admin'")
        )
        role_id = role_row.scalar()
        if not role_id:
            print("Error: role 'agency_admin' not found in database. Make sure migrations are run.")
            sys.exit(1)

        # 3. Check if user already exists
        user_row = await conn.execute(
            text("SELECT id FROM identity.identity_user WHERE email = :email"),
            {"email": default_email},
        )
        user_id = user_row.scalar()

        if not user_id:
            print(f"Creating user '{default_email}' with password '{default_password}'...")
            pw_hash = hasher.hash(default_password)
            user_id = await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES "
                    "(gen_random_uuid(), :tenant_id, :email, :password_hash, 'agency_admin') "
                    "RETURNING id"
                ),
                {"tenant_id": tenant_id, "email": default_email, "password_hash": pw_hash},
            )
            user_id = user_id.scalar_one()

            # Link user to role
            print("Linking user to role...")
            await conn.execute(
                text(
                    "INSERT INTO identity.user_role (id, tenant_id, user_id, role_id) "
                    "VALUES (gen_random_uuid(), :tenant_id, :user_id, :role_id)"
                ),
                {"tenant_id": tenant_id, "user_id": user_id, "role_id": role_id},
            )
            print("User seeded successfully.")
        else:
            print(f"User '{default_email}' already exists.")

    await engine.dispose()
    print("\nInitialization script complete.")
    print(f"Login Email:    {default_email}")
    print(f"Login Password: {default_password}")


if __name__ == "__main__":
    asyncio.run(main())
