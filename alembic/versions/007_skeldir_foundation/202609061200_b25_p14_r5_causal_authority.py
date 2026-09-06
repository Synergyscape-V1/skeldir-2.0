"""B2.5-P14 Corrective V: make B2.8 request intent and solver consequence physical.

Revision ID: 202609061200
Revises: 202609051200

Five propositions were physically reproduced on the entering protected-main tree
(``0d8d2283``, tree ``795b4ddc``, head ``202609051200``) on a fresh PostgreSQL 15
provisioned by the repository's own role script, using the real least-privilege
``app_user`` login and no application call at all::

    REQ_DIRECT_SQL_NO_INTENT       ALLOWED  requested_by='attacker:not-a-real-caller'
    REQ_EMPTY_REQUESTED_BY         ALLOWED  requested_by=''
    RESULT_FORGED_NO_SOLVER        ALLOWED  solver_invocations=1, channels 'a'/'b'
    RESULT_SOLVER_INVOCATIONS_99   ALLOWED  solver_invocations=99
    PROPOSAL_ON_FORGED_RESULT      ALLOWED

and one structural observation::

    CHANNEL_EVIDENCE_RETAINED      False    the request stores channel_count only

----------------------------------------------------------------------------
Root cause
----------------------------------------------------------------------------

Two independent defects with one shape.

**Authority was assigned by relation membership, not by causal responsibility.**
``app_user`` -- the generic API principal -- held INSERT on
``b28_simulation_requests``, ``b28_simulation_results`` and ``b28_proposals``.
One authority domain could therefore author the alleged cause *and* the alleged
consequence. This is the C16/C19 issuance self-certification defect applied to
P14's own relations; the issuance side closed it by giving the consequence its
own login principal, which ``SET ROLE`` cannot forge because the guard keys on
``session_user``.

**The guards compared rows instead of deriving facts.** The Corrective IV guard
checks that a result *agrees with* its request: same envelope, same budget, same
snapshot string, governed profile name. Agreement is necessary and not
sufficient. Nothing recomputed anything, so::

    requested_by         was text the writer chose
    input_snapshot_hash  was a hash of nothing -- no input was retained
    solver_invocations   was an integer the writer chose
    allocations          was any conserving split the writer chose
    sufficiency          was never adjudicated at the durable boundary

B2.7 was never fabricable in this way, and the reason is instructive: its guard
does not compare the narrative to anything, it *re-derives* the narrative from
the registered frame corpus and requires equality. That is the physics this
revision brings to B2.8.

----------------------------------------------------------------------------
The repair
----------------------------------------------------------------------------

**1. The request becomes a complete, self-describing input witness.** The exact
governed channel evidence is retained (``channel_evidence``), so an auditor
holding only the durable row can reconstruct what the solver consumed. The
database then *recomputes* ``input_snapshot_hash`` from those bytes by
reproducing ``app.simulation.admission.compute_input_snapshot_hash`` --
``json.dumps(sort_keys=True, separators=(',',':'), ensure_ascii=False)`` over
the same material, SHA-256, ``sha256:`` tag -- and refuses any row whose stored
hash is not the hash of its own stored inputs. The hash stops being a string and
becomes a derived fact.

**2. Requester identity becomes consequence-derived.** ``requested_by`` is no
longer text: the row must name a live ``agent_service_credentials`` row and its
``agent_clients`` parent, both in the same tenant, ``status='active'``, not
revoked, not expired; and ``requested_by`` must equal
``'agent_client:' || requested_by_agent_client_id``, which the guard computes.
Whatever the writer types, it must equal what the database derives from an
authenticated principal that really exists. An invented requester is
unrepresentable, and so is a revoked or foreign-tenant one.

**3. Sufficiency becomes a durable adjudication.** The database evaluates the
governed sufficiency predicate over the retained evidence and refuses a request
whose recorded verdict, reasons or observed counts differ. A result may exist
only for a request whose *database-adjudicated* verdict is true, so an
insufficient request has no representable consequence.

**4. The allocation is recomputed, not compared.** The solver is a deterministic
integer function -- largest remainder over verified revenue, ties broken by
channel id -- so the database can compute it itself. ``b28_recompute_allocation``
is a PL/pgSQL twin of ``app.simulation.solver.allocate_budget``; the result guard
runs it over the request's retained evidence and requires the persisted
allocation to be exactly its output, line for line, including weights and order.
A fabricated allocation is not refused because it looks wrong; it is refused
because it is not the value of the function. ``solver_invocations`` must be
exactly 1: a lawful admission runs the solver once, and 99 is now as
unrepresentable as 0.

For a deterministic function this is the strongest consequence claim available,
and the evidence report says so plainly: what is proved is that the persisted
allocation *is* the governed solver's output on the admitted input. A forger
would have to reimplement the governed algorithm bit-for-bit, at which point the
value is the solver's consequence by extension. No signature over self-asserted
metadata is introduced, because such a witness would remain self-certifiable by
whoever holds the key (Directive V, H-RC-V-08).

**5. Authority follows causal responsibility.** ``app_user`` loses INSERT on all
three B2.8 relations and keeps SELECT. Two dedicated least-privilege logins are
introduced and the guards key on ``session_user``::

    app_b28_requester   may insert a request, and nothing else
    app_b28_solver      may insert a result and a proposal, and nothing else

Neither is a member of ``app_rw``/``app_ro``, so no runtime principal reaches
either by inheritance, and neither reaches the other. The privilege layer refuses
before any trigger runs, and the guards refuse independently if a grant
regression ever restores the privilege -- the same two-layer construction the
Gate 0 issuance fence uses.

Owners and superusers are exempt from the *principal* checks only. They can drop
the trigger outright, so refusing them buys no authority; the C20/C21 contracts
assert no runtime login reaches the owner. Every *derivation* check -- snapshot,
sufficiency, allocation -- runs for every principal including the owner, because
those are statements about truth rather than about authority.

----------------------------------------------------------------------------
Pre-existing rows
----------------------------------------------------------------------------

The B2.8 relations were created two revisions ago, carry no production ingress
(P14 exposes no HTTP surface) and have no application writer on the entering
tree. A row written before this revision cannot satisfy the corrected contract
and there is no honest backfill for an authenticated principal that never
existed, so the upgrade asserts the relations are empty and fails closed rather
than inventing provenance. That is a declared limitation, not an accident.
"""

from __future__ import annotations

from alembic import op


revision = "202609061200"
down_revision = "202609051200"
branch_labels = None
depends_on = None


