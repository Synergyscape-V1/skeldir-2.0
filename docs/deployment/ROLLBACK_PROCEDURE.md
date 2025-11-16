# Rollback Procedure

**Purpose**: Document procedure to revert repository restructuring if critical issues are discovered  
**Date**: 2025-11-16

---

## Rollback Scenarios

### Scenario 1: Pre-Merge Issues

**Condition**: Issues discovered before PR merge to main

**Procedure**:
1. Fix issues in feature branch
2. Push fixes to feature branch
3. Re-run CI validation
4. Proceed with merge after fixes verified

**No rollback needed** - fixes applied in feature branch

---

### Scenario 2: Post-Merge Critical Issues

**Condition**: Critical issues discovered after merge to main

**Procedure**:

#### Step 1: Identify Rollback Point

```bash
# Find commit before restructuring
git log --oneline | grep "pre-restructuring"

# Or use tag
git tag -l "pre-restructuring-*"
```

#### Step 2: Create Revert Branch

```bash
# Checkout main
git checkout main
git pull origin main

# Create revert branch from pre-restructuring tag
git checkout -b revert/restructuring pre-restructuring-20251116

# Or from specific commit
git checkout -b revert/restructuring <commit-hash>
```

#### Step 3: Verify Revert State

```bash
# Verify structure matches pre-restructuring
ls contracts/  # Should show old structure
ls alembic/versions/  # Should show flat structure
```

#### Step 4: Create Revert PR

```bash
# Push revert branch
git push origin revert/restructuring

# Create PR
gh pr create --title "Revert: Repository Restructuring" \
  --body "Reverting repository restructuring due to critical issues.

This reverts the restructuring changes and restores the previous structure.

Issues encountered:
- [List issues]

After revert, we will:
- [List remediation steps]"
```

#### Step 5: Merge Revert PR

- Get required approvals
- Merge to main
- Verify main branch is functional

---

### Scenario 3: Partial Rollback

**Condition**: Only specific components need rollback

**Procedure**:

#### Option A: Revert Specific Commits

```bash
# Identify commits to revert
git log --oneline | grep "refactor(contracts)"

# Revert specific commit
git revert <commit-hash>

# Push revert
git push origin main
```

#### Option B: Manual Fix

1. Identify problematic component
2. Create fix branch
3. Restore previous structure for that component
4. Update references
5. Create PR with fix

---

## Rollback Verification

After rollback:

1. **CI/CD**: Verify all workflows pass
2. **Documentation**: Verify links work
3. **Team**: Verify team can work effectively
4. **External**: Verify external access works

---

## Post-Rollback Actions

1. **Root Cause Analysis**: Document why rollback was necessary
2. **Remediation Plan**: Create plan to address issues
3. **Re-deployment Plan**: Plan for re-deployment after fixes
4. **Communication**: Notify team of rollback and plan

---

## Prevention

To minimize rollback risk:

1. **Thorough Testing**: Complete all pre-deployment validations
2. **Incremental Deployment**: Deploy in phases with validation
3. **Feature Flags**: Use feature flags for gradual rollout (if applicable)
4. **Monitoring**: Monitor repository after deployment
5. **Team Communication**: Keep team informed of changes

---

## Rollback Checklist

- [ ] Identify rollback point (tag or commit)
- [ ] Create revert branch
- [ ] Verify revert state matches expectations
- [ ] Create revert PR
- [ ] Get approvals
- [ ] Merge revert PR
- [ ] Verify main branch functional
- [ ] Document root cause
- [ ] Create remediation plan
- [ ] Communicate to team

---

## Related Documentation

- **Deployment Procedure**: `docs/deployment/DEPLOYMENT_PROCEDURE.md`
- **Pre-Deployment Validation**: `scripts/deployment/validate-pre-deployment.sh`

