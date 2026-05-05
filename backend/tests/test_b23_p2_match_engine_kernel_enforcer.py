from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b23_p2_match_engine_kernel.py"
CONTRACT = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b23_p2_match_engine_kernel.main.json"
)
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
EXTRACTION = (
    REPO_ROOT / "backend" / "app" / "revenue_verification" / "extraction_registry.py"
)
KERNEL = (
    REPO_ROOT / "backend" / "app" / "revenue_verification" / "match_engine_kernel.py"
)
WEBHOOKS = REPO_ROOT / "backend" / "app" / "api" / "webhooks.py"
RUNTIME_TESTS = (
    REPO_ROOT / "backend" / "tests" / "test_b23_p2_match_engine_kernel.py"
)
_SPEC = importlib.util.spec_from_file_location("b23_p2_enforcer_module", ENFORCER)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
run_enforcement = _MODULE.run_enforcement


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENFORCER), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _mutated_file(
    *,
    tmp_path: Path,
    name: str,
    base_file: Path,
    old: str,
    new: str,
) -> Path:
    payload = base_file.read_text(encoding="utf-8")
    assert old in payload, f"mutation marker not found: {old}"
    output = tmp_path / name
    output.write_text(payload.replace(old, new, 1), encoding="utf-8")
    return output


def _assert_enforcer_fail(
    result: subprocess.CompletedProcess[str], expected_token: str
) -> None:
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert expected_token in combined, combined


def test_b23_p2_match_engine_kernel_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        extraction_module=EXTRACTION,
        kernel_module=KERNEL,
        failure_boundary_module=(
            REPO_ROOT
            / "backend"
            / "app"
            / "revenue_verification"
            / "failure_boundary.py"
        ),
        webhook_module=WEBHOOKS,
        runtime_tests_module=RUNTIME_TESTS,
        enforcer_tests_module=Path(__file__).resolve(),
        simulate_regression=False,
    )
    assert status == 0, f"unexpected violations: {violations}"


def test_b23_p2_match_engine_kernel_enforcer_negative_control_forced_regression() -> (
    None
):
    result = _run("--simulate-regression")
    _assert_enforcer_fail(result, "synthetic_regression=forced_failure_path")


def test_negative_control_getattr_zero_default_rejected(tmp_path: Path) -> None:
    mutated = _mutated_file(
        tmp_path=tmp_path,
        name="extraction.getattr_zero.py",
        base_file=EXTRACTION,
        old="amount_minor=int(payload.gross_captured_minor),",
        new='amount_minor=getattr(payload, "gross_captured_minor", 0),',
    )
    result = _run("--extraction-module", str(mutated))
    _assert_enforcer_fail(result, "authority_allowlist_forbidden_call")


def test_negative_control_getattr_decimal_zero_default_rejected(tmp_path: Path) -> None:
    mutated = _mutated_file(
        tmp_path=tmp_path,
        name="extraction.getattr_decimal_zero.py",
        base_file=EXTRACTION,
        old="amount_minor=int(payload.gross_captured_minor),",
        new='amount_minor=getattr(payload, "gross_captured_minor", Decimal("0")),',
    )
    result = _run("--extraction-module", str(mutated))
    _assert_enforcer_fail(result, "authority_allowlist_forbidden_call")


