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


def _write_mutation(
    *, base_file: Path, tmp_path: Path, output_name: str, old: str, new: str
) -> Path:
    mutated = tmp_path / output_name
    mutated.write_text(
        base_file.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8"
    )
    return mutated


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
        simulate_regression=False,
    )
    assert status == 0, f"unexpected violations: {violations}"


def test_b23_p2_match_engine_kernel_enforcer_negative_control_forced_regression() -> (
    None
):
    result = _run("--simulate-regression")
    assert result.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (result.stdout + result.stderr)


def test_negative_control_missing_provider_registration(tmp_path: Path) -> None:
    mutated = _write_mutation(
        base_file=EXTRACTION,
        tmp_path=tmp_path,
        output_name="extraction.missing_provider.py",
        old='"woocommerce": _woocommerce_dispatch,',
        new="",
    )
    result = _run("--extraction-module", str(mutated))
    assert result.returncode != 0
    assert "extractor_registry_missing:woocommerce" in (result.stdout + result.stderr)


def test_negative_control_stripe_net_field_used_as_canonical(tmp_path: Path) -> None:
    mutated = _write_mutation(
        base_file=EXTRACTION,
        tmp_path=tmp_path,
        output_name="extraction.stripe_net_canonical.py",
        old="amount_minor=int(payload.gross_captured_minor),",
        new="amount_minor=int(payload.net_after_fees_minor),",
    )
    result = _run("--extraction-module", str(mutated))
    assert result.returncode != 0
    assert "stripe_net_after_fees_used_as_canonical_amount" in (
        result.stdout + result.stderr
    )


def test_negative_control_semantic_zero_fallback_or_literal(tmp_path: Path) -> None:
    mutated = _write_mutation(
        base_file=EXTRACTION,
        tmp_path=tmp_path,
        output_name="extraction.zero_or_literal.py",
        old="amount_minor=int(payload.gross_captured_minor),",
        new="amount_minor=int(payload.gross_captured_minor or 0),",
    )
    result = _run("--extraction-module", str(mutated))
    assert result.returncode != 0
    assert "semantic_zero_fallback_bool_or" in (result.stdout + result.stderr)


def test_negative_control_semantic_zero_fallback_ternary(tmp_path: Path) -> None:
    mutated = _write_mutation(
        base_file=EXTRACTION,
        tmp_path=tmp_path,
        output_name="extraction.zero_ternary.py",
        old="amount_minor=int(payload.gross_captured_minor),",
        new="amount_minor=int(payload.gross_captured_minor if payload.gross_captured_minor else 0),",
    )
    result = _run("--extraction-module", str(mutated))
    assert result.returncode != 0
    assert "semantic_zero_fallback_ternary" in (result.stdout + result.stderr)


