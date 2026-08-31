#!/usr/bin/env python3
"""Policy-as-code validator for the M0 maintainability scope lock.

The validator intentionally stays narrow: it proves that M0 governance
artifacts are present, internally consistent, stale blocked-state language is
absent, branch-protection evidence is recorded, and the corrective diff does
not implement B2.4 or reopen prohibited B2.3/provider-boundary surfaces.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

M0_BASELINE_PATH = REPO_ROOT / "docs" / "maintainability" / "m0_baseline.md"
M0_SCOPE_LOCK_PATH = REPO_ROOT / "docs" / "maintainability" / "m0_scope_lock.md"
M0_ISSUE_REGISTER_PATH = (
    REPO_ROOT / "docs" / "maintainability" / "maintainability_issue_register.yaml"
)
M0_COMPLETION_RECORD_PATH = (
    REPO_ROOT / "docs" / "maintainability" / "m0_completion_record.md"
)
CODEOWNERS_PATH = REPO_ROOT / ".github" / "CODEOWNERS"

CANONICAL_ARTIFACT = "docs/maintainability/m0_completion_record.md"
M0_JOB_NAME = "m0-maintainability-scope-lock"

REQUIRED_ARTIFACTS = [
    M0_BASELINE_PATH,
    M0_SCOPE_LOCK_PATH,
    M0_ISSUE_REGISTER_PATH,
    M0_COMPLETION_RECORD_PATH,
]

REQUIRED_BASELINE_FIELDS = [
    "primary branch",
    "primary branch head",
    "remote",
    "m0 baseline sha",
    "m0 ci workflow",
    "m0 ci job name",
    "required for merge",
    "final clean-state confirmation",
    "b2.4 implementation is unauthorized",
    "post-b2.3 and pre-b2.4",
    "b2.3 semantics are closed",
]

REQUIRED_SCOPE_LOCK_PHRASES = [
    "b2.4 implementation prohibition",
    "b2.3 semantic reopening prohibition",
    "provider-boundary behavior-change prohibition",
    "broad ci refactor prohibition",
    CANONICAL_ARTIFACT,
    "required ci status",
    M0_JOB_NAME,
]

REQUIRED_SOURCES = {"Nicholas", "Trey", "George", "Synthesized"}

REQUIRED_CATEGORIES = {
    "local_development",
    "stale_documentation",
    "ci_sprawl",
    "ci_enforcement_insertion_risk",
    "hardcoded_external_db",
    "db_topology",
    "append_only_test_isolation",
    "ops_runbooks",
    "b24_substrate",
    "llm_provider_boundary",
    "repo_hygiene",
    "dependency_drift",
    "m0_policy_enforcement",
}

REQUIRED_ISSUE_FIELDS = [
    "id",
    "source",
    "title",
    "evidence",
    "severity",
    "phase_disposition",
    "b24_entry_blocking",
    "affected_substrate",
    "rationale",
    "owner_phase",
    "deferred_reason",
    "validation_expectation",
]

REQUIRED_REPORT_PHRASES = [
    "final verdict: m0_pass",
    "required for main: yes",
    "required status context: m0-maintainability-scope-lock",
    "branch protection evidence",
    "fresh checkout git status --short",
    "clean",
    "canonical completion artifact",
    CANONICAL_ARTIFACT,
    "validator governance protection",
    "no b2.4 implementation occurred",
    "no b2.3 semantic modules changed",
    "no provider-boundary behavior changed",
]

REQUIRED_CODEOWNER_PATHS = [
    "scripts/ci/validate_m0_scope_lock.py",
    ".github/workflows/m0-maintainability-scope-lock.yml",
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    "docs/maintainability/m0_scope_lock.md",
    "docs/maintainability/maintainability_issue_register.yaml",
]

B24_DEPENDENCY_PATTERNS = [
    r"pymc",
    r"pymc-marketing",
    r"pymc_marketing",
    r"arviz",
]

B24_CODE_PATTERNS = [
    r"pm\.Model",
    r"pm\.sample",
    r"az\.rhat",
    r"az\.ess\b",
    r"az\.summary",
]

PROHIBITED_SURFACE_PATTERNS = [
    r"provider_boundary\.py$",
    r"match_engine_kernel\.py$",
    r"semantic_authority\.py$",
    r"state_transitions\.py$",
    r"extraction_registry\.py$",
    r"batch_engine\.py$",
    r"(^|/)migrations?(/|$)",
    r"requirements.*\.txt$",
    r"pyproject\.toml$",
    r"setup\.(py|cfg)$",
    r"Pipfile$",
]

ALLOWED_M0_PATHS = [
    # --- Hygiene remediation surface (exhaustive line-level hygiene audit) ---
    # Governance integration fix, not a product-semantics exemption, following the
    # precedent set for the Corrective XIV evidence report: the diff is still computed
    # exactly, and every B2.3/provider/dependency/migration prohibition in
    # PROHIBITED_SURFACE_PATTERNS is retained unchanged. These paths carry removal of
    # zero-consumer artifacts, the cross-domain .gitignore anchor, the reproducible
    # environment specification, and the environment specification. No trust,
    # signing, builder, governance-manifest, or C13/C14 enforcer path is included --
    # those remain outside this surface and untouched by the branch.
    ".gitignore",
    # B2.5-P13 Corrective XV: repository line-ending policy. Without it a
    # stock Windows clone rewrites LF shell scripts to CRLF and the
    # documented bootstrap is not executable.
    ".gitattributes",
    "db/schema/canonical_schema.sql",
    ".hypothesis/",
    "artifacts/",
    "artifacts_vt_run3/",
    "backend/.hypothesis/",
    "backend/tmp_celery_init.py",
    "backend/tmp_celery_schema.py",
    "backend/tmp_create_table.py",
    "backend/tmp_list_tables.py",
    "backend/tmp_schemata.py",
    "backend/validation/evidence/contracts/",
    "docs/environment/",
    "docs/forensics/evidence/b14_p0/",
    "docs/forensics/validation/runtime/R6_context_gathering/",
    "tmp/",
    "tmp_asyncpg_check.py",
    "tmp_asyncpg_params.py",
    "tmp_asyncpg_test.py",
    "tmp_celery_schema.py",
    "docs/maintainability/",
    "docs/testing.md",
    "docs/testing_db_topology.md",
    "docs/testing_append_only_isolation.md",
    "docs/testing_celery_modes.md",
    "docs/testing_topology_url_authority.md",
    "docs/testing_b24_persistence_readiness.md",
    "docs/testing_b24_persistence_entry_gate.md",
    "docs/testing_parallel_isolation.md",
    "docs/b2_4/",
    "docs/b2_7/",
    "docs/database/ADR-016-b25-p13-confidence-truth-downgrade.md",
    "docs/database/ADR-017-b25-p13-c10-inference-provenance-downgrade.md",
    "docs/llm/",
    "M2 Remediation Evidence Pack.md",
    "Makefile",
    "contracts/trust-api/",
    "scripts/ci/validate_m0_scope_lock.py",
    "scripts/ci/validate_m1_local_dev_authority.py",
    "scripts/ci/validate_b25_p1_contracts.py",
    "scripts/ci/validate_b25_p1_trust_drift.py",
    "backend/tests/trust/test_b25_p2_manifest_coverage.py",
    "scripts/ci/validate_b25_p2_canonicalization.py",
    "scripts/ci/validate_b25_p3_text_disposition.py",
    "scripts/ci/validate_b25_p4_money_authority.py",
    "scripts/ci/validate_b25_p5_builder.py",
    "scripts/ci/validate_b25_p6_reason_truth_matrix.py",
    "scripts/ci/validate_b25_p7_provenance_audit.py",
    "scripts/ci/validate_b25_p8_signing_verification.py",
    "scripts/ci/validate_b25_p9_machine_identity.py",
    "scripts/ci/validate_b25_p10_trust_api_surface.py",
    "scripts/ci/validate_b25_p11_export_compatibility.py",
    "scripts/ci/validate_b25_p13_confidence_truth.py",
    "scripts/ci/validate_b25_p13_c4_closure.py",
    "scripts/ci/validate_b25_p13_c5_closure.py",
    "scripts/ci/validate_b25_p13_c6_closure.py",
    "scripts/ci/validate_b25_p13_c7_closure.py",
    "scripts/ci/validate_b25_p13_c12_closure.py",
    "scripts/ci/validate_b25_p13_c13_closure.py",
    "scripts/ci/validate_b25_p13_c13_artifact_closure.py",
    "scripts/ci/validate_b25_p13_c14_closure.py",
    "contracts-internal/governance/b25_p13_c13_authority_topology.v1.json",
    "contracts-internal/governance/b25_p13_c14_trust_semantic_authority.v1.json",
    "backend/tests/trust/test_b25_p13_c13_signing_truth_boundary.py",
    "backend/tests/trust/test_b25_p13_c14_semantic_authority.py",
    "alembic/versions/007_skeldir_foundation/202608271200_b25_p13_c13_signing_authority.py",
    # --- B2.5-P13 Corrective XV surface (issuance capability, audit truth) ---
    # Governance integration for the corrective action, following the precedent
    # set for the Corrective XIV evidence report. Every B2.3/provider/dependency
    # prohibition below is retained unchanged; the migration is declared
    # explicitly rather than by loosening the alembic prohibition.
    "scripts/ci/validate_b25_p13_c15_closure.py",
    "backend/tests/trust/test_b25_p13_c15_issuance_truth.py",
    "backend/app/trust/issuance_authority_ledger.py",
    "alembic/versions/007_skeldir_foundation/202608291200_b25_p13_c15_issuance_completion_state.py",
    "docs/security/b25_p13_c15_trusted_computing_base.md",
    "docs/environment/SUPPORTED_ENVIRONMENTS.md",
    "docs/environment/INFRASTRUCTURE_EVIDENCE_CAPSULES.md",
    "scripts/phase_gates/validate_manifest.py",
    "docs/forensics/B2.5-P13 Corrective Action Remediation XV Report.md",
    # --- B2.5-P13 Corrective XVI surface (bidirectional issuance truth) ---
    # Same precedent again: the C16 migration, its gate, its falsifier, the
    # issuance-consequence database custody module, and the evidence pack are
    # declared explicitly rather than by loosening the alembic prohibition.
    "scripts/ci/validate_b25_p13_c16_closure.py",
    "scripts/ci/run_b25_p13_c16_production_topology_proof.sh",
    "backend/tests/trust/test_b25_p13_c16_bidirectional_issuance_truth.py",
    "backend/app/trust/issuance_session.py",
    "alembic/versions/007_skeldir_foundation/202608301200_b25_p13_c16_bidirectional_issuance_truth.py",
    "docs/forensics/B2.5-P13 Corrective Action Remediation XVI Report.md",
    "docs/forensics/B2.5-P13 XVI CHECK Constraint NULL Semantics Survey.md",
    "docs/environment/B2.5-P13 INDEPENDENT PRODUCTION TOPOLOGY REPRODUCTION.md",
    "scripts/database/prepare_migration_authority_boundary.py",
    ".github/actions/setup-postgres-ci/action.yml",
    # --- B2.5-P13 Corrective XVII surface (consequence lineage) ---
    "scripts/ci/validate_b25_p13_c17_closure.py",
    "backend/tests/trust/test_b25_p13_c17_consequence_lineage.py",
    "backend/app/trust/signer_session.py",
    "backend/app/trust/signer_service.py",
    "backend/app/trust/signer_gateway.py",
    "backend/app/trust/signing_authorization.py",
    "backend/app/trust/signing_consequence.py",
    "alembic/versions/007_skeldir_foundation/202608311200_b25_p13_c17_consequence_lineage.py",
    "docs/forensics/B2.5-P13 Corrective Action Remediation XVII Report.md",
    # The bounded issuance reconciler and the Optional correlation-id typing it
    # requires: both are Corrective XVI trust-closure surfaces, not M0/M1 scope.
    "backend/app/tasks/maintenance.py",
    "backend/app/observability/context.py",
    "docker-compose.local.yml",
    "DEVELOPMENT.md",
    "scripts/ci/validate_b24_artifact_topology.py",
    "scripts/ci/_b25_p13_c7_dependency_derivation.py",
    "scripts/contracts/check_error_model.py",
    ".github/workflows/b2_5-p12-ci-gates.yml",
    "scripts/ci/validate_b25_p12_contract_projection.py",
    "scripts/ci/validate_b25_p12_trust_isolation.py",
    "scripts/ci/_b25_p12_runtime_trace.py",
    "backend/tests/trust/test_b25_p13_e2e_trust_closure.py",
    ".github/workflows/b2_5-p13-e2e-trust-closure.yml",
    "scripts/ci/validate_b25_p12_ci_gates.py",
    "docs/ci/b25_p12_invariant_registry.yaml",
    "contracts/trust-api/export-artifact.v2.yaml",
    "contracts/trust-api/examples/export_artifact_signed_valid_v2.json",
    "docs/forensics/B2.5-P12 Remediation Evidence Pack.md",
    "docs/forensics/B2.5-P13 Remediation Evidence Pack.md",
    "docs/forensics/B2.5-P13 Corrective Action Remediation V Report.md",
    "docs/forensics/B2.5-P13 Corrective Action Remediation VI Report.md",
    "docs/forensics/B2.5-P13 Corrective Action Remediation VII Report.md",
    "docs/forensics/B2.5-P13 Corrective Action Remediation VIII Report.md",
    "docs/forensics/B2.5-P13 Corrective Action Remediation IX Report.md",
    "docs/forensics/B2.5-P13 Corrective Action Remediation X Report.md",
    "docs/forensics/B2.5-P13 Corrective Action Remediation XI Report.md",
    "docs/forensics/B2.5-P13 Corrective Action Remediation XII Report.md",
    "docs/forensics/B2.5-P13 Corrective Action Remediation XIII Report.md",
    "docs/forensics/B2.5-P13 Corrective Action Remediation XIV Report.md",
    "scripts/contracts/error_component_registry.py",
    "api-contracts/openapi/v1/_common/error-component-registry.yaml",
    ".github/workflows/b2_5-p9-machine-identity.yml",
    ".github/workflows/b2_5-p10-trust-api-surface.yml",
    ".github/workflows/b2_5-p11-export-compatibility.yml",
    "alembic/versions/007_skeldir_foundation/202607191200_b25_p9_machine_identity.py",
    "alembic/versions/007_skeldir_foundation/202608081200_b25_p11_export_scope.py",
    "alembic/versions/007_skeldir_foundation/202608131200_b25_p13_confidence_truth_closure.py",
    "alembic/versions/007_skeldir_foundation/202608181200_b25_p13_c4_confidence_state_closure.py",
    "alembic/versions/007_skeldir_foundation/202608191200_b25_p13_c5_terminal_truth_temporal_plausibility.py",
    "alembic/versions/007_skeldir_foundation/202608201200_b25_p13_c6_authority_orchestration_contract.py",
    "alembic/versions/007_skeldir_foundation/202608202300_b25_p13_c6_wakeup_coalescing.py",
    "alembic/versions/007_skeldir_foundation/202608221200_b25_p13_c7_source_causality_obligation_conservation.py",
    "alembic/versions/007_skeldir_foundation/202608231200_b25_p13_c8_identity_window_causality.py",
    "alembic/versions/007_skeldir_foundation/202608240900_b25_p13_c9_planner_degradation_authority.py",
    "alembic/versions/007_skeldir_foundation/202608241000_b25_p13_c9_authority_request_supersession.py",
    "alembic/versions/007_skeldir_foundation/202608250900_b25_p13_c10_inference_policy_provenance.py",
    "alembic/versions/007_skeldir_foundation/202608251200_b25_p13_c11_semantic_authority.py",
    "alembic/versions/007_skeldir_foundation/202608261200_b25_p13_c12_authority_closure.py",
    "contracts/bayesian/",
    "scripts/database/prepare_migration_authority_boundary.py",
    "api-contracts/openapi/v1/export.yaml",
    "api-contracts/dist/openapi/v1/export.bundled.yaml",
    "backend/app/api/export.py",
    "backend/app/api/trust_export.py",
    "backend/requirements-dev.txt",
    "backend/requirements-lock.txt",
    "backend/tests/integration/test_b07_p5_bayesian_timeout_runtime.py",
    "contracts/export/v1/export.yaml",
    "contracts/export/baselines/v1.0.0/export.yaml",
    "contracts/export/CSV_EVOLUTION.md",
    "scripts/ci/run_m1_onboarding_bootstrap.sh",
    "scripts/ci/validate_m2_test_feedback_loop.py",
    "scripts/ci/run_m2_test_feedback_loop.sh",
    "scripts/ci/validate_m3_ci_governance.py",
    "scripts/ci/validate_m4_ops_runbooks.py",
    "scripts/ci/validate_m5_b24_readiness_design.py",
    "scripts/ci/validate_m6_llm_boundary.py",
    "scripts/ci/validate_m7_b24_readiness.py",
    "scripts/ci/enforce_b21_p4_queue_isolation_semantics_lock.py",
    "scripts/ci/enforce_forensics_index.py",
    "scripts/ci/run_ci_governance_cohort.py",
    "scripts/ci/enforce_boundary.sh",
    "scripts/ci/enforce_postgres_only.py",
    "scripts/ci/enforce_b21_p4_benchmark_adjudication.py",
    "scripts/benchmarks/b21_p4_queue_isolation_benchmark.py",
    "scripts/phase8/run_phase8_closure_pack.py",
    "scripts/phase_gates/generate_value_trace_proof_pack.py",
    "api-contracts/openapi/v1/attribution.yaml",
    "api-contracts/openapi/v1/reconciliation.yaml",
    "frontend/src/types/api/attribution.ts",
    "frontend/src/types/api/export.ts",
    "frontend/src/types/api/reconciliation.ts",
    "scripts/test-response-parity.sh",
    "scripts/smoke/",
    "scripts/ops/",
    "scripts/testing/",
    ".github/workflows/m0-maintainability-scope-lock.yml",
    ".github/workflows/m1-local-dev-authority.yml",
    ".github/workflows/m2-test-feedback-loop.yml",
    ".github/workflows/m3-ci-governance.yml",
    ".github/workflows/m4-operational-runbooks.yml",
    ".github/workflows/b2_4-gate-dry-run.yml",
    ".github/workflows/b2_5-p1-contracts.yml",
    ".github/workflows/b2_5-p2-canonicalization.yml",
    ".github/workflows/b2_5-p3-text-disposition.yml",
    ".github/workflows/b2_5-p4-money-authority.yml",
    ".github/workflows/b2_5-p5-builder.yml",
    ".github/workflows/b2_5-p6-reason-truth-matrix.yml",
    ".github/workflows/b2_5-p7-provenance-audit.yml",
    ".github/workflows/b2_5-p8-signing-verification.yml",
    ".github/workflows/b2_5-p10-trust-api-surface.yml",
    ".github/workflows/contract-publish.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/r2-data-truth-hardening.yml",
    ".github/actions/setup-postgres-ci/",
    "alembic/versions/007_skeldir_foundation/202605201200_b24_p1_authority_schema.py",
    "alembic/versions/007_skeldir_foundation/202605201430_b24_p1_corrective_authority_closure.py",
    "alembic/versions/007_skeldir_foundation/202605211200_b24_p1_partitioned_authority_schema.py",
    "alembic/versions/007_skeldir_foundation/202605211430_b24_p2_sparse_fallback_reasons.py",
    "alembic/versions/007_skeldir_foundation/202605221200_b24_p2_source_stream_safety_indexes.py",
    "alembic/versions/007_skeldir_foundation/202605221430_b24_p3_fit_planning_outbox.py",
    "alembic/versions/007_skeldir_foundation/202605231200_b24_p4_resource_bounds.py",
    "alembic/versions/007_skeldir_foundation/202605241200_b24_p4_feature_cardinality_indexes.py",
    "alembic/versions/007_skeldir_foundation/202605241430_b24_p4_cardinality_early_stop_indexes.py",
    "alembic/versions/007_skeldir_foundation/202605251200_b24_p4_feature_authority.py",
    "alembic/versions/007_skeldir_foundation/202605251430_b24_p4_authority_liveness.py",
    "alembic/versions/007_skeldir_foundation/202605251800_b24_p4_supersession_profiling_lease.py",
    "alembic/versions/007_skeldir_foundation/202605261200_b24_p4_atomic_dominance_canonical_profiling.py",
    "alembic/versions/007_skeldir_foundation/202605271200_b24_p4_strict_profiling_purge.py",
    "alembic/versions/007_skeldir_foundation/202605281200_b24_p5_runtime_statuses.py",
    "alembic/versions/007_skeldir_foundation/202606021200_b24_p6_fit_execution_states.py",
    "alembic/versions/007_skeldir_foundation/202606041200_b24_p7_diagnostic_semantics.py",
    "alembic/versions/007_skeldir_foundation/202606031200_b24_p6_fit_id_resolution_policy.py",
    "alembic/versions/007_skeldir_foundation/202606061200_b24_p8_artifact_lifecycle.py",
    "alembic/versions/007_skeldir_foundation/202606071200_b24_p8_follow_up_airgap_quota.py",
    "alembic/versions/007_skeldir_foundation/202606081200_b24_p9_worker_tenant_hygiene.py",
    "alembic/versions/007_skeldir_foundation/202606141200_b24_p9_directive_ix_dispatch_authority.py",
    "alembic/versions/007_skeldir_foundation/202606181200_b24_p9_directive_x_broker_independent_authority.py",
    "alembic/versions/007_skeldir_foundation/202606201300_b24_p9_directive_xiii_shared_recovery.py",
    "alembic/versions/007_skeldir_foundation/202606201430_b24_p9_directive_xiv_failure_ack_recovery.py",
    "alembic/versions/007_skeldir_foundation/202607011200_b25_p7_trust_audit_provenance.py",
    "backend/app/trust/",
    "backend/app/api/trust_api.py",
    "backend/app/api/trust_keys.py",
    "backend/app/config/contract_scope.yaml",
    "backend/app/main.py",
    "backend/tests/trust/",
    "docs/ci/",
    "docs/forensics/B2.5-P10 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P10 Corrective Remediation Evidence Pack.md",
    "docs/forensics/B2.5-P11 Remediation Evidence Pack.md",
    "docs/forensics/B2.5-P11 Corrective Remediation Evidence Pack.md",
    "docs/forensics/B2.5-P11 Third Corrective Remediation Evidence Pack.md",
    "docs/forensics/B2.5-P11 Second Corrective Remediation Evidence Pack.md",
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    ".github/CODEOWNERS",
    "backend/app/bayesian/",
    "backend/app/confidence_projection/",
    "backend/app/trust/",
    "backend/app/api/trust_keys.py",
    "backend/app/main.py",
    "backend/Dockerfile.bayesian",
    "backend/requirements.txt",
    "backend/requirements-bayesian.txt",
    "backend/app/ingestion/event_service.py",
    "backend/app/models/__init__.py",
    "backend/app/revenue_verification/batch_engine.py",
    "backend/app/tasks/attribution.py",
    "backend/app/tasks/bayesian.py",
    "backend/app/tasks/bayesian_publisher.py",
    "backend/app/inference_policy_registry.py",
    "backend/app/celery_app.py",
    "backend/app/core/queues.py",
    "scripts/ci/validate_b25_p13_c11_closure.py",
    "scripts/security/phase4_enforcement_probe.py",
    "backend/app/tasks/beat_schedule.py",
    "Procfile",
    "docs/ci/",
    "docs/ops/",
    "docs/forensics/INDEX.md",
    "docs/forensics/B2.4-P Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P1 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P1_Authority_Corrective_Closure_Report.md",
    "docs/forensics/B2.4-P1_Partitioned_Authority_Schema_Corrective_Report.md",
    "docs/forensics/B2.4-P1_Authority_Schema_RLS_Module_Transition_Completion_Report.md",
    "docs/forensics/B2.4-P2_Deterministic_Input_Contract_Source_Snapshot_Completion_Report.md",
    "docs/forensics/B2.4-P2_Source_Safety_and_Sparse_Privacy_Corrective_Report.md",
    "docs/forensics/B2.4-P3_Fit_Planning_Debounced_Atomic_Claim_Dispatch_Outbox_Completion_Report.md",
    "docs/forensics/B2.4-P4_Input_Cardinality_Memory_Graph_Envelope_PreGraph_Resource_Controls_Completion_Report.md",
    "docs/forensics/B2.4-P4_Live_Feature_Cardinality_Graph_Envelope_Corrective_Report.md",
    "docs/forensics/B2.4-P4_Bounded_Cardinality_DB_Work_Corrective_Report.md",
    "docs/forensics/B2.4-P4_Source_Window_Feature_Authority_Corrective_Report.md",
    "docs/forensics/B2.4-P4_Authority_Transient_Yield_Reactivation_Corrective_Report.md",
    "docs/forensics/B2.4-P4_Snapshot_Supersession_Build_Dispatch_Profiling_Lease_Corrective_Report.md",
    "docs/forensics/B2.4-P4_Atomic_Dominance_Canonical_Profiling_Dispatch_Corrective_Report.md",
    "docs/forensics/B2.4-P4_Strict_Purge_Causal_Dispatch_Recovery_Boundary_Corrective_Report.md",
    "docs/forensics/B2.4-P5 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P6 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P7 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P8 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P9 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P10 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P11 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P12 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P1 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P2 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P3 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P4 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P5 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P5 Follow-Up Corrective Evidence Pack.md",
    "docs/forensics/B2.5-P6 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P6 Follow-Up Corrective Evidence Pack.md",
    "docs/forensics/B2.5-P7 Remediation Evidence Pack.md",
    "docs/forensics/B2.5-P7 Follow-Up Corrective Evidence Pack.md",
    "docs/forensics/B2.5-P7 Second Follow-Up Corrective Evidence Pack.md",
    "docs/forensics/B2.5-P8 Remediation Evidence Pack.md",
    "docs/forensics/B2.5-P9 Remediation Evidence Pack.md",
    "docs/forensics/M3 Remediation Evidence Pack .md",
    "docs/forensics/M5 Remediation Evidence Pack .md",
    "db/schema/canonical_schema.sql",
    "db/schema/canonical_schema.yaml",
    "scripts/ci/validate_b24_p1_authority_schema.py",
    "scripts/ci/validate_b24_p2_source_snapshot.py",
    "scripts/ci/validate_b24_p3_fit_planning.py",
    "scripts/ci/validate_b24_p4_resource_bounds.py",
    "scripts/ci/validate_b24_p5_runtime_harness.py",
    "scripts/ci/validate_b24_p6_real_fit_worker.py",
    "scripts/ci/validate_b24_p7_diagnostics.py",
    "scripts/ci/validate_b24_p8_artifact_lifecycle.py",
    "scripts/ci/validate_b24_p9_worker_tenant_hygiene.py",
    "scripts/ci/validate_b24_p10_projection.py",
    "scripts/ci/validate_b24_p11_ci_gates.py",
    "scripts/ci/validate_b24_p11_execution_artifacts.py",
    "scripts/ci/validate_b24_p11_workflow_vacuity.py",
    "scripts/ci/validate_b24_p12_internal_e2e.py",
    "scripts/ci/validate_live_branch_protection.py",
    "scripts/ci/write_b24_p11_command_junit.py",
    "scripts/ci/phase2_schema_closure_gate.py",
    "scripts/schema/assert_canonical_schema.py",
    "M4 Remediation Evidence Pack.md",
    "M4.1_Remediation_Completion_Record.md",
    ".github/workflows/r7-final-winning-state.yml",
    "scripts/r3/ingestion_under_fire.py",
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    "contracts/internal/",
    "frontend/src/budget/components/BudgetScenarioDetailV2/scenarioData.ts",
    "frontend/src/channel-detail/components/CampaignTable.tsx",
    "frontend/src/channel-detail/mockData.ts",
    ".github/CODEOWNERS",
    "DEVELOPMENT.md",
    "README.md",
    "backend/README.md",
    "backend/Dockerfile",
    ".env.example",
    ".env.local.example",
    "docker-compose.local.yml",
    "docker-compose.test.yml",
    "docker-compose.e2e.yml",
    "contracts-internal/governance/main_branch_protection_integrity.main.json",
    "Makefile",
    "pytest.ini",
    "backend/app/db/session.py",
    "backend/app/tasks/enqueue.py",
    "backend/app/tasks/observability_test.py",
    "backend/apply_pii_trigger_fix.py",
    "backend/check_channels.py",
    "backend/check_revenue_ledger.py",
    "backend/check_role_rls_bypass.py",
    "backend/check_tenants_schema.py",
    "backend/check_trigger.py",
    "backend/investigate_pii_trigger.py",
    "backend/run_tests_with_trigger_fix.py",
    "backend/test_rls_context.py",
    "backend/test_rls_direct.py",
    "backend/validate_b042.py",
    "backend/validate_schema_simple.py",
    "backend/verify_rls_config.py",
    "backend/tests/",
    "tests/",
    "scripts/guard_no_docker.py",
    "graphify-out/",
    # CI throughput topology (see docs/ci/CI_TOPOLOGY_PHYSICS.md): concurrency
    # groups, merge_group triggers, and dependency caching were applied across every
    # workflow. Listed individually rather than allowing .github/workflows/ wholesale,
    # so a future workflow change still needs explicit sanction here.
    ".github/workflows/b0541-view-registry.yml",
    ".github/workflows/b0542-refresh-executor.yml",
    ".github/workflows/b0543-matview-task-layer.yml",
    ".github/workflows/b0545-convergence.yml",
    ".github/workflows/b057-p3-webhook-ingestion-least-privilege.yml",
    ".github/workflows/b057-p4-llm-audit-persistence.yml",
    ".github/workflows/b057-p5-full-chain.yml",
    ".github/workflows/b060_phase2_adjudication.yml",
    ".github/workflows/b06_phase0_adjudication.yml",
    ".github/workflows/b07-p4-e2e-operational-readiness.yml",
    ".github/workflows/b07-phase8-closure-pack.yml",
    ".github/workflows/b07-phase8-full-physics-staging.yml",
    ".github/workflows/b11-p1-control-plane-adjudication.yml",
    ".github/workflows/b11-p2-secret-readiness-adjudication.yml",
    ".github/workflows/b11-p3-crypto-rotation-adjudication.yml",
    ".github/workflows/b11-p4-db-provider-ci-audit-adjudication.yml",
    ".github/workflows/b11-p5-webhook-secret-redesign-adjudication.yml",
    ".github/workflows/b11-p6-end-to-end-closure-pack.yml",
    ".github/workflows/b17-p4-mixed-workload-benchmark.yml",
    ".github/workflows/channel_governance_ci.yml",
    ".github/workflows/ci-physics-guard.yml",
    ".github/workflows/contract-artifacts.yml",
    ".github/workflows/contract-enforcement.yml",
    ".github/workflows/contract-validation.yml",
    ".github/workflows/contracts.yml",
    ".github/workflows/empirical-validation.yml",
    ".github/workflows/mock-contract-validation.yml",
    ".github/workflows/phase-gates.yml",
    ".github/workflows/r1-contract-runtime.yml",
    ".github/workflows/r1-validation.yml",
    ".github/workflows/r3-ingestion-under-fire.yml",
    ".github/workflows/r4-worker-failure-semantics.yml",
    ".github/workflows/r5-context-gathering.yml",
    ".github/workflows/r5-remediation.yml",
    ".github/workflows/r6-worker-resource-governance.yml",
    ".github/workflows/schema-deploy-production.yml",
    ".github/workflows/schema-drift-check.yml",
    ".github/workflows/schema-validation.yml",
    ".github/workflows/workflow-yaml-lint.yml",
    "scripts/ci/_workflow_physics.py",
    "scripts/ci/test_ci_physics_negative_controls.py",
    "scripts/ci/validate_ci_physics.py",
    "scripts/migrations/ci_topology/apply_throughput_topology.py",
    "scripts/migrations/ci_topology/dissolve_barrier_edges.py",
    "scripts/migrations/ci_topology/prune_unused_cache_keys.py",
    # Relocated to scripts/migrations/ci_topology/; the deletions still appear in the
    # diff against the baseline, so the former paths stay listed.
    "scripts/ci/apply_throughput_topology.py",
    "scripts/ci/dissolve_barrier_edges.py",
    "scripts/ci/prune_unused_cache_keys.py",
]


class ValidationResult:
    """Collect pass/fail results for all checks."""

    def __init__(self) -> None:
        self.checks: list[tuple[str, bool, str]] = []

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append((name, passed, detail))

    def passed(self) -> bool:
        return all(ok for _, ok, _ in self.checks)

    def report(self) -> str:
        lines = []
        for name, ok, detail in self.checks:
            status = "PASS" if ok else "FAIL"
            line = f"  [{status}] {name}"
            if detail:
                line += f" - {detail}"
            lines.append(line)
        total = len(self.checks)
        passed = sum(1 for _, ok, _ in self.checks if ok)
        lines.append("")
        lines.append(f"  Total: {total} | Passed: {passed} | Failed: {total - passed}")
        return "\n".join(lines)


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _read_lower(path: Path) -> str:
    return _read_text(path).lower()


def _git(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
        cwd=str(REPO_ROOT),
        timeout=timeout,
    )


def _git_diff_names(baseline_sha: str) -> list[str]:
    result = _git(["diff", "--name-only", f"{baseline_sha}...HEAD"])
    if result.returncode != 0:
        result = _git(["diff", "--name-only", baseline_sha, "HEAD"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _git_diff_content(baseline_sha: str) -> str:
    result = _git(["diff", f"{baseline_sha}...HEAD"], timeout=60)
    if result.returncode != 0:
        result = _git(["diff", baseline_sha, "HEAD"], timeout=60)
    return result.stdout


def _extract_baseline_sha_from_artifact() -> str | None:
    match = re.search(r"M0_BASELINE_SHA=([a-f0-9]{40})", _read_text(M0_BASELINE_PATH))
    return match.group(1) if match else None


def _is_governance_path(filepath: str) -> bool:
    return any(filepath.startswith(allowed) for allowed in ALLOWED_M0_PATHS)


def _filter_diff_exclude_governance(diff_content: str) -> str:
    filtered_lines: list[str] = []
    in_governance_file = False

    for line in diff_content.splitlines():
        if line.startswith("diff --git "):
            parts = line.split(" b/")
            filepath = parts[-1] if len(parts) >= 2 else ""
            in_governance_file = _is_governance_path(filepath)
        if not in_governance_file:
            filtered_lines.append(line)

    return "\n".join(filtered_lines)


def check_artifacts_exist(result: ValidationResult) -> None:
    for path in REQUIRED_ARTIFACTS:
        exists = path.exists() and path.stat().st_size > 0
        result.add(
            f"Artifact exists: {path.relative_to(REPO_ROOT)}",
            exists,
        )


def check_baseline_fields(result: ValidationResult) -> None:
    content = _read_lower(M0_BASELINE_PATH)
    if not content:
        result.add("Baseline readable", False, "m0_baseline.md is missing or empty")
        return

    for field in REQUIRED_BASELINE_FIELDS:
        result.add(f"Baseline field: {field}", field in content)

    stale_markers = [
        "**status:** pending",
        "pending admin action",
    ]
    stale_clean_state = re.search(
        r"final clean-state confirmation\s*:?\s*(?:\*\*status:\*\*\s*)?pending",
        content,
    )
    result.add(
        "Baseline has no stale pending/admin language",
        stale_clean_state is None
        and not any(marker in content for marker in stale_markers),
    )
    result.add(
        "Baseline references canonical validation artifact",
        CANONICAL_ARTIFACT in content,
    )


def check_scope_lock_prohibitions(result: ValidationResult) -> None:
    content = _read_lower(M0_SCOPE_LOCK_PATH)
    if not content:
        result.add("Scope lock readable", False, "m0_scope_lock.md is missing or empty")
        return

    for phrase in REQUIRED_SCOPE_LOCK_PHRASES:
        result.add(f"Scope lock contains: {phrase}", phrase.lower() in content)


def check_canonical_artifact_consistency(result: ValidationResult) -> None:
    baseline = _read_lower(M0_BASELINE_PATH)
    scope_lock = _read_lower(M0_SCOPE_LOCK_PATH)
    completion_record = _read_lower(M0_COMPLETION_RECORD_PATH)

    result.add(
        "Canonical completion artifact is required", M0_COMPLETION_RECORD_PATH.exists()
    )
    result.add(
        "Baseline uses canonical completion path", CANONICAL_ARTIFACT in baseline
    )
    result.add(
        "Scope lock uses canonical completion path", CANONICAL_ARTIFACT in scope_lock
    )
    result.add(
        "Completion record self-identifies canonical path",
        CANONICAL_ARTIFACT in completion_record,
    )
    result.add(
        "Completion record claims canonical status",
        "canonical completion artifact" in completion_record
        and "m0_completion_record.md" in completion_record,
    )


def check_validation_report(result: ValidationResult) -> None:
    content = _read_lower(M0_COMPLETION_RECORD_PATH)
    if not content:
        result.add(
            "Completion record readable",
            False,
            "canonical artifact is missing or empty",
        )
        return

    for phrase in REQUIRED_REPORT_PHRASES:
        result.add(f"Completion record contains: {phrase}", phrase in content)

    blocked_verdicts = [
        "m0_blocked_by_unenforced_validator",
        "m0_blocked_by_artifact_inconsistency",
        "m0_blocked_by_incomplete_clean_baseline_evidence",
        "m0_blocked_by_validator_staleness_gap",
        "m0_blocked_by_validator_governance_bypass",
        "m0_blocked_by_feature_contamination",
        "m0_blocked_by_primary_branch_not_green",
    ]
    result.add(
        "Completion record has no blocked final verdict",
        not any(verdict in content for verdict in blocked_verdicts),
    )


def check_codeowners(result: ValidationResult) -> None:
    content = _read_text(CODEOWNERS_PATH)
    if not content:
        result.add("CODEOWNERS present", False, ".github/CODEOWNERS is missing")
        return

    for path in REQUIRED_CODEOWNER_PATHS:
        result.add(f"CODEOWNERS protects {path}", path in content)


def check_issue_register(result: ValidationResult) -> None:
    content = _read_text(M0_ISSUE_REGISTER_PATH)
    if not content:
        result.add(
            "Issue register readable", False, "issue register is missing or empty"
        )
        return

    for source in REQUIRED_SOURCES:
        result.add(
            f"Issue register covers source: {source}", f"source: {source}" in content
        )

    for category in REQUIRED_CATEGORIES:
        result.add(
            f"Issue register covers category: {category}",
            f"affected_substrate: {category}" in content,
        )

    result.add(
        "Issue register has B2.4-entry blockers", "b24_entry_blocking: true" in content
    )

    null_deferred_reasons = 0
    for issue_block in content.split("  - id:")[1:]:
        if "phase_disposition: deferred" in issue_block:
            if (
                "deferred_reason: null" in issue_block
                or "deferred_reason:" not in issue_block
            ):
                null_deferred_reasons += 1
    result.add(
        "Deferred issues have reasons",
        null_deferred_reasons == 0,
        (
            f"{null_deferred_reasons} deferred issues lack reasons"
            if null_deferred_reasons
            else ""
        ),
    )

    for field in REQUIRED_ISSUE_FIELDS:
        result.add(f"Issue register field present: {field}", f"{field}:" in content)

    result.add(
        "MIR-032 expects required CI status check",
        M0_JOB_NAME in content and "required CI status check" in content,
    )


def _added_lines_for_dependency_files(diff_content: str) -> list[str]:
    added_lines: list[str] = []
    current_path = ""
    dependency_path_pattern = re.compile(
        r"(^|/)(requirements.*\.txt|pyproject\.toml|setup\.(py|cfg)|Pipfile)$",
        re.IGNORECASE,
    )
    for line in diff_content.splitlines():
        if line.startswith("diff --git "):
            marker = " b/"
            current_path = line.split(marker, 1)[1] if marker in line else ""
            continue
        if not current_path or not dependency_path_pattern.search(current_path):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line)
    return added_lines


def check_b24_contamination_dependencies(
    result: ValidationResult, diff_content: str
) -> None:
    added_lines = _added_lines_for_dependency_files(diff_content)
    for pattern in B24_DEPENDENCY_PATTERNS:
        found = any(re.search(pattern, line.lower()) for line in added_lines)
        result.add(f"No B2.4 dependency addition: {pattern}", not found)


def check_b24_contamination_code(result: ValidationResult, diff_content: str) -> None:
    added_lines: list[str] = []
    current_path = ""
    for line in diff_content.splitlines():
        if line.startswith("diff --git "):
            marker = " b/"
            current_path = line.split(marker, 1)[1] if marker in line else ""
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if (
            current_path.startswith("docs/")
            or current_path.startswith("scripts/ci/")
            or current_path.startswith("backend/tests/")
            or current_path.startswith("tests/")
        ):
            continue
        added_lines.append(line)
    for pattern in B24_CODE_PATTERNS:
        found = any(re.search(pattern, line) for line in added_lines)
        result.add(f"No B2.4 code pattern: {pattern}", not found)


def check_allowed_change_surface(
    result: ValidationResult, changed_files: list[str]
) -> None:
    violations = [
        filepath for filepath in changed_files if not _is_governance_path(filepath)
    ]
    result.add(
        "M0 changes within allowed surface",
        not violations,
        f"Violations: {', '.join(violations[:5])}" if violations else "",
    )


def check_no_prohibited_surface_changes(
    result: ValidationResult, changed_files: list[str]
) -> None:
    violations = [
        filepath
        for filepath in changed_files
        if any(re.search(pattern, filepath) for pattern in PROHIBITED_SURFACE_PATTERNS)
        and not _is_governance_path(filepath)
    ]
    result.add(
        "No prohibited B2.3/provider/dependency/migration surfaces changed",
        not violations,
        f"Violations: {', '.join(violations[:5])}" if violations else "",
    )


def check_no_ci_gate_removal(result: ValidationResult, diff_content: str) -> None:
    removed_lines: list[tuple[str, str]] = []
    current_path = ""
    for line in diff_content.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            current_path = (
                parts[3][2:] if len(parts) >= 4 and parts[3].startswith("b/") else ""
            )
            continue
        if line.startswith("-") and not line.startswith("---"):
            removed_lines.append((current_path, line))
    suspicious = [
        line.strip()[:120]
        for path, line in removed_lines
        if any(
            keyword in line.lower()
            for keyword in [
                "required_status_checks",
                "required: true",
                "status_check",
                "branch_protection",
            ]
        )
        and not (
            path.startswith("scripts/ci/enforce_")
            and line.strip().startswith("-REQUIRED_CHECKS_FILE")
        )
    ]
    result.add(
        "No CI gate removal detected",
        not suspicious,
        f"Suspicious: {suspicious[:3]}" if suspicious else "",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="M0 Scope Lock Validator")
    parser.add_argument(
        "--baseline-sha", help="Override baseline SHA for diff comparison"
    )
    parser.add_argument(
        "--local-dev",
        action="store_true",
        help="Skip diff-based checks. Artifact staleness checks still run.",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  M0 SCOPE LOCK VALIDATOR")
    print("  Pre-B2.4 Maintainability Stabilization")
    print("=" * 70)
    print()

    result = ValidationResult()

    print("-- Artifact Checks --")
    check_artifacts_exist(result)
    check_baseline_fields(result)
    check_scope_lock_prohibitions(result)
    check_canonical_artifact_consistency(result)
    check_validation_report(result)
    check_codeowners(result)
    check_issue_register(result)

    if args.local_dev:
        print("-- Repository-State Checks (SKIPPED: --local-dev) --")
        result.add("Repository-state checks", True, "Skipped in local-dev mode")
    else:
        print("-- Repository-State Checks --")
        baseline_sha = args.baseline_sha or _extract_baseline_sha_from_artifact()
        if baseline_sha is None:
            result.add(
                "Baseline SHA available",
                False,
                "Cannot determine baseline SHA from artifact or --baseline-sha",
            )
        else:
            result.add("Baseline SHA available", True, baseline_sha[:12])
            changed_files = _git_diff_names(baseline_sha)
            diff_content = _git_diff_content(baseline_sha)
            result.add("Diff available", True, f"{len(changed_files)} files changed")
            check_allowed_change_surface(result, changed_files)
            check_no_prohibited_surface_changes(result, changed_files)
            nongovernance_diff = _filter_diff_exclude_governance(diff_content)
            check_b24_contamination_dependencies(result, nongovernance_diff)
            check_b24_contamination_code(result, nongovernance_diff)
            check_no_ci_gate_removal(result, nongovernance_diff)

    print()
    print("-- Results --")
    print(result.report())
    print()

    if result.passed():
        print("  VERDICT: M0_SCOPE_LOCK_VALID")
        return 0

    print("  VERDICT: M0_SCOPE_LOCK_INVALID")
    return 1


if __name__ == "__main__":
    sys.exit(main())
