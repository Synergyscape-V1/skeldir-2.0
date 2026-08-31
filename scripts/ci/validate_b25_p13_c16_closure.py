#!/usr/bin/env python3
"""Fail-closed Corrective XVI closure validator.

Runtime tests prove the irreversible signing/database transitions against real
PostgreSQL.  This validator binds those falsifiers to the implementation,
migration, scheduler, privilege boundary, deployment serialization, and the
required P13 aggregate.  Every static obligation has a semantic mutation under
``--negative-control`` so a passing counter cannot be decorative.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path("backend/app/trust/audit.py")
TRUST_API = Path("backend/app/api/trust_api.py")
TRUST_EXPORT = Path("backend/app/api/trust_export.py")
TENANT_SECURITY = Path("backend/app/trust/tenant_security.py")
LEDGER = Path("backend/app/trust/issuance_authority_ledger.py")
ISSUANCE_SESSION = Path("backend/app/trust/issuance_session.py")
MAINTENANCE = Path("backend/app/tasks/maintenance.py")
BEAT = Path("backend/app/tasks/beat_schedule.py")
MODELS = Path("backend/app/bayesian/models.py")
MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/"
    "202608301200_b25_p13_c16_bidirectional_issuance_truth.py"
)
TESTS = Path("backend/tests/trust/test_b25_p13_c16_bidirectional_issuance_truth.py")
WORKFLOW = Path(".github/workflows/b2_5-p13-e2e-trust-closure.yml")
SCHEMA_DEPLOY = Path(".github/workflows/schema-deploy-production.yml")
SURVEY = Path(
    "docs/forensics/B2.5-P13 XVI CHECK Constraint NULL Semantics Survey.md"
)
CAPSULES = Path("docs/environment/INFRASTRUCTURE_EVIDENCE_CAPSULES.md")

REQUIRED_AGGREGATE_JOBS = {
    "b25-p13-e2e-trust-closure-core",
    "b2-5-p13-c9-positive-confidence",
    "b2-5-p13-c10-artifact-topology",
    "b2-5-p13-c13-semantic-history",
    "b2-5-p13-c14-semantic-authority",
    "b2-5-p13-c15-issuance-truth",
    "b2-5-p13-c16-bidirectional-truth",
}


class ValidationError(RuntimeError):
    """A required Corrective XVI binding is absent or contradictory."""


def _read(path: Path, overrides: Mapping[Path, str]) -> str:
    if path in overrides:
        return overrides[path]
    full = ROOT / path
    if not full.is_file():
        raise ValidationError(f"missing_required_file:{path.as_posix()}")
    return full.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _between(source: str, start: str, end: str) -> str:
    _require(start in source, f"section_start_missing:{start}")
    tail = source.split(start, 1)[1]
    _require(end in tail, f"section_end_missing:{end}")
    return tail.split(end, 1)[0]


def _ordered(source: str, tokens: tuple[str, ...], message: str) -> None:
    positions = [source.find(token) for token in tokens]
    _require(all(position >= 0 for position in positions), f"{message}:token_missing")
    _require(positions == sorted(positions), f"{message}:order_drift")


def _validate_state_machine(audit: str) -> None:
    for token in (
        "def record_trust_issuance_attempt_started(",
        "SET issuance_state = 'signing'",
        "def record_trust_issuance_completed(",
        "SET issuance_state = 'issued'",
        "issued_signature_hash = :signature_hash",
        "issued_signature = :signature",
        "def record_trust_issuance_outcome_unknown(",
        "SET issuance_state = 'signature_outcome_unknown'",
        "def record_trust_issuance_batch_outcome_unknown(",
        "def reconcile_stale_trust_issuance_states(",
        "FOR UPDATE SKIP LOCKED",
        'observed_rows = int(getattr(result, "rowcount", -1))',
    ):
        _require(token in audit, f"issuance_state_machine_missing:{token}")
    _require(
        audit.count("AND issuance_state = 'signing'") >= 3,
        "completion_or_unknown_not_bound_to_signing",
    )
    _require(
        audit.count("FOR UPDATE SKIP LOCKED") == 2,
        "reconciler_not_bounded_and_lock_safe",
    )


def _validate_route_order(trust_api: str, trust_export: str) -> None:
    issue = _between(trust_api, "async def _issue_signed_envelope(", "@router.get(")
    _ordered(
        issue,
        (
            "await record_trust_issuance_attempt_started(",
            "sign_trust_envelope,",
            "await record_trust_issuance_completed(",
            "_assert_external_payload_safe(signed)",
            "return signed",
        ),
        "trust_api_irreversible_boundary",
    )
    _require(
        issue.count("await record_trust_issuance_outcome_unknown(") == 2,
        "trust_api_unknown_outcome_not_total",
    )

    export_issue = _between(
        trust_export,
        "async def _issue_export_envelope(",
        "async def _finalize_export_issuance_completions(",
    )
    _ordered(
        export_issue,
        (
            "await record_trust_issuance_attempt_started(",
            "sign_trust_envelope,",
            "await record_trust_issuance_outcome_unknown(",
            "return signed, result.audit_record.audit_ref",
        ),
        "trust_export_irreversible_boundary",
    )
    # XVI-C. Externalisation safety is a delivery property. The read path
    # evaluates it strictly after the durable completion write, so the export
    # path must not evaluate it inside the signing boundary -- otherwise the
    # same physical consequence yields two different durable issuance truths.
    _require(
        "_assert_external_payload_safe(" not in export_issue,
        "export_payload_safety_inside_signing_boundary",
    )
    create_export = _between(
        trust_export,
        "async def _create_export_with_capacity(",
        "@router.post(",
    )
    finalization = create_export.rfind(
        "await _finalize_export_issuance_completions("
    )
    _require(finalization >= 0, "export_batch_completion_missing")
    for post_sign_boundary in (
        "_assert_external_payload_safe(envelope)",
        "if deferred_refusal is not None:",
        "MAX_SIGNED_EXPORT_ENVELOPES",
        "build_export_artifact,",
        "MAX_EXPORT_ARTIFACT_BYTES",
        "issue_trust_query_continuation(",
        "return response",
    ):
        position = create_export.find(post_sign_boundary)
        _require(position > finalization, f"export_early_exit_precedes_completion:{post_sign_boundary}")
    finalizer = _between(
        trust_export,
        "async def _finalize_export_issuance_completions(",
        "async def _create_export_with_capacity(",
    )
    _require(
        "record_trust_issuance_batch_completed" in finalizer
        and "record_trust_issuance_batch_outcome_unknown" in finalizer,
        "export_batch_completion_has_no_unknown_fallback",
    )


def _validate_database_contract(migration: str, models: str) -> None:
    upgrade = migration.split("def downgrade()", 1)[0]
    for token in (
        "ADD COLUMN issuance_attempted_at timestamptz",
        "ADD COLUMN issuance_outcome_unknown_at timestamptz",
        "ADD COLUMN issued_signature bytea",
        "'signing'",
        "'signature_outcome_unknown'",
        "issued_signature_hash IS NOT NULL",
        "issued_signature IS NOT NULL",
        "octet_length(issued_signature) = 64",
        "issued_signature IS NULL",
        "ADD COLUMN issuance_attempt_count integer NOT NULL DEFAULT 0",
        "ADD COLUMN issuance_unknown_outcome_count integer NOT NULL DEFAULT 0",
        "trust_access_log_issuance_authority_guard",
        "session_user IN ('app_trust_issuer', table_owner)",
        "trust_issuance_authority_violation:principal:%",
        "trust_issuance_authority_violation:terminal:%",
        "trust_issuance_authority_violation:transition:%->%",
        "trust_issuance_authority_violation:tenant_rebind",
        "trust_issuance_authority_violation:lineage_regression",
        "trust_issuance_authority_violation:insert_state:%",
        "trust_issuance_authority_violation:insert_evidence",
        "divergence_count IS NOT NULL AND divergence_count = 0",
        "confidence_bucket IS NULL",
        "confidence_evidence_snapshot_hash IS NOT NULL",
        "confidence_bucket_reason IS NOT NULL",
        "claim_capability_digest IS NULL",
        "cache_hit_count IS NULL",
    ):
        _require(token in upgrade, f"migration_null_or_evidence_contract_missing:{token}")
    issued_constraint = _between(
        upgrade,
        "ADD CONSTRAINT ck_trust_access_log_issued_requires_crypto",
        "ADD CONSTRAINT ck_trust_access_log_legacy_issued_evidence",
    )
    for token in (
        "issued_signature_hash IS NOT NULL",
        "issued_signature IS NOT NULL",
        "octet_length(issued_signature) = 64",
    ):
        _require(token in issued_constraint, f"issued_crypto_constraint_missing:{token}")
    _require(
        "issued_signature = NULL" in upgrade,
        "historical_backfill_fabricates_or_omits_raw_signature_policy",
    )
    _require(
        "THEN 'issued_legacy'" in upgrade
        and "ELSE 'signature_outcome_unknown'" in upgrade,
        "historical_issuance_backfill_not_truthful",
    )
    for token in (
        "divergence_count IS NOT NULL",
        "confidence_bucket IS NULL",
        "confidence_evidence_snapshot_hash IS NOT NULL",
        "confidence_bucket_reason IS NOT NULL",
    ):
        _require(token in models, f"orm_check_contract_drift:{token}")

    # XVI-B. The guard must enforce the whole legal transition graph, not a
    # single forbidden edge, and terminal history must be immutable.
    guard = _between(
        upgrade,
        "CREATE OR REPLACE FUNCTION public.trust_access_log_issuance_authority_guard()",
        "CREATE TRIGGER trg_trust_access_log_issuance_authority_guard",
    )
    for token in (
        "OLD.issuance_state = 'authorized'",
        "NEW.issuance_state IN ('signing', 'failed')",
        "OLD.issuance_state = 'signing'",
        "'issued', 'signature_outcome_unknown'",
        "OLD.issuance_state IN (\n                'issued', 'issued_legacy', 'not_applicable'\n            )",
        "NEW.tenant_id IS DISTINCT FROM OLD.tenant_id",
        "NEW.issuance_attempt_count < OLD.issuance_attempt_count",
    ):
        _require(token in guard, f"issuance_authority_guard_incomplete:{token}")
    _require(
        "BEFORE INSERT OR UPDATE\n            ON public.trust_access_log" in upgrade,
        "issuance_authority_guard_not_total",
    )


def _validate_issuance_custody(session_module: str, audit: str) -> None:
    """XVI-B. Issuance-consequence writes must not run as the ordinary role."""
    for token in (
        'TRUST_ISSUANCE_DATABASE_URL_ENV = "TRUST_ISSUANCE_DATABASE_URL"',
        'TRUST_ISSUANCE_PRINCIPAL = "app_trust_issuer"',
        "def trust_issuance_session_factory(",
    ):
        _require(token in session_module, f"issuance_custody_module_missing:{token}")
    # Exactly two issuance-consequence entry points bind the custody boundary:
    # the per-transition executor and the reconciler. Pinning the count means a
    # future path that quietly reverts to the ordinary session turns this red.
    _require(
        audit.count("audit_session_factory = trust_issuance_session_factory()") == 2,
        "issuance_writes_not_bound_to_issuance_custody",
    )
    transitions = audit.split("async def _execute_durable_issuance_update(", 1)[1]
    _require(
        "from app.db.session import AsyncSessionLocal" not in transitions,
        "issuance_transition_falls_back_to_ordinary_runtime_session",
    )
    # XVI-D. A retry may not erase the fact that an earlier signing consequence
    # may physically have occurred, so every attempt and every unresolved
    # outcome increments a monotonic counter the trigger refuses to regress.
    _require(
        "issuance_attempt_count = issuance_attempt_count + 1" in audit,
        "issuance_attempt_lineage_not_retained",
    )
    _require(
        audit.count("issuance_unknown_outcome_count + 1") == 3
        and "log.issuance_unknown_outcome_count + 1" in audit,
        "issuance_unknown_lineage_not_retained",
    )


def _validate_reconciler_and_privilege(
    tenant_security: str,
    maintenance: str,
    beat: str,
) -> None:
    _require("SELECT rolbypassrls" in tenant_security, "rls_bypass_guard_missing")
    _require("SELECT rolsuper" in tenant_security, "rls_superuser_guard_missing")
    _require(
        "row is None or bool(row[1]) or bool(row[2])" in tenant_security,
        "rls_privilege_result_not_fail_closed",
    )
    for token in (
        'name="app.tasks.maintenance.reconcile_trust_issuance_for_tenant"',
        'name="app.tasks.maintenance.reconcile_trust_issuance_all_tenants"',
        "reconcile_stale_trust_issuance_states(",
    ):
        _require(token in maintenance, f"reconciler_task_missing:{token}")
    for token in (
        'schedule["b25-p13-trust-issuance-reconciler"]',
        '"app.tasks.maintenance.reconcile_trust_issuance_all_tenants"',
        '"B25_TRUST_ISSUANCE_STALE_SECONDS", 900',
        '"B25_TRUST_ISSUANCE_RECONCILE_BATCH_SIZE", 100',
    ):
        _require(token in beat, f"reconciler_schedule_missing:{token}")


def _validate_tcb(ledger: str) -> None:
    _require('"app.trust.builder"' in ledger, "builder_missing_from_tcb")
    _require('"app.trust.semantic_authority"' in ledger, "authority_missing_from_tcb")
    _require('"app.trust.signing"' not in ledger, "dead_signing_tcb_grant_present")


def _validate_workflows(workflow_text: str, schema_deploy: str) -> None:
    workflow = yaml.safe_load(workflow_text)
    jobs = workflow.get("jobs", {})
    c16 = jobs.get("b2-5-p13-c16-bidirectional-truth")
    _require(isinstance(c16, dict), "c16_load_bearing_job_missing")
    c16_run = "\n".join(
        str(step.get("run", ""))
        for step in c16.get("steps", [])
        if isinstance(step, dict)
    )
    for token in (
        "test_b25_p13_c16_bidirectional_issuance_truth.py",
        "validate_b25_p13_c16_closure.py --negative-control",
        "python -m alembic downgrade 202608291200",
        "python -m alembic upgrade 202608301200",
        "c16_post_signature_boundary_observations=4",
        "c16_nullable_check_candidates=0",
        "c16_reconciled_nonterminal_states=2",
        "c16_static_negative_controls_fired=27",
        "c16_issuance_authority_topology_asserted=1",
        "c16_runtime_negative_controls_fired=$fired",
        "DROP TRIGGER trg_trust_access_log_issuance_authority_guard",
        'TRUST_ISSUANCE_DATABASE_URL="$DATABASE_URL"',
    ):
        _require(token in c16_run, f"c16_workflow_proof_missing:{token}")
    aggregate = jobs.get("b25-p13-e2e-trust-closure")
    _require(isinstance(aggregate, dict), "p13_required_aggregate_missing")
    _require(
        set(aggregate.get("needs", [])) == REQUIRED_AGGREGATE_JOBS,
        "p13_required_aggregate_dependency_drift",
    )
    aggregate_run = "\n".join(
        str(step.get("run", ""))
        for step in aggregate.get("steps", [])
        if isinstance(step, dict)
    )
    _require(
        "b2-5-p13-c16-bidirectional-truth" in aggregate_run,
        "c16_result_not_asserted_by_required_aggregate",
    )

    for token in (
        "group: production-schema-deployment-${{ github.repository }}-main",
        "cancel-in-progress: false",
    ):
        _require(token in schema_deploy, f"schema_deploy_serialization_missing:{token}")
    concurrency = _between(schema_deploy, "concurrency:", "jobs:")
    _require("github.run_id" not in concurrency, "schema_deploy_group_is_per_run")
    _require("github.event_name" not in concurrency, "schema_deploy_group_is_per_event")


def _validate_falsifiers(tests: str) -> None:
    for token in (
        "original_signer = trust_api.sign_trust_envelope",
        "signed = original_signer(*args, **kwargs)",
        "c16_injected_completion_write_failure",
        'verification_status"] == "verified"',
        'issuance_state"] == "signature_outcome_unknown"',
        "MAX_EXPORT_ARTIFACT_BYTES",
        'issuance_state"] == "issued"',
        'len(rows[0]["issued_signature"]) == 64',
        "c16_ordinary_principal_completion_refusals=",
        "c16_issuer_principal_bounded_refusals=",
        "c16_fabricated_insert_refused=",
        "c16_retained_retry_lineage=",
        "c16_nullable_check_candidates=",
        "c16_nullable_check_mutations_refused=",
        "reconcile_stale_trust_issuance_states(",
        "c16_reconciler_schedule_observations=",
    ):
        _require(token in tests, f"c16_runtime_falsifier_missing:{token}")


def _validate_evidence_docs(survey: str, capsules: str) -> None:
    for token in (
        "1248",
        "NULL",
        "ck_trust_access_log_issued_requires_crypto",
        "ck_bayesian_model_fits_available_interval_requires_passed_diagnostics",
        "ck_bayesian_model_fits_available_confidence_complete",
        "c16_nullable_check_candidates=0",
    ):
        _require(token in survey, f"constraint_survey_evidence_missing:{token}")
    for token in ("IEC-XVI-01", "IEC-XVI-02", "IEC-XVI-03"):
        _require(token in capsules, f"infrastructure_capsule_missing:{token}")


def validate_all(overrides: Mapping[Path, str] | None = None) -> None:
    supplied = overrides or {}
    audit = _read(AUDIT, supplied)
    trust_api = _read(TRUST_API, supplied)
    trust_export = _read(TRUST_EXPORT, supplied)
    tenant_security = _read(TENANT_SECURITY, supplied)
    ledger = _read(LEDGER, supplied)
    maintenance = _read(MAINTENANCE, supplied)
    beat = _read(BEAT, supplied)
    models = _read(MODELS, supplied)
    issuance_session = _read(ISSUANCE_SESSION, supplied)
    migration = _read(MIGRATION, supplied)
    tests = _read(TESTS, supplied)
    workflow = _read(WORKFLOW, supplied)
    schema_deploy = _read(SCHEMA_DEPLOY, supplied)
    survey = _read(SURVEY, supplied)
    capsules = _read(CAPSULES, supplied)

    _validate_state_machine(audit)
    _validate_route_order(trust_api, trust_export)
    _validate_database_contract(migration, models)
    _validate_issuance_custody(issuance_session, audit)
    _validate_reconciler_and_privilege(tenant_security, maintenance, beat)
    _validate_tcb(ledger)
    _validate_workflows(workflow, schema_deploy)
    _validate_falsifiers(tests)
    _validate_evidence_docs(survey, capsules)


def _replace_once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count < 1:
        raise ValidationError(f"negative_control_fixture_missing:{old}")
    return source.replace(old, new, 1)


def run_negative_controls() -> int:
    originals = {
        path: _read(path, {})
        for path in (
            AUDIT,
            TRUST_API,
            TRUST_EXPORT,
            TENANT_SECURITY,
            LEDGER,
            MAINTENANCE,
            BEAT,
            MODELS,
            ISSUANCE_SESSION,
            MIGRATION,
            TESTS,
            WORKFLOW,
            SCHEMA_DEPLOY,
            SURVEY,
            CAPSULES,
        )
    }
    controls = (
        (AUDIT, "SET issuance_state = 'signing'", "SET issuance_state = 'authorized'"),
        (AUDIT, "issued_signature = :signature", "issued_signature = NULL"),
        (AUDIT, "FOR UPDATE SKIP LOCKED", "FOR UPDATE"),
        (
            TRUST_API,
            "await record_trust_issuance_attempt_started(",
            "await skipped_attempt_started(",
        ),
        (
            TRUST_EXPORT,
            "await record_trust_issuance_batch_outcome_unknown(",
            "await skipped_batch_unknown(",
        ),
        (
            MIGRATION,
            "AND issued_signature_hash IS NOT NULL\n"
            "                    AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'\n"
            "                    AND issued_signature IS NOT NULL",
            "AND issued_signature_hash IS NULL\n"
            "                    AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'\n"
            "                    AND issued_signature IS NULL",
        ),
        (MIGRATION, "octet_length(issued_signature) = 64", "TRUE"),
        (
            MIGRATION,
            "divergence_count IS NOT NULL AND divergence_count = 0",
            "divergence_count = 0",
        ),
        (
            MIGRATION,
            "confidence_evidence_snapshot_hash IS NOT NULL",
            "confidence_evidence_snapshot_hash IS NULL",
        ),
        (TENANT_SECURITY, "SELECT rolsuper", "SELECT false AS rolsuper"),
        (LEDGER, '"app.trust.semantic_authority",', '"app.trust.signing",'),
        (
            BEAT,
            'schedule["b25-p13-trust-issuance-reconciler"]',
            'schedule["retired-trust-issuance-reconciler"]',
        ),
        (
            WORKFLOW,
            "      - b2-5-p13-c16-bidirectional-truth\n",
            "",
        ),
        (
            SCHEMA_DEPLOY,
            "group: production-schema-deployment-${{ github.repository }}-main",
            "group: ${{ github.run_id }}",
        ),
        (
            TESTS,
            "original_signer = trust_api.sign_trust_envelope",
            "original_signer = fake_signer",
        ),
        (
            SURVEY,
            "c16_nullable_check_candidates=0",
            "c16_nullable_check_candidates=unknown",
        ),
        # NC-C16-B: the issuance transition authority is load-bearing.
        (
            MIGRATION,
            "has_authority := session_user IN ('app_trust_issuer', table_owner);",
            "has_authority := true;",
        ),
        (
            MIGRATION,
            "OLD.issuance_state IN (\n"
            "                'issued', 'issued_legacy', 'not_applicable'\n"
            "            )",
            "false",
        ),
        (
            MIGRATION,
            "NEW.issuance_attempt_count < OLD.issuance_attempt_count",
            "false",
        ),
        (
            MIGRATION,
            "BEFORE INSERT OR UPDATE\n            ON public.trust_access_log",
            "BEFORE UPDATE OF issuance_state\n            ON public.trust_access_log",
        ),
        # NC-C16-C: issuance writes must not fall back to the ordinary role.
        (
            AUDIT,
            "audit_session_factory = trust_issuance_session_factory()",
            "audit_session_factory = None or __import__(\n"
            "            'app.db.session', fromlist=['AsyncSessionLocal']\n"
            "        ).AsyncSessionLocal",
        ),
        (
            ISSUANCE_SESSION,
            'TRUST_ISSUANCE_PRINCIPAL = "app_trust_issuer"',
            'TRUST_ISSUANCE_PRINCIPAL = "app_user"',
        ),
        # NC-C16-D: export must not resolve externalisation safety inside the
        # signing boundary, where it would contradict the read path.
        (
            TRUST_EXPORT,
            "    for envelope in envelopes:\n"
            "        _assert_external_payload_safe(envelope)\n",
            "",
        ),
        # NC-C16-E: the retained-lineage counters are load-bearing.
        (
            AUDIT,
            "issuance_attempt_count = issuance_attempt_count + 1",
            "issuance_attempt_count = issuance_attempt_count",
        ),
        (
            MIGRATION,
            "ADD COLUMN issuance_unknown_outcome_count integer NOT NULL DEFAULT 0",
            "ADD COLUMN issuance_unknown_outcome_retired integer NOT NULL DEFAULT 0",
        ),
        # NC-C16-F: the live-database runtime controls must stay attached.
        (
            WORKFLOW,
            "c16_issuance_authority_topology_asserted=1",
            "c16_issuance_authority_topology_retired=1",
        ),
        (
            WORKFLOW,
            "c16_runtime_negative_controls_fired=",
            "c16_runtime_negative_controls_retired=",
        ),
    )
    fired = 0
    for path, old, new in controls:
        mutated = _replace_once(originals[path], old, new)
        try:
            validate_all({path: mutated})
        except ValidationError:
            fired += 1
        else:
            raise ValidationError(
                f"negative_control_did_not_fire:{path.as_posix()}:{old}"
            )
    return fired


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    # Once C17 is present, its consequence-lineage closure is a strict
    # strengthening of this historical C16 gate. Running the old source-token
    # contract against the strengthened state machine would incorrectly demand
    # that known signatures regress to unknown. Bind the compatibility entry
    # point to the load-bearing successor instead.
    c17_migration = ROOT / (
        "alembic/versions/007_skeldir_foundation/"
        "202608311200_b25_p13_c17_consequence_lineage.py"
    )
    if c17_migration.is_file():
        from validate_b25_p13_c17_closure import (
            run_negative_controls as run_c17_negative_controls,
            validate_all as validate_c17_all,
        )

        validate_c17_all()
        if args.negative_control:
            print(
                "c16_compatibility_negative_controls_fired="
                f"{run_c17_negative_controls()}"
            )
        print("B25_P13_C16_CLOSURE_VALIDATION_PASS")
        return 0
    validate_all()
    if args.negative_control:
        print(f"c16_static_negative_controls_fired={run_negative_controls()}")
    print("B25_P13_C16_CLOSURE_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