def test_negative_control_semantic_zero_fallback_indirect_default(tmp_path: Path) -> None:
    mutated = _write_mutation(
        base_file=EXTRACTION,
        tmp_path=tmp_path,
        output_name="extraction.zero_indirect_default.py",
        old="return ExtractedRevenue(",
        new="default_amount = 0\n    return ExtractedRevenue(",
    )
    mutated.write_text(
        mutated.read_text(encoding="utf-8").replace(
            "amount_minor=int(payload.gross_captured_minor),",
            "amount_minor=int(payload.gross_captured_minor or default_amount),",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--extraction-module", str(mutated))
    assert result.returncode != 0
    assert "semantic_zero_fallback_bool_or" in (result.stdout + result.stderr)


def test_negative_control_semantic_zero_fallback_dict_get_default(tmp_path: Path) -> None:
    injected = (
        EXTRACTION.read_text(encoding="utf-8")
        + "\n\ndef _synthetic_bad_default(payload: dict[str, int]) -> int:\n"
        + "    return int(payload.get(\"amount\", 0))\n"
    )
    mutated = tmp_path / "extraction.get_default_zero.py"
    mutated.write_text(injected, encoding="utf-8")
    result = _run("--extraction-module", str(mutated))
    assert result.returncode != 0
    assert "semantic_zero_fallback_dict_get_default" in (
        result.stdout + result.stderr
    )


def test_negative_control_semantic_zero_fallback_decimal_zero(tmp_path: Path) -> None:
    mutated = _write_mutation(
        base_file=EXTRACTION,
        tmp_path=tmp_path,
        output_name="extraction.decimal_zero.py",
        old="amount_minor=int(payload.gross_captured_minor),",
        new='amount_minor=int(payload.gross_captured_minor or Decimal("0")),',
    )
    result = _run("--extraction-module", str(mutated))
    assert result.returncode != 0
    assert "semantic_zero_fallback_bool_or" in (result.stdout + result.stderr)


def test_negative_control_semantic_zero_fallback_helper(tmp_path: Path) -> None:
    injected = (
        EXTRACTION.read_text(encoding="utf-8")
        + "\n\ndef coerce_missing_money_to_zero(value: int | None) -> int:\n"
        + "    return int(value or 0)\n"
        + "\n\ndef _synthetic_bad_helper(payload: StripeRevenueExtractionInput) -> int:\n"
        + "    return coerce_missing_money_to_zero(payload.gross_captured_minor)\n"
    )
    mutated = tmp_path / "extraction.helper_zero.py"
    mutated.write_text(injected, encoding="utf-8")
    result = _run("--extraction-module", str(mutated))
    assert result.returncode != 0
    assert "semantic_zero_fallback_helper" in (result.stdout + result.stderr)


def test_negative_control_unmatched_uses_hardcoded_arrival_literal(
    tmp_path: Path,
) -> None:
    mutated = _write_mutation(
        base_file=KERNEL,
        tmp_path=tmp_path,
        output_name="kernel.hardcoded_arrival.py",
        old="stale_before = normalized_now - WEBHOOK_ARRIVAL_WINDOW",
        new="stale_before = normalized_now - timedelta(minutes=30)",
    )
    result = _run("--kernel-module", str(mutated))
    assert result.returncode != 0
    assert "kernel_hardcoded_arrival_window_literal_detected" in (
        result.stdout + result.stderr
    )


def test_negative_control_revenue_ledger_authority_write(tmp_path: Path) -> None:
    mutated = tmp_path / "kernel.revenue_ledger.py"
    mutated.write_text(
        KERNEL.read_text(encoding="utf-8") + "\n# forbidden marker: revenue_ledger\n",
        encoding="utf-8",
    )
    result = _run("--kernel-module", str(mutated))
    assert result.returncode != 0
    assert "kernel_forbidden_token_present:revenue_ledger" in (
        result.stdout + result.stderr
    )


def test_negative_control_concurrency_downgraded_to_python_lock(tmp_path: Path) -> None:
    mutated = tmp_path / "kernel.python_lock.py"
    mutated.write_text(
        KERNEL.read_text(encoding="utf-8") + "\nlock = asyncio.Lock()\n",
        encoding="utf-8",
    )
    result = _run("--kernel-module", str(mutated))
    assert result.returncode != 0
    assert "kernel_forbidden_token_present:asyncio.Lock(" in (
        result.stdout + result.stderr
    )


def test_negative_control_llm_reachable_from_kernel_path(tmp_path: Path) -> None:
    mutated = tmp_path / "kernel.llm_import.py"
    mutated.write_text(
        KERNEL.read_text(encoding="utf-8") + "\nimport openai\n",
        encoding="utf-8",
    )
    result = _run("--kernel-module", str(mutated))
    assert result.returncode != 0
    assert "kernel_forbidden_token_present:import openai" in (
        result.stdout + result.stderr
    )


def test_negative_control_unresolved_path_loses_exception_boundary(tmp_path: Path) -> None:
    mutated = _write_mutation(
        base_file=KERNEL,
        tmp_path=tmp_path,
        output_name="kernel.no_unresolved_boundary.py",
        old="B23FailureBoundaryClass.VALID_POST_CAPTURE_UNRESOLVED_ORDER_IDENTITY",
        new="B23FailureBoundaryClass.AUTHENTICATED_MALFORMED_CANONICAL_PAYLOAD",
    )
    result = _run("--kernel-module", str(mutated))
    assert result.returncode != 0
    assert "kernel_missing_token:VALID_POST_CAPTURE_UNRESOLVED_ORDER_IDENTITY" in (
        result.stdout + result.stderr
    )


def test_negative_control_authenticated_malformed_payload_boundary_removed(
    tmp_path: Path,
) -> None:
    mutated = _write_mutation(
        base_file=WEBHOOKS,
        tmp_path=tmp_path,
        output_name="webhooks.no_boundary.py",
        old="B23FailureBoundaryClass.AUTHENTICATED_MALFORMED_CANONICAL_PAYLOAD",
        new="B23FailureBoundaryClass.UNAUTHENTICATED_MALFORMED_WEBHOOK",
    )
    result = _run("--webhook-module", str(mutated))
    assert result.returncode != 0
    assert "webhook_boundary_missing_token" in (result.stdout + result.stderr)


def test_negative_control_ci_runtime_db_proof_env_removed(tmp_path: Path) -> None:
    mutated = tmp_path / "ci.no_b23_env.yml"
    mutated.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            'SKELDIR_B23_P2_REQUIRE_DB_PROOFS: "1"\n', ""
        ),
        encoding="utf-8",
    )
    result = _run("--workflow-file", str(mutated))
    assert result.returncode != 0
    assert "ci_missing_runtime_db_proof_token:SKELDIR_B23_P2_REQUIRE_DB_PROOFS: \"1\"" in (
        result.stdout + result.stderr
    )
