import asyncio
from app.db.session import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        try:
            await conn.execute(text('CREATE TABLE public.tmp_app_user_test(id int)'))
            print('table created')
        except Exception as e:
            print('failed create table', e)
    await engine.dispose()

asyncio.run(main())
