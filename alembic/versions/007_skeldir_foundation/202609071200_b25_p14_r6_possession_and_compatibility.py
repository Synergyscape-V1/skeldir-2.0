"""B2.5-P14 Corrective VI: prove request possession, state solver semantics honestly.

Revision ID: 202609071200
Revises: 202609061200

Four propositions were physically reproduced as false on the entering
protected-main tree (``d4ccb816``, tree ``b3bcfbce``, head ``202609061200``) on a
fresh PostgreSQL 15 provisioned by the repository's own role script, using the
real least-privilege logins::

    GATE_F_tokenless_request        ALLOWED  request_id=c89ca01d-...
    GATE_G_dsn_direct_connect       ALLOWED  session_user=app_b28_requester
                                             caller=__main__
    GATE_K_no_solver_exact_alloc    ALLOWED  result_id=10c30bd2-...
                                             solver_invocations=1, no solver call
    GATE_P_stale_known_revision     ACCEPTED 202609051200 as migration_owner
                                             ACCEPTED 202609051200 as app_user

and one structural observation::

    every b28_* column comment                 NULL

----------------------------------------------------------------------------
Root cause
----------------------------------------------------------------------------

Corrective V moved every *value* in B2.8 from assertion to derivation. It left
two *events* still self-asserted, and one compatibility predicate that measures
familiarity rather than fitness.

**A request proved a writer, not a requester.** ``b28_enforce_request_consequence``
establishes that ``requested_by_credential_id`` names a live credential row in
the right tenant, that its client is live, and that ``requested_by`` is the
derivation of the client id. Every one of those facts is readable from the
credential *row*. None of them requires the writer to hold the credential's
plaintext secret. The application half authenticates honestly --
``authenticate_simulation_requester`` does a prefix lookup and an
``hmac.compare_digest`` over the presented token -- but its conclusion left no
durable trace, so the two universes Directive VI names H-DU-VI-01 produced
byte-identical rows::

    present token -> verify -> insert request        (library path)
    know credential row id  -> insert request        (dedicated-role SQL)

The durable layer is the layer the phase claims as its trust root, and at that
layer the possession proposition was simply absent.

**A result asserted an execution count it could not witness.**
``solver_invocations integer NOT NULL`` reads as *the governed solver ran this
many times*. Corrective V narrowed the claim in prose -- what the database
actually proves is extensional: the persisted allocation IS the value of
``b28_recompute_allocation`` over the request's own retained evidence -- but the
persisted vocabulary was never changed to say so, and no column carried a
comment at all. An independently recomputed allocation inserted with
``solver_invocations = 1`` was therefore accepted, and the artifact claimed an
event nobody observed.

**Production readiness confused a known revision with a compatible one.** That
third defect is not a schema property and is repaired in
``app.core.construction_authority`` rather than here; this revision's part in it
is to be the head that contract pins, and to keep the ``SECURITY DEFINER``
revision reader that lets a runtime principal answer the question without
holding ``alembic_version``.

----------------------------------------------------------------------------
The repair
----------------------------------------------------------------------------

**1. Possession becomes a durable, single-use, request-bound witness.**
``b28_request_authentications`` records one fact: *at this instant, a caller
proved possession of this credential's plaintext secret, for this exact request*.
No principal holds INSERT on it. The only writer is
``b28_authenticate_request_possession``, a ``SECURITY DEFINER`` function that
takes the plaintext token, recomputes ``sha256(token)`` and compares it to the
stored ``token_hash``, re-checks revocation, status, expiry, client liveness and
tenant, derives the request binding itself, and returns the witness id. The
caller cannot name the client or the credential: both are read out of the row
the secret resolves to.

``b28_simulation_requests.request_authentication_id`` is ``NOT NULL`` with a
``UNIQUE`` index, so:

* a request without a witness is not representable -- no grant, no trigger and
  no policy is involved, the column simply cannot be filled;
* a witness minted for one request cannot authorise another -- the guard
  re-derives the binding from the row and requires equality;
* a witness cannot be replayed -- the unique index refuses the second request.

The structural half and the guard half are deliberately redundant, in the
Corrective-V idiom: severing the trigger still leaves possession required, and
dropping the column is a schema change the compatibility contract refuses to
serve.

**2. The persisted solver contract states the proposition the system proves.**
``solver_invocations`` is dropped. ``solver_consequence_kind`` replaces it, is
``CHECK``-pinned to ``governed_deterministic_consequence``, and carries a comment
saying exactly what that means and what it does not: the row is the value of the
governed deterministic function over the admitted input, verified by
``b28_recompute_allocation`` inside this trigger, and it is *not* a claim that
any particular process executed. Directive VI §18 Architecture B, chosen because
the product needs the allocation to be right rather than to know which process
computed it -- and because an execution witness produced and verified by the same
authority would be self-certification (Directive V H-RC-V-08).

**3. Every durable B2.8 field is classified.** Directive VI §15 requires each
column to declare which of four things it is, and what physical evidence makes
it true. The classification is a column comment with a machine-checkable prefix,
so ``scripts/ci/assert_b25_p14_field_semantics.py`` refuses an unclassified or
misclassified column at merge time. A schema that says exactly what it can prove
is the whole point of Gate 3.

----------------------------------------------------------------------------
Pre-existing rows
----------------------------------------------------------------------------

Both B2.8 relations gain a ``NOT NULL`` column for which no honest backfill
exists: a request written before this revision has no possession witness, and
inventing one would fabricate the very evidence the revision exists to require.
The upgrade asserts both relations are empty and fails closed. P14 exposes no
HTTP surface and the Corrective-V contract has never been deployed with live
rows, so this is a declared limitation rather than an accident.
"""

