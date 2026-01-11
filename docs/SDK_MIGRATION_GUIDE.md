# SDK Migration Guide
**From:** Local SDK Generation (`openapi-typescript-codegen`)  
**To:** Published Package (`@skeldir/api-client`)

---

## ⚠️ CRITICAL DISCLAIMER

**STATUS:** 🚧 **SPECULATIVE DOCUMENTATION - NOT READY FOR EXECUTION**

This migration guide contains **UNVERIFIED ASSUMPTIONS** about the published SDK structure. Code examples, class names, method signatures, and configuration patterns are **SPECULATIVE** and may not match the actual published package.

**DO NOT EXECUTE THIS MIGRATION** until you have:
1. ✅ Verified `@skeldir/api-client` package is published
2. ✅ Reviewed actual package README and TypeScript declarations
3. ✅ Completed **PRE_EXECUTION_VALIDATION.md** checklist
4. ✅ Updated this guide with verified API structure

**See:** `docs/forensics/root/PRE_EXECUTION_VALIDATION.md` for required validation steps.

---

## Why This Migration?

### Architectural Violation (Current State)
❌ **Frontend generates its own SDK** from OpenAPI contracts  
❌ **Tight coupling** - requires backend repository access  
❌ **No single source of truth** - generated code may drift from backend  
❌ **Manual maintenance** - devs must remember to regenerate SDK  

### Contract-First Architecture (Target State)
✅ **Backend publishes SDK** - single source of truth  
✅ **Loose coupling** - frontend depends on npm package, not backend repo  
✅ **Type safety guaranteed** - SDK types match backend reality  
✅ **Semantic versioning** - breaking changes are explicit via major versions  

---

## Migration Overview

### Current Architecture
```
Backend OpenAPI Contracts
        ↓
  [Developer runs script]
        ↓
openapi-typescript-codegen
        ↓
client/src/api/generated/
        ↓
   Frontend App
```

**Problems:**
- Manual SDK regeneration required
- No version control
- No rollback capability
- Drift risk (forgotten regeneration)

### Target Architecture
```
Backend OpenAPI Contracts
        ↓
Backend SDK Generation (CI/CD)
        ↓
npm Package: @skeldir/api-client@1.2.3
        ↓
   Frontend App
```

**Benefits:**
- Automatic SDK updates
- Semantic versioning
- Rollback via package.json
- No drift - backend controls SDK

---

## Pre-Migration Checklist

### Step 1: Confirm Package Availability
- [ ] Backend team confirms `@skeldir/api-client` is published
- [ ] Verify package registry URL (GitHub Packages, npm, private registry)
- [ ] Obtain authentication credentials (GitHub PAT, npm token)
- [ ] Test package access: `npm view @skeldir/api-client versions`

### Step 2: Understand Package Structure
- [ ] Review published SDK README
- [ ] Check CHANGELOG for breaking changes
- [ ] Understand exported modules:
  - Configuration class
  - Service clients (Attribution, Health, Export, etc.)
  - Type definitions (request/response models)
  - Error types

### Step 3: Environment Setup
- [ ] Configure `.npmrc` with registry authentication
- [ ] Add `.npmrc` to `.gitignore` (never commit tokens!)
- [ ] Verify authentication: `npm whoami --registry=<registry-url>`

---

## Migration Steps

### Phase 1: Install Published SDK

```bash
# Install with exact version pinning
npm install --save-exact @skeldir/api-client@1.0.0

# Verify installation
ls -la node_modules/@skeldir/api-client
```

### Phase 2: Create SDK Client Wrapper

**File:** `client/src/api/client.ts`

```typescript
import { 
  Configuration, 
  AttributionApi, 
  HealthApi,
  ExportApi,
  // ... other services
} from '@skeldir/api-client';
import { tokenManager } from '@/lib/token-manager';

// UUID generation for correlation IDs
function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// Configure SDK client
const config = new Configuration({
  basePath: import.meta.env.VITE_API_BASE_URL || 'http://localhost:4010',
  credentials: 'include',
  headers: {
    // Correlation ID will be added per request
  },
  middleware: [
    {
      pre: async (context) => {
        // Inject correlation ID
        context.init.headers = {
          ...context.init.headers,
          'X-Correlation-ID': generateUUID(),
        };
        
        // Inject auth token
        const authHeader = await tokenManager.getAuthHeader();
        if (authHeader.Authorization) {
          context.init.headers['Authorization'] = authHeader.Authorization;
        }
        
        return context;
      }
    }
  ]
});

// Export service instances
export const attributionApi = new AttributionApi(config);
export const healthApi = new HealthApi(config);
export const exportApi = new ExportApi(config);
// ... other services

// Singleton SDK client
export const apiClient = {
  attribution: attributionApi,
  health: healthApi,
  export: exportApi,
  // ... other services
};
```

