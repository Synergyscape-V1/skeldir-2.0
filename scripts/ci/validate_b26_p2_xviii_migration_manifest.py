#!/usr/bin/env python3
"""B2.6-P2 Corrective XVIII migration-identity integrity gate.

H-XVIII-R16 (Directive XVIII, NC-12): an already-published migration
identity must be content-addressed. Editing a deployed revision under
the same revision id -- without a new revision -- REDs here:

- every governed revision's file hash equals the manifest entry;
- across git history, no published entry's digest ever changes
  (legitimate evolution appends entries; existing entries immutable).

Exit code is the gate. Prints B26_P2_XVIII_MANIFEST_PASS on success.
History arm fails closed on shallow checkouts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b26_p2_migration_manifest.json"
)
MIGRATION_DIR = (
    REPO_ROOT / "alembic" / "versions" / "007_skeldir_foundation"
)


def _git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr[:200]}")
    return proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="XVIII manifest gate.")
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}

    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        print("B26_P2_XVIII_MANIFEST_FAIL")
        print(f"manifest_unreadable:{exc}")
        return 1
    revisions = manifest.get("revisions", {})
    if not revisions:
        violations.append("manifest_revisions_empty")
    live: dict[str, str] = {}
    for revision, entry in sorted(revisions.items()):
        matches = sorted(MIGRATION_DIR.glob(f"{revision}_*.py"))
        if len(matches) != 1 or matches[0].name != entry.get("file"):
            violations.append(f"manifest_revision_file_missing:{revision}")
            continue
        digest = hashlib.sha256(matches[0].read_bytes()).hexdigest()
        live[revision] = digest
        if digest != entry.get("sha256"):
            violations.append(f"manifest_hash_mismatch:{revision}")
    if not [v for v in violations if "manifest_hash_mismatch" in v
            or "manifest_revision_file_missing" in v]:
        checks["manifest_hashes_match"] = True

    # History arm: no published entry may change across history.
    try:
        shallow = _git(["rev-parse", "--is-shallow-repository"]).strip()
        if shallow == "true":
            violations.append("manifest_history_unavailable_shallow_checkout")
            raise RuntimeError("shallow")
        rel = str(MANIFEST_PATH.relative_to(REPO_ROOT))
        first_publication = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{rel}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
        ).returncode != 0
        if first_publication:
            checks["manifest_first_publication_coherent"] = True
        else:
            commits = [
                line.strip()
                for line in _git(["log", "--format=%H", "--", rel]).splitlines()
                if line.strip()
            ]
            if not commits:
                violations.append("manifest_history_empty")
            else:
                for revision, current in sorted(live.items()):
                    seen: set[str] = set()
                    for sha in commits:
                        try:
                            blob = _git(["show", f"{sha}:{rel}"])
                            old = json.loads(blob)
                            old_entry = old.get("revisions", {}).get(revision)
                            if old_entry is not None:
                                seen.add(str(old_entry.get("sha256")))
                        except (RuntimeError, ValueError):
                            violations.append(
                                f"manifest_history_unreadable:{sha[:12]}"
                            )
                            break
                    if len(seen) > 1:
                        violations.append(
                            "manifest_published_digest_changed:"
                            f"{revision}"
                        )
                    elif seen and seen != {current}:
                        violations.append(
                            f"manifest_history_diverges:{revision}"
                        )
                if not [v for v in violations
                        if "manifest_published_digest_changed" in v
                        or "manifest_history_diverges" in v]:
                    checks["manifest_history_single_valued"] = True
    except RuntimeError as exc:
        if "manifest_history_unavailable" not in ";".join(violations):
            violations.append(f"manifest_history_check_failed:{exc}")

    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XVIII_MANIFEST_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XVIII-MANIFEST",
                    "status": status,
                    "violations": sorted(violations),
                    "checks": checks,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