from __future__ import annotations

from alembic import op


revision = "202609071200"
down_revision = "202609061200"
branch_labels = None
depends_on = None


# Mirrors app/simulation/solver.py and app/simulation/contract.py. The drift
# test in backend/tests/trust/test_b25_p14_r6_possession_authority.py asserts
# the equality, so a constant that moves in one place and not the other is
# merge-blocking.
_SOLVER_PROFILE = "b25-p14-deterministic-largest-remainder-v1"
_SOLVER_CONSEQUENCE_KIND = "governed_deterministic_consequence"

# Mirrors app/trust/machine_identity.py.
_TOKEN_PREFIX_LENGTH = 8
_TOKEN_HASH_ALGORITHM = "sha256"

# Mirrors app/simulation/requester_identity.py::POSSESSION_WITNESS_TTL_SECONDS.
# A witness is bound to its exact request, so a stale one could only re-authorise
# the identical row the unique index already refuses; the window is defence in
# depth, not the mechanism.
_POSSESSION_WITNESS_TTL_SECONDS = 900

_REQUEST_PRINCIPAL = "app_b28_requester"
_SOLVER_PRINCIPAL = "app_b28_solver"

# Directive VI §15. Four categories, and every durable B2.8 column declares one.
_DERIVED = "DERIVED VALUE"
_EVENT = "OBSERVED EVENT"
_AUTHORITY = "AUTHORITY IDENTITY"
_PROVENANCE = "PROVENANCE REFERENCE"

