#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

import psycopg2

from app.testing.jwt_rs256 import private_ring_payload, public_ring_payload


@dataclass(frozen=True)
class _Phase8Config:
    repo_root: Path
    artifact_dir: Path
    logs_dir: Path
    runtime_sync_dsn: str
    runtime_async_dsn: str
    worker_sync_dsn: str
    migration_dsn: str
    compose_runtime_async_dsn: str
    compose_worker_async_dsn: str
    compose_runtime_sync_dsn: str
    compose_broker_dsn: str
    compose_result_dsn: str
    api_base_url: str
    mock_base_url: str
    ci_subset: bool
    full_physics: bool


_R3_VERDICT_BEGIN = re.compile(r"^R3_VERDICT_BEGIN\s+(.+)$")
_R3_VERDICT_END = re.compile(r"^R3_VERDICT_END\s+(.+)$")
_CONTAINER_DB_IDENTITY_PROBE = """
import json
import os
import sys

import psycopg2


dsn = os.environ.get("DATABASE_URL", "")
if not dsn:
    print(json.dumps({"error": "DATABASE_URL missing"}))
    sys.exit(2)
dsn = dsn.replace("+asyncpg", "")
expected = os.environ.get("PHASE8_EXPECTED_DB_USER", "app_user")

with psycopg2.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT current_user, (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)"
        )
        current_user, rolsuper = cur.fetchone()
        cur.execute(
            '''
            SELECT EXISTS (
              SELECT 1
              FROM pg_namespace n
              JOIN pg_roles r ON r.oid = n.nspowner
              WHERE n.nspname = 'public' AND r.rolname = current_user
            )
            '''
        )
        owns_public_schema = bool(cur.fetchone()[0])
        cur.execute(
            '''
            SELECT EXISTS (
              SELECT 1
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
              JOIN pg_roles r ON r.oid = c.relowner
              WHERE n.nspname = 'public'
                AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
                AND r.rolname = current_user
            )
            '''
        )
        owns_public_objects = bool(cur.fetchone()[0])

payload = {
    "expected_user": expected,
    "current_user": str(current_user),
    "rolsuper": bool(rolsuper),
    "owns_public_schema": owns_public_schema,
    "owns_public_objects": owns_public_objects,
}
print(json.dumps(payload, sort_keys=True))

if payload["current_user"] != expected:
    sys.exit(3)
if payload["rolsuper"]:
    sys.exit(4)
"""


