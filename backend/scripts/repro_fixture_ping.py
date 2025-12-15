#!/usr/bin/env python3
"""
Reproduce fixture control-plane ping behavior outside pytest.
Tests whether Popen-spawned worker responds to celery_app.control.ping().
"""
import os
import subprocess
import sys
import time
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

# Set environment before importing celery_app
os.environ["DATABASE_URL"] = "postgresql+asyncpg://app_user:app_user@127.0.0.1:5432/skeldir_validation"
os.environ["CELERY_BROKER_URL"] = "sqla+postgresql://app_user:app_user@127.0.0.1:5432/skeldir_validation"
os.environ["CELERY_RESULT_BACKEND"] = "db+postgresql://app_user:app_user@127.0.0.1:5432/skeldir_validation"
os.environ["CELERY_METRICS_PORT"] = "9546"
os.environ["CELERY_METRICS_ADDR"] = "127.0.0.1"

from app.celery_app import celery_app

def main():
    print(f"[REPRO] Starting worker subprocess...")
    print(f"[REPRO] broker_url: {celery_app.conf.broker_url}")
    print(f"[REPRO] result_backend: {celery_app.conf.result_backend}")

    # Spawn worker exactly like fixture does
    env = os.environ.copy()
    env["PYTHONPATH"] = str(backend_dir.parent)

    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "app.celery_app",
        "worker",
        "-P",
        "solo",
        "-c",
        "1",
        "--loglevel=INFO",
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=backend_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    print(f"[REPRO] Worker PID: {proc.pid}")

    # Poll for 60s like fixture does
    timeout_seconds = 60
    poll_interval = 2
    elapsed = 0

    try:
        while elapsed < timeout_seconds:
            time.sleep(poll_interval)
            elapsed += poll_interval

            # Check if worker is still alive
            if proc.poll() is not None:
                print(f"[REPRO] {elapsed}s - Worker died! Exit code: {proc.returncode}")
                break

            # Try control ping
            result = celery_app.control.ping(timeout=5)
            print(f"[REPRO] {elapsed}s - control.ping() = {result}")

            if result:
                print(f"[REPRO] SUCCESS: Worker responded after {elapsed}s")
                break
        else:
            print(f"[REPRO] TIMEOUT: No response after {timeout_seconds}s")

    finally:
        print(f"[REPRO] Terminating worker...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

        print(f"[REPRO] Worker stdout (first 50 lines):")
        stdout, _ = proc.communicate()
        if stdout:
            lines = stdout.split('\n')[:50]
            for line in lines:
                print(f"  {line}")

if __name__ == "__main__":
    main()
