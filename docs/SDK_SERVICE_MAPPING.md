# SDK Service Mapping Reference
**From:** Manual SDK Implementation (`client/src/lib/sdk-client.ts`)  
**To:** Published SDK Package (`@skeldir/api-client`)

---

## ⚠️ SPECULATIVE MAPPING - REQUIRES VERIFICATION

**STATUS:** 🚧 **DRAFT** - Class names, method signatures, and types shown below are **ASSUMED** and may not match the actual published SDK.

**REQUIRED BEFORE USE:**
1. Install published package: `npm install @skeldir/api-client`
2. Inspect actual exports and TypeScript types
3. Update this mapping with verified API structure

**See:** `docs/PRE_EXECUTION_VALIDATION.md` → Section 4: "Verify Service Method Signatures"

---

## Service Inventory

### Current Manual SDK Structure

The current implementation has **10 service classes** with the following methods:

---

## 1. AttributionService
**Base URL:** `http://localhost:4010`

| Method | Endpoint | Return Type | Description |
|--------|----------|-------------|-------------|
| `getRevenueRealtime()` | `GET /api/attribution/revenue/realtime` | `Promise<RealtimeRevenueData>` | Fetch real-time revenue counter |
| `getAttributionMetrics(period: string)` | `GET /api/attribution/metrics?period={period}` | `Promise<MetricsData>` | Get attribution metrics for period |

**Expected Published SDK:**
```typescript
import { AttributionApi } from '@skeldir/api-client';

const attribution = new AttributionApi(config);
await attribution.getRealtimeRevenue(); // Correlation ID injected automatically
await attribution.getMetrics({ period: '30d' });
```

---

## 2. HealthService
**Base URL:** `http://localhost:4011`

| Method | Endpoint | Return Type | Description |
|--------|----------|-------------|-------------|
| `getHealthStatus()` | `GET /api/health` | `Promise<HealthStatus>` | Check backend service health |

**Expected Published SDK:**
```typescript
import { HealthApi } from '@skeldir/api-client';

const health = new HealthApi(config);
await health.getHealth();
```

---

## 3. ExportService
**Base URL:** `http://localhost:4012`

| Method | Endpoint | Return Type | Description |
|--------|----------|-------------|-------------|
| `exportCSV()` | `GET /api/export/csv` | `Promise<Blob>` | Export data as CSV |
| `exportJSON()` | `GET /api/export/json` | `Promise<object>` | Export data as JSON |
| `exportExcel()` | `GET /api/export/excel` | `Promise<Blob>` | Export data as Excel |

**Expected Published SDK:**
```typescript
import { ExportApi } from '@skeldir/api-client';

const exportApi = new ExportApi(config);
const csvBlob = await exportApi.exportCsv();
const jsonData = await exportApi.exportJson();
const excelBlob = await exportApi.exportExcel();
```

---

## 4. ReconciliationService
**Base URL:** `http://localhost:4013`

| Method | Endpoint | Return Type | Description |
|--------|----------|-------------|-------------|
| `getReconciliationStatus()` | `GET /api/reconciliation/status` | `Promise<ReconciliationStatus>` | Get reconciliation job status |

**Expected Published SDK:**
```typescript
import { ReconciliationApi } from '@skeldir/api-client';

const reconciliation = new ReconciliationApi(config);
await reconciliation.getStatus();
```

---

## 5. ErrorsService
**Base URL:** `http://localhost:4014`

| Method | Endpoint | Return Type | Description |
|--------|----------|-------------|-------------|
| `logError(errorData)` | `POST /api/errors/log` | `Promise<LogResponse>` | Log frontend error to backend |

**Current Request Schema:**
```typescript
{
  error_message: string;
  stack_trace: string;
  user_context: {
    user_id?: string;
    session_id?: string;
    url: string;
    user_agent: string;
  };
  timestamp: string;
}
```

**Expected Published SDK:**
```typescript
import { ErrorsApi, ErrorLogRequest } from '@skeldir/api-client';

const errors = new ErrorsApi(config);
const request: ErrorLogRequest = {
  errorMessage: 'Frontend error occurred',
  stackTrace: error.stack,
  userContext: { /* ... */ },
  timestamp: new Date().toISOString()
};
await errors.logError(request);
```

---

## 6. AuthService
**Base URL:** `http://localhost:4015`

| Method | Endpoint | Return Type | Description |
|--------|----------|-------------|-------------|
| `login(email, password)` | `POST /api/auth/login` | `Promise<AuthResponse>` | Authenticate user |
| `refreshToken(refreshToken)` | `POST /api/auth/refresh` | `Promise<AuthResponse>` | Refresh JWT token |
| `verifyToken()` | `GET /api/auth/verify` | `Promise<VerifyResponse>` | Verify current token |

**Current Request Schemas:**

**Login:**
```typescript
{
  email: string;
  password: string;
}
```

**Refresh:**
```typescript
{
  refresh_token: string;
}
```

**Expected Published SDK:**
```typescript
import { AuthApi, LoginRequest, RefreshRequest } from '@skeldir/api-client';

const auth = new AuthApi(config);

// Login
const loginReq: LoginRequest = { email: 'user@example.com', password: 'secret' };
const authResponse = await auth.login(loginReq);

// Refresh
const refreshReq: RefreshRequest = { refreshToken: 'xyz...' };
const newTokens = await auth.refresh(refreshReq);

// Verify
const verifyResponse = await auth.verify();
```

---

## 7. ShopifyWebhookService
**Base URL:** `http://localhost:4016`

| Method | Endpoint | Return Type | Description |
|--------|----------|-------------|-------------|
| `processOrderWebhook(payload)` | `POST /api/webhooks/shopify/orders` | `Promise<WebhookResponse>` | Process Shopify order webhook |