# Mirrors app/simulation/contract.py and app/simulation/solver.py. A drift test
# in backend/tests/trust/test_b25_p14_r5_causal_authority.py asserts the
# equality, so a constant that moves in one place and not the other is
# merge-blocking.
_CONTRACT_VERSION = "b25-p14-simulation-v1"
_SOLVER_PROFILE = "b25-p14-deterministic-largest-remainder-v1"
_SUFFICIENCY_POLICY_VERSION = "b25-p14-sufficiency-v1"

# Mirrors app/simulation/sufficiency.py.
_MIN_CHANNELS = 2
_MIN_TOTAL_CONVERSIONS = 5
_MIN_CHANNELS_WITH_EVIDENCE = 2
_MIN_TOTAL_REVENUE_MINOR = 1

_BASIS_POINTS = 10_000

# The dedicated causal authorities. The names are load-bearing: the guards
# compare them to `session_user`, which SET ROLE cannot change.
_REQUEST_PRINCIPAL = "app_b28_requester"
_SOLVER_PRINCIPAL = "app_b28_solver"

_ADMISSIBLE_POLICY_STATES = (
    "ARRAY['simulation_only', 'proposal_required', 'approval_required']::text[]"
)


def _if_role_exists(role: str, statement: str) -> None:
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
    # 0. Fail closed on rows that cannot satisfy the corrected contract.
    # ------------------------------------------------------------------
    # The relation is RLS-FORCED, so even its owner sees no rows while
    # `app.current_tenant_id` is unset: `tenant_id = NULL::uuid` evaluates to
    # UNKNOWN and the policy filters everything out. A bare `count(*)` here
    # would therefore return 0 over a populated table and admit the very state
    # it exists to refuse -- Directive V H-RC-V-06, observed rather than
    # theorised. The force flag is lifted for the count and restored
    # immediately; if the assertion fires, the whole migration transaction rolls
    # back and the flag is restored by the rollback as well.
    op.execute(
        """
        DO $$
        DECLARE
            existing bigint;
        BEGIN
            ALTER TABLE public.b28_simulation_requests
                NO FORCE ROW LEVEL SECURITY;
            SELECT count(*) INTO existing FROM public.b28_simulation_requests;
            ALTER TABLE public.b28_simulation_requests
                FORCE ROW LEVEL SECURITY;
            IF existing > 0 THEN
                RAISE EXCEPTION
                    'b25_p14_r5_requires_empty_b28_requests:% rows carry no authenticated requester provenance to backfill',
                    existing
                    USING ERRCODE = '55000';
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # 1. The request becomes a complete input witness with a derived identity.
    # ------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE public.b28_simulation_requests
            ADD COLUMN requested_by_agent_client_id uuid NOT NULL
                REFERENCES public.agent_clients(id) ON DELETE RESTRICT,
            ADD COLUMN requested_by_credential_id uuid NOT NULL
                REFERENCES public.agent_service_credentials(id) ON DELETE RESTRICT,
            ADD COLUMN request_authority_principal text NOT NULL,
            ADD COLUMN channel_evidence jsonb NOT NULL,
            ADD COLUMN solver_profile text NOT NULL,
            ADD COLUMN sufficiency_verdict boolean NOT NULL,
            ADD COLUMN sufficiency_reasons text[] NOT NULL,
            ADD COLUMN observed_channels integer NOT NULL,
            ADD COLUMN observed_conversions integer NOT NULL,
            ADD COLUMN observed_revenue_minor bigint NOT NULL
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.b28_simulation_requests
            ADD CONSTRAINT ck_b28_request_channel_evidence CHECK (
                jsonb_typeof(channel_evidence) = 'array'
                AND jsonb_array_length(channel_evidence) = channel_count
                AND jsonb_array_length(channel_evidence) >= 1
            ),
            ADD CONSTRAINT ck_b28_request_solver_profile CHECK (
                solver_profile = '{_SOLVER_PROFILE}'
            ),
            ADD CONSTRAINT ck_b28_request_requested_by_derived CHECK (
                requested_by = 'agent_client:' || requested_by_agent_client_id::text
            ),
            ADD CONSTRAINT ck_b28_request_observed_nonnegative CHECK (
                observed_channels >= 0
                AND observed_conversions >= 0
                AND observed_revenue_minor >= 0
            )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b28_request_requester
            ON public.b28_simulation_requests
            (tenant_id, requested_by_agent_client_id)
        """
    )

    # ------------------------------------------------------------------
    # 2. The canonical input-snapshot identity, computed by the database.
    # ------------------------------------------------------------------
    # Reproduces app.simulation.admission.compute_input_snapshot_hash exactly:
    # json.dumps(sort_keys=True, separators=(',',':'), ensure_ascii=False) over
    # the governed material, SHA-256, `sha256:` tag. Keys are emitted in
    # code-point order literally rather than sorted at runtime, so the ordering
    # is auditable by reading rather than by trusting a collation. String values
    # are escaped with `to_jsonb(text)::text`, whose escaping rules -- `"`, `\`,
    # and control characters below U+0020, with non-ASCII passed through -- are
    # exactly Python's under `ensure_ascii=False`.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b28_canonical_input_material(
            p_source_envelope_id text,
            p_source_semantic_truth_hash text,
            p_total_budget_minor bigint,
            p_currency text,
            p_channel_evidence jsonb
        )
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        SET search_path = pg_catalog, public
        AS $BODY$
            SELECT '{{"channels":['
                || COALESCE(
                     (
                       SELECT string_agg(
                                '{{"channel_id":'
                                || to_jsonb(elem ->> 'channel_id')::text
                                || ',"conversion_count":'
                                || (elem ->> 'conversion_count')::bigint::text
                                || ',"verified_revenue_minor":'
                                || (elem ->> 'verified_revenue_minor')::bigint::text
                                || '}}',
                                ','
                                ORDER BY (elem ->> 'channel_id') COLLATE "C"
                              )
                       FROM jsonb_array_elements(p_channel_evidence) AS elem
                     ),
                     ''
                   )
                || ']'
                || ',"contract_version":'
                || to_jsonb('{_CONTRACT_VERSION}'::text)::text
                || ',"currency":' || to_jsonb(p_currency)::text
                || ',"solver_profile":' || to_jsonb('{_SOLVER_PROFILE}'::text)::text
                || ',"source_envelope_id":' || to_jsonb(p_source_envelope_id)::text
                || ',"source_semantic_truth_hash":'
                || to_jsonb(p_source_semantic_truth_hash)::text
                || ',"sufficiency_policy_version":'
                || to_jsonb('{_SUFFICIENCY_POLICY_VERSION}'::text)::text
                || ',"total_budget_minor":' || p_total_budget_minor::text
                || '}}'
        $BODY$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b28_input_snapshot_hash(
            p_source_envelope_id text,
            p_source_semantic_truth_hash text,
            p_total_budget_minor bigint,
            p_currency text,
            p_channel_evidence jsonb
        )
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        SET search_path = pg_catalog, public
        AS $BODY$
            SELECT 'sha256:' || encode(
                sha256(
                    convert_to(
                        public.b28_canonical_input_material(
                            p_source_envelope_id,
                            p_source_semantic_truth_hash,
                            p_total_budget_minor,
                            p_currency,
                            p_channel_evidence
                        ),
                        'UTF8'
                    )
                ),
                'hex'
            )
        $BODY$;
        """
    )

    # ------------------------------------------------------------------
    # 3. The governed sufficiency predicate, adjudicated by the database.
    # ------------------------------------------------------------------
    # Mirrors app.simulation.sufficiency.adjudicate_sufficiency, including the
    # order and exact text of the reason codes: an auditor reconstructs the
    # adjudication from the persisted numbers alone.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b28_adjudicate_sufficiency(
            p_channel_evidence jsonb
        )
        RETURNS TABLE (
            sufficient boolean,
            reasons text[],
            observed_channels integer,
            observed_conversions integer,
            observed_revenue_minor bigint
        )
        LANGUAGE plpgsql
        IMMUTABLE
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            n_channels integer := 0;
            n_conversions bigint := 0;
            n_revenue bigint := 0;
            n_with_evidence integer := 0;
            found_reasons text[] := ARRAY[]::text[];
            elem jsonb;
        BEGIN
            FOR elem IN SELECT * FROM jsonb_array_elements(p_channel_evidence)
            LOOP
                n_channels := n_channels + 1;
                n_conversions := n_conversions
                    + (elem ->> 'conversion_count')::bigint;
                n_revenue := n_revenue
                    + (elem ->> 'verified_revenue_minor')::bigint;
                IF (elem ->> 'conversion_count')::bigint > 0
                   AND (elem ->> 'verified_revenue_minor')::bigint > 0
                THEN
                    n_with_evidence := n_with_evidence + 1;
                END IF;
            END LOOP;

            IF n_channels < {_MIN_CHANNELS} THEN
                found_reasons := found_reasons || (
                    'channels_below_minimum:' || n_channels::text
                    || '<' || {_MIN_CHANNELS}::text
                );
            END IF;
            IF n_with_evidence < {_MIN_CHANNELS_WITH_EVIDENCE} THEN
                found_reasons := found_reasons || (
                    'channels_with_evidence_below_minimum:' || n_with_evidence::text
                    || '<' || {_MIN_CHANNELS_WITH_EVIDENCE}::text
                );
            END IF;
            IF n_conversions < {_MIN_TOTAL_CONVERSIONS} THEN
                found_reasons := found_reasons || (
                    'conversions_below_minimum:' || n_conversions::text
                    || '<' || {_MIN_TOTAL_CONVERSIONS}::text
                );
            END IF;
            IF n_revenue < {_MIN_TOTAL_REVENUE_MINOR} THEN
                found_reasons := found_reasons || (
                    'revenue_below_minimum:' || n_revenue::text
                    || '<' || {_MIN_TOTAL_REVENUE_MINOR}::text
                );
            END IF;

            sufficient := (array_length(found_reasons, 1) IS NULL);
            reasons := found_reasons;
            observed_channels := n_channels;
            observed_conversions := n_conversions::integer;
            observed_revenue_minor := n_revenue;
            RETURN NEXT;
        END;
        $BODY$;
        """
    )

    # ------------------------------------------------------------------
    # 4. The deterministic solver, recomputed by the database.
    # ------------------------------------------------------------------
    # A PL/pgSQL twin of app.simulation.solver.allocate_budget: integer
    # largest-remainder over verified revenue, weights in basis points, ties
    # broken by channel id. Numerators are `numeric` because Python integers are
    # unbounded and `revenue * budget` overflows bigint at design-partner
    # magnitudes; every emitted value is back inside bigint because an
    # allocation never exceeds the budget.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b28_recompute_allocation(
            p_channel_evidence jsonb,
            p_total_budget_minor bigint
        )
        RETURNS jsonb
        LANGUAGE plpgsql
        IMMUTABLE
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            ids text[];
            revenues numeric[];
            total_revenue numeric := 0;
            weights bigint[];
            allocations bigint[];
            weight_remainders numeric[];
            remainders numeric[];
            weight_shortfall bigint;
            shortfall bigint;
            idx integer;
            position_index integer;
            n integer;
            lines jsonb := '[]'::jsonb;
        BEGIN
            IF p_total_budget_minor IS NULL OR p_total_budget_minor < 1 THEN
                RAISE EXCEPTION 'b28_solver_budget_not_positive'
                    USING ERRCODE = '22023';
            END IF;

            SELECT array_agg(channel_id ORDER BY channel_id COLLATE "C"),
                   array_agg(revenue ORDER BY channel_id COLLATE "C")
              INTO ids, revenues
              FROM (
                    SELECT elem ->> 'channel_id' AS channel_id,
                           (elem ->> 'verified_revenue_minor')::numeric AS revenue
                      FROM jsonb_array_elements(p_channel_evidence) AS elem
                   ) AS ordered;

            n := COALESCE(array_length(ids, 1), 0);
            IF n = 0 THEN
                RAISE EXCEPTION 'b28_solver_channels_required'
                    USING ERRCODE = '22023';
            END IF;

            FOR idx IN 1 .. n LOOP
                total_revenue := total_revenue + revenues[idx];
            END LOOP;
            IF total_revenue <= 0 THEN
                RAISE EXCEPTION 'b28_solver_no_positive_revenue_evidence'
                    USING ERRCODE = '22023';
            END IF;

            weights := ARRAY[]::bigint[];
            weight_remainders := ARRAY[]::numeric[];
            allocations := ARRAY[]::bigint[];
            remainders := ARRAY[]::numeric[];
            FOR idx IN 1 .. n LOOP
                weights := weights
                    || div(revenues[idx] * {_BASIS_POINTS}, total_revenue)::bigint;
                weight_remainders := weight_remainders
                    || mod(revenues[idx] * {_BASIS_POINTS}, total_revenue);
                allocations := allocations
                    || div(
                         revenues[idx] * p_total_budget_minor, total_revenue
                       )::bigint;
                remainders := remainders
                    || mod(revenues[idx] * p_total_budget_minor, total_revenue);
            END LOOP;

            weight_shortfall := {_BASIS_POINTS};
            FOR idx IN 1 .. n LOOP
                weight_shortfall := weight_shortfall - weights[idx];
            END LOOP;
            IF weight_shortfall > 0 THEN
                FOR position_index IN
                    SELECT t.ord
                      FROM unnest(weight_remainders, ids)
                           WITH ORDINALITY AS t(remainder, channel_id, ord)
                     ORDER BY t.remainder DESC, t.channel_id COLLATE "C" ASC
                     LIMIT weight_shortfall
                LOOP
                    weights[position_index] := weights[position_index] + 1;
                END LOOP;
            END IF;

            shortfall := p_total_budget_minor;
            FOR idx IN 1 .. n LOOP
                shortfall := shortfall - allocations[idx];
            END LOOP;
            IF shortfall < 0 THEN
                RAISE EXCEPTION 'b28_solver_allocation_overflow'
                    USING ERRCODE = '22023';
            END IF;
            IF shortfall > 0 THEN
                FOR position_index IN
                    SELECT t.ord
                      FROM unnest(remainders, ids)
                           WITH ORDINALITY AS t(remainder, channel_id, ord)
                     ORDER BY t.remainder DESC, t.channel_id COLLATE "C" ASC
                     LIMIT shortfall
                LOOP
                    allocations[position_index] :=
                        allocations[position_index] + 1;
                END LOOP;
            END IF;

            FOR idx IN 1 .. n LOOP
                lines := lines || jsonb_build_array(
                    jsonb_build_object(
                        'channel_id', ids[idx],
                        'allocation_minor', allocations[idx],
                        'weight_basis_points', weights[idx]
                    )
                );
            END LOOP;
            RETURN lines;
        END;
        $BODY$;
        """
    )

    # ------------------------------------------------------------------
    # 5. The request consequence guard, rewritten around derivation.
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b28_enforce_request_consequence()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            issuance_semantic_truth_hash text;
            issuance_policy_state text;
            admissible text[] := {_ADMISSIBLE_POLICY_STATES};
            principal_is_trusted boolean;
            table_owner_oid oid;
            credential_tenant uuid;
            credential_client uuid;
            credential_status text;
            credential_revoked timestamptz;
            credential_expires timestamptz;
            client_tenant uuid;
            client_status text;
            expected_snapshot text;
            elem jsonb;
            seen_ids text[] := ARRAY[]::text[];
            adjudication record;
        BEGIN
            SELECT rolsuper INTO principal_is_trusted
              FROM pg_catalog.pg_roles WHERE rolname = session_user;
            SELECT relowner INTO table_owner_oid
              FROM pg_catalog.pg_class WHERE oid = TG_RELID;
            principal_is_trusted := COALESCE(principal_is_trusted, false)
                OR pg_catalog.pg_has_role(session_user, table_owner_oid, 'USAGE');

            -- Authority. A principal that can drop this trigger gains nothing
            -- from being refused by it, so the owner and superuser skip the
            -- principal check only; every derivation check below runs for them.
            IF NOT principal_is_trusted THEN
                IF session_user <> '{_REQUEST_PRINCIPAL}' THEN
                    RAISE EXCEPTION
                        'b28_request_principal_not_authorized:%', session_user
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            IF NEW.request_authority_principal IS DISTINCT FROM session_user THEN
                RAISE EXCEPTION
                    'b28_request_authority_principal_not_derived:% vs %',
                    NEW.request_authority_principal, session_user
                    USING ERRCODE = '42501';
            END IF;

            -- Durable source Trust, unchanged from Corrective IV.
            SELECT semantic_truth_hash, policy_state
              INTO issuance_semantic_truth_hash, issuance_policy_state
              FROM public.trust_envelope_issuance_log
             WHERE tenant_id = NEW.tenant_id
               AND envelope_hash = NEW.source_issuance_envelope_hash;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'b28_request_requires_durable_issuance:%',
                    NEW.source_issuance_envelope_hash
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.source_semantic_truth_hash
                   IS DISTINCT FROM issuance_semantic_truth_hash
            THEN
                RAISE EXCEPTION
                    'b28_request_source_trust_mismatch:%',
                    NEW.source_issuance_envelope_hash
                    USING ERRCODE = '42501';
            END IF;
            -- Written as a total predicate. `NULL = ANY(...)` is UNKNOWN, and
            -- `IF UNKNOWN` takes the ELSE branch, so a NULL policy state would
            -- otherwise be admitted by a guard that reads as though it refuses
            -- it (Directive V H-RC-V-06).
            IF issuance_policy_state IS NULL
               OR NOT (issuance_policy_state = ANY(admissible))
            THEN
                RAISE EXCEPTION
                    'b28_request_policy_forbids:%',
                    COALESCE(issuance_policy_state, 'null')
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.sufficiency_policy_version
                   <> '{_SUFFICIENCY_POLICY_VERSION}'
            THEN
                RAISE EXCEPTION
                    'b28_request_sufficiency_policy_unknown:%',
                    NEW.sufficiency_policy_version
                    USING ERRCODE = '42501';
            END IF;

            -- Corrective V, H-V-02. The requester is an authenticated principal
            -- that really exists and is really live, not a string.
            SELECT tenant_id, agent_client_id, status, revoked_at, expires_at
              INTO credential_tenant, credential_client, credential_status,
                   credential_revoked, credential_expires
              FROM public.agent_service_credentials
             WHERE id = NEW.requested_by_credential_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'b28_request_requester_credential_unknown:%',
                    NEW.requested_by_credential_id
                    USING ERRCODE = '42501';
            END IF;
            IF credential_tenant IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION
                    'b28_request_requester_tenant_mismatch'
                    USING ERRCODE = '42501';
            END IF;
            IF credential_client
                   IS DISTINCT FROM NEW.requested_by_agent_client_id
            THEN
                RAISE EXCEPTION
                    'b28_request_requester_client_mismatch'
                    USING ERRCODE = '42501';
            END IF;
            IF credential_status IS DISTINCT FROM 'active'
               OR credential_revoked IS NOT NULL
               OR (credential_expires IS NOT NULL AND credential_expires <= now())
            THEN
                RAISE EXCEPTION
                    'b28_request_requester_credential_not_live:%',
                    COALESCE(credential_status, 'null')
                    USING ERRCODE = '42501';
            END IF;
            SELECT tenant_id, status INTO client_tenant, client_status
              FROM public.agent_clients
             WHERE id = NEW.requested_by_agent_client_id;
            IF NOT FOUND
               OR client_tenant IS DISTINCT FROM NEW.tenant_id
               OR client_status IS DISTINCT FROM 'active'
            THEN
                RAISE EXCEPTION
                    'b28_request_requester_client_not_live:%',
                    NEW.requested_by_agent_client_id
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.requested_by IS DISTINCT FROM
               ('agent_client:' || NEW.requested_by_agent_client_id::text)
            THEN
                RAISE EXCEPTION
                    'b28_request_requested_by_not_derived:%', NEW.requested_by
                    USING ERRCODE = '42501';
            END IF;

            -- Corrective V, H-V-06. The retained evidence is well formed, so the
            -- canonical material is a total function of the stored row.
            IF NEW.solver_profile <> '{_SOLVER_PROFILE}' THEN
                RAISE EXCEPTION
                    'b28_request_solver_profile_ungoverned:%', NEW.solver_profile
                    USING ERRCODE = '42501';
            END IF;
            FOR elem IN SELECT * FROM jsonb_array_elements(NEW.channel_evidence)
            LOOP
                IF jsonb_typeof(elem) <> 'object'
                   OR (SELECT count(*) FROM jsonb_object_keys(elem)) <> 3
                   OR NOT (elem ? 'channel_id')
                   OR NOT (elem ? 'verified_revenue_minor')
                   OR NOT (elem ? 'conversion_count')
                THEN
                    RAISE EXCEPTION
                        'b28_request_channel_evidence_shape:%', elem
                        USING ERRCODE = '42501';
                END IF;
                IF jsonb_typeof(elem -> 'channel_id') <> 'string'
                   OR (elem ->> 'channel_id') !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{{0,63}}$'
                THEN
                    RAISE EXCEPTION
                        'b28_request_channel_id_shape:%', elem ->> 'channel_id'
                        USING ERRCODE = '42501';
                END IF;
                IF jsonb_typeof(elem -> 'verified_revenue_minor') <> 'number'
                   OR (elem ->> 'verified_revenue_minor') !~ '^[0-9]+$'
                   OR jsonb_typeof(elem -> 'conversion_count') <> 'number'
                   OR (elem ->> 'conversion_count') !~ '^[0-9]+$'
                THEN
                    RAISE EXCEPTION
                        'b28_request_channel_evidence_not_integer:%', elem
                        USING ERRCODE = '42501';
                END IF;
                IF (elem ->> 'channel_id') = ANY(seen_ids) THEN
                    RAISE EXCEPTION
                        'b28_request_channel_ids_not_unique:%',
                        elem ->> 'channel_id'
                        USING ERRCODE = '42501';
                END IF;
                seen_ids := seen_ids || (elem ->> 'channel_id');
            END LOOP;

            -- Corrective V, H-V-06. The snapshot hash is the hash of the row's
            -- own inputs or it is not admissible.
            expected_snapshot := public.b28_input_snapshot_hash(
                NEW.source_envelope_id,
                NEW.source_semantic_truth_hash,
                NEW.total_budget_minor,
                NEW.currency,
                NEW.channel_evidence
            );
            IF NEW.input_snapshot_hash IS DISTINCT FROM expected_snapshot THEN
                RAISE EXCEPTION
                    'b28_request_input_snapshot_not_derived:% vs %',
                    NEW.input_snapshot_hash, expected_snapshot
                    USING ERRCODE = '42501';
            END IF;

            -- Corrective V, H-V-05. Sufficiency is adjudicated here, durably.
            SELECT * INTO adjudication
              FROM public.b28_adjudicate_sufficiency(NEW.channel_evidence);
            IF NEW.sufficiency_verdict IS DISTINCT FROM adjudication.sufficient
               OR NEW.sufficiency_reasons IS DISTINCT FROM adjudication.reasons
               OR NEW.observed_channels
                      IS DISTINCT FROM adjudication.observed_channels
               OR NEW.observed_conversions
                      IS DISTINCT FROM adjudication.observed_conversions
               OR NEW.observed_revenue_minor
                      IS DISTINCT FROM adjudication.observed_revenue_minor
            THEN
                RAISE EXCEPTION
                    'b28_request_sufficiency_not_derived:% vs %',
                    NEW.sufficiency_verdict, adjudication.sufficient
                    USING ERRCODE = '42501';
            END IF;

            RETURN NEW;
        END;
        $BODY$;
        """
    )

    # ------------------------------------------------------------------
    # 6. The result consequence guard, rewritten around recomputation.
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b28_enforce_result_consequence()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            request_row public.b28_simulation_requests%ROWTYPE;
            issuance_policy_state text;
            derived_authority text;
            recomputed jsonb;
            principal_is_trusted boolean;
            table_owner_oid oid;
        BEGIN
            SELECT rolsuper INTO principal_is_trusted
              FROM pg_catalog.pg_roles WHERE rolname = session_user;
            SELECT relowner INTO table_owner_oid
              FROM pg_catalog.pg_class WHERE oid = TG_RELID;
            principal_is_trusted := COALESCE(principal_is_trusted, false)
                OR pg_catalog.pg_has_role(session_user, table_owner_oid, 'USAGE');

            IF NOT principal_is_trusted THEN
                IF session_user <> '{_SOLVER_PRINCIPAL}' THEN
                    RAISE EXCEPTION
                        'b28_result_principal_not_authorized:%', session_user
                        USING ERRCODE = '42501';
                END IF;
            END IF;

            SELECT * INTO request_row
              FROM public.b28_simulation_requests
             WHERE id = NEW.request_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'b28_result_requires_explicit_request:%', NEW.request_id
                    USING ERRCODE = '42501';
            END IF;
            IF request_row.tenant_id IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION
                    'b28_result_tenant_mismatch' USING ERRCODE = '42501';
            END IF;
            IF NEW.source_envelope_id
                   IS DISTINCT FROM request_row.source_envelope_id
               OR NEW.source_semantic_truth_hash
                   IS DISTINCT FROM request_row.source_semantic_truth_hash
               OR NEW.input_snapshot_hash
                   IS DISTINCT FROM request_row.input_snapshot_hash
               OR NEW.total_budget_minor
                   IS DISTINCT FROM request_row.total_budget_minor
               OR NEW.currency IS DISTINCT FROM request_row.currency
            THEN
                RAISE EXCEPTION
                    'b28_result_disagrees_with_request:%', NEW.request_id
                    USING ERRCODE = '42501';
            END IF;
            IF jsonb_array_length(NEW.allocations)
                   IS DISTINCT FROM request_row.channel_count
            THEN
                RAISE EXCEPTION
                    'b28_result_channel_count_disagrees:% vs %',
                    jsonb_array_length(NEW.allocations),
                    request_row.channel_count
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.solver_profile <> '{_SOLVER_PROFILE}'
               OR NEW.solver_profile IS DISTINCT FROM request_row.solver_profile
            THEN
                RAISE EXCEPTION
                    'b28_result_solver_profile_ungoverned:%', NEW.solver_profile
                    USING ERRCODE = '42501';
            END IF;

            -- Corrective V, H-V-05. Sufficiency is a durable precondition of the
            -- consequence, not a decision the writer reports having made.
            IF NOT request_row.sufficiency_verdict THEN
                RAISE EXCEPTION
                    'b28_result_request_insufficient:%',
                    array_to_string(request_row.sufficiency_reasons, ';')
                    USING ERRCODE = '42501';
            END IF;

            -- Corrective V, H-V-04. The allocation is not compared to the
            -- request; it is recomputed from it. `solver_invocations` stops
            -- being evidence and becomes a shape: a lawful admission runs the
            -- deterministic solver exactly once.
            IF NEW.solver_invocations IS DISTINCT FROM 1 THEN
                RAISE EXCEPTION
                    'b28_result_solver_invocations_not_one:%',
                    NEW.solver_invocations
                    USING ERRCODE = '42501';
            END IF;
            recomputed := public.b28_recompute_allocation(
                request_row.channel_evidence,
                request_row.total_budget_minor
            );
            IF NEW.allocations IS DISTINCT FROM recomputed THEN
                RAISE EXCEPTION
                    'b28_result_not_solver_consequence:% vs %',
                    NEW.allocations::text, recomputed::text
                    USING ERRCODE = '42501';
            END IF;

            SELECT policy_state INTO issuance_policy_state
              FROM public.trust_envelope_issuance_log
             WHERE tenant_id = NEW.tenant_id
               AND envelope_hash = request_row.source_issuance_envelope_hash;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'b28_result_requires_durable_issuance:%',
                    request_row.source_issuance_envelope_hash
                    USING ERRCODE = '42501';
            END IF;
            derived_authority := CASE
                WHEN issuance_policy_state IN (
                    'blocked', 'read_only', 'simulation_only', 'proposal_required'
                ) THEN issuance_policy_state
                ELSE 'proposal_required'
            END;
            IF NEW.action_authority IS DISTINCT FROM derived_authority THEN
                RAISE EXCEPTION
                    'b28_result_action_authority_not_derived:% vs %',
                    NEW.action_authority, derived_authority
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $BODY$;
        """
    )

    # ------------------------------------------------------------------
    # 7. The proposal guard gains the same principal separation.
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b28_enforce_proposal_consequence()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            result_tenant_id uuid;
            result_envelope_id text;
            result_action_authority text;
            result_allocations jsonb;
            principal_is_trusted boolean;
            table_owner_oid oid;
        BEGIN
            SELECT rolsuper INTO principal_is_trusted
              FROM pg_catalog.pg_roles WHERE rolname = session_user;
            SELECT relowner INTO table_owner_oid
              FROM pg_catalog.pg_class WHERE oid = TG_RELID;
            principal_is_trusted := COALESCE(principal_is_trusted, false)
                OR pg_catalog.pg_has_role(session_user, table_owner_oid, 'USAGE');

            IF NOT principal_is_trusted THEN
                IF session_user <> '{_SOLVER_PRINCIPAL}' THEN
                    RAISE EXCEPTION
                        'b28_proposal_principal_not_authorized:%', session_user
                        USING ERRCODE = '42501';
                END IF;
            END IF;

            SELECT tenant_id, source_envelope_id, action_authority, allocations
              INTO result_tenant_id, result_envelope_id,
                   result_action_authority, result_allocations
              FROM public.b28_simulation_results
             WHERE id = NEW.result_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'b28_proposal_requires_simulation_result:%', NEW.result_id
                    USING ERRCODE = '42501';
            END IF;
            IF result_tenant_id IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION
                    'b28_proposal_tenant_mismatch' USING ERRCODE = '42501';
            END IF;
            IF NEW.source_envelope_id IS DISTINCT FROM result_envelope_id
               OR NEW.action_authority IS DISTINCT FROM result_action_authority
               OR NEW.allocations IS DISTINCT FROM result_allocations
            THEN
                RAISE EXCEPTION
                    'b28_proposal_disagrees_with_result:%', NEW.result_id
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $BODY$;
        """
    )

    # ------------------------------------------------------------------
    # 7b. Reading the construction revision without reading the metadata.
    # ------------------------------------------------------------------
    # Exit Gate 13's runtime half asks one question at the readiness boundary:
    # does this database carry a revision the repository declares? The obvious
    # implementation -- `SELECT version_num FROM public.alembic_version` as the
    # runtime principal -- cannot work, and should not: the baseline revision
    # deliberately revokes runtime access to the migration metadata, and CI
    # re-asserts that revoke. A readiness check that needed the grant back would
    # be trading a real least-privilege property for a diagnostic.
    #
    # A SECURITY DEFINER function owned by the migration principal answers the
    # question without granting the table. It exposes exactly the revision
    # identifiers -- values that already live in this repository's source -- takes
    # no arguments, so there is no injection surface, and pins its search_path.
    # EXECUTE is revoked from PUBLIC and granted only to the principals that
    # serve readiness.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.skeldir_database_construction_revisions()
        RETURNS SETOF text
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $BODY$
            SELECT version_num FROM public.alembic_version
        $BODY$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.skeldir_database_construction_revisions()"
        " FROM PUBLIC"
    )
    for role in ("app_user", "app_worker", "app_ro", "app_rw"):
        _if_role_exists(
            role,
            "GRANT EXECUTE ON FUNCTION"
            " public.skeldir_database_construction_revisions()"
            f" TO {role}",
        )

    # ------------------------------------------------------------------
    # 8. Authority follows causal responsibility.
    # ------------------------------------------------------------------
    # The generic API principal loses the ability to create a consequence it did
    # not cause. It keeps SELECT: reading a simulation is a read.
    for relation in (
        "b28_simulation_requests",
        "b28_simulation_results",
        "b28_proposals",
    ):
        op.execute(f"REVOKE ALL ON TABLE public.{relation} FROM PUBLIC")
        _if_role_exists(
            "app_user",
            f"REVOKE ALL ON TABLE public.{relation} FROM app_user;"
            f" GRANT SELECT ON TABLE public.{relation} TO app_user",
        )
        _if_role_exists(
            "app_rw", f"REVOKE ALL ON TABLE public.{relation} FROM app_rw"
        )
        _if_role_exists(
            "app_ro",
            f"REVOKE ALL ON TABLE public.{relation} FROM app_ro;"
            f" GRANT SELECT ON TABLE public.{relation} TO app_ro",
        )

    _if_role_exists(
        _REQUEST_PRINCIPAL,
        f"GRANT USAGE ON SCHEMA public TO {_REQUEST_PRINCIPAL};"
        " GRANT SELECT, INSERT ON TABLE public.b28_simulation_requests"
        f" TO {_REQUEST_PRINCIPAL};"
        " GRANT SELECT ON TABLE public.trust_envelope_issuance_log"
        f" TO {_REQUEST_PRINCIPAL};"
        " GRANT SELECT ON TABLE public.agent_service_credentials"
        f" TO {_REQUEST_PRINCIPAL};"
        f" GRANT SELECT ON TABLE public.agent_clients TO {_REQUEST_PRINCIPAL};"
        " GRANT SELECT ON TABLE public.agent_token_revocations"
        f" TO {_REQUEST_PRINCIPAL};"
        f" GRANT SELECT ON TABLE public.tenants TO {_REQUEST_PRINCIPAL}",
    )
    _if_role_exists(
        _SOLVER_PRINCIPAL,
        f"GRANT USAGE ON SCHEMA public TO {_SOLVER_PRINCIPAL};"
        " GRANT SELECT, INSERT ON TABLE public.b28_simulation_results"
        f" TO {_SOLVER_PRINCIPAL};"
        f" GRANT SELECT, INSERT ON TABLE public.b28_proposals TO {_SOLVER_PRINCIPAL};"
        " GRANT SELECT ON TABLE public.b28_simulation_requests"
        f" TO {_SOLVER_PRINCIPAL};"
        " GRANT SELECT ON TABLE public.trust_envelope_issuance_log"
        f" TO {_SOLVER_PRINCIPAL};"
        f" GRANT SELECT ON TABLE public.tenants TO {_SOLVER_PRINCIPAL}",
    )
    # Neither causal authority may reach the other's relation, nor the B2.7
    # surface, nor anything the generic runtime graph carries.
    _if_role_exists(
        _REQUEST_PRINCIPAL,
        "REVOKE ALL ON TABLE public.b28_simulation_results"
        f" FROM {_REQUEST_PRINCIPAL};"
        f" REVOKE ALL ON TABLE public.b28_proposals FROM {_REQUEST_PRINCIPAL};"
        " REVOKE ALL ON TABLE public.b27_explanation_materializations"
        f" FROM {_REQUEST_PRINCIPAL}",
    )
    _if_role_exists(
        _SOLVER_PRINCIPAL,
        "REVOKE INSERT, UPDATE, DELETE ON TABLE public.b28_simulation_requests"
        f" FROM {_SOLVER_PRINCIPAL};"
        " REVOKE ALL ON TABLE public.b27_explanation_materializations"
        f" FROM {_SOLVER_PRINCIPAL}",
    )

    # The derivation helpers are pure functions that read no relation, so PUBLIC
    # EXECUTE grants no authority; every principal that can insert must be able
    # to call them, and an auditor holding only SELECT must be able to
    # independently recompute.
    for function_signature in (
        "public.b28_canonical_input_material(text, text, bigint, text, jsonb)",
        "public.b28_input_snapshot_hash(text, text, bigint, text, jsonb)",
        "public.b28_adjudicate_sufficiency(jsonb)",
        "public.b28_recompute_allocation(jsonb, bigint)",
    ):
        op.execute(f"GRANT EXECUTE ON FUNCTION {function_signature} TO PUBLIC")