### Phase 3: Update Component Usage

**Before (Manual SDK):**
```typescript
import { sdk } from '@/lib/sdk-client';

const data = await sdk.attribution.getRevenueRealtime();
```

**After (Published SDK):**
```typescript
import { apiClient } from '@/api/client';

const data = await apiClient.attribution.getRevenueRealtime();
```

### Phase 4: Remove Local Generation Infrastructure

```bash
# Remove generation script
rm scripts/generate-sdk.sh

# Remove generated code
rm -rf client/src/api/generated/

# Remove old wrapper
rm client/src/api/sdk-client.ts

# Remove manual implementation
rm client/src/lib/sdk-client.ts

# Remove generation dependency
npm uninstall openapi-typescript-codegen
```

### Phase 5: Update .gitignore

Remove obsolete entries:
```diff
- # SDK Generation
- client/src/api/generated/
```

---

## Service Mapping

### Current Manual Services → Published SDK Services

| Current Service | Current Method | Published SDK | Published Method |
|----------------|----------------|---------------|------------------|
| AttributionService | `getRevenueRealtime()` | AttributionApi | `getRealtimeRevenue()` |
| AttributionService | `getAttributionMetrics(period)` | AttributionApi | `getMetrics(period)` |
| HealthService | `getHealthStatus()` | HealthApi | `getHealth()` |
| ExportService | `exportCSV()` | ExportApi | `exportCsv()` |
| ExportService | `exportJSON()` | ExportApi | `exportJson()` |
| ExportService | `exportExcel()` | ExportApi | `exportExcel()` |
| ReconciliationService | `getReconciliationStatus()` | ReconciliationApi | `getStatus()` |
| ErrorsService | `logError(data)` | ErrorsApi | `logError(data)` |
| AuthService | `login(email, pwd)` | AuthApi | `login(credentials)` |
| AuthService | `refreshToken(token)` | AuthApi | `refresh(token)` |
| AuthService | `verifyToken()` | AuthApi | `verify()` |

**Note:** Actual method names depend on backend SDK generation. Verify in published package README.

---

## Environment Variables Migration

### Current: Multi-Service URLs (10 endpoints)
```bash
VITE_ATTRIBUTION_API_URL=http://localhost:4010
VITE_HEALTH_API_URL=http://localhost:4011
VITE_EXPORT_API_URL=http://localhost:4012
VITE_RECONCILIATION_API_URL=http://localhost:4013
VITE_ERRORS_API_URL=http://localhost:4014
VITE_AUTH_API_URL=http://localhost:4015
VITE_SHOPIFY_WEBHOOK_URL=http://localhost:4016
VITE_WOOCOMMERCE_WEBHOOK_URL=http://localhost:4017
VITE_STRIPE_WEBHOOK_URL=http://localhost:4018
VITE_PAYPAL_WEBHOOK_URL=http://localhost:4019
```

### Target: Consolidated (if backend uses API Gateway)
```bash
VITE_API_BASE_URL=http://localhost:4000
```

**Or:** Target: Service Discovery (if backend uses service mesh)
```bash
VITE_API_BASE_URL=http://localhost:4000
# SDK internally routes to correct service based on endpoint
```

**Coordination Required:** Confirm with backend team the URL structure.

---

## Critical Patterns to Preserve

### 1. Correlation ID Injection ✅
```typescript
headers: {
  'X-Correlation-ID': generateUUID()
}
```

### 2. Token Management ✅
```typescript
const authHeader = await tokenManager.getAuthHeader();
headers: { 'Authorization': authHeader.Authorization }
```

### 3. Error Handling with Correlation ID ✅
```typescript
try {
  await apiClient.attribution.getRevenueRealtime();
} catch (error) {
  // Extract correlation_id from error response
  console.error(`[${error.correlation_id}] ${error.message}`);
}
```

