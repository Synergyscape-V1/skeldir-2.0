-- DDL Specification for revenue_ledger table
-- Purpose: Store verified revenue aggregates for reconciliation
-- Data Class: Non-PII
-- Ownership: Reconciliation service
-- Contract Mapping: Supports RealtimeRevenueResponse (total_revenue, verified, data_freshness_seconds)

CREATE TABLE revenue_ledger (
    -- Primary key: id uuid with gen_random_uuid() (Style Guide)
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign key: tenant_id (Style Guide, Contract Mapping)
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Timestamp trio: created_at, updated_at (Style Guide)
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    
    -- Revenue in cents: INTEGER (not DECIMAL or FLOAT) (Style Guide)
    -- Contract mapping: total_revenue (number float) → revenue_cents (integer)
    revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK (revenue_cents >= 0),
    
    -- Verified flag: boolean (Style Guide)
    -- Contract mapping: verified (boolean) → is_verified (boolean)
    is_verified boolean NOT NULL DEFAULT false,
    
    -- Last verification timestamp
    verified_at timestamptz,
    
    -- Reconciliation run reference (nullable, links to reconciliation_runs)
    reconciliation_run_id uuid,
    
    -- Allocation reference (nullable, links to attribution_allocations) - Phase 4C requirement
    allocation_id uuid REFERENCES attribution_allocations(id) ON DELETE CASCADE,
    
    -- Posted timestamp - Phase 4C requirement
    posted_at timestamptz NOT NULL DEFAULT now()
);

-- Time-series index: (tenant_id, updated_at DESC) (Style Guide, Lint Rules)
CREATE INDEX idx_revenue_ledger_tenant_updated_at 
    ON revenue_ledger (tenant_id, updated_at DESC);

-- Index on is_verified for verified revenue queries
CREATE INDEX idx_revenue_ledger_is_verified 
    ON revenue_ledger (is_verified) 
    WHERE is_verified = true;

-- Idempotency unique index: (tenant_id, allocation_id) where allocation_id IS NOT NULL - Phase 4C requirement
CREATE UNIQUE INDEX idx_revenue_ledger_tenant_allocation_id
    ON revenue_ledger (tenant_id, allocation_id)
    WHERE allocation_id IS NOT NULL;

-- Check constraint with naming: ck_{table}_{column}_{condition} (Style Guide)
ALTER TABLE revenue_ledger 
    ADD CONSTRAINT ck_revenue_ledger_revenue_positive 
    CHECK (revenue_cents >= 0);

-- Comments on all objects (Style Guide, Lint Rules)
COMMENT ON TABLE revenue_ledger IS 
    'Stores verified revenue aggregates for reconciliation. Purpose: Revenue verification and aggregation. Data class: Non-PII. Ownership: Reconciliation service. RLS enabled for tenant isolation.';

COMMENT ON COLUMN revenue_ledger.id IS 
    'Primary key UUID. Purpose: Unique ledger entry identifier. Data class: Non-PII.';

COMMENT ON COLUMN revenue_ledger.tenant_id IS 
    'Foreign key to tenants table. Purpose: Tenant isolation. Data class: Non-PII.';

COMMENT ON COLUMN revenue_ledger.created_at IS 
    'Record creation timestamp. Purpose: Audit trail. Data class: Non-PII.';

COMMENT ON COLUMN revenue_ledger.updated_at IS 
    'Record update timestamp. Purpose: Audit trail. Data class: Non-PII.';

COMMENT ON COLUMN revenue_ledger.revenue_cents IS 
    'Revenue amount in cents (INTEGER). Purpose: Store verified revenue aggregate. Contract mapping: total_revenue (number float) → revenue_cents (integer). Data class: Non-PII.';

COMMENT ON COLUMN revenue_ledger.is_verified IS 
    'Whether revenue has been verified through reconciliation pipeline. Purpose: Reconciliation status. Contract mapping: verified (boolean) → is_verified (boolean). Data class: Non-PII.';

COMMENT ON COLUMN revenue_ledger.verified_at IS 
    'Timestamp when revenue was verified. Purpose: Verification time tracking. Data class: Non-PII.';

COMMENT ON COLUMN revenue_ledger.reconciliation_run_id IS 
    'Reference to reconciliation run that verified this revenue. Purpose: Link to reconciliation_runs table. Data class: Non-PII.';

COMMENT ON COLUMN revenue_ledger.allocation_id IS 
    'Foreign key to attribution_allocations table (nullable). Purpose: Link ledger entry to specific allocation for allocation-based posting. Supports both allocation-based (allocation_id set) and run-based (reconciliation_run_id set) posting patterns. Data class: Non-PII.';

COMMENT ON COLUMN revenue_ledger.posted_at IS 
    'Timestamp when revenue was posted to the ledger. Purpose: Track posting time for audit trail and reconciliation. Data class: Non-PII.';

COMMENT ON INDEX idx_revenue_ledger_tenant_updated_at IS 
    'Composite index on (tenant_id, updated_at DESC). Purpose: Optimize time-series queries by tenant.';

COMMENT ON INDEX idx_revenue_ledger_is_verified IS 
    'Partial index on is_verified WHERE is_verified = true. Purpose: Enable fast queries for verified revenue.';

COMMENT ON INDEX idx_revenue_ledger_tenant_allocation_id IS 
    'Unique index on (tenant_id, allocation_id) where allocation_id IS NOT NULL. Purpose: Prevent duplicate ledger entries for the same allocation, ensuring idempotent allocation-based posting. Data class: Non-PII.';

COMMENT ON CONSTRAINT ck_revenue_ledger_revenue_positive ON revenue_ledger IS 
    'Ensures revenue_cents >= 0. Purpose: Prevent negative revenue values.';

