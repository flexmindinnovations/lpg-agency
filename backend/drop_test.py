import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def drop():
    engine = create_async_engine('postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test')
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS notification CASCADE"))
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(drop())
    print("Dropped schema from lpg_test")
