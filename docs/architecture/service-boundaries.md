# Service Boundaries & Microservices Extraction Readiness

**Purpose**: Define service boundaries, dependencies, API ownership, data access patterns, and extraction sequencing for modular monolith → microservices migration.

**Last Updated**: 2025-11-16

## Architecture Overview

**Current State**: Modular Monolith  
**Target State**: Microservices (extraction-ready)  
**Principle**: Strict component boundaries with clear API contracts enable extraction without architectural rewrites

## Service Components

### 1. Ingestion Service

**Location**: `backend/app/ingestion/`

**Responsibilities**:
- Webhook payload ingestion (Shopify, Stripe, PayPal, WooCommerce)
- PII stripping (Layer 1 - primary defense)
- Channel normalization
- Idempotency enforcement
- Dead letter queue routing

**API Contracts**:
- `contracts/webhooks/v1/shopify.yaml`
- `contracts/webhooks/v1/stripe.yaml`
- `contracts/webhooks/v1/paypal.yaml`
- `contracts/webhooks/v1/woocommerce.yaml`

**Database Dependencies**:
- `attribution_events` table (INSERT only)
- `dead_events` table (INSERT only)
- `channel_taxonomy` table (SELECT for normalization)
- `tenants` table (SELECT for tenant validation)

**External Dependencies**: None

**Data Access Pattern**: Write-only (INSERT) to event tables, read-only (SELECT) to reference tables

**Extraction Readiness**: ✅ High - Minimal dependencies, clear boundaries

---

### 2. Attribution Service

**Location**: `backend/app/attribution/`

**Responsibilities**:
- Statistical attribution models (Bayesian MMM, deterministic)
- Revenue aggregation and reporting
- Channel performance analytics
- Attribution allocation calculations

**API Contracts**:
- `contracts/attribution/v1/attribution.yaml` - GET `/api/attribution/revenue/realtime`

**Database Dependencies**:
- `attribution_events` table (SELECT)
- `attribution_allocations` table (INSERT, SELECT)
- `revenue_ledger` table (SELECT)
- `mv_realtime_revenue` materialized view (SELECT)
- `mv_channel_performance` materialized view (SELECT)
- `mv_daily_revenue_summary` materialized view (SELECT)
- `mv_allocation_summary` materialized view (SELECT)

**External Dependencies**: None

**Data Access Pattern**: Read-heavy (SELECT from events, ledger, materialized views), Write (INSERT allocations)

**Extraction Readiness**: ✅ High - Clear read/write boundaries, materialized views provide data isolation

---

### 3. Auth Service

**Location**: `backend/app/auth/`

**Responsibilities**:
- User authentication (JWT tokens)
- Token refresh
- Session management
- API key validation

**API Contracts**:
- `contracts/auth/v1/auth.yaml` - POST `/api/auth/login`, `/api/auth/refresh`, `/api/auth/logout`

**Database Dependencies**:
- `tenants` table (SELECT for api_key_hash validation, UPDATE for session management)

**External Dependencies**: None

**Data Access Pattern**: Read (SELECT tenants), Write (UPDATE session data)

**Extraction Readiness**: ✅ High - Minimal dependencies, isolated authentication logic

---

### 4. Webhooks Service

**Location**: `backend/app/webhooks/`

**Responsibilities**:
- Webhook signature validation (HMAC)
- Webhook payload routing to ingestion service
- Correlation ID propagation
- Error handling and retry logic

**API Contracts**:
- `contracts/webhooks/v1/shopify.yaml`
- `contracts/webhooks/v1/stripe.yaml`
- `contracts/webhooks/v1/paypal.yaml`
- `contracts/webhooks/v1/woocommerce.yaml`

**Database Dependencies**:
- None (stateless webhook validation and routing)

**External Dependencies**:
- Ingestion Service (internal API call)

**Data Access Pattern**: Stateless (no direct database access)

**Extraction Readiness**: ✅ High - Stateless, clear external dependency on Ingestion Service

---

### 5. Reconciliation Service

**Location**: `backend/app/reconciliation/` (planned)

**Responsibilities**:
- Revenue reconciliation pipeline
- Reconciliation run management
- Status reporting

**API Contracts**:
- `contracts/reconciliation/v1/reconciliation.yaml` - GET `/api/reconciliation/status`

**Database Dependencies**:
- `reconciliation_runs` table (INSERT, SELECT, UPDATE)
- `mv_reconciliation_status` materialized view (SELECT)
- `revenue_ledger` table (SELECT for reconciliation)

**External Dependencies**: None

**Data Access Pattern**: Read (SELECT from ledger, materialized views), Write (INSERT/UPDATE reconciliation runs)

**Extraction Readiness**: ✅ Medium - Depends on revenue_ledger, but clear boundaries

---

### 6. Export Service

**Location**: `backend/app/export/` (planned)

