import os
import sys
import asyncio
import asyncpg

async def drop():
    conn = await asyncpg.connect('postgresql://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test')
    await conn.execute('DROP SCHEMA IF EXISTS notification CASCADE')
    await conn.close()

def main():
    os.environ['LPG_MIGRATION_DATABASE_URL'] = 'postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test'
    os.environ['LPG_DATABASE_URL'] = 'postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test'
    # we can just use alembic module
    from alembic.config import Config
    from alembic import command
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    print("Done lpg_test")

if __name__ == '__main__':
    main()
