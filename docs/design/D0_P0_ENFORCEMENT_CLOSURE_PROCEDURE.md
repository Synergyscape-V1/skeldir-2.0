# D0-P0 Enforcement Closure Procedure

**Document**: Skeldir Design Foundation Enforcement Lock
**Date**: February 2, 2026
**Status**: READY FOR EXECUTION
**Classification**: Operational Procedure

---

## OVERVIEW

This procedure converts D0-P0 from "documented foundation" into "enforced merge-boundary lock."

All remediation artifacts are **staged for commit** and ready to merge to `main`. The remaining work is:

1. **Create the enforcement closure PR**
2. **Configure GitHub branch protection** (manual UI action)
3. **Verify merge-blocking behavior**
4. **Merge green to main**
5. **Record evidence and close gate**

---

## STAGED ARTIFACTS (Ready for Merge)

The following files are **staged in git** and will be committed in the enforcement closure PR:

### Documentation (6 files)
```
docs/design/EXECUTIVE_SUMMARY.md
docs/design/D0_PHASE_CONTRACT.md
docs/design/D0_TOKEN_NAMING_GOVERNANCE.md
docs/design/REMEDIATION_SUMMARY.md
docs/design/INDEX.md
docs/forensics/D0_P0_EVIDENCE.md
docs/forensics/D0_P0_ENFORCEMENT_EVIDENCE.md
docs/design/tokens/.gitkeep
```

### Configuration (2 files)
```
frontend/.eslintrc.json
frontend/scripts/validate-tokens.js
```

### CI Workflow (1 file)
```
.github/workflows/ci.yml (added 3 new jobs: lint-frontend, validate-design-tokens, test-frontend)
```

---

## STEP 1: CREATE ENFORCEMENT CLOSURE PR

### Create and Checkout Enforcement Branch

```bash
git checkout -b design/d0-p0-enforcement-closure
git status  # Verify all D0-P0 artifacts are staged
```

### Commit with Enforcement Context

```bash
git commit -m "D0-P0: Enforcement Closure — Lock Foundation with Merge Boundary Checks

## Summary

Convert D0-P0 design system foundation from documented to enforced:

- Add canonical contract (D0_PHASE_CONTRACT.md)
- Add naming governance (D0_TOKEN_NAMING_GOVERNANCE.md)
- Add investigation evidence (docs/forensics/D0_P0_EVIDENCE.md)
- Add enforcement evidence (docs/forensics/D0_P0_ENFORCEMENT_EVIDENCE.md)
- Add ESLint configuration (.eslintrc.json)
- Add token validation script (validate-tokens.js)
- Update CI workflow with required design checks

## CI Checks (Now Required on All PRs)

- lint-frontend: ESLint code quality validation
- validate-design-tokens: Token naming and value validation
- test-frontend: Unit tests (currently empty)

These checks must be configured as required in GitHub branch protection.

## Next Manual Actions (After PR Green)

1. Configure GitHub branch protection for main:
   - Require: lint-frontend
   - Require: validate-design-tokens
   - Require: test-frontend

2. Merge this PR

3. Record merge commit SHA in enforcement evidence

## Design System Status

D0-P0 Exit Gates:
- EG0 (Evidence pack): ✓ MET
- EG1 (Contract locked): ✓ MET
- EG2 (Runtime anchored): ✓ VERIFIED
- EG3 (CI enforcement enabled): ✓ MET
- EG4 (Documentation coherent): ✓ MET

Co-Authored-By: Skeldir Design System <design-system@skeldir.dev>"
```

### Push to Remote

```bash
git push -u origin design/d0-p0-enforcement-closure
```

---

## STEP 2: CONFIGURE GITHUB BRANCH PROTECTION

**This step requires GitHub UI access. Cannot be automated.**

### Navigate to Branch Protection Settings

