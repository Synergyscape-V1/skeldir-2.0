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


def test_b23_p2_match_engine_kernel_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        extraction_module=EXTRACTION,
        kernel_module=KERNEL,
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
    mutated = tmp_path / "extraction.missing_provider.py"
    mutated.write_text(
        EXTRACTION.read_text(encoding="utf-8").replace(
            '"woocommerce": _woocommerce_dispatch,', "", 1
        ),
        encoding="utf-8",
    )
    result = _run("--extraction-module", str(mutated))
    assert result.returncode != 0
    assert "extractor_registry_missing:woocommerce" in (result.stdout + result.stderr)


def test_negative_control_stripe_net_field_used_as_canonical(tmp_path: Path) -> None:
    mutated = tmp_path / "extraction.stripe_net_canonical.py"
    mutated.write_text(
        EXTRACTION.read_text(encoding="utf-8").replace(
            "amount_minor=int(payload.gross_captured_minor or 0),",
            "amount_minor=int(payload.net_after_fees_minor or 0),",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--extraction-module", str(mutated))
    assert result.returncode != 0
    assert "stripe_net_after_fees_used_as_canonical_amount" in (
        result.stdout + result.stderr
    )


def test_negative_control_unmatched_uses_hardcoded_arrival_literal(
    tmp_path: Path,
) -> None:
    mutated = tmp_path / "kernel.hardcoded_arrival.py"
    mutated.write_text(
        KERNEL.read_text(encoding="utf-8").replace(
            "stale_before = normalized_now - WEBHOOK_ARRIVAL_WINDOW",
            "stale_before = normalized_now - timedelta(minutes=30)",
            1,
        ),
        encoding="utf-8",
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
