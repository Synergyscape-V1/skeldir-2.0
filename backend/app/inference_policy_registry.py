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
_CURRENT_MANIFEST: dict[str, Any] = {
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

CURRENT_POLICY_BUNDLE_HASH = semantic_digest(_CURRENT_MANIFEST)


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


def validate_policy_provenance(
    provenance: Mapping[str, object],
    *,
    confidence_policy_version: object | None = None,
    confidence_semantics_version: object | None = None,
) -> dict[str, Any]:
    """Resolve provenance or fail closed before any available claim is signed."""

    raw_hash = str(provenance.get("policy_bundle_hash") or "")
    bundle_hash = raw_hash.removeprefix("sha256:")
    if bundle_hash != CURRENT_POLICY_BUNDLE_HASH:
        raise PolicyRegistryError("policy_bundle_unknown_or_semantically_rewritten")
    expected = current_policy_tuple()
    for field, expected_value in expected.items():
        if provenance.get(field) != expected_value:
            raise PolicyRegistryError(f"policy_bundle_tuple_mismatch:{field}")
    if (
        confidence_policy_version is not None
        and confidence_policy_version != CONFIDENCE_POLICY_VERSION
    ):
        raise PolicyRegistryError("confidence_policy_version_unknown")
    if (
        confidence_semantics_version is not None
        and confidence_semantics_version != CONFIDENCE_SEMANTICS_VERSION
    ):
        raise PolicyRegistryError("confidence_semantics_version_unknown")
    return current_manifest()


__all__ = (
    "CONFIDENCE_POLICY_VERSION",
    "CONFIDENCE_SEMANTICS_VERSION",
    "CURRENT_POLICY_BUNDLE_HASH",
    "DIAGNOSTIC_POLICY_VERSION",
    "INFERENCE_PROFILE_VERSION",
    "PolicyRegistryError",
    "RUNTIME_POLICY_VERSION",
    "SAMPLING_POLICY_VERSION",
    "canonical_json",
    "current_component_digests",
    "current_manifest",
    "current_policy_tuple",
    "semantic_digest",
    "validate_policy_provenance",
)
