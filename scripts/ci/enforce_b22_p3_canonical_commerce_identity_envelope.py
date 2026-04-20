#!/usr/bin/env python3
"""B2.2-P3 canonical commerce identity envelope enforcer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_CONTRACT = (
    "contracts-internal/governance/b22_p3_canonical_commerce_identity_envelope.main.json"
)
MODEL_FILE = "backend/app/models/webhook_ingress_identity.py"
WEBHOOKS_FILE = "backend/app/api/webhooks.py"
EVENT_SERVICE_FILE = "backend/app/ingestion/event_service.py"
MIGRATION_FILE = (
    "alembic/versions/007_skeldir_foundation/202604201200_b22_p3_webhook_ingress_identity_envelope.py"
)
CI_WORKFLOW = ".github/workflows/ci.yml"
P3_TEST_FILE = "backend/tests/test_b22_p3_canonical_identity_envelope.py"
P3_ENFORCER_TEST_FILE = "backend/tests/test_b22_p3_canonical_identity_envelope_enforcer.py"

EXPECTED_PROVIDERS = {"shopify", "woocommerce", "stripe", "paypal"}
EXPECTED_REQUIRED_FIELDS = {
    "tenant_id",
    "provider",
    "provider_native_event_reference",
    "provider_native_commerce_reference",
    "normalized_commerce_reference_kind",
    "normalized_commerce_reference_value",
    "verified_amount_minor",
    "verified_amount_currency",
    "verified_amount_scale",
    "event_timestamp",
    "idempotency_key",
    "verified_commerce_ingress_state",
    "verified_at",
}
EXPECTED_KIND_MAP = {
    "shopify": "shopify_order_id",
    "woocommerce": "woocommerce_order_id",
    "stripe": "stripe_payment_intent_id",
    "paypal": "paypal_transaction_id",
}


def _resolve(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _validate_contract(contract: dict[str, Any], violations: list[str]) -> None:
    providers = {str(item).strip() for item in contract.get("supported_providers", [])}
    if providers != EXPECTED_PROVIDERS:
        violations.append("contract_provider_set_mismatch:" + "|".join(sorted(providers)))

    required_fields = {
        str(item).strip()
        for item in contract.get("canonical_envelope_required_fields", [])
    }
    if required_fields != EXPECTED_REQUIRED_FIELDS:
        violations.append(
            "contract_required_field_set_mismatch:" + "|".join(sorted(required_fields))
        )

    kind_map = contract.get("normalized_reference_kind_by_provider")
    if not isinstance(kind_map, dict):
        violations.append("contract_missing_kind_map")
    else:
        observed = {str(k): str(v) for k, v in kind_map.items()}
        if observed != EXPECTED_KIND_MAP:
            violations.append("contract_kind_map_mismatch")

    if contract.get("required_verified_state_value") != "authenticity_verified":
        violations.append("contract_verified_state_value_mismatch")
    if int(contract.get("required_monetary_scale", -1)) != 2:
        violations.append("contract_required_monetary_scale_mismatch")
    if contract.get("fixed_money_exponent_authority") != "in_process_map":
        violations.append("contract_fixed_money_exponent_authority_mismatch")
    if contract.get("required_ledger_anchor") != "event_id_unique_fk":
        violations.append("contract_required_ledger_anchor_mismatch")


def _validate_model(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "class WebhookIngressIdentity",
        "provider_native_event_reference",
        "provider_native_commerce_reference",
        "normalized_commerce_reference_kind",
        "normalized_commerce_reference_value",
        "verified_amount_minor",
        "verified_amount_currency",
        "verified_amount_scale",
        "verified_commerce_ingress_state",
        "verified_at",
        "uq_webhook_ingress_identities_event_id",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"model_missing_token:{token}")


def _validate_webhooks(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "\"normalized_commerce_reference_kind\": \"shopify_order_id\"",
        "\"normalized_commerce_reference_kind\": \"woocommerce_order_id\"",
        "\"normalized_commerce_reference_kind\": \"stripe_payment_intent_id\"",
        "\"normalized_commerce_reference_kind\": \"paypal_transaction_id\"",
        "\"provider_native_event_reference\"",
        "\"provider_native_commerce_reference\"",
        "\"verified_amount_minor\"",
        "\"verified_amount_currency\"",
        "\"verified_amount_scale\"",
        "\"verified_commerce_ingress_state\": \"authenticity_verified\"",
        "_FIXED_MONEY_EXPONENT_BY_CURRENCY",
        "_canonical_money_scale(",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"webhooks_missing_token:{token}")

    forbidden_tokens = (
        "matched_order_id",
        "discrepancy",
        "tolerance",
        "reconciliation",
    )
    for token in forbidden_tokens:
        if token in text:
            violations.append(f"webhooks_forbidden_b23_token_present:{token}")


def _validate_event_service(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "_extract_webhook_ingress_identity(",
        "_WEBHOOK_INGRESS_IDENTITY_REQUIRED_FIELDS",
        "WebhookIngressIdentity(",
        "verified_commerce_ingress_state",
        "_assert_webhook_identity_substrate_available(",
        "AuthoritativeIngressInvariantError",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"event_service_missing_token:{token}")


def _validate_migration(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "CREATE TABLE public.webhook_ingress_identities",
        "provider_native_event_reference",
        "provider_native_commerce_reference",
        "normalized_commerce_reference_kind",
        "normalized_commerce_reference_value",
        "verified_amount_minor",
        "verified_amount_currency",
        "verified_amount_scale",
        "verified_commerce_ingress_state",
        "verified_at timestamptz NOT NULL",
        "CONSTRAINT uq_webhook_ingress_identities_event_id UNIQUE (event_id)",
        "ENABLE ROW LEVEL SECURITY",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"migration_missing_token:{token}")


def _validate_ci(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "python scripts/ci/enforce_b22_p3_canonical_commerce_identity_envelope.py",
        "pytest backend/tests/test_b22_p3_canonical_identity_envelope_enforcer.py -q",
        "pytest backend/tests/test_b22_p3_canonical_identity_envelope.py -q",
        "SKELDIR_B22_P3_REQUIRE_DB_PROOFS: \"1\"",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"ci_missing_b22_p3_token:{token}")


def _validate_test_surfaces(*, p3_test: Path, p3_enforcer_test: Path, violations: list[str]) -> None:
    p3_text = _read_text(p3_test)
    p3_required_tests = (
        "test_b22_p3_all_supported_providers_persist_canonical_identity_envelope",
        "test_b22_p3_verified_state_is_first_class_queryable",
        "test_b22_p3_negative_control_typed_reference_detector_is_non_vacuous",
        "test_b22_p3_authoritative_webhook_path_fails_when_substrate_unavailable",
    )
    for token in p3_required_tests:
        if token not in p3_text:
            violations.append(f"p3_test_missing_token:{token}")

    enforcer_text = _read_text(p3_enforcer_test)
    enforcer_required_tests = (
        "test_b22_p3_canonical_identity_envelope_enforcer_passes_repo_state",
        "test_b22_p3_canonical_identity_envelope_enforcer_negative_control_forced_regression",
    )
    for token in enforcer_required_tests:
        if token not in enforcer_text:
            violations.append(f"p3_enforcer_test_missing_token:{token}")


def run_enforcement(
    *,
    governance_contract: Path,
    model_file: Path,
    webhooks_file: Path,
    event_service_file: Path,
    migration_file: Path,
    ci_workflow: Path,
    p3_test_file: Path,
    p3_enforcer_test_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_paths = (
        governance_contract,
        model_file,
        webhooks_file,
        event_service_file,
        migration_file,
        ci_workflow,
        p3_test_file,
        p3_enforcer_test_file,
    )
    for path in required_paths:
        if not path.exists():
            violations.append(f"missing_required_file:{path}")
    if violations:
        return 1, violations

    contract = _read_json(governance_contract)
    _validate_contract(contract, violations)
    _validate_model(model_file, violations)
    _validate_webhooks(webhooks_file, violations)
    _validate_event_service(event_service_file, violations)
    _validate_migration(migration_file, violations)
    _validate_ci(ci_workflow, violations)
    _validate_test_surfaces(
        p3_test=p3_test_file,
        p3_enforcer_test=p3_enforcer_test_file,
        violations=violations,
    )
    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.2-P3 canonical identity envelope and explicit verified-state invariants."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--governance-contract", default=GOVERNANCE_CONTRACT)
    parser.add_argument("--model-file", default=MODEL_FILE)
    parser.add_argument("--webhooks-file", default=WEBHOOKS_FILE)
    parser.add_argument("--event-service-file", default=EVENT_SERVICE_FILE)
    parser.add_argument("--migration-file", default=MIGRATION_FILE)
    parser.add_argument("--ci-workflow", default=CI_WORKFLOW)
    parser.add_argument("--p3-test-file", default=P3_TEST_FILE)
    parser.add_argument("--p3-enforcer-test-file", default=P3_ENFORCER_TEST_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b22_p3_canonical_commerce_identity_envelope_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        governance_contract=_resolve(repo_root, args.governance_contract),
        model_file=_resolve(repo_root, args.model_file),
        webhooks_file=_resolve(repo_root, args.webhooks_file),
        event_service_file=_resolve(repo_root, args.event_service_file),
        migration_file=_resolve(repo_root, args.migration_file),
        ci_workflow=_resolve(repo_root, args.ci_workflow),
        p3_test_file=_resolve(repo_root, args.p3_test_file),
        p3_enforcer_test_file=_resolve(repo_root, args.p3_enforcer_test_file),
    )

    lines = ["b22_p3_canonical_commerce_identity_envelope_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append(
            "enforcement=canonical_provider_preserving_identity_envelope_and_verified_commerce_state"
        )
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
