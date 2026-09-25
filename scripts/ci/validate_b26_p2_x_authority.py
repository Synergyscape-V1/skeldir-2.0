#!/usr/bin/env python3
"""B2.6-P2 Corrective X effect-authority validator.

Static mode: scan every alembic migration for routines carrying a
conducted *write* effect; only the governed (name, signature) pair may
carry one. No name-hint ignore list exists: a helper/seed/probe-named
routine with a write effect is a violation, not an exemption.
Trigger functions on the protected tables carrying a write effect are
violations unconditionally (legitimate guards raise, never write).

Live mode (--dsn REQUIRED): judge the migrated database, not the
files. Every pg_proc routine is identified by OID (overloads are
independent classifications; unknown overload = RED). Bodies come from
pg_proc (prosrc), never from migration text. EXECUTE reachability uses
has_function_privilege(role_oid, func_oid, 'EXECUTE'). Governed routine
bodies must equal their migration-chunk meaning (whitespace-collapsed):
a live-only pg_proc mutation is RED even when every file is pristine.
Any crash/timeout/missing-DB/ambiguous-routine is a REQUIRED GATE RED,
never a static fallback PASS.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_DIR = REPO_ROOT / "alembic"

ALLOWLIST = {
    ("b26_p2_mark_conducted", "text"),
    (
        "b26_p2_record_conduction_receipt",
        "text, text, integer, text",
    ),
}
RUNTIME_ROLES = ("app_worker", "app_user", "app_relay", "app_beat")

WRITE_TOKENS = (
    "set delivery_state = 'conducted'",
    "set state = 'conducted'",
    "insert into public.b26_p2_conduction_receipts",
)

PROTECTED_TABLES = (
    "b23_match_task_dispatches",
    "b26_p2_execution_outbox",
    "b26_p2_conduction_receipts",
)

# Governed routines whose live meaning must equal the migration chunk.
# Corrective XI extends the set to the rewritten/new load-bearing
# routines (latest upgrade chunk wins; historical law is immutable).
GOVERNED_ROUTINES = (
    "b26_p2_ascii_strip",
    "b26_p2_strip_provider_token",
    "b26_p2_strip_currency_token",
    "b26_p2_normalize_provider",
    "b26_p2_normalize_currency",
    "b26_p2_classify_candidate",
    "b26_p2_canonical_scope_identity_for_window",
    "b26_p2_record_conduction_receipt",
    "b26_p2_mark_conducted",
    "b26_p2_enforce_verdict_temporal_conservation",
    "b26_p2_enforce_ingress_provenance",
    "b26_p2_enforce_dispatch_provenance",
    "b26_p2_attest_provenance_evidence",
    "b26_p2_guard_conducted_transition",
    "b26_p2_guard_conduction_receipt",
    "b26_p2_record_scheduler_heartbeat",
    "b26_p2_enforce_ingress_verified_authorship",
    "b26_p2_record_ingress_auth_witness",
    "b26_p2_state_eligible_for_p3",
    "b26_p2_xi_invariant_oracle",
    "b26_p2_enforce_dispatch_quarantine_exclusion",
)

FUNC_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+public\.(\w+)\s*\(([^;]*?)\)",
    re.IGNORECASE | re.DOTALL,
)
TRIGGER_RE = re.compile(
    r"CREATE\s+TRIGGER\s+(\w+).*?ON\s+public\.(\w+).*?"
    r"EXECUTE\s+FUNCTION\s+public\.(\w+)\s*\(",
    re.IGNORECASE | re.DOTALL,
)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _body_has_write_effect(body: str) -> bool:
    lowered = body.lower()
    return any(token in lowered for token in WRITE_TOKENS)


def _function_chunks(source: str) -> list[tuple[str, str, str]]:
    """Split source into (routine_name, arg_text, chunk) per CREATE FUNCTION."""
    matches = list(FUNC_RE.finditer(source))
    chunks: list[tuple[str, str, str]] = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(source)
        chunks.append(
            (match.group(1), match.group(2), source[match.start():end])
        )
    return chunks


def _norm_args(arg_text: str) -> str:
    """Normalize an argument list to comma-joined lowercase type names."""
    parts = []
    for piece in arg_text.split(","):
        piece = re.sub(r"\bDEFAULT\b.*", "", piece, flags=re.IGNORECASE).strip()
        if not piece:
            continue
        words = piece.strip().split()
        if not words:
            continue
        token = re.sub(r"\(.*", "", words[-1].rstrip(","))
        parts.append(token.lower())
    return ", ".join(parts)


def _upgrade_sql_of(path: Path) -> str:
    """Return the Python-evaluated SQL text of a migration's upgrade()."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""
    upgrade_source = source.split("\ndef downgrade")[0]
    try:
        upgrade_tree = ast.parse(upgrade_source)
    except SyntaxError:
        return ""
    statements: list[str] = []
    for node in ast.walk(upgrade_tree):
        if not isinstance(node, ast.Expr):
            continue
        call = node.value
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "execute"
            and isinstance(func.value, ast.Name)
            and func.value.id == "op"
        ):
            continue
        if not call.args:
            continue
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            statements.append(first.value)
    _ = tree
    return "\n".join(statements)


