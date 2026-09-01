#!/usr/bin/env python3
"""Fail-closed Directive XIV authority-capability and CI proof graph."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = Path("backend/app/trust/semantic_authority.py")
BUILDER = Path("backend/app/trust/builder.py")
AUDIT = Path("backend/app/trust/audit.py")
SIGNING = Path("backend/app/trust/signing.py")
TRUST_API = Path("backend/app/api/trust_api.py")
TRUST_EXPORT = Path("backend/app/api/trust_export.py")
TESTS = Path("backend/tests/trust/test_b25_p13_c14_semantic_authority.py")
SCHEMA = Path("contracts/trust-api/trust-envelope.v2.yaml")
MATRIX = Path(
    "contracts-internal/governance/" "b25_p13_c14_trust_semantic_authority.v1.json"
)
WORKFLOW = Path(".github/workflows/b2_5-p13-e2e-trust-closure.yml")

EXPECTED_PRIVATE_KEY_ROUTES = {
    "backend/app/trust/signing.py",
    "backend/app/trust/export_artifact.py",
    "backend/app/trust/query_continuation.py",
}
# Corrective XVII removed the private key from the public API process. The
# process-local capability entry point therefore has exactly one referencing
# module, and the API reaches a real consequence only through the credential-
# isolated signer service. Both inventories are asserted so that reintroducing
# an in-process signing call, or widening the signer surface, fails closed.
EXPECTED_TRUST_SIGN_CALLERS = {
    "backend/app/trust/signing.py",
}
EXPECTED_DURABLE_SIGN_CALLERS = {
    "backend/app/trust/signer_service.py",
}
EXPECTED_SIGNER_GATEWAY_CALLERS = {
    "backend/app/api/trust_api.py",
    "backend/app/api/trust_export.py",
}
LOAD_BEARING_JOBS = {
    "b25-p13-e2e-trust-closure-core",
    "b2-5-p13-c9-positive-confidence",
    "b2-5-p13-c10-artifact-topology",
    "b2-5-p13-c13-semantic-history",
    "b2-5-p13-c14-semantic-authority",
    # B2.5-P13 Corrective XV: issuance-capability inescapability, durable
    # audit truth, and historical HTTP serviceability are merge-governing.
    "b2-5-p13-c15-issuance-truth",
    # Corrective XVI: physical signature history is conserved in both
    # directions and nullable CHECK semantics are surveyed exhaustively.
    "b2-5-p13-c16-bidirectional-truth",
    # Corrective XIX: the full production-topology composition proof
    # (external evidence to public verification) is merge-governing.
    "b2-5-p13-c19-context-robust-closure",
    "b2-5-p13-c17-consequence-lineage",
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


def _call_files(call_name: str) -> set[str]:
    found: set[str] = set()
    for path in (ROOT / "backend/app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, ast.Call)
            and (
                isinstance(node.func, ast.Name)
                and node.func.id == call_name
                or isinstance(node.func, ast.Attribute)
                and node.func.attr == call_name
            )
            for node in ast.walk(tree)
        ):
            found.add(path.relative_to(ROOT).as_posix())
    return found


def _name_reference_files(name: str) -> set[str]:
    found: set[str] = set()
    for path in (ROOT / "backend/app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, ast.Name) and node.id == name for node in ast.walk(tree)
        ):
            found.add(path.relative_to(ROOT).as_posix())
    return found


def _manifest_fields(authority_text: str) -> set[str]:
    tree = ast.parse(authority_text)
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "TRUST_ENVELOPE_AUTHORITY_FIELDS"
                for target in node.targets
            )
            and isinstance(node.value, ast.Call)
            and node.value.args
        ):
            return set(ast.literal_eval(node.value.args[0]))
    raise ValidationError("runtime_authority_field_manifest_missing")


def validate_field_authority_closure(
    authority_text: str | None = None,
    matrix_text: str | None = None,
) -> None:
    authority = authority_text if authority_text is not None else _read(AUTHORITY)
    matrix = json.loads(matrix_text if matrix_text is not None else _read(MATRIX))
    schema = yaml.safe_load(_read(SCHEMA))
    schema_fields = set(schema["properties"])
    runtime_fields = _manifest_fields(authority)
    matrix_fields = {row["field"] for row in matrix["fields"]}
    _require(
        schema_fields == runtime_fields == matrix_fields,
        "signed_semantic_authority_inventory_drift",
    )
    _require(len(schema_fields) == 41, "signed_semantic_field_count_drift")
    _require(
        len(matrix.get("compound_claims", [])) == 5,
        "compound_authority_claims_incomplete",
    )
    universal = matrix.get("universal_boundary", {})
    for key in (
        "who_may_mutate",
        "correspondence_proof",
        "immutable_at",
        "validated_before_issuance",
        "failure_behavior",
        "public_verification_limit",
    ):
        _require(bool(universal.get(key)), f"authority_matrix_column_missing:{key}")


def validate_capability_boundary(
    signing_text: str | None = None,
    authority_text: str | None = None,
    audit_text: str | None = None,
    api_text: str | None = None,
    export_text: str | None = None,
) -> None:
    signing = signing_text if signing_text is not None else _read(SIGNING)
    authority = authority_text if authority_text is not None else _read(AUTHORITY)
    audit = audit_text if audit_text is not None else _read(AUDIT)
    api = api_text if api_text is not None else _read(TRUST_API)
    export = export_text if export_text is not None else _read(TRUST_EXPORT)

    capability_check = signing.index(
        "isinstance(authorized_envelope, AuthorizedTrustEnvelope)"
    )
    seal_check = signing.index("authorized_envelope._validated_payload_copy()")
    key_selection = signing.index("key_registry.active_signing_key()")
    crypto = signing.index("key.private_key.sign(material)")
    _require(
        capability_check < seal_check < key_selection < crypto,
        "capability_validation_not_before_private_key",
    )
    for token in (
        "if actual_bytes != expected_bytes",
        "if audited_payload != expected",
        "_validate_identity_correspondence(payload, witness=witness)",
        "_validate_source_window_correspondence(payload, witness=witness)",
        "_validate_confidence_state(payload)",
        "validate_envelope_policy_authority(payload)",
        "return AuthorizedTrustEnvelope(",
    ):
        _require(token in authority, f"semantic_capability_boundary_missing:{token}")
    _require(
        "authorized_envelope = _authorize_audited_trust_envelope(" in audit,
        "audit_does_not_mint_capability",
    )
    for source, label in ((api, "api"), (export, "export")):
        _require(
            "result.authorized_envelope" in source,
            f"{label}_does_not_consume_capability",
        )
        _require(
            "sign_trust_envelope,\n        result.unsigned_payload" not in source,
            f"{label}_signs_mutable_payload",
        )


def validate_capability_graph() -> None:
    _require(
        _call_files("_authorize_audited_trust_envelope") == {AUDIT.as_posix()},
        "capability_mint_callsite_drift",
    )
    _require(
        _call_files("AuthorizedTrustEnvelope") == {AUTHORITY.as_posix()},
        "capability_constructor_callsite_drift",
    )
    _require(
        _call_files("TrustEnvelopeBuildWitness") == {BUILDER.as_posix()},
        "builder_witness_constructor_callsite_drift",
    )
    _require(
        _name_reference_files("sign_trust_envelope") == EXPECTED_TRUST_SIGN_CALLERS,
        "trust_signing_caller_inventory_drift",
    )
    _require(
        _name_reference_files("sign_durable_trust_authorization")
        == EXPECTED_DURABLE_SIGN_CALLERS,
        "durable_signing_caller_inventory_drift",
    )
    _require(
        _name_reference_files("request_trust_envelope_signature")
        == EXPECTED_SIGNER_GATEWAY_CALLERS,
        "signer_gateway_caller_inventory_drift",
    )
    actual_private: set[str] = set()
    for path in (ROOT / "backend/app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "sign"
            for node in ast.walk(tree)
        ):
            actual_private.add(path.relative_to(ROOT).as_posix())
    _require(
        actual_private == EXPECTED_PRIVATE_KEY_ROUTES,
        f"unclassified_private_key_route:{sorted(actual_private ^ EXPECTED_PRIVATE_KEY_ROUTES)}",
    )


def validate_merge_graph(workflow_text: str | None = None) -> None:
    source = workflow_text if workflow_text is not None else _read(WORKFLOW)
    workflow = yaml.safe_load(source)
    jobs = workflow.get("jobs", {})
    semantic = jobs.get("b2-5-p13-c14-semantic-authority", {})
    run = "\n".join(str(step.get("run", "")) for step in semantic.get("steps", []))
    for token in (
        "test_b25_p13_c14_semantic_authority.py",
        "validate_b25_p13_c14_closure.py --negative-control",
        "NC-XIV-FINANCIAL",
        "NC-XIV-IDENTITY",
        "NC-XIV-SOURCE-WINDOW",
        "NC-XIV-CONFIDENCE",
        "NC-XIV-BAYESIAN",
    ):
        _require(token in run, f"c14_merge_proof_missing:{token}")
    gate = jobs.get("b25-p13-e2e-trust-closure", {})
    _require(gate.get("if") == "always()", "required_aggregator_not_fail_closed")
    _require(
        set(gate.get("needs", [])) == LOAD_BEARING_JOBS,
        "required_aggregator_dependency_drift",
    )
    gate_run = "\n".join(str(step.get("run", "")) for step in gate.get("steps", []))
    _require(
        "b2-5-p13-c14-semantic-authority" in gate_run,
        "c14_result_not_asserted_by_required_aggregator",
    )


def validate_all() -> None:
    for path in (
        AUTHORITY,
        BUILDER,
        AUDIT,
        SIGNING,
        TRUST_API,
        TRUST_EXPORT,
        TESTS,
        SCHEMA,
        MATRIX,
        WORKFLOW,
    ):
        _read(path)
    validate_field_authority_closure()
    validate_capability_boundary()
    validate_capability_graph()
    validate_merge_graph()


def run_negative_controls() -> None:
    authority = _read(AUTHORITY)
    signing = _read(SIGNING)
    audit = _read(AUDIT)
    api = _read(TRUST_API)
    matrix = _read(MATRIX)
    workflow = _read(WORKFLOW)
    controls = (
        (
            "raw_signer_reenabled",
            lambda: validate_capability_boundary(
                signing.replace(
                    "isinstance(authorized_envelope, AuthorizedTrustEnvelope)",
                    "True",
                    1,
                ),
                authority,
                audit,
                api,
                _read(TRUST_EXPORT),
            ),
        ),
        (
            "audit_capability_mint_removed",
            lambda: validate_capability_boundary(
                signing,
                authority,
                audit.replace(
                    "authorized_envelope = _authorize_audited_trust_envelope(",
                    "authorized_envelope = None # ",
                    1,
                ),
                api,
                _read(TRUST_EXPORT),
            ),
        ),
        (
            "api_mutable_payload_restored",
            lambda: validate_capability_boundary(
                signing,
                authority,
                audit,
                api.replace(
                    "result.authorized_envelope",
                    "result.unsigned_payload",
                ),
                _read(TRUST_EXPORT),
            ),
        ),
        (
            "schema_field_authority_removed",
            lambda: validate_field_authority_closure(
                authority,
                matrix.replace('"field":"currency",', '"field":"currency_removed",', 1),
            ),
        ),
        (
            "identity_validator_removed",
            lambda: validate_capability_boundary(
                signing,
                authority.replace(
                    "_validate_identity_correspondence(payload, witness=witness)",
                    "None",
                    1,
                ),
                audit,
                api,
                _read(TRUST_EXPORT),
            ),
        ),
        (
            "confidence_validator_removed",
            lambda: validate_capability_boundary(
                signing,
                authority.replace("_validate_confidence_state(payload)", "None", 1),
                audit,
                api,
                _read(TRUST_EXPORT),
            ),
        ),
        (
            "c14_job_detached",
            lambda: validate_merge_graph(
                workflow.replace(
                    "      - b2-5-p13-c14-semantic-authority\n",
                    "",
                    1,
                )
            ),
        ),
    )
    fired = 0
    for name, runner in controls:
        try:
            runner()
        except (ValidationError, ValueError, json.JSONDecodeError, SyntaxError):
            fired += 1
        else:
            raise ValidationError(f"negative_control_did_not_fire:{name}")
    print(f"c14_static_negative_controls_fired={fired}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        validate_all()
        if args.negative_control:
            run_negative_controls()
    except (ValidationError, yaml.YAMLError, json.JSONDecodeError) as exc:
        print(f"B25_P13_C14_CLOSURE_VALIDATION_FAIL: {exc}")
        return 1
    print("B25_P13_C14_CLOSURE_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
