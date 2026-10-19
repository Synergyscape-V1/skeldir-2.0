"""Fail-closed contract for the Phase 8 composed instrumentation.

The gate must refuse authoritative composed evidence when the load helper is
missing or failed, when its interval does not cover the R3 authority window,
or when conduction is absent. These tests pin the attempt-3 false green
(missing load-helper artifact, null perf window, zero LLM calls, no drain,
no activity evidence) as a RED signature.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest


def _load_pack_module():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "phase8" / "run_phase8_closure_pack.py"
    spec = importlib.util.spec_from_file_location("phase8_closure_pack", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PACK = _load_pack_module()

_WINDOW_START = "2026-10-18T14:59:48.000000+00:00"
_WINDOW_END = "2026-10-18T15:00:48.000000+00:00"
_PROBE_START = "2026-10-18T14:57:48.000000+00:00"
_PROBE_FINISH = "2026-10-18T15:01:48.000000+00:00"
_LOAD_START = "2026-10-18T14:57:30.000000+00:00"
_LOAD_FINISH = "2026-10-18T15:06:45.000000+00:00"


def _r3_profile() -> dict[str, Any]:
    return {
        "window_start_utc": _WINDOW_START,
        "window_end_utc": _WINDOW_END,
    }


def _worker_probe(
    *, started: str = _PROBE_START, finished: str = _PROBE_FINISH
) -> dict[str, Any]:
    return {
        "started_at": started,
        "finished_at": finished,
        "summary": {
            "sample_count": 479,
            "max_total_messages": 7467,
            "final_total_messages": 7467,
        },
    }


def _write_load_artifact(
    tmp_path: Path,
    *,
    status: str = "ok",
    error: str | None = None,
    dispatch_mode: str = "inline",
    dispatched_count: int = 60,
    started_at: str = _LOAD_START,
    finished_at: str = _LOAD_FINISH,
) -> Path:
    artifact = tmp_path / "phase8_llm_perf_probe.json"
    artifact.write_text(
        json.dumps(
            {
                "status": status,
                "error": error,
                "dispatch_mode": dispatch_mode,
                "task_name": "app.tasks.llm.explanation",
                "dispatched_count": dispatched_count,
                "started_at": started_at,
                "finished_at": finished_at,
            }
        ),
        encoding="utf-8",
    )
    return artifact


def _write_cpu_probe(
    tmp_path: Path,
    *,
    status: str = "ok",
    error: str | None = None,
    sample_count: int = 90,
) -> Path:
    artifact = tmp_path / "phase8_runner_cpu_probe.json"
    artifact.write_text(
        json.dumps(
            {
                "status": status,
                "error": error,
                "sample_count": sample_count,
                "total_busy_pct_avg": 71.2,
                "psi_cpu_some_stall_us_total": 123456.7,
                "classes": {"generator": {"cpu_pct_avg": 24.0}},
            }
        ),
        encoding="utf-8",
    )
    return artifact


def _write_pg_stat_probe(
    tmp_path: Path,
    *,
    status: str = "ok",
    error: str | None = None,
    sample_count: int = 90,
    pgss_available: bool = True,
    pgss_error: str | None = None,
) -> Path:
    artifact = tmp_path / "phase8_pg_stat_probe.json"
    artifact.write_text(
        json.dumps(
            {
                "status": status,
                "error": error,
                "sample_count": sample_count,
                "interval_s": 5.0,
                "pgss_available": pgss_available,
                "pgss_error": pgss_error,
                "extversion": "1.10" if pgss_available else None,
                "track_setting": "all" if pgss_available else None,
                "totals_first": {"statements": 150, "calls": 10, "total_exec_ms": 1.0},
                "totals_last": {"statements": 160, "calls": 4000, "total_exec_ms": 900.0},
                # Synthetic probe-artifact fixture: the query text below is a
                # fake pg_stat_statements row used to exercise the composed-
                # instrumentation validator; it is never executed.
                "top_statements_by_delta": [
                    {
                        "qid": "1",
                        # RAW_SQL_ALLOWLIST: fixture text only, never executed.
                        "q": "INSERT INTO attribution_events ...",
                        "calls": 3990,
                        "total_exec_ms": 899.0,
                        "mean_exec_ms": 0.2253,
                        "rows": 3990,
                        "toplevel": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return artifact


def _validate(
    tmp_path: Path,
    *,
    full_physics: bool = True,
    llm_load_artifact: Path | None = None,
    llm_load_returncode: int = 0,
    queue_probe_returncode: int = 0,
    cpu_probe_artifact: Path | None = None,
    cpu_probe_returncode: int = 0,
    pg_stat_probe_artifact: Path | None = None,
    pg_stat_probe_returncode: int = 0,
    worker_probe: dict[str, Any] | None = None,
    r3_profile: dict[str, Any] | None = None,
    perf_llm_calls: int = 55,
) -> dict[str, Any]:
    llm_log = tmp_path / "llm_background_load.log"
    llm_log.write_text("load helper ok\n", encoding="utf-8")
    queue_log = tmp_path / "queue_liveness_probe.log"
    queue_log.write_text("queue probe ok\n", encoding="utf-8")
    cpu_log = tmp_path / "runner_cpu_probe.log"
    cpu_log.write_text("cpu probe ok\n", encoding="utf-8")
    pg_stat_log = tmp_path / "pg_stat_probe.log"
    pg_stat_log.write_text("pg_stat probe ok\n", encoding="utf-8")
    if cpu_probe_artifact is None:
        cpu_probe_artifact = _write_cpu_probe(tmp_path)
    if pg_stat_probe_artifact is None:
        pg_stat_probe_artifact = _write_pg_stat_probe(tmp_path)
    return _PACK._validate_composed_instrumentation(
        full_physics=full_physics,
        llm_load_artifact=llm_load_artifact
        or (tmp_path / "phase8_llm_perf_probe.json"),
        llm_load_log=llm_log,
        queue_probe_log=queue_log,
        cpu_probe_artifact=cpu_probe_artifact,
        cpu_probe_log=cpu_log,
        pg_stat_probe_artifact=pg_stat_probe_artifact,
        pg_stat_probe_log=pg_stat_log,
        llm_load_returncode=llm_load_returncode,
        queue_probe_returncode=queue_probe_returncode,
        cpu_probe_returncode=cpu_probe_returncode,
        pg_stat_probe_returncode=pg_stat_probe_returncode,
        worker_probe=worker_probe if worker_probe is not None else _worker_probe(),
        r3_profile=r3_profile if r3_profile is not None else _r3_profile(),
        perf_llm_calls=perf_llm_calls,
    )


def test_attempt3_false_green_signature_missing_artifact_fails_closed(
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="artifact missing"):
        _validate(tmp_path, perf_llm_calls=0)


def test_failed_helper_returncode_fails_closed_with_log_tail(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path, dispatched_count=0)
    llm_log = tmp_path / "llm_background_load.log"
    llm_log.write_text("Traceback: provider boundary init failed\n", encoding="utf-8")
    cpu_artifact = _write_cpu_probe(tmp_path)
    cpu_log = tmp_path / "runner_cpu_probe.log"
    cpu_log.write_text("cpu probe ok\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="exited with code 2") as excinfo:
        _PACK._validate_composed_instrumentation(
            full_physics=True,
            llm_load_artifact=artifact,
            llm_load_log=llm_log,
            queue_probe_log=tmp_path / "queue.log",
            cpu_probe_artifact=cpu_artifact,
            cpu_probe_log=cpu_log,
            pg_stat_probe_artifact=_write_pg_stat_probe(tmp_path),
            pg_stat_probe_log=tmp_path / "pg_stat.log",
            llm_load_returncode=2,
            queue_probe_returncode=0,
            cpu_probe_returncode=0,
            pg_stat_probe_returncode=0,
            worker_probe=_worker_probe(),
            r3_profile=_r3_profile(),
            perf_llm_calls=0,
        )
    assert "provider boundary init failed" in str(excinfo.value)


def test_missing_runner_cpu_probe_artifact_fails_closed(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path)
    with pytest.raises(RuntimeError, match="runner CPU probe artifact missing"):
        _validate(
            tmp_path,
            llm_load_artifact=artifact,
            cpu_probe_artifact=tmp_path / "absent_runner_cpu_probe.json",
        )


def test_failed_runner_cpu_probe_fails_closed_with_log_tail(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path)
    cpu_log = tmp_path / "runner_cpu_probe.log"
    cpu_log.write_text("Traceback: /proc scan failed\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="runner_cpu_probe.py exited") as excinfo:
        _PACK._validate_composed_instrumentation(
            full_physics=True,
            llm_load_artifact=artifact,
            llm_load_log=tmp_path / "llm.log",
            queue_probe_log=tmp_path / "queue.log",
            cpu_probe_artifact=tmp_path / "phase8_runner_cpu_probe.json",
            cpu_probe_log=cpu_log,
            pg_stat_probe_artifact=_write_pg_stat_probe(tmp_path),
            pg_stat_probe_log=tmp_path / "pg_stat.log",
            llm_load_returncode=0,
            queue_probe_returncode=0,
            cpu_probe_returncode=3,
            pg_stat_probe_returncode=0,
            worker_probe=_worker_probe(),
            r3_profile=_r3_profile(),
            perf_llm_calls=42,
        )
    assert "/proc scan failed" in str(excinfo.value)


def test_runner_cpu_probe_non_ok_status_fails_closed(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path)
    cpu_artifact = _write_cpu_probe(
        tmp_path, status="failed", error="insufficient samples"
    )
    with pytest.raises(RuntimeError, match="runner CPU probe status='failed'"):
        _validate(
            tmp_path,
            llm_load_artifact=artifact,
            cpu_probe_artifact=cpu_artifact,
        )


def test_runner_cpu_probe_insufficient_samples_fails_closed(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path)
    cpu_artifact = _write_cpu_probe(tmp_path, sample_count=1)
    with pytest.raises(RuntimeError, match="fewer"):
        _validate(
            tmp_path,
            llm_load_artifact=artifact,
            cpu_probe_artifact=cpu_artifact,
        )


def test_missing_pg_stat_probe_artifact_fails_closed(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path)
    with pytest.raises(RuntimeError, match="pg_stat probe artifact missing"):
        _validate(
            tmp_path,
            llm_load_artifact=artifact,
            pg_stat_probe_artifact=tmp_path / "absent_pg_stat_probe.json",
        )


def test_failed_pg_stat_probe_fails_closed_with_log_tail(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path)
    pg_stat_log = tmp_path / "pg_stat_probe.log"
    pg_stat_log.write_text("Traceback: connection refused\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="pg_stat_probe.py exited") as excinfo:
        _PACK._validate_composed_instrumentation(
            full_physics=True,
            llm_load_artifact=artifact,
            llm_load_log=tmp_path / "llm.log",
            queue_probe_log=tmp_path / "queue.log",
            cpu_probe_artifact=_write_cpu_probe(tmp_path),
            cpu_probe_log=tmp_path / "cpu.log",
            pg_stat_probe_artifact=tmp_path / "phase8_pg_stat_probe.json",
            pg_stat_probe_log=pg_stat_log,
            llm_load_returncode=0,
            queue_probe_returncode=0,
            cpu_probe_returncode=0,
            pg_stat_probe_returncode=2,
            worker_probe=_worker_probe(),
            r3_profile=_r3_profile(),
            perf_llm_calls=42,
        )
    assert "connection refused" in str(excinfo.value)


def test_pg_stat_probe_unavailable_fails_closed(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path)
    pg_stat_artifact = _write_pg_stat_probe(
        tmp_path,
        status="failed",
        error="pg_stat_statements unavailable",
        pgss_available=False,
        pgss_error="ProgrammingError: relation does not exist",
    )
    with pytest.raises(RuntimeError, match="pg_stat_statements unavailable"):
        _validate(
            tmp_path,
            llm_load_artifact=artifact,
            pg_stat_probe_artifact=pg_stat_artifact,
        )


def test_pg_stat_probe_non_ok_status_fails_closed(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path)
    pg_stat_artifact = _write_pg_stat_probe(
        tmp_path, status="failed", error="insufficient samples"
    )
    with pytest.raises(RuntimeError, match="pg_stat probe status='failed'"):
        _validate(
            tmp_path,
            llm_load_artifact=artifact,
            pg_stat_probe_artifact=pg_stat_artifact,
        )


def test_pg_stat_probe_insufficient_samples_fails_closed(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path)
    pg_stat_artifact = _write_pg_stat_probe(tmp_path, sample_count=1)
    with pytest.raises(RuntimeError, match="pg_stat probe recorded fewer"):
        _validate(
            tmp_path,
            llm_load_artifact=artifact,
            pg_stat_probe_artifact=pg_stat_artifact,
        )


def test_failed_queue_probe_fails_closed(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path)
    with pytest.raises(RuntimeError, match="queue_liveness_probe.py exited"):
        _validate(
            tmp_path,
            llm_load_artifact=artifact,
            queue_probe_returncode=1,
        )


def test_non_ok_load_artifact_status_fails_closed(tmp_path: Path) -> None:
    artifact = _write_load_artifact(
        tmp_path, status="failed", error="OperationalError: connection refused"
    )
    with pytest.raises(RuntimeError, match="load-helper status='failed'"):
        _validate(tmp_path, llm_load_artifact=artifact)


def test_zero_dispatches_fails_closed(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path, dispatched_count=0)
    with pytest.raises(RuntimeError, match="dispatched zero calls"):
        _validate(tmp_path, llm_load_artifact=artifact)


def test_stale_interval_fails_closed(tmp_path: Path) -> None:
    artifact = _write_load_artifact(
        tmp_path,
        started_at="2026-10-18T14:55:00.000000+00:00",
        finished_at="2026-10-18T14:57:00.000000+00:00",
    )
    with pytest.raises(RuntimeError, match="stale or mismatched load interval"):
        _validate(tmp_path, llm_load_artifact=artifact)


def test_broker_dispatch_mode_fails_closed(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path, dispatch_mode="broker")
    with pytest.raises(RuntimeError, match="certified inline dispatch"):
        _validate(tmp_path, llm_load_artifact=artifact)


def test_absent_conduction_fails_closed(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path)
    with pytest.raises(RuntimeError, match="absent conduction"):
        _validate(tmp_path, llm_load_artifact=artifact, perf_llm_calls=0)


def test_queue_probe_interval_must_cover_window(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path)
    with pytest.raises(RuntimeError, match="queue liveness interval"):
        _validate(
            tmp_path,
            llm_load_artifact=artifact,
            worker_probe=_worker_probe(started="2026-10-18T15:00:00.000000+00:00"),
        )


def test_honest_instrumentation_passes(tmp_path: Path) -> None:
    artifact = _write_load_artifact(tmp_path, dispatched_count=60)
    evidence = _validate(tmp_path, llm_load_artifact=artifact, perf_llm_calls=42)
    assert evidence["authority_window_start_utc"] == _WINDOW_START
    assert evidence["authority_window_end_utc"] == _WINDOW_END
    assert evidence["load_helper_dispatched_count"] == 60
    assert evidence["load_helper_dispatch_mode"] == "inline"
    assert evidence["cpu_probe_sample_count"] == 90
    assert evidence["cpu_probe_psi_some_stall_us"] == 123456.7
    assert evidence["pg_stat_probe_sample_count"] == 90
    assert evidence["pg_stat_probe_extversion"] == "1.10"
    assert evidence["pg_stat_probe_top_statements_by_delta"][0]["qid"] == "1"


def test_ci_subset_sanity_still_requires_helper_integrity(tmp_path: Path) -> None:
    artifact = _write_load_artifact(
        tmp_path,
        dispatch_mode="inline",
        started_at="2026-10-18T15:10:00.000000+00:00",
        finished_at="2026-10-18T15:11:00.000000+00:00",
    )
    evidence = _validate(
        tmp_path,
        full_physics=False,
        llm_load_artifact=artifact,
        perf_llm_calls=0,
    )
    assert "authority_window_start_utc" not in evidence

    zero_dispatch = _write_load_artifact(tmp_path, dispatched_count=0)
    with pytest.raises(RuntimeError, match="dispatched zero calls"):
        _validate(
            tmp_path,
            full_physics=False,
            llm_load_artifact=zero_dispatch,
            perf_llm_calls=0,
        )


def test_r3_leg_span_matches_profile_defaults() -> None:
    full_env = {
        "R3_NULL_BENCHMARK": "1",
        "R3_NULL_BENCHMARK_DURATION_S": "60",
        "R3_EG34_TEST1_DURATION_S": "60",
        "R3_EG34_TEST2_DURATION_S": "60",
        "R3_EG34_TEST3_DURATION_S": "300",
    }
    assert _PACK._r3_leg_span_seconds(full_env) == 480
    ci_env = {
        "R3_NULL_BENCHMARK": "1",
        "R3_NULL_BENCHMARK_DURATION_S": "30",
        "R3_EG34_TEST1_DURATION_S": "30",
        "R3_EG34_TEST2_DURATION_S": "30",
        "R3_EG34_TEST3_DURATION_S": "60",
    }
    assert _PACK._r3_leg_span_seconds(ci_env) == 150


def _write_r3_log(tmp_path: Path, *, passed: bool) -> Path:
    verdict = {
        "passed": passed,
        "window_start_utc": _WINDOW_START,
        "window_end_utc": _WINDOW_END,
        "target_rps": 46.0,
        "achieved_rps": 34.348,
        "elapsed_s": 80.3548,
        "latency_p95_ms": 6167.017,
    }
    log = tmp_path / "r3_ingestion_under_fire.log"
    log.write_text(
        "R3_VERDICT_BEGIN EG3_4_Test2_Month18\n"
        + json.dumps(verdict, indent=2)
        + "\nR3_VERDICT_END EG3_4_Test2_Month18\n",
        encoding="utf-8",
    )
    return log


def test_best_effort_window_from_failed_verdict(tmp_path: Path) -> None:
    log = _write_r3_log(tmp_path, passed=False)
    window = _PACK._extract_profile_window_best_effort(log, "EG3_4_Test2_Month18")
    assert window["passed"] is False
    assert window["window_start_utc"] == _WINDOW_START
    assert window["window_end_utc"] == _WINDOW_END
    with pytest.raises(RuntimeError, match="verdict failed"):
        _PACK._extract_profile_metrics_from_r3_log(log, "EG3_4_Test2_Month18")


def test_best_effort_window_missing_log_returns_empty(tmp_path: Path) -> None:
    missing = tmp_path / "absent.log"
    assert _PACK._extract_profile_window_best_effort(missing, "EG3_4_Test2_Month18") == {}
