"""B2.5-P5 unsigned read-only TrustEnvelope payload builder."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.confidence_projection.policy import (
    EVIDENCE_FRESHNESS_CEILING_SECONDS,
    evidence_timestamp_is_plausible,
)
from app.trust.benchmark_defaults import unavailable_benchmark_metadata
from app.trust.canonicalization import canonicalize_envelope_payload
from app.trust.hash_identity import compute_semantic_truth_hash, compute_signature_hash
from app.trust.issuance_authority_ledger import (
    IssuanceAuthorityLedgerError,
    mint_build_witness_authority,
    redeem_build_witness_authority,
)
from app.trust.money_source_adapter import (
    AuthoritativeMoneyMinor,
    MoneyAuthorityDecision,
    resolve_authoritative_money,
)
from app.trust.policy_defaults import read_only_policy_authority
from app.trust.provenance import build_match_verdict_provenance_chain
from app.trust.refusal import (
    build_error_envelope,
    default_audience_binding,
    tagged_sha256,
    tenant_hash,
    utc_second,
)
from app.trust.schema_versions import validate_schema_canonicalization_compatibility
from app.trust.source_adapters import (
    SUPPORTED_P5_SUBJECT_TYPES,
    ConfidenceProjectionSource,
    FieldSourceDecision,
    MatchVerdictSource,
    data_completeness_for_match_status,
    iter_field_source_decisions,
    normalize_match_verdict_status,
    read_confidence_projection_source,
    read_match_verdict_source,
)
from app.trust.text_disposition import dispose_text_for_field
from app.trust.subject_authority import subject_authority_definition


BuildStatus = Literal["success", "refused", "degraded"]

_PLACEHOLDER_SHA = "sha256:" + ("0" * 64)
_P5_SIGNATURE_PLACEHOLDER = "p5-unsigned-placeholder-signature"
_P5_SIGNING_KEY_PLACEHOLDER = "kid:b25-p5-unsigned-placeholder"


class TrustEnvelopeBuildError(ValueError):
    """Raised when an unsigned TrustEnvelope cannot be built safely."""


@dataclass(frozen=True)
class TrustEnvelopeBuildRequest:
    """Strict P5 builder input."""

    tenant_id: UUID
    subject_type: str
    subject_ref: str
    request_context: dict[str, object]
    schema_version: str = "trust-envelope-schema-v2"
    canonicalization_version: str = "trust-canonical-json-v1"


@dataclass(frozen=True)
class ReadOnlyObservation:
    """Test-facing proof metadata for P5 no-mutation behavior."""

    source_reads: int
    source_writes: int
    task_dispatches: int
    artifact_writes: int
    export_writes: int
    audit_writes: int
    llm_calls: int
    runtime_llm_modules_loaded: tuple[str, ...]

    def external_projection(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class TrustEnvelopeBuildResult:
    """Strict P5 builder output."""

    status: BuildStatus
    unsigned_payload: dict[str, Any] | None
    refusal_payload: dict[str, Any] | None
    reason_code: str | None
    field_source_decisions: tuple[FieldSourceDecision, ...]
    money_authority_decision: MoneyAuthorityDecision | None
    read_only_observation: ReadOnlyObservation
    authority_witness: TrustEnvelopeBuildWitness | None


@dataclass(frozen=True, slots=True)
class TrustEnvelopeBuildWitness:
    """Immutable proof that P5 produced these exact authoritative bytes.

    B2.5-P13 Corrective XV (H-XV-01): ``canonical_payload`` is no longer carried
    on the instance. It lives in the closure-private ledger and is addressed by
    ``_authority_handle``, a 256-bit value the ledger issued. A witness
    fabricated by ``object.__new__``, by the constructor, or by transplanting an
    attribute off a donor therefore resolves to nothing and fails closed --
    where the previous module-level ``object()`` seal was importable and
    ``getattr``-retrievable, and so proved only that the caller had read the
    module.
    """

    tenant_id_hash: str
    subject_type: str
    subject_ref: str
    subject_ref_hash: str
    source_snapshot_hash: str
    field_authority_names: tuple[str, ...]
    _authority_handle: str = field(repr=False, compare=False)

    @property
    def canonical_payload(self) -> bytes:
        """Resolve the authoritative P5 bytes from the issuing ledger."""

        return redeem_build_witness_authority(self._authority_handle, consume=False)

    def assert_authoritative_payload(self, payload: dict[str, Any]) -> None:
        """Reject fabricated witnesses and any mutation after P5 construction."""

        try:
            authoritative = self.canonical_payload
        except IssuanceAuthorityLedgerError as exc:
            raise TrustEnvelopeBuildError("builder_authority_witness_invalid") from exc
        if canonicalize_envelope_payload(payload) != authoritative:
            raise TrustEnvelopeBuildError("builder_authority_payload_mismatch")


def _build_authority_witness(
    *,
    payload: dict[str, Any],
    decisions: tuple[FieldSourceDecision, ...],
) -> TrustEnvelopeBuildWitness:
    """Mint the P5 witness at the point authority is still mechanically known."""

    truth_authority = payload.get("truth_authority")
    if not isinstance(truth_authority, dict):
        raise TrustEnvelopeBuildError("builder_truth_authority_missing")
    witness_fields: dict[str, str] = {}
    for field_name in (
        "tenant_id_hash",
        "subject_type",
        "subject_ref",
        "subject_ref_hash",
    ):
        value = payload.get(field_name)
        if not isinstance(value, str):
            raise TrustEnvelopeBuildError(
                f"builder_authority_string_required:{field_name}"
            )
        witness_fields[field_name] = value
    source_snapshot_hash = truth_authority.get("source_snapshot_hash")
    if not isinstance(source_snapshot_hash, str):
        raise TrustEnvelopeBuildError("builder_source_snapshot_hash_required")
    return TrustEnvelopeBuildWitness(
        tenant_id_hash=witness_fields["tenant_id_hash"],
        subject_type=witness_fields["subject_type"],
        subject_ref=witness_fields["subject_ref"],
        subject_ref_hash=witness_fields["subject_ref_hash"],
        source_snapshot_hash=source_snapshot_hash,
        field_authority_names=tuple(row.field_name for row in decisions),
        _authority_handle=mint_build_witness_authority(
            canonicalize_envelope_payload(payload)
        ),
    )


def _context_datetime(
    request_context: dict[str, object],
    key: str,
    fallback: datetime,
) -> datetime:
    value = request_context.get(key)
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    return fallback


def _source_snapshot_hash(source: MatchVerdictSource) -> str:
    return tagged_sha256(
        {
            "source": "b23_match_verdicts",
            "id": str(source.id),
            "status": source.status,
            "amount_minor": source.canonical_net_verified_amount_minor,
            "currency": source.currency_code,
            "updated_at": utc_second(source.updated_at),
        }
    )


def _subject_ref_hash(subject_ref: str) -> str:
    return tagged_sha256({"subject_ref": subject_ref})


def _envelope_id(
    *,
    tenant_id_hash: str,
    subject_ref: str,
    schema_version: str,
    canonicalization_version: str,
) -> str:
    digest = tagged_sha256(
        {
            "tenant_id_hash": tenant_id_hash,
            "subject_ref": subject_ref,
            "schema_version": schema_version,
            "canonicalization_version": canonicalization_version,
            "phase": "b25-p5-unsigned-builder",
        }
    ).split(":", 1)[1]
    return f"env_{digest[:32]}"


def _confidence_unavailable() -> dict[str, object]:
    return {
        "confidence_status": "unavailable",
        "confidence_authority": "deterministic_only",
        "confidence_score_basis_points": None,
        "bayesian_model_type": "deterministic_only",
        "bayesian_model_version": None,
        "diagnostics_status": "not_applicable",
        "unavailable_reason": "not_applicable",
        # No inference ran, so there is no producing regime to name. Null is
        # the honest value; a bundle hash here would attribute a Bayesian
        # authority to a claim that never had one.
        "inference_provenance": None,
    }


def _tag_b24_hash(value: str) -> str:
    return value if value.startswith("sha256:") else f"sha256:{value}"


def _inference_provenance(projection: object) -> dict[str, object] | None:
    """The producing policy bundle, as persisted beside the confidence.

    Returns None only for rows written before C10 existed, which is honest:
    those confidences genuinely have no recorded regime, and inventing one
    would be worse than admitting the gap.
    """

    bundle_hash = getattr(projection, "policy_bundle_hash", None)
    if not bundle_hash:
        return None
    provenance = {
        "policy_bundle_hash": _tag_b24_hash(str(bundle_hash)),
        "inference_profile_version": getattr(
            projection, "inference_profile_version", None
        ),
        "runtime_policy_version": getattr(projection, "runtime_policy_version", None),
        "sampling_policy_version": getattr(projection, "sampling_policy_version", None),
        "diagnostic_policy_version": getattr(
            projection, "diagnostic_policy_version", None
        ),
        "confidence_policy_version": getattr(
            getattr(projection, "decision", None), "confidence_policy_version", None
        ),
        "confidence_semantics_version": getattr(
            getattr(projection, "decision", None),
            "confidence_semantics_version",
            None,
        ),
        # Both halves of the correspondence, so a verifier can check the claim
        # rather than take the producer's word that they matched.
        "authorized_chains": getattr(projection, "authorized_chains", None),
        "observed_chains": getattr(projection, "observed_chains", None),
        "authorized_posterior_draws_total": getattr(
            projection, "authorized_posterior_draws_total", None
        ),
        "observed_posterior_draws_total": getattr(
            projection, "observed_posterior_draws_total", None
        ),
    }
    required_versions = (
        "inference_profile_version",
        "runtime_policy_version",
        "sampling_policy_version",
        "diagnostic_policy_version",
        "confidence_policy_version",
        "confidence_semantics_version",
    )
    if any(not provenance.get(field) for field in required_versions):
        return None
    topology_values = (
        provenance["authorized_chains"],
        provenance["observed_chains"],
        provenance["authorized_posterior_draws_total"],
        provenance["observed_posterior_draws_total"],
    )
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in topology_values
    ):
        return None
    if provenance["authorized_chains"] != provenance["observed_chains"]:
        return None
    if (
        provenance["authorized_posterior_draws_total"]
        != provenance["observed_posterior_draws_total"]
    ):
        return None
    # Signature integrity cannot repair false provenance.  Resolve the bundle
    # and all component labels against the neutral semantic registry before the
    # available claim is constructed.  This import is intentionally not a
    # Bayesian import, preserving P12's read-only boundary.
    from app.inference_policy_registry import (
        PolicyRegistryError,
        validate_policy_provenance,
    )

    decision = getattr(projection, "decision", None)
    try:
        validate_policy_provenance(
            provenance,
            confidence_policy_version=getattr(
                decision, "confidence_policy_version", None
            ),
            confidence_semantics_version=getattr(
                decision, "confidence_semantics_version", None
            ),
        )
    except PolicyRegistryError:
        return None
    return provenance


def _confidence_projection_metadata(
    source: ConfidenceProjectionSource,
) -> tuple[dict[str, object], str, str, bool, str]:
    """Normalize the B2.4-owned decision into the bounded B2.5 vocabulary."""

    projection = source.projection
    decision = projection.decision
    reason = decision.confidence_bucket_reason.value
    if decision.confidence_available:
        provenance = _inference_provenance(projection)
        if provenance is None:
            return (
                {
                    "confidence_status": "unavailable",
                    "confidence_authority": "explicitly_unavailable",
                    "confidence_score_basis_points": None,
                    "bayesian_model_type": None,
                    "bayesian_model_version": None,
                    "diagnostics_status": "unavailable",
                    "unavailable_reason": "confidence_unavailable",
                    "inference_provenance": None,
                },
                "degraded_or_unavailable_truth",
                "insufficient_evidence",
                True,
                "confidence_unavailable",
            )
        return (
            {
                "confidence_status": "available",
                "confidence_authority": "b24_confidence_projection",
                # B2.4 owns interval-width buckets, not a scalar score mapping.
                "confidence_score_basis_points": None,
                "bayesian_model_type": "pymc_marketing_mmm",
                "bayesian_model_version": projection.model_version,
                "diagnostics_status": "passed",
                "unavailable_reason": None,
                # The regime that produced this number, carried into the bytes
                # that get signed.
                #
                # A confidence means different things under different inference
                # policies -- four chains against one, an ESS floor of 400
                # against 40 -- so a signature over the number alone commits to
                # less than the claim asserts. This was previously computed by
                # as_provenance() and then never called, so nothing an external
                # verifier could inspect named the governing regime at all.
                #
                # Read from the persisted fit, not recomputed: Trust may not
                # reach into Bayesian modules, and re-deriving it here would
                # report today's policy for a confidence produced under an
                # older one -- exactly the substitution being prevented.
                "inference_provenance": provenance,
            },
            "confidence_projection_context",
            "complete",
            False,
            "none",
        )

    diagnostic_failure = projection.diagnostic_status in {"failed", "error"}
    if diagnostic_failure:
        status = "diagnostics_failed"
        authority = "b24_confidence_projection"
        model_type: str | None = "pymc_marketing_mmm"
        model_version: str | None = projection.model_version
        diagnostics_status = "failed"
        unavailable_reason = "diagnostics_failed"
        fallback_reason = "diagnostics_failed"
    elif reason == "source_snapshot_changed":
        status = "degraded"
        authority = "explicitly_unavailable"
        model_type = None
        model_version = None
        diagnostics_status = "unavailable"
        unavailable_reason = "source_snapshot_stale"
        fallback_reason = "source_snapshot_stale"
    elif reason == "source_authority_unknown":
        status = "unavailable"
        authority = "explicitly_unavailable"
        model_type = None
        model_version = None
        diagnostics_status = "unavailable"
        unavailable_reason = "confidence_unavailable"
        fallback_reason = "confidence_authority_indeterminate"
    elif reason == "multi_currency_unsupported":
        status = "unavailable"
        authority = "explicitly_unavailable"
        model_type = None
        model_version = None
        diagnostics_status = "unavailable"
        unavailable_reason = "unsupported_financial_context"
        fallback_reason = "unsupported_financial_context"
    elif reason in {"artifact_pruned", "artifact_unavailable"}:
        status = "degraded"
        authority = "b24_confidence_projection"
        model_type = "pymc_marketing_mmm"
        model_version = projection.model_version
        diagnostics_status = "unavailable"
        unavailable_reason = reason
        fallback_reason = reason
    elif reason in {"no_fit", "insufficient_data"}:
        status = "unavailable"
        authority = "explicitly_unavailable"
        model_type = None
        model_version = None
        diagnostics_status = "unavailable"
        unavailable_reason = (
            "cold_start_insufficient_data"
            if reason == "insufficient_data"
            else "model_not_fit"
        )
        fallback_reason = "confidence_unavailable"
    else:
        status = "unavailable"
        authority = "explicitly_unavailable"
        model_type = None
        model_version = None
        diagnostics_status = "unavailable"
        unavailable_reason = "confidence_unavailable"
        fallback_reason = "confidence_unavailable"

    return (
        {
            "confidence_status": status,
            "confidence_authority": authority,
            "confidence_score_basis_points": None,
            "bayesian_model_type": model_type,
            "bayesian_model_version": model_version,
            "diagnostics_status": diagnostics_status,
            "unavailable_reason": unavailable_reason,
            # Recorded for refusals too. "This regime looked and could not
            # answer" is a different and more useful statement than "no answer",
            # and a verifier auditing a topology defect needs the refusals as
            # much as the acceptances.
            "inference_provenance": _inference_provenance(projection),
        },
        "degraded_or_unavailable_truth",
        (
            "degraded"
            if status in {"degraded", "diagnostics_failed"}
            else "insufficient_evidence"
        ),
        True,
        fallback_reason,
    )


def _confidence_projection_payload(
    *,
    request: TrustEnvelopeBuildRequest,
    source: ConfidenceProjectionSource,
) -> dict[str, Any]:
    projection = source.projection
    tenant_id_hash = tenant_hash(request.tenant_id)
    subject_ref_hash = _subject_ref_hash(request.subject_ref)
    source_snapshot_hash = _tag_b24_hash(projection.source_snapshot_hash)
    evidence_snapshot_at = projection.evidence_snapshot_at
    source_read_started_at = projection.source_read_started_at
    source_read_completed_at = projection.source_read_completed_at
    created_at = _context_datetime(
        request.request_context, "created_at", projection.observed_at
    )
    # Relative chronology is necessary but not sufficient. Evidence that claims
    # to have been read after the envelope was issued is not zero seconds old --
    # it is not evidence. The tolerance is the one governed skew allowance shared
    # with the database producer, so "slightly ahead because two clocks differ"
    # and "dated thirty days into the future" are answered by one rule.
    temporal_chronology_ordered = (
        evidence_snapshot_at is not None
        and source_read_started_at is not None
        and source_read_completed_at is not None
        and source_read_completed_at >= source_read_started_at
    )
    temporal_plausible = all(
        evidence_timestamp_is_plausible(stamp, authoritative_now=created_at)
        for stamp in (
            evidence_snapshot_at,
            source_read_started_at,
            source_read_completed_at,
            projection.confidence_classified_at,
        )
    )
    temporal_authority_available = temporal_chronology_ordered and temporal_plausible
    valid_until = _context_datetime(
        request.request_context,
        "valid_until",
        created_at + timedelta(hours=24),
    )
    audience_id = str(
        request.request_context.get("audience_id") or "b25-p5-internal-builder"
    )
    (
        confidence_metadata,
        truth_type,
        data_completeness_status,
        fallback_applied,
        fallback_reason,
    ) = _confidence_projection_metadata(source)
    if (
        not temporal_authority_available
        and confidence_metadata["confidence_status"] == "available"
    ):
        confidence_metadata = {
            **confidence_metadata,
            "confidence_status": "unavailable",
            "confidence_authority": "explicitly_unavailable",
            "diagnostics_status": "unavailable",
            "unavailable_reason": "confidence_unavailable",
        }
        truth_type = "degraded_or_unavailable_truth"
        data_completeness_status = "insufficient_evidence"
        fallback_applied = True
        fallback_reason = "confidence_unavailable"
    fit_ref = f"urn:skeldir:bayesian_model_fits:{projection.fit_id}"
    provenance_chain = [
        {
            "provenance_type": (
                "b24_source_snapshot"
                if temporal_authority_available
                else "explicit_unavailable"
            ),
            "authority_table": (
                "b24_confidence_projection"
                if temporal_authority_available
                else "bayesian_model_fits"
            ),
            "source_ref": (
                f"urn:skeldir:b24_source_snapshot:{projection.source_snapshot_hash}"
            ),
            "source_ref_hash": tagged_sha256(
                {
                    "model_type": projection.model_type,
                    "model_version": projection.model_version,
                    "source_window_start": utc_second(projection.source_window_start),
                    "source_window_end": utc_second(projection.source_window_end),
                    "source_snapshot_hash": projection.source_snapshot_hash,
                    "source_read_started_at": (
                        utc_second(source_read_started_at)
                        if source_read_started_at is not None
                        else None
                    ),
                    "source_read_completed_at": (
                        utc_second(source_read_completed_at)
                        if source_read_completed_at is not None
                        else None
                    ),
                }
            ),
            "source_snapshot_hash": source_snapshot_hash,
            "observed_at": utc_second(evidence_snapshot_at or projection.observed_at),
            "display_metadata": {
                "text_trust_class": "none",
                "raw_text_sha256": None,
                "display_transform": "none",
            },
        },
        {
            "provenance_type": "bayesian_fit",
            "authority_table": "bayesian_model_fits",
            "source_ref": fit_ref,
            "source_ref_hash": tagged_sha256({"fit_ref": fit_ref}),
            "source_snapshot_hash": source_snapshot_hash,
            "observed_at": utc_second(projection.observed_at),
            "display_metadata": {
                "text_trust_class": "none",
                "raw_text_sha256": None,
                "display_transform": "none",
            },
        },
        {
            "provenance_type": "bayesian_diagnostic",
            "authority_table": "bayesian_model_fits",
            "source_ref": (f"urn:skeldir:bayesian_diagnostic:{projection.fit_id}"),
            "source_ref_hash": tagged_sha256(
                {
                    "diagnostic_status": projection.diagnostic_status,
                    "diagnostic_failure_reason": (projection.diagnostic_failure_reason),
                    "confidence_bucket": (projection.decision.confidence_bucket.value),
                    "confidence_bucket_reason": (
                        projection.decision.confidence_bucket_reason.value
                    ),
                    "confidence_policy_version": (
                        projection.decision.confidence_policy_version
                    ),
                    "confidence_semantics_version": (
                        projection.decision.confidence_semantics_version
                    ),
                    "deterministic_revenue_minor": (
                        projection.deterministic_revenue_minor
                    ),
                    "deterministic_row_count": projection.deterministic_row_count,
                    "match_verdict_count": projection.match_verdict_count,
                    "currency_count": projection.currency_count,
                    "confidence_classified_at": (
                        utc_second(projection.confidence_classified_at)
                        if projection.confidence_classified_at is not None
                        else None
                    ),
                    "confidence_evidence_snapshot_hash": (
                        projection.confidence_evidence_snapshot_hash
                    ),
                }
            ),
            "source_snapshot_hash": source_snapshot_hash,
            "observed_at": utc_second(projection.observed_at),
            "display_metadata": {
                "text_trust_class": "none",
                "raw_text_sha256": None,
                "display_transform": "none",
            },
        },
        {
            "provenance_type": "b24_snapshot_freshness",
            "authority_table": "b24_dirty_events",
            "source_ref": (f"urn:skeldir:b24_snapshot_freshness:{projection.fit_id}"),
            "source_ref_hash": tagged_sha256(
                {
                    "snapshot_freshness": projection.snapshot_freshness,
                    "has_snapshot_lineage": projection.has_snapshot_lineage,
                    "has_later_dirty_evidence": (projection.has_later_dirty_evidence),
                    "has_newer_fit": projection.has_newer_fit,
                }
            ),
            "source_snapshot_hash": source_snapshot_hash,
            "observed_at": utc_second(projection.observed_at),
            "display_metadata": {
                "text_trust_class": "none",
                "raw_text_sha256": None,
                "display_transform": "none",
            },
        },
        {
            "provenance_type": (
                "bayesian_artifact"
                if projection.artifact_ref is not None
                else "explicit_unavailable"
            ),
            "authority_table": (
                "bayesian_artifacts"
                if projection.artifact_ref is not None
                else "b24_confidence_projection"
            ),
            "source_ref": (f"urn:skeldir:bayesian_artifact:{projection.fit_id}"),
            "source_ref_hash": tagged_sha256(
                {
                    "artifact_ref": projection.artifact_ref,
                    "artifact_hash": projection.artifact_hash,
                    "artifact_lifecycle_status": (projection.artifact_lifecycle_status),
                }
            ),
            "source_snapshot_hash": source_snapshot_hash,
            "observed_at": utc_second(projection.observed_at),
            "display_metadata": {
                "text_trust_class": "none",
                "raw_text_sha256": None,
                "display_transform": "none",
            },
        },
    ]
    artifact_available = (
        confidence_metadata["confidence_status"] == "available"
        and projection.artifact_ref is not None
        and projection.artifact_hash is not None
    )
    artifact_ref = (
        f"urn:skeldir:artifact:b24_{projection.fit_id}" if artifact_available else None
    )
    artifact_hash = (
        _tag_b24_hash(projection.artifact_hash)
        if artifact_available and projection.artifact_hash is not None
        else None
    )
    authority = subject_authority_definition("confidence_projection")
    # `data_freshness_seconds` is bounded by the wire contract, so for evidence
    # older than the ceiling the number alone is a lie by omission: a five-year-old
    # snapshot and a 364-day-old one rendered identically. The number keeps its
    # bound; `data_freshness_bound` says whether it is the exact age or a floor,
    # and `evidence_age_status` classifies absolute age independently of lineage.
    raw_age_seconds = (
        int((created_at - evidence_snapshot_at).total_seconds())
        if temporal_authority_available and evidence_snapshot_at is not None
        else None
    )
    if raw_age_seconds is None:
        freshness_seconds: int | None = None
        freshness_bound = "unavailable"
        evidence_age_status = "unavailable"
    elif raw_age_seconds > EVIDENCE_FRESHNESS_CEILING_SECONDS:
        freshness_seconds = EVIDENCE_FRESHNESS_CEILING_SECONDS
        freshness_bound = "at_least_ceiling"
        evidence_age_status = "beyond_supported_horizon"
    else:
        # A small negative age is clock skew inside the governed tolerance --
        # materially future evidence never reaches this branch, because
        # `temporal_authority_available` is already false for it.
        freshness_seconds = max(0, raw_age_seconds)
        freshness_bound = "exact"
        evidence_age_status = "within_supported_horizon"
    source_read_skew_ms = (
        max(
            0,
            min(
                86400000,
                int(
                    (source_read_completed_at - source_read_started_at).total_seconds()
                    * 1000
                ),
            ),
        )
        if temporal_authority_available
        and source_read_started_at is not None
        and source_read_completed_at is not None
        else None
    )
    if projection.snapshot_freshness == "current" and temporal_authority_available:
        staleness_status = "current"
        consistency_status = "consistent"
    elif projection.snapshot_freshness == "stale":
        staleness_status = "stale_degraded"
        consistency_status = "stale_degraded"
    else:
        staleness_status = "unavailable"
        consistency_status = "unavailable"
    payload: dict[str, Any] = {
        "envelope_version": "trust-envelope-v1",
        "schema_version": request.schema_version,
        "canonicalization_version": request.canonicalization_version,
        "envelope_id": _envelope_id(
            tenant_id_hash=tenant_id_hash,
            subject_ref=request.subject_ref,
            schema_version=request.schema_version,
            canonicalization_version=request.canonicalization_version,
        ),
        "tenant_id_hash": tenant_id_hash,
        "audience_binding": default_audience_binding(audience_id=audience_id),
        "subject_authority": {
            "subject_type": "confidence_projection",
            "subject_ref": request.subject_ref,
            "subject_ref_hash": subject_ref_hash,
            "source_authority_class": authority.source_authority_class,
            "allowed_source_tables": list(authority.governed_source_tables),
            "mutable_workflow_subject": False,
        },
        "subject_type": "confidence_projection",
        "subject_ref": request.subject_ref,
        "subject_ref_hash": subject_ref_hash,
        "truth_type": truth_type,
        "truth_authority": {
            "authority_class": (
                "confidence_metadata_projection"
                if confidence_metadata["confidence_status"] == "available"
                else "refusal_or_degraded_state"
            ),
            "source_snapshot_hash": source_snapshot_hash,
            "source_system": "skeldir_b24_confidence_projection",
        },
        "confidence_metadata": confidence_metadata,
        "provenance_chain": provenance_chain,
        "data_completeness_status": data_completeness_status,
        "benchmark_metadata": unavailable_benchmark_metadata(),
        "policy_action_authority": read_only_policy_authority(),
        "fallback_applied": fallback_applied,
        "fallback_reason": fallback_reason,
        "evidence_temporal_boundary": {
            "evidence_snapshot_at": (
                utc_second(evidence_snapshot_at)
                if evidence_snapshot_at is not None
                else None
            ),
            "source_read_started_at": (
                utc_second(source_read_started_at)
                if source_read_started_at is not None
                else None
            ),
            "source_read_completed_at": (
                utc_second(source_read_completed_at)
                if source_read_completed_at is not None
                else None
            ),
            "data_freshness_seconds": freshness_seconds,
            "data_freshness_bound": freshness_bound,
            "evidence_age_status": evidence_age_status,
            "staleness_status": staleness_status,
            "evidence_snapshot_hash": source_snapshot_hash,
            "max_source_read_skew_ms": source_read_skew_ms,
            "snapshot_consistency_status": consistency_status,
        },
        "audit_ref": "urn:skeldir:audit:p5_unsigned_builder_unissued",
        "audit_hash": tagged_sha256(
            {
                "p5_audit_placeholder": "not_persisted",
                "tenant_id_hash": tenant_id_hash,
                "subject_ref_hash": subject_ref_hash,
            }
        ),
        "semantic_truth_hash": _PLACEHOLDER_SHA,
        "artifact_ref": artifact_ref,
        "artifact_hash": artifact_hash,
        "signature_hash": _PLACEHOLDER_SHA,
        "signature": _P5_SIGNATURE_PLACEHOLDER,
        "signing_algorithm": "ed25519",
        "signing_key_id": _P5_SIGNING_KEY_PLACEHOLDER,
        "created_at": utc_second(created_at),
        "valid_until": utc_second(valid_until),
        "untrusted_display_data": {
            "text_trust_class": "none",
            "raw_text_sha256": None,
            "display_text": None,
            "display_transform": "none",
            "text_disposition_version": "text-disposition-v1",
        },
    }
    payload["semantic_truth_hash"] = compute_semantic_truth_hash(payload)
    payload["signature_hash"] = compute_signature_hash(payload)
    canonicalize_envelope_payload(payload)
    return payload


def _display_data_from_provider_text(raw_text: str) -> dict[str, object]:
    decision = dispose_text_for_field(
        field_path="untrusted_display_data.display_text",
        raw_text=raw_text,
        source="provider",
    )
    projection = decision.external_projection()
    action = projection["disposition_action"]
    display_transform = "none"
    text_trust_class = projection["text_trust_class"]
    if action == "emit_untrusted_display_label":
        display_transform = "escaped_display_only"
    elif action in {
        "omit_raw_text_and_emit_quarantine_metadata",
        "redact_with_reason",
    }:
        display_transform = "redacted"
        if text_trust_class == "untrusted_display_label":
            text_trust_class = "quarantined_text_hash"
    return {
        "text_trust_class": text_trust_class,
        "content_safety_flags": projection["content_safety_flags"],
        "disposition_action": action,
        "raw_text_sha256": projection["raw_text_sha256"],
        "raw_text_hmac": projection["raw_text_hmac"],
        "display_text": projection["display_text"],
        "normalized_display_text": projection["normalized_display_text"],
        "display_transform": display_transform,
        "opaque_reference_hash": projection["opaque_reference_hash"],
        "opaque_reference_metadata": projection["opaque_reference_metadata"],
        "redaction_reason": projection["redaction_reason"],
        "text_disposition_version": projection["text_disposition_version"],
    }


def _qualified_match_verdict_status(source: MatchVerdictSource) -> str:
    """XXI P1: presentation status under ingress authority and family law."""
    if not source.ingress_has_current_authority:
        return "unavailable"
    normalized = normalize_match_verdict_status(source.status)
    if source.provider == "shopify" and not source.event_family_law_current:
        return "ambiguous" if normalized == "matched" else normalized
    return normalized


def _qualified_data_completeness(source: MatchVerdictSource) -> str:
    """XXI P1: completeness semantics under ingress authority and family law."""
    if not source.ingress_has_current_authority:
        return "unavailable"
    if source.provider == "shopify" and not source.event_family_law_current:
        return "degraded"
    return data_completeness_for_match_status(source.status)


def _event_meaning_reason_code(source: MatchVerdictSource) -> str | None:
    """XXI P1: consumer-visible event-meaning qualification.

    Travels through the governed reason-code decision entry (XVIII
    precedent; no new envelope field). Shopify rows cite the
    event-family law version under which their meaning was
    established; rows minted under a superseded law are disclosed as
    such; every other row keeps the historical codes.
    """
    if not source.ingress_has_current_authority:
        return "source_authority_not_current"
    if source.provider != "shopify":
        return None
    version = source.event_family_law_version or "unknown"
    if not source.event_family_law_current:
        return f"event_family_law_superseded:{version}"
    if version == "unknown":
        return None
    return f"event_family_law:{version}"


def _match_verdict_payload(
    *,
    request: TrustEnvelopeBuildRequest,
    source: MatchVerdictSource,
    money_decision: AuthoritativeMoneyMinor,
) -> dict[str, Any]:
    tenant_id_hash = tenant_hash(request.tenant_id)
    subject_ref_hash = _subject_ref_hash(request.subject_ref)
    source_snapshot_hash = _source_snapshot_hash(source)
    created_at = _context_datetime(
        request.request_context, "created_at", source.updated_at
    )
    valid_until = _context_datetime(
        request.request_context,
        "valid_until",
        created_at + timedelta(hours=24),
    )
    audience_id = str(
        request.request_context.get("audience_id") or "b25-p5-internal-builder"
    )
    display_data = _display_data_from_provider_text(source.canonical_commerce_reference)
    authority = subject_authority_definition("match_verdict")
    payload: dict[str, Any] = {
        "envelope_version": "trust-envelope-v1",
        "schema_version": request.schema_version,
        "canonicalization_version": request.canonicalization_version,
        "envelope_id": _envelope_id(
            tenant_id_hash=tenant_id_hash,
            subject_ref=request.subject_ref,
            schema_version=request.schema_version,
            canonicalization_version=request.canonicalization_version,
        ),
        "tenant_id_hash": tenant_id_hash,
        "audience_binding": default_audience_binding(audience_id=audience_id),
        "subject_authority": {
            "subject_type": "match_verdict",
            "subject_ref": request.subject_ref,
            "subject_ref_hash": subject_ref_hash,
            "source_authority_class": authority.source_authority_class,
            "allowed_source_tables": list(authority.governed_source_tables),
            "mutable_workflow_subject": False,
        },
        "subject_type": "match_verdict",
        "subject_ref": request.subject_ref,
        "subject_ref_hash": subject_ref_hash,
        "truth_type": "deterministic_match_verdict",
        "truth_authority": {
            "authority_class": "deterministic_machine_fact",
            "source_snapshot_hash": source_snapshot_hash,
            "source_system": "skeldir_b23_match_engine",
        },
        # XVIII (H-XVIII-R7/R9): a verdict whose backing ingress lost
        # current P2 authority (demoted history) never surfaces as
        # verified truth: explicit degraded semantics instead. The
        # amount stays the verdict's recorded figure; the STATUS is
        # what an agent/LLM must read, and it reads unavailable.
        # NOTE: no new top-level envelope field is introduced: the
        # envelope schema is closed (additionalProperties forbidden)
        # and C14 fails closed on undeclared signed fields. The
        # degraded semantics travel through governed fields only.
        # XXI P1 (consumer-visible event meaning): the family law that
        # established this verdict's meaning rides the same governed
        # fields. A verdict established under a superseded event-family
        # law never presents as verified: it reads ambiguous with
        # amounts and authority kept, completeness reads degraded, and
        # the reason-code entry cites the law version at mint. A
        # current-law Shopify row cites its establishing version
        # (event_family_law:vN) so the creation-window basis is
        # checkable downstream; the (0,60]s indistinguishable kernel
        # remains a recorded deviation, never a per-row claim.
        "match_verdict_status": _qualified_match_verdict_status(source),
        # XXV (B6/B9/B12): the certified figure travels IN the signed
        # artifact. The amount and currency come from the money-authority
        # decision that was already resolved and validated for this verdict
        # (and whose source attestation the caller verified before reaching
        # here), so the signature now covers the integer-minor amount a
        # machine consumer has to read -- instead of covering a provenance
        # hash of it that no consumer can invert.
        "verified_revenue_minor": money_decision.amount_minor,
        "currency": money_decision.currency,
        "confidence_metadata": _confidence_unavailable(),
        "provenance_chain": build_match_verdict_provenance_chain(
            source=source,
            display_data=display_data,
            money_authority_projection=money_decision.external_projection(),
            reason_code=_event_meaning_reason_code(source),
        ),
        "data_completeness_status": _qualified_data_completeness(source),
        "benchmark_metadata": unavailable_benchmark_metadata(),
        "policy_action_authority": read_only_policy_authority(),
        "fallback_applied": False,
        "fallback_reason": "none",
        "evidence_temporal_boundary": {
            "evidence_snapshot_at": utc_second(source.updated_at),
            "source_read_started_at": utc_second(created_at),
            "source_read_completed_at": utc_second(created_at),
            "data_freshness_seconds": 0,
            "data_freshness_bound": "exact",
            "evidence_age_status": "within_supported_horizon",
            "staleness_status": "current",
            "evidence_snapshot_hash": source_snapshot_hash,
            "max_source_read_skew_ms": 0,
            "snapshot_consistency_status": "consistent",
        },
        "audit_ref": "urn:skeldir:audit:p5_unsigned_builder_unissued",
        "audit_hash": tagged_sha256(
            {
                "p5_audit_placeholder": "not_persisted",
                "tenant_id_hash": tenant_id_hash,
                "subject_ref_hash": subject_ref_hash,
            }
        ),
        "semantic_truth_hash": _PLACEHOLDER_SHA,
        "artifact_ref": None,
        "artifact_hash": None,
        "signature_hash": _PLACEHOLDER_SHA,
        "signature": _P5_SIGNATURE_PLACEHOLDER,
        "signing_algorithm": "ed25519",
        "signing_key_id": _P5_SIGNING_KEY_PLACEHOLDER,
        "created_at": utc_second(created_at),
        "valid_until": utc_second(valid_until),
        "untrusted_display_data": display_data,
    }
    payload["semantic_truth_hash"] = compute_semantic_truth_hash(payload)
    payload["signature_hash"] = compute_signature_hash(payload)
    canonicalize_envelope_payload(payload)
    if money_decision.amount_minor is None:
        raise TrustEnvelopeBuildError("accepted_money_authority_missing_amount")
    return payload


def _money_decision_for_match_verdict(
    source: MatchVerdictSource,
) -> MoneyAuthorityDecision:
    return resolve_authoritative_money(
        source_domain="b23_match_verdicts",
        source_field_path="canonical_net_verified_amount_minor",
        raw_value=source.canonical_net_verified_amount_minor,
        currency=source.currency_code,
        intended_trust_field="verified_revenue_minor",
    )


#: Maximum age of a beat-authored history observation the builder
#: trusts (XXI H-XXI-07/Gate N). Older, missing, violated, or
#: live-divergent observations refuse issuance: an envelope must not
#: assert deterministic truth over unverifiable correction history.
HISTORY_INTEGRITY_HORIZON_SECONDS = 1200

#: Roles whose beat observations the builder accepts. Authorship is
#: stamped by session_user at INSERT and cannot be forged in-session;
#: any other author (including maintenance roles) is rejected.
HISTORY_OBSERVER_AUTHORS = frozenset({"app_worker"})


async def read_history_integrity_status(
    db_session: AsyncSession,
) -> tuple[bool, str]:
    """Check beat-observed ledger continuity for Trust issuance.

    Returns (True, "") only when a fresh beat-authored clean
    observation agrees with live ledger count and tip. Anything else
    -- never observed, untrusted author, stale, violations present, or
    live divergence -- returns (False, reason). Real SQL against live
    state; no in-memory substitutes.
    """
    from datetime import datetime, timezone  # noqa: PLC0415

    row = (
        (
            await db_session.execute(
                text(
                    "SELECT ledger_count, ledger_tip,"
                    " observer_violations, observed_at, author"
                    " FROM public.b26_p2_history_integrity_observations"
                    " ORDER BY id DESC LIMIT 1"
                )
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return False, "history_integrity_never_observed"
    if str(row["author"] or "") not in HISTORY_OBSERVER_AUTHORS:
        return False, "history_integrity_untrusted_observer"
    observed_at = row["observed_at"]
    now = datetime.now(timezone.utc)
    if observed_at is not None:
        moment = observed_at
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        if (now - moment).total_seconds() > HISTORY_INTEGRITY_HORIZON_SECONDS:
            return False, "history_integrity_observation_stale"
        if (moment - now).total_seconds() > HISTORY_INTEGRITY_HORIZON_SECONDS:
            return False, "history_integrity_observation_future"
    if str(row["observer_violations"] or "").strip():
        return False, "history_integrity_violations_present"
    # The observation row is writable by the maintenance principal and
    # its author column is not a signature. Re-read the live protection
    # and continuity verdict independently through the owner-context
    # DEFINER reader, so a planted "clean" observation cannot hide a
    # truncated, broken, or privilege-widened ledger.
    #
    # XXIII (HB-07): one statement, one snapshot. The witness state,
    # prefix digest, violation verdict, and authority universe must
    # describe the same instant; separate READ COMMITTED statements can
    # interleave with a lawful append and manufacture a false divergence.
    live = (
        (
            await db_session.execute(
                text(
                    "SELECT n, tip_seq, tip_hash, prefix_digest,"
                    " violations, authority_universe FROM"
                    " public.b26_p2_read_history_snapshot(NULL)"
                )
            )
        )
        .mappings()
        .one()
    )
    tenant_value = (
        await db_session.execute(
            text("SELECT current_setting('app.current_tenant_id', true)")
        )
    ).scalar_one_or_none()
    if not tenant_value:
        return False, "history_integrity_tenant_missing"
    import os  # noqa: PLC0415

    evidence = None
    if os.getenv("B26_P2_SOURCE_EVIDENCE_REQUIRED", "").strip().lower() == "true":
        from app.revenue_verification.source_evidence import (  # noqa: PLC0415
            source_evidence_snapshot,
        )
        evidence = await source_evidence_snapshot(
            db_session, tenant_id=str(tenant_value)
        )
    if str(live["violations"] or "").strip():
        return False, "history_integrity_violations_present"
    if int(live["n"] or 0) != int(row["ledger_count"] or 0):
        return False, "history_integrity_live_count_diverged"
    if (live["tip_hash"] or None) != (row["ledger_tip"] or None):
        # Both NULL (empty ledger, empty observation) agrees; any
        # other mismatch refuses.
        if not (live["tip_hash"] is None and row["ledger_tip"] is None):
            return False, "history_integrity_live_tip_diverged"
    witness_ok, witness_reason = _verify_signed_history_witness(
        ledger_count=int(live["n"] or 0),
        ledger_tip_hash=live["tip_hash"] or None,
        ledger_prefix_digest=live.get("prefix_digest"),
        authority_universe=(
            str(live["authority_universe"])
            if live.get("authority_universe") is not None
            else None
        ),
        tenant_source_evidence_digest=(
            {str(tenant_value): str(evidence["digest"])}
            if evidence is not None
            else None
        ),
    )
    if not witness_ok:
        return False, witness_reason
    return True, ""


def _history_anchor_required() -> bool:
    """True when the deployment must carry a compiled historical anchor.

    XXV (HB-01): this is a *requirement* predicate, never an *enforcement*
    predicate. Enforcement in ``_verify_signed_history_witness`` is
    unconditional whenever the image carries an anchor; this function only
    decides where a missing anchor is itself fatal. It reads the canonical
    environment through ``is_production_like`` so no alias can make it
    unreachable.
    """
    from app.core.config import settings  # noqa: PLC0415
    from app.core.control_plane import is_production_like  # noqa: PLC0415

    return is_production_like(settings.ENVIRONMENT)


def _verify_signed_history_witness(
    *,
    ledger_count: int,
    ledger_tip_hash: str | None,
    ledger_prefix_digest: str | None = None,
    authority_universe: str | None = None,
    tenant_source_evidence_digest: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Verify the out-of-database signed checkpoint against live state.

    The database observation (and even the ledger chain) can be produced
    by the same principal that rewrites the ledger. The signed journal is
    held outside that principal's control and commits to the exact live
    count and tip. Missing, stale, malformed, future-dated, or divergent
    journals refuse issuance rather than degrading to ledger-only trust.

    XXIII (HB-02/HB-03): the journal must be bound to this authority
    universe, and a monotonic custody record must not sit above the
    journal tip (journal rollback replay).
    """
    from app.core.config import settings  # noqa: PLC0415
    from app.trust.history_witness import (  # noqa: PLC0415
        HistoryWitnessError,
        load_custody,
        load_public_key,
        public_key_fingerprint,
        verify_journal,
    )
    from app.trust.witness_anchor import (  # noqa: PLC0415
        COMPILED_GENESIS_HASH,
        COMPILED_PUBLIC_KEY_SHA256,
    )

    if not settings.B26_P2_HISTORY_WITNESS_REQUIRED:
        return True, ""
    try:
        genesis_hash = settings.B26_P2_HISTORY_WITNESS_GENESIS_HASH
        # XXV (HB-01/A1/A5): the compiled-anchor comparison is NOT gated on
        # an environment predicate. The previous guard tested the literal
        # "production", while app/core/config.py canonicalises every
        # environment value through resolve_control_plane_env ("production"
        # -> "prod"), so the branch was unreachable in every possible
        # deployment and the entire root-substitution class was open. The
        # comparison now fires whenever the deployed image carries an anchor,
        # which is what makes the anchor an authority rather than a label:
        #
        #   * an image built with the anchor (every production image, by the
        #     import-time assertion in Settings) always compares it, so a
        #     substituted runtime key, journal, heartbeat or genesis is
        #     refused regardless of ENVIRONMENT;
        #   * a source/dev image carries no anchor and cannot run as prod or
        #     stage at all, because Settings refuses to construct.
        #
        # Reached by: xxv-hb01-anchor-reachability, xxv-hb01-root-substitution.
        anchored = bool(COMPILED_GENESIS_HASH and COMPILED_PUBLIC_KEY_SHA256)
        if _history_anchor_required() and not anchored:
            raise HistoryWitnessError("witness_compiled_anchor_missing")
        if anchored:
            if genesis_hash != COMPILED_GENESIS_HASH:
                raise HistoryWitnessError(
                    "witness_compiled_genesis_mismatch"
                )
            public_key = load_public_key(
                settings.B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH
            )
            if public_key_fingerprint(public_key) != COMPILED_PUBLIC_KEY_SHA256:
                raise HistoryWitnessError(
                    "witness_compiled_public_key_mismatch"
                )
            genesis_hash = COMPILED_GENESIS_HASH
        journal = verify_journal(
            settings.B26_P2_HISTORY_WITNESS_JOURNAL_PATH,
            public_key_path=settings.B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH,
            genesis_hash=genesis_hash,
            require_freshness=True,
            freshness_seconds=settings.B26_P2_HISTORY_WITNESS_HORIZON_SECONDS,
            expected_count=ledger_count,
            expected_tip_hash=ledger_tip_hash,
            expected_prefix_digest=ledger_prefix_digest,
            expected_universe=authority_universe,
            require_universe=True,
            expected_source_evidence_by_tenant=tenant_source_evidence_digest,
            require_source_evidence=(tenant_source_evidence_digest is not None),
            heartbeat_path=settings.B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH,
        )
        custody = load_custody(
            settings.B26_P2_HISTORY_WITNESS_CUSTODY_PATH
        )
        if custody is None:
            # XXV (HB-02/A5): custody loss is refused whenever the witness is
            # required, not only under an unreachable environment literal. A
            # journal always has a custody record once the observer has run,
            # so a missing custody record means the record was removed or was
            # never published -- neither of which may issue as complete
            # history. Reached by: xxv-hb02-custody.
            raise HistoryWitnessError("witness_custody_missing")
        else:
            custody_count = int(custody["ledger_count"])
            latest = journal.latest
            if latest.ledger_count < custody_count:
                raise HistoryWitnessError("witness_custody_rollback")
            if (
                latest.ledger_count == custody_count
                and latest.checkpoint_hash != custody["checkpoint_hash"]
            ):
                raise HistoryWitnessError("witness_custody_fork")
    except HistoryWitnessError as exc:
        return False, f"history_integrity_witness_refused:{exc}"
    return True, ""


