#!/usr/bin/env python3
"""B2.6-P2 Corrective X two-phase change-law check.

When a change modifies a load-bearing semantic contract or the
verifier that judges it, the same change must not both introduce the
new rule and use the new rule as its sole evidence of correctness.
This check enforces the accompanying-representation half in CI:

- protected history must resolve (merge-base with origin/main);
  otherwise RED (no candidate-carried history).
- the scope policy and the frozen pure-Python law library must be
  byte-identical to base (X changes no governed meaning; evolution
  uses version bumps, judged elsewhere).
- every truth-file change must be accompanied by regenerated
  representations (pins/manifests/schema/authority companion).
- behavioral proof (oracle, canaries, proof-plane battery, guards)
  is adjudicated by its own gates, never by this script.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FROZEN_FILES = (
    "contracts/reconciliation/b2.6/scope-policy.v2.yaml",
    "contracts/reconciliation/b2.6/scope-policy.v1.yaml",
    "backend/app/finance_reconciliation/scope_authority.py",
)

TRUTH_COMPANIONS = {
    "backend/app/finance_reconciliation/candidate_conduction.py": (
        "contracts-internal/governance/b26_p2_semantic_universe.pin.json",
        "contracts-internal/governance/b26_p2_x_semantic_universe.pin.json",
    ),
    "alembic/versions/007_skeldir_foundation/202609240001_b26_p2_corrective_x_assurance_sovereignty.py": (
        "contracts-internal/governance/b26_p2_authority_universe.pin.json",
        "db/schema/canonical_schema.sql",
        "db/schema/canonical_authority.sql",
    ),
    "alembic/versions/007_skeldir_foundation/202609240002_b26_p2_corrective_xi_p2_core_closure.py": (
        "contracts-internal/governance/b26_p2_authority_universe.pin.json",
        "contracts-internal/governance/b26_p2_xi_semantic_dependency_manifest.json",
        "db/schema/canonical_schema.sql",
        "db/schema/canonical_authority.sql",
    ),
    "alembic/versions/007_skeldir_foundation/202609250001_b26_p2_corrective_xii_fact_anchored_closure.py": (
        "contracts-internal/governance/b26_p2_authority_universe.pin.json",
        "contracts-internal/governance/b26_p2_xii_semantic_dependency_manifest.json",
        "db/schema/canonical_schema.sql",
        "db/schema/canonical_authority.sql",
    ),
    "alembic/versions/007_skeldir_foundation/202609260001_b26_p2_corrective_xiii_root_of_trust_closure.py": (
        "contracts-internal/governance/b26_p2_authority_universe.pin.json",
        "contracts-internal/governance/b26_p2_xiii_semantic_contract.v1.json",
        "db/schema/canonical_schema.sql",
        "db/schema/canonical_authority.sql",
    ),
    "alembic/versions/007_skeldir_foundation/202609270001_b26_p2_corrective_xiv_compositional_closure.py": (
        "contracts-internal/governance/b26_p2_authority_universe.pin.json",
        "contracts-internal/governance/b26_p2_xiii_semantic_contract.v1.json",
        "db/schema/canonical_schema.sql",
        "db/schema/canonical_authority.sql",
    ),
    "alembic/versions/007_skeldir_foundation/202609270002_b26_p2_corrective_xiv_temporal_enforcement.py": (
        "contracts-internal/governance/b26_p2_authority_universe.pin.json",
        "contracts-internal/governance/b26_p2_xiii_semantic_contract.v1.json",
        "db/schema/canonical_schema.sql",
        "db/schema/canonical_authority.sql",
    ),
    "alembic/versions/007_skeldir_foundation/202609270003_b26_p2_corrective_xiv_definer_evidence.py": (
        "contracts-internal/governance/b26_p2_authority_universe.pin.json",
        "contracts-internal/governance/b26_p2_xiii_semantic_contract.v1.json",
        "db/schema/canonical_schema.sql",
        "db/schema/canonical_authority.sql",
    ),
    "alembic/versions/007_skeldir_foundation/202609280001_b26_p2_corrective_xv_binding_closure.py": (
        "contracts-internal/governance/b26_p2_authority_universe.pin.json",
        "contracts-internal/governance/b26_p2_xiii_semantic_contract.v1.json",
        "db/schema/canonical_schema.sql",
        "db/schema/canonical_authority.sql",
    ),
    "alembic/versions/007_skeldir_foundation/202609280002_b26_p2_corrective_xvi_sovereign_closure.py": (
        "contracts-internal/governance/b26_p2_authority_universe.pin.json",
        "contracts-internal/governance/b26_p2_xiii_semantic_contract.v1.json",
        "db/schema/canonical_schema.sql",
        "db/schema/canonical_authority.sql",
    ),
    "alembic/versions/007_skeldir_foundation/202609290001_b26_p2_corrective_xvii_historical_reconciliation.py": (
        "contracts-internal/governance/b26_p2_authority_universe.pin.json",
        "db/schema/canonical_schema.sql",
        "db/schema/canonical_authority.sql",
    ),
}


def _companion_acknowledges_live_state(
    companion: str, violations: list[str], checks: dict
) -> bool:
    """Prove an unchanged companion still describes live state.

    Currently implemented for the X semantic universe pin: re-derive
    the module universe, B2.3 footprint, trigger columns, and dynamic
    forms from the live tree and require exact equality with the
    pinned content. A truth change that leaves every derived
    representation identical (e.g. an authority overlay that adds no
    modules, columns, or dynamic forms) keeps its companion honestly.
    Any derivation gap returns False (companion must be regenerated).
    """
    if companion != (
        "contracts-internal/governance/b26_p2_x_semantic_universe.pin.json"
    ):
        return False
    try:
        import importlib.util as _ilu

        spec = _ilu.spec_from_file_location(
            "b26_p2_x_semantic_live",
            str(
                REPO_ROOT
                / "scripts"
                / "ci"
                / "validate_b26_p2_x_semantic.py"
            ),
        )
        if spec is None or spec.loader is None:
            return False
        module = _ilu.module_from_spec(spec)
        sys.modules["b26_p2_x_semantic_live"] = module
        spec.loader.exec_module(module)
        pin = json.loads(
            (REPO_ROOT / companion).read_text(encoding="utf-8")
        )
        live_modules = module._derive()
        acknowledged = (
            sorted(live_modules["modules"]) == sorted(pin.get("modules", []))
            and sorted(live_modules["b23_footprint"])
            == sorted(pin.get("b23_footprint", []))
            and sorted(live_modules["trigger_columns"])
            == sorted(pin.get("trigger_columns", []))
            and {
                key: sorted(value)
                for key, value in live_modules["dynamic_forms"].items()
            }
            == {
                key: sorted(value)
                for key, value in pin.get("dynamic_forms", {}).items()
            }
        )
        checks["companion_live_acknowledged"] = bool(acknowledged)
        return bool(acknowledged)
    except Exception:  # noqa: BLE001
        return False


def _git(args: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO_ROOT),
        )
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return proc.returncode, (proc.stdout or "").strip()


def _module_ast_sha256(path: Path) -> str:
    return hashlib.sha256(
        ast.dump(
            ast.parse(path.read_text(encoding="utf-8")),
            include_attributes=False,
        ).encode("utf-8")
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check B2.6-P2 Corrective X two-phase change law."
    )
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict[str, object] = {}
    try:
        rc, base = _git(["merge-base", "HEAD", "origin/main"])
        if rc != 0 or not base:
            violations.append("x_two_phase_history_unavailable")
            checks["base_resolution"] = "unavailable_no_merge_base"
        else:
            checks["base_resolution"] = f"merge-base:{base[:12]}"
            # Working-tree diff (in CI the checkout is clean, so this
            # equals the committed candidate diff; locally it also
            # covers uncommitted work). Untracked files are included:
            # a new companion pin/migration is a change too.
            rc, out = _git(["diff", "--name-only", base])
            if rc != 0:
                violations.append("x_two_phase_diff_failed")
                changed = set()
            else:
                changed = {line.strip() for line in out.splitlines() if line.strip()}
            rc2, out2 = _git(["status", "--porcelain"])
            if rc2 == 0:
                for line in out2.splitlines():
                    if len(line) < 4:
                        continue
                    code = line[:2]
                    name = line[3:].strip().strip('"')
                    if code[0] in ("?", "A", "M") and name:
                        changed.add(name)
            checks["files_changed"] = sorted(changed)
            for frozen in FROZEN_FILES:
                if frozen in changed:
                    violations.append(f"x_two_phase_frozen_changed:{frozen}")
            for truth, companions in TRUTH_COMPANIONS.items():
                if truth not in changed:
                    continue
                for companion in companions:
                    if companion not in changed:
                        # Companion may predate this change only if it
                        # already acknowledges the live tree state
                        # (verified, not assumed).
                        if _companion_acknowledges_live_state(
                            companion, violations, checks
                        ):
                            continue
                        violations.append(
                            f"x_two_phase_companion_missing:{truth}" f"->{companion}"
                        )
            # Semantic pin must acknowledge the live adapter bytes.
            pin_path = (
                REPO_ROOT
                / "contracts-internal"
                / "governance"
                / "b26_p2_semantic_universe.pin.json"
            )
            conduction = (
                REPO_ROOT
                / "backend"
                / "app"
                / "finance_reconciliation"
                / "candidate_conduction.py"
            )
            if pin_path.is_file() and conduction.is_file():
                try:
                    pin = json.loads(pin_path.read_text(encoding="utf-8"))
                    live = _module_ast_sha256(conduction)
                    checks["adapter_ast_live"] = live
                    checks["adapter_ast_pinned"] = pin.get(
                        "candidate_conduction_ast_sha256"
                    )
                    if pin.get("candidate_conduction_ast_sha256") != live:
                        violations.append("x_two_phase_adapter_pin_stale")
                except (OSError, ValueError, SyntaxError) as exc:
                    violations.append(f"x_two_phase_pin_unreadable:{exc}")
            # Authority pin must name the X head.
            authority_pin = (
                REPO_ROOT
                / "contracts-internal"
                / "governance"
                / "b26_p2_authority_universe.pin.json"
            )
            if authority_pin.is_file():
                try:
                    apin = json.loads(authority_pin.read_text(encoding="utf-8"))
                    checks["authority_pin_head"] = apin.get("migration_head")
                    if apin.get("migration_head") not in (
                        "202609240002",
                        "202609250001",
                        "202609260001",
                        "202609270001",
                        "202609270002",
                        "202609270003",
                        "202609280001",
                        "202609280002",
                        "202609290001",
                        "202609300001",
                        "202609300002",
                        "202609300003",
                    ):
                        violations.append("x_two_phase_authority_pin_stale")
                except (OSError, ValueError) as exc:
                    violations.append(f"x_two_phase_authority_pin_unreadable:{exc}")
            # Schema companion must carry the X objects.
            schema = REPO_ROOT / "db" / "schema" / "canonical_schema.sql"
            if schema.is_file():
                try:
                    text = schema.read_text(encoding="utf-8")
                    checks["schema_has_classifier"] = (
                        "b26_p2_classify_candidate" in text
                    )
                    checks["schema_has_evidence"] = "b26_p2_provenance_evidence" in text
                    checks["schema_has_guards"] = (
                        "b26_p2_guard_conducted_transition" in text
                    )
                    checks["schema_has_witness"] = (
                        "b26_p2_ingress_auth_witness" in text
                        and "b26_p2_record_ingress_auth_witness" in text
                        and "b26_p2_state_eligible_for_p3" in text
                    )
                    if not (
                        checks["schema_has_classifier"]
                        and checks["schema_has_evidence"]
                        and checks["schema_has_guards"]
                        and checks["schema_has_witness"]
                    ):
                        violations.append("x_two_phase_schema_missing_x")
                except OSError as exc:
                    violations.append(f"x_two_phase_schema_unreadable:{exc}")
    except Exception as exc:  # noqa: BLE001
        violations.append(f"x_two_phase_validator_crash:{exc}")
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-X-TWO-PHASE",
        "validator": "check_b26_p2_x_two_phase",
        "status": status,
        "violations": sorted(violations),
        "checks": checks,
    }
    if args.evidence_out is not None:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    if args.evidence_dir is not None:
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        (args.evidence_dir / "x-two-phase.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_X_TWO_PHASE_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_X_TWO_PHASE_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
