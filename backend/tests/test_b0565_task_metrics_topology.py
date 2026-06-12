"""
B0.5.6.5: Task Metrics Topology (No DB sink, no worker listener, safe scraping).

These tests enforce:
- Exporter is DB-independent and serves /metrics with invalid DATABASE_URL.
- Worker runtime does not import or start any HTTP listener.
- PROMETHEUS_MULTIPROC_DIR configuration is single-source and fail-fast.
- Orphan shard pruning is conservative and bounded.
- Exporter is read-only w.r.t. PROMETHEUS_MULTIPROC_DIR.
- Task metric labels remain privacy-safe and bounded.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import pytest

from app.observability.metrics_policy import normalize_task_name
from app.observability.metrics_runtime_config import MULTIPROC_DIR_INVALID_ERROR
from app.observability.multiprocess_shard_pruner import prune_stale_multiproc_shards


UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_for_http_200(url: str, *, timeout_s: float = 10.0) -> bytes:
    deadline = time.time() + timeout_s
    last_exc: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1) as resp:  # noqa: S310 - local test server only
                if resp.status == 200:
                    return resp.read()
        except Exception as exc:
            last_exc = exc
            time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for 200 from {url}: {last_exc}")


def test_eg53_exporter_serves_metrics_with_invalid_database_url(tmp_path: Path):
    """
    EG5.3: No DB sink / no DB dependency for exporter.
    """
    multiproc_dir = tmp_path / "multiproc"
    multiproc_dir.mkdir()
    sentinel = multiproc_dir / "SENTINEL_DO_NOT_TOUCH.txt"
    sentinel.write_text("sentinel", encoding="utf-8")

    port = _pick_free_port()
    env = dict(os.environ)
    env.update(
        {
            "PROMETHEUS_MULTIPROC_DIR": str(multiproc_dir),
            "WORKER_METRICS_EXPORTER_HOST": "127.0.0.1",
            "WORKER_METRICS_EXPORTER_PORT": str(port),
            "DATABASE_URL": "postgresql://invalid:invalid@invalid.invalid:5432/invalid",
        }
    )

    backend_dir = Path(__file__).resolve().parents[1]
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.observability.worker_metrics_exporter"],
        cwd=str(backend_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        body = _wait_for_http_200(f"http://127.0.0.1:{port}/metrics")
        assert isinstance(body, (bytes, bytearray))
        assert sentinel.exists(), "Exporter must not delete or modify non-shard files in multiproc dir"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def test_eg52_worker_entrypoints_do_not_import_http_server_primitives():
    """
    EG5.1/EG5.2: Worker runtime must not bind listeners or import server primitives.
    """
    repo_root = Path(__file__).resolve().parents[2]
    celery_app_path = repo_root / "backend" / "app" / "celery_app.py"
    content = celery_app_path.read_text(encoding="utf-8")

    assert "worker_metrics_exporter" not in content
    assert "wsgiref.simple_server" not in content
    assert "http.server" not in content
    assert "socketserver" not in content
    assert "start_http_server" not in content

    guardrail = repo_root / "scripts" / "ci" / "enforce_no_worker_http_server.py"
    result = subprocess.run(
        [sys.executable, str(guardrail)],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )
    assert "PASS: No worker HTTP server primitives detected." in result.stdout


def test_eg57_convergence_fail_fast_when_multiproc_dir_missing(monkeypatch: pytest.MonkeyPatch):
    from app.observability import metrics_runtime_config as cfg

    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    with pytest.raises(RuntimeError) as exc:
        cfg.get_multiproc_dir()
    assert str(exc.value) == MULTIPROC_DIR_INVALID_ERROR


def test_eg57_convergence_fail_fast_when_multiproc_dir_not_absolute(monkeypatch: pytest.MonkeyPatch):
    from app.observability import metrics_runtime_config as cfg

    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", "relative/path")
    with pytest.raises(RuntimeError) as exc:
        cfg.get_multiproc_dir()
    assert str(exc.value) == MULTIPROC_DIR_INVALID_ERROR


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions required for unwritable-dir validation")
def test_eg57_convergence_fail_fast_when_multiproc_dir_unwritable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.observability import metrics_runtime_config as cfg

    multiproc_dir = tmp_path / "multiproc_unwritable"
    multiproc_dir.mkdir()
    os.chmod(multiproc_dir, 0o500)  # r-x------
    try:
        monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(multiproc_dir))
        with pytest.raises(RuntimeError) as exc:
            cfg.get_multiproc_dir()
        assert str(exc.value) == MULTIPROC_DIR_INVALID_ERROR
    finally:
        os.chmod(multiproc_dir, 0o700)


def test_eg56_active_pruning_prunes_dead_pid_shards_but_keeps_live(tmp_path: Path):
    multiproc_dir = tmp_path / "multiproc"
    multiproc_dir.mkdir()

    sentinel = multiproc_dir / "SENTINEL_DO_NOT_TOUCH.txt"
    sentinel.write_text("sentinel", encoding="utf-8")

    live_pid = os.getpid()
    dead_pid = 999999

    dead_file = multiproc_dir / f"counter_{dead_pid}.db"
    live_file = multiproc_dir / f"counter_{live_pid}.db"
    dead_file.write_text("x", encoding="utf-8")
    live_file.write_text("y", encoding="utf-8")

    old = time.time() - 3600
    os.utime(dead_file, (old, old))
    os.utime(live_file, (old, old))

    result = prune_stale_multiproc_shards(
        multiproc_dir=multiproc_dir,
        live_pids={live_pid},
        grace_seconds=600,
        max_shard_files=10_000,
        now_epoch_seconds=time.time(),
    )
    assert result.orphan_db_files_detected >= 1
    assert result.pruned_db_files == 1
    assert not dead_file.exists()
    assert live_file.exists()
    assert sentinel.exists()


def test_eg55_worker_shutdown_hook_calls_mark_process_dead(monkeypatch: pytest.MonkeyPatch):
    import prometheus_client.multiprocess as mp
    from app import celery_app as celery_app_module

    called: list[int] = []

    def _mark(pid: int) -> None:
        called.append(int(pid))

    monkeypatch.setattr(mp, "mark_process_dead", _mark)
    celery_app_module._on_worker_process_shutdown(pid=123)
    assert called == [123]


def test_eg58_task_metrics_labels_are_privacy_safe_and_bounded():
    from prometheus_client import generate_latest
    from app.observability import metrics as metrics_module

    uuidish = "550e8400-e29b-41d4-a716-446655440000"
    metrics_module.celery_task_started_total.labels(task_name=normalize_task_name(uuidish)).inc()
    metrics_module.celery_task_duration_seconds.labels(task_name=normalize_task_name(uuidish)).observe(0.01)

    text = generate_latest().decode("utf-8", errors="replace")
    assert "tenant_id" not in text
    assert UUID_PATTERN.search(text) is None
