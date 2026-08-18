#!/usr/bin/env python3
"""Validate B2.5-P13 C3 confidence authority as one closed system.

This gate binds the signed contract, subject-conditioned field registry,
physical SQL graph, persisted-classification seam, reason semantics, bounded
read topology, and CI triggers. Its negative controls mutate semantic inputs to
the same checkers; syntax errors and invalid fixtures do not count.
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.confidence_projection.policy import (  # noqa: E402
    CONFIDENCE_POLICY_VERSION,
    CONFIDENCE_SEMANTICS_VERSION,
    ConfidenceBucket,
    ConfidenceBucketReason,
    ConfidencePolicyDecision,
    classify_confidence,
)
from app.confidence_projection.read_model import (  # noqa: E402
    _EXACT_FIT_PROJECTION_SQL,
)
from app.confidence_projection.sql_authority import (  # noqa: E402
    executable_public_relations,
)
from app.trust.builder import _confidence_projection_metadata  # noqa: E402
from app.trust.source_adapters import (  # noqa: E402
    TRUST_ENVELOPE_FIELD_SOURCE_REGISTRIES,
)
from app.trust.subject_authority import (  # noqa: E402
    SUBJECT_AUTHORITY_DEFINITIONS,
)


READ_MODEL = ROOT / "backend/app/confidence_projection/read_model.py"
BUILDER = ROOT / "backend/app/trust/builder.py"
CONTRACT_REGISTRY = ROOT / "contracts/trust-api/subject-authority-registry.yaml"
P13_WORKFLOW = ROOT / ".github/workflows/b2_5-p13-e2e-trust-closure.yml"
B24_WORKFLOW = ROOT / ".github/workflows/b2_4-gate-dry-run.yml"

REQUIRED_P13_TRIGGER_PATHS = (
    "backend/app/bayesian/fit_execution.py",
    "backend/app/bayesian/fit_claim.py",
    "backend/app/bayesian/runtime_state.py",
    "backend/app/bayesian/e2e_harness.py",
    "backend/app/bayesian/models.py",
    "backend/app/bayesian/repository.py",
    "backend/app/bayesian/source_snapshot.py",
    "backend/app/confidence_projection/**",
    "backend/app/trust/**",
    "alembic/versions/007_skeldir_foundation/**",
    "contracts/trust-api/**",
    "scripts/ci/validate_b25_p13_confidence_truth.py",
    "scripts/ci/validate_b25_p13_c4_closure.py",
)


class B25P13ConfidenceTruthError(RuntimeError):
    """Raised when any C3 confidence authority invariant is false."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise B25P13ConfidenceTruthError(reason)


def _registry(value: dict[str, Any] | None = None) -> dict[str, Any]:
    if value is not None:
        return value
    return yaml.safe_load(CONTRACT_REGISTRY.read_text(encoding="utf-8"))


def validate_source_authority(
    *,
    registry: dict[str, Any] | None = None,
    definitions: dict[str, Any] | None = None,
    read_source: str | None = None,
    read_sql: str | None = None,
) -> int:
    """Bind governed declarations to the actual direct SQL read graph."""

    definitions = definitions or SUBJECT_AUTHORITY_DEFINITIONS
    contract = _registry(registry).get("allowed_subject_types") or {}
    _require(set(contract) >= set(definitions), "contract_subject_authority_missing")
    for subject, definition in definitions.items():
        row = contract[subject]
        _require(
            row.get("source_authority_class") == definition.source_authority_class,
            f"authority_class_drift:{subject}",
        )
        _require(
            tuple(row.get("allowed_source_tables") or ())
            == definition.governed_source_tables,
            f"governed_source_drift:{subject}",
        )
        _require(
            set(definition.physical_read_tables)
            <= set(definition.governed_source_tables),
            f"hidden_physical_authority:{subject}",
        )

    source = read_source if read_source is not None else READ_MODEL.read_text("utf-8")
    sql = read_sql if read_sql is not None else str(_EXACT_FIT_PROJECTION_SQL)
    physical = tuple(sorted(executable_public_relations(sql)))
    expected = tuple(sorted(definitions["confidence_projection"].physical_read_tables))
    _require(physical == expected, f"physical_read_graph_drift:{physical}!={expected}")
    _require(
        "classify_confidence" not in source,
        "late_or_live_confidence_dependency:classify_confidence",
    )
    _require(
        "assert_executable_read_authority(" in source,
        "runtime_executable_authority_fence_missing",
    )
    _require(
        "persisted_confidence_decision" in source, "persisted_classifier_seam_missing"
    )
    _require(
        'not bool(mapping.get("has_snapshot_lineage"))' in source
        and 'mapping.get("source_read_started_at")' in source
        and 'mapping.get("source_read_completed_at")' in source
        and 'return "unknown"' in source,
        "missing_freshness_authority_not_unknown",
    )
    return len(expected)


