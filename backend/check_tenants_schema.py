"""Check tenants table schema"""
import asyncio
import os

os.environ["DATABASE_URL"] = "postgresql://migration_owner:migration_owner@127.0.0.1:5432/skeldir"

from sqlalchemy import text
from app.db.session import engine


async def main():
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'tenants'
                ORDER BY ordinal_position
            """)
        )
        columns = result.fetchall()

        print("\ntenants table schema:")
        print("="*60)
        for col in columns:
            print(f"  {col[0]:<30} {col[1]}")
        print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
