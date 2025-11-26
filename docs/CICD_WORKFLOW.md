# CI/CD Workflow Documentation

## Overview

The Skeldir Frontend Contracts Integration uses a multi-gate CI/CD pipeline to enforce contract integrity, version coupling, and zero-defect compliance. **All gates must pass before code can be merged.**

## Pipeline Architecture

```
┌─────────────────────────────────────────────┐
│          PR Created / Code Pushed            │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  GATE 1: Contract Checksum Validation        │
│  • Validates SHA256 hashes                   │
│  • Detects unauthorized contract changes     │
│  • Blocks PR if checksums.json out of sync   │
└─────────────────┬───────────────────────────┘
                  │ ✅ Pass
                  ▼
┌─────────────────────────────────────────────┐
│  GATE 2: Package Version Coupling            │
│  • Verifies openapi-contracts === api-client │
│  • Detects version drift                     │
│  • Blocks PR if versions don't match         │
└─────────────────┬───────────────────────────┘
                  │ ✅ Pass
                  ▼
┌─────────────────────────────────────────────┐
│  GATE 3: Mock Server Health Check            │
│  • Starts all 10 Prism servers               │
│  • Validates each server responds            │
│  • Blocks PR if any server fails             │
└─────────────────┬───────────────────────────┘
                  │ ✅ Pass
                  ▼
┌─────────────────────────────────────────────┐
│  GATE 4: Breaking Change Detection (Future)  │
│  • Runs openapi-diff on contracts            │
│  • Identifies breaking changes               │
│  • Requires manual approval if breaking      │
└─────────────────┬───────────────────────────┘
                  │ ✅ Pass
                  ▼
┌─────────────────────────────────────────────┐
│  GATE 5: Contract Compliance Tests (Future)  │
│  • Runs full test suite                      │
│  • Validates 100% endpoint coverage          │
│  • Checks header validation                  │
│  • Verifies error handling                   │
└─────────────────┬───────────────────────────┘
                  │ ✅ All Gates Pass
                  ▼
┌─────────────────────────────────────────────┐
│         PR Ready for Review & Merge          │
└─────────────────────────────────────────────┘
```

## Workflow Files

### 1. Contract Checksum Validation

**File**: `.github/workflows/contract-checksum.yml`

**Triggers**:
- Pull requests modifying `docs/api/contracts/**`
- Pull requests modifying `checksums.json`
- Pushes to `main` branch

**Steps**:
1. Checkout code
2. Setup Node.js 20
3. Run `node scripts/validate-checksums.js`
4. Fail if checksums don't match

**Failure Message**:
```
❌ CHECKSUM VALIDATION FAILED
Contract files have been modified without updating checksums.json

To fix:
  1. Run: node scripts/generate-checksums.js
  2. Commit the updated checksums.json
  3. Push changes
```

**How to Fix**:
```bash
node scripts/generate-checksums.js
git add checksums.json
git commit -m "chore: update contract checksums"
git push
```

---

### 2. Package Version Coupling

**File**: `.github/workflows/version-coupling.yml`

**Triggers**:
- Pull requests modifying `package.json`
- Pull requests modifying `package-lock.json`
- Pushes to `main` branch

**Steps**:
1. Checkout code
2. Setup Node.js 20
3. Extract package versions from package.json
4. Compare @muk223/openapi-contracts vs @muk223/api-client
5. Fail if versions don't match

**Failure Message**:
```
❌ VERSION MISMATCH DETECTED
Contract version: 2.0.7
Client version: 2.1.0

These packages MUST be the same version to ensure SDK matches contracts.

To fix:
  npm install @muk223/openapi-contracts@2.0.7 @muk223/api-client@2.0.7
```

**How to Fix**:
```bash
npm install @muk223/openapi-contracts@2.0.7 @muk223/api-client@2.0.7
git add package.json package-lock.json
git commit -m "chore: sync @muk223 package versions to 2.0.7"
git push
```

---

### 3. Mock Server Health Check

**File**: `.github/workflows/mock-health.yml`

