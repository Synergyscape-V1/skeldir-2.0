"""B2.5-P14: close issuance fabricability and give B2.7/B2.8 a bounded substrate.

Revision ID: 202609041200
Revises: 202609031200

This migration carries two things: P14 Gate 0, and the physical substrate the
B2.7/B2.8 conservation proofs run against.

----------------------------------------------------------------------------
Gate 0 -- durable issuance history must be causally non-fabricable
----------------------------------------------------------------------------

Independent audit 67 physically executed, on protected main, as the real
``app_worker`` login::

    INSERT INTO trust_envelope_issuance_log (..., status) VALUES (..., 'success')

and received ``INSERT 0 1``. The row satisfied every CHECK, sat correctly under
RLS, and was observationally indistinguishable from a record of a real signing.
The C21 immutability trigger did not catch it: that trigger covers ``UPDATE``
and ``DELETE``, and a fabrication is an ``INSERT``.

Two independent facts made it possible, and this migration addresses both.

**Privilege.** ``202607011200`` granted ``SELECT, INSERT, UPDATE`` on all four
trust audit relations to ``app_user`` *and* ``app_rw``. C21 removed the UPDATE
head from both but kept INSERT on ``app_rw``, justified in its own docstring by
"the C9 positive-confidence lane composes a Trust read under the worker
principal". That lane sets ``DATABASE_URL`` to ``app_worker`` for its whole test
process because the same process also samples inline; it is a harness
convenience, not a fact about the deployed topology. In production only the API
container receives the trust issuance path, ``worker_bayesian``/``worker_b23_*``
receive ``C19_WORKER_DATABASE_URL`` and no route to it, and ``grep`` across
``app/tasks/`` finds no reference to ``record_trust_audit_event``,
``_project_completed_issuance_log`` or the trust API at all. The one
worker-reachable issuance-adjacent function,
``reconcile_stale_trust_issuance_states``, already uses the dedicated
``app_trust_issuer`` factory. The API may authorize an issuance, while only
the dedicated issuer may project its terminal consequence.

**Consequence.** Fencing the principal alone would leave the deeper property
unstated: nothing in the schema bound a terminal success row to *any* real
lineage. ``access_audit_ref`` was free text; a fabricated row could name an
audit record that never existed. Audit 66 recorded this as bounded hardening
debt on the same relation. So this migration also makes the durable record a
*projection* of the audit ledger rather than an independent claim:

  * a real foreign key ``(tenant_id, access_audit_ref) -> trust_access_log
    (tenant_id, audit_ref)``, so the lineage exists physically and survives a
    disabled trigger;
  * a BEFORE INSERT guard that requires the referenced ledger row and linked
    issuance attempt to have reached signer-confirmed ``issued`` state, with
    exact retained-artifact correspondence, before identity fields may project
    into terminal history.

Authority is therefore expressed three times -- privilege, referential binding,
consequence guard -- for the reason Corrective XX and XXI established
empirically: a later migration that re-grants the historical privilege must not
silently restore the historical capability. The P14 negative controls sever each
layer independently and then all of them, and only the fully severed state may
reproduce the audit's fabrication.

The same blanket grant reached ``trust_replay_events`` and
``trust_scope_denial_events``; both are written only by the API session on the
same code path, so both are narrowed the same way. That is audit 67's forward
obligation 2.

----------------------------------------------------------------------------
B2.7 / B2.8 substrate
----------------------------------------------------------------------------

``b27_explanation_materializations`` stores explanations keyed by a *semantic*
cache identity, not by envelope id. The identity closes over tenant, semantic
truth, policy state, confidence state, causal status, fallback state and the
content-addressed projection profile hash, so a lawful source transition
T1 -> T2 produces a different key and a stale explanation is unreachable rather
than merely detectable. A trigger additionally marks superseded rows stale when
new issuance history for the same subject carries a different semantic truth,
which is the observable half of Gate 10.

``b28_simulation_requests`` / ``b28_simulation_results`` / ``b28_proposals``
make Gate 6 structural: a result carries a NOT NULL foreign key to a request,
so a simulation result cannot physically exist without the explicit request
that authorized it. Money columns are ``bigint`` minor units with CHECK
constraints, allocation sums are conserved by a constraint trigger, and a CHECK
refuses any action authority stronger than ``proposal_required`` -- P14 emits
proposals, never executions.
"""