#: ``relation -> column -> (classification, what physical evidence makes it true)``
FIELD_SEMANTICS: dict[str, dict[str, tuple[str, str]]] = {
    "b28_request_authentications": {
        "id": (_PROVENANCE, "surrogate identity of this possession witness"),
        "tenant_id": (
            _AUTHORITY,
            "the tenant boundary the proven credential belongs to",
        ),
        "agent_client_id": (
            _AUTHORITY,
            "read out of the credential row the presented secret resolved to;"
            " never supplied by the caller",
        ),
        "credential_id": (
            _AUTHORITY,
            "the credential row whose stored token_hash equals sha256 of the"
            " secret the caller presented",
        ),
        "request_binding": (
            _DERIVED,
            "b28_request_authentication_binding over the tenant, request_ref,"
            " source issuance hash and input snapshot hash the caller committed"
            " to",
        ),
        "authenticated_at": (
            _EVENT,
            "the database clock at the instant possession was verified",
        ),
        "authenticated_by_principal": (
            _AUTHORITY,
            "session_user at verification time; SET ROLE cannot change it",
        ),
    },
    "b28_simulation_requests": {
        "id": (_PROVENANCE, "surrogate identity of this durable request"),
        "tenant_id": (_AUTHORITY, "the tenant boundary this request belongs to"),
        "request_ref": (_PROVENANCE, "caller-visible reference, unique per tenant"),
        "requested_by": (
            _AUTHORITY,
            "re-derived by the guard as agent_client: || "
            "requested_by_agent_client_id; never writer-chosen text",
        ),
        "requested_by_agent_client_id": (
            _AUTHORITY,
            "a live agent_clients row, re-checked by the guard and equal to the"
            " client the possession witness resolved to",
        ),
        "requested_by_credential_id": (
            _AUTHORITY,
            "a live agent_service_credentials row whose plaintext secret was"
            " verified by b28_authenticate_request_possession",
        ),
        "request_authority_principal": (
            _AUTHORITY,
            "session_user of the writing session; the guard refuses any other"
            " value",
        ),
        "request_authentication_id": (
            _EVENT,
            "the possession verification that physically occurred: a caller"
            " presented the plaintext secret and the database recomputed its"
            " sha256. Single-use by UNIQUE index and bound to this exact request",
        ),
        "source_envelope_id": (_PROVENANCE, "the source TrustEnvelope identity"),
        "source_semantic_truth_hash": (
            _PROVENANCE,
            "conserved from the source Trust; the guard requires equality with"
            " trust_envelope_issuance_log",
        ),
        "source_issuance_envelope_hash": (
            _PROVENANCE,
            "names the durable issuance record this request is bound to",
        ),
        "input_snapshot_hash": (
            _DERIVED,
            "b28_input_snapshot_hash over this row's own retained inputs; the"
            " guard refuses any other value",
        ),
        "total_budget_minor": (
            _EVENT,
            "the budget the authenticated requester committed to; covered by"
            " input_snapshot_hash and by the possession binding",
        ),
        "currency": (
            _EVENT,
            "the currency the authenticated requester committed to; covered by"
            " input_snapshot_hash and by the possession binding",
        ),
        "channel_count": (
            _DERIVED,
            "jsonb_array_length(channel_evidence), CHECK-enforced",
        ),
        "channel_evidence": (
            _EVENT,
            "the exact governed evidence the requester committed to, retained"
            " verbatim so the admitted input is reconstructible from this row"
            " alone",
        ),
        "solver_profile": (_PROVENANCE, "names the governed deterministic profile"),
        "sufficiency_policy_version": (
            _PROVENANCE,
            "names the governed sufficiency policy",
        ),
        "sufficiency_verdict": (
            _DERIVED,
            "b28_adjudicate_sufficiency over channel_evidence; the guard refuses"
            " any other value",
        ),
        "sufficiency_reasons": (
            _DERIVED,
            "b28_adjudicate_sufficiency over channel_evidence, reason for reason",
        ),
        "observed_channels": (
            _DERIVED,
            "b28_adjudicate_sufficiency over channel_evidence",
        ),
        "observed_conversions": (
            _DERIVED,
            "b28_adjudicate_sufficiency over channel_evidence",
        ),
        "observed_revenue_minor": (
            _DERIVED,
            "b28_adjudicate_sufficiency over channel_evidence",
        ),
        "requested_at": (
            _EVENT,
            "the database clock at the instant the request committed",
        ),
    },
    "b28_simulation_results": {
        "id": (_PROVENANCE, "surrogate identity of this durable result"),
        "tenant_id": (_AUTHORITY, "the tenant boundary this result belongs to"),
        "request_id": (
            _PROVENANCE,
            "the possession-verified request that authorised this consequence",
        ),
        "source_envelope_id": (_PROVENANCE, "conserved from the request"),
        "source_semantic_truth_hash": (_PROVENANCE, "conserved from the request"),
        "projection_profile_hash": (
            _PROVENANCE,
            "names the governed projection profile the source was read through",
        ),
        "input_snapshot_hash": (
            _PROVENANCE,
            "cites the request's derived snapshot; the guard re-derives the"
            " request's own hash so a post-admission input change is"
            " unrepresentable as a consequence",
        ),
        "solver_profile": (_PROVENANCE, "names the governed deterministic profile"),
        "solver_consequence_kind": (
            _DERIVED,
            "asserts exactly this and nothing more: allocations is the value of"
            " b28_recompute_allocation over the request's retained evidence,"
            " verified inside this trigger. It is NOT a claim that any"
            " particular process executed a solver -- no execution witness"
            " exists and none is claimed (Directive VI section 18,"
            " Architecture B)",
        ),
        "total_budget_minor": (_PROVENANCE, "conserved from the request"),
        "allocated_total_minor": (
            _DERIVED,
            "sum of allocations; conservation is CHECK-enforced against"
            " total_budget_minor",
        ),
        "currency": (_PROVENANCE, "conserved from the request"),
        "action_authority": (
            _DERIVED,
            "derived from the source issuance policy_state, bounded above by"
            " proposal_required; the guard refuses any other value",
        ),
        "authority_class": (_DERIVED, "constant class of a P14 simulation artifact"),
        "llm_authority_over_allocation": (
            _DERIVED,
            "constant none; no model has authority over money in P14",
        ),
        "allocations": (
            _DERIVED,
            "b28_recompute_allocation over the request's retained evidence, line"
            " for line including weights and order",
        ),
        "created_at": (
            _EVENT,
            "the database clock at the instant the result committed",
        ),
    },
    "b28_proposals": {
        "id": (_PROVENANCE, "surrogate identity of this durable proposal"),
        "tenant_id": (_AUTHORITY, "the tenant boundary this proposal belongs to"),
        "result_id": (_PROVENANCE, "the durable result this proposal projects"),
        "proposal_ref": (_PROVENANCE, "caller-visible reference, unique per result"),
        "source_envelope_id": (_PROVENANCE, "conserved from the result"),
        "action_authority": (
            _DERIVED,
            "equal to the result's action_authority; a proposal cannot"
            " strengthen the authority it projects",
        ),
        "requires_human_approval": (
            _DERIVED,
            "constant true; P14 emits no auto-executable proposal",
        ),
        "authority_class": (_DERIVED, "constant non_authoritative_proposal"),
        "allocations": (_DERIVED, "equal to the result's allocations"),
        "created_at": (
            _EVENT,
            "the database clock at the instant the proposal committed",
        ),
    },
}


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


