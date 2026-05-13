"""Test that get_session() correctly sets app.current_tenant_id"""
import asyncio
import os
from uuid import uuid4

os.environ["DATABASE_URL"] = "postgresql://migration_owner:migration_owner@127.0.0.1:5432/skeldir"

from sqlalchemy import text
from app.db.session import get_session


async def main():
    tenant_a = uuid4()
    tenant_b = uuid4()

    print("\n" + "="*70)
    print("TESTING RLS CONTEXT SETTING")
    print("="*70)

    # Test tenant_a context
    async with get_session(tenant_id=tenant_a) as session:
        result = await session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
        current_tenant = result.scalar()
        print(f"\nTenant A context:")
        print(f"  Expected: {tenant_a}")
        print(f"  Actual:   {current_tenant}")
        print(f"  Match:    {str(tenant_a) == current_tenant}")

    # Test tenant_b context
    async with get_session(tenant_id=tenant_b) as session:
        result = await session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
        current_tenant = result.scalar()
        print(f"\nTenant B context:")
        print(f"  Expected: {tenant_b}")
        print(f"  Actual:   {current_tenant}")
        print(f"  Match:    {str(tenant_b) == current_tenant}")

    print("\n" + "="*70)


if __name__ == "__main__":
    asyncio.run(main())
