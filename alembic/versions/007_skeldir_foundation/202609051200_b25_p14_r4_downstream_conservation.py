"""B2.5-P14 Corrective IV: conserve the causal witness and bind downstream consequence.

Revision ID: 202609051200
Revises: 202609041200

Three physical conservation failures were reproduced on protected main before
this revision was written, each on a fresh PostgreSQL 15 instance provisioned by
the repository's own role script and migrated empty-to-head.

----------------------------------------------------------------------------
1. The terminal record's causal witness was mutable (Corrective IV Gate 1)
----------------------------------------------------------------------------

After a lawful signer-confirmed issuance reached terminal ``issued`` and its
durable row existed in ``trust_envelope_issuance_log``, 48 of 56 attempted
post-terminal field mutations on the parent ``trust_access_log`` row were
ACCEPTED with ``rowcount=1`` -- ``envelope_hash``, ``semantic_truth_hash``,
``idempotency_key_hash``, ``subject_ref_hash``, ``audit_hash``, ``status``,
``policy_state``, ``request_identity_hash``, ``reason_code``, ``subject_type``,
``evidence_refs_allowed`` and ``created_at``, under every one of ``app_user``,
``app_worker``, ``app_trust_issuer`` and ``app_trust_signer``. The measured end
state had ``ledger.semantic_truth_hash <> terminal.semantic_truth_hash``: the
durable record and the witness it is referentially bound to disagreed about what
was signed.

**Root cause, established before remediation.** The C16/C17-B guard
``trust_access_log_issuance_authority_guard`` computes ``consequence_changed``
over the issuance state machine and its cryptographic columns, and then:

    IF NOT consequence_changed THEN RETURN NEW; END IF;

Every protection the guard offers -- terminal refusal, per-transition principal
checks, evidence correspondence -- sits *after* that early return. An UPDATE that
touches only truth-bearing identity columns changes no listed consequence column,
so the guard returns before any of it runs. The sibling guard on
``trust_issuance_attempts`` has no such short-circuit, and the same probe found
that relation correctly fenced. The defect is the short-circuit, not the column
list, which is why this revision does not merely lengthen the list.

**The repair.** A second, independently severable trigger partitions the
relation's columns *totally*, by iterating ``to_jsonb(NEW)`` rather than naming
columns:

    mutable operational metadata   replay_count, last_replayed_at, updated_at
    governed issuance machine      the twelve columns C16/C17-B adjudicates
    immutable causal witness       everything else -- including any column a
                                   future migration adds

The third set is fenced for the whole lifecycle, not only after terminalization.
Post-terminal-only would have left the class open: an identity column rewritten
while the ledger is still ``authorized`` is projected into terminal history by
the Gate 0 agreement guard, and the durable record then faithfully records a
witness that was already falsified. Fencing from INSERT is the narrower repair
*and* the total one.

Lawful behaviour is preserved exactly. ``_upsert_access_log``'s replay path
(``ON CONFLICT DO UPDATE SET replay_count = replay_count + 1, last_replayed_at,
updated_at``) is the only UPDATE the API principal performs on this relation, and
every issuer/signer UPDATE in ``app/trust/audit.py`` writes issuance-machine
columns alone. Both remain permitted; the probe re-run confirms all three
operational columns still accept writes from every principal that holds UPDATE.

----------------------------------------------------------------------------
2. B2.7/B2.8 persistence was self-certified (Corrective IV Gate 3)
----------------------------------------------------------------------------

The same session found that ``app_user`` could, with no application code
involved, INSERT a complete downstream consequence chain:

    b28_simulation_requests   naming an envelope that was never issued
      -> b28_simulation_results  claiming solver_invocations = 1
        -> b28_proposals

and a ``b27_explanation_materializations`` row whose ``narrative`` read "The
email channel caused $9,999,999 of incremental revenue." -- an artifact no
adjudicator had ever seen, bound to no real Trust. The ``NOT NULL`` request
foreign key proved a request *row* existed; it could not prove a request was
*made*, and nothing bound either to a real issuance. This is structurally the
Gate 0 defect class applied to P14's own relations.

**The repair**, following the shape Gate 0 already proved:

  * **Referential binding.** ``b27_explanation_materializations`` and
    ``b28_simulation_requests`` gain a NOT NULL ``source_issuance_envelope_hash``
    with a real foreign key to ``trust_envelope_issuance_log (tenant_id,
    envelope_hash)``. A downstream artifact that names no durable issuance is now
    unrepresentable, and stays unrepresentable if a trigger is dropped.

  * **Consequence guards.** BEFORE INSERT triggers require agreement with the
    bound terminal row (tenant, subject, semantic truth, policy state), admission
    policy for a simulation request, field-by-field agreement between a result
    and its request, the deterministic derivation of ``action_authority`` from
    the source policy, and allocation agreement between a proposal and its
    result.

  * **Immutability.** BEFORE UPDATE/DELETE triggers fence every downstream
    relation, admitting exactly one transition: the definer-authority staleness
    marking on ``b27_explanation_materializations``.

----------------------------------------------------------------------------
3. Free prose could carry causal authority the source lacked (Gate 2)
----------------------------------------------------------------------------

Twenty ordinary English sentences asserting causation were accepted by the real
``compose_explanation`` path against a Trust state with no causal authority. The
adjudicator's ``_CAUSAL_LANGUAGE`` indicator is a finite denylist, and the class
it is trying to decide is open-world.

The application-tier repair lives in ``app/explanation/templates.py``: an
explanation's narrative is admissible only as the exact join of registered frame
instances, each filled with a value matching a machine grammar. This revision
carries the *physical* half of that law, so a row written straight past the
application is refused the same way:

  * ``b27_narrative_templates`` mirrors the closed frame corpus row-for-row;
  * ``b27_narrative_template_registry`` pins its content address;
  * the B2.7 consequence guard re-derives every claim's rendering from the
    template and its ``value_text``, requires the value to match the frame's
    grammar, and requires the stored narrative to equal the exact join.

No runtime principal holds INSERT, UPDATE or DELETE on either registry relation:
adding a frame is a migration, which is a merge-governed act.
"""