**Triggers**:
- Pull requests modifying `docs/api/contracts/**`
- Pull requests modifying `scripts/start-mock-servers.sh`
- Pull requests modifying `docker-compose.mock.yml`
- Pushes to `main` branch

**Steps**:
1. Checkout code
2. Setup Node.js 20
3. Install Prism CLI globally
4. Start all mock servers with bash script
5. Wait 5 seconds for servers to initialize
6. Run health check script
7. Fail if any server is offline

**Failure Message**:
```
❌ MOCK SERVER HEALTH CHECK FAILED
One or more mock servers are not responding

Check:
  • Contract files are valid OpenAPI 3.1
  • All 10 servers (4010-4019) are configured
  • No port conflicts
```

**How to Fix**:
```bash
# Validate contract syntax
npx @apidevtools/swagger-cli validate docs/api/contracts/attribution.yaml

# Test locally
bash scripts/start-mock-servers.sh
node scripts/mock-health-check.js
```

---

### 4. Breaking Change Detection (Future)

**File**: `.github/workflows/breaking-changes.yml` (To be implemented)

**Triggers**:
- Pull requests modifying contract files

**Steps**:
1. Checkout code with full history
2. Install openapi-diff
3. Compare current contracts with base branch
4. Generate diff report
5. Fail if breaking changes detected (or require approval)

**Implementation**:
```yaml
- name: Detect breaking changes
  run: |
    npx openapi-diff \
      origin/main:docs/api/contracts/attribution.yaml \
      docs/api/contracts/attribution.yaml \
      --format markdown > breaking-changes.md
    
    if grep -q "Breaking changes" breaking-changes.md; then
      echo "❌ Breaking changes detected"
      cat breaking-changes.md
      exit 1
    fi
```

---

### 5. Contract Compliance Tests (Future)

**File**: `.github/workflows/contract-tests.yml` (To be implemented)

**Triggers**:
- All pull requests
- Pushes to `main`

**Steps**:
1. Checkout code
2. Install dependencies
3. Start mock servers
4. Run contract test suite
5. Generate coverage report
6. Fail if coverage < 100%

**Implementation**:
```yaml
- name: Run contract tests
  run: |
    npm run test:contracts
    npm run test:coverage
    
- name: Check coverage
  run: |
    COVERAGE=$(cat coverage/summary.json | jq '.total.lines.pct')
    if (( $(echo "$COVERAGE < 100" | bc -l) )); then
      echo "❌ Coverage below 100%: $COVERAGE%"
      exit 1
    fi
```

---

## Status Checks Configuration

### Required Checks (GitHub Branch Protection)

Configure these as required status checks on `main` branch:

1. ✅ **Contract Checksum Validation**
2. ✅ **Package Version Coupling**
3. ✅ **Mock Server Health Check**
4. ⏳ **Breaking Change Detection** (future)
5. ⏳ **Contract Compliance Tests** (future)

### GitHub Branch Protection Settings

```
Settings → Branches → main → Edit

☑️ Require status checks to pass before merging
  ☑️ Require branches to be up to date before merging
  
  Required status checks:
  ✅ Contract Checksum Validation
  ✅ Package Version Coupling  
  ✅ Mock Server Health Check
  
☑️ Do not allow bypassing the above settings
```

---

## Local Development Workflow

### Before Committing

```bash
# 1. Validate checksums
node scripts/validate-checksums.js

# 2. Validate versions
node scripts/validate-versions.js

# 3. Test mock servers
bash scripts/mock-docker-start.sh
node scripts/mock-health-check.js

# 4. Run tests (when available)
npm run test:contracts
```

### Commit Workflow

```bash
# 1. Stage changes
git add .

# 2. Commit with conventional commits
git commit -m "feat: add new attribution endpoint"

# 3. Push to feature branch
git push origin feature/new-endpoint

# 4. Create PR
# 5. CI runs automatically
# 6. Fix any failures
# 7. Merge after approval + green CI
```

---

## Failure Handling

### Checksum Failure

**Symptom**: PR blocked with checksum validation error