def validate_subject_conditioned_fields(
    registries: dict[str, dict[str, Any]] | None = None,
) -> int:
    """Require distinct truthful field authority for both supported subjects."""

    registries = registries or TRUST_ENVELOPE_FIELD_SOURCE_REGISTRIES
    _require(
        set(registries) == {"match_verdict", "confidence_projection"},
        "field_registry_subject_set_drift",
    )
    match = registries["match_verdict"]
    confidence = registries["confidence_projection"]
    _require(set(match) == set(confidence), "field_registry_surface_drift")
    _require(
        match["truth_authority"].authority_class == "deterministic_machine_fact"
        and match["truth_authority"].source_path.startswith("b23_match_verdicts"),
        "match_verdict_field_authority_changed",
    )
    for field in (
        "subject_authority",
        "truth_type",
        "truth_authority",
        "confidence_metadata",
        "provenance_chain",
        "data_completeness_status",
        "fallback_applied",
        "fallback_reason",
        "evidence_temporal_boundary",
        "artifact_ref",
        "artifact_hash",
    ):
        _require(
            confidence[field].authority_class == "confidence_metadata_projection",
            f"confidence_field_uses_wrong_authority:{field}",
        )
    _require(
        "b24_dirty_events" in confidence["provenance_chain"].source_path,
        "freshness_provenance_not_field_governed",
    )
    for field in ("match_verdict_status", "verified_revenue_minor"):
        _require(
            confidence[field].source_class == "explicit_unavailable"
            and confidence[field].authority_class == "explicitly_unavailable",
            f"confidence_inapplicable_field_not_explicit:{field}",
        )
    return len(confidence)


def _projection(reason: ConfidenceBucketReason, *, diagnostic: str = "passed") -> Any:
    return SimpleNamespace(
        model_version="b24-c3-v1",
        diagnostic_status=diagnostic,
        decision=ConfidencePolicyDecision(
            confidence_available=False,
            confidence_bucket=ConfidenceBucket.UNAVAILABLE,
            confidence_bucket_reason=reason,
        ),
    )


def validate_reason_truth(
    expected: dict[ConfidenceBucketReason, tuple[str, str]] | None = None,
) -> int:
    """Mechanically bind internal conditions to objectively true external states."""

    expected = expected or {
        ConfidenceBucketReason.INSUFFICIENT_DATA: (
            "unavailable",
            "cold_start_insufficient_data",
        ),
        ConfidenceBucketReason.BAD_RHAT: (
            "diagnostics_failed",
            "diagnostics_failed",
        ),
        ConfidenceBucketReason.SOURCE_SNAPSHOT_CHANGED: (
            "degraded",
            "source_snapshot_stale",
        ),
        ConfidenceBucketReason.SOURCE_AUTHORITY_UNKNOWN: (
            "unavailable",
            "confidence_unavailable",
        ),
        ConfidenceBucketReason.MULTI_CURRENCY_UNSUPPORTED: (
            "unavailable",
            "unsupported_financial_context",
        ),
        ConfidenceBucketReason.ARTIFACT_PRUNED: ("degraded", "artifact_pruned"),
        ConfidenceBucketReason.ARTIFACT_UNAVAILABLE: (
            "degraded",
            "artifact_unavailable",
        ),
    }
    for reason, (status, external_reason) in expected.items():
        diagnostic = "failed" if reason is ConfidenceBucketReason.BAD_RHAT else "passed"
        metadata, *_ = _confidence_projection_metadata(
            SimpleNamespace(projection=_projection(reason, diagnostic=diagnostic))
        )
        _require(
            metadata["confidence_status"] == status
            and metadata["unavailable_reason"] == external_reason,
            f"false_reason_mapping:{reason.value}",
        )
    return len(expected)


