# B055 Phase 5 Remediation Evidence

## Repo Pin (Adjudicated)
- PR: https://github.com/Muk223/skeldir-2.0/pull/22
- ADJUDICATED_SHA: see bundle `MANIFEST.json` field `adjudicated_sha`
- Artifact rule: `b055-evidence-bundle-${ADJUDICATED_SHA}`
- CI run identity: authoritative in bundle `MANIFEST.json` (`workflow_run_id`, `run_attempt`)

## Enforcement (Fail-Closed)
- Hermeticity scan log: bundle `LOGS/hermeticity_scan.log`
- Determinism scan log: bundle `LOGS/determinism_scan.log`

## Cohesion Proofs (Tests)
- Proof log: bundle `LOGS/pytest_b055.log`
- Coverage includes:
  - `backend/tests/test_b055_llm_payload_fidelity.py`
  - `backend/tests/test_b055_matview_boundary.py`
  - `backend/tests/test_b055_tenant_propagation.py`
  - `backend/tests/test_b052_queue_topology_and_dlq.py`
  - `backend/tests/test_b055_llm_worker_stubs.py`

## Evidence Bundle (Phase 4 Adjudication)
- Generator: `scripts/ci/b055_evidence_bundle.py`
- Artifact name rule: `b055-evidence-bundle-${ADJUDICATED_SHA}`
- Manifest fields required:
  - `adjudicated_sha`
  - `pr_head_sha`
  - `github_sha`
  - `workflow_run_id`
  - `run_attempt`
- Required logs present in bundle:
  - `LOGS/hermeticity_scan.log`
  - `LOGS/determinism_scan.log`
  - `LOGS/pytest_b055.log`
  - `LOGS/migrations.log`

## Adjudication Proof (Latest)
- PR link: https://github.com/Muk223/skeldir-2.0/pull/22
- ADJUDICATED_SHA: `cfac454d4fc7d20eccfaba4acb6f1087030b3e66`
- Artifact name: `b055-evidence-bundle-cfac454d4fc7d20eccfaba4acb6f1087030b3e66`
- Manifest binding (from bundle `MANIFEST.json`):
  - `adjudicated_sha`: `cfac454d4fc7d20eccfaba4acb6f1087030b3e66`
  - `pr_head_sha`: `cfac454d4fc7d20eccfaba4acb6f1087030b3e66`
  - `github_sha`: `ce2957a1fd0c30f4b25e2ca7bdcfc300237b6c96`
  - `workflow_run_id`: `21011865546`
  - `run_attempt`: `1`
- Adjudicated checkout log (CI job `Checkout Code`):
  ```
  PR_HEAD_SHA=cfac454d4fc7d20eccfaba4acb6f1087030b3e66
  MERGE_SHA=30198ea9a8b7950d38c24966946c835af4dfa8bc
  GITHUB_SHA=ce2957a1fd0c30f4b25e2ca7bdcfc300237b6c96
  ADJUDICATED_SHA=cfac454d4fc7d20eccfaba4acb6f1087030b3e66
  HEAD_SHA=$(git rev-parse HEAD)
  ```
