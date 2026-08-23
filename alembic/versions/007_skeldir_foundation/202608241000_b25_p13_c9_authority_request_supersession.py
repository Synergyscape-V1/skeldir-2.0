"""B2.5-P13 C9: a feature-authority request for a snapshot that is gone terminates.

``build_feature_authority`` asks the producer to measure one exact source
snapshot. When the source has already moved, the producer correctly writes
nothing -- measuring a snapshot it cannot observe would be the hybrid-authority
defect C9 closed elsewhere. What happened next was the problem: the request was
parked with ``retry_after_at = now() + 60 seconds``, unconditionally, forever.

That treats two different situations as one. A hash that does not match *yet*
because a writer is mid-flight is temporarily unavailable and should be retried.
A hash naming a source state that has been superseded is not unavailable -- it is
historically impossible, and no amount of retrying will make those bytes exist
again. Retrying it every minute for the life of the deployment is churn that
never converges, against a question that already has a permanent answer.

The bounded-retry columns for this already existed on the table and were never
consulted: ``retry_count`` and ``max_retries``. So does the terminal vocabulary --
``terminal_reason`` and ``terminal_at`` -- and the dirty-event side already
carries ``authority_retry_superseded``. The pieces were present and unconnected.

This migration adds the one governed state the request table was missing so the
connection can be made, rather than inventing a second lifecycle beside the one
B2.4 already owns.

Revision ID: 202608241000
Revises: 202608240900
"""

from __future__ import annotations

from alembic import op


revision = "202608241000"
down_revision = "202608240900"
branch_labels = None
depends_on = None

# Reuse the constraint's existing name. A drop-and-recreate under a new
# name would change the schema's identity for this rule and make every
# future diff read as a rename plus an addition rather than an addition.
CONSTRAINT = "ck_b24_feature_authority_request_status"

PRIOR_STATUSES = (
    "authority_build_requested",
    "authority_waiting",
    "authority_retry_ready",
    "authority_completed",
    "authority_timeout",
    "authority_build_failed",
)
SUPERSEDED = "authority_superseded"


TERMINAL_REASON_CONSTRAINT = "ck_b24_feature_authority_request_terminal_reason"
PRIOR_TERMINAL_REASONS = (
    "cardinality_authority_timeout",
    "cardinality_authority_build_failed",
)
SUPERSEDED_REASON = "source_snapshot_superseded"


def _terminal_reason_check(reasons: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{reason}'" for reason in reasons)
    return (
        "ALTER TABLE public.b24_feature_authority_build_requests"
        f" ADD CONSTRAINT {TERMINAL_REASON_CONSTRAINT}"
        f" CHECK (terminal_reason IS NULL OR terminal_reason IN ({rendered}))"
    )


def _status_check(statuses: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{status}'" for status in statuses)
    return (
        "ALTER TABLE public.b24_feature_authority_build_requests"
        f" ADD CONSTRAINT {CONSTRAINT}"
        f" CHECK (status IN ({rendered}))"
    )


def _drop_existing_status_check() -> None:
    """Drop whichever name the current status CHECK carries.

    The constraint was created inline with the table, so its generated name is
    not guaranteed across provisioning lineages. Finding it by what it
    constrains rather than by what it is called keeps this migration correct on
    a fresh install and on an upgraded one.
    """

    op.execute(
        """
        DO $$
        DECLARE
            target text;
        BEGIN
            SELECT conname INTO target
            FROM pg_constraint
            WHERE conrelid = 'public.b24_feature_authority_build_requests'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) LIKE '%authority_build_requested%'
            LIMIT 1;
            IF target IS NOT NULL THEN
                EXECUTE format(
                    'ALTER TABLE public.b24_feature_authority_build_requests'
                    ' DROP CONSTRAINT %I', target
                );
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    _drop_existing_status_check()
    op.execute(_status_check(PRIOR_STATUSES + (SUPERSEDED,)))
    op.execute(
        "ALTER TABLE public.b24_feature_authority_build_requests"
        f" DROP CONSTRAINT IF EXISTS {TERMINAL_REASON_CONSTRAINT}"
    )
    op.execute(
        _terminal_reason_check(PRIOR_TERMINAL_REASONS + (SUPERSEDED_REASON,))
    )


def downgrade() -> None:
    # A request already superseded has no earlier state to return to; the
    # honest downgrade is to terminate it under the state that existed before,
    # not to invent a plausible-looking one.
    op.execute(
        "UPDATE public.b24_feature_authority_build_requests"
        f" SET status = 'authority_build_failed' WHERE status = '{SUPERSEDED}'"
    )
    op.execute(
        "UPDATE public.b24_feature_authority_build_requests"
        f" SET terminal_reason = 'cardinality_authority_build_failed'"
        f" WHERE terminal_reason = '{SUPERSEDED_REASON}'"
    )
    op.execute(
        "ALTER TABLE public.b24_feature_authority_build_requests"
        f" DROP CONSTRAINT IF EXISTS {TERMINAL_REASON_CONSTRAINT}"
    )
    op.execute(_terminal_reason_check(PRIOR_TERMINAL_REASONS))
    _drop_existing_status_check()
    op.execute(_status_check(PRIOR_STATUSES))
