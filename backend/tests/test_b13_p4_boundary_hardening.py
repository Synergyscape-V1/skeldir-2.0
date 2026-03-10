from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.api.problem_details import problem_details_response

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_b13_p4_boundary_hardening.py"


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
    )


def _minimal_request() -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


def test_b13_p4_gate_passes_repo_state() -> None:
    result = _run([sys.executable, str(GATE_SCRIPT)])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p4_negative_control_detects_missing_required_context(tmp_path: Path) -> None:
    checks_contract = REPO_ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
    payload = json.loads(checks_contract.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value
        for value in payload.get("required_contexts", [])
        if value != "B1.3 P4 Boundary Hardening Proofs"
    ]
    mutated = tmp_path / "required_checks.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--required-checks-contract",
            str(mutated),
        ]
    )
    assert result.returncode != 0
    assert "missing context" in f"{result.stdout}\n{result.stderr}"


def test_b13_p4_negative_control_detects_viewer_scope_regression(tmp_path: Path) -> None:
    platforms_file = REPO_ROOT / "backend/app/api/platforms.py"
    mutated = platforms_file.read_text(encoding="utf-8").replace(
        "Depends(require_lifecycle_mutation_access)",
        "Depends(require_lifecycle_read_access)",
        1,
    )
    mutated_path = tmp_path / "platforms.py"
    mutated_path.write_text(mutated, encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--platforms-api-file",
            str(mutated_path),
        ]
    )
    assert result.returncode != 0
    assert "mutation access" in f"{result.stdout}\n{result.stderr}"


def test_b13_p4_negative_control_detects_enqueue_guard_removal(tmp_path: Path) -> None:
    enqueue_file = REPO_ROOT / "backend/app/tasks/enqueue.py"
    mutated = enqueue_file.read_text(encoding="utf-8").replace(
        "assert_no_sensitive_material(task_kwargs, boundary_name=\"celery_task_kwargs\")",
        "task_kwargs = task_kwargs",
    )
    mutated_path = tmp_path / "enqueue.py"
    mutated_path.write_text(mutated, encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--enqueue-file",
            str(mutated_path),
        ]
    )
    assert result.returncode != 0
    assert "enqueue must reject sensitive task payload kwargs structurally" in f"{result.stdout}\n{result.stderr}"


def test_b13_p4_negative_control_detects_phase_collapse_marker(tmp_path: Path) -> None:
    platforms_file = REPO_ROOT / "backend/app/api/platforms.py"
    mutated = platforms_file.read_text(encoding="utf-8") + "\n# /platform-oauth/ callback\n"
    mutated_path = tmp_path / "platforms.py"
    mutated_path.write_text(mutated, encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--platforms-api-file",
            str(mutated_path),
        ]
    )
    assert result.returncode != 0
    assert "phase-collapse marker" in f"{result.stdout}\n{result.stderr}"


def test_b13_p4_problem_details_sanitizes_sensitive_detail_and_error_payload() -> None:
    response = problem_details_response(
        _minimal_request(),
        status_code=400,
        title="Bad Request",
        detail="provider callback leaked access_token=abc",
        correlation_id=uuid4(),
        type_url="https://api.skeldir.com/problems/validation-error",
        errors=[
            {
                "field": "payload",
                "message": "contains refresh_token",
                "vendor_payload": {"refresh_token": "secret"},
            }
        ],
    )
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["detail"] == "Sensitive details withheld."
    assert payload["errors"][0]["vendor_payload"] == "[REDACTED_RAW_PROVIDER_BODY]"

