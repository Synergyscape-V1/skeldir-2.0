#!/usr/bin/env python3
"""B2.6-P2 Corrective XII physical ingress capability isolation (BLOCKER B).

Law: only the execution boundary that actually performs provider
authentication may possess the capability that persists
authentication-authoritative state. Ordinary API routes, the generic
worker, relay, beat, and the B2.3 worker hold no ingress capability at
the process level -- not merely by convention.

Static: the ingress DSN token appears only on API-boundary lines; every
non-ingress Procfile process blanks it; every non-API compose service
blanks it; only the ingestion boundary + pool factory reference it in
shipped backend code; the worker startup guard exists.

Live (--dsn REQUIRED): the worker guard refuses a smuggled credential;
get_ingress_session without the authentication boundary raises;
non-ingress runtime principals hold no witness/consequence authority.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INGRESS_DSN_TOKEN = "B26_P2_INGRESS_DATABASE_URL"


def _line_mounts_ingress(line: str) -> bool:
    """Shared blanking-aware mount detection (see the XI validator)."""
    import sys as _sys

    _sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))
    try:
        from validate_b26_p2_xi_ingress_isolation import (  # noqa: PLC0415
            _line_mounts_ingress as _shared,
        )

        return bool(_shared(line))
    finally:
        try:
            _sys.path.remove(str(REPO_ROOT / "scripts" / "ci"))
        except ValueError:
            pass


def _topology_checks(violations: list[str], checks: dict) -> None:
    procfile = REPO_ROOT / "Procfile"
    try:
        text = procfile.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xii_proc_procfile_unreadable:{exc}")
        return
    for name in (
        "worker", "relay_b26_p2", "beat", "worker_b23",
        "worker_bayesian", "worker_bayesian_publisher",
    ):
        lines = [
            line for line in text.splitlines()
            if re.match(r"\s*%s\s*:" % re.escape(name), line)
        ]
        if not lines:
            continue
        mounted = any(_line_mounts_ingress(line) for line in lines)
        blanked = any(
            INGRESS_DSN_TOKEN in line and not _line_mounts_ingress(line)
            for line in lines
        )
        checks["procfile_%s_blanked" % name] = blanked and not mounted
        if mounted:
            violations.append("xii_proc_worker_holds_ingress_dsn:%s" % name)
        if not checks["procfile_%s_blanked" % name]:
            violations.append("xii_proc_worker_not_blanked:%s" % name)
    # Backend holders: only the ingestion boundary + pool factory.
    allowed_holders = {
        "backend/app/ingestion/event_service.py",
        "backend/app/db/session.py",
    }
    offenders = []
    for path in sorted((REPO_ROOT / "backend" / "app").rglob("*.py")):
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        if INGRESS_DSN_TOKEN in body and rel not in allowed_holders:
            offenders.append(rel)
    checks["ingress_dsn_backend_holders"] = offenders
    if offenders:
        violations.append(
            "xii_proc_ingress_dsn_beyond_boundary:" + ",".join(offenders[:10])
        )
    # The worker startup guard must exist in shipped code: smuggled
    # credentials are sanitized (variable removed, pool nulled) with a
    # CRITICAL log, so the capability is unavailable in the process.
    guard = (REPO_ROOT / "backend" / "app" / "celery_app.py").read_text(
        encoding="utf-8"
    )
    if "sanitize_worker_ingress_environment" not in guard:
        violations.append("xii_proc_worker_guard_absent")
    session_src = (REPO_ROOT / "backend" / "app" / "db" / "session.py").read_text(
        encoding="utf-8"
    )
    for token in (
        "IngressBoundaryError",
        "b26_p2_ingress_out_of_boundary",
        "assert_worker_ingress_isolation",
    ):
        if token not in session_src:
            violations.append("xii_proc_session_boundary_absent:%s" % token)
    # Compose census: no non-API service may mount the ingress DSN
    # (blanking assignments carry no credential and are skipped).
    for name in (
        "docker-compose.local.yml",
        "docker-compose.e2e.yml",
        "docker-compose.c19.yml",
    ):
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8")
        for i, line in enumerate(body.splitlines(), 1):
            if _line_mounts_ingress(line):
                context = "\n".join(body.splitlines()[max(0, i - 14):i])
                if not re.search(
                    r"(api)\s*:", context
                ):
                    violations.append(
                        "xii_proc_ingress_dsn_compose:%s:%d" % (name, i)
                    )
    checks["topology_done"] = True


def _live_checks(admin_dsn: str, violations: list[str], checks: dict) -> None:
    env = dict(os.environ)
    env["B26_P2_INGRESS_DATABASE_URL"] = (
        "postgresql+asyncpg://app_ingress:app_ingress@127.0.0.1:1/x"
    )
    # Importing the session module requires settings; the dummy DSNs
    # are never dialed (NullPool under TESTING; the probes fail before
    # any connection attempt).
    env.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://app_user:app_user@127.0.0.1:1/x",
    )
    env["TESTING"] = "1"
    env["PYTHONPATH"] = "%s%s%s" % (
        REPO_ROOT, os.pathsep, REPO_ROOT / "backend",
    )
    # Worker startup sanitizes a smuggled credential: afterwards the
    # variable is physically absent, the pool globals are nulled, and
    # the ingress session remains unavailable (boundary gate).
    sanitize_probe = (
        "from app.db.session import sanitize_worker_ingress_environment\n"
        "import app.db.session as session_module\n"
        "import os\n"
        "sanitized = sanitize_worker_ingress_environment()\n"
        "assert sanitized is True, 'expected sanitization'\n"
        "assert os.getenv('B26_P2_INGRESS_DATABASE_URL') is None\n"
        "assert session_module.ingress_engine is None\n"
        "assert session_module.IngressAsyncSessionLocal is None\n"
        "print('XII_PROC_SANITIZED')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", sanitize_probe],
        capture_output=True, text=True, env=env,
        cwd=str(REPO_ROOT / "backend"),
    )
    if proc.returncode != 0 or "XII_PROC_SANITIZED" not in proc.stdout:
        violations.append(
            "xii_proc_worker_sanitize_failed:"
            + (proc.stdout + proc.stderr)[-160:]
        )
    else:
        checks["worker_guard_sanitizes"] = True
    # Unrelated code without the authentication boundary cannot obtain
    # the ingress session (process-level unavailability).
    boundary_probe = (
        "import asyncio\n"
        "from uuid import uuid4\n"
        "from app.db.session import get_ingress_session\n"
        "async def main():\n"
        "    async with get_ingress_session(tenant_id=uuid4()):\n"
        "        pass\n"
        "asyncio.run(main())\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", boundary_probe],
        capture_output=True, text=True, env=env,
        cwd=str(REPO_ROOT / "backend"),
    )
    if proc.returncode == 0:
        violations.append("xii_proc_unrelated_route_obtained_session")
    elif "b26_p2_ingress_out_of_boundary" not in (proc.stdout + proc.stderr):
        violations.append(
            "xii_proc_boundary_wrong_refusal:" + (proc.stdout + proc.stderr)[:160]
        )
    else:
        checks["boundary_required"] = True
    _grant_probes(admin_dsn, violations, checks)


def _grant_probes(admin_dsn: str, violations: list[str], checks: dict) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xii_proc_live_no_driver:{exc}")
        return
    try:
        conn = psycopg2.connect(admin_dsn)
        conn.autocommit = True
    except Exception as exc:
        violations.append(f"xii_proc_live_connect_failed:{exc}")
        return
    try:
        cur = conn.cursor()
        # Non-ingress runtimes hold no consequence/witness authority.
        cur.execute(
            """
            SELECT r.rolname, p.proname,
                   has_function_privilege(r.oid, p.oid, 'EXECUTE') AS can
            FROM pg_roles r, pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public'
              AND p.proname IN (
                  'b26_p2_record_provider_auth_consequence',
                  'b26_p2_record_ingress_auth_witness'
              )
              AND r.rolname IN (
                  'app_worker', 'app_relay', 'app_beat'
              )
            """
        )
        for func, role, can in cur.fetchall():
            if can:
                violations.append(
                    "xii_proc_runtime_holds_auth_capability:%s:%s"
                    % (role, func)
                )
        cur.execute(
            """
            SELECT r.rolname
            FROM pg_roles r
            WHERE r.rolname IN ('app_worker', 'app_relay', 'app_beat')
              AND has_table_privilege(
                  r.rolname,
                  'public.b26_p2_provider_auth_consequence',
                  'INSERT'
              )
            """
        )
        writers = [r[0] for r in cur.fetchall()]
        if writers:
            violations.append(
                "xii_proc_runtime_authors_consequence:" + ",".join(writers)
            )
        checks["grant_ceiling_done"] = True
    except Exception as exc:
        violations.append(f"xii_proc_live_catalog_failed:{exc}")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 XII process capability isolation law."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _topology_checks(violations, checks)
    if args.dsn is None:
        violations.append("xii_proc_live_check_required_no_dsn")
    else:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-XII-PROCESS-ISOLATION",
        "validator": "validate_b26_p2_xii_process_isolation",
        "status": status,
        "violations": sorted(violations),
        "checks": checks,
    }
    if args.evidence_out is not None:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if args.evidence_dir is not None:
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        (args.evidence_dir / "xii-process-isolation.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_XII_PROC_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_XII_PROC_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
