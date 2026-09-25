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

-- === 202609190001 Corrective V: one execution tuple, conducted gate ===
-- The tuple UNIQUE + composite FKs carry no GRANT vocabulary (constraints,
-- not privileges) and therefore need no companion statements; they arrive
-- via canonical_schema.sql (pg_dump shape). What this companion carries is
-- the V privilege physics: recovery principals, conduction receipts and
-- quarantine readability, and the gate/staleness routine EXECUTE shape.
-- Source of truth for each statement is the 202609190001 migration.
-- If the migration changes V grants, this file must change with it (the
-- equivalence proof REDs otherwise).

-- Recovery principals exist in provisioned lanes (prepare script); the
-- migration grants them existence-guarded, so bare-role lanes keep
-- working. This companion runs after roles are provisioned; the guards
-- below keep direct application of this file equally safe.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
        GRANT USAGE ON SCHEMA public TO app_relay;
        GRANT SELECT ON TABLE public.tenants TO app_relay;
        GRANT SELECT ON TABLE public.b23_match_task_dispatches TO app_relay;
        GRANT SELECT ON TABLE public.b26_p2_execution_outbox TO app_relay;
        GRANT SELECT ON TABLE public.webhook_ingress_identities TO app_relay;
        GRANT UPDATE (delivery_state, publish_attempts, last_publish_error, updated_at)
            ON TABLE public.b23_match_task_dispatches TO app_relay;
        GRANT UPDATE (state, publish_attempts, last_publish_error, next_retry_at, updated_at)
            ON TABLE public.b26_p2_execution_outbox TO app_relay;
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.kombu_message TO app_relay;
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.kombu_queue TO app_relay;
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_taskmeta TO app_relay;
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_tasksetmeta TO app_relay;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_relay;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_beat') THEN
        GRANT USAGE ON SCHEMA public TO app_beat;
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.kombu_message TO app_beat;
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.kombu_queue TO app_beat;
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_taskmeta TO app_beat;
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_tasksetmeta TO app_beat;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_beat;
    END IF;
END $$;

-- === 202609190001 Corrective V: conduction receipts (worker-written) ===
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        GRANT SELECT, INSERT ON TABLE public.b26_p2_conduction_receipts TO app_worker;
        GRANT SELECT ON TABLE public.b26_p2_execution_quarantine TO app_worker;
    END IF;
END $$;
GRANT SELECT ON TABLE public.b26_p2_conduction_receipts TO app_ro;
GRANT SELECT ON TABLE public.b26_p2_execution_quarantine TO app_ro;
GRANT SELECT ON TABLE public.b26_p2_execution_quarantine TO app_user;

-- === 202609190001 Corrective V: conduction gate (worker-only) ===
REVOKE ALL ON FUNCTION public.b26_p2_mark_conducted(text) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        GRANT EXECUTE ON FUNCTION public.b26_p2_mark_conducted(text) TO app_worker;
    END IF;
END $$;

