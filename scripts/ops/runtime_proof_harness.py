"""Run the non-vacuous M4 local diagnostic proof chain."""

from __future__ import annotations

import subprocess
import sys

from common import emit


PROOF_STEPS = (
    ("seed", ("scripts/ops/seed_diagnostics.py",)),
    ("dlq_positive", ("scripts/ops/dlq_inspect.py",)),
    ("dlq_missing_negative", ("scripts/ops/dlq_inspect.py", "--missing-control")),
    ("rls_physical_boundary", ("scripts/ops/rls_check.py",)),
    ("b23_positive", ("scripts/ops/b23_trace.py",)),
    ("b23_unknown_negative", ("scripts/ops/b23_trace.py", "--unknown-control")),
    ("webhook_valid_tampered_duplicate", ("scripts/ops/webhook_replay_local.py", "--mode", "all")),
)

EXPECTED_FAILURE_STEPS = (
    (
        "webhook_unsafe_target_negative",
        (
            "scripts/ops/webhook_replay_local.py",
            "--mode",
            "valid",
            "--api-base-url",
            "https://api.skeldir.invalid",
        ),
        "production payload replay is forbidden in M4",
    ),
)


def _run(label: str, args: tuple[str, ...]) -> dict[str, object]:
    proc = subprocess.run(
        [sys.executable, *args],
        text=True,
        capture_output=True,
        timeout=120,
    )
    result = {
        "label": label,
        "returncode": proc.returncode,
        "stdout_excerpt": proc.stdout[-2000:],
        "stderr_excerpt": proc.stderr[-2000:],
    }
    if proc.returncode != 0:
        emit({"status": "failed", "failed_step": result})
        raise SystemExit(proc.returncode)
    return result


def _run_expected_failure(
    label: str,
    args: tuple[str, ...],
    required_message: str,
) -> dict[str, object]:
    proc = subprocess.run(
        [sys.executable, *args],
        text=True,
        capture_output=True,
        timeout=120,
    )
    combined = f"{proc.stdout}\n{proc.stderr}"
    result = {
        "label": label,
        "returncode": proc.returncode,
        "stdout_excerpt": proc.stdout[-2000:],
        "stderr_excerpt": proc.stderr[-2000:],
        "expected_failure": required_message,
    }
    if proc.returncode == 0 or required_message not in combined:
        emit({"status": "failed", "failed_expected_negative_step": result})
        raise SystemExit(1)
    return result


def main() -> None:
    results: list[dict[str, object]] = []
    negative_results: list[dict[str, object]] = []
    cleanup: dict[str, object] | None = None
    seeded = False
    try:
        for label, args in PROOF_STEPS:
            results.append(_run(label, args))
            if label == "seed":
                seeded = True
        for label, args, required_message in EXPECTED_FAILURE_STEPS:
            negative_results.append(_run_expected_failure(label, args, required_message))
    finally:
        if seeded:
            cleanup = _run("cleanup", ("scripts/ops/clear_diagnostics.py",))
    emit(
        {
            "status": "ok",
            "fixture_class": "local_only_run_scoped",
            "proof_steps": results,
            "expected_negative_steps": negative_results,
            "cleanup": cleanup,
        }
    )


if __name__ == "__main__":
    main()
