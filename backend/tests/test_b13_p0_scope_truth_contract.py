from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
    )


def test_b13_p0_scope_truth_gate_passes_repo_state() -> None:
    result = _run([sys.executable, "scripts/ci/enforce_b13_p0_scope_truth.py"])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p0_scope_truth_negative_control_detects_registry_drift(tmp_path: Path) -> None:
    baseline = REPO_ROOT / "contracts-internal/governance/b13_p0_provider_capability_matrix.main.json"
    modified = json.loads(baseline.read_text(encoding="utf-8-sig"))
    modified["runtime_backed_providers"] = []
    contract_path = tmp_path / "capability.json"
    contract_path.write_text(json.dumps(modified, indent=2), encoding="utf-8")

    result = _run(
        [
            sys.executable,
            "scripts/ci/enforce_b13_p0_scope_truth.py",
            "--capability-contract",
            str(contract_path),
        ]
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "runtime_backed_providers" in combined


def test_b13_p0_codeowners_gate_passes_repo_state_static_only() -> None:
    result = _run(
        [
            sys.executable,
            "scripts/ci/enforce_b13_p0_codeowners.py",
            "--skip-github-api",
        ]
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p0_codeowners_negative_control_detects_missing_secure_ownership(tmp_path: Path) -> None:
    codeowners = tmp_path / "CODEOWNERS"
    codeowners.write_text("docs/ @Muk223\n", encoding="utf-8")

    result = _run(
        [
            sys.executable,
            "scripts/ci/enforce_b13_p0_codeowners.py",
            "--codeowners-file",
            str(codeowners),
            "--skip-github-api",
        ]
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "Missing CODEOWNERS coverage for secure path" in combined


def test_b13_p0_evidence_pack_gate_passes_repo_state() -> None:
    result = _run([sys.executable, "scripts/ci/enforce_b13_p0_evidence_pack.py"])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p0_evidence_pack_negative_control_detects_missing_sections(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.md"
    evidence.write_text("## Executive Verdict\nPASS\n", encoding="utf-8")

    result = _run(
        [
            sys.executable,
            "scripts/ci/enforce_b13_p0_evidence_pack.py",
            "--evidence-pack",
            str(evidence),
        ]
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "Missing required section" in combined
