# Replit Baseline Validation - Execution Instructions

**Status**: ⚠️ PREREQUISITE - Must complete before CI becomes authoritative  
**Blocker**: CI workflow cannot be trusted until Replit environment validated  
**Timeline**: Execute immediately in Replit

---

## Critical Context

The GitHub Actions CI workflow (`.github/workflows/empirical-validation.yml`) is designed to be the **single source of empirical truth**. However, it can only serve this role if the target operational environment (Replit) is proven capable of running the backend stack.

**This baseline validation must pass before CI results are considered authoritative.**

---

## Prerequisites

Before running validation:

1. **Access Replit**: Open your Replit project
2. **Verify Procfile exists**: Confirms service orchestration is configured
3. **Environment variables set**:
   ```bash
   # Check in Replit Secrets:
   DATABASE_URL=postgresql://...
   PGDATA=/path/to/pgdata  # If using Replit PostgreSQL
   PGSOCKET=/path/to/socket
   ```

---

## Execution Steps

### 1. Upload Validation Script

In Replit shell:
```bash
# Ensure script is executable
chmod +x scripts/baseline_validation_replit.sh
```

### 2. Run Baseline Validation

```bash
# Execute validation
bash scripts/baseline_validation_replit.sh
```

**Expected Duration**: 2-3 minutes

### 3. Monitor Output

Watch for:
```
✓ Multi-process feasibility: VALIDATED
✓ Database operations: INSERT, SELECT, DROP verified  
✓ Bayesian model: EXECUTED SUCCESSFULLY
✓ BASELINE VALIDATION: PASSED
```

### 4. Review Artifacts

```bash
# View summary
cat baseline_validation/VALIDATION_REPORT.txt

# Check process snapshot
cat baseline_validation/process_snapshot.txt

# Verify database connection
cat baseline_validation/db_version.txt

# Review model run
cat baseline_validation/bayesian_model_run.txt
```

---

## Success Criteria

### 1. Multi-Process Feasibility ✓

**Required Evidence**:
- `process_snapshot.txt` shows:
  - ≥1 uvicorn process
  - ≥1 celery process
  - ≥1 redis process
  - ≥1 postgres process
- `health_check.txt` shows HTTP 200 from FastAPI
- `port_bindings.txt` shows ports 8000, 6379, 5432 listening

**Failure Modes**:
- Processes crash immediately after start
- OOM (Out of Memory) errors in logs
- Port conflicts
- Missing dependencies

### 2. Database Connection ✓

**Required Evidence**:
- `db_version.txt` contains PostgreSQL version string
- `db_operations.txt` shows:
  - CREATE TABLE success
  - INSERT success
  - SELECT returns data
  - DROP TABLE success
  - Final message "Database operations: SUCCESS"
- `alembic_current.txt` shows migration tracking works

**Failure Modes**:
- Connection refused
- Authentication failure
- Permission denied on operations
- Extension limitations

### 3. Statistical Model Execution ✓

**Required Evidence**:
- `python_scientific_env.txt` shows:
  - ✓ numpy
  - ✓ pandas
  - ✓ scipy
  - ✓ matplotlib
  - ✓ pymc
  - ✓ arviz
- `bayesian_model_run.txt` contains:
  - "Sampling complete"
  - R-hat values < 1.01
  - ESS values > 100
  - "Statistical model execution: SUCCESS"

**Failure Modes**:
- PyMC not installable (Python version incompatibility)
- Memory constraints during sampling
- Incomplete chains
- Convergence failures

---

## Troubleshooting

### Issue: Services Don't Start

**Symptoms**: Process count = 0

**Solutions**:
```bash
# Check if Procfile exists
ls -la Procfile

# Try manual service start
postgres -D $PGDATA &
redis-server --port 6379 &
cd backend && uvicorn app.main:app --port 8000 &
```

### Issue: Database Connection Fails

**Symptoms**: "connection refused" in db_version.txt

