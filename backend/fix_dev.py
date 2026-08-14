import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def drop():
    engine = create_async_engine('postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_dev')
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS notification CASCADE"))
        await conn.execute(text("DELETE FROM alembic_version WHERE version_num = 'd8045524a3d8'"))
        await conn.execute(text("DELETE FROM alembic_version WHERE version_num = '0df30969e03e'"))
    await engine.dispose()
    print("Fixed lpg_dev")

if __name__ == '__main__':
    asyncio.run(drop())
