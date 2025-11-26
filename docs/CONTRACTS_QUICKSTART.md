# Frontend Contracts Integration - Quick Start Guide

**Get up and running with contract-driven development in 5 minutes**

## Prerequisites

- Node.js 18+ installed
- Docker and Docker Compose (for mock servers)
- Access to `@muk223` npm packages

## Step 1: Verify Contracts (30 seconds)

Check that contract files are in place:

```bash
ls -la docs/api/contracts/
```

Expected files:
- `attribution.yaml` ✓
- `health.yaml`
- `export.yaml`
- `reconciliation.yaml`
- `errors.yaml`
- `auth.yaml`
- `webhooks/shopify.yaml`
- `webhooks/woocommerce.yaml`
- `webhooks/stripe.yaml`
- `webhooks/paypal.yaml`

## Step 2: Validate Contract Integrity (30 seconds)

Generate and validate checksums:

```bash
# Generate checksums for all contracts
node scripts/generate-checksums.js

# Validate checksums
node scripts/validate-checksums.js
```

Expected output: `✅ All contract checksums valid`

## Step 3: Start Mock Servers (1 minute)

### Option A: Docker (Recommended)

```bash
bash scripts/mock-docker-start.sh
```

### Option B: Local Prism

```bash
bash scripts/start-mock-servers.sh
```

## Step 4: Verify Server Health (30 seconds)

```bash
node scripts/mock-health-check.js
```

Expected output: `✅ All 10 mock servers are responding!`

## Step 5: Test API Integration (1 minute)

Test the Attribution API:

```bash
curl -H "X-Correlation-ID: $(uuidgen)" \
     -H "Authorization: Bearer test-token" \
     http://localhost:4010/api/attribution/revenue/realtime
```

Expected: JSON response with mock revenue data

## Step 6: Use in Frontend (1 minute)

```typescript
import { sdk } from '@/lib/sdk-client';

// SDK automatically uses mock servers in development
const revenue = await sdk.attribution.getRevenueRealtime();
console.log(revenue); // Mock data from port 4010
```

## Verification Checklist

- [ ] All 10 mock servers running (ports 4010-4019)
- [ ] Health check passes for all servers
- [ ] Checksum validation passes
- [ ] Can fetch data from Attribution API
- [ ] SDK client configured and working

## Troubleshooting

### Mock servers won't start
```bash
# Kill any processes using ports 4010-4019
lsof -ti:4010-4019 | xargs kill -9

# Restart servers
bash scripts/mock-docker-start.sh
```

### Checksum validation fails
```bash
# Regenerate checksums
node scripts/generate-checksums.js
```

### Missing contract files
Check with backend team for latest contract package delivery

## Next Steps

- Read full documentation: `docs/CONTRACTS_README.md`
- Review SDK integration patterns: `docs/FRONTEND_INTEGRATION.md`
- Understand CI/CD workflows: `docs/CICD_WORKFLOW.md`
- Check binary gates: `docs/BINARY_GATES.md`

## Quick Reference

| Task | Command |
|------|---------|
| Generate checksums | `node scripts/generate-checksums.js` |
| Validate checksums | `node scripts/validate-checksums.js` |
| Start mocks (Docker) | `bash scripts/mock-docker-start.sh` |
| Start mocks (local) | `bash scripts/start-mock-servers.sh` |
| Health check | `node scripts/mock-health-check.js` |
| Stop Docker mocks | `docker-compose -f docker-compose.mock.yml down` |

---

**Integration Status**: 🚧 In Progress  
**Target Compliance**: 100% contract coverage  
**Timeline**: 2-week implementation window
