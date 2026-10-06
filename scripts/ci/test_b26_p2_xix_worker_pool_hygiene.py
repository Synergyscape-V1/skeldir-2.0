#!/usr/bin/env python3
"""B2.6-P2 Corrective XIX worker boot-gate pool-hygiene probe (NC-15).

Falsifier: the worker_ready construction-authority gate runs inside a
transient asyncio.run() loop. If it touches the shared module-level
engine, the pool binds connections to that short-lived loop; every
later task using the shared engine then fails with cross-loop errors
(asyncpg "attached to a different loop"), the failures store as
FAILURE results, and the pre-existing VI result-integrity trigger
denies the result-backend write -- killing C19 workers with exit 1.

The gate must therefore use a dedicated, disposed engine. This probe
fails closed if the shared engine is unusable on the worker loop
after the gate runs.

Usage: --dsn SYNC_DSN (migration_owner lane DSN; the probe derives the
app_worker async DSN) --evidence-out PATH.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description="XIX NC-15 pool hygiene.")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    checks: dict = {}
    violations: list[str] = []

    worker_dsn = args.dsn.replace(
        "migration_owner:migration_owner", "app_worker:app_worker"
    )
    if worker_dsn.startswith("postgresql://"):
        worker_dsn = "postgresql+asyncpg://" + worker_dsn[len("postgresql://"):]
    os.environ["DATABASE_URL"] = worker_dsn
    os.environ["SKELDIR_PROCESS_ROLE"] = "worker"
    os.environ["SKELDIR_CELERY_WORKER_ROLE"] = "non_bayesian"

    try:
        from sqlalchemy import text  # noqa: PLC0415

        from app.celery_app import (  # noqa: PLC0415
            _assert_b26_p2_construction_authority_at_boot,
        )
        from app.db.session import engine  # noqa: PLC0415
        from app.tasks.context import run_in_worker_loop  # noqa: PLC0415

        _assert_b26_p2_construction_authority_at_boot()
        checks["boot_gate_done"] = True

        async def _q() -> int:
            async with engine.connect() as conn:
                return int(
                    (
                        await conn.execute(
                            text(
                                "SELECT count(*) FROM"
                                " public.b26_p2_task_authority_directory"
                            )
                        )
                    ).scalar()
                )

        first = run_in_worker_loop(_q())
        second = run_in_worker_loop(_q())
        checks["shared_engine_first"] = first
        checks["shared_engine_reuse"] = second
    except Exception as exc:
        violations.append(f"xix_nc15_worker_pool_poisoned:{exc}")

    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XIX-NC-15",
                    "status": "PASS" if not violations else "FAIL",
                    "checks": checks,
                    "violations": violations,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    if violations:
        print("B26_P2_XIX_NC15_FAIL")
        for violation in violations:
            print(violation)
        return 1
    print("B26_P2_XIX_NC15_PASS")
    print(json.dumps({"checks": checks}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
