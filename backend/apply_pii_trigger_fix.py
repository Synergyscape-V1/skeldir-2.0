"""
Apply PII Trigger Fix to Production Database

Executes fix_pii_trigger.sql to replace single function with table-specific functions.
"""
import asyncio
import os

os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_ETLZ7UxM3obe@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from sqlalchemy import text
from app.db.session import engine


async def main():
    print("\n" + "="*70)
    print("APPLYING PII TRIGGER FIX")
    print("="*70)

    # Read SQL file
    with open("fix_pii_trigger.sql", "r") as f:
        sql = f.read()

    # Execute entire file as single transaction
    # asyncpg supports multi-statement execution
    async with engine.begin() as conn:
        print("\n[1] Dropping existing triggers...")
        await conn.execute(text("DROP TRIGGER IF EXISTS trg_pii_guardrail_attribution_events ON attribution_events"))
        await conn.execute(text("DROP TRIGGER IF EXISTS trg_pii_guardrail_dead_events ON dead_events"))
        await conn.execute(text("DROP TRIGGER IF EXISTS trg_pii_guardrail_revenue_ledger ON revenue_ledger"))
        print("    SUCCESS")

        print("\n[2] Creating fn_enforce_pii_guardrail_events()...")
        await conn.execute(text("""
CREATE OR REPLACE FUNCTION public.fn_enforce_pii_guardrail_events()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    detected_key TEXT;
BEGIN
    IF fn_detect_pii_keys(NEW.raw_payload) THEN
        SELECT key INTO detected_key
        FROM jsonb_object_keys(NEW.raw_payload) key
        WHERE key IN (
            'email', 'email_address',
            'phone', 'phone_number',
            'ssn', 'social_security_number',
            'ip_address', 'ip',
            'first_name', 'last_name', 'full_name',
            'address', 'street_address'
        )
        LIMIT 1;

        RAISE EXCEPTION 'PII key detected in %.raw_payload. Ingestion blocked by database policy (Layer 2 guardrail). Key found: %. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from payload before retry.',
            TG_TABLE_NAME,
            detected_key
        USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$
        """))
        print("    SUCCESS")

        print("\n[3] Creating fn_enforce_pii_guardrail_revenue()...")
        await conn.execute(text("""
CREATE OR REPLACE FUNCTION public.fn_enforce_pii_guardrail_revenue()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    detected_key TEXT;
BEGIN
    IF NEW.metadata IS NOT NULL THEN
        IF fn_detect_pii_keys(NEW.metadata) THEN
            SELECT key INTO detected_key
            FROM jsonb_object_keys(NEW.metadata) key
            WHERE key IN (
                'email', 'email_address',
                'phone', 'phone_number',
                'ssn', 'social_security_number',
                'ip_address', 'ip',
                'first_name', 'last_name', 'full_name',
                'address', 'street_address'
            )
            LIMIT 1;

            RAISE EXCEPTION 'PII key detected in revenue_ledger.metadata. Write blocked by database policy (Layer 2 guardrail). Key found: %. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from metadata before retry.',
                detected_key
            USING ERRCODE = '23514';
        END IF;
    END IF;

    RETURN NEW;
END;
$$
        """))
        print("    SUCCESS")

        print("\n[4] Creating trigger on attribution_events...")
        await conn.execute(text("""
CREATE TRIGGER trg_pii_guardrail_attribution_events
BEFORE INSERT ON attribution_events
FOR EACH ROW
EXECUTE FUNCTION fn_enforce_pii_guardrail_events()
        """))
        print("    SUCCESS")

        print("\n[5] Creating trigger on dead_events...")
        await conn.execute(text("""
CREATE TRIGGER trg_pii_guardrail_dead_events
BEFORE INSERT ON dead_events
FOR EACH ROW
EXECUTE FUNCTION fn_enforce_pii_guardrail_events()
        """))
        print("    SUCCESS")

        print("\n[6] Creating trigger on revenue_ledger...")
        await conn.execute(text("""
CREATE TRIGGER trg_pii_guardrail_revenue_ledger
BEFORE INSERT ON revenue_ledger
FOR EACH ROW
EXECUTE FUNCTION fn_enforce_pii_guardrail_revenue()
        """))
        print("    SUCCESS")

        print("\n[7] Verifying triggers...")
        result = await conn.execute(text("""
SELECT
    tgname AS trigger_name,
    tgrelid::regclass AS table_name,
    tgfoid::regproc AS function_name,
    CASE tgenabled
        WHEN 'O' THEN 'ENABLED'
        WHEN 'D' THEN 'DISABLED'
    END AS status
FROM pg_trigger
WHERE tgname LIKE 'trg_pii_guardrail%'
ORDER BY tgrelid::regclass::text
        """))
        rows = result.fetchall()
        for row in rows:
            print(f"    {row[0]:<50} ON {row[1]:<25} -> {row[2]:<40} [{row[3]}]")

    print("\n" + "="*70)
    print("PII TRIGGER FIX APPLIED SUCCESSFULLY")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
