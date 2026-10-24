#!/usr/bin/env python3
"""XXIV A7: a committed source change cannot be signed stale.

The proof seeds a real B2.3 verdict, reads the builder's source snapshot,
then holds the issuance advisory lock from a second connection while the
builder blocks on the same lock. The source is updated and committed
inside that transaction; when the builder proceeds it must re-read the
source and refuse with ``source_changed_during_issuance``.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
NATURAL_PROOF = REPO_ROOT / "scripts" / "ci" / "prove_b26_p2_xxiv_natural_correction.py"


def _load_natural_proof():
    spec = importlib.util.spec_from_file_location(
        "xxiv_natural_proof", str(NATURAL_PROOF)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["xxiv_natural_proof"] = module
    spec.loader.exec_module(module)
    return module


def _request(tenant_id: UUID, verdict_id: UUID):
    from app.trust.builder import TrustEnvelopeBuildRequest

    return TrustEnvelopeBuildRequest(
        tenant_id=tenant_id,
        subject_type="match_verdict",
        subject_ref=f"urn:skeldir:match_verdict:{verdict_id}",
        request_context={
            "created_at": datetime.now(timezone.utc),
            "valid_until": datetime.now(timezone.utc).replace(
                year=datetime.now(timezone.utc).year + 1
            ),
            "audience_id": "xxiv-a7-proof",
        },
    )


def _observe_history(worker_dsn: str) -> str:
    import psycopg2

    conn = psycopg2.connect(worker_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT public.b26_p2_observe_history_integrity()")
            row = cur.fetchone()
    finally:
        conn.close()
    return str(row[0]) if row else ""


async def _run(args: argparse.Namespace) -> dict[str, object]:
    natural = _load_natural_proof()
    world = natural._seed_world(args.admin_dsn)
    tenant_id = UUID(world["tenant"])
    verdict_id = UUID(world["verdict"])
    observation = _observe_history(args.worker_dsn)

    from sqlalchemy import text

    from app.db.session import B23AsyncSessionLocal
    from app.trust.builder import build_unsigned_trust_envelope
    from app.trust.source_adapters import read_match_verdict_source

    async with B23AsyncSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )
        source_before = await read_match_verdict_source(
            session,
            tenant_id=tenant_id,
            subject_ref=f"urn:skeldir:match_verdict:{verdict_id}",
        )
    if source_before is None:
        raise RuntimeError("seeded source is not readable")

    locked = threading.Event()
    release = threading.Event()
    committed = threading.Event()
    thread_error: list[str] = []

    def hold_lock_and_change_source() -> None:
        import psycopg2

        try:
            conn = psycopg2.connect(args.admin_dsn)
            conn.autocommit = False
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_xact_lock(82173645, 300003)")
                    locked.set()
                    if not release.wait(timeout=20):
                        raise RuntimeError("caller did not release the lock")
                    cur.execute(
                        "SELECT set_config('app.current_tenant_id', %s, false)",
                        (str(tenant_id),),
                    )
                    cur.execute(
                        "UPDATE public.b23_match_verdicts"
                        " SET last_transition_at = clock_timestamp()"
                        " WHERE tenant_id = %s AND id = %s",
                        (str(tenant_id), str(verdict_id)),
                    )
                    if cur.rowcount != 1:
                        raise RuntimeError(
                            f"source update affected {cur.rowcount} rows"
                        )
                conn.commit()
                committed.set()
            finally:
                conn.close()
        except Exception as exc:  # noqa: BLE001
            thread_error.append(f"{type(exc).__name__}:{exc}")
            committed.set()

    thread = threading.Thread(target=hold_lock_and_change_source, daemon=True)
    thread.start()
    if not locked.wait(timeout=10):
        raise RuntimeError("lock holder did not acquire the issuance lock")

    async with B23AsyncSessionLocal() as builder_session:
        await builder_session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )
        builder = asyncio.create_task(
            build_unsigned_trust_envelope(
                builder_session,
                _request(tenant_id, verdict_id),
                source=source_before,
            )
        )
        await asyncio.sleep(0.5)
        blocked = not builder.done()
        release.set()
        if not committed.wait(timeout=10):
            raise RuntimeError("source update did not commit")
        result = await asyncio.wait_for(builder, timeout=30)
    thread.join(timeout=10)

    async with B23AsyncSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )
        source_after = await read_match_verdict_source(
            session,
            tenant_id=tenant_id,
            subject_ref=f"urn:skeldir:match_verdict:{verdict_id}",
        )
    if source_after is None:
        raise RuntimeError("updated source is not readable")

    return {
        "world": world,
        "history_observation": observation,
        "builder_blocked_on_lock": blocked,
        "builder_status": result.status,
        "builder_reason": result.reason_code,
        "source_changed": (
            source_before.last_transition_at != source_after.last_transition_at
        ),
        "thread_error": thread_error,
        "source_after": {
            "last_transition_at": source_after.last_transition_at.isoformat(),
            "amount_minor": source_after.canonical_net_verified_amount_minor,
        },
        "source_before": {
            "last_transition_at": source_before.last_transition_at.isoformat(),
            "amount_minor": source_before.canonical_net_verified_amount_minor,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-dsn", required=True)
    parser.add_argument("--runtime-dsn", required=True)
    parser.add_argument("--worker-dsn", required=True)
    parser.add_argument("--evidence-out", required=True)
    args = parser.parse_args()

    os.environ["DATABASE_URL"] = args.runtime_dsn
    os.environ["MIGRATION_DATABASE_URL"] = args.admin_dsn
    os.environ["B26_P2_HISTORY_WITNESS_REQUIRED"] = "false"
    os.environ["ENVIRONMENT"] = "test"
    sys.path.insert(0, str(BACKEND_ROOT))

    observed = asyncio.run(_run(args))
    status = (
        observed["builder_status"] == "refused"
        and observed["builder_reason"] == "source_changed_during_issuance"
        and observed["builder_blocked_on_lock"] is True
        and observed["source_changed"] is True
    )
    evidence = {
        "status": "PASS" if status else "FAIL",
        "observed": observed,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    evidence_path = Path(args.evidence_out)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": evidence["status"], "evidence": str(evidence_path)}))
    return 0 if status else 1


if __name__ == "__main__":
    raise SystemExit(main())
