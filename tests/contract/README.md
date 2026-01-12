# Contract Conformance Tests

This directory contains the contract test suites that validate both mock servers and FastAPI implementation against OpenAPI contracts.

## Test Sequence (Schmidt's Causal Chain)

**Phase 2 (Integrity):** Mock servers vs Contracts → `test_mock_integrity.py`
**Phase 3 (Provider):** Implementation vs Contracts → `test_contract_semantics.py`

### Why This Sequence Matters

1. **Integrity Tests First**: Validate contracts are internally consistent
   - Tests: Mocks serve responses that match contract schemas
   - Proves: Contract examples are valid against their own schemas
   - If fails: Fix the contract (examples violate schemas)

2. **Provider Tests Second**: Validate implementation matches contracts
   - Tests: FastAPI endpoints match contract behavior
   - Proves: Implementation conforms to validated contracts
   - If fails: Fix the implementation (divergence from contract)

### Failure Interpretation

| Integrity Result | Provider Result | Diagnosis | Action |
|---|---|---|---|
| ✓ Pass | ✓ Pass | All correct | No action |
| ✓ Pass | ✗ Fail | Implementation divergence | Fix FastAPI code |
| ✗ Fail | ✓ Pass | Impossible state | Contract has invalid examples |
| ✗ Fail | ✗ Fail | Contract issue | Fix contract first |

## Overview

Contract tests ensure that:
- Mock servers serve contract-compliant responses (integrity)
- Response status codes match contract specifications (provider)
- Response payloads validate against OpenAPI schemas (both)
- Error responses conform to RFC7807 Problem schema (provider)
- All in-scope operations are tested at least once (coverage)

## Test Structure

### Phase 2: Contract Integrity Tests

