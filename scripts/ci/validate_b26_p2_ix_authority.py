#!/usr/bin/env python3
"""B2.6-P2 Corrective IX effect-level authority validator.

Static mode (default): parse the IX migration plus every alembic version for
CREATE FUNCTION bodies with a conducted *write* effect (SET delivery_state /
SET state to conducted, or INSERT INTO b26_p2_conduction_receipts), collect
routine names, and require only the allowlisted writers. Read-only guards
that merely compare against conducted are not authorities and are ignored.
Test helpers (test/helper/probe/falsifier/seed/example names) are ignored.

Live mode (--dsn): additionally inspect pg_proc for routines executable by a
runtime role whose body carries the same write effect, under the same
allowlist.

Schema check: no GRANT CREATE ON SCHEMA public TO app_* may appear in the IX
migration; absence is recorded as a note.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_DIR = REPO_ROOT / "alembic"
IX_MIGRATION = (
    ALEMBIC_DIR
    / "versions/007_skeldir_foundation"
    / "202609230001_b26_p2_corrective_ix_consequence_authority.py"
)

ALLOWLIST = frozenset(
    {"b26_p2_mark_conducted", "b26_p2_record_conduction_receipt"}
)
RUNTIME_ROLES = ("app_worker", "app_user", "app_relay", "app_beat")

# Conducted *write* effects only. Guards that read conducted state
# (IF/WHERE/AND ... = 'conducted') are not consequence authorities.
WRITE_TOKENS = (
    "SET delivery_state = 'conducted'",
    "SET state = 'conducted'",
    "INSERT INTO public.b26_p2_conduction_receipts",
)

IGNORED_NAME_HINTS = ("test", "helper", "probe", "falsif", "seed", "example")

FUNC_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+public\.(\w+)\s*\(",
    re.IGNORECASE,
)
SCHEMA_CREATE_RE = re.compile(
    r"GRANT\s+CREATE\s+ON\s+SCHEMA\s+public\s+TO\s+(app_\w+)",
    re.IGNORECASE,
)


def _function_chunks(source: str) -> list[tuple[str, str]]:
    """Split source into (routine_name, body_chunk) per CREATE FUNCTION."""
    matches = list(FUNC_RE.finditer(source))
    chunks: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(source)
        chunks.append((match.group(1), source[match.start() : end]))
    return chunks


def _is_ignored(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in IGNORED_NAME_HINTS)


def _static_scan(checks: dict[str, object]) -> tuple[set[str], set[str]]:
    """Return (writers, ignored) routine-name sets across all versions."""
    writers: set[str] = set()
    ignored: set[str] = set()
    files = sorted(ALEMBIC_DIR.rglob("*.py")) if ALEMBIC_DIR.is_dir() else []
    checks["alembic_files_scanned"] = len(files)
    per_file: dict[str, list[str]] = {}
    ix_writers: list[str] = []
    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        names: list[str] = []
        for name, chunk in _function_chunks(source):
            if not any(token in chunk for token in WRITE_TOKENS):
                continue
            if _is_ignored(name):
                ignored.add(name)
                continue
            writers.add(name)
            names.append(name)
        if names:
            per_file[path.relative_to(REPO_ROOT).as_posix()] = sorted(names)
        if path == IX_MIGRATION:
            ix_writers = sorted(names)
    checks["static_writers"] = sorted(writers)
    checks["static_ignored_helpers"] = sorted(ignored)
    checks["static_writers_by_file"] = per_file
    checks["ix_migration_writers"] = ix_writers
    return writers, ignored


def _check_static(violations: list[str], checks: dict[str, object]) -> None:
    if not IX_MIGRATION.is_file():
        violations.append("ix_authority_migration_missing:202609230001")
        checks["ix_migration_exists"] = False
        return
    checks["ix_migration_exists"] = True
    writers, _ = _static_scan(checks)
    checks["allowlist"] = sorted(ALLOWLIST)
    extra = sorted(writers - ALLOWLIST)
    checks["alternate_writers"] = extra
    for name in extra:
        violations.append(f"ix_authority_alternate_conducted_authority:{name}")


def _check_schema_create(
    violations: list[str], checks: dict[str, object]
) -> None:
    if not IX_MIGRATION.is_file():
        return
    source = IX_MIGRATION.read_text(encoding="utf-8")
    grants = sorted(set(SCHEMA_CREATE_RE.findall(source)))
    checks["ix_schema_create_grants_to_app_roles"] = grants
    if grants:
        for role in grants:
            violations.append(f"ix_authority_schema_create_granted:{role}")
    else:
        checks["schema_note"] = (
            "no GRANT CREATE ON SCHEMA public TO app_* in IX migration"
        )


def _check_live(
    dsn: str | None, violations: list[str], checks: dict[str, object]
) -> None:
    if not dsn:
        checks["live_check"] = "skipped_no_dsn_static_only"
        return
    try:
        import psycopg2  # type: ignore[import-untyped]  # noqa: PLC0415
    except ImportError:
        violations.append("ix_authority_live_check_driver_missing:psycopg2")
        checks["live_check"] = "driver_missing"
        return
    try:
        conn = psycopg2.connect(dsn)
    except Exception as exc:  # noqa: BLE001
        violations.append(f"ix_authority_live_check_connect_failed:{exc}")
        checks["live_check"] = "connect_failed"
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT p.proname AS name,
                           pg_get_function_identity_arguments(p.oid) AS args,
                           COALESCE(p.prosrc, '') AS src
                      FROM pg_proc AS p
                      JOIN pg_namespace AS n ON n.oid = p.pronamespace
                     WHERE n.nspname = 'public'
                    """
                )
                rows = cur.fetchall()
                live_writers: list[str] = []
                for name, _args, src in rows:
                    if not any(token in src for token in WRITE_TOKENS):
                        continue
                    if _is_ignored(str(name)):
                        continue
                    executable_by: list[str] = []
                    for role in RUNTIME_ROLES:
                        cur.execute(
                            "SELECT has_function_privilege(%s, %s, 'EXECUTE')",
                            (
                                role,
                                f"public.{name}",
                            ),
                        )
                        row = cur.fetchone()
                        if row and bool(row[0]):
                            executable_by.append(role)
                    if executable_by:
                        live_writers.append(str(name))
                        checks[f"live_executable_by:{name}"] = executable_by
                checks["live_routines_scanned"] = len(rows)
                checks["live_writers"] = sorted(set(live_writers))
                for name in sorted(set(live_writers) - ALLOWLIST):
                    violations.append(
                        f"ix_authority_live_alternate_conducted_authority:{name}"
                    )
                if not violations:
                    checks["live_check"] = "pass_allowlist_only"
    except Exception as exc:  # noqa: BLE001
        violations.append(f"ix_authority_live_check_failed:{exc}")
        checks["live_check"] = "query_failed"
    finally:
        conn.close()


