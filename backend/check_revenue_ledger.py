"""Check if revenue_ledger table exists with metadata column"""
import asyncio
import os

os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_ETLZ7UxM3obe@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from sqlalchemy import text
from app.db.session import engine


async def main():
    async with engine.connect() as conn:
        # Check if table exists
        result = await conn.execute(
            text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'revenue_ledger'
                ORDER BY ordinal_position
            """)
        )
        columns = result.fetchall()

        if columns:
            print(f"\nrevenue_ledger table found with {len(columns)} columns:")
            print("="*60)
            for col in columns:
                print(f"  {col[0]:<30} {col[1]}")
            print("="*60)
        else:
            print("\nrevenue_ledger table NOT FOUND!")
            print("This might explain the trigger error - table may not be deployed yet.")


if __name__ == "__main__":
    asyncio.run(main())