from __future__ import annotations

from alembic import op


revision = "202609041200"
down_revision = "202609031200"
branch_labels = None
depends_on = None


# The identity fields a durable issuance record projects from the audit ledger.
# Each is written from the same `_params(...)` mapping as the ledger row in the
# same transaction, so agreement is a property of the lawful path rather than a
# hope about it.
_LEDGER_PROJECTED_COLUMNS = (
    "idempotency_key_hash",
    "subject_type",
    "subject_ref_hash",
    "envelope_hash",
    "semantic_truth_hash",
    "policy_state",
    "audit_hash",
)

_P14_TENANT_TABLES = (
    "b27_explanation_materializations",
    "b28_simulation_requests",
    "b28_simulation_results",
    "b28_proposals",
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


def _enable_force_rls(table: str) -> None:
    op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"DROP POLICY IF EXISTS tenant_isolation_policy_{table} ON public.{table}"
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_policy_{table}
        ON public.{table}
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Gate 0 -- referential binding.
    # ------------------------------------------------------------------
    # Rows written before this revision by anything other than
    # the prior authorization-time projection may name an audit_ref that never
    # existed. They are
    # exactly the class this constraint exists to make impossible, so the
    # migration refuses to run rather than silently validating around them.
    op.execute(
        """
        DO $$
        DECLARE
            orphan_count bigint;
        BEGIN
            SELECT count(*)
              INTO orphan_count
              FROM public.trust_envelope_issuance_log AS issuance
             WHERE NOT EXISTS (
                   SELECT 1
                     FROM public.trust_access_log AS ledger
                    WHERE ledger.tenant_id = issuance.tenant_id
                      AND ledger.audit_ref = issuance.access_audit_ref
             );
            IF orphan_count > 0 THEN
                RAISE EXCEPTION
                    'B2.5-P14 Gate 0: % durable issuance row(s) name no audit '
                    'ledger record. Durable issuance history must project a '
                    'real access-log issuance; resolve the unbound rows before '
                    'migrating.', orphan_count
                    USING ERRCODE = '23503';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        ALTER TABLE public.trust_envelope_issuance_log
            ADD CONSTRAINT fk_trust_issuance_log_access_audit
            FOREIGN KEY (tenant_id, access_audit_ref)
            REFERENCES public.trust_access_log (tenant_id, audit_ref)
            ON DELETE CASCADE
        """
    )

    # ------------------------------------------------------------------
    # 2. Gate 0 -- consequence layer.
    # ------------------------------------------------------------------
    agreement_predicate = "\n               OR ".join(
        f"NEW.{column} IS DISTINCT FROM ledger_{column}"
        for column in _LEDGER_PROJECTED_COLUMNS
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.trust_enforce_issuance_consequence_authority()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            principal_is_superuser boolean;
            table_owner_oid oid;
            issuer_role_oid oid;
            caller_is_issuer boolean;
            -- Scalars, not ``trust_access_log%ROWTYPE``. PL/pgSQL resolves a
            -- %ROWTYPE declaration when the function is *created*, and pg_dump
            -- emits functions before the tables they name -- which makes the
            -- canonical schema artifact inapplicable to an empty database.
            -- Corrective XVII found that exact class on this schema, and the R2
            -- bootstrap already carries a reorder list because of it. Naming the
            -- columns keeps the compile-time dependency out of the artifact
            -- instead of adding another entry to that list.
            ledger_event_type text;
            ledger_status text;
            ledger_idempotency_key_hash text;
            ledger_subject_type text;
            ledger_subject_ref_hash text;
            ledger_envelope_hash text;
            ledger_semantic_truth_hash text;
            ledger_policy_state text;
            ledger_audit_hash text;
            ledger_issuance_state text;
            ledger_issued_attempt_id uuid;
            ledger_issued_signing_key_id text;
            ledger_issued_signature_hash text;
            ledger_issued_signature bytea;
            ledger_issued_envelope jsonb;
            attempt_state text;
            attempt_signing_key_id text;
            attempt_signature_hash text;
            attempt_signature bytea;
            attempt_signed_envelope jsonb;
        BEGIN
            SELECT rolsuper
              INTO principal_is_superuser
              FROM pg_catalog.pg_roles
             WHERE rolname = session_user;
            SELECT relowner
              INTO table_owner_oid
              FROM pg_catalog.pg_class
             WHERE oid = TG_RELID;

            -- A superuser or the owning migration principal can drop this
            -- trigger outright, so refusing them buys no authority. C20/C21
            -- already assert that no runtime login reaches the owner.
            IF COALESCE(principal_is_superuser, false)
               OR pg_catalog.pg_has_role(session_user, table_owner_oid, 'USAGE')
            THEN
                RETURN NEW;
            END IF;

            -- Layer A: only the dedicated issuer may project a terminal
            -- consequence.  The API principal may authorize an issuance, but
            -- it cannot assert that signing happened: pairing an
            -- ``authorized`` ledger row with a well-shaped terminal row is
            -- not sufficient evidence of a completed consequence.
            SELECT oid
              INTO issuer_role_oid
              FROM pg_catalog.pg_roles
             WHERE rolname = 'app_trust_issuer';
            caller_is_issuer := issuer_role_oid IS NOT NULL
                AND session_user = 'app_trust_issuer';
            IF NOT caller_is_issuer THEN
                RAISE EXCEPTION
                    'durable trust issuance history is recorded by the '
                    'dedicated issuer alone; % may not assert a signing '
                    'consequence', session_user
                    USING ERRCODE = '42501';
            END IF;

            -- Layer B: the row must project a completed, signer-confirmed
            -- issuance.  ``authorized`` is authorization to try, not evidence
            -- of a consequence.  The source ledger and attempt therefore have
            -- to be terminal and agree on the retained signature artifact.
            SELECT event_type, status, idempotency_key_hash, subject_type,
                   subject_ref_hash, envelope_hash, semantic_truth_hash,
                   policy_state, audit_hash, issuance_state, issued_attempt_id,
                   issued_signing_key_id, issued_signature_hash,
                   issued_signature, issued_envelope
              INTO ledger_event_type, ledger_status, ledger_idempotency_key_hash,
                   ledger_subject_type, ledger_subject_ref_hash,
                   ledger_envelope_hash, ledger_semantic_truth_hash,
                   ledger_policy_state, ledger_audit_hash,
                   ledger_issuance_state, ledger_issued_attempt_id,
                   ledger_issued_signing_key_id, ledger_issued_signature_hash,
                   ledger_issued_signature, ledger_issued_envelope
              FROM public.trust_access_log
             WHERE tenant_id = NEW.tenant_id
               AND audit_ref = NEW.access_audit_ref;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'durable trust issuance history must project an existing '
                    'audit ledger record; % names no such audit_ref',
                    NEW.access_audit_ref
                    USING ERRCODE = '42501';
            END IF;
            IF ledger_event_type <> 'issuance' OR ledger_status <> 'success' THEN
                RAISE EXCEPTION
                    'durable trust issuance history may only project a '
                    'successful issuance ledger record; % is %/%',
                    NEW.access_audit_ref, ledger_event_type, ledger_status
                    USING ERRCODE = '42501';
            END IF;
            IF ledger_issuance_state <> 'issued'
               OR ledger_issued_attempt_id IS NULL THEN
                RAISE EXCEPTION
                    'durable trust issuance history requires an issued ledger '
                    'record with a signer-confirmed attempt; % is %',
                    NEW.access_audit_ref, ledger_issuance_state
                    USING ERRCODE = '42501';
            END IF;
            SELECT attempt.attempt_state, attempt.signing_key_id,
                   attempt.signature_hash, attempt.signature,
                   attempt.signed_envelope
              INTO attempt_state, attempt_signing_key_id, attempt_signature_hash,
                   attempt_signature, attempt_signed_envelope
              FROM public.trust_issuance_attempts AS attempt
             WHERE attempt.tenant_id = NEW.tenant_id
               AND attempt.audit_ref = NEW.access_audit_ref
               AND attempt.id = ledger_issued_attempt_id;
            IF NOT FOUND OR attempt_state <> 'issued'
               OR attempt_signing_key_id IS DISTINCT FROM ledger_issued_signing_key_id
               OR attempt_signature_hash IS DISTINCT FROM ledger_issued_signature_hash
               OR attempt_signature IS DISTINCT FROM ledger_issued_signature
               OR attempt_signed_envelope IS DISTINCT FROM ledger_issued_envelope THEN
                RAISE EXCEPTION
                    'durable trust issuance history requires completed '
                    'attempt evidence corresponding to the ledger; %',
                    NEW.access_audit_ref
                    USING ERRCODE = '42501';
            END IF;
            IF {agreement_predicate}
            THEN
                RAISE EXCEPTION
                    'durable trust issuance history must agree with the audit '
                    'ledger record it projects; % disagrees',
                    NEW.access_audit_ref
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.audit_ref IS DISTINCT FROM NEW.access_audit_ref THEN
                RAISE EXCEPTION
                    'durable trust issuance history carries one audit identity; '
                    '% and % disagree', NEW.audit_ref, NEW.access_audit_ref
                    USING ERRCODE = '42501';
            END IF;

            RETURN NEW;
        END;
        $BODY$;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_trust_issuance_consequence_authority
            ON public.trust_envelope_issuance_log;
        CREATE TRIGGER trg_trust_issuance_consequence_authority
            BEFORE INSERT ON public.trust_envelope_issuance_log
            FOR EACH ROW
            EXECUTE FUNCTION public.trust_enforce_issuance_consequence_authority();
        """
    )

    # ------------------------------------------------------------------
    # 3. Gate 0 -- privilege layer.
    # ------------------------------------------------------------------
    # The terminal issuance projection is written only after C16/C17 completed
    # the signer-confirmed ledger transition, under the dedicated issuer.  The
    # API still appends request-local replay/denial events, so those retain
    # their narrower API writer.  Treating all three alike was the P14 gap:
    # ``app_user`` could author both an ``authorized`` ledger and its supposed
    # terminal consequence before any signing attempt existed.
    for relation in ("trust_envelope_issuance_log",):
        op.execute(f"REVOKE ALL ON TABLE public.{relation} FROM PUBLIC")
        _if_role_exists(
            "app_user",
            f"REVOKE ALL ON TABLE public.{relation} FROM app_user;"
            f" GRANT SELECT ON TABLE public.{relation} TO app_user",
        )
        _if_role_exists(
            "app_rw",
            f"REVOKE ALL ON TABLE public.{relation} FROM app_rw;"
            f" GRANT SELECT ON TABLE public.{relation} TO app_rw",
        )
        _if_role_exists(
            "app_ro",
            f"REVOKE ALL ON TABLE public.{relation} FROM app_ro;"
            f" GRANT SELECT ON TABLE public.{relation} TO app_ro",
        )
        _if_role_exists(
            "app_trust_issuer",
            f"REVOKE ALL ON TABLE public.{relation} FROM app_trust_issuer;"
            f" GRANT SELECT, INSERT ON TABLE public.{relation} TO app_trust_issuer",
        )

    for relation in ("trust_replay_events", "trust_scope_denial_events"):
        op.execute(f"REVOKE ALL ON TABLE public.{relation} FROM PUBLIC")
        _if_role_exists(
            "app_user",
            f"REVOKE ALL ON TABLE public.{relation} FROM app_user;"
            f" GRANT SELECT, INSERT ON TABLE public.{relation} TO app_user",
        )
        _if_role_exists(
            "app_rw",
            f"REVOKE ALL ON TABLE public.{relation} FROM app_rw;"
            f" GRANT SELECT ON TABLE public.{relation} TO app_rw",
        )
        _if_role_exists(
            "app_ro",
            f"REVOKE ALL ON TABLE public.{relation} FROM app_ro;"
            f" GRANT SELECT ON TABLE public.{relation} TO app_ro",
        )

    # ------------------------------------------------------------------
    # 4. B2.7 explanation materializations.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE public.b27_explanation_materializations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            cache_identity_hash text NOT NULL,
            source_envelope_id text NOT NULL,
            source_semantic_truth_hash text NOT NULL,
            subject_type text NOT NULL,
            subject_ref_hash text NOT NULL,
            projection_profile_id text NOT NULL,
            projection_profile_version text NOT NULL,
            projection_profile_hash text NOT NULL,
            explanation_contract_version text NOT NULL,
            policy_state text NOT NULL,
            confidence_status text NOT NULL,
            causal_status text,
            fallback_applied boolean NOT NULL,
            claim_count integer NOT NULL,
            narrative text NOT NULL,
            claims jsonb NOT NULL,
            authority_class text NOT NULL DEFAULT 'non_authoritative_explanation',
            judge_authority text NOT NULL DEFAULT 'none',
            stale boolean NOT NULL DEFAULT false,
            superseded_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_b27_cache_identity_shape CHECK (
                cache_identity_hash ~ '^sha256:[0-9a-f]{64}$'
                AND source_semantic_truth_hash ~ '^sha256:[0-9a-f]{64}$'
                AND subject_ref_hash ~ '^sha256:[0-9a-f]{64}$'
                AND projection_profile_hash ~ '^sha256:[0-9a-f]{64}$'
            ),
            -- P14-G2/G3/G4 restated where the bytes actually live. An
            -- explanation row that claims a judge authority, or that was
            -- produced under a profile admitting provider labels, cannot exist.
            CONSTRAINT ck_b27_projection_profile CHECK (
                projection_profile_id = 'llm_explanation_projection_safe'
            ),
            CONSTRAINT ck_b27_judge_authority CHECK (judge_authority = 'none'),
            CONSTRAINT ck_b27_authority_class CHECK (
                authority_class = 'non_authoritative_explanation'
            ),
            CONSTRAINT ck_b27_policy_state CHECK (
                policy_state IN (
                    'blocked', 'read_only', 'simulation_only',
                    'proposal_required', 'approval_required'
                )
            ),
            CONSTRAINT ck_b27_confidence_status CHECK (
                confidence_status IN (
                    'available', 'unavailable', 'degraded', 'diagnostics_failed'
                )
            ),
            CONSTRAINT ck_b27_claims_object CHECK (jsonb_typeof(claims) = 'array'),
            CONSTRAINT ck_b27_stale_shape CHECK (
                (stale = true AND superseded_at IS NOT NULL)
                OR (stale = false AND superseded_at IS NULL)
            ),
            -- The cache key is the semantic identity, scoped to the tenant.
            -- H-P14-E7: a foreign tenant cannot collide with this key even if
            -- it somehow computed the same semantic hash.
            CONSTRAINT uq_b27_cache_identity UNIQUE (tenant_id, cache_identity_hash)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_b27_explanation_subject
            ON public.b27_explanation_materializations
            (tenant_id, subject_type, subject_ref_hash, stale)
        """
    )

    # ------------------------------------------------------------------
    # 5. B2.8 simulation substrate.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE public.b28_simulation_requests (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            request_ref text NOT NULL,
            requested_by text NOT NULL,
            source_envelope_id text NOT NULL,
            source_semantic_truth_hash text NOT NULL,
            input_snapshot_hash text NOT NULL,
            total_budget_minor bigint NOT NULL,
            currency text NOT NULL,
            channel_count integer NOT NULL,
            sufficiency_policy_version text NOT NULL,
            requested_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_b28_request_hashes CHECK (
                source_semantic_truth_hash ~ '^sha256:[0-9a-f]{64}$'
                AND input_snapshot_hash ~ '^sha256:[0-9a-f]{64}$'
            ),
            CONSTRAINT ck_b28_request_budget CHECK (total_budget_minor > 0),
            CONSTRAINT ck_b28_request_currency CHECK (currency ~ '^[A-Z]{3}$'),
            CONSTRAINT ck_b28_request_channels CHECK (channel_count > 0),
            CONSTRAINT uq_b28_request_ref UNIQUE (tenant_id, request_ref)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.b28_simulation_results (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            -- Gate 6 made structural: NOT NULL. A result cannot exist without
            -- the explicit request that authorized it, so "data sufficiency
            -- autonomously triggered optimization" has no representable form.
            request_id uuid NOT NULL
                REFERENCES public.b28_simulation_requests(id) ON DELETE RESTRICT,
            source_envelope_id text NOT NULL,
            source_semantic_truth_hash text NOT NULL,
            projection_profile_hash text NOT NULL,
            input_snapshot_hash text NOT NULL,
            solver_profile text NOT NULL,
            solver_invocations integer NOT NULL,
            total_budget_minor bigint NOT NULL,
            allocated_total_minor bigint NOT NULL,
            currency text NOT NULL,
            action_authority text NOT NULL,
            authority_class text NOT NULL DEFAULT 'deterministic_simulation',
            llm_authority_over_allocation text NOT NULL DEFAULT 'none',
            allocations jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_b28_result_hashes CHECK (
                source_semantic_truth_hash ~ '^sha256:[0-9a-f]{64}$'
                AND projection_profile_hash ~ '^sha256:[0-9a-f]{64}$'
                AND input_snapshot_hash ~ '^sha256:[0-9a-f]{64}$'
            ),
            -- Sigma allocation_minor = total_budget_minor, as a constraint the
            -- writer cannot argue with.
            CONSTRAINT ck_b28_result_conserved CHECK (
                allocated_total_minor = total_budget_minor
            ),
            CONSTRAINT ck_b28_result_budget CHECK (total_budget_minor > 0),
            CONSTRAINT ck_b28_result_solver_ran CHECK (solver_invocations >= 1),
            -- P14 emits proposals, never executions. `approval_required` is a
            -- lawful *source* authority and an unlawful *downstream* one.
            CONSTRAINT ck_b28_result_action_authority CHECK (
                action_authority IN (
                    'blocked', 'read_only', 'simulation_only', 'proposal_required'
                )
            ),
            CONSTRAINT ck_b28_result_llm_authority CHECK (
                llm_authority_over_allocation = 'none'
            ),
            CONSTRAINT ck_b28_result_authority_class CHECK (
                authority_class = 'deterministic_simulation'
            ),
            CONSTRAINT ck_b28_result_allocations CHECK (
                jsonb_typeof(allocations) = 'array'
            ),
            CONSTRAINT uq_b28_result_request UNIQUE (tenant_id, request_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.b28_proposals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            result_id uuid NOT NULL
                REFERENCES public.b28_simulation_results(id) ON DELETE RESTRICT,
            proposal_ref text NOT NULL,
            source_envelope_id text NOT NULL,
            action_authority text NOT NULL,
            requires_human_approval boolean NOT NULL DEFAULT true,
            authority_class text NOT NULL DEFAULT 'non_authoritative_proposal',
            allocations jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_b28_proposal_action_authority CHECK (
                action_authority IN (
                    'blocked', 'read_only', 'simulation_only', 'proposal_required'
                )
            ),
            CONSTRAINT ck_b28_proposal_human_approval CHECK (
                requires_human_approval = true
            ),
            CONSTRAINT ck_b28_proposal_authority_class CHECK (
                authority_class = 'non_authoritative_proposal'
            ),
            CONSTRAINT ck_b28_proposal_allocations CHECK (
                jsonb_typeof(allocations) = 'array'
            ),
            CONSTRAINT uq_b28_proposal_ref UNIQUE (tenant_id, proposal_ref)
        )
        """
    )

    # The conservation trigger. The CHECK above compares two stored columns;
    # this one compares the stored total against the allocation rows actually
    # persisted, so a row whose jsonb disagrees with its own total cannot exist
    # either.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b28_enforce_allocation_conservation()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            summed bigint;
            line jsonb;
        BEGIN
            summed := 0;
            FOR line IN
                SELECT * FROM jsonb_array_elements(NEW.allocations)
            LOOP
                IF jsonb_typeof(line -> 'allocation_minor') <> 'number' THEN
                    RAISE EXCEPTION
                        'b28 allocation lines carry integer minor units; % does not',
                        line
                        USING ERRCODE = '22P02';
                END IF;
                IF (line ->> 'allocation_minor') !~ '^-?[0-9]+$' THEN
                    RAISE EXCEPTION
                        'b28 allocation lines may not carry fractional money; % does',
                        line ->> 'allocation_minor'
                        USING ERRCODE = '22P02';
                END IF;
                summed := summed + (line ->> 'allocation_minor')::bigint;
            END LOOP;
            IF summed <> NEW.total_budget_minor THEN
                RAISE EXCEPTION
                    'b28 allocation must conserve the requested budget; % <> %',
                    summed, NEW.total_budget_minor
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $BODY$;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b28_allocation_conservation
            ON public.b28_simulation_results;
        CREATE TRIGGER trg_b28_allocation_conservation
            BEFORE INSERT OR UPDATE ON public.b28_simulation_results
            FOR EACH ROW
            EXECUTE FUNCTION public.b28_enforce_allocation_conservation();
        """
    )

    # ------------------------------------------------------------------
    # 6. Gate 10 observability -- new Trust supersedes dependent explanations.
    # ------------------------------------------------------------------
    # The cache identity already makes a stale row unreachable for the new
    # state. This makes the transition *visible*, which is what an auditor
    # reconstructing "was this explanation current when it was served?" needs.
    # SECURITY DEFINER with a pinned search path. Marking a dependent
    # explanation stale is a *consequence of the issuance*, not an action the
    # issuing principal takes, so it runs with the schema owner's authority
    # rather than the caller's. That keeps the API principal's grant set at
    # INSERT+SELECT -- it never needs UPDATE on a relation it does not own --
    # and it keeps the consequence working for any future lawful issuer without
    # widening that issuer's authority. FORCE RLS still applies to the owner, so
    # the update stays inside the session's bound tenant.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b27_supersede_stale_explanations()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $BODY$
        BEGIN
            UPDATE public.b27_explanation_materializations AS materialization
               SET stale = true,
                   superseded_at = now()
             WHERE materialization.tenant_id = NEW.tenant_id
               AND materialization.subject_type = NEW.subject_type
               AND materialization.subject_ref_hash = NEW.subject_ref_hash
               AND materialization.source_semantic_truth_hash
                   IS DISTINCT FROM NEW.semantic_truth_hash
               AND materialization.stale = false;
            RETURN NEW;
        END;
        $BODY$;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b27_supersede_stale_explanations
            ON public.trust_envelope_issuance_log;
        CREATE TRIGGER trg_b27_supersede_stale_explanations
            AFTER INSERT ON public.trust_envelope_issuance_log
            FOR EACH ROW
            EXECUTE FUNCTION public.b27_supersede_stale_explanations();
        """
    )

    # ------------------------------------------------------------------
    # 7. Tenant isolation and least privilege for the new relations.
    # ------------------------------------------------------------------
    for table in _P14_TENANT_TABLES:
        _enable_force_rls(table)
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC")
        _if_role_exists(
            "app_user",
            f"GRANT SELECT, INSERT ON TABLE public.{table} TO app_user",
        )
        _if_role_exists("app_ro", f"GRANT SELECT ON TABLE public.{table} TO app_ro")

    # No runtime principal holds UPDATE or DELETE on any P14 relation. The one
    # lawful post-insert transition -- marking a superseded explanation stale --
    # is a definer-authority consequence of issuance, so it does not require the
    # writer to hold a capability it would otherwise never use.
    op.execute(
        """
        REVOKE EXECUTE ON FUNCTION public.b27_supersede_stale_explanations()
            FROM PUBLIC
        """
    )


def downgrade() -> None:
    # The four relations dropped here are created by this revision and by
    # nothing before it, so a downgrade removes exactly what the upgrade
    # added. They hold downstream materializations, never authoritative
    # truth: every value in them is a projection of a TrustEnvelope that
    # remains intact. That is why the destructive annotation is honest here
    # and would not be on an upstream relation.
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b27_supersede_stale_explanations
            ON public.trust_envelope_issuance_log;
        DROP FUNCTION IF EXISTS public.b27_supersede_stale_explanations();
        DROP TRIGGER IF EXISTS trg_b28_allocation_conservation
            ON public.b28_simulation_results;
        DROP FUNCTION IF EXISTS public.b28_enforce_allocation_conservation();
        DROP TABLE IF EXISTS public.b28_proposals; -- # CI:DESTRUCTIVE_OK
        DROP TABLE IF EXISTS public.b28_simulation_results; -- # CI:DESTRUCTIVE_OK
        DROP TABLE IF EXISTS public.b28_simulation_requests; -- # CI:DESTRUCTIVE_OK
        DROP TABLE IF EXISTS public.b27_explanation_materializations; -- # CI:DESTRUCTIVE_OK
        DROP TRIGGER IF EXISTS trg_trust_issuance_consequence_authority
            ON public.trust_envelope_issuance_log;
        DROP FUNCTION IF EXISTS
            public.trust_enforce_issuance_consequence_authority();
        ALTER TABLE public.trust_envelope_issuance_log
            DROP CONSTRAINT IF EXISTS fk_trust_issuance_log_access_audit;
        """
    )
    for relation in (
        "trust_envelope_issuance_log",
        "trust_replay_events",
        "trust_scope_denial_events",
    ):
        _if_role_exists(
            "app_rw",
            f"GRANT SELECT, INSERT ON TABLE public.{relation} TO app_rw",
        )
