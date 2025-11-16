-- ILLUSTRATIVE ONLY - NOT APPLIED
-- This example demonstrates comment standards for all object types

-- Table comment: Purpose, Data Class, Ownership
COMMENT ON TABLE attribution_events IS 
    'Stores attribution events for revenue tracking. Purpose: Event ingestion and attribution calculations. Data class: Non-PII. Ownership: Attribution service.';

-- Column comments: Purpose, Data Class
COMMENT ON COLUMN attribution_events.id IS 
    'Primary key UUID. Purpose: Unique identifier. Data class: Non-PII.';

COMMENT ON COLUMN attribution_events.tenant_id IS 
    'Foreign key to tenants table. Purpose: Tenant isolation. Data class: Non-PII.';

COMMENT ON COLUMN attribution_events.revenue_cents IS 
    'Revenue amount in cents (INTEGER). Purpose: Store revenue for attribution calculations. Data class: Non-PII.';

COMMENT ON COLUMN attribution_events.correlation_id IS 
    'Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing. Data class: Non-PII.';

COMMENT ON COLUMN attribution_events.actor_service_name IS 
    'Service that processed this event. Purpose: Audit trail. Data class: Non-PII.';

-- Index comment: Purpose
COMMENT ON INDEX idx_attribution_events_tenant_timestamp IS 
    'Composite index on (tenant_id, event_timestamp DESC). Purpose: Optimize time-series queries by tenant.';

-- Check constraint comment: Purpose
COMMENT ON CONSTRAINT ck_attribution_events_revenue_positive ON attribution_events IS 
    'Ensures revenue_cents >= 0. Purpose: Prevent negative revenue values.';

-- RLS policy comment: Purpose
COMMENT ON POLICY tenant_isolation_policy ON attribution_events IS 
    'RLS policy enforcing tenant isolation. Purpose: Prevent cross-tenant data access. Requires app.current_tenant_id to be set via set_config().';

-- Foreign key comment: Purpose (optional, but recommended)
-- Note: PostgreSQL doesn't support COMMENT ON FOREIGN KEY directly
-- Document FK purpose in table/column comments instead





