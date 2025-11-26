# OpenAPI 3.1 Contracts Directory

## Status: AWAITING BACKEND DELIVERABLES

This directory is designated for OpenAPI 3.1 contract files from the backend team (Cursor AI). These contracts are **critical blockers** for frontend development under the contract-first architecture mandate.

## Required Contract Files (Backend Phase B0.5.1, B0.5.2, B0.5.3)

### From Backend Team:
The following OpenAPI 3.1 specification files must be provided by the backend team:

1. **`attribution.yaml`** (Port 4010) - Attribution endpoints
   - GET /api/attribution/revenue/realtime
   - GET /api/attribution/summaries
   - GET /api/attribution/channels
   - GET /api/attribution/campaigns

2. **`auth.yaml`** (Port 4011) - Authentication endpoints
   - POST /api/auth/login
   - POST /api/auth/verify
   - POST /api/auth/refresh
   - POST /api/auth/logout

3. **`export.yaml`** (Port 4012) - Export endpoints
   - GET /api/export/csv
   - GET /api/export/json
   - GET /api/export/excel

4. **`errors.yaml`** (Port 4013) - Error logging endpoints
   - POST /api/errors/log

5. **`reconciliation.yaml`** (Port 4014) - Reconciliation endpoints
   - GET /api/reconciliation/status

6. **`shopify-webhook.yaml`** (Port 4015) - Shopify webhook schemas
   - ShopifyOrderCreated
   - ShopifyCheckoutUpdated

7. **`woocommerce-webhook.yaml`** (Port 4016) - WooCommerce webhook schemas
   - WooCommerceOrderCreated

8. **`stripe-webhook.yaml`** (Port 4017) - Stripe webhook schemas
   - StripePaymentSucceeded
   - StripeChargeRefunded

9. **`paypal-webhook.yaml`** (Port 4018) - PayPal webhook schemas
   - PayPalPaymentCaptured

## Prism Mock Server Configuration

Once contract files are received, Prism mock servers will be started on ports 4010-4018:

```bash
# Start all mock servers
npm run mock:all

# Start individual mock server
npx prism mock docs/api/contracts/attribution.yaml -p 4010
```

## Contract Validation

All contracts must:
- Use OpenAPI 3.1 specification
- Include complete schema definitions for all request/response bodies
- Define all required headers (X-Correlation-ID, Authorization, ETag, etc.)
- Include example responses
- Document error responses (400, 401, 429, 500, 503)

## Current Blocker

**STATUS:** Frontend development BLOCKED on contract delivery

The frontend cannot proceed with:
- TypeScript SDK generation (requires OpenAPI contracts)
- Mock server integration testing
- Contract compliance validation
- Full implementation of authentication, revenue counter, export, webhooks

**Action Required:** Backend team must deliver all 9 OpenAPI contract files to this directory.

---

*Last Updated: 2025-10-15*
*Waiting on: Backend Team (Cursor AI)*
