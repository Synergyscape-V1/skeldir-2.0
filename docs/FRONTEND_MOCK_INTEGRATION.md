# SKELDIR 2.0 Mock Server Integration Guide

> **IMPORTANT**: This guide uses **process-based** mock servers (Prism). Docker is NOT used.

This guide enables frontend developers to consume SKELDIR mock APIs immediately, without waiting for backend implementation.

## Quick Start

### 1. Start Mock Servers (Process-Based)

```bash
./scripts/start-mocks-prism.sh
```

All 9 mock servers will start as native Node.js processes. Verify with:

```bash
curl http://localhost:4014/api/health -H "X-Correlation-ID: test-uuid"
```

Expected output:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-26T14:30:00Z",
  "services": {
    "database": "up",
    "api": "up"
  }
}
```

### 2. Stop Mock Servers

```bash
./scripts/stop-mocks-prism.sh
```

### 3. Health Check All Services

```bash
./scripts/health-check-mocks.sh
```

## Service URLs

| Domain | Base URL | Port | Key Endpoints |
|--------|----------|------|---------------|
| Authentication | http://localhost:4010 | 4010 | `/api/auth/login`, `/api/auth/refresh`, `/api/auth/logout` |
| Attribution | http://localhost:4011 | 4011 | `/api/attribution/revenue/realtime`, `/api/attribution/channels` |
| Reconciliation | http://localhost:4012 | 4012 | `/api/reconciliation/status` |
| Export | http://localhost:4013 | 4013 | `/api/export/revenue`, `/api/export/csv` |
| Health | http://localhost:4014 | 4014 | `/api/health`, `/api/health/ready` |
| Webhooks (Shopify) | http://localhost:4015 | 4015 | `/webhooks/shopify/orders/create` |
| Webhooks (WooCommerce) | http://localhost:4016 | 4016 | `/webhooks/woocommerce/order/created` |
| Webhooks (Stripe) | http://localhost:4017 | 4017 | `/webhooks/stripe/charge/succeeded` |
| Webhooks (PayPal) | http://localhost:4018 | 4018 | `/webhooks/paypal/payment/sale/completed` |

**Note**: Webhook endpoints (ports 4015-4018) are for backend integration testing. Frontend applications do NOT consume webhooks directly.

## Environment Variables

Add these to your `.env` file:

```bash
# Frontend-facing mock API URLs
VITE_AUTH_API_URL=http://localhost:4010
VITE_ATTRIBUTION_API_URL=http://localhost:4011
VITE_RECONCILIATION_API_URL=http://localhost:4012
VITE_EXPORT_API_URL=http://localhost:4013
VITE_HEALTH_API_URL=http://localhost:4014

# Enable mock mode
VITE_MOCK_MODE=true
```

## SDK Configuration

### Required Headers

Every request MUST include:

```javascript
const headers = {
  'X-Correlation-ID': crypto.randomUUID(), // Required for all requests
  'Content-Type': 'application/json',
};
```

Protected endpoints additionally require:
```javascript
headers['Authorization'] = `Bearer ${accessToken}`;
```

### Using TanStack Query (Recommended)

```typescript
import { useQuery } from '@tanstack/react-query';

// Realtime revenue with ETag caching support
export function useRealtimeRevenue() {
  return useQuery({
    queryKey: ['/api/attribution/revenue/realtime'],
    refetchInterval: 30000, // 30-second polling
  });
}
```

### Direct Fetch (with Correlation ID)

```typescript
function generateCorrelationId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

