# Contract→Schema Mapping Rulebook

This document defines the mapping rules from OpenAPI 3.1 contracts to PostgreSQL database schema.

## Type Mappings

### string(uuid) → uuid

**OpenAPI Type**: `string` with `format: uuid`

**PostgreSQL Type**: `uuid`

**Example from Contract**:
- `api-contracts/openapi/v1/attribution.yaml:60-63`: `tenant_id: string (uuid)`

**PostgreSQL Mapping**:
```sql
tenant_id uuid NOT NULL
```

**Rationale**: PostgreSQL `uuid` type provides native UUID support and validation.

### string(date-time) → timestamptz

**OpenAPI Type**: `string` with `format: date-time`

**PostgreSQL Type**: `timestamptz` (timestamp with time zone)

**Example from Contract**:
- `api-contracts/openapi/v1/reconciliation.yaml:55-58`: `last_run_at: string (date-time)`

**PostgreSQL Mapping**:
```sql
last_run_at timestamptz NOT NULL
```

**Rationale**: `timestamptz` ensures correct timezone handling and ISO 8601 compliance.

### number (float) for Currency → integer (cents)

**OpenAPI Type**: `number` with `format: float` for currency values

**PostgreSQL Type**: `integer` (stored as cents)

**Example from Contract**:
- `api-contracts/openapi/v1/attribution.yaml:47-49`: `total_revenue: number (float)`

**PostgreSQL Mapping**:
```sql
revenue_cents INTEGER NOT NULL CHECK (revenue_cents >= 0)
```

**API Conversion**: Convert to float (dollars) in responses: `revenue_cents / 100.0`

**Rationale** (per `.cursor/rules:164`):
- Integer arithmetic is exact (no floating-point errors)
- Better performance than DECIMAL
- Cents provide sufficient precision for currency

### boolean → boolean

**OpenAPI Type**: `boolean`

**PostgreSQL Type**: `boolean`

**Example from Contract**:
- `api-contracts/openapi/v1/attribution.yaml:52-54`: `verified: boolean`

**PostgreSQL Mapping**:
```sql
verified boolean NOT NULL
```

**Rationale**: PostgreSQL `boolean` type provides native boolean support.

### integer → integer

**OpenAPI Type**: `integer`

**PostgreSQL Type**: `integer` or `bigint` (depending on range)

**Example from Contract**:
- `api-contracts/openapi/v1/attribution.yaml:56-59`: `data_freshness_seconds: integer`

**PostgreSQL Mapping**:
```sql
data_freshness_seconds INTEGER NOT NULL
```

**Rationale**: PostgreSQL `integer` type provides native integer support.

## Nullability/Required Mapping

### OpenAPI `required` → `NOT NULL` or Default Strategy

**Rule**: OpenAPI `required` fields must be `NOT NULL` in database (with exceptions).

**Example**:
- Contract: `total_revenue: number (float)` (required)
- Database: `revenue_cents INTEGER NOT NULL`

**Exception Cases**:
1. **Soft-Delete Fields**: `deleted_at timestamptz NULL` (not required in contract, nullable in DB)
2. **Audit Fields**: Optional audit metadata may be nullable
3. **Backward Compatibility**: New required fields added to existing tables may use `NOT NULL DEFAULT <value>` for migration safety

**Rationale**: Required fields represent business invariants that must be enforced at database level.

## Enum Handling

### Small, Stable Enums → CHECK Constraint

**Criteria**: Enums with <10 values that are stable (rarely change)

**Implementation**: `CHECK col IN (...)` constraint

**Example from Contract**:
- `api-contracts/openapi/v1/reconciliation.yaml:47-52`: `state: enum (idle|running|failed|completed)`

**PostgreSQL Mapping**:
```sql
state VARCHAR(20) NOT NULL CHECK (state IN ('idle', 'running', 'failed', 'completed'))
```

**Rationale**: CHECK constraints are simple, performant, and enforce enum values at database level.

### Large or Evolving Enums → Lookup Table

**Criteria**: Enums with >10 values or frequently changing values

**Implementation**: Separate lookup table with foreign key

**Example**:
```sql
CREATE TABLE channel_types (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT
);

CREATE TABLE attribution_events (
    ...
    channel_type_id uuid NOT NULL REFERENCES channel_types(id),
    ...
);
```

**Rationale**: Lookup tables provide flexibility for evolving enums and enable metadata storage.

## Identifier Conventions

### UUIDv4 Standard

**Pattern**: Use `gen_random_uuid()` for all primary keys

**Example**:
```sql
id uuid PRIMARY KEY DEFAULT gen_random_uuid()
```

**Rationale**: UUIDs provide globally unique identifiers, prevent enumeration attacks, and enable distributed systems.

### Idempotency Key Format

**Pattern**: `{tenant_id}:{event_id}` (per `.cursor/rules:150`)

**Example**:
```sql
idempotency_key VARCHAR(255) NOT NULL UNIQUE
-- Format: "550e8400-e29b-41d4-a716-446655440000:evt_12345"
```

