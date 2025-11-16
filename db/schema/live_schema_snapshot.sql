-- ============================================================================
-- LIVE SCHEMA SNAPSHOT
-- ============================================================================
-- Purpose: Current implemented schema as of 2025-11-15
-- Source: Alembic migrations through 202511141311_allocations_channel_fk_to_taxonomy
-- Method: Reconstructed from migration analysis (B0.3_FORENSIC_ANALYSIS_RESPONSE.md)
-- Status: Represents actual implemented state before corrective migrations
-- ============================================================================

-- ============================================================================
-- TABLE: tenants (CURRENT STATE)
-- ============================================================================

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Constraints
ALTER TABLE tenants 
    ADD CONSTRAINT ck_tenants_name_not_empty 
    CHECK (LENGTH(TRIM(name)) > 0);

-- Indexes
CREATE INDEX idx_tenants_name ON tenants (name);

-- RLS
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON tenants
    USING (id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (id = current_setting('app.current_tenant_id')::UUID);

-- ============================================================================
-- TABLE: attribution_events (CURRENT STATE)
-- ============================================================================

CREATE TABLE attribution_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    occurred_at TIMESTAMPTZ NOT NULL,
    external_event_id TEXT,
    correlation_id UUID,
    session_id UUID,  -- NOTE: Currently NULLABLE (should be NOT NULL per canonical)
    revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK (revenue_cents >= 0),
    raw_payload JSONB NOT NULL
);

-- Constraints
ALTER TABLE attribution_events 
    ADD CONSTRAINT ck_attribution_events_revenue_positive 
    CHECK (revenue_cents >= 0);

-- Idempotency indexes (composite, different from canonical)
CREATE UNIQUE INDEX idx_attribution_events_tenant_external_event_id 
    ON attribution_events (tenant_id, external_event_id) 
    WHERE external_event_id IS NOT NULL;

CREATE UNIQUE INDEX idx_attribution_events_tenant_correlation_id 
    ON attribution_events (tenant_id, correlation_id) 
    WHERE correlation_id IS NOT NULL AND external_event_id IS NULL;

-- Performance indexes
CREATE INDEX idx_attribution_events_tenant_occurred_at 
    ON attribution_events (tenant_id, occurred_at DESC);

CREATE INDEX idx_attribution_events_session_id 
    ON attribution_events (session_id) 
    WHERE session_id IS NOT NULL;

-- RLS
ALTER TABLE attribution_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE attribution_events FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON attribution_events
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- ============================================================================
-- TABLE: attribution_allocations (CURRENT STATE)
-- ============================================================================

CREATE TABLE attribution_allocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES attribution_events(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    channel_code TEXT NOT NULL,  -- NOTE: Was 'channel', renamed in migration 202511141311
    allocated_revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK (allocated_revenue_cents >= 0),
    model_metadata JSONB,
    correlation_id UUID,
    -- Added in migration 202511131232:
    allocation_ratio NUMERIC(6,5) NOT NULL DEFAULT 0.0,
    model_version TEXT NOT NULL DEFAULT 'unknown'
);

-- Constraints
ALTER TABLE attribution_allocations 
    ADD CONSTRAINT ck_attribution_allocations_revenue_positive 
    CHECK (allocated_revenue_cents >= 0);

ALTER TABLE attribution_allocations
    ADD CONSTRAINT ck_attribution_allocations_allocation_ratio_bounds
    CHECK (allocation_ratio >= 0 AND allocation_ratio <= 1);

ALTER TABLE attribution_allocations
    ADD CONSTRAINT ck_attribution_allocations_channel_code_valid
    CHECK (channel_code IN (
        'google_search', 'facebook_ads', 'direct', 'email', 
        'organic', 'referral', 'social', 'paid_search', 'display'
    ));

-- Foreign key to channel_taxonomy (added in migration 202511141311)
ALTER TABLE attribution_allocations
    ADD CONSTRAINT fk_attribution_allocations_channel_code
    FOREIGN KEY (channel_code) REFERENCES channel_taxonomy(code);

-- Indexes
CREATE INDEX idx_attribution_allocations_tenant_created_at 
    ON attribution_allocations (tenant_id, created_at DESC);

CREATE INDEX idx_attribution_allocations_event_id 
    ON attribution_allocations (event_id);

CREATE INDEX idx_attribution_allocations_channel 
    ON attribution_allocations (channel_code);

CREATE UNIQUE INDEX idx_attribution_allocations_tenant_event_model_channel
    ON attribution_allocations (tenant_id, event_id, model_version, channel_code)
    WHERE model_version IS NOT NULL;

CREATE INDEX idx_attribution_allocations_tenant_model_version
    ON attribution_allocations (tenant_id, model_version);

