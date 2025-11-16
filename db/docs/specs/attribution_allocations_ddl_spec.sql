-- DDL Specification for attribution_allocations table
-- Purpose: Store attribution model allocations (channel credit assignments)
-- Data Class: Non-PII
-- Ownership: Attribution service
-- Contract Mapping: Supports attribution calculations and channel performance queries

CREATE TABLE attribution_allocations (
    -- Primary key: id uuid with gen_random_uuid() (Style Guide)
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign key: tenant_id (Style Guide, Contract Mapping)
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Foreign key: event_id (references attribution_events)
    event_id uuid NOT NULL REFERENCES attribution_events(id) ON DELETE CASCADE,
    
    -- Timestamp trio: created_at, updated_at (Style Guide)
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    
    -- Channel identifier (e.g., google_search, facebook_ads)
    channel text NOT NULL,
    
    -- Allocation ratio (0.0 to 1.0): numeric(6,5) (Phase 4A requirement)
    allocation_ratio numeric(6,5) NOT NULL DEFAULT 0.0 CHECK (allocation_ratio >= 0 AND allocation_ratio <= 1),
    
    -- Model version: text NOT NULL (Phase 4A requirement)
    model_version text NOT NULL DEFAULT 'unknown',
    
    -- Allocated revenue in cents: INTEGER (not DECIMAL or FLOAT) (Style Guide)
    allocated_revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK (allocated_revenue_cents >= 0),
    
    -- Attribution model metadata (JSONB for model-specific data)
    model_metadata jsonb,
    
    -- Correlation ID for distributed tracing (nullable)
    correlation_id uuid
);

-- Time-series index: (tenant_id, created_at DESC) (Style Guide, Lint Rules)
CREATE INDEX idx_attribution_allocations_tenant_created_at 
    ON attribution_allocations (tenant_id, created_at DESC);

-- Index on event_id for event-to-allocation joins
CREATE INDEX idx_attribution_allocations_event_id 
    ON attribution_allocations (event_id);

-- Index on channel for channel performance queries
CREATE INDEX idx_attribution_allocations_channel 
    ON attribution_allocations (channel);

-- Idempotency unique index: (tenant_id, event_id, model_version, channel) (Phase 4A requirement)
CREATE UNIQUE INDEX idx_attribution_allocations_tenant_event_model_channel
    ON attribution_allocations (tenant_id, event_id, model_version, channel)
    WHERE model_version IS NOT NULL;

-- Index on (tenant_id, model_version) for model rollups (Phase 4A requirement)
CREATE INDEX idx_attribution_allocations_tenant_model_version
    ON attribution_allocations (tenant_id, model_version);

-- Check constraint with naming: ck_{table}_{column}_{condition} (Style Guide)
ALTER TABLE attribution_allocations 
    ADD CONSTRAINT ck_attribution_allocations_revenue_positive 
    CHECK (allocated_revenue_cents >= 0);

-- Allocation ratio bounds check (Phase 4A requirement)
ALTER TABLE attribution_allocations
    ADD CONSTRAINT ck_attribution_allocations_allocation_ratio_bounds
    CHECK (allocation_ratio >= 0 AND allocation_ratio <= 1);

-- Channel code validation (Phase 4A requirement - deferred to contract review)
ALTER TABLE attribution_allocations
    ADD CONSTRAINT ck_attribution_allocations_channel_code_valid
    CHECK (channel IN (
        'google_search',
        'facebook_ads',
        'direct',
        'email',
        'organic',
        'referral',
        'social',
        'paid_search',
        'display'
    ));

-- Comments on all objects (Style Guide, Lint Rules)
COMMENT ON TABLE attribution_allocations IS 
    'Stores attribution model allocations (channel credit assignments). Purpose: Store channel credit for attribution calculations. Data class: Non-PII. Ownership: Attribution service. RLS enabled for tenant isolation.';

COMMENT ON COLUMN attribution_allocations.id IS 
    'Primary key UUID. Purpose: Unique allocation identifier. Data class: Non-PII.';

COMMENT ON COLUMN attribution_allocations.tenant_id IS 
    'Foreign key to tenants table. Purpose: Tenant isolation. Data class: Non-PII.';

COMMENT ON COLUMN attribution_allocations.event_id IS 
    'Foreign key to attribution_events table. Purpose: Link allocation to source event. Data class: Non-PII.';

COMMENT ON COLUMN attribution_allocations.created_at IS 
    'Record creation timestamp. Purpose: Audit trail. Data class: Non-PII.';

COMMENT ON COLUMN attribution_allocations.updated_at IS 
    'Record update timestamp. Purpose: Audit trail. Data class: Non-PII.';

COMMENT ON COLUMN attribution_allocations.channel IS 
    'Channel identifier (e.g., google_search, facebook_ads). Purpose: Identify attribution channel. Data class: Non-PII.';

COMMENT ON COLUMN attribution_allocations.allocation_ratio IS 
    'Allocation ratio (0.0 to 1.0) representing the proportion of event revenue allocated to this channel. Purpose: Enable deterministic revenue accounting and sum-equality validation. Data class: Non-PII.';

COMMENT ON COLUMN attribution_allocations.model_version IS 
    'Attribution model version (semantic version string). Purpose: Track which model version generated this allocation, enabling model rollups and sum-equality validation per model version. Data class: Non-PII.';

COMMENT ON COLUMN attribution_allocations.allocated_revenue_cents IS 
    'Allocated revenue amount in cents (INTEGER). Purpose: Store channel credit amount. Data class: Non-PII.';

COMMENT ON COLUMN attribution_allocations.model_metadata IS 
    'Attribution model metadata (JSONB). Purpose: Store model-specific data (e.g., convergence_r_hat, effective_sample_size). Data class: Non-PII.';

COMMENT ON COLUMN attribution_allocations.correlation_id IS 
    'Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing and event stitching across tables. Links attribution_allocations, attribution_events, and dead_events. Data class: Non-PII.';

COMMENT ON INDEX idx_attribution_allocations_tenant_created_at IS 
    'Composite index on (tenant_id, created_at DESC). Purpose: Optimize time-series queries by tenant.';

COMMENT ON INDEX idx_attribution_allocations_event_id IS 
    'Index on event_id. Purpose: Enable fast event-to-allocation joins.';

COMMENT ON INDEX idx_attribution_allocations_channel IS 
    'Index on channel. Purpose: Enable fast channel performance queries.';

COMMENT ON INDEX idx_attribution_allocations_tenant_event_model_channel IS 
    'Unique index ensuring idempotency per (tenant_id, event_id, model_version, channel). Purpose: Prevent duplicate allocations for the same event/model/channel combination. Supports sum-equality validation.';

COMMENT ON INDEX idx_attribution_allocations_tenant_model_version IS 
    'Composite index on (tenant_id, model_version). Purpose: Enable fast model rollups and sum-equality validation queries per model version.';

COMMENT ON CONSTRAINT ck_attribution_allocations_revenue_positive ON attribution_allocations IS 
    'Ensures allocated_revenue_cents >= 0. Purpose: Prevent negative allocation values.';

COMMENT ON CONSTRAINT ck_attribution_allocations_allocation_ratio_bounds ON attribution_allocations IS 
    'Ensures allocation_ratio is between 0 and 1 (inclusive). Purpose: Prevent invalid allocation ratios.';

COMMENT ON CONSTRAINT ck_attribution_allocations_channel_code_valid ON attribution_allocations IS 
    'Validates channel code against allowed enum values. Purpose: Enforce channel code consistency. NOTE: Channel codes should be reviewed against contract definitions.';

