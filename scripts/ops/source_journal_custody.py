#!/usr/bin/env python3
"""Export, verify or restore signed XXV source-journal custody bundles."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))
# Custody is filesystem-only; the package initializer imports the application
# settings contract, so provide a non-connecting required DSN default.
os.environ.setdefault("DATABASE_URL", "postgresql://custody@127.0.0.1:5432/custody")

from app.revenue_verification.source_journal_custody import (  # noqa: E402
    SourceJournalCustodyError,
    export_custody_bundle,
    restore_custody_bundle,
    verify_custody_bundle,
)
from app.trust.history_witness import (  # noqa: E402
    HistoryWitnessError,
    verify_journal,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export")
    export.add_argument("--journal", required=True)
    export.add_argument("--custody-dir", required=True)
    export.add_argument("--private-key", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--public-key", required=True)
    verify.add_argument("--public-key-is-private-seed", action="store_true")

    restore = sub.add_parser("restore")
    restore.add_argument("--manifest", required=True)
    restore.add_argument("--journal", required=True)
    restore.add_argument("--public-key", required=True)
    restore.add_argument("--public-key-is-private-seed", action="store_true")
    restore.add_argument("--accepted-source-count", type=int)
    restore.add_argument("--accepted-source-tip")
    restore.add_argument("--witness-journal")
    restore.add_argument("--witness-public-key")
    restore.add_argument("--witness-genesis-hash")

    args = parser.parse_args()
    try:
        if args.command == "export":
            bundle = export_custody_bundle(
                journal=args.journal,
                custody_dir=args.custody_dir,
                private_key_path=args.private_key,
            )
            outcome = {
                "status": "exported",
                "manifest": str(bundle.manifest_path),
                "record_count": bundle.manifest["record_count"],
                "journal_tip": bundle.manifest["journal_tip"],
            }
        elif args.command == "verify":
            bundle = verify_custody_bundle(
                manifest_path=args.manifest,
                public_key_path=args.public_key,
                public_key_is_private_seed=args.public_key_is_private_seed,
            )
            outcome = {
                "status": "verified",
                "manifest": str(bundle.manifest_path),
                "record_count": bundle.manifest["record_count"],
                "journal_tip": bundle.manifest["journal_tip"],
            }
        else:
            accepted_count = args.accepted_source_count
            accepted_tip = args.accepted_source_tip
            if args.witness_journal is not None:
                if accepted_count is not None or accepted_tip is not None:
                    raise SourceJournalCustodyError(
                        "custody_accepted_source_arguments_conflict"
                    )
                if args.witness_public_key is None:
                    raise SourceJournalCustodyError(
                        "custody_witness_public_key_required"
                    )
                witness = verify_journal(
                    args.witness_journal,
                    public_key_path=args.witness_public_key,
                    genesis_hash=args.witness_genesis_hash,
                )
                latest = witness.latest
                accepted_count = latest.source_journal_count
                accepted_tip = latest.source_journal_tip
                if accepted_count is None:
                    raise SourceJournalCustodyError(
                        "custody_witness_source_commitment_missing"
                    )
            disposition = restore_custody_bundle(
                manifest_path=args.manifest,
                journal=args.journal,
                public_key_path=args.public_key,
                public_key_is_private_seed=args.public_key_is_private_seed,
                accepted_source_count=accepted_count,
                accepted_source_tip=accepted_tip,
            )
            outcome = {"status": disposition}
    except (OSError, SourceJournalCustodyError, HistoryWitnessError) as exc:
        print(f"SOURCE_JOURNAL_CUSTODY_FAIL {exc}", file=sys.stderr)
        return 1
    print(json.dumps(outcome, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
