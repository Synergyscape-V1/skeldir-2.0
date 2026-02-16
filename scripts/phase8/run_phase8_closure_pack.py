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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

import psycopg2


@dataclass(frozen=True)
class _Phase8Config:
    repo_root: Path
    artifact_dir: Path
    logs_dir: Path
    runtime_sync_dsn: str
    runtime_async_dsn: str
    migration_dsn: str
    compose_runtime_async_dsn: str
    compose_runtime_sync_dsn: str
    compose_broker_dsn: str
    compose_result_dsn: str
    api_base_url: str
    mock_base_url: str
    ci_subset: bool
    full_physics: bool


_R3_VERDICT_BEGIN = re.compile(r"^R3_VERDICT_BEGIN\s+(.+)$")
_R3_VERDICT_END = re.compile(r"^R3_VERDICT_END\s+(.+)$")


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
    memory_limit_v1 = _read_text_if_exists(Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"))

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
        cfg.repo_root / "api-contracts" / "dist" / "openapi" / "v1" / "reconciliation.bundled.yaml"
    )
    attribution = (
        cfg.repo_root / "api-contracts" / "dist" / "openapi" / "v1" / "attribution.bundled.yaml"
    )
    if not reconciliation.exists() or not attribution.exists():
        missing: list[str] = []
        if not reconciliation.exists():
            missing.append(str(reconciliation))
        if not attribution.exists():
            missing.append(str(attribution))
        raise RuntimeError(f"Canonical OpenAPI bundle(s) missing: {', '.join(missing)}")
    joined = f"{_sha256_file(reconciliation)}|{_sha256_file(attribution)}".encode("utf-8")
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


def _extract_profile_metrics_from_r3_log(log_path: Path, profile_name: str) -> dict[str, Any]:
    verdicts = _parse_r3_verdicts(log_path)
    payload = verdicts.get(profile_name)
    if not isinstance(payload, dict):
        raise RuntimeError(f"R3 profile verdict not found in log: {profile_name}")
    if not bool(payload.get("passed")):
        raise RuntimeError(f"R3 profile verdict failed: {profile_name}")
    return payload


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


