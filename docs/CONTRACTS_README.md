# Frontend Contracts Integration - Complete Guide

## Overview

This guide provides comprehensive documentation for the Skeldir Frontend Contracts Integration using a contract-first architecture approach. All frontend API interactions go through an auto-generated TypeScript SDK derived from OpenAPI 3.1 contracts.

## Architecture

```
┌─────────────────────────────────────────────┐
│   OpenAPI 3.1 Contracts (12 files)          │
│   @muk223/openapi-contracts@2.0.7          │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│   Auto-Generated TypeScript SDK             │
│   @muk223/api-client@2.0.7                 │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│   SDK Client Wrapper                        │
│   (Correlation IDs, Auth, Error Handling)   │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│   React Components                          │
│   (No raw fetch(), SDK only)                │
└─────────────────────────────────────────────┘
```

## Contract Inventory

### Core API Contracts (7 files)

1. **base.yaml** - Shared schemas, error responses, common components
2. **attribution.yaml** - Revenue attribution and metrics endpoints
3. **health.yaml** - System health monitoring
4. **export.yaml** - Data export (CSV, JSON, Excel)
5. **reconciliation.yaml** - Platform reconciliation status
6. **errors.yaml** - Frontend error logging
7. **auth.yaml** - Authentication (login, refresh, verify)

### Webhook Contracts (5 files)

8. **webhooks/base.yaml** - Shared webhook schemas and signatures
9. **webhooks/shopify.yaml** - Shopify order and checkout webhooks
10. **webhooks/woocommerce.yaml** - WooCommerce order webhooks
11. **webhooks/stripe.yaml** - Stripe payment webhooks
12. **webhooks/paypal.yaml** - PayPal payment webhooks

**Total**: 12 OpenAPI 3.1 contract files

## Mock Server Configuration

| Port | Service | Contract | URL |
|------|---------|----------|-----|
| 4010 | Attribution API | attribution.yaml | http://localhost:4010 |
| 4011 | Health Monitoring | health.yaml | http://localhost:4011 |
| 4012 | Export API | export.yaml | http://localhost:4012 |
| 4013 | Reconciliation | reconciliation.yaml | http://localhost:4013 |
| 4014 | Error Logging | errors.yaml | http://localhost:4014 |
| 4015 | Authentication | auth.yaml | http://localhost:4015 |
| 4016 | Shopify Webhooks | webhooks/shopify.yaml | http://localhost:4016 |
| 4017 | WooCommerce Webhooks | webhooks/woocommerce.yaml | http://localhost:4017 |
| 4018 | Stripe Webhooks | webhooks/stripe.yaml | http://localhost:4018 |
| 4019 | PayPal Webhooks | webhooks/paypal.yaml | http://localhost:4019 |

## Installation

### Prerequisites

- Node.js 18+
- Docker and Docker Compose (for mock servers)
- NPM access to @muk223 packages

### Setup Steps

1. **Install Dependencies**

```bash
npm install
```

2. **Install Skeldir Packages** (when available)

```bash
npm install @muk223/openapi-contracts@2.0.7 @muk223/api-client@2.0.7
```

3. **Configure Environment**

```bash
cp .env.example .env
```

4. **Validate Contracts**

```bash
node scripts/validate-checksums.js
```

5. **Start Mock Servers**

```bash
# Docker (recommended)
bash scripts/mock-docker-start.sh

# Or local Prism
bash scripts/start-mock-servers.sh
```

6. **Verify Health**

```bash
node scripts/mock-health-check.js
```

## Usage

### Import SDK

```typescript
import { sdk } from '@/lib/sdk-client';
```

### Make API Calls

```typescript
// Get attribution revenue
const revenue = await sdk.attribution.getRevenueRealtime();

// Export data
const csv = await sdk.export.exportCSV();

// Log error
await sdk.errors.logError({
  error_message: error.message,
  stack_trace: error.stack,
  timestamp: new Date().toISOString(),
  url: window.location.href,
  user_agent: navigator.userAgent
});
```

### Error Handling

```typescript
try {
  const data = await sdk.attribution.getRevenueRealtime();
} catch (error) {
  console.error('API Error:', {
    correlationId: error.correlationId, // For debugging
    errorId: error.errorId,             // Unique identifier
    statusCode: error.statusCode,       // HTTP status
    message: error.message
  });
  
  // Show to user
  toast.error(
    `Request failed. Correlation ID: ${error.correlationId}`
  );
}
```

## Validation & Testing

### Checksum Validation

```bash
# Generate checksums
node scripts/generate-checksums.js

# Validate checksums
node scripts/validate-checksums.js
```

### Version Validation

```bash
# Check package version coupling
node scripts/validate-versions.js
```

### Mock Server Health

```bash
# Check all 10 servers
node scripts/mock-health-check.js
```

### Contract Tests

```bash
# Run contract compliance tests
npm run test:contracts

# Check coverage
npm run test:coverage
```

## Contract Integrity

### SHA256 Checksums

All contract files are protected with SHA256 checksums stored in `checksums.json`. This ensures:

- **Tamper Detection**: Any unauthorized contract changes are detected
- **CI Validation**: Checksums validated on every PR
- **Drift Prevention**: Frontend/backend contract alignment enforced

