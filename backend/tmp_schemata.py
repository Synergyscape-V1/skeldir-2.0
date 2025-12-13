import asyncio
from app.db.session import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT schema_name FROM information_schema.schemata"))
        print(res.fetchall())
    await engine.dispose()

asyncio.run(main())