async def read_source_money_conservation_status(
    db_session: AsyncSession,
    *,
    tenant_id: UUID,
    verdict_id: UUID,
) -> tuple[bool, str]:
    """Check that current verdict money is the lawful source continuation."""
    result = await db_session.execute(
        text(
            "SELECT violation FROM"
            " public.b26_p2_verify_source_money_conservation("
            ":tenant_id, :verdict_id)"
        ),
        {"tenant_id": str(tenant_id), "verdict_id": str(verdict_id)},
    )
    scalars = getattr(result, "scalars", None)
    if scalars is None:
        return True, ""
    violations = [str(v) for v in scalars().all() if str(v).strip()]
    # A lawful regime retirement makes every ingress non-current. The
    # conservation oracle reports that as a distinct violation, but the
    # envelope still exists: the source reader and the qualified status
    # fields below publish ``unavailable`` rather than verified truth.
    # Every other conservation violation (amount/currency divergence,
    # missing source, discontinuous ledger) remains a hard refusal.
    if violations == ["conservation_source_authority_unresolved"]:
        return True, ""
    if violations:
        return False, "source_money_conservation_unverifiable:" + violations[0]
    return True, ""


def _read_only_observation(*, llm_modules: tuple[str, ...]) -> ReadOnlyObservation:
    return ReadOnlyObservation(
        source_reads=1,
        source_writes=0,
        task_dispatches=0,
        artifact_writes=0,
        export_writes=0,
        audit_writes=0,
        llm_calls=0,
        runtime_llm_modules_loaded=llm_modules,
    )


