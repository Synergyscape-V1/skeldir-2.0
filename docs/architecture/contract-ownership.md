# Contract Ownership Mapping

**Purpose**: Map OpenAPI contracts to backend service components, ownership, and implementation status.

**Last Updated**: 2025-11-16

## Contract Structure

Contracts are organized into domain-based directories:

```
contracts/
├── attribution/
│   ├── v1/
│   │   └── attribution.yaml
│   └── baselines/
│       └── v1.0.0/
│           └── attribution.yaml
├── webhooks/
│   ├── v1/
│   │   ├── shopify.yaml
│   │   ├── stripe.yaml
│   │   ├── paypal.yaml
│   │   └── woocommerce.yaml
│   └── baselines/
│       └── v1.0.0/
│           ├── shopify.yaml
│           ├── stripe.yaml
│           ├── paypal.yaml
│           └── woocommerce.yaml
├── auth/
│   ├── v1/
│   │   └── auth.yaml
│   └── baselines/
│       └── v1.0.0/
│           └── auth.yaml
├── reconciliation/
│   ├── v1/
│   │   └── reconciliation.yaml
│   └── baselines/
│       └── v1.0.0/
│           └── reconciliation.yaml
├── export/
│   ├── v1/
│   │   └── export.yaml
│   └── baselines/
│       └── v1.0.0/
│           └── export.yaml
├── health/
│   ├── v1/
│   │   └── health.yaml
│   └── baselines/
│       └── v1.0.0/
│           └── health.yaml
└── _common/
    └── v1/
        ├── components.yaml
        ├── pagination.yaml
        └── parameters.yaml
```

## Contract-to-Service Mapping

| Contract Domain | Contract File | Backend Component | Ownership | Implementation Status |
|----------------|---------------|-------------------|-----------|----------------------|
| **Attribution** | `contracts/attribution/v1/attribution.yaml` | `backend/app/attribution/` | Attribution Service Team | 🔄 Planned |
| **Webhooks** | `contracts/webhooks/v1/shopify.yaml` | `backend/app/webhooks/` | Webhooks Service Team | 🔄 Planned |
| **Webhooks** | `contracts/webhooks/v1/stripe.yaml` | `backend/app/webhooks/` | Webhooks Service Team | 🔄 Planned |
| **Webhooks** | `contracts/webhooks/v1/paypal.yaml` | `backend/app/webhooks/` | Webhooks Service Team | 🔄 Planned |
| **Webhooks** | `contracts/webhooks/v1/woocommerce.yaml` | `backend/app/webhooks/` | Webhooks Service Team | 🔄 Planned |
| **Auth** | `contracts/auth/v1/auth.yaml` | `backend/app/auth/` | Auth Service Team | 🔄 Planned |
| **Reconciliation** | `contracts/reconciliation/v1/reconciliation.yaml` | `backend/app/reconciliation/` | Attribution Service Team | 🔄 Planned |
| **Export** | `contracts/export/v1/export.yaml` | `backend/app/export/` | Attribution Service Team | 🔄 Planned |
| **Health** | `contracts/health/v1/health.yaml` | `backend/app/health/` | Platform Team | 🔄 Planned |

## API Endpoint Mapping

### Attribution API

**Contract**: `contracts/attribution/v1/attribution.yaml`

**Endpoints**:
- `GET /api/attribution/revenue/realtime` - Get realtime revenue attribution data

**Backend Component**: `backend/app/attribution/` (planned)

**Database Dependencies**:
- `mv_realtime_revenue` materialized view
- `revenue_ledger` table

**Mock Server**: `docker-compose.yml` - Attribution service on port 4011

---

### Webhook APIs

**Contracts**: `contracts/webhooks/v1/*.yaml`

**Endpoints**:
- `POST /webhooks/shopify/orders/create` - Shopify order webhook
- `POST /webhooks/stripe/charge/succeeded` - Stripe payment webhook
- `POST /webhooks/paypal/payment/sale/completed` - PayPal payment webhook
- `POST /webhooks/woocommerce/order/created` - WooCommerce order webhook

**Backend Component**: `backend/app/webhooks/` (planned)

**Database Dependencies**:
- `attribution_events` table
- `dead_events` table
- PII guardrail triggers (Layer 2)

