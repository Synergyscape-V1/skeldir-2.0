"""Simple schema validation using direct SQL queries"""

import asyncio
import os

os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_ETLZ7UxM3obe@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from sqlalchemy import text
from app.db.session import engine
from app.models import AttributionEvent, DeadEvent, ChannelTaxonomy


async def get_db_columns(table_name):
    """Get column names from database"""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :table
                ORDER BY ordinal_position
            """),
            {"table": table_name}
        )
        return {row[0] for row in result}


async def main():
    print("\n" + "="*60)
    print(" B0.4.2 SCHEMA ALIGNMENT VALIDATION")
    print("="*60 + "\n")

    # Attribution Events
    print("Checking attribution_events...")
    db_cols = await get_db_columns("attribution_events")
    model_cols = {col.name for col in AttributionEvent.__table__.columns}

    missing = db_cols - model_cols
    extra = model_cols - db_cols

    if missing or extra:
        print(f"  FAIL - Missing: {missing}, Extra: {extra}")
    else:
        print(f"  PASS - All {len(model_cols)} columns aligned")

    # Dead Events
    print("\nChecking dead_events...")
    db_cols = await get_db_columns("dead_events")
    model_cols = {col.name for col in DeadEvent.__table__.columns}

    missing = db_cols - model_cols
    extra = model_cols - db_cols

    if missing or extra:
        print(f"  FAIL - Missing: {missing}, Extra: {extra}")
    else:
        print(f"  PASS - All {len(model_cols)} columns aligned")

    # Channel Taxonomy
    print("\nChecking channel_taxonomy...")
    db_cols = await get_db_columns("channel_taxonomy")
    model_cols = {col.name for col in ChannelTaxonomy.__table__.columns}

    missing = db_cols - model_cols
    extra = model_cols - db_cols

    if missing or extra:
        print(f"  FAIL - Missing: {missing}, Extra: {extra}")
    else:
        print(f"  PASS - All {len(model_cols)} columns aligned")

    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(main())
