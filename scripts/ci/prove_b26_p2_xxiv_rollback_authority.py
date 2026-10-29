#!/usr/bin/env python3
"""XXIV A11/B11: data-carrying rollback must conserve authority identity.

The probe provisions a CI-faithful database, mints one signed witness
checkpoint bound to the database authority universe, applies the supported
data-carrying downgrade from the current head to 202610180002, and re-applies
the chain to head. It then verifies that:

* the same authority-universe row and DEFINER reader survive both directions;
* the signed checkpoint still verifies against that universe while the
  corrective schema is downgraded and after it is restored;
* a re-upgrade does not mint a new universe.

The result is primary evidence for a data-carrying rollback, not a
binary-version serviceability claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
HEAD_REVISION = "202610280001"
DOWN_REVISION = "202610180002"
EMPTY_DIGEST = hashlib.sha256(b"").hexdigest()


def _run(command: list[str], *, env: dict[str, str], timeout: int = 1200) -> str:
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
            f"stdout:\n{completed.stdout[-4000:]}\n"
            f"stderr:\n{completed.stderr[-4000:]}"
        )
    return completed.stdout


def _dsn_parts(admin_dsn: str) -> tuple[str, str]:
    from urllib.parse import urlparse

    parsed = urlparse(admin_dsn)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 5432
    return host, str(port)


def _migration_dsn(admin_dsn: str, database: str) -> str:
    host, port = _dsn_parts(admin_dsn)
    return (
        f"postgresql://migration_owner:migration_owner@{host}:{port}/{database}"
    )


def _revision(dsn: str) -> str:
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version_num FROM public.alembic_version")
            row = cur.fetchone()
    if not row:
        raise RuntimeError("alembic_version is empty")
    return str(row[0])


def _universe(dsn: str) -> str:
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT public.b26_p2_authority_universe()")
            row = cur.fetchone()
            cur.execute("SELECT count(*) FROM public.b26_p2_authority_universe")
            rows = cur.fetchone()
    if not row or not rows or int(rows[0]) != 1:
        raise RuntimeError("authority universe row is not singular")
    return str(row[0])


def _universe_table_exists(dsn: str) -> bool:
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT to_regclass('public.b26_p2_authority_universe') IS NOT NULL"
            )
            row = cur.fetchone()
    return bool(row and row[0])


def _alembic_env(migration_dsn: str) -> dict[str, str]:
    env = dict(os.environ)
    env["DATABASE_URL"] = migration_dsn
    env["MIGRATION_DATABASE_URL"] = migration_dsn
    existing = env.get("PYTHONPATH", "")
    parts = [str(BACKEND_ROOT), str(REPO_ROOT)]
    if existing:
        parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["TESTING"] = "1"
    return env


def _provision(admin_dsn: str, database: str) -> None:
    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "database" / "prepare_migration_authority_boundary.py"),
            "--admin-dsn",
            admin_dsn,
            "--database-name",
            database,
        ],
        env=dict(os.environ),
        timeout=600,
    )


def _append_checkpoint(
    *,
    journal_path: Path,
    private_key_path: Path,
    public_key_path: Path,
    custody_path: Path,
    universe: str,
) -> dict[str, Any]:
    sys.path.insert(0, str(BACKEND_ROOT))
    from app.trust.history_witness import append_checkpoint, generate_keypair

    if not private_key_path.exists():
        private_seed, public_key = generate_keypair()
        private_key_path.write_text(private_seed, encoding="utf-8")
        public_key_path.write_text(public_key, encoding="utf-8")
    checkpoint = append_checkpoint(
        journal_path,
        private_key_path=private_key_path,
        ledger_count=0,
        ledger_tip_seq=None,
        ledger_tip_hash=None,
        ledger_prefix_digest=EMPTY_DIGEST,
        authority_universe=universe,
        custody_path=custody_path,
    )
    return {
        "checkpoint_hash": checkpoint.checkpoint_hash,
        "ledger_count": checkpoint.ledger_count,
        "authority_universe": checkpoint.authority_universe,
    }


def _verify_checkpoint(
    *,
    journal_path: Path,
    public_key_path: Path,
    genesis_hash: str,
    universe: str,
) -> dict[str, Any]:
    sys.path.insert(0, str(BACKEND_ROOT))
    from app.trust.history_witness import verify_journal

    verified = verify_journal(
        journal_path,
        public_key_path=public_key_path,
        genesis_hash=genesis_hash,
        expected_universe=universe,
        require_universe=True,
    )
    latest = verified.latest
    return {
        "checkpoint_count": len(verified.checkpoints),
        "tip_seq": latest.ledger_tip_seq,
        "tip_hash": latest.ledger_tip_hash,
        "authority_universe": latest.authority_universe,
        "verified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-dsn", required=True)
    parser.add_argument("--database", default="skeldir_xxiv_rollback_ci")
    parser.add_argument("--evidence-out", required=True)
    args = parser.parse_args()

    _provision(args.admin_dsn, args.database)
    migration_dsn = _migration_dsn(args.admin_dsn, args.database)
    env = _alembic_env(migration_dsn)

    _run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env)
    head_revision = _revision(migration_dsn)
    if head_revision != HEAD_REVISION:
        raise RuntimeError(
            f"expected head {HEAD_REVISION}, observed {head_revision}"
        )
    universe_before = _universe(migration_dsn)

    workdir = Path(tempfile.mkdtemp(prefix="xxiv-rollback-"))
    journal_path = workdir / "journal.jsonl"
    private_key_path = workdir / "witness.key"
    public_key_path = workdir / "witness.pub"
    custody_path = workdir / "custody.json"
    checkpoint = _append_checkpoint(
        journal_path=journal_path,
        private_key_path=private_key_path,
        public_key_path=public_key_path,
        custody_path=custody_path,
        universe=universe_before,
    )
    before_downgrade = _verify_checkpoint(
        journal_path=journal_path,
        public_key_path=public_key_path,
        genesis_hash=checkpoint["checkpoint_hash"],
        universe=universe_before,
    )

    _run(
        [sys.executable, "-m", "alembic", "downgrade", DOWN_REVISION],
        env=env,
    )
    down_revision = _revision(migration_dsn)
    if down_revision != DOWN_REVISION:
        raise RuntimeError(
            f"expected downgrade {DOWN_REVISION}, observed {down_revision}"
        )
    universe_down = _universe(migration_dsn)
    if universe_down != universe_before:
        raise RuntimeError("downgrade changed the authority universe")
    while_down = _verify_checkpoint(
        journal_path=journal_path,
        public_key_path=public_key_path,
        genesis_hash=checkpoint["checkpoint_hash"],
        universe=universe_down,
    )

    _run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env)
    restored_revision = _revision(migration_dsn)
    if restored_revision != HEAD_REVISION:
        raise RuntimeError(
            f"expected restored head {HEAD_REVISION}, observed {restored_revision}"
        )
    universe_restored = _universe(migration_dsn)
    if universe_restored != universe_before:
        raise RuntimeError("re-upgrade minted a different authority universe")
    after_restore = _verify_checkpoint(
        journal_path=journal_path,
        public_key_path=public_key_path,
        genesis_hash=checkpoint["checkpoint_hash"],
        universe=universe_restored,
    )

    evidence = {
        "status": "PASS",
        "database": args.database,
        "revisions": {
            "head": head_revision,
            "downgraded": down_revision,
            "restored": restored_revision,
        },
        "authority_universe": {
            "before": universe_before,
            "downgraded": universe_down,
            "restored": universe_restored,
            "stable": universe_before
            == universe_down
            == universe_restored,
            "table_retained": _universe_table_exists(migration_dsn),
        },
        "signed_history": {
            "checkpoint": checkpoint,
            "before_downgrade": before_downgrade,
            "while_downgraded": while_down,
            "after_restore": after_restore,
        },
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    evidence_path = Path(args.evidence_out)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "evidence": str(evidence_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
