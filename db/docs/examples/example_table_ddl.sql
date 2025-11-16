-- ILLUSTRATIVE ONLY - NOT APPLIED
-- This example demonstrates all style guide rules and lint rule compliance

-- Example table following all style guide conventions
CREATE TABLE example_attribution_events (
    -- Primary key: id uuid with gen_random_uuid()
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign key: tenant_id (references tenants table)
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Timestamp trio: created_at, updated_at, and domain-specific timestamp
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    event_timestamp timestamptz NOT NULL,
    
    -- Boolean with prefix: is_verified
    is_verified boolean NOT NULL DEFAULT false,
    
    -- Revenue in cents: INTEGER (not DECIMAL or FLOAT)
    revenue_cents INTEGER NOT NULL CHECK (revenue_cents >= 0),
    
    -- JSONB for raw payload
    raw_payload JSONB NOT NULL,
    
    -- Processing status state machine
    processing_status VARCHAR(20) NOT NULL DEFAULT 'pending' 
        CHECK (processing_status IN ('pending', 'processed', 'failed', 'dead')),
    
    -- Traceability: correlation_id and actor metadata
    correlation_id uuid,
    actor_user_id uuid,
    actor_service_name VARCHAR(100)
);

-- Check constraint with naming: ck_{table}_{column}_{condition}
ALTER TABLE example_attribution_events 
    ADD CONSTRAINT ck_example_attribution_events_revenue_positive 
    CHECK (revenue_cents >= 0);

-- Index with naming: idx_{table}_{columns}
CREATE INDEX idx_example_attribution_events_tenant_timestamp 
    ON example_attribution_events (tenant_id, event_timestamp DESC);

-- GIN index for JSONB column
CREATE INDEX idx_example_attribution_events_raw_payload 
    ON example_attribution_events USING GIN (raw_payload);

-- Comments on all objects (required by lint rules)
COMMENT ON TABLE example_attribution_events IS 
    'Example attribution events table demonstrating style guide compliance. Purpose: Illustrate schema patterns. Data class: Non-PII. Ownership: Backend team.';

COMMENT ON COLUMN example_attribution_events.id IS 
    'Primary key UUID. Purpose: Unique identifier. Data class: Non-PII.';

COMMENT ON COLUMN example_attribution_events.tenant_id IS 
    'Foreign key to tenants table. Purpose: Tenant isolation. Data class: Non-PII.';

COMMENT ON COLUMN example_attribution_events.revenue_cents IS 
    'Revenue amount in cents (INTEGER). Purpose: Store revenue for attribution. Data class: Non-PII.';

COMMENT ON COLUMN example_attribution_events.raw_payload IS 
    'Raw webhook payload (JSONB). Purpose: Store original event data. Data class: Non-PII (PII stripped).';

-- RLS policy for tenant isolation (required for multi-tenant tables)
ALTER TABLE example_attribution_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON example_attribution_events
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

COMMENT ON POLICY tenant_isolation_policy ON example_attribution_events IS 
    'RLS policy enforcing tenant isolation. Purpose: Prevent cross-tenant data access.';





