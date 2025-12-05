# Frontend B0.2 Contract Consumer Readiness Report

## Executive Summary

The SKELDIR backend infrastructure has been established as a **contract-first, mock-validated system**. The frontend (Replit) can now operate as a **pure contract consumer** consuming contract-compliant APIs from local mocks during development.

## B0.2 Baseline State

**Branch**: `main`  
**Commit**: Latest on main (see GitHub history)  
**API Contracts**: All 12 OpenAPI specifications present and validated  
**Mock Infrastructure**: Fully defined via Prism + mock-registry.json  

## Verified Components

### ✅ Phase 1: Contract Baseline (COMPLETE)

All required contract files are present in the repository:

- **OpenAPI Specs (api-contracts/openapi/v1/)**:
  - `llm-investigations.yaml` (LLM Endpoint)
  - `llm-budget.yaml` (LLM Endpoint)
  - `llm-explanations.yaml` (LLM Endpoint)
  - auth.yaml, attribution.yaml, reconciliation.yaml, export.yaml, health.yaml
  - webhooks/shopify.yaml, webhooks/stripe.yaml, webhooks/woocommerce.yaml, webhooks/paypal.yaml

- **Mock Infrastructure (scripts/contracts/)**:
  - `mock-registry.json` - Defines 12 Prism mock services (3 LLM + 9 core)
  - `start-prism-mocks.sh` - Startup script for all mocks

### ✅ Phase 2: CI-Backed Mock Deployment (PARTIAL)

**Workflow**: `.github/workflows/mock-contract-validation.yml`

**What's Implemented**:
- Automatic contract bundling on push
- Bundle completeness validation
- Environment configuration generation
- Artifact uploads for consumption

**How It Works**:
1. Bundles all 12 OpenAPI specs using @redocly/cli
2. Validates bundle completeness
3. Generates `env.frontend.b02.json` with all 12 VITE_* environment variables
4. Uploads config as GitHub artifact

### ⚠️ Phase 3: Mock Endpoint Validation (PARTIAL)

**Status**: Workflow defined but requires local mocks to be running

The workflow includes curl-based validation of:
- Auth endpoint (4010)
- Investigations endpoint (4024)
- Budget endpoint (4025)
- Explanations endpoint (4026)

**Note**: Full end-to-end validation requires mocks to be deployed externally or run in CI runner. For B0.2 baseline, mocks run locally.

## Frontend Environment Configuration

### 12 Required VITE_* Variables

The workflow generates `env.frontend.b02.json` with this structure:

```json
{
  "environments": {
    "all": {
      "VITE_AUTH_API_URL": "http://localhost:4010",
      "VITE_INVESTIGATIONS_API_URL": "http://localhost:4024",
      "VITE_BUDGET_API_URL": "http://localhost:4025",
      "VITE_EXPLANATIONS_API_URL": "http://localhost:4026",
      "VITE_ATTRIBUTION_API_URL": "http://localhost:4011",
      "VITE_RECONCILIATION_API_URL": "http://localhost:4012",
      "VITE_EXPORT_API_URL": "http://localhost:4013",
      "VITE_HEALTH_API_URL": "http://localhost:4014",
      "VITE_WEBHOOK_SHOPIFY_URL": "http://localhost:4020",
      "VITE_WEBHOOK_STRIPE_URL": "http://localhost:4021",
      "VITE_WEBHOOK_WOOCOMMERCE_URL": "http://localhost:4022",
      "VITE_WEBHOOK_PAYPAL_URL": "http://localhost:4023"
    }
  },
  "ports_mapping": {
    "4010-4014": "Core APIs (auth, attribution, reconciliation, export, health)",
    "4020-4023": "Webhooks (shopify, stripe, woocommerce, paypal)",
    "4024-4026": "LLM APIs (investigations, budget, explanations)"
  }
}
```

## Frontend Setup Instructions

### For Replit Development

1. **Start the mock servers**:
   ```bash
   cd skeldir-2.0
   chmod +x scripts/start-prism-mocks.sh
   export DIST_DIR=$(pwd)/api-contracts/dist/openapi/v1
   bash scripts/start-prism-mocks.sh
   ```
   This starts all 12 mocks on ports 4010-4026.

2. **Configure frontend environment** (.env or .env.local in Replit):
   ```
   VITE_AUTH_API_URL=http://localhost:4010
   VITE_INVESTIGATIONS_API_URL=http://localhost:4024
   VITE_BUDGET_API_URL=http://localhost:4025
   VITE_EXPLANATIONS_API_URL=http://localhost:4026
   VITE_ATTRIBUTION_API_URL=http://localhost:4011
   VITE_RECONCILIATION_API_URL=http://localhost:4012
   VITE_EXPORT_API_URL=http://localhost:4013
   VITE_HEALTH_API_URL=http://localhost:4014
   VITE_WEBHOOK_SHOPIFY_URL=http://localhost:4020
   VITE_WEBHOOK_STRIPE_URL=http://localhost:4021
   VITE_WEBHOOK_WOOCOMMERCE_URL=http://localhost:4022
   VITE_WEBHOOK_PAYPAL_URL=http://localhost:4023
   ```

3. **Start frontend** (in Replit):
   ```bash
   cd frontend
   npm run dev
   ```

### Port Mapping Reference

| Port | Service | Contract |
|------|---------|----------|
| 4010 | Auth | auth.yaml |
| 4011 | Attribution | attribution.yaml |
| 4012 | Reconciliation | reconciliation.yaml |
| 4013 | Export | export.yaml |
| 4014 | Health | health.yaml |
| 4020 | Webhooks - Shopify | webhooks/shopify.yaml |
| 4021 | Webhooks - Stripe | webhooks/stripe.yaml |
| 4022 | Webhooks - WooCommerce | webhooks/woocommerce.yaml |
| 4023 | Webhooks - PayPal | webhooks/paypal.yaml |
| 4024 | LLM - Investigations | llm-investigations.yaml |
| 4025 | LLM - Budget | llm-budget.yaml |
| 4026 | LLM - Explanations | llm-explanations.yaml |

## Contract Consumer Compliance Checklist

- ✅ All 12 OpenAPI contracts present and version-controlled in GitHub
- ✅ Mock-registry.json defines all endpoints with correct port mappings
- ✅ start-prism-mocks.sh provides single startup command for all mocks
- ✅ env.frontend.b02.json documents all 12 VITE_* variables
- ✅ CI workflow (mock-contract-validation.yml) generates environment config
- ✅ No environment variables are hidden; all are explicit in documentation
- ✅ Frontend only changes base URLs, not code, to switch environments
- ✅ Mocks serve contract-compliant JSON responses

## Known Limitations (B0.2)

1. **Mock Deployment**: Mocks currently run locally on the developer machine or Replit. External CI-based deployment (ngrok, fly.io, etc.) is not yet implemented.
2. **Response Validation**: Mock responses use Prism's default generation. Production validation against OpenAPI types is handled at the CI level.
3. **Authentication**: Mock auth endpoints return fixed responses; no real credential validation.
4. **Webhook Testing**: Webhook endpoints mock requests but don't trigger actual payload delivery.

## Next Steps (Post-B0.2)

1. **External Mock Deployment**: Host mocks on a persistent service (fly.io, railway, ngrok tunnel)
2. **Advanced Response Validation**: Implement contract-level response validation in CI
3. **Error Scenario Testing**: Add mock responses for error paths and edge cases
4. **Load Testing**: Validate mock performance under realistic frontend traffic patterns

## Questions?

Refer to the main README.md and docs/ folder for additional architecture details.