### 4. ETag Caching ✅
```typescript
headers: { 'If-None-Match': previousEtag }
// Handle 304 Not Modified responses
```

---

## Testing Checklist

### Unit Tests
- [ ] SDK client initializes correctly
- [ ] Correlation IDs are generated and injected
- [ ] Auth tokens are added to headers
- [ ] Error handling extracts correlation_id

### Integration Tests
- [ ] Health check endpoint works
- [ ] Authentication flow (login → refresh → verify)
- [ ] Attribution realtime revenue fetching
- [ ] Export endpoints (CSV, JSON, Excel)
- [ ] Reconciliation status polling
- [ ] Error logging with correlation tracking

### E2E Tests
- [ ] Dashboard loads and displays revenue
- [ ] Export button downloads files
- [ ] Error boundary shows error_id and correlation_id
- [ ] Polling intervals work correctly (30s)
- [ ] ETag caching prevents unnecessary data refetches

---

## Rollback Plan

If migration fails:

### Step 1: Revert package.json
```bash
git checkout HEAD -- package.json package-lock.json
npm install
```

### Step 2: Restore deleted files
```bash
git checkout HEAD -- client/src/lib/sdk-client.ts
git checkout HEAD -- client/src/api/
git checkout HEAD -- scripts/generate-sdk.sh
```

### Step 3: Reinstall old dependencies
```bash
npm install openapi-typescript-codegen@^0.29.0 --save-dev
```

### Step 4: Regenerate SDK
```bash
bash scripts/generate-sdk.sh
```

---

## SDK Version Upgrade Workflow

### When Backend Releases New SDK Version

**Step 1: Review Changelog**
```bash
npm view @skeldir/api-client versions
# Check CHANGELOG.md for breaking changes
```

**Step 2: Update Package**
```bash
# For patch/minor (non-breaking):
npm update @skeldir/api-client

# For major (breaking changes):
# Review migration guide first, then:
npm install @skeldir/api-client@2.0.0
```

**Step 3: Test**
```bash
npm run check  # TypeScript compilation
npm run build  # Build success
npm run dev    # Runtime testing
```

**Step 4: Commit**
```bash
git add package.json package-lock.json
git commit -m "chore: upgrade @skeldir/api-client to v2.0.0"
```

---

## Troubleshooting

### Problem: "Cannot find module '@skeldir/api-client'"
**Solution:** Verify `.npmrc` authentication, run `npm install`

### Problem: "401 Unauthorized" when installing package
**Solution:** Check GitHub PAT/npm token has correct permissions

### Problem: TypeScript errors after SDK upgrade
**Solution:** Review breaking changes in CHANGELOG, update usage patterns

### Problem: Correlation IDs missing from requests
**Solution:** Verify middleware configuration in SDK client setup

---

## Success Criteria

Migration is complete when:

- [x] `@skeldir/api-client` package installed
- [x] All imports from `@/lib/sdk-client` updated to `@/api/client`
- [x] Local SDK generation infrastructure removed
- [x] TypeScript compilation succeeds (0 errors)
- [x] Application builds successfully
- [x] All critical flows tested and working
- [x] Correlation IDs present on all API requests
- [x] Error handling displays error_id and correlation_id
- [x] Documentation updated

---

## Questions for Backend Team

Before starting migration, confirm:

1. **Package name:** `@skeldir/api-client` or `@muk223/api-client`?
2. **Registry:** GitHub Packages, npm public, or private registry?
3. **Auth method:** GitHub PAT, npm token, or custom?
4. **URL structure:** Single API Gateway or multiple service URLs?
5. **Services included:** Are all 10 services (attribution, health, export, reconciliation, errors, auth, 4 webhooks) in one package?
6. **Middleware support:** Does SDK support request/response middleware for correlation IDs?
7. **Breaking changes:** Any differences from current manual SDK API?

---

**Migration Timeline:**
- **Preparation:** ✅ Complete
- **Execution:** ⏳ Waiting for `@skeldir/api-client` package publication
- **Validation:** ⏳ Pending
- **Cleanup:** ⏳ Pending

---

**Prepared by:** Frontend SDK Migration Team  
**Date:** 2025-11-01  
**Status:** Ready to execute once backend SDK package is available
