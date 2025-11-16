-- DDL Specification for attribution_events table
-- Purpose: Store attribution events for revenue tracking and attribution calculations
-- Data Class: Non-PII (PII stripped from raw_payload before persistence)
-- Ownership: Attribution service
-- Contract Mapping: Supports webhook ingestion endpoints and attribution calculations

CREATE TABLE attribution_events (
    -- Primary key: id uuid with gen_random_uuid() (Style Guide)
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign key: tenant_id (Style Guide, Contract Mapping)
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Timestamp trio: created_at, updated_at, and domain-specific timestamp (Style Guide)
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    occurred_at timestamptz NOT NULL,
    
    -- External event ID for idempotency (nullable if source lacks it)
    external_event_id text,
    
    -- Correlation ID for distributed tracing (nullable but recommended)
    correlation_id uuid,
    
    -- Session ID for session-scoped events (nullable; future join)
    session_id uuid,
    
    -- Revenue in cents: INTEGER (not DECIMAL or FLOAT) (Style Guide, Contract Mapping)
    -- Contract mapping: total_revenue (number float) → revenue_cents (integer)
    revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK (revenue_cents >= 0),
    
    -- Raw payload: JSONB (Style Guide)
    -- PII stripped before persistence per PRIVACY-NOTES.md
    raw_payload jsonb NOT NULL
);

-- Idempotency constraints: UNIQUE on (tenant_id, external_event_id) or (tenant_id, correlation_id)
-- Strategy: Use external_event_id when available (Shopify, PayPal, WooCommerce), correlation_id as fallback (Stripe)
CREATE UNIQUE INDEX idx_attribution_events_tenant_external_event_id 
    ON attribution_events (tenant_id, external_event_id) 
    WHERE external_event_id IS NOT NULL;

CREATE UNIQUE INDEX idx_attribution_events_tenant_correlation_id 
    ON attribution_events (tenant_id, correlation_id) 
    WHERE correlation_id IS NOT NULL AND external_event_id IS NULL;

-- Time-series index: (tenant_id, occurred_at DESC) (Style Guide, Lint Rules)
CREATE INDEX idx_attribution_events_tenant_occurred_at 
    ON attribution_events (tenant_id, occurred_at DESC);

-- Index on session_id for session-scoped queries
CREATE INDEX idx_attribution_events_session_id 
    ON attribution_events (session_id) 
    WHERE session_id IS NOT NULL;

-- Check constraint with naming: ck_{table}_{column}_{condition} (Style Guide)
ALTER TABLE attribution_events 
    ADD CONSTRAINT ck_attribution_events_revenue_positive 
    CHECK (revenue_cents >= 0);

-- Comments on all objects (Style Guide, Lint Rules)
COMMENT ON TABLE attribution_events IS 
    'Stores attribution events for revenue tracking. Purpose: Event ingestion and attribution calculations. Data class: Non-PII (PII stripped from raw_payload). Ownership: Attribution service. RLS enabled for tenant isolation.';

COMMENT ON COLUMN attribution_events.id IS 
    'Primary key UUID. Purpose: Unique event identifier. Data class: Non-PII.';

COMMENT ON COLUMN attribution_events.tenant_id IS 
    'Foreign key to tenants table. Purpose: Tenant isolation. Data class: Non-PII.';

COMMENT ON COLUMN attribution_events.created_at IS 
    'Record creation timestamp. Purpose: Audit trail. Data class: Non-PII.';

COMMENT ON COLUMN attribution_events.updated_at IS 
    'Record update timestamp. Purpose: Audit trail. Data class: Non-PII.';

COMMENT ON COLUMN attribution_events.occurred_at IS 
    'Domain-specific event timestamp (when event occurred). Purpose: Business logic timestamping. Data class: Non-PII.';

COMMENT ON COLUMN attribution_events.external_event_id IS 
    'External event ID from source system (e.g., Shopify order ID, PayPal transaction ID). Purpose: Idempotency key. Data class: Non-PII.';

COMMENT ON COLUMN attribution_events.correlation_id IS 
    'Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing and event stitching across tables. Links attribution_events, dead_events, and future attribution_allocations. Data class: Non-PII.';

COMMENT ON COLUMN attribution_events.session_id IS 
    'Session identifier for session-scoped events (30-minute inactivity timeout). Purpose: Session grouping. Data class: Non-PII.';

COMMENT ON COLUMN attribution_events.revenue_cents IS 
    'Revenue amount in cents (INTEGER). Purpose: Store revenue for attribution calculations. Contract mapping: total_revenue (number float) → revenue_cents (integer). Data class: Non-PII.';

COMMENT ON COLUMN attribution_events.raw_payload IS 
    'Raw webhook payload (JSONB). Purpose: Store original event data. Data class: Non-PII (PII stripped before persistence per PRIVACY-NOTES.md).';

COMMENT ON INDEX idx_attribution_events_tenant_external_event_id IS 
    'Unique index on (tenant_id, external_event_id) for idempotency. Purpose: Prevent duplicate ingestion when external_event_id is available.';

COMMENT ON INDEX idx_attribution_events_tenant_correlation_id IS 
    'Unique index on (tenant_id, correlation_id) for idempotency fallback. Purpose: Prevent duplicate ingestion when external_event_id is not available.';

COMMENT ON INDEX idx_attribution_events_tenant_occurred_at IS 
    'Composite index on (tenant_id, occurred_at DESC). Purpose: Optimize time-series queries by tenant.';

COMMENT ON INDEX idx_attribution_events_session_id IS 
    'Index on session_id. Purpose: Enable fast session-scoped queries.';

COMMENT ON CONSTRAINT ck_attribution_events_revenue_positive ON attribution_events IS 
    'Ensures revenue_cents >= 0. Purpose: Prevent negative revenue values.';