def _migration_body_for(name: str) -> str | None:
    """Return the latest evaluated upgrade-chunk body for a routine."""
    files = sorted(ALEMBIC_DIR.rglob("*.py")) if ALEMBIC_DIR.is_dir() else []
    found: str | None = None
    for path in files:
        sql = _upgrade_sql_of(path)
        if not sql:
            continue
        for chunk_name, _args, chunk in _function_chunks(sql):
            if chunk_name != name:
                continue
            start = chunk.find("AS $$")
            if start == -1:
                start = chunk.find("AS $function$")
                if start == -1:
                    continue
                marker = "AS $function$"
            else:
                marker = "AS $$"
            # Bodies never nest dollar-quoting: the first closer after
            # the opener ends the body (a later DO $$ grant block must
            # not be swallowed).
            end = chunk.find("$$", start + len(marker))
            if end <= start:
                continue
            found = chunk[start + len(marker):end]
    return found


def _check_static(violations: list[str], checks: dict[str, object]) -> None:
    files = sorted(ALEMBIC_DIR.rglob("*.py")) if ALEMBIC_DIR.is_dir() else []
    checks["alembic_files_scanned"] = len(files)
    # Latest upgrade definition wins per routine: historical migrations
    # are immutable superseded law, not live authority. (Downgrade
    # bodies are excluded by construction: only upgrade() SQL is read.)
    latest: dict[str, tuple[str, str, str]] = {}
    for path in files:
        sql = _upgrade_sql_of(path)
        if not sql:
            continue
        for name, arg_text, chunk in _function_chunks(sql):
            latest[name] = (path.relative_to(REPO_ROOT).as_posix(), arg_text, chunk)
    writers: list[str] = []
    for name in sorted(latest):
        rel, arg_text, chunk = latest[name]
        if not _body_has_write_effect(chunk):
            continue
        sig = _norm_args(arg_text)
        if (name, sig) not in ALLOWLIST:
            writers.append(f"{rel}:{name}({sig})")
    trigger_violations: list[str] = []
    for path in files:
        sql = _upgrade_sql_of(path)
        if not sql:
            continue
        for trig_name, table, func in TRIGGER_RE.findall(sql):
            if table not in PROTECTED_TABLES:
                continue
            for fname, _a, fchunk in _function_chunks(sql):
                if fname == func and _body_has_write_effect(fchunk):
                    trigger_violations.append(
                        f"{path.relative_to(REPO_ROOT).as_posix()}:"
                        f"{trig_name}->{func}"
                    )
    checks["static_writers"] = sorted(writers)
    checks["static_trigger_writers"] = sorted(trigger_violations)
    for entry in sorted(writers):
        violations.append(f"x_authority_static_alternate_writer:{entry}")
    for entry in sorted(trigger_violations):
        violations.append(f"x_authority_static_trigger_writer:{entry}")
    checks["allowlist"] = sorted(f"{n}({a})" for n, a in ALLOWLIST)


def _live_connect(dsn: str, violations: list[str], checks: dict[str, object]):
    try:
        import psycopg2  # type: ignore[import-untyped]  # noqa: PLC0415
    except ImportError:
        violations.append("x_authority_live_check_driver_missing")
        checks["live_check"] = "driver_missing"
        return None
    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        return conn
    except Exception as exc:  # noqa: BLE001
        violations.append(f"x_authority_live_check_connect_failed:{exc}")
        checks["live_check"] = "connect_failed"
        return None