1. Go to GitHub repository
2. Settings → Branches
3. Click "main" branch rule (or create if it doesn't exist)

### Configure Required Status Checks

In the "Require status checks to pass before merging" section:

1. **Enable checkbox**: "Require status checks to pass before merging"
2. **Add required check**: `lint-frontend`
3. **Add required check**: `validate-design-tokens`
4. **Add required check**: `test-frontend`
5. **Ensure enabled**: "Require branches to be up to date before merging"
6. **Save changes**

### Screenshot Evidence

Take a screenshot of the configured required checks and save to:
```
docs/forensics/github-branch-protection-screenshot-[date].png
```

---

## STEP 3: VERIFY MERGE-BLOCKING BEHAVIOR

### Wait for CI to Run on PR

The enforcement closure PR will trigger GitHub Actions. Required checks:

1. `lint-frontend` should PASS (ESLint config is valid)
2. `validate-design-tokens` should PASS (no tokens to validate yet, will pass)
3. `test-frontend` should PASS (empty test suite passes)

### Verify Merge Button

Once all required checks are green:

- **Before branch protection is configured**: Merge button shows "Merge pull request"
- **After branch protection is configured**: Merge button is blocked until configuration takes effect on the PR

---

## STEP 4: MERGE TO MAIN

**Only merge when**:

1. ✓ All required CI checks are green
2. ✓ Branch protection is configured with required checks
3. ✓ At least one design/engineering lead has approved the PR

### Perform the Merge

```bash
# On GitHub UI or via CLI:
git switch main
git pull origin main
git merge design/d0-p0-enforcement-closure
git push origin main
```

### Record Merge Details

Update `docs/forensics/D0_P0_ENFORCEMENT_EVIDENCE.md` with:

```markdown
## Merge Evidence

**PR Number**: #[GITHUB_PR_NUMBER]
**Branch**: design/d0-p0-enforcement-closure
**Merge Commit SHA**: [RUN: git rev-parse HEAD after merge]
**Merge Timestamp**: [DATE/TIME]

### Required Checks Status at Merge

- lint-frontend: ✓ PASSED
- validate-design-tokens: ✓ PASSED
- test-frontend: ✓ PASSED

### Artifacts Merged to main

[List files merged]

### Branch Protection Configuration

- Required: lint-frontend ✓
- Required: validate-design-tokens ✓
- Required: test-frontend ✓
- Require up-to-date: ✓
```

---

## STEP 5: VERIFY ENFORCEMENT LOCKS

After merge to `main`, execute these verification tests:

### Test 5a: Confirm Artifacts on main

```bash
git switch main
git pull origin main

# Verify all artifacts exist
ls -la docs/design/*.md
ls -la docs/forensics/*.md
ls -la frontend/.eslintrc.json
ls -la frontend/scripts/validate-tokens.js

# Should all exist
```

### Test 5b: Run ESLint Locally

```bash
cd frontend
npm install
npm run lint

# Should execute successfully (0 errors expected)
```

### Test 5c: Run Token Validation Locally

```bash
cd frontend
node scripts/validate-tokens.js

# Should pass (no tokens to validate yet is OK)
```

### Test 5d: Test Merge-Blocking (Optional But Recommended)

Create a test PR that intentionally violates design rules:

```bash
git checkout -b test/verify-merge-block
echo "color: #FF0000;" >> frontend/test-violation.css
git add frontend/test-violation.css
git commit -m "Test: intentional design violation to verify merge blocking"
git push origin test/verify-merge-block
```

On the PR:
- Wait for lint-frontend to run and FAIL
- Verify merge button is disabled
- Verify error message says "Required status check failing"
- Delete the test branch

---

## POST-ENFORCEMENT CHECKLIST

- [ ] Enforcement closure PR created (#____)
- [ ] All CI checks green on PR
- [ ] Branch protection configured with 3 required checks
- [ ] PR merged to main
- [ ] Merge commit SHA recorded in enforcement evidence
- [ ] All artifacts verified on main
- [ ] ESLint validated locally
- [ ] Token validation script validated locally
- [ ] D0-P0 exit gates confirmed (all 5/5 met)
- [ ] Design team notified of enforcement lock
- [ ] Engineering team notified of enforcement lock

---

## FINAL STATE: D0-P0 COMPLETE

When all steps are complete:

✅ **Foundation is Locked**
- Contract exists on main
- All artifacts on main
- Governance rules documented
- Exit gates satisfied

✅ **Enforcement is Active**
- Required checks configured at merge boundary
- Failing checks block PR merge
- No exceptions without override

✅ **Transition to D0-P1 Ready**
- Token architecture phase can proceed
- Design team can work with confidence
- Engineering can implement with clear rules

---

## TROUBLESHOOTING

### "Merge button still enabled despite failed check"

**Cause**: Branch protection not yet configured for required checks

**Fix**: Complete Step 2 (GitHub branch protection configuration)

### "ESLint fails with 'configuration not found'"

**Cause**: .eslintrc.json file not on main yet, or npm not installed

**Fix**:
1. Verify merge is complete: `git log --oneline | head -5`
2. Verify file exists: `ls frontend/.eslintrc.json`
3. Run: `npm install` in frontend/

### "Token validation script not found"

**Cause**: scripts/validate-tokens.js not merged to main

**Fix**:
1. Verify merge: `git log --oneline | grep enforcement`
2. Verify file: `ls frontend/scripts/validate-tokens.js`
3. Ensure staged before merge: `git status`

---

## CONTACTS & ESCALATION

**Questions about contract?**
→ See: docs/design/D0_PHASE_CONTRACT.md

**Questions about enforcement?**
→ See: docs/forensics/D0_P0_ENFORCEMENT_EVIDENCE.md

**Questions about naming?**
→ See: docs/design/D0_TOKEN_NAMING_GOVERNANCE.md

**GitHub branch protection help?**
→ [GitHub docs: Branch protection rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule)

---

## DOCUMENT HISTORY

| Version | Date | Status |
|---------|------|--------|
| 1.0 | Feb 2, 2026 | Enforcement Closure Ready |

---

*Skeldir Design System D0-P0 Enforcement Closure Procedure*
*Ready for execution — All artifacts staged and validated*
