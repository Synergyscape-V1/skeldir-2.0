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


def _protected_base() -> str | None:
    """Resolve the protected-history reference for publication checks.

    Merge-base with origin/main when available (PR and main-push
    topologies); the merge-base itself otherwise. None when no
    protected history is resolvable (fail closed by the caller).
    """
    for args in (
        ["merge-base", "HEAD", "origin/main"],
        ["rev-parse", "origin/main"],
        ["merge-base", "HEAD", "main"],
        ["rev-parse", "main"],
    ):
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip().splitlines()[0]
    return None


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

    # History arm: "published" means protected main, not the feature
    # branch. Development commits on an unmerged branch may iterate;
    # only divergence from the merge-base (the last protected state)
    # is a violation. Existing entries are immutable; evolution adds
    # entries; removal is forbidden.
    try:
        shallow = _git(["rev-parse", "--is-shallow-repository"]).strip()
        if shallow == "true":
            violations.append("manifest_history_unavailable_shallow_checkout")
            raise RuntimeError("shallow")
        rel = str(MANIFEST_PATH.relative_to(REPO_ROOT))
        base = _protected_base()
        if base is None:
            violations.append("manifest_history_no_protected_base")
            raise RuntimeError("no-base")
        try:
            base_blob = _git(["show", f"{base}:{rel}"])
            base_manifest = json.loads(base_blob)
            base_revisions = base_manifest.get("revisions", {})
        except (RuntimeError, ValueError):
            base_revisions = None
        if base_revisions is None:
            checks["manifest_first_publication_coherent"] = True
        else:
            for revision, entry in sorted(revisions.items()):
                base_entry = base_revisions.get(revision)
                if base_entry is None:
                    continue  # new entry: legitimate evolution
                if str(base_entry.get("sha256")) != str(entry.get("sha256")):
                    violations.append(
                        f"manifest_published_digest_changed:{revision}"
                    )
                if str(base_entry.get("file")) != str(entry.get("file")):
                    violations.append(
                        f"manifest_published_file_changed:{revision}"
                    )
            for revision in sorted(base_revisions):
                if revision not in revisions:
                    violations.append(
                        f"manifest_published_entry_removed:{revision}"
                    )
            if not [v for v in violations
                    if "manifest_published_" in v]:
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
