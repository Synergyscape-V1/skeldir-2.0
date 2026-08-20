"""B2.5-P13 C5 terminal fit truth immutability and absolute temporal plausibility.

Revision ID: 202608191200
Revises: 202608181200
Create Date: 2026-08-19 12:00:00.000000

Two independent database invariants, both unconditional and both free of any
application convention:

Rule A (authority fence, pre-existing, now precisely scoped)
    Changing an *authority-bearing* column of ``bayesian_model_fits`` requires a
    currently valid dispatch lease for that exact fit. Changing only inert
    bookkeeping (``updated_at``, ``eligibility_status``,
    ``last_eligibility_check_at``, resource ceilings) does not. Before C5 the
    fence demanded a dispatch lease for *every* update, which made the B2.4-P2/P3
    planner's own ``claim_fit_for_snapshot`` upsert unreachable -- the planner is
    not a dispatch worker and never holds a lease.

Rule B (terminal epistemic immutability, new)
    Once a fit reaches a terminal status, no authority-bearing column may change
    again -- with a lease, with a reclaimed lease, or as table owner. A fit's
    terminal truth is a historical observation; restating it would silently
    change what an already-issued, already-signed TrustEnvelope asserted.

Rule B is what closes the reproduced C5 exploit: a least-privilege runtime
identity could rewrite its own dispatch-outbox lease bookkeeping (the outbox's
tenant-isolation policy is a permissive ALL policy keyed only on ``tenant_id``),
reclaim the lease through the governed SECURITY DEFINER claim function, and then
rewrite an already-``succeeded`` fit's ``confidence_bucket``. Rule B makes that
final write impossible regardless of how the lease was obtained, so the fix does
not depend on lease acquisition being unforgeable.

Rule C (absolute temporal plausibility, new)
    Evidence timestamps may not be materially in the future. The C4 constraints
    established relative chronology (start <= end <= classified) but never
    compared any of them to the clock, so a fit dated thirty days ahead satisfied
    every constraint and then rendered as zero seconds old. A bounded tolerance
    is used rather than a strict ``<= now()`` because the database clock and the
    API clock are not the same clock; the tolerance has exactly one owner,
    ``public.b24_evidence_future_skew_tolerance_seconds()``, which the C5 CI gate
    asserts equals the Python constant.
"""

from __future__ import annotations

from alembic import op


revision = "202608191200"
down_revision = "202608181200"
branch_labels = None
depends_on = None


#: Statuses after which a fit's epistemic truth is final. Deliberately narrow:
#: every in-flight status stays mutable, because every production writer already
#: gates its UPDATE on ``status IN ('pending','queued','running','persist_pending')``
#: and no production path mutates a terminal fit at all.
TERMINAL_FIT_STATUSES = (
    "succeeded",
    "failed",
    "timeout",
    "worker_lost",
    "fallback_only",
    "cancelled",
)

#: Authority-bearing columns. A change to any of these is a change to what the
#: fit *asserts*, as opposed to how it is scheduled or accounted for.
AUTHORITY_FIT_COLUMNS = (
    "status",
    "source_snapshot_hash",
    "source_read_started_at",
    "source_read_completed_at",
    "data_completeness_status",
    "fallback_applied",
    "fallback_reason",
    "diagnostic_status",
    "diagnostic_failure_reason",
    "diagnostic_policy_version",
    "diagnostic_target_filter_version",
    "diagnostics_computed_at",
    "credible_interval_status",
    "interval_policy_version",
    "interval_shape",
    "interval_element_count",
    "interval_summary_bytes",
    "hdi_lower",
    "hdi_upper",
    "r_hat_max",
    "ess_min",
    "divergence_count",
    "n_chains",
    "n_samples_actual",
    "runtime_seconds",
    "sampling_started_at",
    "last_fit_at",
    "completed_at",
    "artifact_ref",
    "artifact_hash",
    "confidence_bucket",
    "confidence_bucket_reason",
    "confidence_policy_version",
    "confidence_semantics_version",
    "confidence_classified_at",
    "confidence_evidence_snapshot_hash",
    "confidence_deterministic_revenue_minor",
    "confidence_deterministic_row_count",
    "confidence_match_verdict_count",
    "confidence_currency_count",
    # Resource ceilings are not Trust authority, but they bound what a future
    # worker may spend. Freezing them keeps the fence relaxation below strictly
    # about inert bookkeeping: after C5 the only columns a caller may change
    # without a dispatch lease are `updated_at`, `eligibility_status` and
    # `last_eligibility_check_at`, none of which the Trust projection reads and
    # none of which bounds compute.
    "max_runtime_seconds",
    "max_samples",
    "max_cores",
)

#: Bounded clock-skew tolerance between the database clock and any producer's
#: clock. Mirrored by ``app.confidence_projection.policy`` and asserted equal by
#: the C5 CI gate, so the two can never drift into two different policies.
EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS = 120


