#!/usr/bin/env python3
"""Fail-closed Corrective XV closure: issuance capability, audit truth, history.

Guards the three properties Corrective XV established, each of which was
falsified against protected main before remediation:

* **H-XV-01** -- TrustEnvelope signing capability is unforgeable outside a
  declared trusted computing base, and carries no payload to transplant.
* **H-XV-02/03** -- durable audit history distinguishes an *authorised* issuance
  from a *completed cryptographic* one, and the database physically refuses to
  record completion without the signature that would justify it.
* **H-XV-09** -- the repository governs its own line endings, so the documented
  bootstrap is executable on a clean clone.

Every check here is paired with a negative control under ``--negative-control``:
a meaningful mutation must make the check red, or the check is decorative.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

LEDGER = Path("backend/app/trust/issuance_authority_ledger.py")
AUTHORITY = Path("backend/app/trust/semantic_authority.py")
BUILDER = Path("backend/app/trust/builder.py")
AUDIT = Path("backend/app/trust/audit.py")
TRUST_API = Path("backend/app/api/trust_api.py")
TRUST_EXPORT = Path("backend/app/api/trust_export.py")
MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/"
    "202608301200_b25_p13_c16_bidirectional_issuance_truth.py"
)
TESTS = Path("backend/tests/trust/test_b25_p13_c15_issuance_truth.py")
TCB_DOC = Path("docs/security/b25_p13_c15_trusted_computing_base.md")
GITATTRIBUTES = Path(".gitattributes")
ENV_MATRIX = Path("docs/environment/SUPPORTED_ENVIRONMENTS.md")
WORKFLOW = Path(".github/workflows/b2_5-p13-e2e-trust-closure.yml")

EXPECTED_TCB = {
    "app.trust.builder",
    "app.trust.semantic_authority",
}


class ValidationError(RuntimeError):
    pass


def _read(path: Path) -> str:
    full = ROOT / path
    if not full.is_file():
        raise ValidationError(f"missing_required_file:{path.as_posix()}")
    return full.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


# ---------------------------------------------------------------- capability


def validate_capability_inescapability(
    ledger: str, authority: str, builder: str
) -> None:
    """The capability must carry no claim and must be ledger-addressed."""

    declared = set(re.findall(r'"(app\.trust\.[a-z_]+)"', ledger))
    _require(
        declared == EXPECTED_TCB,
        "c15_tcb_declaration_missing",
    )
    _require(
        "def _assert_trusted_caller" in ledger,
        "c15_ledger_has_no_caller_boundary",
    )
    _require(
        "_assert_trusted_caller" in ledger.split("def mint", 1)[-1],
        "c15_mint_does_not_check_caller",
    )
    _require(
        "entries: dict[str, bytes] = {}" in ledger,
        "c15_ledger_table_is_not_closure_private",
    )
    _require(
        "sys._getframe" in ledger,
        "c15_caller_identity_not_resolved",
    )

    # The dead seal design must not come back. Matched as a *definition*, so
    # the docstrings that explain why it was removed do not trip the check.
    _require(
        re.search(r"^_CAPABILITY_SEAL\s*=", authority, re.M) is None,
        "c15_importable_capability_seal_reintroduced",
    )
    _require(
        re.search(r"^_BUILD_WITNESS_SEAL\s*=", builder, re.M) is None,
        "c15_importable_witness_seal_reintroduced",
    )
    # No payload on the capability means nothing for an attacker to author.
    _require(
        "_payload_snapshot: bytes" not in authority,
        "c15_capability_carries_transplantable_payload",
    )
    _require(
        "canonical_payload: bytes" not in builder,
        "c15_witness_carries_transplantable_payload",
    )
    _require(
        "_authority_handle" in authority and "_authority_handle" in builder,
        "c15_ledger_handle_missing",
    )
    # Redemption at the private-key boundary must consume the capability.
    _require(
        "consume=True" in authority,
        "c15_capability_redemption_is_not_single_use",
    )


# ------------------------------------------------------------- audit truth


def validate_issuance_state_model(audit: str, api: str, export: str) -> None:
    """Authorization, private-key entry, uncertainty, and completion are distinct."""

    _require(
        "async def record_trust_issuance_completed" in audit,
        "c15_no_issuance_completion_record",
    )
    _require(
        "async def record_trust_issuance_attempt_started" in audit,
        "c15_no_write_ahead_signing_record",
    )
    _require(
        "issuance_completion_requires_signature_identity" in audit,
        "c15_completion_does_not_require_signature_identity",
    )
    _require(
        "THEN 'authorized' ELSE 'not_applicable' END" in audit,
        "c15_pre_sign_row_does_not_record_authorized_state",
    )
    _require(
        "async def record_trust_issuance_outcome_unknown" in audit,
        "c15_no_indeterminate_issuance_record",
    )
    _require(
        "async def record_trust_issuance_batch_outcome_unknown" in audit,
        "c15_no_batch_indeterminate_issuance_record",
    )
    _require(
        "issuance_completion_requires_valid_signature_bytes" in audit,
        "c15_completion_does_not_retain_signature_evidence",
    )
    # The read route finalises per envelope; the export route signs several per
    # request and finalises them in one transaction. Either shape counts as
    # finalisation, but a route with neither does not.
    for source, label in ((api, "api"), (export, "export")):
        _require(
            "record_trust_issuance_completed(" in source
            or "record_trust_issuance_batch_completed(" in source,
            f"c15_{label}_does_not_finalize_completed_issuance",
        )
        _require(
            "record_trust_issuance_attempt_started(" in source,
            f"c15_{label}_does_not_write_ahead_before_signing",
        )
        _require(
            "record_trust_issuance_outcome_unknown(" in source
            or "record_trust_issuance_batch_outcome_unknown(" in source,
            f"c15_{label}_does_not_record_indeterminate_issuance",
        )


def validate_database_enforces_completion(migration: str) -> None:
    """The invariant must be physics, not application discipline."""

    _require(
        "ck_trust_access_log_issued_requires_crypto" in migration,
        "c15_no_database_completion_constraint",
    )
    _require(
        "issued_signature_hash IS NOT NULL" in migration,
        "c15_completion_constraint_allows_null_hash",
    )
    _require(
        "issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'" in migration,
        "c15_completion_constraint_does_not_bind_signature",
    )
    _require(
        "issued_signature IS NOT NULL" in migration
        and "octet_length(issued_signature) = 64" in migration,
        "c15_completion_constraint_lacks_signature_bytes",
    )
    _require(
        "ck_trust_access_log_nonissued_has_no_crypto" in migration,
        "c15_unissued_rows_may_carry_signature_evidence",
    )


# --------------------------------------------------- bootstrap portability


def validate_line_ending_policy(gitattributes: str) -> None:
    """A CRLF shell script is a broken supported build path."""

    _require("* text=auto" in gitattributes, "c15_no_repository_eol_normalization")
    for pattern in ("*.sh", "Makefile", "Procfile"):
        _require(
            re.search(rf"^{re.escape(pattern)}\s+text eol=lf", gitattributes, re.M)
            is not None,
            f"c15_lf_not_enforced_for:{pattern}",
        )
    _require(
        re.search(r"^\*\.ps1\s+text eol=crlf", gitattributes, re.M) is not None,
        "c15_powershell_crlf_not_preserved",
    )


def validate_supported_environment_matrix(matrix: str) -> None:
    """Documentation must not imply compatibility the repository lacks."""

    for required in (
        "Supported environments",
        "Not supported",
        "run_m1_onboarding_bootstrap.sh",
    ):
        _require(required in matrix, f"c15_environment_matrix_missing:{required}")


# ----------------------------------------------------------------- proofs


def validate_proof_wiring(tests: str, workflow: str) -> None:
    """The falsifiers must exist and must gate the merge."""

    for marker in (
        "test_c15_direct_constructor_cannot_mint_capability",
        "test_c15_object_new_and_setattr_cannot_mint_capability",
        "test_c15_ledger_mint_outside_the_tcb_is_refused",
        "test_c15_forged_build_witness_is_refused",
        "test_c15_raw_caller_dictionary_still_cannot_sign",
        "test_c15_durable_history_never_overstates_physical_issuance",
        "test_c15_database_physically_refuses_unbacked_completion_claim",
        "test_c15_retry_after_indeterminate_yields_one_coherent_lineage",
        "test_c15_historical_envelope_serviceable_over_http_after_key_rotation",
    ):
        _require(marker in tests, f"c15_missing_falsifier:{marker}")
    _require(
        "b2-5-p13-c15-issuance-truth" in workflow,
        "c15_proof_job_not_declared",
    )
    _require(
        "- b2-5-p13-c15-issuance-truth" in workflow,
        "c15_proof_job_not_required_by_aggregate",
    )


def validate_all() -> None:
    ledger = _read(LEDGER)
    authority = _read(AUTHORITY)
    builder = _read(BUILDER)
    audit = _read(AUDIT)
    api = _read(TRUST_API)
    export = _read(TRUST_EXPORT)
    migration = _read(MIGRATION)
    tests = _read(TESTS)
    _read(TCB_DOC)

    validate_capability_inescapability(ledger, authority, builder)
    validate_issuance_state_model(audit, api, export)
    validate_database_enforces_completion(migration)
    validate_line_ending_policy(_read(GITATTRIBUTES))
    validate_supported_environment_matrix(_read(ENV_MATRIX))
    validate_proof_wiring(tests, _read(WORKFLOW))


def run_negative_controls() -> None:
    """Every check above must be red under a meaningful violation.

    The mutations deliberately use mechanisms different from the exact defects
    originally discovered, per the open-world rule: a control that only detects
    the historical bug proves nothing about the class.
    """

    ledger = _read(LEDGER)
    authority = _read(AUTHORITY)
    builder = _read(BUILDER)
    audit = _read(AUDIT)
    api = _read(TRUST_API)
    export = _read(TRUST_EXPORT)
    migration = _read(MIGRATION)
    tests = _read(TESTS)
    workflow = _read(WORKFLOW)
    gitattributes = _read(GITATTRIBUTES)
    matrix = _read(ENV_MATRIX)

    controls = (
        (
            "tcb_boundary_removed",
            lambda: validate_capability_inescapability(
                ledger.replace("def _assert_trusted_caller", "def _unused_caller_check"),
                authority,
                builder,
            ),
        ),
        (
            "ledger_table_made_module_global",
            lambda: validate_capability_inescapability(
                ledger.replace("entries: dict[str, bytes] = {}", "entries = _GLOBALS"),
                authority,
                builder,
            ),
        ),
        (
            "capability_payload_reintroduced",
            lambda: validate_capability_inescapability(
                ledger,
                authority.replace(
                    "    authority_proof_hash: str",
                    "    _payload_snapshot: bytes\n    authority_proof_hash: str",
                    1,
                ),
                builder,
            ),
        ),
        (
            "witness_payload_reintroduced",
            lambda: validate_capability_inescapability(
                ledger,
                authority,
                builder.replace(
                    "    tenant_id_hash: str",
                    "    canonical_payload: bytes\n    tenant_id_hash: str",
                    1,
                ),
            ),
        ),
        (
            "importable_capability_seal_restored",
            lambda: validate_capability_inescapability(
                ledger, "_CAPABILITY_SEAL = object()\n" + authority, builder
            ),
        ),
        (
            "importable_witness_seal_restored",
            lambda: validate_capability_inescapability(
                ledger, authority, "_BUILD_WITNESS_SEAL = object()\n" + builder
            ),
        ),
        (
            "capability_redemption_made_replayable",
            lambda: validate_capability_inescapability(
                ledger, authority.replace("consume=True", "consume=False"), builder
            ),
        ),
        (
            "completion_record_removed",
            lambda: validate_issuance_state_model(
                audit.replace(
                    "async def record_trust_issuance_completed",
                    "async def _retired_record_trust_issuance_completed",
                ),
                api,
                export,
            ),
        ),
        (
            "pre_sign_row_claims_completion",
            lambda: validate_issuance_state_model(
                audit.replace(
                    "THEN 'authorized' ELSE 'not_applicable' END",
                    "THEN 'issued' ELSE 'not_applicable' END",
                ),
                api,
                export,
            ),
        ),
        (
            "api_stops_finalizing_issuance",
            lambda: validate_issuance_state_model(
                audit,
                api.replace("record_trust_issuance_completed(", "_skip_completion("),
                export,
            ),
        ),
        (
            "export_stops_finalizing_completion",
            lambda: validate_issuance_state_model(
                audit,
                api,
                export.replace("record_trust_issuance_batch_completed(", "_skip("),
            ),
        ),
        (
            "batch_completion_stops_requiring_signature_identity",
            lambda: validate_issuance_state_model(
                audit.replace(
                    "issuance_completion_requires_valid_signature_bytes",
                    "issuance_completion_unchecked",
                ),
                api,
                export,
            ),
        ),
        (
            "export_stops_recording_indeterminate_outcome",
            lambda: validate_issuance_state_model(
                audit,
                api,
                export.replace(
                    "record_trust_issuance_outcome_unknown(", "_skip_unknown("
                ).replace(
                    "record_trust_issuance_batch_outcome_unknown(",
                    "_skip_batch_unknown(",
                ),
            ),
        ),
        (
            "database_completion_constraint_dropped",
            lambda: validate_database_enforces_completion(
                migration.replace(
                    "ck_trust_access_log_issued_requires_crypto",
                    "ck_trust_access_log_retired_constraint",
                )
            ),
        ),
        (
            "completion_constraint_stops_binding_signature",
            lambda: validate_database_enforces_completion(
                migration.replace(
                    "issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'",
                    "issued_signature_hash IS NOT NULL",
                )
            ),
        ),
        (
            "shell_line_endings_unpinned",
            lambda: validate_line_ending_policy(
                gitattributes.replace("*.sh            text eol=lf", "# removed")
            ),
        ),
        (
            "powershell_forced_to_lf",
            lambda: validate_line_ending_policy(
                gitattributes.replace(
                    "*.ps1           text eol=crlf", "*.ps1           text eol=lf"
                )
            ),
        ),
        (
            "environment_matrix_drops_unsupported_section",
            lambda: validate_supported_environment_matrix(
                matrix.replace("Not supported", "Other notes")
            ),
        ),
        (
            "capability_falsifier_deleted",
            lambda: validate_proof_wiring(
                tests.replace(
                    "test_c15_object_new_and_setattr_cannot_mint_capability",
                    "_disabled_object_new_probe",
                ),
                workflow,
            ),
        ),
        (
            "historical_serviceability_falsifier_deleted",
            lambda: validate_proof_wiring(
                tests.replace(
                    "test_c15_historical_envelope_serviceable_over_http_after_key_rotation",
                    "_disabled_historical_probe",
                ),
                workflow,
            ),
        ),
        (
            "proof_job_dropped_from_aggregate",
            lambda: validate_proof_wiring(
                tests, workflow.replace("- b2-5-p13-c15-issuance-truth", "- retired")
            ),
        ),
    )

    fired = 0
    for name, control in controls:
        try:
            control()
        except ValidationError:
            fired += 1
            continue
        raise ValidationError(f"negative_control_did_not_fire:{name}")
    print(f"c15_static_negative_controls_fired={fired}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        validate_all()
        if args.negative_control:
            run_negative_controls()
    except ValidationError as exc:
        print(f"B25_P13_C15_CLOSURE_VALIDATION_FAIL: {exc}")
        return 1
    print("B25_P13_C15_CLOSURE_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
