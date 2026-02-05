# B0.7-P0 Evidence Note - Non-Vacuous Contracts + CI Runtime Proof Harness

## Scope (what this phase added)

This phase adds **non-vacuous, falsifiable** guardrails so B0.7 provider work cannot drift:

1. **Provider boundary path exists and is non-empty**
   - Stub module: `backend/app/llm/provider_boundary.py`
   - Imported by core worker seam: `backend/app/workers/llm.py`
   - Unit test proving callable stub behavior: `backend/tests/test_b07_p0_provider_boundary_stub.py`

2. **Machine-checkable write-shape contract exists**
   - Contract artifact: `contracts-internal/llm/b07_llm_api_calls_write_contract.json`
   - Validator (Pydantic): `scripts/ci/validate_llm_write_contract.py`
   - Negative control: `backend/tests/fixtures/b07_p0_invalid_llm_write_contract.json`
   - Tests: `backend/tests/test_b07_p0_llm_write_contract_validation.py`

3. **Non-vacuous "wrapper-only dependency" enforcement exists**
   - Scanner: `scripts/ci/enforce_llm_provider_boundary.py`
   - Negative control fixture (text -> temp .py in test): `backend/tests/fixtures/forbidden_provider_import_fixture.txt`
   - Tests: `backend/tests/test_b07_p0_provider_boundary_enforcement.py`

4. **CI runtime substrate proof includes worker (DB broker/backend)**
   - Compose worker service: `docker-compose.e2e.yml` (`worker`)
   - CI job starts DB+API stack, applies migrations, then starts worker and proves `/health/worker`:
     - Workflow: `.github/workflows/ci.yml` job `b060-phase6-e2e`
     - Probe script: `scripts/wait_for_e2e_worker.py`
   - Compose logs are always captured and uploaded:
     - Artifact: `b060-phase6-e2e-artifacts`
     - File: `artifacts/b060-phase6-e2e/compose.log`

5. **DB parity scaffold distinguishes artifact validation vs runtime schema**
   - Contract separates `current_row_shape` (enforced) vs `target_row_shape` (reported).
   - DB parity checker: `scripts/ci/llm_contract_db_parity.py`
   - Negative controls (non-vacuous): `backend/tests/test_b07_p0_llm_contract_db_parity.py`

## CI proof run links (PR #51)

Repository: `https://github.com/Muk223/skeldir-2.0`

- EG-P0-3 (provider boundary scanner non-vacuous):
  - CI run: `https://github.com/Muk223/skeldir-2.0/actions/runs/21722925971/job/62657346360`
  - Notes: `backend/tests/test_b07_p0_provider_boundary_enforcement.py` asserts scanner fails on a meaningful violation (temp file).

- EG-P0-4 (compose substrate bring-up + worker proof):
  - CI run: `https://github.com/Muk223/skeldir-2.0/actions/runs/21722925971/job/62657346403`
  - Notes: `scripts/wait_for_e2e_worker.py` must pass (200 + `"worker":"ok"` from `/health/worker`).
  - Debug artifacts: `b060-phase6-e2e-artifacts` -> `compose.log`

- EG-F1-4 (current schema parity enforced):
  - CI run: `https://github.com/Muk223/skeldir-2.0/actions/runs/21722925971/job/62657346403`
  - Notes: `scripts/ci/llm_contract_db_parity.py --shape current_row_shape --mode enforce`

- EG-F1-5 (target schema drift reported):
  - CI run: `https://github.com/Muk223/skeldir-2.0/actions/runs/21722925971/job/62657346403`
  - Artifact: `b060-phase6-e2e-artifacts` -> `llm_contract_target_report.txt`

- EG-F1-3 (non-vacuity / negative controls):
  - CI run: `https://github.com/Muk223/skeldir-2.0/actions/runs/21722925971/job/62657346360`
  - Notes: `backend/tests/test_b07_p0_llm_contract_db_parity.py` forces mismatch and asserts non-zero exit in enforce mode.

## Local reproduction (Linux / CI-equivalent)

Bring up DB+API+mock, apply migrations, then start worker and probe:

```bash
docker compose -f docker-compose.e2e.yml up -d --build postgres mock_platform api
export MIGRATION_DATABASE_URL="postgresql://skeldir:skeldir_e2e@127.0.0.1:5432/skeldir_e2e"
alembic upgrade head
docker compose -f docker-compose.e2e.yml up -d worker
python scripts/wait_for_e2e_health.py
python scripts/wait_for_e2e_worker.py
```

Teardown:

```bash
docker compose -f docker-compose.e2e.yml down -v
```