def _is_kid_keyring_payload(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return False
    return (
        isinstance(parsed, dict)
        and isinstance(parsed.get("current_kid"), str)
        and isinstance(parsed.get("keys"), dict)
    )


def _resolved_jwt_env_values() -> tuple[str, str, str]:
    algorithm = os.getenv("AUTH_JWT_ALGORITHM", "RS256")
    private_ring = os.getenv("AUTH_JWT_SECRET")
    public_ring = os.getenv("AUTH_JWT_PUBLIC_KEY_RING")
    if algorithm == "RS256":
        if not _is_kid_keyring_payload(private_ring):
            private_ring = private_ring_payload()
        if not _is_kid_keyring_payload(public_ring):
            public_ring = public_ring_payload()
    else:
        private_ring = private_ring or private_ring_payload()
        public_ring = public_ring or public_ring_payload()
    return private_ring, public_ring, algorithm


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_authority(cfg: _Phase8Config) -> str:
    return "full_physics" if cfg.full_physics else "ci_subset"


def _eg85_gate_name(run_authority: str) -> str:
    return (
        "eg8_5_composed_ingestion_perf_authority"
        if run_authority == "full_physics"
        else "eg8_5_ci_sanity"
    )


def _summary_filename_for_authority(run_authority: str) -> str:
    return (
        "phase8_gate_summary_full_physics.json"
        if run_authority == "full_physics"
        else "phase8_gate_summary_ci_subset.json"
    )


def _read_text_if_exists(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:  # noqa: BLE001
        return None


def _collect_runner_physics(cfg: _Phase8Config, run_authority: str) -> dict[str, Any]:
    cpu_count = os.cpu_count() or 0
    cpu_model = None
    cpuinfo_text = _read_text_if_exists(Path("/proc/cpuinfo"))
    if cpuinfo_text:
        for line in cpuinfo_text.splitlines():
            if line.lower().startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break

    meminfo_map: dict[str, int] = {}
    meminfo_text = _read_text_if_exists(Path("/proc/meminfo"))
    if meminfo_text:
        for line in meminfo_text.splitlines():
            if ":" not in line:
                continue
            key, raw_value = line.split(":", 1)
            raw_value = raw_value.strip().split(" ", 1)[0]
            try:
                meminfo_map[key] = int(raw_value)
            except Exception:  # noqa: BLE001
                continue

    cpu_max = _read_text_if_exists(Path("/sys/fs/cgroup/cpu.max"))
    memory_max = _read_text_if_exists(Path("/sys/fs/cgroup/memory.max"))
    cpu_quota = _read_text_if_exists(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"))
    cpu_period = _read_text_if_exists(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us"))
    memory_limit_v1 = _read_text_if_exists(
        Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    )

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "run_authority": run_authority,
        "github": {
            "run_id": os.getenv("GITHUB_RUN_ID"),
            "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
            "workflow": os.getenv("GITHUB_WORKFLOW"),
            "sha": os.getenv("GITHUB_SHA"),
            "ref": os.getenv("GITHUB_REF"),
            "repository": os.getenv("GITHUB_REPOSITORY"),
            "runner_name": os.getenv("RUNNER_NAME"),
            "runner_arch": os.getenv("RUNNER_ARCH"),
            "runner_os": os.getenv("RUNNER_OS"),
        },
        "host": {
            "cpu_count": cpu_count,
            "cpu_model": cpu_model,
            "mem_total_kib": meminfo_map.get("MemTotal"),
            "mem_available_kib": meminfo_map.get("MemAvailable"),
        },
        "cgroup_limits": {
            "cpu_max": cpu_max,
            "memory_max": memory_max,
            "cpu_cfs_quota_us": cpu_quota,
            "cpu_cfs_period_us": cpu_period,
            "memory_limit_in_bytes_v1": memory_limit_v1,
        },
    }
    (cfg.artifact_dir / "runner_physics_probe.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return payload


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_openapi_spec_hash(cfg: _Phase8Config) -> str:
    reconciliation = (
        cfg.repo_root
        / "api-contracts"
        / "dist"
        / "openapi"
        / "v1"
        / "reconciliation.bundled.yaml"
    )
    attribution = (
        cfg.repo_root
        / "api-contracts"
        / "dist"
        / "openapi"
        / "v1"
        / "attribution.bundled.yaml"
    )
    if not reconciliation.exists() or not attribution.exists():
        missing: list[str] = []
        if not reconciliation.exists():
            missing.append(str(reconciliation))
        if not attribution.exists():
            missing.append(str(attribution))
        raise RuntimeError(f"Canonical OpenAPI bundle(s) missing: {', '.join(missing)}")
    joined = f"{_sha256_file(reconciliation)}|{_sha256_file(attribution)}".encode(
        "utf-8"
    )
    return hashlib.sha256(joined).hexdigest()


def _parse_r3_verdicts(log_path: Path) -> dict[str, dict[str, Any]]:
    if not log_path.exists():
        raise RuntimeError(f"R3 log not found: {log_path}")
    verdicts: dict[str, dict[str, Any]] = {}
    current_name: str | None = None
    buf: list[str] = []
    for raw_line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        begin_match = _R3_VERDICT_BEGIN.match(line)
        if begin_match:
            current_name = begin_match.group(1).strip()
            buf = []
            continue
        end_match = _R3_VERDICT_END.match(line)
        if end_match and current_name:
            payload = "\n".join(buf).strip()
            verdicts[current_name] = json.loads(payload) if payload else {}
            current_name = None
            buf = []
            continue
        if current_name is not None:
            buf.append(raw_line)
    return verdicts


def _extract_profile_metrics_from_r3_log(
    log_path: Path, profile_name: str
) -> dict[str, Any]:
    verdicts = _parse_r3_verdicts(log_path)
    payload = verdicts.get(profile_name)
    if not isinstance(payload, dict):
        raise RuntimeError(f"R3 profile verdict not found in log: {profile_name}")
    if not bool(payload.get("passed")):
        raise RuntimeError(f"R3 profile verdict failed: {profile_name}")
    return payload


def _extract_profile_window_best_effort(
    log_path: Path, profile_name: str
) -> dict[str, Any]:
    """Read a profile verdict for diagnostics, tolerating a failed profile."""
    try:
        verdicts = _parse_r3_verdicts(log_path)
    except RuntimeError:
        return {}
    payload = verdicts.get(profile_name)
    if not isinstance(payload, dict):
        return {}
    return {
        "passed": bool(payload.get("passed")),
        "window_start_utc": payload.get("window_start_utc"),
        "window_end_utc": payload.get("window_end_utc"),
        "target_rps": payload.get("target_rps"),
        "achieved_rps": payload.get("achieved_rps"),
        "elapsed_s": payload.get("elapsed_s"),
        "latency_p50_ms": payload.get("latency_p50_ms"),
        "latency_p95_ms": payload.get("latency_p95_ms"),
        "latency_p99_ms": payload.get("latency_p99_ms"),
    }


def _r3_leg_span_seconds(env: dict[str, str]) -> int:
    """Sum of the EG3.4/null-benchmark profile durations, i.e. the R3 leg span."""
    total = 0
    if str(env.get("R3_NULL_BENCHMARK", "1")).strip() == "1":
        total += int(env.get("R3_NULL_BENCHMARK_DURATION_S", "0") or 0)
    for key in (
        "R3_EG34_TEST1_DURATION_S",
        "R3_EG34_TEST2_DURATION_S",
        "R3_EG34_TEST3_DURATION_S",
    ):
        total += int(env.get(key, "0") or 0)
    return total


def _read_log_tail(path: Path, max_lines: int = 40) -> str:
    if not path.exists():
        return "<log missing>"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])


def _validate_composed_instrumentation(
    *,
    full_physics: bool,
    llm_load_artifact: Path,
    llm_load_log: Path,
    queue_probe_log: Path,
    cpu_probe_artifact: Path,
    cpu_probe_log: Path,
    pg_stat_probe_artifact: Path,
    pg_stat_probe_log: Path,
    llm_load_returncode: int,
    queue_probe_returncode: int,
    cpu_probe_returncode: int,
    pg_stat_probe_returncode: int,
    worker_probe: dict[str, Any],
    r3_profile: dict[str, Any],
    perf_llm_calls: int,
) -> dict[str, Any]:
    """Fail closed on a missing/failed helper, a stale interval or absent conduction."""
    if llm_load_returncode != 0:
        raise RuntimeError(
            "Composed instrumentation invalid: llm_background_load.py exited "
            f"with code {llm_load_returncode}; tail:\n{_read_log_tail(llm_load_log)}"
        )
    if queue_probe_returncode != 0:
        raise RuntimeError(
            "Composed instrumentation invalid: queue_liveness_probe.py exited "
            f"with code {queue_probe_returncode}; tail:\n{_read_log_tail(queue_probe_log)}"
        )
    if cpu_probe_returncode != 0:
        raise RuntimeError(
            "Composed instrumentation invalid: runner_cpu_probe.py exited "
            f"with code {cpu_probe_returncode}; tail:\n{_read_log_tail(cpu_probe_log)}"
        )
    if not cpu_probe_artifact.exists():
        raise RuntimeError(
            "Composed instrumentation invalid: runner CPU probe artifact missing "
            f"({cpu_probe_artifact.name})"
        )
    cpu_probe = json.loads(cpu_probe_artifact.read_text(encoding="utf-8"))
    if not isinstance(cpu_probe, dict):
        raise RuntimeError(
            "Composed instrumentation invalid: runner CPU probe artifact is not "
            "a JSON object"
        )
    if cpu_probe.get("status") != "ok":
        raise RuntimeError(
            "Composed instrumentation invalid: runner CPU probe status="
            f"{cpu_probe.get('status')!r} error={cpu_probe.get('error')!r}"
        )
    cpu_probe_samples = int(cpu_probe.get("sample_count", 0) or 0)
    if cpu_probe_samples < 2:
        raise RuntimeError(
            "Composed instrumentation invalid: runner CPU probe recorded fewer "
            f"than 2 samples ({cpu_probe_samples})"
        )
    if pg_stat_probe_returncode != 0:
        raise RuntimeError(
            "Composed instrumentation invalid: pg_stat_probe.py exited "
            f"with code {pg_stat_probe_returncode}; tail:\n"
            f"{_read_log_tail(pg_stat_probe_log)}"
        )
    if not pg_stat_probe_artifact.exists():
        raise RuntimeError(
            "Composed instrumentation invalid: pg_stat probe artifact missing "
            f"({pg_stat_probe_artifact.name})"
        )
    pg_stat_probe = json.loads(pg_stat_probe_artifact.read_text(encoding="utf-8"))
    if not isinstance(pg_stat_probe, dict):
        raise RuntimeError(
            "Composed instrumentation invalid: pg_stat probe artifact is not "
            "a JSON object"
        )
    if pg_stat_probe.get("status") != "ok":
        raise RuntimeError(
            "Composed instrumentation invalid: pg_stat probe status="
            f"{pg_stat_probe.get('status')!r} error={pg_stat_probe.get('error')!r}"
        )
    if not pg_stat_probe.get("pgss_available"):
        raise RuntimeError(
            "Composed instrumentation invalid: pg_stat_statements unavailable in "
            f"the composed postgres (preloaded={pg_stat_probe.get('preloaded_libraries')!r}, "
            f"error={pg_stat_probe.get('pgss_error')!r})"
        )
    pg_stat_probe_samples = int(pg_stat_probe.get("sample_count", 0) or 0)
    if pg_stat_probe_samples < 2:
        raise RuntimeError(
            "Composed instrumentation invalid: pg_stat probe recorded fewer "
            f"than 2 samples ({pg_stat_probe_samples})"
        )
    if not llm_load_artifact.exists():
        raise RuntimeError(
            "Composed instrumentation invalid: load-helper artifact missing "
            f"({llm_load_artifact.name})"
        )
    llm_probe = json.loads(llm_load_artifact.read_text(encoding="utf-8"))
    if not isinstance(llm_probe, dict):
        raise RuntimeError(
            "Composed instrumentation invalid: load-helper artifact is not a JSON object"
        )
    if llm_probe.get("status") != "ok":
        raise RuntimeError(
            "Composed instrumentation invalid: load-helper status="
            f"{llm_probe.get('status')!r} error={llm_probe.get('error')!r}"
        )
    dispatched_count = int(llm_probe.get("dispatched_count", 0) or 0)
    if dispatched_count <= 0:
        raise RuntimeError(
            "Composed instrumentation invalid: load-helper dispatched zero calls"
        )

    evidence: dict[str, Any] = {
        "load_helper_dispatched_count": dispatched_count,
        "load_helper_dispatch_mode": llm_probe.get("dispatch_mode"),
        "load_helper_started_at": llm_probe.get("started_at"),
        "load_helper_finished_at": llm_probe.get("finished_at"),
        # Ordered-plan step 3 measurements (observation only).
        "cpu_probe_sample_count": cpu_probe_samples,
        "cpu_probe_total_busy_pct_avg": cpu_probe.get("total_busy_pct_avg"),
        "cpu_probe_psi_some_stall_us": cpu_probe.get("psi_cpu_some_stall_us_total"),
        "cpu_probe_psi_some_avg10_max": cpu_probe.get("psi_cpu_some_avg10_max"),
        "cpu_probe_throttle_delta": cpu_probe.get("throttle_delta"),
        "cpu_probe_classes": cpu_probe.get("classes"),
        "cpu_probe_top_processes": cpu_probe.get("top_processes"),
        # Ordered-plan step 4: intra-postgres split (observation only).
        "pg_stat_probe_sample_count": pg_stat_probe_samples,
        "pg_stat_probe_interval_s": pg_stat_probe.get("interval_s"),
        "pg_stat_probe_extversion": pg_stat_probe.get("extversion"),
        "pg_stat_probe_track_setting": pg_stat_probe.get("track_setting"),
        "pg_stat_probe_totals_first": pg_stat_probe.get("totals_first"),
        "pg_stat_probe_totals_last": pg_stat_probe.get("totals_last"),
        "pg_stat_probe_top_statements_by_delta": pg_stat_probe.get(
            "top_statements_by_delta"
        ),
    }
    if not full_physics:
        return evidence

    if llm_probe.get("dispatch_mode") != "inline":
        raise RuntimeError(
            "Composed instrumentation invalid: authority conduction requires the "
            f"certified inline dispatch, got {llm_probe.get('dispatch_mode')!r}"
        )

    window_start_raw = r3_profile.get("window_start_utc")
    window_end_raw = r3_profile.get("window_end_utc")
    load_start_raw = llm_probe.get("started_at")
    load_finish_raw = llm_probe.get("finished_at")
    probe_start_raw = worker_probe.get("started_at")
    probe_finish_raw = worker_probe.get("finished_at")
    missing = [
        name
        for name, value in (
            ("authority_window_start", window_start_raw),
            ("authority_window_end", window_end_raw),
            ("load_started_at", load_start_raw),
            ("load_finished_at", load_finish_raw),
            ("probe_started_at", probe_start_raw),
            ("probe_finished_at", probe_finish_raw),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Composed instrumentation invalid: missing interval timestamps "
            f"({', '.join(missing)})"
        )
    window_start = datetime.fromisoformat(str(window_start_raw))
    window_end = datetime.fromisoformat(str(window_end_raw))
    load_start = datetime.fromisoformat(str(load_start_raw))
    load_finish = datetime.fromisoformat(str(load_finish_raw))
    probe_start = datetime.fromisoformat(str(probe_start_raw))
    probe_finish = datetime.fromisoformat(str(probe_finish_raw))
    if load_start > window_start or load_finish < window_end:
        raise RuntimeError(
            "Composed instrumentation invalid: stale or mismatched load interval; "
            f"{load_start_raw}..{load_finish_raw} does not cover authority window "
            f"{window_start_raw}..{window_end_raw}"
        )
    if probe_start > window_start or probe_finish < window_end:
        raise RuntimeError(
            "Composed instrumentation invalid: queue liveness interval; "
            f"{probe_start_raw}..{probe_finish_raw} does not cover authority window "
            f"{window_start_raw}..{window_end_raw}"
        )
    if perf_llm_calls <= 0:
        raise RuntimeError(
            "Composed instrumentation invalid: absent conduction; no LLM calls "
            "recorded during the authority window"
        )
    evidence.update(
        {
            "authority_window_start_utc": window_start_raw,
            "authority_window_end_utc": window_end_raw,
            "queue_probe_started_at": probe_start_raw,
            "queue_probe_finished_at": probe_finish_raw,
        }
    )
    return evidence


def _eg85_profile_metadata(cfg: _Phase8Config, env: dict[str, str]) -> dict[str, Any]:
    run_authority = _run_authority(cfg)
    if run_authority == "full_physics":
        ingestion_profile_name = "EG3_4_46rps_60s"
    else:
        ingestion_profile_name = "EG8_5_ci_sanity_profile"
    return {
        "run_authority": run_authority,
        "ingestion_profile_name": ingestion_profile_name,
        "target_rps": float(env["R3_EG34_TEST2_RPS"]),
        "duration_s": int(env["R3_EG34_TEST2_DURATION_S"]),
        "concurrency": int(env["R3_CONCURRENCY"]),
    }


def _default_config(
    *, artifact_dir: Path, ci_subset: bool, full_physics: bool
) -> _Phase8Config:
    db_name = os.getenv("PHASE8_DB_NAME", "skeldir_e2e")
    db_host = os.getenv("PHASE8_DB_HOST", "127.0.0.1")
    db_compose_host = os.getenv("PHASE8_DB_COMPOSE_HOST", "postgres")
    admin_user = os.getenv("PHASE8_DB_ADMIN_USER", "skeldir")
    admin_pass = os.getenv("PHASE8_DB_ADMIN_PASS", "skeldir_e2e")
    runtime_user = os.getenv("PHASE8_RUNTIME_DB_USER", "app_user")
    runtime_pass = os.getenv("PHASE8_RUNTIME_DB_PASS", "app_user")
    api_base_url = os.getenv("E2E_API_BASE_URL", "http://127.0.0.1:8000")
    mock_base_url = os.getenv("E2E_MOCK_BASE_URL", "http://127.0.0.1:8080")

    runtime_sync = (
        f"postgresql://{runtime_user}:{runtime_pass}@{db_host}:5432/{db_name}"
    )
    runtime_async = (
        f"postgresql+asyncpg://{runtime_user}:{runtime_pass}@{db_host}:5432/{db_name}"
    )
    worker_sync = f"postgresql://app_worker:app_worker@{db_host}:5432/{db_name}"
    migration = f"postgresql://{admin_user}:{admin_pass}@{db_host}:5432/{db_name}"
    compose_runtime_async = f"postgresql+asyncpg://{runtime_user}:{runtime_pass}@{db_compose_host}:5432/{db_name}"
    compose_runtime_sync = (
        f"postgresql://{runtime_user}:{runtime_pass}@{db_compose_host}:5432/{db_name}"
    )
    # The Bayesian worker container runs on the dedicated worker login. It is
    # deliberately a different principal from the API/generic worker DSN.
    compose_worker_async = (
        f"postgresql+asyncpg://app_worker:app_worker@{db_compose_host}:5432/{db_name}"
    )

    return _Phase8Config(
        repo_root=_repo_root(),
        artifact_dir=artifact_dir,
        logs_dir=artifact_dir / "logs",
        runtime_sync_dsn=runtime_sync,
        runtime_async_dsn=runtime_async,
        worker_sync_dsn=worker_sync,
        migration_dsn=migration,
        compose_runtime_async_dsn=compose_runtime_async,
        compose_worker_async_dsn=compose_worker_async,
        compose_runtime_sync_dsn=compose_runtime_sync,
        compose_broker_dsn=f"sqla+{compose_runtime_sync}",
        compose_result_dsn=f"db+{compose_runtime_sync}",
        api_base_url=api_base_url,
        mock_base_url=mock_base_url,
        ci_subset=ci_subset,
        full_physics=full_physics,
    )


def _database_name_from_dsn(dsn: str) -> str:
    parsed = urlparse(dsn)
    return (parsed.path or "/").strip("/") or "postgres"


def _ensure_dirs(cfg: _Phase8Config) -> None:
    cfg.artifact_dir.mkdir(parents=True, exist_ok=True)
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    (cfg.artifact_dir / "sql").mkdir(parents=True, exist_ok=True)


def _build_env(cfg: _Phase8Config) -> dict[str, str]:
    env = os.environ.copy()
    jwt_private_ring, jwt_public_ring, jwt_algorithm = _resolved_jwt_env_values()
    env.update(
        {
            "CI": "true",
            "PYTHONPATH": f"{cfg.repo_root}{os.pathsep}{cfg.repo_root / 'backend'}",
            "ENVIRONMENT": "test",
            "DATABASE_URL": cfg.runtime_async_dsn,
            "B07_P8_RUNTIME_DATABASE_URL": cfg.runtime_sync_dsn,
            "MIGRATION_DATABASE_URL": cfg.migration_dsn,
            "CELERY_BROKER_URL": f"sqla+{cfg.runtime_sync_dsn}",
            "CELERY_RESULT_BACKEND": f"db+{cfg.runtime_sync_dsn}",
            "EXPECTED_RUNTIME_DB_USER": os.getenv("PHASE8_RUNTIME_DB_USER", "app_user"),
            "RUNTIME_USER": os.getenv("PHASE8_RUNTIME_DB_USER", "app_user"),
            "B07_P2_RUNTIME_DATABASE_URL": cfg.runtime_sync_dsn,
            "B07_P5_BAYESIAN_WORKER_DATABASE_URL": cfg.worker_sync_dsn,
            "B07_P5_EXPECTED_WORKER_DB_USER": "app_worker",
            "B07_P4_RUNTIME_DATABASE_URL": cfg.runtime_sync_dsn,
            "B07_P2_ARTIFACT_DIR": str(cfg.artifact_dir),
            "B07_P4_ARTIFACT_DIR": str(cfg.artifact_dir),
            "B07_P8_ARTIFACT_DIR": str(cfg.artifact_dir),
            "E2E_API_BASE_URL": cfg.api_base_url,
            "E2E_MOCK_BASE_URL": cfg.mock_base_url,
            "E2E_DB_URL": cfg.runtime_sync_dsn,
            "E2E_WAIT_TIMEOUT_S": "120",
            "AUTH_JWT_SECRET": jwt_private_ring,
            "AUTH_JWT_PUBLIC_KEY_RING": jwt_public_ring,
            "AUTH_JWT_ALGORITHM": jwt_algorithm,
            "AUTH_JWT_ISSUER": os.getenv(
                "AUTH_JWT_ISSUER", "https://issuer.skeldir.test"
            ),
            "AUTH_JWT_AUDIENCE": os.getenv("AUTH_JWT_AUDIENCE", "skeldir-api"),
            "PLATFORM_TOKEN_ENCRYPTION_KEY": os.getenv(
                "PLATFORM_TOKEN_ENCRYPTION_KEY", "e2e-platform-key"
            ),
            "PLATFORM_TOKEN_KEY_ID": os.getenv("PLATFORM_TOKEN_KEY_ID", "e2e-key"),
            "INGESTION_FOLLOWUP_TASKS_ENABLED": "true",
            "E2E_DATABASE_URL": cfg.compose_runtime_async_dsn,
            "E2E_WORKER_DATABASE_URL": cfg.compose_worker_async_dsn,
            "E2E_CELERY_BROKER_URL": cfg.compose_broker_dsn,
            "E2E_CELERY_RESULT_BACKEND": cfg.compose_result_dsn,
            # B2.6-P2 Corrective XIV Architecture B: the pack posts
            # verified webhooks through the API relay, which relays to
            # the dedicated authentication trust root (same topology as
            # production/c19/e2e). Single secret-delivery law: the
            # ingress credential is file-mounted into the auth service
            # only (provisioned below); the API holds no DB capability.
            "E2E_PROCESS_ROLE": "api",
            "E2E_INGRESS_DATABASE_URL": "",
            "TENANT_API_KEY_HEADER": "X-Skeldir-Tenant-Key",
            "R3_ADMIN_DATABASE_URL": cfg.migration_dsn,
            "R3_RUNTIME_DATABASE_URL": cfg.runtime_sync_dsn,
            "R3_API_BASE_URL": cfg.api_base_url,
            "E2E_ENVIRONMENT": "test",
            "E2E_API_ENVIRONMENT": "test",
            "E2E_WORKER_ENVIRONMENT": "test",
            "E2E_DATABASE_FORCE_POOLING": "0",
            "E2E_DATABASE_POOL_SIZE": "20",
            "E2E_DATABASE_MAX_OVERFLOW": "0",
            "E2E_API_DATABASE_FORCE_POOLING": "0",
            "E2E_API_DATABASE_POOL_SIZE": "20",
            "E2E_API_DATABASE_MAX_OVERFLOW": "0",
            "E2E_WORKER_DATABASE_FORCE_POOLING": "0",
            "E2E_WORKER_DATABASE_POOL_SIZE": "20",
            "E2E_WORKER_DATABASE_MAX_OVERFLOW": "0",
            "E2E_API_WORKERS": "1",
        }
    )

    if cfg.ci_subset and not cfg.full_physics:
        env.update(
            {
                "R3_LADDER": "20,50",
                "R3_CONCURRENCY": "40",
                "R3_TIMEOUT_S": "8",
                "R3_NULL_BENCHMARK": "1",
                "R3_NULL_BENCHMARK_TARGET_RPS": "20",
                "R3_NULL_BENCHMARK_DURATION_S": "30",
                "R3_NULL_BENCHMARK_MIN_RPS": "15",
                "R3_EG34_P95_MAX_MS": "2500",
                "R3_EG34_TEST1_RPS": "10",
                "R3_EG34_TEST1_DURATION_S": "30",
                "R3_EG34_TEST2_RPS": "15",
                "R3_EG34_TEST2_DURATION_S": "30",
                "R3_EG34_TEST3_RPS": "3",
                "R3_EG34_TEST3_DURATION_S": "60",
            }
        )
    else:
        detected_cores = max(2, os.cpu_count() or 2)
        api_workers = max(2, min(8, detected_cores - 1))
        # In full-physics CI we typically do not wire control-plane credentials into compose runtime.
        # Default API env to test unless control-plane is explicitly enabled by the caller.
        control_plane_enabled = env.get("SKELDIR_CONTROL_PLANE_ENABLED", "0") == "1"
        default_api_environment = "staging" if control_plane_enabled else "test"
        default_worker_environment = "test"
        default_shared_environment = "staging" if control_plane_enabled else "test"
        env.update(
            {
                # Full-physics authority is encoded by EG3.4 Test2 (46 rps), not by high-N ladder replay storms.
                # Keep ladder bounded by default so hosted runners can reach the authoritative profile gate.
                "R3_LADDER": os.getenv("R3_LADDER", "50"),
                "R3_CONCURRENCY": os.getenv("R3_CONCURRENCY", "80"),
                "R3_TIMEOUT_S": os.getenv("R3_TIMEOUT_S", "10"),
                "R3_NULL_BENCHMARK": os.getenv("R3_NULL_BENCHMARK", "1"),
                "R3_NULL_BENCHMARK_TARGET_RPS": os.getenv(
                    "R3_NULL_BENCHMARK_TARGET_RPS", "50"
                ),
                "R3_NULL_BENCHMARK_DURATION_S": os.getenv(
                    "R3_NULL_BENCHMARK_DURATION_S", "60"
                ),
                "R3_NULL_BENCHMARK_MIN_RPS": os.getenv(
                    "R3_NULL_BENCHMARK_MIN_RPS", "50"
                ),
                "R3_EG34_P95_MAX_MS": os.getenv("R3_EG34_P95_MAX_MS", "2000"),
                "R3_EG34_TEST1_RPS": os.getenv("R3_EG34_TEST1_RPS", "29"),
                "R3_EG34_TEST1_DURATION_S": os.getenv("R3_EG34_TEST1_DURATION_S", "60"),
                "R3_EG34_TEST2_RPS": os.getenv("R3_EG34_TEST2_RPS", "46"),
                "R3_EG34_TEST2_DURATION_S": os.getenv("R3_EG34_TEST2_DURATION_S", "60"),
                "R3_EG34_TEST3_RPS": os.getenv("R3_EG34_TEST3_RPS", "5"),
                "R3_EG34_TEST3_DURATION_S": os.getenv(
                    "R3_EG34_TEST3_DURATION_S", "300"
                ),
                "E2E_ENVIRONMENT": os.getenv(
                    "E2E_ENVIRONMENT", default_shared_environment
                ),
                "E2E_API_ENVIRONMENT": os.getenv(
                    "E2E_API_ENVIRONMENT", default_api_environment
                ),
                "E2E_WORKER_ENVIRONMENT": os.getenv(
                    "E2E_WORKER_ENVIRONMENT", default_worker_environment
                ),
                "E2E_DATABASE_FORCE_POOLING": os.getenv(
                    "E2E_DATABASE_FORCE_POOLING", "0"
                ),
                "E2E_DATABASE_POOL_SIZE": os.getenv("E2E_DATABASE_POOL_SIZE", "20"),
                "E2E_DATABASE_MAX_OVERFLOW": os.getenv(
                    "E2E_DATABASE_MAX_OVERFLOW", "0"
                ),
                "E2E_API_DATABASE_FORCE_POOLING": os.getenv(
                    "E2E_API_DATABASE_FORCE_POOLING", "1"
                ),
                "E2E_API_DATABASE_POOL_SIZE": os.getenv(
                    "E2E_API_DATABASE_POOL_SIZE", "40"
                ),
                "E2E_API_DATABASE_MAX_OVERFLOW": os.getenv(
                    "E2E_API_DATABASE_MAX_OVERFLOW", "20"
                ),
                "E2E_WORKER_DATABASE_FORCE_POOLING": os.getenv(
                    "E2E_WORKER_DATABASE_FORCE_POOLING", "0"
                ),
                "E2E_WORKER_DATABASE_POOL_SIZE": os.getenv(
                    "E2E_WORKER_DATABASE_POOL_SIZE", "20"
                ),
                "E2E_WORKER_DATABASE_MAX_OVERFLOW": os.getenv(
                    "E2E_WORKER_DATABASE_MAX_OVERFLOW", "0"
                ),
                "E2E_API_WORKERS": os.getenv("E2E_API_WORKERS", str(api_workers)),
                "E2E_AUTH_WORKERS": os.getenv("E2E_AUTH_WORKERS", "2"),
            }
        )
    return env


def _run_logged(
    cfg: _Phase8Config,
    *,
    name: str,
    cmd: Sequence[str],
    env: dict[str, str],
    cwd: Path | None = None,
) -> None:
    log_path = cfg.logs_dir / f"{name}.log"
    with log_path.open("w", encoding="utf-8") as handle:
        proc = subprocess.Popen(
            list(cmd),
            cwd=str(cwd or cfg.repo_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            handle.write(line)
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"Step failed ({name}): {' '.join(cmd)}")


def _run_capture(
    cfg: _Phase8Config,
    *,
    name: str,
    cmd: Sequence[str],
    env: dict[str, str],
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    log_path = cfg.logs_dir / f"{name}.log"
    proc = subprocess.run(
        list(cmd),
        cwd=str(cwd or cfg.repo_root),
        env=env,
        capture_output=True,
        text=True,
    )
    combined = f"{proc.stdout}{proc.stderr}"
    log_path.write_text(combined, encoding="utf-8")
    if check and proc.returncode != 0:
        raise RuntimeError(f"Step failed ({name}): {' '.join(cmd)}")
    return proc


def _parse_json_line(payload: str) -> dict[str, Any]:
    lines = [line.strip() for line in payload.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("{") and line.endswith("}"):
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                return parsed
    raise RuntimeError("Expected JSON object in subprocess output")


def _assert_compose_missing_runtime_dsn_fails(
    cfg: _Phase8Config, env: dict[str, str]
) -> dict[str, Any]:
    neg_env = env.copy()
    neg_env.pop("E2E_DATABASE_URL", None)
    neg_env.pop("E2E_CELERY_BROKER_URL", None)
    neg_env.pop("E2E_CELERY_RESULT_BACKEND", None)
    proc = _run_capture(
        cfg,
        name="compose_missing_runtime_dsn_negative_control",
        cmd=["docker", "compose", "-f", "docker-compose.e2e.yml", "config"],
        env=neg_env,
        check=False,
    )
    if proc.returncode == 0:
        raise RuntimeError(
            "Missing runtime DSN negative control did not fail: docker compose accepted unset E2E_DATABASE_URL"
        )
    return {
        "name": "missing_runtime_dsn_rejected",
        "passed": True,
        "returncode": proc.returncode,
        "log": "logs/compose_missing_runtime_dsn_negative_control.log",
        "message_excerpt": f"{proc.stdout}{proc.stderr}"[-500:],
    }


def _probe_container_db_identity(
    cfg: _Phase8Config,
    env: dict[str, str],
    *,
    service: str,
    expected_user: str,
    check: bool,
    log_name: str,
) -> tuple[int, dict[str, Any]]:
    proc = _run_capture(
        cfg,
        name=log_name,
        cmd=[
            "docker",
            "compose",
            "-f",
            "docker-compose.e2e.yml",
            "exec",
            "-T",
            "-e",
            f"PHASE8_EXPECTED_DB_USER={expected_user}",
            service,
            "python",
            "-c",
            _CONTAINER_DB_IDENTITY_PROBE,
        ],
        env=env,
        check=check,
    )
    payload = _parse_json_line(proc.stdout)
    payload["service"] = service
    payload["returncode"] = proc.returncode
    return proc.returncode, payload


def _run_container_identity_probes(
    cfg: _Phase8Config, env: dict[str, str]
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for service in ("api", "worker"):
        _, payload = _probe_container_db_identity(
            cfg,
            env,
            service=service,
            expected_user="app_user",
            check=True,
            log_name=f"container_identity_{service}",
        )
        if payload.get("current_user") != "app_user":
            raise RuntimeError(
                f"Container {service} identity mismatch: expected app_user"
            )
        if bool(payload.get("rolsuper")):
            raise RuntimeError(
                f"Container {service} identity invalid: superuser role detected"
            )
        checks.append(payload)
        (cfg.artifact_dir / f"phase8_container_identity_{service}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    rc, negative = _probe_container_db_identity(
        cfg,
        env,
        service="api",
        expected_user="phase8_invalid_expected_user",
        check=False,
        log_name="container_identity_negative_control",
    )
    if rc == 0:
        raise RuntimeError(
            "Container identity negative control did not fail with invalid expected user"
        )
    negative["passed"] = True
    probe_payload = {"services": checks, "negative_control": negative}
    (cfg.artifact_dir / "container_identity_probe.json").write_text(
        json.dumps(probe_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return probe_payload


def _wait_for_postgres(dsn: str, timeout_s: int = 120) -> None:
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with psycopg2.connect(dsn):
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"Postgres not ready after {timeout_s}s: {last_error}")


def _exec_sql(dsn: str, sql: str) -> None:
    with psycopg2.connect(dsn) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)


def _provision_ingress_dsn_file(cfg: _Phase8Config, env: dict[str, str]) -> None:
    """Write the file-mounted ingress credential for the auth root.

    XIV single secret-delivery law: file/secret mount only. The DSN
    targets the compose-network postgres host; the file lives on the
    runner and is bind-mounted read-only into the auth_ingress service
    via E2E_INGRESS_DSN_FILE. No process ever receives the legacy
    environment-string credential.
    """
    import tempfile

    db_name = _database_name_from_dsn(cfg.migration_dsn)
    compose_host = os.getenv("PHASE8_DB_COMPOSE_HOST", "postgres")
    ingress_dsn = (
        f"postgresql+asyncpg://app_ingress:app_ingress"
        f"@{compose_host}:5432/{db_name}"
    )
    fd, dsn_path = tempfile.mkstemp(prefix="b26_p2_ingress_dsn_p8_")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(ingress_dsn)
    env["E2E_INGRESS_DSN_FILE"] = dsn_path


def _provision_source_attestation_key(env: dict[str, str]) -> None:
    """Mount an ephemeral XXV source-attestation seed into the auth root.

    Full-physics e2e exercises the same required-attestation law as a
    deployment: the authentication root signs the provider-verified amount
    inside the ingress transaction. The seed is generated per run and never
    written to the repository or database.
    """
    import base64
    import tempfile

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )

    private_key = Ed25519PrivateKey.generate()
    private_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    private_seed = base64.urlsafe_b64encode(private_raw).rstrip(b"=").decode("ascii")
    fd, key_path = tempfile.mkstemp(prefix="b26_p2_source_attestation_key_p8_")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(private_seed)
    env["E2E_SOURCE_ATTESTATION_KEY_FILE"] = key_path
    env["E2E_SOURCE_ATTESTATION_REQUIRED"] = "true"


def _wait_for_auth_root(
    env: dict[str, str], timeout_s: int = 120
) -> None:
    """Wait until the dedicated auth root serves (relay dependency).

    The compose interpolation context (E2E_* lane variables) is passed
    explicitly: this probe must not depend on ambient process env.
    """
    import subprocess as _sp

    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        proc = _sp.run(
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.e2e.yml",
                "exec",
                "-T",
                "auth_ingress",
                "python",
                "-c",
                "import urllib.request;print(urllib.request.urlopen("
                "'http://localhost:8001/health/live', timeout=3).status)",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if proc.returncode == 0 and "200" in proc.stdout:
            return
        last_error = RuntimeError(proc.stdout[-200:] + proc.stderr[-200:])
        time.sleep(2)
    raise RuntimeError(f"auth root not ready after {timeout_s}s: {last_error}")


def _provision_runtime_identity(cfg: _Phase8Config) -> None:
    db_name = _database_name_from_dsn(cfg.migration_dsn)
    _exec_sql(
        cfg.migration_dsn,
        f"""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
            CREATE ROLE app_rw NOLOGIN;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ro') THEN
            CREATE ROLE app_ro NOLOGIN;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            CREATE USER app_user WITH PASSWORD 'app_user';
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
            CREATE USER app_worker WITH PASSWORD 'app_worker';
          END IF;
          -- B2.6-P2 Corrective XII: lanes serving verified webhooks
          -- through the API ingress boundary provision the ingress
          -- principal (role only; authority flows from the migrations
          -- under strict single-regime law).
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
            CREATE USER app_ingress WITH PASSWORD 'app_ingress';
          END IF;
        END$$;
        ALTER USER app_user WITH PASSWORD 'app_user';
        ALTER USER app_worker WITH PASSWORD 'app_worker';
        GRANT app_rw TO app_user;
        GRANT app_ro TO app_user;
        GRANT CONNECT ON DATABASE {db_name} TO app_user;
        GRANT CONNECT ON DATABASE {db_name} TO app_worker;
        GRANT USAGE ON SCHEMA public TO app_user;
        GRANT USAGE ON SCHEMA public TO app_worker;
        """,
    )


def _grant_runtime_privileges(cfg: _Phase8Config) -> None:
    _exec_sql(
        cfg.migration_dsn,
        """
        GRANT USAGE ON SCHEMA public TO app_user;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_user;
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'security') THEN
            GRANT USAGE ON SCHEMA security TO app_user;
            GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA security TO app_user;
          END IF;
        END$$;
        """,
    )


def _write_manifest(artifact_dir: Path) -> None:
    entries: list[tuple[str, str]] = []
    for path in sorted(artifact_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "manifest.sha256":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append((digest, str(path.relative_to(artifact_dir)).replace("\\", "/")))
    manifest_path = artifact_dir / "manifest.sha256"
    with manifest_path.open("w", encoding="utf-8") as handle:
        for digest, rel in entries:
            handle.write(f"{digest}  {rel}\n")


def _verify_manifest(artifact_dir: Path) -> None:
    manifest_path = artifact_dir / "manifest.sha256"
    if not manifest_path.exists():
        raise RuntimeError(f"Manifest not found: {manifest_path}")
    expected: dict[str, str] = {}
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise RuntimeError(f"Invalid manifest line: {line}")
        expected[parts[1]] = parts[0]

    actual: dict[str, str] = {}
    for path in sorted(artifact_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "manifest.sha256":
            continue
        rel = str(path.relative_to(artifact_dir)).replace("\\", "/")
        actual[rel] = hashlib.sha256(path.read_bytes()).hexdigest()

    if set(expected.keys()) != set(actual.keys()):
        missing = sorted(set(actual.keys()) - set(expected.keys()))
        extra = sorted(set(expected.keys()) - set(actual.keys()))
        raise RuntimeError(
            f"Manifest coverage mismatch; missing={missing[:5]} extra={extra[:5]}"
        )
    for rel, digest in actual.items():
        if expected.get(rel) != digest:
            raise RuntimeError(f"Manifest digest mismatch: {rel}")


def _build_closure_pack_zip(artifact_dir: Path) -> tuple[str, str]:
    zip_path = artifact_dir / "closure_pack_artifact.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(artifact_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.name == "closure_pack_artifact.zip":
                continue
            rel = str(path.relative_to(artifact_dir)).replace("\\", "/")
            archive.write(path, arcname=rel)
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sha_path = artifact_dir / "closure_pack_artifact.sha256"
    sha_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    return (zip_path.name, digest)


def _assert_secret_hygiene(log_path: Path) -> None:
    content = log_path.read_text(encoding="utf-8", errors="ignore")
    forbidden_patterns = [
        r"LLM_PROVIDER_API_KEY=(?!\*\*\*)\S+",
        r"Authorization:\s*Bearer\s+(?!\*\*\*)\S+",
        r"MIGRATION_DATABASE_URL=postgresql(?:\+asyncpg)?://",
        r"DATABASE_URL=postgresql(?:\+asyncpg)?://",
        r"CELERY_BROKER_URL=sqla\+postgresql://",
    ]
    for pattern in forbidden_patterns:
        if re.search(pattern, content):
            raise RuntimeError(
                f"Secret redaction gate failed; pattern matched: {pattern}"
            )


def _run_phase8(cfg: _Phase8Config, env: dict[str, str]) -> dict[str, Any]:
    gates: dict[str, str] = {}
    openapi_spec_sha256 = _canonical_openapi_spec_hash(cfg)
    run_authority = _run_authority(cfg)
    profile_metadata = _eg85_profile_metadata(cfg, env)
    eg85_evidence: dict[str, Any] = {}
    negative_controls: dict[str, Any] = {}
    container_identity_evidence: dict[str, Any] = {}
    llm_load_proc: subprocess.Popen[str] | None = None
    queue_probe_proc: subprocess.Popen[str] | None = None
    llm_load_log_handle: Any = None
    queue_probe_log_handle: Any = None
    queue_probe_artifact = cfg.artifact_dir / "phase8_worker_liveness_probe.json"

    def run_step(name: str, cmd: Sequence[str], *, cwd: Path | None = None) -> None:
        _run_logged(cfg, name=name, cmd=cmd, env=env, cwd=cwd)

    try:
        negative_controls["compose_missing_runtime_dsn"] = (
            _assert_compose_missing_runtime_dsn_fails(cfg, env)
        )
        run_step(
            "compose_up_substrate",
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.e2e.yml",
                "up",
                "-d",
                "--build",
                "postgres",
                "mock_platform",
            ],
        )
        _wait_for_postgres(cfg.migration_dsn)
        # XXI step 4: the composed postgres preloads pg_stat_statements
        # (track=all); create the extension so the intra-postgres split
        # probe can sample it. Fail-closed: a compose that lost the
        # preload raises here and fails the run.
        _exec_sql(
            cfg.migration_dsn,
            "CREATE EXTENSION IF NOT EXISTS pg_stat_statements",
        )
        _provision_runtime_identity(cfg)
        run_step(
            "alembic_upgrade",
            [sys.executable, "-m", "alembic", "upgrade", "head"],
        )
        _grant_runtime_privileges(cfg)
        run_step(
            "assert_runtime_identity",
            [
                sys.executable,
                "scripts/identity/assert_runtime_identity.py",
                "--runtime-dsn-env",
                "B07_P8_RUNTIME_DATABASE_URL",
                "--migration-dsn-env",
                "MIGRATION_DATABASE_URL",
                "--expected-runtime-user-env",
                "EXPECTED_RUNTIME_DB_USER",
            ],
        )

        run_step(
            "pytest_p7",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "backend/tests/test_b07_p7_ledger_cost_cache_audit.py",
            ],
        )
        run_step(
            "pytest_p5",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "backend/tests/integration/test_b07_p5_bayesian_timeout_runtime.py",
            ],
        )
        run_step(
            "pytest_p3_provider_swap",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "backend/tests/test_b07_p3_provider_controls.py",
                "-k",
                "provider_swap_config_only_proof or timeout_non_vacuous_negative_control",
            ],
        )
        run_step(
            "pytest_p6_router",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "backend/tests/test_b07_p6_complexity_router.py",
                "-k",
                "eg63 or eg65",
            ],
        )
        run_step(
            "pytest_boundary_enforcement",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "backend/tests/test_b07_p0_provider_boundary_enforcement.py",
            ],
        )
        gates["eg8_3_compute_safety"] = "pass"

        # XIV: provision the file-mounted ingress credential for the
        # dedicated auth root (single secret-delivery law; the API
        # never receives it) and boot the root alongside the relay.
        _provision_ingress_dsn_file(cfg, env)
        _provision_source_attestation_key(env)
        run_step(
            "compose_up_runtime",
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.e2e.yml",
                "up",
                "-d",
                "--build",
                "api",
                "auth_ingress",
                "worker",
            ],
        )
        _grant_runtime_privileges(cfg)
        _wait_for_auth_root(env)
        run_step("wait_health", [sys.executable, "scripts/wait_for_e2e_health.py"])
        run_step("wait_worker", [sys.executable, "scripts/wait_for_e2e_worker.py"])
        container_identity_evidence = _run_container_identity_probes(cfg, env)
        gates["eg8_1_startability_identity"] = "pass"

        run_step(
            "pytest_p4",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "backend/tests/integration/test_b07_p4_operational_readiness_e2e.py",
            ],
        )
        run_step(
            "pytest_p8_topology",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "backend/tests/integration/test_b07_p8_topology_closure_pack.py",
            ],
        )
        run_step(
            "pytest_p8_instrumentation",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "backend/tests/test_b07_p8_composed_instrumentation_fail_closed.py",
            ],
        )
        gates["eg8_2_unified_topologies"] = "pass"
        gates["eg8_4_ledger_audit_cost"] = "pass"
        gates["eg8_6_openapi_runtime_fidelity"] = "pass"

        # The LLM load must conduct real work across the whole R3 leg,
        # including the authority window (EG3.4 Test2). An interval that ends
        # before the authority window starts is a stale instrument and is
        # rejected below.
        llm_duration_s = _r3_leg_span_seconds(env) + 120
        llm_interval_s = 1.0 if cfg.full_physics else 0.5
        queue_probe_duration_s = max(
            int(env.get("R3_EG34_TEST2_DURATION_S", "60")) + 180,
            240,
        )
        queue_probe_log_path = cfg.logs_dir / "queue_liveness_probe.log"
        llm_load_log_path = cfg.logs_dir / "llm_background_load.log"
        queue_probe_log_handle = queue_probe_log_path.open("w", encoding="utf-8")
        llm_load_log_handle = llm_load_log_path.open("w", encoding="utf-8")
        queue_probe_proc = subprocess.Popen(
            [
                sys.executable,
                "scripts/phase8/queue_liveness_probe.py",
                "--db-url",
                cfg.runtime_sync_dsn,
                "--duration-s",
                str(queue_probe_duration_s),
                "--interval-s",
                "0.5",
                "--artifact",
                str(queue_probe_artifact),
            ],
            cwd=str(cfg.repo_root),
            env=env,
            stdout=queue_probe_log_handle,
            stderr=subprocess.STDOUT,
        )
        llm_load_artifact = cfg.artifact_dir / "phase8_llm_perf_probe.json"
        llm_load_proc = subprocess.Popen(
            [
                sys.executable,
                "scripts/phase8/llm_background_load.py",
                "--duration-s",
                str(llm_duration_s),
                "--interval-s",
                str(llm_interval_s),
                "--artifact",
                str(llm_load_artifact),
            ],
            cwd=str(cfg.repo_root),
            env=env,
            stdout=llm_load_log_handle,
            stderr=subprocess.STDOUT,
        )
        # Ordered-plan step 3: runner-wide CPU/starvation accounting for the
        # whole R3 leg (generator, api, auth root, postgres, workers).
        cpu_probe_artifact = cfg.artifact_dir / "phase8_runner_cpu_probe.json"
        cpu_probe_log_path = cfg.logs_dir / "runner_cpu_probe.log"
        cpu_probe_log_handle = cpu_probe_log_path.open("w", encoding="utf-8")
        cpu_probe_proc = subprocess.Popen(
            [
                sys.executable,
                "scripts/phase8/runner_cpu_probe.py",
                "--duration-s",
                str(llm_duration_s),
                "--interval-s",
                "2.0",
                "--artifact",
                str(cpu_probe_artifact),
                "--jsonl",
                str(cfg.logs_dir / "runner_cpu_probe.jsonl"),
            ],
            cwd=str(cfg.repo_root),
            env=env,
            stdout=cpu_probe_log_handle,
            stderr=subprocess.STDOUT,
        )
        # Ordered-plan step 4: intra-postgres split for the same leg.
        # pg_stat_statements (preloaded, track=all) is sampled here; the
        # per-leg split is derived post-hoc from the artefact's samples.
        pg_stat_probe_artifact = cfg.artifact_dir / "phase8_pg_stat_probe.json"
        pg_stat_probe_log_path = cfg.logs_dir / "pg_stat_probe.log"
        pg_stat_probe_log_handle = pg_stat_probe_log_path.open("w", encoding="utf-8")
        pg_stat_probe_proc = subprocess.Popen(
            [
                sys.executable,
                "scripts/phase8/pg_stat_probe.py",
                "--duration-s",
                str(llm_duration_s),
                "--interval-s",
                "5.0",
                "--artifact",
                str(pg_stat_probe_artifact),
                "--jsonl",
                str(cfg.logs_dir / "pg_stat_probe.jsonl"),
            ],
            cwd=str(cfg.repo_root),
            env=env,
            stdout=pg_stat_probe_log_handle,
            stderr=subprocess.STDOUT,
        )
        r3_step_error: Exception | None = None
        try:
            run_step(
                "r3_ingestion_under_fire",
                [sys.executable, "scripts/r3/ingestion_under_fire.py"],
            )
        except Exception as exc:  # noqa: BLE001 - diagnostics first, re-raised below
            r3_step_error = exc
        # Let the bounded helpers finish even when the R3 leg failed, so a
        # failing composed run still yields conduction and queue evidence.
        try:
            llm_load_returncode = llm_load_proc.wait(timeout=llm_duration_s + 180)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "llm_background_load.py did not exit before the wait deadline"
            ) from exc
        try:
            queue_probe_returncode = queue_probe_proc.wait(
                timeout=queue_probe_duration_s + 120
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "queue_liveness_probe.py did not exit before the wait deadline"
            ) from exc
        try:
            cpu_probe_returncode = cpu_probe_proc.wait(
                timeout=llm_duration_s + 180
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "runner_cpu_probe.py did not exit before the wait deadline"
            ) from exc
        try:
            pg_stat_probe_returncode = pg_stat_probe_proc.wait(
                timeout=llm_duration_s + 180
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "pg_stat_probe.py did not exit before the wait deadline"
            ) from exc

        r3_window = _extract_profile_window_best_effort(
            cfg.logs_dir / "r3_ingestion_under_fire.log",
            "EG3_4_Test2_Month18",
        )
        collect_phase8_sql_cmd = [
            sys.executable,
            "scripts/phase8/collect_sql_probes.py",
            "--db-url",
            cfg.runtime_sync_dsn,
            "--runtime-probe",
            str(cfg.artifact_dir / "runtime_db_probe.json"),
            "--llm-load-probe",
            str(llm_load_artifact),
            "--out-dir",
            str(cfg.artifact_dir / "sql"),
        ]
        if (
            cfg.full_physics
            and r3_window.get("window_start_utc")
            and r3_window.get("window_end_utc")
        ):
            collect_phase8_sql_cmd += [
                "--window-start",
                str(r3_window["window_start_utc"]),
                "--window-end",
                str(r3_window["window_end_utc"]),
            ]
        collect_error: Exception | None = None
        try:
            run_step("collect_phase8_sql", collect_phase8_sql_cmd)
        except Exception as exc:  # noqa: BLE001 - recorded in diagnostics
            collect_error = exc
        sql_summary_path = cfg.artifact_dir / "sql" / "phase8_sql_probe_summary.json"
        sql_probe_summary: dict[str, Any] = {}
        if sql_summary_path.exists():
            sql_probe_summary = json.loads(sql_summary_path.read_text(encoding="utf-8"))
        llm_probe_payload: dict[str, Any] = {}
        if llm_load_artifact.exists():
            try:
                loaded = json.loads(llm_load_artifact.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    llm_probe_payload = loaded
            except json.JSONDecodeError:
                llm_probe_payload = {}
        if r3_step_error is not None or collect_error is not None:
            failure_diagnostics = {
                "r3_step_error": str(r3_step_error) if r3_step_error else None,
                "r3_test2": r3_window,
                "llm_load_returncode": llm_load_returncode,
                "llm_load_status": llm_probe_payload.get("status"),
                "llm_load_error": llm_probe_payload.get("error"),
                "llm_load_dispatched_count": llm_probe_payload.get("dispatched_count"),
                "llm_load_started_at": llm_probe_payload.get("started_at"),
                "llm_load_finished_at": llm_probe_payload.get("finished_at"),
                "queue_probe_returncode": queue_probe_returncode,
                "cpu_probe_returncode": cpu_probe_returncode,
                "pg_stat_probe_returncode": pg_stat_probe_returncode,
                "collect_phase8_sql_error": str(collect_error) if collect_error else None,
                "perf_window": sql_probe_summary.get("perf_window"),
                "perf_composed_llm_calls": sql_probe_summary.get(
                    "perf_composed_llm_calls"
                ),
                "perf_composed_llm_api_calls": sql_probe_summary.get(
                    "perf_composed_llm_api_calls"
                ),
                "perf_composed_llm_audit_calls": sql_probe_summary.get(
                    "perf_composed_llm_audit_calls"
                ),
                "perf_revenue_ledger_rows_during_window": sql_probe_summary.get(
                    "perf_revenue_ledger_rows_during_window"
                ),
            }
            (
                cfg.artifact_dir / "phase8_failure_diagnostics.json"
            ).write_text(
                json.dumps(failure_diagnostics, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            try:
                _run_logged(
                    cfg,
                    name="compose_logs_failure",
                    cmd=[
                        "docker",
                        "compose",
                        "-f",
                        "docker-compose.e2e.yml",
                        "logs",
                        "--no-color",
                    ],
                    env=env,
                )
            except Exception:  # noqa: BLE001 - diagnostics are best-effort
                pass
        if r3_step_error is not None:
            raise r3_step_error
        if collect_error is not None:
            raise collect_error
        r3_profile = _extract_profile_metrics_from_r3_log(
            cfg.logs_dir / "r3_ingestion_under_fire.log",
            "EG3_4_Test2_Month18",
        )
        perf_llm_calls = int(sql_probe_summary.get("perf_composed_llm_calls", 0))
        perf_llm_api_calls = int(
            sql_probe_summary.get("perf_composed_llm_api_calls", 0)
        )
        perf_llm_audit_calls = int(
            sql_probe_summary.get("perf_composed_llm_audit_calls", 0)
        )
        perf_ledger_rows = int(
            sql_probe_summary.get("perf_revenue_ledger_rows_during_window", 0)
        )
        llm_probe_dispatched = int(llm_probe_payload.get("dispatched_count", 0) or 0)
        target_request_count = int(r3_profile.get("target_request_count", 0) or 0)
        observed_request_count = int(r3_profile.get("observed_request_count", 0) or 0)
        status_counts = r3_profile.get("http_status_counts", {})
        numeric_status_responses = (
            sum(
                int(v)
                for k, v in (
                    status_counts.items() if isinstance(status_counts, dict) else []
                )
                if str(k).isdigit()
            )
            if isinstance(status_counts, dict)
            else 0
        )
        timeout_count = int(r3_profile.get("http_timeout_count", 0) or 0)
        connection_error_count = int(r3_profile.get("http_connection_errors", 0) or 0)

        if cfg.full_physics:
            if (
                int(profile_metadata["target_rps"]) != 46
                or int(profile_metadata["duration_s"]) != 60
            ):
                raise RuntimeError(
                    "EG8.5 authority profile mismatch; expected 46 rps for 60s"
                )
            if int(float(r3_profile.get("target_rps", 0.0) or 0.0)) != 46:
                raise RuntimeError(
                    "EG8.5 target_rps drift detected in runtime verdict payload"
                )
            if int(r3_profile.get("duration_s", 0) or 0) != 60:
                raise RuntimeError(
                    "EG8.5 duration_s drift detected in runtime verdict payload"
                )

        if target_request_count <= 0 or observed_request_count <= 0:
            raise RuntimeError(
                "Composed performance evidence invalid: missing request accounting"
            )
        if observed_request_count < int(target_request_count * 0.99):
            raise RuntimeError(
                "Composed performance evidence invalid: observed_request_count below 99% of target"
            )
        if numeric_status_responses + timeout_count + connection_error_count < int(
            observed_request_count * 0.99
        ):
            raise RuntimeError(
                "Composed performance evidence invalid: response accounting does not match observed requests"
            )
        if int(r3_profile.get("window_canonical_rows", 0) or 0) <= 0:
            raise RuntimeError(
                "Composed performance evidence invalid: canonical row delta did not increase"
            )
        if not r3_profile.get("resource_stable", False):
            raise RuntimeError(
                "Composed performance evidence invalid: resource_stable=false"
            )
        if float(r3_profile.get("http_error_rate_percent", 100.0)) > 0.0:
            raise RuntimeError(
                "Composed performance evidence invalid: non-zero HTTP error rate"
            )

        if not queue_probe_artifact.exists():
            raise RuntimeError(
                "Worker liveness probe invalid: artifact missing "
                f"({queue_probe_artifact.name})"
            )
        worker_probe = json.loads(queue_probe_artifact.read_text(encoding="utf-8"))
        worker_summary = (
            worker_probe.get("summary", {}) if isinstance(worker_probe, dict) else {}
        )
        worker_sample_count = int(worker_summary.get("sample_count", 0) or 0)
        worker_peak_depth = int(worker_summary.get("max_total_messages", 0) or 0)
        worker_final_depth = int(worker_summary.get("final_total_messages", 0) or 0)
        worker_drain_rate = float(
            worker_summary.get("drain_rate_messages_per_s", 0.0) or 0.0
        )
        worker_drain_observed = (
            worker_drain_rate > 0 or worker_final_depth < worker_peak_depth
        )
        if worker_sample_count <= 0:
            raise RuntimeError(
                "Worker liveness probe invalid: no queue samples captured"
            )
        if worker_peak_depth <= 0:
            raise RuntimeError(
                "Worker liveness probe invalid: queue depth never increased above zero"
            )

        # Fail closed: a missing or failed helper, a stale or mismatched
        # interval, or absent conduction fails the gate. The workload, the
        # bars and the statistical cage are unchanged.
        composed_instrumentation = _validate_composed_instrumentation(
            full_physics=cfg.full_physics,
            llm_load_artifact=llm_load_artifact,
            llm_load_log=llm_load_log_path,
            queue_probe_log=queue_probe_log_path,
            cpu_probe_artifact=cpu_probe_artifact,
            cpu_probe_log=cpu_probe_log_path,
            pg_stat_probe_artifact=pg_stat_probe_artifact,
            pg_stat_probe_log=pg_stat_probe_log_path,
            llm_load_returncode=llm_load_returncode,
            queue_probe_returncode=queue_probe_returncode,
            cpu_probe_returncode=cpu_probe_returncode,
            pg_stat_probe_returncode=pg_stat_probe_returncode,
            worker_probe=worker_probe,
            r3_profile=r3_profile,
            perf_llm_calls=perf_llm_calls,
        )
        llm_activity_evidence = perf_llm_calls > 0

        # CI subset is a sanity gate only; authoritative EG3.4 certification is full physics only.
        gates[_eg85_gate_name(run_authority)] = "pass"
        eg85_evidence = {
            "run_authority": run_authority,
            "authoritative": run_authority == "full_physics",
            "gate_label": _eg85_gate_name(run_authority),
            **profile_metadata,
            "target_request_count": target_request_count,
            "requests_sent": observed_request_count,
            "responses_received": numeric_status_responses,
            "timeout_count": timeout_count,
            "connection_error_count": connection_error_count,
            "window_canonical_rows": int(
                r3_profile.get("window_canonical_rows", 0) or 0
            ),
            "p50_ms": r3_profile.get("latency_p50_ms"),
            "p95_ms": r3_profile.get("latency_p95_ms"),
            "p99_ms": r3_profile.get("latency_p99_ms"),
            "error_rate_percent": r3_profile.get("http_error_rate_percent"),
            "pii_violations": int(r3_profile.get("pii_key_hit_count_in_db", 0)),
            "duplicates": int(r3_profile.get("duplicate_canonical_keys_in_window", 0)),
            "dlq_count": int(r3_profile.get("dlq_rows_for_all_profile_keys", 0)),
            "llm_calls_during_window": perf_llm_calls,
            "llm_api_calls_during_window": perf_llm_api_calls,
            "llm_audit_rows_during_window": perf_llm_audit_calls,
            "ledger_rows_written_during_window": perf_ledger_rows,
            "llm_probe_dispatched": llm_probe_dispatched,
            "composed_instrumentation": composed_instrumentation,
            "worker_liveness": {
                "sample_count": worker_sample_count,
                "peak_queue_depth": worker_peak_depth,
                "final_queue_depth": worker_final_depth,
                "drain_rate_messages_per_s": worker_drain_rate,
                "drain_observed": worker_drain_observed,
                "llm_activity_evidence": llm_activity_evidence,
                "probe_artifact": str(
                    queue_probe_artifact.relative_to(cfg.artifact_dir)
                ),
            },
            "router_engaged": any(
                isinstance(row.get("provider_attempted"), str)
                and bool(row.get("provider_attempted").strip())
                for row in (sql_probe_summary.get("llm_outcomes") or [])
                if isinstance(row, dict)
            ),
            "safety_controls_verified_via_gate": gates.get("eg8_3_compute_safety")
            == "pass",
        }

        run_step(
            "compose_logs",
            ["docker", "compose", "-f", "docker-compose.e2e.yml", "logs", "--no-color"],
        )
        _assert_secret_hygiene(cfg.logs_dir / "compose_logs.log")
        gates["eg8_7_operational_readiness_pack"] = "pass"
        return {
            "run_authority": run_authority,
            "openapi_spec_sha256": openapi_spec_sha256,
            "gates": gates,
            "eg8_5": eg85_evidence,
            "negative_controls": negative_controls,
            "container_identity": container_identity_evidence,
        }
    finally:
        if llm_load_proc is not None and llm_load_proc.poll() is None:
            llm_load_proc.terminate()
            try:
                llm_load_proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                llm_load_proc.kill()
        if queue_probe_proc is not None and queue_probe_proc.poll() is None:
            queue_probe_proc.terminate()
            try:
                queue_probe_proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                queue_probe_proc.kill()
        for handle in (llm_load_log_handle, queue_probe_log_handle):
            if handle is not None:
                try:
                    handle.close()
                except Exception:  # noqa: BLE001
                    pass
        try:
            _run_logged(
                cfg,
                name="compose_teardown",
                cmd=["docker", "compose", "-f", "docker-compose.e2e.yml", "down", "-v"],
                env=env,
            )
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", default="artifacts/b07-phase8")
    parser.add_argument("--ci-subset", action="store_true")
    parser.add_argument("--full-physics", action="store_true")
    args = parser.parse_args()

    cfg = _default_config(
        artifact_dir=Path(args.artifact_dir),
        ci_subset=bool(args.ci_subset),
        full_physics=bool(args.full_physics),
    )
    _ensure_dirs(cfg)
    env = _build_env(cfg)

    run_authority = _run_authority(cfg)
    runner_physics = _collect_runner_physics(cfg, run_authority)
    summary = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run_authority": run_authority,
        "ci_subset": cfg.ci_subset,
        "full_physics": cfg.full_physics,
        "runner_physics_artifact": "runner_physics_probe.json",
        "runner_physics": runner_physics,
        "gates": {},
        "eg8_5": {},
        "negative_controls": {},
        "container_identity": {},
        "status": "failed",
    }
    try:
        run_result = _run_phase8(cfg, env)
        summary["openapi_spec_sha256"] = run_result["openapi_spec_sha256"]
        summary["gates"] = run_result["gates"]
        summary["eg8_5"] = run_result["eg8_5"]
        summary["negative_controls"] = run_result.get("negative_controls", {})
        summary["container_identity"] = run_result.get("container_identity", {})
        summary["status"] = "passed"
        return_code = 0
    except Exception as exc:  # noqa: BLE001
        summary["error"] = str(exc)
        print(f"PHASE8_PACK_FAILURE: {exc}", file=sys.stderr)
        for line in traceback.format_exc().splitlines():
            print(f"PHASE8_PACK_TRACEBACK: {line}", file=sys.stderr)
        return_code = 1
    finally:
        summary["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        canonical_summary = cfg.artifact_dir / "phase8_gate_summary.json"
        authority_summary = cfg.artifact_dir / _summary_filename_for_authority(
            run_authority
        )
        payload = json.dumps(summary, indent=2, sort_keys=True)
        canonical_summary.write_text(payload, encoding="utf-8")
        authority_summary.write_text(
            json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
        )
        zip_name, zip_sha256 = _build_closure_pack_zip(cfg.artifact_dir)
        (cfg.artifact_dir / "closure_pack_artifact_metadata.json").write_text(
            json.dumps(
                {
                    "name": zip_name,
                    "sha256": zip_sha256,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        _write_manifest(cfg.artifact_dir)
        _verify_manifest(cfg.artifact_dir)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
