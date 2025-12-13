"""
Investigate PII Guardrail Trigger Function

Retrieves full function definition to identify NEW.metadata bug.
"""
import asyncio
import os

os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_ETLZ7UxM3obe@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from sqlalchemy import text
from app.db.session import engine


async def main():
    async with engine.connect() as conn:
        # Get full function definition
        result = await conn.execute(
            text("SELECT pg_get_functiondef('fn_enforce_pii_guardrail'::regproc)")
        )
        func_def = result.scalar()

        print("\n" + "="*70)
        print("CURRENT PRODUCTION FUNCTION: fn_enforce_pii_guardrail()")
        print("="*70)
        print(func_def)
        print("="*70)

        # Check which tables use this trigger
        result = await conn.execute(
            text("""
                SELECT tgname, tgrelid::regclass, tgenabled
                FROM pg_trigger
                WHERE tgfoid = 'fn_enforce_pii_guardrail'::regproc
                ORDER BY tgrelid::regclass::text
            """)
        )
        triggers = result.fetchall()

        print("\n" + "="*70)
        print("TRIGGERS USING THIS FUNCTION:")
        print("="*70)
        for trig in triggers:
            status = "ENABLED" if trig[2] == 'O' else "DISABLED"
            print(f"  {trig[0]:<50} ON {trig[1]:<20} [{status}]")
        print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
