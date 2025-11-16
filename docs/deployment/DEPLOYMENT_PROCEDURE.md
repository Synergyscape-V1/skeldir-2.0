# GitHub Deployment Procedure

**Purpose**: Step-by-step procedure for deploying restructured repository to GitHub  
**Date**: 2025-11-16  
**Status**: Ready for Execution

---

## Overview

This document provides a phased approach to deploying the restructured SKELDIR 2.0 repository to GitHub with full validation at each stage.

---

## Prerequisites

### Local Environment

- Git installed and configured
- GitHub CLI (`gh`) installed (optional, for easier authentication)
- Access to `skeldir-2.0` GitHub repository
- All restructuring changes complete locally

### GitHub Repository

- Repository exists: `https://github.com/{org}/skeldir-2.0`
- Main branch protection rules configured
- GitHub Actions enabled
- Required secrets configured (if needed)

---

## PHASE 1: Pre-Deployment Integrity Validation

### Objective

Verify all restructuring changes are complete and internally consistent before GitHub push.

### Execution

```bash
# Run pre-deployment validation
bash scripts/deployment/validate-pre-deployment.sh
```

### Exit Gates

#### Gate 1.1: Path Consistency Verification

**Validation**: Automated scan shows zero references to old directory structures

**Command**:
```bash
grep -r "contracts/openapi/v1" --include="*.yml" --include="*.yaml" --include="*.md" --include="*.sh" --include="*.py" --include="*.json" . | grep -v "docs/archive" | grep -v "node_modules" | wc -l
```

**Expected Result**: `0`

**Evidence**: Capture output showing zero matches

---

#### Gate 1.2: Contract Integrity

**Validation**: All OpenAPI $refs resolve correctly in new structure

**Command**:
```bash
# Check for broken references
grep -r '\$ref.*\.\./\.\./\.\./_common' contracts/ | wc -l
grep -r '\$ref.*\.\./_common' contracts/ | grep -v "_common/v1" | wc -l
```

**Expected Result**: Both commands return `0`

**Evidence**: Capture output showing zero broken references

---

#### Gate 1.3: Navigation Validation

**Validation**: Manual verification of documentation discoverability

**Test Procedure**:
1. Open `README.md`
2. Navigate to each critical document within 3 clicks
3. Verify all links work

**Critical Documents**:
- `docs/database/pii-controls.md`
- `docs/database/schema-governance.md`
- `docs/architecture/service-boundaries.md`
- `docs/architecture/contract-ownership.md`
- `docs/operations/pii-control-evidence.md`

**Evidence**: Screenshot or document navigation paths

---

#### Gate 1.4: Build Readiness

**Validation**: All Dockerfiles parse without syntax errors

**Command**:
```bash
# Check Dockerfiles exist and have FROM directive
for df in backend/app/*/Dockerfile; do
    if [ -f "$df" ] && grep -q "^FROM" "$df"; then
        echo "✓ $df"
    else
        echo "✗ $df"
    fi
done
```

**Expected Result**: All Dockerfiles valid

**Evidence**: Capture output showing all Dockerfiles valid

---

## PHASE 2: GitHub Repository Preparation

### Objective

Prepare the GitHub repository for the restructured codebase.

### Execution Steps

#### Step 2.1: Verify Branch Protection

```bash
# Check branch protection rules (requires GitHub CLI)
gh api repos/{owner}/{repo}/branches/main/protection

# Or verify via GitHub web interface:
# Settings → Branches → Branch protection rules → main
```

**Required Settings**:
- ✅ Require pull request reviews before merging
- ✅ Require status checks to pass before merging
- ✅ Require branches to be up to date before merging

**Evidence**: Screenshot or API response

---

#### Step 2.2: Verify Secrets Configuration

```bash
# List GitHub Actions secrets (requires GitHub CLI)
gh secret list

# Required secrets (if applicable):
# - DATABASE_URL (for CI tests)
# - JWT_SECRET (for CI tests)
# - Any other environment-specific secrets
```

**Evidence**: List of configured secrets (redacted values)

---

#### Step 2.3: Verify Access Permissions

**Check via GitHub Web Interface**:
- Settings → Collaborators & teams
- Verify team members have appropriate access

**Evidence**: Screenshot of permissions

---

#### Step 2.4: Prepare Rollback Procedure

