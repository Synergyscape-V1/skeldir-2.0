# Traceability Standard

This document defines metadata conventions for traceability and auditability.

## correlation_id Propagation

**Purpose**: Enable distributed tracing across services and database operations.

**Pattern**: `correlation_id uuid` column in relevant tables

**Propagation Flow**:
1. **API Request**: `X-Correlation-ID` header (UUID format, per `api-contracts/openapi/v1/_common/components.yaml:17-23`)
2. **Application Layer**: Extract correlation ID from header, set in database context
3. **Database Layer**: Store correlation ID in table columns for auditability

**Example**:
```sql
CREATE TABLE attribution_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    correlation_id uuid,  -- From X-Correlation-ID header
    ...
);
```

**Usage**:
- Query all operations for a given correlation ID: `SELECT * FROM attribution_events WHERE correlation_id = '...'`
- Trace request flow across services and database operations
- Debug issues by correlating logs and database operations

**Rationale**: Correlation IDs enable end-to-end request tracing and debugging.

## actor_* Metadata

**Purpose**: Track who performed an action (user, service, system).

**Pattern**: `actor_*` columns for actor identification

**Columns**:
- `actor_user_id uuid` - User who performed action (if applicable)
- `actor_service_name VARCHAR(100)` - Service that performed action
- `actor_system boolean` - Whether action was performed by system (not user)

**Example**:
```sql
CREATE TABLE attribution_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    correlation_id uuid,
    actor_user_id uuid,  -- User who triggered event (if applicable)
    actor_service_name VARCHAR(100) NOT NULL,  -- Service that processed event
    actor_system boolean NOT NULL DEFAULT false,  -- System-generated event
    ...
);
```

**Usage**:
- Audit trail: Who/what performed each action
- Compliance: Track user actions for regulatory requirements
- Debugging: Identify source of problematic operations

**Rationale**: Actor metadata enables auditability and compliance tracking.

## Traceability in Comments

**Requirement**: Comments should reference traceability requirements.

**Example**:
```sql
COMMENT ON COLUMN attribution_events.correlation_id IS 
    'Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing. Data class: Non-PII.';

COMMENT ON COLUMN attribution_events.actor_service_name IS 
    'Service that processed this event. Purpose: Audit trail. Data class: Non-PII.';
```

**Rationale**: Comments document traceability purpose and data classification.

## Cross-References

- **Contract Mapping**: See `CONTRACT_TO_SCHEMA_MAPPING.md` for correlation_id type mapping
- **Comment Standard**: See `SCHEMA_STYLE_GUIDE.md` for comment requirements





