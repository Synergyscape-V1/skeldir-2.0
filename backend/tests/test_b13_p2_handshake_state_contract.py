from __future__ import annotations

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


def test_b13_p2_handshake_gate_passes_repo_state() -> None:
    result = _run([sys.executable, "scripts/ci/enforce_b13_p2_handshake_state.py"])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p2_negative_control_detects_missing_gc_column(tmp_path: Path) -> None:
    migration = (
        REPO_ROOT
        / "alembic/versions/007_skeldir_foundation/202603101000_b13_p2_oauth_handshake_state_substrate.py"
    )
    mutated = migration.read_text(encoding="utf-8").replace("gc_after", "gc_window")
    migration_copy = tmp_path / "migration.py"
    migration_copy.write_text(mutated, encoding="utf-8")

    result = _run(
        [
            sys.executable,
            "scripts/ci/enforce_b13_p2_handshake_state.py",
            "--migration-file",
            str(migration_copy),
        ]
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "gc_after" in combined


def test_b13_p2_negative_control_detects_missing_atomic_pending_guard(tmp_path: Path) -> None:
    service = REPO_ROOT / "backend/app/services/oauth_handshake_state.py"
    mutated = service.read_text(encoding="utf-8").replace(
        'OAuthHandshakeSession.status == "pending"',
        'OAuthHandshakeSession.status == "active"',
    )
    service_copy = tmp_path / "service.py"
    service_copy.write_text(mutated, encoding="utf-8")

    result = _run(
        [
            sys.executable,
            "scripts/ci/enforce_b13_p2_handshake_state.py",
            "--service-file",
            str(service_copy),
        ]
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "atomic_pending_guard" in combined


def test_b13_p2_evidence_gate_passes_repo_state() -> None:
    result = _run([sys.executable, "scripts/ci/enforce_b13_p2_evidence_pack.py"])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p2_evidence_gate_negative_control_detects_missing_sections(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.md"
    evidence.write_text("## Executive Verdict\nPASS\n", encoding="utf-8")

    result = _run(
        [
            sys.executable,
            "scripts/ci/enforce_b13_p2_evidence_pack.py",
            "--evidence-pack",
            str(evidence),
        ]
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "Missing required section" in combined
