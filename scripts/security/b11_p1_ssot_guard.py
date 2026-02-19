from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.core.managed_settings_guard import (
    run_guard,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="B11-P1 SSOT contract enforcement")
    parser.add_argument(
        "--snapshot",
        default="docs/forensics/evidence/b11_p1/ssot_contract_snapshot.json",
        help="Snapshot output path",
    )
    parser.add_argument(
        "--check-drift",
        action="store_true",
        help="Fail if snapshot differs from regenerated output",
    )
    args = parser.parse_args()
    os.environ.setdefault("DATABASE_URL", "postgresql://app_user:app_user@127.0.0.1:5432/skeldir")
    key_count = run_guard(snapshot_path=Path(args.snapshot), check_drift=args.check_drift)
    print(f"SSOT guard passed: keys={key_count}")


if __name__ == "__main__":
    main()
