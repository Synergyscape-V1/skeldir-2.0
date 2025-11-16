# DDL Lint Rules

This document defines static analysis rules for database DDL. All migrations must pass these rules before approval.

## Rule 1: Tables Must Have Comments

**Rule**: Forbid tables without comments.

**Severity**: Error (not warning)

**Example - Passing**:
```sql
CREATE TABLE attribution_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ...
);

COMMENT ON TABLE attribution_events IS 'Stores attribution events for revenue tracking. Non-PII data only.';
```

**Example - Failing**:
```sql
CREATE TABLE attribution_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ...
);
-- Missing COMMENT ON TABLE
```

**Enforcement**: Static analysis tool checks for `COMMENT ON TABLE` statements for all `CREATE TABLE` statements.

## Rule 2: Forbid Generic Column Names

**Rule**: Forbid columns named `data`, `misc`, `other`, or `stuff`.

**Severity**: Error

**Rationale**: Generic names indicate unclear schema design and make queries unreadable.

**Example - Passing**:
```sql
CREATE TABLE attribution_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_payload JSONB NOT NULL,  -- Descriptive name
    metadata JSONB,  -- Descriptive name
    ...
);
```

**Example - Failing**:
```sql
CREATE TABLE attribution_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    data JSONB NOT NULL,  -- Too generic
    misc TEXT,  -- Too generic
    ...
);
```

**Enforcement**: Static analysis tool checks column names against forbidden list.

## Rule 3: Enforce NOT NULL for Required Fields

**Rule**: Enforce `NOT NULL` for required fields (per contract mapping rulebook).

**Severity**: Error

**Rationale**: Contract `required` fields must be `NOT NULL` in database (with exceptions for soft-delete, audit fields).

**Example - Passing**:
```sql
-- Contract: total_revenue (required)
CREATE TABLE revenue_ledger (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    revenue_cents INTEGER NOT NULL,  -- Required field is NOT NULL
    ...
);
```

**Example - Failing**:
```sql
-- Contract: total_revenue (required)
CREATE TABLE revenue_ledger (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    revenue_cents INTEGER,  -- Missing NOT NULL for required field
    ...
);
```

**Enforcement**: Static analysis tool cross-references contract mapping rulebook to verify required fields are `NOT NULL`.

## Rule 4: Require tenant_id for Multi-Tenant Tables

**Rule**: Require `tenant_id uuid NOT NULL` with FK to `tenants(id)` for multi-tenant tables.

**Severity**: Error

**Rationale**: All tenant-scoped tables must have tenant isolation via `tenant_id` column.

**Example - Passing**:
```sql
CREATE TABLE attribution_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    ...
);
```

**Example - Failing**:
```sql
CREATE TABLE attribution_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Missing tenant_id
    ...
);
```

**Enforcement**: Static analysis tool checks for `tenant_id uuid NOT NULL` in all tables (except `tenants` table itself).

## Rule 5: Require RLS Policy Tag for Multi-Tenant Tables

**Rule**: Require RLS policy tag/comment for multi-tenant tables.

**Severity**: Error

**Rationale**: All multi-tenant tables must have RLS policies enabled and documented.

**Example - Passing**:
```sql
CREATE TABLE attribution_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    ...
);

ALTER TABLE attribution_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON attribution_events
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

COMMENT ON TABLE attribution_events IS '... RLS enabled for tenant isolation.';
```

**Example - Failing**:
```sql
CREATE TABLE attribution_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    ...
);
-- Missing RLS policy
```

**Enforcement**: Static analysis tool checks for `ENABLE ROW LEVEL SECURITY` and `CREATE POLICY` statements for tables with `tenant_id`.

## Rule 6: Forbid DECIMAL/FLOAT for Revenue

**Rule**: Forbid `DECIMAL` or `FLOAT` for revenue columns. Must use `INTEGER` (cents).

**Severity**: Error

**Rationale**: Per `.cursor/rules:164`, revenue must be stored as `INTEGER` (cents) for precision and performance.

**Example - Passing**:
```sql
CREATE TABLE revenue_ledger (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    revenue_cents INTEGER NOT NULL CHECK (revenue_cents >= 0),
    ...
);
```

**Example - Failing**:
```sql
CREATE TABLE revenue_ledger (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    revenue DECIMAL(10, 2) NOT NULL,  -- Forbidden type
    ...
);
```

**Enforcement**: Static analysis tool checks for `DECIMAL` or `FLOAT` types in columns with "revenue" in name.

## Rule 7: Require Time-Series Indexes

**Rule**: Require indexes on `(tenant_id, timestamp DESC)` for time-series tables.

**Severity**: Warning (can be waived with rationale)

**Rationale**: Time-series queries by tenant and time range are common. Composite indexes optimize these queries.

**Example - Passing**:
```sql
CREATE TABLE attribution_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    event_timestamp timestamptz NOT NULL,
    ...
);

CREATE INDEX idx_attribution_events_tenant_timestamp 
    ON attribution_events (tenant_id, event_timestamp DESC);
```

**Example - Failing**:
```sql
CREATE TABLE attribution_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    event_timestamp timestamptz NOT NULL,
    ...
);
-- Missing time-series index
```

**Enforcement**: Static analysis tool checks for composite indexes on `(tenant_id, timestamp_column DESC)` for tables with both `tenant_id` and timestamp columns.

## Enforcement Mechanism

**Static Analysis Tool**: TBD (e.g., custom Python script, sqlfluff, or similar)

**CI Integration**: Lint rules run automatically on all migration PRs.

**Manual Review**: PR reviewers verify lint compliance before approval.

## Cross-References

- **RLS Template**: See `db/migrations/templates/rls_policy.py.template` for RLS policy patterns
- **Style Guide**: See `SCHEMA_STYLE_GUIDE.md` for naming conventions