-- RLS
ALTER TABLE attribution_allocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE attribution_allocations FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON attribution_allocations
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- ============================================================================
-- TABLE: revenue_ledger (CURRENT STATE)
-- ============================================================================

CREATE TABLE revenue_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK (revenue_cents >= 0),
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    reconciliation_run_id UUID,
    -- Added in migration 202511131250:
    allocation_id UUID NOT NULL REFERENCES attribution_allocations(id) ON DELETE CASCADE,  -- Made NOT NULL in 202511141302
    posted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Constraints
ALTER TABLE revenue_ledger 
    ADD CONSTRAINT ck_revenue_ledger_revenue_positive 
    CHECK (revenue_cents >= 0);

-- Indexes
CREATE INDEX idx_revenue_ledger_tenant_updated_at 
    ON revenue_ledger (tenant_id, updated_at DESC);

CREATE INDEX idx_revenue_ledger_is_verified 
    ON revenue_ledger (is_verified) 
    WHERE is_verified = TRUE;

CREATE UNIQUE INDEX idx_revenue_ledger_tenant_allocation_id
    ON revenue_ledger (tenant_id, allocation_id)
    WHERE allocation_id IS NOT NULL;

-- RLS
ALTER TABLE revenue_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE revenue_ledger FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON revenue_ledger
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- ============================================================================
-- TABLE: dead_events (CURRENT STATE)
-- ============================================================================

CREATE TABLE dead_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source TEXT NOT NULL,
    error_code TEXT NOT NULL,
    error_detail JSONB NOT NULL,
    raw_payload JSONB NOT NULL,
    correlation_id UUID,
    external_event_id TEXT
);

-- Indexes
CREATE INDEX idx_dead_events_tenant_ingested_at 
    ON dead_events (tenant_id, ingested_at DESC);

CREATE INDEX idx_dead_events_source 
    ON dead_events (source);

CREATE INDEX idx_dead_events_error_code 
    ON dead_events (error_code);

-- RLS
ALTER TABLE dead_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE dead_events FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON dead_events
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- ============================================================================
-- TABLE: reconciliation_runs (EXTRA TABLE - Not in canonical spec)
-- ============================================================================

CREATE TABLE reconciliation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_run_at TIMESTAMPTZ NOT NULL,
    state VARCHAR(20) NOT NULL DEFAULT 'idle' 
        CHECK (state IN ('idle', 'running', 'failed', 'completed')),
    error_message TEXT,
    run_metadata JSONB
);

-- Indexes
CREATE INDEX idx_reconciliation_runs_tenant_last_run_at 
    ON reconciliation_runs (tenant_id, last_run_at DESC);

CREATE INDEX idx_reconciliation_runs_state 
    ON reconciliation_runs (state);

-- RLS
ALTER TABLE reconciliation_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE reconciliation_runs FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON reconciliation_runs
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- ============================================================================
-- TABLE: channel_taxonomy (Added in migration 202511141310)
-- ============================================================================

CREATE TABLE channel_taxonomy (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    parent_code TEXT REFERENCES channel_taxonomy(code),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_channel_taxonomy_parent_code 
    ON channel_taxonomy (parent_code);

CREATE INDEX idx_channel_taxonomy_is_active 
    ON channel_taxonomy (is_active) 
    WHERE is_active = TRUE;

-- ============================================================================
-- MATERIALIZED VIEWS (CURRENT STATE)
-- ============================================================================

-- NOTE: These exist but with different names than canonical spec expects

CREATE MATERIALIZED VIEW mv_realtime_revenue AS
SELECT 
    rl.tenant_id,
    COALESCE(SUM(rl.revenue_cents), 0) / 100.0 AS total_revenue,
    BOOL_OR(rl.is_verified) AS verified,
    EXTRACT(EPOCH FROM (now() - MAX(rl.updated_at)))::INTEGER AS data_freshness_seconds
FROM revenue_ledger rl
GROUP BY rl.tenant_id;

CREATE UNIQUE INDEX idx_mv_realtime_revenue_tenant_id 
    ON mv_realtime_revenue (tenant_id);

CREATE MATERIALIZED VIEW mv_reconciliation_status AS
SELECT 
    rr.tenant_id,
    rr.state,
    rr.last_run_at,
    rr.id AS reconciliation_run_id
FROM reconciliation_runs rr
INNER JOIN (
    SELECT tenant_id, MAX(last_run_at) AS max_last_run_at
    FROM reconciliation_runs
    GROUP BY tenant_id
) latest ON rr.tenant_id = latest.tenant_id 
    AND rr.last_run_at = latest.max_last_run_at;

CREATE UNIQUE INDEX idx_mv_reconciliation_status_tenant_id 
    ON mv_reconciliation_status (tenant_id);

-- ============================================================================
-- END LIVE SCHEMA SNAPSHOT
-- ============================================================================



