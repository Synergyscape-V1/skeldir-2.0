"""B2.5-P13 C13: register signer-enforced policy semantics.

Revision ID: 202608271200
Revises: 202608261200
"""

from __future__ import annotations

import json

from alembic import op


revision = "202608271200"
down_revision = "202608261200"
branch_labels = None
depends_on = None

POLICY_BUNDLE_HASH = "66cb748ab92eca922c27fca5f27e41a2d3282d7d511e7674524f018f9bc83a28"
POLICY_TUPLE = {
    "inference_profile_version": "b24-inference-profile-v2",
    "runtime_policy_version": "b24-p5-runtime-policy-v2",
    "sampling_policy_version": "b24-p6-sampling-policy-v2",
    "diagnostic_policy_version": "b24-p7-diagnostic-policy-v2",
}
CONFIDENCE_POLICY_VERSION = "b24-p10-confidence-policy-v1"
CONFIDENCE_SEMANTICS_VERSION = "b24-p10-confidence-semantics-v1"

# Frozen migration data: never import live application policy into history.
SEMANTIC_MANIFEST = {
    "schema_version": "b24-inference-policy-manifest-v1",
    "components": {
        "inference_profile": {
            "version": "b24-inference-profile-v2",
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
            "version": "b24-p5-runtime-policy-v2",
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
            "version": "b24-p6-sampling-policy-v2",
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
            "version": "b24-p7-diagnostic-policy-v2",
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
        "confidence_policy": {
            "version": "b24-p10-confidence-policy-v1",
            "semantics_version": "b24-p10-confidence-semantics-v1",
            "semantics": {
                "available_requires": [
                    "diagnostic_status=passed",
                    "credible_interval_status=available",
                    "artifact_identity_present",
                    "single_currency",
                ],
                "width_ratio_high_max": 0.1,
                "width_ratio_medium_max": 0.25,
                "money_authority": "deterministic_minor_units_only",
            },
        },
        "trust_issuance_policy": {
            "version": "b25-p13-trust-issuance-policy-v2",
            "semantics": {
                "semantic_validation_before_private_key_signature": True,
                "available_confidence_requires_current_policy_bundle": True,
                "available_confidence_requires_runtime_correspondence": True,
                "historical_bundle_resolution_is_read_only": True,
                "historical_bundle_reissuance_forbidden": True,
            },
        },
    },
}
COMPONENT_DIGESTS = {
    "confidence_policy": "e7f1627ba3f0654b1891cb9484735cc54ead291471dc66ed7074a4eeee66d862",
    "diagnostic_policy": "0022df7fb2555854fcefb5f5f3f48470e65990168a6837a821c87b2ec7f49fdc",
    "inference_profile": "f484b4bfaac96a874f84c6a747d0b9139f19d38377a74515fb179898d2736601",
    "runtime_policy": "1692cf404180c2fdb370c7c33305aca37ca2e839519beb617ed86cf87bd881c2",
    "sampling_policy": "b9bda475d8a2027798f7231ad723dc74b76c70b279eba1f5cc64f92225fc0404",
    "trust_issuance_policy": "c111940333cdb0b26238752b2d03477915c85e8f024a65487ece461721f4b9a7",
}


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        """
        INSERT INTO public.b24_inference_policy_registry (
            policy_bundle_hash, inference_profile_version,
            runtime_policy_version, sampling_policy_version,
            diagnostic_policy_version, confidence_policy_version,
            confidence_semantics_version, semantic_manifest, component_digests
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
        ON CONFLICT (policy_bundle_hash) DO NOTHING
        """,
        (
            POLICY_BUNDLE_HASH,
            POLICY_TUPLE["inference_profile_version"],
            POLICY_TUPLE["runtime_policy_version"],
            POLICY_TUPLE["sampling_policy_version"],
            POLICY_TUPLE["diagnostic_policy_version"],
            CONFIDENCE_POLICY_VERSION,
            CONFIDENCE_SEMANTICS_VERSION,
            json.dumps(SEMANTIC_MANIFEST, sort_keys=True, separators=(",", ":")),
            json.dumps(COMPONENT_DIGESTS, sort_keys=True, separators=(",", ":")),
        ),
    )


def downgrade() -> None:
    # CI:DESTRUCTIVE_OK - controlled rollback of the single registry row added
    # by this revision; the immutable trigger is restored in the same statement.
    op.execute(
        "ALTER TABLE public.b24_inference_policy_registry DISABLE TRIGGER trg_b24_policy_registry_immutable"
    )
    op.get_bind().exec_driver_sql(
        "DELETE FROM public.b24_inference_policy_registry WHERE policy_bundle_hash = %s",
        (POLICY_BUNDLE_HASH,),
    )
    op.execute(
        "ALTER TABLE public.b24_inference_policy_registry ENABLE TRIGGER trg_b24_policy_registry_immutable"
    )