def _loaded_llm_modules(before: set[str], after: set[str]) -> tuple[str, ...]:
    loaded = sorted(after - before)
    forbidden = tuple(
        name
        for name in loaded
        if (
            name.startswith("app.llm")
            or name.startswith("backend.app.llm")
            or name in {"openai", "anthropic"}
            or name.startswith("openai.")
            or name.startswith("anthropic.")
        )
    )
    return forbidden


_ISSUANCE_LOCK_NAMESPACE = 82173645
_ISSUANCE_LOCK_KEY = 300003


async def _acquire_issuance_lock(db_session: AsyncSession) -> bool:
    """Serialize match-correction writes against Trust issuance.

    XXIV (A7): source read, conservation, witness verification and
    envelope construction must describe one committed world. The
    correction path takes the same transaction-scoped advisory lock, so
    a newer correction cannot commit between the builder's source read
    and its signature. Test doubles without a connection are not locked;
    production paths always are.
    """
    connection_factory = getattr(db_session, "connection", None)
    if connection_factory is None:
        return False
    connection = await connection_factory()
    await connection.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, :key)"),
        {"namespace": _ISSUANCE_LOCK_NAMESPACE, "key": _ISSUANCE_LOCK_KEY},
    )
    return True


def _source_evidence_tuple(
    source: MatchVerdictSource,
) -> tuple[object, ...]:
    return (
        source.status,
        source.canonical_net_verified_amount_minor,
        source.currency_code,
        source.last_transition_at,
        source.updated_at,
        source.ingress_authority_state,
        source.ingress_has_current_authority,
    )


