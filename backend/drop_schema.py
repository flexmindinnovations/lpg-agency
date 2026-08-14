import asyncio
import asyncpg

async def main():
    for db in ['lpg_dev', 'lpg_test']:
        try:
            conn = await asyncpg.connect(f'postgresql://lpg_admin:dev_only_not_a_real_secret@localhost:55432/{db}')
            await conn.execute('DROP SCHEMA IF EXISTS notification CASCADE')
            await conn.close()
            print(f"Dropped schema from {db}")
        except Exception as e:
            print(f"Failed for {db}: {e}")

if __name__ == '__main__':
    asyncio.run(main())
