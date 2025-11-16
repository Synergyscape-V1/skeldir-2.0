# Deployment Documentation

**Purpose**: Comprehensive deployment documentation for repository restructuring  
**Date**: 2025-11-16

---

## Overview

This directory contains all documentation and scripts required for deploying the restructured SKELDIR 2.0 repository to GitHub.

---

## Documentation Files

### [DEPLOYMENT_PROCEDURE.md](./DEPLOYMENT_PROCEDURE.md)

Complete step-by-step procedure for deploying the restructured repository to GitHub. Includes:

- Pre-deployment validation
- GitHub repository preparation
- Structured code deployment
- Post-deployment verification
- Enterprise activation

**Use this for**: Full deployment process

---

### [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)

Quick reference checklist for deployment. Includes:

- Pre-deployment tasks
- GitHub preparation
- Code deployment steps
- Post-deployment verification
- Success criteria

**Use this for**: Quick reference during deployment

---

### [ROLLBACK_PROCEDURE.md](./ROLLBACK_PROCEDURE.md)

Procedure for reverting repository restructuring if critical issues are discovered. Includes:

- Rollback scenarios
- Step-by-step rollback procedure
- Rollback verification
- Post-rollback actions

**Use this for**: Emergency rollback situations

---

## Scripts

### `scripts/deployment/validate-pre-deployment.sh`

Bash script for pre-deployment validation. Validates:

- Path consistency (no old paths)
- Contract integrity ($ref references)
- Navigation (documentation exists)
- Build readiness (Dockerfiles valid)

**Usage**:
```bash
bash scripts/deployment/validate-pre-deployment.sh
```

**Exit Code**: 0 = pass, 1 = fail

---

### `scripts/deployment/validate-pre-deployment.ps1`

PowerShell version of validation script for Windows.

**Usage**:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\deployment\validate-pre-deployment.ps1
```

---

### `scripts/deployment/prepare-git-commits.sh`

Bash script to stage changes in logical groups for clean git history.

**Usage**:
```bash
bash scripts/deployment/prepare-git-commits.sh
```

**Note**: Review staged changes before committing

---

## Deployment Phases

### Phase 1: Pre-Deployment Validation

**Objective**: Verify all changes complete and consistent

**Script**: `validate-pre-deployment.sh` or `validate-pre-deployment.ps1`

**Exit Gates**: All validations pass

---

### Phase 2: GitHub Preparation

**Objective**: Prepare GitHub repository

**Tasks**:
- Verify branch protection
- Verify secrets
- Verify permissions
- Create rollback tag

---

### Phase 3: Structured Deployment

**Objective**: Deploy with clean git history

**Script**: `prepare-git-commits.sh`

**Tasks**:
- Create feature branch
- Create logical commits
- Push to GitHub
- Create PR
- Verify CI passes

---

### Phase 4: Post-Deployment Verification

**Objective**: Verify deployment successful

**Tasks**:
- Verify CI workflows
- Test clone
- Verify documentation
- Test setup

---

### Phase 5: Enterprise Activation

**Objective**: Confirm acquisition-ready

**Tasks**:
- External evaluator test
- CI/CD operational
- Documentation functional
- Team workflow verified

---

## Quick Start

1. **Validate**: Run validation script
   ```bash
   bash scripts/deployment/validate-pre-deployment.sh
   ```

2. **Prepare**: Stage changes
   ```bash
   bash scripts/deployment/prepare-git-commits.sh
   ```

3. **Deploy**: Follow [DEPLOYMENT_PROCEDURE.md](./DEPLOYMENT_PROCEDURE.md)

4. **Verify**: Complete post-deployment checks

---

## Support

For issues or questions:

1. Review [DEPLOYMENT_PROCEDURE.md](./DEPLOYMENT_PROCEDURE.md)
2. Check [ROLLBACK_PROCEDURE.md](./ROLLBACK_PROCEDURE.md) if issues occur
3. Review validation script output for specific errors

---

## Related Documentation

- **Empirical Validation**: `docs/archive/implementation-phases/b0.3/EMPIRICAL_VALIDATION_REPORT.md`
- **Exit Gate Evidence**: `docs/archive/implementation-phases/b0.3/PHASE*_EXIT_GATE_EVIDENCE.md`
- **Service Boundaries**: `docs/architecture/service-boundaries.md`

