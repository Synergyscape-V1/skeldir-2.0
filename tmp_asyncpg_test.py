import asyncio, asyncpg
async def main():
    dsn = "postgresql://app_user:5K31d1r_App_Pr8d_2025%21@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
    try:
        conn = await asyncpg.connect(dsn)
        row = await conn.fetchrow('select current_user')
        print(row)
        await conn.close()
    except Exception as e:
        print('asyncpg error', e)
asyncio.run(main())
