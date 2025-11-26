# API SDK Integration

## Overview

This directory contains the auto-generated TypeScript SDK from OpenAPI 3.1 contracts and the integration layer that wraps it with application-specific patterns.

## Directory Structure

```
client/src/api/
├── generated/              # Auto-generated TypeScript SDK (DO NOT EDIT)
│   ├── core/              # HTTP client core
│   ├── models/            # TypeScript type definitions from schemas
│   ├── services/          # API service classes
│   ├── index.ts           # Main exports
│   └── SkelAttributionClient.ts  # Main SDK client
│
├── sdk-client.ts          # Integration layer wrapping SDK
└── README.md              # This file
```

## Usage

### Using the SDK Client

```typescript
import { sdkClient } from '@/api/sdk-client';

// Get realtime revenue with correlation ID
const correlationId = crypto.randomUUID();
const { data, error } = await sdkClient.getRealtimeRevenue(correlationId);

if (error) {
  console.error('Revenue fetch failed:', error.message);
  return;
}

console.log('Total Revenue:', data.total_revenue);
console.log('Event Count:', data.event_count);
console.log('Last Updated:', data.last_updated);
```

### Using in React Components

```typescript
import { useSDKClient } from '@/api/sdk-client';

function RevenueCounter() {
  const sdk = useSDKClient();
  
  useEffect(() => {
    const fetchRevenue = async () => {
      const correlationId = crypto.randomUUID();
      const { data, error } = await sdk.getRealtimeRevenue(correlationId);
      
      if (data) {
        setRevenue(data.total_revenue);
      }
    };
    
    fetchRevenue();
  }, [sdk]);
  
  // ...
}
```

### With ETag Caching

```typescript
// First request
const correlationId = crypto.randomUUID();
const { data, error } = await sdkClient.getRealtimeRevenue(correlationId);

// Store ETag from response headers
const etag = response.headers.get('ETag');

// Subsequent request with ETag
const { data: cachedData, error: cacheError } = await sdkClient.getRealtimeRevenue(
  correlationId,
  etag
);

// If 304 Not Modified, SDK will throw - use cached data
```

## SDK Generation

### Regenerate SDK from Contracts

When new OpenAPI contracts are added or existing ones are updated:

```bash
# Generate from attribution contract
npx openapi-typescript-codegen \
  --input docs/api/contracts/attribution.yaml \
  --output client/src/api/generated \
  --client fetch \
  --name SkelAttributionClient

# Generate from all contracts (when available)
bash scripts/generate-sdk.sh
```

### Current Status

| Service | Contract File | SDK Status | Notes |
|---------|---------------|------------|-------|
| Attribution | `attribution.yaml` | ✅ Generated | Realtime revenue endpoint |
| Authentication | `auth.yaml` | ❌ Awaiting | Login, verify, refresh, logout |
| Export | `export.yaml` | ❌ Awaiting | CSV, JSON, Excel exports |
| Error Logging | `errors.yaml` | ❌ Awaiting | Frontend error logging |
| Reconciliation | `reconciliation.yaml` | ❌ Awaiting | Platform reconciliation status |
| Shopify Webhooks | `shopify-webhook.yaml` | ❌ Awaiting | Order, checkout events |
| WooCommerce Webhooks | `woocommerce-webhook.yaml` | ❌ Awaiting | Order events |
| Stripe Webhooks | `stripe-webhook.yaml` | ❌ Awaiting | Payment, refund events |
| PayPal Webhooks | `paypal-webhook.yaml` | ❌ Awaiting | Payment capture events |

## Type Safety

The SDK provides full TypeScript type safety:

```typescript
import type { RealtimeRevenueCounter } from '@/api/generated/models/RealtimeRevenueCounter';

// All fields are typed
const counter: RealtimeRevenueCounter = {
  total_revenue: 125430.50,
  event_count: 1247,
  last_updated: '2025-10-15T14:32:00Z',
  data_freshness_seconds: 5,
  verified: true,
  upgrade_notice: null
};
```

## Error Handling

The SDK integration layer converts SDK errors to our application error format:

```typescript
const { data, error } = await sdkClient.getRealtimeRevenue(correlationId);

if (error) {
  // Error format: { status, message, correlationId, details }
  console.error(`[${error.correlationId}] ${error.message}`);
  
  if (error.status === 401) {
    // Handle unauthorized
  } else if (error.status === 429) {
    // Handle rate limiting
  }
}
```

## Authentication

The SDK client automatically:
1. Fetches JWT token from TokenManager
2. Adds `Authorization: Bearer <token>` header to all requests
3. Handles token refresh on 401 responses (future enhancement)

## Contract Compliance

### Fields Implemented (Attribution API)

✅ All 6 required fields from `RealtimeRevenueCounter` schema:
- `total_revenue` (number)
- `event_count` (integer)
- `last_updated` (string - ISO 8601)
- `data_freshness_seconds` (integer)
- `verified` (boolean)
- `upgrade_notice` (string | null)

### Headers Implemented

✅ Request Headers:
- `X-Correlation-ID` (required, UUID)
- `If-None-Match` (optional, ETag for caching)
- `Authorization` (automatic via token manager)

✅ Response Headers (parsed automatically):
- `X-Correlation-ID` (echoed back)
- `ETag` (for cache validation)
- `Retry-After` (for 429 responses - future enhancement)

## Migration from useApiClient

### Before (useApiClient):
```typescript
const apiClient = useApiClient();
const response = await apiClient.get('/api/attribution/revenue');
```

### After (SDK):
```typescript
const sdk = useSDKClient();
const correlationId = crypto.randomUUID();
const { data, error } = await sdk.getRealtimeRevenue(correlationId);
```

## Next Steps

1. **Await Backend Contracts**: Need 8 additional OpenAPI contract files
2. **Regenerate Full SDK**: Once all contracts are available
3. **Replace All API Calls**: Migrate from `useApiClient` to `useSDKClient`
4. **Add Response Interceptors**: For global error handling
5. **Implement Token Refresh**: Automatic refresh on 401 responses

---

*Last Updated: 2025-10-15*  
*Status: Partial Implementation (1 of 9 contracts)*