def _default_config(*, artifact_dir: Path, ci_subset: bool, full_physics: bool) -> _Phase8Config:
    db_name = os.getenv("PHASE8_DB_NAME", "skeldir_e2e")
    db_host = os.getenv("PHASE8_DB_HOST", "127.0.0.1")
    db_compose_host = os.getenv("PHASE8_DB_COMPOSE_HOST", "postgres")
    admin_user = os.getenv("PHASE8_DB_ADMIN_USER", "skeldir")
    admin_pass = os.getenv("PHASE8_DB_ADMIN_PASS", "skeldir_e2e")
    runtime_user = os.getenv("PHASE8_RUNTIME_DB_USER", "app_user")
    runtime_pass = os.getenv("PHASE8_RUNTIME_DB_PASS", "app_user")
    api_base_url = os.getenv("E2E_API_BASE_URL", "http://127.0.0.1:8000")
    mock_base_url = os.getenv("E2E_MOCK_BASE_URL", "http://127.0.0.1:8080")

    runtime_sync = f"postgresql://{runtime_user}:{runtime_pass}@{db_host}:5432/{db_name}"
    runtime_async = f"postgresql+asyncpg://{runtime_user}:{runtime_pass}@{db_host}:5432/{db_name}"
    migration = f"postgresql://{admin_user}:{admin_pass}@{db_host}:5432/{db_name}"
    compose_runtime_async = (
        f"postgresql+asyncpg://{runtime_user}:{runtime_pass}@{db_compose_host}:5432/{db_name}"
    )
    compose_runtime_sync = f"postgresql://{runtime_user}:{runtime_pass}@{db_compose_host}:5432/{db_name}"

    return _Phase8Config(
        repo_root=_repo_root(),
        artifact_dir=artifact_dir,
        logs_dir=artifact_dir / "logs",
        runtime_sync_dsn=runtime_sync,
        runtime_async_dsn=runtime_async,
        migration_dsn=migration,
        compose_runtime_async_dsn=compose_runtime_async,
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
            "B07_P4_RUNTIME_DATABASE_URL": cfg.runtime_sync_dsn,
            "B07_P2_ARTIFACT_DIR": str(cfg.artifact_dir),
            "B07_P4_ARTIFACT_DIR": str(cfg.artifact_dir),
            "B07_P8_ARTIFACT_DIR": str(cfg.artifact_dir),
            "E2E_API_BASE_URL": cfg.api_base_url,
            "E2E_MOCK_BASE_URL": cfg.mock_base_url,
            "E2E_DB_URL": cfg.runtime_sync_dsn,
            "E2E_WAIT_TIMEOUT_S": "120",
            "AUTH_JWT_SECRET": os.getenv("AUTH_JWT_SECRET", "e2e-secret"),
            "AUTH_JWT_ALGORITHM": os.getenv("AUTH_JWT_ALGORITHM", "HS256"),
            "AUTH_JWT_ISSUER": os.getenv("AUTH_JWT_ISSUER", "https://issuer.skeldir.test"),
            "AUTH_JWT_AUDIENCE": os.getenv("AUTH_JWT_AUDIENCE", "skeldir-api"),
            "INGESTION_FOLLOWUP_TASKS_ENABLED": "true",
            "E2E_DATABASE_URL": cfg.compose_runtime_async_dsn,
            "E2E_CELERY_BROKER_URL": cfg.compose_broker_dsn,
            "E2E_CELERY_RESULT_BACKEND": cfg.compose_result_dsn,
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
        env.update(
            {
                # Full-physics authority is encoded by EG3.4 Test2 (46 rps), not by high-N ladder replay storms.
                # Keep ladder bounded by default so hosted runners can reach the authoritative profile gate.
                "R3_LADDER": os.getenv("R3_LADDER", "50"),
                "R3_CONCURRENCY": os.getenv("R3_CONCURRENCY", "80"),
                "R3_TIMEOUT_S": os.getenv("R3_TIMEOUT_S", "10"),
                "R3_NULL_BENCHMARK": os.getenv("R3_NULL_BENCHMARK", "1"),
                "R3_NULL_BENCHMARK_TARGET_RPS": os.getenv("R3_NULL_BENCHMARK_TARGET_RPS", "50"),
                "R3_NULL_BENCHMARK_DURATION_S": os.getenv("R3_NULL_BENCHMARK_DURATION_S", "60"),
                "R3_NULL_BENCHMARK_MIN_RPS": os.getenv("R3_NULL_BENCHMARK_MIN_RPS", "50"),
                "R3_EG34_P95_MAX_MS": os.getenv("R3_EG34_P95_MAX_MS", "2000"),
                "R3_EG34_TEST1_RPS": os.getenv("R3_EG34_TEST1_RPS", "29"),
                "R3_EG34_TEST1_DURATION_S": os.getenv("R3_EG34_TEST1_DURATION_S", "60"),
                "R3_EG34_TEST2_RPS": os.getenv("R3_EG34_TEST2_RPS", "46"),
                "R3_EG34_TEST2_DURATION_S": os.getenv("R3_EG34_TEST2_DURATION_S", "60"),
                "R3_EG34_TEST3_RPS": os.getenv("R3_EG34_TEST3_RPS", "5"),
                "R3_EG34_TEST3_DURATION_S": os.getenv("R3_EG34_TEST3_DURATION_S", "300"),
                "E2E_ENVIRONMENT": os.getenv("E2E_ENVIRONMENT", "staging"),
                "E2E_API_ENVIRONMENT": os.getenv("E2E_API_ENVIRONMENT", "staging"),
                "E2E_WORKER_ENVIRONMENT": os.getenv("E2E_WORKER_ENVIRONMENT", "test"),
                "E2E_DATABASE_FORCE_POOLING": os.getenv("E2E_DATABASE_FORCE_POOLING", "0"),
                "E2E_DATABASE_POOL_SIZE": os.getenv("E2E_DATABASE_POOL_SIZE", "20"),
                "E2E_DATABASE_MAX_OVERFLOW": os.getenv("E2E_DATABASE_MAX_OVERFLOW", "0"),
                "E2E_API_DATABASE_FORCE_POOLING": os.getenv("E2E_API_DATABASE_FORCE_POOLING", "1"),
                "E2E_API_DATABASE_POOL_SIZE": os.getenv("E2E_API_DATABASE_POOL_SIZE", "40"),
                "E2E_API_DATABASE_MAX_OVERFLOW": os.getenv("E2E_API_DATABASE_MAX_OVERFLOW", "20"),
                "E2E_WORKER_DATABASE_FORCE_POOLING": os.getenv("E2E_WORKER_DATABASE_FORCE_POOLING", "0"),
                "E2E_WORKER_DATABASE_POOL_SIZE": os.getenv("E2E_WORKER_DATABASE_POOL_SIZE", "20"),
                "E2E_WORKER_DATABASE_MAX_OVERFLOW": os.getenv("E2E_WORKER_DATABASE_MAX_OVERFLOW", "0"),
                "E2E_API_WORKERS": os.getenv("E2E_API_WORKERS", str(api_workers)),
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
        END$$;
        ALTER USER app_user WITH PASSWORD 'app_user';
        GRANT app_rw TO app_user;
        GRANT app_ro TO app_user;
        GRANT CONNECT ON DATABASE {db_name} TO app_user;
        GRANT USAGE ON SCHEMA public TO app_user;
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
            raise RuntimeError(f"Secret redaction gate failed; pattern matched: {pattern}")


def _run_phase8(cfg: _Phase8Config, env: dict[str, str]) -> dict[str, Any]:
    gates: dict[str, str] = {}
    openapi_spec_sha256 = _canonical_openapi_spec_hash(cfg)
    run_authority = _run_authority(cfg)
    profile_metadata = _eg85_profile_metadata(cfg, env)
    eg85_evidence: dict[str, Any] = {}
    llm_load_proc: subprocess.Popen[str] | None = None
    queue_probe_proc: subprocess.Popen[str] | None = None
    queue_probe_artifact = cfg.artifact_dir / "phase8_worker_liveness_probe.json"

    def run_step(name: str, cmd: Sequence[str], *, cwd: Path | None = None) -> None:
        _run_logged(cfg, name=name, cmd=cmd, env=env, cwd=cwd)

    try:
        run_step(
            "compose_up_substrate",
            ["docker", "compose", "-f", "docker-compose.e2e.yml", "up", "-d", "--build", "postgres", "mock_platform"],
        )
        _wait_for_postgres(cfg.migration_dsn)
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
        gates["eg8_1_startability_identity"] = "pass"

        run_step("pytest_p7", [sys.executable, "-m", "pytest", "-q", "backend/tests/test_b07_p7_ledger_cost_cache_audit.py"])
        run_step(
            "pytest_p5",
            [sys.executable, "-m", "pytest", "-q", "backend/tests/integration/test_b07_p5_bayesian_timeout_runtime.py"],
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
            [sys.executable, "-m", "pytest", "-q", "backend/tests/test_b07_p0_provider_boundary_enforcement.py"],
        )
        gates["eg8_3_compute_safety"] = "pass"

        run_step(
            "compose_up_runtime",
            ["docker", "compose", "-f", "docker-compose.e2e.yml", "up", "-d", "--build", "api", "worker"],
        )
        _grant_runtime_privileges(cfg)
        run_step("wait_health", [sys.executable, "scripts/wait_for_e2e_health.py"])
        run_step("wait_worker", [sys.executable, "scripts/wait_for_e2e_worker.py"])

        run_step(
            "pytest_p4",
            [sys.executable, "-m", "pytest", "-q", "backend/tests/integration/test_b07_p4_operational_readiness_e2e.py"],
        )
        run_step(
            "pytest_p8_topology",
            [sys.executable, "-m", "pytest", "-q", "backend/tests/integration/test_b07_p8_topology_closure_pack.py"],
        )
        gates["eg8_2_unified_topologies"] = "pass"
        gates["eg8_4_ledger_audit_cost"] = "pass"
        gates["eg8_6_openapi_runtime_fidelity"] = "pass"

        llm_duration_s = 120 if not cfg.ci_subset else 600
        llm_interval_s = 1.0 if cfg.full_physics else 0.5
        queue_probe_duration_s = max(
            int(env.get("R3_EG34_TEST2_DURATION_S", "60")) + 180,
            240,
        )
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
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
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
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        run_step("r3_ingestion_under_fire", [sys.executable, "scripts/r3/ingestion_under_fire.py"])
        if llm_load_proc is not None:
            llm_load_proc.wait(timeout=llm_duration_s + 120)
        if queue_probe_proc is not None:
            queue_probe_proc.wait(timeout=queue_probe_duration_s + 60)

        run_step(
            "collect_phase8_sql",
            [
                sys.executable,
                "scripts/phase8/collect_sql_probes.py",
                "--db-url",
                cfg.runtime_sync_dsn,
                "--runtime-probe",
                str(cfg.artifact_dir / "runtime_db_probe.json"),
                "--llm-load-probe",
                str(cfg.artifact_dir / "phase8_llm_perf_probe.json"),
                "--out-dir",
                str(cfg.artifact_dir / "sql"),
            ],
        )
        sql_probe_summary = json.loads(
            (cfg.artifact_dir / "sql" / "phase8_sql_probe_summary.json").read_text(
                encoding="utf-8"
            )
        )
        perf_llm_calls = int(sql_probe_summary.get("perf_composed_llm_calls", 0))
        perf_llm_api_calls = int(sql_probe_summary.get("perf_composed_llm_api_calls", 0))
        perf_llm_audit_calls = int(sql_probe_summary.get("perf_composed_llm_audit_calls", 0))
        perf_ledger_rows = int(sql_probe_summary.get("perf_revenue_ledger_rows_during_window", 0))
        if perf_llm_calls <= 0:
            llm_probe = json.loads(llm_load_artifact.read_text(encoding="utf-8"))
            dispatched = int(llm_probe.get("dispatched_count", 0))
            if dispatched <= 0:
                raise RuntimeError(
                    "Composed performance evidence invalid: no llm_api_calls during ingestion load window"
                )
        r3_profile = _extract_profile_metrics_from_r3_log(
            cfg.logs_dir / "r3_ingestion_under_fire.log",
            "EG3_4_Test2_Month18",
        )
        target_request_count = int(r3_profile.get("target_request_count", 0) or 0)
        observed_request_count = int(r3_profile.get("observed_request_count", 0) or 0)
        status_counts = r3_profile.get("http_status_counts", {})
        numeric_status_responses = (
            sum(
                int(v)
                for k, v in (status_counts.items() if isinstance(status_counts, dict) else [])
                if str(k).isdigit()
            )
            if isinstance(status_counts, dict)
            else 0
        )
        timeout_count = int(r3_profile.get("http_timeout_count", 0) or 0)
        connection_error_count = int(r3_profile.get("http_connection_errors", 0) or 0)

        if cfg.full_physics:
            if int(profile_metadata["target_rps"]) != 46 or int(profile_metadata["duration_s"]) != 60:
                raise RuntimeError("EG8.5 authority profile mismatch; expected 46 rps for 60s")
            if int(float(r3_profile.get("target_rps", 0.0) or 0.0)) != 46:
                raise RuntimeError("EG8.5 target_rps drift detected in runtime verdict payload")
            if int(r3_profile.get("duration_s", 0) or 0) != 60:
                raise RuntimeError("EG8.5 duration_s drift detected in runtime verdict payload")

        if target_request_count <= 0 or observed_request_count <= 0:
            raise RuntimeError("Composed performance evidence invalid: missing request accounting")
        if observed_request_count < int(target_request_count * 0.99):
            raise RuntimeError(
                "Composed performance evidence invalid: observed_request_count below 99% of target"
            )
        if numeric_status_responses + timeout_count + connection_error_count < int(observed_request_count * 0.99):
            raise RuntimeError(
                "Composed performance evidence invalid: response accounting does not match observed requests"
            )
        if int(r3_profile.get("window_canonical_rows", 0) or 0) <= 0:
            raise RuntimeError(
                "Composed performance evidence invalid: canonical row delta did not increase"
            )
        if not r3_profile.get("resource_stable", False):
            raise RuntimeError("Composed performance evidence invalid: resource_stable=false")
        if float(r3_profile.get("http_error_rate_percent", 100.0)) > 0.0:
            raise RuntimeError("Composed performance evidence invalid: non-zero HTTP error rate")

        worker_probe = json.loads(queue_probe_artifact.read_text(encoding="utf-8"))
        worker_summary = worker_probe.get("summary", {}) if isinstance(worker_probe, dict) else {}
        worker_sample_count = int(worker_summary.get("sample_count", 0) or 0)
        worker_peak_depth = int(worker_summary.get("max_total_messages", 0) or 0)
        worker_final_depth = int(worker_summary.get("final_total_messages", 0) or 0)
        worker_drain_rate = float(worker_summary.get("drain_rate_messages_per_s", 0.0) or 0.0)
        if worker_sample_count <= 0:
            raise RuntimeError("Worker liveness probe invalid: no queue samples captured")
        if worker_peak_depth <= 0:
            raise RuntimeError("Worker liveness probe invalid: queue depth never increased above zero")
        if cfg.full_physics and worker_drain_rate <= 0 and worker_final_depth >= worker_peak_depth:
            raise RuntimeError("Worker liveness probe invalid: queue drain rate is non-positive")

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
            "window_canonical_rows": int(r3_profile.get("window_canonical_rows", 0) or 0),
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
            "worker_liveness": {
                "sample_count": worker_sample_count,
                "peak_queue_depth": worker_peak_depth,
                "final_queue_depth": worker_final_depth,
                "drain_rate_messages_per_s": worker_drain_rate,
                "probe_artifact": str(queue_probe_artifact.relative_to(cfg.artifact_dir)),
            },
            "router_engaged": any(
                isinstance(row.get("provider_attempted"), str)
                and bool(row.get("provider_attempted").strip())
                for row in (sql_probe_summary.get("llm_outcomes") or [])
                if isinstance(row, dict)
            ),
            "safety_controls_verified_via_gate": gates.get("eg8_3_compute_safety") == "pass",
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
        "status": "failed",
    }
    try:
        run_result = _run_phase8(cfg, env)
        summary["openapi_spec_sha256"] = run_result["openapi_spec_sha256"]
        summary["gates"] = run_result["gates"]
        summary["eg8_5"] = run_result["eg8_5"]
        summary["status"] = "passed"
        return_code = 0
    except Exception as exc:  # noqa: BLE001
        summary["error"] = str(exc)
        return_code = 1
    finally:
        summary["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        canonical_summary = cfg.artifact_dir / "phase8_gate_summary.json"
        authority_summary = cfg.artifact_dir / _summary_filename_for_authority(run_authority)
        payload = json.dumps(summary, indent=2, sort_keys=True)
        canonical_summary.write_text(
            payload, encoding="utf-8"
        )
        authority_summary.write_text(
            json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
        )
        _write_manifest(cfg.artifact_dir)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
