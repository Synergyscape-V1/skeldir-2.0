# Environment Variable Migration Guide
**SDK Migration:** Local Generation → Published Package (`@skeldir/api-client`)

---

## ⚠️ ARCHITECTURE DECISION PENDING

**STATUS:** 🚧 **SCENARIOS SPECULATIVE** - Backend architecture (API Gateway vs Multi-Service) is **UNKNOWN**.

This guide presents **THREE POSSIBLE SCENARIOS** but the actual backend structure must be confirmed before migration.

**REQUIRED ACTION:**
- Coordinate with backend team to confirm URL architecture
- Remove unused scenarios from this guide
- Update environment variables to match confirmed structure

**See:** `docs/forensics/root/PRE_EXECUTION_VALIDATION.md` → Section 6: "Confirm Backend URL Structure"

---

## Current Multi-Service Architecture

The frontend currently connects to **10 separate mock servers** during development:

### Attribution & Core Services
```bash
VITE_ATTRIBUTION_API_URL=http://localhost:4010
VITE_HEALTH_API_URL=http://localhost:4011
VITE_EXPORT_API_URL=http://localhost:4012
VITE_RECONCILIATION_API_URL=http://localhost:4013
VITE_ERRORS_API_URL=http://localhost:4014
VITE_AUTH_API_URL=http://localhost:4015
```

### Webhook Services
```bash
VITE_SHOPIFY_WEBHOOK_URL=http://localhost:4016
VITE_WOOCOMMERCE_WEBHOOK_URL=http://localhost:4017
VITE_STRIPE_WEBHOOK_URL=http://localhost:4018
VITE_PAYPAL_WEBHOOK_URL=http://localhost:4019
```

### Mock Mode Toggle
```bash
VITE_MOCK_MODE=true
```

---

## Backend Architecture Scenarios

The published SDK package (`@skeldir/api-client`) may support different backend architectures. Confirm with backend team which scenario applies:

### Scenario A: API Gateway (Recommended)
**Single entry point** - all services behind unified gateway

```
Frontend → API Gateway (localhost:4000) → Internal Services
                  ↓
         ┌────────┼────────┐
    Attribution  Auth   Export
```

**Environment Variables:**
```bash
# Consolidated base URL
VITE_API_BASE_URL=http://localhost:4000

# Or with API prefix
VITE_API_BASE_URL=http://localhost:4000/api
```

**Published SDK Configuration:**
```typescript
import { Configuration } from '@skeldir/api-client';

const config = new Configuration({
  basePath: import.meta.env.VITE_API_BASE_URL
});

// SDK internally routes:
// attribution.getRevenue() → http://localhost:4000/api/attribution/revenue/realtime
// health.getHealth()       → http://localhost:4000/api/health
// export.exportCsv()       → http://localhost:4000/api/export/csv
```

---

### Scenario B: Service Mesh / Multi-Base URLs
**Multiple entry points** - services on different hosts/ports

```
Frontend → Attribution (4010)
        → Health (4011)
        → Export (4012)
        → etc.
```

**Environment Variables:**
```bash
# Still maintain separate URLs
VITE_ATTRIBUTION_BASE_URL=http://localhost:4010
VITE_HEALTH_BASE_URL=http://localhost:4011
VITE_EXPORT_BASE_URL=http://localhost:4012
VITE_RECONCILIATION_BASE_URL=http://localhost:4013
VITE_ERRORS_BASE_URL=http://localhost:4014
VITE_AUTH_BASE_URL=http://localhost:4015
```

**Published SDK Configuration:**
```typescript
import { Configuration, AttributionApi, HealthApi } from '@skeldir/api-client';

// Separate configs per service
const attributionConfig = new Configuration({
  basePath: import.meta.env.VITE_ATTRIBUTION_BASE_URL
});

const healthConfig = new Configuration({
  basePath: import.meta.env.VITE_HEALTH_BASE_URL
});

export const apiClient = {
  attribution: new AttributionApi(attributionConfig),
  health: new HealthApi(healthConfig),
  // ...
};
```

---

### Scenario C: Hybrid (Likely for Webhooks)
**Core services via Gateway** + **Webhooks on separate endpoints**

