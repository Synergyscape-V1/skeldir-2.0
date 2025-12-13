-- ============================================================================
-- PII GUARDRAIL TRIGGER FIX - B0.4.3.1 Remediation
-- ============================================================================
-- Problem: Single fn_enforce_pii_guardrail() references NEW.metadata which
--          doesn't exist in attribution_events/dead_events tables
-- Solution: Split into table-specific functions to avoid cross-table field refs
-- ============================================================================

-- Drop existing triggers (already disabled, but drop for clean reinstall)
DROP TRIGGER IF EXISTS trg_pii_guardrail_attribution_events ON attribution_events;
DROP TRIGGER IF EXISTS trg_pii_guardrail_dead_events ON dead_events;
DROP TRIGGER IF EXISTS trg_pii_guardrail_revenue_ledger ON revenue_ledger;

-- ============================================================================
-- Function 1: PII Guardrail for Events (raw_payload column)
-- ============================================================================
CREATE OR REPLACE FUNCTION public.fn_enforce_pii_guardrail_events()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    detected_key TEXT;
BEGIN
    -- Check raw_payload for PII keys
    IF fn_detect_pii_keys(NEW.raw_payload) THEN
        -- Find first PII key for error message
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
        USING ERRCODE = '23514';  -- check_violation
    END IF;

    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION fn_enforce_pii_guardrail_events() IS
'PII guardrail for attribution_events and dead_events tables. Scans raw_payload JSONB column for prohibited PII keys. Part of Layer 2 defense-in-depth (ADR-003).';

-- ============================================================================
-- Function 2: PII Guardrail for Revenue Ledger (metadata column)
-- ============================================================================
CREATE OR REPLACE FUNCTION public.fn_enforce_pii_guardrail_revenue()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    detected_key TEXT;
BEGIN
    -- Check metadata for PII keys (only if NOT NULL)
    IF NEW.metadata IS NOT NULL THEN
        IF fn_detect_pii_keys(NEW.metadata) THEN
            -- Find first PII key for error message
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
            USING ERRCODE = '23514';  -- check_violation
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION fn_enforce_pii_guardrail_revenue() IS
'PII guardrail for revenue_ledger table. Scans metadata JSONB column for prohibited PII keys. Part of Layer 2 defense-in-depth (ADR-003).';

-- ============================================================================
-- Recreate Triggers with Correct Functions
-- ============================================================================

-- Attribution Events trigger
CREATE TRIGGER trg_pii_guardrail_attribution_events
BEFORE INSERT ON attribution_events
FOR EACH ROW
EXECUTE FUNCTION fn_enforce_pii_guardrail_events();

COMMENT ON TRIGGER trg_pii_guardrail_attribution_events ON attribution_events IS
'PII guardrail trigger (Layer 2 defense-in-depth). Blocks INSERT if raw_payload contains PII keys. Function: fn_enforce_pii_guardrail_events(). Reference: ADR-003-PII-Defense-Strategy.md.';

-- Dead Events trigger
CREATE TRIGGER trg_pii_guardrail_dead_events
BEFORE INSERT ON dead_events
FOR EACH ROW
EXECUTE FUNCTION fn_enforce_pii_guardrail_events();

COMMENT ON TRIGGER trg_pii_guardrail_dead_events ON dead_events IS
'PII guardrail trigger (Layer 2 defense-in-depth). Blocks INSERT if raw_payload contains PII keys. Function: fn_enforce_pii_guardrail_events(). Reference: ADR-003-PII-Defense-Strategy.md.';

-- Revenue Ledger trigger
CREATE TRIGGER trg_pii_guardrail_revenue_ledger
BEFORE INSERT ON revenue_ledger
FOR EACH ROW
EXECUTE FUNCTION fn_enforce_pii_guardrail_revenue();

COMMENT ON TRIGGER trg_pii_guardrail_revenue_ledger ON revenue_ledger IS
'PII guardrail trigger (Layer 2 defense-in-depth). Blocks INSERT if metadata contains PII keys. Function: fn_enforce_pii_guardrail_revenue(). Reference: ADR-003-PII-Defense-Strategy.md.';

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Verify triggers are enabled
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
ORDER BY tgrelid::regclass::text;
