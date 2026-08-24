"""B2.5-P13 C10: bind the inference policy bundle to the fit that ran under it.

A confidence is only interpretable against the inference regime that produced
it. Before this migration the fit table carried exactly one of the four policy
identities -- ``diagnostic_policy_version`` -- and Trust's read model did not
select even that one, so an external verifier holding a signed envelope had no
way to answer "which governed inference regime produced this number?".

Version columns and one bundle hash close that. The hash is the load-bearing
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
    "diagnostic_policy_version",
    "authorized_chains",
    "authorized_posterior_draws_total",
    "superseded_policy_bundle_hash",
    "policy_replanned_at",
    "policy_replan_count",
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
    ("superseded_policy_bundle_hash", "varchar(64)"),
    ("policy_replanned_at", "timestamp with time zone"),
)

_AVAILABLE_BUCKETS = ("low", "medium", "high")
_PRE_C10_TERMINAL_COLUMNS = _TERMINAL_GOVERNED_COLUMNS[:31]


def _terminal_trigger_body(
    columns: tuple[str, ...] = _TERMINAL_GOVERNED_COLUMNS,
) -> str:
    comparisons = "\n               OR ".join(
        f"NEW.{column} IS DISTINCT FROM OLD.{column}" for column in columns
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
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_policy_replan_evidence"  # CI:DESTRUCTIVE_OK - Idempotent C10 constraint replacement; see ADR-017.
    )
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "ADD COLUMN IF NOT EXISTS policy_replan_count integer DEFAULT 0 NOT NULL"
    )

    op.execute(_terminal_trigger_body())

    # The initial publisher is intentionally global: it must see due outbox
    # rows across tenants, just like the separately governed recovery
    # reconciler. FORCE RLS therefore needs an explicit transaction-local
    # capability; without this policy a correctly scheduled publisher would
    # observe an empty table and fresh work would still never move.
    op.execute(
        """
        DROP POLICY IF EXISTS initial_dispatch_publisher_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;
        CREATE POLICY initial_dispatch_publisher_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox
            FOR ALL
            USING (
                session_user = 'app_worker'
                AND current_setting('app.b24_initial_dispatch_publisher', true) = 'on'
            )
            WITH CHECK (
                session_user = 'app_worker'
                AND current_setting('app.b24_initial_dispatch_publisher', true) = 'on'
            );
        """
    )

    # Claim-time policy identity is inserted by the planner. Once a dispatch
    # exists, changing that identity is an execution-authority write and must
    # carry the same live database lease as every other worker mutation. This
    # separate trigger composes with the established C5 dispatch fence without
    # copying its larger state machine into a later migration.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_enforce_policy_bundle_write_authority()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.inference_profile_version IS DISTINCT FROM OLD.inference_profile_version
               OR NEW.runtime_policy_version IS DISTINCT FROM OLD.runtime_policy_version
               OR NEW.sampling_policy_version IS DISTINCT FROM OLD.sampling_policy_version
               OR NEW.policy_bundle_hash IS DISTINCT FROM OLD.policy_bundle_hash
               OR NEW.diagnostic_policy_version IS DISTINCT FROM OLD.diagnostic_policy_version
               OR NEW.authorized_chains IS DISTINCT FROM OLD.authorized_chains
               OR NEW.authorized_posterior_draws_total
                    IS DISTINCT FROM OLD.authorized_posterior_draws_total
               OR NEW.superseded_policy_bundle_hash
                    IS DISTINCT FROM OLD.superseded_policy_bundle_hash
               OR NEW.policy_replanned_at IS DISTINCT FROM OLD.policy_replanned_at
               OR NEW.policy_replan_count IS DISTINCT FROM OLD.policy_replan_count THEN
                IF NOT public.b24_current_dispatch_fence_valid(NEW.tenant_id, NEW.id) THEN
                    RAISE EXCEPTION 'b24_policy_bundle_write_authority_rejected';
                END IF;
            END IF;
            RETURN NEW;
        END
        $$;

        DROP TRIGGER IF EXISTS trg_z_b24_policy_bundle_write_authority
            ON public.bayesian_model_fits;
        CREATE TRIGGER trg_z_b24_policy_bundle_write_authority
            BEFORE UPDATE ON public.bayesian_model_fits
            FOR EACH ROW
            EXECUTE FUNCTION public.b24_enforce_policy_bundle_write_authority();
        """
    )

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
        "DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_available_policy_bundle"  # CI:DESTRUCTIVE_OK - Idempotent C10 constraint replacement; see ADR-017.
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
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "ADD CONSTRAINT ck_bayesian_model_fits_policy_replan_evidence "
        "CHECK ((policy_replan_count = 0 "
        "AND superseded_policy_bundle_hash IS NULL "
        "AND policy_replanned_at IS NULL) OR (policy_replan_count > 0 "
        "AND superseded_policy_bundle_hash IS NOT NULL "
        "AND char_length(superseded_policy_bundle_hash) = 64 "
        "AND policy_replanned_at IS NOT NULL)) NOT VALID"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS initial_dispatch_publisher_b24_fit_dispatch_outbox "
        "ON public.b24_fit_dispatch_outbox; "
        "-- # CI:DESTRUCTIVE_OK - Controlled C10 rollback; see ADR-017."
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_z_b24_policy_bundle_write_authority "
        "ON public.bayesian_model_fits; "
        "-- # CI:DESTRUCTIVE_OK - Controlled C10 rollback; see ADR-017."
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b24_enforce_policy_bundle_write_authority(); "
        "-- # CI:DESTRUCTIVE_OK - Controlled C10 rollback; see ADR-017."
    )
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_policy_replan_evidence; "  # CI:DESTRUCTIVE_OK - Controlled C10 rollback; see ADR-017.
        "-- # CI:DESTRUCTIVE_OK - Controlled C10 rollback; see ADR-017."
    )
    # Restore the C7 terminal predicate before removing columns it would
    # otherwise continue to reference after a one-revision rollback.
    op.execute(_terminal_trigger_body(_PRE_C10_TERMINAL_COLUMNS))
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_available_policy_bundle; "  # CI:DESTRUCTIVE_OK - Controlled C10 rollback; see ADR-017.
        "-- # CI:DESTRUCTIVE_OK - Controlled C10 rollback; see ADR-017."
    )
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "DROP COLUMN IF EXISTS policy_replan_count; "  # CI:DESTRUCTIVE_OK - Controlled C10 rollback; see ADR-017.
        "-- # CI:DESTRUCTIVE_OK - Controlled C10 rollback; see ADR-017."
    )
    for column, _ in _NEW_COLUMNS:
        op.execute(
            "ALTER TABLE public.bayesian_model_fits "
            f"DROP COLUMN IF EXISTS {column}; "  # CI:DESTRUCTIVE_OK - Controlled C10 rollback; see ADR-017.
            "-- # CI:DESTRUCTIVE_OK - Controlled C10 rollback; see ADR-017."
        )