**Rationale**: Compound key format ensures idempotency across tenants and events.

## Timestamp Handling

### Authoritative Clock

**Pattern**: Use `now()` for `created_at` and `updated_at`

**Example**:
```sql
created_at timestamptz NOT NULL DEFAULT now(),
updated_at timestamptz NOT NULL DEFAULT now()
```

**Rationale**: PostgreSQL `now()` provides server-side authoritative timestamps.

### Monotonicity Notes

**Considerations**:
- `created_at` is immutable (never updated)
- `updated_at` is updated on every row modification (via trigger or application logic)
- Domain-specific timestamps (e.g., `event_timestamp`) may differ from `created_at` (event occurred before ingestion)

**Rationale**: Clear timestamp semantics prevent confusion and enable correct temporal queries.

## Events Immutability Policy

### Append-Only Semantics

**Policy**: `attribution_events` table is append-only. Events cannot be updated or deleted by application roles.

**Contract Impact**:
- **No UPDATE endpoints**: OpenAPI contracts must not define UPDATE operations for events
- **No DELETE endpoints**: OpenAPI contracts must not define DELETE operations for events
- **Correction model**: Corrections must be represented as new events (linked via `correlation_id` or correction flag)

**Schema Impact**:
- **GRANT Policy**: `app_rw` role has `SELECT`, `INSERT` only (no `UPDATE` or `DELETE`)
- **Guard Trigger**: `trg_events_prevent_mutation` prevents UPDATE/DELETE operations (defense-in-depth)
- **Table COMMENT**: Must explicitly state append-only semantics

**Mapping Rule**: When mapping contract operations to database operations:
- `POST /api/events` → `INSERT INTO attribution_events` ✅ Allowed
- `GET /api/events/{id}` → `SELECT FROM attribution_events` ✅ Allowed
- `PUT /api/events/{id}` → ❌ **Not allowed** (no UPDATE operations)
- `DELETE /api/events/{id}` → ❌ **Not allowed** (no DELETE operations)
- `POST /api/events/corrections` → `INSERT INTO attribution_events` (with correction flag) ✅ Allowed

**Cross-Reference**: See `db/docs/EVENTS_IMMUTABILITY_POLICY.md` for complete policy statement.

## Ledger Immutability Policy

### Write-Once Semantics

**Policy**: `revenue_ledger` table is write-once. Ledger entries cannot be updated or deleted by application roles.

**Contract Impact**:
- **No UPDATE endpoints**: OpenAPI contracts must not define UPDATE operations for ledger entries
- **No DELETE endpoints**: OpenAPI contracts must not define DELETE operations for ledger entries
- **Correction model**: Corrections must be represented as new ledger entries (additive corrections)

**Schema Impact**:
- **GRANT Policy**: `app_rw` role has `SELECT`, `INSERT` only (no `UPDATE` or `DELETE`)
- **Guard Trigger**: `trg_ledger_prevent_mutation` prevents UPDATE/DELETE operations (defense-in-depth)
- **Table COMMENT**: Must explicitly state write-once semantics

**Mapping Rule**: When mapping contract operations to database operations:
- `POST /api/ledger/entries` → `INSERT INTO revenue_ledger` ✅ Allowed
- `GET /api/ledger/entries/{id}` → `SELECT FROM revenue_ledger` ✅ Allowed
- `PUT /api/ledger/entries/{id}` → ❌ **Not allowed** (no UPDATE operations)
- `DELETE /api/ledger/entries/{id}` → ❌ **Not allowed** (no DELETE operations)
- `POST /api/ledger/corrections` → `INSERT INTO revenue_ledger` (with negative revenue_cents) ✅ Allowed

**Cross-Reference**: See `db/docs/IMMUTABILITY_POLICY.md` for complete policy statement.

## Channel Taxonomy Governance

### Canonical Channel Source

**Policy**: `channel_taxonomy` table is **the only** allowed place to define canonical channels.

**Enforcement**:
- All channel codes must be defined in `channel_taxonomy` table
- `attribution_allocations.channel_code` (or `channel`) must FK to `channel_taxonomy.code`
- No hard-coded channel strings in allocations or read models
- No CHECK constraints on channel values (replaced by FK)

**New Channel Process**:
1. Add channel to `channel_taxonomy` table
2. Update `channel_mapping.yaml` if vendor mapping needed
3. Update OpenAPI contracts if exposing channel fields
4. All changes must go through PR review

**Governance Rule**: Reviewers can reject PRs that sneak in new channels outside taxonomy.

**Cross-Reference**: See `B0.3_IMPLEMENTATION_COMPLETE.md` (Phase 3) for complete channel taxonomy specification.

## Cross-References

- **Style Guide**: See `SCHEMA_STYLE_GUIDE.md` for naming conventions
- **RLS Template**: See `db/migrations/templates/rls_policy.py.template` for tenant isolation patterns
- **Events Immutability Policy**: See `db/docs/EVENTS_IMMUTABILITY_POLICY.md` for append-only semantics


