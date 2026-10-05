#!/usr/bin/env python3
"""B2.6-P2 Corrective XVIII contract-hierarchy coherence gate.

H-XVIII-R13/R14 (Directive XVIII, NC-09): provider/API contracts and
the P2 semantic contract have an explicit machine-governed
scope/projection relationship. A payload must not be simultaneously
"valid per the public provider contract" and "semantically invalid
per the sovereign reconciliation law" without a governed rule
explaining the difference, and no served route may claim P2 authority
outside the sovereign families.

Checks (all static):
- the hierarchy document declares ranks 1-4 with existing artifacts;
- every implemented webhook route is declared supported with a family
  inside the sovereign contract's supported families (no route
  masquerades as supported);
- every superseded_legacy/ingestion_rejected entry names a real
  artifact containing the divergent path (no phantom governance);
- the sovereign family law, the parser map, and the database atomic
  allowlist name the same canonical families (no drift between the
  three family authorities).

Exit code is the gate. Prints B26_P2_XVIII_HIERARCHY_PASS on success.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HIERARCHY_PATH = (
    REPO_ROOT
    / "contracts"
    / "reconciliation"
    / "b2.6"
    / "contract-hierarchy.v1.json"
)
SEMANTIC_CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "reconciliation"
    / "b2.6"
    / "provider-semantic-contract.v1.json"
)
FAMILY_LAW_PATH = (
    REPO_ROOT
    / "contracts"
    / "reconciliation"
    / "b2.6"
    / "event-family-law.v1.json"
)
RELAY_PATH = REPO_ROOT / "backend" / "app" / "api" / "webhooks.py"
DERIVATION_PATH = (
    REPO_ROOT / "backend" / "app" / "webhooks" / "commerce_derivation.py"
)
MIG_XVIII = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609300001_b26_p2_corrective_xviii_authority_conservation.py"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="XVIII hierarchy gate.")
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}

    try:
        hierarchy = json.loads(HIERARCHY_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        print("B26_P2_XVIII_HIERARCHY_FAIL")
        print(f"hierarchy_unreadable:{exc}")
        return 1
    ranks = {item.get("rank"): item for item in hierarchy.get("precedence", [])}
    if set(ranks) != {1, 2, 3, 4}:
        violations.append("hierarchy_precedence_not_four_ranks")
    else:
        for rank, item in sorted(ranks.items()):
            artifact = REPO_ROOT / str(item.get("artifact", ""))
            if "*" in str(item.get("artifact", "")):
                parent = REPO_ROOT / str(item["artifact"]).split("*")[0]
                if not parent.is_dir():
                    violations.append(f"hierarchy_rank_missing:{rank}")
            elif not artifact.is_file():
                violations.append(f"hierarchy_rank_missing:{rank}")
        if not [v for v in violations if "hierarchy_rank_missing" in v]:
            checks["hierarchy_ranks_present"] = True

    try:
        contract = json.loads(SEMANTIC_CONTRACT_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        violations.append(f"semantic_contract_unreadable:{exc}")
        contract = {"providers": {}}
    sovereign_families: dict[str, set[str]] = {}
    for provider, spec in contract.get("providers", {}).items():
        sovereign_families[provider] = {
            str(f).lower().replace("/", ".") for f in spec.get("supported_event_families", [])
        }

    relay_text = RELAY_PATH.read_text(encoding="utf-8")
    implemented = sorted(
        {match.group(1) for match in re.finditer(r'@router\.post\(\s*"([^"]+)"', relay_text)
         if match.group(1).startswith("/webhooks/")}
    )
    declared = {
        item["route"]: item
        for item in hierarchy.get("p2_supported_routes", [])
        if item.get("status") == "supported"
    }
    if set(implemented) != set(declared):
        violations.append(
            "route_authority_mismatch:implemented="
            f"{sorted(set(implemented) - set(declared))}:declared_unimplemented="
            f"{sorted(set(declared) - set(implemented))}"
        )
    else:
        checks["routes_declared_supported"] = True
    for route, item in sorted(declared.items()):
        provider = str(item.get("provider", ""))
        family = str(item.get("p2_event_family", "")).lower().replace("/", ".")
        if family not in sovereign_families.get(provider, set()):
            violations.append(f"route_family_outside_sovereign_law:{route}")
    if not [v for v in violations if "route_family_outside_sovereign_law" in v]:
        checks["route_families_sovereign"] = True

    for item in hierarchy.get("superseded_legacy_entries", []):
        artifact = REPO_ROOT / str(item.get("artifact", ""))
        if not artifact.is_file():
            violations.append(f"superseded_artifact_missing:{item.get('artifact')}")
            continue
        needle = str(item.get("path", ""))
        content = artifact.read_text(encoding="utf-8")
        if needle not in content and needle.split(" ")[0] not in content:
            violations.append(f"superseded_entry_not_found:{needle[:60]}")
        if item.get("status") not in (
            "superseded_legacy",
            "ingestion_rejected_by_sovereign_law",
        ):
            violations.append(f"superseded_status_ungoverned:{needle[:60]}")
    if not [v for v in violations if "superseded_" in v]:
        checks["divergences_explicitly_governed"] = True

    try:
        family_law = json.loads(FAMILY_LAW_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        violations.append(f"family_law_unreadable:{exc}")
        family_law = {"families": {}}
    law_canonical = {
        provider: str(spec.get("canonical_family", ""))
        for provider, spec in family_law.get("families", {}).items()
    }
    derivation_text = DERIVATION_PATH.read_text(encoding="utf-8")
    for provider, canonical in sorted(law_canonical.items()):
        if f'"{provider}": "{canonical}"' not in derivation_text:
            violations.append(f"parser_family_map_diverges:{provider}")
    if not [v for v in violations if "parser_family_map_diverges" in v]:
        checks["parser_family_map_matches_law"] = True
    try:
        mig_text = MIG_XVIII.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xviii_migration_unreadable:{exc}")
        mig_text = ""
    for provider, canonical in sorted(law_canonical.items()):
        if canonical not in mig_text:
            violations.append(f"database_family_allowlist_diverges:{provider}")
    if not [v for v in violations if "database_family_allowlist_diverges" in v]:
        checks["database_family_allowlist_matches_law"] = True
    for provider, canonical in sorted(law_canonical.items()):
        if canonical not in sovereign_families.get(provider, set()) and canonical.lower().replace("/", ".") not in sovereign_families.get(provider, set()):
            violations.append(f"family_law_outside_semantic_contract:{provider}")
    if not [v for v in violations if "family_law_outside_semantic_contract" in v]:
        checks["family_law_within_semantic_contract"] = True

    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XVIII_HIERARCHY_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XVIII-HIERARCHY",
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