**Expected Published SDK:**
```typescript
import { ShopifyWebhookApi, ShopifyOrderPayload } from '@skeldir/api-client';

const shopify = new ShopifyWebhookApi(config);
await shopify.processOrderWebhook(payload);
```

---

## 8. WooCommerceWebhookService
**Base URL:** `http://localhost:4017`

| Method | Endpoint | Return Type | Description |
|--------|----------|-------------|-------------|
| `processOrderWebhook(payload)` | `POST /api/webhooks/woocommerce/orders` | `Promise<WebhookResponse>` | Process WooCommerce order webhook |

**Expected Published SDK:**
```typescript
import { WooCommerceWebhookApi, WooCommerceOrderPayload } from '@skeldir/api-client';

const woocommerce = new WooCommerceWebhookApi(config);
await woocommerce.processOrderWebhook(payload);
```

---

## 9. StripeWebhookService
**Base URL:** `http://localhost:4018`

| Method | Endpoint | Return Type | Description |
|--------|----------|-------------|-------------|
| `processPaymentWebhook(payload)` | `POST /api/webhooks/stripe/payments` | `Promise<WebhookResponse>` | Process Stripe payment webhook |

**Expected Published SDK:**
```typescript
import { StripeWebhookApi, StripePaymentPayload } from '@skeldir/api-client';

const stripe = new StripeWebhookApi(config);
await stripe.processPaymentWebhook(payload);
```

---

## 10. PayPalWebhookService
**Base URL:** `http://localhost:4019`

| Method | Endpoint | Return Type | Description |
|--------|----------|-------------|-------------|
| `processPaymentWebhook(payload)` | `POST /api/webhooks/paypal/payments` | `Promise<WebhookResponse>` | Process PayPal payment webhook |

**Expected Published SDK:**
```typescript
import { PayPalWebhookApi, PayPalPaymentPayload } from '@skeldir/api-client';

const paypal = new PayPalWebhookApi(config);
await paypal.processPaymentWebhook(payload);
```

---

## Expected Published SDK Package Structure

Based on OpenAPI contract-first architecture, the published SDK should export:

```typescript
// Configuration
export class Configuration {
  constructor(config: ConfigurationParameters);
}

export interface ConfigurationParameters {
  basePath?: string;
  credentials?: RequestCredentials;
  headers?: Record<string, string>;
  middleware?: Middleware[];
}

// Service APIs
export class AttributionApi { /* ... */ }
export class HealthApi { /* ... */ }
export class ExportApi { /* ... */ }
export class ReconciliationApi { /* ... */ }
export class ErrorsApi { /* ... */ }
export class AuthApi { /* ... */ }
export class ShopifyWebhookApi { /* ... */ }
export class WooCommerceWebhookApi { /* ... */ }
export class StripeWebhookApi { /* ... */ }
export class PayPalWebhookApi { /* ... */ }

// Request/Response Types
export interface RealtimeRevenueResponse { /* ... */ }
export interface HealthStatus { /* ... */ }
export interface AuthResponse { /* ... */ }
export interface LoginRequest { /* ... */ }
export interface RefreshRequest { /* ... */ }
export interface ErrorLogRequest { /* ... */ }
// ... all other types

// Error Types
export class ApiException extends Error {
  statusCode: number;
  correlationId?: string;
  errorId?: string;
}
```

---

## Migration Pattern

### Before (Manual SDK):
```typescript
import { sdk } from '@/lib/sdk-client';

// Direct service access
const revenue = await sdk.attribution.getRevenueRealtime();
const health = await sdk.health.getHealthStatus();
const csv = await sdk.export.exportCSV();
```

### After (Published SDK):
```typescript
import { apiClient } from '@/api/client';

// Same pattern, different import
const revenue = await apiClient.attribution.getRevenueRealtime();
const health = await apiClient.health.getHealth(); // Note: method name may differ
const csv = await apiClient.export.exportCsv(); // Note: camelCase vs PascalCase
```

---

## Critical Integration Points

### 1. Correlation ID Injection
**Requirement:** Every API call must include `X-Correlation-ID` header

**Implementation Strategy:**
```typescript
const config = new Configuration({
  middleware: [
    {
      pre: async (context) => {
        context.init.headers['X-Correlation-ID'] = generateUUID();
        return context;
      }
    }
  ]
});
```

### 2. Token Management
**Requirement:** JWT tokens from `tokenManager` must be injected

**Implementation Strategy:**
```typescript
const config = new Configuration({
  middleware: [
    {
      pre: async (context) => {
        const authHeader = await tokenManager.getAuthHeader();
        if (authHeader.Authorization) {
          context.init.headers['Authorization'] = authHeader.Authorization;
        }
        return context;
      }
    }
  ]
});
```

### 3. Error Handling
**Requirement:** Extract `correlation_id` and `error_id` from API errors

**Implementation Strategy:**
```typescript
try {
  await apiClient.attribution.getRevenueRealtime();
} catch (error) {
  if (error instanceof ApiException) {
    console.error(`[${error.correlationId}] ${error.message}`);
    showErrorBanner(error.errorId, error.correlationId);
  }
}
```

---

## Verification Checklist

After migration, verify:

- [ ] All 10 services are accessible via published SDK
- [ ] Method signatures match expected patterns
- [ ] Request/response types are correctly typed
- [ ] Correlation IDs appear in all API requests
- [ ] Auth tokens are injected automatically
- [ ] Error handling extracts correlation_id and error_id
- [ ] Multi-service URLs work correctly (or consolidated URL if backend uses API Gateway)

---

**Status:** Reference document for migration execution  
**Updated:** 2025-11-01  
**Next Review:** After `@skeldir/api-client` package structure is confirmed
