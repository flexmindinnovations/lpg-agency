import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    engine = create_async_engine('postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test')
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT table_schema, table_name FROM information_schema.tables WHERE table_name = 'in_app_notification'"))
        for row in res:
            print(row)
        
        await conn.execute(text("DROP TABLE IF EXISTS notification.in_app_notification CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS public.in_app_notification CASCADE"))
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(check())
