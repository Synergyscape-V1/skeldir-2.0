"""B2.5-P13 C10: bind the inference policy bundle to the fit that ran under it.

A confidence is only interpretable against the inference regime that produced
it. Before this migration the fit table carried exactly one of the four policy
identities -- ``diagnostic_policy_version`` -- and Trust's read model did not
select even that one, so an external verifier holding a signed envelope had no
way to answer "which governed inference regime produced this number?".

Four columns and one bundle hash close that. The hash is the load-bearing
identity: four version strings that must be read together are more faithfully
carried as one digest that cannot be half-right than as four fields that can
drift apart or be partially copied.

Two further changes follow from the same principle.

``authorized_chains`` and ``authorized_posterior_draws_total`` are added beside
the existing ``n_chains`` and ``n_samples_actual``, which now carry *observed*
posterior dimensions. Both halves are kept because the question "what was
supposed to happen" and the question "what actually happened" are different
questions, and the defect this corrective exists to close was answering the
second with the first. A fit whose observed topology differs from its authorised
topology can no longer claim usable confidence.

Finally the terminal-immutability trigger's governed column set grows to cover
the new identities. Policy provenance that can be edited after the fact is not
provenance.

Revision ID: 202608250900
Revises: 202608241000
"""

from __future__ import annotations

from alembic import op

revision = "202608250900"
down_revision = "202608241000"
branch_labels = None
depends_on = None


_TERMINAL_GOVERNED_COLUMNS = (
    "id",
    "tenant_id",
    "model_type",
    "model_version",
    "source_window_start",
    "source_window_end",
    "source_snapshot_hash",
    "status",
    "data_completeness_status",
    "fallback_applied",
    "fallback_reason",
    "created_at",
    "completed_at",
    "updated_at",
    "diagnostic_status",
    "diagnostic_failure_reason",
    "credible_interval_status",
    "confidence_bucket",
    "confidence_bucket_reason",
    "confidence_policy_version",
    "confidence_semantics_version",
    "confidence_deterministic_revenue_minor",
    "confidence_deterministic_row_count",
    "confidence_match_verdict_count",
    "confidence_currency_count",
    "confidence_classified_at",
    "confidence_evidence_snapshot_hash",
    "source_read_started_at",
    "source_read_completed_at",
    "artifact_ref",
    "artifact_hash",
    # C10 additions: the producing inference regime, and the observed-versus
    # -authorised topology that regime actually delivered.
    "inference_profile_version",
    "runtime_policy_version",
    "sampling_policy_version",
    "policy_bundle_hash",
    "authorized_chains",
    "authorized_posterior_draws_total",
    "n_chains",
    "n_samples_actual",
)

_NEW_COLUMNS = (
    ("inference_profile_version", "varchar(128)"),
    ("runtime_policy_version", "varchar(128)"),
    ("sampling_policy_version", "varchar(128)"),
    ("policy_bundle_hash", "varchar(64)"),
    ("authorized_chains", "integer"),
    ("authorized_posterior_draws_total", "integer"),
)

_AVAILABLE_BUCKETS = ("low", "medium", "high")


def _terminal_trigger_body() -> str:
    comparisons = "\n               OR ".join(
        f"NEW.{column} IS DISTINCT FROM OLD.{column}"
        for column in _TERMINAL_GOVERNED_COLUMNS
    )
    return f"""
        CREATE OR REPLACE FUNCTION public.b24_enforce_terminal_fit_truth()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF public.b24_fit_status_is_terminal(OLD.status)
               AND ({comparisons}) THEN
                RAISE EXCEPTION 'b24_terminal_fit_truth_immutable';
            END IF;
            RETURN NEW;
        END
        $$;
    """


def upgrade() -> None:
    for column, column_type in _NEW_COLUMNS:
        op.execute(
            "ALTER TABLE public.bayesian_model_fits "
            f"ADD COLUMN IF NOT EXISTS {column} {column_type}"
        )

    op.execute(_terminal_trigger_body())

    buckets = ", ".join(f"'{bucket}'" for bucket in _AVAILABLE_BUCKETS)
    # Usable confidence now requires the authority needed to interpret it.
    #
    # F-13 established that a completeness constraint which has never once been
    # evaluated is not evidence of completeness -- it went unexercised for as
    # long as no fit reached an available bucket. The same philosophy applies to
    # provenance: a confidence a verifier cannot attribute to a governed regime
    # should not be expressible, rather than merely discouraged.
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_available_policy_bundle"
    )
    op.execute(
        f"""
        ALTER TABLE public.bayesian_model_fits
        ADD CONSTRAINT ck_bayesian_model_fits_available_policy_bundle
        CHECK (
            confidence_bucket IS NULL
            OR confidence_bucket::text NOT IN ({buckets})
            OR (
                inference_profile_version IS NOT NULL
                AND runtime_policy_version IS NOT NULL
                AND sampling_policy_version IS NOT NULL
                AND diagnostic_policy_version IS NOT NULL
                AND policy_bundle_hash IS NOT NULL
                AND char_length(policy_bundle_hash) = 64
                AND authorized_chains IS NOT NULL
                AND authorized_posterior_draws_total IS NOT NULL
                AND n_chains IS NOT NULL
                AND n_samples_actual IS NOT NULL
                -- Observed topology must be the authorised topology. A fit that
                -- ran a different shape than it was authorised to run cannot
                -- carry usable confidence, whatever its diagnostics said.
                AND n_chains = authorized_chains
                AND n_samples_actual = authorized_posterior_draws_total
            )
        )
        NOT VALID
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_available_policy_bundle"
    )
    for column, _ in _NEW_COLUMNS:
        op.execute(
            "ALTER TABLE public.bayesian_model_fits "
            f"DROP COLUMN IF EXISTS {column}"
        )
