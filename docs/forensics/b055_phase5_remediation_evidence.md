# B055 Phase 5 Remediation Evidence

## Repo Pin
- Branch: b055-phase5-fullpass
- Head SHA: 56e81e83ceed8f7f1f4b3287d8cd26af7174c0ac
- PR: N/A (local branch not pushed)
- CI run: N/A (no CI run yet)

## Phase 5 Preflight Findings
1. CI hermeticity enforcement hook: `.github/workflows/ci.yml` → job `celery-foundation` → step `Enforce hermetic runtime imports (Phase 5)`.
2. LLM API router presence: none in `backend/app/api/` (files present: `attribution.py`, `auth.py`, `health.py`, `webhooks.py`).
3. Tenant-scoped Celery tasks beyond LLM:
   - `backend/app/tasks/maintenance.py`: `refresh_matview_for_tenant`, `scan_for_pii_contamination_task`, `enforce_data_retention_task` (all `@tenant_task`).
   - `backend/app/tasks/attribution.py`: `recompute_window` (`@tenant_task`).
4. Matview refresh session/role: `backend/app/matviews/executor.py` uses SQLAlchemy `engine.begin()` and psycopg2 `refresh_single()` with `_build_sync_dsn()` derived from `settings.DATABASE_URL` and explicit `set_config('app.current_tenant_id', ...)`.

## Enforcement (Fail-Closed)
- Hermeticity scan: `scripts/ci/enforce_runtime_hermeticity.py` (CI step writes `LOGS/hermeticity_scan.log`).
- Determinism scan: `scripts/ci/enforce_runtime_determinism.py` (CI step writes `LOGS/determinism_scan.log`).

## Cohesion Proofs (Tests)
- API→broker payload fidelity: `backend/tests/test_b055_llm_payload_fidelity.py`
- Routing determinism under concurrency: `backend/tests/test_b052_queue_topology_and_dlq.py`
- DLQ concurrency stability: `backend/tests/test_b052_queue_topology_and_dlq.py`
- Matview boundary invariant: `backend/tests/test_b055_matview_boundary.py`
- Non-LLM tenant propagation: `backend/tests/test_b055_tenant_propagation.py`
- Stub determinism/idempotency: `backend/tests/test_b055_llm_worker_stubs.py`

## Evidence Bundle (Phase 4 Adjudication)
- Generator: `scripts/ci/b055_evidence_bundle.py`
- Artifact name: `b055-evidence-bundle-${B055_PR_HEAD_SHA}`
- Required logs: `LOGS/hermeticity_scan.log`, `LOGS/determinism_scan.log`, `LOGS/pytest_b055.log`, `LOGS/migrations.log`

## Required CI Updates (To Complete Phase 5)
- Push branch to origin and open PR.
- Run CI on PR head SHA; capture run ID + artifact URL.
- Update this file with PR link, CI run ID, and artifact name bound to PR head SHA.
# B055 Phase 5 Remediation Evidence

## Repo Pin
- Branch: b055-phase3-eg9-topology-idempotency-remediation
- Head SHA: 214a98d7dbe0312a8b682732d1e550cbcbe54666
- PR: pending
- CI run: pending

## Phase 5 Preflight Findings
1. CI hermeticity enforcement hook: `.github/workflows/ci.yml` → job `celery-foundation` → step `Enforce hermetic runtime imports (Phase 5)`.
2. LLM API router presence: none in `backend/app/api/` (files present: `attribution.py`, `auth.py`, `health.py`, `webhooks.py`).
3. Tenant-scoped Celery tasks beyond LLM:
   - `backend/app/tasks/maintenance.py`: `refresh_matview_for_tenant`, `scan_for_pii_contamination_task`, `enforce_data_retention_task` (all `@tenant_task`).
   - `backend/app/tasks/attribution.py`: `recompute_window` (`@tenant_task`).
4. Matview refresh session/role: `backend/app/matviews/executor.py` uses SQLAlchemy `engine.begin()` for async refresh and psycopg2 `refresh_single()` with `_build_sync_dsn()` derived from `settings.DATABASE_URL` (app_user) and explicit `set_config('app.current_tenant_id', ...)`.

## Remediation Summary
- Hermetic runtime enforcement is wired into PR CI and produces a hermeticity scan log.
- Added canonical LLM task producer (`backend/app/services/llm_dispatch.py`) to serve as API-equivalent enqueue entrypoint without adding an API router.
- Added Phase 5 cohesion tests: LLM payload JSON roundtrip, concurrent routing determinism + DLQ stability, matview boundary invariants, and tenant propagation beyond LLM.
- Added Phase 4 evidence bundle generator `scripts/ci/b055_evidence_bundle.py` and CI wiring to emit `LOGS/hermeticity_scan.log`, `LOGS/migrations.log`, `LOGS/pytest_b055.log`, and `MANIFEST.json`.

## Evidence Pointers
- Hermeticity enforcement log: `backend/validation/evidence/runtime/hermeticity_scan.log`
- LLM payload fidelity test: `backend/tests/test_b055_llm_model_parity.py` → `test_llm_payload_json_roundtrip_fidelity`
- Routing concurrency test: `backend/tests/test_b052_queue_topology_and_dlq.py` → `test_queue_routing_deterministic_under_concurrency`
- DLQ concurrency test: `backend/tests/test_b052_queue_topology_and_dlq.py` → `test_dlq_failure_handler_concurrent`
- Matview boundary invariant test: `backend/tests/test_b055_matview_boundary.py` → `test_matview_refresh_sql_invariant`
- Non-LLM tenant propagation tests: `backend/tests/test_b055_tenant_propagation.py`

## Evidence Bundle (Phase 4)
- Bundle generator: `scripts/ci/b055_evidence_bundle.py`
- Bundle output (CI): `backend/validation/evidence/b055_phase4_bundle/`
- Artifact name (CI): `b055-phase4-evidence-${GITHUB_SHA}` (ends with head SHA)
- Required files enumerated in `MANIFEST.json` (includes `LOGS/hermeticity_scan.log`).

## Outstanding Updates (populate post-CI)
- PR link: pending
- CI run id + evidence artifact URL: pending
