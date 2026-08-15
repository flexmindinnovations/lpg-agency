import asyncio
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from lpg.config.settings import get_settings

async def main():
    settings = get_settings()
    dsn = settings.migration_database_url
    if not dsn:
        dsn = "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_dev"

    engine = create_async_engine(str(dsn))

    async with engine.begin() as conn:
        tenant_row = await conn.execute(text("SELECT id FROM tenant.tenant WHERE slug = 'dev-tenant'"))
        tenant_id = tenant_row.scalar()
        if not tenant_id:
            print("Error: tenant not found.")
            sys.exit(1)
            
        print("Seeding dummy customers...")
        customers = [
            ("CUST001", "John", "Doe", "johndoe@example.com", "1234567890"),
            ("CUST002", "Jane", "Smith", "janesmith@example.com", "0987654321"),
            ("CUST003", "Alice", "Johnson", "alicej@example.com", "1122334455")
        ]
        
        for cnum, fname, lname, email, phone in customers:
            await conn.execute(
                text("""
                    INSERT INTO customer.customer 
                    (id, tenant_id, consumer_number, first_name, last_name, email, phone_number, status, kyc_status, current_version, created_at, updated_at) 
                    VALUES (gen_random_uuid(), :tenant_id, :cnum, :fname, :lname, :email, :phone, 'active', 'pending', 1, now(), now())
                    ON CONFLICT (tenant_id, consumer_number) DO NOTHING
                """),
                {
                    "tenant_id": tenant_id, "cnum": cnum, "fname": fname, "lname": lname, 
                    "email": email, "phone": phone
                }
            )
        print("Demo customers seeded.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
