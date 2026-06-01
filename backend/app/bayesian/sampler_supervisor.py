"""Process-group supervisor for B2.4-P5 sampler children."""

from __future__ import annotations

import argparse
import ctypes
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.bayesian.child_environment import build_sampler_child_env
from app.bayesian.compiledir_reaper import (
    CompiledirLease,
    cleanup_compiledir,
    record_child_pid,
)


@dataclass(frozen=True)
class SupervisedSamplerResult:
    status: str
    child_pid: int
    elapsed_seconds: float
    killed_by_supervisor: bool
    returncode: int | None
    orphan_reaped: bool


def _linux_pdeathsig() -> None:
    libc = ctypes.CDLL("libc.so.6")
    pr_set_pdeathsig = 1
    if libc.prctl(pr_set_pdeathsig, signal.SIGKILL) != 0:
        raise OSError("failed to apply PR_SET_PDEATHSIG")


def _popen_kwargs() -> dict[str, object]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP, "close_fds": True}
    return {
        "start_new_session": True,
        "close_fds": True,
        "preexec_fn": _linux_pdeathsig,
    }


def _kill_process_tree(proc: subprocess.Popen[object]) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
            )
        except subprocess.TimeoutExpired:
            proc.kill()
        return
    os.killpg(proc.pid, signal.SIGKILL)


def _process_is_alive(pid: int) -> bool:
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                text=True,
                capture_output=True,
                check=False,
                timeout=5,
            )
        except subprocess.TimeoutExpired:
            return True
        return str(pid) in result.stdout
    try:
        result = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0 and "Z" in result.stdout:
            return False
    except Exception:
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def run_supervised_sampler(
    command: list[str],
    *,
    deadline_seconds: float,
    env: dict[str, str] | None = None,
    compiledir_lease: CompiledirLease | None = None,
) -> SupervisedSamplerResult:
    """Run a sampler child under an OS-enforced process deadline."""

    if deadline_seconds <= 0:
        raise ValueError("deadline_seconds must be positive")
    started = time.monotonic()
    proc = launch_sampler_child(command, env=env)
    if compiledir_lease is not None:
        compiledir_lease = record_child_pid(compiledir_lease, proc.pid)
    killed = False
    try:
        while proc.poll() is None:
            if time.monotonic() - started >= deadline_seconds:
                killed = True
                _kill_process_tree(proc)
                break
            time.sleep(0.02)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc)
            proc.wait(timeout=2)
        elapsed = time.monotonic() - started
        alive = proc.poll() is None and _process_is_alive(proc.pid)
        return SupervisedSamplerResult(
            status="timeout" if killed else "completed",
            child_pid=proc.pid,
            elapsed_seconds=elapsed,
            killed_by_supervisor=killed,
            returncode=proc.returncode,
            orphan_reaped=not alive,
        )
    finally:
        if compiledir_lease is not None and compiledir_lease.path.exists():
            cleanup_compiledir(compiledir_lease)


def launch_sampler_child(
    command: list[str], *, env: dict[str, str] | None = None
) -> subprocess.Popen[object]:
    """Launch a sampler child with descriptor isolation and parent-death signal."""

    return subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        **_popen_kwargs(),
    )


def sampler_child_command(
    *,
    mode: str,
    output: Path | None = None,
    marker: Path | None = None,
    seconds: int = 60,
) -> list[str]:
    bootstrap = Path(__file__).with_name("sampler_child_bootstrap.py")
    command = [
        sys.executable,
        str(bootstrap),
        "--mode",
        mode,
        "--seconds",
        str(seconds),
    ]
    if output is not None:
        command.extend(["--output", str(output)])
    if marker is not None:
        command.extend(["--marker", str(marker)])
    return command


def build_child_env_for_lease(
    lease: CompiledirLease, *, source_env: dict[str, str] | None = None
) -> dict[str, str]:
    return build_sampler_child_env(
        compiledir=lease.path,
        execution_id=lease.execution_id,
        source_env=source_env,
    )


def synthetic_blocking_child_command(*, seconds: int = 60) -> list[str]:
    return [
        sys.executable,
        "-m",
        "app.bayesian.sampler_supervisor",
        "--synthetic-blocking-child",
        "--seconds",
        str(seconds),
        "--token",
        uuid4().hex,
    ]


def _run_synthetic_blocking_child(seconds: int) -> int:
    if os.name != "nt":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    deadline = time.monotonic() + seconds
    marker_raw = os.getenv("B24_SYNTHETIC_CHILD_MARKER")
    if marker_raw:
        marker = Path(marker_raw)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(os.getpid()), encoding="utf-8")
    while time.monotonic() < deadline:
        time.sleep(0.2)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic-blocking-child", action="store_true")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--token", default="")
    args = parser.parse_args()
    if args.synthetic_blocking_child:
        return _run_synthetic_blocking_child(args.seconds)
    parser.error("no supervisor mode selected")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