def _assert_empty(relation: str, why: str) -> None:
    """Refuse to migrate a populated relation that has no honest backfill.

    The relation is RLS-FORCED, so even its owner sees no rows while
    ``app.current_tenant_id`` is unset -- ``tenant_id = NULL::uuid`` is UNKNOWN
    and the policy filters everything out. A bare ``count(*)`` would therefore
    return 0 over a populated table and admit the state it exists to refuse. The
    force flag is lifted for the count and restored in the same transaction; if
    the assertion fires the whole migration rolls back and the flag returns with
    it.
    """
    op.execute(
        f"""
        DO $$
        DECLARE
            existing bigint;
        BEGIN
            ALTER TABLE public.{relation} NO FORCE ROW LEVEL SECURITY;
            SELECT count(*) INTO existing FROM public.{relation};
            ALTER TABLE public.{relation} FORCE ROW LEVEL SECURITY;
            IF existing > 0 THEN
                RAISE EXCEPTION
                    'b25_p14_r6_requires_empty_{relation}:% rows {why}',
                    existing
                    USING ERRCODE = '55000';
            END IF;
        END $$;
        """
    )


def _comment_fields() -> None:
    for relation, columns in FIELD_SEMANTICS.items():
        for column, (classification, evidence) in columns.items():
            body = f"{classification}. {evidence}.".replace("'", "''")
            op.execute(f"COMMENT ON COLUMN public.{relation}.{column} IS '{body}'")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 0. Fail closed on rows that cannot satisfy the corrected contract.
    # ------------------------------------------------------------------
    _assert_empty(
        "b28_simulation_requests",
        "carry no possession witness to backfill",
    )
    _assert_empty(
        "b28_simulation_results",
        "carry no governed consequence kind to backfill",
    )

    # ------------------------------------------------------------------
    # 1. The possession witness relation.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE public.b28_request_authentications (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL
                REFERENCES public.tenants(id) ON DELETE CASCADE,
            agent_client_id uuid NOT NULL
                REFERENCES public.agent_clients(id) ON DELETE RESTRICT,
            credential_id uuid NOT NULL
                REFERENCES public.agent_service_credentials(id) ON DELETE RESTRICT,
            request_binding text NOT NULL,
            authenticated_at timestamptz NOT NULL DEFAULT now(),
            authenticated_by_principal text NOT NULL,
            CONSTRAINT ck_b28_request_authentication_binding CHECK (
                request_binding ~ '^sha256:[0-9a-f]{64}$'
            ),
            CONSTRAINT ck_b28_request_authentication_principal CHECK (
                length(authenticated_by_principal) BETWEEN 1 AND 63
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_b28_request_authentication_credential"
        " ON public.b28_request_authentications (tenant_id, credential_id)"
    )
    op.execute(
        "ALTER TABLE public.b28_request_authentications ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b28_request_authentications FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_b28_request_authentications
        ON public.b28_request_authentications
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (
            tenant_id = current_setting('app.current_tenant_id', true)::uuid
        )
        """
    )

    # ------------------------------------------------------------------
    # 2. The binding a witness is minted for and a request is checked against.
    # ------------------------------------------------------------------
    # String components are escaped with `to_jsonb(text)::text` -- the same
    # escaping `b28_canonical_input_material` uses -- so no component can forge a
    # separator and shift the boundary between fields.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b28_request_authentication_binding(
            p_tenant_id uuid,
            p_request_ref text,
            p_source_issuance_envelope_hash text,
            p_input_snapshot_hash text
        )
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        SET search_path = pg_catalog, public
        AS $BODY$
            SELECT 'sha256:' || encode(
                sha256(
                    convert_to(
                        '{"binding_version":"b25-p14-c6-request-binding-v1"'
                        || ',"tenant_id":'
                        || to_jsonb(COALESCE(p_tenant_id::text, ''))::text
                        || ',"request_ref":'
                        || to_jsonb(COALESCE(p_request_ref, ''))::text
                        || ',"source_issuance_envelope_hash":'
                        || to_jsonb(
                               COALESCE(p_source_issuance_envelope_hash, '')
                           )::text
                        || ',"input_snapshot_hash":'
                        || to_jsonb(COALESCE(p_input_snapshot_hash, ''))::text
                        || '}',
                        'UTF8'
                    )
                ),
                'hex'
            )
        $BODY$;
        """
    )

    # ------------------------------------------------------------------
    # 3. The only writer of a possession witness.
    # ------------------------------------------------------------------
    # SECURITY DEFINER because no principal holds INSERT on the witness
    # relation: possession, not privilege, is what mints a row. The caller
    # supplies a secret and gets back an id; it cannot name the client, the
    # credential, the principal or the timestamp. `session_user` is unaffected by
    # SECURITY DEFINER, so the authority check below still sees the real login
    # rather than the function owner.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b28_authenticate_request_possession(
            p_tenant_id uuid,
            p_presented_token text,
            p_request_ref text,
            p_source_issuance_envelope_hash text,
            p_input_snapshot_hash text
        )
        RETURNS uuid
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            principal_is_trusted boolean;
            v_prefix text;
            v_presented_hash text;
            v_credential_id uuid;
            v_client_id uuid;
            v_token_hash text;
            v_hash_algorithm text;
            v_status text;
            v_revoked_at timestamptz;
            v_expires_at timestamptz;
            v_credential_tenant uuid;
            v_client_status text;
            v_client_tenant uuid;
            v_binding text;
            v_witness uuid;
        BEGIN
            SELECT COALESCE(rolsuper, false) INTO principal_is_trusted
              FROM pg_catalog.pg_roles WHERE rolname = session_user;
            principal_is_trusted := COALESCE(principal_is_trusted, false)
                OR pg_catalog.pg_has_role(
                       session_user, 'migration_owner', 'USAGE'
                   );
            IF NOT principal_is_trusted
               AND session_user <> '{_REQUEST_PRINCIPAL}'
            THEN
                RAISE EXCEPTION
                    'b28_request_possession_principal_not_authorized:%',
                    session_user
                    USING ERRCODE = '42501';
            END IF;

            IF p_presented_token IS NULL
               OR length(p_presented_token) < {_TOKEN_PREFIX_LENGTH}
            THEN
                RAISE EXCEPTION
                    'b28_request_possession_token_malformed'
                    USING ERRCODE = '42501';
            END IF;
            IF p_tenant_id IS NULL THEN
                RAISE EXCEPTION
                    'b28_request_possession_tenant_required'
                    USING ERRCODE = '42501';
            END IF;

            v_prefix := left(p_presented_token, {_TOKEN_PREFIX_LENGTH});
            v_presented_hash := encode(
                sha256(convert_to(p_presented_token, 'UTF8')), 'hex'
            );

            SELECT cred.id, cred.agent_client_id, cred.token_hash,
                   cred.hash_algorithm, cred.status, cred.revoked_at,
                   cred.expires_at, cred.tenant_id
              INTO v_credential_id, v_client_id, v_token_hash,
                   v_hash_algorithm, v_status, v_revoked_at,
                   v_expires_at, v_credential_tenant
              FROM public.agent_service_credentials AS cred
             WHERE cred.tenant_id = p_tenant_id
               AND cred.token_prefix = v_prefix
             LIMIT 1;

            -- A wrong prefix and a wrong secret are the same refusal on
            -- purpose: a caller must not learn which prefixes exist.
            IF NOT FOUND
               OR COALESCE(v_hash_algorithm, '{_TOKEN_HASH_ALGORITHM}')
                      <> '{_TOKEN_HASH_ALGORITHM}'
               OR v_token_hash IS NULL
               OR v_token_hash <> v_presented_hash
            THEN
                RAISE EXCEPTION
                    'b28_request_possession_credential_unknown'
                    USING ERRCODE = '42501';
            END IF;

            IF EXISTS (
                SELECT 1 FROM public.agent_token_revocations
                 WHERE tenant_id = p_tenant_id AND token_prefix = v_prefix
            ) THEN
                RAISE EXCEPTION
                    'b28_request_possession_credential_revoked'
                    USING ERRCODE = '42501';
            END IF;
            IF v_status IS DISTINCT FROM 'active'
               OR v_revoked_at IS NOT NULL
               OR (v_expires_at IS NOT NULL AND v_expires_at <= now())
            THEN
                RAISE EXCEPTION
                    'b28_request_possession_credential_not_live:%',
                    COALESCE(v_status, 'null')
                    USING ERRCODE = '42501';
            END IF;
            IF v_credential_tenant IS DISTINCT FROM p_tenant_id THEN
                RAISE EXCEPTION
                    'b28_request_possession_tenant_mismatch'
                    USING ERRCODE = '42501';
            END IF;

            SELECT status, tenant_id INTO v_client_status, v_client_tenant
              FROM public.agent_clients WHERE id = v_client_id;
            IF NOT FOUND
               OR v_client_status IS DISTINCT FROM 'active'
               OR v_client_tenant IS DISTINCT FROM p_tenant_id
            THEN
                RAISE EXCEPTION
                    'b28_request_possession_client_not_live:%',
                    COALESCE(v_client_status, 'null')
                    USING ERRCODE = '42501';
            END IF;

            v_binding := public.b28_request_authentication_binding(
                p_tenant_id,
                p_request_ref,
                p_source_issuance_envelope_hash,
                p_input_snapshot_hash
            );

            INSERT INTO public.b28_request_authentications (
                tenant_id, agent_client_id, credential_id,
                request_binding, authenticated_by_principal
            ) VALUES (
                p_tenant_id, v_client_id, v_credential_id,
                v_binding, session_user
            )
            RETURNING id INTO v_witness;
            RETURN v_witness;
        END;
        $BODY$;
        """
    )

    # ------------------------------------------------------------------
    # 4. The request names its witness, once.
    # ------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE public.b28_simulation_requests
            ADD COLUMN request_authentication_id uuid NOT NULL
                REFERENCES public.b28_request_authentications(id)
                ON DELETE RESTRICT
        """
    )
    # Single-use, structurally. Consuming a witness is not a mutation anybody
    # needs privilege for: the second request naming it simply cannot exist.
    op.execute(
        "CREATE UNIQUE INDEX uq_b28_request_authentication"
        " ON public.b28_simulation_requests (request_authentication_id)"
    )

    # ------------------------------------------------------------------
    # 5. The possession guard, as its own severable trigger.
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b28_enforce_request_possession()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            w_tenant uuid;
            w_client uuid;
            w_credential uuid;
            w_binding text;
            w_at timestamptz;
            expected_binding text;
        BEGIN
            SELECT tenant_id, agent_client_id, credential_id,
                   request_binding, authenticated_at
              INTO w_tenant, w_client, w_credential, w_binding, w_at
              FROM public.b28_request_authentications
             WHERE id = NEW.request_authentication_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'b28_request_possession_witness_unknown:%',
                    NEW.request_authentication_id
                    USING ERRCODE = '42501';
            END IF;
            IF w_tenant IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION
                    'b28_request_possession_witness_tenant_mismatch'
                    USING ERRCODE = '42501';
            END IF;
            IF w_client IS DISTINCT FROM NEW.requested_by_agent_client_id THEN
                RAISE EXCEPTION
                    'b28_request_possession_witness_client_mismatch:% vs %',
                    w_client, NEW.requested_by_agent_client_id
                    USING ERRCODE = '42501';
            END IF;
            IF w_credential IS DISTINCT FROM NEW.requested_by_credential_id THEN
                RAISE EXCEPTION
                    'b28_request_possession_witness_credential_mismatch:% vs %',
                    w_credential, NEW.requested_by_credential_id
                    USING ERRCODE = '42501';
            END IF;

            -- The witness authorises this row and no other. Re-deriving the
            -- binding here rather than comparing a stored copy means a witness
            -- minted for a cheaper request cannot be spent on a richer one.
            expected_binding := public.b28_request_authentication_binding(
                NEW.tenant_id,
                NEW.request_ref,
                NEW.source_issuance_envelope_hash,
                NEW.input_snapshot_hash
            );
            IF w_binding IS DISTINCT FROM expected_binding THEN
                RAISE EXCEPTION
                    'b28_request_possession_binding_mismatch:% vs %',
                    w_binding, expected_binding
                    USING ERRCODE = '42501';
            END IF;
            IF w_at IS NULL
               OR w_at <= now()
                   - interval '{_POSSESSION_WITNESS_TTL_SECONDS} seconds'
            THEN
                RAISE EXCEPTION
                    'b28_request_possession_witness_expired:%', w_at
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $BODY$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b28_request_possession"
        " ON public.b28_simulation_requests"
    )
    # PostgreSQL fires BEFORE triggers in name order, so `..._consequence`
    # (c) runs before `..._possession` (p). That ordering is deliberate and
    # pinned by a test: the consequence guard's refusals are the more specific
    # diagnosis of a malformed row, and an operator should see
    # `b28_request_requester_credential_unknown` rather than a witness mismatch
    # when the credential itself is the problem. Both must pass, so the order
    # is a diagnostic property, never a security one.
    op.execute(
        """
        CREATE TRIGGER trg_b28_request_possession
        BEFORE INSERT ON public.b28_simulation_requests
        FOR EACH ROW
        EXECUTE FUNCTION public.b28_enforce_request_possession()
        """
    )

    # ------------------------------------------------------------------
    # 6. The persisted solver contract stops claiming an execution event.
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE public.b28_simulation_results DROP COLUMN solver_invocations"
    )
    op.execute(
        f"""
        ALTER TABLE public.b28_simulation_results
            ADD COLUMN solver_consequence_kind text NOT NULL,
            ADD CONSTRAINT ck_b28_result_solver_consequence_kind CHECK (
                solver_consequence_kind = '{_SOLVER_CONSEQUENCE_KIND}'
            )
        """
    )

    # ------------------------------------------------------------------
    # 7. The result guard, with the event claim replaced by the value claim.
    # ------------------------------------------------------------------
    op.execute(_result_guard_sql(consequence_kind=True))

    # ------------------------------------------------------------------
    # 8. Directive VI section 15 -- every durable field says what it is.
    # ------------------------------------------------------------------
    _comment_fields()
    op.execute(
        "COMMENT ON TABLE public.b28_request_authentications IS"
        " 'B2.5-P14 Corrective VI. One row = one verified proof that a caller"
        " held a machine credential''s plaintext secret, bound to one exact"
        " request. Written only by b28_authenticate_request_possession(); no"
        " principal holds INSERT.'"
    )

    # ------------------------------------------------------------------
    # 9. Authority. Possession mints witnesses; privilege does not.
    # ------------------------------------------------------------------
    op.execute("REVOKE ALL ON TABLE public.b28_request_authentications FROM PUBLIC")
    for role in ("app_user", "app_ro"):
        _if_role_exists(
            role,
            f"REVOKE ALL ON TABLE public.b28_request_authentications FROM {role};"
            " GRANT SELECT ON TABLE public.b28_request_authentications"
            f" TO {role}",
        )
    for role in ("app_rw", "app_worker"):
        _if_role_exists(
            role,
            "REVOKE ALL ON TABLE public.b28_request_authentications"
            f" FROM {role}",
        )
    # The request principal reads the witness (its guard must) and never writes
    # one. INSERT stays with the definer function, whose key is a secret rather
    # than a grant.
    _if_role_exists(
        _REQUEST_PRINCIPAL,
        "GRANT SELECT ON TABLE public.b28_request_authentications"
        f" TO {_REQUEST_PRINCIPAL};"
        " REVOKE INSERT, UPDATE, DELETE, TRUNCATE"
        " ON TABLE public.b28_request_authentications"
        f" FROM {_REQUEST_PRINCIPAL}",
    )
    _if_role_exists(
        _SOLVER_PRINCIPAL,
        "REVOKE ALL ON TABLE public.b28_request_authentications"
        f" FROM {_SOLVER_PRINCIPAL}",
    )

    op.execute(
        "REVOKE ALL ON FUNCTION public.b28_authenticate_request_possession("
        "uuid, text, text, text, text) FROM PUBLIC"
    )
    _if_role_exists(
        _REQUEST_PRINCIPAL,
        "GRANT EXECUTE ON FUNCTION public.b28_authenticate_request_possession("
        f"uuid, text, text, text, text) TO {_REQUEST_PRINCIPAL}",
    )
    # A pure function over its arguments; an auditor holding only SELECT must be
    # able to recompute the binding independently.
    op.execute(
        "GRANT EXECUTE ON FUNCTION"
        " public.b28_request_authentication_binding(uuid, text, text, text)"
        " TO PUBLIC"
    )