-- === 202609190001 Corrective V: staleness signal ===
REVOKE ALL ON FUNCTION public.b26_p2_stale_unconducted(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.b26_p2_stale_unconducted(integer) TO app_user;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        GRANT EXECUTE ON FUNCTION public.b26_p2_stale_unconducted(integer) TO app_worker;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
        GRANT EXECUTE ON FUNCTION public.b26_p2_stale_unconducted(integer) TO app_relay;
    END IF;
END $$;

-- === 202609200001 Corrective VI: sovereign root, closed synthesis ===
-- Source of truth is the 202609200001 migration. Direct receipt
-- synthesis ends on every lane (worker/user INSERT revoked); the only
-- receipt writer is the SECURITY DEFINER record function (worker-only
-- EXECUTE). The ambient INSERT default that created the V lane
-- divergence is revoked going forward (SELECT default preserved for
-- runtime readability; future writes require explicit governed GRANTs).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        REVOKE INSERT ON TABLE public.b26_p2_conduction_receipts FROM app_worker;
    END IF;
END $$;
REVOKE INSERT ON TABLE public.b26_p2_conduction_receipts FROM app_user;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.b26_p2_execution_quarantine FROM app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE migration_owner IN SCHEMA public
    REVOKE INSERT ON TABLES FROM app_user;

-- === 202609200001 Corrective VI: transport/result telemetry is not truth ===
-- FAILURE is the only result-backend state that can terminalize (hide) a
-- stale execution, so exactly that status is closed to non-transport
-- principals at the database plane (b26_p2_enforce_result_integrity
-- trigger below, mirrored from the migration). PENDING/SUCCESS/STARTED
-- keep flowing for least-privilege topologies. The transport grants
-- mirror the 006 celery foundation on both lanes; the trigger constrains
-- FAILURE identically wherever the tables exist.
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_taskmeta TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_tasksetmeta TO app_user;

-- === 202609200001 Corrective VI: receipt record function (worker-only) ===
-- Corrective VIII: the VII 3-argument overload is dropped (unbound path);
-- the bound 4-argument form carries the same least-privilege grants.
REVOKE ALL ON FUNCTION public.b26_p2_record_conduction_receipt(text, text, integer, text) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        GRANT EXECUTE ON FUNCTION
            public.b26_p2_record_conduction_receipt(text, text, integer, text)
            TO app_worker;
    END IF;
END $$;

-- === 202609200001 Corrective VI: relay operational reads ===
-- The relay is the shipping consumer of stale/quarantine/disposition
-- state (sweep log + beat-scheduled evaluator execution). Reads only;
-- no execution authority, no gate/resolver EXECUTE, no receipt writes.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
        GRANT SELECT ON TABLE public.b26_p2_execution_quarantine TO app_relay;
        GRANT SELECT ON TABLE public.worker_failed_jobs TO app_relay;
    END IF;
END $$;

-- === 202609200001 Corrective VI: total disposition law ===
REVOKE ALL ON FUNCTION public.b26_p2_operational_disposition(text, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.b26_p2_operational_disposition(text, integer) TO app_user;
GRANT EXECUTE ON FUNCTION public.b26_p2_operational_disposition(text, integer) TO app_ro;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
        GRANT EXECUTE ON FUNCTION
            public.b26_p2_operational_disposition(text, integer)
            TO app_relay;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        GRANT EXECUTE ON FUNCTION
            public.b26_p2_operational_disposition(text, integer)
            TO app_worker;
    END IF;
END $$;

-- === 202609200001 Corrective VI: canonical window helpers ===
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        GRANT EXECUTE ON FUNCTION
            public.b26_p2_canonical_day_start(timestamptz) TO app_worker;
        GRANT EXECUTE ON FUNCTION
            public.b26_p2_canonical_day_end(timestamptz) TO app_worker;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
        GRANT EXECUTE ON FUNCTION
            public.b26_p2_canonical_day_start(timestamptz) TO app_relay;
        GRANT EXECUTE ON FUNCTION
            public.b26_p2_canonical_day_end(timestamptz) TO app_relay;
    END IF;
END $$;

-- === 202609210001 Corrective VII: policy authority (global read) ===
-- Source of truth is the 202609210001 migration. Single-row governed P2
-- identity (v2 + semantic/source SHAs); both lanes carry identical rows.
-- Explicit REVOKE converges the ambient INSERT default (same V divergence
-- pattern): runtime holds SELECT only; writes are owner-only.
REVOKE ALL ON TABLE public.b26_p2_scope_policy_authority FROM app_user;
REVOKE ALL ON TABLE public.b26_p2_scope_policy_authority FROM app_ro;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        REVOKE ALL ON TABLE public.b26_p2_scope_policy_authority FROM app_worker;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
        REVOKE ALL ON TABLE public.b26_p2_scope_policy_authority FROM app_relay;
    END IF;
END $$;
GRANT SELECT ON TABLE public.b26_p2_scope_policy_authority TO app_user;
GRANT SELECT ON TABLE public.b26_p2_scope_policy_authority TO app_ro;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        GRANT SELECT ON TABLE public.b26_p2_scope_policy_authority TO app_worker;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
        GRANT SELECT ON TABLE public.b26_p2_scope_policy_authority TO app_relay;
    END IF;
END $$;

-- === 202609210001 Corrective VII: evaluator heartbeat (relay writes, all read) ===
-- Source of truth is the 202609210001 migration. Monitor-of-monitor:
-- evaluator (relay queue/principal) ticks per tenant; API health
-- (independent failure domain) observes ticks to detect evaluator absence.
REVOKE ALL ON TABLE public.b26_p2_evaluator_heartbeat FROM app_user;
REVOKE ALL ON TABLE public.b26_p2_evaluator_heartbeat FROM app_ro;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
        REVOKE ALL ON TABLE public.b26_p2_evaluator_heartbeat FROM app_relay;
        GRANT SELECT, INSERT, UPDATE ON TABLE public.b26_p2_evaluator_heartbeat TO app_relay;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        REVOKE ALL ON TABLE public.b26_p2_evaluator_heartbeat FROM app_worker;
        GRANT SELECT ON TABLE public.b26_p2_evaluator_heartbeat TO app_worker;
    END IF;
END $$;
GRANT SELECT ON TABLE public.b26_p2_evaluator_heartbeat TO app_user;
GRANT SELECT ON TABLE public.b26_p2_evaluator_heartbeat TO app_ro;

-- === 202609220001 Corrective VIII: meaning binding + heartbeat integrity ===
-- Source of truth is the 202609220001 migration. Same-version policy
-- meaning is immutable (trigger in canonical_schema); runtime roles hold
-- no UPDATE/DELETE on the policy row. Heartbeat direct writes are revoked
-- from the monitored relay credential; the single SECURITY DEFINER
-- evaluation function recomputes the counts, so invoking it IS the
-- governed evaluation. The bound 4-argument recorder keeps worker-only
-- EXECUTE (see the amended VI block above).
REVOKE UPDATE, DELETE ON TABLE public.b26_p2_scope_policy_authority
    FROM app_user, app_worker, app_relay, app_beat, app_ro, app_rw;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
        REVOKE INSERT, UPDATE, DELETE ON TABLE public.b26_p2_evaluator_heartbeat FROM app_relay;
    END IF;
END $$;
REVOKE ALL ON FUNCTION public.b26_p2_record_evaluator_heartbeat(integer) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
        GRANT EXECUTE ON FUNCTION public.b26_p2_record_evaluator_heartbeat(integer) TO app_relay;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_beat') THEN
        GRANT EXECUTE ON FUNCTION public.b26_p2_record_evaluator_heartbeat(integer) TO app_beat;
    END IF;
END $$;

-- === 202609230001 Corrective IX: canonical consequence authority ===
-- Source of truth is the 202609230001 migration. The sovereign DB mirror
-- of the canonical P2 scope (consumed by the recorder and the gate alike)
-- is readable by the worker and the API issuer; it writes nothing and
-- holds no table authority.
REVOKE ALL ON FUNCTION public.b26_p2_canonical_scope_identity_for_window(uuid, timestamptz, timestamptz) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        GRANT EXECUTE ON FUNCTION public.b26_p2_canonical_scope_identity_for_window(uuid, timestamptz, timestamptz) TO app_worker;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
        GRANT EXECUTE ON FUNCTION public.b26_p2_canonical_scope_identity_for_window(uuid, timestamptz, timestamptz) TO app_user;
    END IF;
END $$;

-- === 202609230001 Corrective IX: scheduler liveness separated ===
-- Source of truth is the 202609230001 migration. Scheduler liveness is
-- writable only by the beat principal; manual evaluation (relay) cannot
-- manufacture scheduler health. Reads mirror the evaluator-heartbeat
-- shape (beat writes, issuer/relay read).
REVOKE ALL ON TABLE public.b26_p2_scheduler_heartbeat FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_beat') THEN
        GRANT SELECT, INSERT, UPDATE ON TABLE public.b26_p2_scheduler_heartbeat TO app_beat;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
        GRANT SELECT ON TABLE public.b26_p2_scheduler_heartbeat TO app_user;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
        GRANT SELECT ON TABLE public.b26_p2_scheduler_heartbeat TO app_relay;
    END IF;
END $$;
REVOKE ALL ON FUNCTION public.b26_p2_record_scheduler_heartbeat() FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_beat') THEN
        GRANT EXECUTE ON FUNCTION public.b26_p2_record_scheduler_heartbeat() TO app_beat;
    END IF;
END $$;

-- === 202609240001 Corrective X: single normalization authority ===
-- Source of truth is the 202609240001 migration. The ASCII-strip
-- normalization family and the per-candidate classifier are the only
-- P2 meaning implementation; the worker and the API issuer observe
-- dispositions through them (thin adapters, no independent
-- classification). They write nothing and hold no table authority.
REVOKE ALL ON FUNCTION public.b26_p2_ascii_strip(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.b26_p2_strip_provider_token(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.b26_p2_strip_currency_token(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.b26_p2_normalize_provider(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.b26_p2_normalize_currency(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.b26_p2_classify_candidate(uuid, text, text, timestamptz, timestamptz, timestamptz, text, text) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
        GRANT EXECUTE ON FUNCTION public.b26_p2_ascii_strip(text) TO app_worker;
        GRANT EXECUTE ON FUNCTION public.b26_p2_strip_provider_token(text) TO app_worker;
        GRANT EXECUTE ON FUNCTION public.b26_p2_strip_currency_token(text) TO app_worker;
        GRANT EXECUTE ON FUNCTION public.b26_p2_normalize_provider(text) TO app_worker;
        GRANT EXECUTE ON FUNCTION public.b26_p2_normalize_currency(text) TO app_worker;
        GRANT EXECUTE ON FUNCTION public.b26_p2_classify_candidate(uuid, text, text, timestamptz, timestamptz, timestamptz, text, text) TO app_worker;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
        GRANT EXECUTE ON FUNCTION public.b26_p2_ascii_strip(text) TO app_user;
        GRANT EXECUTE ON FUNCTION public.b26_p2_strip_provider_token(text) TO app_user;
        GRANT EXECUTE ON FUNCTION public.b26_p2_strip_currency_token(text) TO app_user;
        GRANT EXECUTE ON FUNCTION public.b26_p2_normalize_provider(text) TO app_user;
        GRANT EXECUTE ON FUNCTION public.b26_p2_normalize_currency(text) TO app_user;
        GRANT EXECUTE ON FUNCTION public.b26_p2_classify_candidate(uuid, text, text, timestamptz, timestamptz, timestamptz, text, text) TO app_user;
    END IF;
END $$;

-- === 202609240001 Corrective X: effect-bound conducted/receipt guards ===
-- Source of truth is the 202609240001 migration. Guard functions fire
-- through the trigger mechanism only (no EXECUTE grant is required for
-- trigger firing, proven live); the default PUBLIC grant is revoked so
-- no runtime principal holds a direct path to the guard bodies.
REVOKE ALL ON FUNCTION public.b26_p2_guard_conducted_transition() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.b26_p2_guard_conduction_receipt() FROM PUBLIC;

-- === 202609240001 Corrective X: evidence-backed provenance ===
-- Source of truth is the 202609240001 migration. Evidence rows are
-- written only by the SECURITY DEFINER attester (EXECUTE app_user);
-- no runtime principal holds direct table authority. The attester is
-- the sole promotion path from unknown_legacy.
REVOKE ALL ON TABLE public.b26_p2_provenance_evidence FROM PUBLIC;
REVOKE ALL ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
        GRANT EXECUTE ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text) TO app_user;
    END IF;
END $$;

-- === 202609240001 Corrective X: beat-plane tenant enumeration ===
-- Source of truth is the 202609240001 migration. The scheduler-plane
-- ticker must list tenants to tick per-tenant heartbeats; the beat
-- credential holds column-scoped SELECT(id) and nothing else on the
-- tenant registry.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_beat') THEN
        GRANT SELECT (id) ON TABLE public.tenants TO app_beat;
    END IF;
END $$;

-- === 202609240002 Corrective XI: dedicated ingress principal ===
-- Source of truth is the 202609240002 migration. Only the process
-- boundary that verifies provider authentication (the API ingress
-- path on the dedicated ingress credential) may author
-- authenticity_verified or execute the witness/attester. Ordinary
-- application authority is revoked from the attester. The ingress
-- principal holds ingress persistence alone: it cannot write B2.3
-- verdicts, mark P2 conducted, mutate policy, or reach any other
-- P2 table. The generic worker holds no ingress capability at all
-- (Procfile pins its DSN to the worker credential).
DO $$
BEGIN
    -- Predecessor-compatible topology rule (mirrors the XI
    -- migration): the EXECUTE grant follows the live role census,
    -- so lanes without the ingress principal keep Corrective-X
    -- attestation semantics bit-for-bit.
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            REVOKE ALL ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text) FROM app_user;
        END IF;
        GRANT USAGE ON SCHEMA public TO app_ingress;
        GRANT SELECT, INSERT, UPDATE ON TABLE public.webhook_ingress_identities TO app_ingress;
        GRANT SELECT ON TABLE public.tenants TO app_ingress;
        GRANT SELECT ON TABLE public.attribution_events TO app_ingress;
        GRANT SELECT ON TABLE public.b23_match_task_dispatches TO app_ingress;
        GRANT SELECT ON TABLE public.b26_p2_provenance_evidence TO app_ingress;
        GRANT EXECUTE ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid) TO app_ingress;
        GRANT EXECUTE ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text) TO app_ingress;
    ELSE
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT EXECUTE ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text) TO app_user;
        END IF;
    END IF;
END $$;

-- === 202609240002 Corrective XI: unforgeable witness relation ===
-- Source of truth is the 202609240002 migration. Witness rows prove a
-- governed authenticated-ingress consequence ran; they appear only
-- through the SECURITY DEFINER witness function (EXECUTE app_ingress
-- alone). No runtime principal holds direct table authority, so no
-- downstream caller can invent authentication evidence. The witness
-- table shape (but not its grants) arrives via canonical_schema.sql.
REVOKE ALL ON TABLE public.b26_p2_ingress_auth_witness FROM PUBLIC;
DO $$
DECLARE _r text;
BEGIN
    FOREACH _r IN ARRAY ARRAY[
        'app_user', 'app_worker', 'app_relay', 'app_beat',
        'app_rw', 'app_ro', 'app_ingress',
        'app_dispatch_publisher', 'app_celery_transport'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = _r) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE public.b26_p2_ingress_auth_witness FROM %I',
                _r
            );
        END IF;
    END LOOP;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
        GRANT SELECT ON TABLE public.b26_p2_ingress_auth_witness TO app_ingress;
    END IF;
END $$;
REVOKE ALL ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.b26_p2_enforce_dispatch_quarantine_exclusion() FROM PUBLIC;

-- === 202609240002 Corrective XI: P3 eligibility predicate ===
-- Source of truth is the 202609240002 migration. The predicate is
-- read-only classification consumed by P3; it mints nothing and no P3
-- principal can override it. Runtime roles hold EXECUTE and nothing
-- else on the underlying state through this function.
REVOKE ALL ON FUNCTION public.b26_p2_state_eligible_for_p3(text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.b26_p2_xi_invariant_oracle() FROM PUBLIC;
DO $$
DECLARE _r text;
BEGIN
    FOREACH _r IN ARRAY ARRAY[
        'app_user', 'app_worker', 'app_relay', 'app_beat', 'app_ingress'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = _r) THEN
            EXECUTE format(
                'GRANT EXECUTE ON FUNCTION public.b26_p2_state_eligible_for_p3(text, uuid) TO %I',
                _r
            );
        END IF;
    END LOOP;
END $$;
