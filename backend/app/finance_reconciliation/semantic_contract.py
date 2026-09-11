"""Runtime-resolvable B2.6-P1 semantic constitution.

This module loads and validates authority metadata only. It intentionally owns
no reconciliation calculation or financial state. Future B2.6 consumers must
cite this contract and the B2.3 callable it names; CI rejects a second coverage
implementation or a dependency on a fenced legacy surface.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml  # type: ignore[import-untyped]


_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = (
    _PACKAGE_ROOT.parent
    if (_PACKAGE_ROOT.parent / "contracts/reconciliation").is_dir()
    else _PACKAGE_ROOT
)
B26_P1_SEMANTIC_CONTRACT_PATH = (
    _REPO_ROOT / "contracts/reconciliation/b2.6/semantic-authority.v1.yaml"
)
B26_P1_CONTRACT_VERSION = "b2.6-p1-semantic-authority-v4"
B26_P1_SUPERSEDES_VERSION = "b2.6-p1-semantic-authority-v3"

_REQUIRED_TOP_LEVEL = frozenset(
    {
        "phase_id",
        "contract_version",
        "supersession",
        "maturity_mode",
        "authority_kind",
        "migration_authority",
        "coverage_authority",
        "truth_status",
        "truth_state_vocabulary",
        "scope_dispositions",
        "finance_discrepancy_reasons",
        "required_reconciliation_reasons",
        "legacy_collapsed_reason_labels_superseded",
        "money_authority",
        "projection_doctrine",
        "tenant_identifier_policy",
        "ontological_authority",
        "authority_map",
        "legacy_false_authorities",
        "legacy_authority_quarantine",
        "future_insertion_seam",
        "negative_control_registry",
        "proof_artifact_identity_requirements",
        "prohibited_P1_product_machinery",
        "successor_product_authorization",
        "authority_classes",
        "closure_snapshot",
    }
)

# Authority classifications a governed future contract field may carry.
# An unknown top-level field without one of these classifications is RED.
B26_KNOWN_AUTHORITY_CLASSES = frozenset(
    {
        "PERMANENT_MACHINE_ENFORCED",
        "PHASE_LOCAL_CLOSURE_FACT",
        "DOCUMENTATION_ONLY",
        "FUTURE_REQUIRED_EXTENSION",
    }
)

# Successor-phase product-machinery gate values.
B26_SUCCESSOR_STATUS_NONE = "none"
B26_SUCCESSOR_STATUS_AUTHORIZED = "authorized_p2_product_growth"

# Governed taxonomy minor-version bumps: v1 bare iff no additive reasons.
B26_DISCREPANCY_TAXONOMY_V1 = "b2.6-discrepancy-taxonomy-v1"
_B26_TAXONOMY_BUMP_RE = re.compile(
    r"^b2\.6-discrepancy-taxonomy-v1\.[1-9][0-9]*$"
)

B26_REQUIRED_DISCREPANCY_REASONS = frozenset(
    {
        "amount_mismatch_tax_shipping",
        "amount_mismatch_platform_claim",
        "late_webhook",
        "unsupported_payment_rail",
        "refund_or_chargeback_adjustment",
        "missing_order_reference",
        "duplicate_claim",
        "privacy_limited_resolution",
    }
)

B26_REQUIRED_TRUTH_STATE_VOCABULARY = frozenset(
    {
        "matched_confirmed",
        "matched_provisional",
        "adjusted_confirmed",
    }
)

B26_REQUIRED_SCOPE_DISPOSITIONS = frozenset(
    {
        "supported_unresolved",
        "unsupported_provider_excluded",
        "unsupported_currency_excluded",
        "outside_governed_window_excluded",
        "source_identity_unresolved",
        "authority_unavailable",
    }
)

B26_REQUIRED_FUTURE_INSERTION_SEAM = frozenset(
    {
        "B2.3_deterministic_verdict_and_coverage_authority",
        "future_B2.6_deterministic_reconciliation_projection_boundary",
        "future_finance_projection",
        "future_B2.6_TrustEnvelope_projection",
    }
)

# Exact nested structures whose values are permanent law (SW-03 class).
# A syntactically valid YAML replacement of any of these is RED.
B26_REQUIRED_AUTHORITY_MAP = {
    "sovereign": [
        "authenticated_commerce_identity:webhook_ingress_identities",
        "deterministic_match_verdict:b23_match_verdicts",
        "verification_coverage:app.revenue_verification.verification_coverage",
    ],
    "derived": [
        "future_B2.6_reconciliation:from_B2.3_verdict_and_coverage_authority_only",
    ],
    "projection_only": [
        "finance_export",
        "TrustEnvelope_reconciliation_projection",
    ],
    "forbidden": [
        "B2.4_confidence_as_money_or_denominator",
        "B2.13_counterfactual_as_revenue_or_discrepancy",
        "LLM_output_as_reconciliation_truth",
    ],
}

B26_REQUIRED_LEGACY_FALSE_AUTHORITIES = [
    {
        "id": "legacy_reconciliation_service",
        "python_module": "app.services.revenue_reconciliation",
        "python_symbol": "RevenueReconciliationService",
    },
    {
        "id": "legacy_revenue_ledger",
        "database_relation": "public.revenue_ledger",
    },
    {
        "id": "legacy_reconciliation_api",
        "python_module": "app.api.reconciliation",
        "route_prefix": "/api/reconciliation",
    },
    {
        "id": "route_local_source_alias_arithmetic",
        "python_module": "app.api.reconciliation",
        "python_symbol": "_SOURCE_ALIASES",
    },
    {
        "id": "allocation_grain_export_recomputation",
        "python_module": "app.api.export",
        "python_symbol": "_fetch_reporting_rows",
    },
]

B26_REQUIRED_PROOF_IDENTITY_FIELDS = [
    "gate_id",
    "phase",
    "contract_version",
    "contract_hash",
    "candidate_sha",
    "candidate_tree",
    "migration_head",
    "producer",
    "workflow",
    "event_type",
    "run_id",
    "artifact_hash",
    "scenario_id",
    "falsifier_id",
    "status",
]

B26_REQUIRED_PROHIBITED_PRODUCT_MACHINERY = [
    "reconciliation_business_table",
    "reconciliation_computation_kernel",
    "reconciliation_API",
    "reconciliation_worker_or_scheduler",
    "reconciliation_outbox",
    "finance_reconciliation_export",
    "TrustEnvelope_reconciliation_fields",
]

B26_REQUIRED_COHERENT_OBJECT_FIELDS = [
    "financial_amount",
    "governed_scope",
    "truth_status",
    "reason_or_exclusion",
    "provenance",
    "tenant_authority",
    "contract_version",
    "trust_envelope_identity",
]

B26_REQUIRED_AUTHORITY_CLASSES = {    "phase_id": "PERMANENT_MACHINE_ENFORCED",
    "contract_version": "PERMANENT_MACHINE_ENFORCED",
    "supersession": "DOCUMENTATION_ONLY",
    "maturity_mode": "PERMANENT_MACHINE_ENFORCED",
    "authority_kind": "PERMANENT_MACHINE_ENFORCED",
    "migration_authority.schema_change_required_in_P1": "PHASE_LOCAL_CLOSURE_FACT",
    "migration_authority.expected_single_head": "PHASE_LOCAL_CLOSURE_FACT",
    "migration_authority.p1_closure_head": "PHASE_LOCAL_CLOSURE_FACT",
    "migration_authority.ancestry_law": "PERMANENT_MACHINE_ENFORCED",
    "migration_authority.revision_graph_source": "PERMANENT_MACHINE_ENFORCED",
    "migration_authority.rationale": "DOCUMENTATION_ONLY",
    "coverage_authority": "PERMANENT_MACHINE_ENFORCED",
    "coverage_authority.canonical_admission_seam": "PERMANENT_MACHINE_ENFORCED",
    "coverage_authority.supported_provider_scope_reference": "PERMANENT_MACHINE_ENFORCED",
    "coverage_authority.supported_currency_scope_reference": "PERMANENT_MACHINE_ENFORCED",
    "coverage_authority.numerator.definition": "DOCUMENTATION_ONLY",
    "coverage_authority.denominator.definition": "DOCUMENTATION_ONLY",
    "coverage_authority.window_semantics": "DOCUMENTATION_ONLY",
    "coverage_authority.unsupported_rail_doctrine.later_finance_representation": "DOCUMENTATION_ONLY",
    "truth_status": "PERMANENT_MACHINE_ENFORCED",
    "truth_status.future_consumer_requirement": "DOCUMENTATION_ONLY",
    "truth_state_vocabulary": "PERMANENT_MACHINE_ENFORCED",
    "scope_dispositions": "PERMANENT_MACHINE_ENFORCED",
    "finance_discrepancy_reasons": "PERMANENT_MACHINE_ENFORCED",
    "finance_discrepancy_reasons.additional_governed_reasons": "PERMANENT_MACHINE_ENFORCED",
    "finance_discrepancy_reasons.evolution_policy": "PERMANENT_MACHINE_ENFORCED",
    "finance_discrepancy_reasons.classifier_status": "FUTURE_REQUIRED_EXTENSION",
    "required_reconciliation_reasons": "PHASE_LOCAL_CLOSURE_FACT",
    "legacy_collapsed_reason_labels_superseded": "DOCUMENTATION_ONLY",
    "money_authority": "PERMANENT_MACHINE_ENFORCED",
    "projection_doctrine": "PERMANENT_MACHINE_ENFORCED",
    "tenant_identifier_policy": "PERMANENT_MACHINE_ENFORCED",
    "ontological_authority": "PERMANENT_MACHINE_ENFORCED",
    "authority_map": "PERMANENT_MACHINE_ENFORCED",
    "legacy_false_authorities": "PERMANENT_MACHINE_ENFORCED",
    "legacy_authority_quarantine": "PERMANENT_MACHINE_ENFORCED",
    "future_insertion_seam": "PERMANENT_MACHINE_ENFORCED",
    "negative_control_registry": "PHASE_LOCAL_CLOSURE_FACT",
    "proof_artifact_identity_requirements": "PERMANENT_MACHINE_ENFORCED",
    "prohibited_P1_product_machinery": "PHASE_LOCAL_CLOSURE_FACT",
    "successor_product_authorization": "PERMANENT_MACHINE_ENFORCED",
    "closure_snapshot": "PHASE_LOCAL_CLOSURE_FACT",
}


class SemanticContractError(ValueError):
    """Raised when B2.6 semantic authority is absent, malformed, or weakened."""


@dataclass(frozen=True)
class SemanticContractIdentity:
    """Exact source and semantic identities of the governing contract."""

    phase: str
    contract_version: str
    source_sha256: str
    semantic_sha256: str


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise SemanticContractError(reason)


def _validate_contract(document: Mapping[str, Any]) -> None:
    missing = sorted(_REQUIRED_TOP_LEVEL - set(document))
    _require(not missing, f"b26_p1_contract_missing_fields:{','.join(missing)}")
    _require(document["phase_id"] == "B2.6-P1", "b26_p1_phase_mismatch")
    _require(
        document["contract_version"] == B26_P1_CONTRACT_VERSION,
        "b26_p1_contract_version_mismatch",
    )
    supersession = document["supersession"]
    _require(
        isinstance(supersession, dict)
        and supersession.get("supersedes") == B26_P1_SUPERSEDES_VERSION
        and isinstance(supersession.get("reason"), str)
        and bool(supersession.get("reason")),
        "b26_p1_supersession_identity_drift",
    )
    _require(
        document["maturity_mode"] == "DESIGN_PARTNER_MODE",
        "b26_p1_maturity_mode_mismatch",
    )
    _require(
        document["authority_kind"] == "semantic_constitution_not_financial_result",
        "b26_p1_authority_kind_drift",
    )
    migration = document["migration_authority"]
    _require(
        migration.get("schema_change_required_in_P1") is False
        and migration.get("expected_single_head") == "202609072001"
        and migration.get("p1_closure_head") == "202609072001"
        and migration.get("ancestry_law") == "descendant_of_p1_closure_head_required"
        and migration.get("revision_graph_source") == "alembic_native_ScriptDirectory",
        "b26_p1_migration_authority_drift",
    )

    coverage = document["coverage_authority"]
    _require(isinstance(coverage, dict), "b26_p1_coverage_authority_not_object")
    _require(
        coverage.get("aggregate_callable")
        == "app.revenue_verification.verification_coverage."
        "fetch_verification_coverage_aggregate",
        "b26_p1_coverage_aggregate_authority_drift",
    )
    _require(
        coverage.get("metric_object")
        == "app.revenue_verification.verification_coverage.VERIFICATION_COVERAGE",
        "b26_p1_coverage_metric_authority_drift",
    )
    _require(
        coverage.get("metric_method") == "compute",
        "b26_p1_coverage_metric_method_drift",
    )
    _require(
        coverage.get("supported_provider_scope_reference")
        == "app.revenue_verification.verification_coverage."
        "SUPPORTED_VERIFICATION_COVERAGE_PLATFORMS",
        "b26_p1_coverage_provider_scope_drift",
    )
    _require(
        coverage.get("supported_currency_scope_reference")
        == "app.revenue_verification.verification_coverage."
        "SUPPORTED_VERIFICATION_COVERAGE_CURRENCIES",
        "b26_p1_coverage_currency_scope_drift",
    )
    # Machine identifiers for the governed legs (SW-03 class): the prose
    # definitions are honestly DOCUMENTATION_ONLY, but the leg names are law.
    _require(
        coverage.get("numerator", {}).get("name") == "matched_webhook_revenue_minor"
        and coverage.get("denominator", {}).get("name")
        == "connected_platform_revenue_minor",
        "b26_p1_coverage_leg_identity_drift",
    )
    implementation_hash = coverage.get("implementation_ast_sha256")
    _require(
        isinstance(implementation_hash, str)
        and len(implementation_hash) == 64
        and all(character in "0123456789abcdef" for character in implementation_hash),
        "b26_p1_coverage_implementation_hash_invalid",
    )
    vector = coverage.get("golden_falsification_vector", {})
    _require(
        vector
        == {
            "matched_minor": 76000,
            "connected_supported_minor": 80000,
            "total_business_minor": 100000,
            "required_percent": "95.00",
            "forbidden_percent": "76.00",
        },
        "b26_p1_coverage_golden_vector_drift",
    )
    unsupported = coverage.get("unsupported_rail_doctrine", {})
    _require(
        unsupported.get("numerator") == "excluded"
        and unsupported.get("denominator") == "excluded",
        "b26_p1_unsupported_rail_denominator_drift",
    )
    seam_decl = coverage.get("canonical_admission_seam", {})
    _require(
        seam_decl.get("module")
        == "app.finance_reconciliation.coverage_authority"
        and seam_decl.get("sealed_type")
        == "app.finance_reconciliation.coverage_authority."
        "CanonicalVerificationCoverage"
        and seam_decl.get("loader")
        == "app.finance_reconciliation.coverage_authority."
        "load_canonical_verification_coverage"
        and seam_decl.get("admitter")
        == "app.finance_reconciliation.coverage_authority."
        "admit_canonical_verification_coverage"
        and seam_decl.get("scope_verifier")
        == "app.finance_reconciliation.coverage_authority."
        "require_canonical_scope"
        and seam_decl.get("sovereign_producer")
        == "app.revenue_verification.verification_coverage."
        "fetch_verification_coverage_aggregate"
        "+app.revenue_verification.verification_coverage."
        "VERIFICATION_COVERAGE.compute"
        and seam_decl.get("law") == "only_sovereign_rederivation_may_be_canonical",
        "b26_p1_coverage_admission_seam_drift",
    )

    truth_status = document["truth_status"]
    provisional = truth_status.get("matched_provisional", {})
    _require(
        truth_status.get("coverage_is_not_final_finance_confirmation") is True,
        "b26_p1_coverage_confirmation_conflation",
    )
    _require(
        provisional.get("participates_in_coverage_numerator") is True
        and provisional.get("finance_truth_status") == "provisional"
        and provisional.get("may_be_relabelled_confirmed") is False,
        "b26_p1_provisional_semantics_drift",
    )
    confirmed = truth_status.get("matched_confirmed", {})
    _require(
        confirmed.get("participates_in_coverage_numerator") is True
        and confirmed.get("finance_truth_status") == "confirmed",
        "b26_p1_confirmed_semantics_drift",
    )
    adjusted = truth_status.get("adjusted", {})
    _require(
        adjusted.get("participates_in_coverage_numerator") is True
        and adjusted.get("finance_truth_status") == "confirmed_adjusted",
        "b26_p1_adjusted_semantics_drift",
    )

    money = document["money_authority"]
    _require(
        money.get("representation") == "integer_minor_units"
        and money.get("authoritative_float_or_decimal_major_units") == "forbidden"
        and money.get("display_major_units") == "derived_non_authoritative_only",
        "b26_p1_integer_money_authority_drift",
    )
    tenant = document["tenant_identifier_policy"]
    _require(
        tenant.get("durable_state") == "tenant_scoped"
        and tenant.get("external_raw_tenant_id") == "forbidden"
        and tenant.get("external_identity") == "one_way_tenant_id_hash_or_equivalent",
        "b26_p1_tenant_externalization_drift",
    )
    seam = document["future_insertion_seam"]
    _require(
        isinstance(seam, list) and set(seam) == B26_REQUIRED_FUTURE_INSERTION_SEAM,
        "b26_p1_future_insertion_seam_drift",
    )
    truth_vocab = document["truth_state_vocabulary"]
    _require(
        isinstance(truth_vocab, list)
        and set(truth_vocab) == B26_REQUIRED_TRUTH_STATE_VOCABULARY,
        "b26_p1_truth_state_vocabulary_drift",
    )
    scope_disp = document["scope_dispositions"]
    _require(
        isinstance(scope_disp, list)
        and set(scope_disp) == B26_REQUIRED_SCOPE_DISPOSITIONS,
        "b26_p1_scope_disposition_drift",
    )
    discrepancy = document["finance_discrepancy_reasons"]
    required_reasons = set(discrepancy.get("required_reasons", []))
    additional_reasons = discrepancy.get("additional_governed_reasons", [])
    _require(
        isinstance(additional_reasons, list)
        and len(additional_reasons) == len(set(additional_reasons)),
        "b26_p1_discrepancy_additive_slot_malformed",
    )
    additional_set = set(additional_reasons)
    _require(
        isinstance(discrepancy, dict)
        and B26_REQUIRED_DISCREPANCY_REASONS <= required_reasons
        and required_reasons == B26_REQUIRED_DISCREPANCY_REASONS | additional_set
        and not (additional_set & B26_REQUIRED_DISCREPANCY_REASONS),
        "b26_p1_discrepancy_taxonomy_drift",
    )
    taxonomy_version = discrepancy.get("taxonomy_version")
    if not additional_set:
        _require(
            taxonomy_version == B26_DISCREPANCY_TAXONOMY_V1,
            "b26_p1_discrepancy_taxonomy_version_drift",
        )
    else:
        _require(
            isinstance(taxonomy_version, str)
            and bool(_B26_TAXONOMY_BUMP_RE.match(taxonomy_version)),
            "b26_p1_discrepancy_additive_evolution_requires_minor_version_bump",
        )
    _require(
        discrepancy.get("evolution_policy")
        == "additive_only_with_minor_version_bump"
        and discrepancy.get("classifier_status")
        == "deferred_to_B2.6-P3_no_classifier_in_P1",
        "b26_p1_discrepancy_evolution_policy_drift",
    )
    collapsed = document["required_reconciliation_reasons"]
    _require(
        collapsed == [],
        "b26_p1_collapsed_reason_category_resurrected",
    )
    legacy_collapsed = document["legacy_collapsed_reason_labels_superseded"]
    _require(
        isinstance(legacy_collapsed, list) and len(legacy_collapsed) == 9,
        "b26_p1_legacy_collapsed_record_drift",
    )
    authority_classes = document["authority_classes"]
    _require(
        isinstance(authority_classes, dict),
        "b26_p1_authority_class_drift",
    )
    for key, value in B26_REQUIRED_AUTHORITY_CLASSES.items():
        _require(
            authority_classes.get(key) == value,
            f"b26_p1_authority_class_drift:{key}",
        )
    # Forward composition: a governed future field may extend the registry,
    # but only with a known classification. Unknown classes are RED.
    for key, value in authority_classes.items():
        _require(
            key in B26_REQUIRED_AUTHORITY_CLASSES or value in B26_KNOWN_AUTHORITY_CLASSES,
            f"b26_p1_authority_class_ungoverned:{key}",
        )
    # Any top-level contract field beyond the required set must be classified
    # above; an unclassified normative field is RED (LG-07 negative direction).
    unclassified = sorted(
        key
        for key in document
        if key not in _REQUIRED_TOP_LEVEL and key not in authority_classes
    )
    _require(
        not unclassified,
        f"b26_p1_unclassified_normative_field:{','.join(unclassified)}",
    )
    successor = document["successor_product_authorization"]
    _require(
        isinstance(successor, dict)
        and successor.get("status")
        in (B26_SUCCESSOR_STATUS_NONE, B26_SUCCESSOR_STATUS_AUTHORIZED)
        and isinstance(successor.get("authorized_machinery"), list),
        "b26_p1_successor_authorization_malformed",
    )
    if successor.get("status") == B26_SUCCESSOR_STATUS_AUTHORIZED:
        _require(
            len(successor.get("authorized_machinery", [])) > 0,
            "b26_p1_successor_authorization_empty",
        )
    snapshot = document["closure_snapshot"]
    _require(
        isinstance(snapshot, dict)
        and snapshot.get("p1_closure_migration_head") == "202609072001"
        and snapshot.get("p1_closure_package_files")
        == [
            "__init__.py",
            "semantic_contract.py",
            "coverage_authority.py",
            "legacy_quarantine.py",
        ]
        and snapshot.get("p1_closure_proof_cell_count") == 5
        and snapshot.get("p1_closure_contract_version")
        == B26_P1_CONTRACT_VERSION,
        "b26_p1_closure_snapshot_drift",
    )
    projections = document["projection_doctrine"]
    for projection_name in ("finance_export", "trust_envelope"):
        projection = projections.get(projection_name, {})
        _require(
            projection.get("authority") == "projection_only"
            and projection.get("recomputation") == "forbidden"
            and projection.get("required_source")
            == "future_durable_B2.6_reconciliation_authority",
            f"b26_p1_projection_authority_drift:{projection_name}",
        )
    _require(
        projections.get("trust_envelope", {}).get("fields_created_in_P1") is False,
        "b26_p1_trust_envelope_fields_created_in_p1",
    )
    _require(
        projections.get("coherent_information_object_requires")
        == B26_REQUIRED_COHERENT_OBJECT_FIELDS,
        "b26_p1_coherent_object_requirements_drift",
    )

    ontology = document["ontological_authority"]
    _require(
        ontology.get("deterministic_B2.3_truth") == "sovereign_input"
        and ontology.get("deterministic_B2.6_reconciliation")
        == "future_derived_authority"
        and ontology.get("B2.4_and_B2.13_usage")
        == "optional_separately_labelled_enrichment_only",
        "b26_p1_ontological_lineage_drift",
    )
    for key in (
        "B2.4_estimation_financial_authority",
        "B2.13_counterfactual_financial_authority",
        "LLM_financial_or_classification_authority",
    ):
        _require(ontology.get(key) == "NONE", f"b26_p1_false_authority:{key}")

    _require(
        document["authority_map"] == B26_REQUIRED_AUTHORITY_MAP,
        "b26_p1_authority_map_drift",
    )
    _require(
        document["legacy_false_authorities"]
        == B26_REQUIRED_LEGACY_FALSE_AUTHORITIES,
        "b26_p1_false_authority_registry_drift",
    )
    quarantine = document["legacy_authority_quarantine"]
    _require(
        isinstance(quarantine, dict)
        and quarantine.get("status") == "compatibility_only_non_authoritative"
        and quarantine.get("mounted_for_compatibility") is True
        and quarantine.get("canonical_admission") == "refused"
        and set(quarantine.get("route_paths", []))
        == {
            "/api/reconciliation/status",
            "/api/reconciliation/platform/{platform_id}",
            "/api/reconciliation/sync",
        }
        and set(quarantine.get("modules", []))
        == {
            "app.services.revenue_reconciliation",
            "app.api.reconciliation",
            "app.api.export",
        },
        "b26_p1_legacy_quarantine_drift",
    )
    _require(
        document["proof_artifact_identity_requirements"]
        == B26_REQUIRED_PROOF_IDENTITY_FIELDS,
        "b26_p1_proof_identity_requirements_drift",
    )
    _require(
        document["prohibited_P1_product_machinery"]
        == B26_REQUIRED_PROHIBITED_PRODUCT_MACHINERY,
        "b26_p1_product_scope_fence_drift",
    )
    _require(
        len(document["negative_control_registry"]) >= 7,
        "b26_p1_negative_control_registry_incomplete",
    )


@lru_cache(maxsize=1)
def load_b26_p1_semantic_contract() -> Mapping[str, Any]:
    """Load the exact shipped contract and fail closed on any semantic drift."""
    if not B26_P1_SEMANTIC_CONTRACT_PATH.is_file():
        raise SemanticContractError(
            f"b26_p1_contract_missing:{B26_P1_SEMANTIC_CONTRACT_PATH.as_posix()}"
        )
    document = yaml.safe_load(
        B26_P1_SEMANTIC_CONTRACT_PATH.read_text(encoding="utf-8")
    )
    if not isinstance(document, dict):
        raise SemanticContractError("b26_p1_contract_not_object")
    _validate_contract(document)
    return document


def semantic_contract_identity() -> SemanticContractIdentity:
    """Return byte and semantic hashes recoverable inside a shipped image."""
    document = load_b26_p1_semantic_contract()
    source = B26_P1_SEMANTIC_CONTRACT_PATH.read_bytes()
    return SemanticContractIdentity(
        phase="B2.6-P1",
        contract_version=B26_P1_CONTRACT_VERSION,
        source_sha256=hashlib.sha256(source).hexdigest(),
        semantic_sha256=hashlib.sha256(_canonical_json(document)).hexdigest(),
    )


if __name__ == "__main__":
    print(json.dumps(semantic_contract_identity().__dict__, sort_keys=True))
