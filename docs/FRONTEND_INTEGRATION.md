# Frontend Integration Guide - Skeldir SDK

## Overview

This guide demonstrates how to integrate the Skeldir SDK into your frontend application using the contract-first architecture approach. All API interactions go through the auto-generated TypeScript SDK, ensuring 100% contract compliance.

## SDK Architecture

```
@muk223/api-client (Auto-generated from OpenAPI contracts)
         ↓
  lib/sdk-client.ts (Wrapper with correlation IDs, auth, error handling)
         ↓
  React Components (Use SDK services, no raw fetch())
```

## Installation & Setup

### 1. Install Packages

```bash
# Install Skeldir packages (when available from registry)
npm install @muk223/openapi-contracts@2.0.7
npm install @muk223/api-client@2.0.7
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure URLs:

```bash
# Development (Mock servers)
VITE_ATTRIBUTION_API_URL=http://localhost:4010
VITE_HEALTH_API_URL=http://localhost:4011
# ... (other mock URLs)

# Production
# VITE_ATTRIBUTION_API_URL=https://api.skeldir.com
```

### 3. Import SDK in Components

```typescript
import { sdk } from '@/lib/sdk-client';

// Example: Fetch attribution revenue
const RevenueComponent = () => {
  const { data, isLoading } = useQuery({
    queryKey: ['/api/attribution/revenue/realtime'],
    queryFn: () => sdk.attribution.getRevenueRealtime()
  });

  if (isLoading) return <div>Loading...</div>;
  
  return <div>Revenue: ${data.total_revenue}</div>;
};
```

## SDK Services Reference

### Attribution Service

```typescript
// Real-time revenue
const revenue = await sdk.attribution.getRevenueRealtime();

// Attribution metrics by period
const metrics = await sdk.attribution.getAttributionMetrics('30d');
```

### Health Service

```typescript
// System health status
const health = await sdk.health.getHealthStatus();
console.log(health.status); // 'healthy' | 'degraded' | 'unhealthy'
```

### Export Service

```typescript
// Export data in various formats
const csv = await sdk.export.exportCSV();
const json = await sdk.export.exportJSON();
const excel = await sdk.export.exportExcel();
```

### Reconciliation Service

```typescript
// Platform reconciliation status
const status = await sdk.reconciliation.getReconciliationStatus();
status.platforms.forEach(platform => {
  console.log(`${platform.platform_name}: ${platform.connection_status}`);
});
```

### Errors Service

```typescript
// Log frontend errors
await sdk.errors.logError({
  error_message: 'Component render failed',
  stack_trace: error.stack,
  timestamp: new Date().toISOString(),
  url: window.location.href,
  user_agent: navigator.userAgent,
  metadata: { component: 'Dashboard' }
});
```

### Auth Service

```typescript
// Login
const { access_token, refresh_token } = await sdk.auth.login(
  'user@example.com',
  'password'
);
localStorage.setItem('auth_token', access_token);

// Refresh token
const { access_token: newToken } = await sdk.auth.refreshToken(refresh_token);

// Verify token
const { valid, user_id } = await sdk.auth.verifyToken();
```

### Webhook Services (Testing)

```typescript
// Test Shopify webhook
await sdk.webhooks.shopify.processOrder({
  id: 'order_123',
  order_number: '1001',
  total_price: '99.99',
  created_at: new Date().toISOString()
});

// Test Stripe webhook
await sdk.webhooks.stripe.processPayment({
  id: 'evt_123',
  type: 'payment_intent.succeeded',
  data: { object: { id: 'pi_123', amount: 9999, currency: 'usd' } }
});
```

## Error Handling

The SDK automatically includes correlation IDs in all requests and extracts them from errors:

```typescript
try {
  await sdk.attribution.getRevenueRealtime();
} catch (error) {
  console.error('API Error:', {
    message: error.message,
    correlationId: error.correlationId, // For debugging
    errorId: error.errorId,             // Unique error identifier
    statusCode: error.statusCode        // HTTP status
  });
  
  // Display to user with correlation ID for support
  toast.error(
    `Request failed. Correlation ID: ${error.correlationId}`,
    { description: error.message }
  );
}
```

## Correlation ID Tracking

Every API request includes a `X-Correlation-ID` header:

1. **Generated**: UUID v4 created for each request
2. **Sent**: Included in all API calls automatically
3. **Returned**: Backend echoes it in responses/errors
4. **Logged**: Both frontend and backend log with same ID
5. **Debugging**: Use to trace requests across systems

## Best Practices

### ✅ DO

```typescript
// Use SDK services
const data = await sdk.attribution.getRevenueRealtime();

// Handle errors with correlation IDs
catch (error) {
  console.error('Correlation ID:', error.correlationId);
}

// Type-safe with SDK-generated types
const revenue: RevenueResponse = await sdk.attribution.getRevenueRealtime();
```

### ❌ DON'T

```typescript
// Raw fetch() - FORBIDDEN
const response = await fetch('http://localhost:4010/api/attribution');

// Hardcoded URLs - FORBIDDEN
const API_URL = 'http://localhost:4010';

// Missing error handling
await sdk.attribution.getRevenueRealtime(); // No try/catch
```

## Testing Against Mocks

### Start Mock Servers

```bash
# Docker (recommended)
bash scripts/mock-docker-start.sh

# Local Prism
bash scripts/start-mock-servers.sh

# Health check
node scripts/mock-health-check.js
```

### Test SDK Integration

```typescript
// SDK automatically uses mock URLs in development
const revenue = await sdk.attribution.getRevenueRealtime();
// Fetches from http://localhost:4010 (mock server)
```

### Switch to Production

```bash
# Update .env
VITE_ATTRIBUTION_API_URL=https://api.skeldir.com
# ... (other production URLs)

# Rebuild
npm run build
```

## Contract Compliance Rules

1. **Zero Raw Fetch**: All API calls must use SDK
2. **Correlation IDs**: Automatically injected, must be logged in errors
3. **Error Display**: Show correlation ID to users for support
4. **Type Safety**: Use SDK-generated TypeScript types
5. **Auth Headers**: SDK handles `Authorization: Bearer <token>`
6. **Version Sync**: `@muk223/openapi-contracts` === `@muk223/api-client`

## Troubleshooting

### SDK returns 404 errors
- Check mock servers are running: `node scripts/mock-health-check.js`
- Verify .env URLs match mock server ports

### Correlation IDs not in errors
- Ensure using `sdk.*` methods, not raw fetch()
- Check error handling wraps SDK calls in try/catch

### Type errors with SDK
- Verify `@muk223/api-client` version matches contracts
- Regenerate types if contracts changed

### Mock servers won't start
- Check ports 4010-4019 are available: `lsof -ti:4010-4019`
- Validate contract files: `node scripts/validate-checksums.js`

## Next Steps

- Review contract specifications: `docs/api/contracts/`
- Set up CI/CD validation: `docs/CICD_WORKFLOW.md`
- Review binary gates: `docs/BINARY_GATES.md`
- Check package versioning: `docs/PACKAGE_VERSIONING.md`
