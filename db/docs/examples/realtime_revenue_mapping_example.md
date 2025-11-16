# RealtimeRevenueResponse Contract→Schema Mapping Example

This document demonstrates the complete mapping from OpenAPI contract to hypothetical database schema.

## Contract Definition

**Source**: `api-contracts/openapi/v1/attribution.yaml:39-64`

**Contract Schema**:
```yaml
RealtimeRevenueResponse:
  type: object
  required:
    - total_revenue
    - verified
    - data_freshness_seconds
    - tenant_id
  properties:
    total_revenue:
      type: number
      format: float
      description: Total revenue in dollars
      example: 125000.50
    verified:
      type: boolean
      description: Whether the revenue data has been verified through reconciliation pipeline
      example: true
    data_freshness_seconds:
      type: integer
      description: Number of seconds since data was last updated
      example: 45
    tenant_id:
      type: string
      format: uuid
      description: Tenant identifier
      example: "550e8400-e29b-41d4-a716-446655440000"
```

## Type Conversions

### total_revenue: number (float) → revenue_cents: integer

**Contract**: `total_revenue: number (float)` (required)

**Database Mapping**:
```sql
revenue_cents INTEGER NOT NULL CHECK (revenue_cents >= 0)
```

**Conversion Logic**:
- **Storage**: Store as cents (integer): `125000.50` → `12500050` cents
- **API Response**: Convert to float (dollars): `revenue_cents / 100.0` → `125000.50`

**Rationale**: Integer arithmetic is exact, better performance than DECIMAL/FLOAT (per `.cursor/rules:164`).

### verified: boolean → verified: boolean

**Contract**: `verified: boolean` (required)

**Database Mapping**:
```sql
verified boolean NOT NULL
```

**Rationale**: Direct mapping, PostgreSQL boolean type provides native support.

### data_freshness_seconds: integer → data_freshness_seconds: integer

**Contract**: `data_freshness_seconds: integer` (required)

**Database Mapping**:
```sql
data_freshness_seconds INTEGER NOT NULL
```

**Rationale**: Direct mapping, PostgreSQL integer type provides native support.

### tenant_id: string (uuid) → tenant_id: uuid

**Contract**: `tenant_id: string (uuid)` (required)

**Database Mapping**:
```sql
tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
```

**Rationale**: PostgreSQL uuid type provides native UUID support and validation.

## Nullability Decisions

**All fields are required** in the contract, so all database columns are `NOT NULL`:

- `revenue_cents INTEGER NOT NULL`
- `verified boolean NOT NULL`
- `data_freshness_seconds INTEGER NOT NULL`
- `tenant_id uuid NOT NULL`

**Rationale**: Required fields represent business invariants that must be enforced at database level.

## Index Requirements

**Time-Series Query Pattern**: Queries by tenant and time range are common.

**Required Index**:
```sql
CREATE INDEX idx_revenue_ledger_tenant_created 
    ON revenue_ledger (tenant_id, created_at DESC);
```

**Rationale**: Composite index on `(tenant_id, timestamp DESC)` optimizes time-series queries per tenant.

## Materialized View Requirement

**Contract Requirement**: `RealtimeRevenueResponse` represents aggregated, real-time revenue data.

**Materialized View**:
```sql
CREATE MATERIALIZED VIEW mv_realtime_revenue AS
SELECT 
    tenant_id,
    SUM(revenue_cents) AS total_revenue_cents,
    BOOL_OR(verified) AS verified,
    EXTRACT(EPOCH FROM (NOW() - MAX(updated_at)))::INTEGER AS data_freshness_seconds,
    MAX(updated_at) AS last_updated_at
FROM revenue_ledger
GROUP BY tenant_id;

CREATE UNIQUE INDEX idx_mv_realtime_revenue_tenant 
    ON mv_realtime_revenue (tenant_id);
```

**Refresh Policy**: Refresh materialized view every 30-60 seconds (via Celery task or similar).

**API Response Mapping**:
```python
# Query materialized view
result = db.query(mv_realtime_revenue).filter_by(tenant_id=tenant_id).first()

# Convert to contract-compliant response
response = RealtimeRevenueResponse(
    total_revenue=result.total_revenue_cents / 100.0,  # Convert cents to dollars
    verified=result.verified,
    data_freshness_seconds=result.data_freshness_seconds,
    tenant_id=result.tenant_id
)
```

**Rationale**: Materialized view provides fast, pre-aggregated data for real-time dashboard queries (p95 < 50ms requirement).

## Complete Table Schema (Hypothetical)

```sql
CREATE TABLE revenue_ledger (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    revenue_cents INTEGER NOT NULL CHECK (revenue_cents >= 0),
    verified boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_revenue_ledger_tenant_created 
    ON revenue_ledger (tenant_id, created_at DESC);

COMMENT ON TABLE revenue_ledger IS 
    'Stores revenue entries for real-time aggregation. Purpose: Revenue tracking and verification. Data class: Non-PII. Ownership: Attribution service.';
```

## Traceability

- **Contract Source**: `api-contracts/openapi/v1/attribution.yaml:39-64`
- **API Endpoint**: `GET /api/attribution/revenue/realtime`
- **Database Objects**: `revenue_ledger` table, `mv_realtime_revenue` materialized view
- **Mapping Rationale**: All type conversions, nullability decisions, and index requirements documented above





