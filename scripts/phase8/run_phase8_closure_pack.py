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
from pathlib import Path
from typing import Sequence
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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


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
        env.update(
            {
                "R3_LADDER": os.getenv("R3_LADDER", "50,250,1000"),
                "R3_CONCURRENCY": os.getenv("R3_CONCURRENCY", "200"),
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


def _run_phase8(cfg: _Phase8Config, env: dict[str, str]) -> dict[str, str]:
    gates: dict[str, str] = {}
    llm_load_proc: subprocess.Popen[str] | None = None

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
        llm_load_artifact = cfg.artifact_dir / "phase8_llm_perf_probe.json"
        llm_load_proc = subprocess.Popen(
            [
                sys.executable,
                "scripts/phase8/llm_background_load.py",
                "--duration-s",
                str(llm_duration_s),
                "--interval-s",
                "0.5",
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
        if int(sql_probe_summary.get("perf_composed_llm_calls", 0)) <= 0:
            raise RuntimeError(
                "Composed performance evidence invalid: no llm_api_calls during ingestion load window"
            )
        gates["eg8_5_composed_ingestion_perf"] = "pass"

        run_step(
            "compose_logs",
            ["docker", "compose", "-f", "docker-compose.e2e.yml", "logs", "--no-color"],
        )
        _assert_secret_hygiene(cfg.logs_dir / "compose_logs.log")
        gates["eg8_7_operational_readiness_pack"] = "pass"
        return gates
    finally:
        if llm_load_proc is not None and llm_load_proc.poll() is None:
            llm_load_proc.terminate()
            try:
                llm_load_proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                llm_load_proc.kill()
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

    summary = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ci_subset": cfg.ci_subset,
        "full_physics": cfg.full_physics,
        "gates": {},
        "status": "failed",
    }
    try:
        summary["gates"] = _run_phase8(cfg, env)
        summary["status"] = "passed"
        return_code = 0
    except Exception as exc:  # noqa: BLE001
        summary["error"] = str(exc)
        return_code = 1
    finally:
        summary["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        (cfg.artifact_dir / "phase8_gate_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
        )
        _write_manifest(cfg.artifact_dir)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
