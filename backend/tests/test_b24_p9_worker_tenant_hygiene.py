from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from app.bayesian.artifact_repository import _artifact_ref
from app.bayesian.compiledir_reaper import create_compiledir_lease
from app.bayesian.temp_workspace import (
    cleanup_workspace,
    create_workspace_lease,
    reap_expired_workspaces,
)


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts/ci/validate_b24_p9_worker_tenant_hygiene.py"
FIT_EXECUTION = ROOT / "backend/app/bayesian/fit_execution.py"
TENANT_CONTEXT = ROOT / "backend/app/bayesian/tenant_context.py"
TEMP_WORKSPACE = ROOT / "backend/app/bayesian/temp_workspace.py"
CHILD_ENVIRONMENT = ROOT / "backend/app/bayesian/child_environment.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_b24_p9_worker_tenant_hygiene", VALIDATOR
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_b24_p9_transaction_context_uses_set_local_only() -> None:
    text = _read(TENANT_CONTEXT)
    assert "bind_transaction_local_tenant" in text
    assert "set_config('app.current_tenant_id', :tenant_id, true)" in text
    assert "tenant_transaction" in text
    assert "assert_fresh_checkout_is_clean" in text
    assert "set_config('app.current_tenant_id', :tenant_id, false)" not in text
    assert "lru_cache" not in text


def test_b24_p9_workspace_scopes_and_cleans_tenant_fit_hash_attempt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tenant_id = uuid4()
    fit_id = uuid4()
    source_hash = "a" * 64
    monkeypatch.setenv("B24_BAYESIAN_WORKSPACE_ROOT", str(tmp_path / "workspaces"))

    lease_a = create_workspace_lease(
        tenant_id=tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=source_hash,
        execution_attempt_id="attempt-a",
    )
    lease_b = create_workspace_lease(
        tenant_id=tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=source_hash,
        execution_attempt_id="attempt-b",
    )

    assert lease_a.path != lease_b.path
    assert str(tenant_id) in lease_a.path.parts
    assert str(fit_id) in lease_a.path.parts
    assert source_hash in lease_a.path.parts
    assert "attempt-a" in lease_a.path.parts
    assert json.loads(
        (lease_a.path / "skeldir_workspace_owner.json").read_text(encoding="utf-8")
    )["tenant_id"] == str(tenant_id)
    assert cleanup_workspace(lease_a) is True
    assert not lease_a.path.exists()

    with pytest.raises(ValueError, match="unsafe"):
        create_workspace_lease(
            tenant_id=tenant_id,
            fit_id=fit_id,
            source_snapshot_hash=source_hash,
            execution_attempt_id="../escape",
        )

    metadata_path = lease_b.path / "skeldir_workspace_owner.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["created_at"] = 1
    metadata["parent_pid"] = 99999999
    metadata_path.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")
    report = reap_expired_workspaces(ttl_seconds=60, max_deletions=10)
    assert report["deleted"] >= 1
    assert not lease_b.path.exists()


def test_b24_p9_compiledir_scopes_tenant_fit_hash_attempt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tenant_id = uuid4()
    fit_id = uuid4()
    source_hash = "b" * 64
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))

    lease_a = create_compiledir_lease(
        execution_id="attempt-a",
        worker_id="unit-worker",
        tenant_id=tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=source_hash,
    )
    lease_b = create_compiledir_lease(
        execution_id="attempt-b",
        worker_id="unit-worker",
        tenant_id=tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=source_hash,
    )

    assert lease_a.path != lease_b.path
    assert str(tenant_id) in lease_a.path.parts
    assert str(fit_id) in lease_a.path.parts
    assert source_hash in lease_a.path.parts
    assert "attempt-a" in lease_a.path.parts
    metadata = json.loads(
        (lease_a.path / "skeldir_compiledir_owner.json").read_text(encoding="utf-8")
    )
    assert metadata["tenant_id"] == str(tenant_id)
    assert metadata["fit_id"] == str(fit_id)
    assert metadata["source_snapshot_hash"] == source_hash


def test_b24_p9_child_env_is_allowlisted_without_parent_mutation(
    tmp_path: Path,
) -> None:
    from app.bayesian.child_environment import build_sampler_child_env

    parent_before = dict(os.environ)
    env = build_sampler_child_env(
        compiledir=tmp_path / "compiledir",
        execution_id="attempt-env",
        source_env={
            "PATH": os.environ.get("PATH", ""),
            "DATABASE_URL": "postgresql://must:not@leak/db",
            "B24_STAGE_MARKER_PATH": str(tmp_path / "marker.jsonl"),
            "PYTENSOR_FLAGS": "mode=FAST_RUN,base_compiledir=/tmp/global",
        },
    )

    assert os.environ == parent_before
    assert "DATABASE_URL" not in env
    assert env["B24_STAGE_MARKER_PATH"].endswith("marker.jsonl")
    assert env["B24_PYTENSOR_COMPILEDIR"] == str(tmp_path / "compiledir")
    assert env["PYTENSOR_FLAGS"].startswith(
        f"base_compiledir={(tmp_path / 'compiledir').as_posix()}"
    )
    assert "/tmp/global" not in env["PYTENSOR_FLAGS"]


def test_b24_p9_artifact_ref_contains_tenant_authority() -> None:
    tenant_id = uuid4()
    fit_id = uuid4()
    ref = _artifact_ref(
        tenant_id=tenant_id,
        fit_id=fit_id,
        artifact_type="diagnostics",
        artifact_hash="c" * 64,
    )
    assert ref == f"b24://artifact/{tenant_id}/{fit_id}/diagnostics/{'c' * 12}"


def test_b24_p9_fit_execution_wires_cleanup_and_payload_airgap() -> None:
    text = _read(FIT_EXECUTION)
    for token in (
        "run_preflight_janitor(",
        "assert_fresh_checkout_is_clean(engine)",
        "create_workspace_lease(",
        "create_compiledir_lease(",
        "tenant_id=tenant_id",
        "fit_id=fit_id",
        "source_snapshot_hash=source_snapshot_hash",
        "cleanup_fit_attempt(workspace=workspace, compiledir=lease)",
        "stderr_retained_bytes",
        "stderr_truncated",
    ):
        assert token in text
    assert "stderr_retained\": result.stderr.retained_text" not in text
    assert "payload_json" not in _read(CHILD_ENVIRONMENT)


def test_b24_p9_validator_negative_controls() -> None:
    validator = _load_validator()
    validator.validate_all()
    validator.run_negative_controls()
