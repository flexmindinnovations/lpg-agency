import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    for db in ['lpg_dev', 'lpg_test']:
        print(f"Checking {db}...")
        engine = create_async_engine(f'postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/{db}')
        try:
            async with engine.begin() as conn:
                res = await conn.execute(text("SELECT * FROM alembic_version"))
                for row in res:
                    print(row)
        except Exception as e:
            print(f"Error checking {db}: {e}")
        await engine.dispose()

if __name__ == '__main__':
    asyncio.run(check())
