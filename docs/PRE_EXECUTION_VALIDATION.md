# Pre-Execution Validation Checklist
**CRITICAL:** Complete this checklist BEFORE executing the SDK migration.

---

## ⚠️ BLOCKER STATUS

**Current State:** ❌ **CANNOT EXECUTE MIGRATION**  
**Reason:** `@skeldir/api-client` package not published yet  
**Blocking Issues:** Backend P0 blockers #3.3 and #3.4

---

## Package Availability Verification

### 1. Confirm Package Exists
```bash
# Try to view package metadata
npm view @skeldir/api-client versions

# Expected: List of published versions (e.g., 1.0.0, 1.0.1, ...)
# If 404: Package not published yet - STOP HERE
```

**Status:** ⏸️ Pending  
**Blocker:** Package does not exist yet

---

### 2. Obtain Package Documentation

Once package is published, obtain:
- [ ] README.md from npm package or GitHub repository
- [ ] CHANGELOG.md showing version history
- [ ] TypeScript declaration files (.d.ts) or API documentation
- [ ] Example usage code from backend team

**Critical Information Needed:**
- Exported module names (AttributionApi? AttributionService? AttributionClient?)
- Configuration class name and constructor parameters
- Middleware/interceptor pattern (if any)
- Error class names and structure

---

## API Structure Validation

### 3. Verify Exported Modules

**Speculative Assumptions in Current Docs:**
```typescript
// ⚠️ UNVERIFIED - May be incorrect
import { 
  Configuration,
  AttributionApi,
  HealthApi,
  ExportApi,
  // ...
} from '@skeldir/api-client';
```

**Validation Steps:**
1. Install package: `npm install @skeldir/api-client@latest`
2. Inspect exports: `node -e "console.log(Object.keys(require('@skeldir/api-client')))"`
3. Check TypeScript types: Open `node_modules/@skeldir/api-client/index.d.ts`

**Record Actual Exports:**
```typescript
// ✅ VERIFIED EXPORTS (fill in after package inspection):
import {
  // TODO: List actual exported classes/types
} from '@skeldir/api-client';
```

**Status:** ⏸️ Pending package publication

---

### 4. Verify Service Method Signatures

**Speculative Assumptions in Current Docs:**

| Assumed Class | Assumed Method | Actual Class | Actual Method |
|---------------|---------------|--------------|---------------|
| `AttributionApi` | `getRealtimeRevenue()` | ❓ TBD | ❓ TBD |
| `HealthApi` | `getHealth()` | ❓ TBD | ❓ TBD |
| `ExportApi` | `exportCsv()` | ❓ TBD | ❓ TBD |
| `ReconciliationApi` | `getStatus()` | ❓ TBD | ❓ TBD |
| `ErrorsApi` | `logError(data)` | ❓ TBD | ❓ TBD |
| `AuthApi` | `login(credentials)` | ❓ TBD | ❓ TBD |

**Validation Steps:**
1. Review package README for method examples
2. Inspect TypeScript declaration files
3. Test each service endpoint with mock data

**Status:** ⏸️ Pending package publication

---

## Configuration Pattern Validation

### 5. Verify SDK Configuration Hooks

**Speculative Assumption:**
```typescript
// ⚠️ UNVERIFIED - May not exist
const config = new Configuration({
  basePath: 'http://localhost:4000',
  credentials: 'include',
  middleware: [
    {
      pre: async (context) => {
        // Inject correlation ID and auth token
      }
    }
  ]
});
```

**Questions to Answer:**
- [ ] Does SDK export a `Configuration` class?
- [ ] Does it support middleware/interceptors?
- [ ] How are headers injected? (middleware, config.headers, per-request?)
- [ ] How are credentials configured? (credentials prop, withCredentials, etc.?)
- [ ] Can correlation IDs be injected globally or only per-request?

**Validation Steps:**
1. Read package README section on configuration
2. Check TypeScript types for `Configuration` interface
3. Test header injection with mock server
4. Verify correlation ID appears in request headers

**Status:** ⏸️ Pending package publication

---

## Architecture Decision Validation

### 6. Confirm Backend URL Structure

**Current Unknown:** Does backend use API Gateway or multi-service architecture?

**Three Possible Scenarios:**

**Scenario A: API Gateway (Single Base URL)**
```typescript
const config = new Configuration({
  basePath: 'http://localhost:4000'  // All services here
});
```

**Scenario B: Multi-Service (Separate Base URLs)**
```typescript
const attributionConfig = new Configuration({
  basePath: 'http://localhost:4010'
});
const healthConfig = new Configuration({
  basePath: 'http://localhost:4011'
});
```

**Scenario C: Hybrid (Core API + Separate Webhooks)**
```typescript
const coreConfig = new Configuration({
  basePath: 'http://localhost:4000'  // Attribution, health, export, etc.
});
const webhookConfig = new Configuration({
  basePath: 'http://localhost:4016'  // Shopify, Stripe, etc.
});
```

**Questions for Backend Team:**
- [ ] Which architecture does backend use?
- [ ] Are all 10 services in ONE published package?
- [ ] What is the base URL structure?
- [ ] How do webhooks fit into the architecture?

