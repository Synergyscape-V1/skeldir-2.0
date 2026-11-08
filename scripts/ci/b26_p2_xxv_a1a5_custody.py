#!/usr/bin/env python3
"""A1/A5: shipping volume and key custody for the source-fact journal."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b26_p2_xxv_falsify as F  # noqa: E402
from b26_p2_xxv_lane import (  # noqa: E402
    API,
    AUTH,
    OBSERVER,
    SOURCE_EVIDENCE_VOL,
    WITNESS_VOL,
    load_state,
)

os.environ.setdefault(
    "DATABASE_URL",
    f"postgresql+asyncpg://app_user:app_user@127.0.0.1:{F.PG_PORT}/{F.DB_NAME}",
)
os.environ.setdefault("ENVIRONMENT", "ci")

OUT = Path(
    os.environ.get(
        "A1A5_CUSTODY_OUT",
        str(F.LANE_ROOT / "evidence" / "xxv-a1a5-custody.json"),
    )
)


def _mounts(container: str) -> dict[str, dict]:
    proc = F.docker("inspect", container, "--format", "{{json .Mounts}}")
    return {item["Destination"]: item for item in json.loads(proc.stdout)}


def _can_write(container: str, path: str) -> bool:
    proc = F.docker("exec", container, "sh", "-c", f"printf x >> {path}")
    return proc.returncode == 0


def _can_read(container: str, path: str) -> bool:
    proc = F.docker("exec", container, "sh", "-c", f"test -r {path}")
    return proc.returncode == 0


def main() -> int:
    state = load_state()
    auth = _mounts(AUTH)
    api = _mounts(API)
    observer = _mounts(OBSERVER)
    source_path = "/var/lib/b26_p2_source/source_evidence.jsonl"
    ingress_key = "/run/secrets/b26_p2_source_attestation_key"
    witness_key = "/run/secrets/b26_p2_history_witness_key"
    checks = {
        "auth_source_rw": bool(auth.get("/var/lib/b26_p2_source", {}).get("RW")),
        "api_source_ro": not bool(api.get("/var/lib/b26_p2_source", {}).get("RW")),
        "observer_source_ro": not bool(
            observer.get("/var/lib/b26_p2_source", {}).get("RW")
        ),
        "auth_witness_ro": not bool(auth.get("/var/lib/b26_p2", {}).get("RW")),
        "api_witness_ro": not bool(api.get("/var/lib/b26_p2", {}).get("RW")),
        "observer_witness_rw": bool(observer.get("/var/lib/b26_p2", {}).get("RW")),
        "api_cannot_write_journal": not _can_write(API, source_path),
        "observer_cannot_write_journal": not _can_write(
            OBSERVER, source_path
        ),
        "auth_holds_ingress_attestation_key": _can_read(AUTH, ingress_key),
        "api_has_no_ingress_key_mount": "/run/secrets" not in api,
        "observer_has_no_ingress_key": not _can_read(OBSERVER, ingress_key),
        "observer_holds_witness_key": _can_read(OBSERVER, witness_key),
        "auth_has_no_witness_key": not _can_read(AUTH, witness_key),
        "api_has_no_witness_key": not _can_read(API, witness_key),
    }
    journal_bytes = F.volume_get(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl")
    witness_bytes = F.volume_get(WITNESS_VOL, "history_witness.jsonl")
    with tempfile.TemporaryDirectory(prefix="a1a5-") as temporary:
        journal = Path(temporary) / "source.jsonl"
        witness = Path(temporary) / "witness.jsonl"
        journal.write_bytes(journal_bytes)
        witness.write_bytes(witness_bytes)
        os.environ["B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH"] = str(journal)
        from app.revenue_verification.source_evidence_journal import (  # noqa: PLC0415
            journal_record_hash,
            load_source_fact_records,
        )

        records = load_source_fact_records() or []
        current_count = len(records)
        current_tip = journal_record_hash(records[-1]) if records else None
        latest = json.loads(witness.read_text(encoding="utf-8").splitlines()[-1])[
            "payload"
        ]
        witnessed_count = latest.get("source_journal_count")
        witnessed_tip = latest.get("source_journal_tip")
        prefix_ok = bool(
            witnessed_count is not None
            and current_count >= witnessed_count
            and (
                witnessed_count == 0
                or journal_record_hash(records[witnessed_count - 1])
                == witnessed_tip
            )
        )
        checks.update(
            {
                "journal_chain_valid": True,
                "journal_count": current_count,
                "journal_tip": current_tip,
                "witnessed_journal_count": witnessed_count,
                "witnessed_journal_tip": witnessed_tip,
                "witnessed_tip_is_prefix": prefix_ok,
            }
        )
    passed = all(
        value is True for key, value in checks.items() if isinstance(value, bool)
    )
    record = {
        "property": (
            "A1/A5: source-journal volume and signing-key custody, and "
            "independent journal-tip prefix"
        ),
        "artifact": state["artifact"],
        "checks": checks,
        "limit_of_inference": (
            "Docker volume mount modes and container reachability on the running "
            "lane; it does not prove a cloud deployment's volume ACLs or an "
            "independent actor audit."
        ),
        "passed": passed,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(checks, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