def _negative_controls(checks: dict[str, object]) -> list[str]:
    results: dict[str, bool] = {}
    # Control 1: a foreign conducted-writer must be flagged.
    evil = (
        "CREATE OR REPLACE FUNCTION public.b26_p2_evil_conduct() "
        "RETURNS void AS $$ BEGIN "
        "UPDATE public.b23_match_task_dispatches AS d "
        "SET delivery_state = 'conducted'; END $$ LANGUAGE plpgsql;"
    )
    evil_writers = {
        name
        for name, chunk in _function_chunks(evil)
        if any(token in chunk for token in WRITE_TOKENS)
    }
    results["writer_sensor_flags_foreign_routine"] = (
        evil_writers - ALLOWLIST == {"b26_p2_evil_conduct"}
    )
    # Control 2: a read-only conducted guard must NOT be flagged.
    guard = (
        "CREATE OR REPLACE FUNCTION public.b26_p2_guard_probe() "
        "RETURNS trigger AS $$ BEGIN "
        "IF NEW.delivery_state = 'conducted' THEN "
        "RAISE EXCEPTION 'nope'; END IF; RETURN NEW; END $$ "
        "LANGUAGE plpgsql;"
    )
    guard_writers = {
        name
        for name, chunk in _function_chunks(guard)
        if any(token in chunk for token in WRITE_TOKENS)
    }
    results["writer_sensor_ignores_read_guard"] = not guard_writers
    # Control 3: allowlisted writers must clear the allowlist.
    known = (
        "CREATE OR REPLACE FUNCTION public.b26_p2_mark_conducted() "
        "RETURNS text AS $$ BEGIN "
        "UPDATE public.b23_match_task_dispatches AS d "
        "SET delivery_state = 'conducted'; END $$ LANGUAGE plpgsql;"
    )
    known_writers = {
        name
        for name, chunk in _function_chunks(known)
        if any(token in chunk for token in WRITE_TOKENS)
    }
    results["allowlist_clears_known_writer"] = (
        known_writers - ALLOWLIST == set()
    )
    checks["negative_controls"] = results
    return [
        f"ix_authority_negative_control_blind:{n}"
        for n, ok in results.items()
        if not ok
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 Corrective IX effect-level authority."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict[str, object] = {}
    try:
        _check_static(violations, checks)
        _check_schema_create(violations, checks)
        _check_live(args.dsn, violations, checks)
        violations.extend(_negative_controls(checks))
    except Exception as exc:  # noqa: BLE001
        violations.append(f"ix_authority_validator_crash:{exc}")
    status = "PASS" if not violations else "FAIL"
    evidence = {
        # Declared gate identity for the proof-plane capsule census (same
        # convention as the authority-universe cell): additive, ignored by
        # required-cell adjudication.
        "gate_id": "B26-P2-IX-AUTHORITY",
        "validator": "validate_b26_p2_ix_authority",
        "status": status,
        "violations": sorted(violations),
        "checks": checks,
        "mode": "live" if args.dsn else "static",
    }
    if args.evidence_out is not None:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if args.evidence_dir is not None:
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        (args.evidence_dir / "ix-authority.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_IX_AUTHORITY_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_IX_AUTHORITY_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
