# PROOF_INDEX (B1.2-P0 Corrective Action)

## Hypothesis Verdicts

| Hypothesis | Verdict | Evidence Pointers |
|---|---|---|
| H01 (`403` absent on operations) | TRUE (pre-remediation), REMEDIATED | `docs/forensics/evidence/b12_p0/auth_contract_inventory.json` (`operations_with_403_problem`), `tests/contract/test_contract_semantics.py`, JWT contract files under `api-contracts/openapi/v1/*.yaml` |
| H02 (`oasdiff` sparse baseline coverage) | TRUE (pre-remediation), REMEDIATED | `.github/workflows/ci.yml` (`Detect breaking changes` now compares each bundled spec vs `origin/main`), `docs/forensics/evidence/b12_p0/B1.2-P0_Adjudication_Map.md` (`Structural Diff Coverage`) |
| H03 (worker invariants not adjudicated via `@tenant_task`) | TRUE (pre-remediation), REMEDIATED | `backend/tests/test_b07_p1_identity_guc.py` (`test_worker_tenant_task_*`), `.github/workflows/ci.yml` (`JWT Tenant Context Invariants` job executes this test file) |
| H04 (negative controls incomplete for `403` drift) | TRUE (pre-remediation), REMEDIATED | `scripts/contracts/run_negative_controls.sh` (added `6/8` 403 drift and `8/8` worker bypass controls) |

## Exit Gate Evidence Mapping

| Exit Gate | Status | Evidence |
|---|---|---|
| EG1 `403` Contract Surface Lock | PASS (repo state) | `auth_contract_inventory.json` (`operations_with_403_problem: 22`), `test_contract_auth_topology_and_error_surface` |
| EG2 `oasdiff` Coverage Lock | PASS (repo wiring) | `.github/workflows/ci.yml` (`origin/main` bundled comparison loop over all families) |
| EG3 Worker-Plane Invariant Adjudication | PASS (repo state) | `backend/tests/test_b07_p1_identity_guc.py` + CI job wiring in `.github/workflows/ci.yml` |
| EG4 Non-Vacuous CI Proof Closure | PENDING CI EXECUTION | `scripts/contracts/run_negative_controls.sh` includes required new controls; CI run links to be appended post-run |

## Reproduction Commands

```bash
# Regenerate bundles
bash scripts/contracts/bundle.sh

# Contract topology + error surface adjudication
pytest tests/contract/test_contract_semantics.py -q -k test_contract_auth_topology_and_error_surface

# HTTP tenant invariant
pytest tests/test_b060_phase1_auth_tenant.py -q -k test_missing_tenant_claim_returns_401

# Worker-plane invariants via @tenant_task
pytest backend/tests/test_b07_p1_identity_guc.py -q

# Full negative controls (CI-equivalent toolchain required: node/go/oasdiff)
bash scripts/contracts/run_negative_controls.sh

# Regenerate adjudication map artifacts
python scripts/contracts/generate_b12_p0_adjudication_map.py
```

## CI Evidence Links
- Green PR run: _to be filled after push_
- Negative-control failing runs (intentional mutation branches): _to be filled after push_
- Branch protection required-check confirmation: _to be filled after push_
