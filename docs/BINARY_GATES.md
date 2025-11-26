# Frontend Contracts Integration - 20 Binary Gates

This document defines the 20 binary validation gates that must ALL pass for the integration to be considered complete. **Any single gate failure = integration blocked.**

## Gate Status Legend
- ✅ **PASS**: Gate validates successfully
- ❌ **FAIL**: Gate validation failed - integration blocked
- ⏳ **PENDING**: Gate not yet validated

---

## Phase 1: Infrastructure Gates (1-5)

### Gate 1: Package Installation ⏳
**Validation**: Verify @muk223 packages installed with correct versions and all 12 YAML files present

```bash
# Check packages
npm list @muk223/openapi-contracts @muk223/api-client

# Expected output:
# ├── @muk223/openapi-contracts@2.0.7
# └── @muk223/api-client@2.0.7

# Verify contract files
ls -la docs/api/contracts/
# Must show all 12 files:
# - base.yaml
# - attribution.yaml  
# - health.yaml
# - export.yaml
# - reconciliation.yaml
# - errors.yaml
# - auth.yaml
# - webhooks/base.yaml
# - webhooks/shopify.yaml
# - webhooks/woocommerce.yaml
# - webhooks/stripe.yaml
# - webhooks/paypal.yaml
```

**Pass Criteria**: 
- Both packages at v2.0.7
- All 12 YAML files present
- No version drift

---

### Gate 2: SHA256 Checksum Validation ⏳
**Validation**: SHA256 checksum scripts pass locally and in CI

```bash
# Generate checksums
node scripts/generate-checksums.js

# Validate checksums  
node scripts/validate-checksums.js

# Expected output:
# ✅ All contract checksums valid
# 🚀 Contract integrity verified - safe to proceed
```

**Pass Criteria**:
- Generate script creates checksums.json with all 12 contracts
- Validate script passes with 0 failures
- CI workflow `.github/workflows/contract-checksum.yml` passes

---

### Gate 3: Mock Server Health ⏳
**Validation**: All 10 Prism mock servers launch and respond to health checks

```bash
# Start mock servers
bash scripts/mock-docker-start.sh

# Run health check
node scripts/mock-health-check.js

# Expected output:
# ✅ All 10 mock servers are responding!
# Summary: 10 online, 0 offline (of 10 total)
```

**Pass Criteria**:
- All 10 servers (ports 4010-4019) online
- Health check script exits with code 0
- Docker containers healthy
- All endpoints return mock data

---

### Gate 4: Documentation Completeness ⏳
**Validation**: Documentation exposes all endpoints, mock configs, SDK setup clearly

```bash
# Check required docs exist
ls -la docs/

# Must include:
# - CONTRACTS_QUICKSTART.md
# - CONTRACTS_README.md
# - FRONTEND_INTEGRATION.md
# - CICD_WORKFLOW.md
# - BINARY_GATES.md (this file)
# - PACKAGE_VERSIONING.md
```

**Pass Criteria**:
- All 6 documentation files present
- All 12 contracts enumerated in docs
- Mock server URLs documented (4010-4019)
- SDK usage examples provided
- Troubleshooting sections complete

---

### Gate 5: CI Pipeline Integration ⏳
**Validation**: CI pipeline runs checksum validation as first step

```bash
# Check CI workflows exist
ls -la .github/workflows/

# Must include:
# - contract-checksum.yml
# - mock-health.yml
# - version-coupling.yml
# - breaking-changes.yml (future)
# - contract-tests.yml (future)
```

**Pass Criteria**:
- Checksum validation runs on every PR
- Workflow fails PR if checksums invalid
- Status checks enforce gate passage

---

## Phase 2: SDK Integration Gates (6-10)

### Gate 6: Version Coupling ⏳
**Validation**: @muk223/openapi-contracts@2.0.7 === @muk223/api-client@2.0.7

```bash
# Automated check
node scripts/validate-versions.js

# Manual check
npm list @muk223/openapi-contracts @muk223/api-client
```

**Pass Criteria**:
- Exact version match (2.0.7 === 2.0.7)
- CI workflow enforces coupling
- PR blocked if versions drift

---

### Gate 7: Test Coverage ⏳
**Validation**: Tests cover all endpoints, payloads, headers, webhooks, edge cases

```bash
# Run contract tests
npm run test:contracts

# Check coverage
npm run test:coverage
```

**Pass Criteria**:
- 100% endpoint coverage (all paths in all 12 contracts)
- All request headers validated
- All response schemas validated
- Error cases tested (400, 401, 403, 404, 500, 503)
- Webhook signatures validated

---

### Gate 8: Breaking Change Detection ⏳
**Validation**: openapi-diff runs on every PR with 0 breaking changes

```bash
# Install openapi-diff
npm install -g openapi-diff

# Run diff check
npm run contracts:diff
```

**Pass Criteria**:
- No breaking changes detected
- CI workflow runs on every PR
- Workflow fails if breaking changes found

---

### Gate 9: SDK-Only API Calls ⏳
**Validation**: All API calls use SDK only (no raw fetch() detected)

```bash
# Audit codebase
npm run audit:fetch

# Or manually search
grep -r "fetch(" client/src --include="*.ts" --include="*.tsx"
```

**Pass Criteria**:
- Zero raw fetch() calls in application code
- ESLint rule `no-restricted-globals` blocks fetch
- All API interactions through `sdk.*` methods

---

### Gate 10: Offline Tarball Support ⏳
**Validation**: Tarball fallback mechanism for offline installs works

