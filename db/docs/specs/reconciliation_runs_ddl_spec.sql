-- DDL Specification for reconciliation_runs table
-- Purpose: Store reconciliation pipeline run status and metadata
-- Data Class: Non-PII
-- Ownership: Reconciliation service
-- Contract Mapping: Supports ReconciliationStatusResponse (state, last_run_at, tenant_id)

CREATE TABLE reconciliation_runs (
    -- Primary key: id uuid with gen_random_uuid() (Style Guide)
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign key: tenant_id (Style Guide, Contract Mapping)
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Timestamp trio: created_at, updated_at, and domain-specific timestamp (Style Guide)
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    last_run_at timestamptz NOT NULL,
    
    -- State enum: CHECK constraint for small stable enum (Contract Mapping)
    -- Contract mapping: state enum (idle|running|failed|completed) → state VARCHAR(20) CHECK
    state VARCHAR(20) NOT NULL DEFAULT 'idle' 
        CHECK (state IN ('idle', 'running', 'failed', 'completed')),
    
    -- Error message if state is 'failed' (nullable)
    error_message text,
    
    -- Run metadata (JSONB for structured run information)
    run_metadata jsonb
);

-- Time-series index: (tenant_id, last_run_at DESC) (Style Guide, Lint Rules)
CREATE INDEX idx_reconciliation_runs_tenant_last_run_at 
    ON reconciliation_runs (tenant_id, last_run_at DESC);

-- Index on state for status queries
CREATE INDEX idx_reconciliation_runs_state 
    ON reconciliation_runs (state);

-- Check constraint with naming: ck_{table}_{column}_{condition} (Style Guide)
ALTER TABLE reconciliation_runs 
    ADD CONSTRAINT ck_reconciliation_runs_state_valid 
    CHECK (state IN ('idle', 'running', 'failed', 'completed'));

-- Comments on all objects (Style Guide, Lint Rules)
COMMENT ON TABLE reconciliation_runs IS 
    'Stores reconciliation pipeline run status and metadata. Purpose: Track reconciliation pipeline execution. Data class: Non-PII. Ownership: Reconciliation service. RLS enabled for tenant isolation.';

COMMENT ON COLUMN reconciliation_runs.id IS 
    'Primary key UUID. Purpose: Unique reconciliation run identifier. Data class: Non-PII.';

COMMENT ON COLUMN reconciliation_runs.tenant_id IS 
    'Foreign key to tenants table. Purpose: Tenant isolation. Data class: Non-PII.';

COMMENT ON COLUMN reconciliation_runs.created_at IS 
    'Record creation timestamp. Purpose: Audit trail. Data class: Non-PII.';

COMMENT ON COLUMN reconciliation_runs.updated_at IS 
    'Record update timestamp. Purpose: Audit trail. Data class: Non-PII.';

COMMENT ON COLUMN reconciliation_runs.last_run_at IS 
    'Timestamp of the last reconciliation run. Purpose: Track last execution time. Contract mapping: last_run_at (string date-time) → last_run_at (timestamptz). Data class: Non-PII.';

COMMENT ON COLUMN reconciliation_runs.state IS 
    'Current state of the reconciliation pipeline. Purpose: Track pipeline status. Contract mapping: state enum (idle|running|failed|completed) → state VARCHAR(20) CHECK. Data class: Non-PII.';

COMMENT ON COLUMN reconciliation_runs.error_message IS 
    'Error message if state is failed. Purpose: Store failure details. Data class: Non-PII.';

COMMENT ON COLUMN reconciliation_runs.run_metadata IS 
    'Structured run information (JSONB). Purpose: Store run-specific metadata. Data class: Non-PII.';

COMMENT ON INDEX idx_reconciliation_runs_tenant_last_run_at IS 
    'Composite index on (tenant_id, last_run_at DESC). Purpose: Optimize status queries by tenant. Supports GET /api/reconciliation/status?tenant_id=X.';

COMMENT ON INDEX idx_reconciliation_runs_state IS 
    'Index on state. Purpose: Enable fast filtering by pipeline state.';

COMMENT ON CONSTRAINT ck_reconciliation_runs_state_valid ON reconciliation_runs IS 
    'Ensures state is one of: idle, running, failed, completed. Purpose: Enforce valid state values.';




