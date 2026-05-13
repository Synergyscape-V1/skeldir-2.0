"""Check if PII guardrail trigger/function exists and matches canonical schema"""
import asyncio
import os

os.environ["DATABASE_URL"] = "postgresql://migration_owner:migration_owner@127.0.0.1:5432/skeldir"

from sqlalchemy import text
from app.db.session import engine


async def main():
    async with engine.connect() as conn:
        # Check trigger exists
        result = await conn.execute(
            text("""
                SELECT tgname, tgrelid::regclass, tgfoid::regproc
                FROM pg_trigger
                WHERE tgname = 'trg_pii_guardrail_attribution_events'
            """)
        )
        trigger = result.fetchone()

        if trigger:
            print(f"Trigger found: {trigger[0]} on {trigger[1]} -> function {trigger[2]}")
        else:
            print("Trigger NOT found!")

        # Check function definition
        result = await conn.execute(
            text("SELECT pg_get_functiondef('fn_enforce_pii_guardrail'::regproc)")
        )
        func_def = result.scalar()
        if func_def:
            print("\nFunction definition:")
            print("="*60)
            print(func_def[:500])
            print("...")
        else:
            print("Function NOT found!")


if __name__ == "__main__":
    asyncio.run(main())
