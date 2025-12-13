"""Quick script to list channel taxonomy codes"""
import asyncio
import os

os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_ETLZ7UxM3obe@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from sqlalchemy import text
from app.db.session import engine


async def main():
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT code, display_name FROM channel_taxonomy ORDER BY code")
        )
        print("\nChannel Taxonomy Codes:")
        print("="*50)
        for row in result:
            print(f"  {row[0]:<20} {row[1]}")
        print("="*50)


if __name__ == "__main__":
    asyncio.run(main())