**Create Rollback Tag**:
```bash
# Tag current main branch state
git fetch origin
git tag -a "pre-restructuring-$(date +%Y%m%d)" origin/main -m "Pre-restructuring state for rollback"
git push origin --tags
```

**Document Rollback Steps**:
1. Identify commit hash before restructuring
2. Create revert branch: `git checkout -b revert/restructuring <commit-hash>`
3. Force push (if necessary): `git push origin revert/restructuring --force`
4. Create PR to restore previous state

**Evidence**: Tag created and documented

---

## PHASE 3: Structured Code Deployment

### Objective

Deploy restructured codebase to GitHub with preservation of git history.

### Execution Steps

#### Step 3.1: Prepare Logical Commits

```bash
# Run commit preparation script
bash scripts/deployment/prepare-git-commits.sh

# Review staged changes
git status
git diff --cached
```

#### Step 3.2: Create Feature Branch

```bash
# Ensure you're on main and up to date
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/repository-restructuring
```

#### Step 3.3: Create Logical Commits

```bash
# Commit 1: Contract Reorganization
git commit -m "refactor(contracts): reorganize into domain-based structure

- Move contracts from openapi/v1/ to domain-based directories
- Update all \$ref references to _common/v1/
- Reorganize baselines to match domain structure
- Update docker-compose.yml mock server paths

BREAKING CHANGE: Contract paths changed from contracts/openapi/v1/ to contracts/{domain}/v1/"

# Commit 2: Database Migration Reorganization
git commit -m "refactor(database): group migrations by logical function

- Organize migrations into 001_core_schema/, 002_pii_controls/, 003_data_governance/
- Update alembic.ini with version_locations configuration
- Preserve linear migration history
- Add database validation scripts"

# Commit 3: Documentation Consolidation
git commit -m "docs: consolidate B0.3 documentation into functional categories

- Merge PII documentation into docs/database/pii-controls.md
- Merge schema docs into docs/database/schema-governance.md
- Create docs/architecture/ with service boundaries and contract ownership
- Archive all B0.3 documents to docs/archive/implementation-phases/b0.3/
- Create evidence mapping and operational documentation"

# Commit 4: Service Boundaries
git commit -m "feat(services): add Dockerfiles and service boundaries

- Add Dockerfiles for ingestion, attribution, auth, webhooks services
- Create docker-compose.component-dev.yml for component development
- Document service boundaries with dependency graph
- Define extraction sequencing strategy"

# Commit 5: Environment Configuration
git commit -m "feat(config): add comprehensive environment configuration

- Create .env.example with 30+ environment variables
- Document all configuration categories
- Add service URL configuration"

# Commit 6: Monitoring & Operations
git commit -m "feat(monitoring): add PII monitoring and alerting

- Add Prometheus metrics configuration
- Create Grafana dashboard for PII defense
- Define alert rules for PII detection
- Create incident response playbooks"

# Commit 7: CI/CD Updates
git commit -m "ci: update workflows for new repository structure

- Update contract validation paths
- Add breaking change detection
- Update model generation scripts
- Update package.json scripts"

# Commit 8: Documentation Updates
git commit -m "docs: update contributing guidelines for new structure

- Update CONTRIBUTING.md with new contract paths
- Update backend/README.md
- Document new directory structure conventions"

# Commit 9: Deployment Scripts
git commit -m "chore(deployment): add pre-deployment validation scripts

- Add validate-pre-deployment.sh
- Add prepare-git-commits.sh
- Add deployment procedure documentation"
```

#### Step 3.4: Push to GitHub

```bash
# Push feature branch
git push origin feature/repository-restructuring

# Create pull request (via GitHub CLI or web interface)
gh pr create --title "Repository Restructuring: Enterprise-Ready Organization" \
  --body "This PR implements comprehensive repository restructuring for enterprise readiness:

- Domain-based contract organization
- Logical migration grouping
- Consolidated documentation
- Service boundary definitions
- Complete operational framework

See docs/deployment/DEPLOYMENT_PROCEDURE.md for details."
```

### Exit Gates

#### Gate 3.1: Logical Commits

**Validation**: Changes grouped by domain

**Evidence**: `git log --oneline` showing logical commit structure

---

#### Gate 3.2: CI Validation

**Validation**: All GitHub Actions workflows pass on feature branch

**Check**: GitHub Actions tab shows all workflows passing

**Evidence**: Screenshot of passing workflows

---

#### Gate 3.3: Contract Validation

**Validation**: OpenAPI specs validate successfully in CI

