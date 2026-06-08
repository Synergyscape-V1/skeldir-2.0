from __future__ import annotations

import importlib.util
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from uuid import uuid4

import pytest

from app.bayesian.artifact_repository import _artifact_ref
from app.bayesian.cleanup import cleanup_fit_attempt, run_preflight_janitor
from app.bayesian.compiledir_reaper import create_compiledir_lease
from app.bayesian.fit_execution import _sampler_failure_stream_metadata
from app.bayesian.sampler_supervisor import (
    CapturedChildStream,
    SupervisedSamplerResult,
    build_child_env_for_lease,
    run_supervised_sampler,
    synthetic_blocking_child_command,
)
from app.bayesian.temp_workspace import (
    _is_owned_child_path as _workspace_child_path_is_owned,
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
COMPILEDIR_REAPER = ROOT / "backend/app/bayesian/compiledir_reaper.py"


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


def _representative_parent_worker_attempt(
    *,
    tenant_id,
    fit_id,
    source_hash: str,
    attempt_id: str,
    sentinel: str,
) -> dict[str, object]:
    parent_pid = os.getpid()
    workspace = create_workspace_lease(
        tenant_id=tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=source_hash,
        execution_attempt_id=attempt_id,
    )
    compiledir = create_compiledir_lease(
        execution_id=attempt_id,
        worker_id="p9-reused-worker-proof",
        tenant_id=tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=source_hash,
    )
    ipc_dir = workspace.path / "ipc"
    ipc_dir.mkdir(parents=True, exist_ok=False)
    (ipc_dir / "private_source_payload.txt").write_text(sentinel, encoding="utf-8")
    env = build_child_env_for_lease(
        compiledir,
        source_env={
            "PATH": os.environ.get("PATH", ""),
            "DATABASE_URL": f"postgresql://{sentinel}@must-not-leak/db",
            "PYTENSOR_FLAGS": "mode=FAST_RUN,base_compiledir=/tmp/global",
        },
    )
    artifact_ref = _artifact_ref(
        tenant_id=tenant_id,
        fit_id=fit_id,
        artifact_type="diagnostics",
        artifact_hash="d" * 64,
    )
    state = {
        "parent_pid": parent_pid,
        "tenant_id": str(tenant_id),
        "fit_id": str(fit_id),
        "workspace": str(workspace.path),
        "compiledir": str(compiledir.path),
        "artifact_ref": artifact_ref,
        "child_env_keys": sorted(env),
        "child_compiledir": env["B24_PYTENSOR_COMPILEDIR"],
        "pytensor_flags": env["PYTENSOR_FLAGS"],
    }
    cleanup_report = cleanup_fit_attempt(workspace=workspace, compiledir=compiledir)
    state["cleanup"] = cleanup_report.__dict__
    state["workspace_exists_after_cleanup"] = workspace.path.exists()
    state["compiledir_exists_after_cleanup"] = compiledir.path.exists()
    return state


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
        "_sampler_failure_stream_metadata(result)",
        "stderr_retained_bytes",
        "stderr_truncated",
    ):
        assert token in text
    assert 'stderr_retained": result.stderr.retained_text' not in text
    assert "payload_json" not in _read(CHILD_ENVIRONMENT)