**Fix**:
```bash
node scripts/generate-checksums.js
git add checksums.json
git commit -m "chore: update checksums"
git push
```

### Version Coupling Failure

**Symptom**: PR blocked with version mismatch error

**Fix**:
```bash
npm install @muk223/openapi-contracts@2.0.7 @muk223/api-client@2.0.7
git add package*.json
git commit -m "chore: sync package versions"
git push
```

### Mock Health Failure

**Symptom**: PR blocked with server health error

**Fix**:
```bash
# Validate contract syntax locally
npx @apidevtools/swagger-cli validate docs/api/contracts/[file].yaml

# Test server startup locally
bash scripts/start-mock-servers.sh
node scripts/mock-health-check.js

# Fix contract syntax errors
# Commit fixed contracts
git add docs/api/contracts/
git commit -m "fix: correct OpenAPI syntax"
git push
```

---

## Pipeline Metrics

### Success Criteria

- ✅ All status checks green
- ✅ 100% contract checksum validation
- ✅ 100% version coupling compliance
- ✅ 100% mock server health
- ✅ 0 breaking changes (or approved)
- ✅ 100% test coverage (future)

### Monitoring

**CI Dashboard**:
- View workflow runs: `Actions` tab in GitHub
- Check status: PR checks section
- Review logs: Click on failed workflow

**Metrics to Track**:
- PR approval time
- Gate failure frequency
- Most common failure type
- Time to fix failures

---

## Emergency Procedures

### Bypass CI (Use Sparingly)

**Only for critical hotfixes:**

1. Create emergency branch
2. Make minimal fix
3. Request admin override
4. Merge with `--no-verify`
5. Fix CI in follow-up PR immediately

**Command**:
```bash
git push --no-verify
```

**⚠️ Warning**: This bypasses all safety checks. Use only in genuine emergencies.

---

### Rollback Procedure

**If bad code gets merged:**

1. **Immediate Revert**:
   ```bash
   git revert <commit-hash>
   git push
   ```

2. **Validate Revert**:
   ```bash
   node scripts/validate-checksums.js
   node scripts/validate-versions.js
   ```

3. **Create Fix PR**:
   - Fix the original issue
   - Ensure all CI passes
   - Merge with full validation

---

## Adding New Workflows

### Checklist for New CI Checks

1. **Create Workflow File**:
   ```bash
   touch .github/workflows/new-check.yml
   ```

2. **Define Triggers**:
   ```yaml
   on:
     pull_request:
       paths:
         - 'relevant/files/**'
     push:
       branches:
         - main
   ```

3. **Add Validation Steps**:
   - Checkout
   - Setup environment
   - Run validation
   - Report results

4. **Test Locally**:
   ```bash
   act pull_request  # Using act to test GitHub Actions locally
   ```

5. **Document in This File**:
   - Add workflow description
   - Document failure messages
   - Provide fix procedures

6. **Add to Branch Protection**:
   - Settings → Branches → main
   - Add to required status checks

---

## Future Enhancements

### Planned Workflows

1. **breaking-changes.yml** - openapi-diff integration
2. **contract-tests.yml** - Full test suite execution
3. **sdk-audit.yml** - Detect raw fetch() usage
4. **coverage-report.yml** - Test coverage enforcement
5. **performance-tests.yml** - API response time validation

### Planned Integrations

- Slack notifications on CI failures
- Automated PR comments with violation details
- Dashboard for compliance metrics
- Auto-rollback on critical failures

---

## Quick Reference

| Workflow | Validates | Failure Fix |
|----------|-----------|-------------|
| contract-checksum.yml | SHA256 integrity | `node scripts/generate-checksums.js` |
| version-coupling.yml | Package versions | `npm install @muk223/...@2.0.7` |
| mock-health.yml | Server health | Validate OpenAPI syntax |
| breaking-changes.yml | API compatibility | Review/approve changes |
| contract-tests.yml | Test coverage | Fix failing tests |

---

**CI/CD Status**: Phase 1 complete (3/5 workflows)  
**Next Steps**: Implement breaking change detection and contract tests  
**Target**: 100% gate compliance before production release
