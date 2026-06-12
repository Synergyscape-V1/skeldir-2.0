from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen


@dataclass(frozen=True)
class ProcHandle:
    proc: subprocess.Popen[str]
    output_lines: list[str]


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def wait_for_substring(
    lines: list[str],
    substring: str,
    *,
    timeout_s: float = 60.0,
    proc: subprocess.Popen[str] | None = None,
) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if any(substring in line for line in lines):
            return
        if proc is not None and proc.poll() is not None:
            raise AssertionError(
                f"Process exited before emitting {substring!r}. Last output:\n"
                + "\n".join(lines[-50:])
            )
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for process output containing {substring!r}")


def wait_for_http_200(url: str, *, timeout_s: float = 20.0) -> bytes:
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


def _start_process(
    *,
    cmd: list[str],
    cwd: Path,
    env: dict[str, str],
    ready_substring: str | None = None,
    ready_timeout_s: float = 60.0,
) -> ProcHandle:
    proc: subprocess.Popen[str] = subprocess.Popen(  # noqa: S603
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    lines: list[str] = []

    def _reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))

    threading.Thread(target=_reader, name=f"proc-reader-{cmd[0]}", daemon=True).start()

    if ready_substring:
        wait_for_substring(lines, ready_substring, timeout_s=ready_timeout_s, proc=proc)

    return ProcHandle(proc=proc, output_lines=lines)


def terminate_process(proc: subprocess.Popen[str], *, timeout_s: float = 20.0) -> None:
    if proc.poll() is not None:
        return

    try:
        proc.terminate()
    except Exception:
        # Process may have already exited between poll() and terminate(), or may
        # not support terminate on this platform.
        pass
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        proc.wait(timeout=timeout_s)


@dataclass
class MetricsTopology:
    api_url: str
    exporter_url: str
    multiproc_dir: Path
    worker_queue: str
    api: ProcHandle
    worker: ProcHandle
    exporter: ProcHandle


def start_metrics_topology(
    *,
    tmp_path: Path,
    worker_queue: str,
    api_env_overrides: dict[str, str] | None = None,
) -> MetricsTopology:
    backend_dir = Path(__file__).resolve().parents[1]

    multiproc_dir = tmp_path / "prom_multiproc"
    multiproc_dir.mkdir(parents=True, exist_ok=True)

    exporter_port = pick_free_port()
    api_port = pick_free_port()

    base_env = dict(os.environ)
    base_env.setdefault("PYTHONUNBUFFERED", "1")
    base_env.setdefault("TESTING", "1")

    worker_env = dict(base_env)
    worker_env.update(
        {
            "PROMETHEUS_MULTIPROC_DIR": str(multiproc_dir),
        }
    )

    pool = "prefork" if os.name != "nt" else "solo"
    worker_cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "app.celery_app.celery_app",
        "worker",
        "-P",
        pool,
        "-c",
        "1",
        "-Q",
        f"{worker_queue},housekeeping",
        "--without-gossip",
        "--without-mingle",
        "--without-heartbeat",
        "--loglevel=INFO",
    ]

    worker = _start_process(cmd=worker_cmd, cwd=backend_dir, env=worker_env, ready_substring="ready.", ready_timeout_s=120)

    exporter_env = dict(base_env)
    exporter_env.update(
        {
            "PROMETHEUS_MULTIPROC_DIR": str(multiproc_dir),
            "WORKER_METRICS_EXPORTER_HOST": "127.0.0.1",
            "WORKER_METRICS_EXPORTER_PORT": str(exporter_port),
        }
    )
    exporter_cmd = [sys.executable, "-m", "app.observability.worker_metrics_exporter"]
    exporter = _start_process(cmd=exporter_cmd, cwd=backend_dir, env=exporter_env)
    exporter_url = f"http://127.0.0.1:{exporter_port}"
    wait_for_http_200(f"{exporter_url}/metrics", timeout_s=20.0)

    api_env = dict(base_env)
    api_env.update(
        {
            # B0.5.6.7: provide PROMETHEUS_MULTIPROC_DIR but API entrypoint strips it.
            "PROMETHEUS_MULTIPROC_DIR": str(multiproc_dir),
            "BROKER_QUEUE_STATS_CACHE_TTL_SECONDS": "0",
        }
    )
    if api_env_overrides:
        api_env.update(api_env_overrides)
    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(api_port),
        "--log-level",
        "warning",
    ]
    api = _start_process(cmd=api_cmd, cwd=backend_dir, env=api_env)
    api_url = f"http://127.0.0.1:{api_port}"
    wait_for_http_200(f"{api_url}/health/live", timeout_s=30.0)

    return MetricsTopology(
        api_url=api_url,
        exporter_url=exporter_url,
        multiproc_dir=multiproc_dir,
        worker_queue=worker_queue,
        api=api,
        worker=worker,
        exporter=exporter,
    )


def stop_metrics_topology(topology: MetricsTopology) -> None:
    for handle in (topology.api, topology.exporter, topology.worker):
        terminate_process(handle.proc, timeout_s=30.0)


def ensure_worker_running(topology: MetricsTopology) -> None:
    if topology.worker.proc.poll() is None:
        return

    backend_dir = Path(__file__).resolve().parents[1]

    base_env = dict(os.environ)
    base_env.setdefault("PYTHONUNBUFFERED", "1")
    base_env.setdefault("TESTING", "1")

    worker_env = dict(base_env)
    worker_env.update(
        {
            "PROMETHEUS_MULTIPROC_DIR": str(topology.multiproc_dir),
        }
    )

    pool = "prefork" if os.name != "nt" else "solo"
    worker_cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "app.celery_app.celery_app",
        "worker",
        "-P",
        pool,
        "-c",
        "1",
        "-Q",
        f"{topology.worker_queue},housekeeping",
        "--without-gossip",
        "--without-mingle",
        "--without-heartbeat",
        "--loglevel=INFO",
    ]

    topology.worker = _start_process(cmd=worker_cmd, cwd=backend_dir, env=worker_env, ready_substring="ready.", ready_timeout_s=120)