def downgrade() -> None:
    """Restore the ``202609061200`` contract exactly."""

    op.execute(
        "DROP TRIGGER IF EXISTS trg_b28_request_possession"
        " ON public.b28_simulation_requests"
    )
    op.execute("DROP FUNCTION IF EXISTS public.b28_enforce_request_possession()")
    op.execute("DROP INDEX IF EXISTS public.uq_b28_request_authentication")
    op.execute(
        "ALTER TABLE public.b28_simulation_requests"
        " DROP COLUMN IF EXISTS request_authentication_id"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b28_authenticate_request_possession("
        "uuid, text, text, text, text)"
    )
    op.execute("DROP TABLE IF EXISTS public.b28_request_authentications")
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b28_request_authentication_binding(uuid, text, text, text)"
    )

    for relation, columns in FIELD_SEMANTICS.items():
        if relation == "b28_request_authentications":
            continue
        for column in columns:
            if column in ("request_authentication_id", "solver_consequence_kind"):
                continue
            op.execute(f"COMMENT ON COLUMN public.{relation}.{column} IS NULL")

    op.execute(
        "ALTER TABLE public.b28_simulation_results"
        " DROP CONSTRAINT IF EXISTS ck_b28_result_solver_consequence_kind"
    )
    op.execute(
        "ALTER TABLE public.b28_simulation_results"
        " DROP COLUMN IF EXISTS solver_consequence_kind"
    )
    op.execute(
        "ALTER TABLE public.b28_simulation_results"
        " ADD COLUMN solver_invocations integer NOT NULL"
    )
    op.execute(_result_guard_sql(consequence_kind=False))


