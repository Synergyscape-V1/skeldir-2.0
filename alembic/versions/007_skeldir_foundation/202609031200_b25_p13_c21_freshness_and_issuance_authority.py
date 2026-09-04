"""B2.5-P13 C21: conserve B2.4 freshness authority and durable issuance history.

Revision ID: 202609031200
Revises: 202609021200

Corrective XXI. Audit 65 physically reproduced two authority violations on
protected main ``737db584``, both inside an otherwise honest trust journey:

  * CF-XXI-01 -- the API database principal rewrote
    ``b24_dirty_events.source_snapshot_hash`` on already-created invalidation
    evidence, which flipped the confidence projection's
    ``has_later_dirty_evidence`` predicate from TRUE to FALSE and made a stale
    fit eligible for Trust. No Bayesian recomputation occurred; only the
    invalidation premise changed.
  * CF-XXI-02 -- the same principal rewrote ``envelope_hash`` and
    ``semantic_truth_hash`` on a completed row of
    ``trust_envelope_issuance_log``, so durable history could disagree with the
    artifact that was actually signed and returned.

Privilege lineage (root cause, not hypothesis):

  * ``202605221430_b24_p3_fit_planning_outbox`` granted
    ``SELECT, INSERT, UPDATE`` on ``b24_dirty_events`` to ``app_user`` inside a
    loop over three B2.4-P3 orchestration tables. The other two were later
    narrowed to ``SELECT`` by the C6 authority contract; the dirty-event grant
    was not, because the relation reads like a scheduler queue rather than the
    freshness authority the Trust projection actually consults.
  * ``202607011200_b25_p7_trust_audit_provenance`` granted
    ``SELECT, INSERT, UPDATE`` on all four trust audit relations to both
    ``app_user`` *and* ``app_rw``. ``app_user`` and ``app_worker`` are members
    of ``app_rw``, so the capability is two-headed: revoking the direct grant
    alone leaves the inherited one standing.

Both are the same historical shape Corrective XX found on verdicts -- authority
derived from tables rather than from causal meaning -- so this migration derives
it from the consequence graph instead:

  * Provenance identity on an invalidation record ("what changed, over which
    window, for whom") is written once, at INSERT, by the producer. No lawful
    lifecycle transition restates it, so no runtime principal may.
  * ``source_snapshot_hash`` is the single dirty-event column with a lawful
    post-insert writer: the B2.4 planner binds the resolved snapshot when it
    parks a leased obligation in ``authority_waiting``
    (``app/bayesian/fit_planner.py::mark_authority_waiting_dirty_events``).
    That exact transition is the whole lawful set, so it is what the database
    permits -- by principal *and* by transition.
  * ``trust_envelope_issuance_log`` carries a ``status = 'success'`` CHECK, so
    every row is terminal the moment it exists. It is written once by the API
    principal alongside the returned envelope and never read back for mutation
    anywhere in the codebase. It is therefore append-only in fact, and this
    migration makes PostgreSQL say so.

Authority is expressed twice on each surface -- a privilege layer and a
consequence layer -- for the reason Corrective XX established empirically: a
later migration re-granting the historical privilege must not silently restore
the historical capability. The C21 negative controls sever each layer
independently and then both together, and only the both-severed case may
reproduce the audit's RED.

The trust audit siblings ``trust_replay_events`` and
``trust_scope_denial_events`` received the same blanket grant from the same
migration and are INSERT-only in every code path, so they lose UPDATE on both
heads too. ``trust_access_log`` is deliberately untouched: its UPDATE is the
replay-counter upsert, and the C16 guard already refuses any change to an
issuance-consequence column from a principal that is not the issuer.

INSERT stays with ``app_rw`` on all three narrowed relations.
``record_trust_audit_event`` writes every one of them from whichever session
composes a Trust read, and the C9 positive-confidence lane composes one under
the worker principal -- a revoke there fences a lawful author, which is the
failure mode directive H-XXI-11 names and which mandatory CI caught before this
landed.
"""

from __future__ import annotations

from alembic import op


revision = "202609031200"
down_revision = "202609021200"
branch_labels = None
depends_on = None


# Columns whose value *is* the identity of the invalidation evidence: what
# changed, for which tenant, over which event-time window, under which model
# identity. The confidence projection reads the window columns and the model
# identity directly; the rest name the source event that produced the record.
# Nothing in the lawful lifecycle restates any of them after INSERT.
#
# ``observed_at`` is deliberately absent: the C7 lifecycle trigger already makes
# it immutable for every principal including the owner, which is strictly
# stronger than what this guard would add, and duplicating it here would only
# change which error message a caller sees.
_EVIDENCE_IDENTITY_COLUMNS = (
    "tenant_id",
    "model_type",
    "model_version",
    "source_window_start",
    "source_window_end",
    "dirty_reason",
    "source_family",
    "event_hash",
    "source_event_id",
    "created_at",
)

