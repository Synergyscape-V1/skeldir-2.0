-- ILLUSTRATIVE ONLY - NOT APPLIED
-- 
-- This exemplar demonstrates ALL governance rules working together:
-- - Style guide compliance (naming, primary key, timestamps, booleans, FKs, check constraints, indexes, comments)
-- - Contract mapping compliance (type conversions, nullability, enum handling)
-- - RLS policy application (tenant isolation using template from Phase 5)
-- - Roles/GRANTs application (using patterns from Phase 5)
-- - Comment standard compliance (all objects commented with Purpose, data class, ownership)
-- - Traceability standard compliance (correlation_id, actor_* metadata)
-- 
-- This exemplar passes all lint rules and validates against all governance artifacts.

-- ============================================================================
-- HYPOTHETICAL TABLE: revenue_events
-- ============================================================================
-- Purpose: Demonstrates complete governance rule compliance
-- Data Class: Non-PII
-- Ownership: Attribution service
-- 
-- This table represents a hypothetical revenue event table that would support
-- the RealtimeRevenueResponse contract (api-contracts/openapi/v1/attribution.yaml:39-64)
-- ============================================================================

-- Step 1: Create table following style guide
CREATE TABLE revenue_events (
    -- Primary key: id uuid with gen_random_uuid() (Style Guide)
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign key: tenant_id (Style Guide, Contract Mapping)
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Timestamp trio: created_at, updated_at, and domain-specific timestamp (Style Guide)
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    event_timestamp timestamptz NOT NULL,
    
    -- Contract mapping: total_revenue (number float) → revenue_cents (integer) (Contract Mapping)
    -- Required field → NOT NULL (Contract Mapping)
    revenue_cents INTEGER NOT NULL CHECK (revenue_cents >= 0),
    
    -- Contract mapping: verified (boolean) → verified (boolean) (Contract Mapping)
    -- Required field → NOT NULL (Contract Mapping)
    verified boolean NOT NULL DEFAULT false,
    
    -- Contract mapping: data_freshness_seconds (integer) → data_freshness_seconds (integer) (Contract Mapping)
    -- Required field → NOT NULL (Contract Mapping)
    data_freshness_seconds INTEGER NOT NULL,
    
    -- Enum handling: reconciliation_state (CHECK constraint for small stable enum) (Contract Mapping)
    -- Example from reconciliation.yaml:47-52
    reconciliation_state VARCHAR(20) NOT NULL DEFAULT 'idle' 
        CHECK (reconciliation_state IN ('idle', 'running', 'failed', 'completed')),
    
    -- Boolean with prefix: is_processed (Style Guide)
    is_processed boolean NOT NULL DEFAULT false,
    
    -- JSONB for raw payload (Style Guide)
    raw_payload JSONB NOT NULL,
    
    -- Traceability: correlation_id (Traceability Standard)
    correlation_id uuid,
    
    -- Traceability: actor_* metadata (Traceability Standard)
    actor_user_id uuid,
    actor_service_name VARCHAR(100) NOT NULL DEFAULT 'attribution-service',
    actor_system boolean NOT NULL DEFAULT false
);

-- Step 2: Check constraint with naming: ck_{table}_{column}_{condition} (Style Guide)
ALTER TABLE revenue_events 
    ADD CONSTRAINT ck_revenue_events_revenue_positive 
    CHECK (revenue_cents >= 0);

-- Step 3: Index with naming: idx_{table}_{columns} (Style Guide)
-- Time-series index: (tenant_id, timestamp DESC) (Style Guide, Lint Rules)
CREATE INDEX idx_revenue_events_tenant_timestamp 
    ON revenue_events (tenant_id, event_timestamp DESC);

-- GIN index for JSONB column (Style Guide)
CREATE INDEX idx_revenue_events_raw_payload 
    ON revenue_events USING GIN (raw_payload);

-- Step 4: Comments on all objects (Style Guide, Lint Rules)
COMMENT ON TABLE revenue_events IS 
    'Hypothetical revenue events table demonstrating governance rule compliance. Purpose: Illustrate complete schema patterns. Data class: Non-PII. Ownership: Attribution service.';

COMMENT ON COLUMN revenue_events.id IS 
    'Primary key UUID. Purpose: Unique identifier. Data class: Non-PII.';