**Security Requirements**:
- HMAC signature validation (per `.cursor/rules:481`)
- PII stripping before database write (Layer 1 - B0.4)
- Correlation ID propagation

**Mock Servers**: `docker-compose.yml` - Webhook services on ports 4015-4018

---

### Auth API

**Contract**: `contracts/auth/v1/auth.yaml`

**Endpoints**:
- `POST /api/auth/login` - User authentication
- `POST /api/auth/refresh` - Token refresh
- `POST /api/auth/logout` - Session invalidation

**Backend Component**: `backend/app/auth/` (planned)

**Database Dependencies**:
- `tenants` table (api_key_hash, notification_email)

**Mock Server**: `docker-compose.yml` - Auth service on port 4010

---

### Reconciliation API

**Contract**: `contracts/reconciliation/v1/reconciliation.yaml`

**Endpoints**:
- `GET /api/reconciliation/status` - Get reconciliation status

**Backend Component**: `backend/app/reconciliation/` (planned)

**Database Dependencies**:
- `mv_reconciliation_status` materialized view
- `reconciliation_runs` table

**Mock Server**: `docker-compose.yml` - Reconciliation service on port 4012

---

### Export API

**Contract**: `contracts/export/v1/export.yaml`

**Endpoints**:
- `GET /api/export/revenue` - Export revenue data (CSV/JSON)

**Backend Component**: `backend/app/export/` (planned)

**Database Dependencies**:
- `revenue_ledger` table
- `attribution_allocations` table

**Mock Server**: `docker-compose.yml` - Export service on port 4013

---

### Health API

**Contract**: `contracts/health/v1/health.yaml`

**Endpoints**:
- `GET /api/health` - Health check endpoint

**Backend Component**: `backend/app/health/` (planned)

**Database Dependencies**: None (stateless health check)

**Mock Server**: `docker-compose.yml` - Health service on port 4014

---

## Common Components

**Location**: `contracts/_common/v1/`

**Files**:
- `components.yaml` - Shared schemas, responses, security schemes
- `pagination.yaml` - Pagination parameters (limit, cursor)
- `parameters.yaml` - Common parameters

**Usage**: Referenced via `$ref` in all domain contracts:
- `$ref: '../../_common/v1/components.yaml#/components/responses/Unauthorized'`
- `$ref: '../../_common/v1/pagination.yaml#/components/parameters/limit'`

---

## Contract Versioning

**Current Version**: `v1.0.0`

**Baseline Strategy**: 
- Baselines stored in `contracts/{domain}/baselines/v1.0.0/`
- Active contracts in `contracts/{domain}/v1/`
- Breaking changes require new version (v2.0.0)

**Versioning Policy**:
- **Major** (v1 → v2): Breaking changes (removed endpoints, changed response schemas)
- **Minor** (v1.0 → v1.1): Non-breaking additions (new endpoints, optional fields)
- **Patch** (v1.0.0 → v1.0.1): Documentation-only changes

---

## Client Generation

**Python Client**:
- Generated from: `contracts/{domain}/v1/*.yaml`
- Output: `backend/generated/clients/python/`
- Tool: `openapi-generator-cli`

**TypeScript Client**:
- Generated from: `contracts/{domain}/v1/*.yaml`
- Output: `frontend/generated/clients/typescript/`
- Tool: `openapi-generator-cli`

**Generation Script**: `scripts/generate-models.sh`

**Validation**: All generated clients validated against contract specifications

---

## Breaking Change Detection

**CI Workflow**: `.github/workflows/contract-validation.yml`

**Detection Method**:
1. Compare active contracts (`v1/`) against baselines (`baselines/v1.0.0/`)
2. Detect breaking changes:
   - Removed endpoints
   - Changed response schemas
   - Changed required fields
   - Changed parameter types
3. Fail CI if breaking changes detected without version bump

**Test Protocol**: Intentional breaking change test validates detection

---

## Related Documentation

- **Service Boundaries**: `docs/architecture/service-boundaries.md`
- **Evidence Mapping**: `docs/architecture/evidence-mapping.md`
- **API Evolution**: `docs/architecture/api-evolution.md` (to be created)

