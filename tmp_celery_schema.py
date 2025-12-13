import asyncio, os
from app.db.session import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        try:
            await conn.execute(text('CREATE SCHEMA celery'))
            print('created schema')
        except Exception as e:
            print('failed create schema', e)
    await engine.dispose()

asyncio.run(main())
