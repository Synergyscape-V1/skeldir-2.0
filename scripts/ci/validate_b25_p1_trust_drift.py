#!/usr/bin/env python3
"""Block unauthorized B2.5 runtime TrustEnvelope model drift.

B2.5-P1 was contract authority only. Later B2.5 subphases authorize narrow
pure trust modules, but still do not authorize generated or hand-written
runtime TrustEnvelope models, routes, signers, or schema drift outside the
phase allowlist below.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

PROTECTED_PATH_PATTERNS = (
    "backend/**/trust*.py",
    "backend/**/trust_envelope*.py",
    "backend/**/schemas/*trust*.py",
    "backend/**/schemas/*envelope*.py",
    "backend/**/models/*trust*.py",
    "backend/**/models/*envelope*.py",
)

PYDANTIC_TRUST_MODEL_PATTERNS = (
    re.compile(r"(?m)^class\s+TrustEnvelope\b.*\bBaseModel\b"),
    re.compile(r"(?m)^class\s+\w*Trust\w*Envelope\w*\b.*\bBaseModel\b"),
    re.compile(r"(?m)^class\s+\w*Envelope\w*\b.*\bBaseModel\b"),
)

ALLOWED_NON_RUNTIME_PATHS = (
    "backend/app/bayesian/snapshot_supersession.py",
    "backend/app/trust/__init__.py",
    "backend/app/trust/array_ordering.py",
    "backend/app/trust/audit.py",
    "backend/app/trust/audit_hash.py",
    "backend/app/trust/canonicalization.py",
    "backend/app/trust/hash_domains.py",
    "backend/app/trust/hash_identity.py",
    "backend/app/trust/money_authority_registry.py",
    "backend/app/trust/money_source_adapter.py",
    "backend/app/trust/benchmark_defaults.py",
    "backend/app/trust/builder.py",
    "backend/app/trust/opaque_reference.py",
    "backend/app/trust/policy_defaults.py",
    "backend/app/trust/provenance.py",
    "backend/app/trust/reason_codes.py",
    "backend/app/trust/reason_truth_matrix.py",
    "backend/app/trust/refusal.py",
    "backend/app/trust/schema_versions.py",
    "backend/app/trust/schema_verification.py",
    "backend/app/trust/key_registry.py",
    "backend/app/trust/signing.py",
    "backend/app/trust/semantic_authority.py",
    "backend/app/trust/verification.py",
    "backend/app/trust/jwks.py",
    "backend/app/trust/source_adapters.py",
    "backend/app/trust/subject_authority.py",
    "backend/app/trust/text_disposition.py",
    "backend/app/trust/text_safety_registry.py",
    "backend/app/api/trust_keys.py",
    "backend/tests/trust/test_b25_p2_array_ordering.py",
    "backend/tests/trust/test_b25_p2_canonicalization.py",
    "backend/tests/trust/test_b25_p2_hash_identity.py",
    "backend/tests/trust/test_b25_p2_manifest_coverage.py",
    "backend/tests/trust/test_b25_p2_schema_versions.py",
    "backend/tests/trust/test_b25_p2_serializer_boundaries.py",
    "backend/tests/trust/test_b25_p3_text_disposition.py",
    "backend/tests/trust/test_b25_p4_money_authority.py",
    "backend/tests/trust/test_b25_p5_builder.py",
    "backend/tests/trust/test_b25_p6_reason_truth_matrix.py",
    "backend/tests/trust/test_b25_p7_provenance_audit.py",
    "backend/tests/trust/test_b25_p8_signing_verification.py",
    "backend/app/trust/machine_identity.py",
    "backend/app/trust/machine_auth.py",
    "backend/app/trust/runtime_keys.py",
    "backend/app/trust/tenant_security.py",
    "backend/app/trust/query_continuation.py",
    "backend/app/api/trust_api.py",
    "backend/app/api/trust_export.py",
    "backend/app/trust/export_artifact.py",
    "backend/app/trust/export_projection.py",
    "backend/app/trust/spreadsheet_safety.py",
    "backend/app/config/contract_scope.yaml",
    "backend/app/main.py",
    "backend/tests/trust/test_b25_p9_machine_identity.py",
    "backend/tests/trust/test_b25_p10_trust_api_surface.py",
    "backend/tests/trust/test_b25_p10_corrective_action.py",
    "backend/tests/trust/test_b25_p10_corrective_action_ii.py",
    "backend/tests/trust/test_b25_p10_postgres_physics.py",
    "backend/tests/trust/test_b25_p11_error_provenance.py",
    "backend/tests/trust/test_b25_p11_export_artifact.py",
    "backend/tests/trust/test_b25_p11_export_projection.py",
    "backend/tests/trust/test_b25_p11_postgres_physics.py",
    "backend/tests/trust/test_b25_p13_e2e_trust_closure.py",
    "backend/tests/trust/test_b25_p13_c6_postgres_physics.py",
    "backend/tests/trust/test_b25_p13_c7_conservation_physics.py",
    "backend/tests/trust/test_b25_p13_c8_identity_window_physics.py",
    "backend/tests/trust/test_b25_p13_c8_transport_physics.py",
    "backend/tests/trust/test_b25_p13_c8_contiguous_journey.py",
    "backend/tests/trust/test_b25_p13_c9_feature_cardinality_physics.py",
    "backend/tests/trust/test_b25_p13_c9_tenant_containment.py",
    "backend/tests/trust/test_b25_p13_c9_degradation_matrix.py",
    "backend/tests/trust/test_b25_p13_c9_authority_supersession.py",
    "backend/tests/trust/test_b25_p13_c9_positive_confidence.py",
    "backend/tests/trust/test_b25_p13_c10_policy_transport_physics.py",
    "backend/tests/trust/test_b25_p13_c11_semantic_authority.py",
    "backend/tests/trust/test_b25_p13_c12_authority_closure.py",
    "backend/tests/trust/test_b25_p13_c13_signing_truth_boundary.py",
    "backend/tests/trust/test_b25_p13_c14_semantic_authority.py",
    # B2.5-P13 Corrective XV: the issuance-authority ledger and its
    # falsifiers. Declared here for the same reason as the C14 surface --
    # they are post-P1 trust closure, not P1 runtime drift.
    "backend/app/trust/issuance_authority_ledger.py",
    "backend/tests/trust/test_b25_p13_c15_issuance_truth.py",
    # B2.5-P13 Corrective XVI: the issuance-consequence database custody
    # boundary and its falsifiers. Same reason again -- these are post-P1
    # trust closure surfaces, not P1 runtime drift.
    "backend/app/trust/issuance_session.py",
    "backend/tests/trust/test_b25_p13_c16_bidirectional_issuance_truth.py",
    # Corrective XVII: signer consequence custody, the credential-isolated
    # signer service and its public-API client, durable signing authority, and
    # reconstructable attempt lineage are all post-P1 trust closure surfaces.
    "backend/app/trust/signer_session.py",
    "backend/app/trust/signer_service.py",
    "backend/app/trust/signer_gateway.py",
    "backend/app/trust/signing_authorization.py",
    "backend/app/trust/signing_consequence.py",
    "backend/app/trust/consequence_verification.py",
    "backend/tests/trust/test_b25_p13_c17_consequence_lineage.py",
    # Corrective XIX: the context-robust production-topology observer and the
    # legitimate-source physics falsifiers are post-P1 trust closure surfaces
    # like their C15-C17 predecessors, not P1 runtime drift.
    "backend/tests/trust/test_b25_p13_c19_context_robust_topology.py",
    "backend/tests/trust/test_b25_p13_c19_legitimate_source_physics.py",
    # Corrective XX: the verdict-authority conservation proof lives beside the
    # C19 observer for the same reason -- it adjudicates who may assert B2.3
    # truth on a real role graph, which is post-P1 closure, not P1 runtime.
    "backend/tests/trust/test_b25_p13_c20_runtime_authority.py",
    # Corrective XXI: B2.4 freshness-authority conservation and durable
    # issuance-history immutability, proved on the same real role graph. Same
    # classification as its C19/C20 neighbours -- post-P1 closure physics.
    "backend/tests/trust/test_b25_p13_c21_freshness_issuance_authority.py",
    # B2.5-P14: the downstream projection boundary. These are the opposite of
    # P1 runtime drift -- they are pure, read-only *consumers* of an already
    # signed envelope, and neither constructs, models nor mutates one. The
    # profile registry is a contract file; `projection.py` copies allowlisted
    # source values and never re-derives any of them.
    "backend/app/trust/projection.py",
    "backend/app/trust/projection_profiles.py",
    "backend/tests/trust/test_b25_p14_projection_contract_floor.py",
    "backend/tests/trust/test_b25_p14_b27_explanation_conservation.py",
    "backend/tests/trust/test_b25_p14_b28_simulation_conservation.py",
    "backend/tests/trust/test_b25_p14_gate0_issuance_consequence_authority.py",
    # B2.5-P14 Corrective IV: terminal-provenance conservation and downstream
    # consequence binding. Same classification as their P14 neighbours. The
    # terminal-provenance proof never touches an envelope at all -- it drives
    # the audit ledger's own state machine. The downstream-consequence proof
    # signs one envelope with a key it generates at test time so the journey it
    # measures is a real cryptographic consequence rather than a fixture, but it
    # does so through the P5/P8 signing path itself and models nothing: the
    # payload is a shipped contract example, and every field the proof reads
    # back comes out of PostgreSQL.
    "backend/tests/trust/test_b25_p14_r4_terminal_provenance.py",
    "backend/tests/trust/test_b25_p14_r4_downstream_consequence.py",
    # B2.5-P14 Corrective V: genuine B2.8 request intent and solver consequence.
    # Same classification, and for the same reason. The causal-authority proof
    # reuses the Corrective IV signing helper -- one envelope, signed at test
    # time through the P5/P8 path with a key generated there -- so the journey
    # it measures is a real cryptographic consequence rather than a fixture; it
    # models no envelope of its own, and every field it adjudicates is read back
    # out of PostgreSQL. The construction-authority proof touches no envelope at
    # all: its subject is which database constructions may back a production
    # process.
    "backend/tests/trust/test_b25_p14_r5_causal_authority.py",
    "backend/tests/trust/test_b25_p14_r5_construction_authority.py",
    # B2.5-P14 Corrective VI: proven request possession, honest solver
    # semantics, pinned schema compatibility. Same classification again. The
    # possession proof reuses the Corrective IV signing helper for its source
    # Trust -- one envelope, signed at test time through the P5/P8 path -- and
    # models nothing of its own; its subjects are a database possession witness,
    # a column-comment taxonomy and a revision-compatibility predicate, none of
    # which is an envelope surface.
    "backend/tests/trust/test_b25_p14_r6_possession_authority.py",
)


@dataclass(frozen=True)
class DriftViolation:
    path: str
    reason: str


def _norm(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def _is_allowed(path: str) -> bool:
    return path in ALLOWED_NON_RUNTIME_PATHS


def _matches_protected_path(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in PROTECTED_PATH_PATTERNS)


def inspect_file(path: str, text: str) -> list[DriftViolation]:
    if _is_allowed(path):
        return []
    violations: list[DriftViolation] = []
    if _matches_protected_path(path):
        violations.append(
            DriftViolation(
                path, "backend TrustEnvelope/trust model path is forbidden in B2.5-P1"
            )
        )
    lowered = text.lower()
    if "trustenvelope" in lowered or "trust envelope" in lowered:
        for pattern in PYDANTIC_TRUST_MODEL_PATTERNS:
            if pattern.search(text):
                violations.append(
                    DriftViolation(
                        path,
                        "hand-written Pydantic TrustEnvelope model is forbidden in B2.5-P1",
                    )
                )
                break
    return violations


def scan_tree() -> list[DriftViolation]:
    violations: list[DriftViolation] = []
    for path in (ROOT / "backend").rglob("*.py"):
        rel = _norm(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8", errors="replace")
        violations.extend(inspect_file(rel, text))
    return violations


def run_negative_controls() -> int:
    controls = {
        "backend/app/schemas/trust.py": "from pydantic import BaseModel\nclass TrustEnvelope(BaseModel):\n    pass\n",
        "backend/app/schemas/trust_envelope.py": "from pydantic import BaseModel\nclass TrustEnvelope(BaseModel):\n    pass\n",
        "backend/app/models/trust_runtime.py": "from pydantic import BaseModel\nclass RuntimeTrustEnvelope(BaseModel):\n    pass\n",
        "backend/app/models/payment_envelope.py": "from pydantic import BaseModel\nclass TrustEnvelope(BaseModel):\n    pass\n",
    }
    passed = 0
    for path, text in controls.items():
        violations = inspect_file(path, text)
        if not violations:
            raise RuntimeError(f"negative control did not fail: {path}")
        passed += 1
    return passed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()

    try:
        violations = scan_tree()
        if violations:
            for violation in violations:
                print(
                    f"B25_P1_TRUST_DRIFT_VIOLATION {violation.path}: {violation.reason}"
                )
            return 1
        print("B25_P1_TRUST_DRIFT_VALIDATION_PASS")
        print(f"protected_path_patterns={len(PROTECTED_PATH_PATTERNS)}")
        if args.negative_control:
            count = run_negative_controls()
            print(f"drift_negative_controls_passed={count}")
            print(
                "meta_negative_controls=unauthorized_backend_trust_paths_and_pydantic_models_fail"
            )
        return 0
    except RuntimeError as exc:
        print(f"B25_P1_TRUST_DRIFT_VALIDATION_FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