**Check**: Contract validation job passes

**Evidence**: CI log showing successful validation

---

#### Gate 3.4: Model Generation

**Validation**: Pydantic clients generate without errors

**Check**: Model generation job passes

**Evidence**: CI log showing successful generation

---

## PHASE 4: Post-Deployment Verification

### Objective

Verify the deployed repository functions correctly in the GitHub environment.

### Execution Steps

#### Step 4.1: Web Interface Validation

**Test Procedure**:
1. Navigate to repository on GitHub
2. Verify documentation renders correctly
3. Check all links work
4. Verify file structure is visible

**Evidence**: Screenshots of rendered documentation

---

#### Step 4.2: Clone Testing

```bash
# Clone from clean environment
cd /tmp
git clone https://github.com/{org}/skeldir-2.0.git test-clone
cd test-clone
git checkout feature/repository-restructuring

# Verify structure
ls -la contracts/
ls -la docs/database/
ls -la docs/architecture/
```

**Expected Result**: All directories present and accessible

**Evidence**: Terminal output showing successful clone

---

#### Step 4.3: Setup Verification

```bash
# Follow README.md setup instructions
cd test-clone
npm install  # If applicable
# Verify setup completes without errors
```

**Evidence**: Terminal output showing successful setup

---

#### Step 4.4: External Dependencies

**Test Procedure**:
1. Verify Docker builds work: `docker build -f backend/app/ingestion/Dockerfile .`
2. Verify npm packages install: `npm install`
3. Verify contract validation: `npm run contracts:validate`

**Evidence**: Terminal output showing successful operations

---

## PHASE 5: Enterprise Repository Activation

### Objective

Confirm the GitHub repository is fully operational and acquisition-ready.

### Execution Steps

#### Step 5.1: Acquisition Team Simulation

**Test Procedure**:
1. Share repository URL with external technical evaluator
2. Request they navigate to key documentation within 30 minutes
3. Verify they can find:
   - PII controls documentation
   - Service boundaries
   - API contracts
   - Deployment procedures

**Evidence**: Feedback from external evaluator

---

#### Step 5.2: CI/CD Pipeline Operational

**Validation**: All GitHub Actions workflows passing consistently

**Check**: Monitor workflows for 24-48 hours

**Evidence**: Screenshot of consistent passing status

---

#### Step 5.3: Documentation Ecosystem Functional

**Validation**: All cross-references, links, and generated content working

**Test Procedure**:
1. Verify all markdown links resolve
2. Check generated documentation (if applicable)
3. Verify API documentation renders

**Evidence**: Screenshot of working documentation

---

#### Step 5.4: Development Workflow Verified

**Validation**: Team can effectively perform day-to-day work

**Test Procedure**:
1. Team member creates feature branch
2. Makes contract change
3. Validates contract
4. Generates models
5. Creates PR

**Evidence**: Successful PR workflow

---

#### Step 5.5: Rollback Capability Confirmed

**Validation**: Verified ability to revert if needed

**Test Procedure**:
1. Identify rollback commit
2. Create revert branch
3. Verify revert procedure works

**Evidence**: Documented rollback procedure tested

---

## Merge to Main

Once all phases complete and exit gates pass:

```bash
# Merge PR via GitHub web interface or CLI
gh pr merge feature/repository-restructuring --squash

# Or merge via web interface with required approvals
```

---

## Post-Merge Verification

After merging to main:

1. Verify main branch builds pass
2. Verify documentation accessible
3. Notify team of new structure
4. Update any external documentation references

---

## Rollback Procedure

If critical issues discovered:

1. **Immediate**: Revert merge commit
2. **Investigation**: Identify root cause
3. **Fix**: Address issues in new PR
4. **Re-deploy**: Follow procedure again

---

## Success Criteria

The deployment is successful when:

- ✅ All CI/CD workflows passing
- ✅ Documentation accessible and functional
- ✅ Team can work effectively in new structure
- ✅ External evaluators can understand repository
- ✅ All exit gates passed with evidence

---

## Related Documentation

- **Empirical Validation Report**: `docs/archive/implementation-phases/b0.3/EMPIRICAL_VALIDATION_REPORT.md`
- **Exit Gate Evidence**: `docs/archive/implementation-phases/b0.3/PHASE*_EXIT_GATE_EVIDENCE.md`
- **Service Boundaries**: `docs/architecture/service-boundaries.md`

