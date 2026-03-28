"""B1.5-P6 anti-cyborg governance enforcer tests."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return (
        _repo_root()
        / "scripts"
        / "ci"
        / "enforce_b15_p6_anti_cyborg_governance.py"
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run_enforcer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_script_path()), *args],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )


def _build_tmp_contracts(
    tmp_path: Path,
    *,
    decision_file: Path,
    exception_files: list[Path],
    exception_ids: list[str],
) -> tuple[Path, Path, Path]:
    matrix = _load_json(
        _repo_root()
        / "contracts-internal"
        / "governance"
        / "b15_p6_prohibited_signature_matrix.main.json"
    )
    matrix["decision_surface_roots"] = []
    matrix["decision_surface_files"] = [str(decision_file)]

    registry = _load_json(
        _repo_root()
        / "contracts-internal"
        / "governance"
        / "b15_p6_realtime_exception_registry.main.json"
    )
    registry["exceptions"] = []
    for exception_id, exception_file in zip(exception_ids, exception_files, strict=True):
        registry["exceptions"].append(
            {
                "exception_id": exception_id,
                "owner_domain": "verification",
                "owner_team": "frontend-platform",
                "purpose": "test fixture",
                "exception_surface_files": [str(exception_file)],
                "allowed_scope_roots": ["frontend/src/types/api"],
                "allowed_for_b15_decision_surfaces": False,
            }
        )

    overrides = _load_json(
        _repo_root()
        / "contracts-internal"
        / "governance"
        / "b15_p6_escalation_overrides.main.json"
    )
    overrides["baseline_exception_approvals"] = [
        {
            "exception_id": exception_id,
            "ticket": f"TEST-{exception_id}",
            "approved_by": ["test-governance"],
            "justification": "test baseline approval",
        }
        for exception_id in exception_ids
    ]
    overrides["active_overrides"] = []

    matrix_file = tmp_path / "matrix.json"
    registry_file = tmp_path / "registry.json"
    overrides_file = tmp_path / "overrides.json"
    _write_json(matrix_file, matrix)
    _write_json(registry_file, registry)
    _write_json(overrides_file, overrides)
    return matrix_file, registry_file, overrides_file


def test_b15_p6_enforcer_passes_repo_baseline() -> None:
    result = _run_enforcer()
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b15_p6_enforcer_negative_control_synthetic_regression() -> None:
    result = _run_enforcer("--simulate-regression")
    assert result.returncode != 0
    assert "synthetic_regression" in (result.stdout + result.stderr)


def test_b15_p6_enforcer_negative_control_direct_realtime_import(tmp_path: Path) -> None:
    exception_file = tmp_path / "verificationRealtimeException.ts"
    exception_file.write_text("export const verificationRealtime = true;\n", encoding="utf-8")

    decision_file = tmp_path / "BudgetDecisionSurface.ts"
    decision_file.write_text(
        "import { verificationRealtime } from './verificationRealtimeException';\n"
        "export const marker = verificationRealtime;\n",
        encoding="utf-8",
    )

    matrix_file, registry_file, overrides_file = _build_tmp_contracts(
        tmp_path,
        decision_file=decision_file,
        exception_files=[exception_file],
        exception_ids=["verification_realtime_surface_test"],
    )

    result = _run_enforcer(
        "--matrix-file",
        str(matrix_file),
        "--registry-file",
        str(registry_file),
        "--overrides-file",
        str(overrides_file),
    )
    assert result.returncode != 0
    assert "deny_by_default_blocked:import_fence:verification_realtime_surface_test" in (
        result.stdout + result.stderr
    )


def test_b15_p6_enforcer_negative_control_reexport_realtime_import(tmp_path: Path) -> None:
    exception_file = tmp_path / "verificationRealtimeException.ts"
    exception_file.write_text("export const verificationRealtime = true;\n", encoding="utf-8")

    barrel_file = tmp_path / "barrel.ts"
    barrel_file.write_text(
        "export { verificationRealtime } from './verificationRealtimeException';\n",
        encoding="utf-8",
    )

    decision_file = tmp_path / "InvestigationDecisionSurface.ts"
    decision_file.write_text(
        "import { verificationRealtime } from './barrel';\n"
        "export const marker = verificationRealtime;\n",
        encoding="utf-8",
    )

    matrix_file, registry_file, overrides_file = _build_tmp_contracts(
        tmp_path,
        decision_file=decision_file,
        exception_files=[exception_file],
        exception_ids=["verification_realtime_surface_reexport_test"],
    )

    result = _run_enforcer(
        "--matrix-file",
        str(matrix_file),
        "--registry-file",
        str(registry_file),
        "--overrides-file",
        str(overrides_file),
    )
    assert result.returncode != 0
    assert "deny_by_default_blocked:import_fence:verification_realtime_surface_reexport_test" in (
        result.stdout + result.stderr
    )


def test_b15_p6_enforcer_negative_control_forbidden_signature(tmp_path: Path) -> None:
    exception_file = tmp_path / "verificationRealtimeException.ts"
    exception_file.write_text("export const verificationRealtime = true;\n", encoding="utf-8")

    decision_file = tmp_path / "BudgetDecisionSurface.ts"
    decision_file.write_text(
        "const ws = new WebSocket('wss://example.com/stream');\n"
        "export const marker = ws;\n",
        encoding="utf-8",
    )

    matrix_file, registry_file, overrides_file = _build_tmp_contracts(
        tmp_path,
        decision_file=decision_file,
        exception_files=[exception_file],
        exception_ids=["verification_realtime_surface_signature_test"],
    )

    result = _run_enforcer(
        "--matrix-file",
        str(matrix_file),
        "--registry-file",
        str(registry_file),
        "--overrides-file",
        str(overrides_file),
    )
    assert result.returncode != 0
    assert "deny_by_default_blocked:transport.websocket.new_expression" in (
        result.stdout + result.stderr
    )


def test_b15_p6_enforcer_negative_control_exception_added_without_baseline_override(
    tmp_path: Path,
) -> None:
    decision_file = tmp_path / "DecisionSurface.ts"
    decision_file.write_text("export const marker = true;\n", encoding="utf-8")

    exception_file_a = tmp_path / "exceptionA.ts"
    exception_file_a.write_text("export const a = 1;\n", encoding="utf-8")
    exception_file_b = tmp_path / "exceptionB.ts"
    exception_file_b.write_text("export const b = 2;\n", encoding="utf-8")

    matrix_file, registry_file, overrides_file = _build_tmp_contracts(
        tmp_path,
        decision_file=decision_file,
        exception_files=[exception_file_a, exception_file_b],
        exception_ids=["exception_a", "exception_b"],
    )

    overrides = _load_json(overrides_file)
    overrides["baseline_exception_approvals"] = [overrides["baseline_exception_approvals"][0]]
    _write_json(overrides_file, overrides)

    result = _run_enforcer(
        "--matrix-file",
        str(matrix_file),
        "--registry-file",
        str(registry_file),
        "--overrides-file",
        str(overrides_file),
    )
    assert result.returncode != 0
    assert "overrides_baseline_exception_alignment_mismatch" in (
        result.stdout + result.stderr
    )


def test_b15_p6_enforcer_override_is_mechanical_and_removal_fails(tmp_path: Path) -> None:
    exception_file = tmp_path / "verificationRealtimeException.ts"
    exception_file.write_text("export const verificationRealtime = true;\n", encoding="utf-8")

    decision_file = tmp_path / "BudgetDecisionSurface.ts"
    decision_file.write_text(
        "const ws = new WebSocket('wss://example.com/stream');\n"
        "export const marker = ws;\n",
        encoding="utf-8",
    )

    matrix_file, registry_file, overrides_file = _build_tmp_contracts(
        tmp_path,
        decision_file=decision_file,
        exception_files=[exception_file],
        exception_ids=["verification_realtime_surface_override_test"],
    )

    decision_glob = str(decision_file).replace("\\", "/")
    expires_on = (date.today() + timedelta(days=7)).isoformat()
    overrides = _load_json(overrides_file)
    overrides["active_overrides"] = [
        {
            "override_id": "OVERRIDE-TEST-001",
            "status": "active",
            "ticket": "B15-P6-OVERRIDE-TEST",
            "approved_by": ["test-governance"],
            "expires_on": expires_on,
            "decision_surface_globs": [decision_glob],
            "allowed_violation_ids": ["transport.websocket.new_expression"],
            "justification": "temporary approved experiment",
        }
    ]
    _write_json(overrides_file, overrides)

    allowed_result = _run_enforcer(
        "--matrix-file",
        str(matrix_file),
        "--registry-file",
        str(registry_file),
        "--overrides-file",
        str(overrides_file),
    )
    assert allowed_result.returncode == 0, allowed_result.stdout + "\n" + allowed_result.stderr
    assert "override_applied:OVERRIDE-TEST-001" in (allowed_result.stdout + allowed_result.stderr)

    overrides["active_overrides"] = []
    _write_json(overrides_file, overrides)
    denied_result = _run_enforcer(
        "--matrix-file",
        str(matrix_file),
        "--registry-file",
        str(registry_file),
        "--overrides-file",
        str(overrides_file),
    )
    assert denied_result.returncode != 0
    assert "deny_by_default_blocked:transport.websocket.new_expression" in (
        denied_result.stdout + denied_result.stderr
    )
