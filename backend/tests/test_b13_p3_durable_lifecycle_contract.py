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


def test_b13_p3_durable_lifecycle_gate_passes_repo_state() -> None:
    result = _run([sys.executable, "scripts/ci/enforce_b13_p3_durable_lifecycle.py"])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p3_negative_control_detects_missing_scheduler_column(tmp_path: Path) -> None:
    migration = (
        REPO_ROOT
        / "alembic/versions/007_skeldir_foundation/202603101530_b13_p3_platform_credentials_lifecycle_metadata.py"
    )
    mutated = migration.read_text(encoding="utf-8").replace(
        "next_refresh_due_at",
        "next_refresh_window",
    )
    migration_copy = tmp_path / "migration.py"
    migration_copy.write_text(mutated, encoding="utf-8")

    result = _run(
        [
            sys.executable,
            "scripts/ci/enforce_b13_p3_durable_lifecycle.py",
            "--migration-file",
            str(migration_copy),
        ]
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "next_refresh_due_at" in combined


def test_b13_p3_negative_control_detects_parallel_store_attempt(tmp_path: Path) -> None:
    migration = (
        REPO_ROOT
        / "alembic/versions/007_skeldir_foundation/202603101530_b13_p3_platform_credentials_lifecycle_metadata.py"
    )
    injected = (
        migration.read_text(encoding="utf-8")
        + "\n\n"
        + "def bad_create() -> None:\n"
        + "    op.execute(\"CREATE TABLE public.platform_tokens (id uuid)\")\n"
    )
    migration_copy = tmp_path / "migration.py"
    migration_copy.write_text(injected, encoding="utf-8")

    result = _run(
        [
            sys.executable,
            "scripts/ci/enforce_b13_p3_durable_lifecycle.py",
            "--migration-file",
            str(migration_copy),
        ]
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "CREATE TABLE" in combined or "parallel durable token store" in combined


def test_b13_p3_negative_control_detects_missing_required_context(tmp_path: Path) -> None:
    checks_contract = REPO_ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
    payload = json.loads(checks_contract.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value
        for value in payload.get("required_contexts", [])
        if value != "B1.3 P3 Durable Lifecycle Schema Proofs"
    ]
    contract_copy = tmp_path / "required_checks.json"
    contract_copy.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(
        [
            sys.executable,
            "scripts/ci/enforce_b13_p3_durable_lifecycle.py",
            "--required-checks-contract",
            str(contract_copy),
        ]
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "missing context" in combined


def test_b13_p3_negative_control_detects_decrypt_in_due_selector(tmp_path: Path) -> None:
    service = REPO_ROOT / "backend/app/services/platform_credentials.py"
    original = service.read_text(encoding="utf-8")
    injected = original.replace(
        "result = await session.execute(query)",
        "# regression: forbidden decryption in scheduler selector\n"
        "        _ = _decrypt_ciphertext_once\n"
        "        result = await session.execute(query)",
        1,
    )
    service_copy = tmp_path / "platform_credentials.py"
    service_copy.write_text(injected, encoding="utf-8")

    result = _run(
        [
            sys.executable,
            "scripts/ci/enforce_b13_p3_durable_lifecycle.py",
            "--service-file",
            str(service_copy),
        ]
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "list_refresh_due must not decrypt" in combined
