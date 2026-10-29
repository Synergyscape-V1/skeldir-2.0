#!/usr/bin/env python3
"""R-0021 addendum: transaction evidence outlives pg_xact_status retention.

A committed source fact is copied into a journal whose producing transaction id
is an old xid whose status PostgreSQL has forgotten (``pg_xact_status`` returns
NULL). The auth-root-signed committed outcome is the independent evidence. The
same journal is exercised against a database restored from a dump, so the
original transaction history is not preserved. The source reader must still
return ``xxv_attested`` and the source manifest must resolve the current source.
The no-outcome control must be honestly unverifiable, not silently accepted.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault(
    "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH",
    "C:/Users/ayewhy/AppData/Local/Temp/b26p2xxv-lane/source_attestation_ed25519.pub",
)
import b26_p2_xxv_falsify as F  # noqa: E402
from b26_p2_xxv_lane import load_state, sql  # noqa: E402

os.environ.setdefault(
    "DATABASE_URL",
    f"postgresql+asyncpg://app_user:app_user@127.0.0.1:{F.PG_PORT}/{F.DB_NAME}",
)
os.environ.setdefault("ENVIRONMENT", "ci")

OUT = Path(
    os.environ.get(
        "R21_AGING_OUT",
        str(F.LANE_ROOT / "evidence" / "xxv-r21-aging.json"),
    )
)
RESTORED_DB = "xxv_r21_aging"
FAKE_XID = "100"  # old, forgotten transaction id; pg_xact_status returns NULL


def _pg(*args: str) -> subprocess.CompletedProcess:
    return F.docker("exec", f"{F.PREFIX}-pg", *args)


def _write_journal(records, path: Path, *, include_outcome: bool) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    if include_outcome:
        # The outcome is signed over the fake transaction id; it is the
        # independent evidence that survives status retention.
        from app.revenue_verification.source_evidence_journal import (  # noqa: PLC0415
            append_source_fact_outcome,
        )

        append_source_fact_outcome(
            record=records[-1],
            outcome="committed",
            private_key_path=str(_SOURCE_KEY),
            path=path,
        )


def _restore_database() -> None:
    _pg("dropdb", "-U", "postgres", "--if-exists", RESTORED_DB)
    dump = "/tmp/xxv_r21_aging.dump"
    _pg("pg_dump", "-U", "postgres", "-d", F.DB_NAME, "-Fc", "-f", dump)
    _pg("createdb", "-U", "postgres", RESTORED_DB)
    _pg("pg_restore", "-U", "postgres", "-d", RESTORED_DB, dump)


async def _read_restored(tenant: str, verdict: str, journal: Path):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.revenue_verification.source_attestation import (
        read_verdict_source_attestation_status,
    )
    from app.revenue_verification.source_evidence import source_evidence_snapshot

    engine = create_async_engine(
        f"postgresql+asyncpg://app_user:app_user@127.0.0.1:{F.PG_PORT}/{RESTORED_DB}"
    )
    try:
        async with AsyncSession(engine) as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :t, false)"),
                {"t": tenant},
            )
            snapshot = await source_evidence_snapshot(
                session, tenant_id=tenant
            )
            status = await read_verdict_source_attestation_status(
                session, tenant_id=tenant, verdict_id=verdict
            )
            return {
                "snapshot_digest": snapshot["digest"],
                "current_source": snapshot["current_sources"],
                "reader_status": status.status,
                "reader_reason": status.reason,
            }
    finally:
        await engine.dispose()


def main() -> int:
    global _SOURCE_KEY
    state = load_state()
    tenant = state["tenant_a"]
    # A fresh committed fact, with a real signed outcome in the live journal.
    commerce = f"pi_aging{uuid.uuid4().hex[:12]}"
    F.post_stripe_envelope(
        state,
        tenant,
        event_reference=f"evt_aging{uuid.uuid4().hex[:12]}",
        commerce_reference=commerce,
        amount=4321,
    )
    verdict = F.wait_verdict(tenant["tenant_id"], commerce, timeout_s=180)
    if verdict is None:
        raise RuntimeError("aging_verdict_missing")
    F.observe_once(state)
    row = sql(
        "SELECT i.id::text, i.provider, i.provider_native_commerce_reference,"
        " a.statement::text, a.signature, a.key_sha256"
        " FROM public.webhook_ingress_identities i"
        " JOIN public.b26_p2_source_money_attestation a"
        " ON a.webhook_ingress_identity_id=i.id"
        " WHERE i.tenant_id=%s AND i.provider_native_commerce_reference=%s",
        (tenant["tenant_id"], commerce),
    )[0]
    ingress_id, provider, commerce_ref, statement_text, signature, key_sha256 = row
    statement = json.loads(statement_text)
    live_bytes = F.volume_get(
        F.SOURCE_EVIDENCE_VOL, "source_evidence.jsonl"
    )
    live_records = [
        json.loads(line)
        for line in live_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    filtered = [
        record
        for record in live_records
        if not (
            record.get("version") == "b26-p2-source-fact-journal-v2"
            and record.get("fact_kind") == "source_money"
            and record.get("fact_id") == ingress_id
        )
        and not (
            record.get("version") == "b26-p2-source-fact-outcome-v1"
            and record.get("fact_kind") == "source_money"
            and record.get("fact_id") == ingress_id
        )
    ]
    prepared = {
        "version": "b26-p2-source-fact-journal-v2",
        "fact_kind": "source_money",
        "fact_id": ingress_id,
        "tenant_id": tenant["tenant_id"],
        "verdict_id": "",
        "statement": statement,
        "signature": signature,
        "key_sha256": key_sha256,
        "database_transaction_id": FAKE_XID,
    }
    _SOURCE_KEY = F.LANE_ROOT / "aging-source.key"
    _SOURCE_KEY.write_text(state["material"]["attestation_private_b64url"], encoding="utf-8")
    public_path = F.LANE_ROOT / "aging-source.pub"
    public_path.write_bytes(F.volume_get(F.WITNESS_VOL, "source_attestation_ed25519.pub"))

    with tempfile.TemporaryDirectory(prefix="r21-aging-") as temporary:
        temp = Path(temporary)
        committed_journal = temp / "committed.jsonl"
        unverifiable_journal = temp / "unverifiable.jsonl"
        _write_journal([*filtered, prepared], committed_journal, include_outcome=True)
        _write_journal([*filtered, prepared], unverifiable_journal, include_outcome=False)

        status = sql(
            "SELECT pg_xact_status(%s::xid8)::text", (FAKE_XID,)
        )[0][0]
        _restore_database()

        os.environ["DATABASE_URL"] = (
            f"postgresql+asyncpg://app_user:app_user@127.0.0.1:{F.PG_PORT}/{RESTORED_DB}"
        )
        os.environ["ENVIRONMENT"] = "ci"
        os.environ["B26_P2_SOURCE_ATTESTATION_REQUIRED"] = "true"
        os.environ["B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH"] = str(public_path)
        os.environ["B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH"] = str(committed_journal)
        restored = asyncio.run(_read_restored(tenant["tenant_id"], verdict["verdict_id"], committed_journal))

        os.environ["B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH"] = str(unverifiable_journal)
        try:
            unverified = asyncio.run(_read_restored(tenant["tenant_id"], verdict["verdict_id"], unverifiable_journal))
            unverified_result = {"accepted": True, **unverified}
        except Exception as exc:  # noqa: BLE001 - the refusal is the expected result
            unverified_result = {
                "accepted": False,
                "error": f"{type(exc).__name__}:{exc}",
            }

        record = {
            "artifact": state["artifact"],
            "fake_xid": FAKE_XID,
            "pg_xact_status": status,
            "restored_database": RESTORED_DB,
            "verdict_id": verdict["verdict_id"],
            "committed_journal": str(committed_journal),
            "unverifiable_journal": str(unverifiable_journal),
            "restored": restored,
            "unverifiable": unverified_result,
            "oracle": {
                "status_forgotten": status is None,
                "committed_fact_attested": restored["reader_status"] == "xxv_attested",
                "current_source_resolved": bool(restored["current_source"]),
                "no_outcome_refused": unverified_result["accepted"] is False,
            },
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        print(json.dumps(record["oracle"], indent=2))
        return 0 if all(record["oracle"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