**Status:** ⏸️ Pending backend team confirmation

---

## Error Handling Validation

### 7. Verify Error Structure

**Speculative Assumption:**
```typescript
// ⚠️ UNVERIFIED
try {
  await api.attribution.getRealtimeRevenue();
} catch (error) {
  if (error instanceof ApiException) {
    console.error(error.correlationId);  // May not exist
    console.error(error.errorId);        // May not exist
  }
}
```

**Questions to Answer:**
- [ ] What error class does SDK throw? (ApiException? ApiError? FetchError?)
- [ ] Does error object include `correlationId` property?
- [ ] Does error object include `errorId` property?
- [ ] Does error object include `statusCode` property?
- [ ] How are error details structured?

**Validation Steps:**
1. Review error types in package TypeScript declarations
2. Trigger intentional error with mock server
3. Inspect error object structure
4. Verify correlation_id and error_id extraction

**Status:** ⏸️ Pending package publication

---

## Token Management Validation

### 8. Verify Authentication Pattern

**Current Pattern:**
```typescript
// Uses tokenManager from @/lib/token-manager
const authHeader = await tokenManager.getAuthHeader();
// Returns: { Authorization: 'Bearer <token>' }
```

**Questions to Answer:**
- [ ] How does SDK accept auth tokens? (per-request header, global config, middleware?)
- [ ] Does SDK support async token resolution?
- [ ] Can tokens be refreshed automatically by SDK?
- [ ] What happens when token is invalid/expired?

**Validation Steps:**
1. Test SDK with valid JWT token
2. Test SDK with expired token (expect 401)
3. Test SDK with missing token (expect 401 or 403)
4. Verify token refresh flow works

**Status:** ⏸️ Pending package publication

---

## Service Coverage Validation

### 9. Verify All Services Included

**Required Services (10 total):**
- [ ] Attribution Service
- [ ] Health Service
- [ ] Export Service
- [ ] Reconciliation Service
- [ ] Errors Service
- [ ] Auth Service
- [ ] Shopify Webhook Service
- [ ] WooCommerce Webhook Service
- [ ] Stripe Webhook Service
- [ ] PayPal Webhook Service

**Validation:**
Check if published SDK includes ALL services or only a subset.

**If Subset:** Migration cannot proceed until all services are published.

**Status:** ⏸️ Pending package publication

---

## Registry Authentication Validation

### 10. Configure Package Registry Access

**Questions for Backend Team:**
- [ ] What registry hosts the package? (GitHub Packages, npm, private registry)
- [ ] What authentication method? (GitHub PAT, npm token, other)
- [ ] What permissions/scopes are required?

**Validation Steps:**
1. Configure .npmrc with registry and auth token
2. Test authentication: `npm whoami --registry=<registry-url>`
3. Test package access: `npm view @skeldir/api-client`
4. Test package install: `npm install @skeldir/api-client`

**Status:** ⏸️ Pending backend team credentials

---

## Migration Readiness Checklist

**Pre-Execution Requirements:**

### Package Availability
- [ ] Package published to registry
- [ ] Registry authentication configured
- [ ] Package README and CHANGELOG reviewed

### API Structure Verified
- [ ] Exported modules documented
- [ ] Service method signatures confirmed
- [ ] Request/response types documented

### Configuration Verified
- [ ] Configuration class/interface documented
- [ ] Middleware/interceptor pattern confirmed
- [ ] Header injection method verified
- [ ] Credentials configuration confirmed

### Architecture Confirmed
- [ ] Backend URL structure decided (Gateway vs Multi-service)
- [ ] Environment variables aligned
- [ ] All 10 services included in package

### Integration Patterns Verified
- [ ] Correlation ID injection tested
- [ ] Token management integration tested
- [ ] Error handling tested (correlation_id, error_id extraction)
- [ ] ETag caching pattern verified

---

## Execution Gate

**ONLY PROCEED WITH MIGRATION WHEN:**
✅ All 10 checklist items above are verified  
✅ Actual SDK API documented (not speculative)  
✅ Test plan created based on real SDK structure  
✅ Backend team confirms migration-ready

**Current Status:** ❌ **NOT READY**  
**Blockers:** Package not published, API structure unknown

---

## Update Migration Documentation

Once all validation is complete:

### 1. Update SDK_MIGRATION_GUIDE.md
Replace all speculative code with verified examples:
```diff
- // ⚠️ SPECULATIVE
- import { AttributionApi } from '@skeldir/api-client';

+ // ✅ VERIFIED
+ import { ActualExportedClass } from '@skeldir/api-client';
```

### 2. Update SDK_SERVICE_MAPPING.md
Fill in actual method names and signatures

### 3. Update ENVIRONMENT_MIGRATION.md
Remove unused architecture scenarios, keep only confirmed one

### 4. Create Migration Test Plan
Document test cases based on real SDK behavior

---

**Last Updated:** 2025-11-01  
**Status:** Awaiting package publication  
**Next Action:** Coordinate with backend team on publication timeline
