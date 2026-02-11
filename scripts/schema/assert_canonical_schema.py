#!/usr/bin/env python3
"""Deterministic schema authority check: migrations -> dump -> normalize -> diff."""

from __future__ import annotations

import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable


DEFAULT_DUMP_IMAGE = "postgres@sha256:b3968e348b48f1198cc6de6611d055dbad91cd561b7990c406c3fc28d7095b21"


def _run(cmd: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, env=env, cwd=cwd, check=False)


def _normalize_schema(text: str) -> str:
    not_null_constraint_re = re.compile(r"\bCONSTRAINT\s+[A-Za-z0-9_]+\s+NOT\s+NULL\b")
    qualifier_re = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\.")

    out: list[str] = []
    in_matview_query = False
    for line in text.splitlines():
        if line.startswith("--"):
            continue
        if line.startswith("\\restrict"):
            continue
        if line.startswith("\\unrestrict"):
            continue
        if line.startswith("SET "):
            continue
        if line.startswith("SELECT pg_catalog.set_config"):
            continue
        if line.startswith("COMMENT ON EXTENSION"):
            continue
        norm = line.rstrip()
        if "--" in norm:
            norm = norm.split("--", 1)[0].rstrip()
        norm = not_null_constraint_re.sub("NOT NULL", norm)
        if norm.startswith("CREATE MATERIALIZED VIEW "):
            in_matview_query = True
        # Cross-version pg_dump may qualify column refs differently in SELECT bodies.
        if norm.lstrip().startswith(
            (
                "SELECT ",
                "FROM ",
                "WHERE ",
                "GROUP BY ",
                "ORDER BY ",
                "JOIN ",
                "LEFT JOIN ",
                "RIGHT JOIN ",
                "INNER JOIN ",
                "FULL JOIN ",
                "ON ",
                "AND ",
                "OR ",
            )
        ):
            norm = qualifier_re.sub("", norm)
        elif in_matview_query:
            # pg_dump output differs by version on qualification inside matview SELECT bodies.
            norm = qualifier_re.sub("", norm)
            if "WITH NO DATA;" in norm:
                in_matview_query = False
        out.append(norm)
    normalized: list[str] = []
    prev_blank = False
    for line in out:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        normalized.append(line)
        prev_blank = is_blank
    return "\n".join(normalized).strip() + "\n"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _docker_bin() -> str | None:
    for candidate in ("docker", "podman"):
        if shutil.which(candidate):
            return candidate
    return None


def _pg_dump_with_container(container_bin: str, image: str, db_url: str) -> tuple[int, str, str]:
    cmd = [
        container_bin,
        "run",
        "--rm",
        "--network",
        "host",
        image,
        "pg_dump",
        "--schema-only",
        "--no-owner",
        "--no-privileges",
        "--no-comments",
        db_url,
    ]
    res = _run(cmd)
    return res.returncode, res.stdout, res.stderr


def _pg_dump_local(db_url: str) -> tuple[int, str, str]:
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        return 127, "", "pg_dump not found on PATH"
    res = _run(
        [
            pg_dump,
            "--schema-only",
            "--no-owner",
            "--no-privileges",
            "--no-comments",
            db_url,
        ]
    )
    return res.returncode, res.stdout, res.stderr


def _diff(a: str, b: str, a_name: str, b_name: str) -> str:
    return "".join(
        difflib.unified_diff(
            a.splitlines(keepends=True),
            b.splitlines(keepends=True),
            fromfile=a_name,
            tofile=b_name,
        )
    )


def _apply_migrations(repo_root: Path, migration_url: str) -> None:
    env = os.environ.copy()
    env["MIGRATION_DATABASE_URL"] = migration_url
    env["DATABASE_URL"] = migration_url
    res = _run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, cwd=repo_root)
    if res.returncode != 0:
        raise RuntimeError(f"Alembic upgrade failed:\n{res.stdout}\n{res.stderr}")