```
Frontend → API Gateway (4000) → Attribution, Auth, Export, etc.
        → Webhook Endpoints (4016-4019) → Shopify, Stripe, etc.
```

**Environment Variables:**
```bash
# Core API
VITE_API_BASE_URL=http://localhost:4000

# Webhooks (still separate)
VITE_SHOPIFY_WEBHOOK_URL=http://localhost:4016
VITE_WOOCOMMERCE_WEBHOOK_URL=http://localhost:4017
VITE_STRIPE_WEBHOOK_URL=http://localhost:4018
VITE_PAYPAL_WEBHOOK_URL=http://localhost:4019
```

---

## Migration Strategy

### Step 1: Confirm Backend Architecture

**Questions for Backend Team:**
1. Does backend use an API Gateway (single entry point)?
2. Are all services accessible via single base URL?
3. Do webhooks require separate URLs?
4. What is the base URL structure in development vs production?

### Step 2: Update .env Files

#### If Using API Gateway (Scenario A):

**`.env.development`:**
```bash
# Consolidated API base URL
VITE_API_BASE_URL=http://localhost:4000

# Remove old multi-service URLs
# VITE_ATTRIBUTION_API_URL=... ❌ DELETE
# VITE_HEALTH_API_URL=... ❌ DELETE
# etc.
```

**`.env.production`:**
```bash
VITE_API_BASE_URL=https://api.skeldir.com
```

#### If Using Multi-Base URLs (Scenario B):

**`.env.development`:**
```bash
# Rename variables (remove _API_ for consistency)
VITE_ATTRIBUTION_BASE_URL=http://localhost:4010
VITE_HEALTH_BASE_URL=http://localhost:4011
VITE_EXPORT_BASE_URL=http://localhost:4012
VITE_RECONCILIATION_BASE_URL=http://localhost:4013
VITE_ERRORS_BASE_URL=http://localhost:4014
VITE_AUTH_BASE_URL=http://localhost:4015
VITE_SHOPIFY_WEBHOOK_BASE_URL=http://localhost:4016
VITE_WOOCOMMERCE_WEBHOOK_BASE_URL=http://localhost:4017
VITE_STRIPE_WEBHOOK_BASE_URL=http://localhost:4018
VITE_PAYPAL_WEBHOOK_BASE_URL=http://localhost:4019
```

**`.env.production`:**
```bash
VITE_ATTRIBUTION_BASE_URL=https://attribution.skeldir.com
VITE_HEALTH_BASE_URL=https://health.skeldir.com
# etc.
```

### Step 3: Update SDK Client Configuration

**Scenario A (API Gateway):**

**File:** `client/src/api/client.ts`
```typescript
import { Configuration, AttributionApi, HealthApi } from '@skeldir/api-client';

// Single base URL for all services
const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:4000';

const config = new Configuration({
  basePath: baseUrl,
  credentials: 'include',
  middleware: [/* correlation ID, auth */]
});

export const apiClient = {
  attribution: new AttributionApi(config),
  health: new HealthApi(config),
  export: new ExportApi(config),
  // All services use same base URL
};
```

**Scenario B (Multi-Base URLs):**

**File:** `client/src/api/client.ts`
```typescript
import { Configuration, AttributionApi, HealthApi } from '@skeldir/api-client';

// Helper to create config with middleware
function createConfig(baseUrl: string): Configuration {
  return new Configuration({
    basePath: baseUrl,
    credentials: 'include',
    middleware: [/* correlation ID, auth */]
  });
}

// Separate base URLs per service
export const apiClient = {
  attribution: new AttributionApi(
    createConfig(import.meta.env.VITE_ATTRIBUTION_BASE_URL || 'http://localhost:4010')
  ),
  health: new HealthApi(
    createConfig(import.meta.env.VITE_HEALTH_BASE_URL || 'http://localhost:4011')
  ),
  export: new ExportApi(
    createConfig(import.meta.env.VITE_EXPORT_BASE_URL || 'http://localhost:4012')
  ),
  // ...
};
```

### Step 4: Remove Old Environment References

**Files to update:**
1. `client/src/lib/sdk-client.ts` - Delete (will be replaced)
2. `client/src/api/sdk-client.ts` - Delete (uses old URLs)
3. `.env.example` - Update with new structure
4. `.env.mock` - Update with new structure

