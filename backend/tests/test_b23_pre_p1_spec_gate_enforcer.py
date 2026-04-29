from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b23_pre_p1_spec_gate.py"
CONTRACT_FILE = REPO_ROOT / "contracts-internal" / "governance" / "b23_pre_p1_spec_gate.main.json"
SPEC_FILE = REPO_ROOT / "docs" / "forensics" / "B2.3-Pre-P1 Specification Gates A-B.md"
CI_FILE = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENFORCER), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run_with_mutated_contract(tmp_path: Path, payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    mutated = tmp_path / "contract.regression.json"
    _write_json(mutated, payload)
    return _run("--contract-file", str(mutated))


def test_b23_pre_p1_spec_gate_enforcer_passes_repo_baseline() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b23_pre_p1_spec_gate_enforcer_negative_control_forced_regression() -> None:
    result = _run("--simulate-regression")
    assert result.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (result.stdout + result.stderr)


def test_negative_control_missing_canonical_envelope_authority_field(tmp_path: Path) -> None:
    payload = _load_json(CONTRACT_FILE)
    del payload["revenue_extraction_standard"]["providers"]["stripe"]["b23_authority_amount_field"]
    result = _run_with_mutated_contract(tmp_path, payload)
    assert result.returncode != 0
    assert "revenue_provider_stripe_missing_field:b23_authority_amount_field" in (
        result.stdout + result.stderr
    )


def test_negative_control_raw_provider_field_reclassified_as_runtime_authority(tmp_path: Path) -> None:
    payload = _load_json(CONTRACT_FILE)
    stripe = payload["revenue_extraction_standard"]["providers"]["stripe"]
    stripe["b23_authority_amount_field"] = stripe["provider_origin_revenue_field"]
    stripe["b23_authority_currency_field"] = stripe["provider_origin_currency_field"]
    result = _run_with_mutated_contract(tmp_path, payload)
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "revenue_provider_origin_runtime_boundary_broken:stripe:amount" in out
    assert "revenue_provider_origin_runtime_boundary_broken:stripe:currency" in out


def test_negative_control_raw_payload_forbidden_flag_removed(tmp_path: Path) -> None:
    payload = _load_json(CONTRACT_FILE)
    del payload["revenue_extraction_standard"]["raw_webhook_payload_forbidden_as_b23_authority"]
    result = _run_with_mutated_contract(tmp_path, payload)
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert (
        "schema:revenue_extraction_standard.missing_key:raw_webhook_payload_forbidden_as_b23_authority"
        in out
    )


def test_negative_control_remove_provider_amount_parsing_scope(tmp_path: Path) -> None:
    payload = _load_json(CONTRACT_FILE)
    scopes = payload["revenue_extraction_standard"]["canonical_storage"]["binary_float_forbidden_scopes"]
    payload["revenue_extraction_standard"]["canonical_storage"]["binary_float_forbidden_scopes"] = [
        scope for scope in scopes if scope != "provider_amount_parsing"
    ]
    result = _run_with_mutated_contract(tmp_path, payload)
    assert result.returncode != 0
    assert "revenue_binary_float_scope_missing:provider_amount_parsing" in (result.stdout + result.stderr)


def test_negative_control_remove_decimal_to_minor_scope(tmp_path: Path) -> None:
    payload = _load_json(CONTRACT_FILE)
    scopes = payload["revenue_extraction_standard"]["canonical_storage"]["binary_float_forbidden_scopes"]
    payload["revenue_extraction_standard"]["canonical_storage"]["binary_float_forbidden_scopes"] = [
        scope for scope in scopes if scope != "decimal_string_to_minor_unit_conversion"
    ]
    result = _run_with_mutated_contract(tmp_path, payload)
    assert result.returncode != 0
    assert "revenue_binary_float_scope_missing:decimal_string_to_minor_unit_conversion" in (
        result.stdout + result.stderr
    )


def test_negative_control_remove_exact_decimal_rule(tmp_path: Path) -> None:
    payload = _load_json(CONTRACT_FILE)
    del payload["revenue_extraction_standard"]["exact_decimal_parsing_policy"]["require_exact_decimal_arithmetic"]
    result = _run_with_mutated_contract(tmp_path, payload)
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert (
        "schema:revenue_extraction_standard.exact_decimal_parsing_policy.missing_key:require_exact_decimal_arithmetic"
        in out
    )


def test_negative_control_remove_test_fixture_float_scope(tmp_path: Path) -> None:
    payload = _load_json(CONTRACT_FILE)
    scopes = payload["revenue_extraction_standard"]["canonical_storage"]["binary_float_forbidden_scopes"]
    payload["revenue_extraction_standard"]["canonical_storage"]["binary_float_forbidden_scopes"] = [
        scope
        for scope in scopes
        if scope != "test_fixtures_except_explicit_rejection_or_normalization_tests"
    ]
    result = _run_with_mutated_contract(tmp_path, payload)
    assert result.returncode != 0
    assert "revenue_binary_float_scope_missing:test_fixtures_except_explicit_rejection_or_normalization_tests" in (
        result.stdout + result.stderr
    )


def test_negative_control_remove_reversal_event(tmp_path: Path) -> None:
    payload = _load_json(CONTRACT_FILE)
    payload["refund_chargeback_concurrency_law"]["distinct_adjustment_events"] = [
        event
        for event in payload["refund_chargeback_concurrency_law"]["distinct_adjustment_events"]
        if event != "reversal"
    ]
    result = _run_with_mutated_contract(tmp_path, payload)
    assert result.returncode != 0
    assert "concurrency_adjustment_event_missing:reversal" in (result.stdout + result.stderr)


def test_negative_control_wrong_provider_enum_value(tmp_path: Path) -> None:
    payload = _load_json(CONTRACT_FILE)
    providers = payload["revenue_extraction_standard"]["providers"]
    providers["stripe_bad"] = providers.pop("stripe")
    result = _run_with_mutated_contract(tmp_path, payload)
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "schema:revenue_extraction_standard.providers.missing_key:stripe" in out
    assert "schema:revenue_extraction_standard.providers.unexpected_key:stripe_bad" in out


def test_negative_control_wrong_money_storage_enum(tmp_path: Path) -> None:
    payload = _load_json(CONTRACT_FILE)
    payload["revenue_extraction_standard"]["canonical_storage"]["amount"] = "decimal_major_units"
    result = _run_with_mutated_contract(tmp_path, payload)
    assert result.returncode != 0
    assert (
        "schema:revenue_extraction_standard.canonical_storage.amount.invalid_enum:decimal_major_units"
        in (result.stdout + result.stderr)
    )


def test_negative_control_wrong_timing_unit_enum(tmp_path: Path) -> None:
    payload = _load_json(CONTRACT_FILE)
    payload["timing_constants"]["PROVISIONAL_MATCH_WINDOW"]["unit"] = "weeks"
    result = _run_with_mutated_contract(tmp_path, payload)
    assert result.returncode != 0
    assert "schema:timing_constants.PROVISIONAL_MATCH_WINDOW.unit.invalid_enum:weeks" in (
        result.stdout + result.stderr
    )


def test_negative_control_wrong_boolean_type(tmp_path: Path) -> None:
    payload = _load_json(CONTRACT_FILE)
    payload["revenue_extraction_standard"]["raw_webhook_payload_forbidden_as_b23_authority"] = "true"
    result = _run_with_mutated_contract(tmp_path, payload)
    assert result.returncode != 0
    assert "schema:revenue_extraction_standard.raw_webhook_payload_forbidden_as_b23_authority.type_not_bool" in (
        result.stdout + result.stderr
    )


def test_negative_control_unknown_extra_field_rejected(tmp_path: Path) -> None:
    payload = _load_json(CONTRACT_FILE)
    payload["unknown_contract_field"] = "should_fail"
    result = _run_with_mutated_contract(tmp_path, payload)
    assert result.returncode != 0
    assert "schema:contract.unexpected_key:unknown_contract_field" in (result.stdout + result.stderr)


def test_negative_control_malformed_nested_provider_object_shape(tmp_path: Path) -> None:
    payload = _load_json(CONTRACT_FILE)
    payload["revenue_extraction_standard"]["providers"]["stripe"] = {
        "provider_origin_revenue_field": ["data.object.amount"],
        "provider_origin_currency_field": "data.object.currency",
        "source_amount_unit": "minor_units_integer",
        "canonical_amount_basis": "captured_payment_intent_gross",
        "b23_authority_amount_field": "verified_amount_minor",
        "b23_authority_currency_field": "verified_currency_code",
        "canonical_storage_unit": "minor_units_integer",
        "currency_exponent_source": "iso_4217_exponent_by_currency",
        "rounding_mode": "ROUND_HALF_UP",
        "tax_inclusion": "unknown",
        "shipping_inclusion": "unknown",
        "discount_inclusion": "unknown",
        "processor_fee_inclusion": "no",
        "refund_chargeback_adjustment_posture": "append_only_adjustment_events",
        "multi_currency_posture": "same_currency_only_no_cross_currency_match"
    }
    result = _run_with_mutated_contract(tmp_path, payload)
    assert result.returncode != 0
    assert "schema:revenue_extraction_standard.providers.stripe.provider_origin_revenue_field.type_or_empty" in (
        result.stdout + result.stderr
    )


def test_negative_control_missing_required_spec_token(tmp_path: Path) -> None:
    mutated_spec = tmp_path / "spec.regression.md"
    mutated_spec.write_text(
        SPEC_FILE.read_text(encoding="utf-8").replace(
            "provider amount parsing",
            "provider parsing",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--spec-file", str(mutated_spec))
    assert result.returncode != 0
    assert "spec_missing_token:provider amount parsing" in (result.stdout + result.stderr)


def test_negative_control_ci_wiring_removed(tmp_path: Path) -> None:
    mutated_ci = tmp_path / "ci.regression.yml"
    mutated_ci.write_text(
        CI_FILE.read_text(encoding="utf-8").replace(
            "python scripts/ci/enforce_b23_pre_p1_spec_gate.py",
            "python scripts/ci/enforce_b23_pre_p1_spec_gate_regressed.py",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--ci-file", str(mutated_ci))
    assert result.returncode != 0
    assert "ci_missing_token:python scripts/ci/enforce_b23_pre_p1_spec_gate.py" in (
        result.stdout + result.stderr
    )
