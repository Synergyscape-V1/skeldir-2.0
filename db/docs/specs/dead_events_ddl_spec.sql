-- DDL Specification for dead_events table
-- Purpose: Dead-letter queue for invalid/unparseable webhook payloads
-- Data Class: Non-PII (PII stripped from raw_payload before persistence)
-- Ownership: Ingestion service
-- Contract Mapping: Supports error handling for webhook ingestion failures

CREATE TABLE dead_events (
    -- Primary key: id uuid with gen_random_uuid() (Style Guide)
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign key: tenant_id (Style Guide, Contract Mapping)
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Timestamp: ingested_at (when failure occurred)
    ingested_at timestamptz NOT NULL DEFAULT now(),
    
    -- Source system identifier
    source text NOT NULL,
    
    -- Error classification
    error_code text NOT NULL,
    
    -- Error details (JSONB for structured error information)
    error_detail jsonb NOT NULL,
    
    -- Raw payload that failed (JSONB)
    -- PII stripped before persistence per PRIVACY-NOTES.md
    raw_payload jsonb NOT NULL,
    
    -- Correlation ID for distributed tracing (nullable)
    correlation_id uuid,
    
    -- External event ID when known (nullable)
    external_event_id text
);

-- Time-series index: (tenant_id, ingested_at DESC) (Style Guide, Lint Rules)
CREATE INDEX idx_dead_events_tenant_ingested_at 
    ON dead_events (tenant_id, ingested_at DESC);

-- Index on source for operator triage
CREATE INDEX idx_dead_events_source 
    ON dead_events (source);

-- Index on error_code for error analysis
CREATE INDEX idx_dead_events_error_code 
    ON dead_events (error_code);

-- Comments on all objects (Style Guide, Lint Rules)
COMMENT ON TABLE dead_events IS 
    'Dead-letter queue for invalid/unparseable webhook payloads. Purpose: Store failed ingestion attempts for operator triage. Data class: Non-PII (PII stripped from raw_payload). Ownership: Ingestion service. RLS enabled for tenant isolation.';

COMMENT ON COLUMN dead_events.id IS 
    'Primary key UUID. Purpose: Unique dead event identifier. Data class: Non-PII.';

COMMENT ON COLUMN dead_events.tenant_id IS 
    'Foreign key to tenants table. Purpose: Tenant isolation. Data class: Non-PII.';

COMMENT ON COLUMN dead_events.ingested_at IS 
    'Timestamp when failure occurred. Purpose: Failure time tracking. Data class: Non-PII.';

COMMENT ON COLUMN dead_events.source IS 
    'Source system identifier (e.g., shopify, stripe, paypal, woocommerce). Purpose: Identify source of failed payload. Data class: Non-PII.';

COMMENT ON COLUMN dead_events.error_code IS 
    'Error classification code. Purpose: Categorize failure types. Data class: Non-PII.';

COMMENT ON COLUMN dead_events.error_detail IS 
    'Structured error information (JSONB). Purpose: Store detailed error context for debugging. Data class: Non-PII.';

COMMENT ON COLUMN dead_events.raw_payload IS 
    'Raw webhook payload that failed (JSONB). Purpose: Store original payload for analysis. Data class: Non-PII (PII stripped before persistence per PRIVACY-NOTES.md).';

COMMENT ON COLUMN dead_events.correlation_id IS 
    'Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing and event stitching across tables. Links dead_events, attribution_events, and future attribution_allocations. Data class: Non-PII.';

COMMENT ON COLUMN dead_events.external_event_id IS 
    'External event ID when known (e.g., Shopify order ID). Purpose: Link to source system event. Data class: Non-PII.';

COMMENT ON INDEX idx_dead_events_tenant_ingested_at IS 
    'Composite index on (tenant_id, ingested_at DESC). Purpose: Optimize operator triage queries by tenant and time.';

COMMENT ON INDEX idx_dead_events_source IS 
    'Index on source. Purpose: Enable fast filtering by source system.';

COMMENT ON INDEX idx_dead_events_error_code IS 
    'Index on error_code. Purpose: Enable fast error analysis queries.';




