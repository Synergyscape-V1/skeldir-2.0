"""B2.5-P13 C9: planner-owned degradation authority.

The planner decides that a source cannot be fitted. Recording that decision is
not a computational result -- nothing was sampled, no artifact exists, no
posterior was drawn -- but until now the dispatch fence treated it as one.

The fence has always admitted two planner-authored states without dispatch
authority, ``queued`` and ``pending``, because scheduling a fit is not the same
act as producing one. Declaring that a fit *cannot* happen belongs to the same
category and was simply missing from the list, so the planner's own governed
fallback write raised ``b24_dispatch_fence_rejected`` from inside a trigger,
with nothing in the Python call stack expecting a database exception there. A
legitimate negative state became an uncontrolled failure.

This adds the missing state, and adds it narrowly. The exemption is not "any
fallback_only insert" -- that would let anything holding write access to the
Bayesian plane manufacture degradation, and degradation is an input to signed
Trust results. It is admitted only for a row that carries no computational
consequence whatsoever:

    no artifact, no artifact hash, no confidence evidence hash
    no sampling, fit or completion timestamps
    no runtime, sample count, chain count
    no r-hat, no ESS, no divergences, no credible interval
    and a confidence bucket that is explicitly unavailable

A row claiming degradation while carrying a posterior, an artifact, or a usable
confidence is still refused. Worker-produced fit and artifact truth still
requires a valid dispatch lease, unchanged.

The forgery boundary underneath this is the table grant, not the trigger:
``app_user`` -- the API runtime role -- holds SELECT only on
``bayesian_model_fits``. Nothing reachable from an HTTP request can write a fit
row of any shape.

Revision ID: 202608240900
Revises: 202608231200
"""

from __future__ import annotations

from alembic import op


revision = "202608240900"
down_revision = "202608231200"
branch_labels = None
depends_on = None


