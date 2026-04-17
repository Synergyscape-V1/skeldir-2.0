from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "ci" / "enforce_b21_p4_benchmark_adjudication.py"


def _run_enforcer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_script_path()), *args],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )


def _base_payload(*, topology_mode: str, elapsed_seconds: float) -> dict[str, Any]:
    return {
        "schema_version": "b21_p4_queue_isolation_benchmark.v1",
        "mode": "measure",
        "topology_mode": topology_mode,
        "contention_mode": "real",
        "timing_boundary": "enqueue_to_durable_commit",
        "dispatch_mode": "celery_send_task",
        "task_always_eager": False,
        "broker_url": "sqla+postgresql://app_user:app_user@127.0.0.1:5432/skeldir",
        "result_backend": "db+postgresql://app_user:app_user@127.0.0.1:5432/skeldir",
        "event_count": 10000,
        "deterministic": {
            "task_name": "app.tasks.attribution.recompute_window",
            "elapsed_seconds": elapsed_seconds,
            "job_id": "11111111-1111-1111-1111-111111111111",
            "job_status": "succeeded",
            "allocation_count": 5000,
        },
        "contention": {
            "task_name": "app.tasks.bayesian.run_resource_contention",
            "error": "",
            "result": {
                "status": "completed",
                "db_queries": 45,
                "iterations": 10,
            },
        },
        "read_path": {
            "status_code": 200,
            "projection_recompute_job_id": "11111111-1111-1111-1111-111111111111",
            "recompute_mutation_detected": False,
        },
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_b21_p4_benchmark_adjudication_passes_with_valid_payloads(
    tmp_path: Path,
) -> None:
    isolated = tmp_path / "isolated.json"
    corouted = tmp_path / "corouted.json"
    _write(isolated, _base_payload(topology_mode="isolated", elapsed_seconds=4.1))
    _write(
        corouted,
        _base_payload(topology_mode="corouted_shared_worker", elapsed_seconds=7.2),
    )

    result = _run_enforcer(
        "--isolated-file", str(isolated), "--corouted-file", str(corouted)
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b21_p4_benchmark_adjudication_fails_when_isolated_sla_regresses(
    tmp_path: Path,
) -> None:
    isolated = tmp_path / "isolated.slow.json"
    corouted = tmp_path / "corouted.json"
    _write(isolated, _base_payload(topology_mode="isolated", elapsed_seconds=5.7))
    _write(
        corouted,
        _base_payload(topology_mode="corouted_shared_worker", elapsed_seconds=7.0),
    )

    result = _run_enforcer(
        "--isolated-file", str(isolated), "--corouted-file", str(corouted)
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "isolated_elapsed_not_under_threshold" in combined


def test_b21_p4_benchmark_adjudication_fails_when_corouted_negative_control_missing(
    tmp_path: Path,
) -> None:
    isolated = tmp_path / "isolated.json"
    corouted = tmp_path / "corouted.fast.json"
    _write(isolated, _base_payload(topology_mode="isolated", elapsed_seconds=4.0))
    _write(
        corouted,
        _base_payload(topology_mode="corouted_shared_worker", elapsed_seconds=4.2),
    )

    result = _run_enforcer(
        "--isolated-file", str(isolated), "--corouted-file", str(corouted)
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "corouted_negative_control_not_triggered" in combined


def test_b21_p4_benchmark_adjudication_fails_on_eager_cheat(tmp_path: Path) -> None:
    isolated_payload = _base_payload(topology_mode="isolated", elapsed_seconds=4.1)
    isolated_payload["dispatch_mode"] = "eager_apply"
    isolated_payload["task_always_eager"] = True
    corouted_payload = _base_payload(
        topology_mode="corouted_shared_worker", elapsed_seconds=7.0
    )

    isolated = tmp_path / "isolated.eager.json"
    corouted = tmp_path / "corouted.json"
    _write(isolated, isolated_payload)
    _write(corouted, corouted_payload)

    result = _run_enforcer(
        "--isolated-file", str(isolated), "--corouted-file", str(corouted)
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "isolated_dispatch_mode_not_celery_send_task" in combined
    assert "isolated_task_always_eager_enabled" in combined


def test_b21_p4_benchmark_adjudication_fails_on_fake_contention(tmp_path: Path) -> None:
    isolated_payload = _base_payload(topology_mode="isolated", elapsed_seconds=4.0)
    isolated_payload["contention_mode"] = "fake_sleep"
    isolated_payload["contention"][
        "task_name"
    ] = "app.tasks.bayesian.run_mcmc_inference"
    isolated_payload["contention"]["result"]["db_queries"] = 0
    isolated_payload["contention"]["result"]["iterations"] = 0

    isolated = tmp_path / "isolated.fake-contention.json"
    corouted = tmp_path / "corouted.json"
    _write(isolated, isolated_payload)
    _write(
        corouted,
        _base_payload(topology_mode="corouted_shared_worker", elapsed_seconds=7.0),
    )

    result = _run_enforcer(
        "--isolated-file", str(isolated), "--corouted-file", str(corouted)
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "isolated_contention_mode_not_real" in combined
    assert "isolated_contention_task_not_resource_real" in combined
    assert "isolated_contention_db_queries_below_min" in combined


def test_b21_p4_benchmark_adjudication_fails_on_read_path_recompute_regression(
    tmp_path: Path,
) -> None:
    isolated_payload = _base_payload(topology_mode="isolated", elapsed_seconds=4.0)
    isolated_payload["read_path"]["recompute_mutation_detected"] = True
    corouted_payload = _base_payload(
        topology_mode="corouted_shared_worker", elapsed_seconds=7.1
    )

    isolated = tmp_path / "isolated.read-regression.json"
    corouted = tmp_path / "corouted.json"
    _write(isolated, isolated_payload)
    _write(corouted, corouted_payload)

    result = _run_enforcer(
        "--isolated-file", str(isolated), "--corouted-file", str(corouted)
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "isolated_read_path_recompute_mutation_detected" in combined