**Responsibilities**:
- Revenue data export (CSV/JSON)
- Pagination and filtering
- Format conversion

**API Contracts**:
- `contracts/export/v1/export.yaml` - GET `/api/export/revenue`

**Database Dependencies**:
- `revenue_ledger` table (SELECT)
- `attribution_allocations` table (SELECT)

**External Dependencies**: None

**Data Access Pattern**: Read-only (SELECT from ledger and allocations)

**Extraction Readiness**: ✅ High - Read-only, clear boundaries

---

### 7. Health Service

**Location**: `backend/app/health/` (planned)

**Responsibilities**:
- Health check endpoints
- Service status reporting
- Dependency health checks

**API Contracts**:
- `contracts/health/v1/health.yaml` - GET `/api/health`

**Database Dependencies**: None (optional database health check)

**External Dependencies**: None

**Data Access Pattern**: Stateless (optional database ping)

**Extraction Readiness**: ✅ High - Stateless, minimal dependencies

---

## Dependency Graph

```
┌─────────────────┐
│  Webhooks        │
│  Service         │
└────────┬─────────┘
         │ (internal API)
         ▼
┌─────────────────┐
│  Ingestion       │
│  Service         │
└────────┬─────────┘
         │ (writes events)
         ▼
┌─────────────────┐
│  PostgreSQL     │
│  Database       │
└────────┬────────┘
         │
         ├──► Attribution Service (reads events, writes allocations)
         ├──► Reconciliation Service (reads ledger, writes runs)
         ├──► Export Service (reads ledger, allocations)
         └──► Auth Service (reads/updates tenants)
```

**Key Observations**:
- **Webhooks → Ingestion**: Internal API dependency (can be HTTP/gRPC in microservices)
- **All Services → Database**: Direct database access (can be replaced with data service in microservices)
- **No Service-to-Service Dependencies**: Except Webhooks → Ingestion (clean boundaries)

---

## API Ownership Matrix

| API Endpoint | Contract | Service Owner | Database Tables | Materialized Views |
|--------------|----------|---------------|-----------------|-------------------|
| `POST /webhooks/shopify/orders/create` | `webhooks/v1/shopify.yaml` | Webhooks Service | None | None |
| `POST /webhooks/stripe/charge/succeeded` | `webhooks/v1/stripe.yaml` | Webhooks Service | None | None |
| `POST /webhooks/paypal/payment/sale/completed` | `webhooks/v1/paypal.yaml` | Webhooks Service | None | None |
| `POST /webhooks/woocommerce/order/created` | `webhooks/v1/woocommerce.yaml` | Webhooks Service | None | None |
| `GET /api/attribution/revenue/realtime` | `attribution/v1/attribution.yaml` | Attribution Service | `revenue_ledger` | `mv_realtime_revenue` |
| `GET /api/reconciliation/status` | `reconciliation/v1/reconciliation.yaml` | Reconciliation Service | `reconciliation_runs` | `mv_reconciliation_status` |
| `GET /api/export/revenue` | `export/v1/export.yaml` | Export Service | `revenue_ledger`, `attribution_allocations` | None |
| `POST /api/auth/login` | `auth/v1/auth.yaml` | Auth Service | `tenants` | None |
| `POST /api/auth/refresh` | `auth/v1/auth.yaml` | Auth Service | `tenants` | None |
| `POST /api/auth/logout` | `auth/v1/auth.yaml` | Auth Service | `tenants` | None |
| `GET /api/health` | `health/v1/health.yaml` | Health Service | None | None |

---

## Data Access Patterns

### Read Patterns

| Service | Tables Read | Materialized Views Read | Access Pattern |
|---------|-------------|------------------------|----------------|
| **Attribution** | `attribution_events`, `revenue_ledger` | `mv_realtime_revenue`, `mv_channel_performance`, `mv_daily_revenue_summary`, `mv_allocation_summary` | Read-heavy, materialized views for performance |
| **Reconciliation** | `revenue_ledger`, `reconciliation_runs` | `mv_reconciliation_status` | Read ledger, write runs |
| **Export** | `revenue_ledger`, `attribution_allocations` | None | Read-only, pagination |
| **Auth** | `tenants` | None | Read api_key_hash, update session |
| **Ingestion** | `channel_taxonomy`, `tenants` | None | Read reference data only |

### Write Patterns

| Service | Tables Written | Write Pattern | Constraints |
|---------|----------------|---------------|-------------|
| **Ingestion** | `attribution_events`, `dead_events` | INSERT only | PII guardrail triggers, idempotency constraints |
| **Attribution** | `attribution_allocations` | INSERT only | Sum-equality validation trigger |
| **Reconciliation** | `reconciliation_runs` | INSERT, UPDATE | Immutability on events/ledger |
| **Auth** | `tenants` | UPDATE (session data) | Limited to session fields |