def test_negative_control_getattr_indirect_zero_default_rejected(tmp_path: Path) -> None:
    mutated = _mutated_file(
        tmp_path=tmp_path,
        name="extraction.getattr_indirect_zero.py",
        base_file=EXTRACTION,
        old="return ExtractedRevenue(",
        new="default_amount = 0\n    return ExtractedRevenue(",
    )
    mutated.write_text(
        mutated.read_text(encoding="utf-8").replace(
            "amount_minor=int(payload.gross_captured_minor),",
            'amount_minor=getattr(payload, "gross_captured_minor", default_amount),',
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--extraction-module", str(mutated))
    _assert_enforcer_fail(result, "authority_allowlist_forbidden_call")


def test_negative_control_hasattr_zero_fallback_rejected(tmp_path: Path) -> None:
    mutated = _mutated_file(
        tmp_path=tmp_path,
        name="extraction.hasattr_fallback.py",
        base_file=EXTRACTION,
        old="amount_minor=int(payload.gross_captured_minor),",
        new='amount_minor=payload.gross_captured_minor if hasattr(payload, "gross_captured_minor") else 0,',
    )
    result = _run("--extraction-module", str(mutated))
    _assert_enforcer_fail(result, "authority_allowlist_forbidden_call")


def _mutate_try_except_return(
    *,
    tmp_path: Path,
    name: str,
    except_clause: str,
    fallback_value: str,
) -> Path:
    old_block = """def _extract_from_stripe(payload: StripeRevenueExtractionInput) -> ExtractedRevenue:
    return ExtractedRevenue(
        amount_minor=int(payload.gross_captured_minor),
        currency_code=_normalize_currency(payload.currency_code),
    )
"""
    new_block = f"""def _extract_from_stripe(payload: StripeRevenueExtractionInput) -> ExtractedRevenue:
    try:
        amount_minor = int(payload.gross_captured_minor)
    except {except_clause}:
        amount_minor = {fallback_value}
    return ExtractedRevenue(
        amount_minor=amount_minor,
        currency_code=_normalize_currency(payload.currency_code),
    )
"""
    mutated = _mutated_file(
        tmp_path=tmp_path,
        name=name,
        base_file=EXTRACTION,
        old=old_block,
        new=new_block,
    )
    return mutated


def test_negative_control_attribute_error_zero_fallback_rejected(tmp_path: Path) -> None:
    mutated = _mutate_try_except_return(
        tmp_path=tmp_path,
        name="extraction.attr_error_zero.py",
        except_clause="AttributeError",
        fallback_value="0",
    )
    result = _run("--extraction-module", str(mutated))
    _assert_enforcer_fail(result, "authority_allowlist_exception_fallback_forbidden")


def test_negative_control_type_error_zero_fallback_rejected(tmp_path: Path) -> None:
    mutated = _mutate_try_except_return(
        tmp_path=tmp_path,
        name="extraction.type_error_zero.py",
        except_clause="TypeError",
        fallback_value="0",
    )
    result = _run("--extraction-module", str(mutated))
    _assert_enforcer_fail(result, "authority_allowlist_exception_fallback_forbidden")


def test_negative_control_value_error_zero_fallback_rejected(tmp_path: Path) -> None:
    mutated = _mutate_try_except_return(
        tmp_path=tmp_path,
        name="extraction.value_error_zero.py",
        except_clause="ValueError",
        fallback_value="0",
    )
    result = _run("--extraction-module", str(mutated))
    _assert_enforcer_fail(result, "authority_allowlist_exception_fallback_forbidden")


def test_negative_control_exception_zero_fallback_rejected(tmp_path: Path) -> None:
    mutated = _mutate_try_except_return(
        tmp_path=tmp_path,
        name="extraction.exception_zero.py",
        except_clause="Exception",
        fallback_value="0",
    )
    result = _run("--extraction-module", str(mutated))
    _assert_enforcer_fail(result, "authority_allowlist_exception_fallback_forbidden")


def test_negative_control_exception_decimal_zero_fallback_rejected(tmp_path: Path) -> None:
    mutated = _mutate_try_except_return(
        tmp_path=tmp_path,
        name="extraction.exception_decimal_zero.py",
        except_clause="Exception",
        fallback_value='Decimal("0")',
    )
    result = _run("--extraction-module", str(mutated))
    _assert_enforcer_fail(result, "authority_allowlist_exception_fallback_forbidden")


def test_negative_control_vars_money_access_rejected(tmp_path: Path) -> None:
    mutated = _mutated_file(
        tmp_path=tmp_path,
        name="extraction.vars_access.py",
        base_file=EXTRACTION,
        old="amount_minor=int(payload.gross_captured_minor),",
        new='amount_minor=int(vars(payload)["gross_captured_minor"]),',
    )
    result = _run("--extraction-module", str(mutated))
    _assert_enforcer_fail(result, "authority_allowlist_forbidden_call")


def test_negative_control_dunder_dict_money_access_rejected(tmp_path: Path) -> None:
    mutated = _mutated_file(
        tmp_path=tmp_path,
        name="extraction.dunder_dict_access.py",
        base_file=EXTRACTION,
        old="amount_minor=int(payload.gross_captured_minor),",
        new='amount_minor=int(payload.__dict__["gross_captured_minor"]),',
    )
    result = _run("--extraction-module", str(mutated))
    _assert_enforcer_fail(result, "authority_allowlist_forbidden_dunder_dict_access")


def test_negative_control_model_dump_get_default_zero_rejected(tmp_path: Path) -> None:
    mutated = _mutated_file(
        tmp_path=tmp_path,
        name="extraction.model_dump_get.py",
        base_file=EXTRACTION,
        old="amount_minor=int(payload.gross_captured_minor),",
        new='amount_minor=int(payload.model_dump().get("gross_captured_minor", 0)),',
    )
    result = _run("--extraction-module", str(mutated))
    _assert_enforcer_fail(result, "authority_allowlist_forbidden_model_dump_get")


def test_negative_control_unresolved_helper_call_rejected(tmp_path: Path) -> None:
    mutated = _mutated_file(
        tmp_path=tmp_path,
        name="extraction.unresolved_helper.py",
        base_file=EXTRACTION,
        old="amount_minor=int(payload.gross_captured_minor),",
        new="amount_minor=normalize_money(payload.gross_captured_minor),",
    )
    result = _run("--extraction-module", str(mutated))
    _assert_enforcer_fail(result, "authority_allowlist_unresolved_or_unallowlisted_call")


def test_negative_control_non_allowlisted_ast_construct_rejected(tmp_path: Path) -> None:
    mutated = _mutated_file(
        tmp_path=tmp_path,
        name="extraction.lambda_rejected.py",
        base_file=EXTRACTION,
        old="amount_minor=int(payload.gross_captured_minor),",
        new="amount_minor=(lambda x: int(x))(payload.gross_captured_minor),",
    )
    result = _run("--extraction-module", str(mutated))
    _assert_enforcer_fail(result, "authority_allowlist_non_allowlisted_ast")


def _mutate_runtime_test(
    *,
    tmp_path: Path,
    name: str,
    old: str,
    new: str,
) -> Path:
    payload = RUNTIME_TESTS.read_text(encoding="utf-8")
    assert old in payload, f"runtime mutation marker not found: {old}"
    mutated = tmp_path / name
    mutated.write_text(payload.replace(old, new, 1), encoding="utf-8")
    return mutated


def test_negative_control_db_proof_mocked_required_table_check_rejected(
    tmp_path: Path,
) -> None:
    mutated = _mutate_runtime_test(
        tmp_path=tmp_path,
        name="runtime_tests.mocked_required_tables.py",
        old="def test_b23_p2_match_quality_is_deterministic_high_medium_low() -> None:",
        new=(
            "def test_b23_p2_match_quality_is_deterministic_high_medium_low() -> None:\n"
            "    monkeypatch.setattr('x', 'y', lambda: True)\n"
        ),
    )
    result = _run("--runtime-tests-module", str(mutated))
    _assert_enforcer_fail(
        result, "runtime_db_proof_anti_spoof_forbidden_token_outside_negative_control"
    )


def test_negative_control_db_proof_mock_engine_rejected(tmp_path: Path) -> None:
    mutated = _mutate_runtime_test(
        tmp_path=tmp_path,
        name="runtime_tests.mock_engine.py",
        old="def test_b23_p2_match_quality_is_deterministic_high_medium_low() -> None:",
        new=(
            "def test_b23_p2_match_quality_is_deterministic_high_medium_low() -> None:\n"
            "    fake_engine = object()\n"
        ),
    )
    result = _run("--runtime-tests-module", str(mutated))
    _assert_enforcer_fail(
        result, "runtime_db_proof_anti_spoof_forbidden_token_outside_negative_control"
    )


def test_negative_control_db_proof_sqlite_memory_rejected(tmp_path: Path) -> None:
    mutated = _mutate_runtime_test(
        tmp_path=tmp_path,
        name="runtime_tests.sqlite_memory.py",
        old="def test_b23_p2_match_quality_is_deterministic_high_medium_low() -> None:",
        new=(
            "def test_b23_p2_match_quality_is_deterministic_high_medium_low() -> None:\n"
            "    dsn = 'sqlite:///:memory:'\n"
        ),
    )
    result = _run("--runtime-tests-module", str(mutated))
    _assert_enforcer_fail(
        result, "runtime_db_proof_anti_spoof_forbidden_token_outside_negative_control"
    )


def test_negative_control_db_proof_stubbed_to_regclass_rejected(tmp_path: Path) -> None:
    mutated = _mutate_runtime_test(
        tmp_path=tmp_path,
        name="runtime_tests.stub_to_regclass.py",
        old="def test_b23_p2_match_quality_is_deterministic_high_medium_low() -> None:",
        new=(
            "def test_b23_p2_match_quality_is_deterministic_high_medium_low() -> None:\n"
            "    monkeypatch.setattr(f\"{__name__}._table_regclass\", lambda _name: 'public.b23_match_verdicts')\n"
        ),
    )
    result = _run("--runtime-tests-module", str(mutated))
    _assert_enforcer_fail(
        result, "runtime_db_proof_anti_spoof_forbidden_token_outside_negative_control"
    )


def test_negative_control_db_proof_patched_migration_check_rejected(
    tmp_path: Path,
) -> None:
    mutated = _mutate_runtime_test(
        tmp_path=tmp_path,
        name="runtime_tests.patch_migration.py",
        old="def test_b23_p2_match_quality_is_deterministic_high_medium_low() -> None:",
        new=(
            "def test_b23_p2_match_quality_is_deterministic_high_medium_low() -> None:\n"
            "    marker = 'mock.patch'\n"
        ),
    )
    result = _run("--runtime-tests-module", str(mutated))
    _assert_enforcer_fail(
        result, "runtime_db_proof_anti_spoof_forbidden_token_outside_negative_control"
    )


def test_negative_control_db_proof_monkeypatched_success_path_rejected(
    tmp_path: Path,
) -> None:
    mutated = _mutate_runtime_test(
        tmp_path=tmp_path,
        name="runtime_tests.monkeypatch_success.py",
        old="def test_b23_p2_match_quality_is_deterministic_high_medium_low() -> None:",
        new=(
            "def test_b23_p2_match_quality_is_deterministic_high_medium_low() -> None:\n"
            "    monkeypatch.setattr('x', 'y', lambda: 1)\n"
        ),
    )
    result = _run("--runtime-tests-module", str(mutated))
    _assert_enforcer_fail(
        result, "runtime_db_proof_anti_spoof_forbidden_token_outside_negative_control"
    )