**`test_mock_integrity.py`** (NEW - Schmidt's Phase B)

Mock server validation tests that:
1. Load bundled OpenAPI specifications from `api-contracts/dist/openapi/v1/`
2. Send requests to running mock servers (localhost:4010-4012)
3. Validate mock responses against contract schemas
4. Prove contract examples are valid

**Purpose:** Verify contracts are internally consistent before testing implementation.

### Phase 3: Provider Contract Tests

**`test_contract_semantics.py`** (Existing - Jamie's Provider Tests)

Schemathesis-based tests that:
1. Load bundled OpenAPI specifications
2. Generate test cases for all operations
3. Execute requests against FastAPI app (ASGI, no network)
4. Validate responses against schemas

**Purpose:** Verify FastAPI implementation conforms to validated contracts.

### Negative Test Documentation

**`negative_tests_static.md`**
- Documents scenarios where static conformance checks should fail
- Used to validate the enforcement mechanism itself
- Examples: undeclared routes, phantom operations, parameter mismatches

**`negative_tests_dynamic.md`**
- Documents scenarios where dynamic conformance tests should fail
- Used to validate behavioral enforcement
- Examples: wrong status codes, missing fields, type mismatches

## Running Tests

### Phase 2: Mock Integrity Tests (Run First)

```bash
# Start mocks first
bash scripts/start-mocks.sh

# Run integrity tests
cd tests/contract
pytest test_mock_integrity.py -v

# Or use Makefile
make contract-integrity
```

**Expected output:** 0 failures, 100% coverage for primary mocks (auth, attribution, health)

### Phase 3: Provider Contract Tests (Run Second)

```bash
cd tests/contract
pytest test_contract_semantics.py -v

# Or use Makefile
make contract-provider
```

### Full Contract Pipeline

```bash
# Run complete sequence: bundle → integrity → provider
make contract-full
```

### Specific Tests

```bash
# Single integrity test
pytest test_mock_integrity.py::test_mock_integrity[auth] -v

# Single provider test
pytest test_contract_semantics.py::test_auth_login_happy_path -v
```

### Coverage Reports

```bash
# Integrity coverage
pytest test_mock_integrity.py::test_coverage_report -v -s

# Provider coverage
pytest test_contract_semantics.py::test_coverage_report -v -s
```

Expected output:
```
Contract Coverage Report:
  Total in-scope routes: 4
  Routes:
    - POST /api/auth/login
    - POST /api/auth/refresh
    - POST /api/auth/logout
    - GET /api/attribution/revenue/realtime
```

## Prerequisites

### Dependencies

Install test dependencies:
```bash
pip install -r backend/requirements-dev.txt
```

Key dependencies:
- `schemathesis>=3.19.0`: Spec-driven API testing
- `pytest>=7.4.0`: Test framework
- `pytest-asyncio>=0.21.0`: Async test support
- `httpx>=0.24.0`: Async HTTP client

### Bundled Specifications

Ensure OpenAPI contracts are bundled:
```bash
cd api-contracts
npx @redocly/cli bundle <domain> --output=dist/openapi/v1/<domain>.bundled.yaml --force
```

Or run full pipeline:
```bash
./scripts/contracts/pipeline.ps1
```

### Generated Models

Ensure Pydantic models are generated:
```bash
bash scripts/generate-models.sh
```

### FastAPI App

Ensure FastAPI app exists and is importable:
```bash
python -c "from app.main import app; print('✓ App imported')"
```

## Test Failures

### Understanding Failures

**Schemathesis Validation Error**:
```
Schemathesis validation error:
  Response body does not match schema for POST /api/auth/login
  Missing required property: 'session_id'
```

**Action**: Add missing field to implementation or remove from contract

**Status Code Mismatch**:
```
Response status code 201 is not defined in the schema
Allowed status codes: [200, 401, 429, 500]
```

**Action**: Change implementation status code to match contract or update contract

### Debugging Tips

1. **Inspect actual response**:
   ```python
   # Add to test
   print("Response:", response.json())
   ```

2. **Check bundled schema**:
   ```bash
   cat api-contracts/dist/openapi/v1/auth.bundled.yaml | grep -A 10 "LoginResponse"
   ```

3. **Verify Pydantic model**:
   ```python
   from backend.app.schemas.auth import LoginResponse
   print(LoginResponse.model_json_schema())
   ```

4. **Run single operation**:
   ```bash
   pytest test_contract_semantics.py -v -k "login"
   ```

## Adding New Tests

### For New Endpoints

Schemathesis automatically generates tests for all operations in bundled specs. When you add a new endpoint:

1. Add operation to OpenAPI contract
2. Bundle contracts
3. Implement route in FastAPI
4. Run tests - new operation automatically tested

### For Explicit Scenarios

Add to `test_contract_semantics.py`:

```python
def test_new_endpoint_scenario():
    """Test specific scenario for new endpoint."""
    from fastapi.testclient import TestClient
    import uuid
    
    client = TestClient(app)
    
    response = client.post(
        "/api/new/endpoint",
        json={"field": "value"},
        headers={"X-Correlation-ID": str(uuid.uuid4())}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "required_field" in data
```

## Negative Testing

To test enforcement mechanism itself:

1. Create test branch
2. Apply negative scenario from documentation
3. Run tests and verify they fail as expected
4. Delete test branch

Example:
```bash
git checkout -b test/wrong-status-code
# Modify route to return 201 instead of 200
pytest test_contract_semantics.py -v
# Should fail with status code error
git checkout main
git branch -D test/wrong-status-code
```

## CI Integration

These tests run automatically in CI via `.github/workflows/contract-enforcement.yml`:

```yaml
contract-dynamic:
  runs-on: ubuntu-latest
  steps:
    - name: Run Schemathesis Contract Tests
      run: |
        cd tests/contract
        pytest test_contract_semantics.py -v --tb=short
```

Failure blocks PR merge.

## Troubleshooting

### "Cannot import app.main"

**Cause**: Python path not set

**Solution**:
```bash
export PYTHONPATH="${PWD}/backend:${PYTHONPATH}"
```

### "Bundled specs not found"

**Cause**: Contracts not bundled

**Solution**:
```bash
cd api-contracts
npx @redocly/cli bundle <domain> --output=dist/openapi/v1/<domain>.bundled.yaml --force
```

### "Schema validation failed unexpectedly"

**Cause**: Generated models out of sync with bundled specs

**Solution**:
```bash
bash scripts/generate-models.sh
```

## References

- [Schemathesis Documentation](https://schemathesis.readthedocs.io/)
- [Contract Enforcement Guide](../../docs/implementation/contract-enforcement.md)
- [Forensic Validation Report](../../docs/forensics/implementation/contract-enforcement-validation-report.md)
- [Negative Test Scenarios - Dynamic](./negative_tests_dynamic.md)
- [Negative Test Scenarios - Static](./negative_tests_static.md)

