#!/usr/bin/env python3
"""B2.6-P2 Corrective VIII authority-universe pin assertion.

The capability manifest's authority_universe_hash binds MEANING (routine
signature/owner/secdef/config/body, trigger identity/definition, schema
privileges, RLS definitions, ownership), not just grant/name membership.
The reviewed pin (contracts-internal/governance/...) records the hash a
human reviewed for one migration head. Any load-bearing semantic mutation
changes the hash and REDs here until the pin is explicitly re-reviewed
(pin update + falsifier evidence in the same change).

Usage:
  python scripts/ci/assert_b26_p2_authority_universe.py \
    --dsn postgresql://postgres:postgres@127.0.0.1:5432/db \
    --pin contracts-internal/governance/b26_p2_authority_universe.pin.json \
    [--covered app_worker:EXECUTE:b26_p2_mark_conducted ...] \
    [--evidence-out artifacts/b26_p2/authority/universe.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = (
    Path(__file__).resolve().parents[2]
    if len(Path(__file__).resolve().parents) > 2
    else Path(__file__).resolve().parent
)
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))
sys.path.insert(0, str(REPO_ROOT))


def _migration_head(explicit: str | None) -> str:
    if explicit:
        return explicit
    import re
    import subprocess

    output = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=str(REPO_ROOT),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    heads = {
        match.group(1)
        for line in output.splitlines()
        if (match := re.match(r"^([0-9a-f]+)\b", line.strip()))
    }
    if len(heads) != 1:
        raise SystemExit(f"expected_one_migration_head:{sorted(heads)}")
    return next(iter(heads))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--pin", type=Path, required=True)
    parser.add_argument("--covered", nargs="*", default=[])
    parser.add_argument("--evidence-out", type=Path, default=None)
    parser.add_argument("--migration-head", default=None)
    args = parser.parse_args()

    from b26_p2_capability_surface import build_manifest  # noqa: PLC0415

    pin = json.loads(args.pin.read_text(encoding="utf-8"))
    live_head = _migration_head(args.migration_head)
    manifest = build_manifest(args.dsn, tuple(args.covered))
    live_hash = manifest["authority_universe_hash"]
    unknown = manifest.get("open_world_unknown", [])
    multi = manifest.get("multi_signature_routine_names", [])

    details = {
        "migration_head_live": live_head,
        "migration_head_pin": pin.get("migration_head"),
        "authority_universe_hash_live": live_hash,
        "authority_universe_hash_pin": pin.get("authority_universe_hash"),
        "open_world_unknown": unknown,
        "multi_signature_routine_names": multi,
        "meaning_surface_counts": {
            "routine_meaning": len(manifest.get("routine_meaning_identities", [])),
            "trigger_meaning": len(manifest.get("trigger_meaning_census", [])),
            "schema_meaning": len(manifest.get("schema_meaning_privs", [])),
            "rls_meaning": len(manifest.get("rls_meaning_census", [])),
            "ownership": len(manifest.get("ownership_census", [])),
        },
    }
    failures: list[str] = []
    if pin.get("migration_head") != live_head:
        failures.append(
            "pin_migration_head_stale:pin=%s:live=%s"
            % (pin.get("migration_head"), live_head)
        )
    if pin.get("authority_universe_hash") != live_hash:
        failures.append("authority_universe_drift:review_required")
    if unknown:
        failures.append("open_world_unknown:%s" % unknown[:3])
    if args.evidence_out is not None:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(json.dumps(details, indent=2), encoding="utf-8")
    if failures:
        print("B26_P2_AUTHORITY_UNIVERSE_FAIL " + ";".join(failures))
        print(json.dumps(details, indent=2))
        return 1
    print(f"B26_P2_AUTHORITY_UNIVERSE_PASS hash={live_hash[:12]} head={live_head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
