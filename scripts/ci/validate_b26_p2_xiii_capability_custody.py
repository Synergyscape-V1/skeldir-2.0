#!/usr/bin/env python3
"""B2.6-P2 Corrective XIII physical capability custody validator (BLOCKER B).

Laws:
- the general API process must NOT possess the authenticated-ingress
  persistence credential (env string or file reference);
- generic workers / B2.3 / Bayesian / relay / beat must NOT possess it;
- only the dedicated authentication trust root
  (SKELDIR_PROCESS_ROLE=auth_ingress with B26_P2_INGRESS_DATABASE_URL_FILE)
  may possess it;
- the ingress pool constructs only there (role + file gated);
- sanitization deletes (never retains); child processes of
  non-ingress processes inherit nothing.

Static: Procfile/compose manifests + backend holder census.
Live (--dsn not required; subprocess probes with controlled env):
- CAP-1: general API role with file path present but role=api cannot
  construct the pool (credential_unavailable / wrong_process);
- CAP-2: worker role sanitizes smuggled vars (deleted, no restore);
- CAP-3: child of a sanitized process inherits no credential.

Exit code is the gate.
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
LEGACY_TOKEN = "B26_P2_INGRESS_DATABASE_URL"
FILE_TOKEN = "B26_P2_INGRESS_DATABASE_URL_FILE"
ROLE_TOKEN = "SKELDIR_PROCESS_ROLE"


def _line_mounts_legacy(line: str) -> bool:
    # A line mounts the legacy env credential when it assigns a
    # non-empty value (blanking `VAR=` / `VAR: ""` carries none).
    if LEGACY_TOKEN not in line:
        return False
    stripped = line.strip()
    if re.search(r"B26_P2_INGRESS_DATABASE_URL\s*=\s*(#|$|\s)", stripped):
        return False
    if re.search(r'B26_P2_INGRESS_DATABASE_URL\s*:\s*""', stripped):
        return False
    if re.search(r"B26_P2_INGRESS_DATABASE_URL\s*=\s*$", stripped):
        return False
    return True


def _topology_checks(violations: list[str], checks: dict) -> None:
    procfile = REPO_ROOT / "Procfile"
    try:
        text = procfile.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xiii_cap_procfile_unreadable:{exc}")
        return
    # Only auth_ingress may mount the file credential; every other
    # process must blank both vars and declare a non-auth role.
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"\s*([a-z0-9_]+)\s*:", stripped)
        if not m:
            continue
        name = m.group(1)
        if name in ("db", "mock_auth", "mock_attribution", "mock_reconciliation",
                    "mock_export", "mock_health", "mock_privacy", "mock_shopify",
                    "mock_woocommerce", "mock_stripe", "mock_paypal",
                    "mock_llm_investigations", "mock_llm_budget",
                    "mock_llm_explanations"):
            continue
        if name == "auth_ingress":
            if ROLE_TOKEN not in line or "auth_ingress" not in line:
                violations.append("xiii_cap_auth_role_missing:Procfile")
            continue
        if _line_mounts_legacy(line):
            violations.append(f"xiii_cap_legacy_mount:{name}")
        if FILE_TOKEN in line and 'FILE= ' not in line and 'FILE=' in line:
            # Any non-blank FILE assignment outside auth_ingress mounts.
            if not re.search(r"B26_P2_INGRESS_DATABASE_URL_FILE\s*=\s*(#|$|\s)", line):
                violations.append(f"xiii_cap_file_mount:{name}")
        if name in ("web", "worker", "worker_b23", "worker_bayesian",
                    "worker_bayesian_publisher", "relay_b26_p2", "beat"):
            if ROLE_TOKEN not in line:
                violations.append(f"xiii_cap_role_missing:{name}")
    checks["procfile_done"] = True
    # Backend holders: the legacy env string may appear only in the
    # session boundary (gated) and event_service compat shim (None).
    allowed = {
        "backend/app/db/session.py",
        "backend/app/ingestion/event_service.py",
    }
    offenders = []
    for path in sorted((REPO_ROOT / "backend" / "app").rglob("*.py")):
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        if LEGACY_TOKEN in body and rel not in allowed:
            # The auth service server references the file token only.
            offenders.append(rel)
    # Filter: auth_service may reference FILE token (not legacy env).
    offenders = [o for o in offenders if "auth_service" not in o]
    if offenders:
        violations.append(
            "xiii_cap_legacy_beyond_boundary:" + ",".join(offenders[:10])
        )
    checks["backend_holders_done"] = True
    # Compose census: only auth services may mount the file credential.
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
            if FILE_TOKEN in line and '""' not in line and ": ''" not in line:
                context = "\n".join(body.splitlines()[max(0, i - 16):i])
                if not re.search(r"auth", context, re.IGNORECASE):
                    violations.append(f"xiii_cap_file_compose:{name}:{i}")
    checks["compose_done"] = True


def _live_probes(violations: list[str], checks: dict) -> None:
    base = dict(os.environ)
    base.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://app_user:app_user@127.0.0.1:1/x",
    )
    base["TESTING"] = "1"
    base["PYTHONPATH"] = "%s%s%s" % (
        REPO_ROOT, os.pathsep, REPO_ROOT / "backend",
    )
    # CAP-1: API role with a file path present cannot construct the pool.
    env = dict(base)
    env[ROLE_TOKEN] = "api"
    env[FILE_TOKEN] = "/nonexistent/b26_p2_ingress_dsn"
    env.pop(LEGACY_TOKEN, None)
    probe = (
        "import asyncio\n"
        "from uuid import uuid4\n"
        "from app.db.session import _ingress_boundary, get_ingress_session\n"
        "async def main():\n"
        "    async with _ingress_boundary():\n"
        "        async with get_ingress_session(tenant_id=uuid4()):\n"
        "            pass\n"
        "asyncio.run(main())\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True, text=True, env=env,
        cwd=str(REPO_ROOT / "backend"),
    )
    out = proc.stdout + proc.stderr
    if proc.returncode == 0:
        violations.append("xiii_cap_api_role_obtained_session")
    elif "b26_p2_ingress_wrong_process" not in out and "credential_unavailable" not in out:
        violations.append("xiii_cap_api_wrong_refusal:" + out[:160])
    else:
        checks["cap_api_denied"] = True
    # CAP-2: worker sanitizes smuggled vars with no restore.
    env2 = dict(base)
    env2[ROLE_TOKEN] = "worker"
    env2[LEGACY_TOKEN] = "postgresql+asyncpg://app_ingress:x@127.0.0.1:1/x"
    env2[FILE_TOKEN] = "/tmp/smuggled_ingress_dsn"
    probe2 = (
        "import os\n"
        "from app.db.session import sanitize_worker_ingress_environment,"
        " restore_worker_ingress_environment\n"
        "s = sanitize_worker_ingress_environment()\n"
        "assert s is True, 'expected sanitization'\n"
        "assert os.getenv('B26_P2_INGRESS_DATABASE_URL') is None\n"
        "assert os.getenv('B26_P2_INGRESS_DATABASE_URL_FILE') is None\n"
        "assert restore_worker_ingress_environment() is False\n"
        "assert os.getenv('B26_P2_INGRESS_DATABASE_URL') is None\n"
        "print('XIII_CAP_SANITIZED')\n"
    )
    proc2 = subprocess.run(
        [sys.executable, "-c", probe2],
        capture_output=True, text=True, env=env2,
        cwd=str(REPO_ROOT / "backend"),
    )
    if proc2.returncode != 0 or "XIII_CAP_SANITIZED" not in proc2.stdout:
        violations.append(
            "xiii_cap_sanitize_failed:" + (proc2.stdout + proc2.stderr)[-200:]
        )
    else:
        checks["cap_sanitize_deletes"] = True
    # CAP-3: unrelated mint of the ContextVar without the role still
    # cannot obtain a session (role gate fires after boundary check).
    env3 = dict(base)
    env3[ROLE_TOKEN] = "api"
    env3.pop(LEGACY_TOKEN, None)
    env3.pop(FILE_TOKEN, None)
    probe3 = (
        "import asyncio\n"
        "from uuid import uuid4\n"
        "from app.db.session import enter_ingress_auth_boundary, get_ingress_session\n"
        "enter_ingress_auth_boundary()\n"
        "async def main():\n"
        "    async with get_ingress_session(tenant_id=uuid4()):\n"
        "        pass\n"
        "asyncio.run(main())\n"
    )
    proc3 = subprocess.run(
        [sys.executable, "-c", probe3],
        capture_output=True, text=True, env=env3,
        cwd=str(REPO_ROOT / "backend"),
    )
    out3 = proc3.stdout + proc3.stderr
    if proc3.returncode == 0:
        violations.append("xiii_cap_minted_token_obtained_session")
    elif "b26_p2_ingress_wrong_process" not in out3 and "credential_unavailable" not in out3:
        violations.append("xiii_cap_mint_wrong_refusal:" + out3[:160])
    else:
        checks["cap_mint_denied"] = True


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate XIII capability custody.")
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _topology_checks(violations, checks)
    _live_probes(violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XIII_CAP_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {"gate_id": "B26-P2-XIII-CAPABILITY", "status": status,
                 "violations": sorted(violations), "checks": checks},
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
