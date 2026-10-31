#!/usr/bin/env python3
"""XXV B8: a pre-XXV financial cohort survives the XXV upgrade and is
reported as unqualified rather than served as current money.

The probe provisions a CI-faithful database at the immediate predecessor
generation 202610180003, seeds a real tenant/ingress/verdict cohort through
the predecessor atomic transition, upgrades to 202610280001, and verifies:

* the tenant, ingress, and verdict rows still exist;
* the XXV-only attestation relation exists and contains no attestation for
  the pre-XXV ingress (the provider's signed bytes were never retained);
* the mandatory attestation sweep PASSes, classifying the row as
  ``source_not_root_authenticated`` rather than as a served current claim;
* no unverifiable current claim is produced.

This is a data-carrying predecessor-generation proof. It does not establish
the VII/XX legacy generations or control-plane equivalence.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.secrets import get_database_url  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
PREDECESSOR = "202610180003"
HEAD = "202610280001"
NATURAL_PROOF = REPO_ROOT / "scripts" / "ci" / "prove_b26_p2_xxiv_natural_correction.py"
SWEEP = REPO_ROOT / "scripts" / "ci" / "b26_p2_xxv_attestation_sweep.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _run(command: list[str], *, env: dict[str, str], timeout: int = 1800) -> None:
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout[-3000:]}\n"
            f"stderr:\n{completed.stderr[-3000:]}"
        )


def _alembic_env(migration_dsn: str) -> dict[str, str]:
    env = dict(os.environ)
    env["DATABASE_URL"] = migration_dsn
    env["MIGRATION_DATABASE_URL"] = migration_dsn
    env.setdefault("ENVIRONMENT", "ci")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(BACKEND_ROOT), str(REPO_ROOT), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    return env


def _row(dsn: str, verdict_id: str) -> tuple:
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id::text, tenant_id::text,"
                " b26_p2_source_authority_state::text,"
                " canonical_net_verified_amount_minor,"
                " webhook_ingress_identity_id::text"
                " FROM public.b23_match_verdicts WHERE id=%s",
                (verdict_id,),
            )
            return cur.fetchone()


def _attestation_count(dsn: str, ingress_id: str) -> int:
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM public.b26_p2_source_money_attestation"
                " WHERE webhook_ingress_identity_id=%s",
                (ingress_id,),
            )
            return int(cur.fetchone()[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-dsn", required=True)
    parser.add_argument("--database", default="skeldir_xxv_b8_cohort")
    parser.add_argument("--public-key-path", required=True)
    parser.add_argument("--evidence-out", required=True)
    args = parser.parse_args()

    admin = args.admin_dsn
    db = args.database
    conn = psycopg2.connect(admin)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (db,))
            if cur.fetchone():
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                    " WHERE datname=%s",
                    (db,),
                )
                cur.execute(f'DROP DATABASE "{db}"')
            cur.execute(f'CREATE DATABASE "{db}"')
    finally:
        conn.close()

    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "database" / "prepare_migration_authority_boundary.py"),
            "--admin-dsn",
            admin,
            "--database-name",
            db,
        ],
        env=dict(os.environ),
    )
    migration_dsn = (
        "postgresql://migration_owner:migration_owner@"
        + admin.split("@", 1)[1].rsplit("/", 1)[0]
        + "/"
        + db
    )
    env = _alembic_env(migration_dsn)
    _run([sys.executable, "-m", "alembic", "upgrade", PREDECESSOR], env=env)

    natural = _load(NATURAL_PROOF, "xxv_b8_natural")
    seed_dsn = admin.rsplit("/", 1)[0] + "/" + db
    world = natural._seed_world(seed_dsn)
    before = _row(seed_dsn, world["verdict"])
    if before is None:
        raise RuntimeError("predecessor cohort is absent before upgrade")

    _run([sys.executable, "-m", "alembic", "upgrade", HEAD], env=env)
    after = _row(seed_dsn, world["verdict"])
    attestations = _attestation_count(seed_dsn, before[4])

    os.environ["SKELDIR_PROCESS_DATABASE_URL"] = migration_dsn
    os.environ["MIGRATION_DATABASE_URL"] = migration_dsn
    os.environ.setdefault("ENVIRONMENT", "ci")
    sweep_module = _load(SWEEP, "xxv_b8_sweep")
    sweep_result = sweep_module.sweep(
        seed_dsn, public_key_path=args.public_key_path
    )
    census = sweep_result["census"]
    # Execute the actual reader function used by the signed/unsigned customer
    # surfaces, not just the sweep. The predecessor row has no attestation, so
    # the reader code must return an unqualified status rather than current
    # money. This is reader-code execution; it is not an HTTP request.
    from sqlalchemy import text as sql_text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import (  # noqa: PLC0415
        AsyncSession,
        create_async_engine,
    )

    os.environ["SKELDIR_PROCESS_DATABASE_URL"] = (
        "postgresql+asyncpg://"
        + seed_dsn.split("://", 1)[1]
    )
    os.environ["MIGRATION_DATABASE_URL"] = seed_dsn
    os.environ["B26_P2_SOURCE_ATTESTATION_REQUIRED"] = "true"
    os.environ["B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH"] = str(
        args.public_key_path
    )
    from app.revenue_verification.source_attestation import (  # noqa: PLC0415
        read_verdict_source_attestation_status,
    )

    async def _read_customer_status():
        engine = create_async_engine(get_database_url())
        try:
            async with AsyncSession(engine) as session:
                await session.execute(
                    sql_text(
                        "SELECT set_config('app.current_tenant_id', :tenant, false)"
                    ),
                    {"tenant": after[1]},
                )
                return await read_verdict_source_attestation_status(
                    session,
                    tenant_id=after[1],
                    verdict_id=after[0],
                )
        finally:
            await engine.dispose()

    reader_status = asyncio.run(_read_customer_status())
    reader_unqualified = (
        reader_status.status.startswith("unverifiable:")
        and reader_status.attested is False
    )
    status = (
        before is not None
        and after is not None
        and after[0] == before[0]
        and after[1] == before[1]
        and after[4] == before[4]
        and attestations == 0
        and not sweep_result["unverifiable"]
        and (
            census.get("source_not_root_authenticated", 0) >= 1
            or census.get("unattested_not_claimed_current", 0) >= 1
        )
        and reader_unqualified
    )
    evidence = {
        "property": (
            "B8: a pre-XXV financial cohort survives the XXV upgrade and the"
            " mandatory sweep classifies it as source_not_root_authenticated,"
            " not as attested current money"
        ),
        "actor": "pre-XXV persisted tenant/ingress/verdict cohort",
        "predecessor_revision": PREDECESSOR,
        "upgraded_revision": HEAD,
        "world": world,
        "before": {
            "verdict_id": before[0],
            "tenant_id": before[1],
            "authority_state": before[2],
            "amount_minor": before[3],
            "ingress_id": before[4],
        },
        "after": {
            "verdict_id": after[0],
            "tenant_id": after[1],
            "authority_state": after[2],
            "amount_minor": after[3],
            "ingress_id": after[4],
            "attestation_count_for_ingress": attestations,
        },
        "attestation_sweep": {
            "status": "PASS" if not sweep_result["unverifiable"] else "FAIL",
            "census": census,
            "unverifiable": sweep_result["unverifiable"],
        },
        "row_and_ingress_preserved": after[0] == before[0] and after[4] == before[4],
        "customer_reader": {
            "reader": (
                "app.revenue_verification.source_attestation."
                "read_verdict_source_attestation_status"
            ),
            "status": reader_status.status,
            "reason": reader_status.reason,
            "attested": reader_status.attested,
            "unqualified": reader_unqualified,
            "limit": "reader-code execution, not an HTTP customer request",
        },
        "status": "PASS" if status else "FAIL",
        "limit_of_inference": (
            "This proves the immediate XXV predecessor cohort, including"
            " execution of the actual source-attestation reader code. It is"
            " not an HTTP customer request and does not replace the VII/XX"
            " generation matrix or control-plane equivalence."
        ),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    out = Path(args.evidence_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"status": evidence["status"], "evidence": str(out)}))
    return 0 if status else 1


if __name__ == "__main__":
    raise SystemExit(main())