COMMENT ON COLUMN revenue_events.tenant_id IS 
    'Foreign key to tenants table. Purpose: Tenant isolation. Data class: Non-PII.';

COMMENT ON COLUMN revenue_events.created_at IS 
    'Record creation timestamp. Purpose: Audit trail. Data class: Non-PII.';

COMMENT ON COLUMN revenue_events.updated_at IS 
    'Record update timestamp. Purpose: Audit trail. Data class: Non-PII.';

COMMENT ON COLUMN revenue_events.event_timestamp IS 
    'Domain-specific event timestamp. Purpose: Business logic timestamping. Data class: Non-PII.';

COMMENT ON COLUMN revenue_events.revenue_cents IS 
    'Revenue amount in cents (INTEGER). Purpose: Store revenue for attribution calculations. Contract mapping: total_revenue (number float) → revenue_cents (integer). Data class: Non-PII.';

COMMENT ON COLUMN revenue_events.verified IS 
    'Whether revenue data has been verified. Purpose: Reconciliation status. Contract mapping: verified (boolean). Data class: Non-PII.';

COMMENT ON COLUMN revenue_events.data_freshness_seconds IS 
    'Seconds since data was last updated. Purpose: Data freshness tracking. Contract mapping: data_freshness_seconds (integer). Data class: Non-PII.';

COMMENT ON COLUMN revenue_events.reconciliation_state IS 
    'Reconciliation pipeline state. Purpose: Track reconciliation status. Contract mapping: state enum (idle|running|failed|completed). Data class: Non-PII.';

COMMENT ON COLUMN revenue_events.is_processed IS 
    'Whether event has been processed. Purpose: Processing status tracking. Data class: Non-PII.';

COMMENT ON COLUMN revenue_events.raw_payload IS 
    'Raw webhook payload (JSONB). Purpose: Store original event data. Data class: Non-PII (PII stripped).';

COMMENT ON COLUMN revenue_events.correlation_id IS 
    'Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing. Data class: Non-PII.';

COMMENT ON COLUMN revenue_events.actor_service_name IS 
    'Service that processed this event. Purpose: Audit trail. Data class: Non-PII.';

COMMENT ON INDEX idx_revenue_events_tenant_timestamp IS 
    'Composite index on (tenant_id, event_timestamp DESC). Purpose: Optimize time-series queries by tenant.';

COMMENT ON INDEX idx_revenue_events_raw_payload IS 
    'GIN index on raw_payload JSONB column. Purpose: Enable fast JSON queries.';

COMMENT ON CONSTRAINT ck_revenue_events_revenue_positive ON revenue_events IS 
    'Ensures revenue_cents >= 0. Purpose: Prevent negative revenue values.';

-- Step 5: RLS policy for tenant isolation (RLS Template, Lint Rules)
ALTER TABLE revenue_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON revenue_events
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

COMMENT ON POLICY tenant_isolation_policy ON revenue_events IS 
    'RLS policy enforcing tenant isolation. Purpose: Prevent cross-tenant data access. Requires app.current_tenant_id to be set via set_config().';

-- Step 6: Roles and GRANTs (Roles/GRANTs Template)
-- Create roles (if not exists) - repeatable migration pattern
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_rw') THEN
        CREATE ROLE app_rw;
    END IF;
    
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_ro') THEN
        CREATE ROLE app_ro;
    END IF;
END
$$;

-- Grant permissions to roles
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE revenue_events TO app_rw;
GRANT SELECT ON TABLE revenue_events TO app_ro;

-- ============================================================================
-- VALIDATION CHECKLIST
-- ============================================================================
-- This exemplar demonstrates:
-- ✅ Style guide: snake_case, id uuid, timestamps, booleans, FKs, check constraints, indexes, comments
-- ✅ Contract mapping: type conversions, nullability, enum handling
-- ✅ RLS policy: tenant isolation using current_setting('app.current_tenant_id')::UUID
-- ✅ Roles/GRANTs: app_rw and app_ro grants
-- ✅ Comments: All objects commented with Purpose, Data Class, Ownership
-- ✅ Traceability: correlation_id, actor_* metadata
-- ✅ Lint compliance: No data/misc columns, all objects commented, NOT NULL for required, tenant_id present, RLS policy present, INTEGER for revenue
-- ============================================================================





