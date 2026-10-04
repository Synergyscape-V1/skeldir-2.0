#!/usr/bin/env python3
"""B2.6-P2 Corrective XVIII immutable semantic-regime registry gate.

H-XVIII-R1/R2 (Directive XVIII, NC-01): the published semantic identity
``xvii-sovereign-v1`` denotes exactly one immutable contract law. The
pin proves same-commit correspondence; THIS gate proves identity
immutability:

- the live contract bytes equal the registry entry digest, the XVII
  pin digest, the XVIII migration seed literal, and (with --dsn) the
  live database registry row;
- across git history, the published digest for the identity never
  changes (append-only evolution: a new law requires a new identity);
- the registry schema admits multiple regimes (evolvability is
  representable; R2), while each identity stays single-valued.

A simultaneous co-edit of contract + parser + oracle + goldens + pin
under the same regime REDs here (the registry/migration/history
still name the published law).

Exit code is the gate. Prints B26_P2_XVIII_REGISTRY_PASS on success.
Static gate (no database required) unless --dsn is given, in which
case the live table row is also asserted. History arm fails closed
when git history is unavailable (shallow checkout).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "reconciliation"
    / "b2.6"
    / "provider-semantic-contract.v1.json"
)
REGISTRY_PATH = (
    REPO_ROOT
    / "contracts"
    / "reconciliation"
    / "b2.6"
    / "semantic-regime-registry.json"
)
PIN_PATH = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b26_p2_xvii_semantic_contract.pin.json"
)
MIG_XVIII = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609300001_b26_p2_corrective_xviii_authority_conservation.py"
)

REGIME = "xvii-sovereign-v1"


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
    parser = argparse.ArgumentParser(description="XVIII registry gate.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}

    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        print("B26_P2_XVIII_REGISTRY_FAIL")
        print(f"registry_unreadable:{exc}")
        return 1
    regimes = registry.get("regimes", [])
    by_id = {entry.get("regime_id"): entry for entry in regimes}
    if len(by_id) != len(regimes):
        violations.append("registry_regime_identity_not_unique")
    else:
        checks["registry_identities_unique"] = True
    entry = by_id.get(REGIME)
    if entry is None:
        violations.append(f"registry_missing_published_regime:{REGIME}")
        print("B26_P2_XVIII_REGISTRY_FAIL")
        print(";".join(sorted(violations)))
        return 1

    live_digest = hashlib.sha256(
        CONTRACT_PATH.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    if entry.get("contract_digest") != live_digest:
        violations.append("registry_digest_diverges_from_live_contract")
    else:
        checks["registry_matches_live_contract"] = True

    try:
        pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        violations.append(f"xvii_pin_unreadable:{exc}")
        pin = {}
    if pin.get("contract_sha256") != live_digest:
        violations.append("registry_digest_diverges_from_reviewed_pin")
    else:
        checks["registry_matches_reviewed_pin"] = True

    try:
        mig_text = MIG_XVIII.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xviii_migration_unreadable:{exc}")
        mig_text = ""
    seed = re.search(
        r'_XVIII_CONTRACT_DIGEST\s*=\s*\(\s*"([0-9a-f]{64})"\s*\)', mig_text
    ) or re.search(r'_XVIII_CONTRACT_DIGEST[^"]*"([0-9a-f]{64})"', mig_text)
    if seed is None or seed.group(1) != live_digest:
        violations.append("registry_digest_diverges_from_migration_seed")
    else:
        checks["registry_matches_migration_seed"] = True
    if entry.get("activation_revision") != "202609300001":
        violations.append("registry_activation_revision_unexpected")
    else:
        checks["registry_activation_revision_bound"] = True

    # History arm: "published" means protected main, not the feature
    # branch. Development commits on an unmerged branch may iterate;
    # only divergence from the merge-base (the last protected state)
    # is a violation. A same-identity semantic change (contract+pin
    # co-edit) keeps the head self-consistent but diverges from the
    # published law -> RED.
    try:
        shallow = _git(["rev-parse", "--is-shallow-repository"]).strip()
        if shallow == "true":
            violations.append("registry_history_unavailable_shallow_checkout")
            raise RuntimeError("shallow")
        base = _protected_base()
        if base is None:
            violations.append("registry_history_no_protected_base")
            raise RuntimeError("no-base")
        rel = str(REGISTRY_PATH.relative_to(REPO_ROOT))
        try:
            base_blob = _git(["show", f"{base}:{rel}"])
            base_registry = json.loads(base_blob)
            base_by_id = {
                entry.get("regime_id"): entry
                for entry in base_registry.get("regimes", [])
            }
        except (RuntimeError, ValueError):
            base_by_id = None
        if base_by_id is None:
            # First publication (absent from protected history): the
            # coherence arms above carry the proof; PR review carries
            # the publication.
            checks["registry_first_publication_coherent"] = True
        else:
            for regime_id, current_entry in sorted(by_id.items()):
                base_entry = base_by_id.get(regime_id)
                if base_entry is None:
                    continue  # new identity: legitimate evolution
                if str(base_entry.get("contract_digest")) != str(
                    current_entry.get("contract_digest")
                ):
                    violations.append(
                        "registry_published_digest_changed_under_same_identity"
                        f":{regime_id}"
                    )
            for regime_id in sorted(base_by_id):
                if regime_id not in by_id:
                    violations.append(
                        f"registry_published_identity_removed:{regime_id}"
                    )
            if not [v for v in violations if "registry_published_" in v]:
                checks["registry_history_single_valued"] = True
    except RuntimeError as exc:
        if "registry_history_unavailable" not in ";".join(violations):
            violations.append(f"registry_history_check_failed:{exc}")

    if args.dsn is not None:
        try:
            import psycopg2  # noqa: PLC0415

            conn = psycopg2.connect(args.dsn)
            conn.autocommit = True
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT contract_version, contract_digest,"
                        " activation_revision, status"
                        " FROM public.b26_p2_semantic_regime_registry"
                        " WHERE regime_id = %s",
                        (REGIME,),
                    )
                    row = cur.fetchone()
            finally:
                conn.close()
            if row is None:
                violations.append("registry_live_row_missing")
            elif (
                row[0] != entry.get("contract_version")
                or row[1] != live_digest
                or row[2] != entry.get("activation_revision")
                or row[3] != "active"
            ):
                violations.append("registry_live_row_diverges_from_file")
            else:
                checks["registry_live_row_matches"] = True
        except ImportError as exc:
            violations.append(f"registry_live_no_driver:{exc}")
        except Exception as exc:
            violations.append(f"registry_live_failed:{exc}")

    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XVIII_REGISTRY_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XVIII-REGISTRY",
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