---

## Extraction Sequencing

### Phase 1: Stateless Services (Easiest)

**Services**: Webhooks, Health

**Rationale**: No database dependencies, stateless operations

**Extraction Steps**:
1. Create Dockerfile for service
2. Extract to separate repository/service
3. Configure service discovery
4. Update routing (API gateway or service mesh)

**Dependencies**: None (Webhooks depends on Ingestion via internal API)

---

### Phase 2: Read-Only Services

**Services**: Export

**Rationale**: Read-only database access, no write dependencies

**Extraction Steps**:
1. Create Dockerfile
2. Extract to separate service
3. Configure database connection (read-only role)
4. Update API routing

**Dependencies**: Database (read-only access)

---

### Phase 3: Authentication Service

**Services**: Auth

**Rationale**: Minimal database dependencies, isolated functionality

**Extraction Steps**:
1. Create Dockerfile
2. Extract to separate service
3. Configure database connection (limited to tenants table)
4. Update API routing
5. Configure JWT token validation across services

**Dependencies**: Database (tenants table only)

---

### Phase 4: Write Services (Moderate Complexity)

**Services**: Ingestion

**Rationale**: Write-only access, clear boundaries, but critical path

**Extraction Steps**:
1. Create Dockerfile
2. Extract to separate service
3. Configure database connection (write role)
4. Implement PII stripping (Layer 1)
5. Update Webhooks service to call Ingestion via HTTP/gRPC
6. Configure correlation ID propagation

**Dependencies**: Database (attribution_events, dead_events, channel_taxonomy, tenants)

---

### Phase 5: Complex Read-Write Services (Higher Complexity)

**Services**: Attribution, Reconciliation

**Rationale**: Complex read-write patterns, materialized view dependencies

**Extraction Steps**:
1. Create Dockerfile
2. Extract to separate service
3. Configure database connection (read-write role)
4. Handle materialized view refresh coordination
5. Update API routing
6. Configure inter-service communication if needed

**Dependencies**: Database (multiple tables, materialized views)

---

## Service Communication Patterns

### Current (Modular Monolith)

**Pattern**: Direct function calls within same process

**Example**: Webhooks → Ingestion (function call)

### Target (Microservices)

**Pattern**: HTTP REST or gRPC

**Example**: Webhooks → Ingestion (HTTP POST to `http://ingestion-service:8001/api/ingest`)

**Communication Contracts**:
- Request/response schemas defined in OpenAPI contracts
- Correlation ID propagation via headers
- Error handling and retry logic

---

## Database Access Patterns

### Current (Modular Monolith)

**Pattern**: Direct database connections per service component

**Connection Pooling**: Shared connection pool per component

### Target (Microservices)

**Pattern**: Service-specific database connections

**Options**:
1. **Direct Database Access**: Each service connects directly (simplest)
2. **Data Service Layer**: Centralized data service (more complex, better isolation)
3. **Event Sourcing**: Event-driven architecture (most complex, best decoupling)

**Recommendation**: Start with direct database access, evolve to data service layer if needed

---

## Dockerfile Examples

### Ingestion Service Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/app/ingestion/ ./app/ingestion/
COPY backend/app/schemas/ ./app/schemas/

# Set environment variables
ENV PYTHONPATH=/app
ENV SERVICE_NAME=ingestion

# Expose port
EXPOSE 8001

# Run service
CMD ["uvicorn", "app.ingestion.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

### Attribution Service Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/app/attribution/ ./app/attribution/
COPY backend/app/schemas/ ./app/schemas/

# Set environment variables
ENV PYTHONPATH=/app
ENV SERVICE_NAME=attribution

# Expose port
EXPOSE 8002

# Run service
CMD ["uvicorn", "app.attribution.main:app", "--host", "0.0.0.0", "--port", "8002"]
```

---

## Health Check Endpoints

**Standard Pattern**: `GET /api/health`

**Response**:
```json
{
  "status": "healthy",
  "service": "ingestion",
  "version": "1.0.0",
  "dependencies": {
    "database": "healthy",
    "redis": "healthy"
  }
}
```

**Implementation**: Each service implements health check endpoint per `contracts/health/v1/health.yaml`

---

## Service Discovery

### Development (docker-compose)

**Pattern**: Service names as hostnames

**Example**: `http://ingestion-service:8001/api/ingest`

### Production

**Pattern**: Service mesh or API gateway

**Options**:
- **Kubernetes**: Service discovery via DNS
- **Consul**: Service registry and discovery
- **API Gateway**: Centralized routing (Kong, AWS API Gateway)

---

## Related Documentation

- **Contract Ownership**: `docs/architecture/contract-ownership.md`
- **Evidence Mapping**: `docs/architecture/evidence-mapping.md`
- **Database Object Catalog**: `docs/database/object-catalog.md`