async function apiRequest(endpoint: string, options: RequestInit = {}) {
  const correlationId = generateCorrelationId();
  const baseUrl = import.meta.env.VITE_ATTRIBUTION_API_URL || 'http://localhost:4011';
  
  const response = await fetch(`${baseUrl}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Correlation-ID': correlationId,
      ...options.headers,
    },
  });

  return response;
}
```

## Authentication Flow

### Login

```typescript
const AUTH_URL = import.meta.env.VITE_AUTH_API_URL || 'http://localhost:4010';

async function login(email: string, password: string) {
  const correlationId = crypto.randomUUID();
  
  const response = await fetch(`${AUTH_URL}/api/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Correlation-ID': correlationId,
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const problem = await response.json();
    throw new Error(problem.detail);
  }

  const data = await response.json();
  // Store tokens securely
  return data;
}
```

### Token Refresh

```typescript
async function refreshToken(refreshToken: string, accessToken: string) {
  const response = await fetch(`${AUTH_URL}/api/auth/refresh`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${accessToken}`,
      'X-Correlation-ID': crypto.randomUUID(),
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    throw new Error('Token refresh failed');
  }

  return response.json();
}
```

## Error Handling

All errors follow RFC7807 Problem Details format:

```typescript
interface ProblemDetails {
  type: string;           // URI identifying problem type
  title: string;          // Human-readable summary
  status: number;         // HTTP status code
  detail: string;         // Human-readable explanation
  instance: string;       // URI of this occurrence
  correlation_id: string; // Request correlation ID
  timestamp: string;      // ISO 8601 timestamp
  errors?: Array<{        // Optional validation errors
    field: string;
    message: string;
    code: string;
  }>;
}
```

Example error handler:

```typescript
async function handleApiError(response: Response): Promise<never> {
  const problem: ProblemDetails = await response.json();
  
  console.error('API Error:', {
    correlationId: problem.correlation_id,
    status: problem.status,
    detail: problem.detail,
  });
  
  throw new Error(problem.detail);
}
```

## Error Simulation with Prism

Use Prism's `Prefer` header to simulate different error scenarios:

### Simulate 401 Unauthorized
```typescript
const response = await fetch(`${API_URL}/api/attribution/revenue/realtime`, {
  headers: {
    'X-Correlation-ID': crypto.randomUUID(),
    'Prefer': 'code=401',
  },
});
```

### Simulate 429 Rate Limit
```typescript
const response = await fetch(`${API_URL}/api/attribution/revenue/realtime`, {
  headers: {
    'X-Correlation-ID': crypto.randomUUID(),
    'Prefer': 'code=429',
  },
});
```

### Simulate 500 Server Error
```typescript
const response = await fetch(`${API_URL}/api/attribution/revenue/realtime`, {
  headers: {
    'X-Correlation-ID': crypto.randomUUID(),
    'Prefer': 'code=500',
  },
});
```

## Troubleshooting

### Check Service Status (Process-Based)

```bash
# View running processes
ps aux | grep prism

# Check specific port
lsof -i :4011

# Run health check
./scripts/health-check-mocks.sh
```

### View Logs

```bash
# View logs for specific service
tail -f /tmp/skeldir-mocks/prism_4011.log

# View all mock server logs
tail -f /tmp/skeldir-mocks/*.log
```

### Restart Services

```bash
# Stop all
./scripts/stop-mocks-prism.sh

# Start all
./scripts/start-mocks-prism.sh
```

### Validate Contracts

```bash
./scripts/validate-contracts.sh
```

### Common Errors

#### Port Conflicts

**Error**: `Address already in use`

**Solution**: 
1. Check what's using the port: `lsof -i :4011`
2. Stop existing processes: `./scripts/stop-mocks-prism.sh`
3. Restart: `./scripts/start-mocks-prism.sh`

#### Contract File Not Found

**Error**: `Contract file not found`

**Solution**: 
1. Verify files exist: `ls api-contracts/openapi/v1/*.yaml`
2. Ensure you're in the project root directory

#### Service Not Responding

**Error**: `Connection refused`

**Solution**:
1. Check if service is running: `ps aux | grep prism`
2. View logs: `tail -f /tmp/skeldir-mocks/prism_<port>.log`
3. Restart the service

## Process Management Commands

| Action | Command |
|--------|---------|
| Start all mocks | `./scripts/start-mocks-prism.sh` |
| Stop all mocks | `./scripts/stop-mocks-prism.sh` |
| Health check | `./scripts/health-check-mocks.sh` |
| Validate contracts | `./scripts/validate-contracts.sh` |
| View logs | `tail -f /tmp/skeldir-mocks/prism_<port>.log` |
| Check port | `lsof -i :<port>` |

## Port Assignment Reference

| Port | Service | Type |
|------|---------|------|
| 4010 | Auth | Frontend |
| 4011 | Attribution | Frontend |
| 4012 | Reconciliation | Frontend |
| 4013 | Export | Frontend |
| 4014 | Health | Frontend |
| 4015 | Shopify Webhooks | Backend-only |
| 4016 | WooCommerce Webhooks | Backend-only |
| 4017 | Stripe Webhooks | Backend-only |
| 4018 | PayPal Webhooks | Backend-only |

## Next Steps

- Review [API Contracts](../api-contracts/README.md) for detailed endpoint documentation
- Check [Governance Rules](../api-contracts/governance/invariants.md) for contract change policies
- See [Integration Map](../api-contracts/governance/integration-map.json) for service dependencies
