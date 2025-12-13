import asyncio
from app.db.session import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT schemaname, tablename FROM pg_tables WHERE tablename ILIKE 'celery_%' OR tablename ILIKE 'kombu_%' ORDER BY schemaname, tablename"))
        rows = res.fetchall()
        print(rows)
    await engine.dispose()

asyncio.run(main())
