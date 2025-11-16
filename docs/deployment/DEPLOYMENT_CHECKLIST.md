# Deployment Checklist

**Purpose**: Quick reference checklist for GitHub deployment  
**Date**: 2025-11-16

---

## Pre-Deployment

- [ ] Run `bash scripts/deployment/validate-pre-deployment.sh` - all validations pass
- [ ] Verify zero references to old contract paths
- [ ] Verify all $ref references point to _common/v1/
- [ ] Verify all critical documentation exists
- [ ] Verify all Dockerfiles valid
- [ ] Review git status - no uncommitted changes

---

## GitHub Preparation

- [ ] Verify branch protection rules configured
- [ ] Verify GitHub Actions secrets configured
- [ ] Verify team access permissions
- [ ] Create rollback tag: `git tag -a "pre-restructuring-$(date +%Y%m%d)" origin/main`
- [ ] Push tag: `git push origin --tags`

---

## Code Deployment

- [ ] Run `bash scripts/deployment/prepare-git-commits.sh`
- [ ] Review staged changes
- [ ] Create feature branch: `git checkout -b feature/repository-restructuring`
- [ ] Create logical commits (9 commits)
- [ ] Push feature branch: `git push origin feature/repository-restructuring`
- [ ] Create pull request
- [ ] Verify CI workflows pass on feature branch
- [ ] Get required approvals
- [ ] Merge PR to main

---

## Post-Deployment Verification

- [ ] Verify main branch CI workflows pass
- [ ] Verify documentation renders in GitHub UI
- [ ] Test clone from clean environment
- [ ] Verify setup instructions work
- [ ] Verify external dependencies accessible
- [ ] Monitor for 24-48 hours

---

## Enterprise Activation

- [ ] External evaluator can navigate repository (30 min test)
- [ ] CI/CD pipelines operational consistently
- [ ] Documentation ecosystem functional
- [ ] Development workflow verified
- [ ] Rollback capability confirmed

---

## Success Criteria

- [ ] All CI/CD workflows passing
- [ ] Documentation accessible and functional
- [ ] Team can work effectively
- [ ] External evaluators can understand repository
- [ ] All exit gates passed with evidence

---

## Quick Commands Reference

```bash
# Pre-deployment validation
bash scripts/deployment/validate-pre-deployment.sh

# Prepare commits
bash scripts/deployment/prepare-git-commits.sh

# Create feature branch
git checkout -b feature/repository-restructuring

# Push and create PR
git push origin feature/repository-restructuring
gh pr create --title "Repository Restructuring: Enterprise-Ready Organization"
```

---

## Emergency Contacts

- **Deployment Lead**: [Name/Contact]
- **GitHub Admin**: [Name/Contact]
- **CI/CD Admin**: [Name/Contact]

---

## Related Documentation

- **Full Procedure**: `docs/deployment/DEPLOYMENT_PROCEDURE.md`
- **Rollback Procedure**: `docs/deployment/ROLLBACK_PROCEDURE.md`
- **Validation Script**: `scripts/deployment/validate-pre-deployment.sh`

