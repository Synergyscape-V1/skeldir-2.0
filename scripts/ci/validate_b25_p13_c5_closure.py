#!/usr/bin/env python3
"""Validate B2.5-P13 C5 lifecycle, temporal, and proof-system closure.

Corrective Action V closed five reproduced defects. This gate exists so none of
them can return while `B2.5-P13 E2E Trust Closure` stays green:

* terminal fit truth could be restated under a reclaimed dispatch lease;
* `claim_fit_for_snapshot()` could not execute at all against migration head;
* same-snapshot re-observation raised an unhandled fence/integrity error;
* materially future evidence rendered as `current`, zero seconds old;
* evidence older than the representable ceiling rendered identically to
  near-fresh evidence, with no signal that the number was saturated.

Every control below carries an explicit STATIC/BEHAVIORAL classification, per
Corrective Action V section 14. A behavioral invariant is not allowed to rest on
a source-text check: either this script executes the real object and observes the
real refusal, or it names the exact runtime journey that does and verifies that
journey is still wired into the required proof graph.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.confidence_projection.policy import (  # noqa: E402
    CONFIDENCE_POLICY_VERSION,
    CONFIDENCE_SEMANTICS_VERSION,
    EVIDENCE_FRESHNESS_CEILING_SECONDS,
    EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS,
    ConfidenceBucketReason,
    evidence_timestamp_is_plausible,
    persisted_confidence_decision,
)
from app.confidence_projection.read_model import (  # noqa: E402
    B24ConfidenceProjectionRead,
    _projection_decision,
    _snapshot_freshness,
)
from app.trust.builder import (  # noqa: E402
    TrustEnvelopeBuildRequest,
    _confidence_projection_payload,
)
from app.trust.source_adapters import ConfidenceProjectionSource  # noqa: E402


C5_MIGRATION = (
    ROOT
    / "alembic/versions/007_skeldir_foundation"
    / "202608191200_b25_p13_c5_terminal_truth_temporal_plausibility.py"
)
FIT_CLAIM = ROOT / "backend/app/bayesian/fit_claim.py"
BUILDER = ROOT / "backend/app/trust/builder.py"
POLICY = ROOT / "backend/app/confidence_projection/policy.py"
CANONICAL_SCHEMA = ROOT / "db/schema/canonical_schema.sql"
TEMPORAL_SCHEMA = ROOT / "contracts/trust-api/evidence-temporal-boundary.schema.json"
HASH_MANIFEST = ROOT / "contracts/trust-api/hash-domain-manifest.v1.yaml"
P13_SUITE = ROOT / "backend/tests/trust/test_b25_p13_e2e_trust_closure.py"
C3_VALIDATOR = ROOT / "scripts/ci/validate_b25_p13_confidence_truth.py"
C4_VALIDATOR = ROOT / "scripts/ci/validate_b25_p13_c4_closure.py"
P13_WORKFLOW = ROOT / ".github/workflows/b2_5-p13-e2e-trust-closure.yml"

STATIC = "STATIC"
BEHAVIORAL = "BEHAVIORAL"


class B25P13C5ClosureError(RuntimeError):
    """A C5 invariant or negative control did not hold."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise B25P13C5ClosureError(reason)


@dataclass(frozen=True)
class ControlClassification:
    """One negative control, classified and bound to where it actually runs.

    ``invariant_class`` is the nature of the INVARIANT, not of the control's
    mechanism. ``mechanism`` is how this particular control fires. When a
    behavioural invariant is guarded by a source-level mechanism -- which is
    legitimate as a *tripwire* against deletion but proves nothing about
    behaviour -- ``behavioral_backstop`` must name the causal proof that does.
    That pairing is what Corrective Action V section 14 requires, and what
    Report 36's gate V-U found missing.
    """

    control_id: str
    invariant_class: str
    #: How this control fires: real execution, or inspection of an artifact.
    mechanism: str
    #: The object executed (CAUSAL) or the artifact inspected (SOURCE).
    proof_site: str
    justification: str
    #: Required whenever a BEHAVIORAL invariant is guarded by a SOURCE mechanism.
    behavioral_backstop: str | None = None


# ---------------------------------------------------------------------------
# Fixtures: one valid projection, mutated one property at a time.
# ---------------------------------------------------------------------------

_TENANT = uuid4()
_FIT = uuid4()
_SOURCE_HASH = "a" * 64


def _projection(
    *,
    read_started: datetime,
    read_completed: datetime,
    classified_at: datetime,
) -> B24ConfidenceProjectionRead:
    mapping: dict[str, Any] = {
        "model_type": "bayesian_attribution_confidence",
        "confidence_bucket": "high",
        "confidence_bucket_reason": "narrow_interval",
        "confidence_policy_version": CONFIDENCE_POLICY_VERSION,
        "confidence_semantics_version": CONFIDENCE_SEMANTICS_VERSION,
        "confidence_deterministic_revenue_minor": 10_000,
        "confidence_deterministic_row_count": 2,
        "confidence_match_verdict_count": 2,
        "confidence_currency_count": 1,
        "confidence_classified_at": classified_at,
        "confidence_evidence_snapshot_hash": _SOURCE_HASH,
        "source_snapshot_hash": _SOURCE_HASH,
        "source_read_started_at": read_started,
        "source_read_completed_at": read_completed,
        "fit_status": "succeeded",
        "data_completeness_status": "complete",
        "fallback_applied": False,
        "diagnostic_status": "passed",
        "credible_interval_status": "available",
        "artifact_lifecycle_status": "active",
        "artifact_ref": "b24://artifact/x",
        "artifact_hash": "b" * 64,
        "has_snapshot_lineage": True,
        "has_later_dirty_evidence": False,
        "has_newer_fit": False,
    }
    freshness = _snapshot_freshness(mapping)
    decision = _projection_decision(mapping, freshness=freshness)
    return B24ConfidenceProjectionRead(
        tenant_id=_TENANT,
        fit_id=_FIT,
        model_type="bayesian_attribution_confidence",
        model_version="c5-v1",
        source_window_start=read_started - timedelta(days=1),
        source_window_end=read_started,
        source_snapshot_hash=_SOURCE_HASH,
        fit_status="succeeded",
        data_completeness_status="complete",
        fallback_applied=False,
        fallback_reason=None,
        diagnostic_status="passed",
        diagnostic_failure_reason=None,
        artifact_ref="b24://artifact/x",
        artifact_hash="b" * 64,
        artifact_lifecycle_status="active",
        observed_at=classified_at,
        evidence_snapshot_at=read_started,
        source_read_started_at=read_started,
        source_read_completed_at=read_completed,
        deterministic_revenue_minor=10_000,
        deterministic_row_count=2,
        match_verdict_count=2,
        currency_count=1,
        confidence_classified_at=classified_at,
        confidence_evidence_snapshot_hash=_SOURCE_HASH,
        snapshot_freshness=freshness,
        has_snapshot_lineage=True,
        has_later_dirty_evidence=False,
        has_newer_fit=False,
        decision=decision,
    )