PLANNER_DECLARATION_FENCE = """
CREATE OR REPLACE FUNCTION public.b24_enforce_dispatch_fence()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            v_tenant_id uuid;
            v_fit_id uuid;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'b24_dispatch_delete_forbidden';
            END IF;

            IF TG_OP = 'UPDATE' THEN
                IF TG_ARGV[0] = 'fit' THEN
                    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                       OR NEW.id IS DISTINCT FROM OLD.id THEN
                        RAISE EXCEPTION 'b24_dispatch_immutable_fit_authority';
                    END IF;
                    -- B2.5-P13 C5: the planner owns fit creation and scheduling
                    -- bookkeeping and never holds a dispatch lease. An update
                    -- that changes no authority-bearing column changes nothing
                    -- the fence exists to protect.
                    IF NOT (NEW.status IS DISTINCT FROM OLD.status
               OR NEW.source_snapshot_hash IS DISTINCT FROM OLD.source_snapshot_hash
               OR NEW.source_read_started_at IS DISTINCT FROM OLD.source_read_started_at
               OR NEW.source_read_completed_at IS DISTINCT FROM OLD.source_read_completed_at
               OR NEW.data_completeness_status IS DISTINCT FROM OLD.data_completeness_status
               OR NEW.fallback_applied IS DISTINCT FROM OLD.fallback_applied
               OR NEW.fallback_reason IS DISTINCT FROM OLD.fallback_reason
               OR NEW.diagnostic_status IS DISTINCT FROM OLD.diagnostic_status
               OR NEW.diagnostic_failure_reason IS DISTINCT FROM OLD.diagnostic_failure_reason
               OR NEW.diagnostic_policy_version IS DISTINCT FROM OLD.diagnostic_policy_version
               OR NEW.diagnostic_target_filter_version IS DISTINCT FROM OLD.diagnostic_target_filter_version
               OR NEW.diagnostics_computed_at IS DISTINCT FROM OLD.diagnostics_computed_at
               OR NEW.credible_interval_status IS DISTINCT FROM OLD.credible_interval_status
               OR NEW.interval_policy_version IS DISTINCT FROM OLD.interval_policy_version
               OR NEW.interval_shape IS DISTINCT FROM OLD.interval_shape
               OR NEW.interval_element_count IS DISTINCT FROM OLD.interval_element_count
               OR NEW.interval_summary_bytes IS DISTINCT FROM OLD.interval_summary_bytes
               OR NEW.hdi_lower IS DISTINCT FROM OLD.hdi_lower
               OR NEW.hdi_upper IS DISTINCT FROM OLD.hdi_upper
               OR NEW.r_hat_max IS DISTINCT FROM OLD.r_hat_max
               OR NEW.ess_min IS DISTINCT FROM OLD.ess_min
               OR NEW.divergence_count IS DISTINCT FROM OLD.divergence_count
               OR NEW.n_chains IS DISTINCT FROM OLD.n_chains
               OR NEW.n_samples_actual IS DISTINCT FROM OLD.n_samples_actual
               OR NEW.runtime_seconds IS DISTINCT FROM OLD.runtime_seconds
               OR NEW.sampling_started_at IS DISTINCT FROM OLD.sampling_started_at
               OR NEW.last_fit_at IS DISTINCT FROM OLD.last_fit_at
               OR NEW.completed_at IS DISTINCT FROM OLD.completed_at
               OR NEW.artifact_ref IS DISTINCT FROM OLD.artifact_ref
               OR NEW.artifact_hash IS DISTINCT FROM OLD.artifact_hash
               OR NEW.confidence_bucket IS DISTINCT FROM OLD.confidence_bucket
               OR NEW.confidence_bucket_reason IS DISTINCT FROM OLD.confidence_bucket_reason
               OR NEW.confidence_policy_version IS DISTINCT FROM OLD.confidence_policy_version
               OR NEW.confidence_semantics_version IS DISTINCT FROM OLD.confidence_semantics_version
               OR NEW.confidence_classified_at IS DISTINCT FROM OLD.confidence_classified_at
               OR NEW.confidence_evidence_snapshot_hash IS DISTINCT FROM OLD.confidence_evidence_snapshot_hash
               OR NEW.confidence_deterministic_revenue_minor IS DISTINCT FROM OLD.confidence_deterministic_revenue_minor
               OR NEW.confidence_deterministic_row_count IS DISTINCT FROM OLD.confidence_deterministic_row_count
               OR NEW.confidence_match_verdict_count IS DISTINCT FROM OLD.confidence_match_verdict_count
               OR NEW.confidence_currency_count IS DISTINCT FROM OLD.confidence_currency_count
               OR NEW.max_runtime_seconds IS DISTINCT FROM OLD.max_runtime_seconds
               OR NEW.max_samples IS DISTINCT FROM OLD.max_samples
               OR NEW.max_cores IS DISTINCT FROM OLD.max_cores) THEN
                        RETURN NEW;
                    END IF;
                ELSIF TG_ARGV[0] = 'artifact' THEN
                    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                       OR NEW.fit_id IS DISTINCT FROM OLD.fit_id
                       OR NEW.artifact_ref IS DISTINCT FROM OLD.artifact_ref THEN
                        RAISE EXCEPTION 'b24_dispatch_immutable_artifact_authority';
                    END IF;
                ELSE
                    RAISE EXCEPTION 'b24_dispatch_unknown_fence_subject';
                END IF;
            END IF;

            IF TG_ARGV[0] = 'fit' THEN
                v_tenant_id := NEW.tenant_id;
                v_fit_id := NEW.id;
                IF TG_OP = 'INSERT' AND NEW.status IN ('queued', 'pending') THEN
                    RETURN NEW;
                END IF;
                IF TG_OP IN ('INSERT', 'UPDATE')
                   AND NEW.status = 'fallback_only'
                   AND NEW.fallback_applied IS TRUE
                   AND NEW.fallback_reason IS NOT NULL
                   AND NEW.confidence_bucket = 'unavailable'
                   AND NEW.artifact_ref IS NULL
                   AND NEW.artifact_hash IS NULL
                   AND NEW.confidence_evidence_snapshot_hash IS NULL
                   AND NEW.sampling_started_at IS NULL
                   AND NEW.last_fit_at IS NULL
                   AND NEW.completed_at IS NULL
                   AND NEW.runtime_seconds IS NULL
                   AND NEW.n_samples_actual IS NULL
                   AND NEW.n_chains IS NULL
                   AND NEW.r_hat_max IS NULL
                   AND NEW.ess_min IS NULL
                   AND NEW.divergence_count IS NULL
                   AND NEW.hdi_lower IS NULL
                   AND NEW.hdi_upper IS NULL THEN
                    RETURN NEW;
                END IF;
            ELSIF TG_ARGV[0] = 'artifact' THEN
                v_tenant_id := NEW.tenant_id;
                v_fit_id := NEW.fit_id;
            ELSE
                RAISE EXCEPTION 'b24_dispatch_unknown_fence_subject';
            END IF;

            IF NOT public.b24_current_dispatch_fence_valid(v_tenant_id, v_fit_id) THEN
                RAISE EXCEPTION 'b24_dispatch_fence_rejected';
            END IF;
            RETURN NEW;
        END
        $$;
"""

