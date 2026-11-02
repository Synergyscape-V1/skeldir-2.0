"""Physical custody boundary probe: separate Postgres archive authority.

This is an equivalence probe, not a deployed S3/EFS claim. It stores the
actual signed custody bundle in a separate database owned by a custody role;
the finance actor has no CONNECT, the writer has INSERT/SELECT only, and a
trigger refuses UPDATE/DELETE. The bundle is downloaded and verified/restored
after the local live copy is removed.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import psycopg2

ROOT = Path(r"C:\Users\ayewhy\skeldir-2.0")
import sys

sys.path.insert(0, str(ROOT / "backend"))

from app.revenue_verification.source_attestation import generate_keypair
from app.revenue_verification.source_evidence_journal import (
    append_source_fact,
    load_source_fact_records,
)
from app.revenue_verification.source_journal_custody import (
    export_custody_bundle,
    restore_custody_bundle,
    verify_custody_bundle,
)

ADMIN_DSN = "host=127.0.0.1 port=5432 dbname=postgres user=postgres password=postgres"
suffix = uuid4().hex[:8]
DB = f"xxv_custody_probe_{suffix}"
OWNER = f"xxv_custody_owner_{suffix}"
WRITER = f"xxv_custody_writer_{suffix}"
FINANCE = f"xxv_finance_actor_{suffix}"
WRITER_PW = "W" + uuid4().hex
FINANCE_PW = "F" + uuid4().hex


def dsn(role: str, password: str) -> str:
    return f"host=127.0.0.1 port=5432 dbname={DB} user={role} password={password}"


def force_rmtree(path: Path) -> None:
    for child in sorted(path.rglob("*"), reverse=True):
        try:
            os.chmod(child, 0o666)
        except OSError:
            pass
    shutil.rmtree(path, ignore_errors=True)


def append(journal: Path, fact_id: str, xid: str) -> None:
    append_source_fact(
        fact_kind="source_money",
        fact_id=fact_id,
        tenant_id="custody-tenant",
        verdict_id="custody-verdict",
        statement={"id": fact_id},
        signature="sig",
        key_sha256="k",
        database_transaction_id=xid,
        path=journal,
    )


def main() -> dict:
    result: dict = {
        "scope": "Separate PostgreSQL archive authority; physical bytes and active permissions.",
        "limits": [
            "Not S3 Object Lock COMPLIANCE retention and not an EFS access point.",
            "A cluster superuser can drop the database; the financial-maintenance actor cannot connect.",
        ],
    }
    tmp = Path(tempfile.mkdtemp(prefix="r0030-storage-"))
    admin = psycopg2.connect(ADMIN_DSN)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                f"CREATE ROLE {OWNER} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE"
            )
            cur.execute(
                f"CREATE ROLE {WRITER} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE",
                (WRITER_PW,),
            )
            cur.execute(
                f"CREATE ROLE {FINANCE} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE",
                (FINANCE_PW,),
            )
            cur.execute(f"CREATE DATABASE {DB} OWNER {OWNER}")
            cur.execute(f"REVOKE CONNECT ON DATABASE {DB} FROM PUBLIC")
            cur.execute(f"GRANT CONNECT ON DATABASE {DB} TO {WRITER}")

        db_admin = psycopg2.connect(
            f"host=127.0.0.1 port=5432 dbname={DB} user=postgres password=postgres"
        )
        db_admin.autocommit = True
        try:
            with db_admin.cursor() as cur:
                cur.execute(f"SET ROLE {OWNER}")
                cur.execute(
                    """
                    CREATE TABLE custody_objects (
                        tip text PRIMARY KEY,
                        bytes bytea NOT NULL,
                        manifest jsonb NOT NULL,
                        created_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE FUNCTION deny_custody_mutation() RETURNS trigger
                    LANGUAGE plpgsql AS $$
                    BEGIN
                        RAISE EXCEPTION 'custody_object_immutable';
                    END;
                    $$
                    """
                )
                cur.execute(
                    """
                    CREATE TRIGGER custody_objects_immutable
                    BEFORE UPDATE OR DELETE ON custody_objects
                    FOR EACH ROW EXECUTE FUNCTION deny_custody_mutation()
                    """
                )
                cur.execute("REVOKE ALL ON custody_objects FROM PUBLIC")
                cur.execute(f"GRANT USAGE ON SCHEMA public TO {WRITER}")
                cur.execute(f"GRANT INSERT, SELECT ON custody_objects TO {WRITER}")
                cur.execute("RESET ROLE")
        finally:
            db_admin.close()

        private_seed, public_b64 = generate_keypair()
        private_path = tmp / "custody.key"
        public_path = tmp / "custody.pub"
        private_path.write_text(private_seed, encoding="utf-8")
        public_path.write_text(public_b64, encoding="utf-8")
        live = tmp / "live.jsonl"
        append(live, "s1", "100")
        append(live, "s2", "200")
        bundle = export_custody_bundle(
            journal=live, custody_dir=tmp / "local-custody", private_key_path=private_path
        )
        manifest_bytes = bundle.manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        tip = str(manifest["journal_tip"])

        writer = psycopg2.connect(dsn(WRITER, WRITER_PW))
        writer.autocommit = True
        with writer.cursor() as cur:
            cur.execute(
                "INSERT INTO custody_objects (tip, bytes, manifest) VALUES (%s, %s, %s)",
                (tip, psycopg2.Binary(bundle.journal_bytes), manifest_bytes.decode("utf-8")),
            )

        finance_connect = "CONNECTED"
        try:
            finance = psycopg2.connect(dsn(FINANCE, FINANCE_PW))
            finance.close()
        except Exception as exc:  # noqa: BLE001 - observed refusal
            finance_connect = f"{type(exc).__name__}:{str(exc).splitlines()[0]}"

        writer_delete = "ALLOWED"
        try:
            with writer.cursor() as cur:
                cur.execute("DELETE FROM custody_objects WHERE tip=%s", (tip,))
        except Exception as exc:  # noqa: BLE001 - observed refusal
            writer_delete = f"{type(exc).__name__}:{str(exc).splitlines()[0]}"

        writer_update = "ALLOWED"
        try:
            with writer.cursor() as cur:
                cur.execute(
                    "UPDATE custody_objects SET bytes=%s WHERE tip=%s",
                    (psycopg2.Binary(b"tampered"), tip),
                )
        except Exception as exc:  # noqa: BLE001 - observed refusal
            writer_update = f"{type(exc).__name__}:{str(exc).splitlines()[0]}"

        with writer.cursor() as cur:
            cur.execute(
                "SELECT bytes, manifest FROM custody_objects WHERE tip=%s", (tip,)
            )
            stored_bytes, stored_manifest = cur.fetchone()
        writer.close()

        force_rmtree(tmp / "local-custody")
        live.unlink()
        recovered = tmp / "recovered"
        recovered.mkdir()
        bundle_path = recovered / f"source-evidence-{tip}.jsonl"
        manifest_path = recovered / f"source-evidence-{tip}.manifest.json"
        bundle_path.write_bytes(bytes(stored_bytes))
        manifest_path.write_text(
            stored_manifest if isinstance(stored_manifest, str) else json.dumps(stored_manifest),
            encoding="utf-8",
        )
        verified = verify_custody_bundle(
            manifest_path=manifest_path, public_key_path=public_path
        )
        restored_journal = tmp / "restored.jsonl"
        disposition = restore_custody_bundle(
            manifest_path=manifest_path,
            journal=restored_journal,
            public_key_path=public_path,
        )
        restored_records = load_source_fact_records(restored_journal) or []

        result.update(
            {
                "database": DB,
                "roles": {
                    "archive_owner": OWNER,
                    "writer": WRITER,
                    "finance_actor": FINANCE,
                },
                "finance_connect": finance_connect,
                "writer_delete": writer_delete,
                "writer_update": writer_update,
                "stored_bundle_sha256": __import__("hashlib")
                .sha256(bundle.journal_bytes)
                .hexdigest(),
                "stored_record_count": verified.manifest["record_count"],
                "stored_tip": verified.manifest["journal_tip"],
                "restore_disposition": disposition,
                "restored_record_count": len(restored_records),
                "restored_matches": len(restored_records) == 2,
                "local_live_copy_removed_before_restore": True,
            }
        )
        result["passed"] = (
            finance_connect != "CONNECTED"
            and writer_delete != "ALLOWED"
            and writer_update != "ALLOWED"
            and disposition == "restored"
            and len(restored_records) == 2
        )
    finally:
        admin.close()
        cleanup = psycopg2.connect(ADMIN_DSN)
        cleanup.autocommit = True
        with cleanup.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
                (DB,),
            )
            cur.execute(f"DROP DATABASE IF EXISTS {DB}")
            cur.execute(f"DROP ROLE IF EXISTS {WRITER}")
            cur.execute(f"DROP ROLE IF EXISTS {FINANCE}")
            cur.execute(f"DROP ROLE IF EXISTS {OWNER}")
        cleanup.close()
        force_rmtree(tmp)
    return result


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
