import asyncio
import asyncpg
import os

async def check_webhook_columns():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])

    # Check for webhook-related columns in tenants table
    cols = await conn.fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'tenants'
        AND column_name LIKE '%webhook%'
        ORDER BY column_name
    """)

    print("Webhook-related columns in tenants table:")
    for col in cols:
        print(f"  {col['column_name']}: {col['data_type']}")

    if not cols:
        print("  No webhook columns found")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_webhook_columns())
