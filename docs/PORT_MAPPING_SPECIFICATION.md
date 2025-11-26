# Port Mapping Specification - Contract Compliance

## Authoritative Port Allocation

**Source of Truth**: Local OpenAPI contracts + SDK client implementation

### Confirmed Port Mappings (Evidence-Based)

| Service | Port | Contract File | SDK Usage | Status |
|---------|------|---------------|-----------|--------|
| **Attribution** | **4010** | `attribution.yaml` | ✅ `sdk-client.ts:29` | ✅ CONFIRMED |
| **Health** | **4011** | `health.yaml` | ✅ `sdk-client.ts:30` | ✅ CONFIRMED |
| **Export** | **4012** | `export.yaml` | ✅ `sdk-client.ts:31` | ✅ CONFIRMED |
| **Reconciliation** | **4013** | `reconciliation.yaml` | ✅ `sdk-client.ts:32` | ✅ CONFIRMED |
| **Errors** | **4014** | `errors.yaml` | ✅ `sdk-client.ts:33` | ✅ CONFIRMED |
| **Auth** | **4015** | `auth.yaml` | ✅ `sdk-client.ts:34` | ✅ CONFIRMED |

### Webhook Services (Inbound Only - No Frontend Calls)

| Service | Port | Contract File | Frontend Responsibility |
|---------|------|---------------|------------------------|
| Shopify Webhooks | 4016 | `webhooks/shopify.yaml` | ❌ None (inbound only) |
| WooCommerce Webhooks | 4017 | `webhooks/woocommerce.yaml` | ❌ None (inbound only) |
| Stripe Webhooks | 4018 | `webhooks/stripe.yaml` | ❌ None (inbound only) |
| PayPal Webhooks | 4019 | `webhooks/paypal.yaml` | ❌ None (inbound only) |

## Evidence Chain

### 1. Contract Definitions
```yaml
# docs/api/contracts/attribution.yaml
servers:
  - url: http://localhost:4010

# docs/api/contracts/health.yaml  
servers:
  - url: http://localhost:4011

# ... (all contracts define their ports)
```

### 2. SDK Client Implementation
```typescript
// client/src/lib/sdk-client.ts lines 29-34
const API_ENDPOINTS = {
  attribution: import.meta.env.VITE_ATTRIBUTION_API_URL || 'http://localhost:4010',
  health: import.meta.env.VITE_HEALTH_API_URL || 'http://localhost:4011',
  export: import.meta.env.VITE_EXPORT_API_URL || 'http://localhost:4012',
  reconciliation: import.meta.env.VITE_RECONCILIATION_API_URL || 'http://localhost:4013',
  errors: import.meta.env.VITE_ERRORS_API_URL || 'http://localhost:4014',
  auth: import.meta.env.VITE_AUTH_API_URL || 'http://localhost:4015',
}
```

### 3. Generated SDK Code
```typescript
// client/src/api/generated/core/OpenAPI.ts line 23
BASE: 'http://localhost:4010' // Attribution service
```

## Discrepancy Resolution

### Strategy Document Specification (REJECTED)
The attached integration strategy documents specified different ports:
- Auth: 4010 ❌
- Attribution: 4011 ❌
- Reconciliation: 4012 ❌
- Export: 4013 ❌
- Health: 4014 ❌

**Decision**: These mappings are **REJECTED** because:
1. They contradict existing contract definitions
2. They contradict SDK client implementation  
3. They contradict generated code
4. Changing would break existing integration
5. No empirical evidence supports them

**Rationale**: The strategy documents were theoretical/planning documents. The actual implementation (contracts + code) is the source of truth.

## Environment Variable Requirements

### Required .env Variables

```bash
# Service API Endpoints (Development - Prism Mock Servers)
VITE_ATTRIBUTION_API_URL=http://localhost:4010
VITE_HEALTH_API_URL=http://localhost:4011
VITE_EXPORT_API_URL=http://localhost:4012
VITE_RECONCILIATION_API_URL=http://localhost:4013
VITE_ERRORS_API_URL=http://localhost:4014
VITE_AUTH_API_URL=http://localhost:4015

# Webhook URLs (Optional - Frontend doesn't call these)
# VITE_SHOPIFY_WEBHOOK_URL=http://localhost:4016
# VITE_WOOCOMMERCE_WEBHOOK_URL=http://localhost:4017
# VITE_STRIPE_WEBHOOK_URL=http://localhost:4018
# VITE_PAYPAL_WEBHOOK_URL=http://localhost:4019
```

### Current Environment Status

| Environment File | Status | Issues |
|-----------------|--------|--------|
| `.env.local` | ⚠️ Incomplete | Only has `VITE_API_URL=/api` |
| `.env.mock` | ⚠️ Incomplete | Only has `VITE_API_BASE_URL` |
| `.env.development` | ❌ Missing | Needs creation |

## Action Items

1. ✅ **Port allocation confirmed** - Use 4010-4015 as specified
2. ⏳ **Create `.env.development`** with all required variables
3. ⏳ **Update `.env.mock`** with service-specific URLs
4. ⏳ **Update startup scripts** to use confirmed ports
5. ⏳ **Document webhook exclusion** - frontend never calls 4016-4019

## Compliance Status

- ✅ Contracts define correct ports
- ✅ SDK client uses correct ports  
- ✅ Generated code uses correct ports
- ⚠️ Environment variables incomplete
- ✅ Startup scripts use correct ports

## References

- SDK Client: `client/src/lib/sdk-client.ts`
- Contracts: `docs/api/contracts/*.yaml`
- Startup Script: `scripts/start-mock-servers.sh`
- Empirical Spike: `docs/EMPIRICAL_SPIKE_FINDINGS.md`
