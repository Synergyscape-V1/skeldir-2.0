# Database Schema Governance

**Status**: Active  
**Last Updated**: 2025-11-16  
**Owner**: Backend Engineering Team

## Overview

This document consolidates all database schema governance rules, standards, and procedures for the Skeldir Attribution Intelligence platform. It serves as the single source of truth for schema design, migration procedures, and data integrity controls.

## Table of Contents

1. [Naming Conventions](#naming-conventions)
2. [Type Mappings](#type-mappings)
3. [Contract-to-Schema Mapping](#contract-to-schema-mapping)
4. [Migration System](#migration-system)
5. [Row-Level Security (RLS)](#row-level-security-rls)
6. [Roles and Grants](#roles-and-grants)
7. [Data Integrity Controls](#data-integrity-controls)
8. [Schema Validation](#schema-validation)
9. [Schema Snapshots](#schema-snapshots)

## Naming Conventions

### Tables and Columns

**snake_case** for all table and column names.

**Examples**:
- ✅ `attribution_events`
- ✅ `tenant_id`
- ✅ `created_at`
- ❌ `AttributionEvents` (PascalCase)
- ❌ `tenantId` (camelCase)

**Rationale**: PostgreSQL convention, consistent with Python naming, easier to read in SQL.

### Primary Keys

**Pattern**: `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`

**Rationale**: 
- UUID provides globally unique identifiers
- `gen_random_uuid()` is PostgreSQL native (no extension required)
- UUIDs prevent enumeration attacks and enable distributed systems

**Anti-patterns**:
- ❌ `id serial` (sequential IDs reveal information)
- ❌ Custom UUID generation (use PostgreSQL native)

### Timestamps

**Pattern**: Timestamp trio for most tables:
- `created_at timestamptz NOT NULL DEFAULT now()`
- `updated_at timestamptz NOT NULL DEFAULT now()`
- Domain-specific temporal columns as needed (e.g., `occurred_at`, `processed_at`)

**Rationale**:
- `timestamptz` (timestamp with time zone) ensures correct timezone handling
- `NOT NULL` prevents null timestamps
- `DEFAULT now()` provides automatic timestamping

### Foreign Keys

**Pattern**: `{referenced_table}_id` (singular form of referenced table name)

**Examples**:
- ✅ `tenant_id` (references `tenants` table)
- ✅ `event_id` (references `attribution_events` table)
- ❌ `tenant` (missing `_id` suffix)
- ❌ `tenants_id` (plural form)

### Check Constraints

**Pattern**: `ck_{table}_{column}_{condition}`

**Examples**:
- ✅ `ck_attribution_events_revenue_cents_positive` (CHECK revenue_cents >= 0)
- ✅ `ck_revenue_ledger_status_valid` (CHECK status IN ('pending', 'processed', 'failed'))

### Indexes

**Pattern**: `idx_{table}_{columns}`

**Examples**:
- ✅ `idx_attribution_events_tenant_occurred_at` (on `tenant_id, occurred_at DESC`)
- ✅ `idx_attribution_events_session_id` (on `session_id`)

**For partial indexes**, include condition in name:
- ✅ `idx_attribution_events_tenant_external_event_id` (WHERE external_event_id IS NOT NULL)

## Type Mappings

### Revenue Storage

**Pattern**: `INTEGER` (cents), **never** `DECIMAL` or `FLOAT`

**Example**:
```sql
revenue_cents INTEGER NOT NULL CHECK (revenue_cents >= 0)
```

**Rationale**:
- Integer arithmetic is exact (no floating-point errors)
- Better performance than DECIMAL
- Cents provide sufficient precision for currency
- API converts to float (dollars) in responses: `revenue_cents / 100.0`

**Anti-patterns**:
- ❌ `revenue DECIMAL(10, 2)` (floating-point issues, performance)
- ❌ `revenue FLOAT` (precision loss, performance)

### JSONB Usage

**Pattern**: Use `JSONB` columns for raw payloads and semi-structured data.

**Example**:
```sql
raw_payload JSONB NOT NULL
```

**With GIN Index**:
```sql
CREATE INDEX idx_attribution_events_raw_payload ON attribution_events USING GIN (raw_payload);
```

**When to Use**:
- Raw webhook payloads (before PII stripping)
- Metadata that doesn't fit relational structure
- Configuration data

**When NOT to Use**:
- Core business data (use relational columns)
- Frequently queried fields (extract to columns)
- Data requiring referential integrity (use FKs)

## Contract-to-Schema Mapping

### Type Mappings

| OpenAPI Type | PostgreSQL Type | Example |
|--------------|-----------------|---------|
| `string` (uuid) | `uuid` | `tenant_id uuid NOT NULL` |
| `string` (date-time) | `timestamptz` | `created_at timestamptz NOT NULL` |
| `number` (float) for currency | `integer` (cents) | `revenue_cents INTEGER NOT NULL` |
| `boolean` | `boolean` | `verified boolean NOT NULL` |
| `integer` | `integer` or `bigint` | `data_freshness_seconds INTEGER NOT NULL` |

### Nullability Mapping

**Rule**: OpenAPI `required` fields must be `NOT NULL` in database (with exceptions for soft-delete, audit fields).

**Example**:
- Contract: `total_revenue: number (float)` (required)
- Database: `revenue_cents INTEGER NOT NULL`

**Exceptions**:
- Soft-delete fields: `deleted_at timestamptz NULL`
- Optional audit fields: `actor_user_id uuid NULL`

### Contract Mapping Reference

See `db/docs/CONTRACT_TO_SCHEMA_MAPPING.md` for complete mapping rulebook.

## Migration System

### Tool: Alembic

**Rationale**: Alembic is the standard migration tool for SQLAlchemy-based Python applications. It provides:
- Version control for database schema changes
- Rollback capability
- Environment-aware configuration
- Integration with SQLAlchemy models (when implemented)

### Naming Convention

Migration files follow the pattern: `YYYYMMDDHHMM_descriptive_slug.py`

**Examples**:
- `202511121302_baseline.py` - Initial baseline migration
- `202511131115_add_core_tables.py` - Add core tables

**Rationale**: Timestamp prefix ensures chronological ordering and prevents naming conflicts.

### Version Graph Policy

**Linear Graph Only**: All migrations must form a linear chain. No branching or merging is allowed.

**Rationale**: 
- Linear history is easier to understand and audit
- Prevents complex merge conflicts in migrations
- Ensures deterministic migration path

**Enforcement**: 
- Alembic will detect and prevent multiple heads
- PR review must verify linear history
- `alembic check` command validates migration graph

### Migration Workflow

1. **Create Migration**: `alembic revision -m "descriptive_slug"`
2. **Edit Migration**: Add upgrade/downgrade operations
3. **Self-Review**: Verify migration follows style guide and governance rules
4. **Test Locally**: Apply migration to local database and verify
5. **Create PR**: Submit migration for peer review
6. **Peer Review**: Another developer reviews for correctness and compliance
7. **Approval**: Backend Lead approves migration
8. **Apply**: Migration is applied to target environment

### Rollback Policy

**All migrations must be reversible**. The `downgrade()` function must undo all changes made by `upgrade()`.

**Rationale**: 
- Enables recovery from problematic migrations
- Supports rollback during deployments
- Ensures migration safety

**Testing**: 
- Test rollback locally before PR submission
- Verify `alembic downgrade -1` works correctly

### Migration Safety

**Pre-Migration Checks**:
- Backup verification (mandatory for production)
- Lock timeout: `SET lock_timeout = '30s'`
- Statement timeout: `SET statement_timeout = '5min'`

**Post-Migration Checks**:
- Schema validation (verify changes applied correctly)
- Index usage verification
- RLS policy verification

**Destructive-Change Approval**:
- DROP TABLE, DROP COLUMN, DROP INDEX require Backend Lead approval
- Production destructive changes require Backend Lead + Product Owner approval

**Dry-Run Procedure**:
```bash
# Generate SQL without applying
alembic upgrade --sql head

# Review generated SQL before applying
```

See `db/docs/MIGRATION_SAFETY_CHECKLIST.md` for complete safety procedures.

## Row-Level Security (RLS)

### Policy Pattern

All tenant-scoped tables must have RLS enabled with tenant isolation policies.

**Standard Pattern**:
```sql
ALTER TABLE attribution_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON attribution_events
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

**Rationale**: RLS enforces tenant isolation at the database level, preventing cross-tenant data access even if application logic fails.

### Tenant Context Setting

**Application Responsibility**: Set tenant context before database operations:
```sql
SET app.current_tenant_id = '<tenant_uuid>';
```

**Enforcement**: RLS policies automatically filter queries to current tenant's data.

### RLS Template

See `db/migrations/templates/rls_policy.py.template` for RLS policy patterns.

## Roles and Grants

### Role Model

| Role | Purpose | Capabilities |
|------|---------|--------------|
| `app_rw` | Read-write access for application | SELECT, INSERT, UPDATE, DELETE (RLS-scoped) |
| `app_ro` | Read-only access for reporting | SELECT (RLS-scoped) |
| `app_admin` | Administrative operations | SELECT, INSERT, UPDATE, DELETE (admin tables) |
| `migration_owner` | Migration execution | Full database access (CREATE, ALTER, DROP) |

### Least-Privilege Matrix

| Role | SELECT | INSERT | UPDATE | DELETE | CREATE | ALTER | DROP | RLS Modify |
|------|--------|--------|--------|--------|--------|-------|------|------------|
| app_rw | ✅ (RLS) | ✅ (RLS) | ✅ (RLS) | ✅ (RLS) | ❌ | ❌ | ❌ | ❌ |
| app_ro | ✅ (RLS) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| app_admin | ✅ (admin) | ✅ (admin) | ✅ (admin) | ✅ (admin) | ❌ | ❌ | ❌ | ❌ |
| migration_owner | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### GRANT Template

**Standard Pattern for Tenant-Scoped Tables**:
```sql
-- Grant to application read-write role
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attribution_events TO app_rw;

-- Grant to application read-only role
GRANT SELECT ON TABLE attribution_events TO app_ro;

-- Grant usage on sequence (if using serial IDs)
GRANT USAGE, SELECT ON SEQUENCE attribution_events_id_seq TO app_rw;

-- Revoke PUBLIC access
REVOKE ALL ON TABLE attribution_events FROM PUBLIC;
```

See `db/docs/ROLES_AND_GRANTS.md` for complete role model.

## Data Integrity Controls

### Idempotency

**Strategy**: Enforce idempotency via UNIQUE constraints on `(tenant_id, external_event_id)` or `(tenant_id, correlation_id)`.

**Implementation**:
```sql
-- Primary strategy: external_event_id (Shopify, PayPal, WooCommerce)
CREATE UNIQUE INDEX idx_attribution_events_tenant_external_event_id 
    ON attribution_events (tenant_id, external_event_id) 
    WHERE external_event_id IS NOT NULL;

-- Fallback strategy: correlation_id (Stripe)
CREATE UNIQUE INDEX idx_attribution_events_tenant_correlation_id 
    ON attribution_events (tenant_id, correlation_id) 
    WHERE correlation_id IS NOT NULL AND external_event_id IS NULL;
```

**Rationale**: Prevents duplicate event ingestion from webhook retries.

See `db/docs/IDEMPOTENCY_STRATEGY.md` for complete strategy.

### Immutability

**Policy**: `attribution_events` and `revenue_ledger` rows are immutable - once created, they cannot be updated or deleted by application roles.

**Enforcement**:
- **Database-Level**: Revoke UPDATE/DELETE privileges from `app_rw` and `app_ro`
- **Trigger-Level**: Guard triggers prevent UPDATE/DELETE operations

**Correction Model**: Corrections must be represented as new events, not in-place edits.

**Migration**: `alembic/versions/202511141201_add_events_guard_trigger.py` implements immutability triggers.

See `db/docs/EVENTS_IMMUTABILITY_POLICY.md` for complete policy.

### Sum-Equality Invariant

**Policy**: Attribution allocations must sum to event revenue.

**Enforcement**: Trigger `trg_check_allocation_sum` validates sum-equality on INSERT/UPDATE.

**Implementation**: `alembic/versions/202511131240_add_sum_equality_validation.py`

See `db/docs/SUM_EQUALITY_INVARIANT.md` for complete specification.

### PII Controls

**Policy**: No PII (Personally Identifiable Information) may be persisted in database.

**Enforcement**: Three-layer defense-in-depth:
1. Layer 1 (Application): PII stripping in B0.4 ingestion service
2. Layer 2 (Database): BEFORE INSERT triggers block PII keys
3. Layer 3 (Operations): Periodic audit scanning detects residual PII

**PII Blocklist**: 13 keys (email, phone, ssn, names, IP, address)

See `docs/database/pii-controls.md` for complete PII defense strategy.

## Schema Validation

### Comment Requirements

**All database objects must have comments** using `COMMENT ON` statements.

**Minimum Content**:
- **Purpose**: What the object is used for
- **Data Class**: PII/non-PII classification
- **Ownership**: Which team/component owns this object

**Example**:
```sql
COMMENT ON TABLE attribution_events IS 
    'Stores attribution events for revenue tracking. Purpose: Event ingestion and attribution calculations. Data class: Non-PII (PII stripped from raw_payload). Ownership: Attribution service. RLS enabled for tenant isolation.';
```

**Rationale**: Comments enable data dictionary generation and improve schema legibility.

### DDL Lint Rules

**Rule 1**: Tables must have comments (Error severity)

**Rule 2**: Forbid generic column names (`data`, `misc`, `other`, `stuff`) (Error severity)

**Rule 3**: Enforce NOT NULL for required fields (Error severity)

**Rule 4**: Require `tenant_id` for multi-tenant tables (Error severity)

**Rule 5**: Require RLS policy for multi-tenant tables (Error severity)

**Rule 6**: Forbid DECIMAL/FLOAT for revenue (Error severity)

**Rule 7**: Require time-series indexes (Warning severity, can be waived)

**Enforcement**: Static analysis tool checks migrations before approval.

See `db/docs/DDL_LINT_RULES.md` for complete lint rules.

### Traceability Standard

**correlation_id**: Enable distributed tracing across services and database operations.

**Pattern**: `correlation_id uuid` column in relevant tables

**Propagation**: `X-Correlation-ID` header → Application → Database

**actor_* Metadata**: Track who performed an action (user, service, system).

**Pattern**: `actor_user_id uuid`, `actor_service_name VARCHAR(100)`, `actor_system boolean`

See `db/docs/TRACEABILITY_STANDARD.md` for complete traceability standard.

## Schema Snapshots

### Snapshot Format

**Tool**: `pg_dump --schema-only`

**Command**:
```bash
pg_dump --schema-only --no-owner --no-privileges \
    -h localhost -U user -d skeldir \
    > db/snapshots/schema_YYYYMMDD_HHMMSS.sql
```

**Naming Convention**: `schema_YYYYMMDD_HHMMSS.sql`

### Snapshot Frequency

- **Per Release**: Before and after each release
- **Before Major Migrations**: Create snapshot before applying major migrations
- **After Major Migrations**: Create snapshot after applying major migrations

### Drift Detection

**Process**:
1. Generate snapshot from migrations (apply to fresh database)
2. Compare with last blessed snapshot
3. Analyze differences (expected vs. unexpected)
4. Resolve drift if detected

**Tool**: `sqldef` or `migra` for structured diff analysis

See `db/docs/SCHEMA_SNAPSHOTS.md` for complete snapshot procedures.

## Governance Baseline

### Checklist

All governance baseline artifacts are documented in `db/GOVERNANCE_BASELINE_CHECKLIST.md`:

- ✅ Migration system initialized (Alembic)
- ✅ Style guide and lint rules defined
- ✅ Contract-to-schema mapping rulebook
- ✅ Extension allow-list
- ✅ Roles and grants model
- ✅ Migration safety checklist
- ✅ Schema snapshots and drift detection
- ✅ Documentation and PR gates
- ✅ Seed/fixture governance
- ✅ Traceability standard

### ADRs (Architectural Decision Records)

- **ADR-001**: Schema Source of Truth (`docs/architecture/adr/ADR-001-schema-source-of-truth.md`)
- **ADR-002**: Migration Discipline (`docs/architecture/adr/ADR-002-migration-discipline.md`)
- **ADR-003**: PII Defense Strategy (`docs/architecture/adr/ADR-003-PII-Defense-Strategy.md`)

## References

- **Migration System**: `db/docs/MIGRATION_SYSTEM.md`
- **Style Guide**: `db/docs/SCHEMA_STYLE_GUIDE.md` (source for naming conventions)
- **Lint Rules**: `db/docs/DDL_LINT_RULES.md`
- **Contract Mapping**: `db/docs/CONTRACT_TO_SCHEMA_MAPPING.md`
- **Roles and Grants**: `db/docs/ROLES_AND_GRANTS.md`
- **Idempotency**: `db/docs/IDEMPOTENCY_STRATEGY.md`
- **Immutability**: `db/docs/EVENTS_IMMUTABILITY_POLICY.md`
- **Traceability**: `db/docs/TRACEABILITY_STANDARD.md`
- **Schema Snapshots**: `db/docs/SCHEMA_SNAPSHOTS.md`
- **Governance Checklist**: `db/GOVERNANCE_BASELINE_CHECKLIST.md`

