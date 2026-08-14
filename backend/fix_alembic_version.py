import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def fix():
    for db in ['lpg_dev', 'lpg_test']:
        engine = create_async_engine(f'postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/{db}')
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM alembic_version"))
            await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('e60b8b86b965')"))
        await engine.dispose()
        print(f"Fixed {db}")

if __name__ == '__main__':
    asyncio.run(fix())
