# Seeding Policy

This document defines the policy for database seed data.

## Where Seeds Live

**Location**: `/db/seeds/` directory

**Structure**:
- `/db/seeds/` - Seed data SQL files
- `/db/seeds/templates/` - Seed templates

**Naming**: `seed_{table_name}.sql` (e.g., `seed_tenants.sql`, `seed_attribution_events.sql`)

**Rationale**: Centralized location enables easy discovery and management.

## Invariants

### 1. Never Introduce PII

**Rule**: Seed data must never contain PII (personally identifiable information).

**Forbidden**:
- Email addresses
- Names
- Phone numbers
- Physical addresses
- IP addresses (beyond test data)

**Rationale**: Per privacy-first architecture (`.cursor/rules:36-44`), PII must never be stored.

**Enforcement**: 
- Static analysis checks seed files for PII patterns
- PR review verifies no PII in seed data

### 2. Consistent Tenant Scoping

**Rule**: All seed data must be scoped to test tenants.

**Pattern**:
```sql
-- Use test tenant IDs
INSERT INTO attribution_events (tenant_id, ...) VALUES
    ('00000000-0000-0000-0000-000000000001', ...),  -- Test tenant 1
    ('00000000-0000-0000-0000-000000000002', ...);  -- Test tenant 2
```

**Rationale**: Tenant-scoped seed data enables realistic testing of multi-tenant scenarios.

### 3. Referential Integrity Rules

**Rule**: Seed data must maintain referential integrity.

**Requirements**:
- Foreign keys must reference existing rows
- Seed order must respect dependencies (parents before children)
- Use transactions to ensure atomicity

**Example**:
```sql
BEGIN;

-- Seed tenants first (parent)
INSERT INTO tenants (id, name) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Test Tenant 1');

-- Seed attribution_events (child, references tenants)
INSERT INTO attribution_events (tenant_id, ...) VALUES
    ('00000000-0000-0000-0000-000000000001', ...);

COMMIT;
```

**Rationale**: Referential integrity ensures seed data is valid and testable.

## Alignment with B0.2 Mocks

**Requirement**: Seeds must mirror B0.2 mocks' shapes for contract parity.

**Source**: `docker-compose.mock.yml` defines Prism mock servers that return example data from OpenAPI contracts.

**Alignment Strategy**:
1. Extract example data from OpenAPI contracts (e.g., `attribution.yaml:65-72`)
2. Convert to database seed format (type conversions, nullability)
3. Ensure seed data matches mock server response shapes

**Example**:
- **Contract Example**: `attribution.yaml:65-72` shows `total_revenue: 125000.50`
- **Seed Data**: `revenue_cents: 12500050` (convert to cents)
- **Mock Server**: Returns `total_revenue: 125000.50` (matches contract)
- **Database Seed**: Stores `revenue_cents: 12500050` (matches contract after conversion)

**Rationale**: Contract parity ensures frontend can consume both mock and real data seamlessly.

## Alignment with docker-compose.mock.yml

**Requirement**: Seeds must align with mock server responses.

**Mock Servers** (from `docker-compose.mock.yml`):
- Auth: `http://localhost:4010`
- Attribution: `http://localhost:4011`
- Reconciliation: `http://localhost:4012`
- Export: `http://localhost:4013`
- Health: `http://localhost:4014`
- Webhooks: `http://localhost:4015-4018`

**Alignment**:
- Seed data should enable API endpoints to return responses matching mock server examples
- Tenant IDs in seeds should match tenant IDs used in mock responses
- Data values should be consistent (after type conversion)

**Rationale**: Enables seamless transition from mocks to real database.

## Seed Template

**Template Location**: `/db/seeds/templates/seed_template.sql.template`

**Template Includes**:
- Tenant scoping examples
- PII exclusion requirements
- Referential integrity patterns
- Transaction usage

**Usage**: Copy template and customize for specific table seed data.

## Future Tables

**Requirement**: All new tables must have a seed plan entry.

**Seed Plan Entry Includes**:
- Table name
- Seed data source (contract examples, mock responses)
- Tenant scoping strategy
- Referential integrity dependencies
- PII exclusion checklist

**Rationale**: Ensures seed data is planned before table creation.

## Cross-References

- **Privacy Notes**: See `PRIVACY-NOTES.md` for PII exclusion requirements
- **Contract Mapping**: See `CONTRACT_TO_SCHEMA_MAPPING.md` for type conversion rules
- **Mock Servers**: See `docker-compose.mock.yml` for mock server configuration





