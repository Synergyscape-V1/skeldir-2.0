#!/usr/bin/env python3
"""Apply one reviewable B2.6-P1 on-disk controlled defect."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts/reconciliation/b2.6/semantic-authority.v1.yaml"
SEMANTIC_MODULE = ROOT / "backend/app/finance_reconciliation/semantic_contract.py"
COVERAGE_AUTHORITY_MODULE = (
    ROOT / "backend/app/finance_reconciliation/coverage_authority.py"
)
CANONICAL_SINK_MODULE = ROOT / "backend/app/finance_reconciliation/canonical_sink.py"
EXTERNAL_SEMANTICS_MODULE = (
    ROOT / "backend/app/finance_reconciliation/external_semantics.py"
)
TRUST_REFUSAL_MODULE = ROOT / "backend/app/trust/refusal.py"
AUTHORITATIVE_FIELDS_MODULE = (
    ROOT / "backend/app/finance_reconciliation/authoritative_fields.py"
)
PROOF_MANIFEST_MODULE = ROOT / "backend/app/finance_reconciliation/proof_manifest.py"
WORKFLOW = ROOT / ".github/workflows/b2_6-p1-finance-reconciliation-adjudication.yml"
DOCKERFILE = ROOT / "backend/Dockerfile"


def _replace_once(path: Path, old: str, new: str, *, defect: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{defect}:anchor_count={text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def mandatory_semantic_element() -> None:
    _replace_once(
        CONTRACT,
        "maturity_mode: DESIGN_PARTNER_MODE\n",
        "",
        defect="mandatory_semantic_element",
    )


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
        "async def execute_governed_sink(\n    sink_id: str,\n    *,\n    auth_token: str,\n",
        "async def execute_governed_sink(\n    sink_id: str,\n    *,\n    auth_token: str,\n    tenant_id: Any = None,  # NC-B26-P1-VI-TENANT\n",
        defect="caller_tenant_injection",
    )


def arbitrary_callback_injection() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        "async def execute_governed_sink(\n    sink_id: str,\n    *,\n    auth_token: str,\n    window_start: datetime,\n    window_end: datetime,\n"
        '    supported_platforms: Any = None,\n    currency_code: str = "USD",\n',
        "async def execute_governed_sink(\n    sink_id: str,\n    *,\n    auth_token: str,\n    window_start: datetime,\n    window_end: datetime,\n"
        '    supported_platforms: Any = None,\n    currency_code: str = "USD",\n    adjunct_provider: Any = None,  # NC-B26-P1-VI-CALLBACK\n',
        defect="arbitrary_callback_injection",
    )


def duplicate_sink_permit() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        '            raise DuplicateSinkError(f"canonical_sink_duplicate_refused:{sink_id}")',
        "            SINK_REGISTRY[str(sink_id)] = registration  # NC-B26-P1-VI-DUP\n            _SINK_IMPLEMENTATIONS[str(sink_id)] = func",
        defect="duplicate_sink_permit",
    )


def successor_authorize_permit() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        '    raise SuccessorProvenanceError(\n        "successor_persistence_requires_p2_durable_binding:" f"{registration_id}"\n    )',
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


def revoked_token_tolerance() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        "    await assert_access_token_active(token_claims)",
        "    pass  # NC-B26-P1-VII-REVOKED: lifecycle enforcement removed",
        defect="revoked_token_tolerance",
    )


def required_claims_tolerance() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        "    token_claims = extract_access_token_claims(claims)",
        "    token_claims = None  # NC-B26-P1-VII-CLAIMS: required-claim law skipped\n"
        '    _nc_tenant = claims.get("tenant_id")  # NC-B26-P1-VII-CLAIMS',
        defect="required_claims_tolerance",
    )


def external_promotion_permit() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        "async def render_governed_external(",
        "def to_canonical_external(output: FinalCanonicalOutput) -> dict[str, Any]:  # NC-B26-P1-VII-EXTERNAL\n"
        '    return {"authority": output.authority}  # NC-B26-P1-VII-EXTERNAL\n'
        "\n\n"
        "async def render_governed_external(",
        defect="external_promotion_permit",
    )


def framework_materialization_bypass() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        "            matched_minor=_s_matched_minor,\n"
        "            connected_minor=_s_connected_minor,\n"
        "            coverage_percent=_s_coverage_percent,\n"
        "            zero_denominator=_s_zero_denominator,\n"
        "            provenance_mode=_s_provenance_mode,",
        '            matched_minor=int(cleaned.get("matched_minor", _s_matched_minor)),  # NC-B26-P1-VII-MATERIAL\n'
        "            connected_minor=_s_connected_minor,\n"
        "            coverage_percent=_s_coverage_percent,\n"
        "            zero_denominator=_s_zero_denominator,\n"
        "            provenance_mode=_s_provenance_mode,",
        defect="framework_materialization_bypass",
    )


def post_derivation_alias_reread() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        "            matched_minor=_s_matched_minor,\n"
        "            connected_minor=_s_connected_minor,\n"
        "            coverage_percent=_s_coverage_percent,\n"
        "            zero_denominator=_s_zero_denominator,\n"
        "            provenance_mode=_s_provenance_mode,",
        "            matched_minor=projection_view.matched_minor,  # NC-B26-P1-VIII-ALIAS\n"
        "            connected_minor=projection_view.connected_minor,  # NC-B26-P1-VIII-ALIAS\n"
        "            coverage_percent=projection_view.coverage_percent,  # NC-B26-P1-VIII-ALIAS\n"
        "            zero_denominator=projection_view.zero_denominator,  # NC-B26-P1-VIII-ALIAS\n"
        "            provenance_mode=_s_provenance_mode,",
        defect="post_derivation_alias_reread",
    )


def executable_check_use_divergence() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        "        raw_adjunct = verified_implementation(projection_view)",
        "        implementation = _SINK_IMPLEMENTATIONS[str(sink_id)]  # NC-B26-P1-VIII-TOCTOU\n"
        "        raw_adjunct = implementation(projection_view)",
        defect="executable_check_use_divergence",
    )


def executable_capture_before_awaits() -> None:
    _replace_once(
        CANONICAL_SINK_MODULE,
        "        final_registration, verified_implementation = _capture_verified_implementation(\n"
        "            sink_id\n"
        "        )",
        "        final_registration = require_registered_sink(sink_id)  # NC-B26-P1-VIII-STALE\n"
        "        verified_implementation = _SINK_IMPLEMENTATIONS.get(str(sink_id))  # NC-B26-P1-VIII-STALE",
        defect="executable_capture_before_awaits",
    )


def shared_mutable_alias() -> None:
    """Class IX-A representative: snapshot list shared with projection view.

    Preserves every superficial ``_s_*`` lexical marker while creating
    genuine shared mutable backing storage: the snapshot becomes a ``list``
    and the projection view receives the same list object. In-place
    mutation (``append``/``extend``/item assignment) then corrupts the
    authoritative snapshot even though final materialization still reads
    ``_s_*`` names. Distinct from any permanent positive-test shape, which
    never mutates framework source.
    """
    _replace_once(
        CANONICAL_SINK_MODULE,
        "        _s_supported_platforms = freeze_platform_scope(coverage.supported_platforms)",
        "        _s_supported_platforms = list(coverage.supported_platforms)  # NC-B26-P1-IX-ALIAS",
        defect="shared_mutable_alias",
    )
    _replace_once(
        CANONICAL_SINK_MODULE,
        "            supported_platforms=freeze_platform_scope(_s_supported_platforms),",
        "            supported_platforms=_s_supported_platforms,  # NC-B26-P1-IX-ALIAS",
        defect="shared_mutable_alias",
    )


def authoritative_field_census_gap() -> None:
    """New authoritative field without isolation declaration.

    Adds a dataclass field to ``FinalCanonicalOutput`` without a matching
    ``AUTHORITATIVE_FIELD_REGISTRY`` entry. The census sensor must turn RED:
    future authoritative fields cannot silently escape snapshot-isolation
    proof coverage.
    """
    _replace_once(
        CANONICAL_SINK_MODULE,
        "    content_digest: str\n    adjunct_json: str\n",
        "    content_digest: str\n"
        "    adjunct_json: str\n"
        "    phantom_authoritative_field: str  # NC-B26-P1-IX-CENSUS\n",
        defect="authoritative_field_census_gap",
    )


# ---------------------------------------------------------------------------
# Corrective-X family: external census escape (X-A) and detached authority
# reacquisition (X-B). Each defect is a genuine member of its class through
# a distinct primitive; the proof must RED on every one (X-NC-1..X-NC-14).
# ---------------------------------------------------------------------------


def x_external_extra_literal_key() -> None:
    """X-NC-1: extra authoritative finance field as a literal contract row."""
    _replace_once(
        EXTERNAL_SEMANTICS_MODULE,
        '        normalization="exact governed sovereign-producer constant",\n'
        '        omission_law="never_omitted",\n'
        '    ),\n'
        '}\n',
        '        normalization="exact governed sovereign-producer constant",\n'
        '        omission_law="never_omitted",\n'
        '    ),\n'
        '    "verified_revenue_minor": ExternalFieldSemantics(\n'
        '        external_key="verified_revenue_minor",\n'
        '        source_attr="matched_minor",\n'
        '        external_type="int",\n'
        '        transform_id="integer_minor_identity",\n'
        '        transform=_money_minor_identity,\n'
        '        normalization="NC-B26-P1-X-NC1",\n'
        '        omission_law="never_omitted",\n'
        '    ),\n'
        '}\n',
        defect="x_external_extra_literal_key",
    )


def x_external_extra_dynamic_key() -> None:
    """X-NC-2: extra field via dynamic contract mutation after definition."""
    _replace_once(
        EXTERNAL_SEMANTICS_MODULE,
        "EXTERNAL_SEMANTIC_KEYS: frozenset[str] = frozenset(EXTERNAL_SEMANTICS)\n",
        'EXTERNAL_SEMANTICS["settled_revenue_minor"] = ExternalFieldSemantics(  # NC-B26-P1-X-NC2\n'
        '    external_key="settled_revenue_minor",\n'
        '    source_attr="connected_minor",\n'
        '    external_type="int",\n'
        '    transform_id="integer_minor_identity",\n'
        '    transform=_money_minor_identity,\n'
        '    normalization="NC-B26-P1-X-NC2",\n'
        '    omission_law="never_omitted",\n'
        ")\n"
        "EXTERNAL_SEMANTIC_KEYS: frozenset[str] = frozenset(EXTERNAL_SEMANTICS)\n",
        defect="x_external_extra_dynamic_key",
    )


def x_external_missing_key() -> None:
    """X-NC-3: required external field removed from the contract."""
    _replace_once(
        EXTERNAL_SEMANTICS_MODULE,
        '    "matched_minor": ExternalFieldSemantics(\n'
        '        external_key="matched_minor",\n'
        '        source_attr="matched_minor",\n'
        '        external_type="int",\n'
        '        transform_id="integer_minor_identity",\n'
        '        transform=_money_minor_identity,\n'
        '        normalization="exact integer minor units; no scale, sign, float, or bool drift",\n'
        '        omission_law="never_omitted",\n'
        '    ),\n',
        "",
        defect="x_external_missing_key",
    )


def x_external_wrong_source() -> None:
    """X-NC-4: lawful key sourced from the wrong sovereign attribute."""
    _replace_once(
        EXTERNAL_SEMANTICS_MODULE,
        '    "matched_minor": ExternalFieldSemantics(\n'
        '        external_key="matched_minor",\n'
        '        source_attr="matched_minor",\n',
        '    "matched_minor": ExternalFieldSemantics(\n'
        '        external_key="matched_minor",\n'
        '        source_attr="connected_minor",  # NC-B26-P1-X-NC4\n',
        defect="x_external_wrong_source",
    )


def x_detached_typed_renderer() -> None:
    """X-NC-5: typed detached renderer (annotated variant)."""
    _replace_once(
        CANONICAL_SINK_MODULE,
        "async def render_governed_external(",
        "def emit_canonical_from_transfer(output: FinalCanonicalOutput) -> dict:  # NC-B26-P1-X-NC5\n"
        '    return {"authority": output.authority, "matched_minor": output.matched_minor, "coverage_percent": str(output.coverage_percent)}  # NC-B26-P1-X-NC5\n'
        "\n\n"
        "async def render_governed_external(",
        defect="x_detached_typed_renderer",
    )


def x_detached_untyped_renderer() -> None:
    """X-NC-6: untyped detached renderer (annotation dropped)."""
    _replace_once(
        CANONICAL_SINK_MODULE,
        "async def render_governed_external(",
        "def render_detached_external(output):  # NC-B26-P1-X-NC6\n"
        '    return {"authority": output.authority, "matched_minor": getattr(output, "matched_minor", 0), "coverage_percent": str(getattr(output, "coverage_percent", "0"))}  # NC-B26-P1-X-NC6\n'
        "\n\n"
        "async def render_governed_external(",
        defect="x_detached_untyped_renderer",
    )


def x_detached_mapping_dto_renderer() -> None:
    """X-NC-7: Mapping/dict DTO detached renderer."""
    _replace_once(
        CANONICAL_SINK_MODULE,
        "async def render_governed_external(",
        "def export_canonical_dto(dto: Mapping[str, Any]) -> dict:  # NC-B26-P1-X-NC7\n"
        '    return {"authority": "canonical_B2.6_financial_truth", "matched_minor": int(dto.get("matched_minor", 0)), "coverage_percent": str(dto.get("coverage_percent", "0"))}  # NC-B26-P1-X-NC7\n'
        "\n\n"
        "async def render_governed_external(",
        defect="x_detached_mapping_dto_renderer",
    )


def x_sibling_authority_emitter() -> None:
    """X-NC-8: sibling-module canonical authority emitter (coverage_authority)."""
    _replace_once(
        COVERAGE_AUTHORITY_MODULE,
        '        "coverage_percent": str(result.coverage_percent),\n'
        '        "zero_denominator": bool(result.zero_denominator),\n'
        "    }\n",
        '        "coverage_percent": str(result.coverage_percent),\n'
        '        "zero_denominator": bool(result.zero_denominator),\n'
        "    }\n"
        "\n\n"
        "def sibling_canonical_export(record):  # NC-B26-P1-X-NC8\n"
        '    return {"authority": "canonical_B2.6_financial_truth", "matched_minor": int(record.get("matched_minor", 0)), "coverage_percent": str(record.get("coverage_percent", "0"))}  # NC-B26-P1-X-NC8\n',
        defect="x_sibling_authority_emitter",
    )


def x_serializer_promotion() -> None:
    """X-NC-9: generic serializer promoted as canonical renderer."""
    _replace_once(
        CANONICAL_SINK_MODULE,
        "async def render_governed_external(",
        "def dump_detached_canonical(output: FinalCanonicalOutput):  # NC-B26-P1-X-NC9\n"
        "    from dataclasses import asdict as _nc_asdict  # NC-B26-P1-X-NC9\n"
        "    return _nc_asdict(output)  # NC-B26-P1-X-NC9\n"
        "\n\n"
        "async def render_governed_external(",
        defect="x_serializer_promotion",
    )


def x_raw_tenant_externalized() -> None:
    """X-NC-10: raw tenant identity externalized via a contract row."""
    _replace_once(
        EXTERNAL_SEMANTICS_MODULE,
        '        normalization="exact governed sovereign-producer constant",\n'
        '        omission_law="never_omitted",\n'
        '    ),\n'
        '}\n',
        '        normalization="exact governed sovereign-producer constant",\n'
        '        omission_law="never_omitted",\n'
        '    ),\n'
        '    "tenant_id": ExternalFieldSemantics(\n'
        '        external_key="tenant_id",\n'
        '        source_attr="tenant_id_hash",\n'
        '        external_type="str",\n'
        '        transform_id="str_identity",\n'
        '        transform=_identity_str,\n'
        '        normalization="NC-B26-P1-X-NC10",\n'
        '        omission_law="never_omitted",\n'
        '    ),\n'
        '}\n',
        defect="x_raw_tenant_externalized",
    )


def x_adjunct_externalized() -> None:
    """X-NC-11: adjunct field externalized as a finance semantic."""
    _replace_once(
        EXTERNAL_SEMANTICS_MODULE,
        '        normalization="exact governed sovereign-producer constant",\n'
        '        omission_law="never_omitted",\n'
        '    ),\n'
        '}\n',
        '        normalization="exact governed sovereign-producer constant",\n'
        '        omission_law="never_omitted",\n'
        '    ),\n'
        '    "adjunct_json": ExternalFieldSemantics(\n'
        '        external_key="adjunct_json",\n'
        '        source_attr="adjunct_json",\n'
        '        external_type="str",\n'
        '        transform_id="str_identity",\n'
        '        transform=_identity_str,\n'
        '        normalization="NC-B26-P1-X-NC11",\n'
        '        omission_law="never_omitted",\n'
        '    ),\n'
        '}\n',
        defect="x_adjunct_externalized",
    )


def x_llm_wired_value() -> None:
    """X-NC-12: existing canonical transform wired to adjacent-domain state."""
    _replace_once(
        EXTERNAL_SEMANTICS_MODULE,
        '    "currency_code": ExternalFieldSemantics(\n'
        '        external_key="currency_code",\n'
        '        source_attr="currency_code",\n'
        '        external_type="str",\n'
        '        transform_id="str_identity",\n'
        '        transform=_identity_str,\n',
        '    "currency_code": ExternalFieldSemantics(\n'
        '        external_key="currency_code",\n'
        '        source_attr="currency_code",\n'
        '        external_type="str",\n'
        '        transform_id="str_identity",\n'
        '        transform=lambda value: __import__("os").environ.get(  # NC-B26-P1-X-NC12\n'
        '            "XG_B24_CURRENCY", value\n'
        '        ),\n',
        defect="x_llm_wired_value",
    )


def x_schema_drift() -> None:
    """X-NC-13: internal/external schema desynchronization (policy drift)."""
    _replace_once(
        AUTHORITATIVE_FIELDS_MODULE,
        '        projection_representation="scalar copy in AdjunctContext.sink_id",\n'
        '        alias_policy="immutable value sharing lawful; mutable sharing forbidden",\n'
        '        externalization_policy="emitted as render key",\n',
        '        projection_representation="scalar copy in AdjunctContext.sink_id",\n'
        '        alias_policy="immutable value sharing lawful; mutable sharing forbidden",\n'
        '        externalization_policy="NOT emitted externally (X drift)",  # NC-B26-P1-X-NC13\n',
        defect="x_schema_drift",
    )


def x_unapproved_authority_label() -> None:
    """X-NC-14: canonical authority label emitted via **kwargs function."""
    _replace_once(
        CANONICAL_SINK_MODULE,
        "async def render_governed_external(",
        "def publish_canonical(**kwargs):  # NC-B26-P1-X-NC14\n"
        '    return {"authority": kwargs.get("authority", "canonical_B2.6_financial_truth"), "matched_minor": int(kwargs.get("matched_minor", 0)), "coverage_percent": str(kwargs.get("coverage_percent", "0"))}  # NC-B26-P1-X-NC14\n'
        "\n\n"
        "async def render_governed_external(",
        defect="x_unapproved_authority_label",
    )




# ---------------------------------------------------------------------------
# Corrective-XI controlled defects (classes XI-A/XI-B/XI-C).
# ---------------------------------------------------------------------------


def xi_nc01_window_date_truncation() -> None:
    """XI-NC-01: full-instant transform truncated to date-only."""
    _replace_once(
        EXTERNAL_SEMANTICS_MODULE,
        '    encoded = value.isoformat()\n'
        '    if not _INSTANT_PATTERN.match(encoded):\n'
        '        raise ExternalSemanticsError(\n'
        '            f"external_transform_refused:instant_encoding:{encoded}"\n'
        '        )\n'
        '    return encoded\n',
        '    return value.date().isoformat()  # XI-NC-01\n',
        defect="xi_nc01_window_date_truncation",
    )


def xi_nc02_timezone_stripping() -> None:
    """XI-NC-02: timezone semantics stripped from the instant transform."""
    _replace_once(
        EXTERNAL_SEMANTICS_MODULE,
        '    encoded = value.isoformat()\n'
        '    if not _INSTANT_PATTERN.match(encoded):\n'
        '        raise ExternalSemanticsError(\n'
        '            f"external_transform_refused:instant_encoding:{encoded}"\n'
        '        )\n'
        '    return encoded\n',
        '    return value.replace(tzinfo=None).isoformat()  # XI-NC-02\n',
        defect="xi_nc02_timezone_stripping",
    )


def xi_nc03_money_zeroing() -> None:
    """XI-NC-03: integer money transform corrupted (zeroing)."""
    _replace_once(
        EXTERNAL_SEMANTICS_MODULE,
        '    if value < 0:\n'
        '        raise ExternalSemanticsError("external_transform_refused:money_negative")\n'
        '    return value\n',
        '    if value < 0:\n'
        '        raise ExternalSemanticsError("external_transform_refused:money_negative")\n'
        '    return value * 0  # XI-NC-03\n',
        defect="xi_nc03_money_zeroing",
    )


def xi_nc04_platform_subset() -> None:
    """XI-NC-04: platform membership corrupted (subset)."""
    _replace_once(
        EXTERNAL_SEMANTICS_MODULE,
        '    return members\n',
        '    return members[:1]  # XI-NC-04\n',
        defect="xi_nc04_platform_subset",
    )


def xi_nc05_forged_capability_construct_then_return() -> None:
    """XI-NC-05: construct-then-return FORGED canonical capability."""
    _replace_once(
        COVERAGE_AUTHORITY_MODULE,
        'def is_governed_canonical_sink(name: str) -> bool:\n',
        'def xg_forged_egress_construct(record):  # XI-NC-05\n'
        '    from app.finance_reconciliation.canonical_sink import (  # XI-NC-05\n'
        '        CanonicalExternalTruth as _C,\n'
        '        _EGRESS_ISSUANCE as _P,\n'
        '    )\n'
        '    payload = {"authority": "canonical_B2.6_financial_truth", "matched_minor": int(record.get("matched_minor", 0))}  # XI-NC-05\n'
        '    return _C(payload, _P)  # XI-NC-05\n'
        '\n'
        '\n'
        'def is_governed_canonical_sink(name: str) -> bool:\n',
        defect="xi_nc05_forged_capability_construct_then_return",
    )


def xi_nc06_forged_capability_dict_call() -> None:
    """XI-NC-06: dict(...)-built fields FORGED into a canonical capability."""
    _replace_once(
        COVERAGE_AUTHORITY_MODULE,
        'def is_governed_canonical_sink(name: str) -> bool:\n',
        'def xg_forged_egress_dict(record):  # XI-NC-06\n'
        '    from app.finance_reconciliation.canonical_sink import (  # XI-NC-06\n'
        '        CanonicalExternalTruth as _C,\n'
        '        _EGRESS_ISSUANCE as _P,\n'
        '    )\n'
        '    return _C(dict(authority="canonical_B2.6_financial_truth", matched_minor=int(record.get("matched_minor", 0))), _P)  # XI-NC-06\n'
        '\n'
        '\n'
        'def is_governed_canonical_sink(name: str) -> bool:\n',
        defect="xi_nc06_forged_capability_dict_call",
    )


def xi_nc07_forged_capability_wrapper_class() -> None:
    """XI-NC-07: wrapper/subclass attempt on the sealed capability type."""
    _replace_once(
        COVERAGE_AUTHORITY_MODULE,
        'def is_governed_canonical_sink(name: str) -> bool:\n',
        'def xg_forged_wrapper(record):  # XI-NC-07\n'
        '    from app.finance_reconciliation.canonical_sink import (  # XI-NC-07\n'
        '        CanonicalExternalTruth as _C,\n'
        '    )\n'
        '\n'
        '    class XgWrapperCapability(_C):  # XI-NC-07\n'
        '        pass\n'
        '\n'
        '    return XgWrapperCapability\n'
        '\n'
        '\n'
        'def is_governed_canonical_sink(name: str) -> bool:\n',
        defect="xi_nc07_forged_capability_wrapper_class",
    )


def xi_nc08_forged_capability_renamed_serializer() -> None:
    """XI-NC-08: renamed serializer output FORGED into a capability."""
    _replace_once(
        COVERAGE_AUTHORITY_MODULE,
        'def is_governed_canonical_sink(name: str) -> bool:\n',
        'def xg_forged_egress_serializer(output):  # XI-NC-08\n'
        '    from dataclasses import asdict as xg_serialize  # XI-NC-08\n'
        '    from app.finance_reconciliation.canonical_sink import (  # XI-NC-08\n'
        '        CanonicalExternalTruth as _C,\n'
        '        _EGRESS_ISSUANCE as _P,\n'
        '    )\n'
        '    return _C(xg_serialize(output), _P)  # XI-NC-08\n'
        '\n'
        '\n'
        'def is_governed_canonical_sink(name: str) -> bool:\n',
        defect="xi_nc08_forged_capability_renamed_serializer",
    )


def xi_nc09_forged_capability_alias_marker() -> None:
    """XI-NC-09: aliased/computed authority marker FORGED into a capability."""
    _replace_once(
        COVERAGE_AUTHORITY_MODULE,
        'def is_governed_canonical_sink(name: str) -> bool:\n',
        'def xg_forged_egress_alias(output):  # XI-NC-09\n'
        '    AUTH = "canonical_B2.6_" + "financial_truth"  # XI-NC-09\n'
        '    from app.finance_reconciliation.canonical_sink import (  # XI-NC-09\n'
        '        CanonicalExternalTruth as _C,\n'
        '        _EGRESS_ISSUANCE as _P,\n'
        '    )\n'
        '    return _C({"authority": AUTH, "matched_minor": int(output.matched_minor)}, _P)  # XI-NC-09\n'
        '\n'
        '\n'
        'def is_governed_canonical_sink(name: str) -> bool:\n',
        defect="xi_nc09_forged_capability_alias_marker",
    )


def xi_nc10_unregistered_egress_surface() -> None:
    """XI-NC-10: second, unreviewed entry in the governed egress registry."""
    _replace_once(
        CANONICAL_SINK_MODULE,
        '    ),\n'
        '}\n'
        '\n'
        '\n'
        'def verify_external_semantics_contract_pin() -> str:\n',
        '    ),\n'
        '    "xg_second_surface": GovernedEgressSurface(  # XI-NC-10\n'
        '        surface_id="xg_second_surface",\n'
        '        callable_path="app.finance_reconciliation.canonical_sink.render_governed_external",\n'
        '        egress_kind="LIVE_CANONICAL",\n'
        '        consumes="xg",\n'
        '        serializer="xg",\n'
        '        capability_type="xg",\n'
        '        admission="xg",\n'
        '        downstream_consumers="xg",\n'
        '    ),\n'
        '}\n'
        '\n'
        '\n'
        'def verify_external_semantics_contract_pin() -> str:\n',
        defect="xi_nc10_unregistered_egress_surface",
    )


def xi_nc11_unregistered_trust_adapter() -> None:
    """XI-NC-11: unregistered adapter surface forging capabilities."""
    _replace_once(
        TRUST_REFUSAL_MODULE,
        'def tenant_hash(',
        'def xg_trust_canonical_export(record):  # XI-NC-11\n'
        '    from app.finance_reconciliation.canonical_sink import (  # XI-NC-11\n'
        '        CanonicalExternalTruth as _C,\n'
        '        _EGRESS_ISSUANCE as _P,\n'
        '    )\n'
        '    return _C(dict(record), _P)  # XI-NC-11\n'
        '\n'
        '\n'
        'def tenant_hash(',
        defect="xi_nc11_unregistered_trust_adapter",
    )


def xi_nc12_validate_return_divergence() -> None:
    """XI-NC-12: issuer constructs from a divergent post-validation copy."""
    _replace_once(
        CANONICAL_SINK_MODULE,
        '    fields = project_external_fields(output)\n'
        '    return CanonicalExternalTruth(fields, _EGRESS_ISSUANCE)\n',
        '    fields = project_external_fields(output)\n'
        '    divergent = {**fields, "verified_revenue_minor": 7}  # XI-NC-12\n'
        '    return CanonicalExternalTruth(divergent, _EGRESS_ISSUANCE)  # XI-NC-12\n',
        defect="xi_nc12_validate_return_divergence",
    )


def xi_nc13_source_co_drift() -> None:
    """XI-NC-13: co-mutated contract source + lineage-map projection."""
    _replace_once(
        AUTHORITATIVE_FIELDS_MODULE,
        '        "render_attr": spec.source_attr,\n',
        '        "render_attr": (  # XI-NC-13\n'
        '            "connected_minor"\n'
        '            if spec.external_key == "matched_minor"\n'
        '            else spec.source_attr\n'
        '        ),\n',
        defect="xi_nc13_source_co_drift",
    )
    _replace_once(
        EXTERNAL_SEMANTICS_MODULE,
        '    "matched_minor": ExternalFieldSemantics(\n'
        '        external_key="matched_minor",\n'
        '        source_attr="matched_minor",\n',
        '    "matched_minor": ExternalFieldSemantics(\n'
        '        external_key="matched_minor",\n'
        '        source_attr="connected_minor",  # XI-NC-13\n',
        defect="xi_nc13_source_co_drift",
    )


def xi_nc14_adjacent_domain_transform_dependency() -> None:
    """XI-NC-14: transform wired to adjacent-domain environment state."""
    _replace_once(
        EXTERNAL_SEMANTICS_MODULE,
        '    "coverage_percent": ExternalFieldSemantics(\n'
        '        external_key="coverage_percent",\n'
        '        source_attr="coverage_percent",\n'
        '        external_type="str",\n'
        '        transform_id="decimal_2dp_exact_string",\n'
        '        transform=_percent_2dp_str,\n',
        '    "coverage_percent": ExternalFieldSemantics(\n'
        '        external_key="coverage_percent",\n'
        '        source_attr="coverage_percent",\n'
        '        external_type="str",\n'
        '        transform_id="decimal_2dp_exact_string",\n'
        '        transform=lambda value: __import__("os").environ.get(  # XI-NC-14\n'
        '            "XG_B24_ESTIMATE", _percent_2dp_str(value)\n'
        '        ),\n',
        defect="xi_nc14_adjacent_domain_transform_dependency",
    )


def xi_nc15_contract_pin_removed() -> None:
    """XI-NC-15: frozen-contract pin verification removed from egress load."""
    _replace_once(
        CANONICAL_SINK_MODULE,
        '_XI_CONTRACT_PIN_AST_SHA256 = verify_external_semantics_contract_pin()\n',
        '_XI_CONTRACT_PIN_AST_SHA256 = "unpinned"  # XI-NC-15\n',
        defect="xi_nc15_contract_pin_removed",
    )


def xi_nc16_admission_weakened() -> None:
    """XI-NC-16: admission weakened to accept any mapping representation."""
    _replace_once(
        CANONICAL_SINK_MODULE,
        '    if type(candidate) is not CanonicalExternalTruth:\n'
        '        raise CanonicalSinkError(\n'
        '            "canonical_external_admission_refused:not_governed_egress_capability:"\n'
        '            f"{type(candidate).__name__}"\n'
        '        )\n',
        '    if not isinstance(candidate, Mapping):  # XI-NC-16\n'
        '        raise CanonicalSinkError(\n'
        '            "canonical_external_admission_refused:not_governed_egress_capability:"\n'
        '            f"{type(candidate).__name__}"\n'
        '        )\n',
        defect="xi_nc16_admission_weakened",
    )


def xi_nc17_renderer_handwritten_mapping() -> None:
    """XI-NC-17: renderer reintroduces a hand-written external mapping."""
    _replace_once(
        CANONICAL_SINK_MODULE,
        '    return _issue_canonical_external(output)\n',
        '    rendered = {  # XI-NC-17\n'
        '        "authority": output.authority,\n'
        '        "window_start": output.window_start.date().isoformat(),\n'
        '        "matched_minor": int(output.matched_minor),\n'
        '    }  # XI-NC-17\n'
        '    validate_external_rendering(rendered)  # XI-NC-17\n'
        '    return _issue_canonical_external(output)\n',
        defect="xi_nc17_renderer_handwritten_mapping",
    )


def xi_nc18_transform_contract_unpinned_from_yaml() -> None:
    """XI-NC-18: YAML contract pin pointed at a stale transform identity."""
    import hashlib
    import re as _re

    text = CONTRACT.read_text(encoding="utf-8")
    stale = hashlib.sha256(b"stale-xi-nc-18").hexdigest()
    new_text, count = _re.subn(
        r"(\n  ast_sha256: )[0-9a-f]{64}", r"\g<1>" + stale, text, count=1
    )
    if count != 1:
        raise SystemExit("xi_nc18:anchor_count=0")
    CONTRACT.write_text(new_text, encoding="utf-8")


def xi_nc19_capability_seal_removed() -> None:
    """XI-NC-19: issuance-proof check removed from the sealed constructor."""
    _replace_once(
        CANONICAL_SINK_MODULE,
        '            if issuance is not issuance_secret:\n'
        '                raise CanonicalSinkError("canonical_egress_capability_refused")\n',
        '            if False:  # XI-NC-19\n'
        '                raise CanonicalSinkError("canonical_egress_capability_refused")\n',
        defect="xi_nc19_capability_seal_removed",
    )


def xi_nc20_denominator_regression() -> None:
    """XI-NC-20: B2.3 coverage implementation semantic drift (AST pin)."""
    _replace_once(
        ROOT / "backend/app/revenue_verification/verification_coverage.py",
        'def _normalize_utc(value: datetime) -> datetime:',
        'def _xg_nc20_probe():  # XI-NC-20\n'
        '    return 1\n'
        '\n'
        '\n'
        'def _normalize_utc(value: datetime) -> datetime:',
        defect="xi_nc20_denominator_regression",
    )

def xi_immutable_fields_removed() -> None:
    """Extra XI control: capability fields stored mutable (proxy removed)."""
    _replace_once(
        CANONICAL_SINK_MODULE,
        '            object.__setattr__(self, "_fields", MappingProxyType(dict(fields)))\n',
        '            object.__setattr__(self, "_fields", dict(fields))  # XI-EXTRA\n',
        defect="xi_immutable_fields_removed",
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
    "revoked_token_tolerance": revoked_token_tolerance,
    "required_claims_tolerance": required_claims_tolerance,
    "external_promotion_permit": external_promotion_permit,
    "framework_materialization_bypass": framework_materialization_bypass,
    "post_derivation_alias_reread": post_derivation_alias_reread,
    "executable_check_use_divergence": executable_check_use_divergence,
    "executable_capture_before_awaits": executable_capture_before_awaits,
    "shared_mutable_alias": shared_mutable_alias,
    "authoritative_field_census_gap": authoritative_field_census_gap,
    "x_external_extra_literal_key": x_external_extra_literal_key,
    "x_external_extra_dynamic_key": x_external_extra_dynamic_key,
    "x_external_missing_key": x_external_missing_key,
    "x_external_wrong_source": x_external_wrong_source,
    "x_detached_typed_renderer": x_detached_typed_renderer,
    "x_detached_untyped_renderer": x_detached_untyped_renderer,
    "x_detached_mapping_dto_renderer": x_detached_mapping_dto_renderer,
    "x_sibling_authority_emitter": x_sibling_authority_emitter,
    "x_serializer_promotion": x_serializer_promotion,
    "x_raw_tenant_externalized": x_raw_tenant_externalized,
    "x_adjunct_externalized": x_adjunct_externalized,
    "x_llm_wired_value": x_llm_wired_value,
    "x_schema_drift": x_schema_drift,
    "x_unapproved_authority_label": x_unapproved_authority_label,
    "xi_nc01_window_date_truncation": xi_nc01_window_date_truncation,
    "xi_nc02_timezone_stripping": xi_nc02_timezone_stripping,
    "xi_nc03_money_zeroing": xi_nc03_money_zeroing,
    "xi_nc04_platform_subset": xi_nc04_platform_subset,
    "xi_nc05_forged_capability_construct_then_return": (
        xi_nc05_forged_capability_construct_then_return
    ),
    "xi_nc06_forged_capability_dict_call": xi_nc06_forged_capability_dict_call,
    "xi_nc07_forged_capability_wrapper_class": xi_nc07_forged_capability_wrapper_class,
    "xi_nc08_forged_capability_renamed_serializer": (
        xi_nc08_forged_capability_renamed_serializer
    ),
    "xi_nc09_forged_capability_alias_marker": xi_nc09_forged_capability_alias_marker,
    "xi_nc10_unregistered_egress_surface": xi_nc10_unregistered_egress_surface,
    "xi_nc11_unregistered_trust_adapter": xi_nc11_unregistered_trust_adapter,
    "xi_nc12_validate_return_divergence": xi_nc12_validate_return_divergence,
    "xi_nc13_source_co_drift": xi_nc13_source_co_drift,
    "xi_nc14_adjacent_domain_transform_dependency": (
        xi_nc14_adjacent_domain_transform_dependency
    ),
    "xi_nc15_contract_pin_removed": xi_nc15_contract_pin_removed,
    "xi_nc16_admission_weakened": xi_nc16_admission_weakened,
    "xi_nc17_renderer_handwritten_mapping": xi_nc17_renderer_handwritten_mapping,
    "xi_nc18_transform_contract_unpinned_from_yaml": (
        xi_nc18_transform_contract_unpinned_from_yaml
    ),
    "xi_nc19_capability_seal_removed": xi_nc19_capability_seal_removed,
    "xi_nc20_denominator_regression": xi_nc20_denominator_regression,
    "xi_immutable_fields_removed": xi_immutable_fields_removed,
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
