"""Process-group supervisor for B2.4-P5 sampler children."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class SupervisedSamplerResult:
    status: str
    child_pid: int
    elapsed_seconds: float
    killed_by_supervisor: bool
    returncode: int | None
    orphan_reaped: bool


def _popen_kwargs() -> dict[str, object]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


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
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def run_supervised_sampler(command: list[str], *, deadline_seconds: float) -> SupervisedSamplerResult:
    """Run a sampler child under an OS-enforced process deadline."""

    if deadline_seconds <= 0:
        raise ValueError("deadline_seconds must be positive")
    started = time.monotonic()
    proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **_popen_kwargs())
    killed = False
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