def _decide_mode(requested: str, ci: bool) -> str:
    if requested != "auto":
        return requested
    return "ci" if ci else "local"


def _print(msg: str) -> None:
    print(f"[schema-authority] {msg}")


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _emit_diff_file(diff_text: str, out_path: Path | None) -> None:
    if not out_path:
        return
    _write(out_path, diff_text)
    _print(f"wrote diff: {out_path}")


def _validate_canonical_presence(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"canonical schema not found: {path}")


def _checked_dump(mode: str, db_url: str, image: str) -> tuple[int, str, str]:
    if mode == "ci":
        container = _docker_bin()
        if not container:
            return 127, "", "docker/podman not found (required in ci mode)"
        return _pg_dump_with_container(container, image, db_url)
    if mode == "local":
        return _pg_dump_local(db_url)
    raise RuntimeError(f"unsupported mode: {mode}")


def _summarize_commands(mode: str, image: str) -> None:
    if mode == "ci":
        _print(f"mode=ci (pinned container image: {image})")
    else:
        _print("mode=local (system pg_dump fallback)")


def _write_artifacts(dir_path: Path, raw_dump: str, normalized_dump: str, normalized_canonical: str) -> None:
    _write(dir_path / "schema_dump.raw.sql", raw_dump)
    _write(dir_path / "schema_dump.normalized.sql", normalized_dump)
    _write(dir_path / "canonical.normalized.sql", normalized_canonical)


def _iter_lines(text: str, limit: int) -> Iterable[str]:
    count = 0
    for line in text.splitlines():
        if count >= limit:
            break
        yield line
        count += 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical", default="db/schema/canonical_schema.sql")
    parser.add_argument("--mode", choices=("auto", "ci", "local"), default="auto")
    parser.add_argument("--dump-image", default=DEFAULT_DUMP_IMAGE)
    parser.add_argument("--artifacts-dir", default="artifacts/schema_authority")
    parser.add_argument("--diff-out", default="")
    parser.add_argument("--no-migrate", action="store_true")
    parser.add_argument("--runtime-agnostic-local-nonblocking", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    canonical_path = (repo_root / args.canonical).resolve()
    artifacts_dir = (repo_root / args.artifacts_dir).resolve()
    diff_out = Path(args.diff_out).resolve() if args.diff_out else None
    ci = os.getenv("CI", "").lower() == "true"
    mode = _decide_mode(args.mode, ci)

    try:
        migration_url = _require_env("MIGRATION_DATABASE_URL")
        _validate_canonical_presence(canonical_path)
        _summarize_commands(mode, args.dump_image)
        if not args.no_migrate:
            _print("applying migrations to head")
            _apply_migrations(repo_root, migration_url)
        _print("dumping schema")
        rc, dump_out, dump_err = _checked_dump(mode, migration_url, args.dump_image)
        if rc != 0:
            if mode == "local" and args.runtime_agnostic_local_nonblocking:
                _print(f"warning: local dump unavailable ({dump_err.strip()}); skipping local adjudication")
                return 0
            raise RuntimeError(f"pg_dump failed ({rc}): {dump_err.strip()}")

        canonical_raw = canonical_path.read_text(encoding="utf-8", errors="replace")
        normalized_dump = _normalize_schema(dump_out)
        normalized_canonical = _normalize_schema(canonical_raw)
        _write_artifacts(artifacts_dir, dump_out, normalized_dump, normalized_canonical)

        if normalized_dump == normalized_canonical:
            _print("PASS: canonical schema matches migrations-derived schema")
            return 0

        diff_text = _diff(
            normalized_canonical,
            normalized_dump,
            str(canonical_path),
            "migrations_derived_schema.normalized.sql",
        )
        _emit_diff_file(diff_text, diff_out)
        _print("FAIL: canonical schema drift detected")
        for line in _iter_lines(diff_text, 120):
            print(line)
        return 1
    except Exception as exc:
        _print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
