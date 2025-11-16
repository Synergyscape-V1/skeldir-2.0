-- ============================================================================
-- CANONICAL SCHEMA SPECIFICATION
-- ============================================================================
-- Source: UPDATED SKELDIR BACKEND ARCHITECTURE GUIDE (§3.1)
-- Purpose: Authoritative schema definition for B0.3+ database foundation
-- Status: Single Source of Truth for all schema validation and migrations
-- Version: 1.0.0
-- Last Updated: 2025-11-15
--
-- This file defines the canonical schema that all implementations must match.
-- All columns are tagged with invariant categories for validation purposes.
-- ============================================================================

-- ============================================================================
-- TABLE: tenants
-- Purpose: Store tenant information for multi-tenant isolation
-- ============================================================================

CREATE TABLE tenants (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Core tenant identity
    name VARCHAR(255) NOT NULL,
    
    -- INVARIANT: auth_critical
    -- Required for API authentication in B0.4
    api_key_hash VARCHAR(255) NOT NULL UNIQUE,
    
    -- INVARIANT: auth_critical
    -- Required for tenant notifications
    notification_email VARCHAR(255) NOT NULL,
    
    -- Audit timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_tenants_name ON tenants (name);
CREATE UNIQUE INDEX idx_tenants_api_key_hash ON tenants (api_key_hash);

-- Constraints
ALTER TABLE tenants 
    ADD CONSTRAINT ck_tenants_name_not_empty 
    CHECK (LENGTH(TRIM(name)) > 0);

-- RLS Policy
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON tenants
    USING (id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (id = current_setting('app.current_tenant_id')::UUID);

-- ============================================================================
-- TABLE: attribution_events
-- Purpose: Store attribution events for revenue tracking and attribution
-- ============================================================================

CREATE TABLE attribution_events (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- INVARIANT: privacy_critical
    -- Tenant isolation (CASCADE delete for GDPR compliance)
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- INVARIANT: privacy_critical
    -- Session tracking (required for attribution logic)
    session_id UUID NOT NULL,
    
    -- INVARIANT: processing_critical
    -- Single-column idempotency key (replaces composite external_event_id/correlation_id)
    idempotency_key VARCHAR(255) NOT NULL UNIQUE,
    
    -- INVARIANT: processing_critical
    -- Event classification: 'click', 'impression', 'purchase'
    event_type VARCHAR(50) NOT NULL,
    
    -- INVARIANT: processing_critical
    -- Normalized channel taxonomy: 'google_search', 'facebook_ads', etc.
    channel VARCHAR(100) NOT NULL,
    
    -- INVARIANT: analytics_important
    -- Campaign tracking (nullable)
    campaign_id VARCHAR(255),
    
    -- INVARIANT: financial_critical
    -- Revenue amount in cents (nullable for non-conversion events)
    conversion_value_cents INTEGER,
    
    -- INVARIANT: financial_critical
    -- Currency code (defaults to USD)
    currency VARCHAR(3) DEFAULT 'USD',
    
    -- INVARIANT: processing_critical
    -- Authoritative event timestamp (when event occurred)
    event_timestamp TIMESTAMPTZ NOT NULL,
    
    -- INVARIANT: processing_critical
    -- Processing timestamp (when event was processed)
    processed_at TIMESTAMPTZ DEFAULT now(),
    
    -- INVARIANT: processing_critical
    -- Processing status for background worker queue
    processing_status VARCHAR(20) DEFAULT 'pending',
    
    -- INVARIANT: processing_critical
    -- Retry tracking
    retry_count INTEGER DEFAULT 0,
    
    -- Raw payload (PII stripped before persistence)
    raw_payload JSONB NOT NULL,
    
    -- Audit timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_events_tenant_timestamp 
    ON attribution_events (tenant_id, event_timestamp DESC);

CREATE INDEX idx_events_processing_status 
    ON attribution_events (processing_status, processed_at) 
    WHERE processing_status = 'pending';

CREATE UNIQUE INDEX idx_events_idempotency 
    ON attribution_events (idempotency_key);

CREATE INDEX idx_events_session_id 
    ON attribution_events (session_id) 
    WHERE session_id IS NOT NULL;

-- Constraints
ALTER TABLE attribution_events 
    ADD CONSTRAINT ck_attribution_events_revenue_positive 
    CHECK (conversion_value_cents IS NULL OR conversion_value_cents >= 0);

ALTER TABLE attribution_events 
    ADD CONSTRAINT ck_attribution_events_processing_status_valid 
    CHECK (processing_status IN ('pending', 'processed', 'failed'));

-- RLS Policy
ALTER TABLE attribution_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE attribution_events FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON attribution_events
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- ============================================================================
-- TABLE: attribution_allocations
-- Purpose: Store attribution model results (channel credit assignments)
-- ============================================================================

CREATE TABLE attribution_allocations (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- INVARIANT: privacy_critical
    -- Tenant isolation
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Event reference (nullable for aggregate allocations)
    event_id UUID REFERENCES attribution_events(id) ON DELETE SET NULL,
    
    -- INVARIANT: analytics_important
    -- Model identification
    model_type VARCHAR(50) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    
    -- INVARIANT: processing_critical
    -- Channel receiving credit
    channel VARCHAR(100) NOT NULL,
    
    -- INVARIANT: financial_critical
    -- Revenue allocated to this channel
    allocated_revenue_cents INTEGER NOT NULL,
    
    -- INVARIANT: analytics_important
    -- Statistical confidence (0.0 to 1.0)
    confidence_score NUMERIC(4,3) NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    
    -- INVARIANT: analytics_important
    -- Bayesian credible interval bounds
    credible_interval_lower_cents INTEGER,
    credible_interval_upper_cents INTEGER,
    
    -- INVARIANT: analytics_important
    -- MCMC convergence diagnostic (Gelman-Rubin statistic)
    convergence_r_hat NUMERIC(5,4),
    
    -- INVARIANT: analytics_important
    -- Effective sample size for MCMC
    effective_sample_size INTEGER,
    
    -- INVARIANT: analytics_important
    -- Verification tracking
    verified BOOLEAN DEFAULT FALSE,
    verification_source VARCHAR(50),
    verification_timestamp TIMESTAMPTZ,
    
    -- Audit timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_allocations_tenant_created_at 
    ON attribution_allocations (tenant_id, created_at DESC);

CREATE INDEX idx_allocations_event_id 
    ON attribution_allocations (event_id);

CREATE INDEX idx_allocations_channel_performance 
    ON attribution_allocations (tenant_id, channel, created_at DESC) 
    INCLUDE (allocated_revenue_cents, confidence_score);

-- Constraints
ALTER TABLE attribution_allocations 
    ADD CONSTRAINT ck_allocations_revenue_positive 
    CHECK (allocated_revenue_cents >= 0);

-- RLS Policy
ALTER TABLE attribution_allocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE attribution_allocations FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON attribution_allocations
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- ============================================================================
-- TABLE: revenue_ledger
-- Purpose: Transaction-centric revenue tracking with state machine
-- ============================================================================

CREATE TABLE revenue_ledger (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- INVARIANT: privacy_critical
    -- Tenant isolation
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- INVARIANT: financial_critical
    -- Transaction identity and idempotency (unique per processor)
    transaction_id VARCHAR(255) NOT NULL UNIQUE,
    
    -- INVARIANT: financial_critical
    -- Order reference (nullable)
    order_id VARCHAR(255),
    
    -- INVARIANT: financial_critical
    -- State machine: 'authorized', 'captured', 'refunded', 'chargeback'
    state VARCHAR(50) NOT NULL,
    
    -- INVARIANT: financial_critical
    -- Previous state for audit trail
    previous_state VARCHAR(50),
    
    -- INVARIANT: financial_critical
    -- Transaction amount in cents
    amount_cents INTEGER NOT NULL,
    
    -- INVARIANT: financial_critical
    -- ISO currency code (USD, EUR, GBP, etc.)
    currency VARCHAR(3) NOT NULL,
    
    -- INVARIANT: financial_critical
    -- Verification metadata (required for all entries)
    verification_source VARCHAR(50) NOT NULL,
    verification_timestamp TIMESTAMPTZ NOT NULL,
    
    -- Extended metadata (JSONB for FX rates, processor details, etc.)
    metadata JSONB,
    
    -- Audit timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE UNIQUE INDEX idx_revenue_ledger_transaction_id 
    ON revenue_ledger (transaction_id);

CREATE INDEX idx_revenue_ledger_tenant_created_at 
    ON revenue_ledger (tenant_id, created_at DESC);

CREATE INDEX idx_revenue_ledger_state 
    ON revenue_ledger (state);

-- Constraints
ALTER TABLE revenue_ledger 
    ADD CONSTRAINT ck_revenue_ledger_amount_positive 
    CHECK (amount_cents >= 0);

ALTER TABLE revenue_ledger 
    ADD CONSTRAINT ck_revenue_ledger_state_valid 
    CHECK (state IN ('authorized', 'captured', 'refunded', 'chargeback'));

-- RLS Policy
ALTER TABLE revenue_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE revenue_ledger FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON revenue_ledger
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- ============================================================================
-- TABLE: revenue_state_transitions
-- Purpose: Audit trail for revenue state changes (refunds, chargebacks)
-- ============================================================================

CREATE TABLE revenue_state_transitions (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- INVARIANT: financial_critical
    -- Reference to ledger entry
    ledger_id UUID NOT NULL REFERENCES revenue_ledger(id) ON DELETE CASCADE,
    
    -- INVARIANT: financial_critical
    -- State transition tracking
    from_state VARCHAR(50),
    to_state VARCHAR(50) NOT NULL,
    
    -- Audit information
    reason TEXT,
    transitioned_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_revenue_transitions_ledger_id 
    ON revenue_state_transitions (ledger_id, transitioned_at DESC);

-- ============================================================================
-- TABLE: dead_events
-- Purpose: Quarantine failed events with retry tracking
-- ============================================================================

CREATE TABLE dead_events (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- INVARIANT: privacy_critical
    -- Tenant isolation
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- INVARIANT: processing_critical
    -- Event classification
    event_type VARCHAR(50) NOT NULL,
    
    -- Raw payload (preserved for analysis)
    raw_payload JSONB NOT NULL,
    
    -- INVARIANT: processing_critical
    -- Error classification
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    error_traceback TEXT,
    
    -- INVARIANT: processing_critical
    -- Retry tracking for background remediation
    retry_count INTEGER DEFAULT 0,
    last_retry_at TIMESTAMPTZ,
    
    -- INVARIANT: processing_critical
    -- Remediation workflow: 'pending', 'in_progress', 'resolved', 'abandoned'
    remediation_status VARCHAR(20) DEFAULT 'pending',
    remediation_notes TEXT,
    
    -- Audit timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_dead_events_tenant_created_at 
    ON dead_events (tenant_id, created_at DESC);

CREATE INDEX idx_dead_events_error_type 
    ON dead_events (error_type);

CREATE INDEX idx_dead_events_remediation 
    ON dead_events (remediation_status, created_at DESC);

-- Constraints
ALTER TABLE dead_events 
    ADD CONSTRAINT ck_dead_events_remediation_status_valid 
    CHECK (remediation_status IN ('pending', 'in_progress', 'resolved', 'abandoned'));

-- RLS Policy
ALTER TABLE dead_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE dead_events FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON dead_events
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- ============================================================================
-- END CANONICAL SCHEMA SPECIFICATION
-- ============================================================================



