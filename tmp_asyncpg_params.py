import asyncio, asyncpg
async def main():
    try:
        conn = await asyncpg.connect(user='app_user', password='5K31d1r_App_Pr8d_2025%21', host='ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech', database='neondb', ssl='require')
        row = await conn.fetchrow('select current_user')
        print(row)
        await conn.close()
    except Exception as e:
        print('asyncpg error', e)
asyncio.run(main())