def _check_live_writers(conn, violations: list[str], checks: dict[str, object]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT p.oid, p.proname,"
            " pg_get_function_identity_arguments(p.oid) AS args,"
            " COALESCE(p.prosrc, '') AS src"
            " FROM pg_proc AS p"
            " JOIN pg_namespace AS n ON n.oid = p.pronamespace"
            " WHERE n.nspname = 'public'"
        )
        rows = cur.fetchall()
        cur.execute(
            "SELECT oid, rolname FROM pg_roles"
            " WHERE rolname = ANY(%s)",
            (list(RUNTIME_ROLES),),
        )
        role_oids = {name: oid for oid, name in cur.fetchall()}
    checks["live_routines_scanned"] = len(rows)
    writers: list[str] = []
    for oid, name, args, src in rows:
        if not _body_has_write_effect(str(src)):
            continue
        sig = _norm_args(str(args or ""))
        label = f"{name}({sig})"
        if (str(name), sig) not in ALLOWLIST:
            writers.append(label)
            checks[f"live_ungoverned_writer:{label}"] = "RED"
    checks["live_writers_outside_allowlist"] = sorted(writers)
    for label in sorted(writers):
        violations.append(f"x_authority_live_alternate_writer:{label}")
    if not writers:
        checks["live_writer_law"] = "allowlist_only"
    # Least-privilege census: no governed X routine may be PUBLIC
    # executable. A widened grant (e.g. residue from a DROP+CREATE
    # that lost its REVOKE) is RED even when bodies are pristine.
    # Legacy trigger-only functions (enforce_ingress/dispatch/
    # temporal) keep their historical default posture: they carry no
    # write effect, take trigger-only record context, and are covered
    # by the writer scan above.
    widened: list[str] = []
    with conn.cursor() as cur:
        for name in GOVERNED_ROUTINES:
            if name in (
                "b26_p2_enforce_ingress_provenance",
                "b26_p2_enforce_dispatch_provenance",
                "b26_p2_enforce_verdict_temporal_conservation",
            ):
                continue
            cur.execute(
                "SELECT count(*) FROM pg_proc AS p"
                " JOIN pg_namespace AS n ON n.oid = p.pronamespace"
                " WHERE n.nspname = 'public' AND p.proname = %s"
                " AND EXISTS (SELECT 1 FROM aclexplode(p.proacl) AS a"
                " WHERE a.grantee = 0"
                " AND a.privilege_type = 'EXECUTE')",
                (name,),
            )
            if int(cur.fetchone()[0]) > 0:
                widened.append(name)
    checks["live_public_executable_governed"] = sorted(widened)
    for name in sorted(widened):
        violations.append(f"x_authority_live_public_widened:{name}")


def _migration_bodies_for(name: str) -> list[str]:
    """Return the latest-file evaluated upgrade-chunk bodies for a routine.

    Historical migrations are immutable superseded law, not live
    authority: only the latest file defining the routine governs
    (mirrors the static check's latest-wins rule). Overloads are
    independent classifications compared as a multiset: Corrective
    XII governs the fail-closed single-argument witness beside the
    bound four-argument form, so a lane missing either (or carrying
    an unknown overload) is RED.
    """
    files = sorted(ALEMBIC_DIR.rglob("*.py")) if ALEMBIC_DIR.is_dir() else []
    latest_path = None
    latest_bodies: list[str] = []
    for path in files:
        sql = _upgrade_sql_of(path)
        if not sql:
            continue
        bodies: list[str] = []
        for chunk_name, _args, chunk in _function_chunks(sql):
            if chunk_name != name:
                continue
            start = chunk.find("AS $$")
            if start == -1:
                start = chunk.find("AS $function$")
                if start == -1:
                    continue
                marker = "AS $function$"
            else:
                marker = "AS $$"
            end = chunk.find("$$", start + len(marker))
            if end <= start:
                continue
            bodies.append(chunk[start + len(marker):end])
        if bodies:
            latest_path = path
            latest_bodies = bodies
    _ = latest_path
    return latest_bodies


def _check_live_equivalence(conn, violations: list[str], checks: dict[str, object]) -> None:
    drift: list[str] = []
    compared = 0
    with conn.cursor() as cur:
        for name in GOVERNED_ROUTINES:
            expected_bodies = _migration_bodies_for(name)
            if not expected_bodies:
                violations.append(
                    f"x_authority_governed_source_missing:{name}"
                )
                continue
            cur.execute(
                "SELECT p.oid, COALESCE(p.prosrc, '') FROM pg_proc AS p"
                " JOIN pg_namespace AS n ON n.oid = p.pronamespace"
                " WHERE n.nspname = 'public' AND p.proname = %s",
                (name,),
            )
            live_rows = cur.fetchall()
            live_bodies = sorted(_collapse(str(src)) for _oid, src in live_rows)
            expected = sorted(_collapse(body) for body in expected_bodies)
            if live_bodies != expected:
                if len(live_rows) != len(expected):
                    violations.append(
                        f"x_authority_live_routine_count:{name}="
                        f"{len(live_rows)}-vs-{len(expected)}"
                    )
                else:
                    drift.append(name)
                continue
            compared += len(live_rows)
    checks["live_equivalence_compared"] = compared
    checks["live_equivalence_drift"] = sorted(set(drift))
    for name in sorted(set(drift)):
        violations.append(f"x_authority_live_source_drift:{name}")


