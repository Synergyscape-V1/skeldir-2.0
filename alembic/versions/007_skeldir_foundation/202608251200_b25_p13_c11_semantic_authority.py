"""B2.5-P13 C11: semantic authority, publisher custody, and replan lineage.

Revision ID: 202608251200
Revises: 202608250900
"""

from __future__ import annotations


from alembic import op

#: The registry seed, embedded as data rather than imported from the
#: application.
#:
#: A migration is a historical record. If it computed this seed from live
#: policy modules it would write whatever those modules happen to say on
#: the day it runs, so a fresh database and an existing one could disagree
#: about what a version identifier meant -- which is the drift the registry
#: exists to prevent. Frozen here, this revision states what these
#: identifiers denoted when it was written, permanently.
#:
#: It also removes the only `from app...` import in any migration in this
#: tree; alembic invocations that do not put backend on sys.path failed at
#: revision-map build.
CONFIDENCE_POLICY_VERSION = 'b24-p10-confidence-policy-v1'
CONFIDENCE_SEMANTICS_VERSION = 'b24-p10-confidence-semantics-v1'
CURRENT_POLICY_BUNDLE_HASH = 'b5757b2f4419091aabd97bf5906809260cb2a7bad01edeabd604668380a6301c'
SEMANTIC_MANIFEST_JSON = '{"components":{"confidence_policy":{"semantics":{"available_requires":["diagnostic_status=passed","credible_interval_status=available","artifact_identity_present","single_currency"],"money_authority":"deterministic_minor_units_only","width_ratio_high_max":0.1,"width_ratio_medium_max":0.25},"semantics_version":"b24-p10-confidence-semantics-v1","version":"b24-p10-confidence-policy-v1"},"diagnostic_policy":{"semantics":{"allowed_interval_targets":["mu"],"diagnostic_target_coords":{},"diagnostic_target_filter_version":"b24-p7-target-filter-v1","diagnostic_target_var_names":["mu"],"divergence_count_threshold":0,"ess_min_threshold":400.0,"excluded_deterministic_var_names":["observed_signal"],"finite_value_policy":"required","hdi_probability":0.95,"interval_policy_version":"b24-p7-interval-policy-v1","interval_target_coords":{},"interval_target_var_names":["mu"],"max_diagnostic_coords":8,"max_diagnostic_elements":4096,"max_diagnostic_variables":4,"max_hdi_elements":4,"max_interval_dimensions":1,"max_interval_elements":4,"max_interval_summary_bytes":2048,"min_chains":4,"min_samples_actual":1,"r_hat_max_threshold":1.01},"version":"b24-p7-diagnostic-policy-v2"},"inference_profile":{"semantics":{"celery_hard_time_limit_seconds":300,"celery_soft_time_limit_seconds":270,"dispatch_lease_recovery_margin_seconds":30,"fit_execution_budget_seconds":240,"observed_posterior_correspondence_required":true,"runtime_correspondence_required":true,"sampler_supervisor_deadline_seconds":240},"version":"b24-inference-profile-v2"},"runtime_policy":{"semantics":{"blas_total_threads":1,"celery_hard_time_limit_seconds":300,"celery_soft_time_limit_seconds":270,"pymc_chains":4,"pymc_cores":1,"sampler_supervisor_deadline_seconds":240,"worker_concurrency":1,"worker_sampler_explicit_runtime_record":true},"version":"b24-p5-runtime-policy-v2"},"sampling_policy":{"semantics":{"blas_cores":1,"chains":4,"cores":1,"draws_per_chain":1000,"init":"jitter+adapt_diag","posterior_draws_total":4000,"target_accept":0.9,"total_chain_iterations":8000,"tune_per_chain":1000},"version":"b24-p6-sampling-policy-v2"}},"schema_version":"b24-inference-policy-manifest-v1"}'
COMPONENT_DIGESTS_JSON = '{"confidence_policy":"e7f1627ba3f0654b1891cb9484735cc54ead291471dc66ed7074a4eeee66d862","diagnostic_policy":"0022df7fb2555854fcefb5f5f3f48470e65990168a6837a821c87b2ec7f49fdc","inference_profile":"f484b4bfaac96a874f84c6a747d0b9139f19d38377a74515fb179898d2736601","runtime_policy":"1692cf404180c2fdb370c7c33305aca37ca2e839519beb617ed86cf87bd881c2","sampling_policy":"b9bda475d8a2027798f7231ad723dc74b76c70b279eba1f5cc64f92225fc0404"}'
POLICY_TUPLE = {'inference_profile_version': 'b24-inference-profile-v2', 'runtime_policy_version': 'b24-p5-runtime-policy-v2', 'sampling_policy_version': 'b24-p6-sampling-policy-v2', 'diagnostic_policy_version': 'b24-p7-diagnostic-policy-v2'}


