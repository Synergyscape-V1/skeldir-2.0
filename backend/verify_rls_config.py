"""Verify RLS configuration on attribution_events table"""
import asyncio
import os

os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_ETLZ7UxM3obe@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from sqlalchemy import text
from app.db.session import engine


async def main():
    async with engine.connect() as conn:
        # Check if RLS is enabled
        result = await conn.execute(text("""
            SELECT schemaname, tablename, rowsecurity
            FROM pg_tables
            WHERE tablename IN ('attribution_events', 'dead_events')
            ORDER BY tablename
        """))
        print("\n" + "="*70)
        print("RLS ENABLED STATUS:")
        print("="*70)
        for row in result:
            print(f"  {row[1]:<30} rowsecurity={row[2]}")

        # Check RLS policies
        result = await conn.execute(text("""
            SELECT
                schemaname,
                tablename,
                policyname,
                permissive,
                roles,
                cmd,
                qual,
                with_check
            FROM pg_policies
            WHERE tablename IN ('attribution_events', 'dead_events')
            ORDER BY tablename, policyname
        """))
        print("\n" + "="*70)
        print("RLS POLICIES:")
        print("="*70)
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"\n  Table: {row[1]}")
                print(f"  Policy: {row[2]}")
                print(f"  Command: {row[5]}")
                print(f"  Qual: {row[6]}")
                print(f"  With Check: {row[7]}")
        else:
            print("  NO POLICIES FOUND!")

        print("\n" + "="*70)


if __name__ == "__main__":
    asyncio.run(main())
