import asyncio
import asyncpg

async def test_asyncpg():
    try:
        conn = await asyncpg.connect(
            "postgresql://app_user:npg_IGZ4D2rHNndq@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
        )
        result = await conn.fetchrow("SELECT current_user;")
        print(f"? asyncpg SUCCESS: {result}")
        await conn.close()
    except Exception as e:
        print(f"? asyncpg FAILED: {type(e).__name__}: {e}")

asyncio.run(test_asyncpg())
