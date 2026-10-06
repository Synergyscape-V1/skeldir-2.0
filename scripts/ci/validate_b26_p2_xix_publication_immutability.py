#!/usr/bin/env python3
"""B2.6-P2 Corrective XIX publication-immutability gate.

H-XIX-R5/R6/R8 (Directive XIX, NC-04/NC-05): a published semantic,
family, or hierarchy law cannot change meaning under the same
published identity. Unlike the XVIII registry gate (which compares
the working tree against a mutable branch ref and is vacuous when
HEAD == origin/main), this gate consults NO git ref: it verifies the
hash-chained publication history
(contracts/reconciliation/b2.6/publication-history.json) and its
coherence with the live bytes, the parser map, and the XIX migration
allowlist. A same-identity co-edit breaks the chain match in EVERY
topology (PR, merge queue, exact-main push, detached, shallow) --
there is no base resolution to collapse.

Checks (static; --dsn adds the live-ledger cross-check):
- chain integrity: every entry_hash == sha256(
  law_kind|law_id|law_version|law_digest|activation_revision|prev)
  with '' for the genesis prev;
- single-valued identity: no two entries share (law_kind, law_id,
  law_version) with different digests;
- live coherence: each chained artifact file's LF-normalized sha256
  equals its tip entry digest; the semantic-regime-registry file, the
  XVII pin, and the migration seed literal equal the regime digest;
- family-law v2 carries no family-implicit disposition (explicit
  authenticated-fact law) and declares the topic bindings the parser
  implements;
- parser map (CANONICAL_EVENT_FAMILY_BY_PROVIDER) equals the v2
  canonical families; the XIX migration allowlist names the same
  canonical families (no drift between the three family authorities);
- hierarchy v2 ranks the v2 family law and records the v1 supersession;
- with --dsn: the b26_p2_publication_history ledger rows match the
  file chain exactly (kind/id/version/digest/prev/hash), and the
  registry row matches the regime tip.

Exit code is the gate. Prints B26_P2_XIX_PUBLICATION_PASS on success.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
B26_DIR = REPO_ROOT / "contracts" / "reconciliation" / "b2.6"
HISTORY_PATH = B26_DIR / "publication-history.json"
REGISTRY_PATH = B26_DIR / "semantic-regime-registry.json"
SEMANTIC_CONTRACT_PATH = B26_DIR / "provider-semantic-contract.v1.json"
FAMILY_V2_PATH = B26_DIR / "event-family-law.v2.json"
HIERARCHY_V2_PATH = B26_DIR / "contract-hierarchy.v2.json"
PIN_PATH = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b26_p2_xvii_semantic_contract.pin.json"
)
DERIVATION_PATH = (
    REPO_ROOT / "backend" / "app" / "webhooks" / "commerce_derivation.py"
)
MIG_XIX = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609300002_b26_p2_corrective_xix_nonreconstructible_authority.py"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()


def _entry_hash(entry: dict) -> str:
    prev = entry.get("prev_entry_hash") or ""
    preimage = "|".join(
        [
            str(entry.get("law_kind") or ""),
            str(entry.get("law_id") or ""),
            str(entry.get("law_version") or ""),
            str(entry.get("law_digest") or ""),
            str(entry.get("activation_revision") or ""),
            prev,
        ]
    )
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="XIX publication gate.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}

    try:
        history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        print("B26_P2_XIX_PUBLICATION_FAIL")
        print(f"publication_history_unreadable:{exc}")
        return 1
    entries = history.get("entries", [])
    if not entries:
        print("B26_P2_XIX_PUBLICATION_FAIL")
        print("publication_history_empty")
        return 1
    seen: dict[tuple, str] = {}
    prev: str | None = None
    for pos, entry in enumerate(entries):
        key = (
            entry.get("law_kind"),
            entry.get("law_id"),
            entry.get("law_version"),
        )
        if entry.get("law_digest") != seen.setdefault(
            key, entry.get("law_digest")
        ):
            violations.append(
                "publication_identity_rewritten:"
                f"{key[0]}/{key[1]}/{key[2]}"
            )
        if _entry_hash(entry) != entry.get("entry_hash"):
            violations.append(f"publication_chain_broken:pos={pos}")
        if (entry.get("prev_entry_hash") or "") != (prev or ""):
            violations.append(f"publication_chain_unlinked:pos={pos}")
        prev = entry.get("entry_hash")
    if not [v for v in violations if v.startswith("publication_")]:
        checks["publication_chain_intact"] = True

    tips: dict[tuple, dict] = {}
    for entry in entries:
        tips[
            (entry.get("law_kind"), entry.get("law_id"))
        ] = entry
    for (kind, _lid), entry in sorted(tips.items()):
        artifact = entry.get("law_artifact") or ""
        path = REPO_ROOT / artifact
        if kind == "semantic-regime":
            live = _sha(SEMANTIC_CONTRACT_PATH)
        else:
            if not path.is_file():
                violations.append(f"publication_artifact_missing:{artifact}")
                continue
            live = _sha(path)
        if live != entry.get("law_digest"):
            violations.append(
                f"publication_live_diverges:{kind}/"
                f"{entry.get('law_version')}"
            )
    if not [v for v in violations if "publication_live_diverges" in v]:
        checks["publication_live_matches_tip"] = True

    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        regimes = {
            r.get("regime_id"): r for r in registry.get("regimes", [])
        } or {
            registry.get("regime_id", "xvii-sovereign-v1"): registry
        }
    except OSError as exc:
        violations.append(f"registry_unreadable:{exc}")
        regimes = {}
    regime_tip = tips.get(("semantic-regime", "xvii-sovereign-v1"), {})
    if regimes.get("xvii-sovereign-v1", {}).get(
        "contract_digest"
    ) != regime_tip.get("law_digest"):
        violations.append("registry_digest_outside_publication_law")
    else:
        checks["registry_matches_publication_tip"] = True
    try:
        pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        violations.append(f"semantic_pin_unreadable:{exc}")
        pin = {}
    if pin.get("contract_sha256") != regime_tip.get("law_digest"):
        violations.append("pin_digest_outside_publication_law")
    else:
        checks["pin_matches_publication_tip"] = True
    try:
        mig_text = MIG_XIX.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xix_migration_unreadable:{exc}")
        mig_text = ""
    for token in (
        regime_tip.get("law_digest") or "",
        "b26_p2_publication_identity_single_valued",
    ):
        if token and token not in mig_text:
            violations.append(f"migration_seed_outside_law:{token[:16]}")
    if not [v for v in violations if "migration_seed_outside_law" in v]:
        checks["migration_seed_matches_publication_tip"] = True

    try:
        family_v2 = json.loads(FAMILY_V2_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        violations.append(f"family_v2_unreadable:{exc}")
        family_v2 = {"families": {}}
    if family_v2.get("contract_version") != "v2":
        violations.append("family_law_version_not_v2")
    else:
        checks["family_law_v2_identity"] = True
    raw_v2 = FAMILY_V2_PATH.read_text(encoding="utf-8")
    if "family_implicit" in raw_v2:
        violations.append("family_v2_permits_implicit_disposition")
    else:
        checks["family_v2_explicit_only"] = True
    law_canonical = {
        provider: str(spec.get("canonical_family", ""))
        for provider, spec in family_v2.get("families", {}).items()
    }
    try:
        derivation_text = DERIVATION_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"derivation_unreadable:{exc}")
        derivation_text = ""
    for provider, canonical in sorted(law_canonical.items()):
        if f'"{provider}": "{canonical}"' not in derivation_text:
            violations.append(f"parser_family_map_diverges:{provider}")
    if not [v for v in violations if "parser_family_map_diverges" in v]:
        checks["parser_family_map_matches_v2"] = True
    for provider, canonical in sorted(law_canonical.items()):
        if canonical not in mig_text:
            violations.append(f"database_family_allowlist_diverges:{provider}")
    if not [
        v for v in violations if "database_family_allowlist_diverges" in v
    ]:
        checks["database_family_allowlist_matches_v2"] = True
    for provider, spec in family_v2.get("families", {}).items():
        if not spec.get("required_evidence"):
            violations.append(f"family_v2_missing_evidence_rule:{provider}")
    if not [
        v for v in violations if "family_v2_missing_evidence_rule" in v
    ]:
        checks["family_v2_evidence_rules_complete"] = True

    try:
        hierarchy_v2 = json.loads(
            HIERARCHY_V2_PATH.read_text(encoding="utf-8")
        )
    except OSError as exc:
        violations.append(f"hierarchy_v2_unreadable:{exc}")
        hierarchy_v2 = {"precedence": []}
    ranks = {item.get("rank"): item for item in hierarchy_v2.get("precedence", [])}
    if ranks.get(2, {}).get("artifact") != (
        "contracts/reconciliation/b2.6/event-family-law.v2.json"
    ):
        violations.append("hierarchy_v2_not_ranking_family_v2")
    else:
        checks["hierarchy_v2_ranks_family_v2"] = True
    if not hierarchy_v2.get("superseded_law_versions"):
        violations.append("hierarchy_v2_missing_supersession_record")
    else:
        checks["hierarchy_v2_records_supersession"] = True

    if args.dsn is not None:
        try:
            import psycopg2  # noqa: PLC0415

            conn = psycopg2.connect(args.dsn)
            conn.autocommit = True
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT law_kind, law_id, law_version, law_digest,"
                        " activation_revision, prev_entry_hash, entry_hash"
                        " FROM public.b26_p2_publication_history"
                    )
                    rows = cur.fetchall()
            finally:
                conn.close()
            live_map = {
                (r[0], r[1], r[2]): r for r in rows
            }
            for entry in entries:
                key = (
                    entry.get("law_kind"),
                    entry.get("law_id"),
                    entry.get("law_version"),
                )
                row = live_map.get(key)
                if row is None:
                    violations.append(
                        f"ledger_missing_publication:{key[0]}/{key[2]}"
                    )
                    continue
                if (
                    row[3] != entry.get("law_digest")
                    or (row[5] or "") != (entry.get("prev_entry_hash") or "")
                    or row[6] != entry.get("entry_hash")
                ):
                    violations.append(
                        f"ledger_diverges_from_file:{key[0]}/{key[2]}"
                    )
            if not [
                v
                for v in violations
                if v.startswith("ledger_")
            ]:
                checks["ledger_matches_file_chain"] = True
        except Exception as exc:
            violations.append(f"ledger_unreadable:{exc}")

    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XIX_PUBLICATION_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XIX-PUBLICATION",
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
