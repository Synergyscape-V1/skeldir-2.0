"""B2.5-P7 canonical provenance-chain assembly."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

from app.trust.array_ordering import canonicalize_array_by_declared_ordering
from app.trust.refusal import tagged_sha256, utc_second
from app.trust.source_adapters import MatchVerdictSource


ProvenanceAvailability = Literal["available", "explicit_unavailable", "deferred"]

_EMPTY_SHA = "sha256:" + ("0" * 64)


@dataclass(frozen=True)
class ProvenanceSourceRegistration:
    """Registry row for one P7-required provenance source class."""

    source_class: str
    provenance_type: str
    authority_table: str
    required_for_match_verdict: bool
    availability_when_missing: ProvenanceAvailability
    source_path: str

    def external_projection(self) -> dict[str, object]:
        return asdict(self)


REQUIRED_P7_PROVENANCE_SOURCE_CLASSES: tuple[ProvenanceSourceRegistration, ...] = (
    ProvenanceSourceRegistration(
        "webhook_ingress_identity",
        "webhook_signature",
        "webhook_ingress_identities",
        True,
        "explicit_unavailable",
        "b23_match_verdicts.webhook_ingress_identity_id",
    ),
    ProvenanceSourceRegistration(
        "provider_native_references",
        "provider_native_reference",
        "b23_match_verdicts",
        True,
        "explicit_unavailable",
        "b23_match_verdicts.provider_native_*",
    ),
    ProvenanceSourceRegistration(
        "b23_dispatch_match_verdict_lineage",
        "match_verdict",
        "b23_match_verdicts",
        True,
        "explicit_unavailable",
        "b23_match_verdicts",
    ),
    ProvenanceSourceRegistration(
        "deterministic_attribution_output_refs",
        "attribution_allocation",
        "attribution_allocations",
        False,
        "explicit_unavailable",
        "future supported subject type",
    ),
    ProvenanceSourceRegistration(
        "b24_source_snapshot_hash",
        "b24_source_snapshot",
        "b24_confidence_projection",
        False,
        "explicit_unavailable",
        "b24 confidence projection input",
    ),
    ProvenanceSourceRegistration(
        "b24_fit_id",
        "bayesian_fit",
        "bayesian_model_fits",
        False,
        "explicit_unavailable",
        "b24 confidence projection input",
    ),
    ProvenanceSourceRegistration(
        "b24_diagnostic_fallback_status",
        "bayesian_diagnostic",
        "bayesian_model_fits",
        False,
        "explicit_unavailable",
        "b24 confidence projection input",
    ),
    ProvenanceSourceRegistration(
        "b24_artifact_ref_hash",
        "bayesian_artifact",
        "bayesian_artifacts",
        False,
        "explicit_unavailable",
        "b24 artifact projection input",
    ),
    ProvenanceSourceRegistration(
        "policy_authority_source",
        "policy_decision",
        "trust_policy_defaults",
        True,
        "available",
        "backend/app/trust/policy_defaults.py",
    ),
    ProvenanceSourceRegistration(
        "text_disposition_transform_version",
        "text_disposition",
        "trust_text_disposition",
        True,
        "available",
        "backend/app/trust/text_disposition.py",
    ),
    ProvenanceSourceRegistration(
        "money_authority_source",
        "money_authority",
        "trust_money_authority",
        True,
        "available",
        "backend/app/trust/money_source_adapter.py",
    ),
    ProvenanceSourceRegistration(
        "reason_code_decision",
        "reason_code_decision",
        "trust_reason_truth_matrix",
        True,
        "available",
        "backend/app/trust/reason_truth_matrix.py",
    ),
    ProvenanceSourceRegistration(
        "audit_access_record_ref",
        "audit_access_record",
        "trust_access_log",
        True,
        "deferred",
        "backend/app/trust/audit.py",
    ),
    ProvenanceSourceRegistration(
        "audit_access_record_hash",
        "audit_hash",
        "trust_access_log",
        True,
        "deferred",
        "backend/app/trust/audit_hash.py",
    ),
)


def required_source_class_names() -> tuple[str, ...]:
    """Return deterministic P7 source-class names."""
    return tuple(row.source_class for row in REQUIRED_P7_PROVENANCE_SOURCE_CLASSES)


def _source_ref_hash(source_ref: str) -> str:
    return tagged_sha256({"source_ref": source_ref})


def _entry(
    *,
    provenance_type: str,
    authority_table: str,
    source_ref: str,
    source_snapshot_hash: str,
    observed_at: datetime | str,
    display_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "provenance_type": provenance_type,
        "authority_table": authority_table,
        "source_ref": source_ref,
        "source_ref_hash": _source_ref_hash(source_ref),
        "source_snapshot_hash": source_snapshot_hash,
        "observed_at": (
            observed_at if isinstance(observed_at, str) else utc_second(observed_at)
        ),
        "display_metadata": display_metadata or none_display_metadata(),
    }


def none_display_metadata() -> dict[str, object]:
    """Return display metadata that carries no raw provider text."""
    return {
        "text_trust_class": "none",
        "raw_text_sha256": None,
        "display_transform": "none",
    }


def display_metadata_from_disposed_text(
    display_data: dict[str, object],
) -> dict[str, object]:
    """Project P3 text-disposition output into provenance display metadata."""
    raw_hash = display_data.get("raw_text_sha256")
    if isinstance(raw_hash, str) and raw_hash.startswith("sha256:"):
        return {
            "text_trust_class": "provider_controlled_quarantined",
            "raw_text_sha256": raw_hash,
            "display_transform": "redacted",
        }
    transform = str(display_data.get("display_transform") or "none")
    if transform == "escaped_display_only":
        return {
            "text_trust_class": "operator_controlled_safe_label",
            "raw_text_sha256": None,
            "display_transform": "escaped_display_only",
        }
    return none_display_metadata()


def _unavailable_entry(
    registration: ProvenanceSourceRegistration,
    *,
    observed_at: datetime | str,
) -> dict[str, object]:
    source_ref = f"urn:skeldir:unavailable:{registration.source_class}"
    return _entry(
        provenance_type="explicit_unavailable",
        authority_table="trust_provenance_source_registry",
        source_ref=source_ref,
        source_snapshot_hash=tagged_sha256(
            {
                "source_class": registration.source_class,
                "availability": registration.availability_when_missing,
                "source_path": registration.source_path,
            }
        ),
        observed_at=observed_at,
    )


def _webhook_ingress_entry(source: MatchVerdictSource) -> dict[str, object]:
    if source.webhook_ingress_identity_id is None:
        registration = _registration("webhook_ingress_identity")
        return _unavailable_entry(registration, observed_at=source.updated_at)
    source_ref = (
        "urn:skeldir:webhook_ingress_identity:" f"{source.webhook_ingress_identity_id}"
    )
    return _entry(
        provenance_type="webhook_signature",
        authority_table="webhook_ingress_identities",
        source_ref=source_ref,
        source_snapshot_hash=tagged_sha256(
            {
                "webhook_ingress_identity_id": str(source.webhook_ingress_identity_id),
                "provider": source.provider,
                "match_verdict_id": str(source.id),
            }
        ),
        observed_at=source.created_at,
    )


def _provider_reference_entry(source: MatchVerdictSource) -> dict[str, object]:
    reference_hash = tagged_sha256(
        {
            "provider": source.provider,
            "event_reference": source.provider_native_event_reference,
            "commerce_reference": source.provider_native_commerce_reference,
        }
    ).split(":", 1)[1]
    return _entry(
        provenance_type="provider_native_reference",
        authority_table="b23_match_verdicts",
        source_ref=f"urn:skeldir:provider_native_reference:{reference_hash}",
        source_snapshot_hash=tagged_sha256(
            {
                "provider": source.provider,
                "provider_native_event_reference_hash": tagged_sha256(
                    source.provider_native_event_reference
                ),
                "provider_native_commerce_reference_hash": tagged_sha256(
                    source.provider_native_commerce_reference
                ),
            }
        ),
        observed_at=source.created_at,
    )


def _match_verdict_entry(
    source: MatchVerdictSource,
    *,
    display_data: dict[str, object],
) -> dict[str, object]:
    source_ref = f"urn:skeldir:b23_match_verdicts:{source.id}"
    return _entry(
        provenance_type="match_verdict",
        authority_table="b23_match_verdicts",
        source_ref=source_ref,
        source_snapshot_hash=tagged_sha256(
            {
                "source": "b23_match_verdicts",
                "id": str(source.id),
                "status": source.status,
                "amount_minor": source.canonical_net_verified_amount_minor,
                "currency": source.currency_code,
                "updated_at": utc_second(source.updated_at),
            }
        ),
        observed_at=source.last_transition_at,
        display_metadata=display_metadata_from_disposed_text(display_data),
    )


def _internal_decision_entry(
    registration: ProvenanceSourceRegistration,
    *,
    observed_at: datetime | str,
    decision_material: dict[str, object],
) -> dict[str, object]:
    source_ref = f"urn:skeldir:{registration.source_class}:{tagged_sha256(decision_material).split(':', 1)[1]}"
    return _entry(
        provenance_type=registration.provenance_type,
        authority_table=registration.authority_table,
        source_ref=source_ref,
        source_snapshot_hash=tagged_sha256(
            {
                "source_class": registration.source_class,
                "source_path": registration.source_path,
                "decision_material": decision_material,
            }
        ),
        observed_at=observed_at,
    )


def _registration(source_class: str) -> ProvenanceSourceRegistration:
    for row in REQUIRED_P7_PROVENANCE_SOURCE_CLASSES:
        if row.source_class == source_class:
            return row
    raise KeyError(source_class)


def canonicalize_provenance_chain(
    entries: list[dict[str, object]] | tuple[dict[str, object], ...],
) -> list[dict[str, object]]:
    """Return provenance entries ordered by the P2 array-ordering manifest."""
    return canonicalize_array_by_declared_ordering(
        "provenance_chain", [deepcopy(entry) for entry in entries]
    )


def build_match_verdict_provenance_chain(
    *,
    source: MatchVerdictSource,
    display_data: dict[str, object],
    money_authority_projection: dict[str, object] | None,
    reason_code: str | None,
    audit_ref: str | None = None,
    audit_hash: str | None = None,
) -> list[dict[str, object]]:
    """Build canonical P7 provenance for the currently supported subject type."""
    entries: list[dict[str, object]] = [
        _webhook_ingress_entry(source),
        _provider_reference_entry(source),
        _match_verdict_entry(source, display_data=display_data),
    ]
    observed_at = source.updated_at
    unavailable_sources = {
        "deterministic_attribution_output_refs",
        "b24_source_snapshot_hash",
        "b24_fit_id",
        "b24_diagnostic_fallback_status",
        "b24_artifact_ref_hash",
    }
    for source_class in unavailable_sources:
        entries.append(
            _unavailable_entry(_registration(source_class), observed_at=observed_at)
        )
    entries.extend(
        [
            _internal_decision_entry(
                _registration("policy_authority_source"),
                observed_at=observed_at,
                decision_material={"policy_state": "read_only"},
            ),
            _internal_decision_entry(
                _registration("text_disposition_transform_version"),
                observed_at=observed_at,
                decision_material={
                    "text_disposition_version": display_data.get(
                        "text_disposition_version"
                    ),
                    "display_transform": display_data.get("display_transform"),
                    "raw_text_sha256": display_data.get("raw_text_sha256"),
                },
            ),
            _internal_decision_entry(
                _registration("money_authority_source"),
                observed_at=observed_at,
                decision_material=money_authority_projection
                or {"money_authority": "unavailable"},
            ),
            _internal_decision_entry(
                _registration("reason_code_decision"),
                observed_at=observed_at,
                decision_material={"reason_code": reason_code or "none"},
            ),
        ]
    )
    entries.extend(
        _audit_entries(
            observed_at=observed_at,
            audit_ref=audit_ref,
            audit_hash=audit_hash,
        )
    )
    return canonicalize_provenance_chain(entries)


def _audit_entries(
    *,
    observed_at: datetime | str,
    audit_ref: str | None,
    audit_hash: str | None,
) -> list[dict[str, object]]:
    if not audit_ref or not audit_hash:
        return [
            _unavailable_entry(
                _registration("audit_access_record_ref"), observed_at=observed_at
            ),
            _unavailable_entry(
                _registration("audit_access_record_hash"), observed_at=observed_at
            ),
        ]
    return [
        _entry(
            provenance_type="audit_access_record",
            authority_table="trust_access_log",
            source_ref=audit_ref,
            source_snapshot_hash=audit_hash,
            observed_at=observed_at,
        ),
        _entry(
            provenance_type="audit_hash",
            authority_table="trust_access_log",
            source_ref=f"urn:skeldir:audit_hash:{audit_hash.split(':', 1)[1]}",
            source_snapshot_hash=audit_hash,
            observed_at=observed_at,
        ),
    ]


def replace_audit_provenance_entries(
    provenance_chain: list[dict[str, object]],
    *,
    audit_ref: str,
    audit_hash: str,
    observed_at: datetime | str,
) -> list[dict[str, object]]:
    """Replace deferred audit provenance entries with persisted audit refs."""
    filtered = [
        deepcopy(entry)
        for entry in provenance_chain
        if entry.get("provenance_type") not in {"audit_access_record", "audit_hash"}
        and entry.get("source_ref")
        not in {
            "urn:skeldir:unavailable:audit_access_record_ref",
            "urn:skeldir:unavailable:audit_access_record_hash",
        }
    ]
    filtered.extend(
        _audit_entries(
            observed_at=observed_at, audit_ref=audit_ref, audit_hash=audit_hash
        )
    )
    return canonicalize_provenance_chain(filtered)