async def build_unsigned_trust_envelope(
    db_session: AsyncSession,
    request: TrustEnvelopeBuildRequest,
    *,
    source: MatchVerdictSource | ConfidenceProjectionSource | None = None,
    payload_runner: Callable[..., Awaitable[dict[str, Any]]] | None = None,
) -> TrustEnvelopeBuildResult:
    """Build an unsigned, schema-valid TrustEnvelope payload from approved sources."""
    import sys

    before_modules = set(sys.modules)
    decision_subject = (
        request.subject_type
        if request.subject_type in SUPPORTED_P5_SUBJECT_TYPES
        else "match_verdict"
    )
    decisions = iter_field_source_decisions(decision_subject)
    validate_schema_canonicalization_compatibility(
        request.schema_version, request.canonicalization_version
    )
    created_at = _context_datetime(
        request.request_context,
        "created_at",
        datetime.now(timezone.utc),
    )
    audience_id = str(
        request.request_context.get("audience_id") or "b25-p5-internal-builder"
    )

    if request.subject_type not in SUPPORTED_P5_SUBJECT_TYPES:
        refusal = build_error_envelope(
            tenant_id=request.tenant_id,
            reason_code="subject_authority_rejected",
            created_at=created_at,
            audience_id=audience_id,
        )
        return TrustEnvelopeBuildResult(
            status="refused",
            unsigned_payload=None,
            refusal_payload=refusal,
            reason_code="subject_authority_rejected",
            field_source_decisions=decisions,
            money_authority_decision=None,
            read_only_observation=_read_only_observation(llm_modules=()),
            authority_witness=None,
        )

    issuance_locked = False
    if request.subject_type == "match_verdict":
        issuance_locked = await _acquire_issuance_lock(db_session)

    if source is not None:
        expected_ref = f"urn:skeldir:match_verdict:{source.id}"
        if isinstance(source, ConfidenceProjectionSource):
            expected_ref = f"urn:skeldir:confidence_projection:{source.id}"
        expected_type = (
            "confidence_projection"
            if isinstance(source, ConfidenceProjectionSource)
            else "match_verdict"
        )
        if (
            source.tenant_id != request.tenant_id
            or request.subject_type != expected_type
            or request.subject_ref.lower() != expected_ref.lower()
        ):
            raise TrustEnvelopeBuildError("prefetched_source_authority_mismatch")
    else:
        if request.subject_type == "match_verdict":
            source = await read_match_verdict_source(
                db_session,
                tenant_id=request.tenant_id,
                subject_ref=request.subject_ref,
            )
        else:
            source = await read_confidence_projection_source(
                db_session,
                tenant_id=request.tenant_id,
                subject_ref=request.subject_ref,
            )
    if source is None:
        refusal = build_error_envelope(
            tenant_id=request.tenant_id,
            reason_code="subject_authority_rejected",
            created_at=created_at,
            audience_id=audience_id,
        )
        return TrustEnvelopeBuildResult(
            status="refused",
            unsigned_payload=None,
            refusal_payload=refusal,
            reason_code="subject_authority_rejected",
            field_source_decisions=decisions,
            money_authority_decision=None,
            read_only_observation=_read_only_observation(llm_modules=()),
            authority_witness=None,
        )

    if issuance_locked and isinstance(source, MatchVerdictSource):
        refreshed = await read_match_verdict_source(
            db_session,
            tenant_id=request.tenant_id,
            subject_ref=request.subject_ref,
        )
        if refreshed is None or _source_evidence_tuple(
            refreshed
        ) != _source_evidence_tuple(source):
            refusal = build_error_envelope(
                tenant_id=request.tenant_id,
                reason_code="source_changed_during_issuance",
                created_at=created_at,
                audience_id=audience_id,
            )
            return TrustEnvelopeBuildResult(
                status="refused",
                unsigned_payload=None,
                refusal_payload=refusal,
                reason_code="source_changed_during_issuance",
                field_source_decisions=decisions,
                money_authority_decision=None,
                read_only_observation=_read_only_observation(llm_modules=()),
                authority_witness=None,
            )
        source = refreshed

    import os  # noqa: PLC0415

    if (
        os.getenv("B26_P2_SOURCE_EVIDENCE_REQUIRED", "").strip().lower()
        == "true"
    ):
        # The production confidence reader is a Trust subject, not the
        # internal project_b24_confidence helper. It must carry the same
        # complete-source witness as a match verdict.
        history_ok, history_reason = await read_history_integrity_status(
            db_session
        )
        if not history_ok:
            refusal = build_error_envelope(
                tenant_id=request.tenant_id,
                reason_code="history_integrity_unverifiable",
                created_at=created_at,
                audience_id=audience_id,
            )
            return TrustEnvelopeBuildResult(
                status="refused",
                unsigned_payload=None,
                refusal_payload=refusal,
                reason_code="history_integrity_unverifiable",
                field_source_decisions=decisions,
                money_authority_decision=None,
                read_only_observation=_read_only_observation(llm_modules=()),
                authority_witness=None,
            )

    if isinstance(source, ConfidenceProjectionSource):
        if payload_runner is None:
            payload = _confidence_projection_payload(request=request, source=source)
        else:
            payload = await payload_runner(
                _confidence_projection_payload,
                request=request,
                source=source,
            )
        from app.trust.policy_configuration import apply_tenant_policy

        await apply_tenant_policy(db_session, tenant_id=request.tenant_id, payload=payload)
        after_modules = set(sys.modules)
        llm_modules = _loaded_llm_modules(before_modules, after_modules)
        if llm_modules:
            raise TrustEnvelopeBuildError(
                f"p5_builder_loaded_forbidden_llm_modules:{','.join(llm_modules)}"
            )
        return TrustEnvelopeBuildResult(
            status="success",
            unsigned_payload=payload,
            refusal_payload=None,
            reason_code=None,
            field_source_decisions=decisions,
            money_authority_decision=None,
            read_only_observation=_read_only_observation(llm_modules=llm_modules),
            authority_witness=_build_authority_witness(
                payload=payload,
                decisions=decisions,
            ),
        )

    # XXII (H-XXII-12): the schema compatibility check must run at the
    # authorization point, not only at process start. A binary built for
    # an older schema must not issue against a newer database simply
    # because it started successfully.
    from app.core.construction_authority import (  # noqa: PLC0415
        ConstructionAuthorityError,
        assert_production_construction_authority,
        read_construction_revisions,
    )

    try:
        connection_factory = getattr(db_session, "connection", None)
        if connection_factory is not None:
            assert_production_construction_authority(
                await read_construction_revisions(await connection_factory())
            )
    except ConstructionAuthorityError:
        refusal = build_error_envelope(
            tenant_id=request.tenant_id,
            reason_code="schema_version_unsupported",
            created_at=created_at,
            audience_id=audience_id,
        )
        return TrustEnvelopeBuildResult(
            status="refused",
            unsigned_payload=None,
            refusal_payload=refusal,
            reason_code="schema_version_unsupported",
            field_source_decisions=decisions,
            money_authority_decision=None,
            read_only_observation=_read_only_observation(llm_modules=()),
            authority_witness=None,
        )

    # XXI (H-XXI-07/Gate N): live history-integrity gate for new
    # issuance. A Trust envelope asserts deterministic truth; when the
    # correction-history continuity proof is missing, stale, violated,
    # or divergent from live state, no envelope is issued. The claim
    # is refused, not qualified: an amount over unverifiable history
    # is not knowable truth.
    history_ok, history_reason = await read_history_integrity_status(
        db_session
    )
    if not history_ok:
        refusal = build_error_envelope(
            tenant_id=request.tenant_id,
            reason_code="history_integrity_unverifiable",
            created_at=created_at,
            audience_id=audience_id,
        )
        return TrustEnvelopeBuildResult(
            status="refused",
            unsigned_payload=None,
            refusal_payload=refusal,
            reason_code="history_integrity_unverifiable",
            field_source_decisions=decisions,
            money_authority_decision=None,
            read_only_observation=_read_only_observation(llm_modules=()),
            authority_witness=None,
        )

    conservation_ok, conservation_reason = (
        await read_source_money_conservation_status(
            db_session,
            tenant_id=request.tenant_id,
            verdict_id=source.id,
        )
    )
    if not conservation_ok:
        refusal = build_error_envelope(
            tenant_id=request.tenant_id,
            reason_code="money_source_not_authoritative",
            created_at=created_at,
            audience_id=audience_id,
        )
        return TrustEnvelopeBuildResult(
            status="refused",
            unsigned_payload=None,
            refusal_payload=refusal,
            reason_code="money_source_not_authoritative",
            field_source_decisions=decisions,
            money_authority_decision=None,
            read_only_observation=_read_only_observation(llm_modules=()),
            authority_witness=None,
        )

    # XXV (A6/A10): the conservation oracle above compares rows that a single
    # maintenance principal can rewrite together, which is exactly how both
    # XXIV audits produced an internally coherent false world. The sovereign
    # source attestation is the one piece of evidence that principal cannot
    # produce, so issuance now requires it and refuses an attestation that
    # contradicts the money being certified.
    from app.revenue_verification.source_attestation import (  # noqa: PLC0415
        read_verdict_source_attestation_status,
    )

    attestation = await read_verdict_source_attestation_status(
        db_session, tenant_id=request.tenant_id, verdict_id=source.id
    )
    if attestation.unverifiable:
        refusal = build_error_envelope(
            tenant_id=request.tenant_id,
            reason_code="money_source_not_authoritative",
            created_at=created_at,
            audience_id=audience_id,
        )
        return TrustEnvelopeBuildResult(
            status="refused",
            unsigned_payload=None,
            refusal_payload=refusal,
            reason_code="money_source_not_authoritative",
            field_source_decisions=decisions,
            money_authority_decision=None,
            read_only_observation=_read_only_observation(llm_modules=()),
            authority_witness=None,
        )

    money_decision = _money_decision_for_match_verdict(source)
    if not isinstance(money_decision, AuthoritativeMoneyMinor):
        refusal = build_error_envelope(
            tenant_id=request.tenant_id,
            reason_code="money_source_not_authoritative",
            created_at=created_at,
            audience_id=audience_id,
        )
        return TrustEnvelopeBuildResult(
            status="refused",
            unsigned_payload=None,
            refusal_payload=refusal,
            reason_code="money_source_not_authoritative",
            field_source_decisions=decisions,
            money_authority_decision=money_decision,
            read_only_observation=_read_only_observation(llm_modules=()),
            authority_witness=None,
        )

    if payload_runner is None:
        payload = _match_verdict_payload(
            request=request,
            source=source,
            money_decision=money_decision,
        )
    else:
        payload = await payload_runner(
            _match_verdict_payload,
            request=request,
            source=source,
            money_decision=money_decision,
        )
    from app.trust.policy_configuration import apply_tenant_policy

    await apply_tenant_policy(db_session, tenant_id=request.tenant_id, payload=payload)
    after_modules = set(sys.modules)
    llm_modules = _loaded_llm_modules(before_modules, after_modules)
    if llm_modules:
        raise TrustEnvelopeBuildError(
            f"p5_builder_loaded_forbidden_llm_modules:{','.join(llm_modules)}"
        )
    return TrustEnvelopeBuildResult(
        status="success",
        unsigned_payload=payload,
        refusal_payload=None,
        reason_code=None,
        field_source_decisions=decisions,
        money_authority_decision=money_decision,
        read_only_observation=_read_only_observation(llm_modules=llm_modules),
        authority_witness=_build_authority_witness(
            payload=payload,
            decisions=decisions,
        ),
    )
