"""B2.6-P2 Corrective XXI follow-up: verdict-keyed canonical-authority reader.

B24_P1_AUTHORITY_SCHEMA_VALIDATION_FAIL on protected main: no module under
backend/app/bayesian/ may name an identity-bearing reference (the
ingress_identity token), but Corrective XX (H-XX-A, single currentness law)
requires every Bayesian financial reader to consult the canonical
predicate, not just verdict-local cached state. Seven call sites across
api_projection.py, eligibility.py, source_snapshot.py and
source_contract_authority.py did so by passing
v.webhook_ingress_identity_id into b26_p2_ingress_has_current_authority().

This revision adds one P2-owned verdict-keyed reader,
b26_p2_verdict_has_current_authority(p_verdict uuid), which resolves the
verdict's backing ingress inside P2-owned SQL and applies the identical
canonical predicate. Bayesian SQL then names only the verdict id and the
wrapper: double-gating preserved behaviorally, identity isolation restored
textually. The wrapper is STABLE with invoker rights (callers already hold
SELECT on b23_match_verdicts under their own RLS context, exactly as the
inline form; the identity table itself is read only by the pre-existing
SECURITY DEFINER predicate), search_path pinned, REVOKE ALL FROM PUBLIC
with EXECUTE granted solely to the two principals that execute Bayesian
reads (app_user for API projection, app_worker for fit workers). A
missing verdict or NULL backing ingress resolves FALSE (fail-closed),
identical to the inline form by construction (same predicate applied to
the same argument value); proven row-for-row by the differential battery.

Downgrade drops the wrapper. Bayesian reads then fail closed with
undefined-function until re-upgrade; no silent authority is possible.
"""

from __future__ import annotations

from alembic import op

revision = "202609300005"
down_revision = "202609300004"


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_verdict_has_current_authority(
            p_verdict uuid
        )
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SET search_path TO 'pg_catalog', 'public'
        AS $$
          SELECT public.b26_p2_ingress_has_current_authority(
            (SELECT v.webhook_ingress_identity_id
               FROM public.b23_match_verdicts AS v
              WHERE v.id = p_verdict)
          );
        $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION"
        " public.b26_p2_verdict_has_current_authority(uuid)"
        " FROM PUBLIC"
    )
    for _role in ("app_user", "app_worker"):
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '%s')"
            " THEN EXECUTE 'GRANT EXECUTE ON FUNCTION"
            " public.b26_p2_verdict_has_current_authority(uuid) TO %s';"
            " END IF; END $$;" % (_role, _role)
        )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_verdict_has_current_authority(uuid)"
    )