revision = "202608251200"
down_revision = "202608250900"
branch_labels = None
depends_on = None


def _literal(value: object) -> str:
    return str(value).replace("'", "''")


def _role_exists(role_name: str) -> bool:
    row = (
        op.get_bind()
        .exec_driver_sql("SELECT to_regrole(%s)", (role_name,))
        .scalar_one()
    )
    return row is not None


def _execute_if_role_exists(role_name: str, statement: str) -> None:
    if _role_exists(role_name):
        op.get_bind().exec_driver_sql(statement)


def upgrade() -> None:
    manifest = _literal(SEMANTIC_MANIFEST_JSON)
    digests = _literal(COMPONENT_DIGESTS_JSON)
    policy_tuple = POLICY_TUPLE

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b24_inference_policy_registry (
            policy_bundle_hash varchar(64) PRIMARY KEY,
            inference_profile_version varchar(128) NOT NULL,
            runtime_policy_version varchar(128) NOT NULL,
            sampling_policy_version varchar(128) NOT NULL,
            diagnostic_policy_version varchar(128) NOT NULL,
            confidence_policy_version varchar(128) NOT NULL,
            confidence_semantics_version varchar(128) NOT NULL,
            semantic_manifest jsonb NOT NULL,
            component_digests jsonb NOT NULL,
            identity_scheme varchar(64) NOT NULL
                DEFAULT 'canonical-semantic-manifest-sha256-v1',
            registered_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_b24_policy_registry_hash
                CHECK (policy_bundle_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT uq_b24_policy_registry_tuple UNIQUE (
                policy_bundle_hash,
                inference_profile_version,
                runtime_policy_version,
                sampling_policy_version,
                diagnostic_policy_version
            )
        );
        """
    )
    op.get_bind().exec_driver_sql(
        f"""
        INSERT INTO public.b24_inference_policy_registry (
            policy_bundle_hash,
            inference_profile_version,
            runtime_policy_version,
            sampling_policy_version,
            diagnostic_policy_version,
            confidence_policy_version,
            confidence_semantics_version,
            semantic_manifest,
            component_digests
        ) VALUES (
            '{CURRENT_POLICY_BUNDLE_HASH}',
            '{_literal(policy_tuple["inference_profile_version"])}',
            '{_literal(policy_tuple["runtime_policy_version"])}',
            '{_literal(policy_tuple["sampling_policy_version"])}',
            '{_literal(policy_tuple["diagnostic_policy_version"])}',
            '{_literal(CONFIDENCE_POLICY_VERSION)}',
            '{_literal(CONFIDENCE_SEMANTICS_VERSION)}',
            '{manifest}'::jsonb,
            '{digests}'::jsonb
        ) ON CONFLICT (policy_bundle_hash) DO NOTHING;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_reject_policy_registry_rewrite()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'b24_policy_registry_immutable';
        END
        $$;

        DROP TRIGGER IF EXISTS trg_b24_policy_registry_immutable
            ON public.b24_inference_policy_registry;
        CREATE TRIGGER trg_b24_policy_registry_immutable
            BEFORE UPDATE OR DELETE ON public.b24_inference_policy_registry
            FOR EACH ROW EXECUTE FUNCTION public.b24_reject_policy_registry_rewrite();
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b24_fit_policy_replan_lineage (
            tenant_id uuid NOT NULL,
            fit_id uuid NOT NULL,
            transition_sequence integer NOT NULL,
            from_policy_bundle_hash varchar(64) NOT NULL,
            to_policy_bundle_hash varchar(64) NOT NULL,
            from_inference_profile_version varchar(128) NOT NULL,
            to_inference_profile_version varchar(128) NOT NULL,
            from_runtime_policy_version varchar(128) NOT NULL,
            to_runtime_policy_version varchar(128) NOT NULL,
            from_sampling_policy_version varchar(128) NOT NULL,
            to_sampling_policy_version varchar(128) NOT NULL,
            -- A pre-C11 queued row can honestly have no diagnostic identifier.
            -- The transition preserves that unknown rather than fabricating it.
            from_diagnostic_policy_version varchar(128),
            to_diagnostic_policy_version varchar(128) NOT NULL,
            actor_session_user varchar(128) NOT NULL,
            transitioned_at timestamptz NOT NULL,
            PRIMARY KEY (tenant_id, fit_id, transition_sequence),
            CONSTRAINT fk_b24_replan_lineage_fit FOREIGN KEY (tenant_id, fit_id)
                REFERENCES public.bayesian_model_fits (tenant_id, id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_b24_replan_lineage_sequence
                CHECK (transition_sequence > 0),
            CONSTRAINT ck_b24_replan_lineage_transition
                CHECK (from_policy_bundle_hash <> to_policy_bundle_hash)
        );

        CREATE INDEX IF NOT EXISTS ix_b24_fit_policy_replan_lineage_fit
            ON public.b24_fit_policy_replan_lineage
            (tenant_id, fit_id, transition_sequence ASC);

        ALTER TABLE public.b24_fit_policy_replan_lineage ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.b24_fit_policy_replan_lineage FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation_b24_fit_policy_replan_lineage
            ON public.b24_fit_policy_replan_lineage;
        CREATE POLICY tenant_isolation_b24_fit_policy_replan_lineage
            ON public.b24_fit_policy_replan_lineage
            FOR SELECT
            USING (
                tenant_id = NULLIF(
                    current_setting('app.current_tenant_id', true), ''
                )::uuid
            );
        DROP POLICY IF EXISTS c11_trigger_insert_b24_fit_policy_replan_lineage
            ON public.b24_fit_policy_replan_lineage;
        CREATE POLICY c11_trigger_insert_b24_fit_policy_replan_lineage
            ON public.b24_fit_policy_replan_lineage
            FOR INSERT
            WITH CHECK (
                current_user = pg_get_userbyid(
                    (
                        SELECT relowner FROM pg_class
                        WHERE oid = 'public.b24_fit_policy_replan_lineage'::regclass
                    )
                )
            );
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_reject_replan_lineage_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'b24_replan_lineage_append_only';
        END
        $$;

        DROP TRIGGER IF EXISTS trg_b24_replan_lineage_append_only
            ON public.b24_fit_policy_replan_lineage;
        CREATE TRIGGER trg_b24_replan_lineage_append_only
            BEFORE UPDATE OR DELETE ON public.b24_fit_policy_replan_lineage
            FOR EACH ROW EXECUTE FUNCTION public.b24_reject_replan_lineage_mutation();
        """
    )

    # Tuple/hash consistency and history are database physics.  Unknown legacy
    # queued rows may exist, but they cannot become available and must be
    # explicitly replanned to a registered semantic bundle before sampling.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_enforce_c11_policy_provenance()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
            registry_match boolean;
            available_bucket boolean;
        BEGIN
            available_bucket := NEW.confidence_bucket::text IN ('low','medium','high');

            IF TG_OP = 'UPDATE'
               AND NEW.policy_bundle_hash IS DISTINCT FROM OLD.policy_bundle_hash THEN
                IF OLD.sampling_started_at IS NOT NULL THEN
                    RAISE EXCEPTION 'b24_policy_replan_after_sampling_forbidden';
                END IF;
                IF NEW.policy_replan_count <> OLD.policy_replan_count + 1
                   OR NEW.superseded_policy_bundle_hash IS DISTINCT FROM OLD.policy_bundle_hash
                   OR NEW.policy_replanned_at IS NULL THEN
                    RAISE EXCEPTION 'b24_policy_replan_evidence_incomplete';
                END IF;

                SELECT EXISTS (
                    SELECT 1 FROM public.b24_inference_policy_registry registry
                    WHERE registry.policy_bundle_hash = NEW.policy_bundle_hash
                      AND registry.inference_profile_version = NEW.inference_profile_version
                      AND registry.runtime_policy_version = NEW.runtime_policy_version
                      AND registry.sampling_policy_version = NEW.sampling_policy_version
                      AND registry.diagnostic_policy_version = NEW.diagnostic_policy_version
                ) INTO registry_match;
                IF NOT registry_match THEN
                    RAISE EXCEPTION 'b24_policy_bundle_tuple_unknown';
                END IF;

                INSERT INTO public.b24_fit_policy_replan_lineage (
                    tenant_id, fit_id, transition_sequence,
                    from_policy_bundle_hash, to_policy_bundle_hash,
                    from_inference_profile_version, to_inference_profile_version,
                    from_runtime_policy_version, to_runtime_policy_version,
                    from_sampling_policy_version, to_sampling_policy_version,
                    from_diagnostic_policy_version, to_diagnostic_policy_version,
                    actor_session_user, transitioned_at
                ) VALUES (
                    NEW.tenant_id, NEW.id, NEW.policy_replan_count,
                    OLD.policy_bundle_hash, NEW.policy_bundle_hash,
                    OLD.inference_profile_version, NEW.inference_profile_version,
                    OLD.runtime_policy_version, NEW.runtime_policy_version,
                    OLD.sampling_policy_version, NEW.sampling_policy_version,
                    OLD.diagnostic_policy_version, NEW.diagnostic_policy_version,
                    session_user, NEW.policy_replanned_at
                );
            END IF;

            IF available_bucket THEN
                SELECT EXISTS (
                    SELECT 1 FROM public.b24_inference_policy_registry registry
                    WHERE registry.policy_bundle_hash = NEW.policy_bundle_hash
                      AND registry.inference_profile_version = NEW.inference_profile_version
                      AND registry.runtime_policy_version = NEW.runtime_policy_version
                      AND registry.sampling_policy_version = NEW.sampling_policy_version
                      AND registry.diagnostic_policy_version = NEW.diagnostic_policy_version
                      AND registry.confidence_policy_version = NEW.confidence_policy_version
                      AND registry.confidence_semantics_version = NEW.confidence_semantics_version
                ) INTO registry_match;
                IF NOT registry_match THEN
                    RAISE EXCEPTION 'b24_available_policy_provenance_unresolvable';
                END IF;
            END IF;
            RETURN NEW;
        END
        $$;

        DROP TRIGGER IF EXISTS trg_y_b24_c11_policy_provenance
            ON public.bayesian_model_fits;
        CREATE TRIGGER trg_y_b24_c11_policy_provenance
            BEFORE INSERT OR UPDATE ON public.bayesian_model_fits
            FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_c11_policy_provenance();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_policy_lineage_complete(
            p_tenant_id uuid, p_fit_id uuid
        ) RETURNS boolean
        LANGUAGE plpgsql
        STABLE
        SECURITY INVOKER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
            v_complete boolean;
        BEGIN
            -- plpgsql, not sql, so the body is resolved when it runs.
            -- canonical_schema.sql emits functions before tables, and a
            -- LANGUAGE sql body is resolved at CREATE, so this function
            -- alone could not be applied to a bare database. The query is
            -- unchanged.
            WITH fit AS (
                SELECT policy_replan_count
                FROM public.bayesian_model_fits
                WHERE tenant_id = p_tenant_id AND id = p_fit_id
            ), ordered AS (
                SELECT transition_sequence,
                       from_policy_bundle_hash,
                       to_policy_bundle_hash,
                       lag(to_policy_bundle_hash) OVER (
                           ORDER BY transition_sequence
                       ) AS prior_to
                FROM public.b24_fit_policy_replan_lineage
                WHERE tenant_id = p_tenant_id AND fit_id = p_fit_id
            ), summary AS (
                SELECT count(*)::integer AS row_count,
                       COALESCE(min(transition_sequence), 0) AS min_sequence,
                       COALESCE(max(transition_sequence), 0) AS max_sequence,
                       COALESCE(bool_and(
                           transition_sequence = 1
                           OR from_policy_bundle_hash = prior_to
                       ), true) AS chain_complete
                FROM ordered
            )
            SELECT COALESCE(
                summary.row_count = fit.policy_replan_count
                AND (
                    fit.policy_replan_count = 0
                    OR (
                        summary.min_sequence = 1
                        AND summary.max_sequence = fit.policy_replan_count
                        AND summary.chain_complete
                    )
                ),
                false
            )
            INTO v_complete
            FROM fit CROSS JOIN summary;
            RETURN COALESCE(v_complete, false);
        END
        $$;
        """
    )

    # The principal itself is the capability.  Session variables are not an
    # authorization input, so app_worker cannot mint cross-tenant authority.
    op.execute(
        """
        DROP POLICY IF EXISTS initial_dispatch_publisher_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS c11_dispatch_publisher_select
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS c11_dispatch_publisher_update
            ON public.b24_fit_dispatch_outbox;
        CREATE POLICY c11_dispatch_publisher_select
            ON public.b24_fit_dispatch_outbox FOR SELECT
            USING (session_user = 'app_dispatch_publisher');
        CREATE POLICY c11_dispatch_publisher_update
            ON public.b24_fit_dispatch_outbox FOR UPDATE
            USING (session_user = 'app_dispatch_publisher')
            WITH CHECK (session_user = 'app_dispatch_publisher');
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_assert_dispatch_publisher()
        RETURNS text
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
            IF session_user <> 'app_dispatch_publisher' THEN
                RAISE EXCEPTION 'b24_dispatch_publisher_identity_required';
            END IF;
            RETURN session_user;
        END
        $$;
        REVOKE ALL ON FUNCTION public.b24_assert_dispatch_publisher()
            FROM PUBLIC, app_user;

        REVOKE ALL ON TABLE public.b24_inference_policy_registry FROM PUBLIC;
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE  -- # CI:DESTRUCTIVE_OK - Removing the TRUNCATE privilege, not exercising it; see ADR-017.
            ON TABLE public.b24_inference_policy_registry
            FROM app_user;
        GRANT SELECT ON TABLE public.b24_inference_policy_registry
            TO app_user;

        REVOKE ALL ON TABLE public.b24_fit_policy_replan_lineage FROM PUBLIC;
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE  -- # CI:DESTRUCTIVE_OK - Removing the TRUNCATE privilege, not exercising it; see ADR-017.
            ON TABLE public.b24_fit_policy_replan_lineage
            FROM app_user;
        GRANT SELECT ON TABLE public.b24_fit_policy_replan_lineage
            TO app_user;
        """
    )
    _execute_if_role_exists(
        "app_worker",
        """
        REVOKE ALL ON FUNCTION public.b24_assert_dispatch_publisher() FROM app_worker;
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE  -- # CI:DESTRUCTIVE_OK - Removing the TRUNCATE privilege, not exercising it; see ADR-017.
            ON public.b24_inference_policy_registry FROM app_worker;
        GRANT SELECT ON public.b24_inference_policy_registry TO app_worker;
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE  -- # CI:DESTRUCTIVE_OK - Removing the TRUNCATE privilege, not exercising it; see ADR-017.
            ON public.b24_fit_policy_replan_lineage FROM app_worker;
        GRANT SELECT ON public.b24_fit_policy_replan_lineage TO app_worker;
        """,
    )
    _execute_if_role_exists(
        "app_dispatch_publisher",
        """
        GRANT USAGE ON SCHEMA public TO app_dispatch_publisher;
        REVOKE ALL ON FUNCTION public.b24_assert_dispatch_publisher()
            FROM app_dispatch_publisher;
        GRANT EXECUTE ON FUNCTION public.b24_assert_dispatch_publisher()
            TO app_dispatch_publisher;
        REVOKE ALL ON TABLE public.b24_inference_policy_registry
            FROM app_dispatch_publisher;
        GRANT SELECT ON TABLE public.b24_inference_policy_registry
            TO app_dispatch_publisher;
        REVOKE ALL ON TABLE public.b24_fit_policy_replan_lineage
            FROM app_dispatch_publisher;
        REVOKE ALL ON TABLE public.b24_fit_dispatch_outbox
            FROM app_dispatch_publisher;
        GRANT SELECT ON TABLE public.b24_fit_dispatch_outbox
            TO app_dispatch_publisher;
        GRANT UPDATE (
            status, dispatching_started_at, last_attempt_at, attempt_count,
            task_name, attempt_id, payload_hash, claim_capability,
            claim_capability_digest, claim_capability_expires_at,
            assigned_worker_generation, assignment_generation,
            assignment_expires_at, assignment_reason, updated_at,
            dispatched_at, last_error, next_attempt_at, dead_lettered_at
        ) ON public.b24_fit_dispatch_outbox TO app_dispatch_publisher;
        GRANT EXECUTE ON FUNCTION public.b24_next_active_worker_generation()
            TO app_dispatch_publisher;
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.kombu_queue
            TO app_dispatch_publisher;
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.kombu_message
            TO app_dispatch_publisher;
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.celery_taskmeta
            TO app_dispatch_publisher;
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.celery_tasksetmeta
            TO app_dispatch_publisher;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public
            TO app_dispatch_publisher;
        """,
    )

    # Existing C10 trigger remains the lease/fence authority gate, now with the
    # diagnostic component and post-sampling immutability made explicit.
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
               OR NEW.authorized_posterior_draws_total IS DISTINCT FROM OLD.authorized_posterior_draws_total
               OR NEW.superseded_policy_bundle_hash IS DISTINCT FROM OLD.superseded_policy_bundle_hash
               OR NEW.policy_replanned_at IS DISTINCT FROM OLD.policy_replanned_at
               OR NEW.policy_replan_count IS DISTINCT FROM OLD.policy_replan_count THEN
                IF OLD.sampling_started_at IS NOT NULL THEN
                    RAISE EXCEPTION 'b24_policy_provenance_sampling_immutable';
                END IF;
                IF NOT public.b24_current_dispatch_fence_valid(NEW.tenant_id, NEW.id) THEN
                    RAISE EXCEPTION 'b24_policy_bundle_write_authority_rejected';
                END IF;
            END IF;
            RETURN NEW;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_y_b24_c11_policy_provenance
            ON public.bayesian_model_fits;
        DROP FUNCTION IF EXISTS public.b24_enforce_c11_policy_provenance();
        DROP FUNCTION IF EXISTS public.b24_policy_lineage_complete(uuid, uuid);
        DROP FUNCTION IF EXISTS public.b24_assert_dispatch_publisher();
        DROP TABLE IF EXISTS public.b24_fit_policy_replan_lineage;  -- # CI:DESTRUCTIVE_OK - Controlled C11 rollback of tables this revision created; see ADR-017.
        DROP TABLE IF EXISTS public.b24_inference_policy_registry;  -- # CI:DESTRUCTIVE_OK - Controlled C11 rollback of tables this revision created; see ADR-017.
        DROP POLICY IF EXISTS c11_dispatch_publisher_select
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS c11_dispatch_publisher_update
            ON public.b24_fit_dispatch_outbox;
        """
    )
