from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text

from app.celery_app import celery_app
from app.tasks.bayesian import (
    PRODUCTION_BAYESIAN_SOFT_TIME_LIMIT_S,
    PRODUCTION_BAYESIAN_TIME_LIMIT_S,
)


@dataclass(frozen=True)
class _RuntimeCfg:
    runtime_sync_url: str
    runtime_async_url: str
    artifact_dir: Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _runtime_sync_db_url() -> str:
    explicit = os.getenv("B07_P2_RUNTIME_DATABASE_URL")
    if explicit:
        return explicit
    runtime_url = os.getenv("DATABASE_URL")
    if not runtime_url:
        raise RuntimeError("DATABASE_URL or B07_P2_RUNTIME_DATABASE_URL is required")
    if runtime_url.startswith("postgresql+asyncpg://"):
        return runtime_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return runtime_url


def _runtime_async_db_url(runtime_sync: str) -> str:
    if runtime_sync.startswith("postgresql+asyncpg://"):
        return runtime_sync
    return runtime_sync.replace("postgresql://", "postgresql+asyncpg://", 1)


def _artifact_dir() -> Path:
    explicit = os.getenv("B07_P2_ARTIFACT_DIR")
    if explicit:
        path = Path(explicit)
    else:
        path = _repo_root() / "artifacts" / "b07-p2"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cfg() -> _RuntimeCfg:
    sync = _runtime_sync_db_url()
    return _RuntimeCfg(
        runtime_sync_url=sync,
        runtime_async_url=_runtime_async_db_url(sync),
        artifact_dir=_artifact_dir(),
    )


