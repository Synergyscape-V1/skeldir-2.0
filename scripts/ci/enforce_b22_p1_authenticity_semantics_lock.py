#!/usr/bin/env python3
"""B2.2-P1 authenticity semantics + tenant-secret authority lock enforcer."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_CONTRACT = "contracts-internal/governance/b22_p1_authenticity_semantics.main.json"
WEBHOOKS_FILE = "backend/app/api/webhooks.py"
SIGNATURES_FILE = "backend/app/webhooks/signatures.py"
PAYPAL_CONTRACT_FILE = "api-contracts/openapi/v1/webhooks/paypal.yaml"
CI_WORKFLOW = ".github/workflows/ci.yml"
B12_P8_TEST = "backend/tests/test_b12_p8_error_contract_normalization.py"
B22_P1_TEST = "backend/tests/test_b22_p1_authenticity_semantics.py"
B045_TEST = "backend/tests/test_b045_webhooks.py"

EXPECTED_PROVIDERS = {"shopify", "stripe", "paypal", "woocommerce"}
EXPECTED_PAYPAL_REQUIRED_HEADERS = (
    "PayPal-Transmission-Id",
    "PayPal-Transmission-Time",
    "PayPal-Transmission-Sig",
    "PayPal-Auth-Algo",
    "PayPal-Cert-Url",
)
EXPECTED_PAYPAL_OPTIONAL_HEADERS = ("PayPal-Webhook-Id",)


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


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(_read_text(path)) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML payload must be an object: {path}")
    return payload


def _extract_function_source(source: str, function_name: str) -> str:
    pattern = re.compile(
        rf"def {re.escape(function_name)}\s*\(.*?(?=\n\ndef |\Z)",
        re.DOTALL,
    )
    match = pattern.search(source)
    if not match:
        return ""
    return match.group(0)


def _validate_contract(contract: dict[str, Any], violations: list[str]) -> None:
    providers = contract.get("providers")
    if not isinstance(providers, dict):
        violations.append("contract_missing_providers_mapping")
        return
    provider_keys = set(providers.keys())
    if provider_keys != EXPECTED_PROVIDERS:
        violations.append(
            "contract_provider_set_mismatch:" + "|".join(sorted(provider_keys))
        )
        return

    paypal = providers.get("paypal") or {}
    if paypal.get("semantic_class") != "rsa_sha256_canonical_message_crc32":
        violations.append("contract_paypal_semantic_class_mismatch")
    if paypal.get("timestamp_tolerance_seconds") != 300:
        violations.append(
            f"contract_paypal_tolerance_mismatch:{paypal.get('timestamp_tolerance_seconds')}"
        )

    required_headers = paypal.get("required_headers")
    if not isinstance(required_headers, list):
        violations.append("contract_paypal_required_headers_missing")
    else:
        observed = {str(item).strip() for item in required_headers}
        expected = set(EXPECTED_PAYPAL_REQUIRED_HEADERS)
        if observed != expected:
            violations.append(
                "contract_paypal_required_headers_mismatch:" + "|".join(sorted(observed))
            )

    optional_headers = paypal.get("optional_headers")
    if not isinstance(optional_headers, list):
        violations.append("contract_paypal_optional_headers_missing")
    else:
        observed_optional = {str(item).strip() for item in optional_headers}
        expected_optional = set(EXPECTED_PAYPAL_OPTIONAL_HEADERS)
        if observed_optional != expected_optional:
            violations.append(
                "contract_paypal_optional_headers_mismatch:"
                + "|".join(sorted(observed_optional))
            )

    auth_algos = paypal.get("auth_algo_allowlist")
    if auth_algos != ["SHA256withRSA"]:
        violations.append("contract_paypal_auth_algo_allowlist_mismatch")

    cert_fetch = paypal.get("cert_fetch")
    if not isinstance(cert_fetch, dict):
        violations.append("contract_paypal_cert_fetch_policy_missing")
    else:
        expected_flags = {
            "https_only": True,
            "allow_redirects": False,
            "dns_public_ip_only": True,
            "trust_env_proxy": False,
            "cache_required": True,
        }
        for key, expected in expected_flags.items():
            if cert_fetch.get(key) != expected:
                violations.append(f"contract_paypal_cert_fetch_flag_mismatch:{key}")
        if cert_fetch.get("allowed_ports") != [443]:
            violations.append("contract_paypal_cert_fetch_allowed_ports_mismatch")
        if cert_fetch.get("max_bytes") != 131072:
            violations.append("contract_paypal_cert_fetch_max_bytes_mismatch")
        if cert_fetch.get("timeout_seconds") != 0.35:
            violations.append("contract_paypal_cert_fetch_timeout_mismatch")

    tenant_authority = paypal.get("tenant_authority")
    if not isinstance(tenant_authority, dict):
        violations.append("contract_paypal_tenant_authority_missing")
    elif tenant_authority.get("webhook_id_source") != "server_resolved_paypal_webhook_secret":
        violations.append("contract_paypal_tenant_authority_source_mismatch")

    latency_design = contract.get("latency_design")
    if not isinstance(latency_design, dict):
        violations.append("contract_latency_design_missing")
    else:
        if latency_design.get("hot_path_remote_dependency_mode") != "bounded_cache_miss_only":
            violations.append("contract_latency_mode_mismatch")
        if latency_design.get("verification_class") != "local_asymmetric_with_bounded_cert_cache":
            violations.append("contract_latency_verification_class_mismatch")


def _validate_paypal_contract(path: Path, violations: list[str]) -> None:
    payload = _read_yaml(path)
    operation = (
        (payload.get("paths") or {})
        .get("/api/webhooks/paypal/sale_completed", {})
        .get("post", {})
    )
    parameters = operation.get("parameters")
    if not isinstance(parameters, list):
        violations.append("paypal_openapi_missing_parameters")
        return

    parameter_map: dict[str, Any] = {}
    for param in parameters:
        if not isinstance(param, dict):
            continue
        name = str(param.get("name", "")).strip()
        if name:
            parameter_map[name.upper()] = param

    for header in EXPECTED_PAYPAL_REQUIRED_HEADERS:
        key = header.upper()
        if key not in parameter_map:
            violations.append(f"paypal_openapi_missing_header:{header}")
            continue
        if parameter_map[key].get("required") is not True:
            violations.append(f"paypal_openapi_header_not_required:{header}")

    optional_header = "PAYPAL-WEBHOOK-ID"
    optional_param = parameter_map.get(optional_header)
    if optional_param is None:
        violations.append("paypal_openapi_missing_optional_webhook_id_header")
    elif optional_param.get("required") is not False:
        violations.append("paypal_openapi_webhook_id_header_must_be_optional")


def _validate_signatures_file(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    module = ast.parse(text)

    paypal_fn: ast.FunctionDef | None = None
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == "verify_paypal_signature":
            paypal_fn = node
            break
    if paypal_fn is None:
        violations.append("signatures_missing_verify_paypal_signature")
        return

    call_names: set[str] = set()
    string_constants: set[str] = set()
    name_constants: set[str] = set()
    for node in ast.walk(paypal_fn):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                call_names.add(node.func.attr)
            elif isinstance(node.func, ast.Name):
                call_names.add(node.func.id)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            string_constants.add(node.value)
        if isinstance(node, ast.Name):
            name_constants.add(node.id)

    required_calls = {"b64decode", "crc32", "verify"}
    missing_calls = sorted(required_calls - call_names)
    if missing_calls:
        violations.append("signatures_paypal_missing_calls:" + "|".join(missing_calls))

    required_literals = {
        "transmission_id",
        "transmission_time",
        "transmission_sig",
        "auth_algo",
        "cert_url",
    }
    missing_literals = sorted(required_literals - string_constants)
    if missing_literals:
        violations.append(
            "signatures_paypal_missing_required_literals:" + "|".join(missing_literals)
        )

    required_names = {
        "PAYPAL_AUTH_TOLERANCE_SECONDS",
        "PAYPAL_ALLOWED_AUTH_ALGOS",
    }
    missing_names = sorted(required_names - name_constants)
    if missing_names:
        violations.append(
            "signatures_paypal_missing_required_names:" + "|".join(missing_names)
        )

    paypal_source = _extract_function_source(text, "verify_paypal_signature")
    disallowed_tokens = (
        "hmac.new(",
        "HMAC-SHA256(secret",
        "hashlib.sha256(raw_body).hexdigest()",
    )
    for token in disallowed_tokens:
        if token in paypal_source:
            violations.append(f"signatures_paypal_contains_disallowed_token:{token}")

    required_tokens = (
        "padding.PKCS1v15()",
        "hashes.SHA256()",
        "_resolve_paypal_public_key(",
        "_validate_paypal_cert_url(",
    )
    for token in required_tokens:
        if token not in paypal_source:
            violations.append(f"signatures_paypal_missing_required_token:{token}")


def _validate_webhooks_file(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        'alias="PayPal-Transmission-Sig"',
        'alias="PayPal-Transmission-Id"',
        'alias="PayPal-Transmission-Time"',
        'alias="PayPal-Auth-Algo"',
        'alias="PayPal-Cert-Url"',
        "_paypal_auth_envelope_header(",
        "provider=\"paypal\"",
        "paypal_webhook_secret",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"webhooks_missing_paypal_semantics_token:{token}")


def _validate_ci(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "python scripts/ci/enforce_b22_p1_authenticity_semantics_lock.py",
        "pytest backend/tests/test_b22_p1_authenticity_semantics_lock_enforcer.py -q",
        "pytest backend/tests/test_b22_p1_authenticity_semantics.py -q",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"ci_missing_b22_p1_token:{token}")


def _validate_test_surfaces(
    *,
    b12_p8_test: Path,
    b22_p1_test: Path,
    b045_test: Path,
    violations: list[str],
) -> None:
    b12_text = _read_text(b12_p8_test)
    b22_text = _read_text(b22_p1_test)
    b045_text = _read_text(b045_test)

    b12_tokens = (
        "test_eg83_paypal_hmac_failure_variants_share_non_leaky_problem_contract",
        "test_eg8cf_paypal_constant_work_unknown_key_and_known_bad_signature_both_invoke_compute",
        "test_eg8route_stripe_alias_and_canonical_auth_failures_are_equivalent",
    )
    for token in b12_tokens:
        if token not in b12_text:
            violations.append(f"b12_p8_missing_token:{token}")

    b045_tokens = (
        "test_paypal_missing_required_auth_header_returns_401",
        "test_paypal_stale_transmission_time_returns_401",
        "test_paypal_wrong_webhook_id_returns_401",
    )
    for token in b045_tokens:
        if token not in b045_text:
            violations.append(f"b045_missing_token:{token}")

    b22_tokens = (
        "test_b22_p1_paypal_valid_envelope_accepts",
        "test_b22_p1_paypal_rejects_legacy_raw_body_signature_path",
        "test_b22_p1_paypal_rejects_webhook_authority_mismatch",
        "test_b22_p1_paypal_verifier_latency_is_bounded_for_hot_path",
        "test_b22_p1_cert_fetch_timeout_is_fail_closed_and_bounded",
    )
    for token in b22_tokens:
        if token not in b22_text:
            violations.append(f"b22_p1_test_missing_token:{token}")


def run_enforcement(
    *,
    governance_contract: Path,
    webhooks_file: Path,
    signatures_file: Path,
    paypal_contract_file: Path,
    ci_workflow: Path,
    b12_p8_test: Path,
    b22_p1_test: Path,
    b045_test: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_paths = (
        governance_contract,
        webhooks_file,
        signatures_file,
        paypal_contract_file,
        ci_workflow,
        b12_p8_test,
        b22_p1_test,
        b045_test,
    )
    for path in required_paths:
        if not path.exists():
            violations.append(f"missing_required_file:{path}")
    if violations:
        return 1, violations

    contract = _read_json(governance_contract)
    _validate_contract(contract, violations)
    _validate_paypal_contract(paypal_contract_file, violations)
    _validate_signatures_file(signatures_file, violations)
    _validate_webhooks_file(webhooks_file, violations)
    _validate_ci(ci_workflow, violations)
    _validate_test_surfaces(
        b12_p8_test=b12_p8_test,
        b22_p1_test=b22_p1_test,
        b045_test=b045_test,
        violations=violations,
    )

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.2-P1 authenticity semantics closure under tenant secret authority."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--governance-contract", default=GOVERNANCE_CONTRACT)
    parser.add_argument("--webhooks-file", default=WEBHOOKS_FILE)
    parser.add_argument("--signatures-file", default=SIGNATURES_FILE)
    parser.add_argument("--paypal-contract-file", default=PAYPAL_CONTRACT_FILE)
    parser.add_argument("--ci-workflow", default=CI_WORKFLOW)
    parser.add_argument("--b12-p8-test", default=B12_P8_TEST)
    parser.add_argument("--b22-p1-test", default=B22_P1_TEST)
    parser.add_argument("--b045-test", default=B045_TEST)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b22_p1_authenticity_semantics_lock_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        governance_contract=_resolve(repo_root, args.governance_contract),
        webhooks_file=_resolve(repo_root, args.webhooks_file),
        signatures_file=_resolve(repo_root, args.signatures_file),
        paypal_contract_file=_resolve(repo_root, args.paypal_contract_file),
        ci_workflow=_resolve(repo_root, args.ci_workflow),
        b12_p8_test=_resolve(repo_root, args.b12_p8_test),
        b22_p1_test=_resolve(repo_root, args.b22_p1_test),
        b045_test=_resolve(repo_root, args.b045_test),
    )

    lines = ["b22_p1_authenticity_semantics_lock_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append(
            "enforcement=provider_correct_paypal_authenticity_tenant_secret_authority_ssrf_boundedness_lock"
        )
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
