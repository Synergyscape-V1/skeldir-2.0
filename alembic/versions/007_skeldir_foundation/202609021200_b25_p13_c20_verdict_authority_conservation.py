"""B2.5-P13 C20: conserve B2.3 verdict authority at the database boundary.

Revision ID: 202609021200
Revises: 202609011200

Corrective XX, blocker 1. Two independent audits of `87836b60` observed the
API database principal executing the worker-owned transition

    matched_provisional -> matched_confirmed

directly, after which the C19 projection trigger propagated ``verified = true``
onto the allocation. The database derived verification correctly; what it did
not do was fence *who may assert the verdict the derivation reads*.

The privilege root is two-headed, which is why a grant edit alone is not the
whole repair:

  * ``202604291200_b23_p1_schema_authority_lock`` granted
    ``SELECT, INSERT, UPDATE`` on ``b23_match_verdicts`` to ``app_user``
    directly *and* to ``app_rw``;
  * ``app_user`` and ``app_worker`` are both members of ``app_rw``, so the
    inherited path survives revoking the direct grant;
  * ``202605061200_b23_p4_queue_performance_indexes`` re-granted the direct
    privilege after an earlier revoke, which is the empirical reason this
    migration does not rely on grants alone.

So authority is expressed twice, at two different layers:

  1. privilege: only ``app_worker`` may write the relation at all;
  2. consequence: a trigger refuses any *load-bearing* verdict assertion whose
     session principal does not hold B2.3 worker authority, so a future grant
     regression cannot silently restore the historical capability.

Both layers are independently load-bearing and independently falsifiable; the
C20 negative control severs each one separately and then both together, and
only the both-severed case is permitted to reproduce the historical RED.

The trigger is deliberately scoped to the columns that carry verdict truth.
``attribution_events`` and ``webhook_ingress_identities`` reference this table
``ON DELETE SET NULL``; that referential action is a governed consequence of
deleting the referenced row, not an assertion of verdict truth, and must keep
working for whichever principal owns the retention path.
"""

from __future__ import annotations

from alembic import op


revision = "202609021200"
down_revision = "202609011200"
branch_labels = None
depends_on = None


# Columns whose value *is* the deterministic verdict other processes consume.
# A change to any of them is an assertion of B2.3 truth.
_AUTHORITY_COLUMNS = (
    "status",
    "confirmed_at",
    "adjusted_at",
    "unmatched_marked_at",
    "match_quality",
    "attributed_amount_minor",
    "verified_amount_minor",
    "canonical_expected_gross_amount_minor",
    "canonical_captured_gross_amount_minor",
    "canonical_net_verified_amount_minor",
    "discrepancy_amount_minor",
    "discrepancy_ratio_bps",
    "discrepancy_band",
)

_AUTHORITY_CHANGE_PREDICATE = "\n        OR ".join(
    f"OLD.{column} IS DISTINCT FROM NEW.{column}" for column in _AUTHORITY_COLUMNS
)


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b23_enforce_verdict_authorship()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            principal_is_superuser boolean;
            worker_role_oid oid;
        BEGIN
            -- A superuser can drop this trigger, so refusing it buys no
            -- authority and only breaks administrative provisioning.
            SELECT rolsuper
              INTO principal_is_superuser
              FROM pg_catalog.pg_roles
             WHERE rolname = session_user;
            IF COALESCE(principal_is_superuser, false) THEN
                RETURN NEW;
            END IF;

            SELECT oid
              INTO worker_role_oid
              FROM pg_catalog.pg_roles
             WHERE rolname = 'app_worker';
            IF worker_role_oid IS NOT NULL
               AND pg_catalog.pg_has_role(session_user, worker_role_oid, 'USAGE')
            THEN
                RETURN NEW;
            END IF;

            RAISE EXCEPTION
                'b23 verdict authority is owned by the B2.3 worker principal; '
                '% may not % public.b23_match_verdicts',
                session_user, TG_OP
                USING ERRCODE = '42501';
        END;
        $BODY$;
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b23_verdict_authorship_insert
            ON public.b23_match_verdicts;
        CREATE TRIGGER trg_b23_verdict_authorship_insert
            BEFORE INSERT ON public.b23_match_verdicts
            FOR EACH ROW
            EXECUTE FUNCTION public.b23_enforce_verdict_authorship();
        """
    )
    op.execute(
        f"""
        DROP TRIGGER IF EXISTS trg_b23_verdict_authorship_update
            ON public.b23_match_verdicts;
        CREATE TRIGGER trg_b23_verdict_authorship_update
            BEFORE UPDATE ON public.b23_match_verdicts
            FOR EACH ROW
            WHEN (
                {_AUTHORITY_CHANGE_PREDICATE}
            )
            EXECUTE FUNCTION public.b23_enforce_verdict_authorship();
        """
    )

    # Layer 1. app_user inherits app_rw, so both the direct and the inherited
    # grant have to go; app_ro keeps read only; app_worker receives the narrow
    # write capability the B2.3 sweep actually needs.
    op.execute(
        """
        REVOKE ALL ON TABLE public.b23_match_verdicts
            FROM PUBLIC, app_user, app_rw, app_ro;
        GRANT SELECT ON TABLE public.b23_match_verdicts TO app_user, app_ro;
        GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_match_verdicts
            TO app_worker;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b23_verdict_authorship_update
            ON public.b23_match_verdicts;
        DROP TRIGGER IF EXISTS trg_b23_verdict_authorship_insert
            ON public.b23_match_verdicts;
        DROP FUNCTION IF EXISTS public.b23_enforce_verdict_authorship();
        REVOKE ALL ON TABLE public.b23_match_verdicts
            FROM PUBLIC, app_user, app_rw, app_ro, app_worker;
        GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_match_verdicts
            TO app_user, app_rw;
        GRANT SELECT ON TABLE public.b23_match_verdicts TO app_ro;
        """
    )