from __future__ import annotations

from alembic import op


revision = "202609051200"
down_revision = "202609041200"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# The trust_access_log column partition.
# ---------------------------------------------------------------------------
# Operational metadata a holder of UPDATE may write freely. These carry no
# statement about what was requested, adjudicated or signed.
_ACCESS_LOG_OPERATIONAL_COLUMNS = (
    "replay_count",
    "last_replayed_at",
    "updated_at",
)

# The issuance state machine. Changes here are adjudicated by the C16/C17-B
# guard -- transition legality, per-transition principal, terminal refusal and
# evidence correspondence -- so the witness fence defers to it rather than
# duplicating it.
_ACCESS_LOG_ISSUANCE_MACHINE_COLUMNS = (
    "issuance_state",
    "issued_at",
    "issuance_attempted_at",
    "issuance_outcome_unknown_at",
    "known_signature_at",
    "issued_attempt_id",
    "issued_signing_key_id",
    "issued_signature_hash",
    "issued_signature",
    "issued_envelope",
    "issuance_attempt_count",
    "issuance_unknown_outcome_count",
)

_ACCESS_LOG_MUTABLE_COLUMNS = (
    _ACCESS_LOG_OPERATIONAL_COLUMNS + _ACCESS_LOG_ISSUANCE_MACHINE_COLUMNS
)

# ---------------------------------------------------------------------------
# The closed B2.7 narrative frame corpus, mirroring
# app/explanation/templates.py::registry_rows(). The equality is asserted by
# backend/tests/trust/test_b25_p14_r4_downstream_consequence.py, so drift
# between the declared corpus and the physical one is merge-blocking.
# ---------------------------------------------------------------------------
_TEMPLATE_REGISTRY_VERSION = "b25-p14-r4-explanation-templates-v1"
_TEMPLATE_REGISTRY_HASH = (
    "sha256:45a4c69ed37ef8de490b5ae1d2347f893b4bd730273fc4be4a8dbf64b90cb397"
)