---

## Mock Server Configuration

### Current Prism Mock Setup

**File:** `docker-compose.mock.yml`
```yaml
services:
  mock-attribution:
    image: stoplight/prism:latest
    ports:
      - "4010:4000"
    volumes:
      - ./docs/api/contracts/attribution.yaml:/contracts/attribution.yaml
    command: mock -h 0.0.0.0 /contracts/attribution.yaml

  mock-health:
    ports:
      - "4011:4000"
    # ...
```

### Migration Options

**Option 1: API Gateway Mock (Recommended)**
Use a single Prism instance with combined OpenAPI spec:

```yaml
services:
  mock-api-gateway:
    image: stoplight/prism:latest
    ports:
      - "4000:4000"  # Single entry point
    volumes:
      - ./docs/api/contracts/combined.yaml:/contracts/api.yaml
    command: mock -h 0.0.0.0 /contracts/api.yaml
```

**Option 2: Keep Separate Mocks**
Maintain current multi-port setup for development

---

## Environment Variable Reference

### Development (Mock Servers)

**API Gateway:**
```bash
VITE_API_BASE_URL=http://localhost:4000
```

**Multi-Service:**
```bash
VITE_ATTRIBUTION_BASE_URL=http://localhost:4010
VITE_HEALTH_BASE_URL=http://localhost:4011
VITE_EXPORT_BASE_URL=http://localhost:4012
VITE_RECONCILIATION_BASE_URL=http://localhost:4013
VITE_ERRORS_BASE_URL=http://localhost:4014
VITE_AUTH_BASE_URL=http://localhost:4015
VITE_SHOPIFY_WEBHOOK_BASE_URL=http://localhost:4016
VITE_WOOCOMMERCE_WEBHOOK_BASE_URL=http://localhost:4017
VITE_STRIPE_WEBHOOK_BASE_URL=http://localhost:4018
VITE_PAYPAL_WEBHOOK_BASE_URL=http://localhost:4019
```

### Staging Environment

**API Gateway:**
```bash
VITE_API_BASE_URL=https://api-staging.skeldir.com
```

**Multi-Service:**
```bash
VITE_ATTRIBUTION_BASE_URL=https://attribution-staging.skeldir.com
VITE_HEALTH_BASE_URL=https://health-staging.skeldir.com
# etc.
```

### Production Environment

**API Gateway:**
```bash
VITE_API_BASE_URL=https://api.skeldir.com
```

**Multi-Service:**
```bash
VITE_ATTRIBUTION_BASE_URL=https://attribution.skeldir.com
VITE_HEALTH_BASE_URL=https://health.skeldir.com
# etc.
```

---

## Verification Checklist

After environment migration:

- [ ] All environment variables are prefixed with `VITE_`
- [ ] `.env.example` updated with new structure
- [ ] `.env.development` configured for local mock servers
- [ ] `.env.staging` configured (if applicable)
- [ ] `.env.production` configured
- [ ] Old `*_API_URL` variables removed
- [ ] SDK client reads correct environment variables
- [ ] Application builds successfully: `npm run build`
- [ ] Application runs in development: `npm run dev`
- [ ] Health check endpoint accessible
- [ ] All services respond correctly

---

## Rollback

If environment migration fails:

```bash
# Restore old environment files
git checkout HEAD -- .env.example .env.development

# Restore old SDK client
git checkout HEAD -- client/src/lib/sdk-client.ts

# Restart development server
npm run dev
```

---

## Questions for Backend Team

Before finalizing environment strategy, confirm:

1. **Architecture:** API Gateway or multi-service deployment?
2. **URL structure:** What is the base URL pattern?
3. **Webhooks:** Are webhook endpoints consolidated or separate?
4. **Environment parity:** Do all environments (dev/staging/prod) use same URL structure?
5. **CORS configuration:** Are all base URLs whitelisted for CORS?

---

**Status:** Preparation complete  
**Next Step:** Coordinate with backend team on architecture decision  
**Blocker:** Awaiting `@skeldir/api-client` package publication

---

**Updated:** 2025-11-01