def test_b24_p9_same_process_sequential_reused_worker_runtime_lane(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("B24_BAYESIAN_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))
    monkeypatch.setenv("B24_BAYESIAN_MAX_TASKS_PER_CHILD", "10")
    assert os.getenv("B24_BAYESIAN_MAX_TASKS_PER_CHILD") != "1"

    tenant_a = uuid4()
    tenant_b = uuid4()
    fit_a = uuid4()
    fit_b = uuid4()
    sentinel_a = "P9_TENANT_A_SENTINEL_SHOULD_NOT_REACH_B"
    sentinel_b = "P9_TENANT_B_SENTINEL"

    state_a = _representative_parent_worker_attempt(
        tenant_id=tenant_a,
        fit_id=fit_a,
        source_hash="a" * 64,
        attempt_id="attempt-a",
        sentinel=sentinel_a,
    )
    state_b = _representative_parent_worker_attempt(
        tenant_id=tenant_b,
        fit_id=fit_b,
        source_hash="b" * 64,
        attempt_id="attempt-b",
        sentinel=sentinel_b,
    )
    baseline_b = _representative_parent_worker_attempt(
        tenant_id=tenant_b,
        fit_id=fit_b,
        source_hash="b" * 64,
        attempt_id="attempt-b-baseline",
        sentinel=sentinel_b,
    )

    assert state_a["parent_pid"] == state_b["parent_pid"] == os.getpid()
    assert state_b["artifact_ref"] == baseline_b["artifact_ref"]
    assert state_a["workspace"] != state_b["workspace"]
    assert state_a["compiledir"] != state_b["compiledir"]
    assert state_b["child_compiledir"] == state_b["compiledir"]
    assert "/tmp/global" not in str(state_b["pytensor_flags"])
    assert state_b["cleanup"] == {
        "workspace_removed": True,
        "compiledir_removed": True,
    }
    assert state_b["workspace_exists_after_cleanup"] is False
    assert state_b["compiledir_exists_after_cleanup"] is False
    assert sentinel_a not in json.dumps(state_b, sort_keys=True)


def test_b24_p9_concurrent_tenant_isolation_runtime_surfaces(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("B24_BAYESIAN_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))
    barrier = Barrier(2)
    tenant_a = uuid4()
    tenant_b = uuid4()
    fit_a = uuid4()
    fit_b = uuid4()

    def run_lane(label: str, tenant_id, fit_id, source_hash: str) -> dict[str, object]:
        workspace = create_workspace_lease(
            tenant_id=tenant_id,
            fit_id=fit_id,
            source_snapshot_hash=source_hash,
            execution_attempt_id=f"attempt-{label}",
        )
        compiledir = create_compiledir_lease(
            execution_id=f"attempt-{label}",
            worker_id="p9-concurrent-worker-proof",
            tenant_id=tenant_id,
            fit_id=fit_id,
            source_snapshot_hash=source_hash,
        )
        artifact_ref = _artifact_ref(
            tenant_id=tenant_id,
            fit_id=fit_id,
            artifact_type="diagnostics",
            artifact_hash=source_hash,
        )
        barrier.wait(timeout=5)
        workspace_cleanup = cleanup_fit_attempt(workspace=workspace, compiledir=None)
        compiledir_survived_workspace_cleanup = compiledir.path.exists()
        compiledir_cleanup = cleanup_fit_attempt(workspace=None, compiledir=compiledir)
        return {
            "label": label,
            "workspace": workspace.path,
            "compiledir": compiledir.path,
            "artifact_ref": artifact_ref,
            "workspace_removed": workspace_cleanup.workspace_removed,
            "compiledir_survived_workspace_cleanup": compiledir_survived_workspace_cleanup,
            "compiledir_removed": compiledir_cleanup.compiledir_removed,
        }

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(run_lane, "a", tenant_a, fit_a, "a" * 64)
        future_b = executor.submit(run_lane, "b", tenant_b, fit_b, "b" * 64)
        result_a = future_a.result(timeout=10)
        result_b = future_b.result(timeout=10)

    assert result_a["workspace"] != result_b["workspace"]
    assert result_a["compiledir"] != result_b["compiledir"]
    assert result_a["artifact_ref"] != result_b["artifact_ref"]
    assert result_a["workspace_removed"] is True
    assert result_b["workspace_removed"] is True
    assert result_a["compiledir_survived_workspace_cleanup"] is True
    assert result_b["compiledir_survived_workspace_cleanup"] is True
    assert result_a["compiledir_removed"] is True
    assert result_b["compiledir_removed"] is True


def test_b24_p9_concurrent_janitor_toctou_safe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("B24_BAYESIAN_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))
    stale_workspace = create_workspace_lease(
        tenant_id=uuid4(),
        fit_id=uuid4(),
        source_snapshot_hash="e" * 64,
        execution_attempt_id="stale-workspace",
    )
    stale_compiledir = create_compiledir_lease(
        execution_id="stale-compiledir",
        worker_id="p9-janitor",
        tenant_id=uuid4(),
        fit_id=uuid4(),
        source_snapshot_hash="f" * 64,
    )
    for metadata_path in (
        stale_workspace.path / "skeldir_workspace_owner.json",
        stale_compiledir.path / "skeldir_compiledir_owner.json",
    ):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["created_at"] = 1
        metadata["parent_pid"] = 99999999
        metadata_path.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")

    with ThreadPoolExecutor(max_workers=4) as executor:
        reports = list(
            executor.map(
                lambda _: run_preflight_janitor(
                    ttl_seconds=0,
                    max_deletions=10,
                    max_scan_entries=20,
                ),
                range(4),
            )
        )

    assert not stale_workspace.path.exists()
    assert not stale_compiledir.path.exists()
    assert sum(int(report["workspaces"]["deleted"]) for report in reports) >= 1
    assert sum(int(report["compiledirs"]["deleted"]) for report in reports) >= 1
    assert any(
        report["workspaces"]["lock_contended"]
        or report["compiledirs"]["lock_contended"]
        or report["workspaces"]["deleted"]
        or report["compiledirs"]["deleted"]
        for report in reports
    )

    outside = tmp_path / "outside"
    outside.mkdir()
    outside_metadata_dir = outside / "owned-looking"
    outside_metadata_dir.mkdir()
    (outside_metadata_dir / "skeldir_workspace_owner.json").write_text(
        json.dumps(
            {"owner": "skeldir-b24-p9", "created_at": 1, "parent_pid": 99999999}
        ),
        encoding="utf-8",
    )
    symlink = tmp_path / "workspaces" / "symlinked-outside"
    try:
        symlink.symlink_to(outside_metadata_dir, target_is_directory=True)
    except OSError:
        return
    assert _workspace_child_path_is_owned(tmp_path / "workspaces", symlink) is False
    report = run_preflight_janitor(ttl_seconds=0, max_deletions=10, max_scan_entries=20)
    assert outside_metadata_dir.exists()
    assert report["workspaces"]["deleted"] == 0


def test_b24_p9_logs_and_failure_payloads_do_not_emit_sentinels() -> None:
    sentinel_a = "P9_RAW_TENANT_A_STDERR_SENTINEL"
    sentinel_b = "P9_RAW_TENANT_B_STDOUT_SENTINEL"
    result = SupervisedSamplerResult(
        status="completed",
        child_pid=12345,
        elapsed_seconds=0.01,
        killed_by_supervisor=False,
        returncode=2,
        orphan_reaped=True,
        stdout=CapturedChildStream(
            retained_bytes=sentinel_b.encode("utf-8"),
            total_bytes=len(sentinel_b),
            truncated=False,
        ),
        stderr=CapturedChildStream(
            retained_bytes=sentinel_a.encode("utf-8"),
            total_bytes=len(sentinel_a),
            truncated=False,
        ),
    )
    payload = _sampler_failure_stream_metadata(result)
    encoded = json.dumps(payload, sort_keys=True)
    assert sentinel_a not in encoded
    assert sentinel_b not in encoded
    assert payload == {
        "stdout_total_bytes": len(sentinel_b),
        "stdout_retained_bytes": len(sentinel_b),
        "stdout_truncated": False,
        "stderr_total_bytes": len(sentinel_a),
        "stderr_retained_bytes": len(sentinel_a),
        "stderr_truncated": False,
    }


def test_b24_p9_native_memory_lifecycle_child_per_fit_parent_airgap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))
    forbidden_native_modules = {"pymc", "pytensor", "arviz"}
    assert forbidden_native_modules.isdisjoint(sys.modules)
    lease = create_compiledir_lease(
        execution_id="native-child-per-fit",
        worker_id="p9-native-lifecycle",
        tenant_id=uuid4(),
        fit_id=uuid4(),
        source_snapshot_hash="9" * 64,
    )
    result = run_supervised_sampler(
        synthetic_blocking_child_command(seconds=5),
        deadline_seconds=0.2,
        env=build_child_env_for_lease(
            lease,
            source_env={
                "PATH": os.environ.get("PATH", ""),
                "PYTHONPATH": str(ROOT / "backend"),
            },
        ),
        compiledir_lease=lease,
    )
    assert result.child_pid != os.getpid()
    assert result.killed_by_supervisor is True
    assert result.orphan_reaped is True
    assert not lease.path.exists()
    assert forbidden_native_modules.isdisjoint(sys.modules)


def test_b24_p9_validator_negative_controls() -> None:
    validator = _load_validator()
    validator.validate_all()
    validator.run_negative_controls()