```bash
# Create tarball
npm pack @muk223/openapi-contracts
npm pack @muk223/api-client

# Install from tarball
npm install skeldir-openapi-contracts-2.0.7.tgz
npm install skeldir-api-client-2.0.7.tgz

# Verify contracts present
ls node_modules/@muk223/openapi-contracts/contracts/
```

**Pass Criteria**:
- Tarball installation succeeds
- All 12 contracts accessible
- SDK functions normally

---

## Phase 3: Quality Gates (11-15)

### Gate 11: Correlation ID Enforcement ⏳
**Validation**: All requests include X-Correlation-ID header, all errors expose it

**Pass Criteria**:
- SDK auto-generates UUID for each request
- Header present in all mock server logs
- Error responses include correlation_id
- UI displays correlation ID to users

---

### Gate 12: Error Response Compliance ⏳
**Validation**: All error responses match contract error schema

**Pass Criteria**:
- Errors include: error_id, correlation_id, message, timestamp
- HTTP status codes match contract specs
- Error details properly structured

---

### Gate 13: Authorization Headers ⏳
**Validation**: Bearer tokens correctly injected in all authenticated requests

**Pass Criteria**:
- SDK reads token from storage
- Authorization header present when required
- 401 errors handled gracefully
- Token refresh flow works

---

### Gate 14: Pagination Support ⏳
**Validation**: Paginated endpoints support limit, offset, cursors per contract

**Pass Criteria**:
- Pagination parameters sent correctly
- Response metadata includes next/prev
- UI handles pagination state

---

### Gate 15: Webhook Signature Validation ⏳
**Validation**: Webhook payloads include platform-specific signatures

**Pass Criteria**:
- Shopify: X-Shopify-Hmac-SHA256
- Stripe: Stripe-Signature  
- PayPal: PAYPAL-TRANSMISSION-SIG
- WooCommerce: X-WC-Webhook-Signature

---

## Phase 4: Observability Gates (16-18)

### Gate 16: Real-Time Compliance Dashboard ⏳
**Validation**: Dev tools overlay shows live contract compliance metrics

**Pass Criteria**:
- Displays current compliance %
- Shows runtime violations count
- Monitors all 10 mock servers
- Updates in real-time

---

### Gate 17: Version Drift Detection ⏳
**Validation**: System alerts when SDK/contract versions diverge

**Pass Criteria**:
- Visual indicator in dev tools
- CI check fails on drift
- Dashboard shows version status

---

### Gate 18: Mock Server Uptime Monitoring ⏳
**Validation**: 100% uptime tracked for all 10 servers during validation

**Pass Criteria**:
- Health checks pass continuously
- Uptime metrics logged
- Alerts on server failures

---

## Phase 5: Production Readiness Gates (19-20)

### Gate 19: Environment Parity ⏳
**Validation**: Same code works against mocks (dev) and real APIs (prod)

**Pass Criteria**:
- No code changes between environments
- Only .env URLs different
- SDK abstraction works both ways

---

### Gate 20: Zero Runtime Violations ⏳
**Validation**: Complete test suite runs with 0 contract violations

```bash
# Run full test suite
npm run test:all

# Expected output:
# ✅ Contract compliance: 100%
# ✅ Runtime violations: 0
# ✅ All 20 binary gates: PASS
```

**Pass Criteria**:
- All tests pass
- 0 contract violations
- 0 schema mismatches
- 0 missing headers
- 0 unauthorized requests

---

## Gate Status Summary

| Gate | Description | Status | Owner |
|------|-------------|--------|-------|
| 1 | Package Installation | ⏳ Pending | DevOps |
| 2 | SHA256 Checksums | ⏳ Pending | DevOps |
| 3 | Mock Server Health | ⏳ Pending | DevOps |
| 4 | Documentation | ⏳ Pending | Docs |
| 5 | CI Pipeline | ⏳ Pending | DevOps |
| 6 | Version Coupling | ⏳ Pending | DevOps |
| 7 | Test Coverage | ⏳ Pending | QA |
| 8 | Breaking Changes | ⏳ Pending | DevOps |
| 9 | SDK-Only Calls | ⏳ Pending | Dev |
| 10 | Tarball Support | ⏳ Pending | DevOps |
| 11 | Correlation IDs | ⏳ Pending | Dev |
| 12 | Error Compliance | ⏳ Pending | Dev |
| 13 | Auth Headers | ⏳ Pending | Dev |
| 14 | Pagination | ⏳ Pending | Dev |
| 15 | Webhook Sigs | ⏳ Pending | Dev |
| 16 | Compliance Dashboard | ⏳ Pending | Dev |
| 17 | Version Drift | ⏳ Pending | Dev |
| 18 | Mock Uptime | ⏳ Pending | DevOps |
| 19 | Environment Parity | ⏳ Pending | Dev |
| 20 | Zero Violations | ⏳ Pending | QA |

---

## Validation Commands

```bash
# Run all gate validations
npm run gates:validate

# Run specific gate
npm run gate:1  # Package installation
npm run gate:2  # Checksums
npm run gate:3  # Mock health
# ... etc

# Generate gate report
npm run gates:report
```

---

## Failure Protocol

**When any gate fails:**

1. **Stop**: Halt all development work
2. **Investigate**: Identify root cause with correlation IDs
3. **Fix**: Resolve the specific gate failure
4. **Revalidate**: Re-run gate validation
5. **Document**: Update this file with findings
6. **Resume**: Continue only after gate passes

**Critical Rule**: Integration is **BLOCKED** until all 20 gates show ✅ PASS.

---

**Target**: 100% gate passage within 2-week implementation window  
**Current Status**: Infrastructure Phase (Gates 1-5) in progress
