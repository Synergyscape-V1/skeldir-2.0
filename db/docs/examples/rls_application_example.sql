-- ILLUSTRATIVE ONLY - NOT APPLIED
-- This example demonstrates RLS policy application with roles and GRANTs

-- Step 1: Create table with tenant_id
CREATE TABLE example_attribution_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    event_timestamp timestamptz NOT NULL,
    revenue_cents INTEGER NOT NULL CHECK (revenue_cents >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Step 2: Create roles (if not exists) - repeatable migration pattern
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

-- Step 3: Grant permissions to roles
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE example_attribution_events TO app_rw;
GRANT SELECT ON TABLE example_attribution_events TO app_ro;

-- Step 4: Enable RLS on table
ALTER TABLE example_attribution_events ENABLE ROW LEVEL SECURITY;

-- Step 5: Create tenant isolation policy
CREATE POLICY tenant_isolation_policy ON example_attribution_events
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Step 6: Add comment documenting RLS policy
COMMENT ON POLICY tenant_isolation_policy ON example_attribution_events IS 
    'RLS policy enforcing tenant isolation. Purpose: Prevent cross-tenant data access. 
    Requires app.current_tenant_id to be set via set_config().';

-- Usage Example:
-- Application must set tenant context before queries:
--   SET LOCAL app.current_tenant_id = '550e8400-e29b-41d4-a716-446655440000'::text;
--
-- All subsequent queries are automatically filtered to the current tenant:
--   SELECT * FROM example_attribution_events;  -- Only returns rows for current tenant
--   INSERT INTO example_attribution_events (...) VALUES (...);  -- Automatically sets tenant_id from context





