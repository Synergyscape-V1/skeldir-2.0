-- DDL Specification for tenants table
-- Purpose: Store tenant information for multi-tenant isolation
-- Data Class: Non-PII
-- Ownership: Backend service
-- Contract Mapping: Referenced by all tenant-scoped tables via tenant_id FK

CREATE TABLE tenants (
    -- Primary key: id uuid with gen_random_uuid() (Style Guide)
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Tenant name (required for identification)
    name VARCHAR(255) NOT NULL,
    
    -- Timestamp trio: created_at, updated_at (Style Guide)
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Check constraint with naming: ck_{table}_{column}_{condition} (Style Guide)
ALTER TABLE tenants 
    ADD CONSTRAINT ck_tenants_name_not_empty 
    CHECK (LENGTH(TRIM(name)) > 0);

-- Index with naming: idx_{table}_{columns} (Style Guide)
CREATE INDEX idx_tenants_name 
    ON tenants (name);

-- Comments on all objects (Style Guide, Lint Rules)
COMMENT ON TABLE tenants IS 
    'Stores tenant information for multi-tenant isolation. Purpose: Tenant identity and management. Data class: Non-PII. Ownership: Backend service. RLS enabled for tenant isolation.';

COMMENT ON COLUMN tenants.id IS 
    'Primary key UUID. Purpose: Unique tenant identifier. Data class: Non-PII.';

COMMENT ON COLUMN tenants.name IS 
    'Tenant name. Purpose: Human-readable tenant identification. Data class: Non-PII.';

COMMENT ON COLUMN tenants.created_at IS 
    'Record creation timestamp. Purpose: Audit trail. Data class: Non-PII.';

COMMENT ON COLUMN tenants.updated_at IS 
    'Record update timestamp. Purpose: Audit trail. Data class: Non-PII.';

COMMENT ON INDEX idx_tenants_name IS 
    'Index on tenant name. Purpose: Enable fast tenant lookup by name.';

COMMENT ON CONSTRAINT ck_tenants_name_not_empty ON tenants IS 
    'Ensures tenant name is not empty. Purpose: Prevent invalid tenant names.';




