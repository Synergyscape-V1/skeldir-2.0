from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = (
    REPO_ROOT / "scripts" / "ci" / "enforce_b22_p5_performance_negative_control_lock.py"
)
_SPEC = importlib.util.spec_from_file_location("b22_p5_enforcer_module", ENFORCER)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
run_enforcement = _MODULE.run_enforcement

GOVERNANCE_CONTRACT = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b22_p5_performance_negative_control_lock.main.json"
)
WEBHOOKS_FILE = REPO_ROOT / "backend" / "app" / "api" / "webhooks.py"
BENCHMARK_FILE = (
    REPO_ROOT / "scripts" / "benchmarks" / "b22_p5_webhook_ingress_benchmark.py"
)
BENCHMARK_ADJUDICATOR = (
    REPO_ROOT / "scripts" / "ci" / "enforce_b22_p5_webhook_benchmark_adjudication.py"
)
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
RUNTIME_TEST = (
    REPO_ROOT / "backend" / "tests" / "test_b22_p5_performance_negative_controls.py"
)
ENFORCER_TEST = (
    REPO_ROOT
    / "backend"
    / "tests"
    / "test_b22_p5_performance_negative_control_lock_enforcer.py"
)
ADJUDICATOR_TEST = (
    REPO_ROOT
    / "backend"
    / "tests"
    / "test_b22_p5_webhook_benchmark_adjudication_enforcer.py"
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENFORCER), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_b22_p5_performance_negative_control_lock_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        governance_contract=GOVERNANCE_CONTRACT,
        webhooks_file=WEBHOOKS_FILE,
        benchmark_file=BENCHMARK_FILE,
        benchmark_adjudicator=BENCHMARK_ADJUDICATOR,
        ci_workflow=CI_WORKFLOW,
        runtime_test=RUNTIME_TEST,
        enforcer_test=ENFORCER_TEST,
        adjudicator_test=ADJUDICATOR_TEST,
    )
    assert status == 0, f"unexpected enforcement violations: {violations}"


def test_b22_p5_performance_negative_control_lock_enforcer_negative_control_forced_regression() -> (
    None
):
    proc = _run("--simulate-regression")
    assert proc.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (proc.stdout + proc.stderr)


def test_b22_p5_performance_negative_control_lock_enforcer_negative_control_ci_wiring_missing(
    tmp_path: Path,
) -> None:
    mutated_workflow = tmp_path / "ci.regression.yml"
    mutated_workflow.write_text(
        CI_WORKFLOW.read_text(encoding="utf-8").replace(
            "python scripts/ci/enforce_b22_p5_performance_negative_control_lock.py",
            "python scripts/ci/enforce_b22_p5_regressed.py",
            1,
        ),
        encoding="utf-8",
    )
    proc = _run("--ci-workflow", str(mutated_workflow))
    assert proc.returncode != 0
    assert "ci_missing_b22_p5_token" in (proc.stdout + proc.stderr)


def test_b22_p5_performance_negative_control_lock_enforcer_negative_control_contract_negative_class_drift(
    tmp_path: Path,
) -> None:
    payload = json.loads(GOVERNANCE_CONTRACT.read_text(encoding="utf-8"))
    payload["negative_control_matrix"]["required_classes"].remove(
        "unsupported_event_family"
    )
    mutated_contract = tmp_path / "b22_p5.regression.contract.json"
    mutated_contract.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    proc = _run("--governance-contract", str(mutated_contract))
    assert proc.returncode != 0
    assert "contract_negative_control_required_classes_mismatch" in (
        proc.stdout + proc.stderr
    )


def test_b22_p5_performance_negative_control_lock_enforcer_negative_control_benchmark_forbidden_token(
    tmp_path: Path,
) -> None:
    mutated_benchmark = tmp_path / "b22_p5_webhook_ingress_benchmark.py"
    mutated_benchmark.write_text(
        BENCHMARK_FILE.read_text(encoding="utf-8")
        + "\n# regression marker\nmonkeypatch = True\n",
        encoding="utf-8",
    )

    proc = _run("--benchmark-file", str(mutated_benchmark))
    assert proc.returncode != 0
    assert "benchmark_forbidden_token_present:monkeypatch" in (
        proc.stdout + proc.stderr
    )