def _result_guard_sql(*, consequence_kind: bool) -> str:
    """The result consequence guard, in whichever solver vocabulary applies.

    Both the upgrade and the downgrade need the whole body; emitting it from one
    place means the two directions cannot drift into different guards while
    appearing to be inverses.
    """

    if consequence_kind:
        solver_semantics = f"""
            -- Corrective VI, Gate 3 Architecture B. The persisted vocabulary
            -- names the proposition this guard actually establishes: the row is
            -- the value of the governed deterministic function over the admitted
            -- input. `solver_invocations` is gone because the database cannot
            -- witness an execution and the schema must not claim what it cannot
            -- prove.
            IF NEW.solver_consequence_kind
                   IS DISTINCT FROM '{_SOLVER_CONSEQUENCE_KIND}'
            THEN
                RAISE EXCEPTION
                    'b28_result_consequence_kind_ungoverned:%',
                    COALESCE(NEW.solver_consequence_kind, 'null')
                    USING ERRCODE = '42501';
            END IF;
        """
    else:
        solver_semantics = """
            IF NEW.solver_invocations IS DISTINCT FROM 1 THEN
                RAISE EXCEPTION
                    'b28_result_solver_invocations_not_one:%',
                    NEW.solver_invocations
                    USING ERRCODE = '42501';
            END IF;
        """

    return f"""
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

            -- Corrective V, Exit Gate 4's active falsifier. The comparison above
            -- proves the result cites its request's snapshot; it does not prove
            -- the request still *is* what it was admitted as. Re-deriving it
            -- here makes a post-admission input change unrepresentable as a
            -- consequence rather than merely detectable after the fact.
            IF request_row.input_snapshot_hash IS DISTINCT FROM
               public.b28_input_snapshot_hash(
                   request_row.source_envelope_id,
                   request_row.source_semantic_truth_hash,
                   request_row.total_budget_minor,
                   request_row.currency,
                   request_row.channel_evidence
               )
            THEN
                RAISE EXCEPTION
                    'b28_result_request_input_witness_broken:%', NEW.request_id
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
{solver_semantics}
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