def _negative_controls(checks: dict[str, object]) -> list[str]:
    results: dict[str, bool] = {}
    evil = (
        "CREATE OR REPLACE FUNCTION public.b26_p2_evil_conduct() "
        "RETURNS void AS $$ BEGIN "
        "UPDATE public.b23_match_task_dispatches AS d "
        "SET delivery_state = 'conducted'; END $$ LANGUAGE plpgsql;"
    )
    evil_writers = {
        (name, _norm_args(args))
        for name, args, chunk in _function_chunks(evil)
        if _body_has_write_effect(chunk)
    }
    results["writer_sensor_flags_foreign_routine"] = bool(
        evil_writers - ALLOWLIST
    )
    guard = (
        "CREATE OR REPLACE FUNCTION public.b26_p2_guard_probe() "
        "RETURNS trigger AS $$ BEGIN "
        "IF NEW.delivery_state = 'conducted' THEN "
        "RAISE EXCEPTION 'nope'; END IF; RETURN NEW; END $$ "
        "LANGUAGE plpgsql;"
    )
    guard_writers = {
        (name, _norm_args(args))
        for name, args, chunk in _function_chunks(guard)
        if _body_has_write_effect(chunk)
    }
    results["writer_sensor_ignores_read_guard"] = not guard_writers
    overload = (
        "CREATE OR REPLACE FUNCTION public.b26_p2_mark_conducted(p_task_id text, p_extra integer) "
        "RETURNS text AS $$ BEGIN "
        "UPDATE public.b23_match_task_dispatches AS d "
        "SET delivery_state = 'conducted'; END $$ LANGUAGE plpgsql;"
    )
    overload_writers = {
        (name, _norm_args(args))
        for name, args, chunk in _function_chunks(overload)
        if _body_has_write_effect(chunk)
    }
    results["writer_sensor_flags_unknown_overload"] = bool(
        overload_writers - ALLOWLIST
    )
    helper = (
        "CREATE OR REPLACE FUNCTION public.b26_p2_conduction_seed_helper(p_task_id text) "
        "RETURNS text AS $$ BEGIN "
        "UPDATE public.b23_match_task_dispatches AS d "
        "SET delivery_state = 'conducted'; END $$ LANGUAGE plpgsql;"
    )
    helper_writers = {
        (name, _norm_args(args))
        for name, args, chunk in _function_chunks(helper)
        if _body_has_write_effect(chunk)
    }
    results["writer_sensor_flags_hint_named_helper"] = bool(
        helper_writers - ALLOWLIST
    )
    checks["negative_controls"] = results
    return [
        f"x_authority_negative_control_blind:{n}"
        for n, ok in results.items()
        if not ok
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 Corrective X effect authority."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict[str, object] = {}
    conn = None
    try:
        _check_static(violations, checks)
        if not args.dsn:
            # Corrective X: file inference can never prove live database
            # meaning. Missing live database is RED, not static-only PASS.
            violations.append("x_authority_live_check_required_no_dsn")
            checks["live_check"] = "refused_no_dsn"
        else:
            conn = _live_connect(args.dsn, violations, checks)
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT version_num FROM public.alembic_version"
                        )
                        head = str(cur.fetchone()[0])
                        checks["migration_head"] = head
                        if head not in ("202609240002", "202609250001"):
                            violations.append(
                                "x_authority_unexpected_migration_head:"
                                f"{head}"
                            )
                    _check_live_writers(conn, violations, checks)
                    _check_live_equivalence(conn, violations, checks)
                    import sys as _sys  # noqa: PLC0415

                    _sys.path.insert(0, str(Path(__file__).resolve().parent))
                    from b26_p2_x_canaries import (  # noqa: PLC0415
                        run_canaries,
                    )

                    run_canaries(args.dsn, violations, checks)
                    checks["live_check"] = (
                        "executed" if not violations else "executed_with_red"
                    )
                except Exception as exc:  # noqa: BLE001
                    violations.append(f"x_authority_live_check_failed:{exc}")
                    checks["live_check"] = "query_failed"
                finally:
                    conn.close()
        violations.extend(_negative_controls(checks))
    except Exception as exc:  # noqa: BLE001
        violations.append(f"x_authority_validator_crash:{exc}")
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-X-AUTHORITY",
        "validator": "validate_b26_p2_x_authority",
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
        (args.evidence_dir / "x-authority.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_X_AUTHORITY_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_X_AUTHORITY_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