PRIOR_FENCE = """
CREATE OR REPLACE FUNCTION public.b24_enforce_dispatch_fence()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            v_tenant_id uuid;
            v_fit_id uuid;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'b24_dispatch_delete_forbidden';
            END IF;

            IF TG_OP = 'UPDATE' THEN
                IF TG_ARGV[0] = 'fit' THEN
                    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                       OR NEW.id IS DISTINCT FROM OLD.id THEN
                        RAISE EXCEPTION 'b24_dispatch_immutable_fit_authority';
                    END IF;
                    -- B2.5-P13 C5: the planner owns fit creation and scheduling
                    -- bookkeeping and never holds a dispatch lease. An update
                    -- that changes no authority-bearing column changes nothing
                    -- the fence exists to protect.
                    IF NOT (NEW.status IS DISTINCT FROM OLD.status
               OR NEW.source_snapshot_hash IS DISTINCT FROM OLD.source_snapshot_hash
               OR NEW.source_read_started_at IS DISTINCT FROM OLD.source_read_started_at
               OR NEW.source_read_completed_at IS DISTINCT FROM OLD.source_read_completed_at
               OR NEW.data_completeness_status IS DISTINCT FROM OLD.data_completeness_status
               OR NEW.fallback_applied IS DISTINCT FROM OLD.fallback_applied
               OR NEW.fallback_reason IS DISTINCT FROM OLD.fallback_reason
               OR NEW.diagnostic_status IS DISTINCT FROM OLD.diagnostic_status
               OR NEW.diagnostic_failure_reason IS DISTINCT FROM OLD.diagnostic_failure_reason
               OR NEW.diagnostic_policy_version IS DISTINCT FROM OLD.diagnostic_policy_version
               OR NEW.diagnostic_target_filter_version IS DISTINCT FROM OLD.diagnostic_target_filter_version
               OR NEW.diagnostics_computed_at IS DISTINCT FROM OLD.diagnostics_computed_at
               OR NEW.credible_interval_status IS DISTINCT FROM OLD.credible_interval_status
               OR NEW.interval_policy_version IS DISTINCT FROM OLD.interval_policy_version
               OR NEW.interval_shape IS DISTINCT FROM OLD.interval_shape
               OR NEW.interval_element_count IS DISTINCT FROM OLD.interval_element_count
               OR NEW.interval_summary_bytes IS DISTINCT FROM OLD.interval_summary_bytes
               OR NEW.hdi_lower IS DISTINCT FROM OLD.hdi_lower
               OR NEW.hdi_upper IS DISTINCT FROM OLD.hdi_upper
               OR NEW.r_hat_max IS DISTINCT FROM OLD.r_hat_max
               OR NEW.ess_min IS DISTINCT FROM OLD.ess_min
               OR NEW.divergence_count IS DISTINCT FROM OLD.divergence_count
               OR NEW.n_chains IS DISTINCT FROM OLD.n_chains
               OR NEW.n_samples_actual IS DISTINCT FROM OLD.n_samples_actual
               OR NEW.runtime_seconds IS DISTINCT FROM OLD.runtime_seconds
               OR NEW.sampling_started_at IS DISTINCT FROM OLD.sampling_started_at
               OR NEW.last_fit_at IS DISTINCT FROM OLD.last_fit_at
               OR NEW.completed_at IS DISTINCT FROM OLD.completed_at
               OR NEW.artifact_ref IS DISTINCT FROM OLD.artifact_ref
               OR NEW.artifact_hash IS DISTINCT FROM OLD.artifact_hash
               OR NEW.confidence_bucket IS DISTINCT FROM OLD.confidence_bucket
               OR NEW.confidence_bucket_reason IS DISTINCT FROM OLD.confidence_bucket_reason
               OR NEW.confidence_policy_version IS DISTINCT FROM OLD.confidence_policy_version
               OR NEW.confidence_semantics_version IS DISTINCT FROM OLD.confidence_semantics_version
               OR NEW.confidence_classified_at IS DISTINCT FROM OLD.confidence_classified_at
               OR NEW.confidence_evidence_snapshot_hash IS DISTINCT FROM OLD.confidence_evidence_snapshot_hash
               OR NEW.confidence_deterministic_revenue_minor IS DISTINCT FROM OLD.confidence_deterministic_revenue_minor
               OR NEW.confidence_deterministic_row_count IS DISTINCT FROM OLD.confidence_deterministic_row_count
               OR NEW.confidence_match_verdict_count IS DISTINCT FROM OLD.confidence_match_verdict_count
               OR NEW.confidence_currency_count IS DISTINCT FROM OLD.confidence_currency_count
               OR NEW.max_runtime_seconds IS DISTINCT FROM OLD.max_runtime_seconds
               OR NEW.max_samples IS DISTINCT FROM OLD.max_samples
               OR NEW.max_cores IS DISTINCT FROM OLD.max_cores) THEN
                        RETURN NEW;
                    END IF;
                ELSIF TG_ARGV[0] = 'artifact' THEN
                    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                       OR NEW.fit_id IS DISTINCT FROM OLD.fit_id
                       OR NEW.artifact_ref IS DISTINCT FROM OLD.artifact_ref THEN
                        RAISE EXCEPTION 'b24_dispatch_immutable_artifact_authority';
                    END IF;
                ELSE
                    RAISE EXCEPTION 'b24_dispatch_unknown_fence_subject';
                END IF;
            END IF;

            IF TG_ARGV[0] = 'fit' THEN
                v_tenant_id := NEW.tenant_id;
                v_fit_id := NEW.id;
                IF TG_OP = 'INSERT' AND NEW.status IN ('queued', 'pending') THEN
                    RETURN NEW;
                END IF;
            ELSIF TG_ARGV[0] = 'artifact' THEN
                v_tenant_id := NEW.tenant_id;
                v_fit_id := NEW.fit_id;
            ELSE
                RAISE EXCEPTION 'b24_dispatch_unknown_fence_subject';
            END IF;

            IF NOT public.b24_current_dispatch_fence_valid(v_tenant_id, v_fit_id) THEN
                RAISE EXCEPTION 'b24_dispatch_fence_rejected';
            END IF;
            RETURN NEW;
        END
        $$;
"""


def _allow_replace() -> None:
    """PostgreSQL requires EXECUTE on a function before CREATE OR REPLACE.

    C7 revoked EXECUTE on the fence from the runtime roles, and the migration
    principal is not always the owner in every provisioning lineage, so the
    grant is re-established for the duration of this migration.
    """

    op.execute(
        "GRANT EXECUTE ON FUNCTION public.b24_enforce_dispatch_fence()"
        " TO CURRENT_USER"
    )


def upgrade() -> None:
    _allow_replace()
    op.execute(PLANNER_DECLARATION_FENCE)


def downgrade() -> None:
    _allow_replace()
    op.execute(PRIOR_FENCE)
