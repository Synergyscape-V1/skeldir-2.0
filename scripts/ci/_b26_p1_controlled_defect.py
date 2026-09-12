#!/usr/bin/env python3
"""Apply one reviewable B2.6-P1 on-disk controlled defect."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts/reconciliation/b2.6/semantic-authority.v1.yaml"
SEMANTIC_MODULE = ROOT / "backend/app/finance_reconciliation/semantic_contract.py"
COVERAGE_AUTHORITY_MODULE = ROOT / "backend/app/finance_reconciliation/coverage_authority.py"
CANONICAL_SINK_MODULE = ROOT / "backend/app/finance_reconciliation/canonical_sink.py"
PROOF_MANIFEST_MODULE = ROOT / "backend/app/finance_reconciliation/proof_manifest.py"
WORKFLOW = ROOT / ".github/workflows/b2_6-p1-finance-reconciliation-adjudication.yml"
DOCKERFILE = ROOT / "backend/Dockerfile"


def _replace_once(path: Path, old: str, new: str, *, defect: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{defect}:anchor_count={text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def mandatory_semantic_element() -> None:
    _replace_once(CONTRACT, "maturity_mode: DESIGN_PARTNER_MODE\n", "", defect="mandatory_semantic_element")


def coverage_authority_reference() -> None:
    _replace_once(
        CONTRACT,
        "  aggregate_callable: app.revenue_verification.verification_coverage.fetch_verification_coverage_aggregate\n",
        "  aggregate_callable: app.services.revenue_reconciliation.RevenueReconciliationService\n",
        defect="coverage_authority_reference",
    )


def legacy_false_authority_import() -> None:
    _replace_once(
        SEMANTIC_MODULE,
        "import yaml  # type: ignore[import-untyped]\n",
        "import yaml  # type: ignore[import-untyped]\n"
        "from app.services.revenue_reconciliation import RevenueReconciliationService  # NC-B26-P1-03\n",
        defect="legacy_false_authority_import",
    )


def ontological_authority() -> None:
    _replace_once(
        CONTRACT,
        "  LLM_financial_or_classification_authority: NONE\n",
        "  LLM_financial_or_classification_authority: DERIVED\n",
        defect="ontological_authority",
    )


def workflow_execution_identity() -> None:
    _replace_once(
        WORKFLOW,
        "    name: ${{ github.event_name == 'push' && 'B2.6 P1 Exact-Main Diagnostics' || 'B2.6 Finance Reconciliation Adjudication' }}\n",
        "    name: B2.6 Finance Reconciliation Adjudication\n",
        defect="workflow_execution_identity",
    )


def container_contract_copy() -> None:
    _replace_once(
        DOCKERFILE,
        "COPY contracts/reconciliation /app/contracts/reconciliation\n",
        "COPY contracts/reconciliation/v1 /app/contracts/reconciliation/v1\n",
        defect="container_contract_copy",
    )


def reason_identity_substitution() -> None:
    _replace_once(
        CONTRACT,
        "    - amount_mismatch_tax_shipping\n",
        "    - arbitrary_unrelated_reason\n",
        defect="reason_identity_substitution",
    )


def discrepancy_member_removal() -> None:
    _replace_once(
        CONTRACT,
        "    - privacy_limited_resolution\n",
        "",
        defect="discrepancy_member_removal",
    )


def tenant_policy_weakening() -> None:
    _replace_once(
        CONTRACT,
        "  external_raw_tenant_id: forbidden\n",
        "  external_raw_tenant_id: allowed\n",
        defect="tenant_policy_weakening",
    )


def insertion_seam_corruption() -> None:
    _replace_once(
        CONTRACT,
        "  - future_B2.6_deterministic_reconciliation_projection_boundary\n"
        "  - future_finance_projection\n"
        "  - future_B2.6_TrustEnvelope_projection\n"
        "\nnegative_control_registry:",
        "  - future_B2.6_deterministic_reconciliation_projection_boundary\n"
        "  - future_B2.6_TrustEnvelope_projection\n"
        "\nnegative_control_registry:",
        defect="insertion_seam_corruption",
    )


def discrepancy_addition_without_version_bump() -> None:
    _replace_once(
        CONTRACT,
        "    - privacy_limited_resolution\n",
        "    - privacy_limited_resolution\n    - future_probe_reason\n",
        defect="discrepancy_addition_without_version_bump",
    )


def unclassified_normative_field() -> None:
    _replace_once(
        CONTRACT,
        "negative_control_registry:\n  - B26-P1-NC-01",
        "future_probe_field: true\nnegative_control_registry:\n  - B26-P1-NC-01",
        defect="unclassified_normative_field",
    )


def dynamic_legacy_import() -> None:
    _replace_once(
        SEMANTIC_MODULE,
        'if __name__ == "__main__":\n'
        "    print(json.dumps(semantic_contract_identity().__dict__, sort_keys=True))",
        'if __name__ == "__main__":\n'
        "    import importlib as _nc_importlib  # NC-B26-P1-DYNAMIC\n"
        '    _nc_probe = _nc_importlib.import_module("app.services.revenue_reconciliation")\n'
        "    print(json.dumps(semantic_contract_identity().__dict__, sort_keys=True))",
        defect="dynamic_legacy_import",
    )


def legacy_network_client_in_canonical_surface() -> None:
    _replace_once(
        SEMANTIC_MODULE,
        "import yaml  # type: ignore[import-untyped]\n",
        "import yaml  # type: ignore[import-untyped]\n"
        "import httpx  # NC-B26-P1-III-NETWORK\n",
        defect="legacy_network_client_in_canonical_surface",
    )


def legacy_route_reference_in_canonical_surface() -> None:
    _replace_once(
        COVERAGE_AUTHORITY_MODULE,
        'CANONICAL_COVERAGE_LAW = "only_sovereign_rederivation_may_be_canonical"\n',
        'CANONICAL_COVERAGE_LAW = "only_sovereign_rederivation_may_be_canonical"\n'
        '_NC_LEGACY_ROUTE = "/api/reconciliation/status"  # NC-B26-P1-III-ROUTE\n',
        defect="legacy_route_reference_in_canonical_surface",
    )


def unregistered_coverage_origin() -> None:
    _replace_once(
        SEMANTIC_MODULE,
        'if __name__ == "__main__":\n'
        "    print(json.dumps(semantic_contract_identity().__dict__, sort_keys=True))",
        'if __name__ == "__main__":\n'
        "    _nc_forged = CanonicalVerificationCoverage(  # NC-B26-P1-III-ORIGIN\n"
        '        aggregate=None, result=None, producer="forged", supported_platforms=()\n'
        "    )\n"
        "    print(json.dumps(semantic_contract_identity().__dict__, sort_keys=True))",
        defect="unregistered_coverage_origin",
    )


def tenant_authority_bypass() -> None:
    _replace_once(
        COVERAGE_AUTHORITY_MODULE,
        "    await assert_tenant_authority(session, tenant_id)\n    sovereign = _sovereign()",
        "    sovereign = _sovereign()",
        defect="tenant_authority_bypass",
    )


def session_capability_injection() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        "async def execute_governed_sink(\n    sink_id: str,\n    *,",
        "async def execute_governed_sink(\n    sink_id: str,\n    session: Any = None,\n    *,",
        defect="session_capability_injection",
    )


def final_field_override_permit() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        '        if name in AUTHORITATIVE_FIELD_NAMES or "tenant" in name.lower():',
        "        if False:  # NC-B26-P1-V-OVERRIDE",
        defect="final_field_override_permit",
    )


def successor_provenance_omission() -> None:
    _replace_once(
        CONTRACT,
        "  status: provenance_mode_required_no_persistence_in_P1\n",
        "  status: optional\n",
        defect="successor_provenance_omission",
    )


def unregistered_canonical_output() -> None:
    _replace_once(
        SEMANTIC_MODULE,
        'if __name__ == "__main__":\n'
        "    print(json.dumps(semantic_contract_identity().__dict__, sort_keys=True))",
        'if __name__ == "__main__":\n'
        "    _nc_forged_output = FinalCanonicalOutput(  # NC-B26-P1-V-OUTPUT\n"
        '        authority="forged", sink_id="forged", contract_version="forged",\n'
        '        tenant_id_hash="forged", currency_code="USD",\n'
        "        window_start=None, window_end=None, supported_platforms=(),\n"
        "        matched_minor=0, connected_minor=0, coverage_percent=None,\n"
        '        zero_denominator=False, provenance_mode="forged",\n'
        '        sovereign_producer="forged", content_digest="forged",\n'
        '        adjunct_json="{}"\n'
        "    )\n"
        "    print(json.dumps(semantic_contract_identity().__dict__, sort_keys=True))",
        defect="unregistered_canonical_output",
    )


def caller_tenant_injection() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        "    sink_id: str,\n    *,\n    auth_token: str,\n",
        "    sink_id: str,\n    *,\n    auth_token: str,\n    tenant_id: Any = None,  # NC-B26-P1-VI-TENANT\n",
        defect="caller_tenant_injection",
    )


def arbitrary_callback_injection() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        "    supported_platforms: Any = None,\n    currency_code: str = \"USD\",\n",
        "    supported_platforms: Any = None,\n    currency_code: str = \"USD\",\n    adjunct_provider: Any = None,  # NC-B26-P1-VI-CALLBACK\n",
        defect="arbitrary_callback_injection",
    )


def duplicate_sink_permit() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        "            raise DuplicateSinkError(\n                f\"canonical_sink_duplicate_refused:{sink_id}\"\n            )",
        "            SINK_REGISTRY[str(sink_id)] = registration  # NC-B26-P1-VI-DUP\n            _SINK_IMPLEMENTATIONS[str(sink_id)] = func",
        defect="duplicate_sink_permit",
    )


def successor_authorize_permit() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        "    raise SuccessorProvenanceError(\n        \"successor_persistence_requires_p2_durable_binding:\"\n        f\"{registration_id}\"\n    )",
        "    return True  # NC-B26-P1-VI-SUCCESSOR",
        defect="successor_authorize_permit",
    )


def fake_proof_tolerance() -> None:
    _replace_once(
        PROOF_MANIFEST_MODULE,
        "    if tuple(proofs) != tuple(required):",
        "    if False:  # NC-B26-P1-VI-PROOF",
        defect="fake_proof_tolerance",
    )


DEFECTS: dict[str, Callable[[], None]] = {
    "mandatory_semantic_element": mandatory_semantic_element,
    "coverage_authority_reference": coverage_authority_reference,
    "legacy_false_authority_import": legacy_false_authority_import,
    "ontological_authority": ontological_authority,
    "workflow_execution_identity": workflow_execution_identity,
    "container_contract_copy": container_contract_copy,
    "reason_identity_substitution": reason_identity_substitution,
    "discrepancy_member_removal": discrepancy_member_removal,
    "tenant_policy_weakening": tenant_policy_weakening,
    "insertion_seam_corruption": insertion_seam_corruption,
    "discrepancy_addition_without_version_bump": discrepancy_addition_without_version_bump,
    "unclassified_normative_field": unclassified_normative_field,
    "dynamic_legacy_import": dynamic_legacy_import,
    "legacy_network_client_in_canonical_surface": legacy_network_client_in_canonical_surface,
    "legacy_route_reference_in_canonical_surface": legacy_route_reference_in_canonical_surface,
    "unregistered_coverage_origin": unregistered_coverage_origin,
    "tenant_authority_bypass": tenant_authority_bypass,
    "session_capability_injection": session_capability_injection,
    "final_field_override_permit": final_field_override_permit,
    "successor_provenance_omission": successor_provenance_omission,
    "unregistered_canonical_output": unregistered_canonical_output,
    "caller_tenant_injection": caller_tenant_injection,
    "arbitrary_callback_injection": arbitrary_callback_injection,
    "duplicate_sink_permit": duplicate_sink_permit,
    "successor_authorize_permit": successor_authorize_permit,
    "fake_proof_tolerance": fake_proof_tolerance,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("apply", "list"))
    parser.add_argument("defect", nargs="?")
    args = parser.parse_args()
    if args.action == "list":
        print("\n".join(sorted(DEFECTS)))
        return 0
    if not args.defect or args.defect not in DEFECTS:
        parser.error(f"apply requires one of {sorted(DEFECTS)}")
    DEFECTS[args.defect]()
    print(f"B26_P1_CONTROLLED_DEFECT_APPLIED {args.defect}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
