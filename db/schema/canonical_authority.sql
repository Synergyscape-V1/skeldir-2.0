-- B2.6-P2 Corrective IV canonical authority companion.
--
-- db/schema/canonical_schema.sql is produced by
--   pg_dump --schema-only --no-owner --no-privileges
-- so it carries object shape but no privilege physics. This companion
-- carries exactly the P2 authority grants the migrations establish, so
-- that every supported database construction path yields the same P2
-- authority universe:
--
--   path A:  empty / predecessor -> alembic upgrade head
--   path B:  roles (prepare_migration_authority_boundary.py)
--            + canonical_schema.sql + THIS file
--
-- scripts/ci/assert_b26_p2_bootstrap_authority_equivalence.py proves the
-- two paths equivalent (table/column grants, function EXECUTE, RLS,
-- policies). Apply with psql as a superuser/migration owner AFTER
-- canonical_schema.sql. app_worker grants are existence-guarded, mirroring
-- the migrations, so bare-role environments keep working.
--
-- Source of truth for each statement is the migration named in the
-- section header. If a migration changes P2 grants, this file must
-- change with it (the equivalence proof REDs otherwise).

-- === 202609170001 Corrective III: least-privilege dispatch/outbox ===
REVOKE INSERT, UPDATE ON TABLE public.b23_match_task_dispatches FROM app_rw;
GRANT SELECT ON TABLE public.b23_match_task_dispatches TO app_rw;
GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_match_task_dispatches TO app_user;
GRANT SELECT ON TABLE public.b23_match_task_dispatches TO app_ro;
GRANT SELECT, INSERT, UPDATE ON TABLE public.b26_p2_execution_outbox TO app_user;
GRANT SELECT ON TABLE public.b26_p2_execution_outbox TO app_rw;
GRANT SELECT ON TABLE public.b26_p2_execution_outbox TO app_ro;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        GRANT SELECT ON TABLE public.b23_match_task_dispatches TO app_worker;
        GRANT SELECT ON TABLE public.b26_p2_execution_outbox TO app_worker;
    END IF;
END $$;

-- === 202609170001 Corrective III: admission directory (bearer-keyed) ===
-- No RLS by design (exact task_id lookup only; enforced by
-- scripts/security/phase4_enforcement_probe.py grant-shape rule).
GRANT SELECT, INSERT ON TABLE public.b26_p2_task_authority_directory TO app_user;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        GRANT SELECT ON TABLE public.b26_p2_task_authority_directory TO app_worker;
    END IF;
END $$;

-- === 202609170001 Corrective III: constrained admission resolver ===
REVOKE ALL ON FUNCTION public.b26_p2_resolve_dispatch_authority(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.b26_p2_resolve_dispatch_authority(text) TO app_user;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        GRANT EXECUTE ON FUNCTION public.b26_p2_resolve_dispatch_authority(text) TO app_worker;
    END IF;
END $$;

-- === 202609180001 Corrective IV: worker delivery-state writes ===
-- Column-scoped UPDATE only: identity columns stay trigger-immutable for
-- every principal. The worker advances pending_publish -> published ->
-- conducted and backs off attempts; it cannot mint authority.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        EXECUTE 'GRANT UPDATE (delivery_state, publish_attempts,'
            ' last_publish_error, updated_at)'
            ' ON TABLE public.b23_match_task_dispatches TO app_worker';
        EXECUTE 'GRANT UPDATE (state, publish_attempts,'
            ' last_publish_error, next_retry_at, updated_at)'
            ' ON TABLE public.b26_p2_execution_outbox TO app_worker';
        EXECUTE 'GRANT SELECT ON TABLE public.tenants TO app_worker';
    END IF;
END $$;