_IDENTITY_CHANGE_PREDICATE = "\n           OR ".join(
    f"NEW.{column} IS DISTINCT FROM OLD.{column}"
    for column in _EVIDENCE_IDENTITY_COLUMNS
)

# The guard fires for identity changes and for any rebinding of the resolved
# source snapshot -- the column the audit actually rewrote.
_GUARDED_CHANGE_PREDICATE = (
    _IDENTITY_CHANGE_PREDICATE
    + "\n           OR NEW.source_snapshot_hash IS DISTINCT FROM OLD.source_snapshot_hash"
)


def _if_role_exists(role: str, statement: str) -> None:
    """Apply a privilege statement only where the runtime role is provisioned."""

    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '{role}')
            THEN
                EXECUTE $stmt${statement}$stmt$;
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. B2.4 freshness authority -- consequence layer.
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b24_enforce_dirty_event_authority()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            principal_is_superuser boolean;
            table_owner_oid oid;
            planner_role_oid oid;
            caller_is_planner boolean;
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

            -- Likewise the migration principal, which owns the relation and can
            -- drop the trigger outright. C20 asserts, beside its own fence, that
            -- no runtime login can reach that role; the same assertion carries
            -- this one.
            SELECT relowner
              INTO table_owner_oid
              FROM pg_catalog.pg_class
             WHERE oid = TG_RELID;
            IF pg_catalog.pg_has_role(session_user, table_owner_oid, 'USAGE') THEN
                RETURN NEW;
            END IF;

            -- Identity of the invalidation evidence is written once, by the
            -- producer, and is never restated by a lifecycle transition.
            IF {_IDENTITY_CHANGE_PREDICATE}
            THEN
                RAISE EXCEPTION
                    'b24 invalidation evidence identity is immutable after '
                    'creation; % may not restate what changed',
                    session_user
                    USING ERRCODE = '42501';
            END IF;

            -- The resolved source snapshot has exactly one lawful writer and
            -- exactly one lawful moment: the B2.4 planner binding it as a leased
            -- obligation enters authority_waiting.
            IF NEW.source_snapshot_hash IS DISTINCT FROM OLD.source_snapshot_hash
            THEN
                SELECT oid
                  INTO planner_role_oid
                  FROM pg_catalog.pg_roles
                 WHERE rolname = 'app_worker';
                caller_is_planner := planner_role_oid IS NOT NULL
                    AND pg_catalog.pg_has_role(
                        session_user, planner_role_oid, 'USAGE'
                    );
                IF NOT caller_is_planner THEN
                    RAISE EXCEPTION
                        'b24 freshness authority is owned by the B2.4 planner '
                        'principal; % may not rebind source_snapshot_hash',
                        session_user
                        USING ERRCODE = '42501';
                END IF;
                IF OLD.status <> 'leased' OR NEW.status <> 'authority_waiting'
                THEN
                    RAISE EXCEPTION
                        'b24 source snapshot may only be bound on the lawful '
                        'leased -> authority_waiting transition; refused % -> %',
                        OLD.status, NEW.status
                        USING ERRCODE = '42501';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $BODY$;
        """
    )

    # Named to sort before trg_b24_enforce_dirty_event_lifecycle so a statement
    # that violates both rules reports the authority refusal, which is the
    # load-bearing one.
    op.execute(
        f"""
        DROP TRIGGER IF EXISTS trg_b24_dirty_event_authority
            ON public.b24_dirty_events;
            BEFORE UPDATE ON public.b24_dirty_events
            FOR EACH ROW
            WHEN (
                {_GUARDED_CHANGE_PREDICATE}
            )
            EXECUTE FUNCTION public.b24_enforce_dirty_event_authority();
        """
    )

    # ------------------------------------------------------------------
    # 2. B2.4 freshness authority -- privilege layer.
    # ------------------------------------------------------------------
    # The API principal appends invalidation evidence (ingestion and the
    # attribution worker both call append_dirty_event) and reads it. Every
    # UPDATE in the codebase belongs to the planner/Bayesian worker.
    op.execute("REVOKE ALL ON TABLE public.b24_dirty_events FROM PUBLIC")
    _if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.b24_dirty_events FROM app_user;"
        " GRANT SELECT, INSERT, UPDATE ON TABLE public.b24_dirty_events TO app_user",
    )
    _if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.b24_dirty_events FROM app_rw",
    )
    _if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.b24_dirty_events FROM app_ro;"
        " GRANT SELECT ON TABLE public.b24_dirty_events TO app_ro",
    )
    _if_role_exists(
        "app_worker",
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.b24_dirty_events"
        " TO app_worker",
    )

    # ------------------------------------------------------------------
    # 3. Durable issuance history -- consequence layer.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.trust_enforce_issuance_history_immutable()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            principal_is_superuser boolean;
            table_owner_oid oid;
        BEGIN
            SELECT rolsuper
              INTO principal_is_superuser
              FROM pg_catalog.pg_roles
             WHERE rolname = session_user;
            SELECT relowner
              INTO table_owner_oid
              FROM pg_catalog.pg_class
             WHERE oid = TG_RELID;

            -- Superuser and the owning migration principal can drop this
            -- trigger, so refusing them buys no authority; the owner branch is
            -- also what keeps a governed tenant cascade working.
            IF COALESCE(principal_is_superuser, false)
               OR pg_catalog.pg_has_role(session_user, table_owner_oid, 'USAGE')
            THEN
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                RETURN NEW;
            END IF;

            -- Every row of this relation is terminal at INSERT: the status
            -- CHECK admits only 'success', so a row exists exactly when a
            -- cryptographic consequence was recorded. A later statement may
            -- not restate what Skeldir durably claims it signed.
            RAISE EXCEPTION
                'durable trust issuance history is immutable; % may not % '
                'public.trust_envelope_issuance_log',
                session_user, TG_OP
                USING ERRCODE = '42501';
        END;
        $BODY$;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_trust_issuance_history_immutable
            ON public.trust_envelope_issuance_log;
        CREATE TRIGGER trg_trust_issuance_history_immutable
            BEFORE UPDATE OR DELETE ON public.trust_envelope_issuance_log
            FOR EACH ROW
            EXECUTE FUNCTION public.trust_enforce_issuance_history_immutable();
        """
    )

    # ------------------------------------------------------------------
    # 4. Durable issuance history -- privilege layer, plus the siblings that
    #    inherited the same blanket grant from the same migration.
    # ------------------------------------------------------------------
    # UPDATE is what has to go, and it has to go from *both* heads: the direct
    # grant and the one app_user and app_worker inherit through app_rw. INSERT
    # stays on both, because `record_trust_audit_event` writes all three of
    # these relations from whichever session composes a Trust read, and the C9
    # positive-confidence lane composes one under the worker principal.
    for relation in (
        "trust_envelope_issuance_log",
        "trust_replay_events",
        "trust_scope_denial_events",
    ):
        op.execute(f"REVOKE ALL ON TABLE public.{relation} FROM PUBLIC")
        for role in ("app_user", "app_rw"):
            _if_role_exists(
                role,
                f"REVOKE ALL ON TABLE public.{relation} FROM {role};"
                f" GRANT SELECT, INSERT ON TABLE public.{relation} TO {role}",
            )
        _if_role_exists(
            "app_ro",
            f"REVOKE ALL ON TABLE public.{relation} FROM app_ro;"
            f" GRANT SELECT ON TABLE public.{relation} TO app_ro",
        )

    # trust_access_log is deliberately untouched. Its UPDATE is load-bearing --
    # `_upsert_access_log` increments a replay counter through ON CONFLICT DO
    # UPDATE -- and the C16 guard `trust_access_log_issuance_authority_guard`
    # already refuses any change to an issuance-consequence column from a
    # principal that is not the issuer or the relation owner. The remaining
    # capability there is appending audit rows and counting replays, which is
    # not authority over another process's consequence.


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_trust_issuance_history_immutable
            ON public.trust_envelope_issuance_log;
        DROP FUNCTION IF EXISTS
            public.trust_enforce_issuance_history_immutable();
        DROP TRIGGER IF EXISTS trg_b24_dirty_event_authority
            ON public.b24_dirty_events;
        DROP FUNCTION IF EXISTS public.b24_enforce_dirty_event_authority();
        """
    )
    _if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.b24_dirty_events"
        " TO app_user",
    )
    for relation in (
        "trust_envelope_issuance_log",
        "trust_replay_events",
        "trust_scope_denial_events",
    ):
        _if_role_exists(
            "app_user",
            f"GRANT SELECT, INSERT, UPDATE ON TABLE public.{relation} TO app_user",
        )
        _if_role_exists(
            "app_rw",
            f"GRANT SELECT, INSERT, UPDATE ON TABLE public.{relation} TO app_rw",
        )
        _if_role_exists(
            "app_ro",
            f"GRANT SELECT ON TABLE public.{relation} TO app_ro",
        )