def _authority_change_predicate(prefix_old: str = "OLD", prefix_new: str = "NEW") -> str:
    return "\n               OR ".join(
        f"{prefix_new}.{column} IS DISTINCT FROM {prefix_old}.{column}"
        for column in AUTHORITY_FIT_COLUMNS
    )


def _sql_status_list() -> str:
    return ", ".join(f"'{status}'" for status in TERMINAL_FIT_STATUSES)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b24_fit_status_is_terminal(p_status text)
        RETURNS boolean
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT p_status IN ({_sql_status_list()})
        $$;
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION
            public.b24_evidence_future_skew_tolerance_seconds()
        RETURNS integer
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT {EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS}
        $$;
        """
    )
    op.execute(
        """
        GRANT EXECUTE ON FUNCTION public.b24_fit_status_is_terminal(text)
            TO PUBLIC;
        GRANT EXECUTE ON FUNCTION
            public.b24_evidence_future_skew_tolerance_seconds() TO PUBLIC;
        """
    )

    # Rule B. Independent of the dispatch fence on purpose: the fence answers
    # "may this caller act on this dispatch", which is a different question from
    # "is this truth still open to being written at all".
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b24_enforce_terminal_fit_truth()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NOT public.b24_fit_status_is_terminal(OLD.status) THEN
                RETURN NEW;
            END IF;
            IF {_authority_change_predicate()} THEN
                RAISE EXCEPTION 'b24_terminal_fit_truth_immutable';
            END IF;
            RETURN NEW;
        END
        $$;

        DROP TRIGGER IF EXISTS trg_b24_terminal_fit_truth ON public.bayesian_model_fits;
        CREATE TRIGGER trg_b24_terminal_fit_truth
            BEFORE UPDATE ON public.bayesian_model_fits
            FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_terminal_fit_truth();
        """
    )

    # Rule C. A CHECK constraint cannot express this: now() is not IMMUTABLE, so
    # the plausibility bound has to be a trigger.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_enforce_evidence_temporal_plausibility()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_horizon timestamptz;
        BEGIN
            v_horizon := now() + make_interval(
                secs => public.b24_evidence_future_skew_tolerance_seconds()
            );
            IF NEW.source_read_started_at IS NOT NULL
               AND NEW.source_read_started_at > v_horizon THEN
                RAISE EXCEPTION 'b24_evidence_timestamp_implausible';
            END IF;
            IF NEW.source_read_completed_at IS NOT NULL
               AND NEW.source_read_completed_at > v_horizon THEN
                RAISE EXCEPTION 'b24_evidence_timestamp_implausible';
            END IF;
            IF NEW.confidence_classified_at IS NOT NULL
               AND NEW.confidence_classified_at > v_horizon THEN
                RAISE EXCEPTION 'b24_evidence_timestamp_implausible';
            END IF;
            RETURN NEW;
        END
        $$;

        DROP TRIGGER IF EXISTS trg_b24_evidence_temporal_plausibility
            ON public.bayesian_model_fits;
        CREATE TRIGGER trg_b24_evidence_temporal_plausibility
            BEFORE INSERT OR UPDATE ON public.bayesian_model_fits
            FOR EACH ROW
            EXECUTE FUNCTION public.b24_enforce_evidence_temporal_plausibility();
        """
    )

    # Rule A, re-scoped. Same authority model, same capability check, same
    # immutability of tenant/id; the single change is that an update touching no
    # authority column no longer demands a dispatch lease, which is what made the
    # planner's own claim/reuse path unreachable after B2.4-P9.
    op.execute(
        f"""
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
                    IF NOT ({_authority_change_predicate()}) THEN
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
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b24_evidence_temporal_plausibility
            ON public.bayesian_model_fits; -- # CI:DESTRUCTIVE_OK - Downgrade rollback; see ADR-016.
        DROP TRIGGER IF EXISTS trg_b24_terminal_fit_truth
            ON public.bayesian_model_fits; -- # CI:DESTRUCTIVE_OK - Downgrade rollback; see ADR-016.
        DROP FUNCTION IF EXISTS public.b24_enforce_evidence_temporal_plausibility(); -- # CI:DESTRUCTIVE_OK - Downgrade rollback; see ADR-016.
        DROP FUNCTION IF EXISTS public.b24_enforce_terminal_fit_truth(); -- # CI:DESTRUCTIVE_OK - Downgrade rollback; see ADR-016.
        DROP FUNCTION IF EXISTS public.b24_evidence_future_skew_tolerance_seconds(); -- # CI:DESTRUCTIVE_OK - Downgrade rollback; see ADR-016.
        DROP FUNCTION IF EXISTS public.b24_fit_status_is_terminal(text); -- # CI:DESTRUCTIVE_OK - Downgrade rollback; see ADR-016.
        """
    )
    op.execute(
        """
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
    )