_TEMPLATE_SEED_VALUES = r"""
    ('provenance.envelope_id.v1', 'provenance_fact', 'envelope_id', 'This explanation is bound to envelope_id {value}.', 'opaque_id', '^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$'),
    ('provenance.semantic_truth_hash.v1', 'provenance_fact', 'semantic_truth_hash', 'This explanation is bound to semantic_truth_hash {value}.', 'hash', '^sha256:[0-9a-f]{64}$'),
    ('provenance.audit_ref.v1', 'provenance_fact', 'audit_ref', 'This explanation is bound to audit_ref {value}.', 'opaque_id', '^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$'),
    ('financial.verified_revenue_minor.v1', 'financial_fact', 'verified_revenue_minor', 'Verified revenue is {value}.', 'money_minor', '^-?[0-9]{1,19} minor units \(-?[0-9]{1,17}\.[0-9]{2}\)$'),
    ('status.currency.v1', 'status_fact', 'currency', 'Amounts are denominated in {value}.', 'currency', '^[A-Z]{3}$'),
    ('status.deterministic_verification_status.v1', 'status_fact', 'deterministic_verification_status', 'Deterministic verification status is {value}.', 'enum', '^[a-z][a-z0-9_]{0,63}$'),
    ('status.match_verdict_status.v1', 'status_fact', 'match_verdict_status', 'The match verdict is {value}.', 'enum', '^[a-z][a-z0-9_]{0,63}$'),
    ('status.discrepancy_class.v1', 'status_fact', 'discrepancy_class', 'The reconciliation discrepancy class is {value}.', 'enum', '^[a-z][a-z0-9_]{0,63}$'),
    ('status.attribution_model.v1', 'status_fact', 'attribution_model', 'The attribution model applied is {value}.', 'enum', '^[a-z][a-z0-9_]{0,63}$'),
    ('status.model_assumption.v1', 'status_fact', 'model_assumption', 'The model assumption is {value}.', 'enum', '^[a-z][a-z0-9_]{0,63}$'),
    ('status.causal_status.v1', 'status_fact', 'causal_status', 'The causal status of this result is {value}.', 'enum', '^[a-z][a-z0-9_]{0,63}$'),
    ('status.data_completeness_status.v1', 'status_fact', 'data_completeness_status', 'Data completeness is {value}.', 'enum', '^[a-z][a-z0-9_]{0,63}$'),
    ('status.truth_type.v1', 'status_fact', 'truth_type', 'The truth type is {value}.', 'enum', '^[a-z][a-z0-9_]{0,63}$'),
    ('status.truth_authority_authority_class.v1', 'status_fact', 'truth_authority.authority_class', 'The authority class is {value}.', 'enum', '^[a-z][a-z0-9_]{0,63}$'),
    ('status.confidence_metadata_unavailable_reason.v1', 'status_fact', 'confidence_metadata.unavailable_reason', 'The recorded confidence unavailability reason is {value}.', 'enum', '^[a-z][a-z0-9_]{0,63}$'),
    ('confidence.confidence_status.v1', 'confidence_statement', 'confidence_metadata.confidence_status', 'The recorded confidence status is {value}.', 'enum', '^[a-z][a-z0-9_]{0,63}$'),
    ('confidence.confidence_score_basis_points.v1', 'confidence_statement', 'confidence_metadata.confidence_score_basis_points', 'The projected confidence is {value} basis points.', 'integer', '^-?[0-9]{1,19}$'),
    ('fallback.fallback_applied.v1', 'fallback_statement', 'fallback_applied', 'The declared fallback state is {value}.', 'boolean', '^(true|false)$'),
    ('fallback.fallback_reason.v1', 'fallback_statement', 'fallback_reason', 'The declared fallback reason is {value}.', 'enum', '^[a-z][a-z0-9_]{0,63}$'),
    ('policy.policy_state.v1', 'policy_statement', 'policy_action_authority.policy_state', 'The policy authority for this subject is {value}.', 'enum', '^[a-z][a-z0-9_]{0,63}$')
"""

# The B2.8 governed constants, mirroring app/simulation/*.py. A result that
# names a different solver profile or sufficiency policy is not a consequence of
# this system's solver.
_SOLVER_PROFILE = "b25-p14-deterministic-largest-remainder-v1"
_SUFFICIENCY_POLICY_VERSION = "b25-p14-sufficiency-v1"
_SIMULATION_ADMISSIBLE_POLICY_STATES = (
    "simulation_only",
    "proposal_required",
    "approval_required",
)
_MAX_PROPOSAL_AUTHORITY = "proposal_required"

_P14_DOWNSTREAM_TABLES = (
    "b27_explanation_materializations",
    "b28_simulation_requests",
    "b28_simulation_results",
    "b28_proposals",
)