def validate_bounded_read(read_source: str | None = None) -> int:
    """Reject live aggregation and unbounded latest-fit semantics."""

    source = read_source if read_source is not None else READ_MODEL.read_text("utf-8")
    lowered = source.lower()
    for token in ("sum(", "count(", "max(", "latest fit", "limit :"):
        _require(token not in lowered, f"unbounded_or_recomputed_confidence:{token}")
    for token in (
        "fit.id = :fit_id",
        "requested_fit.fit_id = artifact.fit_id",
        "exists (",
    ):
        _require(token in lowered, f"bounded_exact_fit_guard_missing:{token}")
    route = (ROOT / "backend/app/api/trust_api.py").read_text("utf-8")
    for constant in (
        "MAX_EVALUATED_REFS_PER_PAGE = 2",
        "MAX_RETURNED_OUTCOMES = 2",
        "MAX_CONCURRENT_QUERY_REQUESTS = 2",
    ):
        _require(constant in route, f"p10_resource_bound_missing:{constant}")
    return 6


def validate_ci_topology(workflow: str | None = None) -> int:
    """Bind every authority-changing surface to P13 and shared B2.4 proofs."""

    source = workflow if workflow is not None else P13_WORKFLOW.read_text("utf-8")
    for path in REQUIRED_P13_TRIGGER_PATHS:
        _require(path in source, f"p13_trigger_missing:{path}")
    _require(
        "validate_b25_p13_confidence_truth.py --negative-control" in source,
        "confidence_truth_validator_not_invoked",
    )
    _require(
        "p13_confidence_values_reachable" not in source, "rejected_enum_metric_survives"
    )
    b24 = B24_WORKFLOW.read_text("utf-8")
    _require("pull_request:" in b24, "b24_classifier_consumer_not_pr_bound")
    _require("validate-b24-p10-projection" in b24, "b24_p10_classifier_proof_missing")
    return len(REQUIRED_P13_TRIGGER_PATHS) + 4


def validate_builder_authority(source: str | None = None) -> int:
    """Prevent hand-maintained source lists from re-entering signed payloads."""

    source = source if source is not None else BUILDER.read_text("utf-8")
    _require(
        source.count("subject_authority_definition(") >= 2,
        "canonical_authority_builder_not_used",
    )
    _require(
        "list(authority.governed_source_tables)" in source,
        "builder_governed_sources_not_derived",
    )
    _require(
        '"allowed_source_tables": [' not in source, "hand_maintained_builder_sources"
    )
    return 3


def _expect_failure(label: str, call) -> None:
    try:
        call()
    except B25P13ConfidenceTruthError:
        return
    raise B25P13ConfidenceTruthError(f"negative_control_did_not_fire:{label}")