def _wait_for_output(lines: list[str], substring: str, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if any(substring in line for line in lines):
            return
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for worker output containing {substring!r}")


def _start_worker(env: dict[str, str], log_path: Path) -> tuple[subprocess.Popen[str], list[str]]:
    backend_dir = _repo_root() / "backend"
    prom_dir = Path(tempfile.mkdtemp(prefix="b07_p5_prom_"))
    worker_env = dict(env)
    worker_env.setdefault("PROMETHEUS_MULTIPROC_DIR", str(prom_dir))
    cmd = [
        "celery",
        "-A",
        "app.celery_app.celery_app",
        "worker",
        "-P",
        "prefork",
        "--concurrency",
        "1",
        "-Q",
        "attribution,housekeeping",
        "-l",
        "INFO",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(backend_dir),
        env=worker_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: list[str] = []
    log_fp = log_path.open("w", encoding="utf-8")

    def _reader() -> None:
        if proc.stdout is None:
            return
        for line in proc.stdout:
            clean = line.rstrip()
            lines.append(clean)
            log_fp.write(clean + "\n")
            log_fp.flush()
        log_fp.close()

    threading.Thread(target=_reader, name="b07-p5-worker-reader", daemon=True).start()
    _wait_for_output(lines, "ready.", timeout_s=60)
    return proc, lines


def _stop_process(proc: subprocess.Popen[str]) -> None:
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def _runtime_identity_snapshot(runtime_db_url: str) -> dict[str, str | bool]:
    engine = create_engine(runtime_db_url)
    with engine.begin() as conn:
        current_user = str(conn.execute(text("SELECT current_user")).scalar_one())
        rolsuper = bool(
            conn.execute(
                text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            ).scalar_one()
        )
    return {"current_user": current_user, "rolsuper": rolsuper}


def _read_probe_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def test_b07_p5_bayesian_timeout_contract_real_worker() -> None:
    cfg = _cfg()
    assert celery_app.conf.task_always_eager is False, "Runtime proof requires eager mode disabled"
    assert PRODUCTION_BAYESIAN_SOFT_TIME_LIMIT_S == 270
    assert PRODUCTION_BAYESIAN_TIME_LIMIT_S == 300

    runtime_identity = _runtime_identity_snapshot(cfg.runtime_sync_url)
    expected_runtime_user = os.getenv("RUNTIME_USER", "app_user")
    assert runtime_identity["current_user"] == expected_runtime_user
    assert runtime_identity["rolsuper"] is False

    artifact_dir = cfg.artifact_dir
    worker_log = artifact_dir / "p5_bayesian_worker.log"
    probe_log = artifact_dir / "p5_bayesian_probe.jsonl"
    proof_path = artifact_dir / "p5_bayesian_runtime_proof.json"

    env = os.environ.copy()
    env["DATABASE_URL"] = cfg.runtime_async_url
    env["CELERY_BROKER_URL"] = f"sqla+{cfg.runtime_sync_url}"
    env["CELERY_RESULT_BACKEND"] = f"db+{cfg.runtime_sync_url}"
    env["BAYESIAN_TASK_SOFT_TIME_LIMIT_S"] = "4"
    env["BAYESIAN_TASK_TIME_LIMIT_S"] = "5"
    env["BAYESIAN_PROBE_LOG_PATH"] = str(probe_log.resolve())
    env.setdefault("ENVIRONMENT", "test")

    worker_proc = None
    try:
        worker_proc, _ = _start_worker(env, worker_log)

        run_task_id = f"b07-p5-bayes-runaway-{uuid4().hex[:10]}"
        tenant_id = str(uuid4())
        correlation_id = str(uuid4())
        started = time.monotonic()
        run_result = celery_app.send_task(
            "app.tasks.bayesian.run_mcmc_inference",
            kwargs={
                "tenant_id": tenant_id,
                "correlation_id": correlation_id,
                "run_seconds": 60,
                "continue_after_soft_timeout": True,
            },
            task_id=run_task_id,
            queue="attribution",
        )
        run_error_class = ""
        run_error_message = ""
        try:
            run_result.get(timeout=20)
            raise AssertionError("Expected runaway Bayesian task to be hard-terminated")
        except Exception as exc:  # noqa: BLE001 - expected timeout termination path
            run_error_class = exc.__class__.__name__
            run_error_message = str(exc)
        elapsed_s = time.monotonic() - started
        assert (
            "TimeLimitExceeded" in run_error_class
            or "TimeLimitExceeded" in run_error_message
            or "WorkerLostError" in run_error_class
        )

        deadline = time.time() + 20
        fallback_event = None
        while time.time() < deadline:
            events = _read_probe_events(probe_log)
            fallback_event = next(
                (
                    ev
                    for ev in events
                    if ev.get("event") == "bayesian_soft_timeout_fallback"
                    and ev.get("task_id") == run_task_id
                ),
                None,
            )
            if fallback_event is not None:
                break
            time.sleep(0.2)
        assert fallback_event is not None, "Expected deterministic fallback event before hard kill"

        health_result = None
        health_error = None
        health_task_id = ""
        health_deadline = time.time() + 120
        while time.time() < health_deadline:
            health_task_id = f"b07-p5-health-{uuid4().hex[:10]}"
            try:
                health_async = celery_app.send_task(
                    "app.tasks.bayesian.health_probe",
                    kwargs={"tenant_id": str(uuid4()), "correlation_id": str(uuid4())},
                    task_id=health_task_id,
                    queue="attribution",
                )
                health_result = health_async.get(timeout=15)
                if isinstance(health_result, dict) and health_result.get("status") == "ok":
                    break
            except Exception as exc:  # noqa: BLE001 - worker may still be respawning after hard kill
                health_error = exc
                events = _read_probe_events(probe_log)
                if any(
                    ev.get("event") == "bayesian_health_probe_ok" and ev.get("task_id") == health_task_id
                    for ev in events
                ):
                    health_result = {"status": "ok", "task_id": health_task_id}
                    break
                time.sleep(2)
        assert isinstance(health_result, dict), f"Expected health probe result, got error: {health_error}"
        assert health_result.get("status") == "ok"

        proof_path.write_text(
            json.dumps(
                {
                    "production_limits": {
                        "soft_time_limit_s": PRODUCTION_BAYESIAN_SOFT_TIME_LIMIT_S,
                        "time_limit_s": PRODUCTION_BAYESIAN_TIME_LIMIT_S,
                    },
                    "runtime_test_limits": {"soft_time_limit_s": 4, "time_limit_s": 5},
                    "runtime_identity": runtime_identity,
                    "runaway_task_id": run_task_id,
                    "runaway_elapsed_s": elapsed_s,
                    "runaway_error_class": run_error_class,
                    "runaway_error_message": run_error_message,
                    "fallback_event": fallback_event,
                    "health_probe": health_result,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    finally:
        if worker_proc is not None:
            _stop_process(worker_proc)