**Solutions**:
```bash
# Check if PostgreSQL is running
ps aux | grep postgres

# Test connection manually
psql $DATABASE_URL -c "SELECT 1;"

# Check environment variables
echo $DATABASE_URL
echo $PGDATA
```

### Issue: PyMC Not Available

**Symptoms**: "PyMC not available" in validation output

**Solutions**:
```bash
# Check Python version (must be 3.11-3.13)
python --version

# Install scientific stack
cd backend
pip install -r requirements-science.txt

# Or manual install
pip install pymc arviz numpy pandas scipy matplotlib
```

### Issue: Out of Memory

**Symptoms**: Processes killed, "Killed" in logs

**Solutions**:
- Reduce Bayesian model complexity (fewer chains, samples)
- Use smaller datasets
- Disable services not immediately needed
- Consider Replit resource upgrade

---

## After Validation Passes

1. **Commit Artifacts**:
```bash
# Add baseline validation artifacts to git
git add baseline_validation/
git commit -m "chore: add Replit baseline validation artifacts"
git push
```

2. **Document in Evidence Registry**:
```bash
# Copy to evidence registry
mkdir -p evidence_registry/baseline/
cp -r baseline_validation/* evidence_registry/baseline/

git add evidence_registry/baseline/
git commit -m "docs: document Replit baseline validation"
git push
```

3. **Unlock CI Pipeline**:
   - With baseline validation passed, CI workflow results are now authoritative
   - Proceed to push `.github/workflows/empirical-validation.yml`
   - CI artifacts become compliance source of truth

4. **Create Compliance Gate**:
   - Add baseline validation check to CI workflow
   - Ensure baseline artifacts exist before allowing CI runs
   - Document baseline validation timestamp in CI logs

---

## Failure Recovery

If baseline validation fails:

### Critical Failures (Block CI)
- Multi-process feasibility fails → Cannot orchestrate backend
- Database connection fails → Cannot persist data
- PyMC unavailable → Cannot execute statistical validation

**Action**: Do NOT proceed to CI implementation. Resolve blockers first.

### Non-Critical Warnings
- Prism mock not available → CI can use alternative mocking
- Alembic not configured → Can be addressed in CI setup
- Single extension missing → Document limitation

**Action**: Document in baseline report, may proceed with CI if core services work.

---

## Integration with CI Workflow

Once baseline validation passes, the CI workflow will:

1. **Reference Baseline**: CI job comments should link to baseline artifacts
2. **Reproduce Environment**: CI uses same Python version, packages, services
3. **Extend Validation**: CI adds more rigorous checks on top of baseline
4. **Archive Evidence**: CI artifacts become primary compliance record

**Baseline → Feasibility Proof**  
**CI → Continuous Compliance Verification**

---

## Checklist Before CI Authorization

- [ ] Baseline validation script executed in Replit
- [ ] `baseline_validation/VALIDATION_REPORT.txt` shows "PASSED"
- [ ] All three validation categories successful:
  - [ ] Multi-process feasibility
  - [ ] Database connection
  - [ ] Statistical model execution
- [ ] Artifacts committed to evidence registry
- [ ] Timestamp and environment documented
- [ ] No critical blockers or unresolved failures

**Only after ALL items checked may CI workflow become authoritative.**

---

## Timeline

| Phase | Task | Duration | Status |
|-------|------|----------|--------|
| **Now** | Execute baseline validation in Replit | 5 min | ⏳ PENDING |
| **After Pass** | Commit baseline artifacts | 2 min | ⏸️ BLOCKED |
| **Then** | Push CI workflow to GitHub | 1 min | ⏸️ BLOCKED |
| **Then** | CI runs and generates evidence | 10 min | ⏸️ BLOCKED |
| **Finally** | Download CI artifacts, verify compliance | 5 min | ⏸️ BLOCKED |

**Current blocker**: Baseline validation must complete successfully.

---

**Execute `baseline_validation_replit.sh` in Replit now to unblock directive compliance pipeline.**
