#!/usr/bin/env python3
"""Fail-closed static closure validator for Corrective XVII."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
from typing import Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path("backend/app/trust/audit.py")
TRUST_API = Path("backend/app/api/trust_api.py")
TRUST_EXPORT = Path("backend/app/api/trust_export.py")
SIGNING = Path("backend/app/trust/signing.py")
CONSEQUENCE = Path("backend/app/trust/signing_consequence.py")
SIGNING_AUTHORIZATION = Path("backend/app/trust/signing_authorization.py")
SIGNER_SESSION = Path("backend/app/trust/signer_session.py")
SIGNER_SERVICE = Path("backend/app/trust/signer_service.py")
SIGNER_GATEWAY = Path("backend/app/trust/signer_gateway.py")
RUNTIME_KEYS = Path("backend/app/trust/runtime_keys.py")
MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/"
    "202608311200_b25_p13_c17_consequence_lineage.py"
)
MAINTENANCE = Path("backend/app/tasks/maintenance.py")
ENQUEUE = Path("backend/app/tasks/enqueue.py")
TESTS = Path("backend/tests/trust/test_b25_p13_c17_consequence_lineage.py")
WORKFLOW = Path(".github/workflows/b2_5-p13-e2e-trust-closure.yml")


class ValidationError(RuntimeError):
    """A required C17 closure binding is absent."""


def _read(path: Path, overrides: Mapping[Path, str]) -> str:
    return overrides.get(path, (ROOT / path).read_text(encoding="utf-8"))


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValidationError(reason)


def _between(source: str, start: str, end: str) -> str:
    _require(start in source and end in source, f"boundary_missing:{start}:{end}")
    return source.split(start, 1)[1].split(end, 1)[0]


def validate_all(overrides: Mapping[Path, str] | None = None) -> None:
    supplied = overrides or {}
    audit = _read(AUDIT, supplied)
    trust_api = _read(TRUST_API, supplied)
    export = _read(TRUST_EXPORT, supplied)
    signing = _read(SIGNING, supplied)
    consequence = _read(CONSEQUENCE, supplied)
    signing_authorization = _read(SIGNING_AUTHORIZATION, supplied)
    signer_session = _read(SIGNER_SESSION, supplied)
    signer_service = _read(SIGNER_SERVICE, supplied)
    signer_gateway = _read(SIGNER_GATEWAY, supplied)
    runtime_keys = _read(RUNTIME_KEYS, supplied)
    migration = _read(MIGRATION, supplied)
    maintenance = _read(MAINTENANCE, supplied)
    enqueue = _read(ENQUEUE, supplied)
    tests = _read(TESTS, supplied)
    workflow_text = _read(WORKFLOW, supplied)

    for token in (
        "class SignedTrustEnvelopeConsequence",
        "mint_signing_consequence, redeem_signing_consequence = _new_ledger()",
        '_MINT_MODULE = "app.trust.signing"',
        '_REDEEM_MODULE = "app.trust.audit"',
        "if caller != expected:",
        "signed_envelope=deepcopy(material.signed_envelope)",
    ):
        _require(token in consequence, f"signer_consequence_missing:{token}")
    for token in (
        "def bind_verified_signing_consequence(",
        "def sign_durable_trust_authorization(",
        "redeem_durable_signing_authorization(authorization)",
        "verify_trust_envelope(",
        "key_registry.public_only()",
        "mint_signing_consequence(",
    ):
        _require(token in signing, f"verified_consequence_binding_missing:{token}")
    for token in (
        "class DurableSigningAuthorization",
        '"app.trust.audit", "mint"',
        '"app.trust.signing", "redeem"',
        "unsigned_envelope=deepcopy(material.unsigned_envelope)",
    ):
        _require(
            token in signing_authorization,
            f"durable_signing_authority_missing:{token}",
        )
    for token in (
        'TRUST_SIGNER_DATABASE_URL_ENV = "TRUST_SIGNER_DATABASE_URL"',
        'TRUST_SIGNER_PRINCIPAL = "app_trust_signer"',
        "def trust_signer_session_factory(",
    ):
        _require(token in signer_session, f"signer_custody_missing:{token}")
    for token in (
        '"TRUST_ISSUANCE_DATABASE_URL", "MIGRATION_DATABASE_URL"',
        "trust_signer_private_key_required",
        "TRUST_SIGNER_SHARED_SECRET",
        "authorize_durable_trust_signing_request(",
        "sign_durable_trust_authorization",
        "record_trust_signature_consequence(consequence)",
        "assert_durable_export_signing_request(",
        "record_trust_export_artifact_issued(",
    ):
        _require(token in signer_service, f"signer_service_boundary_missing:{token}")
    for token in (
        '"TRUST_SIGNER_DATABASE_URL"',
        '"SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL"',
        "public_api_forbidden_signer_authority:",
        "trust_signer_transport_tls_required",
        "request_trust_envelope_signature(",
        "request_trust_export_artifact_signature(",
        "request_trust_continuation_signature(",
    ):
        _require(token in signer_gateway, f"public_gateway_boundary_missing:{token}")
    _require(
        "return public_registry" in runtime_keys,
        "public_verification_still_requires_private_seed",
    )

    for token in (
        "CREATE TABLE public.trust_issuance_attempts",
        "CREATE TABLE public.trust_export_artifact_attempts",
        "'signature_known'",
        "'issued_pre_xvii'",
        "issued_attempt_id uuid",
        "issued_envelope jsonb",
        "trust_attempt_authority_violation:signer",
        "session_user NOT IN ('app_trust_signer', table_owner)",
        "id = NEW.issued_attempt_id",
        "NEW.issued_envelope IS DISTINCT FROM attempt.signed_envelope",
        "ALTER TABLE public.trust_issuance_attempts FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.trust_export_artifact_attempts FORCE ROW LEVEL SECURITY",
        "GRANT SELECT, INSERT, UPDATE ON public.trust_issuance_attempts",
        "GRANT SELECT, UPDATE ON public.trust_issuance_attempts",
    ):
        _require(token in migration, f"lineage_migration_missing:{token}")
    _require(
        "SET issuance_state = 'issued_pre_xvii'" in migration,
        "historical_c16_completion_improperly_elevated",
    )

    for token in (
        "async def record_trust_signature_consequence(",
        "async def authorize_durable_trust_signing_request(",
        "envelope_hash = compute_envelope_payload_hash(unsigned_envelope)",
        "durable_signing_attempt_not_current",
        "redeem_signing_consequence(consequence)",
        "SET attempt_state = 'signature_known'",
        "signed_envelope = CAST(:signed_envelope AS jsonb)",
        "attempt.id = log.issued_attempt_id",
        "attempt.attempt_state = 'signature_known'",
        "async def load_durable_trust_issuance_replay(",
        "signature_known_to_issued",
        'counts["signature_known_to_issued"] += 1',
        "async def record_trust_export_artifact_issued(",
        "async def load_durable_trust_export_artifact(",
    ):
        _require(token in audit, f"durable_consequence_path_missing:{token}")
    completion = _between(
        audit,
        "async def record_trust_issuance_completed(",
        "async def load_durable_trust_issuance_artifact(",
    )
    for token in (
        "verify_trust_envelope(",
        "key_registry=registry,",
        "load_runtime_verification_registry().public_only()",
        "issuance_completion_signature_invalid:",
    ):
        _require(token in completion, f"completion_public_verification_missing:{token}")
    for token in (
        "load_durable_trust_issuance_replay(",
        "request_trust_envelope_signature(",
        "durable_after_failure = await load_durable_trust_issuance_artifact(",
        "if durable_after_failure is None:",
        "attempt_id=attempt_id",
    ):
        _require(token in trust_api, f"read_path_lineage_missing:{token}")

    create_export = _between(
        export, "async def _create_export_with_capacity(", "@router.post("
    )
    # Reachability of a durably issued export envelope rests on two orderings.
    # The complete accepted set is resolved and money-checked before anything
    # is signed, and every member of a page is prepared before any member of
    # that page is signed, so a page-local refusal precedes the first
    # private-key call. Re-service closes the remaining case.
    signing_position = create_export.find("await _sign_prepared_export_envelope(")
    resolution = create_export.find("if len(sources) != accepted_count:")
    _require(
        0 <= resolution < signing_position,
        "full_set_resolution_not_before_signing",
    )
    preparation = create_export.find(
        "for page_offset, subject_ref in enumerate(page_refs):"
    )
    signing_loop = create_export.find("for prepared in prepared_envelopes:")
    _require(
        0 <= preparation < signing_loop <= signing_position,
        "page_preparation_not_before_page_signing",
    )
    for token in (
        "load_durable_trust_issuance_replay(",
        "load_durable_trust_export_artifact(",
        "record_trust_export_attempt_started(",
        "request_trust_export_artifact_signature(",
        "artifact_verification = verify_export_artifact(",
        "MAX_EXPORT_ARTIFACT_BYTES",
    ):
        _require(
            token in export or token in create_export,
            f"export_consequence_closure_missing:{token}",
        )

    _require(
        '"app.tasks.maintenance.reconcile_trust_issuance_for_tenant"' in tests
        and "in TENANT_SCOPED_TASK_NAMES" in tests,
        "tenant_dispatch_falsifier_missing",
    )
    _require(
        '"app.tasks.maintenance.reconcile_trust_issuance_for_tenant"' in enqueue,
        "tenant_reconciler_not_dispatchable",
    )
    _require("for _ in range(100):" in maintenance, "tenant_reconciler_not_exhaustive")
    for token in (
        "c17_exact_consequence_correspondence=1",
        "c17_strongest_known_fact_retry=1",
        "c17_restart_key_rotation_reservice=1",
        "c17_issuer_fabrication_refusals=4",
        "c17_raw_signer_invalid_completion_refused=1",
        "c17_durable_recovery_convergence=1",
        "c17_reconciler_dispatch_authorized=1",
        "c17_real_process_custody_boundary=1",
        "c17_process_custody_guards=2",
        "c17_durable_export_reservice=1",
    ):
        _require(token in tests, f"runtime_falsifier_missing:{token}")

    workflow = yaml.safe_load(workflow_text)
    jobs = workflow.get("jobs", {})
    job = jobs.get("b2-5-p13-c17-consequence-lineage")
    _require(isinstance(job, dict), "c17_load_bearing_job_missing")
    run = "\n".join(
        str(step.get("run", ""))
        for step in job.get("steps", [])
        if isinstance(step, dict)
    )
    for token in (
        "test_b25_p13_c17_consequence_lineage.py",
        "validate_b25_p13_c17_closure.py --negative-control",
        "python -m alembic downgrade 202608301200",
        "python -m alembic upgrade head",
        "c17_historical_rows_not_elevated=1",
        "c17_runtime_negative_controls_fired=$fired",
        "c17_export_wrapper_correspondence=1",
        "c17_scheduler_broker_worker_recovery=1",
        "c17_multi_tenant_batch_exhaustion=$((converged * 5))",
        "c17_recovery_idempotence=1",
        "SET app.current_tenant_id = '$1'",
        "c17_live_issuance_race_converged=",
    ):
        _require(token in run, f"c17_workflow_proof_missing:{token}")
    # A CI assertion that names a trigger the migration never creates is not
    # a control: count(*) = 0 and DROP TRIGGER on a missing object both fail
    # for reasons unrelated to the invariant. Bind every trigger identity the
    # C17 job asserts to a trigger the C17 migration actually creates.
    declared_triggers = set(re.findall(r"CREATE TRIGGER\s+(\w+)", migration))
    asserted_triggers = set(re.findall(r"tgname\s*=\s*'(\w+)'", run)) | set(
        re.findall(r"DROP TRIGGER\s+(?:IF EXISTS\s+)?(\w+)", run)
    )
    _require(bool(asserted_triggers), "c17_workflow_asserts_no_trigger_identity")
    unknown = sorted(asserted_triggers - declared_triggers)
    _require(not unknown, f"c17_workflow_trigger_identity_drift:{unknown}")
    aggregate = jobs.get("b25-p13-e2e-trust-closure", {})
    _require(
        "b2-5-p13-c17-consequence-lineage" in aggregate.get("needs", []),
        "c17_not_load_bearing_in_aggregate",
    )


def _replace_once(source: str, old: str, new: str) -> str:
    _require(old in source, f"negative_control_fixture_missing:{old}")
    return source.replace(old, new, 1)


def run_negative_controls() -> int:
    paths = (
        AUDIT,
        TRUST_API,
        TRUST_EXPORT,
        SIGNING,
        CONSEQUENCE,
        SIGNING_AUTHORIZATION,
        SIGNER_SESSION,
        SIGNER_SERVICE,
        SIGNER_GATEWAY,
        RUNTIME_KEYS,
        MIGRATION,
        MAINTENANCE,
        ENQUEUE,
        TESTS,
        WORKFLOW,
    )
    originals = {path: _read(path, {}) for path in paths}
    controls = (
        (CONSEQUENCE, "if caller != expected:", "if False:"),
        (SIGNING, "key_registry.public_only()", "key_registry"),
        (
            SIGNING_AUTHORIZATION,
            '"app.trust.audit", "mint"',
            '"app.api.trust_api", "mint"',
        ),
        (
            SIGNER_SESSION,
            'TRUST_SIGNER_PRINCIPAL = "app_trust_signer"',
            'TRUST_SIGNER_PRINCIPAL = "app_user"',
        ),
        (
            MIGRATION,
            "SET issuance_state = 'issued_pre_xvii'",
            "SET issuance_state = 'issued'",
        ),
        (
            MIGRATION,
            "trust_attempt_authority_violation:signer",
            "trust_attempt_authority_retired",
        ),
        (
            MIGRATION,
            "NEW.issued_envelope IS DISTINCT FROM attempt.signed_envelope",
            "FALSE",
        ),
        (
            MIGRATION,
            "ALTER TABLE public.trust_issuance_attempts FORCE ROW LEVEL SECURITY",
            "-- RLS retired",
        ),
        (AUDIT, "redeem_signing_consequence(consequence)", "material = consequence"),
        (
            AUDIT,
            "async def record_trust_signature_consequence(",
            "async def retired_signature_consequence(",
        ),
        (
            AUDIT,
            'counts["signature_known_to_issued"] += 1',
            'counts["signature_known_to_issued"] += 0',
        ),
        (
            AUDIT,
            "issuance_completion_signature_invalid:",
            "issuance_completion_signature_unchecked:",
        ),
        (
            TRUST_API,
            "request_trust_envelope_signature(",
            "local_sign_trust_envelope(",
        ),
        (
            TRUST_API,
            "if durable_after_failure is None:",
            "if True:",
        ),
        (
            TRUST_EXPORT,
            "if len(sources) != accepted_count:",
            "if False:",
        ),
        (
            TRUST_EXPORT,
            "for page_offset, subject_ref in enumerate(page_refs):",
            "for page_offset, subject_ref in enumerate([]):",
        ),
        (
            TRUST_EXPORT,
            "request_trust_export_artifact_signature(",
            "skip_export_artifact_history(",
        ),
        (
            TRUST_EXPORT,
            "artifact_verification = verify_export_artifact(",
            "artifact_verification = accept_export_artifact(",
        ),
        (
            SIGNER_SERVICE,
            '"TRUST_ISSUANCE_DATABASE_URL", "MIGRATION_DATABASE_URL"',
            '"UNUSED_ONE", "UNUSED_TWO"',
        ),
        (
            SIGNER_GATEWAY,
            '"TRUST_SIGNER_DATABASE_URL"',
            '"TRUST_SIGNER_DATABASE_URL_RETIRED"',
        ),
        (
            RUNTIME_KEYS,
            "return public_registry",
            "return load_runtime_signing_registry()",
        ),
        (
            ENQUEUE,
            '"app.tasks.maintenance.reconcile_trust_issuance_for_tenant"',
            '"retired.reconciler"',
        ),
        (MAINTENANCE, "for _ in range(100):", "for _ in range(0):"),
        (
            TESTS,
            "c17_issuer_fabrication_refusals=4",
            "c17_issuer_fabrication_refusals=0",
        ),
        (WORKFLOW, "      - b2-5-p13-c17-consequence-lineage\n", ""),
        (
            WORKFLOW,
            "tgname='trg_trust_issuance_attempt_guard'",
            "tgname='trg_trust_issuance_attempt_authority_guard'",
        ),
        (
            MIGRATION,
            "CREATE TRIGGER trg_trust_issuance_attempt_guard",
            "CREATE TRIGGER trg_trust_issuance_attempt_retired",
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
            raise ValidationError(f"negative_control_did_not_fire:{path}:{old}")
    return fired


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    validate_all()
    if args.negative_control:
        print(f"c17_static_negative_controls_fired={run_negative_controls()}")
    print("B25_P13_C17_CLOSURE_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