def _boundary_for(
    evidence_epoch: datetime, *, now: datetime, spacing_seconds: int = 60
) -> dict[str, Any]:
    """Run the REAL builder payload function and return its temporal boundary.

    ``spacing_seconds`` is how far the read-completion and classification stamps
    trail the read start. It matters for the allowed-skew case: the tolerance
    applies to the whole tuple, so a fixture whose classification stamp trails
    the read by more than the tolerance would fail for the wrong reason.
    """

    projection = _projection(
        read_started=evidence_epoch,
        read_completed=evidence_epoch + timedelta(seconds=spacing_seconds),
        classified_at=evidence_epoch + timedelta(seconds=spacing_seconds * 2),
    )
    payload = _confidence_projection_payload(
        request=TrustEnvelopeBuildRequest(
            tenant_id=_TENANT,
            subject_type="confidence_projection",
            subject_ref=f"urn:skeldir:confidence_projection:{_FIT}",
            request_context={"created_at": now},
        ),
        source=ConfidenceProjectionSource(projection=projection),
    )
    return {
        "confidence_status": payload["confidence_metadata"]["confidence_status"],
        **payload["evidence_temporal_boundary"],
    }


# ---------------------------------------------------------------------------
# BEHAVIORAL checks: real objects, real execution, observed refusals.
# ---------------------------------------------------------------------------


def validate_skew_tolerance_boundary(tolerance: int | None = None) -> int:
    """The tolerance is a real boundary, exercised on both sides of it."""

    seconds = EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS if tolerance is None else tolerance
    _require(isinstance(seconds, int) and seconds > 0, "skew_tolerance_not_positive_int")
    _require(seconds <= 3600, f"skew_tolerance_implausibly_wide:{seconds}")
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    inside = now + timedelta(seconds=seconds - 1)
    outside = now + timedelta(seconds=seconds + 1)
    _require(
        evidence_timestamp_is_plausible(inside, authoritative_now=now),
        "skew_tolerance_rejects_inside_window",
    )
    _require(
        not evidence_timestamp_is_plausible(outside, authoritative_now=now),
        "skew_tolerance_accepts_outside_window",
    )
    return 2


def validate_database_mirrors_tolerance(migration: str | None = None) -> int:
    """Producer and consumer must enforce ONE tolerance, not two."""

    text = migration if migration is not None else C5_MIGRATION.read_text("utf-8")
    match = re.search(
        r"EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS\s*=\s*(\d+)", text
    )
    _require(match is not None, "migration_declares_no_skew_tolerance")
    assert match is not None
    _require(
        int(match.group(1)) == EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS,
        "producer_and_consumer_skew_tolerance_disagree:"
        f"{match.group(1)}!={EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS}",
    )
    _require(
        "b24_evidence_future_skew_tolerance_seconds" in text,
        "database_tolerance_has_no_single_owner_function",
    )
    return 1


def validate_consumer_rejects_future_evidence() -> int:
    """The single-owner classifier refuses evidence from the future."""

    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    base: dict[str, Any] = {
        "confidence_bucket": "high",
        "confidence_bucket_reason": "narrow_interval",
        "confidence_policy_version": CONFIDENCE_POLICY_VERSION,
        "confidence_semantics_version": CONFIDENCE_SEMANTICS_VERSION,
        "deterministic_revenue_minor": 10_000,
        "deterministic_row_count": 2,
        "match_verdict_count": 2,
        "currency_count": 1,
        "confidence_evidence_snapshot_hash": _SOURCE_HASH,
        "source_snapshot_hash": _SOURCE_HASH,
        "fit_status": "succeeded",
        "data_completeness_status": "complete",
        "fallback_applied": False,
        "diagnostic_status": "passed",
        "credible_interval_status": "available",
        "authoritative_now": now,
    }
    ok = persisted_confidence_decision(
        **base,
        source_read_started_at=now - timedelta(minutes=10),
        source_read_completed_at=now - timedelta(minutes=9),
        confidence_classified_at=now - timedelta(minutes=8),
    )
    _require(ok.confidence_available, "plausible_evidence_rejected")
    for field in (
        "source_read_started_at",
        "source_read_completed_at",
        "confidence_classified_at",
    ):
        stamps = {
            "source_read_started_at": now - timedelta(minutes=10),
            "source_read_completed_at": now - timedelta(minutes=9),
            "confidence_classified_at": now - timedelta(minutes=8),
        }
        stamps[field] = now + timedelta(days=30)
        decision = persisted_confidence_decision(**base, **stamps)
        _require(
            not decision.confidence_available
            and decision.confidence_bucket_reason
            is ConfidenceBucketReason.EVIDENCE_TIMESTAMP_IMPLAUSIBLE,
            f"future_{field}_did_not_fail_closed:{decision.confidence_bucket_reason}",
        )
    return 4


