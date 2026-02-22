#!/usr/bin/env python3
"""
Generate/validate the B0.5.5 Phase 4 CI evidence bundle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable
from scripts.security.db_secret_access import resolve_runtime_database_url


REQUIRED_FILES = [
    "MANIFEST.json",
    "SCHEMA/schema.sql",
    "SCHEMA/catalog_constraints.json",
    "ALEMBIC/current.txt",
    "ALEMBIC/heads.txt",
    "ALEMBIC/history.txt",
    "LOGS/pytest_b055.log",
    "LOGS/migrations.log",
    "LOGS/hermeticity_scan.log",
    "LOGS/determinism_scan.log",
    "ENV/git_sha.txt",
    "ENV/python_version.txt",
    "ENV/pip_freeze.txt",
    "ENV/ci_context.json",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def normalize_db_url(db_url: str) -> str:
    if db_url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + db_url[len("postgresql+asyncpg://") :]
    if db_url.startswith("postgresql+psycopg://"):
        return "postgresql://" + db_url[len("postgresql+psycopg://") :]
    return db_url


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_cmd(cmd: Iterable[str], cwd: Path | None = None, env: Dict[str, str] | None = None) -> str:
    cmd_list = list(cmd)
    result = subprocess.run(
        cmd_list,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {cmd_list[0]}\n{result.stdout}")
    return result.stdout


def sha256_hex(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate(bundle_dir: Path, db_url: str) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "ALEMBIC").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "SCHEMA").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "LOGS").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "ENV").mkdir(parents=True, exist_ok=True)

    normalized_db_url = normalize_db_url(db_url)
    env = dict(os.environ)
    env["DATABASE_URL"] = normalized_db_url

    repo = repo_root()
    workflow_sha = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo).strip()
    pr_head_sha = os.environ.get("PR_HEAD_SHA") or os.environ.get("B055_PR_HEAD_SHA") or workflow_sha
    adjudicated_sha = os.environ.get("ADJUDICATED_SHA") or pr_head_sha
    github_sha = os.environ.get("GITHUB_SHA")
    write_text(
        bundle_dir / "ENV/git_sha.txt",
        (
            f"adjudicated_sha={adjudicated_sha}\n"
            f"pr_head_sha={pr_head_sha}\n"
            f"github_sha={github_sha}\n"
            f"workflow_sha={workflow_sha}\n"
        ),
    )
    write_text(bundle_dir / "ENV/python_version.txt", f"{sys.version}\n")

    pip_freeze = run_cmd([sys.executable, "-m", "pip", "freeze"], cwd=repo)
    write_text(bundle_dir / "ENV/pip_freeze.txt", pip_freeze)

    hermeticity_log = bundle_dir / "LOGS" / "hermeticity_scan.log"
    run_cmd(
        [sys.executable, "scripts/ci/enforce_runtime_hermeticity.py", "--output", str(hermeticity_log)],
        cwd=repo,
    )
    determinism_log = bundle_dir / "LOGS" / "determinism_scan.log"
    run_cmd(
        [sys.executable, "scripts/ci/enforce_runtime_determinism.py", "--output", str(determinism_log)],
        cwd=repo,
    )

    ci_context = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "adjudicated_sha": adjudicated_sha,
        "github_sha": github_sha,
        "pr_head_sha": pr_head_sha,
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_run_number": os.environ.get("GITHUB_RUN_NUMBER"),
        "github_workflow": os.environ.get("GITHUB_WORKFLOW"),
        "github_job": os.environ.get("GITHUB_JOB"),
        "github_ref": os.environ.get("GITHUB_REF"),
        "github_actor": os.environ.get("GITHUB_ACTOR"),
        "github_repository": os.environ.get("GITHUB_REPOSITORY"),
    }
    write_text(bundle_dir / "ENV/ci_context.json", json.dumps(ci_context, indent=2, sort_keys=True))

    write_text(bundle_dir / "ALEMBIC/current.txt", run_cmd(["alembic", "current"], cwd=repo, env=env))
    write_text(bundle_dir / "ALEMBIC/heads.txt", run_cmd(["alembic", "heads"], cwd=repo, env=env))
    write_text(bundle_dir / "ALEMBIC/history.txt", run_cmd(["alembic", "history"], cwd=repo, env=env))

    schema_path = bundle_dir / "SCHEMA/schema.sql"
    with schema_path.open("wb") as fh:
        result = subprocess.run(
            ["pg_dump", "--schema-only", "--no-owner", "--no-privileges", normalized_db_url],
            stdout=fh,
            stderr=subprocess.PIPE,
            check=False,
        )
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed ({result.returncode}): {result.stderr.decode('utf-8', errors='replace')}")

    constraints_sql = """
    SELECT COALESCE(json_agg(row_to_json(t)), '[]'::json)
    FROM (
        SELECT
            con.conname AS constraint_name,
            rel.relname AS table_name,
            con.contype AS constraint_type,
            ARRAY(
                SELECT att.attname
                FROM unnest(con.conkey) WITH ORDINALITY AS k(attnum, ordinality)
                JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = k.attnum
                ORDER BY k.ordinality
            ) AS columns
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        WHERE nsp.nspname = 'public'
          AND rel.relkind = 'r'
        ORDER BY rel.relname, con.conname
    ) t;
    """.strip()

    constraints_raw = run_cmd(
        ["psql", normalized_db_url, "-t", "-A", "-c", constraints_sql],
        cwd=repo,
        env=env,
    ).strip()
    try:
        constraints_json = json.loads(constraints_raw or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"pg_constraint JSON parse failed: {exc}\nRaw:\n{constraints_raw}") from exc
    write_text(
        bundle_dir / "SCHEMA/catalog_constraints.json",
        json.dumps(constraints_json, indent=2, sort_keys=True),
    )

    missing_logs = [
        path
        for path in (
            "LOGS/migrations.log",
            "LOGS/pytest_b055.log",
            "LOGS/hermeticity_scan.log",
            "LOGS/determinism_scan.log",
        )
        if not (bundle_dir / path).exists()
    ]
    if missing_logs:
        raise RuntimeError(f"Missing required log files: {', '.join(missing_logs)}")

    manifest_files = {}
    for rel_path in REQUIRED_FILES:
        if rel_path == "MANIFEST.json":
            continue
        file_path = bundle_dir / rel_path
        if not file_path.exists():
            raise RuntimeError(f"Required evidence file missing: {rel_path}")
        size_bytes = file_path.stat().st_size
        if size_bytes == 0:
            raise RuntimeError(f"Required evidence file is empty: {rel_path}")
        manifest_files[rel_path] = {
            "sha256": sha256_hex(file_path),
            "size_bytes": size_bytes,
        }

    manifest = {
        "bundle_name": "b055_evidence_bundle",
        "bundle_dir": str(bundle_dir),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "adjudicated_sha": adjudicated_sha,
        "github_sha": github_sha,
        "pr_head_sha": pr_head_sha,
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "git_sha": adjudicated_sha,
        "workflow_sha": workflow_sha,
        "required_files": REQUIRED_FILES,
        "files": dict(sorted(manifest_files.items())),
    }
    write_text(bundle_dir / "MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True))


def validate(bundle_dir: Path) -> None:
    manifest_path = bundle_dir / "MANIFEST.json"
    if not manifest_path.exists():
        raise RuntimeError("MANIFEST.json missing")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required_files = manifest.get("required_files")
    if required_files is None:
        raise RuntimeError("Manifest missing required_files")

    expected_set = set(REQUIRED_FILES)
    if set(required_files) != expected_set:
        raise RuntimeError(
            f"Manifest required_files mismatch. Expected={sorted(expected_set)} "
            f"Got={sorted(set(required_files))}"
        )

    files = manifest.get("files")
    if files is None:
        raise RuntimeError("Manifest missing files mapping")

    expected_files = expected_set - {"MANIFEST.json"}
    if set(files.keys()) != expected_files:
        raise RuntimeError(
            f"Manifest files mismatch. Expected={sorted(expected_files)} Got={sorted(set(files.keys()))}"
        )

    for rel_path, meta in files.items():
        file_path = bundle_dir / rel_path
        if not file_path.exists():
            raise RuntimeError(f"Missing file: {rel_path}")
        size_bytes = file_path.stat().st_size
        if size_bytes == 0:
            raise RuntimeError(f"Empty file: {rel_path}")
        expected_size = meta.get("size_bytes")
        if expected_size != size_bytes:
            raise RuntimeError(f"Size mismatch for {rel_path}: expected {expected_size}, got {size_bytes}")
        expected_sha = meta.get("sha256")
        actual_sha = sha256_hex(file_path)
        if expected_sha != actual_sha:
            raise RuntimeError(f"SHA mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}")

    print("B055 evidence manifest validation OK")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B055 evidence bundle generator/validator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen = subparsers.add_parser("generate", help="Generate evidence bundle")
    gen.add_argument("--bundle-dir", required=True, help="Bundle output directory")
    gen.add_argument("--database-url", default=None, help="Database URL override")

    val = subparsers.add_parser("validate", help="Validate evidence bundle manifest")
    val.add_argument("--bundle-dir", required=True, help="Bundle directory to validate")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle_dir = Path(args.bundle_dir)
    if not bundle_dir.is_absolute():
        bundle_dir = repo_root() / bundle_dir

    if args.command == "generate":
        db_url = args.database_url or resolve_runtime_database_url()
        if not db_url:
            raise RuntimeError("DATABASE_URL not set and --database-url not provided")
        generate(bundle_dir, db_url)
        return 0

    if args.command == "validate":
        validate(bundle_dir)
        return 0

    raise RuntimeError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
