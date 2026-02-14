# B0.7 Phase 8 End-to-End Integration and Operational Readiness Proof Index

This index is the Phase 8 closure anchor for B0.1-B0.7 composition proof.

## Scope
- Canonical one-command orchestrator:
  - `python scripts/phase8/run_phase8_closure_pack.py --artifact-dir artifacts/b07-phase8`
- CI meaningful subset command:
  - `python scripts/phase8/run_phase8_closure_pack.py --ci-subset --artifact-dir artifacts/b07-phase8`
- Full physics command (staging authority for EG8.5):
  - `python scripts/phase8/run_phase8_closure_pack.py --full-physics --artifact-dir artifacts/b07-phase8`

## Canonical Topology Bring-Up (EG8.1)
- Compose substrate + runtime:
  - `docker-compose.e2e.yml` (env-injected runtime DSNs, no hardcoded privileged DSN)
- Runtime identity enforcement:
  - `scripts/identity/assert_runtime_identity.py`
- Health readiness:
  - `scripts/wait_for_e2e_health.py`
  - `scripts/wait_for_e2e_worker.py`
- Pass criteria:
  - DB user is `app_user`
  - `rolsuper=false`
  - API ready and worker-ready probes succeed

## Unified E2E Closure Pack (EG8.2)
- Event attribution topology (webhook -> persistence -> worker scheduling):
  - `backend/tests/integration/test_b07_p8_topology_closure_pack.py`
- Revenue verification topology (deterministic reconciliation write -> queryable reconciliation API):
  - `backend/tests/integration/test_b07_p8_topology_closure_pack.py`
  - `backend/app/api/reconciliation.py`
- LLM synthesis topology through single boundary:
  - `backend/tests/integration/test_b07_p4_operational_readiness_e2e.py`
  - `backend/tests/test_b07_p6_complexity_router.py -k "eg63 or eg65"`
  - `backend/tests/test_b07_p0_provider_boundary_enforcement.py`

## Compute Safety Under Composition (EG8.3)
- LLM budget/breaker/timeout/router:
  - `backend/tests/integration/test_b07_p4_operational_readiness_e2e.py`
  - `backend/tests/test_b07_p3_provider_controls.py -k "provider_swap_config_only_proof or timeout_non_vacuous_negative_control"`
- Bayesian hard timeout in real worker topology:
  - `backend/tests/integration/test_b07_p5_bayesian_timeout_runtime.py`

## Ledger/Audit Sufficiency and Cost Correctness (EG8.4)
- Ledger/audit outcome coverage + no raw prompt persistence + cache performance:
  - `backend/tests/test_b07_p7_ledger_cost_cache_audit.py`
- SQL probe consolidation:
  - `scripts/phase8/collect_sql_probes.py`
  - Outputs under `artifacts/b07-phase8/sql/`

## Composed Ingestion Performance Re-Proof (EG8.5)
- Runtime harness:
  - `scripts/r3/ingestion_under_fire.py`
- Composition coupling proof (ledger/audit writes during ingestion load):
  - `scripts/phase8/llm_background_load.py`
  - `scripts/phase8/collect_sql_probes.py` (`perf_composed_llm_calls > 0`)
- CI runner constraint:
  - CI runs `--ci-subset` with null benchmark + sanity load profile.
  - Staging runs `--full-physics` with EG3.4 46 rps profile authority.

## OpenAPI Runtime Fidelity Gate (EG8.6)
- Runtime schema validation in composed topology:
  - `backend/tests/integration/test_b07_p8_topology_closure_pack.py`
- Non-vacuous negative controls:
  - same test mutates response payloads (missing required field, wrong type) and asserts validator failure.

## Operational Readiness Evidence Pack (EG8.7)
- Orchestrator:
  - `scripts/phase8/run_phase8_closure_pack.py`
- Artifact set:
  - `artifacts/b07-phase8/phase8_gate_summary.json`
  - `artifacts/b07-phase8/manifest.sha256`
  - `artifacts/b07-phase8/runtime_db_probe.json`
  - `artifacts/b07-phase8/p8_topology_probe.json`
  - `artifacts/b07-phase8/sql/phase8_sql_probe_summary.json`
  - `artifacts/b07-phase8/sql/phase8_llm_outcomes.csv`
  - `artifacts/b07-phase8/sql/phase8_topology_counts.csv`
  - `artifacts/b07-phase8/sql/phase8_pg_snapshot.csv`
  - `artifacts/b07-phase8/logs/*.log`
- Secret hygiene:
  - compose log redaction scan enforced in orchestrator (`_assert_secret_hygiene`).

## CI Wiring
- Dedicated workflow:
  - `.github/workflows/b07-phase8-closure-pack.yml`
- Artifact upload:
  - `b07-phase8-closure-pack`

## Failure Interpretation
- `phase8_gate_summary.json.status=failed`:
  - read `error` and corresponding `logs/<step>.log`.
- `eg8_5_composed_ingestion_perf` failure:
  - inspect `logs/r3_ingestion_under_fire.log` and `sql/phase8_sql_probe_summary.json`.
- Contract fidelity failures:
  - inspect `logs/pytest_p8_topology.log` for schema path/status mismatch.
