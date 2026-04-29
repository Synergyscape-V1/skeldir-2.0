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


def test_b23_pre_p1_spec_gate_enforcer_passes_repo_baseline() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b23_pre_p1_spec_gate_enforcer_negative_control_forced_regression() -> None:
    result = _run("--simulate-regression")
    assert result.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (result.stdout + result.stderr)


def test_b23_pre_p1_spec_gate_enforcer_negative_control_missing_provider_field(
    tmp_path: Path,
) -> None:
    payload = _load_json(CONTRACT_FILE)
    del payload["revenue_extraction_standard"]["providers"]["stripe"]["source_currency_field"]
    mutated = tmp_path / "contract.regression.json"
    _write_json(mutated, payload)

    result = _run("--contract-file", str(mutated))
    assert result.returncode != 0
    assert "revenue_provider_stripe_missing_field:source_currency_field" in (
        result.stdout + result.stderr
    )


def test_b23_pre_p1_spec_gate_enforcer_negative_control_float_ban_scope_removed(
    tmp_path: Path,
) -> None:
    payload = _load_json(CONTRACT_FILE)
    scopes = payload["revenue_extraction_standard"]["canonical_storage"]["binary_float_forbidden_scopes"]
    payload["revenue_extraction_standard"]["canonical_storage"]["binary_float_forbidden_scopes"] = [
        scope for scope in scopes if scope != "match_arithmetic"
    ]
    mutated = tmp_path / "contract.float_scope.regression.json"
    _write_json(mutated, payload)

    result = _run("--contract-file", str(mutated))
    assert result.returncode != 0
    assert "revenue_binary_float_scope_missing:match_arithmetic" in (
        result.stdout + result.stderr
    )


def test_b23_pre_p1_spec_gate_enforcer_negative_control_privacy_table_class_removed(
    tmp_path: Path,
) -> None:
    payload = _load_json(CONTRACT_FILE)
    del payload["table_privacy_lifecycle_pre_spec"]["table_classes"]["revenue_events"]
    mutated = tmp_path / "contract.privacy.regression.json"
    _write_json(mutated, payload)

    result = _run("--contract-file", str(mutated))
    assert result.returncode != 0
    assert "privacy_table_class_missing:revenue_events" in (result.stdout + result.stderr)


def test_b23_pre_p1_spec_gate_enforcer_negative_control_timing_constant_removed(
    tmp_path: Path,
) -> None:
    payload = _load_json(CONTRACT_FILE)
    del payload["timing_constants"]["PROVISIONAL_MATCH_WINDOW"]
    mutated = tmp_path / "contract.timing.regression.json"
    _write_json(mutated, payload)

    result = _run("--contract-file", str(mutated))
    assert result.returncode != 0
    assert "timing_constant_missing:PROVISIONAL_MATCH_WINDOW" in (
        result.stdout + result.stderr
    )


def test_b23_pre_p1_spec_gate_enforcer_negative_control_ci_wiring_removed(
    tmp_path: Path,
) -> None:
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


def test_b23_pre_p1_spec_gate_enforcer_negative_control_spec_token_removed(
    tmp_path: Path,
) -> None:
    mutated_spec = tmp_path / "spec.regression.md"
    mutated_spec.write_text(
        SPEC_FILE.read_text(encoding="utf-8").replace(
            "The `<10 second` benchmark applies only to match-engine batch execution over pre-arrived events.",
            "The benchmark applies to all latency classes.",
            1,
        ),
        encoding="utf-8",
    )

    result = _run("--spec-file", str(mutated_spec))
    assert result.returncode != 0
    assert (
        "spec_missing_token:The `<10 second` benchmark applies only to match-engine batch execution over pre-arrived events."
        in (result.stdout + result.stderr)
    )