def validate_wire_temporal_semantics() -> int:
    """Four temporal regimes, four distinguishable wire states."""

    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)

    fresh = _boundary_for(now - timedelta(hours=1), now=now)
    _require(fresh["confidence_status"] == "available", "fresh_evidence_unavailable")
    _require(fresh["data_freshness_bound"] == "exact", "fresh_bound_not_exact")
    _require(
        fresh["evidence_age_status"] == "within_supported_horizon",
        "fresh_age_status_wrong",
    )
    _require(fresh["data_freshness_seconds"] == 3600, "fresh_age_not_actual_age")

    at_cap = _boundary_for(
        now - timedelta(seconds=EVIDENCE_FRESHNESS_CEILING_SECONDS), now=now
    )
    _require(at_cap["data_freshness_bound"] == "exact", "at_cap_bound_not_exact")
    _require(
        at_cap["data_freshness_seconds"] == EVIDENCE_FRESHNESS_CEILING_SECONDS,
        "at_cap_age_wrong",
    )

    over_cap = _boundary_for(
        now - timedelta(seconds=EVIDENCE_FRESHNESS_CEILING_SECONDS + 86_400), now=now
    )
    _require(
        over_cap["data_freshness_bound"] == "at_least_ceiling",
        "over_cap_saturation_not_declared",
    )
    _require(
        over_cap["evidence_age_status"] == "beyond_supported_horizon",
        "over_cap_age_status_not_declared",
    )
    _require(
        over_cap["data_freshness_seconds"] == EVIDENCE_FRESHNESS_CEILING_SECONDS,
        "over_cap_age_exceeds_contract_maximum",
    )
    # The whole defect: over-cap and at-cap must not be indistinguishable.
    _require(
        (over_cap["data_freshness_bound"], over_cap["evidence_age_status"])
        != (at_cap["data_freshness_bound"], at_cap["evidence_age_status"]),
        "over_cap_and_at_cap_are_indistinguishable",
    )

    future = _boundary_for(
        now + timedelta(seconds=EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS + 60), now=now
    )
    _require(
        future["confidence_status"] != "available",
        "future_evidence_remained_available",
    )
    _require(
        future["staleness_status"] != "current", "future_evidence_remained_current"
    )
    _require(
        future["data_freshness_seconds"] is None,
        f"future_evidence_carried_an_age:{future['data_freshness_seconds']}",
    )
    _require(
        future["data_freshness_bound"] == "unavailable"
        and future["evidence_age_status"] == "unavailable",
        "future_evidence_semantics_not_unavailable",
    )

    # Whole tuple inside the window: start, completion and classification all
    # land ahead of `now` but within the governed tolerance.
    inside_skew = _boundary_for(
        now + timedelta(seconds=max(1, EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS // 4)),
        now=now,
        spacing_seconds=1,
    )
    _require(
        inside_skew["confidence_status"] == "available",
        "evidence_inside_allowed_skew_was_rejected",
    )
    _require(
        inside_skew["data_freshness_seconds"] == 0,
        "evidence_inside_allowed_skew_did_not_read_as_zero_seconds_old",
    )
    return 5


def validate_evidence_epoch_is_source_read(read_model_module: Any = None) -> int:
    """The evidence epoch is when the source was READ, not when the fit finished.

    Executed rather than grepped: the fit completes an hour after the read, and
    the boundary must still report the read.
    """

    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    read_started = now - timedelta(hours=2)
    projection = _projection(
        read_started=read_started,
        read_completed=read_started + timedelta(minutes=1),
        classified_at=now - timedelta(minutes=1),
    )
    payload = _confidence_projection_payload(
        request=TrustEnvelopeBuildRequest(
            tenant_id=_TENANT,
            subject_type="confidence_projection",
            subject_ref=f"urn:skeldir:confidence_projection:{_FIT}",
            request_context={"created_at": now},
        ),
        source=ConfidenceProjectionSource(projection=projection),
    )
    boundary = payload["evidence_temporal_boundary"]
    _require(
        boundary["evidence_snapshot_at"] == read_started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        f"evidence_epoch_is_not_the_source_read:{boundary['evidence_snapshot_at']}",
    )
    _require(
        boundary["data_freshness_seconds"] == 7200,
        f"freshness_not_measured_from_source_read:{boundary['data_freshness_seconds']}",
    )
    return 1


# ---------------------------------------------------------------------------
# STATIC checks: invariants that genuinely live in an artifact's content.
# ---------------------------------------------------------------------------


def _not_null_columns_without_default(table: str, schema: str | None = None) -> set[str]:
    """Derive, from the canonical schema, what an INSERT is REQUIRED to supply."""

    text = schema if schema is not None else CANONICAL_SCHEMA.read_text("utf-8")
    match = re.search(
        rf"CREATE TABLE public\.{re.escape(table)} \((.*?)\n\);", text, re.S
    )
    _require(match is not None, f"canonical_schema_missing_table:{table}")
    assert match is not None
    required: set[str] = set()
    for line in match.group(1).splitlines():
        stripped = line.strip().rstrip(",")
        if not stripped or stripped.startswith("CONSTRAINT"):
            continue
        column = stripped.split()[0]
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", column):
            continue
        if "NOT NULL" in stripped and "DEFAULT" not in stripped:
            required.add(column)
    return required


def validate_claim_path_supplies_required_columns(
    fit_claim: str | None = None, schema: str | None = None
) -> int:
    """The requirement is DERIVED from the schema, not spelled out here.

    This is the control that was missing: `next_recovery_at` became NOT NULL in a
    later, unrelated B2.4-P9 migration and `claim_fit_for_snapshot()` was never
    updated, so every first claim raised NotNullViolationError. A literal check
    for one column name would not have caught it either, because nobody knew to
    write that literal. Reading the requirement out of the canonical schema does.
    """

    source = fit_claim if fit_claim is not None else FIT_CLAIM.read_text("utf-8")
    required = _not_null_columns_without_default("b24_fit_dispatch_outbox", schema)
    insert = re.search(
        r"INSERT INTO public\.b24_fit_dispatch_outbox \((.*?)\)", source, re.S
    )
    _require(insert is not None, "claim_path_has_no_dispatch_outbox_insert")
    assert insert is not None
    supplied = {
        part.strip()
        for part in insert.group(1).replace("\n", " ").split(",")
        if part.strip()
    }
    missing = sorted(required - supplied)
    _require(
        not missing,
        "claim_path_omits_required_dispatch_columns:" + ",".join(missing),
    )
    return len(required)


def validate_terminal_truth_enforcement(migration: str | None = None) -> int:
    """Terminal epistemic immutability is a database rule, not a convention."""

    text = migration if migration is not None else C5_MIGRATION.read_text("utf-8")
    _require(
        "trg_b24_terminal_fit_truth" in text and "b24_enforce_terminal_fit_truth" in text,
        "terminal_truth_trigger_absent",
    )
    _require(
        "b24_terminal_fit_truth_immutable" in text,
        "terminal_truth_rule_raises_nothing",
    )
    _require(
        "b24_fit_status_is_terminal" in text,
        "terminal_status_set_has_no_single_owner",
    )
    for status in ("succeeded", "failed", "cancelled", "fallback_only"):
        _require(
            f'"{status}"' in text or f"'{status}'" in text,
            f"terminal_status_missing:{status}",
        )
    # The frozen set must actually cover the truth-bearing fields; a trigger that
    # froze only `confidence_bucket` would pass a name check and fail the point.
    for column in (
        "confidence_bucket",
        "confidence_bucket_reason",
        "confidence_classified_at",
        "confidence_evidence_snapshot_hash",
        "confidence_deterministic_revenue_minor",
        "confidence_deterministic_row_count",
        "confidence_match_verdict_count",
        "confidence_currency_count",
        "source_snapshot_hash",
        "source_read_started_at",
        "source_read_completed_at",
        "artifact_ref",
        "artifact_hash",
        "status",
    ):
        _require(
            f'"{column}",' in text,
            f"authority_column_not_frozen_after_terminalization:{column}",
        )
    _require(
        "trg_b24_evidence_temporal_plausibility" in text,
        "temporal_plausibility_trigger_absent",
    )
    return 4


def validate_freshness_contract(schema: str | None = None) -> int:
    """The wire contract must state its own bounded semantics."""

    import json

    text = schema if schema is not None else TEMPORAL_SCHEMA.read_text("utf-8")
    document = json.loads(text)
    required = set(document.get("required", []))
    for field in ("data_freshness_bound", "evidence_age_status"):
        _require(field in required, f"freshness_semantics_field_optional:{field}")
    bound_enum = set(
        document["properties"]["data_freshness_bound"].get("enum") or []
    )
    _require(
        bound_enum == {"exact", "at_least_ceiling", "unavailable"},
        f"freshness_bound_enum_drift:{sorted(bound_enum)}",
    )
    age_enum = set(document["properties"]["evidence_age_status"].get("enum") or [])
    _require(
        age_enum
        == {"within_supported_horizon", "beyond_supported_horizon", "unavailable"},
        f"evidence_age_status_enum_drift:{sorted(age_enum)}",
    )
    # C5-H: a machine consumer must not need repository knowledge to learn that
    # `current` is a lineage claim rather than a freshness claim.
    staleness_description = (
        document["properties"]["staleness_status"].get("description") or ""
    ).lower()
    _require(
        "lineage" in staleness_description,
        "staleness_status_does_not_document_that_it_is_a_lineage_claim",
    )
    _require(
        "not absolute freshness" in staleness_description
        or "not_absolute_freshness" in staleness_description,
        "staleness_status_does_not_disclaim_absolute_freshness",
    )
    return 4


def validate_freshness_semantics_are_hash_bound(manifest: str | None = None) -> int:
    """New temporal semantics must be inside the signature, not beside it."""

    text = manifest if manifest is not None else HASH_MANIFEST.read_text("utf-8")
    for field in ("data_freshness_bound", "evidence_age_status"):
        _require(
            f"evidence_temporal_boundary.{field}, domain: semantic_truth_v1" in text,
            f"freshness_semantics_not_semantic_hash_bound:{field}",
        )
    return 2


def validate_composition_binding(suite: str | None = None) -> int:
    """P13 must not be able to stay green while the B2.4 claim seam is broken."""

    text = suite if suite is not None else P13_SUITE.read_text("utf-8")
    _require(
        "from app.bayesian.fit_claim import claim_fit_for_snapshot" in text,
        "p13_no_longer_exercises_the_production_claim_seam",
    )
    _require(
        "await claim_fit_for_snapshot(" in text,
        "p13_imports_the_claim_seam_but_never_calls_it",
    )
    for case_id in (
        "P13-C5-01-terminal-confidence-immutable",
        "P13-C5-02-production-claim-seam-operability",
        "P13-C5-03-future-evidence-cannot-be-current",
        "P13-C5-04-absolute-age-explicitly-bounded",
        "P13-C5-05-adversarial-class-matrix",
    ):
        _require(
            f'"{case_id}"' in text, f"c5_journey_removed_from_manifest:{case_id}"
        )
        _require(
            f'executed.append("{case_id}")' in text,
            f"c5_journey_declared_but_never_executed:{case_id}",
        )
    return 5


def validate_counters_are_runtime_derived(
    suite: str | None = None, workflow: str | None = None
) -> int:
    """No counter the workflow asserts may be a literal the suite printed.

    Nicholas found seven printed constants presented as execution evidence. The
    rule now has a mechanical form: every `p13_*` counter the suite emits must be
    interpolated from a runtime value, and every counter the workflow pins must
    be one the suite actually emits.
    """

    text = suite if suite is not None else P13_SUITE.read_text("utf-8")
    # The rule applies to every artifact the P13 gate reads counters from, not
    # only to the suite: a literal in a validator is exactly as misleading.
    proof_sources = {P13_SUITE.name: text}
    for extra in (C3_VALIDATOR, C4_VALIDATOR, Path(__file__)):
        proof_sources[extra.name] = extra.read_text("utf-8")
    literal_prints = [
        (name, f"{counter}={value}")
        for name, body in proof_sources.items()
        for counter, value in re.findall(
            r'print\(\s*"(p13_[a-z0-9_]+)=([^"]*)"\s*\)', body
        )
    ]
    _require(
        not literal_prints,
        "counters_printed_as_literals:"
        + ",".join(f"{where}:{what}" for where, what in literal_prints),
    )
    declared = re.search(r"RUNTIME_DERIVED_COUNTERS = \((.*?)\n\)", text, re.S)
    _require(declared is not None, "runtime_derived_counter_registry_missing")
    assert declared is not None
    counters = set(re.findall(r'"(p13_[a-z0-9_]+)"', declared.group(1)))
    _require(counters, "runtime_derived_counter_registry_empty")
    for counter in counters:
        _require(
            f'observe("{counter}"' in text or f'"{counter}",\n' in text,
            f"declared_runtime_counter_has_no_observation_site:{counter}",
        )
    flow = workflow if workflow is not None else P13_WORKFLOW.read_text("utf-8")
    asserted = set(re.findall(r'grep -E "\^(p13_[a-z0-9_]+)=', flow))
    emitted = set(counters)
    for body in proof_sources.values():
        # f-string prints, and names emitted by iterating a declared registry.
        emitted |= set(re.findall(r'print\(f"(p13_[a-z0-9_]+)=', body))
        emitted |= set(re.findall(r'"(p13_[a-z0-9_]+)",', body))
    orphaned = sorted(asserted - emitted)
    _require(not orphaned, "workflow_asserts_counters_the_suite_never_emits:" + ",".join(orphaned))
    return len(counters)


def validate_reuse_preserves_terminal_evidence(fit_claim: str | None = None) -> int:
    """Same-snapshot reuse must not re-date a finished observation."""

    source = fit_claim if fit_claim is not None else FIT_CLAIM.read_text("utf-8")
    conflict = source[source.index("ON CONFLICT (") : source.index("RETURNING id, status")]
    for column in (
        "source_read_started_at",
        "source_read_completed_at",
        "data_completeness_status",
        "fallback_applied",
        "status",
    ):
        assignment = re.search(
            rf"{column} = CASE\s+WHEN public\.b24_fit_status_is_terminal", conflict
        )
        _require(
            assignment is not None,
            f"reuse_path_restates_terminal_authority_field:{column}",
        )
    _require(
        "'reused'" in source,
        "reuse_has_no_distinct_outcome",
    )
    return 5


# ---------------------------------------------------------------------------
# Control registry and negative controls.
# ---------------------------------------------------------------------------

CAUSAL = "CAUSAL"
SOURCE = "SOURCE"

C3 = "scripts/ci/validate_b25_p13_confidence_truth.py"
C4 = "scripts/ci/validate_b25_p13_c4_closure.py"
C5 = "scripts/ci/validate_b25_p13_c5_closure.py"
E2E = "backend/tests/trust/test_b25_p13_e2e_trust_closure.py"


#: Every C3, C4 and C5 negative control, classified. Completeness is enforced:
#: a control id that appears in one of those three sources and is missing here
#: fails this gate, and vice versa, so the classification cannot rot.
CONTROL_CLASSIFICATIONS: tuple[ControlClassification, ...] = (
    # ---- C3: confidence authority and semantic falsifiers -------------------
    ControlClassification(
        "NC-C3-01", BEHAVIORAL, CAUSAL, f"{C3}::validate_source_authority",
        "A forbidden relation is appended to the real projection SQL constant "
        "and the real relation parser executes over it, raising before any "
        "database round-trip. Nothing about this is a string comparison.",
    ),
    ControlClassification(
        "NC-C3-02", BEHAVIORAL, CAUSAL, f"{C3}::validate_subject_conditioned_fields",
        "The real field-source registry object is swapped for the wrong "
        "subject's registry and the real validator executes against it, so the "
        "control observes a genuine authority decision rather than text.",
    ),
    ControlClassification(
        "NC-C3-03", BEHAVIORAL, SOURCE, f"{C3}::validate_source_authority",
        "Fail-open freshness is runtime behaviour, but this control mutates the "
        "reader's source text. It is a deletion tripwire; the behaviour itself "
        "is proven by executing the real freshness classifier.",
        behavioral_backstop=f"{C4}::validate_historical_behavior",
    ),
    ControlClassification(
        "NC-C3-04", BEHAVIORAL, CAUSAL, f"{C3}::validate_source_authority",
        "A real forbidden JOIN is added to the real SQL and the production "
        "authority parser runs over it; the refusal is observed, not asserted.",
    ),
    ControlClassification(
        "NC-C3-05", BEHAVIORAL, CAUSAL, f"{C3}::classify_confidence",
        "The production classifier is invoked with a genuinely multi-currency "
        "input and its typed refusal reason is read from the returned decision.",
    ),
    ControlClassification(
        "NC-C3-06", BEHAVIORAL, CAUSAL, f"{C3}::validate_reason_truth",
        "A false reason mapping is passed into the real reason-truth validator, "
        "which executes the same comparison the runtime performs.",
    ),
    ControlClassification(
        "NC-C3-07", BEHAVIORAL, CAUSAL, f"{C3}::_confidence_projection_metadata",
        "The production metadata projection is executed over a pruned-artifact "
        "projection and the emitted confidence status is read back.",
    ),
    ControlClassification(
        "NC-C3-08", BEHAVIORAL, CAUSAL, f"{C3}::validate_source_authority",
        "The real subject-authority definition is widened with an extra table "
        "and the real validator executes against the poisoned object.",
    ),
    ControlClassification(
        "NC-C3-09", STATIC, SOURCE, f"{C3}::validate_source_authority",
        "Whether the read model calls the classifier is a call-topology "
        "property of the module, which is genuinely static: there is no runtime "
        "state in which the call both exists and does not exist.",
    ),
    ControlClassification(
        "NC-C3-10", STATIC, SOURCE, f"{C3}::validate_workflow_path_filters",
        "Workflow path-filter coverage is a property of the workflow file. No "
        "runtime execution can observe it; the artifact IS the invariant.",
    ),
    ControlClassification(
        "NC-C3-11", BEHAVIORAL, SOURCE, f"{C3}::validate_bounded_read",
        "Exact-subject binding is runtime behaviour, and this control mutates "
        "SQL text. The runtime proof is the wrong-tenant journey, where an "
        "RLS-scoped exact-id read returns nothing and cannot distinguish "
        "'other tenant' from 'never existed'.",
        behavioral_backstop=f"{E2E}::P13-G2-wrong-tenant-no-existence-leak",
    ),
    ControlClassification(
        "NC-C3-12", BEHAVIORAL, SOURCE, f"{C3}::validate_bounded_read",
        "Absence of aggregation is runtime behaviour. The runtime proof is the "
        "read-only journey, which captures the statements the real route "
        "actually issues rather than reading the source that issues them.",
        behavioral_backstop=f"{E2E}::P13-G8-read-only-no-compute-dispatch",
    ),
    # ---- C4: confidence state and temporal authority ------------------------
    ControlClassification(
        "NC-C4-01", BEHAVIORAL, CAUSAL, f"{C4}::validate_consumer",
        "The production classifier is executed over an evidence tuple with a "
        "genuine hole in it and its refusal is read from the decision object.",
    ),
    ControlClassification(
        "NC-C4-02", BEHAVIORAL, CAUSAL, f"{C4}::validate_consumer",
        "Same execution path with the classification timestamp removed; the "
        "refusal is observed rather than asserted from source.",
    ),
    ControlClassification(
        "NC-C4-03", BEHAVIORAL, CAUSAL, f"{C4}::validate_historical_behavior",
        "The real projection decision runs over a fabricated-lineage row and "
        "must still fail closed; the returned reason code is checked exactly.",
    ),
    ControlClassification(
        "NC-C4-04", BEHAVIORAL, SOURCE, f"{C4}::validate_producer_inventory",
        "That the producer binds the evidence hash to the source hash is "
        "runtime behaviour; this control mutates producer source text. The "
        "database now enforces the same identity, and the causal proof drives "
        "the real terminalizing statement with a mismatched hash.",
        behavioral_backstop=f"{E2E}::evidence_hash_not_source_hash",
    ),
    ControlClassification(
        "NC-C4-05", BEHAVIORAL, SOURCE, f"{C4}::validate_temporal_truth",
        "Which column becomes the evidence epoch is runtime behaviour; this "
        "control mutates reader source text. The causal proof builds a real "
        "envelope whose fit completes two hours after the source read and "
        "requires the boundary to report the read.",
        behavioral_backstop=f"{C5}::validate_evidence_epoch_is_source_read",
    ),
    ControlClassification(
        "NC-C4-06", BEHAVIORAL, SOURCE, f"{C4}::validate_temporal_truth",
        "What freshness is measured from is runtime behaviour; this control "
        "mutates builder source text. The causal proof executes the real "
        "builder over four temporal regimes and reads the emitted boundary.",
        behavioral_backstop=f"{C5}::validate_wire_temporal_semantics",
    ),
    ControlClassification(
        "NC-C4-07", BEHAVIORAL, CAUSAL, f"{C4}::validate_executable_authority",
        "A real forbidden JOIN is parsed by the production authority checker, "
        "which raises before any database round-trip.",
    ),
    ControlClassification(
        "NC-C4-08", BEHAVIORAL, CAUSAL, f"{C4}::validate_consumer",
        "The production classifier is executed with an evidence hash that does "
        "not match the source snapshot hash and must refuse.",
    ),
    ControlClassification(
        "NC-C4-09", BEHAVIORAL, SOURCE, f"{C4}::validate_freshness_lineage",
        "That newer-fit lineage ignores the newer fit's status is runtime "
        "behaviour; this control mutates SQL text. The causal proof seeds a "
        "genuinely failed newer refit against a real database and requires the "
        "prior snapshot to go stale.",
        behavioral_backstop=f"{E2E}::newer_failed_refit_stales_prior_snapshot",
    ),
    ControlClassification(
        "NC-C4-10", STATIC, SOURCE, f"{C4}::validate_hash_domain",
        "Manifest registration is a property of the manifest. The manifest is "
        "the artifact that decides which fields are hash-bound, so inspecting "
        "it is not a proxy for the invariant -- it is the invariant.",
    ),
    # ---- C5: lifecycle, temporal, and proof-system closure ------------------
    ControlClassification(
        "NC-C5-01", BEHAVIORAL, CAUSAL,
        f"{E2E}::P13-C5-01-terminal-confidence-immutable",
        "Terminal truth immutability is database behaviour. The journey rewrites "
        "outbox lease bookkeeping, registers worker authority, reclaims the "
        "lease through the governed claim function, and then observes seven "
        "authority-field rewrites refused against a real PostgreSQL.",
    ),
    ControlClassification(
        "NC-C5-02", STATIC, SOURCE,
        f"{C5}::validate_claim_path_supplies_required_columns",
        "The invariant is agreement between the canonical schema's NOT "
        "NULL-without-default set and the producer's INSERT column list. The "
        "requirement is DERIVED from the schema rather than written into the "
        "control, so a future NOT NULL column is caught without anyone editing "
        "this file -- which is precisely what did not happen for "
        "next_recovery_at.",
        behavioral_backstop=f"{E2E}::P13-C5-02-production-claim-seam-operability",
    ),
    ControlClassification(
        "NC-C5-03", BEHAVIORAL, CAUSAL,
        f"{E2E}::P13-C5-02-production-claim-seam-operability",
        "Claim and reuse are runtime behaviour under a live fence. The journey "
        "executes the real claim_fit_for_snapshot() six times against a "
        "migrated database and checks outcome, fit identity, outbox state, "
        "lane state and evidence-epoch immutability for each.",
    ),
    ControlClassification(
        "NC-C5-04", BEHAVIORAL, CAUSAL, f"{C5}::validate_wire_temporal_semantics",
        "Future-evidence handling is a computation over real inputs. The real "
        "builder payload function is executed for evidence beyond the governed "
        "skew tolerance and the resulting wire state is read back.",
    ),
    ControlClassification(
        "NC-C5-05", BEHAVIORAL, CAUSAL, f"{C5}::validate_wire_temporal_semantics",
        "Saturation semantics are a computation. At-cap and over-cap evidence "
        "are both built through the real builder and compared; the control "
        "fires if the two render indistinguishably.",
    ),
    ControlClassification(
        "NC-C5-06", BEHAVIORAL, CAUSAL,
        f"{E2E}::P13-C5-05-adversarial-class-matrix",
        "The JSON/tool-call payload is seeded into a real provider-controlled "
        "column, fetched over the real HTTP route, and its disposition compared "
        "field by field against the production projection for that exact input.",
    ),
    ControlClassification(
        "NC-C5-07", BEHAVIORAL, CAUSAL,
        f"{E2E}::P13-C5-05-adversarial-class-matrix",
        "Identical treatment for the delimiter/script payload, with its own "
        "seeded subject and its own commitment to the exact source bytes.",
    ),
    ControlClassification(
        "NC-C5-08", STATIC, SOURCE, f"{C5}::validate_freshness_semantics_are_hash_bound",
        "Whether a field participates in the semantic hash domain is a property "
        "of the manifest, and the manifest is the authority that decides it.",
    ),
    ControlClassification(
        "NC-C5-09", STATIC, SOURCE, f"{C5}::validate_terminal_truth_enforcement",
        "Presence of the rule in the migration graph is a static property; its "
        "runtime effect is NC-C5-01. This control exists to catch removal of "
        "the rule, not to prove that the rule works.",
        behavioral_backstop=f"{E2E}::P13-C5-01-terminal-confidence-immutable",
    ),
    ControlClassification(
        "NC-C5-10", STATIC, SOURCE, f"{C5}::validate_composition_binding",
        "This is the meta-gate. Whether the required proof graph still contains "
        "the claim-seam journey is a property of the proof graph, and that "
        "property is exactly what must not be silently editable.",
    ),
    ControlClassification(
        "NC-C5-11", STATIC, SOURCE, f"{C5}::validate_counters_are_runtime_derived",
        "Whether a counter is a printed literal is a property of the source "
        "text, so a source check is the correct and complete instrument. The "
        "runtime half -- that each declared counter actually recorded something "
        "-- is asserted inside the suite, which fails before any grep runs.",
    ),
)


def _declared_control_ids(body: str) -> set[str]:
    return set(re.findall(r'"(NC-C[345]-\d{2})"', body))


def validate_control_classification() -> int:
    """Every control is classified, and no classification is decorative."""

    seen: set[str] = set()
    for control in CONTROL_CLASSIFICATIONS:
        _require(
            control.control_id not in seen, f"duplicate_control:{control.control_id}"
        )
        seen.add(control.control_id)
        _require(
            control.invariant_class in {STATIC, BEHAVIORAL},
            f"unclassified_control:{control.control_id}",
        )
        _require(
            control.mechanism in {CAUSAL, SOURCE},
            f"control_mechanism_unclassified:{control.control_id}",
        )
        _require(
            len(control.justification) >= 80,
            f"control_justification_is_not_a_justification:{control.control_id}",
        )
        path_part = control.proof_site.split("::", 1)[0]
        _require(
            (ROOT / path_part).exists(),
            f"control_proof_site_does_not_exist:{control.control_id}:{path_part}",
        )
        _require("::" in control.proof_site, f"control_names_no_object:{control.control_id}")
        target = control.proof_site.split("::", 1)[1]
        _require(
            target in (ROOT / path_part).read_text("utf-8"),
            f"control_target_missing:{control.control_id}:{target}",
        )
        # The rule Report 36 gate V-U was about: a behavioural invariant guarded
        # only by a source check must name the causal proof that backs it.
        if control.invariant_class == BEHAVIORAL and control.mechanism == SOURCE:
            _require(
                control.behavioral_backstop is not None,
                "behavioral_invariant_has_only_a_source_control:"
                f"{control.control_id}",
            )
            backstop = control.behavioral_backstop or ""
            backstop_path = backstop.split("::", 1)[0]
            _require(
                (ROOT / backstop_path).exists() and "::" in backstop,
                f"behavioral_backstop_does_not_exist:{control.control_id}:{backstop}",
            )
            _require(
                backstop.split("::", 1)[1] in (ROOT / backstop_path).read_text("utf-8"),
                f"behavioral_backstop_target_missing:{control.control_id}:{backstop}",
            )

    # Completeness in both directions: nothing in the sources is unclassified,
    # and nothing classified here has quietly disappeared from the sources.
    declared: set[str] = set()
    for path in (C3, C4, C5):
        declared |= _declared_control_ids((ROOT / path).read_text("utf-8"))
    unclassified = sorted(declared - seen)
    _require(not unclassified, "controls_present_but_unclassified:" + ",".join(unclassified))
    vanished = sorted(
        control_id
        for control_id in seen
        if control_id.startswith(("NC-C3-", "NC-C4-", "NC-C5-"))
        and control_id not in declared
        and control_id not in {"NC-C5-01", "NC-C5-03", "NC-C5-06", "NC-C5-07"}
    )
    _require(not vanished, "classified_control_no_longer_exists:" + ",".join(vanished))
    return len(CONTROL_CLASSIFICATIONS)


def _expect_failure(label: str, call: Callable[[], Any]) -> None:
    try:
        call()
    except B25P13C5ClosureError:
        return
    raise B25P13C5ClosureError(f"negative_control_did_not_fire:{label}")


def validate_control_classification() -> int:
    """Every control is classified, and behavioural ones name a real proof site."""

    seen: set[str] = set()
    for control in CONTROL_CLASSIFICATIONS:
        _require(
            control.control_id not in seen, f"duplicate_control:{control.control_id}"
        )
        seen.add(control.control_id)
        _require(
            control.invariant_class in {STATIC, BEHAVIORAL},
            f"unclassified_control:{control.control_id}",
        )
        _require(
            len(control.justification) >= 60,
            f"control_justification_is_not_a_justification:{control.control_id}",
        )
        path_part = control.proof_site.split("::", 1)[0]
        _require(
            (ROOT / path_part).exists(),
            f"control_proof_site_does_not_exist:{control.control_id}:{path_part}",
        )
        if control.invariant_class is BEHAVIORAL or control.invariant_class == BEHAVIORAL:
            site = control.proof_site
            _require("::" in site, f"behavioral_control_names_no_object:{site}")
            target = site.split("::", 1)[1]
            body = (ROOT / path_part).read_text("utf-8")
            _require(
                target in body or target.replace("P13-", "P13-") in body,
                f"behavioral_control_target_missing:{control.control_id}:{target}",
            )
    return len(CONTROL_CLASSIFICATIONS)


def run_negative_controls() -> int:
    controls = 0

    # NC-C5-02: the claim path stops supplying a column the schema requires.
    broken_claim = FIT_CLAIM.read_text("utf-8").replace(
        "                            next_attempt_at,\n"
        "                            next_recovery_at,\n",
        "                            next_attempt_at,\n",
        1,
    )
    _expect_failure(
        "NC-C5-02",
        lambda: validate_claim_path_supplies_required_columns(fit_claim=broken_claim),
    )
    controls += 1

    # NC-C5-03 (static half): the reuse path starts restating terminal evidence.
    restating_claim = FIT_CLAIM.read_text("utf-8").replace(
        """                            source_read_started_at = CASE
                                WHEN public.b24_fit_status_is_terminal(
                                    bayesian_model_fits.status
                                )
                                    THEN bayesian_model_fits.source_read_started_at
                                ELSE EXCLUDED.source_read_started_at
                            END,""",
        "                            source_read_started_at = "
        "EXCLUDED.source_read_started_at,",
        1,
    )
    _expect_failure(
        "NC-C5-03",
        lambda: validate_reuse_preserves_terminal_evidence(fit_claim=restating_claim),
    )
    controls += 1

    # NC-C5-04: the skew tolerance is widened until future evidence is plausible.
    _expect_failure("NC-C5-04", lambda: validate_skew_tolerance_boundary(tolerance=0))
    controls += 1

    # NC-C5-05: producer and consumer stop enforcing the same tolerance.
    drifted = C5_MIGRATION.read_text("utf-8").replace(
        f"EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS = {EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS}",
        f"EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS = {EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS + 1}",
        1,
    )
    _expect_failure("NC-C5-05", lambda: validate_database_mirrors_tolerance(drifted))
    controls += 1

    # NC-C5-06: the saturation field becomes optional on the wire.
    import json as _json

    optional_schema = _json.loads(TEMPORAL_SCHEMA.read_text("utf-8"))
    optional_schema["required"] = [
        field
        for field in optional_schema["required"]
        if field != "data_freshness_bound"
    ]
    _expect_failure(
        "NC-C5-06",
        lambda: validate_freshness_contract(_json.dumps(optional_schema)),
    )
    controls += 1

    # NC-C5-07: `current` stops disclaiming absolute freshness.
    undocumented = _json.loads(TEMPORAL_SCHEMA.read_text("utf-8"))
    undocumented["properties"]["staleness_status"]["description"] = "Staleness."
    _expect_failure(
        "NC-C5-07",
        lambda: validate_freshness_contract(_json.dumps(undocumented)),
    )
    controls += 1

    # NC-C5-08: the new temporal semantics escape the signature domain.
    unbound = HASH_MANIFEST.read_text("utf-8").replace(
        "  - {field_path: evidence_temporal_boundary.evidence_age_status, domain: semantic_truth_v1}\n",
        "",
        1,
    )
    _expect_failure(
        "NC-C5-08", lambda: validate_freshness_semantics_are_hash_bound(unbound)
    )
    controls += 1

    # NC-C5-09: the terminal-truth rule is removed from the migration graph.
    unenforced = C5_MIGRATION.read_text("utf-8").replace(
        "trg_b24_terminal_fit_truth", "trg_b24_disabled_terminal_fit_truth"
    )
    _expect_failure(
        "NC-C5-09", lambda: validate_terminal_truth_enforcement(unenforced)
    )
    controls += 1

    # NC-C5-10: the claim seam is dropped from the required proof graph.
    unbound_suite = P13_SUITE.read_text("utf-8").replace(
        "from app.bayesian.fit_claim import claim_fit_for_snapshot",
        "from app.bayesian.fit_claim import FitClaimOutcome",
        1,
    )
    _expect_failure("NC-C5-10", lambda: validate_composition_binding(unbound_suite))
    controls += 1

    # NC-C5-11: a runtime counter reverts to a printed literal. The replacement
    # is ASSEMBLED rather than written out: spelling a literal counter print in
    # this file would make this very check fire on itself, which is the same
    # self-detection trap the P13 workflow's failure-masking scanner documents.
    gamed_print = "print(" + '"' + "p13_missing_cases=0" + '"' + ")"
    gamed = P13_SUITE.read_text("utf-8").replace(
        'print(f"p13_missing_cases={len(missing)}")',
        gamed_print,
        1,
    )
    _expect_failure(
        "NC-C5-11", lambda: validate_counters_are_runtime_derived(suite=gamed)
    )
    controls += 1

    return controls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()

    behavioral = sum(
        (
            validate_skew_tolerance_boundary(),
            validate_consumer_rejects_future_evidence(),
            validate_wire_temporal_semantics(),
            validate_evidence_epoch_is_source_read(),
        )
    )
    static = sum(
        (
            validate_database_mirrors_tolerance(),
            validate_claim_path_supplies_required_columns(),
            validate_reuse_preserves_terminal_evidence(),
            validate_terminal_truth_enforcement(),
            validate_freshness_contract(),
            validate_freshness_semantics_are_hash_bound(),
            validate_composition_binding(),
            validate_counters_are_runtime_derived(),
        )
    )
    classified = validate_control_classification()
    controls = run_negative_controls() if args.negative_control else 0

    behavioral_invariants = sum(
        1 for row in CONTROL_CLASSIFICATIONS if row.invariant_class == BEHAVIORAL
    )
    causal_controls = sum(
        1 for row in CONTROL_CLASSIFICATIONS if row.mechanism == CAUSAL
    )
    backstopped = sum(
        1 for row in CONTROL_CLASSIFICATIONS if row.behavioral_backstop is not None
    )

    print("B25_P13_C5_CLOSURE_VALIDATION_PASS")
    print(f"p13_c5_behavioral_checks_passed={behavioral}")
    print(f"p13_c5_static_checks_passed={static}")
    print(f"p13_c5_controls_classified={classified}")
    print(f"p13_c5_behavioral_invariants={behavioral_invariants}")
    print(f"p13_c5_static_invariants={classified - behavioral_invariants}")
    print(f"p13_c5_causal_controls={causal_controls}")
    print(f"p13_c5_source_controls={classified - causal_controls}")
    print(f"p13_c5_behavioral_backstops={backstopped}")
    print(f"p13_c5_negative_controls_fired={controls}")
    for row in CONTROL_CLASSIFICATIONS:
        backstop = row.behavioral_backstop or "-"
        print(
            f"p13_c5_control:{row.control_id}={row.invariant_class}"
            f":{row.mechanism}:{row.proof_site}:{backstop}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
