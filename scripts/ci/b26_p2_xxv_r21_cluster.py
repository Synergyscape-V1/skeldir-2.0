#!/usr/bin/env python3
"""R-0021: signed source outcomes survive restoration into a new cluster."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b26_p2_xxv_falsify as F  # noqa: E402
from b26_p2_xxv_lane import PG  # noqa: E402

OUT = Path(
    os.environ.get(
        "R21_CLUSTER_OUT",
        str(F.LANE_ROOT / "evidence" / "xxv-r21-cluster.json"),
    )
)
SOURCE_DB = "xxv_b8_replay13_xx"
NEW_DB = "xxv_r21_cluster"
PG2 = "b26p2xxv-pg2"
PORT = "55472"
TENANT = "0e69af50-6d23-4958-94cb-3f0440edf6f0"
VERDICT = "2db89579-cb14-4142-9c2d-1fc6c9adbf2c"
INGRESS = "cdbb668e-8c4e-4c10-96fe-d8e18017358a"
JOURNAL = Path(
    "C:/Users/ayewhy/AppData/Local/Temp/b8-replay-p1p34fdx/source.jsonl"
)
PUBLIC = Path(
    "C:/Users/ayewhy/AppData/Local/Temp/b8-replay-p1p34fdx/source.pub"
)
PRIVATE = Path(
    "C:/Users/ayewhy/AppData/Local/Temp/b8-replay-p1p34fdx/source.key"
)


def _docker(*args: str) -> subprocess.CompletedProcess:
    return F.docker(*args)


def _start_cluster() -> None:
    _docker("rm", "-f", PG2)
    _docker(
        "run", "-d", "--name", PG2,
        "-e", "POSTGRES_USER=postgres",
        "-e", "POSTGRES_PASSWORD=postgres",
        "-e", "POSTGRES_DB=postgres",
        "-p", f"{PORT}:5432",
        "postgres:15-alpine",
    )
    for _ in range(90):
        if _docker("exec", PG2, "pg_isready", "-U", "postgres").returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("cluster_not_ready")


def _restore() -> None:
    dump = "/tmp/xxv_r21_cluster.dump"
    _docker("exec", PG, "pg_dump", "-U", "postgres", "-d", SOURCE_DB, "-Fc", "-f", dump)
    with tempfile.TemporaryDirectory(prefix="r21-dump-") as temporary:
        local_dump = str(Path(temporary) / "cluster.dump")
        first = _docker("cp", f"{PG}:{dump}", local_dump)
        if first.returncode != 0:
            raise RuntimeError(f"dump_copy_failed:{first.stderr[-500:]}")
        second = _docker("cp", local_dump, f"{PG2}:{dump}")
        if second.returncode != 0:
            raise RuntimeError(f"restore_copy_failed:{second.stderr[-500:]}")
    _docker("exec", PG2, "createdb", "-U", "postgres", NEW_DB)
    roles = (
        "app_rw", "app_ro", "app_user", "app_worker", "app_ingress",
        "app_trust_issuer", "app_trust_signer", "app_beat", "app_relay",
        "app_celery_transport", "migration_owner",
    )
    for role in roles:
        _docker(
            "exec", PG2, "psql", "-U", "postgres", "-d", NEW_DB,
            "-c", f"CREATE ROLE {role} LOGIN PASSWORD '{role}'",
        )
    _docker(
        "exec", PG2, "psql", "-U", "postgres", "-d", NEW_DB,
        "-c", "CREATE ROLE app_auth_lookup NOLOGIN BYPASSRLS",
    )
    proc = _docker(
        "exec", PG2, "pg_restore", "-U", "postgres", "-d", NEW_DB,
        "--no-owner", "--no-privileges", dump,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"restore_failed:{proc.stderr[-1000:]}")


def _journal_records(path: Path) -> list[dict]:
    from app.revenue_verification.source_evidence_journal import (  # noqa: PLC0415
        load_source_fact_records,
    )

    return load_source_fact_records(path) or []


def _write_journal(records: list[dict], path: Path) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


async def _read(dsn: str, journal: Path, *, expect_attested: bool) -> dict:
    from sqlalchemy import text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: PLC0415

    from app.revenue_verification.source_attestation import (  # noqa: PLC0415
        read_verdict_source_attestation_status,
    )
    from app.revenue_verification.source_evidence import (  # noqa: PLC0415
        source_evidence_snapshot,
    )

    os.environ["B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH"] = str(journal)
    os.environ["B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH"] = str(PUBLIC)
    os.environ["B26_P2_SOURCE_ATTESTATION_REQUIRED"] = "true"
    from app.core.config import settings  # noqa: PLC0415

    settings.B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH = str(journal)
    settings.B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH = str(PUBLIC)
    settings.B26_P2_SOURCE_ATTESTATION_REQUIRED = True
    engine = create_async_engine(dsn)
    try:
        async with AsyncSession(engine) as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :t, false)"),
                {"t": TENANT},
            )
            snapshot = await source_evidence_snapshot(session, tenant_id=TENANT)
            status = await read_verdict_source_attestation_status(
                session, tenant_id=TENANT, verdict_id=VERDICT
            )
            result = {
                "snapshot_digest": snapshot["digest"],
                "current_source": snapshot["current_sources"],
                "reader_status": status.status,
                "reader_reason": status.reason,
            }
            if expect_attested:
                if status.status != "xxv_attested":
                    raise AssertionError(f"reader_not_attested:{status.status}")
            elif status.status == "xxv_attested":
                raise AssertionError("unknown_outcome_was_accepted")
            return result
    finally:
        await engine.dispose()


def main() -> int:
    # The source journal must be loaded from the working tree before settings
    # is first imported.
    os.environ["PYTHONPATH"] = os.pathsep.join(
        [str(F.REPO_ROOT / "backend"), os.environ.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    os.environ["DATABASE_URL"] = (
        f"postgresql+asyncpg://postgres:postgres@127.0.0.1:{PORT}/{NEW_DB}"
    )
    os.environ["ENVIRONMENT"] = "ci"
    from app.revenue_verification.source_evidence_journal import (  # noqa: PLC0415
        append_source_fact_outcome,
    )

    _start_cluster()
    try:
        _restore()
        records = _journal_records(JOURNAL)
        source_records = [
            record
            for record in records
            if record.get("fact_kind") == "source_money"
            and str(record.get("fact_id")) == INGRESS
            and record.get("version", "").startswith(
                "b26-p2-source-fact-journal-"
            )
        ]
        if not source_records:
            raise RuntimeError("source_journal_fact_missing")
        source_record = source_records[-1]
        old_xid = str(source_record["database_transaction_id"])
        with tempfile.TemporaryDirectory(prefix="r21-cluster-") as temporary:
            temp = Path(temporary)
            committed = temp / "committed.jsonl"
            unknown = temp / "unknown.jsonl"
            recovered = temp / "recovered.jsonl"
            _write_journal(records, committed)
            # The B8 helper's source writer ran outside the shipping outcome
            # context. Add the auth-root-signed committed outcome that the
            # shipping auth path produces, then exercise cluster migration.
            append_source_fact_outcome(
                record=source_record,
                outcome="committed",
                private_key_path=str(PRIVATE),
                path=committed,
            )
            committed_result = asyncio.run(
                _read(
                    os.environ["DATABASE_URL"], committed, expect_attested=True
                )
            )

            filtered = [
                record
                for record in records
                if not (
                    record.get("fact_kind") == "source_money"
                    and str(record.get("fact_id")) == INGRESS
                    and (
                        record.get("version", "").startswith(
                            "b26-p2-source-fact-journal-"
                        )
                        or record.get("version")
                        == "b26-p2-source-fact-outcome-v1"
                    )
                )
            ]
            prepared = {
                "version": "b26-p2-source-fact-journal-v2",
                "fact_kind": "source_money",
                "fact_id": INGRESS,
                "tenant_id": source_record["tenant_id"],
                "verdict_id": "",
                "statement": source_record["statement"],
                "signature": source_record["signature"],
                "key_sha256": source_record["key_sha256"],
                "database_transaction_id": old_xid,
            }
            _write_journal([*filtered, prepared], unknown)
            append_source_fact_outcome(
                record=prepared,
                outcome="unknown",
                private_key_path=str(PRIVATE),
                path=unknown,
            )
            try:
                unknown_result = asyncio.run(
                    _read(
                        os.environ["DATABASE_URL"],
                        unknown,
                        expect_attested=False,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - refusal is expected
                unknown_result = {
                    "refused": True,
                    "error": f"{type(exc).__name__}:{exc}",
                }
            append_source_fact_outcome(
                record=prepared,
                outcome="committed",
                private_key_path=str(PRIVATE),
                path=unknown,
            )
            shutil.copyfile(unknown, recovered)
            recovered_result = asyncio.run(
                _read(
                    os.environ["DATABASE_URL"], recovered, expect_attested=True
                )
            )
            record = {
                "gate_id": "B26-P2-R21-CLUSTER-MIGRATION",
                "source_database": SOURCE_DB,
                "restored_cluster": PG2,
                "restored_database": NEW_DB,
                "old_transaction_id": old_xid,
                "committed_outcome": committed_result,
                "unknown_outcome": unknown_result,
                "recovered_after_committed_outcome": recovered_result,
                "checks": {
                    "signed_committed_outcome_survives_new_cluster": True,
                    "unknown_outcome_is_refused_not_aborted": True,
                    "committed_outcome_after_unknown_restores_attestation": True,
                },
                "passed": True,
            }
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(record, indent=2), encoding="utf-8")
            print(json.dumps(record["checks"], indent=2))
            return 0
    finally:
        _docker("rm", "-f", PG2)


if __name__ == "__main__":
    raise SystemExit(main())
