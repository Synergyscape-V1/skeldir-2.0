"""Neutral, immutable semantic registry for inference policy bundles.

This module is deliberately outside both ``app.bayesian`` and ``app.trust``.
The producer and the read-only Trust consumer may both resolve a persisted
bundle without either layer importing the other.  A bundle identity is the
SHA-256 digest of the complete governed manifest, not a digest of labels.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping


INFERENCE_PROFILE_VERSION = "b24-inference-profile-v2"
RUNTIME_POLICY_VERSION = "b24-p5-runtime-policy-v2"
SAMPLING_POLICY_VERSION = "b24-p6-sampling-policy-v2"
DIAGNOSTIC_POLICY_VERSION = "b24-p7-diagnostic-policy-v2"
CONFIDENCE_POLICY_VERSION = "b24-p10-confidence-policy-v1"
CONFIDENCE_SEMANTICS_VERSION = "b24-p10-confidence-semantics-v1"


class PolicyRegistryError(RuntimeError):
    """Persisted provenance cannot be resolved to immutable semantics."""


def canonical_json(value: Mapping[str, Any]) -> str:
    """Return the one canonical encoding used for semantic identities."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def semantic_digest(value: Mapping[str, Any]) -> str:
    """Content identity for one policy or a complete policy bundle."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


# This manifest is historical authority.  Existing entries are never edited;
# a semantic change adds a new component version and a new complete manifest.
# The C11 validator mechanically compares every live producer policy with this
# record, while Trust imports only this neutral module.
_HISTORICAL_P1_MANIFEST: dict[str, Any] = {
    "schema_version": "b24-inference-policy-manifest-v1",
    "components": {
        "inference_profile": {
            "version": INFERENCE_PROFILE_VERSION,
            "semantics": {
                "fit_execution_budget_seconds": 240,
                "sampler_supervisor_deadline_seconds": 240,
                "celery_soft_time_limit_seconds": 270,
                "celery_hard_time_limit_seconds": 300,
                "dispatch_lease_recovery_margin_seconds": 30,
                "runtime_correspondence_required": True,
                "observed_posterior_correspondence_required": True,
            },
        },
        "runtime_policy": {
            "version": RUNTIME_POLICY_VERSION,
            "semantics": {
                "worker_concurrency": 1,
                "pymc_cores": 1,
                "pymc_chains": 4,
                "blas_total_threads": 1,
                "sampler_supervisor_deadline_seconds": 240,
                "celery_soft_time_limit_seconds": 270,
                "celery_hard_time_limit_seconds": 300,
                "worker_sampler_explicit_runtime_record": True,
            },
        },
        "sampling_policy": {
            "version": SAMPLING_POLICY_VERSION,
            "semantics": {
                "draws_per_chain": 1000,
                "tune_per_chain": 1000,
                "chains": 4,
                "cores": 1,
                "blas_cores": 1,
                "target_accept": 0.9,
                "init": "jitter+adapt_diag",
                "posterior_draws_total": 4000,
                "total_chain_iterations": 8000,
            },
        },
        "diagnostic_policy": {
            "version": DIAGNOSTIC_POLICY_VERSION,
            "semantics": {
                "diagnostic_target_filter_version": "b24-p7-target-filter-v1",
                "interval_policy_version": "b24-p7-interval-policy-v1",
                "hdi_probability": 0.95,
                "diagnostic_target_var_names": ["mu"],
                "diagnostic_target_coords": {},
                "interval_target_var_names": ["mu"],
                "interval_target_coords": {},
                "excluded_deterministic_var_names": ["observed_signal"],
                "allowed_interval_targets": ["mu"],
                "max_diagnostic_variables": 4,
                "max_diagnostic_elements": 4096,
                "max_diagnostic_coords": 8,
                "max_hdi_elements": 4,
                "max_interval_dimensions": 1,
                "max_interval_elements": 4,
                "max_interval_summary_bytes": 2048,
                "r_hat_max_threshold": 1.01,
                "ess_min_threshold": 400.0,
                "divergence_count_threshold": 0,
                "min_chains": 4,
                "min_samples_actual": 1,
                "finite_value_policy": "required",
            },
        },
        # Confidence classification is decision-significant and its identifiers
        # are signed.  It therefore belongs in the resolvable manifest even
        # though it is applied after posterior diagnostics.  Resource admission
        # is intentionally excluded: it decides whether work may start, not the
        # semantics of a posterior or confidence that was actually produced.
        "confidence_policy": {
            "version": CONFIDENCE_POLICY_VERSION,
            "semantics_version": CONFIDENCE_SEMANTICS_VERSION,
            "semantics": {
                "available_requires": [
                    "diagnostic_status=passed",
                    "credible_interval_status=available",
                    "artifact_identity_present",
                    "single_currency",
                ],
                "width_ratio_high_max": 0.10,
                "width_ratio_medium_max": 0.25,
                "money_authority": "deterministic_minor_units_only",
            },
        },
    },
}

# P2 is a real semantic evolution of the bundle, not a label-only bump.  P1
# described producer/runtime/confidence semantics but did not require the
# signer itself to resolve them.  P2 makes that final authority boundary part
# of the meaning of an issuable TrustEnvelope.  P1 remains byte-for-byte
# resolvable below; current issuance is P2-only.
_CURRENT_MANIFEST: dict[str, Any] = deepcopy(_HISTORICAL_P1_MANIFEST)
_CURRENT_MANIFEST["components"]["trust_issuance_policy"] = {
    "version": "b25-p13-trust-issuance-policy-v2",
    "semantics": {
        "semantic_validation_before_private_key_signature": True,
        "available_confidence_requires_current_policy_bundle": True,
        "available_confidence_requires_runtime_correspondence": True,
        "historical_bundle_resolution_is_read_only": True,
        "historical_bundle_reissuance_forbidden": True,
    },
}

CURRENT_POLICY_BUNDLE_HASH = semantic_digest(_CURRENT_MANIFEST)
HISTORICAL_P1_POLICY_BUNDLE_HASH = semantic_digest(_HISTORICAL_P1_MANIFEST)

_POLICY_MANIFESTS_BY_HASH: dict[str, dict[str, Any]] = {
    HISTORICAL_P1_POLICY_BUNDLE_HASH: _HISTORICAL_P1_MANIFEST,
    CURRENT_POLICY_BUNDLE_HASH: _CURRENT_MANIFEST,
}


def current_manifest() -> dict[str, Any]:
    """Return a defensive copy so callers cannot mutate registry authority."""

    return deepcopy(_CURRENT_MANIFEST)


def current_policy_tuple() -> dict[str, str]:
    """Persisted identifiers that must correspond to the current bundle."""

    return {
        "inference_profile_version": INFERENCE_PROFILE_VERSION,
        "runtime_policy_version": RUNTIME_POLICY_VERSION,
        "sampling_policy_version": SAMPLING_POLICY_VERSION,
        "diagnostic_policy_version": DIAGNOSTIC_POLICY_VERSION,
    }


def current_component_digests() -> dict[str, str]:
    """Independently auditable identities for every governed component."""

    return {
        name: semantic_digest(component)
        for name, component in _CURRENT_MANIFEST["components"].items()
    }


def resolve_policy_bundle(policy_bundle_hash: object) -> dict[str, Any]:
    """Resolve one immutable historical bundle by content identity."""

    raw_hash = str(policy_bundle_hash or "")
    bundle_hash = raw_hash.removeprefix("sha256:")
    manifest = _POLICY_MANIFESTS_BY_HASH.get(bundle_hash)
    if manifest is None:
        raise PolicyRegistryError("policy_bundle_unknown_or_semantically_rewritten")
    if semantic_digest(manifest) != bundle_hash:
        raise PolicyRegistryError("policy_bundle_registry_integrity_failure")
    return deepcopy(manifest)


def _manifest_policy_tuple(manifest: Mapping[str, Any]) -> dict[str, str]:
    components = manifest["components"]
    return {
        "inference_profile_version": components["inference_profile"]["version"],
        "runtime_policy_version": components["runtime_policy"]["version"],
        "sampling_policy_version": components["sampling_policy"]["version"],
        "diagnostic_policy_version": components["diagnostic_policy"]["version"],
    }


def resolve_policy_provenance(
    provenance: Mapping[str, object],
    *,
    confidence_policy_version: object | None = None,
    confidence_semantics_version: object | None = None,
) -> dict[str, Any]:
    """Resolve current or historical provenance and prove internal meaning."""

    manifest = resolve_policy_bundle(provenance.get("policy_bundle_hash"))
    expected = _manifest_policy_tuple(manifest)
    for field, expected_value in expected.items():
        if provenance.get(field) != expected_value:
            raise PolicyRegistryError(f"policy_bundle_tuple_mismatch:{field}")
    confidence = manifest["components"]["confidence_policy"]
    expected_confidence_policy = confidence["version"]
    expected_confidence_semantics = confidence["semantics_version"]
    supplied_policy = (
        confidence_policy_version
        if confidence_policy_version is not None
        else provenance.get("confidence_policy_version")
    )
    supplied_semantics = (
        confidence_semantics_version
        if confidence_semantics_version is not None
        else provenance.get("confidence_semantics_version")
    )
    if supplied_policy != expected_confidence_policy:
        raise PolicyRegistryError("confidence_policy_version_unknown")
    if supplied_semantics != expected_confidence_semantics:
        raise PolicyRegistryError("confidence_semantics_version_unknown")

    sampling = manifest["components"]["sampling_policy"]["semantics"]
    runtime = manifest["components"]["runtime_policy"]["semantics"]
    diagnostics = manifest["components"]["diagnostic_policy"]["semantics"]
    expected_chains = sampling["chains"]
    expected_draws = sampling["posterior_draws_total"]
    if runtime["pymc_chains"] != expected_chains:
        raise PolicyRegistryError("policy_bundle_runtime_chain_contradiction")
    if diagnostics["min_chains"] != expected_chains:
        raise PolicyRegistryError("policy_bundle_diagnostic_chain_contradiction")
    for field in ("authorized_chains", "observed_chains"):
        if provenance.get(field) != expected_chains:
            raise PolicyRegistryError(f"policy_bundle_runtime_mismatch:{field}")
    for field in (
        "authorized_posterior_draws_total",
        "observed_posterior_draws_total",
    ):
        if provenance.get(field) != expected_draws:
            raise PolicyRegistryError(f"policy_bundle_runtime_mismatch:{field}")
    return manifest


def validate_policy_provenance(
    provenance: Mapping[str, object],
    *,
    confidence_policy_version: object | None = None,
    confidence_semantics_version: object | None = None,
) -> dict[str, Any]:
    """Resolve provenance or fail closed before any available claim is signed."""

    manifest = resolve_policy_provenance(
        provenance,
        confidence_policy_version=confidence_policy_version,
        confidence_semantics_version=confidence_semantics_version,
    )
    raw_hash = str(provenance.get("policy_bundle_hash") or "")
    if raw_hash.removeprefix("sha256:") != CURRENT_POLICY_BUNDLE_HASH:
        raise PolicyRegistryError("historical_policy_bundle_not_issuable")
    return manifest


def validate_envelope_policy_authority(payload: Mapping[str, object]) -> None:
    """Fail closed at the final pre-sign TrustEnvelope authority boundary."""

    metadata = payload.get("confidence_metadata")
    if not isinstance(metadata, Mapping):
        raise PolicyRegistryError("confidence_metadata_missing")
    provenance = metadata.get("inference_provenance")
    status = metadata.get("confidence_status")
    if status == "available":
        if not isinstance(provenance, Mapping):
            raise PolicyRegistryError("available_confidence_provenance_missing")
        validate_policy_provenance(provenance)
        return
    # No inference is the honest state for deterministic-only envelopes.  If a
    # degraded envelope does name a regime, however, it may not name nonsense.
    if provenance is not None:
        if not isinstance(provenance, Mapping):
            raise PolicyRegistryError("inference_provenance_invalid")
        resolve_policy_provenance(provenance)


__all__ = (
    "CONFIDENCE_POLICY_VERSION",
    "CONFIDENCE_SEMANTICS_VERSION",
    "CURRENT_POLICY_BUNDLE_HASH",
    "HISTORICAL_P1_POLICY_BUNDLE_HASH",
    "DIAGNOSTIC_POLICY_VERSION",
    "INFERENCE_PROFILE_VERSION",
    "PolicyRegistryError",
    "RUNTIME_POLICY_VERSION",
    "SAMPLING_POLICY_VERSION",
    "canonical_json",
    "current_component_digests",
    "current_manifest",
    "current_policy_tuple",
    "resolve_policy_bundle",
    "resolve_policy_provenance",
    "semantic_digest",
    "validate_envelope_policy_authority",
    "validate_policy_provenance",
)
