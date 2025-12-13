"""Check if current database role bypasses RLS"""
import asyncio
import os

os.environ["DATABASE_URL"] = "postgresql://app_user:Sk3ld1r_App_Pr0d_2025!@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from sqlalchemy import text
from app.db.session import engine


async def main():
    async with engine.connect() as conn:
        # Check current role
        result = await conn.execute(text("SELECT current_user, current_database()"))
        user, db = result.fetchone()
        print("\n" + "="*70)
        print("DATABASE CONNECTION INFO:")
        print("="*70)
        print(f"  User: {user}")
        print(f"  Database: {db}")

        # Check if role is superuser
        result = await conn.execute(text("""
            SELECT rolname, rolsuper, rolbypassrls
            FROM pg_roles
            WHERE rolname = current_user
        """))
        row = result.fetchone()
        print(f"\n  Rolename: {row[0]}")
        print(f"  Superuser: {row[1]}")
        print(f"  Bypass RLS: {row[2]}")

        if row[2]:
            print("\n" + "="*70)
            print("CRITICAL: Current role has BYPASSRLS privilege!")
            print("RLS policies will not apply to this role.")
            print("="*70)

        # Check table owner
        result = await conn.execute(text("""
            SELECT schemaname, tablename, tableowner
            FROM pg_tables
            WHERE tablename = 'attribution_events'
        """))
        row = result.fetchone()
        print(f"\n  attribution_events table owner: {row[2]}")

        print("\n" + "="*70)


if __name__ == "__main__":
    asyncio.run(main())
