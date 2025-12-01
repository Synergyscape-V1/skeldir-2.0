# Prism Mock Server Deployment - B0.2

## Executive Summary

**Status:** ✅ **UNBLOCKED** - Ready for immediate deployment
**Spin-up Time:** < 2 minutes
**Phase:** B0.2 Mock Deployment Validation

Prism automatically generates spec-compliant mock responses from OpenAPI contracts. No manual response configuration needed.

## Quick Start (< 2min)

### Prerequisites
```bash
# Install Prism CLI globally (one-time)
npm install -g @stoplight/prism-cli
```

### Deploy All Mock Servers
```bash
# From repository root
cd api-contracts/openapi/v1

# Start all mocks (background processes)
prism mock attribution.yaml --port 4011 &
prism mock auth.yaml --port 4010 &
prism mock reconciliation.yaml --port 4014 &
prism mock export.yaml --port 4015 &
prism mock health.yaml --port 4016 &

# Webhook mocks
prism mock webhooks/shopify.yaml --port 4020 &
prism mock webhooks/stripe.yaml --port 4021 &
prism mock webhooks/woocommerce.yaml --port 4022 &
prism mock webhooks/paypal.yaml --port 4023 &
```

## Port Mapping (B0.2)

| Port | API | Contract File | Status |
|------|-----|---------------|--------|
| 4010 | Authentication | `auth.yaml` | ✅ Ready |
| 4011 | Attribution | `attribution.yaml` | ✅ Ready |
| 4014 | Reconciliation | `reconciliation.yaml` | ✅ Ready |
| 4015 | Export | `export.yaml` | ✅ Ready |
| 4016 | Health | `health.yaml` | ✅ Ready |
| 4020 | Shopify Webhooks | `webhooks/shopify.yaml` | ✅ Ready |
| 4021 | Stripe Webhooks | `webhooks/stripe.yaml` | ✅ Ready |
| 4022 | WooCommerce Webhooks | `webhooks/woocommerce.yaml` | ✅ Ready |
| 4023 | PayPal Webhooks | `webhooks/paypal.yaml` | ✅ Ready |

## Verification Tests

### Test Attribution API
```bash
curl -H "X-Correlation-ID: 550e8400-e29b-41d4-a716-446655440000" \
     http://localhost:4011/api/attribution/revenue/realtime
```

**Expected Response (Prism auto-generated):**
```json
{
  "total_revenue": 125430.5,
  "event_count": 1247,
  "last_updated": "2025-11-26T14:32:00Z",
  "data_freshness_seconds": 5,
  "verified": true,
  "confidence_score": 0.94,
  "upgrade_notice": "Upgrade to Pro for historical analytics"
}
```

### Test Authentication API
```bash
curl -X POST http://localhost:4010/api/auth/login \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{"email": "user@example.com", "password": "securePassword123"}'
```

**Expected Response:**
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

### Test Health Check
```bash
curl http://localhost:4016/api/health
```

## Frontend Integration (Replit Dev Flow)

### 1. Update `.env.development`
```bash
VITE_API_BASE_URL=http://localhost:4011  # Attribution
VITE_AUTH_API_URL=http://localhost:4010  # Auth
VITE_HEALTH_API_URL=http://localhost:4016  # Health
```

### 2. Start Frontend Dev Server
```bash
npm run dev
# Frontend will consume Prism mocks automatically
```

### 3. Verify Integration
- Login flow → hits `POST http://localhost:4010/api/auth/login`
- Revenue dashboard → hits `GET http://localhost:4011/api/attribution/revenue/realtime`
- Health indicator → hits `GET http://localhost:4016/api/health`

## Automated Startup Script

**File:** `scripts/start-prism-mocks.sh`
```bash
#!/usr/bin/env bash
# Start all Prism mock servers for B0.2 validation

set -euo pipefail

CONTRACTS_DIR="api-contracts/openapi/v1"

echo "Starting Prism mock servers..."

prism mock "$CONTRACTS_DIR/auth.yaml" --port 4010 &
prism mock "$CONTRACTS_DIR/attribution.yaml" --port 4011 &
prism mock "$CONTRACTS_DIR/reconciliation.yaml" --port 4014 &
prism mock "$CONTRACTS_DIR/export.yaml" --port 4015 &
prism mock "$CONTRACTS_DIR/health.yaml" --port 4016 &

prism mock "$CONTRACTS_DIR/webhooks/shopify.yaml" --port 4020 &
prism mock "$CONTRACTS_DIR/webhooks/stripe.yaml" --port 4021 &
prism mock "$CONTRACTS_DIR/webhooks/woocommerce.yaml" --port 4022 &
prism mock "$CONTRACTS_DIR/webhooks/paypal.yaml" --port 4023 &

echo "✅ All Prism mocks started"
echo "Use 'pkill -f prism' to stop all mocks"
```

**Usage:**
```bash
bash scripts/start-prism-mocks.sh
```

## B0.2 Success Criteria

✅ All 9 Prism mocks running on designated ports
✅ Frontend can authenticate via mock Auth API
✅ Frontend can display revenue data from mock Attribution API
✅ Health checks respond correctly
✅ < 2min spin-up time documented and verified

## Stopping Mock Servers

```bash
# Stop all Prism processes
pkill -f prism

# Or kill individual ports
lsof -ti:4010 | xargs kill -9
lsof -ti:4011 | xargs kill -9
# etc.
```

## Critical Insight: Prism Auto-Generation

**Prism does NOT require manual response configuration.** It reads OpenAPI contracts and automatically generates spec-compliant responses using:
- Schema definitions (required fields, types, constraints)
- Example values from contract annotations
- Format specifications (date-time, email, uuid, etc.)

This means **all contracts are immediately mockable** as long as they are valid OpenAPI 3.1 specs.

## Backend Stub vs Prism Mock

| Aspect | Backend Stub | Prism Mock |
|--------|--------------|------------|
| **Response Source** | Hand-coded Python dict | Auto-generated from contract |
| **Schema Validation** | Pydantic enforces at runtime | Prism enforces at mock startup |
| **B0.2-001 Issue** | Missing `event_count`, `last_updated` | ✅ Never missing (reads schema) |
| **Maintenance** | Manual updates needed | Auto-syncs with contract changes |

**Takeaway:** Backend stub issues do NOT block Prism deployment. Prism mocks are contract-driven and self-validating.

---

**Document Version:** 1.0
**Phase:** B0.2 Mock Deployment
**Last Updated:** 2025-12-01
**Status:** ✅ Ready for Deployment