### Validation Process

1. Developer modifies contract
2. Runs `node scripts/generate-checksums.js`
3. Commits updated `checksums.json`
4. CI validates checksums match
5. PR blocked if validation fails

## Mock Server Management

### Docker Commands

```bash
# Start all servers
docker-compose -f docker-compose.mock.yml up -d

# Stop all servers
docker-compose -f docker-compose.mock.yml down

# View logs
docker-compose -f docker-compose.mock.yml logs -f

# Check status
docker-compose -f docker-compose.mock.yml ps
```

### Local Prism Commands

```bash
# Start mock server for specific contract
npx prism mock docs/api/contracts/attribution.yaml -p 4010

# Start all servers
bash scripts/start-mock-servers.sh

# Stop all (Ctrl+C or kill processes)
lsof -ti:4010-4019 | xargs kill -9
```

## Package Management

### Version Coupling

**Critical**: These packages MUST always be the same version:

```json
{
  "@muk223/openapi-contracts": "2.0.7",
  "@muk223/api-client": "2.0.7"
}
```

### Update Procedure

```bash
# Update both packages together
npm install @muk223/openapi-contracts@2.1.0 @muk223/api-client@2.1.0

# Regenerate checksums
node scripts/generate-checksums.js

# Validate
node scripts/validate-checksums.js
node scripts/validate-versions.js
```

See [PACKAGE_VERSIONING.md](./PACKAGE_VERSIONING.md) for details.

## Troubleshooting

### Mock servers won't start

```bash
# Check for port conflicts
lsof -ti:4010-4019

# Kill existing processes
lsof -ti:4010-4019 | xargs kill -9

# Restart servers
bash scripts/mock-docker-start.sh
```

### Checksum validation fails

```bash
# Regenerate checksums
node scripts/generate-checksums.js

# Commit changes
git add checksums.json
git commit -m "chore: update contract checksums"
```

### SDK type errors

```bash
# Verify version coupling
node scripts/validate-versions.js

# Update both packages to same version
npm install @muk223/openapi-contracts@2.0.7 @muk223/api-client@2.0.7
```

### 404 errors from SDK

```bash
# Check mock servers are running
node scripts/mock-health-check.js

# Verify environment variables
cat .env | grep VITE_
```

### Contract changes not reflected

```bash
# Restart mock servers
docker-compose -f docker-compose.mock.yml down
docker-compose -f docker-compose.mock.yml up -d

# Or restart local servers
bash scripts/start-mock-servers.sh
```

## Binary Gates

The integration must pass all 20 binary gates. See [BINARY_GATES.md](./BINARY_GATES.md) for complete validation checklist.

**Critical Gates:**
- ✅ All 12 contracts present
- ✅ SHA256 checksums valid
- ✅ Version coupling enforced
- ✅ 10 mock servers healthy
- ✅ SDK-only API calls (no raw fetch)
- ✅ 100% contract compliance

## CI/CD Integration

### GitHub Actions Workflows

- **contract-checksum.yml** - Validates checksums on every PR
- **mock-health.yml** - Verifies mock servers start correctly
- **version-coupling.yml** - Enforces package version synchronization

See [CICD_WORKFLOW.md](./CICD_WORKFLOW.md) for pipeline details.

## Development Workflow

1. **Start Development**
   ```bash
   bash scripts/mock-docker-start.sh
   npm run dev
   ```

2. **Make Changes**
   - Use SDK services in components
   - Never use raw fetch()
   - Handle errors with correlation IDs

3. **Test Locally**
   ```bash
   npm run test:contracts
   node scripts/mock-health-check.js
   ```

4. **Commit & Push**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   git push
   ```

5. **CI Validation**
   - Checksums validated
   - Mock health checked
   - Version coupling enforced
   - PR blocked if any gate fails

## Production Deployment

1. **Update Environment**
   ```bash
   VITE_ATTRIBUTION_API_URL=https://api.skeldir.com
   # ... (other production URLs)
   ```

2. **Build**
   ```bash
   npm run build
   ```

3. **Deploy**
   - Same code works with production APIs
   - No changes needed (environment parity)

## Resources

- [Quick Start](./CONTRACTS_QUICKSTART.md) - 5-minute setup
- [Frontend Integration](./FRONTEND_INTEGRATION.md) - SDK usage patterns
- [Binary Gates](./BINARY_GATES.md) - Validation checklist
- [Package Versioning](./PACKAGE_VERSIONING.md) - Update procedures
- [CI/CD Workflow](./CICD_WORKFLOW.md) - Pipeline documentation

## Support

**For contract issues:**
- Check correlation ID in error messages
- Validate checksums: `node scripts/validate-checksums.js`
- Review logs: `docker-compose -f docker-compose.mock.yml logs`

**For version issues:**
- Validate coupling: `node scripts/validate-versions.js`
- Update both packages: `npm install @muk223/openapi-contracts@X @muk223/api-client@X`

**For mock server issues:**
- Health check: `node scripts/mock-health-check.js`
- Restart: `bash scripts/mock-docker-start.sh`

---

**Target**: 100% contract compliance, zero runtime violations  
**Timeline**: 2-week implementation window  
**Status**: Infrastructure complete, testing in progress