def downgrade() -> None:
    """Restore the ``202609051200`` contract exactly.

    Reversibility is a property of the chain, not an endorsement of the state it
    returns to: the C16 lane migrates to head and then walks back to
    ``202608291200`` as the non-superuser owner, which is how the repository
    proves its migrations are reversible at all. A revision that refused to
    downgrade would break that proof rather than protect anything -- the safety
    here is in the upgrade being applied, and a deployment that walks back to
    ``202609051200`` has chosen that revision's contract deliberately.

    The three consequence guards are re-issued with their ``202609051200``
    bodies. They are restated rather than imported because a downgrade must
    describe the state it produces, and a body that drifted in the predecessor
    file would otherwise silently change what this downgrade restores.
    """

    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.skeldir_database_construction_revisions()"
    )

    _if_role_exists(
        _REQUEST_PRINCIPAL,
        "REVOKE ALL ON TABLE public.b28_simulation_requests"
        f" FROM {_REQUEST_PRINCIPAL};"
        " REVOKE ALL ON TABLE public.trust_envelope_issuance_log"
        f" FROM {_REQUEST_PRINCIPAL};"
        " REVOKE ALL ON TABLE public.agent_service_credentials"
        f" FROM {_REQUEST_PRINCIPAL};"
        f" REVOKE ALL ON TABLE public.agent_clients FROM {_REQUEST_PRINCIPAL};"
        " REVOKE ALL ON TABLE public.agent_token_revocations"
        f" FROM {_REQUEST_PRINCIPAL};"
        f" REVOKE ALL ON TABLE public.tenants FROM {_REQUEST_PRINCIPAL}",
    )
    _if_role_exists(
        _SOLVER_PRINCIPAL,
        "REVOKE ALL ON TABLE public.b28_simulation_results"
        f" FROM {_SOLVER_PRINCIPAL};"
        f" REVOKE ALL ON TABLE public.b28_proposals FROM {_SOLVER_PRINCIPAL};"
        " REVOKE ALL ON TABLE public.b28_simulation_requests"
        f" FROM {_SOLVER_PRINCIPAL};"
        " REVOKE ALL ON TABLE public.trust_envelope_issuance_log"
        f" FROM {_SOLVER_PRINCIPAL};"
        f" REVOKE ALL ON TABLE public.tenants FROM {_SOLVER_PRINCIPAL}",
    )
    for relation in (
        "b28_simulation_requests",
        "b28_simulation_results",
        "b28_proposals",
    ):
        _if_role_exists(
            "app_user",
            f"GRANT SELECT, INSERT ON TABLE public.{relation} TO app_user",
        )

    op.execute("DROP INDEX IF EXISTS public.idx_b28_request_requester")
    # Each removal is stated on its own line so the migration safety validator
    # adjudicates it individually. Every one of these objects is created by this
    # revision's own `upgrade()`, so a downgrade removes exactly what it added
    # and destroys nothing the predecessor contract knows about.
    for constraint in (
        "ck_b28_request_channel_evidence",
        "ck_b28_request_solver_profile",
        "ck_b28_request_requested_by_derived",
        "ck_b28_request_observed_nonnegative",
    ):
        op.execute(
            "ALTER TABLE public.b28_simulation_requests"
            f" DROP CONSTRAINT IF EXISTS {constraint}"  # CI:DESTRUCTIVE_OK - undoes this revision
        )
    for column in (
        "requested_by_agent_client_id",
        "requested_by_credential_id",
        "request_authority_principal",
        "channel_evidence",
        "solver_profile",
        "sufficiency_verdict",
        "sufficiency_reasons",
        "observed_channels",
        "observed_conversions",
        "observed_revenue_minor",
    ):
        op.execute(
            "ALTER TABLE public.b28_simulation_requests"
            f" DROP COLUMN IF EXISTS {column}"  # CI:DESTRUCTIVE_OK - undoes this revision
        )

    # The 202609051200 request guard.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b28_enforce_request_consequence()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            issuance_semantic_truth_hash text;
            issuance_policy_state text;
            admissible text[] := {_ADMISSIBLE_POLICY_STATES};
        BEGIN
            SELECT semantic_truth_hash, policy_state
              INTO issuance_semantic_truth_hash, issuance_policy_state
              FROM public.trust_envelope_issuance_log
             WHERE tenant_id = NEW.tenant_id
               AND envelope_hash = NEW.source_issuance_envelope_hash;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'b28_request_requires_durable_issuance:%',
                    NEW.source_issuance_envelope_hash
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.source_semantic_truth_hash
                   IS DISTINCT FROM issuance_semantic_truth_hash
            THEN
                RAISE EXCEPTION
                    'b28_request_source_trust_mismatch:%',
                    NEW.source_issuance_envelope_hash
                    USING ERRCODE = '42501';
            END IF;
            IF NOT (issuance_policy_state = ANY(admissible)) THEN
                RAISE EXCEPTION
                    'b28_request_policy_forbids:%', issuance_policy_state
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.sufficiency_policy_version
                   <> '{_SUFFICIENCY_POLICY_VERSION}'
            THEN
                RAISE EXCEPTION
                    'b28_request_sufficiency_policy_unknown:%',
                    NEW.sufficiency_policy_version
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $BODY$;
        """
    )

    # The 202609051200 result guard.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b28_enforce_result_consequence()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            request_tenant_id uuid;
            request_envelope_id text;
            request_semantic_truth_hash text;
            request_snapshot_hash text;
            request_budget bigint;
            request_currency text;
            request_channel_count integer;
            request_source_envelope_hash text;
            issuance_policy_state text;
            derived_authority text;
        BEGIN
            SELECT tenant_id, source_envelope_id, source_semantic_truth_hash,
                   input_snapshot_hash, total_budget_minor, currency,
                   channel_count, source_issuance_envelope_hash
              INTO request_tenant_id, request_envelope_id,
                   request_semantic_truth_hash, request_snapshot_hash,
                   request_budget, request_currency, request_channel_count,
                   request_source_envelope_hash
              FROM public.b28_simulation_requests
             WHERE id = NEW.request_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'b28_result_requires_explicit_request:%', NEW.request_id
                    USING ERRCODE = '42501';
            END IF;
            IF request_tenant_id IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION
                    'b28_result_tenant_mismatch' USING ERRCODE = '42501';
            END IF;
            IF NEW.source_envelope_id IS DISTINCT FROM request_envelope_id
               OR NEW.source_semantic_truth_hash
                   IS DISTINCT FROM request_semantic_truth_hash
               OR NEW.input_snapshot_hash IS DISTINCT FROM request_snapshot_hash
               OR NEW.total_budget_minor IS DISTINCT FROM request_budget
               OR NEW.currency IS DISTINCT FROM request_currency
            THEN
                RAISE EXCEPTION
                    'b28_result_disagrees_with_request:%', NEW.request_id
                    USING ERRCODE = '42501';
            END IF;
            IF jsonb_array_length(NEW.allocations)
                   IS DISTINCT FROM request_channel_count
            THEN
                RAISE EXCEPTION
                    'b28_result_channel_count_disagrees:% vs %',
                    jsonb_array_length(NEW.allocations), request_channel_count
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.solver_profile <> '{_SOLVER_PROFILE}' THEN
                RAISE EXCEPTION
                    'b28_result_solver_profile_ungoverned:%', NEW.solver_profile
                    USING ERRCODE = '42501';
            END IF;

            SELECT policy_state INTO issuance_policy_state
              FROM public.trust_envelope_issuance_log
             WHERE tenant_id = NEW.tenant_id
               AND envelope_hash = request_source_envelope_hash;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'b28_result_requires_durable_issuance:%',
                    request_source_envelope_hash
                    USING ERRCODE = '42501';
            END IF;
            derived_authority := CASE
                WHEN issuance_policy_state IN (
                    'blocked', 'read_only', 'simulation_only', 'proposal_required'
                ) THEN issuance_policy_state
                ELSE 'proposal_required'
            END;
            IF NEW.action_authority IS DISTINCT FROM derived_authority THEN
                RAISE EXCEPTION
                    'b28_result_action_authority_not_derived:% vs %',
                    NEW.action_authority, derived_authority
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $BODY$;
        """
    )

    # The 202609051200 proposal guard.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b28_enforce_proposal_consequence()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            result_tenant_id uuid;
            result_envelope_id text;
            result_action_authority text;
            result_allocations jsonb;
        BEGIN
            SELECT tenant_id, source_envelope_id, action_authority, allocations
              INTO result_tenant_id, result_envelope_id,
                   result_action_authority, result_allocations
              FROM public.b28_simulation_results
             WHERE id = NEW.result_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'b28_proposal_requires_simulation_result:%', NEW.result_id
                    USING ERRCODE = '42501';
            END IF;
            IF result_tenant_id IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION
                    'b28_proposal_tenant_mismatch' USING ERRCODE = '42501';
            END IF;
            IF NEW.source_envelope_id IS DISTINCT FROM result_envelope_id
               OR NEW.action_authority IS DISTINCT FROM result_action_authority
               OR NEW.allocations IS DISTINCT FROM result_allocations
            THEN
                RAISE EXCEPTION
                    'b28_proposal_disagrees_with_result:%', NEW.result_id
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $BODY$;
        """
    )

    for function_signature in (
        "public.b28_recompute_allocation(jsonb, bigint)",
        "public.b28_adjudicate_sufficiency(jsonb)",
        "public.b28_input_snapshot_hash(text, text, bigint, text, jsonb)",
        "public.b28_canonical_input_material(text, text, bigint, text, jsonb)",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {function_signature}")
