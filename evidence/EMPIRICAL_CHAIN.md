# Empirical Chain Registry

> This document enumerates every phase gate, required artifacts, and current
> empirical status. Update the rows below whenever a validation run completes.

## Phase Status Summary
- Runtime phase gate: FAIL (artifacts pending)
- Contract phase gate: FAIL (artifacts pending)
- Statistics phase gate: FAIL (artifacts pending)
- Privacy phase gate: FAIL (artifacts pending)

## Detailed Artifact Matrix

| Phase | Criterion | Artifact(s) | Command / Script | Status | Notes |
|-------|-----------|-------------|------------------|--------|-------|
| Runtime | Static config validation | `evidence_registry/runtime/runtime_config_static_check_<ts>.txt` | `scripts/runtime/run_init_with_evidence.sh` | FAIL | Tier A script not yet executed |
| Runtime | Process tree & ports | `evidence_registry/runtime/process_snapshot.txt`, `open_ports.txt` | `scripts/runtime/start_services_with_evidence.sh` | MISSING | Multi-service runtime not captured |
| Runtime | Auto-restart log | `evidence_registry/runtime/auto_restart_log_<ts>.txt` | `scripts/runtime/test_auto_restart.sh` | MISSING | Auto-restart scenario not recorded |
| Contracts | Validation run | `evidence_registry/contracts/contract_validation_log.txt` | `scripts/contracts/run_validation_with_evidence.sh` | FAIL | Needs persisted log |
| Contracts | Route fidelity | `evidence_registry/contracts/route_fidelity_log.txt` | `scripts/contracts/run_route_fidelity_with_evidence.sh` | FAIL | Needs persisted log |
| Contracts | Interim semantics (B0.1) | `evidence_registry/contracts/interim_semantics_B0.1_<ts>.txt` | `scripts/contracts/probe_interim_semantics.sh` | MISSING | Response capture pending |
| Statistics | PyMC sampling (R-hat / ESS) | `evidence_registry/statistics/model_results.json`, `sampling_output.json` | `backend/.venv311/Scripts/python.exe scripts/verify_science_stack.py` | PASS | Latest run captured Nov 20 |
| Statistics | Convergence persisted to DB | `evidence_registry/statistics/convergence_dump_<ts>.sql` | `scripts/statistics/persist_convergence_to_db.py` | MISSING | Requires DB access |
| Privacy | Runtime redaction proof | `evidence_registry/privacy/raw_payload_before.json`, `raw_payload_after.json` | `scripts/privacy/probe_middleware_redaction.py` | FAIL | Middleware fix + capture required |
| Privacy | DB guardrail tests | `evidence_registry/privacy/pii_guardrail_db_tests_<ts>.txt` | `scripts/privacy/run_pii_guardrails_with_evidence.sh` | MISSING | PostgreSQL tests not executed |
| Privacy | DLQ routing | `evidence_registry/privacy/dlq_population_log_<ts>.txt` | `scripts/privacy/probe_dlq_behavior.py` | MISSING | DLQ scenario not executed |

> Once every Status cell reads PASS and the summary reflects PASS values, the
> global chain gate (`scripts/phase_gates/check_chain_phase.py`) will allow
> progression to deployment steps.
