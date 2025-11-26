# Mock Server Setup Guide

## Quick Start

### 1. Start Mock Server (Attribution API Only - Currently Available)
```bash
npx prism mock docs/api/contracts/attribution.yaml -p 4010
```

### 2. Start All Mock Servers (When All Contracts Available)
```bash
bash scripts/start-mock-servers.sh
```

### 3. Health Check
```bash
node scripts/mock-health-check.js
```

## Available Commands

| Command | Description |
|---------|-------------|
| `npx prism mock docs/api/contracts/attribution.yaml -p 4010` | Start Attribution API mock (port 4010) |
| `npx prism mock docs/api/contracts/auth.yaml -p 4011` | Start Auth API mock (port 4011) |
| `npx prism mock docs/api/contracts/export.yaml -p 4012` | Start Export API mock (port 4012) |
| `npx prism mock docs/api/contracts/errors.yaml -p 4013` | Start Error Logging API mock (port 4013) |
| `npx prism mock docs/api/contracts/reconciliation.yaml -p 4014` | Start Reconciliation API mock (port 4014) |
| `bash scripts/start-mock-servers.sh` | Start all 9 mock servers |
| `node scripts/mock-health-check.js` | Check health of all mock servers |

## Mock Server Ports

| Port | API | Contract File | Status |
|------|-----|---------------|--------|
| 4010 | Attribution | `attribution.yaml` | ✅ Stub Available |
| 4011 | Authentication | `auth.yaml` | ❌ Awaiting Backend |
| 4012 | Export | `export.yaml` | ❌ Awaiting Backend |
| 4013 | Error Logging | `errors.yaml` | ❌ Awaiting Backend |
| 4014 | Reconciliation | `reconciliation.yaml` | ❌ Awaiting Backend |
| 4015 | Shopify Webhooks | `shopify-webhook.yaml` | ❌ Awaiting Backend |
| 4016 | WooCommerce Webhooks | `woocommerce-webhook.yaml` | ❌ Awaiting Backend |
| 4017 | Stripe Webhooks | `stripe-webhook.yaml` | ❌ Awaiting Backend |
| 4018 | PayPal Webhooks | `paypal-webhook.yaml` | ❌ Awaiting Backend |

## Testing Mock Servers

### Test Attribution API (Realtime Revenue)
```bash
curl -H "X-Correlation-ID: $(uuidgen)" \
     -H "Authorization: Bearer mock-token" \
     http://localhost:4010/api/attribution/revenue/realtime
```

Expected Response:
```json
{
  "total_revenue": 125430.50,
  "event_count": 1247,
  "last_updated": "2025-10-15T14:32:00Z",
  "data_freshness_seconds": 5,
  "verified": true,
  "upgrade_notice": null
}
```

### Test ETag Caching
```bash
# First request - get ETag
curl -i -H "X-Correlation-ID: $(uuidgen)" \
        -H "Authorization: Bearer mock-token" \
        http://localhost:4010/api/attribution/revenue/realtime

# Second request - use ETag (should return 304)
curl -i -H "X-Correlation-ID: $(uuidgen)" \
        -H "Authorization: Bearer mock-token" \
        -H "If-None-Match: <etag-from-first-response>" \
        http://localhost:4010/api/attribution/revenue/realtime
```

## Environment Configuration

### Mock Mode (.env.mock)
```bash
# Copy to .env to enable mock mode
cp .env.mock .env
```

### Environment Variables
```
VITE_MOCK_MODE=true
VITE_MOCK_ATTRIBUTION_URL=http://localhost:4010
VITE_MOCK_AUTH_URL=http://localhost:4011
# ... etc
```

## Current Status

### ✅ Completed
- [x] Prism CLI installed
- [x] Contract directory structure created
- [x] Attribution API stub contract created
- [x] Mock server startup scripts created
- [x] Health check utility created
- [x] Environment configuration documented

### ❌ Blocked (Awaiting Backend Team)
- [ ] Complete OpenAPI 3.1 contracts for all 9 APIs
- [ ] Contracts must include:
  - Complete schema definitions
  - Example responses
  - Error response schemas
  - Header specifications

### 📋 Next Steps (After Contracts Received)
1. Place all 9 .yaml files in `docs/api/contracts/`
2. Run `bash scripts/start-mock-servers.sh`
3. Run `node scripts/mock-health-check.js` to verify
4. Generate TypeScript SDK from contracts
5. Begin frontend integration testing

## Troubleshooting

### Mock Server Won't Start
```bash
# Check if port is already in use
lsof -i :4010

# Kill existing process
kill -9 <PID>
```

### Contract Validation Errors
```bash
# Validate OpenAPI contract
npx @stoplight/spectral-cli lint docs/api/contracts/attribution.yaml
```

### Health Check Fails
```bash
# Check if mock server is running
ps aux | grep prism

# Check logs
npx prism mock docs/api/contracts/attribution.yaml -p 4010 --verbose
```

---

*Last Updated: 2025-10-15*
*Status: Partial Implementation - Awaiting Backend Contract Delivery*