def _sql_text_array(values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"ARRAY[{joined}]::text[]"


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
    # 1. The causal witness fence on trust_access_log.
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.trust_access_log_witness_immutability_guard()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            principal_is_superuser boolean;
            table_owner_oid oid;
            mutable_columns text[] := {_sql_text_array(_ACCESS_LOG_MUTABLE_COLUMNS)};
            old_row jsonb;
            new_row jsonb;
            column_name text;
        BEGIN
            SELECT rolsuper
              INTO principal_is_superuser
              FROM pg_catalog.pg_roles
             WHERE rolname = session_user;
            SELECT relowner INTO table_owner_oid
              FROM pg_catalog.pg_class WHERE oid = TG_RELID;

            -- A superuser or the owning migration principal can drop this
            -- trigger outright, so refusing them buys no authority. C20/C21
            -- already assert that no runtime login reaches the owner, and the
            -- canonical-schema gate detects the trigger's removal.
            IF COALESCE(principal_is_superuser, false)
               OR pg_catalog.pg_has_role(session_user, table_owner_oid, 'USAGE')
            THEN
                RETURN NEW;
            END IF;

            old_row := to_jsonb(OLD);
            new_row := to_jsonb(NEW);

            -- Total over columns, including columns that do not exist yet. A
            -- future migration that adds a truth-bearing column inherits the
            -- fence by default and has to opt out deliberately, which is the
            -- direction a fail-closed system needs.
            FOR column_name IN SELECT jsonb_object_keys(new_row)
            LOOP
                IF column_name = ANY(mutable_columns) THEN
                    CONTINUE;
                END IF;
                IF (new_row -> column_name) IS DISTINCT FROM (old_row -> column_name)
                THEN
                    RAISE EXCEPTION
                        'trust_access_log_witness_immutable:%', column_name
                        USING ERRCODE = '42501';
                END IF;
            END LOOP;
            RETURN NEW;
        END;
        $BODY$;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_trust_access_log_witness_immutability
            ON public.trust_access_log;
        CREATE TRIGGER trg_trust_access_log_witness_immutability
            BEFORE UPDATE ON public.trust_access_log
            FOR EACH ROW
            EXECUTE FUNCTION public.trust_access_log_witness_immutability_guard();
        """
    )

    # ------------------------------------------------------------------
    # 2. The closed B2.7 narrative frame corpus, physically.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE public.b27_narrative_templates (
            template_id text PRIMARY KEY,
            claim_kind text NOT NULL,
            source_path text NOT NULL,
            template_text text NOT NULL,
            value_grammar text NOT NULL,
            value_pattern text NOT NULL,
            CONSTRAINT ck_b27_template_single_variable CHECK (
                template_text LIKE '%{value}%'
                AND length(template_text)
                    - length(replace(template_text, '{value}', '')) = 7 * 1
            ),
            -- No frame may carry a numeral of its own: every number in an
            -- explanation has to come from a conserved claim value.
            CONSTRAINT ck_b27_template_no_fixed_numeral CHECK (
                replace(template_text, '{value}', ' ') !~ '[0-9]'
            ),
            CONSTRAINT ck_b27_template_kind CHECK (
                claim_kind IN (
                    'financial_fact', 'status_fact', 'confidence_statement',
                    'policy_statement', 'fallback_statement', 'provenance_fact'
                )
            ),
            CONSTRAINT uq_b27_template_binding UNIQUE (claim_kind, source_path)
        )
        """
    )
    op.execute(
        f"""
        INSERT INTO public.b27_narrative_templates
            (template_id, claim_kind, source_path, template_text,
             value_grammar, value_pattern)
        VALUES {_TEMPLATE_SEED_VALUES}
        """
    )
    # ``causal_statement`` is absent from the CHECK above by construction: B2.13
    # is the phase that would introduce a causal substrate, and until it exists
    # there is no source authority a causal frame could conserve.
    op.execute(
        """
        CREATE TABLE public.b27_narrative_template_registry (
            registry_version text PRIMARY KEY,
            registry_hash text NOT NULL,
            CONSTRAINT ck_b27_template_registry_hash CHECK (
                registry_hash ~ '^sha256:[0-9a-f]{64}$'
            )
        )
        """
    )
    op.execute(
        f"""
        INSERT INTO public.b27_narrative_template_registry
            (registry_version, registry_hash)
        VALUES ('{_TEMPLATE_REGISTRY_VERSION}', '{_TEMPLATE_REGISTRY_HASH}')
        """
    )
    for registry_relation in (
        "b27_narrative_templates",
        "b27_narrative_template_registry",
    ):
        op.execute(f"REVOKE ALL ON TABLE public.{registry_relation} FROM PUBLIC")
        # The B2.7 consequence guard is not SECURITY DEFINER, so it resolves the
        # frame corpus with the writer's own authority. SELECT is exactly what
        # that needs and exactly what any principal may hold here: the corpus is
        # a governed contract, and changing it is a migration.
        for role in ("app_user", "app_worker", "app_ro"):
            _if_role_exists(
                role,
                f"REVOKE ALL ON TABLE public.{registry_relation} FROM {role};"
                f" GRANT SELECT ON TABLE public.{registry_relation} TO {role}",
            )

    # ------------------------------------------------------------------
    # 3. Downstream artifacts name the durable issuance they project.
    # ------------------------------------------------------------------
    # Rows written before this revision cannot be bound to an issuance they never
    # recorded, so the migration refuses rather than inventing a lineage for
    # them. These relations were created one revision ago and carry downstream
    # materializations only; a deployment holding such rows should re-derive
    # them from the Trust that is still intact.
    for relation in ("b27_explanation_materializations", "b28_simulation_requests"):
        op.execute(
            f"""
            DO $$
            DECLARE
                unbindable bigint;
            BEGIN
                SELECT count(*) INTO unbindable
                  FROM public.{relation} AS downstream
                 WHERE NOT EXISTS (
                       SELECT 1 FROM public.trust_envelope_issuance_log AS issuance
                        WHERE issuance.tenant_id = downstream.tenant_id
                          AND issuance.semantic_truth_hash
                              = downstream.source_semantic_truth_hash
                 );
                IF unbindable > 0 THEN
                    RAISE EXCEPTION
                        'B2.5-P14 Corrective IV: % row(s) in {relation} project no '
                        'durable issuance. A downstream artifact must be the '
                        'consequence of a real issued TrustEnvelope; re-derive '
                        'the unbound rows before migrating.', unbindable
                        USING ERRCODE = '23503';
                END IF;
            END $$;
            """
        )
        op.execute(
            f"""
            ALTER TABLE public.{relation}
                ADD COLUMN source_issuance_envelope_hash text
            """
        )
        op.execute(
            f"""
            UPDATE public.{relation} AS downstream
               SET source_issuance_envelope_hash = issuance.envelope_hash
              FROM public.trust_envelope_issuance_log AS issuance
             WHERE issuance.tenant_id = downstream.tenant_id
               AND issuance.semantic_truth_hash
                   = downstream.source_semantic_truth_hash
            """
        )
        op.execute(
            f"""
            ALTER TABLE public.{relation}
                ALTER COLUMN source_issuance_envelope_hash SET NOT NULL
            """
        )
        op.execute(
            f"""
            ALTER TABLE public.{relation}
                ADD CONSTRAINT fk_{relation}_source_issuance
                FOREIGN KEY (tenant_id, source_issuance_envelope_hash)
                REFERENCES public.trust_envelope_issuance_log
                    (tenant_id, envelope_hash)
            """
        )

    op.execute(
        """
        ALTER TABLE public.b27_explanation_materializations
            ADD COLUMN explanation_template_registry_hash text
        """
    )
    op.execute(
        f"""
        UPDATE public.b27_explanation_materializations
           SET explanation_template_registry_hash = '{_TEMPLATE_REGISTRY_HASH}'
         WHERE explanation_template_registry_hash IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.b27_explanation_materializations
            ALTER COLUMN explanation_template_registry_hash SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.b27_explanation_materializations
            ADD CONSTRAINT ck_b27_template_registry_hash_shape CHECK (
                explanation_template_registry_hash ~ '^sha256:[0-9a-f]{64}$'
            )
        """
    )

    # ------------------------------------------------------------------
    # 4. The B2.7 consequence guard: source binding + narrative derivation.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b27_enforce_explanation_consequence()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            issuance_subject_type text;
            issuance_subject_ref_hash text;
            issuance_semantic_truth_hash text;
            issuance_policy_state text;
            registry_hash text;
            claim jsonb;
            template_kind text;
            template_path text;
            template_body text;
            template_pattern text;
            renderings text[] := ARRAY[]::text[];
            claim_index integer := 0;
        BEGIN
            SELECT subject_type, subject_ref_hash, semantic_truth_hash, policy_state
              INTO issuance_subject_type, issuance_subject_ref_hash,
                   issuance_semantic_truth_hash, issuance_policy_state
              FROM public.trust_envelope_issuance_log
             WHERE tenant_id = NEW.tenant_id
               AND envelope_hash = NEW.source_issuance_envelope_hash;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'b27_explanation_requires_durable_issuance:%',
                    NEW.source_issuance_envelope_hash
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.source_semantic_truth_hash
                   IS DISTINCT FROM issuance_semantic_truth_hash
               OR NEW.subject_type IS DISTINCT FROM issuance_subject_type
               OR NEW.subject_ref_hash IS DISTINCT FROM issuance_subject_ref_hash
            THEN
                RAISE EXCEPTION
                    'b27_explanation_source_disagrees_with_issuance:%',
                    NEW.source_issuance_envelope_hash
                    USING ERRCODE = '42501';
            END IF;
            -- Authority monotonicity, physically: an explanation restates the
            -- source policy state, it never re-grades it.
            IF NEW.policy_state IS DISTINCT FROM issuance_policy_state THEN
                RAISE EXCEPTION
                    'b27_explanation_policy_state_not_conserved:% vs %',
                    NEW.policy_state, issuance_policy_state
                    USING ERRCODE = '42501';
            END IF;

            SELECT r.registry_hash INTO registry_hash
              FROM public.b27_narrative_template_registry AS r
             WHERE r.registry_hash = NEW.explanation_template_registry_hash;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'b27_explanation_template_registry_unknown:%',
                    NEW.explanation_template_registry_hash
                    USING ERRCODE = '42501';
            END IF;

            IF NEW.claim_count IS DISTINCT FROM jsonb_array_length(NEW.claims) THEN
                RAISE EXCEPTION
                    'b27_explanation_claim_count_disagrees:% vs %',
                    NEW.claim_count, jsonb_array_length(NEW.claims)
                    USING ERRCODE = '42501';
            END IF;

            -- The derivation law. Every sentence must be an instance of a
            -- registered frame filled with a machine-grammar value, and the
            -- narrative must be the exact join of those instances. Free prose
            -- has no representable position, which is what makes this closed
            -- under language the corpus has never seen.
            FOR claim IN SELECT * FROM jsonb_array_elements(NEW.claims)
            LOOP
                claim_index := claim_index + 1;
                IF jsonb_typeof(claim) <> 'object'
                   OR claim ->> 'template_id' IS NULL
                   OR claim ->> 'value_text' IS NULL
                   OR claim ->> 'rendered' IS NULL
                   OR claim ->> 'claim_kind' IS NULL
                   OR claim ->> 'source_path' IS NULL
                THEN
                    RAISE EXCEPTION
                        'b27_explanation_claim_shape:%', claim_index
                        USING ERRCODE = '42501';
                END IF;
                SELECT t.claim_kind, t.source_path, t.template_text, t.value_pattern
                  INTO template_kind, template_path, template_body, template_pattern
                  FROM public.b27_narrative_templates AS t
                 WHERE t.template_id = claim ->> 'template_id';
                IF NOT FOUND THEN
                    RAISE EXCEPTION
                        'b27_explanation_template_unknown:%:%',
                        claim_index, claim ->> 'template_id'
                        USING ERRCODE = '42501';
                END IF;
                IF template_kind IS DISTINCT FROM claim ->> 'claim_kind'
                   OR template_path IS DISTINCT FROM claim ->> 'source_path'
                THEN
                    RAISE EXCEPTION
                        'b27_explanation_template_not_admitted_for_source:%:%',
                        claim_index, claim ->> 'template_id'
                        USING ERRCODE = '42501';
                END IF;
                IF (claim ->> 'value_text') !~ template_pattern THEN
                    RAISE EXCEPTION
                        'b27_explanation_value_grammar_violated:%:%',
                        claim_index, claim ->> 'template_id'
                        USING ERRCODE = '42501';
                END IF;
                IF (claim ->> 'rendered')
                   IS DISTINCT FROM replace(template_body, '{value}',
                                            claim ->> 'value_text')
                THEN
                    RAISE EXCEPTION
                        'b27_explanation_rendering_not_derived:%:%',
                        claim_index, claim ->> 'template_id'
                        USING ERRCODE = '42501';
                END IF;
                renderings := renderings || (claim ->> 'rendered');
            END LOOP;

            IF NEW.narrative IS DISTINCT FROM array_to_string(renderings, ' ') THEN
                RAISE EXCEPTION
                    'b27_explanation_narrative_not_derived_from_claims'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $BODY$;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b27_explanation_consequence
            ON public.b27_explanation_materializations;
        CREATE TRIGGER trg_b27_explanation_consequence
            BEFORE INSERT ON public.b27_explanation_materializations
            FOR EACH ROW
            EXECUTE FUNCTION public.b27_enforce_explanation_consequence();
        """
    )

    # ------------------------------------------------------------------
    # 5. The B2.8 consequence guards.
    # ------------------------------------------------------------------
    admissible_states = _sql_text_array(_SIMULATION_ADMISSIBLE_POLICY_STATES)
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
            admissible text[] := {admissible_states};
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
            -- Admission, physically. `read_only` and `blocked` are strictly
            -- weaker than simulating, so a request against them is refused
            -- rather than downgraded into a result-shaped no-op.
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
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b28_request_consequence
            ON public.b28_simulation_requests;
        CREATE TRIGGER trg_b28_request_consequence
            BEFORE INSERT ON public.b28_simulation_requests
            FOR EACH ROW
            EXECUTE FUNCTION public.b28_enforce_request_consequence();
        """
    )

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
            -- Field-by-field agreement. A foreign key proves a request row
            -- exists; this proves the result is a consequence *of that request*
            -- rather than an independent claim that happens to cite one.
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
            -- Authority is the weaker of the source policy and P14's own
            -- proposal ceiling, computed rather than asserted.
            derived_authority := CASE
                WHEN issuance_policy_state IN (
                    'blocked', 'read_only', 'simulation_only', 'proposal_required'
                ) THEN issuance_policy_state
                ELSE '{_MAX_PROPOSAL_AUTHORITY}'
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
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b28_result_consequence
            ON public.b28_simulation_results;
        CREATE TRIGGER trg_b28_result_consequence
            BEFORE INSERT ON public.b28_simulation_results
            FOR EACH ROW
            EXECUTE FUNCTION public.b28_enforce_result_consequence();
        """
    )

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
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b28_proposal_consequence
            ON public.b28_proposals;
        CREATE TRIGGER trg_b28_proposal_consequence
            BEFORE INSERT ON public.b28_proposals
            FOR EACH ROW
            EXECUTE FUNCTION public.b28_enforce_proposal_consequence();
        """
    )

    # ------------------------------------------------------------------
    # 6. Downstream artifacts are append-only.
    # ------------------------------------------------------------------
    # No runtime principal currently holds UPDATE or DELETE on these relations.
    # The fence exists so that a future grant regression cannot silently restore
    # the capability -- the same reason Gate 0 states its authority three times.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b27_enforce_materialization_immutability()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            principal_is_superuser boolean;
            table_owner_oid oid;
            old_row jsonb;
            new_row jsonb;
            column_name text;
        BEGIN
            SELECT rolsuper INTO principal_is_superuser
              FROM pg_catalog.pg_roles WHERE rolname = session_user;
            SELECT relowner INTO table_owner_oid
              FROM pg_catalog.pg_class WHERE oid = TG_RELID;
            IF COALESCE(principal_is_superuser, false)
               OR pg_catalog.pg_has_role(session_user, table_owner_oid, 'USAGE')
            THEN
                RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION
                    'b27_explanation_materialization_immutable:delete'
                    USING ERRCODE = '42501';
            END IF;
            old_row := to_jsonb(OLD);
            new_row := to_jsonb(NEW);
            FOR column_name IN SELECT jsonb_object_keys(new_row)
            LOOP
                IF column_name IN ('stale', 'superseded_at') THEN
                    CONTINUE;
                END IF;
                IF (new_row -> column_name) IS DISTINCT FROM (old_row -> column_name)
                THEN
                    RAISE EXCEPTION
                        'b27_explanation_materialization_immutable:%', column_name
                        USING ERRCODE = '42501';
                END IF;
            END LOOP;
            -- Staleness is one-way. An explanation superseded by newer Trust
            -- cannot be revived into currency.
            IF OLD.stale AND NOT NEW.stale THEN
                RAISE EXCEPTION
                    'b27_explanation_materialization_immutable:stale_reversal'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $BODY$;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b27_materialization_immutable
            ON public.b27_explanation_materializations;
        CREATE TRIGGER trg_b27_materialization_immutable
            BEFORE UPDATE OR DELETE ON public.b27_explanation_materializations
            FOR EACH ROW
            EXECUTE FUNCTION public.b27_enforce_materialization_immutability();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b28_enforce_downstream_immutability()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            principal_is_superuser boolean;
            table_owner_oid oid;
        BEGIN
            SELECT rolsuper INTO principal_is_superuser
              FROM pg_catalog.pg_roles WHERE rolname = session_user;
            SELECT relowner INTO table_owner_oid
              FROM pg_catalog.pg_class WHERE oid = TG_RELID;
            IF COALESCE(principal_is_superuser, false)
               OR pg_catalog.pg_has_role(session_user, table_owner_oid, 'USAGE')
            THEN
                RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
            END IF;
            RAISE EXCEPTION
                'b28_downstream_record_immutable:%:%', TG_TABLE_NAME, TG_OP
                USING ERRCODE = '42501';
        END;
        $BODY$;
        """
    )
    for relation in (
        "b28_simulation_requests",
        "b28_simulation_results",
        "b28_proposals",
    ):
        op.execute(
            f"""
            DROP TRIGGER IF EXISTS trg_{relation}_immutable ON public.{relation};
            CREATE TRIGGER trg_{relation}_immutable
                BEFORE UPDATE OR DELETE ON public.{relation}
                FOR EACH ROW
                EXECUTE FUNCTION public.b28_enforce_downstream_immutability();
            """
        )

    # The downstream relations are written by the API session that holds the
    # request, and read by anything with app_ro. Nothing else needs either head.
    for relation in _P14_DOWNSTREAM_TABLES:
        op.execute(f"REVOKE ALL ON TABLE public.{relation} FROM PUBLIC")
        _if_role_exists(
            "app_user",
            f"REVOKE ALL ON TABLE public.{relation} FROM app_user;"
            f" GRANT SELECT, INSERT ON TABLE public.{relation} TO app_user",
        )
        _if_role_exists(
            "app_rw",
            f"REVOKE ALL ON TABLE public.{relation} FROM app_rw",
        )
        _if_role_exists(
            "app_ro",
            f"REVOKE ALL ON TABLE public.{relation} FROM app_ro;"
            f" GRANT SELECT ON TABLE public.{relation} TO app_ro",
        )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b28_proposals_immutable ON public.b28_proposals;
        DROP TRIGGER IF EXISTS trg_b28_simulation_results_immutable
            ON public.b28_simulation_results;
        DROP TRIGGER IF EXISTS trg_b28_simulation_requests_immutable
            ON public.b28_simulation_requests;
        DROP FUNCTION IF EXISTS public.b28_enforce_downstream_immutability();
        DROP TRIGGER IF EXISTS trg_b27_materialization_immutable
            ON public.b27_explanation_materializations;
        DROP FUNCTION IF EXISTS public.b27_enforce_materialization_immutability();
        DROP TRIGGER IF EXISTS trg_b28_proposal_consequence ON public.b28_proposals;
        DROP FUNCTION IF EXISTS public.b28_enforce_proposal_consequence();
        DROP TRIGGER IF EXISTS trg_b28_result_consequence
            ON public.b28_simulation_results;
        DROP FUNCTION IF EXISTS public.b28_enforce_result_consequence();
        DROP TRIGGER IF EXISTS trg_b28_request_consequence
            ON public.b28_simulation_requests;
        DROP FUNCTION IF EXISTS public.b28_enforce_request_consequence();
        DROP TRIGGER IF EXISTS trg_b27_explanation_consequence
            ON public.b27_explanation_materializations;
        DROP FUNCTION IF EXISTS public.b27_enforce_explanation_consequence();
        DROP TRIGGER IF EXISTS trg_trust_access_log_witness_immutability
            ON public.trust_access_log;
        DROP FUNCTION IF EXISTS
            public.trust_access_log_witness_immutability_guard();
        ALTER TABLE public.b27_explanation_materializations
            DROP CONSTRAINT IF EXISTS ck_b27_template_registry_hash_shape;
        ALTER TABLE public.b27_explanation_materializations
            DROP CONSTRAINT IF EXISTS
                fk_b27_explanation_materializations_source_issuance;
        ALTER TABLE public.b28_simulation_requests
            DROP CONSTRAINT IF EXISTS fk_b28_simulation_requests_source_issuance;
        ALTER TABLE public.b27_explanation_materializations
            DROP COLUMN IF EXISTS explanation_template_registry_hash; -- # CI:DESTRUCTIVE_OK
        ALTER TABLE public.b27_explanation_materializations
            DROP COLUMN IF EXISTS source_issuance_envelope_hash; -- # CI:DESTRUCTIVE_OK
        ALTER TABLE public.b28_simulation_requests
            DROP COLUMN IF EXISTS source_issuance_envelope_hash; -- # CI:DESTRUCTIVE_OK
        DROP TABLE IF EXISTS public.b27_narrative_template_registry; -- # CI:DESTRUCTIVE_OK
        DROP TABLE IF EXISTS public.b27_narrative_templates; -- # CI:DESTRUCTIVE_OK
        """
    )