def run_negative_controls() -> int:
    """Execute NC-C3-01..12 as semantic mutations against real checkers."""

    controls = 0

    read = READ_MODEL.read_text("utf-8")
    read_sql = str(_EXACT_FIT_PROJECTION_SQL)
    _expect_failure(
        "NC-C3-01",
        lambda: validate_source_authority(
            read_sql=read_sql.replace(
                "FROM public.bayesian_artifacts",
                "FROM public.hidden_confidence_source hidden JOIN public.bayesian_artifacts",
            )
        ),
    )
    controls += 1

    poisoned_fields = copy.deepcopy(TRUST_ENVELOPE_FIELD_SOURCE_REGISTRIES)
    poisoned_fields["confidence_projection"] = poisoned_fields["match_verdict"]
    _expect_failure(
        "NC-C3-02", lambda: validate_subject_conditioned_fields(poisoned_fields)
    )
    controls += 1

    # NC-C3-03/04: fail-open freshness and live recomputation are both rejected.
    _expect_failure(
        "NC-C3-03",
        lambda: validate_source_authority(
            read_source=read.replace('return "unknown"', 'return "current"')
        ),
    )
    controls += 1
    _expect_failure(
        "NC-C3-04",
        lambda: validate_source_authority(
            read_sql=(
                read_sql
                + "\nJOIN public.b23_revenue_events forbidden_live_dependency ON false\n"
            )
        ),
    )
    controls += 1

    multi_currency = classify_confidence(
        {
            "fit_id": "nc-c3-05",
            "fit_status": "succeeded",
            "currency_count": 2,
            "deterministic_revenue_minor": 100,
        }
    )
    _require(
        multi_currency.confidence_bucket_reason
        is ConfidenceBucketReason.MULTI_CURRENCY_UNSUPPORTED,
        "NC-C3-05:multi_currency_not_typed",
    )
    controls += 1

    false_reasons = {
        ConfidenceBucketReason.ARTIFACT_UNAVAILABLE: ("degraded", "artifact_pruned")
    }
    _expect_failure("NC-C3-06", lambda: validate_reason_truth(false_reasons))
    controls += 1

    _require(
        _confidence_projection_metadata(
            SimpleNamespace(
                projection=_projection(ConfidenceBucketReason.ARTIFACT_PRUNED)
            )
        )[0]["confidence_status"]
        != "available",
        "NC-C3-07:pruned_artifact_revived",
    )
    controls += 1

    poisoned_definitions = dict(SUBJECT_AUTHORITY_DEFINITIONS)
    confidence = poisoned_definitions["confidence_projection"]
    poisoned_definitions["confidence_projection"] = SimpleNamespace(
        source_authority_class=confidence.source_authority_class,
        governed_source_tables=confidence.governed_source_tables + ("tenant_b_fit",),
        physical_read_tables=confidence.physical_read_tables,
    )
    _expect_failure(
        "NC-C3-08", lambda: validate_source_authority(definitions=poisoned_definitions)
    )
    controls += 1

    _expect_failure(
        "NC-C3-09",
        lambda: validate_source_authority(
            read_source=read + "\nclassify_confidence(mapping)\n"
        ),
    )
    controls += 1

    workflow = P13_WORKFLOW.read_text("utf-8")
    _expect_failure(
        "NC-C3-10",
        lambda: validate_ci_topology(
            workflow.replace(
                "backend/app/confidence_projection/**",
                "backend/app/confidence_projection/read_model.py",
            )
        ),
    )
    controls += 1

    _expect_failure(
        "NC-C3-11",
        lambda: validate_bounded_read(
            read_source=read.replace("fit.id = :fit_id", "fit.model_type = :model_type")
        ),
    )
    controls += 1
    _expect_failure(
        "NC-C3-12",
        lambda: validate_bounded_read(
            read_source=read + "\nSELECT COUNT(*) FROM public.b24_dirty_events\n"
        ),
    )
    controls += 1
    return controls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()

    checks = 0
    checks += validate_source_authority()
    checks += validate_subject_conditioned_fields()
    checks += validate_reason_truth()
    checks += validate_bounded_read()
    checks += validate_builder_authority()
    checks += validate_ci_topology()
    controls = run_negative_controls() if args.negative_control else 0
    print("B25_P13_CONFIDENCE_TRUTH_VALIDATION_PASS")
    print(f"confidence_truth_checks_passed={checks}")
    print(f"confidence_truth_negative_controls_fired={controls}")
    print(f"confidence_policy_version={CONFIDENCE_POLICY_VERSION}")
    print(f"confidence_semantics_version={CONFIDENCE_SEMANTICS_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
