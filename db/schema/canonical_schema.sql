--
-- PostgreSQL database dump
--

\restrict QsUcjoLVBbEIoyyMaF4RS5kfY5mMsWSbLomjXrS662qIcRJQdpcE98GuOfjq7Jd

-- Dumped from database version 15.19
-- Dumped by pg_dump version 15.15

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: auth; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA auth;


--
-- Name: security; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA security;


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: lookup_user_auth_by_login_hash(text); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.lookup_user_auth_by_login_hash(p_login_identifier_hash text) RETURNS TABLE(user_id uuid, is_active boolean, auth_provider text, password_hash text)
    LANGUAGE sql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
            SELECT
                u.id AS user_id,
                u.is_active,
                u.auth_provider,
                u.password_hash
            FROM public.users AS u
            WHERE u.login_identifier_hash = p_login_identifier_hash
            LIMIT 1
        $$;


--
-- Name: lookup_user_by_login_hash(text); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.lookup_user_by_login_hash(p_login_identifier_hash text) RETURNS TABLE(user_id uuid, is_active boolean, auth_provider text)
    LANGUAGE sql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
            SELECT
                u.id AS user_id,
                u.is_active,
                u.auth_provider
            FROM public.users AS u
            WHERE u.login_identifier_hash = p_login_identifier_hash
            LIMIT 1
        $$;


--
-- Name: b23_enforce_verdict_authorship(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b23_enforce_verdict_authorship() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
        DECLARE
            principal_is_superuser boolean;
            table_owner_oid oid;
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

            -- The migration principal owns this relation and can drop the
            -- trigger, so refusing it buys no authority either. It is already
            -- a member of app_worker where that role exists; naming ownership
            -- explicitly keeps provisioning working in the environments that
            -- migrate before any runtime role is created.
            SELECT relowner
              INTO table_owner_oid
              FROM pg_catalog.pg_class
             WHERE oid = TG_RELID;
            IF pg_catalog.pg_has_role(session_user, table_owner_oid, 'USAGE') THEN
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
        $$;


--
-- Name: b23_project_allocation_verification(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b23_project_allocation_verification() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
        DECLARE
            authority record;
        BEGIN
            SELECT verdict.*
              INTO authority
              FROM public.b23_match_verdicts AS verdict
             WHERE verdict.tenant_id = NEW.tenant_id
               AND verdict.attribution_event_id = NEW.event_id
               AND verdict.status IN ('matched_confirmed', 'adjusted')
             ORDER BY
                 CASE verdict.status WHEN 'adjusted' THEN 0 ELSE 1 END,
                 verdict.last_transition_at DESC,
                 verdict.id DESC
             LIMIT 1;

            IF FOUND THEN
                NEW.verified := true;
                NEW.verification_source := 'b23_match_verdict';
                NEW.verification_timestamp := authority.last_transition_at;
            ELSE
                NEW.verified := false;
                NEW.verification_source := NULL;
                NEW.verification_timestamp := NULL;
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: b23_refresh_allocation_verification(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b23_refresh_allocation_verification() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
        BEGIN
            IF NEW.attribution_event_id IS NULL THEN
                RETURN NEW;
            END IF;

            UPDATE public.attribution_allocations AS allocation
               SET verified = NEW.status IN ('matched_confirmed', 'adjusted'),
                   verification_source = CASE
                       WHEN NEW.status IN ('matched_confirmed', 'adjusted')
                           THEN 'b23_match_verdict'
                       ELSE NULL
                   END,
                   verification_timestamp = CASE
                       WHEN NEW.status IN ('matched_confirmed', 'adjusted')
                           THEN NEW.last_transition_at
                       ELSE NULL
                   END,
                   updated_at = transaction_timestamp()
             WHERE allocation.tenant_id = NEW.tenant_id
               AND allocation.event_id = NEW.attribution_event_id
               AND (
                   allocation.verified IS DISTINCT FROM
                       (NEW.status IN ('matched_confirmed', 'adjusted'))
                   OR allocation.verification_source IS DISTINCT FROM CASE
                       WHEN NEW.status IN ('matched_confirmed', 'adjusted')
                           THEN 'b23_match_verdict'
                       ELSE NULL
                   END
                   OR allocation.verification_timestamp IS DISTINCT FROM CASE
                       WHEN NEW.status IN ('matched_confirmed', 'adjusted')
                           THEN NEW.last_transition_at
                       ELSE NULL
                   END
               );
            RETURN NEW;
        END;
        $$;


--
-- Name: b24_assert_dispatch_publisher(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_assert_dispatch_publisher() RETURNS text
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
        BEGIN
            IF session_user <> 'app_dispatch_publisher' THEN
                RAISE EXCEPTION 'b24_dispatch_publisher_identity_required';
            END IF;
            RETURN session_user;
        END
        $$;


--
-- Name: b24_claim_fit_dispatch(uuid, uuid, text, uuid, text, text, integer, text, integer, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_claim_fit_dispatch(p_dispatch_id uuid, p_fit_id uuid, p_task_name text, p_attempt_id uuid, p_payload_hash text, p_worker_generation text, p_worker_pid integer, p_worker_process_token text, p_recovery_generation integer DEFAULT 0, p_lease_seconds integer DEFAULT 330) RETURNS TABLE(outcome text, tenant_id uuid, fit_id uuid, dispatch_id uuid, attempt_id uuid, claim_epoch integer, lease_capability text, lease_expires_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    v_row public.b24_fit_dispatch_outbox%ROWTYPE;
    v_lease text;
    v_lease_digest text;
    v_next_epoch integer;
    v_lease_seconds integer := LEAST(GREATEST(COALESCE(p_lease_seconds, 330), 30), 900);
    v_outcome text;
    v_shared_recovery_eligible boolean;
BEGIN
    PERFORM set_config('app.b24_worker_authority_access', 'on', true);
    PERFORM set_config('app.b24_dispatch_claim_access', 'on', true);

    IF NOT EXISTS (
        SELECT 1
        FROM public.b24_worker_process_authority auth
        WHERE auth.generation_id = p_worker_generation
          AND auth.pid = p_worker_pid
          AND auth.process_token_digest = public.b24_sha256_text(p_worker_process_token)
          AND auth.status = 'active'
          AND auth.revoked_at IS NULL
          AND auth.expires_at > now()
    ) THEN
        RETURN QUERY SELECT 'UNAUTHORIZED', NULL::uuid, NULL::uuid, NULL::uuid,
            NULL::uuid, NULL::integer, NULL::text, NULL::timestamptz;
        RETURN;
    END IF;

    SELECT *
    INTO v_row
    FROM public.b24_fit_dispatch_outbox outbox
    WHERE outbox.id = p_dispatch_id
      AND outbox.fit_id = p_fit_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT 'UNAUTHORIZED', NULL::uuid, NULL::uuid, NULL::uuid,
            NULL::uuid, NULL::integer, NULL::text, NULL::timestamptz;
        RETURN;
    END IF;

    v_shared_recovery_eligible := (
        COALESCE(v_row.recovery_generation, 0) > 0
        AND COALESCE(p_recovery_generation, 0) = COALESCE(v_row.recovery_generation, 0)
        AND v_row.assigned_worker_generation IS NULL
        AND v_row.assignment_reason = 'recovery_shared_eligible'
    );

    IF v_row.fit_id <> p_fit_id
       OR v_row.task_name <> p_task_name
       OR v_row.attempt_id <> p_attempt_id
       OR v_row.payload_hash <> p_payload_hash
       OR COALESCE(v_row.recovery_generation, 0) <> COALESCE(p_recovery_generation, 0)
       OR NOT COALESCE(
            v_row.assigned_worker_generation = p_worker_generation
            OR v_shared_recovery_eligible,
            false
       )
       OR v_row.assignment_expires_at IS NULL
       OR v_row.assignment_expires_at <= now() THEN
        RETURN QUERY SELECT 'UNAUTHORIZED', NULL::uuid, NULL::uuid, NULL::uuid,
            NULL::uuid, NULL::integer, NULL::text, NULL::timestamptz;
        RETURN;
    END IF;

    IF v_row.status = 'completed' THEN
        RETURN QUERY SELECT 'ALREADY_COMPLETED', v_row.tenant_id, v_row.fit_id,
            v_row.id, v_row.attempt_id, v_row.claim_epoch, NULL::text,
            v_row.lease_expires_at;
        RETURN;
    ELSIF v_row.status = 'cancelled' THEN
        v_outcome := 'CANCELLED';
    ELSIF v_row.status = 'expired' THEN
        v_outcome := 'EXPIRED';
    ELSIF v_row.status = 'superseded' THEN
        v_outcome := 'SUPERSEDED';
    ELSIF v_row.status IN ('failed_terminal', 'dead_lettered', 'quarantined') THEN
        v_outcome := 'TERMINAL_FAILURE';
    ELSIF v_row.lease_expires_at IS NOT NULL
          AND v_row.lease_expires_at > now()
          AND v_row.status IN ('leased', 'running') THEN
        RETURN QUERY SELECT 'ACTIVE_LEASE', v_row.tenant_id, v_row.fit_id,
            v_row.id, v_row.attempt_id, v_row.claim_epoch, NULL::text,
            v_row.lease_expires_at;
        RETURN;
    ELSE
        v_outcome := CASE WHEN v_row.claim_count = 0 THEN 'ACQUIRED' ELSE 'RECLAIMED' END;
    END IF;

    IF v_outcome <> 'ACQUIRED' AND v_outcome <> 'RECLAIMED' THEN
        RETURN QUERY SELECT v_outcome, v_row.tenant_id, v_row.fit_id,
            v_row.id, v_row.attempt_id, v_row.claim_epoch, NULL::text,
            v_row.lease_expires_at;
        RETURN;
    END IF;

    v_lease := encode(gen_random_bytes(32), 'hex');
    v_lease_digest := public.b24_sha256_text(v_lease);
    v_next_epoch := v_row.claim_epoch + 1;

    UPDATE public.b24_fit_dispatch_outbox outbox
    SET status = 'leased',
        claim_epoch = v_next_epoch,
        lease_capability_digest = v_lease_digest,
        lease_owner = p_worker_generation,
        lease_acquired_at = now(),
        lease_expires_at = now() + (v_lease_seconds * interval '1 second'),
        last_heartbeat_at = now(),
        claim_count = claim_count + 1,
        redelivery_count = redelivery_count + CASE WHEN v_row.claim_count > 0 THEN 1 ELSE 0 END,
        next_recovery_at = now() + (v_lease_seconds * interval '1 second'),
        claim_capability = NULL,
        claim_capability_digest = NULL,
        claim_capability_expires_at = NULL,
        updated_at = now()
    WHERE outbox.tenant_id = v_row.tenant_id
      AND outbox.id = v_row.id;

    PERFORM set_config('app.current_tenant_id', v_row.tenant_id::text, true);
    PERFORM set_config('app.b24_dispatch_id', v_row.id::text, true);
    PERFORM set_config('app.b24_attempt_id', v_row.attempt_id::text, true);
    PERFORM set_config('app.b24_claim_epoch', v_next_epoch::text, true);
    PERFORM set_config('app.b24_lease_capability', v_lease, true);

    RETURN QUERY SELECT v_outcome, v_row.tenant_id, v_row.fit_id, v_row.id,
        v_row.attempt_id, v_next_epoch, v_lease,
        now() + (v_lease_seconds * interval '1 second');
END
$$;


--
-- Name: b24_complete_fit_dispatch(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_complete_fit_dispatch() RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
        BEGIN
            UPDATE public.b24_fit_dispatch_outbox outbox
            SET status = 'completed',
                completed_at = now(),
                terminal_reason = NULL,
                updated_at = now()
            WHERE outbox.id = NULLIF(current_setting('app.b24_dispatch_id', true), '')::uuid
              AND public.b24_current_dispatch_fence_valid(outbox.tenant_id, outbox.fit_id);
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b24_dispatch_complete_fence_rejected';
            END IF;
        END
        $$;


--
-- Name: b24_complete_fit_planner_wakeup(uuid, text, bigint, boolean, integer, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_complete_fit_planner_wakeup(p_tenant_id uuid, p_lease_owner text, p_wakeup_revision bigint, p_succeeded boolean, p_quiet_period_seconds integer, p_max_wait_seconds integer) RETURNS text
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
        DECLARE
            residual_eligible integer;
            residual_next timestamptz;
            fenced boolean;
        BEGIN
            IF session_user <> 'app_worker' THEN
                RAISE EXCEPTION 'b24_worker_database_identity_required';
            END IF;
            -- Residual authority is tenant truth read under FORCE RLS. The
            -- caller must already have bound the tenant, so the obligation can
            -- never be judged against another tenant's dirty state.
            IF current_setting('app.current_tenant_id', true)
               IS DISTINCT FROM p_tenant_id::text THEN
                RAISE EXCEPTION 'b24_fit_planner_tenant_context_required';
            END IF;

            IF NOT p_succeeded THEN
                UPDATE public.b24_fit_planner_wakeups
                SET status = 'pending', lease_owner = NULL,
                    lease_expires_at = NULL, next_eligible_at = NULL,
                    updated_at = now()
                WHERE tenant_id = p_tenant_id
                  AND status = 'leased'
                  AND lease_owner = p_lease_owner;
                IF FOUND THEN
                    RETURN 'released';
                END IF;
                RETURN 'stale_revision';
            END IF;

            SELECT eligible_group_count, next_eligible_at
            INTO residual_eligible, residual_next
            FROM public.b24_fit_planner_residual_obligation(
                p_tenant_id, p_quiet_period_seconds, p_max_wait_seconds
            );

            IF COALESCE(residual_eligible, 0) > 0 THEN
                UPDATE public.b24_fit_planner_wakeups
                SET status = 'pending', lease_owner = NULL,
                    lease_expires_at = NULL, next_eligible_at = NULL,
                    updated_at = now()
                WHERE tenant_id = p_tenant_id
                  AND status = 'leased'
                  AND lease_owner = p_lease_owner
                  AND wakeup_revision = p_wakeup_revision;
                fenced := FOUND;
                IF fenced THEN
                    RETURN 'retained_eligible';
                END IF;
            ELSIF residual_next IS NOT NULL THEN
                UPDATE public.b24_fit_planner_wakeups
                SET status = 'pending', lease_owner = NULL,
                    lease_expires_at = NULL,
                    next_eligible_at = residual_next,
                    updated_at = now()
                WHERE tenant_id = p_tenant_id
                  AND status = 'leased'
                  AND lease_owner = p_lease_owner
                  AND wakeup_revision = p_wakeup_revision;
                fenced := FOUND;
                IF fenced THEN
                    RETURN 'deferred';
                END IF;
            ELSE
                DELETE FROM public.b24_fit_planner_wakeups
                WHERE tenant_id = p_tenant_id
                  AND status = 'leased'
                  AND lease_owner = p_lease_owner
                  AND wakeup_revision = p_wakeup_revision;
                fenced := FOUND;
                IF fenced THEN
                    RETURN 'deleted';
                END IF;
            END IF;

            -- Revision fence missed: newer evidence arrived while this pass ran.
            -- Release any lease this owner still holds so the newer revision is
            -- immediately runnable, and never delete it.
            UPDATE public.b24_fit_planner_wakeups
            SET status = 'pending', lease_owner = NULL,
                lease_expires_at = NULL, next_eligible_at = NULL,
                updated_at = now()
            WHERE tenant_id = p_tenant_id
              AND status = 'leased'
              AND lease_owner = p_lease_owner;
            RETURN 'stale_revision';
        END
        $$;


--
-- Name: b24_create_fit_recovery_wakeups(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_create_fit_recovery_wakeups(p_limit integer DEFAULT 25) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
        DECLARE
            v_count integer := 0;
            v_row record;
            v_generation integer;
            v_attempt_id uuid;
        BEGIN
            PERFORM set_config('app.b24_recovery_reconciler', 'on', true);

            FOR v_row IN
                SELECT *
                FROM public.b24_fit_dispatch_outbox outbox
                WHERE outbox.status IN ('dispatched', 'leased', 'running', 'failed_retryable', 'stale_recovered')
                  AND outbox.next_recovery_at <= now()
                  AND (
                      outbox.lease_expires_at IS NULL
                      OR outbox.lease_expires_at <= now()
                      OR outbox.status IN ('failed_retryable', 'stale_recovered')
                  )
                ORDER BY outbox.next_recovery_at ASC, outbox.id ASC
                LIMIT LEAST(GREATEST(COALESCE(p_limit, 25), 1), 100)
                FOR UPDATE SKIP LOCKED
            LOOP
                v_generation := v_row.recovery_generation + 1;
                v_attempt_id := gen_random_uuid();
                UPDATE public.b24_fit_dispatch_outbox outbox
                SET status = 'stale_recovered',
                    attempt_id = v_attempt_id,
                    claim_capability = NULL,
                    claim_capability_digest = NULL,
                    claim_capability_expires_at = NULL,
                    lease_capability_digest = NULL,
                    lease_expires_at = NULL,
                    assigned_worker_generation = NULL,
                    assignment_generation = assignment_generation + 1,
                    assignment_expires_at = NULL,
                    assignment_reason = 'stale_recovery',
                    recovery_generation = v_generation,
                    next_recovery_at = now() + interval '5 minutes',
                    updated_at = now()
                WHERE outbox.tenant_id = v_row.tenant_id
                  AND outbox.id = v_row.id;

                INSERT INTO public.b24_fit_recovery_outbox (
                    dispatch_id,
                    tenant_id,
                    fit_id,
                    attempt_id,
                    task_name,
                    payload_hash,
                    claim_capability,
                    recovery_generation
                )
                VALUES (
                    v_row.id,
                    v_row.tenant_id,
                    v_row.fit_id,
                    v_attempt_id,
                    v_row.task_name,
                    v_row.payload_hash,
                    NULL,
                    v_generation
                )
                ON CONFLICT (tenant_id, dispatch_id, recovery_generation) DO NOTHING;
                v_count := v_count + 1;
            END LOOP;
            RETURN v_count;
        END
        $$;


--
-- Name: b24_current_dispatch_fence_valid(uuid, uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_current_dispatch_fence_valid(p_tenant_id uuid, p_fit_id uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
            SELECT EXISTS (
                SELECT 1
                FROM public.b24_fit_dispatch_outbox outbox
                WHERE outbox.tenant_id = p_tenant_id
                  AND outbox.fit_id = p_fit_id
                  AND outbox.id = NULLIF(current_setting('app.b24_dispatch_id', true), '')::uuid
                  AND outbox.attempt_id = NULLIF(current_setting('app.b24_attempt_id', true), '')::uuid
                  AND outbox.claim_epoch = NULLIF(current_setting('app.b24_claim_epoch', true), '')::integer
                  AND outbox.lease_capability_digest = public.b24_sha256_text(
                        current_setting('app.b24_lease_capability', true)
                      )
                  AND outbox.lease_expires_at > now()
                  AND outbox.status IN ('leased', 'running')
            )
        $$;


--
-- Name: b24_due_fit_planner_tenants(text, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_due_fit_planner_tenants(p_lease_owner text, p_limit integer DEFAULT 25) RETURNS TABLE(tenant_id uuid, wakeup_revision bigint)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
        BEGIN
            IF session_user <> 'app_worker' THEN
                RAISE EXCEPTION 'b24_worker_database_identity_required';
            END IF;
            IF p_lease_owner IS NULL OR btrim(p_lease_owner) = '' THEN
                RAISE EXCEPTION 'b24_fit_planner_lease_owner_required';
            END IF;
            RETURN QUERY
            WITH due AS (
                SELECT wakeup.tenant_id
                FROM public.b24_fit_planner_wakeups wakeup
                WHERE (
                        wakeup.next_eligible_at IS NULL
                        OR wakeup.next_eligible_at <= now()
                      )
                  AND (
                        wakeup.status = 'pending'
                        OR (
                            wakeup.status = 'leased'
                            AND wakeup.lease_expires_at <= now()
                        )
                      )
                ORDER BY wakeup.observed_at, wakeup.tenant_id
                LIMIT LEAST(GREATEST(p_limit, 1), 100)
                FOR UPDATE SKIP LOCKED
            )
            UPDATE public.b24_fit_planner_wakeups wakeup
            SET status = 'leased',
                lease_owner = p_lease_owner,
                lease_expires_at = now()
                    + make_interval(secs => 600),
                updated_at = now()
            FROM due
            WHERE wakeup.tenant_id = due.tenant_id
            RETURNING wakeup.tenant_id, wakeup.wakeup_revision;
        END
        $$;


--
-- Name: b24_enforce_artifact_lifecycle(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_enforce_artifact_lifecycle() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF OLD.lifecycle_status IS NOT DISTINCT FROM NEW.lifecycle_status THEN
                RETURN NEW;
            END IF;
            IF OLD.lifecycle_status IN ('pruned', 'rejected')
               AND NEW.lifecycle_status NOT IN ('pruned', 'rejected') THEN
                RAISE EXCEPTION 'b24_artifact_lifecycle_resurrection_forbidden';
            END IF;
            RETURN NEW;
        END
        $$;


--
-- Name: b24_enforce_c11_policy_provenance(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_enforce_c11_policy_provenance() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
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


--
-- Name: b24_enforce_dirty_event_authority(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_enforce_dirty_event_authority() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
            IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
           OR NEW.model_type IS DISTINCT FROM OLD.model_type
           OR NEW.model_version IS DISTINCT FROM OLD.model_version
           OR NEW.source_window_start IS DISTINCT FROM OLD.source_window_start
           OR NEW.source_window_end IS DISTINCT FROM OLD.source_window_end
           OR NEW.dirty_reason IS DISTINCT FROM OLD.dirty_reason
           OR NEW.source_family IS DISTINCT FROM OLD.source_family
           OR NEW.event_hash IS DISTINCT FROM OLD.event_hash
           OR NEW.source_event_id IS DISTINCT FROM OLD.source_event_id
           OR NEW.created_at IS DISTINCT FROM OLD.created_at
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
        $$;


--
-- Name: b24_enforce_dirty_event_lifecycle(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_enforce_dirty_event_lifecycle() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.observed_at IS DISTINCT FROM OLD.observed_at THEN
                RAISE EXCEPTION 'b24_dirty_event_observed_at_immutable';
            END IF;
            IF OLD.status IN (
                    'coalesced', 'claimed', 'suppressed', 'fallback_only',
                    'superseded', 'dispatched', 'authority_retry_superseded',
                    'authority_timeout', 'authority_build_failed', 'pruned'
               )
               AND NEW.status IS DISTINCT FROM OLD.status THEN
                RAISE EXCEPTION 'b24_dirty_event_terminal_status_immutable';
            END IF;
            RETURN NEW;
        END
        $$;


--
-- Name: b24_enforce_dispatch_fence(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_enforce_dispatch_fence() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
        DECLARE
            v_tenant_id uuid;
            v_fit_id uuid;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'b24_dispatch_delete_forbidden';
            END IF;

            IF TG_OP = 'UPDATE' THEN
                IF TG_ARGV[0] = 'fit' THEN
                    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                       OR NEW.id IS DISTINCT FROM OLD.id THEN
                        RAISE EXCEPTION 'b24_dispatch_immutable_fit_authority';
                    END IF;
                    -- B2.5-P13 C5: the planner owns fit creation and scheduling
                    -- bookkeeping and never holds a dispatch lease. An update
                    -- that changes no authority-bearing column changes nothing
                    -- the fence exists to protect.
                    IF NOT (NEW.status IS DISTINCT FROM OLD.status
               OR NEW.source_snapshot_hash IS DISTINCT FROM OLD.source_snapshot_hash
               OR NEW.source_read_started_at IS DISTINCT FROM OLD.source_read_started_at
               OR NEW.source_read_completed_at IS DISTINCT FROM OLD.source_read_completed_at
               OR NEW.data_completeness_status IS DISTINCT FROM OLD.data_completeness_status
               OR NEW.fallback_applied IS DISTINCT FROM OLD.fallback_applied
               OR NEW.fallback_reason IS DISTINCT FROM OLD.fallback_reason
               OR NEW.diagnostic_status IS DISTINCT FROM OLD.diagnostic_status
               OR NEW.diagnostic_failure_reason IS DISTINCT FROM OLD.diagnostic_failure_reason
               OR NEW.diagnostic_policy_version IS DISTINCT FROM OLD.diagnostic_policy_version
               OR NEW.diagnostic_target_filter_version IS DISTINCT FROM OLD.diagnostic_target_filter_version
               OR NEW.diagnostics_computed_at IS DISTINCT FROM OLD.diagnostics_computed_at
               OR NEW.credible_interval_status IS DISTINCT FROM OLD.credible_interval_status
               OR NEW.interval_policy_version IS DISTINCT FROM OLD.interval_policy_version
               OR NEW.interval_shape IS DISTINCT FROM OLD.interval_shape
               OR NEW.interval_element_count IS DISTINCT FROM OLD.interval_element_count
               OR NEW.interval_summary_bytes IS DISTINCT FROM OLD.interval_summary_bytes
               OR NEW.hdi_lower IS DISTINCT FROM OLD.hdi_lower
               OR NEW.hdi_upper IS DISTINCT FROM OLD.hdi_upper
               OR NEW.r_hat_max IS DISTINCT FROM OLD.r_hat_max
               OR NEW.ess_min IS DISTINCT FROM OLD.ess_min
               OR NEW.divergence_count IS DISTINCT FROM OLD.divergence_count
               OR NEW.n_chains IS DISTINCT FROM OLD.n_chains
               OR NEW.n_samples_actual IS DISTINCT FROM OLD.n_samples_actual
               OR NEW.runtime_seconds IS DISTINCT FROM OLD.runtime_seconds
               OR NEW.sampling_started_at IS DISTINCT FROM OLD.sampling_started_at
               OR NEW.last_fit_at IS DISTINCT FROM OLD.last_fit_at
               OR NEW.completed_at IS DISTINCT FROM OLD.completed_at
               OR NEW.artifact_ref IS DISTINCT FROM OLD.artifact_ref
               OR NEW.artifact_hash IS DISTINCT FROM OLD.artifact_hash
               OR NEW.confidence_bucket IS DISTINCT FROM OLD.confidence_bucket
               OR NEW.confidence_bucket_reason IS DISTINCT FROM OLD.confidence_bucket_reason
               OR NEW.confidence_policy_version IS DISTINCT FROM OLD.confidence_policy_version
               OR NEW.confidence_semantics_version IS DISTINCT FROM OLD.confidence_semantics_version
               OR NEW.confidence_classified_at IS DISTINCT FROM OLD.confidence_classified_at
               OR NEW.confidence_evidence_snapshot_hash IS DISTINCT FROM OLD.confidence_evidence_snapshot_hash
               OR NEW.confidence_deterministic_revenue_minor IS DISTINCT FROM OLD.confidence_deterministic_revenue_minor
               OR NEW.confidence_deterministic_row_count IS DISTINCT FROM OLD.confidence_deterministic_row_count
               OR NEW.confidence_match_verdict_count IS DISTINCT FROM OLD.confidence_match_verdict_count
               OR NEW.confidence_currency_count IS DISTINCT FROM OLD.confidence_currency_count
               OR NEW.max_runtime_seconds IS DISTINCT FROM OLD.max_runtime_seconds
               OR NEW.max_samples IS DISTINCT FROM OLD.max_samples
               OR NEW.max_cores IS DISTINCT FROM OLD.max_cores) THEN
                        RETURN NEW;
                    END IF;
                ELSIF TG_ARGV[0] = 'artifact' THEN
                    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                       OR NEW.fit_id IS DISTINCT FROM OLD.fit_id
                       OR NEW.artifact_ref IS DISTINCT FROM OLD.artifact_ref THEN
                        RAISE EXCEPTION 'b24_dispatch_immutable_artifact_authority';
                    END IF;
                ELSE
                    RAISE EXCEPTION 'b24_dispatch_unknown_fence_subject';
                END IF;
            END IF;

            IF TG_ARGV[0] = 'fit' THEN
                v_tenant_id := NEW.tenant_id;
                v_fit_id := NEW.id;
                IF TG_OP = 'INSERT' AND NEW.status IN ('queued', 'pending') THEN
                    RETURN NEW;
                END IF;
                IF TG_OP IN ('INSERT', 'UPDATE')
                   AND NEW.status = 'fallback_only'
                   AND NEW.fallback_applied IS TRUE
                   AND NEW.fallback_reason IS NOT NULL
                   AND NEW.confidence_bucket = 'unavailable'
                   AND NEW.artifact_ref IS NULL
                   AND NEW.artifact_hash IS NULL
                   AND NEW.confidence_evidence_snapshot_hash IS NULL
                   AND NEW.sampling_started_at IS NULL
                   AND NEW.last_fit_at IS NULL
                   AND NEW.completed_at IS NULL
                   AND NEW.runtime_seconds IS NULL
                   AND NEW.n_samples_actual IS NULL
                   AND NEW.n_chains IS NULL
                   AND NEW.r_hat_max IS NULL
                   AND NEW.ess_min IS NULL
                   AND NEW.divergence_count IS NULL
                   AND NEW.hdi_lower IS NULL
                   AND NEW.hdi_upper IS NULL THEN
                    RETURN NEW;
                END IF;
            ELSIF TG_ARGV[0] = 'artifact' THEN
                v_tenant_id := NEW.tenant_id;
                v_fit_id := NEW.fit_id;
            ELSE
                RAISE EXCEPTION 'b24_dispatch_unknown_fence_subject';
            END IF;

            IF NOT public.b24_current_dispatch_fence_valid(v_tenant_id, v_fit_id) THEN
                RAISE EXCEPTION 'b24_dispatch_fence_rejected';
            END IF;
            RETURN NEW;
        END
        $$;


--
-- Name: b24_enforce_evidence_temporal_plausibility(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_enforce_evidence_temporal_plausibility() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            v_horizon timestamptz;
        BEGIN
            v_horizon := now() + make_interval(
                secs => public.b24_evidence_future_skew_tolerance_seconds()
            );
            IF NEW.source_read_started_at IS NOT NULL
               AND NEW.source_read_started_at > v_horizon THEN
                RAISE EXCEPTION 'b24_evidence_timestamp_implausible';
            END IF;
            IF NEW.source_read_completed_at IS NOT NULL
               AND NEW.source_read_completed_at > v_horizon THEN
                RAISE EXCEPTION 'b24_evidence_timestamp_implausible';
            END IF;
            IF NEW.confidence_classified_at IS NOT NULL
               AND NEW.confidence_classified_at > v_horizon THEN
                RAISE EXCEPTION 'b24_evidence_timestamp_implausible';
            END IF;
            RETURN NEW;
        END
        $$;


--
-- Name: b24_enforce_policy_bundle_write_authority(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_enforce_policy_bundle_write_authority() RETURNS trigger
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


--
-- Name: b24_enforce_terminal_fit_truth(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_enforce_terminal_fit_truth() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF public.b24_fit_status_is_terminal(OLD.status)
               AND (NEW.id IS DISTINCT FROM OLD.id
               OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
               OR NEW.model_type IS DISTINCT FROM OLD.model_type
               OR NEW.model_version IS DISTINCT FROM OLD.model_version
               OR NEW.source_window_start IS DISTINCT FROM OLD.source_window_start
               OR NEW.source_window_end IS DISTINCT FROM OLD.source_window_end
               OR NEW.source_snapshot_hash IS DISTINCT FROM OLD.source_snapshot_hash
               OR NEW.status IS DISTINCT FROM OLD.status
               OR NEW.data_completeness_status IS DISTINCT FROM OLD.data_completeness_status
               OR NEW.fallback_applied IS DISTINCT FROM OLD.fallback_applied
               OR NEW.fallback_reason IS DISTINCT FROM OLD.fallback_reason
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR NEW.completed_at IS DISTINCT FROM OLD.completed_at
               OR NEW.updated_at IS DISTINCT FROM OLD.updated_at
               OR NEW.diagnostic_status IS DISTINCT FROM OLD.diagnostic_status
               OR NEW.diagnostic_failure_reason IS DISTINCT FROM OLD.diagnostic_failure_reason
               OR NEW.credible_interval_status IS DISTINCT FROM OLD.credible_interval_status
               OR NEW.confidence_bucket IS DISTINCT FROM OLD.confidence_bucket
               OR NEW.confidence_bucket_reason IS DISTINCT FROM OLD.confidence_bucket_reason
               OR NEW.confidence_policy_version IS DISTINCT FROM OLD.confidence_policy_version
               OR NEW.confidence_semantics_version IS DISTINCT FROM OLD.confidence_semantics_version
               OR NEW.confidence_deterministic_revenue_minor IS DISTINCT FROM OLD.confidence_deterministic_revenue_minor
               OR NEW.confidence_deterministic_row_count IS DISTINCT FROM OLD.confidence_deterministic_row_count
               OR NEW.confidence_match_verdict_count IS DISTINCT FROM OLD.confidence_match_verdict_count
               OR NEW.confidence_currency_count IS DISTINCT FROM OLD.confidence_currency_count
               OR NEW.confidence_classified_at IS DISTINCT FROM OLD.confidence_classified_at
               OR NEW.confidence_evidence_snapshot_hash IS DISTINCT FROM OLD.confidence_evidence_snapshot_hash
               OR NEW.source_read_started_at IS DISTINCT FROM OLD.source_read_started_at
               OR NEW.source_read_completed_at IS DISTINCT FROM OLD.source_read_completed_at
               OR NEW.artifact_ref IS DISTINCT FROM OLD.artifact_ref
               OR NEW.artifact_hash IS DISTINCT FROM OLD.artifact_hash
               OR NEW.inference_profile_version IS DISTINCT FROM OLD.inference_profile_version
               OR NEW.runtime_policy_version IS DISTINCT FROM OLD.runtime_policy_version
               OR NEW.sampling_policy_version IS DISTINCT FROM OLD.sampling_policy_version
               OR NEW.policy_bundle_hash IS DISTINCT FROM OLD.policy_bundle_hash
               OR NEW.diagnostic_policy_version IS DISTINCT FROM OLD.diagnostic_policy_version
               OR NEW.authorized_chains IS DISTINCT FROM OLD.authorized_chains
               OR NEW.authorized_posterior_draws_total IS DISTINCT FROM OLD.authorized_posterior_draws_total
               OR NEW.superseded_policy_bundle_hash IS DISTINCT FROM OLD.superseded_policy_bundle_hash
               OR NEW.policy_replanned_at IS DISTINCT FROM OLD.policy_replanned_at
               OR NEW.policy_replan_count IS DISTINCT FROM OLD.policy_replan_count
               OR NEW.n_chains IS DISTINCT FROM OLD.n_chains
               OR NEW.n_samples_actual IS DISTINCT FROM OLD.n_samples_actual) THEN
                RAISE EXCEPTION 'b24_terminal_fit_truth_immutable';
            END IF;
            RETURN NEW;
        END
        $$;


--
-- Name: b24_evidence_future_skew_tolerance_seconds(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_evidence_future_skew_tolerance_seconds() RETURNS integer
    LANGUAGE sql IMMUTABLE
    AS $$
            SELECT 120
        $$;


--
-- Name: b24_fail_fit_dispatch_recoverable(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_fail_fit_dispatch_recoverable(p_reason text) RETURNS text
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    v_row record;
    v_terminal boolean;
    v_status text;
BEGIN
    SELECT *
    INTO v_row
    FROM public.b24_fit_dispatch_outbox outbox
    WHERE outbox.id = NULLIF(current_setting('app.b24_dispatch_id', true), '')::uuid
      AND public.b24_current_dispatch_fence_valid(outbox.tenant_id, outbox.fit_id)
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'b24_dispatch_recoverable_failure_fence_rejected';
    END IF;

    v_terminal := COALESCE(v_row.claim_count, 0) >= COALESCE(v_row.max_attempts, 1);
    v_status := CASE WHEN v_terminal THEN 'failed_terminal' ELSE 'failed_retryable' END;

    UPDATE public.bayesian_model_fits fit
    SET status = CASE WHEN v_terminal THEN 'failed' ELSE 'queued' END,
        fallback_applied = CASE WHEN v_terminal THEN true ELSE false END,
        fallback_reason = CASE
            WHEN v_terminal THEN COALESCE(NULLIF(p_reason, ''), 'worker_failure')
            ELSE NULL
        END,
        credible_interval_status = CASE
            WHEN v_terminal THEN 'not_available'
            ELSE fit.credible_interval_status
        END,
        diagnostic_status = CASE
            WHEN v_terminal THEN 'unavailable'
            ELSE fit.diagnostic_status
        END,
        diagnostic_failure_reason = CASE
            WHEN v_terminal THEN 'skipped_non_sampled'
            ELSE fit.diagnostic_failure_reason
        END,
        completed_at = CASE WHEN v_terminal THEN now() ELSE NULL END,
        updated_at = now()
    WHERE fit.tenant_id = v_row.tenant_id
      AND fit.id = v_row.fit_id
      AND fit.status IN ('pending', 'queued', 'running', 'persist_pending');

    UPDATE public.b24_fit_dispatch_outbox outbox
    SET status = v_status,
        terminal_reason = LEFT(
            'recoverable_ack:' || COALESCE(NULLIF(p_reason, ''), 'worker_failure'),
            512
        ),
        lease_owner = NULL,
        lease_capability_digest = NULL,
        lease_acquired_at = NULL,
        lease_expires_at = NULL,
        last_heartbeat_at = NULL,
        assigned_worker_generation = NULL,
        assignment_generation = assignment_generation + 1,
        assignment_expires_at = NULL,
        assignment_reason = 'failure_ack_recovery_required',
        next_recovery_at = now(),
        completed_at = CASE WHEN v_terminal THEN now() ELSE NULL END,
        updated_at = now()
    WHERE outbox.tenant_id = v_row.tenant_id
      AND outbox.id = v_row.id;

    RETURN v_status;
END
$$;


--
-- Name: b24_fail_fit_dispatch_terminal(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_fail_fit_dispatch_terminal(p_reason text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
        BEGIN
            UPDATE public.b24_fit_dispatch_outbox outbox
            SET status = 'failed_terminal',
                terminal_reason = LEFT(COALESCE(p_reason, 'worker_failure'), 512),
                completed_at = now(),
                updated_at = now()
            WHERE outbox.id = NULLIF(current_setting('app.b24_dispatch_id', true), '')::uuid
              AND public.b24_current_dispatch_fence_valid(outbox.tenant_id, outbox.fit_id);
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b24_dispatch_failure_fence_rejected';
            END IF;
        END
        $$;


--
-- Name: b24_fit_planner_residual_obligation(uuid, integer, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_fit_planner_residual_obligation(p_tenant_id uuid, p_quiet_period_seconds integer, p_max_wait_seconds integer) RETURNS TABLE(eligible_group_count integer, next_eligible_at timestamp with time zone)
    LANGUAGE plpgsql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
        BEGIN
            RETURN QUERY
            WITH candidate_groups AS (
                SELECT
                    max(dirty.observed_at) AS last_observed_at,
                    min(dirty.observed_at) AS first_observed_at
                FROM public.b24_dirty_events dirty
                WHERE dirty.tenant_id = p_tenant_id
                  AND (
                      dirty.status IN ('pending', 'authority_retry_ready')
                      OR (
                          dirty.status = 'leased'
                          AND dirty.lease_expires_at IS NOT NULL
                          AND dirty.lease_expires_at <= now()
                      )
                  )
                GROUP BY
                    dirty.model_type,
                    dirty.model_version,
                    dirty.source_window_start,
                    dirty.source_window_end,
                    dirty.source_snapshot_hash
            ),
            due_times AS (
                SELECT LEAST(
                    last_observed_at
                        + make_interval(secs => p_quiet_period_seconds),
                    first_observed_at
                        + make_interval(secs => GREATEST(
                            p_quiet_period_seconds, p_max_wait_seconds))
                ) AS due_at
                FROM candidate_groups
            )
            SELECT
                count(*) FILTER (WHERE due_at <= now())::integer,
                min(due_at) FILTER (WHERE due_at > now())
            FROM due_times;
        END
        $$;


--
-- Name: b24_fit_status_is_terminal(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_fit_status_is_terminal(p_status text) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    AS $$ SELECT p_status IN ('succeeded', 'failed', 'timeout', 'worker_lost', 'fallback_only', 'cancelled') $$;


--
-- Name: b24_invalidate_attribution_allocations_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_invalidate_attribution_allocations_delete() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'attribution_allocations_snapshot_changed',
        'attribution_allocations',
        encode(sha256(convert_to(
            'attribution_allocations|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('attribution_allocations:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.created_at) AS window_start
        FROM old_rows row_set
        WHERE COALESCE(row_set.verified = true, false) AND row_set.created_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$$;


--
-- Name: b24_invalidate_attribution_allocations_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_invalidate_attribution_allocations_insert() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'attribution_allocations_snapshot_changed',
        'attribution_allocations',
        encode(sha256(convert_to(
            'attribution_allocations|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('attribution_allocations:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.created_at) AS window_start
        FROM new_rows row_set
        WHERE COALESCE(row_set.verified = true, false) AND row_set.created_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$$;


--
-- Name: b24_invalidate_attribution_allocations_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_invalidate_attribution_allocations_update() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'attribution_allocations_snapshot_changed',
        'attribution_allocations',
        encode(sha256(convert_to(
            'attribution_allocations|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('attribution_allocations:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT tenant_id, window_start FROM (
            SELECT new_row.tenant_id AS tenant_id,
                   date_trunc('day', new_row.created_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.verified = true, false) AND new_row.created_at IS NOT NULL) OR (COALESCE(old_row.verified = true, false) AND old_row.created_at IS NOT NULL))
              AND (
                (COALESCE(new_row.verified = true, false) AND new_row.created_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.verified = true, false) AND old_row.created_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.event_id, new_row.created_at, new_row.channel_code, new_row.allocated_revenue_cents, new_row.allocation_ratio, new_row.model_type, new_row.model_version, new_row.verified, new_row.verification_source, new_row.verification_timestamp)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.event_id, old_row.created_at, old_row.channel_code, old_row.allocated_revenue_cents, old_row.allocation_ratio, old_row.model_type, old_row.model_version, old_row.verified, old_row.verification_source, old_row.verification_timestamp)
              )
            UNION
            SELECT old_row.tenant_id AS tenant_id,
                   date_trunc('day', old_row.created_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.verified = true, false) AND new_row.created_at IS NOT NULL) OR (COALESCE(old_row.verified = true, false) AND old_row.created_at IS NOT NULL))
              AND (
                (COALESCE(new_row.verified = true, false) AND new_row.created_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.verified = true, false) AND old_row.created_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.event_id, new_row.created_at, new_row.channel_code, new_row.allocated_revenue_cents, new_row.allocation_ratio, new_row.model_type, new_row.model_version, new_row.verified, new_row.verification_source, new_row.verification_timestamp)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.event_id, old_row.created_at, old_row.channel_code, old_row.allocated_revenue_cents, old_row.allocation_ratio, old_row.model_type, old_row.model_version, old_row.verified, old_row.verification_source, old_row.verification_timestamp)
              )
        ) both_buckets
        WHERE window_start IS NOT NULL
    ) affected;
    RETURN NULL;
END
$$;


--
-- Name: b24_invalidate_attribution_events_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_invalidate_attribution_events_delete() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'attribution_events_snapshot_changed',
        'attribution_events',
        encode(sha256(convert_to(
            'attribution_events|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('attribution_events:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.occurred_at) AS window_start
        FROM old_rows row_set
        WHERE COALESCE(row_set.processing_status IN ('pending', 'processed') AND row_set.event_type IN ('conversion', 'purchase'), false) AND row_set.occurred_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$$;


--
-- Name: b24_invalidate_attribution_events_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_invalidate_attribution_events_insert() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'attribution_events_snapshot_changed',
        'attribution_events',
        encode(sha256(convert_to(
            'attribution_events|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('attribution_events:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.occurred_at) AS window_start
        FROM new_rows row_set
        WHERE COALESCE(row_set.processing_status IN ('pending', 'processed') AND row_set.event_type IN ('conversion', 'purchase'), false) AND row_set.occurred_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$$;


--
-- Name: b24_invalidate_attribution_events_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_invalidate_attribution_events_update() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'attribution_events_snapshot_changed',
        'attribution_events',
        encode(sha256(convert_to(
            'attribution_events|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('attribution_events:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT tenant_id, window_start FROM (
            SELECT new_row.tenant_id AS tenant_id,
                   date_trunc('day', new_row.occurred_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.processing_status IN ('pending', 'processed') AND new_row.event_type IN ('conversion', 'purchase'), false) AND new_row.occurred_at IS NOT NULL) OR (COALESCE(old_row.processing_status IN ('pending', 'processed') AND old_row.event_type IN ('conversion', 'purchase'), false) AND old_row.occurred_at IS NOT NULL))
              AND (
                (COALESCE(new_row.processing_status IN ('pending', 'processed') AND new_row.event_type IN ('conversion', 'purchase'), false) AND new_row.occurred_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.processing_status IN ('pending', 'processed') AND old_row.event_type IN ('conversion', 'purchase'), false) AND old_row.occurred_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.occurred_at, new_row.event_timestamp, new_row.event_type, new_row.channel, new_row.campaign_id, new_row.revenue_cents, new_row.conversion_value_cents, new_row.currency, new_row.processing_status)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.occurred_at, old_row.event_timestamp, old_row.event_type, old_row.channel, old_row.campaign_id, old_row.revenue_cents, old_row.conversion_value_cents, old_row.currency, old_row.processing_status)
              )
            UNION
            SELECT old_row.tenant_id AS tenant_id,
                   date_trunc('day', old_row.occurred_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.processing_status IN ('pending', 'processed') AND new_row.event_type IN ('conversion', 'purchase'), false) AND new_row.occurred_at IS NOT NULL) OR (COALESCE(old_row.processing_status IN ('pending', 'processed') AND old_row.event_type IN ('conversion', 'purchase'), false) AND old_row.occurred_at IS NOT NULL))
              AND (
                (COALESCE(new_row.processing_status IN ('pending', 'processed') AND new_row.event_type IN ('conversion', 'purchase'), false) AND new_row.occurred_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.processing_status IN ('pending', 'processed') AND old_row.event_type IN ('conversion', 'purchase'), false) AND old_row.occurred_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.occurred_at, new_row.event_timestamp, new_row.event_type, new_row.channel, new_row.campaign_id, new_row.revenue_cents, new_row.conversion_value_cents, new_row.currency, new_row.processing_status)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.occurred_at, old_row.event_timestamp, old_row.event_type, old_row.channel, old_row.campaign_id, old_row.revenue_cents, old_row.conversion_value_cents, old_row.currency, old_row.processing_status)
              )
        ) both_buckets
        WHERE window_start IS NOT NULL
    ) affected;
    RETURN NULL;
END
$$;


--
-- Name: b24_invalidate_b23_match_verdicts_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_invalidate_b23_match_verdicts_delete() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'b23_match_verdicts_snapshot_changed',
        'b23_match_verdicts',
        encode(sha256(convert_to(
            'b23_match_verdicts|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('b23_match_verdicts:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.last_transition_at) AS window_start
        FROM old_rows row_set
        WHERE COALESCE(row_set.status IN ('matched_confirmed', 'adjusted'), false) AND row_set.last_transition_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$$;


--
-- Name: b24_invalidate_b23_match_verdicts_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_invalidate_b23_match_verdicts_insert() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'b23_match_verdicts_snapshot_changed',
        'b23_match_verdicts',
        encode(sha256(convert_to(
            'b23_match_verdicts|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('b23_match_verdicts:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.last_transition_at) AS window_start
        FROM new_rows row_set
        WHERE COALESCE(row_set.status IN ('matched_confirmed', 'adjusted'), false) AND row_set.last_transition_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$$;


--
-- Name: b24_invalidate_b23_match_verdicts_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_invalidate_b23_match_verdicts_update() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'b23_match_verdicts_snapshot_changed',
        'b23_match_verdicts',
        encode(sha256(convert_to(
            'b23_match_verdicts|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('b23_match_verdicts:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT tenant_id, window_start FROM (
            SELECT new_row.tenant_id AS tenant_id,
                   date_trunc('day', new_row.last_transition_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.status IN ('matched_confirmed', 'adjusted'), false) AND new_row.last_transition_at IS NOT NULL) OR (COALESCE(old_row.status IN ('matched_confirmed', 'adjusted'), false) AND old_row.last_transition_at IS NOT NULL))
              AND (
                (COALESCE(new_row.status IN ('matched_confirmed', 'adjusted'), false) AND new_row.last_transition_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.status IN ('matched_confirmed', 'adjusted'), false) AND old_row.last_transition_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.attribution_event_id, new_row.provider, new_row.canonical_commerce_reference, new_row.status, new_row.match_quality, new_row.attributed_amount_minor, new_row.verified_amount_minor, new_row.currency_code, new_row.confirmed_at, new_row.adjusted_at, new_row.last_transition_at, new_row.canonical_expected_gross_amount_minor, new_row.canonical_captured_gross_amount_minor, new_row.canonical_net_verified_amount_minor, new_row.discrepancy_amount_minor, new_row.discrepancy_ratio_bps, new_row.discrepancy_band)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.attribution_event_id, old_row.provider, old_row.canonical_commerce_reference, old_row.status, old_row.match_quality, old_row.attributed_amount_minor, old_row.verified_amount_minor, old_row.currency_code, old_row.confirmed_at, old_row.adjusted_at, old_row.last_transition_at, old_row.canonical_expected_gross_amount_minor, old_row.canonical_captured_gross_amount_minor, old_row.canonical_net_verified_amount_minor, old_row.discrepancy_amount_minor, old_row.discrepancy_ratio_bps, old_row.discrepancy_band)
              )
            UNION
            SELECT old_row.tenant_id AS tenant_id,
                   date_trunc('day', old_row.last_transition_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.status IN ('matched_confirmed', 'adjusted'), false) AND new_row.last_transition_at IS NOT NULL) OR (COALESCE(old_row.status IN ('matched_confirmed', 'adjusted'), false) AND old_row.last_transition_at IS NOT NULL))
              AND (
                (COALESCE(new_row.status IN ('matched_confirmed', 'adjusted'), false) AND new_row.last_transition_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.status IN ('matched_confirmed', 'adjusted'), false) AND old_row.last_transition_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.attribution_event_id, new_row.provider, new_row.canonical_commerce_reference, new_row.status, new_row.match_quality, new_row.attributed_amount_minor, new_row.verified_amount_minor, new_row.currency_code, new_row.confirmed_at, new_row.adjusted_at, new_row.last_transition_at, new_row.canonical_expected_gross_amount_minor, new_row.canonical_captured_gross_amount_minor, new_row.canonical_net_verified_amount_minor, new_row.discrepancy_amount_minor, new_row.discrepancy_ratio_bps, new_row.discrepancy_band)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.attribution_event_id, old_row.provider, old_row.canonical_commerce_reference, old_row.status, old_row.match_quality, old_row.attributed_amount_minor, old_row.verified_amount_minor, old_row.currency_code, old_row.confirmed_at, old_row.adjusted_at, old_row.last_transition_at, old_row.canonical_expected_gross_amount_minor, old_row.canonical_captured_gross_amount_minor, old_row.canonical_net_verified_amount_minor, old_row.discrepancy_amount_minor, old_row.discrepancy_ratio_bps, old_row.discrepancy_band)
              )
        ) both_buckets
        WHERE window_start IS NOT NULL
    ) affected;
    RETURN NULL;
END
$$;


--
-- Name: b24_invalidate_b23_revenue_events_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_invalidate_b23_revenue_events_delete() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'b23_revenue_events_snapshot_changed',
        'b23_revenue_events',
        encode(sha256(convert_to(
            'b23_revenue_events|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('b23_revenue_events:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.event_occurred_at) AS window_start
        FROM old_rows row_set
        WHERE COALESCE(row_set.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND row_set.event_occurred_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$$;


--
-- Name: b24_invalidate_b23_revenue_events_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_invalidate_b23_revenue_events_insert() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'b23_revenue_events_snapshot_changed',
        'b23_revenue_events',
        encode(sha256(convert_to(
            'b23_revenue_events|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('b23_revenue_events:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.event_occurred_at) AS window_start
        FROM new_rows row_set
        WHERE COALESCE(row_set.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND row_set.event_occurred_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$$;


--
-- Name: b24_invalidate_b23_revenue_events_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_invalidate_b23_revenue_events_update() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'b23_revenue_events_snapshot_changed',
        'b23_revenue_events',
        encode(sha256(convert_to(
            'b23_revenue_events|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('b23_revenue_events:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT tenant_id, window_start FROM (
            SELECT new_row.tenant_id AS tenant_id,
                   date_trunc('day', new_row.event_occurred_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND new_row.event_occurred_at IS NOT NULL) OR (COALESCE(old_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND old_row.event_occurred_at IS NOT NULL))
              AND (
                (COALESCE(new_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND new_row.event_occurred_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND old_row.event_occurred_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.match_verdict_id, new_row.provider, new_row.canonical_commerce_reference, new_row.event_type, new_row.currency_code, new_row.event_occurred_at, new_row.captured_amount_minor, new_row.refund_amount_minor, new_row.chargeback_amount_minor, new_row.reversal_amount_minor, new_row.net_effect_sign, new_row.is_gross_capture_correction)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.match_verdict_id, old_row.provider, old_row.canonical_commerce_reference, old_row.event_type, old_row.currency_code, old_row.event_occurred_at, old_row.captured_amount_minor, old_row.refund_amount_minor, old_row.chargeback_amount_minor, old_row.reversal_amount_minor, old_row.net_effect_sign, old_row.is_gross_capture_correction)
              )
            UNION
            SELECT old_row.tenant_id AS tenant_id,
                   date_trunc('day', old_row.event_occurred_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND new_row.event_occurred_at IS NOT NULL) OR (COALESCE(old_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND old_row.event_occurred_at IS NOT NULL))
              AND (
                (COALESCE(new_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND new_row.event_occurred_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND old_row.event_occurred_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.match_verdict_id, new_row.provider, new_row.canonical_commerce_reference, new_row.event_type, new_row.currency_code, new_row.event_occurred_at, new_row.captured_amount_minor, new_row.refund_amount_minor, new_row.chargeback_amount_minor, new_row.reversal_amount_minor, new_row.net_effect_sign, new_row.is_gross_capture_correction)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.match_verdict_id, old_row.provider, old_row.canonical_commerce_reference, old_row.event_type, old_row.currency_code, old_row.event_occurred_at, old_row.captured_amount_minor, old_row.refund_amount_minor, old_row.chargeback_amount_minor, old_row.reversal_amount_minor, old_row.net_effect_sign, old_row.is_gross_capture_correction)
              )
        ) both_buckets
        WHERE window_start IS NOT NULL
    ) affected;
    RETURN NULL;
END
$$;


--
-- Name: b24_lease_fit_recovery_rows(integer, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_lease_fit_recovery_rows(p_batch_size integer DEFAULT 25, p_stale_publishing_seconds integer DEFAULT 300) RETURNS TABLE(recovery_id uuid, tenant_id uuid, dispatch_id uuid, fit_id uuid, task_name text, attempt_id uuid, payload_hash text, recovery_generation integer, publish_attempt_count integer)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
        BEGIN
            RETURN QUERY
            WITH due AS (
                SELECT recovery.tenant_id, recovery.id, recovery.dispatch_id
                FROM public.b24_fit_recovery_outbox recovery
                WHERE (
                    recovery.status IN ('pending', 'failed_retryable')
                    OR (
                        recovery.status = 'publishing'
                        AND recovery.updated_at <= now() - (
                            LEAST(
                                GREATEST(
                                    COALESCE(p_stale_publishing_seconds, 300), 1
                                ),
                                86400
                            ) * interval '1 second'
                        )
                    )
                )
                ORDER BY recovery.created_at ASC, recovery.id ASC
                LIMIT LEAST(GREATEST(COALESCE(p_batch_size, 25), 1), 100)
                FOR UPDATE SKIP LOCKED
            ),
            assigned AS (
                UPDATE public.b24_fit_dispatch_outbox dispatch
                SET status = 'dispatching',
                    assigned_worker_generation = NULL,
                    assignment_generation = dispatch.assignment_generation + 1,
                    assignment_expires_at = now() + interval '10 minutes',
                    assignment_reason = 'recovery_shared_eligible',
                    dispatching_started_at = now(),
                    updated_at = now()
                FROM due
                WHERE dispatch.tenant_id = due.tenant_id
                  AND dispatch.id = due.dispatch_id
                RETURNING
                    dispatch.tenant_id,
                    dispatch.id AS dispatch_id,
                    dispatch.fit_id,
                    dispatch.task_name,
                    dispatch.attempt_id,
                    dispatch.payload_hash::text AS payload_hash,
                    dispatch.recovery_generation
            )
            UPDATE public.b24_fit_recovery_outbox recovery
            SET status = 'publishing',
                publish_attempt_count = recovery.publish_attempt_count + 1,
                updated_at = now()
            FROM due
            JOIN assigned
              ON assigned.tenant_id = due.tenant_id
             AND assigned.dispatch_id = due.dispatch_id
            WHERE recovery.tenant_id = due.tenant_id
              AND recovery.id = due.id
            RETURNING
                recovery.id,
                recovery.tenant_id,
                recovery.dispatch_id,
                assigned.fit_id,
                assigned.task_name,
                assigned.attempt_id,
                assigned.payload_hash,
                assigned.recovery_generation,
                recovery.publish_attempt_count;
        END
        $$;


--
-- Name: b24_mark_allocation_financial_window_dirty(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_mark_allocation_financial_window_dirty() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
DECLARE
    source_row record;
    financial_window_start timestamptz;
BEGIN
    source_row := CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    IF TG_OP = 'UPDATE' AND
       (NEW.tenant_id,
       NEW.event_id,
       NEW.created_at,
       NEW.channel_code,
       NEW.allocated_revenue_cents,
       NEW.allocation_ratio,
       NEW.model_type,
       NEW.model_version,
       NEW.verified,
       NEW.verification_source,
       NEW.verification_timestamp)
       IS NOT DISTINCT FROM
       (OLD.tenant_id,
       OLD.event_id,
       OLD.created_at,
       OLD.channel_code,
       OLD.allocated_revenue_cents,
       OLD.allocation_ratio,
       OLD.model_type,
       OLD.model_version,
       OLD.verified,
       OLD.verification_source,
       OLD.verification_timestamp) THEN
        RETURN NULL;
    END IF;
    IF NOT COALESCE(
            CASE WHEN TG_OP = 'DELETE' THEN OLD.verified
                 WHEN TG_OP = 'INSERT' THEN NEW.verified
                 ELSE OLD.verified OR NEW.verified END,
            false
        ) THEN
            RETURN NULL;
        END IF;

    SELECT date_trunc('day', event.occurred_at)
      INTO financial_window_start
      FROM public.attribution_events AS event
     WHERE event.tenant_id = source_row.tenant_id
       AND event.id = source_row.event_id
       AND event.processing_status IN ('pending', 'processed')
       AND event.event_type IN ('conversion', 'purchase');
    IF financial_window_start IS NULL THEN
        RETURN NULL;
    END IF;

    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    ) VALUES (
        source_row.tenant_id,
        'bayesian_attribution_confidence', 'b24-p6-real-fit-v1',
        financial_window_start, financial_window_start + interval '1 day',
        'attribution_allocations_financial_event_changed',
        'attribution_allocations',
        encode(sha256(convert_to(
            'c19|attribution_allocations|' || source_row.tenant_id::text || '|'
            || source_row.id::text || '|' || TG_OP || '|'
            || transaction_timestamp()::text || '|' || txid_current()::text,
            'UTF8')), 'hex'),
        left('attribution_allocations:' || source_row.id::text, 128),
        transaction_timestamp(), 'pending',
        transaction_timestamp(), transaction_timestamp()
    );
    RETURN NULL;
END;
$$;


--
-- Name: b24_mark_fit_dispatch_running(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_mark_fit_dispatch_running() RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
        BEGIN
            UPDATE public.b24_fit_dispatch_outbox outbox
            SET status = 'running',
                last_heartbeat_at = now(),
                updated_at = now()
            WHERE outbox.id = NULLIF(current_setting('app.b24_dispatch_id', true), '')::uuid
              AND public.b24_current_dispatch_fence_valid(outbox.tenant_id, outbox.fit_id);
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b24_dispatch_running_fence_rejected';
            END IF;
        END
        $$;


--
-- Name: b24_mark_fit_recovery_failed(uuid, uuid, uuid, text, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_mark_fit_recovery_failed(p_tenant_id uuid, p_recovery_id uuid, p_dispatch_id uuid, p_error text, p_max_attempts integer DEFAULT 5) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
        DECLARE
            v_count integer;
        BEGIN
            UPDATE public.b24_fit_recovery_outbox recovery
            SET status = CASE
                    WHEN recovery.publish_attempt_count >= LEAST(
                        GREATEST(COALESCE(p_max_attempts, 5), 1), 100
                    ) THEN 'quarantined'
                    ELSE 'failed_retryable'
                END,
                last_error = left(COALESCE(p_error, ''), 2048),
                updated_at = now()
            WHERE recovery.tenant_id = p_tenant_id
              AND recovery.id = p_recovery_id
              AND recovery.dispatch_id = p_dispatch_id
              AND recovery.status = 'publishing';
            GET DIAGNOSTICS v_count = ROW_COUNT;
            RETURN v_count = 1;
        END
        $$;


--
-- Name: b24_mark_fit_recovery_published(uuid, uuid, uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_mark_fit_recovery_published(p_tenant_id uuid, p_recovery_id uuid, p_dispatch_id uuid) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
        DECLARE
            v_count integer;
        BEGIN
            UPDATE public.b24_fit_recovery_outbox recovery
            SET status = 'published',
                published_at = now(),
                updated_at = now(),
                last_error = NULL
            WHERE recovery.tenant_id = p_tenant_id
              AND recovery.id = p_recovery_id
              AND recovery.dispatch_id = p_dispatch_id
              AND recovery.status = 'publishing';
            GET DIAGNOSTICS v_count = ROW_COUNT;
            IF v_count <> 1 THEN
                RETURN false;
            END IF;

            UPDATE public.b24_fit_dispatch_outbox dispatch
            SET status = 'dispatched',
                dispatched_at = now(),
                updated_at = now()
            WHERE dispatch.tenant_id = p_tenant_id
              AND dispatch.id = p_dispatch_id
              AND dispatch.status = 'dispatching';
            GET DIAGNOSTICS v_count = ROW_COUNT;
            IF v_count <> 1 THEN
                RAISE EXCEPTION 'b24_recovery_dispatch_transition_missing';
            END IF;
            RETURN true;
        END
        $$;


--
-- Name: b24_mark_verdict_financial_window_dirty(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_mark_verdict_financial_window_dirty() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
DECLARE
    source_row record;
    financial_window_start timestamptz;
BEGIN
    source_row := CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    IF TG_OP = 'UPDATE' AND
       (NEW.tenant_id,
       NEW.attribution_event_id,
       NEW.provider,
       NEW.canonical_commerce_reference,
       NEW.status,
       NEW.match_quality,
       NEW.attributed_amount_minor,
       NEW.verified_amount_minor,
       NEW.currency_code,
       NEW.confirmed_at,
       NEW.adjusted_at,
       NEW.last_transition_at,
       NEW.canonical_expected_gross_amount_minor,
       NEW.canonical_captured_gross_amount_minor,
       NEW.canonical_net_verified_amount_minor,
       NEW.discrepancy_amount_minor,
       NEW.discrepancy_ratio_bps,
       NEW.discrepancy_band)
       IS NOT DISTINCT FROM
       (OLD.tenant_id,
       OLD.attribution_event_id,
       OLD.provider,
       OLD.canonical_commerce_reference,
       OLD.status,
       OLD.match_quality,
       OLD.attributed_amount_minor,
       OLD.verified_amount_minor,
       OLD.currency_code,
       OLD.confirmed_at,
       OLD.adjusted_at,
       OLD.last_transition_at,
       OLD.canonical_expected_gross_amount_minor,
       OLD.canonical_captured_gross_amount_minor,
       OLD.canonical_net_verified_amount_minor,
       OLD.discrepancy_amount_minor,
       OLD.discrepancy_ratio_bps,
       OLD.discrepancy_band) THEN
        RETURN NULL;
    END IF;
    IF NOT (
            (TG_OP <> 'INSERT' AND OLD.status IN ('matched_confirmed', 'adjusted'))
            OR
            (TG_OP <> 'DELETE' AND NEW.status IN ('matched_confirmed', 'adjusted'))
        ) THEN
            RETURN NULL;
        END IF;

    SELECT date_trunc('day', event.occurred_at)
      INTO financial_window_start
      FROM public.attribution_events AS event
     WHERE event.tenant_id = source_row.tenant_id
       AND event.id = source_row.attribution_event_id
       AND event.processing_status IN ('pending', 'processed')
       AND event.event_type IN ('conversion', 'purchase');
    IF financial_window_start IS NULL THEN
        RETURN NULL;
    END IF;

    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    ) VALUES (
        source_row.tenant_id,
        'bayesian_attribution_confidence', 'b24-p6-real-fit-v1',
        financial_window_start, financial_window_start + interval '1 day',
        'b23_match_verdicts_financial_event_changed',
        'b23_match_verdicts',
        encode(sha256(convert_to(
            'c19|b23_match_verdicts|' || source_row.tenant_id::text || '|'
            || source_row.id::text || '|' || TG_OP || '|'
            || transaction_timestamp()::text || '|' || txid_current()::text,
            'UTF8')), 'hex'),
        left('b23_match_verdicts:' || source_row.id::text, 128),
        transaction_timestamp(), 'pending',
        transaction_timestamp(), transaction_timestamp()
    );
    RETURN NULL;
END;
$$;


--
-- Name: b24_next_active_worker_generation(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_next_active_worker_generation() RETURNS text
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
        DECLARE
            v_generation text;
        BEGIN
            PERFORM set_config('app.b24_worker_authority_access', 'on', true);

            SELECT auth.generation_id
            INTO v_generation
            FROM public.b24_worker_process_authority auth
            WHERE auth.status = 'active'
              AND auth.revoked_at IS NULL
              AND auth.expires_at > now()
            ORDER BY auth.registered_at DESC, auth.generation_id DESC
            LIMIT 1;
            RETURN v_generation;
        END
        $$;


--
-- Name: b24_policy_lineage_complete(uuid, uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_policy_lineage_complete(p_tenant_id uuid, p_fit_id uuid) RETURNS boolean
    LANGUAGE plpgsql STABLE
    SET search_path TO 'pg_catalog', 'public'
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


--
-- Name: b24_register_worker_process_authority(text, integer, integer, text, text, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_register_worker_process_authority(p_generation_id text, p_pid integer, p_parent_pid integer, p_topology_fingerprint text, p_process_token text, p_ttl_seconds integer DEFAULT 3600) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $_$
        DECLARE
            v_ttl integer := LEAST(GREATEST(COALESCE(p_ttl_seconds, 3600), 30), 86400);
        BEGIN
            IF p_generation_id IS NULL
               OR p_generation_id = ''
               OR p_generation_id = 'unknown-generation'
               OR p_process_token IS NULL
               OR p_process_token = ''
               OR p_topology_fingerprint !~ '^[a-f0-9]{64}$' THEN
                RAISE EXCEPTION 'b24_worker_process_authority_invalid';
            END IF;

            PERFORM set_config('app.b24_worker_authority_access', 'on', true);

            INSERT INTO public.b24_worker_process_authority (
                generation_id,
                pid,
                parent_pid,
                topology_fingerprint,
                process_token_digest,
                status,
                registered_at,
                expires_at,
                revoked_at
            )
            VALUES (
                p_generation_id,
                p_pid,
                p_parent_pid,
                p_topology_fingerprint,
                public.b24_sha256_text(p_process_token),
                'active',
                now(),
                now() + (v_ttl * interval '1 second'),
                NULL
            )
            ON CONFLICT (generation_id, pid)
            DO UPDATE SET
                parent_pid = EXCLUDED.parent_pid,
                topology_fingerprint = EXCLUDED.topology_fingerprint,
                process_token_digest = EXCLUDED.process_token_digest,
                status = 'active',
                registered_at = now(),
                expires_at = EXCLUDED.expires_at,
                revoked_at = NULL;
        END
        $_$;


--
-- Name: b24_reject_policy_registry_rewrite(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_reject_policy_registry_rewrite() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            RAISE EXCEPTION 'b24_policy_registry_immutable';
        END
        $$;


--
-- Name: b24_reject_replan_lineage_mutation(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_reject_replan_lineage_mutation() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            RAISE EXCEPTION 'b24_replan_lineage_append_only';
        END
        $$;


--
-- Name: b24_sha256_text(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_sha256_text(value text) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
            SELECT encode(digest(value, 'sha256'), 'hex')
        $$;


--
-- Name: b24_signal_fit_planner_wakeup(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_signal_fit_planner_wakeup() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
        BEGIN
            IF NEW.status IN ('pending', 'authority_retry_ready')
               AND (
                    TG_OP = 'INSERT'
                    OR OLD.status IS DISTINCT FROM NEW.status
               ) THEN
                INSERT INTO public.b24_fit_planner_wakeups (
                    tenant_id, observed_at
                ) VALUES (NEW.tenant_id, NEW.observed_at)
                ON CONFLICT (tenant_id) DO UPDATE
                SET wakeup_revision =
                        b24_fit_planner_wakeups.wakeup_revision + 1,
                    observed_at = LEAST(
                        b24_fit_planner_wakeups.observed_at,
                        EXCLUDED.observed_at
                    ),
                    updated_at = now();
            END IF;
            RETURN NEW;
        END
        $$;


--
-- Name: b24_signal_fit_planner_wakeup_coalesced(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_signal_fit_planner_wakeup_coalesced() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
        BEGIN
            IF NEW.status IN ('pending', 'authority_retry_ready')
               AND (
                    TG_OP = 'INSERT'
                    OR OLD.status IS DISTINCT FROM NEW.status
               ) THEN
                INSERT INTO public.b24_fit_planner_wakeups (
                    tenant_id, observed_at
                ) VALUES (NEW.tenant_id, NEW.observed_at)
                ON CONFLICT (tenant_id) DO NOTHING;

                IF NOT FOUND THEN
                    UPDATE public.b24_fit_planner_wakeups
                    SET wakeup_revision = CASE
                            WHEN status = 'leased' THEN wakeup_revision + 1
                            ELSE wakeup_revision
                        END,
                        status = 'pending',
                        lease_owner = NULL,
                        lease_expires_at = NULL,
                        next_eligible_at = NULL,
                        observed_at = LEAST(observed_at, NEW.observed_at),
                        updated_at = now()
                    WHERE tenant_id = NEW.tenant_id
                      AND (status = 'leased' OR next_eligible_at IS NOT NULL);
                END IF;
            END IF;
            RETURN NEW;
        END
        $$;


--
-- Name: b24_source_windows_overlap(timestamp with time zone, timestamp with time zone, timestamp with time zone, timestamp with time zone); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b24_source_windows_overlap(p_change_start timestamp with time zone, p_change_end timestamp with time zone, p_fit_start timestamp with time zone, p_fit_end timestamp with time zone) RETURNS boolean
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    AS $$
            SELECT p_change_start < p_fit_end AND p_fit_start < p_change_end
        $$;


--
-- Name: b27_enforce_explanation_consequence(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b27_enforce_explanation_consequence() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
        $$;


--
-- Name: b27_enforce_materialization_immutability(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b27_enforce_materialization_immutability() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
        $$;


--
-- Name: b27_supersede_stale_explanations(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b27_supersede_stale_explanations() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
        $$;


--
-- Name: b28_adjudicate_sufficiency(jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b28_adjudicate_sufficiency(p_channel_evidence jsonb) RETURNS TABLE(sufficient boolean, reasons text[], observed_channels integer, observed_conversions integer, observed_revenue_minor bigint)
    LANGUAGE plpgsql IMMUTABLE
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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

            IF n_channels < 2 THEN
                found_reasons := found_reasons || (
                    'channels_below_minimum:' || n_channels::text
                    || '<' || 2::text
                );
            END IF;
            IF n_with_evidence < 2 THEN
                found_reasons := found_reasons || (
                    'channels_with_evidence_below_minimum:' || n_with_evidence::text
                    || '<' || 2::text
                );
            END IF;
            IF n_conversions < 5 THEN
                found_reasons := found_reasons || (
                    'conversions_below_minimum:' || n_conversions::text
                    || '<' || 5::text
                );
            END IF;
            IF n_revenue < 1 THEN
                found_reasons := found_reasons || (
                    'revenue_below_minimum:' || n_revenue::text
                    || '<' || 1::text
                );
            END IF;

            sufficient := (array_length(found_reasons, 1) IS NULL);
            reasons := found_reasons;
            observed_channels := n_channels;
            observed_conversions := n_conversions::integer;
            observed_revenue_minor := n_revenue;
            RETURN NEXT;
        END;
        $$;


--
-- Name: b28_canonical_input_material(text, text, bigint, text, jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b28_canonical_input_material(p_source_envelope_id text, p_source_semantic_truth_hash text, p_total_budget_minor bigint, p_currency text, p_channel_evidence jsonb) RETURNS text
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'pg_catalog', 'public'
    AS $$
            SELECT '{"channels":['
                || COALESCE(
                     (
                       SELECT string_agg(
                                '{"channel_id":'
                                || to_jsonb(elem ->> 'channel_id')::text
                                || ',"conversion_count":'
                                || (elem ->> 'conversion_count')::bigint::text
                                || ',"verified_revenue_minor":'
                                || (elem ->> 'verified_revenue_minor')::bigint::text
                                || '}',
                                ','
                                ORDER BY (elem ->> 'channel_id') COLLATE "C"
                              )
                       FROM jsonb_array_elements(p_channel_evidence) AS elem
                     ),
                     ''
                   )
                || ']'
                || ',"contract_version":'
                || to_jsonb('b25-p14-simulation-v1'::text)::text
                || ',"currency":' || to_jsonb(p_currency)::text
                || ',"solver_profile":' || to_jsonb('b25-p14-deterministic-largest-remainder-v1'::text)::text
                || ',"source_envelope_id":' || to_jsonb(p_source_envelope_id)::text
                || ',"source_semantic_truth_hash":'
                || to_jsonb(p_source_semantic_truth_hash)::text
                || ',"sufficiency_policy_version":'
                || to_jsonb('b25-p14-sufficiency-v1'::text)::text
                || ',"total_budget_minor":' || p_total_budget_minor::text
                || '}'
        $$;


--
-- Name: b28_enforce_allocation_conservation(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b28_enforce_allocation_conservation() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $_$
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
        $_$;


--
-- Name: b28_enforce_downstream_immutability(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b28_enforce_downstream_immutability() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
        $$;


--
-- Name: b28_enforce_proposal_consequence(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b28_enforce_proposal_consequence() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
                IF session_user <> 'app_b28_solver' THEN
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
        $$;


--
-- Name: b28_enforce_request_consequence(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b28_enforce_request_consequence() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $_$
        DECLARE
            issuance_semantic_truth_hash text;
            issuance_policy_state text;
            admissible text[] := ARRAY['simulation_only', 'proposal_required', 'approval_required']::text[];
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
                IF session_user <> 'app_b28_requester' THEN
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
                   <> 'b25-p14-sufficiency-v1'
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
            IF NEW.solver_profile <> 'b25-p14-deterministic-largest-remainder-v1' THEN
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
                   OR (elem ->> 'channel_id') !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$'
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
        $_$;


--
-- Name: b28_enforce_result_consequence(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b28_enforce_result_consequence() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
                IF session_user <> 'app_b28_solver' THEN
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
            IF NEW.solver_profile <> 'b25-p14-deterministic-largest-remainder-v1'
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
        $$;


--
-- Name: b28_input_snapshot_hash(text, text, bigint, text, jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b28_input_snapshot_hash(p_source_envelope_id text, p_source_semantic_truth_hash text, p_total_budget_minor bigint, p_currency text, p_channel_evidence jsonb) RETURNS text
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
        $$;


--
-- Name: b28_recompute_allocation(jsonb, bigint); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b28_recompute_allocation(p_channel_evidence jsonb, p_total_budget_minor bigint) RETURNS jsonb
    LANGUAGE plpgsql IMMUTABLE
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
                    || div(revenues[idx] * 10000, total_revenue)::bigint;
                weight_remainders := weight_remainders
                    || mod(revenues[idx] * 10000, total_revenue);
                allocations := allocations
                    || div(
                         revenues[idx] * p_total_budget_minor, total_revenue
                       )::bigint;
                remainders := remainders
                    || mod(revenues[idx] * p_total_budget_minor, total_revenue);
            END LOOP;

            weight_shortfall := 10000;
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
        $$;


--
-- Name: check_allocation_sum(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.check_allocation_sum() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            event_revenue INTEGER;
            allocated_sum INTEGER;
            tolerance_cents INTEGER := 1; -- ±1 cent rounding tolerance
        BEGIN
            SELECT revenue_cents INTO event_revenue
            FROM attribution_events
            WHERE id = COALESCE(NEW.event_id, OLD.event_id);
            
            SELECT COALESCE(SUM(allocated_revenue_cents), 0) INTO allocated_sum
            FROM attribution_allocations
            WHERE event_id = COALESCE(NEW.event_id, OLD.event_id)
              AND model_version = COALESCE(NEW.model_version, OLD.model_version);
            
            IF ABS(allocated_sum - event_revenue) > tolerance_cents THEN
                RAISE EXCEPTION 'Allocation sum mismatch: allocated=% expected=% drift=%', 
                    allocated_sum, event_revenue, ABS(allocated_sum - event_revenue);
            END IF;
            
            RETURN COALESCE(NEW, OLD);
        END;
        $$;


--
-- Name: check_allocation_sum_stmt_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.check_allocation_sum_stmt_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            tolerance_cents INTEGER := 1;
            mismatch RECORD;
        BEGIN
            WITH affected AS (
                SELECT DISTINCT tenant_id, event_id, model_version, recompute_job_id
                FROM oldrows
                WHERE event_id IS NOT NULL
            )
            SELECT
                a.tenant_id,
                a.event_id,
                a.model_version,
                a.recompute_job_id,
                s.allocated_sum AS allocated_sum,
                e.revenue_cents AS event_revenue_cents,
                ABS(s.allocated_sum - e.revenue_cents) AS drift_cents
            INTO mismatch
            FROM affected a
            JOIN attribution_events e
              ON e.tenant_id = a.tenant_id
             AND e.id = a.event_id
            CROSS JOIN LATERAL (
                SELECT COALESCE(SUM(aa.allocated_revenue_cents), 0) AS allocated_sum
                FROM attribution_allocations aa
                WHERE aa.tenant_id = a.tenant_id
                  AND aa.event_id = a.event_id
                  AND (
                    (a.recompute_job_id IS NOT NULL AND aa.recompute_job_id = a.recompute_job_id)
                    OR (
                        a.recompute_job_id IS NULL
                        AND aa.recompute_job_id IS NULL
                        AND aa.model_version = a.model_version
                    )
                  )
            ) s
            WHERE ABS(s.allocated_sum - e.revenue_cents) > tolerance_cents
            LIMIT 1;

            IF FOUND THEN
                RAISE EXCEPTION
                    'Allocation sum mismatch: tenant_id=% event_id=% model_version=% allocated=% expected=% drift=%',
                    mismatch.tenant_id, mismatch.event_id, mismatch.model_version,
                    mismatch.allocated_sum, mismatch.event_revenue_cents, mismatch.drift_cents;
            END IF;

            RETURN NULL;
        END;
        $$;


--
-- Name: check_allocation_sum_stmt_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.check_allocation_sum_stmt_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            tolerance_cents INTEGER := 1;
            mismatch RECORD;
        BEGIN
            WITH affected AS (
                SELECT DISTINCT tenant_id, event_id, model_version, recompute_job_id
                FROM newrows
                WHERE event_id IS NOT NULL
            )
            SELECT
                a.tenant_id,
                a.event_id,
                a.model_version,
                a.recompute_job_id,
                s.allocated_sum AS allocated_sum,
                e.revenue_cents AS event_revenue_cents,
                ABS(s.allocated_sum - e.revenue_cents) AS drift_cents
            INTO mismatch
            FROM affected a
            JOIN attribution_events e
              ON e.tenant_id = a.tenant_id
             AND e.id = a.event_id
            CROSS JOIN LATERAL (
                SELECT COALESCE(SUM(aa.allocated_revenue_cents), 0) AS allocated_sum
                FROM attribution_allocations aa
                WHERE aa.tenant_id = a.tenant_id
                  AND aa.event_id = a.event_id
                  AND (
                    (a.recompute_job_id IS NOT NULL AND aa.recompute_job_id = a.recompute_job_id)
                    OR (
                        a.recompute_job_id IS NULL
                        AND aa.recompute_job_id IS NULL
                        AND aa.model_version = a.model_version
                    )
                  )
            ) s
            WHERE ABS(s.allocated_sum - e.revenue_cents) > tolerance_cents
            LIMIT 1;

            IF FOUND THEN
                RAISE EXCEPTION
                    'Allocation sum mismatch: tenant_id=% event_id=% model_version=% allocated=% expected=% drift=%',
                    mismatch.tenant_id, mismatch.event_id, mismatch.model_version,
                    mismatch.allocated_sum, mismatch.event_revenue_cents, mismatch.drift_cents;
            END IF;

            RETURN NULL;
        END;
        $$;


--
-- Name: check_allocation_sum_stmt_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.check_allocation_sum_stmt_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            tolerance_cents INTEGER := 1;
            mismatch RECORD;
        BEGIN
            WITH affected AS (
                SELECT DISTINCT tenant_id, event_id, model_version, recompute_job_id
                FROM newrows
                WHERE event_id IS NOT NULL
                UNION
                SELECT DISTINCT tenant_id, event_id, model_version, recompute_job_id
                FROM oldrows
                WHERE event_id IS NOT NULL
            )
            SELECT
                a.tenant_id,
                a.event_id,
                a.model_version,
                a.recompute_job_id,
                s.allocated_sum AS allocated_sum,
                e.revenue_cents AS event_revenue_cents,
                ABS(s.allocated_sum - e.revenue_cents) AS drift_cents
            INTO mismatch
            FROM affected a
            JOIN attribution_events e
              ON e.tenant_id = a.tenant_id
             AND e.id = a.event_id
            CROSS JOIN LATERAL (
                SELECT COALESCE(SUM(aa.allocated_revenue_cents), 0) AS allocated_sum
                FROM attribution_allocations aa
                WHERE aa.tenant_id = a.tenant_id
                  AND aa.event_id = a.event_id
                  AND (
                    (a.recompute_job_id IS NOT NULL AND aa.recompute_job_id = a.recompute_job_id)
                    OR (
                        a.recompute_job_id IS NULL
                        AND aa.recompute_job_id IS NULL
                        AND aa.model_version = a.model_version
                    )
                  )
            ) s
            WHERE ABS(s.allocated_sum - e.revenue_cents) > tolerance_cents
            LIMIT 1;

            IF FOUND THEN
                RAISE EXCEPTION
                    'Allocation sum mismatch: tenant_id=% event_id=% model_version=% allocated=% expected=% drift=%',
                    mismatch.tenant_id, mismatch.event_id, mismatch.model_version,
                    mismatch.allocated_sum, mismatch.event_revenue_cents, mismatch.drift_cents;
            END IF;

            RETURN NULL;
        END;
        $$;


--
-- Name: fn_b23_p0_prune_attribution_commerce_identities(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_b23_p0_prune_attribution_commerce_identities(max_delete integer DEFAULT 1000) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
            DECLARE
                cutoff timestamptz := now() - interval '90 days';
                deleted_count integer := 0;
            BEGIN
                WITH doomed AS (
                    SELECT id
                    FROM public.attribution_commerce_identities
                    WHERE last_observed_at < cutoff
                    ORDER BY last_observed_at ASC
                    LIMIT GREATEST(max_delete, 1)
                )
                DELETE FROM public.attribution_commerce_identities target
                USING doomed
                WHERE target.id = doomed.id;

                GET DIAGNOSTICS deleted_count = ROW_COUNT;
                RETURN deleted_count;
            END;
            $$;


--
-- Name: fn_b23_p0_prune_attribution_commerce_identities_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_b23_p0_prune_attribution_commerce_identities_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
            BEGIN
                PERFORM public.fn_b23_p0_prune_attribution_commerce_identities(1000);
                RETURN NULL;
            END;
            $$;


--
-- Name: fn_b23_p1_apply_lifecycle(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_b23_p1_apply_lifecycle(max_delete integer DEFAULT 5000) RETURNS TABLE(table_name text, deleted_rows integer)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
        DECLARE
            effective_limit integer := GREATEST(1, COALESCE(max_delete, 5000));
            removed integer := 0;
        BEGIN
            WITH doomed AS (
                SELECT id
                FROM public.b23_webhook_ingestion_logs
                WHERE received_at < (now() - interval '365 days')
                ORDER BY received_at
                LIMIT effective_limit
            )
            DELETE FROM public.b23_webhook_ingestion_logs target
            USING doomed
            WHERE target.id = doomed.id;
            GET DIAGNOSTICS removed = ROW_COUNT;
            table_name := 'b23_webhook_ingestion_logs';
            deleted_rows := removed;
            RETURN NEXT;

            WITH doomed AS (
                SELECT id
                FROM public.b23_exception_records
                WHERE raised_at < (now() - interval '1825 days')
                ORDER BY raised_at
                LIMIT effective_limit
            )
            DELETE FROM public.b23_exception_records target
            USING doomed
            WHERE target.id = doomed.id;
            GET DIAGNOSTICS removed = ROW_COUNT;
            table_name := 'b23_exception_records';
            deleted_rows := removed;
            RETURN NEXT;

            WITH doomed AS (
                SELECT id
                FROM public.b23_match_verdicts
                WHERE created_at < (now() - interval '1825 days')
                ORDER BY created_at
                LIMIT effective_limit
            )
            DELETE FROM public.b23_match_verdicts target
            USING doomed
            WHERE target.id = doomed.id;
            GET DIAGNOSTICS removed = ROW_COUNT;
            table_name := 'b23_match_verdicts';
            deleted_rows := removed;
            RETURN NEXT;

            WITH doomed AS (
                SELECT id
                FROM public.b23_revenue_events
                WHERE event_occurred_at < (now() - interval '2555 days')
                ORDER BY event_occurred_at
                LIMIT effective_limit
            )
            DELETE FROM public.b23_revenue_events target
            USING doomed
            WHERE target.id = doomed.id;
            GET DIAGNOSTICS removed = ROW_COUNT;
            table_name := 'b23_revenue_events';
            deleted_rows := removed;
            RETURN NEXT;

            RETURN;
        END;
        $$;


--
-- Name: fn_bind_session_authority_from_event(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_bind_session_authority_from_event() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
        DECLARE
            authority_now timestamptz;
        BEGIN
            authority_now := COALESCE(
                NEW.event_timestamp,
                NEW.occurred_at,
                transaction_timestamp()
            );
            IF NEW.session_id IS NULL THEN
                NEW.session_id := gen_random_uuid();
            END IF;

            INSERT INTO public.session_authority
            (
                tenant_id, session_id, issued_at, expires_at, last_seen_at,
                invalidated_at, invalidation_reason, issued_by, created_at, updated_at
            )
            VALUES
            (
                NEW.tenant_id, NEW.session_id, authority_now,
                authority_now + interval '24 hours', authority_now,
                NULL, NULL, 'attribution_event_insert',
                transaction_timestamp(), transaction_timestamp()
            )
            ON CONFLICT (tenant_id, session_id)
            DO UPDATE SET
                last_seen_at = GREATEST(
                    public.session_authority.last_seen_at,
                    EXCLUDED.last_seen_at
                ),
                updated_at = transaction_timestamp();

            IF EXISTS (
                SELECT 1
                  FROM public.session_authority AS authority
                 WHERE authority.tenant_id = NEW.tenant_id
                   AND authority.session_id = NEW.session_id
                   AND (
                       authority.invalidated_at IS NOT NULL
                       OR authority.issued_at > authority_now
                       OR authority.expires_at <= authority_now
                   )
            ) THEN
                RAISE EXCEPTION
                    'session authority violation: stale or invalidated session_id on attribution_events insert';
            END IF;

            RETURN NEW;
        END;
        $$;


--
-- Name: fn_block_worker_ingestion_mutation(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_block_worker_ingestion_mutation() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF current_setting('app.execution_context', true) = 'worker' THEN
        RAISE EXCEPTION 'ingestion tables are read-only in worker context (table=%)', TG_TABLE_NAME;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$;


--
-- Name: fn_compliance_audit_ledger_append_only(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_compliance_audit_ledger_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            RAISE EXCEPTION
                'compliance_audit_ledger is append-only; UPDATE and DELETE are forbidden';
        END;
        $$;


--
-- Name: fn_detect_pii_keys(jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_detect_pii_keys(payload jsonb) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE
    AS $_$
        BEGIN
            IF payload IS NULL THEN
                RETURN FALSE;
            END IF;
            RETURN (jsonb_path_exists(payload, '$.**.email') OR jsonb_path_exists(payload, '$.**.email_address') OR jsonb_path_exists(payload, '$.**.phone') OR jsonb_path_exists(payload, '$.**.phone_number') OR jsonb_path_exists(payload, '$.**.ssn') OR jsonb_path_exists(payload, '$.**.social_security_number') OR jsonb_path_exists(payload, '$.**.ip_address') OR jsonb_path_exists(payload, '$.**.ip') OR jsonb_path_exists(payload, '$.**.first_name') OR jsonb_path_exists(payload, '$.**.last_name') OR jsonb_path_exists(payload, '$.**.full_name') OR jsonb_path_exists(payload, '$.**.address') OR jsonb_path_exists(payload, '$.**.street_address'));
        END;
        $_$;


--
-- Name: fn_enforce_pii_guardrail(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_enforce_pii_guardrail() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
        DECLARE
            detected_key TEXT;
        BEGIN
            IF TG_TABLE_NAME = 'attribution_events' THEN
                IF fn_detect_pii_keys(NEW.raw_payload) THEN
                    detected_key := NULL;
            IF jsonb_path_exists(NEW.raw_payload, '$.**.email') THEN detected_key := 'email'; END IF;
            IF jsonb_path_exists(NEW.raw_payload, '$.**.email_address') THEN detected_key := 'email_address'; END IF;
            IF jsonb_path_exists(NEW.raw_payload, '$.**.phone') THEN detected_key := 'phone'; END IF;
            IF jsonb_path_exists(NEW.raw_payload, '$.**.phone_number') THEN detected_key := 'phone_number'; END IF;
            IF jsonb_path_exists(NEW.raw_payload, '$.**.ssn') THEN detected_key := 'ssn'; END IF;
            IF jsonb_path_exists(NEW.raw_payload, '$.**.social_security_number') THEN detected_key := 'social_security_number'; END IF;
            IF jsonb_path_exists(NEW.raw_payload, '$.**.ip_address') THEN detected_key := 'ip_address'; END IF;
            IF jsonb_path_exists(NEW.raw_payload, '$.**.ip') THEN detected_key := 'ip'; END IF;
            IF jsonb_path_exists(NEW.raw_payload, '$.**.first_name') THEN detected_key := 'first_name'; END IF;
            IF jsonb_path_exists(NEW.raw_payload, '$.**.last_name') THEN detected_key := 'last_name'; END IF;
            IF jsonb_path_exists(NEW.raw_payload, '$.**.full_name') THEN detected_key := 'full_name'; END IF;
            IF jsonb_path_exists(NEW.raw_payload, '$.**.address') THEN detected_key := 'address'; END IF;
            IF jsonb_path_exists(NEW.raw_payload, '$.**.street_address') THEN detected_key := 'street_address'; END IF;
                    RAISE EXCEPTION
                      'PII key detected in %.raw_payload. Ingestion blocked by database policy (Layer 2 guardrail). Key found: %. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from payload before retry.',
                      TG_TABLE_NAME,
                      COALESCE(detected_key, 'unknown')
                    USING ERRCODE = '23514';
                END IF;
            END IF;

            IF TG_TABLE_NAME = 'dead_events' THEN
                detected_key := NULL;
            IF EXISTS ( SELECT 1 FROM jsonb_path_query(NEW.raw_payload, '$.**.email') AS pii(value) WHERE pii.value <> to_jsonb('[REDACTED]'::text)   AND pii.value <> to_jsonb('[REDACTED_B1.4]'::text)   AND pii.value <> '0'::jsonb   AND pii.value <> 'false'::jsonb   AND pii.value <> '[]'::jsonb ) THEN detected_key := 'email'; END IF;
            IF EXISTS ( SELECT 1 FROM jsonb_path_query(NEW.raw_payload, '$.**.email_address') AS pii(value) WHERE pii.value <> to_jsonb('[REDACTED]'::text)   AND pii.value <> to_jsonb('[REDACTED_B1.4]'::text)   AND pii.value <> '0'::jsonb   AND pii.value <> 'false'::jsonb   AND pii.value <> '[]'::jsonb ) THEN detected_key := 'email_address'; END IF;
            IF EXISTS ( SELECT 1 FROM jsonb_path_query(NEW.raw_payload, '$.**.phone') AS pii(value) WHERE pii.value <> to_jsonb('[REDACTED]'::text)   AND pii.value <> to_jsonb('[REDACTED_B1.4]'::text)   AND pii.value <> '0'::jsonb   AND pii.value <> 'false'::jsonb   AND pii.value <> '[]'::jsonb ) THEN detected_key := 'phone'; END IF;
            IF EXISTS ( SELECT 1 FROM jsonb_path_query(NEW.raw_payload, '$.**.phone_number') AS pii(value) WHERE pii.value <> to_jsonb('[REDACTED]'::text)   AND pii.value <> to_jsonb('[REDACTED_B1.4]'::text)   AND pii.value <> '0'::jsonb   AND pii.value <> 'false'::jsonb   AND pii.value <> '[]'::jsonb ) THEN detected_key := 'phone_number'; END IF;
            IF EXISTS ( SELECT 1 FROM jsonb_path_query(NEW.raw_payload, '$.**.ssn') AS pii(value) WHERE pii.value <> to_jsonb('[REDACTED]'::text)   AND pii.value <> to_jsonb('[REDACTED_B1.4]'::text)   AND pii.value <> '0'::jsonb   AND pii.value <> 'false'::jsonb   AND pii.value <> '[]'::jsonb ) THEN detected_key := 'ssn'; END IF;
            IF EXISTS ( SELECT 1 FROM jsonb_path_query(NEW.raw_payload, '$.**.social_security_number') AS pii(value) WHERE pii.value <> to_jsonb('[REDACTED]'::text)   AND pii.value <> to_jsonb('[REDACTED_B1.4]'::text)   AND pii.value <> '0'::jsonb   AND pii.value <> 'false'::jsonb   AND pii.value <> '[]'::jsonb ) THEN detected_key := 'social_security_number'; END IF;
            IF EXISTS ( SELECT 1 FROM jsonb_path_query(NEW.raw_payload, '$.**.ip_address') AS pii(value) WHERE pii.value <> to_jsonb('[REDACTED]'::text)   AND pii.value <> to_jsonb('[REDACTED_B1.4]'::text)   AND pii.value <> '0'::jsonb   AND pii.value <> 'false'::jsonb   AND pii.value <> '[]'::jsonb ) THEN detected_key := 'ip_address'; END IF;
            IF EXISTS ( SELECT 1 FROM jsonb_path_query(NEW.raw_payload, '$.**.ip') AS pii(value) WHERE pii.value <> to_jsonb('[REDACTED]'::text)   AND pii.value <> to_jsonb('[REDACTED_B1.4]'::text)   AND pii.value <> '0'::jsonb   AND pii.value <> 'false'::jsonb   AND pii.value <> '[]'::jsonb ) THEN detected_key := 'ip'; END IF;
            IF EXISTS ( SELECT 1 FROM jsonb_path_query(NEW.raw_payload, '$.**.first_name') AS pii(value) WHERE pii.value <> to_jsonb('[REDACTED]'::text)   AND pii.value <> to_jsonb('[REDACTED_B1.4]'::text)   AND pii.value <> '0'::jsonb   AND pii.value <> 'false'::jsonb   AND pii.value <> '[]'::jsonb ) THEN detected_key := 'first_name'; END IF;
            IF EXISTS ( SELECT 1 FROM jsonb_path_query(NEW.raw_payload, '$.**.last_name') AS pii(value) WHERE pii.value <> to_jsonb('[REDACTED]'::text)   AND pii.value <> to_jsonb('[REDACTED_B1.4]'::text)   AND pii.value <> '0'::jsonb   AND pii.value <> 'false'::jsonb   AND pii.value <> '[]'::jsonb ) THEN detected_key := 'last_name'; END IF;
            IF EXISTS ( SELECT 1 FROM jsonb_path_query(NEW.raw_payload, '$.**.full_name') AS pii(value) WHERE pii.value <> to_jsonb('[REDACTED]'::text)   AND pii.value <> to_jsonb('[REDACTED_B1.4]'::text)   AND pii.value <> '0'::jsonb   AND pii.value <> 'false'::jsonb   AND pii.value <> '[]'::jsonb ) THEN detected_key := 'full_name'; END IF;
            IF EXISTS ( SELECT 1 FROM jsonb_path_query(NEW.raw_payload, '$.**.address') AS pii(value) WHERE pii.value <> to_jsonb('[REDACTED]'::text)   AND pii.value <> to_jsonb('[REDACTED_B1.4]'::text)   AND pii.value <> '0'::jsonb   AND pii.value <> 'false'::jsonb   AND pii.value <> '[]'::jsonb ) THEN detected_key := 'address'; END IF;
            IF EXISTS ( SELECT 1 FROM jsonb_path_query(NEW.raw_payload, '$.**.street_address') AS pii(value) WHERE pii.value <> to_jsonb('[REDACTED]'::text)   AND pii.value <> to_jsonb('[REDACTED_B1.4]'::text)   AND pii.value <> '0'::jsonb   AND pii.value <> 'false'::jsonb   AND pii.value <> '[]'::jsonb ) THEN detected_key := 'street_address'; END IF;
                IF detected_key IS NOT NULL THEN
                    RAISE EXCEPTION
                      'PII key detected in %.raw_payload with unredacted value. Dead-letter payloads must use type-aware redaction masks ([REDACTED], 0, false, []). Key found: %.',
                      TG_TABLE_NAME,
                      detected_key
                    USING ERRCODE = '23514';
                END IF;
            END IF;

            IF TG_TABLE_NAME = 'revenue_ledger' THEN
                IF NEW.metadata IS NOT NULL THEN
                    IF fn_detect_pii_keys(NEW.metadata) THEN
                        detected_key := NULL;
            IF jsonb_path_exists(NEW.metadata, '$.**.email') THEN detected_key := 'email'; END IF;
            IF jsonb_path_exists(NEW.metadata, '$.**.email_address') THEN detected_key := 'email_address'; END IF;
            IF jsonb_path_exists(NEW.metadata, '$.**.phone') THEN detected_key := 'phone'; END IF;
            IF jsonb_path_exists(NEW.metadata, '$.**.phone_number') THEN detected_key := 'phone_number'; END IF;
            IF jsonb_path_exists(NEW.metadata, '$.**.ssn') THEN detected_key := 'ssn'; END IF;
            IF jsonb_path_exists(NEW.metadata, '$.**.social_security_number') THEN detected_key := 'social_security_number'; END IF;
            IF jsonb_path_exists(NEW.metadata, '$.**.ip_address') THEN detected_key := 'ip_address'; END IF;
            IF jsonb_path_exists(NEW.metadata, '$.**.ip') THEN detected_key := 'ip'; END IF;
            IF jsonb_path_exists(NEW.metadata, '$.**.first_name') THEN detected_key := 'first_name'; END IF;
            IF jsonb_path_exists(NEW.metadata, '$.**.last_name') THEN detected_key := 'last_name'; END IF;
            IF jsonb_path_exists(NEW.metadata, '$.**.full_name') THEN detected_key := 'full_name'; END IF;
            IF jsonb_path_exists(NEW.metadata, '$.**.address') THEN detected_key := 'address'; END IF;
            IF jsonb_path_exists(NEW.metadata, '$.**.street_address') THEN detected_key := 'street_address'; END IF;
                        RAISE EXCEPTION
                          'PII key detected in revenue_ledger.metadata. Write blocked by database policy (Layer 2 guardrail). Key found: %. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from metadata before retry.',
                          COALESCE(detected_key, 'unknown')
                        USING ERRCODE = '23514';
                    END IF;
                END IF;
            END IF;

            RETURN NEW;
        END;
        $_$;


--
-- Name: fn_events_prevent_mutation(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_events_prevent_mutation() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            -- Allow migration_owner for emergency repairs (optional)
            IF current_user = 'migration_owner' THEN
                RETURN NULL; -- Allow operation
            END IF;
            
            -- Block all other UPDATE/DELETE attempts
            RAISE EXCEPTION 'attribution_events is append-only; updates and deletes are not allowed. Use INSERT with correlation_id for corrections.';
        END;
        $$;


--
-- Name: fn_guard_attribution_events_payload_identity(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_guard_attribution_events_payload_identity() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
        BEGIN
            IF NEW.raw_payload IS NULL THEN
                RETURN NEW;
            END IF;

            IF (
                jsonb_path_exists(NEW.raw_payload, '$.**.vendor_payload')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.billing_details')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.raw_body')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.raw_body_sha256')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.raw_body_bytes')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.parse_error')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.device_fingerprint')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.user_agent')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.ip_hash')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.session_id')
            ) THEN
                RAISE EXCEPTION
                    'privacy authority violation: forbidden identity/raw-envelope key in attribution_events.raw_payload';
            END IF;

            RETURN NEW;
        END;
        $_$;


--
-- Name: fn_ledger_prevent_mutation(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_ledger_prevent_mutation() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            -- Allow migration_owner for emergency repairs (optional)
            IF current_user = 'migration_owner' THEN
                RETURN NULL; -- Allow operation
            END IF;
            
            -- Block all other UPDATE/DELETE attempts
            RAISE EXCEPTION 'revenue_ledger is immutable; updates and deletes are not allowed. Use INSERT for corrections.';
        END;
        $$;


--
-- Name: fn_llm_call_audit_append_only(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_llm_call_audit_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            RAISE EXCEPTION 'llm_call_audit is append-only; UPDATE and DELETE are forbidden';
        END;
        $$;


--
-- Name: fn_log_channel_assignment_correction(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_log_channel_assignment_correction() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
        DECLARE
            correction_by_val VARCHAR(255);
            correction_reason_val TEXT;
        BEGIN
            -- Only log if the 'channel_code' column actually changed
            IF (NEW.channel_code IS DISTINCT FROM OLD.channel_code) THEN
                -- Read session variables set by application layer
                -- Fall back to 'system' if unset (indicates bypass attempt)
                correction_by_val := COALESCE(
                    current_setting('app.correction_by', true),
                    'system'
                );
                correction_reason_val := COALESCE(
                    NULLIF(current_setting('app.correction_reason', true), ''),
                    'No reason provided'
                );
                
                -- Insert audit record
                INSERT INTO channel_assignment_corrections (
                    tenant_id,
                    entity_type,
                    entity_id,
                    from_channel,
                    to_channel,
                    corrected_by,
                    corrected_at,
                    reason
                )
                VALUES (
                    NEW.tenant_id,
                    'allocation',
                    NEW.id,
                    OLD.channel_code,
                    NEW.channel_code,
                    correction_by_val,
                    NOW(),
                    correction_reason_val
                );
            END IF;
            
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_log_channel_state_change(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_log_channel_state_change() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
        DECLARE
            change_by_val VARCHAR(255);
            change_reason_val TEXT;
        BEGIN
            -- Only log if the 'state' column actually changed
            IF (NEW.state IS DISTINCT FROM OLD.state) THEN
                -- Read session variables set by application layer
                -- Fall back to 'system' if unset (indicates bypass attempt)
                change_by_val := COALESCE(
                    current_setting('app.channel_state_change_by', true),
                    'system'
                );
                change_reason_val := NULLIF(
                    current_setting('app.channel_state_change_reason', true),
                    ''
                );
                
                -- Insert audit record
                INSERT INTO channel_state_transitions (
                    channel_code,
                    from_state,
                    to_state,
                    changed_by,
                    changed_at,
                    reason
                )
                VALUES (
                    NEW.code,
                    OLD.state,
                    NEW.state,
                    change_by_val,
                    NOW(),
                    change_reason_val
                );
            END IF;
            
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_log_revenue_state_change(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_log_revenue_state_change() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
        BEGIN
            IF NEW.state IS DISTINCT FROM OLD.state THEN
                INSERT INTO revenue_state_transitions (
                    ledger_id,
                    tenant_id,
                    from_state,
                    to_state,
                    reason,
                    transitioned_at
                ) VALUES (
                    OLD.id,
                    OLD.tenant_id,
                    OLD.state,
                    NEW.state,
                    COALESCE(NEW.metadata->>'state_change_reason', 'unspecified'),
                    now()
                );
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_scan_pii_contamination(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_scan_pii_contamination() RETURNS integer
    LANGUAGE plpgsql
    AS $$
        DECLARE
            finding_count INTEGER := 0;
            rec RECORD;
            detected_key_var TEXT;
        BEGIN
            -- Scan attribution_events.raw_payload
            FOR rec IN 
                SELECT id, raw_payload 
                FROM attribution_events 
                WHERE fn_detect_pii_keys(raw_payload)
            LOOP
                -- Find first PII key
                SELECT key INTO detected_key_var
                FROM jsonb_object_keys(rec.raw_payload) key
                WHERE key IN (
                    'email', 'email_address', 
                    'phone', 'phone_number', 
                    'ssn', 'social_security_number', 
                    'ip_address', 'ip', 
                    'first_name', 'last_name', 'full_name', 
                    'address', 'street_address'
                )
                LIMIT 1;
                
                INSERT INTO pii_audit_findings (
                    table_name, 
                    column_name, 
                    record_id, 
                    detected_key,
                    sample_snippet
                )
                VALUES (
                    'attribution_events', 
                    'raw_payload', 
                    rec.id, 
                    detected_key_var,
                    'Redacted for security'  -- Do not log actual PII values
                );
                
                finding_count := finding_count + 1;
            END LOOP;
            
            -- Scan dead_events.raw_payload
            FOR rec IN 
                SELECT id, raw_payload 
                FROM dead_events 
                WHERE fn_detect_pii_keys(raw_payload)
            LOOP
                -- Find first PII key
                SELECT key INTO detected_key_var
                FROM jsonb_object_keys(rec.raw_payload) key
                WHERE key IN (
                    'email', 'email_address', 
                    'phone', 'phone_number', 
                    'ssn', 'social_security_number', 
                    'ip_address', 'ip', 
                    'first_name', 'last_name', 'full_name', 
                    'address', 'street_address'
                )
                LIMIT 1;
                
                INSERT INTO pii_audit_findings (
                    table_name, 
                    column_name, 
                    record_id, 
                    detected_key,
                    sample_snippet
                )
                VALUES (
                    'dead_events', 
                    'raw_payload', 
                    rec.id, 
                    detected_key_var,
                    'Redacted for security'
                );
                
                finding_count := finding_count + 1;
            END LOOP;
            
            -- Scan revenue_ledger.metadata (only non-NULL)
            FOR rec IN 
                SELECT id, metadata 
                FROM revenue_ledger 
                WHERE metadata IS NOT NULL AND fn_detect_pii_keys(metadata)
            LOOP
                -- Find first PII key
                SELECT key INTO detected_key_var
                FROM jsonb_object_keys(rec.metadata) key
                WHERE key IN (
                    'email', 'email_address', 
                    'phone', 'phone_number', 
                    'ssn', 'social_security_number', 
                    'ip_address', 'ip', 
                    'first_name', 'last_name', 'full_name', 
                    'address', 'street_address'
                )
                LIMIT 1;
                
                INSERT INTO pii_audit_findings (
                    table_name, 
                    column_name, 
                    record_id, 
                    detected_key,
                    sample_snippet
                )
                VALUES (
                    'revenue_ledger', 
                    'metadata', 
                    rec.id, 
                    detected_key_var,
                    'Redacted for security'
                );
                
                finding_count := finding_count + 1;
            END LOOP;
            
            RETURN finding_count;
        END;
        $$;


--
-- Name: reject_reserved_trust_action_scope(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.reject_reserved_trust_action_scope() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.scope_value IN (
                'trust.action.propose',
                'trust.action.execute',
                'trust.action.approve',
                'trust.action.reject',
                'auto_executable_within_policy'
            ) THEN
                RAISE EXCEPTION 'reserved_trust_action_scope_rejected:%', NEW.scope_value
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: skeldir_database_construction_revisions(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.skeldir_database_construction_revisions() RETURNS SETOF text
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
            SELECT version_num FROM public.alembic_version
        $$;


--
-- Name: trust_access_log_issuance_authority_guard(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trust_access_log_issuance_authority_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
        DECLARE
            table_owner text;
            consequence_changed boolean;
            attempt record;
        BEGIN
            SELECT r.rolname INTO table_owner
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_roles r ON r.oid = c.relowner
            WHERE c.oid = 'public.trust_access_log'::regclass;
            IF TG_OP = 'INSERT' THEN
                IF (NEW.event_type = 'issuance' AND NEW.issuance_state <> 'authorized')
                   OR (NEW.event_type <> 'issuance'
                       AND NEW.issuance_state <> 'not_applicable') THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:insert_state:%',
                        NEW.issuance_state USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:tenant_rebind'
                    USING ERRCODE = '42501';
            END IF;
            consequence_changed :=
                NEW.issuance_state IS DISTINCT FROM OLD.issuance_state
                OR NEW.issued_at IS DISTINCT FROM OLD.issued_at
                OR NEW.issuance_attempted_at IS DISTINCT FROM OLD.issuance_attempted_at
                OR NEW.issuance_outcome_unknown_at IS DISTINCT FROM OLD.issuance_outcome_unknown_at
                OR NEW.known_signature_at IS DISTINCT FROM OLD.known_signature_at
                OR NEW.issued_attempt_id IS DISTINCT FROM OLD.issued_attempt_id
                OR NEW.issued_signing_key_id IS DISTINCT FROM OLD.issued_signing_key_id
                OR NEW.issued_signature_hash IS DISTINCT FROM OLD.issued_signature_hash
                OR NEW.issued_signature IS DISTINCT FROM OLD.issued_signature
                OR NEW.issued_envelope IS DISTINCT FROM OLD.issued_envelope
                OR NEW.issuance_attempt_count IS DISTINCT FROM OLD.issuance_attempt_count
                OR NEW.issuance_unknown_outcome_count IS DISTINCT FROM OLD.issuance_unknown_outcome_count;
            IF NOT consequence_changed THEN RETURN NEW; END IF;
            IF OLD.issuance_state IN (
                'issued', 'issued_pre_xvii', 'issued_legacy', 'not_applicable'
            ) THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:terminal:%',
                    OLD.issuance_state USING ERRCODE = '42501';
            END IF;
            IF OLD.issuance_state = 'signing'
               AND NEW.issuance_state = 'signature_known' THEN
                IF session_user NOT IN ('app_trust_signer', table_owner) THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:signer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
                SELECT * INTO attempt FROM public.trust_issuance_attempts
                WHERE tenant_id = NEW.tenant_id AND audit_ref = NEW.audit_ref
                  AND id = NEW.issued_attempt_id
                  AND attempt_state = 'signature_known';
                IF NOT FOUND OR NEW.known_signature_at IS DISTINCT FROM attempt.signature_known_at THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:known_attempt'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF OLD.issuance_state = 'signature_known'
                  AND NEW.issuance_state = 'issued' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
                SELECT * INTO attempt FROM public.trust_issuance_attempts
                WHERE tenant_id = NEW.tenant_id AND audit_ref = NEW.audit_ref
                  AND id = OLD.issued_attempt_id
                  AND attempt_state = 'signature_known';
                IF NOT FOUND
                   OR NEW.issued_attempt_id IS DISTINCT FROM attempt.id
                   OR NEW.issued_signing_key_id IS DISTINCT FROM attempt.signing_key_id
                   OR NEW.issued_signature_hash IS DISTINCT FROM attempt.signature_hash
                   OR NEW.issued_signature IS DISTINCT FROM attempt.signature
                   OR NEW.issued_envelope IS DISTINCT FROM attempt.signed_envelope THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:evidence_correspondence'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF OLD.issuance_state = 'signing'
                  AND NEW.issuance_state = 'signature_outcome_unknown' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSIF OLD.issuance_state = 'authorized'
                  AND NEW.issuance_state IN ('signing', 'failed')
                  OR OLD.issuance_state IN ('failed', 'signature_outcome_unknown')
                     AND NEW.issuance_state = 'signing' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSE
                RAISE EXCEPTION 'trust_issuance_authority_violation:transition:%->%',
                    OLD.issuance_state, NEW.issuance_state USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_attempt_count < OLD.issuance_attempt_count
               OR NEW.issuance_unknown_outcome_count < OLD.issuance_unknown_outcome_count THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:lineage_regression'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_state = 'signing' AND OLD.issuance_state <> 'signing'
               AND NEW.issuance_attempt_count <> OLD.issuance_attempt_count + 1 THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:attempt_not_counted'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_state = 'signature_outcome_unknown'
               AND OLD.issuance_state <> 'signature_outcome_unknown'
               AND NEW.issuance_unknown_outcome_count <> OLD.issuance_unknown_outcome_count + 1 THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:unknown_not_counted'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: trust_access_log_witness_immutability_guard(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trust_access_log_witness_immutability_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
        DECLARE
            principal_is_superuser boolean;
            table_owner_oid oid;
            mutable_columns text[] := ARRAY['replay_count', 'last_replayed_at', 'updated_at', 'issuance_state', 'issued_at', 'issuance_attempted_at', 'issuance_outcome_unknown_at', 'known_signature_at', 'issued_attempt_id', 'issued_signing_key_id', 'issued_signature_hash', 'issued_signature', 'issued_envelope', 'issuance_attempt_count', 'issuance_unknown_outcome_count']::text[];
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
        $$;


--
-- Name: trust_enforce_issuance_consequence_authority(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trust_enforce_issuance_consequence_authority() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
            IF NEW.idempotency_key_hash IS DISTINCT FROM ledger_idempotency_key_hash
               OR NEW.subject_type IS DISTINCT FROM ledger_subject_type
               OR NEW.subject_ref_hash IS DISTINCT FROM ledger_subject_ref_hash
               OR NEW.envelope_hash IS DISTINCT FROM ledger_envelope_hash
               OR NEW.semantic_truth_hash IS DISTINCT FROM ledger_semantic_truth_hash
               OR NEW.policy_state IS DISTINCT FROM ledger_policy_state
               OR NEW.audit_hash IS DISTINCT FROM ledger_audit_hash
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
        $$;


--
-- Name: trust_enforce_issuance_history_immutable(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trust_enforce_issuance_history_immutable() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
        $$;


--
-- Name: trust_export_artifact_attempt_guard(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trust_export_artifact_attempt_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
        DECLARE table_owner text;
        BEGIN
            SELECT r.rolname INTO table_owner
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_roles r ON r.oid = c.relowner
            WHERE c.oid = 'public.trust_export_artifact_attempts'::regclass;
            IF TG_OP = 'INSERT' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner)
                   OR NEW.attempt_state <> 'signing' THEN
                    RAISE EXCEPTION 'trust_export_attempt_authority_violation:insert:%',
                        session_user USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
               OR NEW.id IS DISTINCT FROM OLD.id
               OR NEW.request_binding_hash IS DISTINCT FROM OLD.request_binding_hash
               OR NEW.page_start IS DISTINCT FROM OLD.page_start
               OR NEW.attempt_number IS DISTINCT FROM OLD.attempt_number THEN
                RAISE EXCEPTION 'trust_export_attempt_authority_violation:identity'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.attempt_state <> 'signing' THEN
                RAISE EXCEPTION 'trust_export_attempt_authority_violation:terminal:%',
                    OLD.attempt_state USING ERRCODE = '42501';
            END IF;
            IF NEW.attempt_state = 'issued' THEN
                IF session_user NOT IN ('app_trust_signer', table_owner) THEN
                    RAISE EXCEPTION 'trust_export_attempt_authority_violation:signer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSIF NEW.attempt_state = 'signature_outcome_unknown' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_export_attempt_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSE
                RAISE EXCEPTION 'trust_export_attempt_authority_violation:transition:%->%',
                    OLD.attempt_state, NEW.attempt_state USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: trust_issuance_attempt_guard(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trust_issuance_attempt_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
        DECLARE table_owner text;
        BEGIN
            SELECT r.rolname INTO table_owner
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_roles r ON r.oid = c.relowner
            WHERE c.oid = 'public.trust_issuance_attempts'::regclass;
            IF TG_OP = 'INSERT' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner)
                   OR NEW.attempt_state <> 'signing' THEN
                    RAISE EXCEPTION 'trust_attempt_authority_violation:insert:%',
                        session_user USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
               OR NEW.audit_ref IS DISTINCT FROM OLD.audit_ref
               OR NEW.id IS DISTINCT FROM OLD.id
               OR NEW.attempt_number IS DISTINCT FROM OLD.attempt_number
               OR NEW.started_at IS DISTINCT FROM OLD.started_at THEN
                RAISE EXCEPTION 'trust_attempt_authority_violation:identity'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.attempt_state IN ('signature_outcome_unknown', 'issued') THEN
                RAISE EXCEPTION 'trust_attempt_authority_violation:terminal:%',
                    OLD.attempt_state USING ERRCODE = '42501';
            END IF;
            IF OLD.attempt_state = 'signing'
               AND NEW.attempt_state = 'signature_known' THEN
                IF session_user NOT IN ('app_trust_signer', table_owner) THEN
                    RAISE EXCEPTION 'trust_attempt_authority_violation:signer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSIF OLD.attempt_state = 'signing'
                  AND NEW.attempt_state = 'signature_outcome_unknown' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_attempt_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSIF OLD.attempt_state = 'signature_known'
                  AND NEW.attempt_state = 'issued' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_attempt_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSE
                RAISE EXCEPTION 'trust_attempt_authority_violation:transition:%->%',
                    OLD.attempt_state, NEW.attempt_state USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: resolve_tenant_webhook_secrets(text); Type: FUNCTION; Schema: security; Owner: -
--

CREATE FUNCTION security.resolve_tenant_webhook_secrets(api_key_hash text) RETURNS TABLE(tenant_id uuid, tenant_updated_at timestamp with time zone, shopify_webhook_secret_ciphertext bytea, shopify_webhook_secret_key_id text, stripe_webhook_secret_ciphertext bytea, stripe_webhook_secret_key_id text, paypal_webhook_secret_ciphertext bytea, paypal_webhook_secret_key_id text, woocommerce_webhook_secret_ciphertext bytea, woocommerce_webhook_secret_key_id text)
    LANGUAGE sql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $_$
          SELECT
            t.id AS tenant_id,
            t.updated_at AS tenant_updated_at,
            t.shopify_webhook_secret_ciphertext,
            t.shopify_webhook_secret_key_id,
            t.stripe_webhook_secret_ciphertext,
            t.stripe_webhook_secret_key_id,
            t.paypal_webhook_secret_ciphertext,
            t.paypal_webhook_secret_key_id,
            t.woocommerce_webhook_secret_ciphertext,
            t.woocommerce_webhook_secret_key_id
          FROM public.tenants t
          WHERE t.api_key_hash = $1
          LIMIT 1
        $_$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: agent_clients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_clients (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    client_name text NOT NULL,
    client_display_hash text NOT NULL,
    audience text NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT ck_agent_clients_audience_not_empty CHECK ((length(btrim(audience)) > 0)),
    CONSTRAINT ck_agent_clients_display_hash CHECK ((client_display_hash ~ '^sha256:[0-9a-f]{64}$'::text)),
    CONSTRAINT ck_agent_clients_status CHECK ((status = ANY (ARRAY['active'::text, 'revoked'::text, 'suspended'::text])))
);

ALTER TABLE ONLY public.agent_clients FORCE ROW LEVEL SECURITY;


--
-- Name: agent_scope_grants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_scope_grants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    agent_client_id uuid NOT NULL,
    scope_value text NOT NULL,
    granted_at timestamp with time zone DEFAULT now() NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT ck_agent_scope_grants_scope_value CHECK (((scope_value = ANY (ARRAY['trust.envelope.read'::text, 'trust.envelope.verify'::text, 'trust.audit.read'::text, 'trust.keys.read'::text, 'trust.export.create_limited'::text])) AND (scope_value <> ALL (ARRAY['trust.action.propose'::text, 'trust.action.execute'::text, 'trust.action.approve'::text, 'trust.action.reject'::text, 'auto_executable_within_policy'::text]))))
);

ALTER TABLE ONLY public.agent_scope_grants FORCE ROW LEVEL SECURITY;


--
-- Name: agent_service_credentials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_service_credentials (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    agent_client_id uuid NOT NULL,
    token_prefix text NOT NULL,
    token_hash text NOT NULL,
    hash_algorithm text DEFAULT 'sha256'::text NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    issued_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone,
    revoked_at timestamp with time zone,
    CONSTRAINT ck_agent_service_credentials_hash_algorithm CHECK ((hash_algorithm = 'sha256'::text)),
    CONSTRAINT ck_agent_service_credentials_prefix_len CHECK ((length(token_prefix) = 8)),
    CONSTRAINT ck_agent_service_credentials_status CHECK ((status = ANY (ARRAY['active'::text, 'revoked'::text, 'expired'::text]))),
    CONSTRAINT ck_agent_service_credentials_token_hash CHECK ((token_hash ~ '^[0-9a-f]{64}$'::text))
);

ALTER TABLE ONLY public.agent_service_credentials FORCE ROW LEVEL SECURITY;


--
-- Name: agent_token_revocations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_token_revocations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    agent_client_id uuid NOT NULL,
    token_prefix text NOT NULL,
    reason_code text NOT NULL,
    revoked_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_agent_token_revocations_prefix_len CHECK ((length(token_prefix) = 8))
);

ALTER TABLE ONLY public.agent_token_revocations FORCE ROW LEVEL SECURITY;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: attribution_allocations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.attribution_allocations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    event_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    channel_code text NOT NULL,
    allocated_revenue_cents integer DEFAULT 0 NOT NULL,
    model_metadata jsonb,
    correlation_id uuid,
    allocation_ratio numeric(6,5) DEFAULT 0.0 NOT NULL,
    model_version text DEFAULT 'unknown'::text NOT NULL,
    model_type character varying(50) NOT NULL,
    confidence_score numeric(4,3) NOT NULL,
    credible_interval_lower_cents integer,
    credible_interval_upper_cents integer,
    convergence_r_hat numeric(5,4),
    effective_sample_size integer,
    verified boolean DEFAULT false NOT NULL,
    verification_source character varying(50),
    verification_timestamp timestamp with time zone,
    recompute_job_id uuid,
    CONSTRAINT attribution_allocations_allocated_revenue_cents_check CHECK ((allocated_revenue_cents >= 0)),
    CONSTRAINT ck_allocations_confidence_score CHECK (((confidence_score >= (0)::numeric) AND (confidence_score <= (1)::numeric))),
    CONSTRAINT ck_attribution_allocations_allocation_ratio_bounds CHECK (((allocation_ratio >= (0)::numeric) AND (allocation_ratio <= (1)::numeric))),
    CONSTRAINT ck_attribution_allocations_revenue_positive CHECK ((allocated_revenue_cents >= 0))
);

ALTER TABLE ONLY public.attribution_allocations FORCE ROW LEVEL SECURITY;


--
-- Name: attribution_commerce_identities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.attribution_commerce_identities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    attribution_event_id uuid NOT NULL,
    provider character varying(32) NOT NULL,
    canonical_commerce_reference character varying(255) NOT NULL,
    source character varying(64) DEFAULT 'ingestion_runtime'::character varying NOT NULL,
    first_observed_at timestamp with time zone DEFAULT now() NOT NULL,
    last_observed_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_attr_commerce_identity_observed_time_order CHECK ((last_observed_at >= first_observed_at)),
    CONSTRAINT ck_attr_commerce_identity_provider_not_blank CHECK ((char_length((provider)::text) > 0)),
    CONSTRAINT ck_attr_commerce_identity_reference_not_blank CHECK ((char_length((canonical_commerce_reference)::text) > 0))
);

ALTER TABLE ONLY public.attribution_commerce_identities FORCE ROW LEVEL SECURITY;


--
-- Name: attribution_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.attribution_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    occurred_at timestamp with time zone NOT NULL,
    external_event_id text,
    correlation_id uuid,
    session_id uuid NOT NULL,
    revenue_cents integer DEFAULT 0 NOT NULL,
    raw_payload jsonb NOT NULL,
    idempotency_key character varying(255) NOT NULL,
    event_type character varying(50) NOT NULL,
    channel character varying(100) NOT NULL,
    campaign_id character varying(255),
    conversion_value_cents integer,
    currency character varying(3) DEFAULT 'USD'::character varying,
    event_timestamp timestamp with time zone NOT NULL,
    processed_at timestamp with time zone DEFAULT now(),
    processing_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    retry_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT attribution_events_revenue_cents_check CHECK ((revenue_cents >= 0)),
    CONSTRAINT ck_attribution_events_processing_status_valid CHECK (((processing_status)::text = ANY ((ARRAY['pending'::character varying, 'processed'::character varying, 'failed'::character varying])::text[]))),
    CONSTRAINT ck_attribution_events_retry_count_positive CHECK ((retry_count >= 0)),
    CONSTRAINT ck_attribution_events_revenue_positive CHECK ((revenue_cents >= 0))
);

ALTER TABLE ONLY public.attribution_events FORCE ROW LEVEL SECURITY;


--
-- Name: attribution_recompute_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.attribution_recompute_jobs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    window_start timestamp with time zone NOT NULL,
    window_end timestamp with time zone NOT NULL,
    model_version text DEFAULT '1.0.0'::text NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    run_count integer DEFAULT 0 NOT NULL,
    last_correlation_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    replay_event_created_ceiling timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_attribution_recompute_jobs_run_count_positive CHECK ((run_count >= 0)),
    CONSTRAINT ck_attribution_recompute_jobs_status_valid CHECK ((status = ANY (ARRAY['pending'::text, 'running'::text, 'succeeded'::text, 'failed'::text]))),
    CONSTRAINT ck_attribution_recompute_jobs_window_bounds_valid CHECK ((window_end > window_start))
);

ALTER TABLE ONLY public.attribution_recompute_jobs FORCE ROW LEVEL SECURITY;


--
-- Name: auth_access_token_denylist; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_access_token_denylist (
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    jti uuid NOT NULL,
    revoked_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    reason text DEFAULT 'logout'::text NOT NULL,
    CONSTRAINT ck_auth_access_token_denylist_reason_not_empty CHECK ((length(TRIM(BOTH FROM reason)) > 0))
);

ALTER TABLE ONLY public.auth_access_token_denylist FORCE ROW LEVEL SECURITY;


--
-- Name: auth_refresh_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_refresh_tokens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    family_id uuid NOT NULL,
    token_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    rotated_at timestamp with time zone,
    replaced_by_id uuid,
    revoked_at timestamp with time zone,
    last_used_at timestamp with time zone,
    CONSTRAINT ck_auth_refresh_tokens_hash_not_empty CHECK ((length(TRIM(BOTH FROM token_hash)) > 0))
);

ALTER TABLE ONLY public.auth_refresh_tokens FORCE ROW LEVEL SECURITY;


--
-- Name: auth_user_token_cutoffs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_user_token_cutoffs (
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    tokens_invalid_before timestamp with time zone NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by_user_id uuid
);

ALTER TABLE ONLY public.auth_user_token_cutoffs FORCE ROW LEVEL SECURITY;


--
-- Name: b23_exception_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b23_exception_records (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    match_verdict_id uuid NOT NULL,
    provider character varying(32) NOT NULL,
    canonical_commerce_reference character varying(255) NOT NULL,
    status character varying(16) NOT NULL,
    severity character varying(16) NOT NULL,
    resolution_code character varying(64),
    resolution_notes text,
    raised_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    dismissed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_b23_exception_records_resolution_code_required CHECK ((((status)::text <> ALL ((ARRAY['resolved'::character varying, 'dismissed'::character varying])::text[])) OR ((resolution_code IS NOT NULL) AND (char_length(TRIM(BOTH FROM resolution_code)) > 0)))),
    CONSTRAINT ck_b23_exception_records_severity CHECK (((severity)::text = ANY ((ARRAY['flagged'::character varying, 'alert'::character varying])::text[]))),
    CONSTRAINT ck_b23_exception_records_status CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'acknowledged'::character varying, 'resolved'::character varying, 'dismissed'::character varying])::text[])))
);

ALTER TABLE ONLY public.b23_exception_records FORCE ROW LEVEL SECURITY;


--
-- Name: b23_match_task_dispatches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b23_match_task_dispatches (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    webhook_ingress_identity_id uuid NOT NULL,
    task_id character varying(155) NOT NULL,
    task_name character varying(255) NOT NULL,
    queue character varying(100) NOT NULL,
    routing_key character varying(255) NOT NULL,
    correlation_id uuid NOT NULL,
    provider character varying(32) NOT NULL,
    provider_native_event_reference character varying(255) NOT NULL,
    provider_native_commerce_reference character varying(255) NOT NULL,
    normalized_commerce_reference_value character varying(255) NOT NULL,
    status character varying(32) DEFAULT 'dispatched'::character varying NOT NULL,
    dispatched_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_b23_match_task_dispatches_queue CHECK (((queue)::text = 'b23_match_engine'::text)),
    CONSTRAINT ck_b23_match_task_dispatches_status CHECK (((status)::text = 'dispatched'::text))
);

ALTER TABLE ONLY public.b23_match_task_dispatches FORCE ROW LEVEL SECURITY;


--
-- Name: b23_match_verdicts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b23_match_verdicts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    attribution_event_id uuid,
    webhook_ingress_identity_id uuid,
    provider character varying(32) NOT NULL,
    canonical_commerce_reference character varying(255) NOT NULL,
    provider_native_event_reference character varying(255) NOT NULL,
    provider_native_commerce_reference character varying(255) NOT NULL,
    status character varying(32) NOT NULL,
    match_quality character varying(16) NOT NULL,
    attributed_amount_minor integer NOT NULL,
    verified_amount_minor integer NOT NULL,
    currency_code character(3) NOT NULL,
    pending_since timestamp with time zone DEFAULT now() NOT NULL,
    provisional_expires_at timestamp with time zone,
    confirmed_at timestamp with time zone,
    adjusted_at timestamp with time zone,
    unmatched_marked_at timestamp with time zone,
    last_transition_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    canonical_expected_gross_amount_minor integer NOT NULL,
    canonical_captured_gross_amount_minor integer NOT NULL,
    canonical_net_verified_amount_minor integer NOT NULL,
    discrepancy_amount_minor integer NOT NULL,
    discrepancy_ratio_bps integer NOT NULL,
    discrepancy_band character varying(32) NOT NULL,
    CONSTRAINT ck_b23_match_verdicts_attributed_amount_non_negative CHECK ((attributed_amount_minor >= 0)),
    CONSTRAINT ck_b23_match_verdicts_canonical_reference_not_blank CHECK ((char_length((canonical_commerce_reference)::text) > 0)),
    CONSTRAINT ck_b23_match_verdicts_captured_amount_non_negative CHECK ((canonical_captured_gross_amount_minor >= 0)),
    CONSTRAINT ck_b23_match_verdicts_captured_matches_legacy CHECK ((canonical_captured_gross_amount_minor = verified_amount_minor)),
    CONSTRAINT ck_b23_match_verdicts_currency_code_len CHECK ((char_length(TRIM(BOTH FROM currency_code)) = 3)),
    CONSTRAINT ck_b23_match_verdicts_discrepancy_amount_consistency CHECK ((discrepancy_amount_minor = abs((canonical_expected_gross_amount_minor - canonical_captured_gross_amount_minor)))),
    CONSTRAINT ck_b23_match_verdicts_discrepancy_band CHECK (((discrepancy_band)::text = ANY ((ARRAY['exact'::character varying, 'within_tolerance'::character varying, 'over_tolerance'::character varying, 'severe_gap'::character varying])::text[]))),
    CONSTRAINT ck_b23_match_verdicts_discrepancy_ratio_consistency CHECK ((discrepancy_ratio_bps =
CASE
    WHEN (canonical_expected_gross_amount_minor = 0) THEN 0
    ELSE ((discrepancy_amount_minor * 10000) / canonical_expected_gross_amount_minor)
END)),
    CONSTRAINT ck_b23_match_verdicts_discrepancy_ratio_range CHECK (((discrepancy_ratio_bps >= '-1000000'::integer) AND (discrepancy_ratio_bps <= 1000000))),
    CONSTRAINT ck_b23_match_verdicts_expected_amount_non_negative CHECK ((canonical_expected_gross_amount_minor >= 0)),
    CONSTRAINT ck_b23_match_verdicts_expected_matches_legacy CHECK ((canonical_expected_gross_amount_minor = attributed_amount_minor)),
    CONSTRAINT ck_b23_match_verdicts_match_quality CHECK (((match_quality)::text = ANY ((ARRAY['high'::character varying, 'medium'::character varying, 'low'::character varying])::text[]))),
    CONSTRAINT ck_b23_match_verdicts_net_amount_non_negative CHECK ((canonical_net_verified_amount_minor >= 0)),
    CONSTRAINT ck_b23_match_verdicts_provider_commerce_reference_not_blank CHECK ((char_length((provider_native_commerce_reference)::text) > 0)),
    CONSTRAINT ck_b23_match_verdicts_provider_event_reference_not_blank CHECK ((char_length((provider_native_event_reference)::text) > 0)),
    CONSTRAINT ck_b23_match_verdicts_provider_not_blank CHECK ((char_length((provider)::text) > 0)),
    CONSTRAINT ck_b23_match_verdicts_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'matched_provisional'::character varying, 'matched_confirmed'::character varying, 'adjusted'::character varying, 'unmatched'::character varying])::text[]))),
    CONSTRAINT ck_b23_match_verdicts_verified_amount_non_negative CHECK ((verified_amount_minor >= 0))
);

ALTER TABLE ONLY public.b23_match_verdicts FORCE ROW LEVEL SECURITY;


--
-- Name: b23_revenue_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b23_revenue_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    match_verdict_id uuid,
    webhook_ingress_identity_id uuid,
    provider character varying(32) NOT NULL,
    provider_native_event_reference character varying(255) NOT NULL,
    provider_native_commerce_reference character varying(255) NOT NULL,
    canonical_commerce_reference character varying(255) NOT NULL,
    event_type character varying(32) NOT NULL,
    currency_code character(3) NOT NULL,
    event_occurred_at timestamp with time zone NOT NULL,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    captured_amount_minor integer,
    refund_amount_minor integer,
    chargeback_amount_minor integer,
    reversal_amount_minor integer,
    net_effect_sign smallint NOT NULL,
    is_gross_capture_correction boolean DEFAULT false NOT NULL,
    CONSTRAINT ck_b23_revenue_events_canonical_reference_not_blank CHECK ((char_length((canonical_commerce_reference)::text) > 0)),
    CONSTRAINT ck_b23_revenue_events_captured_amount_non_negative CHECK (((captured_amount_minor IS NULL) OR (captured_amount_minor >= 0))),
    CONSTRAINT ck_b23_revenue_events_chargeback_amount_non_negative CHECK (((chargeback_amount_minor IS NULL) OR (chargeback_amount_minor >= 0))),
    CONSTRAINT ck_b23_revenue_events_currency_code_len CHECK ((char_length(TRIM(BOTH FROM currency_code)) = 3)),
    CONSTRAINT ck_b23_revenue_events_event_type CHECK (((event_type)::text = ANY ((ARRAY['payment_capture'::character varying, 'partial_refund'::character varying, 'full_refund'::character varying, 'chargeback_opened'::character varying, 'chargeback_won'::character varying, 'chargeback_lost'::character varying, 'reversal'::character varying])::text[]))),
    CONSTRAINT ck_b23_revenue_events_net_effect_sign CHECK ((net_effect_sign = ANY (ARRAY['-1'::integer, 0, 1]))),
    CONSTRAINT ck_b23_revenue_events_net_effect_sign_by_event_type CHECK (((((event_type)::text = 'payment_capture'::text) AND (net_effect_sign = 1)) OR (((event_type)::text = ANY ((ARRAY['partial_refund'::character varying, 'full_refund'::character varying])::text[])) AND (net_effect_sign = '-1'::integer)) OR (((event_type)::text = 'chargeback_opened'::text) AND (net_effect_sign = 0)) OR (((event_type)::text = 'chargeback_lost'::text) AND (net_effect_sign = '-1'::integer)) OR (((event_type)::text = ANY ((ARRAY['chargeback_won'::character varying, 'reversal'::character varying])::text[])) AND (net_effect_sign = 1)))),
    CONSTRAINT ck_b23_revenue_events_operand_columns_by_event_type CHECK (((((event_type)::text = 'payment_capture'::text) AND (captured_amount_minor IS NOT NULL) AND (refund_amount_minor IS NULL) AND (chargeback_amount_minor IS NULL) AND (reversal_amount_minor IS NULL)) OR (((event_type)::text = ANY ((ARRAY['partial_refund'::character varying, 'full_refund'::character varying])::text[])) AND (captured_amount_minor IS NULL) AND (refund_amount_minor IS NOT NULL) AND (chargeback_amount_minor IS NULL) AND (reversal_amount_minor IS NULL)) OR (((event_type)::text = ANY ((ARRAY['chargeback_opened'::character varying, 'chargeback_won'::character varying, 'chargeback_lost'::character varying])::text[])) AND (captured_amount_minor IS NULL) AND (refund_amount_minor IS NULL) AND (chargeback_amount_minor IS NOT NULL) AND (reversal_amount_minor IS NULL)) OR (((event_type)::text = 'reversal'::text) AND (captured_amount_minor IS NULL) AND (refund_amount_minor IS NULL) AND (chargeback_amount_minor IS NULL) AND (reversal_amount_minor IS NOT NULL)))),
    CONSTRAINT ck_b23_revenue_events_provider_commerce_reference_not_blank CHECK ((char_length((provider_native_commerce_reference)::text) > 0)),
    CONSTRAINT ck_b23_revenue_events_provider_event_reference_not_blank CHECK ((char_length((provider_native_event_reference)::text) > 0)),
    CONSTRAINT ck_b23_revenue_events_provider_not_blank CHECK ((char_length((provider)::text) > 0)),
    CONSTRAINT ck_b23_revenue_events_refund_amount_non_negative CHECK (((refund_amount_minor IS NULL) OR (refund_amount_minor >= 0))),
    CONSTRAINT ck_b23_revenue_events_reversal_amount_non_negative CHECK (((reversal_amount_minor IS NULL) OR (reversal_amount_minor >= 0))),
    CONSTRAINT ck_b23_revenue_events_split_operand_exactly_one_non_null CHECK (((((
CASE
    WHEN (captured_amount_minor IS NULL) THEN 0
    ELSE 1
END +
CASE
    WHEN (refund_amount_minor IS NULL) THEN 0
    ELSE 1
END) +
CASE
    WHEN (chargeback_amount_minor IS NULL) THEN 0
    ELSE 1
END) +
CASE
    WHEN (reversal_amount_minor IS NULL) THEN 0
    ELSE 1
END) = 1))
);

ALTER TABLE ONLY public.b23_revenue_events FORCE ROW LEVEL SECURITY;


--
-- Name: b23_webhook_ingestion_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b23_webhook_ingestion_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    provider character varying(32) NOT NULL,
    provider_native_event_reference character varying(255),
    ingestion_status character varying(16) NOT NULL,
    failure_reason text,
    correlation_id uuid,
    received_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_b23_webhook_ingestion_logs_failure_reason_when_failed CHECK ((((ingestion_status)::text <> 'failed'::text) OR ((failure_reason IS NOT NULL) AND (char_length(TRIM(BOTH FROM failure_reason)) > 0)))),
    CONSTRAINT ck_b23_webhook_ingestion_logs_provider_not_blank CHECK ((char_length((provider)::text) > 0)),
    CONSTRAINT ck_b23_webhook_ingestion_logs_status CHECK (((ingestion_status)::text = ANY ((ARRAY['success'::character varying, 'failed'::character varying])::text[])))
);

ALTER TABLE ONLY public.b23_webhook_ingestion_logs FORCE ROW LEVEL SECURITY;


--
-- Name: b24_active_execution_leases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b24_active_execution_leases (
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    fit_id uuid,
    active_source_snapshot_hash character varying(64),
    latest_desired_source_snapshot_hash character varying(64),
    status character varying(32) DEFAULT 'claiming'::character varying NOT NULL,
    needs_refit_after_current boolean DEFAULT false NOT NULL,
    lease_owner character varying(128),
    lease_acquired_at timestamp with time zone DEFAULT now() NOT NULL,
    leased_until timestamp with time zone NOT NULL,
    heartbeat_at timestamp with time zone,
    stale_recovered_at timestamp with time zone,
    terminal_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_b24_active_execution_active_fit_required CHECK ((((status)::text = ANY ((ARRAY['claiming'::character varying, 'profiling'::character varying, 'profile_passed'::character varying, 'profile_rejected'::character varying, 'profile_superseded'::character varying, 'profile_timeout'::character varying, 'profile_failed'::character varying])::text[])) OR (fit_id IS NOT NULL))),
    CONSTRAINT ck_b24_active_execution_active_hash_sha256 CHECK (((active_source_snapshot_hash IS NULL) OR ((active_source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_b24_active_execution_desired_hash_sha256 CHECK (((latest_desired_source_snapshot_hash IS NULL) OR ((latest_desired_source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_b24_active_execution_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_b24_active_execution_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_b24_active_execution_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_b24_active_execution_status CHECK (((status)::text = ANY ((ARRAY['profiling'::character varying, 'profile_passed'::character varying, 'profile_rejected'::character varying, 'profile_superseded'::character varying, 'profile_timeout'::character varying, 'profile_failed'::character varying, 'claiming'::character varying, 'dispatch_pending'::character varying, 'dispatched'::character varying, 'running'::character varying, 'cancel_requested'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying, 'stale_recovered'::character varying])::text[])))
);

ALTER TABLE ONLY public.b24_active_execution_leases FORCE ROW LEVEL SECURITY;


--
-- Name: b24_dirty_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b24_dirty_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    dirty_reason character varying(64) NOT NULL,
    source_family character varying(64) NOT NULL,
    event_hash character varying(64),
    source_event_id character varying(128),
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    planner_owner character varying(128),
    leased_at timestamp with time zone,
    lease_expires_at timestamp with time zone,
    coalesced_at timestamp with time zone,
    claimed_at timestamp with time zone,
    suppressed_at timestamp with time zone,
    fallback_at timestamp with time zone,
    superseded_at timestamp with time zone,
    dispatched_at timestamp with time zone,
    pruned_at timestamp with time zone,
    observed_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    source_snapshot_hash character varying(64),
    authority_retry_count integer DEFAULT 0 NOT NULL,
    authority_retry_after_at timestamp with time zone,
    authority_wait_started_at timestamp with time zone,
    authority_reactivated_at timestamp with time zone,
    authority_terminal_at timestamp with time zone,
    CONSTRAINT ck_b24_dirty_events_authority_retry_count_nonnegative CHECK ((authority_retry_count >= 0)),
    CONSTRAINT ck_b24_dirty_events_event_hash_sha256 CHECK (((event_hash IS NULL) OR ((event_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_b24_dirty_events_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_b24_dirty_events_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_b24_dirty_events_reason_not_blank CHECK ((char_length(TRIM(BOTH FROM dirty_reason)) > 0)),
    CONSTRAINT ck_b24_dirty_events_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_b24_dirty_events_source_family_not_blank CHECK ((char_length(TRIM(BOTH FROM source_family)) > 0)),
    CONSTRAINT ck_b24_dirty_events_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash IS NULL) OR ((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_b24_dirty_events_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_b24_dirty_events_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'leased'::character varying, 'coalesced'::character varying, 'claimed'::character varying, 'suppressed'::character varying, 'fallback_only'::character varying, 'superseded'::character varying, 'dispatched'::character varying, 'authority_waiting'::character varying, 'authority_retry_ready'::character varying, 'authority_retry_superseded'::character varying, 'authority_timeout'::character varying, 'authority_build_failed'::character varying, 'pruned'::character varying])::text[])))
);

ALTER TABLE ONLY public.b24_dirty_events FORCE ROW LEVEL SECURITY;


--
-- Name: b24_feature_authority_build_outbox; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b24_feature_authority_build_outbox (
    tenant_id uuid NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    dispatch_key character varying(160) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    attempt_count integer DEFAULT 0 NOT NULL,
    max_attempts integer DEFAULT 5 NOT NULL,
    next_attempt_at timestamp with time zone DEFAULT now() NOT NULL,
    last_attempt_at timestamp with time zone,
    dispatching_started_at timestamp with time zone,
    dispatched_at timestamp with time zone,
    dead_lettered_at timestamp with time zone,
    stale_recovered_at timestamp with time zone,
    last_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_b24_feature_authority_build_outbox_attempt_count CHECK ((attempt_count >= 0)),
    CONSTRAINT ck_b24_feature_authority_build_outbox_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_b24_feature_authority_build_outbox_max_attempts CHECK ((max_attempts > 0)),
    CONSTRAINT ck_b24_feature_authority_build_outbox_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_b24_feature_authority_build_outbox_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_b24_feature_authority_build_outbox_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'dispatching'::character varying, 'dispatched'::character varying, 'failed_retryable'::character varying, 'dead_lettered'::character varying, 'stale_recovered'::character varying])::text[]))),
    CONSTRAINT ck_b24_feature_authority_build_outbox_window_order CHECK ((source_window_end > source_window_start))
);

ALTER TABLE ONLY public.b24_feature_authority_build_outbox FORCE ROW LEVEL SECURITY;


--
-- Name: b24_feature_authority_build_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b24_feature_authority_build_requests (
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'authority_build_requested'::character varying NOT NULL,
    authority_reason character varying(64) NOT NULL,
    detail text,
    retry_count integer DEFAULT 0 NOT NULL,
    max_retries integer DEFAULT 5 NOT NULL,
    retry_after_at timestamp with time zone,
    requested_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    terminal_reason character varying(64),
    terminal_at timestamp with time zone,
    policy_version character varying(64) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_b24_feature_authority_request_max_retries CHECK ((max_retries > 0)),
    CONSTRAINT ck_b24_feature_authority_request_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_b24_feature_authority_request_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_b24_feature_authority_request_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_b24_feature_authority_request_reason CHECK (((authority_reason)::text = ANY ((ARRAY['cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying])::text[]))),
    CONSTRAINT ck_b24_feature_authority_request_retry_count CHECK ((retry_count >= 0)),
    CONSTRAINT ck_b24_feature_authority_request_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_b24_feature_authority_request_status CHECK (((status)::text = ANY ((ARRAY['authority_build_requested'::character varying, 'authority_waiting'::character varying, 'authority_retry_ready'::character varying, 'authority_completed'::character varying, 'authority_timeout'::character varying, 'authority_build_failed'::character varying, 'authority_superseded'::character varying])::text[]))),
    CONSTRAINT ck_b24_feature_authority_request_terminal_reason CHECK (((terminal_reason IS NULL) OR ((terminal_reason)::text = ANY ((ARRAY['cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_snapshot_superseded'::character varying])::text[])))),
    CONSTRAINT ck_b24_feature_authority_request_window_order CHECK ((source_window_end > source_window_start))
);

ALTER TABLE ONLY public.b24_feature_authority_build_requests FORCE ROW LEVEL SECURITY;


--
-- Name: b24_fit_dispatch_outbox; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b24_fit_dispatch_outbox (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    dispatch_key character varying(128) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    attempt_count integer DEFAULT 0 NOT NULL,
    max_attempts integer DEFAULT 5 NOT NULL,
    next_attempt_at timestamp with time zone DEFAULT now() NOT NULL,
    last_attempt_at timestamp with time zone,
    dispatching_started_at timestamp with time zone,
    dispatched_at timestamp with time zone,
    dead_lettered_at timestamp with time zone,
    stale_recovered_at timestamp with time zone,
    last_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    task_name text NOT NULL,
    attempt_id uuid NOT NULL,
    payload_hash character(64) NOT NULL,
    claim_capability text,
    claim_capability_digest character(64),
    claim_capability_expires_at timestamp with time zone,
    lease_owner text,
    lease_capability_digest character(64),
    lease_acquired_at timestamp with time zone,
    lease_expires_at timestamp with time zone,
    last_heartbeat_at timestamp with time zone,
    claim_epoch integer DEFAULT 0 NOT NULL,
    claim_count integer DEFAULT 0 NOT NULL,
    redelivery_count integer DEFAULT 0 NOT NULL,
    recovery_generation integer DEFAULT 0 NOT NULL,
    completed_at timestamp with time zone,
    cancelled_at timestamp with time zone,
    superseded_by uuid,
    terminal_reason text,
    next_recovery_at timestamp with time zone NOT NULL,
    assigned_worker_generation text,
    assignment_generation integer DEFAULT 0 NOT NULL,
    assignment_expires_at timestamp with time zone,
    assignment_reason text,
    CONSTRAINT ck_b24_fit_dispatch_outbox_assignment_generation_non_negative CHECK ((assignment_generation >= 0)),
    CONSTRAINT ck_b24_fit_dispatch_outbox_attempt_count CHECK ((attempt_count >= 0)),
    CONSTRAINT ck_b24_fit_dispatch_outbox_claim_capability_digest_sha256 CHECK (((claim_capability_digest IS NULL) OR (claim_capability_digest ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_b24_fit_dispatch_outbox_claim_count_non_negative CHECK ((claim_count >= 0)),
    CONSTRAINT ck_b24_fit_dispatch_outbox_claim_epoch_non_negative CHECK ((claim_epoch >= 0)),
    CONSTRAINT ck_b24_fit_dispatch_outbox_dispatch_key_not_blank CHECK ((char_length(TRIM(BOTH FROM dispatch_key)) > 0)),
    CONSTRAINT ck_b24_fit_dispatch_outbox_lease_capability_digest_sha256 CHECK (((lease_capability_digest IS NULL) OR (lease_capability_digest ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_b24_fit_dispatch_outbox_max_attempts CHECK ((max_attempts > 0)),
    CONSTRAINT ck_b24_fit_dispatch_outbox_payload_hash_sha256 CHECK ((payload_hash ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_b24_fit_dispatch_outbox_recovery_generation_non_negative CHECK ((recovery_generation >= 0)),
    CONSTRAINT ck_b24_fit_dispatch_outbox_redelivery_count_non_negative CHECK ((redelivery_count >= 0)),
    CONSTRAINT ck_b24_fit_dispatch_outbox_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'dispatching'::character varying, 'dispatched'::character varying, 'leased'::character varying, 'running'::character varying, 'failed_retryable'::character varying, 'completed'::character varying, 'failed_terminal'::character varying, 'cancelled'::character varying, 'expired'::character varying, 'superseded'::character varying, 'quarantined'::character varying, 'dead_lettered'::character varying, 'stale_recovered'::character varying])::text[])))
);

ALTER TABLE ONLY public.b24_fit_dispatch_outbox FORCE ROW LEVEL SECURITY;


--
-- Name: b24_fit_planner_wakeups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b24_fit_planner_wakeups (
    tenant_id uuid NOT NULL,
    wakeup_revision bigint DEFAULT 1 NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    lease_owner text,
    lease_expires_at timestamp with time zone,
    observed_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    next_eligible_at timestamp with time zone,
    CONSTRAINT b24_fit_planner_wakeups_check CHECK ((((status = 'pending'::text) AND (lease_owner IS NULL) AND (lease_expires_at IS NULL)) OR ((status = 'leased'::text) AND (lease_owner IS NOT NULL) AND (lease_expires_at IS NOT NULL)))),
    CONSTRAINT b24_fit_planner_wakeups_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'leased'::text]))),
    CONSTRAINT b24_fit_planner_wakeups_wakeup_revision_check CHECK ((wakeup_revision > 0))
);

ALTER TABLE ONLY public.b24_fit_planner_wakeups FORCE ROW LEVEL SECURITY;


--
-- Name: b24_fit_policy_replan_lineage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b24_fit_policy_replan_lineage (
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    transition_sequence integer NOT NULL,
    from_policy_bundle_hash character varying(64) NOT NULL,
    to_policy_bundle_hash character varying(64) NOT NULL,
    from_inference_profile_version character varying(128) NOT NULL,
    to_inference_profile_version character varying(128) NOT NULL,
    from_runtime_policy_version character varying(128) NOT NULL,
    to_runtime_policy_version character varying(128) NOT NULL,
    from_sampling_policy_version character varying(128) NOT NULL,
    to_sampling_policy_version character varying(128) NOT NULL,
    from_diagnostic_policy_version character varying(128),
    to_diagnostic_policy_version character varying(128) NOT NULL,
    actor_session_user character varying(128) NOT NULL,
    transitioned_at timestamp with time zone NOT NULL,
    CONSTRAINT ck_b24_replan_lineage_sequence CHECK ((transition_sequence > 0)),
    CONSTRAINT ck_b24_replan_lineage_transition CHECK (((from_policy_bundle_hash)::text <> (to_policy_bundle_hash)::text))
);

ALTER TABLE ONLY public.b24_fit_policy_replan_lineage FORCE ROW LEVEL SECURITY;


--
-- Name: b24_fit_recovery_outbox; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b24_fit_recovery_outbox (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    dispatch_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    attempt_id uuid NOT NULL,
    task_name text NOT NULL,
    payload_hash character(64) NOT NULL,
    claim_capability text,
    recovery_generation integer NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    published_at timestamp with time zone,
    publish_attempt_count integer DEFAULT 0 NOT NULL,
    last_error text,
    CONSTRAINT ck_b24_fit_recovery_outbox_payload_hash_sha256 CHECK ((payload_hash ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_b24_fit_recovery_outbox_publish_attempt_count CHECK ((publish_attempt_count >= 0)),
    CONSTRAINT ck_b24_fit_recovery_outbox_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'publishing'::character varying, 'published'::character varying, 'failed_retryable'::character varying, 'quarantined'::character varying])::text[])))
);

ALTER TABLE ONLY public.b24_fit_recovery_outbox FORCE ROW LEVEL SECURITY;


--
-- Name: b24_inference_policy_registry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b24_inference_policy_registry (
    policy_bundle_hash character varying(64) NOT NULL,
    inference_profile_version character varying(128) NOT NULL,
    runtime_policy_version character varying(128) NOT NULL,
    sampling_policy_version character varying(128) NOT NULL,
    diagnostic_policy_version character varying(128) NOT NULL,
    confidence_policy_version character varying(128) NOT NULL,
    confidence_semantics_version character varying(128) NOT NULL,
    semantic_manifest jsonb NOT NULL,
    component_digests jsonb NOT NULL,
    identity_scheme character varying(64) DEFAULT 'canonical-semantic-manifest-sha256-v1'::character varying NOT NULL,
    registered_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_b24_policy_registry_hash CHECK (((policy_bundle_hash)::text ~ '^[0-9a-f]{64}$'::text))
);


--
-- Name: b24_source_window_feature_authority; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b24_source_window_feature_authority (
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    channel_count integer NOT NULL,
    currency_count integer NOT NULL,
    provider_count integer NOT NULL,
    campaign_or_feature_count integer NOT NULL,
    freshness_status character varying(32) DEFAULT 'fresh'::character varying NOT NULL,
    policy_version character varying(64) NOT NULL,
    computed_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_b24_feature_authority_campaign_count_nonnegative CHECK ((campaign_or_feature_count >= 0)),
    CONSTRAINT ck_b24_feature_authority_channel_count_nonnegative CHECK ((channel_count >= 0)),
    CONSTRAINT ck_b24_feature_authority_currency_count_nonnegative CHECK ((currency_count >= 0)),
    CONSTRAINT ck_b24_feature_authority_freshness_status CHECK (((freshness_status)::text = ANY ((ARRAY['fresh'::character varying, 'stale'::character varying, 'mismatched'::character varying])::text[]))),
    CONSTRAINT ck_b24_feature_authority_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_b24_feature_authority_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_b24_feature_authority_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_b24_feature_authority_provider_count_nonnegative CHECK ((provider_count >= 0)),
    CONSTRAINT ck_b24_feature_authority_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_b24_feature_authority_source_window_order CHECK ((source_window_end > source_window_start))
);

ALTER TABLE ONLY public.b24_source_window_feature_authority FORCE ROW LEVEL SECURITY;


--
-- Name: b24_worker_process_authority; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b24_worker_process_authority (
    generation_id text NOT NULL,
    pid integer NOT NULL,
    parent_pid integer NOT NULL,
    topology_fingerprint character(64) NOT NULL,
    process_token_digest character(64) NOT NULL,
    status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    registered_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT ck_b24_worker_process_authority_digest CHECK ((process_token_digest ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_b24_worker_process_authority_generation CHECK ((length(generation_id) >= 16)),
    CONSTRAINT ck_b24_worker_process_authority_status CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'revoked'::character varying, 'expired'::character varying])::text[]))),
    CONSTRAINT ck_b24_worker_process_authority_topology_fingerprint CHECK ((topology_fingerprint ~ '^[a-f0-9]{64}$'::text))
);

ALTER TABLE ONLY public.b24_worker_process_authority FORCE ROW LEVEL SECURITY;


--
-- Name: b27_explanation_materializations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b27_explanation_materializations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
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
    authority_class text DEFAULT 'non_authoritative_explanation'::text NOT NULL,
    judge_authority text DEFAULT 'none'::text NOT NULL,
    stale boolean DEFAULT false NOT NULL,
    superseded_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    source_issuance_envelope_hash text NOT NULL,
    explanation_template_registry_hash text NOT NULL,
    CONSTRAINT ck_b27_authority_class CHECK ((authority_class = 'non_authoritative_explanation'::text)),
    CONSTRAINT ck_b27_cache_identity_shape CHECK (((cache_identity_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (source_semantic_truth_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (subject_ref_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (projection_profile_hash ~ '^sha256:[0-9a-f]{64}$'::text))),
    CONSTRAINT ck_b27_claims_object CHECK ((jsonb_typeof(claims) = 'array'::text)),
    CONSTRAINT ck_b27_confidence_status CHECK ((confidence_status = ANY (ARRAY['available'::text, 'unavailable'::text, 'degraded'::text, 'diagnostics_failed'::text]))),
    CONSTRAINT ck_b27_judge_authority CHECK ((judge_authority = 'none'::text)),
    CONSTRAINT ck_b27_policy_state CHECK ((policy_state = ANY (ARRAY['blocked'::text, 'read_only'::text, 'simulation_only'::text, 'proposal_required'::text, 'approval_required'::text]))),
    CONSTRAINT ck_b27_projection_profile CHECK ((projection_profile_id = 'llm_explanation_projection_safe'::text)),
    CONSTRAINT ck_b27_stale_shape CHECK ((((stale = true) AND (superseded_at IS NOT NULL)) OR ((stale = false) AND (superseded_at IS NULL)))),
    CONSTRAINT ck_b27_template_registry_hash_shape CHECK ((explanation_template_registry_hash ~ '^sha256:[0-9a-f]{64}$'::text))
);

ALTER TABLE ONLY public.b27_explanation_materializations FORCE ROW LEVEL SECURITY;


--
-- Name: b27_narrative_template_registry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b27_narrative_template_registry (
    registry_version text NOT NULL,
    registry_hash text NOT NULL,
    CONSTRAINT ck_b27_template_registry_hash CHECK ((registry_hash ~ '^sha256:[0-9a-f]{64}$'::text))
);


--
-- Name: b27_narrative_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b27_narrative_templates (
    template_id text NOT NULL,
    claim_kind text NOT NULL,
    source_path text NOT NULL,
    template_text text NOT NULL,
    value_grammar text NOT NULL,
    value_pattern text NOT NULL,
    CONSTRAINT ck_b27_template_kind CHECK ((claim_kind = ANY (ARRAY['financial_fact'::text, 'status_fact'::text, 'confidence_statement'::text, 'policy_statement'::text, 'fallback_statement'::text, 'provenance_fact'::text]))),
    CONSTRAINT ck_b27_template_no_fixed_numeral CHECK ((replace(template_text, '{value}'::text, ' '::text) !~ '[0-9]'::text)),
    CONSTRAINT ck_b27_template_single_variable CHECK (((template_text ~~ '%{value}%'::text) AND ((length(template_text) - length(replace(template_text, '{value}'::text, ''::text))) = (7 * 1))))
);


--
-- Name: b28_proposals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b28_proposals (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    result_id uuid NOT NULL,
    proposal_ref text NOT NULL,
    source_envelope_id text NOT NULL,
    action_authority text NOT NULL,
    requires_human_approval boolean DEFAULT true NOT NULL,
    authority_class text DEFAULT 'non_authoritative_proposal'::text NOT NULL,
    allocations jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_b28_proposal_action_authority CHECK ((action_authority = ANY (ARRAY['blocked'::text, 'read_only'::text, 'simulation_only'::text, 'proposal_required'::text]))),
    CONSTRAINT ck_b28_proposal_allocations CHECK ((jsonb_typeof(allocations) = 'array'::text)),
    CONSTRAINT ck_b28_proposal_authority_class CHECK ((authority_class = 'non_authoritative_proposal'::text)),
    CONSTRAINT ck_b28_proposal_human_approval CHECK ((requires_human_approval = true))
);

ALTER TABLE ONLY public.b28_proposals FORCE ROW LEVEL SECURITY;


--
-- Name: b28_simulation_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b28_simulation_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    request_ref text NOT NULL,
    requested_by text NOT NULL,
    source_envelope_id text NOT NULL,
    source_semantic_truth_hash text NOT NULL,
    input_snapshot_hash text NOT NULL,
    total_budget_minor bigint NOT NULL,
    currency text NOT NULL,
    channel_count integer NOT NULL,
    sufficiency_policy_version text NOT NULL,
    requested_at timestamp with time zone DEFAULT now() NOT NULL,
    source_issuance_envelope_hash text NOT NULL,
    requested_by_agent_client_id uuid NOT NULL,
    requested_by_credential_id uuid NOT NULL,
    request_authority_principal text NOT NULL,
    channel_evidence jsonb NOT NULL,
    solver_profile text NOT NULL,
    sufficiency_verdict boolean NOT NULL,
    sufficiency_reasons text[] NOT NULL,
    observed_channels integer NOT NULL,
    observed_conversions integer NOT NULL,
    observed_revenue_minor bigint NOT NULL,
    CONSTRAINT ck_b28_request_budget CHECK ((total_budget_minor > 0)),
    CONSTRAINT ck_b28_request_channel_evidence CHECK (((jsonb_typeof(channel_evidence) = 'array'::text) AND (jsonb_array_length(channel_evidence) = channel_count) AND (jsonb_array_length(channel_evidence) >= 1))),
    CONSTRAINT ck_b28_request_channels CHECK ((channel_count > 0)),
    CONSTRAINT ck_b28_request_currency CHECK ((currency ~ '^[A-Z]{3}$'::text)),
    CONSTRAINT ck_b28_request_hashes CHECK (((source_semantic_truth_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (input_snapshot_hash ~ '^sha256:[0-9a-f]{64}$'::text))),
    CONSTRAINT ck_b28_request_observed_nonnegative CHECK (((observed_channels >= 0) AND (observed_conversions >= 0) AND (observed_revenue_minor >= 0))),
    CONSTRAINT ck_b28_request_requested_by_derived CHECK ((requested_by = ('agent_client:'::text || (requested_by_agent_client_id)::text))),
    CONSTRAINT ck_b28_request_solver_profile CHECK ((solver_profile = 'b25-p14-deterministic-largest-remainder-v1'::text))
);

ALTER TABLE ONLY public.b28_simulation_requests FORCE ROW LEVEL SECURITY;


--
-- Name: b28_simulation_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b28_simulation_results (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    request_id uuid NOT NULL,
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
    authority_class text DEFAULT 'deterministic_simulation'::text NOT NULL,
    llm_authority_over_allocation text DEFAULT 'none'::text NOT NULL,
    allocations jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_b28_result_action_authority CHECK ((action_authority = ANY (ARRAY['blocked'::text, 'read_only'::text, 'simulation_only'::text, 'proposal_required'::text]))),
    CONSTRAINT ck_b28_result_allocations CHECK ((jsonb_typeof(allocations) = 'array'::text)),
    CONSTRAINT ck_b28_result_authority_class CHECK ((authority_class = 'deterministic_simulation'::text)),
    CONSTRAINT ck_b28_result_budget CHECK ((total_budget_minor > 0)),
    CONSTRAINT ck_b28_result_conserved CHECK ((allocated_total_minor = total_budget_minor)),
    CONSTRAINT ck_b28_result_hashes CHECK (((source_semantic_truth_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (projection_profile_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (input_snapshot_hash ~ '^sha256:[0-9a-f]{64}$'::text))),
    CONSTRAINT ck_b28_result_llm_authority CHECK ((llm_authority_over_allocation = 'none'::text)),
    CONSTRAINT ck_b28_result_solver_ran CHECK ((solver_invocations >= 1))
);

ALTER TABLE ONLY public.b28_simulation_results FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifact_storage_quotas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifact_storage_quotas (
    tenant_id uuid NOT NULL,
    policy_version character varying(64) NOT NULL,
    quota_bytes bigint DEFAULT 1048576 NOT NULL,
    active_bytes bigint DEFAULT 0 NOT NULL,
    pruned_bytes bigint DEFAULT 0 NOT NULL,
    active_artifact_count integer DEFAULT 0 NOT NULL,
    pruned_artifact_count integer DEFAULT 0 NOT NULL,
    rejected_count integer DEFAULT 0 NOT NULL,
    last_rejection_reason character varying(64),
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    max_artifact_count integer DEFAULT 1000 NOT NULL,
    CONSTRAINT ck_bayesian_artifact_storage_quotas_active_count_within_quota CHECK ((active_artifact_count <= max_artifact_count)),
    CONSTRAINT ck_bayesian_artifact_storage_quotas_active_within_quota CHECK ((active_bytes <= quota_bytes)),
    CONSTRAINT ck_bayesian_artifact_storage_quotas_bytes_non_negative CHECK (((quota_bytes >= 0) AND (active_bytes >= 0) AND (pruned_bytes >= 0))),
    CONSTRAINT ck_bayesian_artifact_storage_quotas_counts_non_negative CHECK (((active_artifact_count >= 0) AND (pruned_artifact_count >= 0) AND (rejected_count >= 0))),
    CONSTRAINT ck_bayesian_artifact_storage_quotas_max_count_positive CHECK ((max_artifact_count > 0)),
    CONSTRAINT ck_bayesian_artifact_storage_quotas_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifact_storage_quotas_rejection_reason CHECK (((last_rejection_reason IS NULL) OR ((last_rejection_reason)::text = ANY ((ARRAY['tenant_quota_exceeded'::character varying, 'fit_wal_budget_exceeded'::character varying, 'policy_rejected'::character varying])::text[]))))
);

ALTER TABLE ONLY public.bayesian_artifact_storage_quotas FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
)
PARTITION BY HASH (tenant_id);

ALTER TABLE ONLY public.bayesian_artifacts FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p00; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p00 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p00 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p01; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p01 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p01 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p02; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p02 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p02 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p03; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p03 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p03 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p04; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p04 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p04 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p05; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p05 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p05 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p06; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p06 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p06 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p07; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p07 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p07 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p08; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p08 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p08 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p09; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p09 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p09 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p10; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p10 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p10 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p11; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p11 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p11 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p12; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p12 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p12 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p13; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p13 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p13 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p14; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p14 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p14 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p15; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_artifacts_p15 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    fit_id uuid NOT NULL,
    artifact_ref character varying(255) NOT NULL,
    artifact_hash character varying(64) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    storage_backend character varying(32) NOT NULL,
    artifact_uri_internal character varying(1024) NOT NULL,
    artifact_size_bytes bigint NOT NULL,
    compression character varying(32),
    retention_class character varying(32) NOT NULL,
    expires_at timestamp with time zone,
    pruned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload_json jsonb,
    payload_bytes bytea,
    payload_byte_count bigint DEFAULT 0 NOT NULL,
    lifecycle_status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1'::character varying NOT NULL,
    pruned_reason character varying(64),
    pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256 CHECK (((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_ref_format CHECK (((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text)),
    CONSTRAINT ck_bayesian_artifacts_artifact_type CHECK (((artifact_type)::text = ANY ((ARRAY['diagnostics'::character varying, 'summary'::character varying, 'source_manifest'::character varying, 'fit_metadata'::character varying, 'input_manifest'::character varying, 'model_spec'::character varying, 'posterior_summary'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_compression CHECK (((compression IS NULL) OR ((compression)::text = ANY ((ARRAY['none'::character varying, 'gzip'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_internal_uri CHECK ((((lifecycle_status)::text = ANY ((ARRAY['pruned'::character varying, 'rejected'::character varying])::text[])) OR (((artifact_uri_internal)::text = (artifact_ref)::text) AND ((artifact_uri_internal)::text ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'::text)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state CHECK (((((lifecycle_status)::text = 'active'::text) AND (payload_bytes IS NOT NULL) AND (payload_byte_count = artifact_size_bytes) AND (pruned_at IS NULL)) OR (((lifecycle_status)::text = 'pruned'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NOT NULL)) OR (((lifecycle_status)::text = 'rejected'::text) AND (payload_bytes IS NULL) AND (payload_byte_count = 0) AND (pruned_at IS NULL)))),
    CONSTRAINT ck_bayesian_artifacts_lifecycle_status CHECK (((lifecycle_status)::text = ANY ((ARRAY['active'::character varying, 'pruned'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) = payload_byte_count))),
    CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap CHECK (((payload_byte_count >= 0) AND (payload_byte_count <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap CHECK (((payload_bytes IS NULL) OR (octet_length(payload_bytes) <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank CHECK ((char_length(TRIM(BOTH FROM policy_version)) > 0)),
    CONSTRAINT ck_bayesian_artifacts_pruned_reason CHECK (((pruned_reason IS NULL) OR ((pruned_reason)::text = ANY ((ARRAY['retention_expired'::character varying, 'manual_governance'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry CHECK (((pruned_at IS NULL) OR (expires_at IS NOT NULL))),
    CONSTRAINT ck_bayesian_artifacts_retention_class CHECK (((retention_class)::text = ANY ((ARRAY['ephemeral'::character varying, 'standard'::character varying, 'audit'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_artifacts_size_non_negative CHECK ((artifact_size_bytes >= 0)),
    CONSTRAINT ck_bayesian_artifacts_size_p8_cap CHECK ((((lifecycle_status)::text = 'pruned'::text) OR (artifact_size_bytes <= 65536))),
    CONSTRAINT ck_bayesian_artifacts_storage_backend CHECK (((storage_backend)::text = 'postgres'::text))
);

ALTER TABLE ONLY public.bayesian_artifacts_p15 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
PARTITION BY HASH (tenant_id);

ALTER TABLE ONLY public.bayesian_model_fits FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p00; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p00 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p00 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p01; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p01 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p01 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p02; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p02 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p02 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p03; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p03 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p03 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p04; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p04 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p04 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p05; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p05 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p05 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p06; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p06 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p06 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p07; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p07 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p07 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p08; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p08 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p08 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p09; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p09 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p09 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p10; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p10 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p10 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p11; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p11 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p11 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p12; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p12 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p12 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p13; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p13 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p13 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p14; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p14 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p14 FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_model_fits_p15; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bayesian_model_fits_p15 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    model_type character varying(64) NOT NULL,
    model_version character varying(64) NOT NULL,
    source_window_start timestamp with time zone NOT NULL,
    source_window_end timestamp with time zone NOT NULL,
    source_snapshot_hash character varying(64) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    eligibility_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    data_completeness_status character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    fallback_applied boolean DEFAULT false NOT NULL,
    fallback_reason character varying(64),
    sampling_started_at timestamp with time zone,
    last_eligibility_check_at timestamp with time zone,
    last_fit_at timestamp with time zone,
    completed_at timestamp with time zone,
    runtime_seconds integer,
    max_runtime_seconds integer DEFAULT 60 NOT NULL,
    max_samples integer DEFAULT 0 NOT NULL,
    max_cores integer DEFAULT 1 NOT NULL,
    n_chains integer,
    n_samples_actual integer,
    r_hat_max double precision,
    ess_min double precision,
    divergence_count integer,
    credible_interval_status character varying(32) DEFAULT 'not_available'::character varying NOT NULL,
    confidence_bucket character varying(32),
    confidence_bucket_reason character varying(255),
    confidence_policy_version character varying(64),
    artifact_ref character varying(255),
    artifact_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    hdi_lower double precision,
    hdi_upper double precision,
    interval_shape jsonb DEFAULT '[]'::jsonb NOT NULL,
    interval_element_count integer,
    interval_summary_bytes integer,
    diagnostic_status character varying(32) DEFAULT 'not_computed'::character varying NOT NULL,
    diagnostic_failure_reason character varying(64),
    diagnostic_policy_version character varying(64),
    diagnostic_target_filter_version character varying(64),
    interval_policy_version character varying(64),
    diagnostics_computed_at timestamp with time zone,
    confidence_semantics_version character varying(64),
    confidence_deterministic_revenue_minor bigint,
    confidence_deterministic_row_count bigint,
    confidence_match_verdict_count bigint,
    confidence_currency_count integer,
    confidence_classified_at timestamp with time zone,
    confidence_evidence_snapshot_hash character varying(64),
    source_read_started_at timestamp with time zone,
    source_read_completed_at timestamp with time zone,
    inference_profile_version character varying(128),
    runtime_policy_version character varying(128),
    sampling_policy_version character varying(128),
    policy_bundle_hash character varying(64),
    authorized_chains integer,
    authorized_posterior_draws_total integer,
    superseded_policy_bundle_hash character varying(64),
    policy_replanned_at timestamp with time zone,
    policy_replan_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256 CHECK (((artifact_hash IS NULL) OR ((artifact_hash)::text ~ '^[a-f0-9]{64}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_format CHECK (((artifact_ref IS NULL) OR ((artifact_ref)::text ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'::text))),
    CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair CHECK ((((artifact_ref IS NULL) AND (artifact_hash IS NULL)) OR ((artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagn CHECK ((((credible_interval_status)::text <> 'available'::text) OR (((diagnostic_status)::text = 'passed'::text) AND (fallback_applied = false) AND (r_hat_max IS NOT NULL) AND (r_hat_max <= (1.01)::double precision) AND (ess_min IS NOT NULL) AND (ess_min >= (400)::double precision) AND (divergence_count IS NOT NULL) AND (divergence_count = 0) AND (hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (interval_element_count IS NOT NULL) AND (interval_element_count > 0) AND (diagnostic_policy_version IS NOT NULL) AND (diagnostic_target_filter_version IS NOT NULL) AND (interval_policy_version IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_confidence_bucket CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text = ANY ((ARRAY['unavailable'::character varying, 'low'::character varying, 'medium'::character varying, 'high'::character varying, 'fallback'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative CHECK (((confidence_currency_count IS NULL) OR (confidence_currency_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative CHECK (((confidence_deterministic_row_count IS NULL) OR (confidence_deterministic_row_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative CHECK (((confidence_match_verdict_count IS NULL) OR (confidence_match_verdict_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_credible_interval_status CHECK (((credible_interval_status)::text = ANY ((ARRAY['not_available'::character varying, 'available'::character varying, 'suppressed'::character varying, 'invalid'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_data_completeness_status CHECK (((data_completeness_status)::text = ANY ((ARRAY['unknown'::character varying, 'complete'::character varying, 'partial'::character varying, 'insufficient'::character varying, 'stale'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason CHECK (((diagnostic_failure_reason IS NULL) OR ((diagnostic_failure_reason)::text = ANY ((ARRAY['bad_rhat'::character varying, 'low_ess'::character varying, 'divergence'::character varying, 'nonfinite_diagnostic'::character varying, 'invalid_diagnostic_summary'::character varying, 'diagnostic_scope_too_large'::character varying, 'interval_dimension_exceeded'::character varying, 'interval_payload_too_large'::character varying, 'diagnostics_failed'::character varying, 'diagnostics_memory_exceeded'::character varying, 'diagnostics_timeout'::character varying, 'skipped_non_sampled'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_diagnostic_status CHECK (((diagnostic_status)::text = ANY ((ARRAY['not_computed'::character varying, 'passed'::character varying, 'failed'::character varying, 'error'::character varying, 'unavailable'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative CHECK (((divergence_count IS NULL) OR (divergence_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_eligibility_status CHECK (((eligibility_status)::text = ANY ((ARRAY['unknown'::character varying, 'eligible'::character varying, 'ineligible'::character varying, 'fallback_only'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative CHECK (((ess_min IS NULL) OR (ess_min >= (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason CHECK (((fallback_reason IS NULL) OR ((fallback_reason)::text = ANY ((ARRAY['source_window_empty'::character varying, 'insufficient_data'::character varying, 'insufficient_privacy_cohort'::character varying, 'input_too_large'::character varying, 'feature_width_exceeded'::character varying, 'source_window_too_large'::character varying, 'memory_bound_exceeded'::character varying, 'graph_complexity_exceeded'::character varying, 'parameter_count_exceeded'::character varying, 'hierarchy_width_exceeded'::character varying, 'compilation_memory_bound_exceeded'::character varying, 'cardinality_authority_missing'::character varying, 'cardinality_authority_stale'::character varying, 'cardinality_authority_mismatch'::character varying, 'cardinality_authority_timeout'::character varying, 'cardinality_authority_build_failed'::character varying, 'source_profile_unavailable'::character varying, 'source_snapshot_mismatch'::character varying, 'transport_rejected'::character varying, 'result_too_large'::character varying, 'sampler_health_failed'::character varying, 'model_memory_exceeded'::character varying, 'graph_compile_memory_exceeded'::character varying, 'policy_rejected'::character varying, 'timeout'::character varying, 'worker_failure'::character varying, 'no_convergence'::character varying, 'resource_bound_exceeded'::character varying, 'source_unavailable'::character varying, 'duplicate_fit_suppressed'::character varying, 'artifact_unavailable'::character varying, 'storage_quota_exceeded'::character varying])::text[])))),
    CONSTRAINT ck_bayesian_model_fits_fallback_reason_required CHECK ((((fallback_applied = false) AND (fallback_reason IS NULL)) OR ((fallback_applied = true) AND (fallback_reason IS NOT NULL)))),
    CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order CHECK ((((hdi_lower IS NULL) AND (hdi_upper IS NULL)) OR ((hdi_lower IS NOT NULL) AND (hdi_upper IS NOT NULL) AND (hdi_lower <= hdi_upper)))),
    CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative CHECK (((interval_element_count IS NULL) OR (interval_element_count >= 0))),
    CONSTRAINT ck_bayesian_model_fits_interval_shape_array CHECK ((jsonb_typeof(interval_shape) = 'array'::text)),
    CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative CHECK (((interval_summary_bytes IS NULL) OR (interval_summary_bytes >= 0))),
    CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative CHECK ((max_cores >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative CHECK ((max_runtime_seconds >= 0)),
    CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative CHECK ((max_samples >= 0)),
    CONSTRAINT ck_bayesian_model_fits_model_type_format CHECK (((model_type)::text ~ '^[a-z][a-z0-9_]{1,63}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_model_version_not_blank CHECK ((char_length(TRIM(BOTH FROM model_version)) > 0)),
    CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative CHECK (((n_chains IS NULL) OR (n_chains >= 0))),
    CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative CHECK (((n_samples_actual IS NULL) OR (n_samples_actual >= 0))),
    CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure CHECK (((((diagnostic_status)::text = 'passed'::text) AND (diagnostic_failure_reason IS NULL)) OR ((diagnostic_status)::text <> 'passed'::text))),
    CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive CHECK (((r_hat_max IS NULL) OR (r_hat_max > (0)::double precision))),
    CONSTRAINT ck_bayesian_model_fits_registered_model_type CHECK (((model_type)::text = ANY ((ARRAY['bayesian_attribution_confidence'::character varying, 'mmm'::character varying])::text[]))),
    CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative CHECK (((runtime_seconds IS NULL) OR (runtime_seconds >= 0))),
    CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256 CHECK (((source_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT ck_bayesian_model_fits_source_window_order CHECK ((source_window_end > source_window_start)),
    CONSTRAINT ck_bayesian_model_fits_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'persist_pending'::character varying, 'sampled_unvalidated'::character varying, 'diagnostics_pending'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'timeout'::character varying, 'worker_lost'::character varying, 'fallback_only'::character varying, 'cancelled'::character varying])::text[])))
)
WITH (fillfactor='90');

ALTER TABLE ONLY public.bayesian_model_fits_p15 FORCE ROW LEVEL SECURITY;


--
-- Name: budget_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.budget_jobs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    request_id text NOT NULL,
    correlation_id text NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    ready_for_review_at timestamp with time zone,
    approved_at timestamp with time zone,
    rejected_at timestamp with time zone,
    refine_requested_at timestamp with time zone,
    rerun_requested_at timestamp with time zone,
    completed_at timestamp with time zone,
    failed_at timestamp with time zone,
    timeout_at timestamp with time zone,
    cancelled_at timestamp with time zone,
    result jsonb,
    failure_code text,
    failure_reason text,
    CONSTRAINT ck_budget_jobs_status_valid CHECK ((status = ANY (ARRAY['submitted'::text, 'validating'::text, 'investigating'::text, 'ready_for_review'::text, 'approved'::text, 'rejected'::text, 'refine_requested'::text, 'rerun_requested'::text, 'completed'::text, 'failed'::text, 'timeout'::text, 'cancelled'::text])))
);

ALTER TABLE ONLY public.budget_jobs FORCE ROW LEVEL SECURITY;


--
-- Name: budget_optimization_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.budget_optimization_jobs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    status text NOT NULL,
    recommendations jsonb,
    cost_cents integer DEFAULT 0,
    request_id text NOT NULL,
    authority_job_id uuid,
    lifecycle_role text DEFAULT 'internal_trace'::text NOT NULL,
    CONSTRAINT ck_budget_optimization_jobs_internal_trace_only CHECK ((lifecycle_role = 'internal_trace'::text)),
    CONSTRAINT ck_budget_optimization_jobs_status_valid CHECK ((status = ANY (ARRAY['compute_pending'::text, 'compute_running'::text, 'compute_succeeded'::text, 'compute_failed'::text, 'compute_timeout'::text, 'compute_cancelled'::text])))
);

ALTER TABLE ONLY public.budget_optimization_jobs FORCE ROW LEVEL SECURITY;


--
-- Name: celery_taskmeta; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.celery_taskmeta (
    id integer NOT NULL,
    task_id character varying(155) NOT NULL,
    status character varying(50) NOT NULL,
    result bytea,
    date_done timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    traceback text,
    name character varying(155),
    args text,
    kwargs text,
    worker character varying(155),
    retries integer
);


--
-- Name: celery_taskmeta_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.celery_taskmeta_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: celery_taskmeta_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.celery_taskmeta_id_seq OWNED BY public.celery_taskmeta.id;


--
-- Name: celery_tasksetmeta; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.celery_tasksetmeta (
    id integer NOT NULL,
    taskset_id character varying(155) NOT NULL,
    result bytea,
    date_done timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: celery_tasksetmeta_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.celery_tasksetmeta_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: celery_tasksetmeta_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.celery_tasksetmeta_id_seq OWNED BY public.celery_tasksetmeta.id;


--
-- Name: channel_assignment_corrections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.channel_assignment_corrections (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    entity_type character varying(50) NOT NULL,
    entity_id uuid NOT NULL,
    from_channel character varying(50) NOT NULL,
    to_channel character varying(50) NOT NULL,
    corrected_by character varying(255) NOT NULL,
    corrected_at timestamp with time zone DEFAULT now() NOT NULL,
    reason text NOT NULL,
    metadata jsonb,
    CONSTRAINT channel_assignment_corrections_entity_type_check CHECK (((entity_type)::text = ANY ((ARRAY['event'::character varying, 'allocation'::character varying])::text[])))
);

ALTER TABLE ONLY public.channel_assignment_corrections FORCE ROW LEVEL SECURITY;


--
-- Name: channel_state_transitions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.channel_state_transitions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    channel_code character varying(50) NOT NULL,
    from_state character varying(50),
    to_state character varying(50) NOT NULL,
    changed_by character varying(255) NOT NULL,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    reason text,
    metadata jsonb
);


--
-- Name: channel_taxonomy; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.channel_taxonomy (
    code text NOT NULL,
    family text NOT NULL,
    is_paid boolean NOT NULL,
    display_name text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    state character varying(50) DEFAULT 'active'::character varying NOT NULL,
    CONSTRAINT channel_taxonomy_state_check CHECK (((state)::text = ANY ((ARRAY['draft'::character varying, 'active'::character varying, 'deprecated'::character varying, 'archived'::character varying])::text[])))
);


--
-- Name: compliance_audit_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.compliance_audit_ledger (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    occurred_at timestamp with time zone NOT NULL,
    audit_event_type character varying(64) NOT NULL,
    correlation_id uuid,
    idempotency_key character varying(255) NOT NULL,
    selector jsonb DEFAULT '{}'::jsonb NOT NULL,
    selector_hash character(64) NOT NULL,
    effects jsonb DEFAULT '{}'::jsonb NOT NULL,
    evidence_hash character(64) NOT NULL,
    actor character varying(64) DEFAULT 'privacy_worker'::character varying NOT NULL
);

ALTER TABLE ONLY public.compliance_audit_ledger FORCE ROW LEVEL SECURITY;


--
-- Name: dead_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dead_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ingested_at timestamp with time zone DEFAULT now() NOT NULL,
    source text NOT NULL,
    error_code text NOT NULL,
    error_detail jsonb NOT NULL,
    raw_payload jsonb NOT NULL,
    correlation_id uuid,
    external_event_id text,
    event_type character varying(50) NOT NULL,
    error_type character varying(100) NOT NULL,
    error_message text NOT NULL,
    error_traceback text,
    retry_count integer DEFAULT 0 NOT NULL,
    last_retry_at timestamp with time zone,
    remediation_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    remediation_notes text,
    resolved_at timestamp with time zone,
    idempotency_key character varying(255),
    CONSTRAINT ck_dead_events_remediation_status_valid CHECK (((remediation_status)::text = ANY ((ARRAY['pending'::character varying, 'in_progress'::character varying, 'resolved'::character varying, 'abandoned'::character varying])::text[]))),
    CONSTRAINT ck_dead_events_retry_count_positive CHECK ((retry_count >= 0))
);

ALTER TABLE ONLY public.dead_events FORCE ROW LEVEL SECURITY;


--
-- Name: dead_events_quarantine; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dead_events_quarantine (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid,
    source text NOT NULL,
    raw_payload jsonb NOT NULL,
    error_type text NOT NULL,
    error_code text,
    error_message text NOT NULL,
    error_detail jsonb DEFAULT '{}'::jsonb NOT NULL,
    correlation_id uuid,
    ingested_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by_role text DEFAULT CURRENT_USER NOT NULL,
    idempotency_key character varying(255)
);

ALTER TABLE ONLY public.dead_events_quarantine FORCE ROW LEVEL SECURITY;


--
-- Name: ephemeral_click_resolution; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ephemeral_click_resolution (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    click_id text NOT NULL,
    session_id uuid NOT NULL,
    observed_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    source text DEFAULT 'ingestion_runtime'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_ephemeral_click_resolution_expires_after_observed CHECK ((expires_at > observed_at)),
    CONSTRAINT ck_ephemeral_click_resolution_max_24h CHECK ((expires_at <= (observed_at + '24:00:00'::interval)))
);

ALTER TABLE ONLY public.ephemeral_click_resolution FORCE ROW LEVEL SECURITY;


--
-- Name: ephemeral_order_resolution; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ephemeral_order_resolution (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    order_id text NOT NULL,
    session_id uuid NOT NULL,
    observed_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    source text DEFAULT 'ingestion_runtime'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_ephemeral_order_resolution_expires_after_observed CHECK ((expires_at > observed_at)),
    CONSTRAINT ck_ephemeral_order_resolution_max_24h CHECK ((expires_at <= (observed_at + '24:00:00'::interval)))
);

ALTER TABLE ONLY public.ephemeral_order_resolution FORCE ROW LEVEL SECURITY;


--
-- Name: explanation_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.explanation_cache (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    explanation text NOT NULL,
    citations jsonb NOT NULL,
    cache_hit_count integer DEFAULT 0,
    ci_validation_test boolean DEFAULT false,
    CONSTRAINT explanation_cache_cache_hit_count_check CHECK (((cache_hit_count IS NULL) OR (cache_hit_count >= 0)))
);

ALTER TABLE ONLY public.explanation_cache FORCE ROW LEVEL SECURITY;


--
-- Name: investigation_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.investigation_jobs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    correlation_id character varying(255),
    status character varying(30) DEFAULT 'PENDING'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    min_hold_until timestamp with time zone NOT NULL,
    ready_for_review_at timestamp with time zone,
    approved_at timestamp with time zone,
    completed_at timestamp with time zone,
    result jsonb,
    metadata jsonb,
    request_id text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    rejected_at timestamp with time zone,
    refine_requested_at timestamp with time zone,
    rerun_requested_at timestamp with time zone,
    failed_at timestamp with time zone,
    timeout_at timestamp with time zone,
    cancelled_at timestamp with time zone,
    failure_code text,
    failure_reason text,
    CONSTRAINT ck_investigation_jobs_ready_timestamp_integrity CHECK ((((status)::text <> ALL ((ARRAY['ready_for_review'::character varying, 'approved'::character varying, 'rejected'::character varying, 'refine_requested'::character varying, 'rerun_requested'::character varying, 'completed'::character varying])::text[])) OR (ready_for_review_at IS NOT NULL))),
    CONSTRAINT ck_investigation_jobs_review_timestamp_integrity CHECK ((((status)::text <> ALL ((ARRAY['approved'::character varying, 'completed'::character varying])::text[])) OR (approved_at IS NOT NULL))),
    CONSTRAINT ck_investigation_jobs_status_valid CHECK (((status)::text = ANY ((ARRAY['submitted'::character varying, 'validating'::character varying, 'investigating'::character varying, 'ready_for_review'::character varying, 'approved'::character varying, 'rejected'::character varying, 'refine_requested'::character varying, 'rerun_requested'::character varying, 'completed'::character varying, 'failed'::character varying, 'timeout'::character varying, 'cancelled'::character varying])::text[])))
);

ALTER TABLE ONLY public.investigation_jobs FORCE ROW LEVEL SECURITY;


--
-- Name: investigation_tool_calls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.investigation_tool_calls (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    investigation_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tool_name text NOT NULL,
    input_params jsonb NOT NULL,
    output jsonb
);

ALTER TABLE ONLY public.investigation_tool_calls FORCE ROW LEVEL SECURITY;


--
-- Name: investigations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.investigations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    query text NOT NULL,
    status text NOT NULL,
    result jsonb,
    cost_cents integer DEFAULT 0,
    request_id text NOT NULL,
    authority_job_id uuid,
    lifecycle_role text DEFAULT 'internal_trace'::text NOT NULL,
    CONSTRAINT ck_investigations_internal_trace_only CHECK ((lifecycle_role = 'internal_trace'::text)),
    CONSTRAINT ck_investigations_status_valid CHECK ((status = ANY (ARRAY['compute_pending'::text, 'compute_running'::text, 'compute_succeeded'::text, 'compute_failed'::text, 'compute_timeout'::text, 'compute_cancelled'::text])))
);

ALTER TABLE ONLY public.investigations FORCE ROW LEVEL SECURITY;


--
-- Name: jwt_verification_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.jwt_verification_cache (
    singleton_id smallint NOT NULL,
    jwks_json text,
    fetched_at timestamp with time zone,
    next_allowed_refresh_at timestamp with time zone DEFAULT now() NOT NULL,
    last_refresh_error_at timestamp with time zone,
    refresh_error_count integer DEFAULT 0 NOT NULL,
    refresh_event_count bigint DEFAULT 0 NOT NULL,
    last_refresh_reason text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT jwt_verification_cache_singleton_id_check CHECK ((singleton_id = 1))
);


--
-- Name: kombu_message; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kombu_message (
    id integer NOT NULL,
    visible boolean DEFAULT true NOT NULL,
    "timestamp" timestamp without time zone,
    payload text NOT NULL,
    version smallint DEFAULT '1'::smallint NOT NULL,
    queue_id integer NOT NULL
);


--
-- Name: kombu_message_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kombu_message_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kombu_message_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kombu_message_id_seq OWNED BY public.kombu_message.id;


--
-- Name: kombu_queue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kombu_queue (
    id integer NOT NULL,
    name character varying(200) NOT NULL
);


--
-- Name: kombu_queue_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kombu_queue_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kombu_queue_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kombu_queue_id_seq OWNED BY public.kombu_queue.id;


--
-- Name: llm_api_calls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_api_calls (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    endpoint text NOT NULL,
    model text NOT NULL,
    input_tokens integer NOT NULL,
    output_tokens integer NOT NULL,
    cost_cents integer NOT NULL,
    latency_ms integer NOT NULL,
    was_cached boolean DEFAULT false NOT NULL,
    request_metadata jsonb,
    request_id text NOT NULL,
    user_id uuid DEFAULT '00000000-0000-0000-0000-000000000000'::uuid NOT NULL,
    provider text DEFAULT 'stub'::text NOT NULL,
    distillation_eligible boolean DEFAULT false NOT NULL,
    request_metadata_ref jsonb,
    response_metadata_ref jsonb,
    reasoning_trace_ref jsonb,
    status text DEFAULT 'pending'::text NOT NULL,
    block_reason text,
    failure_reason text,
    breaker_state text DEFAULT 'closed'::text NOT NULL,
    provider_attempted boolean DEFAULT false NOT NULL,
    budget_reservation_cents integer DEFAULT 0 NOT NULL,
    budget_settled_cents integer DEFAULT 0 NOT NULL,
    cache_key text,
    cache_watermark bigint,
    prompt_fingerprint text NOT NULL,
    complexity_score double precision DEFAULT 0 NOT NULL,
    complexity_bucket integer DEFAULT 1 NOT NULL,
    chosen_tier text DEFAULT 'cheap'::text NOT NULL,
    chosen_provider text DEFAULT 'openai'::text NOT NULL,
    chosen_model text DEFAULT 'gpt-4o-mini'::text NOT NULL,
    policy_id text DEFAULT 'unknown'::text NOT NULL,
    policy_version text DEFAULT 'unknown'::text NOT NULL,
    routing_reason text DEFAULT 'bucket_policy'::text NOT NULL,
    CONSTRAINT ck_llm_api_calls_breaker_state_valid CHECK ((breaker_state = ANY (ARRAY['closed'::text, 'open'::text, 'half_open'::text]))),
    CONSTRAINT ck_llm_api_calls_budget_reservation_nonnegative CHECK ((budget_reservation_cents >= 0)),
    CONSTRAINT ck_llm_api_calls_budget_settled_nonnegative CHECK ((budget_settled_cents >= 0)),
    CONSTRAINT ck_llm_api_calls_chosen_tier_valid CHECK ((chosen_tier = ANY (ARRAY['cheap'::text, 'standard'::text, 'premium'::text]))),
    CONSTRAINT ck_llm_api_calls_complexity_bucket_range CHECK (((complexity_bucket >= 1) AND (complexity_bucket <= 10))),
    CONSTRAINT ck_llm_api_calls_complexity_score_range CHECK (((complexity_score >= (0)::double precision) AND (complexity_score <= (1)::double precision))),
    CONSTRAINT ck_llm_api_calls_status_valid CHECK ((status = ANY (ARRAY['pending'::text, 'success'::text, 'blocked'::text, 'failed'::text, 'idempotent_replay'::text]))),
    CONSTRAINT llm_api_calls_cost_cents_check CHECK ((cost_cents >= 0)),
    CONSTRAINT llm_api_calls_input_tokens_check CHECK ((input_tokens >= 0)),
    CONSTRAINT llm_api_calls_latency_ms_check CHECK ((latency_ms >= 0)),
    CONSTRAINT llm_api_calls_output_tokens_check CHECK ((output_tokens >= 0))
);

ALTER TABLE ONLY public.llm_api_calls FORCE ROW LEVEL SECURITY;


--
-- Name: llm_breaker_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_breaker_state (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    breaker_key text NOT NULL,
    state text NOT NULL,
    failure_count integer DEFAULT 0 NOT NULL,
    opened_at timestamp with time zone,
    last_trip_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT llm_breaker_state_failure_count_check CHECK ((failure_count >= 0)),
    CONSTRAINT llm_breaker_state_state_check CHECK ((state = ANY (ARRAY['closed'::text, 'open'::text, 'half_open'::text])))
);

ALTER TABLE ONLY public.llm_breaker_state FORCE ROW LEVEL SECURITY;


--
-- Name: llm_budget_reservations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_budget_reservations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    endpoint text NOT NULL,
    request_id text NOT NULL,
    month date NOT NULL,
    reserved_cents integer NOT NULL,
    settled_cents integer DEFAULT 0 NOT NULL,
    state text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT llm_budget_reservations_reserved_cents_check CHECK ((reserved_cents >= 0)),
    CONSTRAINT llm_budget_reservations_settled_cents_check CHECK ((settled_cents >= 0)),
    CONSTRAINT llm_budget_reservations_state_check CHECK ((state = ANY (ARRAY['reserved'::text, 'settled'::text, 'released'::text, 'blocked'::text])))
);

ALTER TABLE ONLY public.llm_budget_reservations FORCE ROW LEVEL SECURITY;


--
-- Name: llm_call_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_call_audit (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    request_id character varying(255) NOT NULL,
    correlation_id character varying(255),
    requested_model character varying(100) NOT NULL,
    resolved_model character varying(100) NOT NULL,
    estimated_cost_cents integer NOT NULL,
    cap_cents integer NOT NULL,
    decision character varying(20) NOT NULL,
    reason text NOT NULL,
    input_tokens integer,
    output_tokens integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id uuid DEFAULT '00000000-0000-0000-0000-000000000000'::uuid NOT NULL,
    prompt_fingerprint text NOT NULL,
    CONSTRAINT llm_call_audit_decision_check CHECK (((decision)::text = ANY ((ARRAY['ALLOW'::character varying, 'BLOCK'::character varying, 'FALLBACK'::character varying])::text[])))
);

ALTER TABLE ONLY public.llm_call_audit FORCE ROW LEVEL SECURITY;


--
-- Name: llm_hourly_shutoff_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_hourly_shutoff_state (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    hour_start timestamp with time zone NOT NULL,
    is_shutoff boolean DEFAULT false NOT NULL,
    reason text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    threshold_cents integer DEFAULT 0 NOT NULL,
    total_cost_cents integer DEFAULT 0 NOT NULL,
    total_calls integer DEFAULT 0 NOT NULL,
    disabled_until timestamp with time zone,
    CONSTRAINT llm_hourly_shutoff_state_threshold_cents_check CHECK ((threshold_cents >= 0)),
    CONSTRAINT llm_hourly_shutoff_state_total_calls_check CHECK ((total_calls >= 0)),
    CONSTRAINT llm_hourly_shutoff_state_total_cost_cents_check CHECK ((total_cost_cents >= 0))
);

ALTER TABLE ONLY public.llm_hourly_shutoff_state FORCE ROW LEVEL SECURITY;


--
-- Name: llm_monthly_budget_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_monthly_budget_state (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    month date NOT NULL,
    cap_cents integer NOT NULL,
    spent_cents integer DEFAULT 0 NOT NULL,
    reserved_cents integer DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT llm_monthly_budget_state_cap_cents_check CHECK ((cap_cents >= 0)),
    CONSTRAINT llm_monthly_budget_state_reserved_cents_check CHECK ((reserved_cents >= 0)),
    CONSTRAINT llm_monthly_budget_state_spent_cents_check CHECK ((spent_cents >= 0))
);

ALTER TABLE ONLY public.llm_monthly_budget_state FORCE ROW LEVEL SECURITY;


--
-- Name: llm_monthly_costs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_monthly_costs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    month date NOT NULL,
    total_cost_cents integer NOT NULL,
    total_calls integer NOT NULL,
    model_breakdown jsonb NOT NULL,
    user_id uuid DEFAULT '00000000-0000-0000-0000-000000000000'::uuid NOT NULL,
    CONSTRAINT llm_monthly_costs_total_calls_check CHECK ((total_calls >= 0)),
    CONSTRAINT llm_monthly_costs_total_cost_cents_check CHECK ((total_cost_cents >= 0))
);

ALTER TABLE ONLY public.llm_monthly_costs FORCE ROW LEVEL SECURITY;


--
-- Name: llm_semantic_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_semantic_cache (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    endpoint text NOT NULL,
    cache_key text NOT NULL,
    watermark bigint DEFAULT 0 NOT NULL,
    provider text NOT NULL,
    model text NOT NULL,
    response_text text NOT NULL,
    response_metadata_ref jsonb,
    reasoning_trace_ref jsonb,
    input_tokens integer DEFAULT 0 NOT NULL,
    output_tokens integer DEFAULT 0 NOT NULL,
    cost_cents integer DEFAULT 0 NOT NULL,
    hit_count integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT llm_semantic_cache_cost_cents_check CHECK ((cost_cents >= 0)),
    CONSTRAINT llm_semantic_cache_hit_count_check CHECK ((hit_count >= 0)),
    CONSTRAINT llm_semantic_cache_input_tokens_check CHECK ((input_tokens >= 0)),
    CONSTRAINT llm_semantic_cache_output_tokens_check CHECK ((output_tokens >= 0))
);

ALTER TABLE ONLY public.llm_semantic_cache FORCE ROW LEVEL SECURITY;


--
-- Name: llm_validation_failures; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_validation_failures (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    endpoint text NOT NULL,
    validation_error text NOT NULL,
    request_payload jsonb NOT NULL,
    response_payload jsonb
);

ALTER TABLE ONLY public.llm_validation_failures FORCE ROW LEVEL SECURITY;


--
-- Name: message_id_sequence; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.message_id_sequence
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: message_id_sequence; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.message_id_sequence OWNED BY public.kombu_message.id;


--
-- Name: mv_allocation_summary; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mv_allocation_summary AS
 SELECT aa.tenant_id,
    aa.event_id,
    aa.model_version,
    sum(aa.allocated_revenue_cents) AS total_allocated_cents,
    e.revenue_cents AS event_revenue_cents,
        CASE
            WHEN (e.revenue_cents IS NULL) THEN NULL::boolean
            ELSE (sum(aa.allocated_revenue_cents) = e.revenue_cents)
        END AS is_balanced,
        CASE
            WHEN (e.revenue_cents IS NULL) THEN NULL::bigint
            ELSE abs((sum(aa.allocated_revenue_cents) - e.revenue_cents))
        END AS drift_cents
   FROM (public.attribution_allocations aa
     LEFT JOIN public.attribution_events e ON ((aa.event_id = e.id)))
  GROUP BY aa.tenant_id, aa.event_id, aa.model_version, e.revenue_cents
  WITH NO DATA;


--
-- Name: mv_channel_performance; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mv_channel_performance AS
 SELECT attribution_allocations.tenant_id,
    attribution_allocations.channel_code,
    date_trunc('day'::text, attribution_allocations.created_at) AS allocation_date,
    count(DISTINCT attribution_allocations.event_id) AS total_conversions,
    sum(attribution_allocations.allocated_revenue_cents) AS total_revenue_cents,
    avg(attribution_allocations.confidence_score) AS avg_confidence_score,
    count(*) AS total_allocations
   FROM public.attribution_allocations
  WHERE (attribution_allocations.created_at >= (CURRENT_DATE - '90 days'::interval))
  GROUP BY attribution_allocations.tenant_id, attribution_allocations.channel_code, (date_trunc('day'::text, attribution_allocations.created_at))
  WITH NO DATA;


--
-- Name: revenue_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.revenue_ledger (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    revenue_cents integer DEFAULT 0 NOT NULL,
    is_verified boolean DEFAULT false NOT NULL,
    verified_at timestamp with time zone,
    reconciliation_run_id uuid,
    allocation_id uuid,
    posted_at timestamp with time zone DEFAULT now() NOT NULL,
    transaction_id character varying(255) NOT NULL,
    order_id character varying(255),
    state character varying(50) NOT NULL,
    previous_state character varying(50),
    amount_cents integer NOT NULL,
    currency character varying(3) DEFAULT 'USD'::character varying NOT NULL,
    verification_source character varying(50) NOT NULL,
    verification_timestamp timestamp with time zone NOT NULL,
    metadata jsonb,
    claimed_total_cents bigint DEFAULT 0 NOT NULL,
    verified_total_cents bigint DEFAULT 0 NOT NULL,
    ghost_revenue_cents bigint DEFAULT 0 NOT NULL,
    discrepancy_bps integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_revenue_ledger_amount_positive CHECK ((amount_cents >= 0)),
    CONSTRAINT ck_revenue_ledger_claimed_positive CHECK ((claimed_total_cents >= 0)),
    CONSTRAINT ck_revenue_ledger_discrepancy_positive CHECK ((discrepancy_bps >= 0)),
    CONSTRAINT ck_revenue_ledger_ghost_positive CHECK ((ghost_revenue_cents >= 0)),
    CONSTRAINT ck_revenue_ledger_revenue_positive CHECK ((revenue_cents >= 0)),
    CONSTRAINT ck_revenue_ledger_state_valid CHECK (((state)::text = ANY ((ARRAY['authorized'::character varying, 'captured'::character varying, 'refunded'::character varying, 'chargeback'::character varying])::text[]))),
    CONSTRAINT ck_revenue_ledger_verified_positive CHECK ((verified_total_cents >= 0)),
    CONSTRAINT revenue_ledger_revenue_cents_check CHECK ((revenue_cents >= 0))
);

ALTER TABLE ONLY public.revenue_ledger FORCE ROW LEVEL SECURITY;


--
-- Name: mv_daily_revenue_summary; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mv_daily_revenue_summary AS
 SELECT revenue_ledger.tenant_id,
    date_trunc('day'::text, revenue_ledger.verification_timestamp) AS revenue_date,
    revenue_ledger.state,
    revenue_ledger.currency,
    sum(revenue_ledger.amount_cents) AS total_amount_cents,
    count(*) AS transaction_count
   FROM public.revenue_ledger
  WHERE ((revenue_ledger.state)::text = ANY ((ARRAY['captured'::character varying, 'refunded'::character varying, 'chargeback'::character varying])::text[]))
  GROUP BY revenue_ledger.tenant_id, (date_trunc('day'::text, revenue_ledger.verification_timestamp)), revenue_ledger.state, revenue_ledger.currency
  WITH NO DATA;


--
-- Name: mv_realtime_revenue; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mv_realtime_revenue AS
 SELECT rl.tenant_id,
    ((COALESCE(sum(COALESCE(rl.amount_cents, rl.revenue_cents)), (0)::bigint))::numeric / 100.0) AS total_revenue,
    bool_or(COALESCE(rl.is_verified, false)) AS verified,
    (EXTRACT(epoch FROM (now() - max(rl.updated_at))))::integer AS data_freshness_seconds
   FROM public.revenue_ledger rl
  GROUP BY rl.tenant_id
  WITH NO DATA;


--
-- Name: reconciliation_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reconciliation_runs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_run_at timestamp with time zone NOT NULL,
    state character varying(20) DEFAULT 'idle'::character varying NOT NULL,
    error_message text,
    run_metadata jsonb,
    CONSTRAINT ck_reconciliation_runs_state_valid CHECK (((state)::text = ANY ((ARRAY['idle'::character varying, 'running'::character varying, 'failed'::character varying, 'completed'::character varying])::text[]))),
    CONSTRAINT reconciliation_runs_state_check CHECK (((state)::text = ANY ((ARRAY['idle'::character varying, 'running'::character varying, 'failed'::character varying, 'completed'::character varying])::text[])))
);

ALTER TABLE ONLY public.reconciliation_runs FORCE ROW LEVEL SECURITY;


--
-- Name: mv_reconciliation_status; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mv_reconciliation_status AS
 SELECT rr.tenant_id,
    rr.state,
    rr.last_run_at,
    rr.id AS reconciliation_run_id
   FROM (public.reconciliation_runs rr
     JOIN ( SELECT reconciliation_runs.tenant_id,
            max(reconciliation_runs.last_run_at) AS max_last_run_at
           FROM public.reconciliation_runs
          GROUP BY reconciliation_runs.tenant_id) latest ON (((rr.tenant_id = latest.tenant_id) AND (rr.last_run_at = latest.max_last_run_at))))
  WITH NO DATA;


--
-- Name: oauth_handshake_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.oauth_handshake_sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    platform text NOT NULL,
    state_nonce_hash text NOT NULL,
    encrypted_pkce_verifier bytea,
    pkce_key_id text,
    pkce_code_challenge text,
    pkce_code_challenge_method text,
    redirect_uri text,
    provider_session_metadata jsonb,
    status text DEFAULT 'pending'::text NOT NULL,
    terminal_reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    consumed_at timestamp with time zone,
    gc_after timestamp with time zone NOT NULL,
    CONSTRAINT ck_oauth_handshake_sessions_consumed_shape CHECK ((((status = 'consumed'::text) AND (consumed_at IS NOT NULL)) OR ((status <> 'consumed'::text) AND (consumed_at IS NULL)))),
    CONSTRAINT ck_oauth_handshake_sessions_gc_after_window CHECK ((gc_after >= created_at)),
    CONSTRAINT ck_oauth_handshake_sessions_pkce_key_binding CHECK ((((encrypted_pkce_verifier IS NULL) AND (pkce_key_id IS NULL)) OR ((encrypted_pkce_verifier IS NOT NULL) AND (pkce_key_id IS NOT NULL)))),
    CONSTRAINT ck_oauth_handshake_sessions_pkce_method CHECK (((pkce_code_challenge_method IS NULL) OR (pkce_code_challenge_method = ANY (ARRAY['S256'::text, 'plain'::text])))),
    CONSTRAINT ck_oauth_handshake_sessions_status_valid CHECK ((status = ANY (ARRAY['pending'::text, 'consumed'::text, 'expired'::text, 'aborted'::text])))
);

ALTER TABLE ONLY public.oauth_handshake_sessions FORCE ROW LEVEL SECURITY;


--
-- Name: pii_audit_findings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pii_audit_findings (
    id bigint NOT NULL,
    table_name text NOT NULL,
    column_name text NOT NULL,
    record_id uuid NOT NULL,
    detected_key text NOT NULL,
    sample_snippet text,
    detected_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: pii_audit_findings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pii_audit_findings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pii_audit_findings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pii_audit_findings_id_seq OWNED BY public.pii_audit_findings.id;


--
-- Name: platform_connections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.platform_connections (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    platform text NOT NULL,
    platform_account_id text NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    connection_metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT platform_connections_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'active'::text, 'disabled'::text])))
);

ALTER TABLE ONLY public.platform_connections FORCE ROW LEVEL SECURITY;


--
-- Name: platform_credentials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.platform_credentials (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    platform_connection_id uuid NOT NULL,
    platform text NOT NULL,
    encrypted_access_token bytea NOT NULL,
    encrypted_refresh_token bytea,
    expires_at timestamp with time zone,
    scope text,
    token_type text,
    key_id text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    next_refresh_due_at timestamp with time zone,
    lifecycle_status text DEFAULT 'active'::text NOT NULL,
    refresh_failure_count integer DEFAULT 0 NOT NULL,
    last_failure_class text,
    last_failure_at timestamp with time zone,
    last_refresh_at timestamp with time zone,
    revoked_at timestamp with time zone,
    CONSTRAINT ck_platform_credentials_lifecycle_status_valid CHECK ((lifecycle_status = ANY (ARRAY['active'::text, 'degraded'::text, 'revoked'::text]))),
    CONSTRAINT ck_platform_credentials_refresh_failure_count_nonnegative CHECK ((refresh_failure_count >= 0)),
    CONSTRAINT ck_platform_credentials_revoked_refresh_due_null CHECK (((lifecycle_status <> 'revoked'::text) OR (next_refresh_due_at IS NULL))),
    CONSTRAINT ck_platform_credentials_revoked_status_consistency CHECK (((revoked_at IS NULL) OR (lifecycle_status = 'revoked'::text)))
);

ALTER TABLE ONLY public.platform_credentials FORCE ROW LEVEL SECURITY;


--
-- Name: queue_id_sequence; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.queue_id_sequence
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: queue_id_sequence; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.queue_id_sequence OWNED BY public.kombu_queue.id;


--
-- Name: r4_crash_barriers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.r4_crash_barriers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    task_id text NOT NULL,
    scenario text NOT NULL,
    attempt_no integer NOT NULL,
    worker_pid integer,
    wrote_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT r4_crash_barriers_attempt_no_check CHECK ((attempt_no >= 1))
);

ALTER TABLE ONLY public.r4_crash_barriers FORCE ROW LEVEL SECURITY;


--
-- Name: r4_recovery_exclusions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.r4_recovery_exclusions (
    scenario text NOT NULL,
    task_id text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: r4_task_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.r4_task_attempts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    task_id text NOT NULL,
    scenario text NOT NULL,
    attempt_no integer NOT NULL,
    worker_pid integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT r4_task_attempts_attempt_no_check CHECK ((attempt_no >= 1))
);

ALTER TABLE ONLY public.r4_task_attempts FORCE ROW LEVEL SECURITY;


--
-- Name: raw_event_payloads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.raw_event_payloads (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    event_id uuid NOT NULL,
    payload_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    ip_address character varying(64),
    user_agent character varying(1024),
    raw_headers jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    lookup_hash character varying(64) NOT NULL,
    CONSTRAINT ck_raw_event_payloads_lookup_hash_sha256 CHECK ((char_length((lookup_hash)::text) = 64))
);

ALTER TABLE ONLY public.raw_event_payloads FORCE ROW LEVEL SECURITY;


--
-- Name: revenue_cache_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.revenue_cache_entries (
    tenant_id uuid NOT NULL,
    cache_key text NOT NULL,
    payload jsonb NOT NULL,
    data_as_of timestamp with time zone NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    error_cooldown_until timestamp with time zone,
    last_error_at timestamp with time zone,
    last_error_message text,
    etag text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.revenue_cache_entries FORCE ROW LEVEL SECURITY;


--
-- Name: revenue_state_transitions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.revenue_state_transitions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ledger_id uuid NOT NULL,
    from_state character varying(50),
    to_state character varying(50) NOT NULL,
    reason text,
    transitioned_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);

ALTER TABLE ONLY public.revenue_state_transitions FORCE ROW LEVEL SECURITY;


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    code text NOT NULL,
    description text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_roles_code_lowercase CHECK ((code = lower(code))),
    CONSTRAINT ck_roles_code_not_empty CHECK ((length(TRIM(BOTH FROM code)) > 0))
);


--
-- Name: session_authority; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.session_authority (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    issued_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    last_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    invalidated_at timestamp with time zone,
    invalidation_reason text,
    issued_by text DEFAULT 'ingestion_runtime'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_session_authority_expires_after_issued CHECK ((expires_at > issued_at)),
    CONSTRAINT ck_session_authority_invalidation_after_issued CHECK (((invalidated_at IS NULL) OR (invalidated_at >= issued_at))),
    CONSTRAINT ck_session_authority_max_24h CHECK ((expires_at <= (issued_at + '24:00:00'::interval)))
);

ALTER TABLE ONLY public.session_authority FORCE ROW LEVEL SECURITY;


--
-- Name: task_id_sequence; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.task_id_sequence
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: task_id_sequence; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.task_id_sequence OWNED BY public.celery_taskmeta.id;


--
-- Name: taskset_id_sequence; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.taskset_id_sequence
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: taskset_id_sequence; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.taskset_id_sequence OWNED BY public.celery_tasksetmeta.id;


--
-- Name: tenant_membership_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_membership_roles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    membership_id uuid NOT NULL,
    role_code text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.tenant_membership_roles FORCE ROW LEVEL SECURITY;


--
-- Name: tenant_memberships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_memberships (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    membership_status text DEFAULT 'active'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_tenant_memberships_status_valid CHECK ((membership_status = ANY (ARRAY['active'::text, 'revoked'::text])))
);

ALTER TABLE ONLY public.tenant_memberships FORCE ROW LEVEL SECURITY;


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    api_key_hash character varying(255) NOT NULL,
    notification_email character varying(255) NOT NULL,
    shopify_webhook_secret_ciphertext bytea,
    shopify_webhook_secret_key_id text,
    stripe_webhook_secret_ciphertext bytea,
    stripe_webhook_secret_key_id text,
    paypal_webhook_secret_ciphertext bytea,
    paypal_webhook_secret_key_id text,
    woocommerce_webhook_secret_ciphertext bytea,
    woocommerce_webhook_secret_key_id text,
    CONSTRAINT ck_tenants_name_not_empty CHECK ((length(TRIM(BOTH FROM name)) > 0))
);


--
-- Name: trust_access_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trust_access_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    event_type text NOT NULL,
    status text NOT NULL,
    request_identity_hash text NOT NULL,
    idempotency_key_hash text NOT NULL,
    subject_type text NOT NULL,
    subject_ref_hash text,
    envelope_hash text,
    semantic_truth_hash text,
    policy_state text NOT NULL,
    reason_code text,
    audit_ref text NOT NULL,
    audit_hash text NOT NULL,
    evidence_refs_allowed boolean DEFAULT true NOT NULL,
    replay_count integer DEFAULT 0 NOT NULL,
    last_replayed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    issuance_state text DEFAULT 'authorized'::text NOT NULL,
    issued_at timestamp with time zone,
    issued_signing_key_id text,
    issued_signature_hash text,
    issuance_attempted_at timestamp with time zone,
    issuance_outcome_unknown_at timestamp with time zone,
    issued_signature bytea,
    issuance_attempt_count integer DEFAULT 0 NOT NULL,
    issuance_unknown_outcome_count integer DEFAULT 0 NOT NULL,
    known_signature_at timestamp with time zone,
    issued_attempt_id uuid,
    issued_envelope jsonb,
    CONSTRAINT ck_trust_access_log_attempt_state_shape CHECK ((((issuance_state = ANY (ARRAY['signing'::text, 'signature_known'::text, 'issued'::text, 'issued_pre_xvii'::text, 'issued_legacy'::text, 'signature_outcome_unknown'::text])) AND (issuance_attempted_at IS NOT NULL)) OR ((issuance_state = ANY (ARRAY['authorized'::text, 'failed'::text, 'not_applicable'::text])) AND (issuance_attempted_at IS NULL)))),
    CONSTRAINT ck_trust_access_log_audit_ref CHECK ((audit_ref ~ '^urn:skeldir:audit:[A-Za-z0-9._:-]+$'::text)),
    CONSTRAINT ck_trust_access_log_event_type CHECK ((event_type = ANY (ARRAY['issuance'::text, 'refusal'::text, 'scope_denial'::text, 'replay'::text]))),
    CONSTRAINT ck_trust_access_log_hashes CHECK (((request_identity_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (idempotency_key_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (audit_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND ((subject_ref_hash IS NULL) OR (subject_ref_hash ~ '^sha256:[0-9a-f]{64}$'::text)) AND ((envelope_hash IS NULL) OR (envelope_hash ~ '^sha256:[0-9a-f]{64}$'::text)) AND ((semantic_truth_hash IS NULL) OR (semantic_truth_hash ~ '^sha256:[0-9a-f]{64}$'::text)))),
    CONSTRAINT ck_trust_access_log_issuance_state CHECK ((issuance_state = ANY (ARRAY['authorized'::text, 'signing'::text, 'signature_known'::text, 'issued'::text, 'issued_pre_xvii'::text, 'issued_legacy'::text, 'failed'::text, 'signature_outcome_unknown'::text, 'not_applicable'::text]))),
    CONSTRAINT ck_trust_access_log_issuance_state_event CHECK ((((event_type = 'issuance'::text) AND (issuance_state <> 'not_applicable'::text)) OR ((event_type <> 'issuance'::text) AND (issuance_state = 'not_applicable'::text)))),
    CONSTRAINT ck_trust_access_log_issued_requires_crypto CHECK (((issuance_state <> 'issued'::text) OR ((issued_at IS NOT NULL) AND (issuance_attempted_at IS NOT NULL) AND (known_signature_at IS NOT NULL) AND (issued_attempt_id IS NOT NULL) AND (issued_signing_key_id IS NOT NULL) AND (issued_signature_hash IS NOT NULL) AND (issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (issued_signature IS NOT NULL) AND (octet_length(issued_signature) = 64) AND (envelope_hash IS NOT NULL) AND (issued_envelope IS NOT NULL) AND (jsonb_typeof(issued_envelope) = 'object'::text)))),
    CONSTRAINT ck_trust_access_log_known_state_shape CHECK ((((issuance_state = ANY (ARRAY['signature_known'::text, 'issued'::text])) AND (known_signature_at IS NOT NULL) AND (issued_attempt_id IS NOT NULL)) OR ((issuance_state <> ALL (ARRAY['signature_known'::text, 'issued'::text])) AND (known_signature_at IS NULL) AND (issued_attempt_id IS NULL)))),
    CONSTRAINT ck_trust_access_log_legacy_issued_evidence CHECK (((issuance_state <> 'issued_legacy'::text) OR ((issued_at IS NOT NULL) AND (issuance_attempted_at IS NOT NULL) AND (issued_signing_key_id IS NOT NULL) AND (issued_signature_hash IS NOT NULL) AND (issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (issued_signature IS NULL) AND (envelope_hash IS NOT NULL) AND (known_signature_at IS NULL) AND (issued_attempt_id IS NULL) AND (issued_envelope IS NULL)))),
    CONSTRAINT ck_trust_access_log_nonissued_has_no_crypto CHECK (((issuance_state = ANY (ARRAY['issued'::text, 'issued_pre_xvii'::text, 'issued_legacy'::text])) OR ((issued_at IS NULL) AND (issued_signing_key_id IS NULL) AND (issued_signature_hash IS NULL) AND (issued_signature IS NULL) AND (issued_envelope IS NULL)))),
    CONSTRAINT ck_trust_access_log_pre_xvii_evidence CHECK (((issuance_state <> 'issued_pre_xvii'::text) OR ((issued_at IS NOT NULL) AND (issuance_attempted_at IS NOT NULL) AND (issued_signing_key_id IS NOT NULL) AND (issued_signature_hash IS NOT NULL) AND (issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (issued_signature IS NOT NULL) AND (octet_length(issued_signature) = 64) AND (envelope_hash IS NOT NULL) AND (known_signature_at IS NULL) AND (issued_attempt_id IS NULL) AND (issued_envelope IS NULL)))),
    CONSTRAINT ck_trust_access_log_refusal_no_evidence CHECK (((event_type <> ALL (ARRAY['refusal'::text, 'scope_denial'::text])) OR (evidence_refs_allowed = false))),
    CONSTRAINT ck_trust_access_log_status CHECK ((status = ANY (ARRAY['success'::text, 'refused'::text, 'degraded'::text, 'replayed'::text]))),
    CONSTRAINT ck_trust_access_log_unknown_state_shape CHECK ((((issuance_state = 'signature_outcome_unknown'::text) AND (issuance_outcome_unknown_at IS NOT NULL)) OR ((issuance_state <> 'signature_outcome_unknown'::text) AND (issuance_outcome_unknown_at IS NULL))))
);

ALTER TABLE ONLY public.trust_access_log FORCE ROW LEVEL SECURITY;


--
-- Name: trust_envelope_issuance_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trust_envelope_issuance_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    access_audit_ref text NOT NULL,
    idempotency_key_hash text NOT NULL,
    subject_type text NOT NULL,
    subject_ref_hash text NOT NULL,
    envelope_hash text NOT NULL,
    semantic_truth_hash text NOT NULL,
    policy_state text NOT NULL,
    audit_ref text NOT NULL,
    audit_hash text NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_trust_issuance_hashes CHECK (((idempotency_key_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (subject_ref_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (envelope_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (semantic_truth_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (audit_hash ~ '^sha256:[0-9a-f]{64}$'::text))),
    CONSTRAINT ck_trust_issuance_status CHECK ((status = 'success'::text))
);

ALTER TABLE ONLY public.trust_envelope_issuance_log FORCE ROW LEVEL SECURITY;


--
-- Name: trust_export_artifact_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trust_export_artifact_attempts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    request_binding_hash text NOT NULL,
    page_start integer NOT NULL,
    attempt_number integer NOT NULL,
    attempt_state text NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    outcome_unknown_at timestamp with time zone,
    issued_at timestamp with time zone,
    artifact_hash text,
    signing_key_id text,
    signature_hash text,
    signature bytea,
    signed_artifact jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_trust_export_artifact_attempt_evidence CHECK ((((attempt_state = 'issued'::text) AND (issued_at IS NOT NULL) AND (artifact_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (signing_key_id IS NOT NULL) AND (signature_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (octet_length(signature) = 64) AND (jsonb_typeof(signed_artifact) = 'object'::text)) OR ((attempt_state = ANY (ARRAY['signing'::text, 'signature_outcome_unknown'::text])) AND (issued_at IS NULL) AND (artifact_hash IS NULL) AND (signing_key_id IS NULL) AND (signature_hash IS NULL) AND (signature IS NULL) AND (signed_artifact IS NULL)))),
    CONSTRAINT ck_trust_export_artifact_attempt_unknown CHECK ((((attempt_state = 'signature_outcome_unknown'::text) AND (outcome_unknown_at IS NOT NULL)) OR ((attempt_state <> 'signature_outcome_unknown'::text) AND (outcome_unknown_at IS NULL)))),
    CONSTRAINT trust_export_artifact_attempts_attempt_number_check CHECK ((attempt_number > 0)),
    CONSTRAINT trust_export_artifact_attempts_attempt_state_check CHECK ((attempt_state = ANY (ARRAY['signing'::text, 'signature_outcome_unknown'::text, 'issued'::text]))),
    CONSTRAINT trust_export_artifact_attempts_page_start_check CHECK ((page_start >= 0)),
    CONSTRAINT trust_export_artifact_attempts_request_binding_hash_check CHECK ((request_binding_hash ~ '^sha256:[0-9a-f]{64}$'::text))
);

ALTER TABLE ONLY public.trust_export_artifact_attempts FORCE ROW LEVEL SECURITY;


--
-- Name: trust_issuance_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trust_issuance_attempts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    audit_ref text NOT NULL,
    attempt_number integer NOT NULL,
    attempt_state text NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    outcome_unknown_at timestamp with time zone,
    signature_known_at timestamp with time zone,
    issued_at timestamp with time zone,
    signing_key_id text,
    signature_hash text,
    signature bytea,
    signed_envelope_hash text,
    signed_envelope jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_trust_issuance_attempt_evidence CHECK ((((attempt_state = ANY (ARRAY['signature_known'::text, 'issued'::text])) AND (signature_known_at IS NOT NULL) AND (signing_key_id IS NOT NULL) AND (signature_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (octet_length(signature) = 64) AND (signed_envelope_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (jsonb_typeof(signed_envelope) = 'object'::text)) OR ((attempt_state = ANY (ARRAY['signing'::text, 'signature_outcome_unknown'::text])) AND (signature_known_at IS NULL) AND (signing_key_id IS NULL) AND (signature_hash IS NULL) AND (signature IS NULL) AND (signed_envelope_hash IS NULL) AND (signed_envelope IS NULL)))),
    CONSTRAINT ck_trust_issuance_attempt_issued CHECK ((((attempt_state = 'issued'::text) AND (issued_at IS NOT NULL)) OR ((attempt_state <> 'issued'::text) AND (issued_at IS NULL)))),
    CONSTRAINT ck_trust_issuance_attempt_unknown CHECK ((((attempt_state = 'signature_outcome_unknown'::text) AND (outcome_unknown_at IS NOT NULL)) OR ((attempt_state <> 'signature_outcome_unknown'::text) AND (outcome_unknown_at IS NULL)))),
    CONSTRAINT trust_issuance_attempts_attempt_number_check CHECK ((attempt_number > 0)),
    CONSTRAINT trust_issuance_attempts_attempt_state_check CHECK ((attempt_state = ANY (ARRAY['signing'::text, 'signature_outcome_unknown'::text, 'signature_known'::text, 'issued'::text])))
);

ALTER TABLE ONLY public.trust_issuance_attempts FORCE ROW LEVEL SECURITY;


--
-- Name: trust_rate_limit_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trust_rate_limit_state (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    agent_client_id uuid NOT NULL,
    window_started_at timestamp with time zone NOT NULL,
    window_ended_at timestamp with time zone NOT NULL,
    request_count integer DEFAULT 0 NOT NULL,
    request_limit integer NOT NULL,
    last_request_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_trust_rate_limit_state_non_negative CHECK (((request_count >= 0) AND (request_limit > 0)))
);

ALTER TABLE ONLY public.trust_rate_limit_state FORCE ROW LEVEL SECURITY;


--
-- Name: trust_replay_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trust_replay_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    request_identity_hash text NOT NULL,
    idempotency_key_hash text NOT NULL,
    original_audit_ref text NOT NULL,
    replay_status text NOT NULL,
    audit_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_trust_replay_hashes CHECK (((request_identity_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (idempotency_key_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (audit_hash ~ '^sha256:[0-9a-f]{64}$'::text))),
    CONSTRAINT ck_trust_replay_status CHECK ((replay_status = 'idempotent_replay'::text))
);

ALTER TABLE ONLY public.trust_replay_events FORCE ROW LEVEL SECURITY;


--
-- Name: trust_request_nonces; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trust_request_nonces (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    agent_client_id uuid NOT NULL,
    nonce_value text NOT NULL,
    request_identity_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    CONSTRAINT ck_trust_request_nonces_hashes CHECK ((request_identity_hash ~ '^sha256:[0-9a-f]{64}$'::text)),
    CONSTRAINT ck_trust_request_nonces_nonce_not_empty CHECK ((length(btrim(nonce_value)) > 0))
);

ALTER TABLE ONLY public.trust_request_nonces FORCE ROW LEVEL SECURITY;


--
-- Name: trust_scope_denial_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trust_scope_denial_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    request_identity_hash text NOT NULL,
    idempotency_key_hash text NOT NULL,
    subject_type text NOT NULL,
    subject_ref_hash text,
    status text NOT NULL,
    reason_code text NOT NULL,
    evidence_refs_leaked boolean DEFAULT false NOT NULL,
    audit_ref text NOT NULL,
    audit_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_trust_scope_denial_hashes CHECK (((request_identity_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (idempotency_key_hash ~ '^sha256:[0-9a-f]{64}$'::text) AND (audit_hash ~ '^sha256:[0-9a-f]{64}$'::text))),
    CONSTRAINT ck_trust_scope_denial_no_evidence_leak CHECK (((evidence_refs_leaked = false) AND (subject_ref_hash IS NULL))),
    CONSTRAINT ck_trust_scope_denial_reason CHECK ((reason_code = ANY (ARRAY['scope_denied'::text, 'tenant_mismatch'::text]))),
    CONSTRAINT ck_trust_scope_denial_status CHECK ((status = 'refused'::text))
);

ALTER TABLE ONLY public.trust_scope_denial_events FORCE ROW LEVEL SECURITY;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    login_identifier_hash text NOT NULL,
    external_subject_hash text,
    auth_provider text DEFAULT 'password'::text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    password_hash text,
    CONSTRAINT ck_users_auth_provider_valid CHECK ((auth_provider = ANY (ARRAY['password'::text, 'oauth_google'::text, 'oauth_microsoft'::text, 'oauth_github'::text, 'sso'::text]))),
    CONSTRAINT ck_users_login_identifier_hash_not_empty CHECK ((length(TRIM(BOTH FROM login_identifier_hash)) > 0))
);

ALTER TABLE ONLY public.users FORCE ROW LEVEL SECURITY;


--
-- Name: webhook_ingress_identities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.webhook_ingress_identities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    event_id uuid NOT NULL,
    provider character varying(32) NOT NULL,
    provider_native_event_reference character varying(255) NOT NULL,
    provider_native_commerce_reference character varying(255) NOT NULL,
    normalized_commerce_reference_kind character varying(64) NOT NULL,
    normalized_commerce_reference_value character varying(255) NOT NULL,
    verified_amount_minor integer NOT NULL,
    verified_amount_currency character(3) NOT NULL,
    verified_amount_scale integer DEFAULT 2 NOT NULL,
    event_timestamp timestamp with time zone NOT NULL,
    idempotency_key character varying(255) NOT NULL,
    verified_commerce_ingress_state character varying(64) NOT NULL,
    verified_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_webhook_ingress_amount_minor_non_negative CHECK ((verified_amount_minor >= 0)),
    CONSTRAINT ck_webhook_ingress_amount_scale_non_negative CHECK ((verified_amount_scale >= 0))
);

ALTER TABLE ONLY public.webhook_ingress_identities FORCE ROW LEVEL SECURITY;


--
-- Name: worker_failed_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.worker_failed_jobs (
    id uuid NOT NULL,
    task_id character varying(155) NOT NULL,
    task_name character varying(255) NOT NULL,
    queue character varying(100),
    worker character varying(255),
    task_args jsonb,
    task_kwargs jsonb,
    tenant_id uuid,
    error_type character varying(100) NOT NULL,
    exception_class character varying(255) NOT NULL,
    error_message text NOT NULL,
    traceback text,
    retry_count integer DEFAULT 0 NOT NULL,
    last_retry_at timestamp with time zone,
    status character varying(50) DEFAULT '''pending'''::character varying NOT NULL,
    remediation_notes text,
    resolved_at timestamp with time zone,
    correlation_id uuid,
    failed_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_worker_failed_jobs_retry_count_positive CHECK ((retry_count >= 0)),
    CONSTRAINT ck_worker_failed_jobs_status_valid CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'in_progress'::character varying, 'resolved'::character varying, 'abandoned'::character varying])::text[])))
);

ALTER TABLE ONLY public.worker_failed_jobs FORCE ROW LEVEL SECURITY;


--
-- Name: worker_side_effects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.worker_side_effects (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    task_id text NOT NULL,
    correlation_id uuid,
    effect_key text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.worker_side_effects FORCE ROW LEVEL SECURITY;


--
-- Name: bayesian_artifacts_p00; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p00 FOR VALUES WITH (modulus 16, remainder 0);


--
-- Name: bayesian_artifacts_p01; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p01 FOR VALUES WITH (modulus 16, remainder 1);


--
-- Name: bayesian_artifacts_p02; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p02 FOR VALUES WITH (modulus 16, remainder 2);


--
-- Name: bayesian_artifacts_p03; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p03 FOR VALUES WITH (modulus 16, remainder 3);


--
-- Name: bayesian_artifacts_p04; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p04 FOR VALUES WITH (modulus 16, remainder 4);


--
-- Name: bayesian_artifacts_p05; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p05 FOR VALUES WITH (modulus 16, remainder 5);


--
-- Name: bayesian_artifacts_p06; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p06 FOR VALUES WITH (modulus 16, remainder 6);


--
-- Name: bayesian_artifacts_p07; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p07 FOR VALUES WITH (modulus 16, remainder 7);


--
-- Name: bayesian_artifacts_p08; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p08 FOR VALUES WITH (modulus 16, remainder 8);


--
-- Name: bayesian_artifacts_p09; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p09 FOR VALUES WITH (modulus 16, remainder 9);


--
-- Name: bayesian_artifacts_p10; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p10 FOR VALUES WITH (modulus 16, remainder 10);


--
-- Name: bayesian_artifacts_p11; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p11 FOR VALUES WITH (modulus 16, remainder 11);


--
-- Name: bayesian_artifacts_p12; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p12 FOR VALUES WITH (modulus 16, remainder 12);


--
-- Name: bayesian_artifacts_p13; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p13 FOR VALUES WITH (modulus 16, remainder 13);


--
-- Name: bayesian_artifacts_p14; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p14 FOR VALUES WITH (modulus 16, remainder 14);


--
-- Name: bayesian_artifacts_p15; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts ATTACH PARTITION public.bayesian_artifacts_p15 FOR VALUES WITH (modulus 16, remainder 15);


--
-- Name: bayesian_model_fits_p00; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p00 FOR VALUES WITH (modulus 16, remainder 0);


--
-- Name: bayesian_model_fits_p01; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p01 FOR VALUES WITH (modulus 16, remainder 1);


--
-- Name: bayesian_model_fits_p02; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p02 FOR VALUES WITH (modulus 16, remainder 2);


--
-- Name: bayesian_model_fits_p03; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p03 FOR VALUES WITH (modulus 16, remainder 3);


--
-- Name: bayesian_model_fits_p04; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p04 FOR VALUES WITH (modulus 16, remainder 4);


--
-- Name: bayesian_model_fits_p05; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p05 FOR VALUES WITH (modulus 16, remainder 5);


--
-- Name: bayesian_model_fits_p06; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p06 FOR VALUES WITH (modulus 16, remainder 6);


--
-- Name: bayesian_model_fits_p07; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p07 FOR VALUES WITH (modulus 16, remainder 7);


--
-- Name: bayesian_model_fits_p08; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p08 FOR VALUES WITH (modulus 16, remainder 8);


--
-- Name: bayesian_model_fits_p09; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p09 FOR VALUES WITH (modulus 16, remainder 9);


--
-- Name: bayesian_model_fits_p10; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p10 FOR VALUES WITH (modulus 16, remainder 10);


--
-- Name: bayesian_model_fits_p11; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p11 FOR VALUES WITH (modulus 16, remainder 11);


--
-- Name: bayesian_model_fits_p12; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p12 FOR VALUES WITH (modulus 16, remainder 12);


--
-- Name: bayesian_model_fits_p13; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p13 FOR VALUES WITH (modulus 16, remainder 13);


--
-- Name: bayesian_model_fits_p14; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p14 FOR VALUES WITH (modulus 16, remainder 14);


--
-- Name: bayesian_model_fits_p15; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits ATTACH PARTITION public.bayesian_model_fits_p15 FOR VALUES WITH (modulus 16, remainder 15);


--
-- Name: celery_taskmeta id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.celery_taskmeta ALTER COLUMN id SET DEFAULT nextval('public.task_id_sequence'::regclass);


--
-- Name: celery_tasksetmeta id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.celery_tasksetmeta ALTER COLUMN id SET DEFAULT nextval('public.taskset_id_sequence'::regclass);


--
-- Name: kombu_message id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kombu_message ALTER COLUMN id SET DEFAULT nextval('public.message_id_sequence'::regclass);


--
-- Name: kombu_queue id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kombu_queue ALTER COLUMN id SET DEFAULT nextval('public.queue_id_sequence'::regclass);


--
-- Name: pii_audit_findings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pii_audit_findings ALTER COLUMN id SET DEFAULT nextval('public.pii_audit_findings_id_seq'::regclass);


--
-- Name: agent_clients agent_clients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_clients
    ADD CONSTRAINT agent_clients_pkey PRIMARY KEY (id);


--
-- Name: agent_scope_grants agent_scope_grants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_scope_grants
    ADD CONSTRAINT agent_scope_grants_pkey PRIMARY KEY (id);


--
-- Name: agent_service_credentials agent_service_credentials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_service_credentials
    ADD CONSTRAINT agent_service_credentials_pkey PRIMARY KEY (id);


--
-- Name: agent_token_revocations agent_token_revocations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_token_revocations
    ADD CONSTRAINT agent_token_revocations_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: attribution_allocations attribution_allocations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_allocations
    ADD CONSTRAINT attribution_allocations_pkey PRIMARY KEY (id);


--
-- Name: attribution_commerce_identities attribution_commerce_identities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_commerce_identities
    ADD CONSTRAINT attribution_commerce_identities_pkey PRIMARY KEY (id);


--
-- Name: attribution_events attribution_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_events
    ADD CONSTRAINT attribution_events_pkey PRIMARY KEY (id);


--
-- Name: attribution_recompute_jobs attribution_recompute_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_recompute_jobs
    ADD CONSTRAINT attribution_recompute_jobs_pkey PRIMARY KEY (id);


--
-- Name: auth_refresh_tokens auth_refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_refresh_tokens
    ADD CONSTRAINT auth_refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: b23_exception_records b23_exception_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_exception_records
    ADD CONSTRAINT b23_exception_records_pkey PRIMARY KEY (id);


--
-- Name: b23_match_task_dispatches b23_match_task_dispatches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_match_task_dispatches
    ADD CONSTRAINT b23_match_task_dispatches_pkey PRIMARY KEY (id);


--
-- Name: b23_match_verdicts b23_match_verdicts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_match_verdicts
    ADD CONSTRAINT b23_match_verdicts_pkey PRIMARY KEY (id);


--
-- Name: b23_revenue_events b23_revenue_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_revenue_events
    ADD CONSTRAINT b23_revenue_events_pkey PRIMARY KEY (id);


--
-- Name: b23_webhook_ingestion_logs b23_webhook_ingestion_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_webhook_ingestion_logs
    ADD CONSTRAINT b23_webhook_ingestion_logs_pkey PRIMARY KEY (id);


--
-- Name: b24_active_execution_leases b24_active_execution_leases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_active_execution_leases
    ADD CONSTRAINT b24_active_execution_leases_pkey PRIMARY KEY (tenant_id, model_type, model_version, source_window_start, source_window_end);


--
-- Name: b24_dirty_events b24_dirty_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_dirty_events
    ADD CONSTRAINT b24_dirty_events_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: b24_feature_authority_build_outbox b24_feature_authority_build_outbox_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_feature_authority_build_outbox
    ADD CONSTRAINT b24_feature_authority_build_outbox_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: b24_feature_authority_build_requests b24_feature_authority_build_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_feature_authority_build_requests
    ADD CONSTRAINT b24_feature_authority_build_requests_pkey PRIMARY KEY (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: b24_fit_dispatch_outbox b24_fit_dispatch_outbox_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_fit_dispatch_outbox
    ADD CONSTRAINT b24_fit_dispatch_outbox_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: b24_fit_planner_wakeups b24_fit_planner_wakeups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_fit_planner_wakeups
    ADD CONSTRAINT b24_fit_planner_wakeups_pkey PRIMARY KEY (tenant_id);


--
-- Name: b24_fit_policy_replan_lineage b24_fit_policy_replan_lineage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_fit_policy_replan_lineage
    ADD CONSTRAINT b24_fit_policy_replan_lineage_pkey PRIMARY KEY (tenant_id, fit_id, transition_sequence);


--
-- Name: b24_fit_recovery_outbox b24_fit_recovery_outbox_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_fit_recovery_outbox
    ADD CONSTRAINT b24_fit_recovery_outbox_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: b24_inference_policy_registry b24_inference_policy_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_inference_policy_registry
    ADD CONSTRAINT b24_inference_policy_registry_pkey PRIMARY KEY (policy_bundle_hash);


--
-- Name: b24_source_window_feature_authority b24_source_window_feature_authority_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_source_window_feature_authority
    ADD CONSTRAINT b24_source_window_feature_authority_pkey PRIMARY KEY (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: b24_worker_process_authority b24_worker_process_authority_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_worker_process_authority
    ADD CONSTRAINT b24_worker_process_authority_pkey PRIMARY KEY (generation_id, pid);


--
-- Name: b27_explanation_materializations b27_explanation_materializations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b27_explanation_materializations
    ADD CONSTRAINT b27_explanation_materializations_pkey PRIMARY KEY (id);


--
-- Name: b27_narrative_template_registry b27_narrative_template_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b27_narrative_template_registry
    ADD CONSTRAINT b27_narrative_template_registry_pkey PRIMARY KEY (registry_version);


--
-- Name: b27_narrative_templates b27_narrative_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b27_narrative_templates
    ADD CONSTRAINT b27_narrative_templates_pkey PRIMARY KEY (template_id);


--
-- Name: b28_proposals b28_proposals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b28_proposals
    ADD CONSTRAINT b28_proposals_pkey PRIMARY KEY (id);


--
-- Name: b28_simulation_requests b28_simulation_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b28_simulation_requests
    ADD CONSTRAINT b28_simulation_requests_pkey PRIMARY KEY (id);


--
-- Name: b28_simulation_results b28_simulation_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b28_simulation_results
    ADD CONSTRAINT b28_simulation_results_pkey PRIMARY KEY (id);


--
-- Name: bayesian_artifact_storage_quotas bayesian_artifact_storage_quotas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifact_storage_quotas
    ADD CONSTRAINT bayesian_artifact_storage_quotas_pkey PRIMARY KEY (tenant_id);


--
-- Name: bayesian_artifacts bayesian_artifacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts
    ADD CONSTRAINT bayesian_artifacts_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p00 bayesian_artifacts_p00_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p00
    ADD CONSTRAINT bayesian_artifacts_p00_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts uq_bayesian_artifacts_tenant_artifact_ref; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts
    ADD CONSTRAINT uq_bayesian_artifacts_tenant_artifact_ref UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p00 bayesian_artifacts_p00_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p00
    ADD CONSTRAINT bayesian_artifacts_p00_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p01 bayesian_artifacts_p01_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p01
    ADD CONSTRAINT bayesian_artifacts_p01_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p01 bayesian_artifacts_p01_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p01
    ADD CONSTRAINT bayesian_artifacts_p01_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p02 bayesian_artifacts_p02_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p02
    ADD CONSTRAINT bayesian_artifacts_p02_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p02 bayesian_artifacts_p02_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p02
    ADD CONSTRAINT bayesian_artifacts_p02_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p03 bayesian_artifacts_p03_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p03
    ADD CONSTRAINT bayesian_artifacts_p03_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p03 bayesian_artifacts_p03_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p03
    ADD CONSTRAINT bayesian_artifacts_p03_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p04 bayesian_artifacts_p04_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p04
    ADD CONSTRAINT bayesian_artifacts_p04_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p04 bayesian_artifacts_p04_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p04
    ADD CONSTRAINT bayesian_artifacts_p04_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p05 bayesian_artifacts_p05_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p05
    ADD CONSTRAINT bayesian_artifacts_p05_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p05 bayesian_artifacts_p05_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p05
    ADD CONSTRAINT bayesian_artifacts_p05_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p06 bayesian_artifacts_p06_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p06
    ADD CONSTRAINT bayesian_artifacts_p06_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p06 bayesian_artifacts_p06_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p06
    ADD CONSTRAINT bayesian_artifacts_p06_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p07 bayesian_artifacts_p07_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p07
    ADD CONSTRAINT bayesian_artifacts_p07_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p07 bayesian_artifacts_p07_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p07
    ADD CONSTRAINT bayesian_artifacts_p07_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p08 bayesian_artifacts_p08_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p08
    ADD CONSTRAINT bayesian_artifacts_p08_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p08 bayesian_artifacts_p08_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p08
    ADD CONSTRAINT bayesian_artifacts_p08_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p09 bayesian_artifacts_p09_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p09
    ADD CONSTRAINT bayesian_artifacts_p09_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p09 bayesian_artifacts_p09_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p09
    ADD CONSTRAINT bayesian_artifacts_p09_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p10 bayesian_artifacts_p10_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p10
    ADD CONSTRAINT bayesian_artifacts_p10_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p10 bayesian_artifacts_p10_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p10
    ADD CONSTRAINT bayesian_artifacts_p10_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p11 bayesian_artifacts_p11_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p11
    ADD CONSTRAINT bayesian_artifacts_p11_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p11 bayesian_artifacts_p11_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p11
    ADD CONSTRAINT bayesian_artifacts_p11_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p12 bayesian_artifacts_p12_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p12
    ADD CONSTRAINT bayesian_artifacts_p12_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p12 bayesian_artifacts_p12_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p12
    ADD CONSTRAINT bayesian_artifacts_p12_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p13 bayesian_artifacts_p13_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p13
    ADD CONSTRAINT bayesian_artifacts_p13_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p13 bayesian_artifacts_p13_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p13
    ADD CONSTRAINT bayesian_artifacts_p13_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p14 bayesian_artifacts_p14_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p14
    ADD CONSTRAINT bayesian_artifacts_p14_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p14 bayesian_artifacts_p14_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p14
    ADD CONSTRAINT bayesian_artifacts_p14_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p15 bayesian_artifacts_p15_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p15
    ADD CONSTRAINT bayesian_artifacts_p15_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_artifacts_p15 bayesian_artifacts_p15_tenant_id_artifact_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifacts_p15
    ADD CONSTRAINT bayesian_artifacts_p15_tenant_id_artifact_ref_key UNIQUE (tenant_id, artifact_ref);


--
-- Name: bayesian_model_fits bayesian_model_fits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits
    ADD CONSTRAINT bayesian_model_fits_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p00 bayesian_model_fits_p00_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p00
    ADD CONSTRAINT bayesian_model_fits_p00_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits uq_bayesian_model_fits_tenant_model_window_snapshot; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits
    ADD CONSTRAINT uq_bayesian_model_fits_tenant_model_window_snapshot UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p00 bayesian_model_fits_p00_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p00
    ADD CONSTRAINT bayesian_model_fits_p00_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p01 bayesian_model_fits_p01_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p01
    ADD CONSTRAINT bayesian_model_fits_p01_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p01 bayesian_model_fits_p01_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p01
    ADD CONSTRAINT bayesian_model_fits_p01_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p02 bayesian_model_fits_p02_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p02
    ADD CONSTRAINT bayesian_model_fits_p02_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p02 bayesian_model_fits_p02_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p02
    ADD CONSTRAINT bayesian_model_fits_p02_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p03 bayesian_model_fits_p03_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p03
    ADD CONSTRAINT bayesian_model_fits_p03_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p03 bayesian_model_fits_p03_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p03
    ADD CONSTRAINT bayesian_model_fits_p03_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p04 bayesian_model_fits_p04_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p04
    ADD CONSTRAINT bayesian_model_fits_p04_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p04 bayesian_model_fits_p04_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p04
    ADD CONSTRAINT bayesian_model_fits_p04_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p05 bayesian_model_fits_p05_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p05
    ADD CONSTRAINT bayesian_model_fits_p05_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p05 bayesian_model_fits_p05_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p05
    ADD CONSTRAINT bayesian_model_fits_p05_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p06 bayesian_model_fits_p06_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p06
    ADD CONSTRAINT bayesian_model_fits_p06_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p06 bayesian_model_fits_p06_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p06
    ADD CONSTRAINT bayesian_model_fits_p06_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p07 bayesian_model_fits_p07_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p07
    ADD CONSTRAINT bayesian_model_fits_p07_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p07 bayesian_model_fits_p07_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p07
    ADD CONSTRAINT bayesian_model_fits_p07_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p08 bayesian_model_fits_p08_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p08
    ADD CONSTRAINT bayesian_model_fits_p08_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p08 bayesian_model_fits_p08_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p08
    ADD CONSTRAINT bayesian_model_fits_p08_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p09 bayesian_model_fits_p09_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p09
    ADD CONSTRAINT bayesian_model_fits_p09_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p09 bayesian_model_fits_p09_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p09
    ADD CONSTRAINT bayesian_model_fits_p09_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p10 bayesian_model_fits_p10_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p10
    ADD CONSTRAINT bayesian_model_fits_p10_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p10 bayesian_model_fits_p10_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p10
    ADD CONSTRAINT bayesian_model_fits_p10_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p11 bayesian_model_fits_p11_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p11
    ADD CONSTRAINT bayesian_model_fits_p11_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p11 bayesian_model_fits_p11_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p11
    ADD CONSTRAINT bayesian_model_fits_p11_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p12 bayesian_model_fits_p12_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p12
    ADD CONSTRAINT bayesian_model_fits_p12_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p12 bayesian_model_fits_p12_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p12
    ADD CONSTRAINT bayesian_model_fits_p12_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p13 bayesian_model_fits_p13_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p13
    ADD CONSTRAINT bayesian_model_fits_p13_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p13 bayesian_model_fits_p13_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p13
    ADD CONSTRAINT bayesian_model_fits_p13_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p14 bayesian_model_fits_p14_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p14
    ADD CONSTRAINT bayesian_model_fits_p14_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p14 bayesian_model_fits_p14_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p14
    ADD CONSTRAINT bayesian_model_fits_p14_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p15 bayesian_model_fits_p15_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p15
    ADD CONSTRAINT bayesian_model_fits_p15_pkey PRIMARY KEY (tenant_id, id);


--
-- Name: bayesian_model_fits_p15 bayesian_model_fits_p15_tenant_id_model_type_model_version__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_model_fits_p15
    ADD CONSTRAINT bayesian_model_fits_p15_tenant_id_model_type_model_version__key UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: budget_jobs budget_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.budget_jobs
    ADD CONSTRAINT budget_jobs_pkey PRIMARY KEY (id);


--
-- Name: budget_optimization_jobs budget_optimization_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.budget_optimization_jobs
    ADD CONSTRAINT budget_optimization_jobs_pkey PRIMARY KEY (id);


--
-- Name: worker_failed_jobs celery_task_failures_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.worker_failed_jobs
    ADD CONSTRAINT celery_task_failures_pkey PRIMARY KEY (id);


--
-- Name: celery_taskmeta celery_taskmeta_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.celery_taskmeta
    ADD CONSTRAINT celery_taskmeta_pkey PRIMARY KEY (id);


--
-- Name: celery_taskmeta celery_taskmeta_task_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.celery_taskmeta
    ADD CONSTRAINT celery_taskmeta_task_id_key UNIQUE (task_id);


--
-- Name: celery_tasksetmeta celery_tasksetmeta_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.celery_tasksetmeta
    ADD CONSTRAINT celery_tasksetmeta_pkey PRIMARY KEY (id);


--
-- Name: celery_tasksetmeta celery_tasksetmeta_taskset_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.celery_tasksetmeta
    ADD CONSTRAINT celery_tasksetmeta_taskset_id_key UNIQUE (taskset_id);


--
-- Name: channel_assignment_corrections channel_assignment_corrections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_assignment_corrections
    ADD CONSTRAINT channel_assignment_corrections_pkey PRIMARY KEY (id);


--
-- Name: channel_state_transitions channel_state_transitions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_state_transitions
    ADD CONSTRAINT channel_state_transitions_pkey PRIMARY KEY (id);


--
-- Name: channel_taxonomy channel_taxonomy_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_taxonomy
    ADD CONSTRAINT channel_taxonomy_pkey PRIMARY KEY (code);


--
-- Name: b23_match_verdicts ck_b23_match_verdicts_matched_requires_attribution_event; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.b23_match_verdicts
    ADD CONSTRAINT ck_b23_match_verdicts_matched_requires_attribution_event CHECK ((((status)::text <> ALL ((ARRAY['matched_provisional'::character varying, 'matched_confirmed'::character varying, 'adjusted'::character varying])::text[])) OR (attribution_event_id IS NOT NULL))) NOT VALID;


--
-- Name: bayesian_model_fits ck_bayesian_model_fits_available_confidence_complete; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits
    ADD CONSTRAINT ck_bayesian_model_fits_available_confidence_complete CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text <> ALL ((ARRAY['low'::character varying, 'medium'::character varying, 'high'::character varying])::text[])) OR (((status)::text = 'succeeded'::text) AND ((data_completeness_status)::text = 'complete'::text) AND (fallback_applied = false) AND ((diagnostic_status)::text = 'passed'::text) AND ((credible_interval_status)::text = 'available'::text) AND (artifact_ref IS NOT NULL) AND (artifact_hash IS NOT NULL) AND (confidence_evidence_snapshot_hash IS NOT NULL) AND ((confidence_evidence_snapshot_hash)::text = (source_snapshot_hash)::text) AND (confidence_deterministic_revenue_minor IS NOT NULL) AND (confidence_deterministic_row_count IS NOT NULL) AND (confidence_match_verdict_count IS NOT NULL) AND (confidence_currency_count IS NOT NULL) AND (confidence_currency_count <= 1) AND (confidence_classified_at IS NOT NULL) AND (confidence_classified_at >= source_read_completed_at) AND (source_read_started_at IS NOT NULL) AND (source_read_completed_at IS NOT NULL) AND (source_read_completed_at >= source_read_started_at) AND (confidence_bucket_reason IS NOT NULL) AND ((((confidence_bucket)::text = 'high'::text) AND ((confidence_bucket_reason)::text = 'narrow_interval'::text)) OR (((confidence_bucket)::text = 'medium'::text) AND ((confidence_bucket_reason)::text = 'moderate_interval'::text)) OR (((confidence_bucket)::text = 'low'::text) AND ((confidence_bucket_reason)::text = 'wide_interval'::text)))))) NOT VALID;


--
-- Name: bayesian_model_fits ck_bayesian_model_fits_available_policy_bundle; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits
    ADD CONSTRAINT ck_bayesian_model_fits_available_policy_bundle CHECK (((confidence_bucket IS NULL) OR ((confidence_bucket)::text <> ALL (ARRAY['low'::text, 'medium'::text, 'high'::text])) OR ((inference_profile_version IS NOT NULL) AND (runtime_policy_version IS NOT NULL) AND (sampling_policy_version IS NOT NULL) AND (diagnostic_policy_version IS NOT NULL) AND (policy_bundle_hash IS NOT NULL) AND (char_length((policy_bundle_hash)::text) = 64) AND (authorized_chains IS NOT NULL) AND (authorized_posterior_draws_total IS NOT NULL) AND (n_chains IS NOT NULL) AND (n_samples_actual IS NOT NULL) AND (n_chains = authorized_chains) AND (n_samples_actual = authorized_posterior_draws_total)))) NOT VALID;


--
-- Name: bayesian_model_fits ck_bayesian_model_fits_confidence_classification_state; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits
    ADD CONSTRAINT ck_bayesian_model_fits_confidence_classification_state CHECK ((((confidence_bucket IS NULL) AND (confidence_bucket_reason IS NULL) AND (confidence_policy_version IS NULL) AND (confidence_semantics_version IS NULL) AND (confidence_classified_at IS NULL)) OR ((confidence_bucket IS NOT NULL) AND (confidence_bucket_reason IS NOT NULL) AND ((confidence_policy_version)::text = 'b24-p10-confidence-policy-v1'::text) AND ((confidence_semantics_version)::text = 'b24-p10-confidence-semantics-v1'::text) AND (confidence_classified_at IS NOT NULL)))) NOT VALID;


--
-- Name: bayesian_model_fits ck_bayesian_model_fits_confidence_evidence_hash_sha256; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits
    ADD CONSTRAINT ck_bayesian_model_fits_confidence_evidence_hash_sha256 CHECK (((confidence_evidence_snapshot_hash IS NULL) OR ((confidence_evidence_snapshot_hash)::text ~ '^[a-f0-9]{64}$'::text))) NOT VALID;


--
-- Name: bayesian_model_fits ck_bayesian_model_fits_confidence_evidence_tuple; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits
    ADD CONSTRAINT ck_bayesian_model_fits_confidence_evidence_tuple CHECK ((((confidence_evidence_snapshot_hash IS NULL) AND (confidence_deterministic_revenue_minor IS NULL) AND (confidence_deterministic_row_count IS NULL) AND (confidence_match_verdict_count IS NULL) AND (confidence_currency_count IS NULL)) OR ((confidence_evidence_snapshot_hash IS NOT NULL) AND (confidence_deterministic_revenue_minor IS NOT NULL) AND (confidence_deterministic_row_count IS NOT NULL) AND (confidence_match_verdict_count IS NOT NULL) AND (confidence_currency_count IS NOT NULL) AND ((confidence_evidence_snapshot_hash)::text = (source_snapshot_hash)::text)))) NOT VALID;


--
-- Name: bayesian_model_fits ck_bayesian_model_fits_policy_replan_evidence; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits
    ADD CONSTRAINT ck_bayesian_model_fits_policy_replan_evidence CHECK ((((policy_replan_count = 0) AND (superseded_policy_bundle_hash IS NULL) AND (policy_replanned_at IS NULL)) OR ((policy_replan_count > 0) AND (superseded_policy_bundle_hash IS NOT NULL) AND (char_length((superseded_policy_bundle_hash)::text) = 64) AND (policy_replanned_at IS NOT NULL)))) NOT VALID;


--
-- Name: bayesian_model_fits ck_bayesian_model_fits_source_read_pair_order; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits
    ADD CONSTRAINT ck_bayesian_model_fits_source_read_pair_order CHECK ((((source_read_started_at IS NULL) AND (source_read_completed_at IS NULL)) OR ((source_read_started_at IS NOT NULL) AND (source_read_completed_at IS NOT NULL) AND (source_read_completed_at >= source_read_started_at)))) NOT VALID;


--
-- Name: compliance_audit_ledger compliance_audit_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compliance_audit_ledger
    ADD CONSTRAINT compliance_audit_ledger_pkey PRIMARY KEY (id);


--
-- Name: dead_events dead_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dead_events
    ADD CONSTRAINT dead_events_pkey PRIMARY KEY (id);


--
-- Name: dead_events_quarantine dead_events_quarantine_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dead_events_quarantine
    ADD CONSTRAINT dead_events_quarantine_pkey PRIMARY KEY (id);


--
-- Name: ephemeral_click_resolution ephemeral_click_resolution_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ephemeral_click_resolution
    ADD CONSTRAINT ephemeral_click_resolution_pkey PRIMARY KEY (id);


--
-- Name: ephemeral_order_resolution ephemeral_order_resolution_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ephemeral_order_resolution
    ADD CONSTRAINT ephemeral_order_resolution_pkey PRIMARY KEY (id);


--
-- Name: explanation_cache explanation_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explanation_cache
    ADD CONSTRAINT explanation_cache_pkey PRIMARY KEY (id);


--
-- Name: explanation_cache explanation_cache_tenant_id_entity_type_entity_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explanation_cache
    ADD CONSTRAINT explanation_cache_tenant_id_entity_type_entity_id_key UNIQUE (tenant_id, entity_type, entity_id);


--
-- Name: investigation_jobs investigation_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigation_jobs
    ADD CONSTRAINT investigation_jobs_pkey PRIMARY KEY (id);


--
-- Name: investigation_tool_calls investigation_tool_calls_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigation_tool_calls
    ADD CONSTRAINT investigation_tool_calls_pkey PRIMARY KEY (id);


--
-- Name: investigations investigations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT investigations_pkey PRIMARY KEY (id);


--
-- Name: jwt_verification_cache jwt_verification_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jwt_verification_cache
    ADD CONSTRAINT jwt_verification_cache_pkey PRIMARY KEY (singleton_id);


--
-- Name: kombu_message kombu_message_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kombu_message
    ADD CONSTRAINT kombu_message_pkey PRIMARY KEY (id);


--
-- Name: kombu_queue kombu_queue_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kombu_queue
    ADD CONSTRAINT kombu_queue_name_key UNIQUE (name);


--
-- Name: kombu_queue kombu_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kombu_queue
    ADD CONSTRAINT kombu_queue_pkey PRIMARY KEY (id);


--
-- Name: llm_api_calls llm_api_calls_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_api_calls
    ADD CONSTRAINT llm_api_calls_pkey PRIMARY KEY (id);


--
-- Name: llm_breaker_state llm_breaker_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_breaker_state
    ADD CONSTRAINT llm_breaker_state_pkey PRIMARY KEY (id);


--
-- Name: llm_breaker_state llm_breaker_state_tenant_id_user_id_breaker_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_breaker_state
    ADD CONSTRAINT llm_breaker_state_tenant_id_user_id_breaker_key_key UNIQUE (tenant_id, user_id, breaker_key);


--
-- Name: llm_budget_reservations llm_budget_reservations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_budget_reservations
    ADD CONSTRAINT llm_budget_reservations_pkey PRIMARY KEY (id);


--
-- Name: llm_budget_reservations llm_budget_reservations_tenant_id_user_id_endpoint_request__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_budget_reservations
    ADD CONSTRAINT llm_budget_reservations_tenant_id_user_id_endpoint_request__key UNIQUE (tenant_id, user_id, endpoint, request_id);


--
-- Name: llm_call_audit llm_call_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_call_audit
    ADD CONSTRAINT llm_call_audit_pkey PRIMARY KEY (id);


--
-- Name: llm_hourly_shutoff_state llm_hourly_shutoff_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_hourly_shutoff_state
    ADD CONSTRAINT llm_hourly_shutoff_state_pkey PRIMARY KEY (id);


--
-- Name: llm_hourly_shutoff_state llm_hourly_shutoff_state_tenant_id_user_id_hour_start_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_hourly_shutoff_state
    ADD CONSTRAINT llm_hourly_shutoff_state_tenant_id_user_id_hour_start_key UNIQUE (tenant_id, user_id, hour_start);


--
-- Name: llm_monthly_budget_state llm_monthly_budget_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monthly_budget_state
    ADD CONSTRAINT llm_monthly_budget_state_pkey PRIMARY KEY (id);


--
-- Name: llm_monthly_budget_state llm_monthly_budget_state_tenant_id_user_id_month_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monthly_budget_state
    ADD CONSTRAINT llm_monthly_budget_state_tenant_id_user_id_month_key UNIQUE (tenant_id, user_id, month);


--
-- Name: llm_monthly_costs llm_monthly_costs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monthly_costs
    ADD CONSTRAINT llm_monthly_costs_pkey PRIMARY KEY (id);


--
-- Name: llm_semantic_cache llm_semantic_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_semantic_cache
    ADD CONSTRAINT llm_semantic_cache_pkey PRIMARY KEY (id);


--
-- Name: llm_semantic_cache llm_semantic_cache_tenant_id_user_id_endpoint_cache_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_semantic_cache
    ADD CONSTRAINT llm_semantic_cache_tenant_id_user_id_endpoint_cache_key_key UNIQUE (tenant_id, user_id, endpoint, cache_key);


--
-- Name: llm_validation_failures llm_validation_failures_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_validation_failures
    ADD CONSTRAINT llm_validation_failures_pkey PRIMARY KEY (id);


--
-- Name: oauth_handshake_sessions oauth_handshake_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_handshake_sessions
    ADD CONSTRAINT oauth_handshake_sessions_pkey PRIMARY KEY (id);


--
-- Name: pii_audit_findings pii_audit_findings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pii_audit_findings
    ADD CONSTRAINT pii_audit_findings_pkey PRIMARY KEY (id);


--
-- Name: auth_access_token_denylist pk_auth_access_token_denylist; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_access_token_denylist
    ADD CONSTRAINT pk_auth_access_token_denylist PRIMARY KEY (tenant_id, user_id, jti);


--
-- Name: auth_user_token_cutoffs pk_auth_user_token_cutoffs; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_token_cutoffs
    ADD CONSTRAINT pk_auth_user_token_cutoffs PRIMARY KEY (tenant_id, user_id);


--
-- Name: platform_connections platform_connections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_connections
    ADD CONSTRAINT platform_connections_pkey PRIMARY KEY (id);


--
-- Name: platform_credentials platform_credentials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_credentials
    ADD CONSTRAINT platform_credentials_pkey PRIMARY KEY (id);


--
-- Name: r4_crash_barriers r4_crash_barriers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.r4_crash_barriers
    ADD CONSTRAINT r4_crash_barriers_pkey PRIMARY KEY (id);


--
-- Name: r4_recovery_exclusions r4_recovery_exclusions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.r4_recovery_exclusions
    ADD CONSTRAINT r4_recovery_exclusions_pkey PRIMARY KEY (scenario, task_id);


--
-- Name: r4_task_attempts r4_task_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.r4_task_attempts
    ADD CONSTRAINT r4_task_attempts_pkey PRIMARY KEY (id);


--
-- Name: raw_event_payloads raw_event_payloads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_event_payloads
    ADD CONSTRAINT raw_event_payloads_pkey PRIMARY KEY (id);


--
-- Name: reconciliation_runs reconciliation_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reconciliation_runs
    ADD CONSTRAINT reconciliation_runs_pkey PRIMARY KEY (id);


--
-- Name: revenue_cache_entries revenue_cache_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revenue_cache_entries
    ADD CONSTRAINT revenue_cache_entries_pkey PRIMARY KEY (tenant_id, cache_key);


--
-- Name: revenue_ledger revenue_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revenue_ledger
    ADD CONSTRAINT revenue_ledger_pkey PRIMARY KEY (id);


--
-- Name: revenue_state_transitions revenue_state_transitions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revenue_state_transitions
    ADD CONSTRAINT revenue_state_transitions_pkey PRIMARY KEY (id);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (code);


--
-- Name: session_authority session_authority_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_authority
    ADD CONSTRAINT session_authority_pkey PRIMARY KEY (id);


--
-- Name: tenant_membership_roles tenant_membership_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_membership_roles
    ADD CONSTRAINT tenant_membership_roles_pkey PRIMARY KEY (id);


--
-- Name: tenant_memberships tenant_memberships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT tenant_memberships_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: trust_access_log trust_access_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_access_log
    ADD CONSTRAINT trust_access_log_pkey PRIMARY KEY (id);


--
-- Name: trust_envelope_issuance_log trust_envelope_issuance_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_envelope_issuance_log
    ADD CONSTRAINT trust_envelope_issuance_log_pkey PRIMARY KEY (id);


--
-- Name: trust_export_artifact_attempts trust_export_artifact_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_export_artifact_attempts
    ADD CONSTRAINT trust_export_artifact_attempts_pkey PRIMARY KEY (id);


--
-- Name: trust_issuance_attempts trust_issuance_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_issuance_attempts
    ADD CONSTRAINT trust_issuance_attempts_pkey PRIMARY KEY (id);


--
-- Name: trust_rate_limit_state trust_rate_limit_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_rate_limit_state
    ADD CONSTRAINT trust_rate_limit_state_pkey PRIMARY KEY (id);


--
-- Name: trust_replay_events trust_replay_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_replay_events
    ADD CONSTRAINT trust_replay_events_pkey PRIMARY KEY (id);


--
-- Name: trust_request_nonces trust_request_nonces_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_request_nonces
    ADD CONSTRAINT trust_request_nonces_pkey PRIMARY KEY (id);


--
-- Name: trust_scope_denial_events trust_scope_denial_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_scope_denial_events
    ADD CONSTRAINT trust_scope_denial_events_pkey PRIMARY KEY (id);


--
-- Name: agent_clients uq_agent_clients_tenant_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_clients
    ADD CONSTRAINT uq_agent_clients_tenant_name UNIQUE (tenant_id, client_name);


--
-- Name: agent_scope_grants uq_agent_scope_grants_client_scope; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_scope_grants
    ADD CONSTRAINT uq_agent_scope_grants_client_scope UNIQUE (tenant_id, agent_client_id, scope_value);


--
-- Name: agent_service_credentials uq_agent_service_credentials_prefix; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_service_credentials
    ADD CONSTRAINT uq_agent_service_credentials_prefix UNIQUE (tenant_id, token_prefix);


--
-- Name: agent_token_revocations uq_agent_token_revocations_prefix; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_token_revocations
    ADD CONSTRAINT uq_agent_token_revocations_prefix UNIQUE (tenant_id, token_prefix);


--
-- Name: attribution_commerce_identities uq_attr_commerce_identity_tenant_event; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_commerce_identities
    ADD CONSTRAINT uq_attr_commerce_identity_tenant_event UNIQUE (tenant_id, attribution_event_id);


--
-- Name: attribution_commerce_identities uq_attr_commerce_identity_tenant_provider_reference; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_commerce_identities
    ADD CONSTRAINT uq_attr_commerce_identity_tenant_provider_reference UNIQUE (tenant_id, provider, canonical_commerce_reference);


--
-- Name: attribution_events uq_attribution_events_tenant_idempotency_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_events
    ADD CONSTRAINT uq_attribution_events_tenant_idempotency_key UNIQUE (tenant_id, idempotency_key);


--
-- Name: b23_match_task_dispatches uq_b23_match_task_dispatches_task_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_match_task_dispatches
    ADD CONSTRAINT uq_b23_match_task_dispatches_task_id UNIQUE (task_id);


--
-- Name: b23_match_task_dispatches uq_b23_match_task_dispatches_tenant_ingress; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_match_task_dispatches
    ADD CONSTRAINT uq_b23_match_task_dispatches_tenant_ingress UNIQUE (tenant_id, webhook_ingress_identity_id);


--
-- Name: b23_match_verdicts uq_b23_match_verdicts_tenant_provider_event_ref; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_match_verdicts
    ADD CONSTRAINT uq_b23_match_verdicts_tenant_provider_event_ref UNIQUE (tenant_id, provider, provider_native_event_reference);


--
-- Name: b23_revenue_events uq_b23_revenue_events_tenant_provider_event_ref; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_revenue_events
    ADD CONSTRAINT uq_b23_revenue_events_tenant_provider_event_ref UNIQUE (tenant_id, provider, provider_native_event_reference);


--
-- Name: b24_feature_authority_build_outbox uq_b24_feature_authority_build_outbox_candidate; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_feature_authority_build_outbox
    ADD CONSTRAINT uq_b24_feature_authority_build_outbox_candidate UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash);


--
-- Name: b24_feature_authority_build_outbox uq_b24_feature_authority_build_outbox_dispatch_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_feature_authority_build_outbox
    ADD CONSTRAINT uq_b24_feature_authority_build_outbox_dispatch_key UNIQUE (tenant_id, dispatch_key);


--
-- Name: b24_fit_dispatch_outbox uq_b24_fit_dispatch_outbox_dispatch_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_fit_dispatch_outbox
    ADD CONSTRAINT uq_b24_fit_dispatch_outbox_dispatch_key UNIQUE (tenant_id, dispatch_key);


--
-- Name: b24_fit_dispatch_outbox uq_b24_fit_dispatch_outbox_fit; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_fit_dispatch_outbox
    ADD CONSTRAINT uq_b24_fit_dispatch_outbox_fit UNIQUE (tenant_id, fit_id);


--
-- Name: b24_fit_recovery_outbox uq_b24_fit_recovery_outbox_generation; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_fit_recovery_outbox
    ADD CONSTRAINT uq_b24_fit_recovery_outbox_generation UNIQUE (tenant_id, dispatch_id, recovery_generation);


--
-- Name: b24_inference_policy_registry uq_b24_policy_registry_tuple; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_inference_policy_registry
    ADD CONSTRAINT uq_b24_policy_registry_tuple UNIQUE (policy_bundle_hash, inference_profile_version, runtime_policy_version, sampling_policy_version, diagnostic_policy_version);


--
-- Name: b27_explanation_materializations uq_b27_cache_identity; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b27_explanation_materializations
    ADD CONSTRAINT uq_b27_cache_identity UNIQUE (tenant_id, cache_identity_hash);


--
-- Name: b27_narrative_templates uq_b27_template_binding; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b27_narrative_templates
    ADD CONSTRAINT uq_b27_template_binding UNIQUE (claim_kind, source_path);


--
-- Name: b28_proposals uq_b28_proposal_ref; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b28_proposals
    ADD CONSTRAINT uq_b28_proposal_ref UNIQUE (tenant_id, proposal_ref);


--
-- Name: b28_simulation_requests uq_b28_request_ref; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b28_simulation_requests
    ADD CONSTRAINT uq_b28_request_ref UNIQUE (tenant_id, request_ref);


--
-- Name: b28_simulation_results uq_b28_result_request; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b28_simulation_results
    ADD CONSTRAINT uq_b28_result_request UNIQUE (tenant_id, request_id);


--
-- Name: budget_jobs uq_budget_jobs_tenant_request_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.budget_jobs
    ADD CONSTRAINT uq_budget_jobs_tenant_request_id UNIQUE (tenant_id, request_id);


--
-- Name: budget_optimization_jobs uq_budget_optimization_jobs_tenant_request_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.budget_optimization_jobs
    ADD CONSTRAINT uq_budget_optimization_jobs_tenant_request_id UNIQUE (tenant_id, request_id);


--
-- Name: compliance_audit_ledger uq_compliance_audit_ledger_tenant_idempotency_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compliance_audit_ledger
    ADD CONSTRAINT uq_compliance_audit_ledger_tenant_idempotency_key UNIQUE (tenant_id, idempotency_key);


--
-- Name: ephemeral_click_resolution uq_ephemeral_click_resolution_tenant_click; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ephemeral_click_resolution
    ADD CONSTRAINT uq_ephemeral_click_resolution_tenant_click UNIQUE (tenant_id, click_id);


--
-- Name: ephemeral_order_resolution uq_ephemeral_order_resolution_tenant_order; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ephemeral_order_resolution
    ADD CONSTRAINT uq_ephemeral_order_resolution_tenant_order UNIQUE (tenant_id, order_id);


--
-- Name: investigation_jobs uq_investigation_jobs_tenant_request_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigation_jobs
    ADD CONSTRAINT uq_investigation_jobs_tenant_request_id UNIQUE (tenant_id, request_id);


--
-- Name: investigations uq_investigations_tenant_request_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT uq_investigations_tenant_request_id UNIQUE (tenant_id, request_id);


--
-- Name: llm_api_calls uq_llm_api_calls_tenant_request_endpoint; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_api_calls
    ADD CONSTRAINT uq_llm_api_calls_tenant_request_endpoint UNIQUE (tenant_id, request_id, endpoint);


--
-- Name: llm_monthly_costs uq_llm_monthly_costs_tenant_user_month; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monthly_costs
    ADD CONSTRAINT uq_llm_monthly_costs_tenant_user_month UNIQUE (tenant_id, user_id, month);


--
-- Name: oauth_handshake_sessions uq_oauth_handshake_sessions_tenant_state_hash; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_handshake_sessions
    ADD CONSTRAINT uq_oauth_handshake_sessions_tenant_state_hash UNIQUE (tenant_id, state_nonce_hash);


--
-- Name: raw_event_payloads uq_raw_event_payloads_tenant_event; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_event_payloads
    ADD CONSTRAINT uq_raw_event_payloads_tenant_event UNIQUE (tenant_id, event_id);


--
-- Name: session_authority uq_session_authority_tenant_session_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_authority
    ADD CONSTRAINT uq_session_authority_tenant_session_id UNIQUE (tenant_id, session_id);


--
-- Name: tenant_membership_roles uq_tenant_membership_roles_membership_role; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_membership_roles
    ADD CONSTRAINT uq_tenant_membership_roles_membership_role UNIQUE (membership_id, role_code);


--
-- Name: tenant_memberships uq_tenant_memberships_id_tenant; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT uq_tenant_memberships_id_tenant UNIQUE (id, tenant_id);


--
-- Name: tenant_memberships uq_tenant_memberships_tenant_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT uq_tenant_memberships_tenant_user UNIQUE (tenant_id, user_id);


--
-- Name: trust_access_log uq_trust_access_log_audit_ref; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_access_log
    ADD CONSTRAINT uq_trust_access_log_audit_ref UNIQUE (tenant_id, audit_ref);


--
-- Name: trust_access_log uq_trust_access_log_idempotency; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_access_log
    ADD CONSTRAINT uq_trust_access_log_idempotency UNIQUE (tenant_id, event_type, idempotency_key_hash);


--
-- Name: trust_export_artifact_attempts uq_trust_export_artifact_attempt; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_export_artifact_attempts
    ADD CONSTRAINT uq_trust_export_artifact_attempt UNIQUE (tenant_id, request_binding_hash, page_start, attempt_number);


--
-- Name: trust_issuance_attempts uq_trust_issuance_attempt_identity; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_issuance_attempts
    ADD CONSTRAINT uq_trust_issuance_attempt_identity UNIQUE (tenant_id, audit_ref, id);


--
-- Name: trust_issuance_attempts uq_trust_issuance_attempt_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_issuance_attempts
    ADD CONSTRAINT uq_trust_issuance_attempt_number UNIQUE (tenant_id, audit_ref, attempt_number);


--
-- Name: trust_envelope_issuance_log uq_trust_issuance_envelope; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_envelope_issuance_log
    ADD CONSTRAINT uq_trust_issuance_envelope UNIQUE (tenant_id, envelope_hash);


--
-- Name: trust_envelope_issuance_log uq_trust_issuance_idempotency; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_envelope_issuance_log
    ADD CONSTRAINT uq_trust_issuance_idempotency UNIQUE (tenant_id, idempotency_key_hash);


--
-- Name: trust_rate_limit_state uq_trust_rate_limit_state_client_window; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_rate_limit_state
    ADD CONSTRAINT uq_trust_rate_limit_state_client_window UNIQUE (tenant_id, agent_client_id, window_started_at, window_ended_at);


--
-- Name: trust_replay_events uq_trust_replay_event; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_replay_events
    ADD CONSTRAINT uq_trust_replay_event UNIQUE (tenant_id, idempotency_key_hash, original_audit_ref);


--
-- Name: trust_request_nonces uq_trust_request_nonces_tenant_nonce; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_request_nonces
    ADD CONSTRAINT uq_trust_request_nonces_tenant_nonce UNIQUE (tenant_id, nonce_value);


--
-- Name: trust_scope_denial_events uq_trust_scope_denial_idempotency; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_scope_denial_events
    ADD CONSTRAINT uq_trust_scope_denial_idempotency UNIQUE (tenant_id, idempotency_key_hash);


--
-- Name: webhook_ingress_identities uq_webhook_ingress_identities_event_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_ingress_identities
    ADD CONSTRAINT uq_webhook_ingress_identities_event_id UNIQUE (event_id);


--
-- Name: webhook_ingress_identities uq_webhook_ingress_identities_tenant_event; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_ingress_identities
    ADD CONSTRAINT uq_webhook_ingress_identities_tenant_event UNIQUE (tenant_id, event_id);


--
-- Name: webhook_ingress_identities uq_webhook_ingress_identities_tenant_idempotency; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_ingress_identities
    ADD CONSTRAINT uq_webhook_ingress_identities_tenant_idempotency UNIQUE (tenant_id, idempotency_key);


--
-- Name: users users_login_identifier_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_login_identifier_hash_key UNIQUE (login_identifier_hash);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: webhook_ingress_identities webhook_ingress_identities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_ingress_identities
    ADD CONSTRAINT webhook_ingress_identities_pkey PRIMARY KEY (id);


--
-- Name: worker_side_effects worker_side_effects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.worker_side_effects
    ADD CONSTRAINT worker_side_effects_pkey PRIMARY KEY (id);


--
-- Name: idx_bayesian_artifacts_tenant_artifact_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bayesian_artifacts_tenant_artifact_hash ON ONLY public.bayesian_artifacts USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p00_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p00_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p00 USING btree (tenant_id, artifact_hash);


--
-- Name: idx_bayesian_artifacts_tenant_artifact_ref; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bayesian_artifacts_tenant_artifact_ref ON ONLY public.bayesian_artifacts USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p00_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p00_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p00 USING btree (tenant_id, artifact_ref);


--
-- Name: idx_bayesian_artifacts_tenant_fit; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bayesian_artifacts_tenant_fit ON ONLY public.bayesian_artifacts USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p00_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p00_tenant_id_fit_id_idx ON public.bayesian_artifacts_p00 USING btree (tenant_id, fit_id);


--
-- Name: idx_bayesian_artifacts_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bayesian_artifacts_tenant_id ON ONLY public.bayesian_artifacts USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p00_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p00_tenant_id_idx ON public.bayesian_artifacts_p00 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p01_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p01_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p01 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p01_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p01_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p01 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p01_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p01_tenant_id_fit_id_idx ON public.bayesian_artifacts_p01 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p01_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p01_tenant_id_idx ON public.bayesian_artifacts_p01 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p02_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p02_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p02 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p02_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p02_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p02 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p02_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p02_tenant_id_fit_id_idx ON public.bayesian_artifacts_p02 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p02_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p02_tenant_id_idx ON public.bayesian_artifacts_p02 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p03_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p03_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p03 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p03_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p03_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p03 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p03_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p03_tenant_id_fit_id_idx ON public.bayesian_artifacts_p03 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p03_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p03_tenant_id_idx ON public.bayesian_artifacts_p03 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p04_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p04_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p04 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p04_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p04_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p04 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p04_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p04_tenant_id_fit_id_idx ON public.bayesian_artifacts_p04 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p04_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p04_tenant_id_idx ON public.bayesian_artifacts_p04 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p05_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p05_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p05 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p05_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p05_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p05 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p05_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p05_tenant_id_fit_id_idx ON public.bayesian_artifacts_p05 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p05_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p05_tenant_id_idx ON public.bayesian_artifacts_p05 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p06_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p06_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p06 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p06_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p06_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p06 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p06_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p06_tenant_id_fit_id_idx ON public.bayesian_artifacts_p06 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p06_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p06_tenant_id_idx ON public.bayesian_artifacts_p06 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p07_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p07_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p07 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p07_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p07_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p07 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p07_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p07_tenant_id_fit_id_idx ON public.bayesian_artifacts_p07 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p07_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p07_tenant_id_idx ON public.bayesian_artifacts_p07 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p08_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p08_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p08 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p08_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p08_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p08 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p08_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p08_tenant_id_fit_id_idx ON public.bayesian_artifacts_p08 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p08_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p08_tenant_id_idx ON public.bayesian_artifacts_p08 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p09_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p09_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p09 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p09_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p09_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p09 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p09_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p09_tenant_id_fit_id_idx ON public.bayesian_artifacts_p09 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p09_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p09_tenant_id_idx ON public.bayesian_artifacts_p09 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p10_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p10_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p10 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p10_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p10_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p10 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p10_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p10_tenant_id_fit_id_idx ON public.bayesian_artifacts_p10 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p10_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p10_tenant_id_idx ON public.bayesian_artifacts_p10 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p11_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p11_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p11 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p11_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p11_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p11 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p11_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p11_tenant_id_fit_id_idx ON public.bayesian_artifacts_p11 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p11_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p11_tenant_id_idx ON public.bayesian_artifacts_p11 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p12_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p12_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p12 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p12_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p12_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p12 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p12_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p12_tenant_id_fit_id_idx ON public.bayesian_artifacts_p12 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p12_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p12_tenant_id_idx ON public.bayesian_artifacts_p12 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p13_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p13_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p13 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p13_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p13_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p13 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p13_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p13_tenant_id_fit_id_idx ON public.bayesian_artifacts_p13 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p13_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p13_tenant_id_idx ON public.bayesian_artifacts_p13 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p14_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p14_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p14 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p14_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p14_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p14 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p14_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p14_tenant_id_fit_id_idx ON public.bayesian_artifacts_p14 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p14_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p14_tenant_id_idx ON public.bayesian_artifacts_p14 USING btree (tenant_id);


--
-- Name: bayesian_artifacts_p15_tenant_id_artifact_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p15_tenant_id_artifact_hash_idx ON public.bayesian_artifacts_p15 USING btree (tenant_id, artifact_hash);


--
-- Name: bayesian_artifacts_p15_tenant_id_artifact_ref_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p15_tenant_id_artifact_ref_idx ON public.bayesian_artifacts_p15 USING btree (tenant_id, artifact_ref);


--
-- Name: bayesian_artifacts_p15_tenant_id_fit_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p15_tenant_id_fit_id_idx ON public.bayesian_artifacts_p15 USING btree (tenant_id, fit_id);


--
-- Name: bayesian_artifacts_p15_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_artifacts_p15_tenant_id_idx ON public.bayesian_artifacts_p15 USING btree (tenant_id);


--
-- Name: idx_bayesian_model_fits_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bayesian_model_fits_tenant_id ON ONLY public.bayesian_model_fits USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p00_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p00_tenant_id_idx ON public.bayesian_model_fits_p00 USING btree (tenant_id);


--
-- Name: idx_bayesian_model_fits_tenant_model_eligibility; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bayesian_model_fits_tenant_model_eligibility ON ONLY public.bayesian_model_fits USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p00_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p00_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p00 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: idx_bayesian_model_fits_tenant_model_fallback; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bayesian_model_fits_tenant_model_fallback ON ONLY public.bayesian_model_fits USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p00_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p00_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p00 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: idx_bayesian_model_fits_tenant_model_window; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bayesian_model_fits_tenant_model_window ON ONLY public.bayesian_model_fits USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p00_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p00_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p00 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: idx_bayesian_model_fits_tenant_model_window_latest; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bayesian_model_fits_tenant_model_window_latest ON ONLY public.bayesian_model_fits USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p00_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p00_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p00 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: idx_bayesian_model_fits_tenant_source_snapshot_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bayesian_model_fits_tenant_source_snapshot_hash ON ONLY public.bayesian_model_fits USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p00_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p00_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p00 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: idx_bayesian_model_fits_tenant_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bayesian_model_fits_tenant_status ON ONLY public.bayesian_model_fits USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p00_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p00_tenant_id_status_idx ON public.bayesian_model_fits_p00 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p01_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p01_tenant_id_idx ON public.bayesian_model_fits_p01 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p01_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p01_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p01 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p01_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p01_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p01 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p01_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p01_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p01 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p01_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p01_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p01 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p01_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p01_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p01 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p01_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p01_tenant_id_status_idx ON public.bayesian_model_fits_p01 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p02_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p02_tenant_id_idx ON public.bayesian_model_fits_p02 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p02_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p02_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p02 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p02_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p02_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p02 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p02_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p02_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p02 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p02_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p02_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p02 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p02_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p02_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p02 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p02_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p02_tenant_id_status_idx ON public.bayesian_model_fits_p02 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p03_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p03_tenant_id_idx ON public.bayesian_model_fits_p03 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p03_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p03_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p03 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p03_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p03_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p03 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p03_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p03_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p03 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p03_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p03_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p03 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p03_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p03_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p03 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p03_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p03_tenant_id_status_idx ON public.bayesian_model_fits_p03 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p04_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p04_tenant_id_idx ON public.bayesian_model_fits_p04 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p04_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p04_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p04 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p04_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p04_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p04 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p04_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p04_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p04 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p04_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p04_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p04 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p04_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p04_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p04 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p04_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p04_tenant_id_status_idx ON public.bayesian_model_fits_p04 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p05_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p05_tenant_id_idx ON public.bayesian_model_fits_p05 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p05_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p05_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p05 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p05_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p05_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p05 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p05_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p05_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p05 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p05_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p05_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p05 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p05_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p05_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p05 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p05_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p05_tenant_id_status_idx ON public.bayesian_model_fits_p05 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p06_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p06_tenant_id_idx ON public.bayesian_model_fits_p06 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p06_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p06_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p06 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p06_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p06_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p06 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p06_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p06_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p06 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p06_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p06_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p06 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p06_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p06_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p06 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p06_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p06_tenant_id_status_idx ON public.bayesian_model_fits_p06 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p07_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p07_tenant_id_idx ON public.bayesian_model_fits_p07 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p07_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p07_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p07 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p07_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p07_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p07 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p07_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p07_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p07 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p07_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p07_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p07 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p07_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p07_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p07 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p07_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p07_tenant_id_status_idx ON public.bayesian_model_fits_p07 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p08_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p08_tenant_id_idx ON public.bayesian_model_fits_p08 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p08_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p08_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p08 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p08_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p08_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p08 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p08_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p08_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p08 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p08_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p08_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p08 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p08_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p08_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p08 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p08_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p08_tenant_id_status_idx ON public.bayesian_model_fits_p08 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p09_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p09_tenant_id_idx ON public.bayesian_model_fits_p09 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p09_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p09_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p09 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p09_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p09_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p09 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p09_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p09_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p09 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p09_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p09_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p09 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p09_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p09_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p09 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p09_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p09_tenant_id_status_idx ON public.bayesian_model_fits_p09 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p10_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p10_tenant_id_idx ON public.bayesian_model_fits_p10 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p10_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p10_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p10 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p10_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p10_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p10 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p10_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p10_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p10 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p10_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p10_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p10 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p10_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p10_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p10 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p10_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p10_tenant_id_status_idx ON public.bayesian_model_fits_p10 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p11_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p11_tenant_id_idx ON public.bayesian_model_fits_p11 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p11_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p11_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p11 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p11_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p11_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p11 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p11_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p11_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p11 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p11_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p11_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p11 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p11_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p11_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p11 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p11_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p11_tenant_id_status_idx ON public.bayesian_model_fits_p11 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p12_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p12_tenant_id_idx ON public.bayesian_model_fits_p12 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p12_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p12_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p12 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p12_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p12_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p12 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p12_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p12_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p12 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p12_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p12_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p12 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p12_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p12_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p12 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p12_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p12_tenant_id_status_idx ON public.bayesian_model_fits_p12 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p13_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p13_tenant_id_idx ON public.bayesian_model_fits_p13 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p13_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p13_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p13 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p13_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p13_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p13 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p13_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p13_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p13 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p13_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p13_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p13 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p13_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p13_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p13 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p13_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p13_tenant_id_status_idx ON public.bayesian_model_fits_p13 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p14_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p14_tenant_id_idx ON public.bayesian_model_fits_p14 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p14_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p14_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p14 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p14_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p14_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p14 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p14_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p14_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p14 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p14_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p14_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p14 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p14_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p14_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p14 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p14_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p14_tenant_id_status_idx ON public.bayesian_model_fits_p14 USING btree (tenant_id, status);


--
-- Name: bayesian_model_fits_p15_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p15_tenant_id_idx ON public.bayesian_model_fits_p15 USING btree (tenant_id);


--
-- Name: bayesian_model_fits_p15_tenant_id_model_type_eligibility_st_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p15_tenant_id_model_type_eligibility_st_idx ON public.bayesian_model_fits_p15 USING btree (tenant_id, model_type, eligibility_status, last_eligibility_check_at DESC);


--
-- Name: bayesian_model_fits_p15_tenant_id_model_type_fallback_reaso_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p15_tenant_id_model_type_fallback_reaso_idx ON public.bayesian_model_fits_p15 USING btree (tenant_id, model_type, fallback_reason, last_eligibility_check_at DESC) WHERE (fallback_applied = true);


--
-- Name: bayesian_model_fits_p15_tenant_id_model_type_source_window__idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p15_tenant_id_model_type_source_window__idx ON public.bayesian_model_fits_p15 USING btree (tenant_id, model_type, source_window_start, source_window_end);


--
-- Name: bayesian_model_fits_p15_tenant_id_model_type_source_window_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p15_tenant_id_model_type_source_window_idx1 ON public.bayesian_model_fits_p15 USING btree (tenant_id, model_type, source_window_start, source_window_end, created_at DESC);


--
-- Name: bayesian_model_fits_p15_tenant_id_source_snapshot_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p15_tenant_id_source_snapshot_hash_idx ON public.bayesian_model_fits_p15 USING btree (tenant_id, source_snapshot_hash);


--
-- Name: bayesian_model_fits_p15_tenant_id_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bayesian_model_fits_p15_tenant_id_status_idx ON public.bayesian_model_fits_p15 USING btree (tenant_id, status);


--
-- Name: idx_agent_clients_tenant_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_agent_clients_tenant_status ON public.agent_clients USING btree (tenant_id, status, created_at DESC);


--
-- Name: idx_agent_scope_grants_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_agent_scope_grants_lookup ON public.agent_scope_grants USING btree (tenant_id, agent_client_id, scope_value);


--
-- Name: idx_agent_service_credentials_client; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_agent_service_credentials_client ON public.agent_service_credentials USING btree (tenant_id, agent_client_id, issued_at DESC);


--
-- Name: idx_agent_service_credentials_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_agent_service_credentials_lookup ON public.agent_service_credentials USING btree (tenant_id, token_prefix, status);


--
-- Name: idx_agent_token_revocations_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_agent_token_revocations_lookup ON public.agent_token_revocations USING btree (tenant_id, token_prefix);


--
-- Name: idx_allocations_channel_performance; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_allocations_channel_performance ON public.attribution_allocations USING btree (tenant_id, channel_code, created_at DESC) INCLUDE (allocated_revenue_cents, confidence_score);


--
-- Name: idx_allocations_tenant_projection_channel; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_allocations_tenant_projection_channel ON public.attribution_allocations USING btree (tenant_id, recompute_job_id, model_type, channel_code);


--
-- Name: idx_attr_commerce_identity_last_observed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_attr_commerce_identity_last_observed ON public.attribution_commerce_identities USING btree (last_observed_at);


--
-- Name: idx_attr_commerce_identity_tenant_last_observed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_attr_commerce_identity_tenant_last_observed ON public.attribution_commerce_identities USING btree (tenant_id, last_observed_at DESC);


--
-- Name: idx_attr_commerce_identity_tenant_provider_reference; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_attr_commerce_identity_tenant_provider_reference ON public.attribution_commerce_identities USING btree (tenant_id, provider, canonical_commerce_reference);


--
-- Name: idx_attribution_allocations_channel; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_attribution_allocations_channel ON public.attribution_allocations USING btree (channel_code);


--
-- Name: idx_attribution_allocations_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_attribution_allocations_event_id ON public.attribution_allocations USING btree (event_id);


--
-- Name: idx_attribution_allocations_tenant_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_attribution_allocations_tenant_created_at ON public.attribution_allocations USING btree (tenant_id, created_at DESC);


--
-- Name: idx_attribution_allocations_tenant_event_model; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_attribution_allocations_tenant_event_model ON public.attribution_allocations USING btree (tenant_id, event_id, model_version);


--
-- Name: idx_attribution_allocations_tenant_event_model_channel; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_attribution_allocations_tenant_event_model_channel ON public.attribution_allocations USING btree (tenant_id, event_id, model_version, channel_code) WHERE ((model_version IS NOT NULL) AND (recompute_job_id IS NULL));


--
-- Name: idx_attribution_allocations_tenant_event_projection; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_attribution_allocations_tenant_event_projection ON public.attribution_allocations USING btree (tenant_id, event_id, recompute_job_id) WHERE (recompute_job_id IS NOT NULL);


--
-- Name: idx_attribution_allocations_tenant_event_projection_channel; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_attribution_allocations_tenant_event_projection_channel ON public.attribution_allocations USING btree (tenant_id, event_id, recompute_job_id, channel_code) WHERE (recompute_job_id IS NOT NULL);


--
-- Name: idx_attribution_allocations_tenant_model_version; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_attribution_allocations_tenant_model_version ON public.attribution_allocations USING btree (tenant_id, model_version);


--
-- Name: idx_attribution_events_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_attribution_events_session_id ON public.attribution_events USING btree (session_id) WHERE (session_id IS NOT NULL);


--
-- Name: idx_attribution_events_tenant_occurred_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_attribution_events_tenant_occurred_at ON public.attribution_events USING btree (tenant_id, occurred_at DESC);


--
-- Name: idx_attribution_recompute_jobs_tenant_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_attribution_recompute_jobs_tenant_created_at ON public.attribution_recompute_jobs USING btree (tenant_id, created_at DESC);


--
-- Name: idx_attribution_recompute_jobs_tenant_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_attribution_recompute_jobs_tenant_status ON public.attribution_recompute_jobs USING btree (tenant_id, status);


--
-- Name: idx_attribution_recompute_jobs_window_identity; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_attribution_recompute_jobs_window_identity ON public.attribution_recompute_jobs USING btree (tenant_id, window_start, window_end, model_version);


--
-- Name: idx_auth_access_token_denylist_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_access_token_denylist_expires_at ON public.auth_access_token_denylist USING btree (expires_at DESC);


--
-- Name: idx_auth_access_token_denylist_jti; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_access_token_denylist_jti ON public.auth_access_token_denylist USING btree (jti);


--
-- Name: idx_auth_access_token_denylist_tenant_user_revoked_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_access_token_denylist_tenant_user_revoked_at ON public.auth_access_token_denylist USING btree (tenant_id, user_id, revoked_at DESC);


--
-- Name: idx_auth_refresh_tokens_family_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_refresh_tokens_family_created_at ON public.auth_refresh_tokens USING btree (family_id, created_at DESC);


--
-- Name: idx_auth_refresh_tokens_tenant_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_refresh_tokens_tenant_created_at ON public.auth_refresh_tokens USING btree (tenant_id, created_at DESC);


--
-- Name: idx_auth_refresh_tokens_tenant_user_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_refresh_tokens_tenant_user_created_at ON public.auth_refresh_tokens USING btree (tenant_id, user_id, created_at DESC);


--
-- Name: idx_auth_user_token_cutoffs_tenant_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_user_token_cutoffs_tenant_user ON public.auth_user_token_cutoffs USING btree (tenant_id, user_id);


--
-- Name: idx_b23_exception_records_tenant_provider_reference; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_exception_records_tenant_provider_reference ON public.b23_exception_records USING btree (tenant_id, provider, canonical_commerce_reference);


--
-- Name: idx_b23_exception_records_tenant_status_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_exception_records_tenant_status_severity ON public.b23_exception_records USING btree (tenant_id, status, severity, raised_at DESC);


--
-- Name: idx_b23_match_task_dispatches_ingress; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_match_task_dispatches_ingress ON public.b23_match_task_dispatches USING btree (webhook_ingress_identity_id);


--
-- Name: idx_b23_match_task_dispatches_tenant_reference; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_match_task_dispatches_tenant_reference ON public.b23_match_task_dispatches USING btree (tenant_id, provider, provider_native_event_reference, normalized_commerce_reference_value);


--
-- Name: idx_b23_match_verdicts_tenant_discrepancy_band; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_match_verdicts_tenant_discrepancy_band ON public.b23_match_verdicts USING btree (tenant_id, discrepancy_band, last_transition_at DESC);


--
-- Name: idx_b23_match_verdicts_tenant_discrepancy_ratio_bps; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_match_verdicts_tenant_discrepancy_ratio_bps ON public.b23_match_verdicts USING btree (tenant_id, discrepancy_ratio_bps, last_transition_at DESC);


--
-- Name: idx_b23_match_verdicts_tenant_provider_commerce_native; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_match_verdicts_tenant_provider_commerce_native ON public.b23_match_verdicts USING btree (tenant_id, provider, provider_native_commerce_reference);


--
-- Name: idx_b23_match_verdicts_tenant_provider_reference; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_match_verdicts_tenant_provider_reference ON public.b23_match_verdicts USING btree (tenant_id, provider, canonical_commerce_reference);


--
-- Name: idx_b23_match_verdicts_tenant_state_timestamps; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_match_verdicts_tenant_state_timestamps ON public.b23_match_verdicts USING btree (tenant_id, pending_since, provisional_expires_at, confirmed_at, unmatched_marked_at, adjusted_at);


--
-- Name: idx_b23_match_verdicts_tenant_status_transition; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_match_verdicts_tenant_status_transition ON public.b23_match_verdicts USING btree (tenant_id, status, last_transition_at DESC);


--
-- Name: idx_b23_p4_attribution_event_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_p4_attribution_event_tenant_id ON public.attribution_events USING btree (tenant_id, id);


--
-- Name: idx_b23_p4_attribution_order_ref_expr; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_p4_attribution_order_ref_expr ON public.attribution_events USING btree (tenant_id, ((raw_payload ->> 'order_id'::text)), occurred_at DESC) WHERE (raw_payload ? 'order_id'::text);


--
-- Name: idx_b23_p4_match_rate_tenant_transition_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_p4_match_rate_tenant_transition_status ON public.b23_match_verdicts USING btree (tenant_id, last_transition_at DESC, status) WHERE ((status)::text = ANY ((ARRAY['matched_provisional'::character varying, 'matched_confirmed'::character varying, 'adjusted'::character varying, 'unmatched'::character varying])::text[]));


--
-- Name: idx_b23_p4_verdict_webhook_identity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_p4_verdict_webhook_identity ON public.b23_match_verdicts USING btree (tenant_id, webhook_ingress_identity_id) WHERE (webhook_ingress_identity_id IS NOT NULL);


--
-- Name: idx_b23_p4_webhook_failure_tenant_platform_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_p4_webhook_failure_tenant_platform_time ON public.b23_webhook_ingestion_logs USING btree (tenant_id, provider, received_at DESC) WHERE ((ingestion_status)::text = 'failed'::text);


--
-- Name: idx_b23_p4_webhook_identity_claim; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_p4_webhook_identity_claim ON public.webhook_ingress_identities USING btree (tenant_id, verified_commerce_ingress_state, event_timestamp, id) WHERE ((verified_commerce_ingress_state)::text = 'authenticity_verified'::text);


--
-- Name: idx_b23_p4_worker_dlq_open_status_failed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_p4_worker_dlq_open_status_failed_at ON public.worker_failed_jobs USING btree (status, tenant_id, failed_at DESC) WHERE ((status)::text = ANY ((ARRAY['pending'::character varying, 'in_progress'::character varying])::text[]));


--
-- Name: idx_b23_revenue_events_tenant_event_effect_sign; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_revenue_events_tenant_event_effect_sign ON public.b23_revenue_events USING btree (tenant_id, event_type, net_effect_sign, event_occurred_at DESC);


--
-- Name: idx_b23_revenue_events_tenant_event_type_recorded; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_revenue_events_tenant_event_type_recorded ON public.b23_revenue_events USING btree (tenant_id, event_type, recorded_at DESC);


--
-- Name: idx_b23_revenue_events_tenant_gross_capture_correction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_revenue_events_tenant_gross_capture_correction ON public.b23_revenue_events USING btree (tenant_id, match_verdict_id, is_gross_capture_correction, event_occurred_at DESC);


--
-- Name: idx_b23_revenue_events_tenant_provider_commerce_native; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_revenue_events_tenant_provider_commerce_native ON public.b23_revenue_events USING btree (tenant_id, provider, provider_native_commerce_reference);


--
-- Name: idx_b23_revenue_events_tenant_provider_reference; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_revenue_events_tenant_provider_reference ON public.b23_revenue_events USING btree (tenant_id, provider, canonical_commerce_reference, event_occurred_at DESC);


--
-- Name: idx_b23_webhook_ingestion_logs_tenant_provider_received; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_webhook_ingestion_logs_tenant_provider_received ON public.b23_webhook_ingestion_logs USING btree (tenant_id, provider, received_at DESC);


--
-- Name: idx_b23_webhook_ingestion_logs_tenant_status_received; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b23_webhook_ingestion_logs_tenant_status_received ON public.b23_webhook_ingestion_logs USING btree (tenant_id, ingestion_status, received_at DESC);


--
-- Name: idx_b24_active_execution_canonical_profiling; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_active_execution_canonical_profiling ON public.b24_active_execution_leases USING btree (tenant_id, model_type, model_version, source_window_start, source_window_end, status, leased_until) WHERE ((status)::text = 'profiling'::text);


--
-- Name: idx_b24_active_execution_superseded; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_active_execution_superseded ON public.b24_active_execution_leases USING btree (tenant_id, model_type, model_version, source_window_start, source_window_end) WHERE (needs_refit_after_current = true);


--
-- Name: idx_b24_active_execution_tenant_fit; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_active_execution_tenant_fit ON public.b24_active_execution_leases USING btree (tenant_id, fit_id) WHERE (fit_id IS NOT NULL);


--
-- Name: idx_b24_active_execution_tenant_status_lease; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_active_execution_tenant_status_lease ON public.b24_active_execution_leases USING btree (tenant_id, status, leased_until);


--
-- Name: idx_b24_dirty_events_authority_retry_ready; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_dirty_events_authority_retry_ready ON public.b24_dirty_events USING btree (tenant_id, status, authority_retry_after_at, observed_at, id) WHERE ((status)::text = ANY ((ARRAY['authority_waiting'::character varying, 'authority_retry_ready'::character varying])::text[]));


--
-- Name: idx_b24_dirty_events_confidence_freshness; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_dirty_events_confidence_freshness ON public.b24_dirty_events USING btree (tenant_id, model_type, model_version, source_window_start, source_window_end, observed_at, source_snapshot_hash);


--
-- Name: idx_b24_dirty_events_staleness_overlap; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_dirty_events_staleness_overlap ON public.b24_dirty_events USING btree (tenant_id, model_type, source_window_start, source_window_end, observed_at);


--
-- Name: idx_b24_dirty_events_tenant_event_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_dirty_events_tenant_event_hash ON public.b24_dirty_events USING btree (tenant_id, event_hash) WHERE (event_hash IS NOT NULL);


--
-- Name: idx_b24_dirty_events_tenant_model_window_pending; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_dirty_events_tenant_model_window_pending ON public.b24_dirty_events USING btree (tenant_id, model_type, model_version, source_window_start, source_window_end, observed_at, id) WHERE ((status)::text = ANY ((ARRAY['pending'::character varying, 'leased'::character varying])::text[]));


--
-- Name: idx_b24_dirty_events_tenant_status_observed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_dirty_events_tenant_status_observed ON public.b24_dirty_events USING btree (tenant_id, status, observed_at, id);


--
-- Name: idx_b24_feature_authority_build_outbox_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_feature_authority_build_outbox_due ON public.b24_feature_authority_build_outbox USING btree (tenant_id, status, next_attempt_at, id) WHERE ((status)::text = ANY ((ARRAY['pending'::character varying, 'failed_retryable'::character varying, 'stale_recovered'::character varying])::text[]));


--
-- Name: idx_b24_feature_authority_build_requests_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_feature_authority_build_requests_due ON public.b24_feature_authority_build_requests USING btree (tenant_id, status, retry_after_at) WHERE ((status)::text = ANY ((ARRAY['authority_build_requested'::character varying, 'authority_waiting'::character varying, 'authority_retry_ready'::character varying])::text[]));


--
-- Name: idx_b24_feature_authority_tenant_model_window; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_feature_authority_tenant_model_window ON public.b24_source_window_feature_authority USING btree (tenant_id, model_type, model_version, source_window_start, source_window_end, computed_at DESC);


--
-- Name: idx_b24_fit_dispatch_outbox_dispatching; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_fit_dispatch_outbox_dispatching ON public.b24_fit_dispatch_outbox USING btree (tenant_id, dispatching_started_at) WHERE ((status)::text = 'dispatching'::text);


--
-- Name: idx_b24_fit_dispatch_outbox_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_fit_dispatch_outbox_due ON public.b24_fit_dispatch_outbox USING btree (tenant_id, status, next_attempt_at, id) WHERE ((status)::text = ANY ((ARRAY['pending'::character varying, 'failed_retryable'::character varying, 'stale_recovered'::character varying])::text[]));


--
-- Name: idx_b24_fit_dispatch_outbox_recoverable; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_fit_dispatch_outbox_recoverable ON public.b24_fit_dispatch_outbox USING btree (status, next_recovery_at, lease_expires_at) WHERE ((status)::text = ANY ((ARRAY['dispatched'::character varying, 'leased'::character varying, 'running'::character varying, 'failed_retryable'::character varying, 'stale_recovered'::character varying])::text[]));


--
-- Name: idx_b24_fit_recovery_outbox_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_fit_recovery_outbox_due ON public.b24_fit_recovery_outbox USING btree (status, created_at, id) WHERE ((status)::text = ANY ((ARRAY['pending'::character varying, 'failed_retryable'::character varying])::text[]));


--
-- Name: idx_b24_p2_attribution_allocations_source_stream; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p2_attribution_allocations_source_stream ON public.attribution_allocations USING btree (tenant_id, created_at, id) WHERE (verified = true);


--
-- Name: idx_b24_p2_attribution_events_source_stream; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p2_attribution_events_source_stream ON public.attribution_events USING btree (tenant_id, occurred_at, id) WHERE (((processing_status)::text = 'processed'::text) AND ((event_type)::text = 'conversion'::text));


--
-- Name: idx_b24_p2_match_verdicts_source_stream; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p2_match_verdicts_source_stream ON public.b23_match_verdicts USING btree (tenant_id, last_transition_at, id) WHERE ((status)::text = ANY ((ARRAY['matched_confirmed'::character varying, 'adjusted'::character varying])::text[]));


--
-- Name: idx_b24_p2_revenue_events_source_stream; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p2_revenue_events_source_stream ON public.b23_revenue_events USING btree (tenant_id, event_occurred_at, id) WHERE ((event_type)::text = ANY ((ARRAY['payment_capture'::character varying, 'partial_refund'::character varying, 'full_refund'::character varying, 'chargeback_lost'::character varying, 'chargeback_won'::character varying, 'reversal'::character varying])::text[]));


--
-- Name: idx_b24_p3_attribution_allocations_source_stream_fallback; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p3_attribution_allocations_source_stream_fallback ON public.attribution_allocations USING btree (tenant_id, created_at, id);


--
-- Name: idx_b24_p3_attribution_events_source_stream_fallback; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p3_attribution_events_source_stream_fallback ON public.attribution_events USING btree (tenant_id, occurred_at, id);


--
-- Name: idx_b24_p3_match_verdicts_source_stream_fallback; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p3_match_verdicts_source_stream_fallback ON public.b23_match_verdicts USING btree (tenant_id, last_transition_at, id);


--
-- Name: idx_b24_p3_revenue_events_source_stream_fallback; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p3_revenue_events_source_stream_fallback ON public.b23_revenue_events USING btree (tenant_id, event_occurred_at, id);


--
-- Name: idx_b24_p4_attribution_events_campaign_cardinality; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p4_attribution_events_campaign_cardinality ON public.attribution_events USING btree (tenant_id, campaign_id, occurred_at, id) WHERE (((processing_status)::text = 'processed'::text) AND ((event_type)::text = 'conversion'::text) AND (campaign_id IS NOT NULL));


--
-- Name: idx_b24_p4_attribution_events_campaign_early_stop; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p4_attribution_events_campaign_early_stop ON public.attribution_events USING btree (tenant_id, campaign_id, occurred_at, id) WHERE (((processing_status)::text = 'processed'::text) AND ((event_type)::text = 'conversion'::text) AND (campaign_id IS NOT NULL) AND ((campaign_id)::text <> ''::text));


--
-- Name: idx_b24_p4_attribution_events_channel_early_stop; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p4_attribution_events_channel_early_stop ON public.attribution_events USING btree (tenant_id, channel, occurred_at, id) WHERE (((processing_status)::text = 'processed'::text) AND ((event_type)::text = 'conversion'::text) AND (channel IS NOT NULL) AND ((channel)::text <> ''::text));


--
-- Name: idx_b24_p4_match_verdicts_provider_cardinality; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p4_match_verdicts_provider_cardinality ON public.b23_match_verdicts USING btree (tenant_id, provider, last_transition_at, id) WHERE (((status)::text = ANY ((ARRAY['matched_confirmed'::character varying, 'adjusted'::character varying])::text[])) AND (provider IS NOT NULL));


--
-- Name: idx_b24_p4_match_verdicts_provider_early_stop; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p4_match_verdicts_provider_early_stop ON public.b23_match_verdicts USING btree (tenant_id, provider, last_transition_at, id) WHERE (((status)::text = ANY ((ARRAY['matched_confirmed'::character varying, 'adjusted'::character varying])::text[])) AND (provider IS NOT NULL) AND ((provider)::text <> ''::text));


--
-- Name: idx_b24_p4_revenue_events_provider_cardinality; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p4_revenue_events_provider_cardinality ON public.b23_revenue_events USING btree (tenant_id, provider, event_occurred_at, id) WHERE (((event_type)::text = ANY ((ARRAY['payment_capture'::character varying, 'partial_refund'::character varying, 'full_refund'::character varying, 'chargeback_lost'::character varying, 'chargeback_won'::character varying, 'reversal'::character varying])::text[])) AND (provider IS NOT NULL));


--
-- Name: idx_b24_p4_revenue_events_provider_early_stop; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_p4_revenue_events_provider_early_stop ON public.b23_revenue_events USING btree (tenant_id, provider, event_occurred_at, id) WHERE (((event_type)::text = ANY ((ARRAY['payment_capture'::character varying, 'partial_refund'::character varying, 'full_refund'::character varying, 'chargeback_lost'::character varying, 'chargeback_won'::character varying, 'reversal'::character varying])::text[])) AND (provider IS NOT NULL) AND ((provider)::text <> ''::text));


--
-- Name: idx_b24_worker_process_authority_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b24_worker_process_authority_active ON public.b24_worker_process_authority USING btree (expires_at, registered_at) WHERE ((status)::text = 'active'::text);


--
-- Name: idx_b28_request_requester; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_b28_request_requester ON public.b28_simulation_requests USING btree (tenant_id, requested_by_agent_client_id);


--
-- Name: idx_budget_jobs_tenant_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_budget_jobs_tenant_status ON public.budget_optimization_jobs USING btree (tenant_id, status, created_at DESC);


--
-- Name: idx_channel_assignment_corrections_channels; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_channel_assignment_corrections_channels ON public.channel_assignment_corrections USING btree (from_channel, to_channel, corrected_at DESC);


--
-- Name: idx_channel_assignment_corrections_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_channel_assignment_corrections_entity ON public.channel_assignment_corrections USING btree (tenant_id, entity_type, entity_id, corrected_at DESC);


--
-- Name: idx_channel_assignment_corrections_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_channel_assignment_corrections_tenant ON public.channel_assignment_corrections USING btree (tenant_id, corrected_at DESC);


--
-- Name: idx_channel_state_transitions_channel_changed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_channel_state_transitions_channel_changed_at ON public.channel_state_transitions USING btree (channel_code, changed_at DESC);


--
-- Name: idx_channel_state_transitions_to_state_changed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_channel_state_transitions_to_state_changed_at ON public.channel_state_transitions USING btree (to_state, changed_at DESC);


--
-- Name: idx_compliance_audit_ledger_tenant_correlation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_compliance_audit_ledger_tenant_correlation ON public.compliance_audit_ledger USING btree (tenant_id, correlation_id);


--
-- Name: idx_compliance_audit_ledger_tenant_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_compliance_audit_ledger_tenant_created ON public.compliance_audit_ledger USING btree (tenant_id, created_at DESC);


--
-- Name: idx_dead_events_error_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dead_events_error_code ON public.dead_events USING btree (error_code);


--
-- Name: idx_dead_events_quarantine_null_lane; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dead_events_quarantine_null_lane ON public.dead_events_quarantine USING btree (ingested_at DESC) WHERE (tenant_id IS NULL);


--
-- Name: idx_dead_events_quarantine_tenant_idempotency_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dead_events_quarantine_tenant_idempotency_key ON public.dead_events_quarantine USING btree (tenant_id, idempotency_key) WHERE (idempotency_key IS NOT NULL);


--
-- Name: idx_dead_events_quarantine_tenant_ingested_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dead_events_quarantine_tenant_ingested_at ON public.dead_events_quarantine USING btree (tenant_id, ingested_at DESC);


--
-- Name: idx_dead_events_remediation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dead_events_remediation ON public.dead_events USING btree (remediation_status, ingested_at DESC);


--
-- Name: idx_dead_events_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dead_events_source ON public.dead_events USING btree (source);


--
-- Name: idx_dead_events_tenant_idempotency_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dead_events_tenant_idempotency_key ON public.dead_events USING btree (tenant_id, idempotency_key) WHERE (idempotency_key IS NOT NULL);


--
-- Name: idx_dead_events_tenant_ingested_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dead_events_tenant_ingested_at ON public.dead_events USING btree (tenant_id, ingested_at DESC);


--
-- Name: idx_ephemeral_click_resolution_tenant_click; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ephemeral_click_resolution_tenant_click ON public.ephemeral_click_resolution USING btree (tenant_id, click_id);


--
-- Name: idx_ephemeral_click_resolution_tenant_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ephemeral_click_resolution_tenant_expires ON public.ephemeral_click_resolution USING btree (tenant_id, expires_at);


--
-- Name: idx_ephemeral_order_resolution_tenant_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ephemeral_order_resolution_tenant_expires ON public.ephemeral_order_resolution USING btree (tenant_id, expires_at);


--
-- Name: idx_ephemeral_order_resolution_tenant_order; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ephemeral_order_resolution_tenant_order ON public.ephemeral_order_resolution USING btree (tenant_id, order_id);


--
-- Name: idx_events_processing_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_processing_status ON public.attribution_events USING btree (processing_status, processed_at) WHERE ((processing_status)::text = 'pending'::text);


--
-- Name: idx_events_tenant_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_tenant_timestamp ON public.attribution_events USING btree (tenant_id, event_timestamp DESC);


--
-- Name: idx_explanation_cache_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_explanation_cache_lookup ON public.explanation_cache USING btree (tenant_id, entity_type, entity_id);


--
-- Name: idx_investigation_jobs_min_hold; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_investigation_jobs_min_hold ON public.investigation_jobs USING btree (min_hold_until) WHERE ((status)::text = 'PENDING'::text);


--
-- Name: idx_investigation_jobs_tenant_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_investigation_jobs_tenant_status ON public.investigation_jobs USING btree (tenant_id, status, created_at DESC);


--
-- Name: idx_investigations_tenant_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_investigations_tenant_status ON public.investigations USING btree (tenant_id, status, created_at DESC);


--
-- Name: idx_llm_api_calls_prompt_fingerprint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_api_calls_prompt_fingerprint ON public.llm_api_calls USING btree (tenant_id, prompt_fingerprint, created_at DESC);


--
-- Name: idx_llm_breaker_state_tenant_user_updated; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_breaker_state_tenant_user_updated ON public.llm_breaker_state USING btree (tenant_id, user_id, updated_at DESC);


--
-- Name: idx_llm_budget_reservations_tenant_user_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_budget_reservations_tenant_user_month ON public.llm_budget_reservations USING btree (tenant_id, user_id, month DESC);


--
-- Name: idx_llm_call_audit_decision; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_call_audit_decision ON public.llm_call_audit USING btree (decision, created_at DESC);


--
-- Name: idx_llm_call_audit_prompt_fingerprint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_call_audit_prompt_fingerprint ON public.llm_call_audit USING btree (tenant_id, prompt_fingerprint, created_at DESC);


--
-- Name: idx_llm_call_audit_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_call_audit_request_id ON public.llm_call_audit USING btree (request_id);


--
-- Name: idx_llm_call_audit_tenant_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_call_audit_tenant_created ON public.llm_call_audit USING btree (tenant_id, created_at DESC);


--
-- Name: idx_llm_call_audit_tenant_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_call_audit_tenant_user_created ON public.llm_call_audit USING btree (tenant_id, user_id, created_at DESC);


--
-- Name: idx_llm_calls_tenant_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_calls_tenant_created_at ON public.llm_api_calls USING btree (tenant_id, created_at DESC);


--
-- Name: idx_llm_calls_tenant_endpoint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_calls_tenant_endpoint ON public.llm_api_calls USING btree (tenant_id, endpoint, created_at DESC);


--
-- Name: idx_llm_calls_tenant_user_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_calls_tenant_user_created_at ON public.llm_api_calls USING btree (tenant_id, user_id, created_at DESC);


--
-- Name: idx_llm_failures_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_failures_created_at ON public.llm_validation_failures USING btree (created_at DESC);


--
-- Name: idx_llm_failures_tenant_endpoint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_failures_tenant_endpoint ON public.llm_validation_failures USING btree (tenant_id, endpoint, created_at DESC);


--
-- Name: idx_llm_hourly_shutoff_disabled_until; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_hourly_shutoff_disabled_until ON public.llm_hourly_shutoff_state USING btree (tenant_id, user_id, disabled_until DESC);


--
-- Name: idx_llm_hourly_shutoff_tenant_user_hour; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_hourly_shutoff_tenant_user_hour ON public.llm_hourly_shutoff_state USING btree (tenant_id, user_id, hour_start DESC);


--
-- Name: idx_llm_monthly_budget_state_tenant_user_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_monthly_budget_state_tenant_user_month ON public.llm_monthly_budget_state USING btree (tenant_id, user_id, month DESC);


--
-- Name: idx_llm_monthly_tenant_user_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_monthly_tenant_user_month ON public.llm_monthly_costs USING btree (tenant_id, user_id, month DESC);


--
-- Name: idx_llm_semantic_cache_tenant_user_endpoint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_semantic_cache_tenant_user_endpoint ON public.llm_semantic_cache USING btree (tenant_id, user_id, endpoint, updated_at DESC);


--
-- Name: idx_mv_allocation_summary_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_mv_allocation_summary_key ON public.mv_allocation_summary USING btree (tenant_id, event_id, model_version);


--
-- Name: idx_mv_channel_performance_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_mv_channel_performance_unique ON public.mv_channel_performance USING btree (tenant_id, channel_code, allocation_date);


--
-- Name: idx_mv_daily_revenue_summary_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_mv_daily_revenue_summary_unique ON public.mv_daily_revenue_summary USING btree (tenant_id, revenue_date, state, currency);


--
-- Name: idx_mv_realtime_revenue_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_mv_realtime_revenue_tenant_id ON public.mv_realtime_revenue USING btree (tenant_id);


--
-- Name: idx_mv_reconciliation_status_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_mv_reconciliation_status_tenant_id ON public.mv_reconciliation_status USING btree (tenant_id);


--
-- Name: idx_oauth_handshake_sessions_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_oauth_handshake_sessions_expires_at ON public.oauth_handshake_sessions USING btree (expires_at DESC);


--
-- Name: idx_oauth_handshake_sessions_gc_after; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_oauth_handshake_sessions_gc_after ON public.oauth_handshake_sessions USING btree (gc_after);


--
-- Name: idx_oauth_handshake_sessions_tenant_platform_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_oauth_handshake_sessions_tenant_platform_user_created ON public.oauth_handshake_sessions USING btree (tenant_id, platform, user_id, created_at DESC);


--
-- Name: idx_oauth_handshake_sessions_tenant_state_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_oauth_handshake_sessions_tenant_state_lookup ON public.oauth_handshake_sessions USING btree (tenant_id, state_nonce_hash, status);


--
-- Name: idx_pii_audit_findings_detected_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pii_audit_findings_detected_key ON public.pii_audit_findings USING btree (detected_key);


--
-- Name: idx_pii_audit_findings_table_detected_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pii_audit_findings_table_detected_at ON public.pii_audit_findings USING btree (table_name, detected_at DESC);


--
-- Name: idx_platform_connections_tenant_platform_updated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_platform_connections_tenant_platform_updated_at ON public.platform_connections USING btree (tenant_id, platform, updated_at DESC);


--
-- Name: idx_platform_credentials_refresh_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_platform_credentials_refresh_due ON public.platform_credentials USING btree (tenant_id, lifecycle_status, next_refresh_due_at) WHERE (next_refresh_due_at IS NOT NULL);


--
-- Name: idx_platform_credentials_tenant_lifecycle_updated; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_platform_credentials_tenant_lifecycle_updated ON public.platform_credentials USING btree (tenant_id, lifecycle_status, updated_at DESC);


--
-- Name: idx_platform_credentials_tenant_platform_updated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_platform_credentials_tenant_platform_updated_at ON public.platform_credentials USING btree (tenant_id, platform, updated_at DESC);


--
-- Name: idx_platform_credentials_tenant_revoked_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_platform_credentials_tenant_revoked_at ON public.platform_credentials USING btree (tenant_id, revoked_at DESC) WHERE (revoked_at IS NOT NULL);


--
-- Name: idx_r4_crash_barriers_scenario_wrote_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_r4_crash_barriers_scenario_wrote_at ON public.r4_crash_barriers USING btree (scenario, wrote_at DESC);


--
-- Name: idx_r4_task_attempts_scenario_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_r4_task_attempts_scenario_created_at ON public.r4_task_attempts USING btree (scenario, created_at DESC);


--
-- Name: idx_r4_task_attempts_tenant_task; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_r4_task_attempts_tenant_task ON public.r4_task_attempts USING btree (tenant_id, task_id);


--
-- Name: idx_raw_event_payloads_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_raw_event_payloads_event_id ON public.raw_event_payloads USING btree (event_id);


--
-- Name: idx_raw_event_payloads_payload_json_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_raw_event_payloads_payload_json_gin ON public.raw_event_payloads USING gin (payload_json jsonb_path_ops);


--
-- Name: idx_raw_event_payloads_tenant_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_raw_event_payloads_tenant_created ON public.raw_event_payloads USING btree (tenant_id, created_at DESC);


--
-- Name: idx_raw_event_payloads_tenant_lookup_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_raw_event_payloads_tenant_lookup_hash ON public.raw_event_payloads USING btree (tenant_id, lookup_hash);


--
-- Name: idx_reconciliation_runs_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reconciliation_runs_state ON public.reconciliation_runs USING btree (state);


--
-- Name: idx_reconciliation_runs_tenant_last_run_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reconciliation_runs_tenant_last_run_at ON public.reconciliation_runs USING btree (tenant_id, last_run_at DESC);


--
-- Name: idx_revenue_cache_entries_error_cooldown; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_revenue_cache_entries_error_cooldown ON public.revenue_cache_entries USING btree (error_cooldown_until);


--
-- Name: idx_revenue_cache_entries_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_revenue_cache_entries_expires_at ON public.revenue_cache_entries USING btree (expires_at);


--
-- Name: idx_revenue_ledger_is_verified; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_revenue_ledger_is_verified ON public.revenue_ledger USING btree (is_verified) WHERE (is_verified = true);


--
-- Name: idx_revenue_ledger_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_revenue_ledger_state ON public.revenue_ledger USING btree (state);


--
-- Name: idx_revenue_ledger_tenant_allocation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_revenue_ledger_tenant_allocation_id ON public.revenue_ledger USING btree (tenant_id, allocation_id) WHERE (allocation_id IS NOT NULL);


--
-- Name: idx_revenue_ledger_tenant_order_reconciliation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_revenue_ledger_tenant_order_reconciliation ON public.revenue_ledger USING btree (tenant_id, order_id, created_at DESC) WHERE (order_id IS NOT NULL);


--
-- Name: idx_revenue_ledger_tenant_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_revenue_ledger_tenant_state ON public.revenue_ledger USING btree (tenant_id, state, created_at DESC);


--
-- Name: idx_revenue_ledger_tenant_updated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_revenue_ledger_tenant_updated_at ON public.revenue_ledger USING btree (tenant_id, updated_at DESC);


--
-- Name: idx_revenue_ledger_transaction_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_revenue_ledger_transaction_id ON public.revenue_ledger USING btree (transaction_id);


--
-- Name: idx_revenue_state_transitions_ledger_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_revenue_state_transitions_ledger_id ON public.revenue_state_transitions USING btree (ledger_id, transitioned_at DESC);


--
-- Name: idx_revenue_state_transitions_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_revenue_state_transitions_tenant_id ON public.revenue_state_transitions USING btree (tenant_id, transitioned_at DESC);


--
-- Name: idx_session_authority_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_session_authority_active ON public.session_authority USING btree (tenant_id, session_id, expires_at DESC) WHERE (invalidated_at IS NULL);


--
-- Name: idx_session_authority_tenant_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_session_authority_tenant_expires ON public.session_authority USING btree (tenant_id, expires_at DESC);


--
-- Name: idx_session_authority_tenant_last_seen; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_session_authority_tenant_last_seen ON public.session_authority USING btree (tenant_id, last_seen_at DESC);


--
-- Name: idx_tenant_membership_roles_tenant_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tenant_membership_roles_tenant_created_at ON public.tenant_membership_roles USING btree (tenant_id, created_at DESC);


--
-- Name: idx_tenant_memberships_tenant_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tenant_memberships_tenant_created_at ON public.tenant_memberships USING btree (tenant_id, created_at DESC);


--
-- Name: idx_tenant_memberships_user_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tenant_memberships_user_created_at ON public.tenant_memberships USING btree (user_id, created_at DESC);


--
-- Name: idx_tenants_api_key_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_tenants_api_key_hash ON public.tenants USING btree (api_key_hash);


--
-- Name: idx_tenants_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tenants_name ON public.tenants USING btree (name);


--
-- Name: idx_tool_calls_investigation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tool_calls_investigation ON public.investigation_tool_calls USING btree (investigation_id, created_at);


--
-- Name: idx_tool_calls_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tool_calls_tenant ON public.investigation_tool_calls USING btree (tenant_id, created_at DESC);


--
-- Name: idx_trust_access_log_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trust_access_log_created ON public.trust_access_log USING btree (tenant_id, created_at DESC);


--
-- Name: idx_trust_access_log_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trust_access_log_subject ON public.trust_access_log USING btree (tenant_id, subject_type, subject_ref_hash);


--
-- Name: idx_trust_issuance_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trust_issuance_subject ON public.trust_envelope_issuance_log USING btree (tenant_id, subject_type, subject_ref_hash);


--
-- Name: idx_trust_rate_limit_state_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trust_rate_limit_state_lookup ON public.trust_rate_limit_state USING btree (tenant_id, agent_client_id, window_ended_at);


--
-- Name: idx_trust_replay_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trust_replay_created ON public.trust_replay_events USING btree (tenant_id, created_at DESC);


--
-- Name: idx_trust_request_nonces_tenant_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trust_request_nonces_tenant_created ON public.trust_request_nonces USING btree (tenant_id, created_at DESC);


--
-- Name: idx_trust_request_nonces_tenant_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trust_request_nonces_tenant_expires ON public.trust_request_nonces USING btree (tenant_id, expires_at);


--
-- Name: idx_trust_scope_denial_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trust_scope_denial_created ON public.trust_scope_denial_events USING btree (tenant_id, created_at DESC);


--
-- Name: idx_webhook_ingress_identities_tenant_provider_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_webhook_ingress_identities_tenant_provider_created ON public.webhook_ingress_identities USING btree (tenant_id, provider, created_at DESC);


--
-- Name: idx_webhook_ingress_identities_tenant_reference; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_webhook_ingress_identities_tenant_reference ON public.webhook_ingress_identities USING btree (tenant_id, normalized_commerce_reference_kind, normalized_commerce_reference_value);


--
-- Name: idx_webhook_ingress_identities_tenant_verified_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_webhook_ingress_identities_tenant_verified_state ON public.webhook_ingress_identities USING btree (tenant_id, verified_commerce_ingress_state, event_timestamp DESC);


--
-- Name: idx_worker_failed_jobs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_worker_failed_jobs_status ON public.worker_failed_jobs USING btree (status, failed_at);


--
-- Name: idx_worker_failed_jobs_task_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_worker_failed_jobs_task_name ON public.worker_failed_jobs USING btree (task_name);


--
-- Name: idx_worker_side_effects_tenant_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_worker_side_effects_tenant_created_at ON public.worker_side_effects USING btree (tenant_id, created_at DESC);


--
-- Name: ix_b24_fit_policy_replan_lineage_fit; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_b24_fit_policy_replan_lineage_fit ON public.b24_fit_policy_replan_lineage USING btree (tenant_id, fit_id, transition_sequence);


--
-- Name: ix_b27_explanation_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_b27_explanation_subject ON public.b27_explanation_materializations USING btree (tenant_id, subject_type, subject_ref_hash, stale);


--
-- Name: ix_celery_taskmeta_task_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_celery_taskmeta_task_id ON public.celery_taskmeta USING btree (task_id);


--
-- Name: ix_celery_tasksetmeta_taskset_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_celery_tasksetmeta_taskset_id ON public.celery_tasksetmeta USING btree (taskset_id);


--
-- Name: ix_kombu_message_timestamp_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kombu_message_timestamp_id ON public.kombu_message USING btree ("timestamp", id);


--
-- Name: ix_kombu_message_visible; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kombu_message_visible ON public.kombu_message USING btree (visible);


--
-- Name: ix_public_celery_task_failures_task_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_public_celery_task_failures_task_id ON public.worker_failed_jobs USING btree (task_id);


--
-- Name: ix_public_celery_task_failures_task_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_public_celery_task_failures_task_name ON public.worker_failed_jobs USING btree (task_name);


--
-- Name: ix_public_celery_task_failures_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_public_celery_task_failures_tenant_id ON public.worker_failed_jobs USING btree (tenant_id);


--
-- Name: ix_trust_access_log_issuance_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trust_access_log_issuance_state ON public.trust_access_log USING btree (tenant_id, issuance_state);


--
-- Name: ix_trust_export_artifact_attempts_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trust_export_artifact_attempts_lookup ON public.trust_export_artifact_attempts USING btree (tenant_id, request_binding_hash, page_start, attempt_number DESC);


--
-- Name: ix_trust_issuance_attempts_recovery; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trust_issuance_attempts_recovery ON public.trust_issuance_attempts USING btree (tenant_id, attempt_state, updated_at, id);


--
-- Name: ix_trust_issuance_attempts_tenant_audit; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trust_issuance_attempts_tenant_audit ON public.trust_issuance_attempts USING btree (tenant_id, audit_ref, attempt_number DESC);


--
-- Name: uq_b23_exception_records_one_open_per_verdict; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_b23_exception_records_one_open_per_verdict ON public.b23_exception_records USING btree (tenant_id, match_verdict_id) WHERE ((status)::text = ANY ((ARRAY['open'::character varying, 'acknowledged'::character varying])::text[]));


--
-- Name: uq_b24_fit_dispatch_outbox_attempt; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_b24_fit_dispatch_outbox_attempt ON public.b24_fit_dispatch_outbox USING btree (tenant_id, attempt_id);


--
-- Name: uq_platform_connections_tenant_platform_account; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_platform_connections_tenant_platform_account ON public.platform_connections USING btree (tenant_id, platform, platform_account_id);


--
-- Name: uq_platform_credentials_tenant_platform_connection; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_platform_credentials_tenant_platform_connection ON public.platform_credentials USING btree (tenant_id, platform, platform_connection_id);


--
-- Name: ux_r4_crash_barriers_tenant_task_attempt; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_r4_crash_barriers_tenant_task_attempt ON public.r4_crash_barriers USING btree (tenant_id, task_id, attempt_no);


--
-- Name: ux_r4_task_attempts_tenant_task_attempt; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_r4_task_attempts_tenant_task_attempt ON public.r4_task_attempts USING btree (tenant_id, task_id, attempt_no);


--
-- Name: ux_worker_side_effects_tenant_task_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_worker_side_effects_tenant_task_id ON public.worker_side_effects USING btree (tenant_id, task_id);


--
-- Name: bayesian_artifacts_p00_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p00_pkey;


--
-- Name: bayesian_artifacts_p00_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p00_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p00_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p00_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p00_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p00_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p00_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p00_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p00_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p00_tenant_id_idx;


--
-- Name: bayesian_artifacts_p01_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p01_pkey;


--
-- Name: bayesian_artifacts_p01_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p01_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p01_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p01_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p01_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p01_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p01_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p01_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p01_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p01_tenant_id_idx;


--
-- Name: bayesian_artifacts_p02_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p02_pkey;


--
-- Name: bayesian_artifacts_p02_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p02_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p02_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p02_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p02_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p02_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p02_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p02_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p02_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p02_tenant_id_idx;


--
-- Name: bayesian_artifacts_p03_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p03_pkey;


--
-- Name: bayesian_artifacts_p03_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p03_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p03_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p03_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p03_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p03_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p03_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p03_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p03_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p03_tenant_id_idx;


--
-- Name: bayesian_artifacts_p04_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p04_pkey;


--
-- Name: bayesian_artifacts_p04_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p04_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p04_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p04_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p04_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p04_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p04_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p04_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p04_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p04_tenant_id_idx;


--
-- Name: bayesian_artifacts_p05_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p05_pkey;


--
-- Name: bayesian_artifacts_p05_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p05_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p05_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p05_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p05_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p05_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p05_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p05_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p05_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p05_tenant_id_idx;


--
-- Name: bayesian_artifacts_p06_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p06_pkey;


--
-- Name: bayesian_artifacts_p06_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p06_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p06_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p06_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p06_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p06_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p06_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p06_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p06_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p06_tenant_id_idx;


--
-- Name: bayesian_artifacts_p07_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p07_pkey;


--
-- Name: bayesian_artifacts_p07_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p07_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p07_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p07_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p07_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p07_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p07_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p07_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p07_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p07_tenant_id_idx;


--
-- Name: bayesian_artifacts_p08_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p08_pkey;


--
-- Name: bayesian_artifacts_p08_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p08_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p08_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p08_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p08_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p08_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p08_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p08_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p08_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p08_tenant_id_idx;


--
-- Name: bayesian_artifacts_p09_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p09_pkey;


--
-- Name: bayesian_artifacts_p09_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p09_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p09_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p09_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p09_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p09_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p09_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p09_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p09_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p09_tenant_id_idx;


--
-- Name: bayesian_artifacts_p10_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p10_pkey;


--
-- Name: bayesian_artifacts_p10_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p10_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p10_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p10_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p10_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p10_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p10_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p10_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p10_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p10_tenant_id_idx;


--
-- Name: bayesian_artifacts_p11_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p11_pkey;


--
-- Name: bayesian_artifacts_p11_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p11_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p11_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p11_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p11_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p11_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p11_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p11_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p11_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p11_tenant_id_idx;


--
-- Name: bayesian_artifacts_p12_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p12_pkey;


--
-- Name: bayesian_artifacts_p12_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p12_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p12_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p12_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p12_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p12_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p12_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p12_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p12_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p12_tenant_id_idx;


--
-- Name: bayesian_artifacts_p13_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p13_pkey;


--
-- Name: bayesian_artifacts_p13_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p13_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p13_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p13_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p13_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p13_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p13_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p13_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p13_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p13_tenant_id_idx;


--
-- Name: bayesian_artifacts_p14_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p14_pkey;


--
-- Name: bayesian_artifacts_p14_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p14_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p14_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p14_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p14_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p14_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p14_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p14_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p14_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p14_tenant_id_idx;


--
-- Name: bayesian_artifacts_p15_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_artifacts_pkey ATTACH PARTITION public.bayesian_artifacts_p15_pkey;


--
-- Name: bayesian_artifacts_p15_tenant_id_artifact_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_hash ATTACH PARTITION public.bayesian_artifacts_p15_tenant_id_artifact_hash_idx;


--
-- Name: bayesian_artifacts_p15_tenant_id_artifact_ref_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p15_tenant_id_artifact_ref_idx;


--
-- Name: bayesian_artifacts_p15_tenant_id_artifact_ref_key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_artifacts_tenant_artifact_ref ATTACH PARTITION public.bayesian_artifacts_p15_tenant_id_artifact_ref_key;


--
-- Name: bayesian_artifacts_p15_tenant_id_fit_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_fit ATTACH PARTITION public.bayesian_artifacts_p15_tenant_id_fit_id_idx;


--
-- Name: bayesian_artifacts_p15_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_artifacts_tenant_id ATTACH PARTITION public.bayesian_artifacts_p15_tenant_id_idx;


--
-- Name: bayesian_model_fits_p00_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p00_pkey;


--
-- Name: bayesian_model_fits_p00_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p00_tenant_id_idx;


--
-- Name: bayesian_model_fits_p00_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p00_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p00_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p00_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p00_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p00_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p00_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p00_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p00_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p00_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p00_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p00_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p00_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p00_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p01_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p01_pkey;


--
-- Name: bayesian_model_fits_p01_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p01_tenant_id_idx;


--
-- Name: bayesian_model_fits_p01_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p01_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p01_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p01_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p01_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p01_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p01_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p01_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p01_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p01_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p01_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p01_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p01_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p01_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p02_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p02_pkey;


--
-- Name: bayesian_model_fits_p02_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p02_tenant_id_idx;


--
-- Name: bayesian_model_fits_p02_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p02_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p02_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p02_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p02_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p02_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p02_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p02_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p02_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p02_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p02_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p02_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p02_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p02_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p03_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p03_pkey;


--
-- Name: bayesian_model_fits_p03_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p03_tenant_id_idx;


--
-- Name: bayesian_model_fits_p03_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p03_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p03_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p03_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p03_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p03_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p03_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p03_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p03_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p03_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p03_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p03_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p03_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p03_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p04_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p04_pkey;


--
-- Name: bayesian_model_fits_p04_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p04_tenant_id_idx;


--
-- Name: bayesian_model_fits_p04_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p04_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p04_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p04_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p04_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p04_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p04_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p04_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p04_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p04_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p04_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p04_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p04_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p04_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p05_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p05_pkey;


--
-- Name: bayesian_model_fits_p05_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p05_tenant_id_idx;


--
-- Name: bayesian_model_fits_p05_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p05_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p05_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p05_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p05_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p05_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p05_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p05_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p05_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p05_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p05_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p05_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p05_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p05_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p06_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p06_pkey;


--
-- Name: bayesian_model_fits_p06_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p06_tenant_id_idx;


--
-- Name: bayesian_model_fits_p06_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p06_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p06_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p06_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p06_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p06_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p06_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p06_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p06_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p06_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p06_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p06_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p06_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p06_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p07_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p07_pkey;


--
-- Name: bayesian_model_fits_p07_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p07_tenant_id_idx;


--
-- Name: bayesian_model_fits_p07_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p07_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p07_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p07_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p07_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p07_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p07_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p07_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p07_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p07_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p07_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p07_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p07_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p07_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p08_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p08_pkey;


--
-- Name: bayesian_model_fits_p08_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p08_tenant_id_idx;


--
-- Name: bayesian_model_fits_p08_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p08_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p08_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p08_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p08_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p08_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p08_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p08_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p08_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p08_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p08_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p08_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p08_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p08_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p09_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p09_pkey;


--
-- Name: bayesian_model_fits_p09_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p09_tenant_id_idx;


--
-- Name: bayesian_model_fits_p09_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p09_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p09_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p09_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p09_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p09_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p09_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p09_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p09_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p09_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p09_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p09_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p09_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p09_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p10_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p10_pkey;


--
-- Name: bayesian_model_fits_p10_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p10_tenant_id_idx;


--
-- Name: bayesian_model_fits_p10_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p10_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p10_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p10_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p10_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p10_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p10_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p10_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p10_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p10_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p10_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p10_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p10_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p10_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p11_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p11_pkey;


--
-- Name: bayesian_model_fits_p11_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p11_tenant_id_idx;


--
-- Name: bayesian_model_fits_p11_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p11_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p11_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p11_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p11_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p11_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p11_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p11_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p11_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p11_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p11_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p11_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p11_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p11_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p12_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p12_pkey;


--
-- Name: bayesian_model_fits_p12_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p12_tenant_id_idx;


--
-- Name: bayesian_model_fits_p12_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p12_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p12_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p12_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p12_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p12_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p12_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p12_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p12_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p12_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p12_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p12_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p12_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p12_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p13_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p13_pkey;


--
-- Name: bayesian_model_fits_p13_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p13_tenant_id_idx;


--
-- Name: bayesian_model_fits_p13_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p13_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p13_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p13_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p13_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p13_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p13_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p13_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p13_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p13_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p13_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p13_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p13_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p13_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p14_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p14_pkey;


--
-- Name: bayesian_model_fits_p14_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p14_tenant_id_idx;


--
-- Name: bayesian_model_fits_p14_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p14_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p14_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p14_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p14_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p14_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p14_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p14_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p14_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p14_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p14_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p14_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p14_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p14_tenant_id_status_idx;


--
-- Name: bayesian_model_fits_p15_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.bayesian_model_fits_pkey ATTACH PARTITION public.bayesian_model_fits_p15_pkey;


--
-- Name: bayesian_model_fits_p15_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_id ATTACH PARTITION public.bayesian_model_fits_p15_tenant_id_idx;


--
-- Name: bayesian_model_fits_p15_tenant_id_model_type_eligibility_st_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_eligibility ATTACH PARTITION public.bayesian_model_fits_p15_tenant_id_model_type_eligibility_st_idx;


--
-- Name: bayesian_model_fits_p15_tenant_id_model_type_fallback_reaso_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_fallback ATTACH PARTITION public.bayesian_model_fits_p15_tenant_id_model_type_fallback_reaso_idx;


--
-- Name: bayesian_model_fits_p15_tenant_id_model_type_model_version__key; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.uq_bayesian_model_fits_tenant_model_window_snapshot ATTACH PARTITION public.bayesian_model_fits_p15_tenant_id_model_type_model_version__key;


--
-- Name: bayesian_model_fits_p15_tenant_id_model_type_source_window__idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window ATTACH PARTITION public.bayesian_model_fits_p15_tenant_id_model_type_source_window__idx;


--
-- Name: bayesian_model_fits_p15_tenant_id_model_type_source_window_idx1; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_model_window_latest ATTACH PARTITION public.bayesian_model_fits_p15_tenant_id_model_type_source_window_idx1;


--
-- Name: bayesian_model_fits_p15_tenant_id_source_snapshot_hash_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_source_snapshot_hash ATTACH PARTITION public.bayesian_model_fits_p15_tenant_id_source_snapshot_hash_idx;


--
-- Name: bayesian_model_fits_p15_tenant_id_status_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_bayesian_model_fits_tenant_status ATTACH PARTITION public.bayesian_model_fits_p15_tenant_id_status_idx;


--
-- Name: agent_scope_grants trg_agent_scope_grants_reject_reserved; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_agent_scope_grants_reject_reserved BEFORE INSERT OR UPDATE OF scope_value ON public.agent_scope_grants FOR EACH ROW EXECUTE FUNCTION public.reject_reserved_trust_action_scope();


--
-- Name: attribution_allocations trg_allocations_channel_correction_audit; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_allocations_channel_correction_audit AFTER UPDATE OF channel_code ON public.attribution_allocations FOR EACH ROW WHEN ((old.channel_code IS DISTINCT FROM new.channel_code)) EXECUTE FUNCTION public.fn_log_channel_assignment_correction();


--
-- Name: attribution_commerce_identities trg_b23_p0_prune_attribution_commerce_identities; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b23_p0_prune_attribution_commerce_identities AFTER INSERT OR UPDATE OF last_observed_at ON public.attribution_commerce_identities FOR EACH STATEMENT EXECUTE FUNCTION public.fn_b23_p0_prune_attribution_commerce_identities_trigger();


--
-- Name: attribution_allocations trg_b23_project_allocation_verification; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b23_project_allocation_verification BEFORE INSERT OR UPDATE OF tenant_id, event_id, verified, verification_source, verification_timestamp ON public.attribution_allocations FOR EACH ROW EXECUTE FUNCTION public.b23_project_allocation_verification();


--
-- Name: b23_match_verdicts trg_b23_refresh_allocation_verification_insert; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b23_refresh_allocation_verification_insert AFTER INSERT ON public.b23_match_verdicts FOR EACH ROW EXECUTE FUNCTION public.b23_refresh_allocation_verification();


--
-- Name: b23_match_verdicts trg_b23_refresh_allocation_verification_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b23_refresh_allocation_verification_update AFTER UPDATE OF status, attribution_event_id, last_transition_at ON public.b23_match_verdicts FOR EACH ROW WHEN ((((old.status)::text IS DISTINCT FROM (new.status)::text) OR (old.attribution_event_id IS DISTINCT FROM new.attribution_event_id) OR (old.last_transition_at IS DISTINCT FROM new.last_transition_at))) EXECUTE FUNCTION public.b23_refresh_allocation_verification();


--
-- Name: b23_match_verdicts trg_b23_verdict_authorship_insert; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b23_verdict_authorship_insert BEFORE INSERT ON public.b23_match_verdicts FOR EACH ROW EXECUTE FUNCTION public.b23_enforce_verdict_authorship();


--
-- Name: b23_match_verdicts trg_b23_verdict_authorship_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b23_verdict_authorship_update BEFORE UPDATE ON public.b23_match_verdicts FOR EACH ROW WHEN ((((old.status)::text IS DISTINCT FROM (new.status)::text) OR (old.confirmed_at IS DISTINCT FROM new.confirmed_at) OR (old.adjusted_at IS DISTINCT FROM new.adjusted_at) OR (old.unmatched_marked_at IS DISTINCT FROM new.unmatched_marked_at) OR ((old.match_quality)::text IS DISTINCT FROM (new.match_quality)::text) OR (old.attributed_amount_minor IS DISTINCT FROM new.attributed_amount_minor) OR (old.verified_amount_minor IS DISTINCT FROM new.verified_amount_minor) OR (old.canonical_expected_gross_amount_minor IS DISTINCT FROM new.canonical_expected_gross_amount_minor) OR (old.canonical_captured_gross_amount_minor IS DISTINCT FROM new.canonical_captured_gross_amount_minor) OR (old.canonical_net_verified_amount_minor IS DISTINCT FROM new.canonical_net_verified_amount_minor) OR (old.discrepancy_amount_minor IS DISTINCT FROM new.discrepancy_amount_minor) OR (old.discrepancy_ratio_bps IS DISTINCT FROM new.discrepancy_ratio_bps) OR ((old.discrepancy_band)::text IS DISTINCT FROM (new.discrepancy_band)::text))) EXECUTE FUNCTION public.b23_enforce_verdict_authorship();


--
-- Name: b24_dirty_events trg_b24_dirty_event_authority; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_dirty_event_authority BEFORE UPDATE ON public.b24_dirty_events FOR EACH ROW WHEN (((new.tenant_id IS DISTINCT FROM old.tenant_id) OR ((new.model_type)::text IS DISTINCT FROM (old.model_type)::text) OR ((new.model_version)::text IS DISTINCT FROM (old.model_version)::text) OR (new.source_window_start IS DISTINCT FROM old.source_window_start) OR (new.source_window_end IS DISTINCT FROM old.source_window_end) OR ((new.dirty_reason)::text IS DISTINCT FROM (old.dirty_reason)::text) OR ((new.source_family)::text IS DISTINCT FROM (old.source_family)::text) OR ((new.event_hash)::text IS DISTINCT FROM (old.event_hash)::text) OR ((new.source_event_id)::text IS DISTINCT FROM (old.source_event_id)::text) OR (new.created_at IS DISTINCT FROM old.created_at) OR ((new.source_snapshot_hash)::text IS DISTINCT FROM (old.source_snapshot_hash)::text))) EXECUTE FUNCTION public.b24_enforce_dirty_event_authority();


--
-- Name: bayesian_artifacts trg_b24_dispatch_fence_artifacts; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_dispatch_fence_artifacts BEFORE INSERT OR DELETE OR UPDATE ON public.bayesian_artifacts FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_dispatch_fence('artifact');


--
-- Name: bayesian_model_fits trg_b24_dispatch_fence_fits; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_dispatch_fence_fits BEFORE INSERT OR DELETE OR UPDATE ON public.bayesian_model_fits FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_dispatch_fence('fit');


--
-- Name: bayesian_artifacts trg_b24_enforce_artifact_lifecycle; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_enforce_artifact_lifecycle BEFORE UPDATE OF lifecycle_status ON public.bayesian_artifacts FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_artifact_lifecycle();


--
-- Name: b24_dirty_events trg_b24_enforce_dirty_event_lifecycle; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_enforce_dirty_event_lifecycle BEFORE UPDATE ON public.b24_dirty_events FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_dirty_event_lifecycle();


--
-- Name: bayesian_model_fits trg_b24_evidence_temporal_plausibility; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_evidence_temporal_plausibility BEFORE INSERT OR UPDATE ON public.bayesian_model_fits FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_evidence_temporal_plausibility();


--
-- Name: attribution_events trg_b24_invalidate_attribution_events_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_invalidate_attribution_events_delete AFTER DELETE ON public.attribution_events REFERENCING OLD TABLE AS old_rows FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_attribution_events_delete();


--
-- Name: attribution_events trg_b24_invalidate_attribution_events_insert; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_invalidate_attribution_events_insert AFTER INSERT ON public.attribution_events REFERENCING NEW TABLE AS new_rows FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_attribution_events_insert();


--
-- Name: attribution_events trg_b24_invalidate_attribution_events_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_invalidate_attribution_events_update AFTER UPDATE ON public.attribution_events REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_attribution_events_update();


--
-- Name: b23_revenue_events trg_b24_invalidate_b23_revenue_events_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_invalidate_b23_revenue_events_delete AFTER DELETE ON public.b23_revenue_events REFERENCING OLD TABLE AS old_rows FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_b23_revenue_events_delete();


--
-- Name: b23_revenue_events trg_b24_invalidate_b23_revenue_events_insert; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_invalidate_b23_revenue_events_insert AFTER INSERT ON public.b23_revenue_events REFERENCING NEW TABLE AS new_rows FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_b23_revenue_events_insert();


--
-- Name: b23_revenue_events trg_b24_invalidate_b23_revenue_events_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_invalidate_b23_revenue_events_update AFTER UPDATE ON public.b23_revenue_events REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_b23_revenue_events_update();


--
-- Name: attribution_allocations trg_b24_mark_allocation_financial_window_dirty; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_mark_allocation_financial_window_dirty AFTER INSERT OR DELETE OR UPDATE ON public.attribution_allocations FOR EACH ROW EXECUTE FUNCTION public.b24_mark_allocation_financial_window_dirty();


--
-- Name: b23_match_verdicts trg_b24_mark_verdict_financial_window_dirty; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_mark_verdict_financial_window_dirty AFTER INSERT OR DELETE OR UPDATE ON public.b23_match_verdicts FOR EACH ROW EXECUTE FUNCTION public.b24_mark_verdict_financial_window_dirty();


--
-- Name: b24_inference_policy_registry trg_b24_policy_registry_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_policy_registry_immutable BEFORE DELETE OR UPDATE ON public.b24_inference_policy_registry FOR EACH ROW EXECUTE FUNCTION public.b24_reject_policy_registry_rewrite();


--
-- Name: b24_fit_policy_replan_lineage trg_b24_replan_lineage_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_replan_lineage_append_only BEFORE DELETE OR UPDATE ON public.b24_fit_policy_replan_lineage FOR EACH ROW EXECUTE FUNCTION public.b24_reject_replan_lineage_mutation();


--
-- Name: b24_dirty_events trg_b24_signal_fit_planner_wakeup; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_signal_fit_planner_wakeup AFTER INSERT OR UPDATE OF status ON public.b24_dirty_events FOR EACH ROW EXECUTE FUNCTION public.b24_signal_fit_planner_wakeup_coalesced();


--
-- Name: bayesian_model_fits trg_b24_terminal_fit_truth; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b24_terminal_fit_truth BEFORE UPDATE ON public.bayesian_model_fits FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_terminal_fit_truth();


--
-- Name: b27_explanation_materializations trg_b27_explanation_consequence; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b27_explanation_consequence BEFORE INSERT ON public.b27_explanation_materializations FOR EACH ROW EXECUTE FUNCTION public.b27_enforce_explanation_consequence();


--
-- Name: b27_explanation_materializations trg_b27_materialization_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b27_materialization_immutable BEFORE DELETE OR UPDATE ON public.b27_explanation_materializations FOR EACH ROW EXECUTE FUNCTION public.b27_enforce_materialization_immutability();


--
-- Name: trust_envelope_issuance_log trg_b27_supersede_stale_explanations; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b27_supersede_stale_explanations AFTER INSERT ON public.trust_envelope_issuance_log FOR EACH ROW EXECUTE FUNCTION public.b27_supersede_stale_explanations();


--
-- Name: b28_simulation_results trg_b28_allocation_conservation; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b28_allocation_conservation BEFORE INSERT OR UPDATE ON public.b28_simulation_results FOR EACH ROW EXECUTE FUNCTION public.b28_enforce_allocation_conservation();


--
-- Name: b28_proposals trg_b28_proposal_consequence; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b28_proposal_consequence BEFORE INSERT ON public.b28_proposals FOR EACH ROW EXECUTE FUNCTION public.b28_enforce_proposal_consequence();


--
-- Name: b28_proposals trg_b28_proposals_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b28_proposals_immutable BEFORE DELETE OR UPDATE ON public.b28_proposals FOR EACH ROW EXECUTE FUNCTION public.b28_enforce_downstream_immutability();


--
-- Name: b28_simulation_requests trg_b28_request_consequence; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b28_request_consequence BEFORE INSERT ON public.b28_simulation_requests FOR EACH ROW EXECUTE FUNCTION public.b28_enforce_request_consequence();


--
-- Name: b28_simulation_results trg_b28_result_consequence; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b28_result_consequence BEFORE INSERT ON public.b28_simulation_results FOR EACH ROW EXECUTE FUNCTION public.b28_enforce_result_consequence();


--
-- Name: b28_simulation_requests trg_b28_simulation_requests_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b28_simulation_requests_immutable BEFORE DELETE OR UPDATE ON public.b28_simulation_requests FOR EACH ROW EXECUTE FUNCTION public.b28_enforce_downstream_immutability();


--
-- Name: b28_simulation_results trg_b28_simulation_results_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_b28_simulation_results_immutable BEFORE DELETE OR UPDATE ON public.b28_simulation_results FOR EACH ROW EXECUTE FUNCTION public.b28_enforce_downstream_immutability();


--
-- Name: attribution_events trg_bind_session_authority_from_event; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_bind_session_authority_from_event BEFORE INSERT ON public.attribution_events FOR EACH ROW EXECUTE FUNCTION public.fn_bind_session_authority_from_event();


--
-- Name: dead_events trg_block_worker_mutation_dead_events; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_block_worker_mutation_dead_events BEFORE INSERT OR DELETE OR UPDATE ON public.dead_events FOR EACH ROW EXECUTE FUNCTION public.fn_block_worker_ingestion_mutation();


--
-- Name: attribution_events trg_block_worker_mutation_events; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_block_worker_mutation_events BEFORE INSERT OR DELETE OR UPDATE ON public.attribution_events FOR EACH ROW EXECUTE FUNCTION public.fn_block_worker_ingestion_mutation();


--
-- Name: channel_taxonomy trg_channel_taxonomy_state_audit; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_channel_taxonomy_state_audit AFTER UPDATE OF state ON public.channel_taxonomy FOR EACH ROW WHEN (((old.state)::text IS DISTINCT FROM (new.state)::text)) EXECUTE FUNCTION public.fn_log_channel_state_change();


--
-- Name: attribution_allocations trg_check_allocation_sum; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_check_allocation_sum AFTER INSERT ON public.attribution_allocations REFERENCING NEW TABLE AS newrows FOR EACH STATEMENT EXECUTE FUNCTION public.check_allocation_sum_stmt_insert();


--
-- Name: attribution_allocations trg_check_allocation_sum_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_check_allocation_sum_delete AFTER DELETE ON public.attribution_allocations REFERENCING OLD TABLE AS oldrows FOR EACH STATEMENT EXECUTE FUNCTION public.check_allocation_sum_stmt_delete();


--
-- Name: attribution_allocations trg_check_allocation_sum_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_check_allocation_sum_update AFTER UPDATE ON public.attribution_allocations REFERENCING OLD TABLE AS oldrows NEW TABLE AS newrows FOR EACH STATEMENT EXECUTE FUNCTION public.check_allocation_sum_stmt_update();


--
-- Name: compliance_audit_ledger trg_compliance_audit_ledger_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_compliance_audit_ledger_append_only BEFORE DELETE OR UPDATE ON public.compliance_audit_ledger FOR EACH ROW EXECUTE FUNCTION public.fn_compliance_audit_ledger_append_only();


--
-- Name: attribution_events trg_events_prevent_mutation; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_events_prevent_mutation BEFORE DELETE OR UPDATE ON public.attribution_events FOR EACH ROW EXECUTE FUNCTION public.fn_events_prevent_mutation();


--
-- Name: attribution_events trg_guard_attribution_events_payload_identity; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_guard_attribution_events_payload_identity BEFORE INSERT ON public.attribution_events FOR EACH ROW EXECUTE FUNCTION public.fn_guard_attribution_events_payload_identity();


--
-- Name: revenue_ledger trg_ledger_prevent_mutation; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ledger_prevent_mutation BEFORE DELETE OR UPDATE ON public.revenue_ledger FOR EACH ROW EXECUTE FUNCTION public.fn_ledger_prevent_mutation();


--
-- Name: llm_call_audit trg_llm_call_audit_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_llm_call_audit_append_only BEFORE DELETE OR UPDATE ON public.llm_call_audit FOR EACH ROW EXECUTE FUNCTION public.fn_llm_call_audit_append_only();


--
-- Name: attribution_events trg_pii_guardrail_attribution_events; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_pii_guardrail_attribution_events BEFORE INSERT ON public.attribution_events FOR EACH ROW EXECUTE FUNCTION public.fn_enforce_pii_guardrail();


--
-- Name: dead_events trg_pii_guardrail_dead_events; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_pii_guardrail_dead_events BEFORE INSERT ON public.dead_events FOR EACH ROW EXECUTE FUNCTION public.fn_enforce_pii_guardrail();


--
-- Name: revenue_ledger trg_pii_guardrail_revenue_ledger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_pii_guardrail_revenue_ledger BEFORE INSERT ON public.revenue_ledger FOR EACH ROW EXECUTE FUNCTION public.fn_enforce_pii_guardrail();


--
-- Name: revenue_ledger trg_revenue_ledger_state_audit; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_revenue_ledger_state_audit AFTER UPDATE OF state ON public.revenue_ledger FOR EACH ROW WHEN (((old.state)::text IS DISTINCT FROM (new.state)::text)) EXECUTE FUNCTION public.fn_log_revenue_state_change();


--
-- Name: trust_access_log trg_trust_access_log_issuance_authority_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_trust_access_log_issuance_authority_guard BEFORE INSERT OR UPDATE ON public.trust_access_log FOR EACH ROW EXECUTE FUNCTION public.trust_access_log_issuance_authority_guard();


--
-- Name: trust_access_log trg_trust_access_log_witness_immutability; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_trust_access_log_witness_immutability BEFORE UPDATE ON public.trust_access_log FOR EACH ROW EXECUTE FUNCTION public.trust_access_log_witness_immutability_guard();


--
-- Name: trust_export_artifact_attempts trg_trust_export_artifact_attempt_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_trust_export_artifact_attempt_guard BEFORE INSERT OR UPDATE ON public.trust_export_artifact_attempts FOR EACH ROW EXECUTE FUNCTION public.trust_export_artifact_attempt_guard();


--
-- Name: trust_issuance_attempts trg_trust_issuance_attempt_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_trust_issuance_attempt_guard BEFORE INSERT OR UPDATE ON public.trust_issuance_attempts FOR EACH ROW EXECUTE FUNCTION public.trust_issuance_attempt_guard();


--
-- Name: trust_envelope_issuance_log trg_trust_issuance_consequence_authority; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_trust_issuance_consequence_authority BEFORE INSERT ON public.trust_envelope_issuance_log FOR EACH ROW EXECUTE FUNCTION public.trust_enforce_issuance_consequence_authority();


--
-- Name: trust_envelope_issuance_log trg_trust_issuance_history_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_trust_issuance_history_immutable BEFORE DELETE OR UPDATE ON public.trust_envelope_issuance_log FOR EACH ROW EXECUTE FUNCTION public.trust_enforce_issuance_history_immutable();


--
-- Name: bayesian_model_fits trg_y_b24_c11_policy_provenance; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_y_b24_c11_policy_provenance BEFORE INSERT OR UPDATE ON public.bayesian_model_fits FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_c11_policy_provenance();


--
-- Name: bayesian_model_fits trg_z_b24_policy_bundle_write_authority; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_z_b24_policy_bundle_write_authority BEFORE UPDATE ON public.bayesian_model_fits FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_policy_bundle_write_authority();


--
-- Name: agent_clients agent_clients_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_clients
    ADD CONSTRAINT agent_clients_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: agent_scope_grants agent_scope_grants_agent_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_scope_grants
    ADD CONSTRAINT agent_scope_grants_agent_client_id_fkey FOREIGN KEY (agent_client_id) REFERENCES public.agent_clients(id) ON DELETE CASCADE;


--
-- Name: agent_scope_grants agent_scope_grants_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_scope_grants
    ADD CONSTRAINT agent_scope_grants_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: agent_service_credentials agent_service_credentials_agent_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_service_credentials
    ADD CONSTRAINT agent_service_credentials_agent_client_id_fkey FOREIGN KEY (agent_client_id) REFERENCES public.agent_clients(id) ON DELETE CASCADE;


--
-- Name: agent_service_credentials agent_service_credentials_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_service_credentials
    ADD CONSTRAINT agent_service_credentials_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: agent_token_revocations agent_token_revocations_agent_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_token_revocations
    ADD CONSTRAINT agent_token_revocations_agent_client_id_fkey FOREIGN KEY (agent_client_id) REFERENCES public.agent_clients(id) ON DELETE CASCADE;


--
-- Name: agent_token_revocations agent_token_revocations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_token_revocations
    ADD CONSTRAINT agent_token_revocations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: attribution_allocations attribution_allocations_recompute_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_allocations
    ADD CONSTRAINT attribution_allocations_recompute_job_id_fkey FOREIGN KEY (recompute_job_id) REFERENCES public.attribution_recompute_jobs(id) ON DELETE CASCADE;


--
-- Name: attribution_allocations attribution_allocations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_allocations
    ADD CONSTRAINT attribution_allocations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: attribution_commerce_identities attribution_commerce_identities_attribution_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_commerce_identities
    ADD CONSTRAINT attribution_commerce_identities_attribution_event_id_fkey FOREIGN KEY (attribution_event_id) REFERENCES public.attribution_events(id) ON DELETE CASCADE;


--
-- Name: attribution_commerce_identities attribution_commerce_identities_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_commerce_identities
    ADD CONSTRAINT attribution_commerce_identities_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: attribution_events attribution_events_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_events
    ADD CONSTRAINT attribution_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: attribution_recompute_jobs attribution_recompute_jobs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_recompute_jobs
    ADD CONSTRAINT attribution_recompute_jobs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: auth_access_token_denylist auth_access_token_denylist_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_access_token_denylist
    ADD CONSTRAINT auth_access_token_denylist_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: auth_refresh_tokens auth_refresh_tokens_replaced_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_refresh_tokens
    ADD CONSTRAINT auth_refresh_tokens_replaced_by_id_fkey FOREIGN KEY (replaced_by_id) REFERENCES public.auth_refresh_tokens(id) ON DELETE SET NULL;


--
-- Name: auth_refresh_tokens auth_refresh_tokens_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_refresh_tokens
    ADD CONSTRAINT auth_refresh_tokens_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: auth_refresh_tokens auth_refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_refresh_tokens
    ADD CONSTRAINT auth_refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: auth_user_token_cutoffs auth_user_token_cutoffs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_token_cutoffs
    ADD CONSTRAINT auth_user_token_cutoffs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b23_exception_records b23_exception_records_match_verdict_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_exception_records
    ADD CONSTRAINT b23_exception_records_match_verdict_id_fkey FOREIGN KEY (match_verdict_id) REFERENCES public.b23_match_verdicts(id) ON DELETE CASCADE;


--
-- Name: b23_exception_records b23_exception_records_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_exception_records
    ADD CONSTRAINT b23_exception_records_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b23_match_task_dispatches b23_match_task_dispatches_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_match_task_dispatches
    ADD CONSTRAINT b23_match_task_dispatches_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b23_match_task_dispatches b23_match_task_dispatches_webhook_ingress_identity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_match_task_dispatches
    ADD CONSTRAINT b23_match_task_dispatches_webhook_ingress_identity_id_fkey FOREIGN KEY (webhook_ingress_identity_id) REFERENCES public.webhook_ingress_identities(id) ON DELETE CASCADE;


--
-- Name: b23_match_verdicts b23_match_verdicts_attribution_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_match_verdicts
    ADD CONSTRAINT b23_match_verdicts_attribution_event_id_fkey FOREIGN KEY (attribution_event_id) REFERENCES public.attribution_events(id) ON DELETE SET NULL;


--
-- Name: b23_match_verdicts b23_match_verdicts_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_match_verdicts
    ADD CONSTRAINT b23_match_verdicts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b23_match_verdicts b23_match_verdicts_webhook_ingress_identity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_match_verdicts
    ADD CONSTRAINT b23_match_verdicts_webhook_ingress_identity_id_fkey FOREIGN KEY (webhook_ingress_identity_id) REFERENCES public.webhook_ingress_identities(id) ON DELETE SET NULL;


--
-- Name: b23_revenue_events b23_revenue_events_match_verdict_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_revenue_events
    ADD CONSTRAINT b23_revenue_events_match_verdict_id_fkey FOREIGN KEY (match_verdict_id) REFERENCES public.b23_match_verdicts(id) ON DELETE SET NULL;


--
-- Name: b23_revenue_events b23_revenue_events_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_revenue_events
    ADD CONSTRAINT b23_revenue_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b23_revenue_events b23_revenue_events_webhook_ingress_identity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_revenue_events
    ADD CONSTRAINT b23_revenue_events_webhook_ingress_identity_id_fkey FOREIGN KEY (webhook_ingress_identity_id) REFERENCES public.webhook_ingress_identities(id) ON DELETE SET NULL;


--
-- Name: b23_webhook_ingestion_logs b23_webhook_ingestion_logs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b23_webhook_ingestion_logs
    ADD CONSTRAINT b23_webhook_ingestion_logs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b24_active_execution_leases b24_active_execution_leases_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_active_execution_leases
    ADD CONSTRAINT b24_active_execution_leases_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b24_dirty_events b24_dirty_events_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_dirty_events
    ADD CONSTRAINT b24_dirty_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b24_feature_authority_build_outbox b24_feature_authority_build_outbox_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_feature_authority_build_outbox
    ADD CONSTRAINT b24_feature_authority_build_outbox_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b24_feature_authority_build_requests b24_feature_authority_build_requests_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_feature_authority_build_requests
    ADD CONSTRAINT b24_feature_authority_build_requests_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b24_fit_dispatch_outbox b24_fit_dispatch_outbox_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_fit_dispatch_outbox
    ADD CONSTRAINT b24_fit_dispatch_outbox_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b24_fit_planner_wakeups b24_fit_planner_wakeups_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_fit_planner_wakeups
    ADD CONSTRAINT b24_fit_planner_wakeups_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b24_source_window_feature_authority b24_source_window_feature_authority_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_source_window_feature_authority
    ADD CONSTRAINT b24_source_window_feature_authority_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b27_explanation_materializations b27_explanation_materializations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b27_explanation_materializations
    ADD CONSTRAINT b27_explanation_materializations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b28_proposals b28_proposals_result_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b28_proposals
    ADD CONSTRAINT b28_proposals_result_id_fkey FOREIGN KEY (result_id) REFERENCES public.b28_simulation_results(id) ON DELETE RESTRICT;


--
-- Name: b28_proposals b28_proposals_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b28_proposals
    ADD CONSTRAINT b28_proposals_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b28_simulation_requests b28_simulation_requests_requested_by_agent_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b28_simulation_requests
    ADD CONSTRAINT b28_simulation_requests_requested_by_agent_client_id_fkey FOREIGN KEY (requested_by_agent_client_id) REFERENCES public.agent_clients(id) ON DELETE RESTRICT;


--
-- Name: b28_simulation_requests b28_simulation_requests_requested_by_credential_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b28_simulation_requests
    ADD CONSTRAINT b28_simulation_requests_requested_by_credential_id_fkey FOREIGN KEY (requested_by_credential_id) REFERENCES public.agent_service_credentials(id) ON DELETE RESTRICT;


--
-- Name: b28_simulation_requests b28_simulation_requests_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b28_simulation_requests
    ADD CONSTRAINT b28_simulation_requests_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: b28_simulation_results b28_simulation_results_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b28_simulation_results
    ADD CONSTRAINT b28_simulation_results_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.b28_simulation_requests(id) ON DELETE RESTRICT;


--
-- Name: b28_simulation_results b28_simulation_results_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b28_simulation_results
    ADD CONSTRAINT b28_simulation_results_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: bayesian_artifact_storage_quotas bayesian_artifact_storage_quotas_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bayesian_artifact_storage_quotas
    ADD CONSTRAINT bayesian_artifact_storage_quotas_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: bayesian_artifacts bayesian_artifacts_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts
    ADD CONSTRAINT bayesian_artifacts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: bayesian_model_fits bayesian_model_fits_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits
    ADD CONSTRAINT bayesian_model_fits_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: budget_jobs budget_jobs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.budget_jobs
    ADD CONSTRAINT budget_jobs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: budget_optimization_jobs budget_optimization_jobs_authority_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.budget_optimization_jobs
    ADD CONSTRAINT budget_optimization_jobs_authority_job_id_fkey FOREIGN KEY (authority_job_id) REFERENCES public.budget_jobs(id) ON DELETE SET NULL;


--
-- Name: budget_optimization_jobs budget_optimization_jobs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.budget_optimization_jobs
    ADD CONSTRAINT budget_optimization_jobs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: channel_assignment_corrections channel_assignment_corrections_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_assignment_corrections
    ADD CONSTRAINT channel_assignment_corrections_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: channel_assignment_corrections channel_assignment_corrections_to_channel_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_assignment_corrections
    ADD CONSTRAINT channel_assignment_corrections_to_channel_fkey FOREIGN KEY (to_channel) REFERENCES public.channel_taxonomy(code);


--
-- Name: channel_state_transitions channel_state_transitions_channel_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_state_transitions
    ADD CONSTRAINT channel_state_transitions_channel_code_fkey FOREIGN KEY (channel_code) REFERENCES public.channel_taxonomy(code) ON DELETE CASCADE;


--
-- Name: compliance_audit_ledger compliance_audit_ledger_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compliance_audit_ledger
    ADD CONSTRAINT compliance_audit_ledger_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: dead_events_quarantine dead_events_quarantine_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dead_events_quarantine
    ADD CONSTRAINT dead_events_quarantine_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE SET NULL;


--
-- Name: dead_events dead_events_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dead_events
    ADD CONSTRAINT dead_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: ephemeral_click_resolution ephemeral_click_resolution_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ephemeral_click_resolution
    ADD CONSTRAINT ephemeral_click_resolution_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: ephemeral_order_resolution ephemeral_order_resolution_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ephemeral_order_resolution
    ADD CONSTRAINT ephemeral_order_resolution_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: explanation_cache explanation_cache_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explanation_cache
    ADD CONSTRAINT explanation_cache_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: attribution_allocations fk_allocations_event_id_set_null; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_allocations
    ADD CONSTRAINT fk_allocations_event_id_set_null FOREIGN KEY (event_id) REFERENCES public.attribution_events(id) ON DELETE SET NULL;


--
-- Name: attribution_allocations fk_attribution_allocations_channel_code; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_allocations
    ADD CONSTRAINT fk_attribution_allocations_channel_code FOREIGN KEY (channel_code) REFERENCES public.channel_taxonomy(code);


--
-- Name: attribution_events fk_attribution_events_channel; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_events
    ADD CONSTRAINT fk_attribution_events_channel FOREIGN KEY (channel) REFERENCES public.channel_taxonomy(code) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: attribution_events fk_attribution_events_session_authority; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribution_events
    ADD CONSTRAINT fk_attribution_events_session_authority FOREIGN KEY (tenant_id, session_id) REFERENCES public.session_authority(tenant_id, session_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: b24_active_execution_leases fk_b24_active_execution_fit; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_active_execution_leases
    ADD CONSTRAINT fk_b24_active_execution_fit FOREIGN KEY (tenant_id, fit_id) REFERENCES public.bayesian_model_fits(tenant_id, id) ON DELETE RESTRICT;


--
-- Name: b24_feature_authority_build_outbox fk_b24_feature_authority_build_outbox_request; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_feature_authority_build_outbox
    ADD CONSTRAINT fk_b24_feature_authority_build_outbox_request FOREIGN KEY (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash) REFERENCES public.b24_feature_authority_build_requests(tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash) ON DELETE CASCADE;


--
-- Name: b24_fit_dispatch_outbox fk_b24_fit_dispatch_outbox_fit; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_fit_dispatch_outbox
    ADD CONSTRAINT fk_b24_fit_dispatch_outbox_fit FOREIGN KEY (tenant_id, fit_id) REFERENCES public.bayesian_model_fits(tenant_id, id) ON DELETE RESTRICT;


--
-- Name: b24_fit_recovery_outbox fk_b24_fit_recovery_outbox_dispatch; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_fit_recovery_outbox
    ADD CONSTRAINT fk_b24_fit_recovery_outbox_dispatch FOREIGN KEY (tenant_id, dispatch_id) REFERENCES public.b24_fit_dispatch_outbox(tenant_id, id) ON DELETE CASCADE;


--
-- Name: b24_fit_policy_replan_lineage fk_b24_replan_lineage_fit; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b24_fit_policy_replan_lineage
    ADD CONSTRAINT fk_b24_replan_lineage_fit FOREIGN KEY (tenant_id, fit_id) REFERENCES public.bayesian_model_fits(tenant_id, id) ON DELETE RESTRICT;


--
-- Name: b27_explanation_materializations fk_b27_explanation_materializations_source_issuance; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b27_explanation_materializations
    ADD CONSTRAINT fk_b27_explanation_materializations_source_issuance FOREIGN KEY (tenant_id, source_issuance_envelope_hash) REFERENCES public.trust_envelope_issuance_log(tenant_id, envelope_hash);


--
-- Name: b28_simulation_requests fk_b28_simulation_requests_source_issuance; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b28_simulation_requests
    ADD CONSTRAINT fk_b28_simulation_requests_source_issuance FOREIGN KEY (tenant_id, source_issuance_envelope_hash) REFERENCES public.trust_envelope_issuance_log(tenant_id, envelope_hash);


--
-- Name: bayesian_artifacts fk_bayesian_artifacts_tenant_fit; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts
    ADD CONSTRAINT fk_bayesian_artifacts_tenant_fit FOREIGN KEY (tenant_id, fit_id) REFERENCES public.bayesian_model_fits(tenant_id, id) ON DELETE RESTRICT;


--
-- Name: kombu_message fk_kombu_message_queue; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kombu_message
    ADD CONSTRAINT fk_kombu_message_queue FOREIGN KEY (queue_id) REFERENCES public.kombu_queue(id);


--
-- Name: tenant_membership_roles fk_tenant_membership_roles_membership_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_membership_roles
    ADD CONSTRAINT fk_tenant_membership_roles_membership_tenant FOREIGN KEY (membership_id, tenant_id) REFERENCES public.tenant_memberships(id, tenant_id) ON DELETE CASCADE;


--
-- Name: trust_issuance_attempts fk_trust_issuance_attempt_audit; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_issuance_attempts
    ADD CONSTRAINT fk_trust_issuance_attempt_audit FOREIGN KEY (tenant_id, audit_ref) REFERENCES public.trust_access_log(tenant_id, audit_ref) ON DELETE RESTRICT;


--
-- Name: trust_envelope_issuance_log fk_trust_issuance_log_access_audit; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_envelope_issuance_log
    ADD CONSTRAINT fk_trust_issuance_log_access_audit FOREIGN KEY (tenant_id, access_audit_ref) REFERENCES public.trust_access_log(tenant_id, audit_ref) ON DELETE CASCADE;


--
-- Name: investigation_jobs investigation_jobs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigation_jobs
    ADD CONSTRAINT investigation_jobs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: investigation_tool_calls investigation_tool_calls_investigation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigation_tool_calls
    ADD CONSTRAINT investigation_tool_calls_investigation_id_fkey FOREIGN KEY (investigation_id) REFERENCES public.investigations(id) ON DELETE CASCADE;


--
-- Name: investigation_tool_calls investigation_tool_calls_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigation_tool_calls
    ADD CONSTRAINT investigation_tool_calls_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: investigations investigations_authority_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT investigations_authority_job_id_fkey FOREIGN KEY (authority_job_id) REFERENCES public.investigation_jobs(id) ON DELETE SET NULL;


--
-- Name: investigations investigations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT investigations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: llm_api_calls llm_api_calls_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_api_calls
    ADD CONSTRAINT llm_api_calls_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: llm_breaker_state llm_breaker_state_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_breaker_state
    ADD CONSTRAINT llm_breaker_state_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: llm_budget_reservations llm_budget_reservations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_budget_reservations
    ADD CONSTRAINT llm_budget_reservations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: llm_call_audit llm_call_audit_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_call_audit
    ADD CONSTRAINT llm_call_audit_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: llm_hourly_shutoff_state llm_hourly_shutoff_state_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_hourly_shutoff_state
    ADD CONSTRAINT llm_hourly_shutoff_state_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: llm_monthly_budget_state llm_monthly_budget_state_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monthly_budget_state
    ADD CONSTRAINT llm_monthly_budget_state_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: llm_monthly_costs llm_monthly_costs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monthly_costs
    ADD CONSTRAINT llm_monthly_costs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: llm_semantic_cache llm_semantic_cache_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_semantic_cache
    ADD CONSTRAINT llm_semantic_cache_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: llm_validation_failures llm_validation_failures_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_validation_failures
    ADD CONSTRAINT llm_validation_failures_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: oauth_handshake_sessions oauth_handshake_sessions_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_handshake_sessions
    ADD CONSTRAINT oauth_handshake_sessions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: oauth_handshake_sessions oauth_handshake_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_handshake_sessions
    ADD CONSTRAINT oauth_handshake_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: platform_connections platform_connections_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_connections
    ADD CONSTRAINT platform_connections_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: platform_credentials platform_credentials_platform_connection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_credentials
    ADD CONSTRAINT platform_credentials_platform_connection_id_fkey FOREIGN KEY (platform_connection_id) REFERENCES public.platform_connections(id) ON DELETE CASCADE;


--
-- Name: platform_credentials platform_credentials_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_credentials
    ADD CONSTRAINT platform_credentials_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: r4_crash_barriers r4_crash_barriers_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.r4_crash_barriers
    ADD CONSTRAINT r4_crash_barriers_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: r4_task_attempts r4_task_attempts_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.r4_task_attempts
    ADD CONSTRAINT r4_task_attempts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: raw_event_payloads raw_event_payloads_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_event_payloads
    ADD CONSTRAINT raw_event_payloads_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.attribution_events(id) ON DELETE CASCADE;


--
-- Name: raw_event_payloads raw_event_payloads_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_event_payloads
    ADD CONSTRAINT raw_event_payloads_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: reconciliation_runs reconciliation_runs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reconciliation_runs
    ADD CONSTRAINT reconciliation_runs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: revenue_cache_entries revenue_cache_entries_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revenue_cache_entries
    ADD CONSTRAINT revenue_cache_entries_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: revenue_ledger revenue_ledger_allocation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revenue_ledger
    ADD CONSTRAINT revenue_ledger_allocation_id_fkey FOREIGN KEY (allocation_id) REFERENCES public.attribution_allocations(id) ON DELETE CASCADE;


--
-- Name: revenue_ledger revenue_ledger_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revenue_ledger
    ADD CONSTRAINT revenue_ledger_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: revenue_state_transitions revenue_state_transitions_ledger_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revenue_state_transitions
    ADD CONSTRAINT revenue_state_transitions_ledger_id_fkey FOREIGN KEY (ledger_id) REFERENCES public.revenue_ledger(id) ON DELETE CASCADE;


--
-- Name: revenue_state_transitions revenue_state_transitions_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revenue_state_transitions
    ADD CONSTRAINT revenue_state_transitions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: session_authority session_authority_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_authority
    ADD CONSTRAINT session_authority_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: tenant_membership_roles tenant_membership_roles_role_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_membership_roles
    ADD CONSTRAINT tenant_membership_roles_role_code_fkey FOREIGN KEY (role_code) REFERENCES public.roles(code) ON DELETE RESTRICT;


--
-- Name: tenant_membership_roles tenant_membership_roles_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_membership_roles
    ADD CONSTRAINT tenant_membership_roles_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: tenant_memberships tenant_memberships_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT tenant_memberships_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: tenant_memberships tenant_memberships_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT tenant_memberships_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: trust_access_log trust_access_log_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_access_log
    ADD CONSTRAINT trust_access_log_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: trust_envelope_issuance_log trust_envelope_issuance_log_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_envelope_issuance_log
    ADD CONSTRAINT trust_envelope_issuance_log_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: trust_export_artifact_attempts trust_export_artifact_attempts_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_export_artifact_attempts
    ADD CONSTRAINT trust_export_artifact_attempts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: trust_issuance_attempts trust_issuance_attempts_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_issuance_attempts
    ADD CONSTRAINT trust_issuance_attempts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: trust_rate_limit_state trust_rate_limit_state_agent_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_rate_limit_state
    ADD CONSTRAINT trust_rate_limit_state_agent_client_id_fkey FOREIGN KEY (agent_client_id) REFERENCES public.agent_clients(id) ON DELETE CASCADE;


--
-- Name: trust_rate_limit_state trust_rate_limit_state_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_rate_limit_state
    ADD CONSTRAINT trust_rate_limit_state_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: trust_replay_events trust_replay_events_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_replay_events
    ADD CONSTRAINT trust_replay_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: trust_request_nonces trust_request_nonces_agent_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_request_nonces
    ADD CONSTRAINT trust_request_nonces_agent_client_id_fkey FOREIGN KEY (agent_client_id) REFERENCES public.agent_clients(id) ON DELETE CASCADE;


--
-- Name: trust_request_nonces trust_request_nonces_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_request_nonces
    ADD CONSTRAINT trust_request_nonces_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: trust_scope_denial_events trust_scope_denial_events_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_scope_denial_events
    ADD CONSTRAINT trust_scope_denial_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: webhook_ingress_identities webhook_ingress_identities_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_ingress_identities
    ADD CONSTRAINT webhook_ingress_identities_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.attribution_events(id) ON DELETE CASCADE;


--
-- Name: webhook_ingress_identities webhook_ingress_identities_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_ingress_identities
    ADD CONSTRAINT webhook_ingress_identities_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: worker_side_effects worker_side_effects_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.worker_side_effects
    ADD CONSTRAINT worker_side_effects_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: agent_clients; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.agent_clients ENABLE ROW LEVEL SECURITY;

--
-- Name: agent_scope_grants; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.agent_scope_grants ENABLE ROW LEVEL SECURITY;

--
-- Name: agent_service_credentials; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.agent_service_credentials ENABLE ROW LEVEL SECURITY;

--
-- Name: agent_token_revocations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.agent_token_revocations ENABLE ROW LEVEL SECURITY;

--
-- Name: attribution_allocations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.attribution_allocations ENABLE ROW LEVEL SECURITY;

--
-- Name: attribution_commerce_identities; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.attribution_commerce_identities ENABLE ROW LEVEL SECURITY;

--
-- Name: attribution_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.attribution_events ENABLE ROW LEVEL SECURITY;

--
-- Name: attribution_recompute_jobs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.attribution_recompute_jobs ENABLE ROW LEVEL SECURITY;

--
-- Name: attribution_recompute_jobs attribution_recompute_jobs_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY attribution_recompute_jobs_tenant_isolation ON public.attribution_recompute_jobs USING (((tenant_id)::text = current_setting('app.current_tenant_id'::text, true))) WITH CHECK (((tenant_id)::text = current_setting('app.current_tenant_id'::text, true)));


--
-- Name: auth_access_token_denylist; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.auth_access_token_denylist ENABLE ROW LEVEL SECURITY;

--
-- Name: auth_refresh_tokens; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.auth_refresh_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: auth_user_token_cutoffs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.auth_user_token_cutoffs ENABLE ROW LEVEL SECURITY;

--
-- Name: b23_exception_records; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b23_exception_records ENABLE ROW LEVEL SECURITY;

--
-- Name: b23_match_task_dispatches; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b23_match_task_dispatches ENABLE ROW LEVEL SECURITY;

--
-- Name: b23_match_verdicts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b23_match_verdicts ENABLE ROW LEVEL SECURITY;

--
-- Name: b23_revenue_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b23_revenue_events ENABLE ROW LEVEL SECURITY;

--
-- Name: b23_webhook_ingestion_logs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b23_webhook_ingestion_logs ENABLE ROW LEVEL SECURITY;

--
-- Name: b24_active_execution_leases; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b24_active_execution_leases ENABLE ROW LEVEL SECURITY;

--
-- Name: b24_dirty_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b24_dirty_events ENABLE ROW LEVEL SECURITY;

--
-- Name: b24_feature_authority_build_outbox; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b24_feature_authority_build_outbox ENABLE ROW LEVEL SECURITY;

--
-- Name: b24_feature_authority_build_requests; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b24_feature_authority_build_requests ENABLE ROW LEVEL SECURITY;

--
-- Name: b24_fit_dispatch_outbox; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b24_fit_dispatch_outbox ENABLE ROW LEVEL SECURITY;

--
-- Name: b24_fit_planner_wakeups; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b24_fit_planner_wakeups ENABLE ROW LEVEL SECURITY;

--
-- Name: b24_fit_planner_wakeups b24_fit_planner_wakeups_worker_only; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY b24_fit_planner_wakeups_worker_only ON public.b24_fit_planner_wakeups USING ((CURRENT_USER = 'app_worker'::name)) WITH CHECK ((CURRENT_USER = 'app_worker'::name));


--
-- Name: b24_fit_policy_replan_lineage; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b24_fit_policy_replan_lineage ENABLE ROW LEVEL SECURITY;

--
-- Name: b24_fit_recovery_outbox; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b24_fit_recovery_outbox ENABLE ROW LEVEL SECURITY;

--
-- Name: b24_source_window_feature_authority; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b24_source_window_feature_authority ENABLE ROW LEVEL SECURITY;

--
-- Name: b24_worker_process_authority; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b24_worker_process_authority ENABLE ROW LEVEL SECURITY;

--
-- Name: b27_explanation_materializations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b27_explanation_materializations ENABLE ROW LEVEL SECURITY;

--
-- Name: b28_proposals; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b28_proposals ENABLE ROW LEVEL SECURITY;

--
-- Name: b28_simulation_requests; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b28_simulation_requests ENABLE ROW LEVEL SECURITY;

--
-- Name: b28_simulation_results; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.b28_simulation_results ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifact_storage_quotas; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifact_storage_quotas ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p00; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p00 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p01; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p01 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p02; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p02 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p03; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p03 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p04; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p04 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p05; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p05 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p06; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p06 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p07; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p07 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p08; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p08 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p09; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p09 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p10; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p10 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p11; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p11 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p12; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p12 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p13; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p13 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p14; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p14 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_artifacts_p15; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_artifacts_p15 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p00; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p00 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p01; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p01 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p02; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p02 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p03; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p03 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p04; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p04 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p05; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p05 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p06; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p06 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p07; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p07 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p08; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p08 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p09; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p09 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p10; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p10 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p11; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p11 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p12; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p12 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p13; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p13 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p14; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p14 ENABLE ROW LEVEL SECURITY;

--
-- Name: bayesian_model_fits_p15; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bayesian_model_fits_p15 ENABLE ROW LEVEL SECURITY;

--
-- Name: budget_jobs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.budget_jobs ENABLE ROW LEVEL SECURITY;

--
-- Name: budget_optimization_jobs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.budget_optimization_jobs ENABLE ROW LEVEL SECURITY;

--
-- Name: b24_fit_dispatch_outbox c11_dispatch_publisher_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY c11_dispatch_publisher_select ON public.b24_fit_dispatch_outbox FOR SELECT USING ((SESSION_USER = 'app_dispatch_publisher'::name));


--
-- Name: b24_fit_dispatch_outbox c11_dispatch_publisher_update; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY c11_dispatch_publisher_update ON public.b24_fit_dispatch_outbox FOR UPDATE USING ((SESSION_USER = 'app_dispatch_publisher'::name)) WITH CHECK ((SESSION_USER = 'app_dispatch_publisher'::name));


--
-- Name: b24_fit_policy_replan_lineage c11_trigger_insert_b24_fit_policy_replan_lineage; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY c11_trigger_insert_b24_fit_policy_replan_lineage ON public.b24_fit_policy_replan_lineage FOR INSERT WITH CHECK ((CURRENT_USER = pg_get_userbyid(( SELECT pg_class.relowner
   FROM pg_class
  WHERE (pg_class.oid = ('public.b24_fit_policy_replan_lineage'::regclass)::oid)))));


--
-- Name: b24_fit_dispatch_outbox c12_dispatch_internal_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY c12_dispatch_internal_select ON public.b24_fit_dispatch_outbox FOR SELECT USING (((CURRENT_USER = 'migration_owner'::name) AND (SESSION_USER = 'app_worker'::name)));


--
-- Name: b24_fit_dispatch_outbox c12_dispatch_internal_update; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY c12_dispatch_internal_update ON public.b24_fit_dispatch_outbox FOR UPDATE USING (((CURRENT_USER = 'migration_owner'::name) AND (SESSION_USER = 'app_worker'::name))) WITH CHECK (((CURRENT_USER = 'migration_owner'::name) AND (SESSION_USER = 'app_worker'::name)));


--
-- Name: b24_fit_recovery_outbox c12_recovery_internal_insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY c12_recovery_internal_insert ON public.b24_fit_recovery_outbox FOR INSERT WITH CHECK (((CURRENT_USER = 'migration_owner'::name) AND (SESSION_USER = 'app_worker'::name)));


--
-- Name: b24_fit_recovery_outbox c12_recovery_internal_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY c12_recovery_internal_select ON public.b24_fit_recovery_outbox FOR SELECT USING (((CURRENT_USER = 'migration_owner'::name) AND (SESSION_USER = 'app_worker'::name)));


--
-- Name: b24_fit_recovery_outbox c12_recovery_internal_update; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY c12_recovery_internal_update ON public.b24_fit_recovery_outbox FOR UPDATE USING (((CURRENT_USER = 'migration_owner'::name) AND (SESSION_USER = 'app_worker'::name))) WITH CHECK (((CURRENT_USER = 'migration_owner'::name) AND (SESSION_USER = 'app_worker'::name)));


--
-- Name: b24_worker_process_authority c12_worker_authority_internal_insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY c12_worker_authority_internal_insert ON public.b24_worker_process_authority FOR INSERT WITH CHECK (((CURRENT_USER = 'migration_owner'::name) AND (SESSION_USER = 'app_worker'::name)));


--
-- Name: b24_worker_process_authority c12_worker_authority_internal_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY c12_worker_authority_internal_select ON public.b24_worker_process_authority FOR SELECT USING (((CURRENT_USER = 'migration_owner'::name) AND (SESSION_USER = ANY (ARRAY['app_worker'::name, 'app_dispatch_publisher'::name]))));


--
-- Name: b24_worker_process_authority c12_worker_authority_internal_update; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY c12_worker_authority_internal_update ON public.b24_worker_process_authority FOR UPDATE USING (((CURRENT_USER = 'migration_owner'::name) AND (SESSION_USER = 'app_worker'::name))) WITH CHECK (((CURRENT_USER = 'migration_owner'::name) AND (SESSION_USER = 'app_worker'::name)));


--
-- Name: channel_assignment_corrections; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.channel_assignment_corrections ENABLE ROW LEVEL SECURITY;

--
-- Name: compliance_audit_ledger; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.compliance_audit_ledger ENABLE ROW LEVEL SECURITY;

--
-- Name: dead_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.dead_events ENABLE ROW LEVEL SECURITY;

--
-- Name: dead_events_quarantine; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.dead_events_quarantine ENABLE ROW LEVEL SECURITY;

--
-- Name: b24_worker_process_authority deny_all_b24_worker_process_authority; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY deny_all_b24_worker_process_authority ON public.b24_worker_process_authority USING (false) WITH CHECK (false);


--
-- Name: ephemeral_click_resolution; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ephemeral_click_resolution ENABLE ROW LEVEL SECURITY;

--
-- Name: ephemeral_order_resolution; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ephemeral_order_resolution ENABLE ROW LEVEL SECURITY;

--
-- Name: explanation_cache; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.explanation_cache ENABLE ROW LEVEL SECURITY;

--
-- Name: investigation_jobs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.investigation_jobs ENABLE ROW LEVEL SECURITY;

--
-- Name: investigation_tool_calls; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.investigation_tool_calls ENABLE ROW LEVEL SECURITY;

--
-- Name: investigations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.investigations ENABLE ROW LEVEL SECURITY;

--
-- Name: llm_api_calls; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.llm_api_calls ENABLE ROW LEVEL SECURITY;

--
-- Name: llm_breaker_state; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.llm_breaker_state ENABLE ROW LEVEL SECURITY;

--
-- Name: llm_budget_reservations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.llm_budget_reservations ENABLE ROW LEVEL SECURITY;

--
-- Name: llm_call_audit; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.llm_call_audit ENABLE ROW LEVEL SECURITY;

--
-- Name: llm_hourly_shutoff_state; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.llm_hourly_shutoff_state ENABLE ROW LEVEL SECURITY;

--
-- Name: llm_monthly_budget_state; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.llm_monthly_budget_state ENABLE ROW LEVEL SECURITY;

--
-- Name: llm_monthly_costs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.llm_monthly_costs ENABLE ROW LEVEL SECURITY;

--
-- Name: llm_semantic_cache; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.llm_semantic_cache ENABLE ROW LEVEL SECURITY;

--
-- Name: llm_validation_failures; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.llm_validation_failures ENABLE ROW LEVEL SECURITY;

--
-- Name: oauth_handshake_sessions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.oauth_handshake_sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: dead_events_quarantine ops_quarantine_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY ops_quarantine_select ON public.dead_events_quarantine FOR SELECT USING (((tenant_id IS NULL) AND (CURRENT_USER = 'app_ops'::name)));


--
-- Name: platform_connections; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.platform_connections ENABLE ROW LEVEL SECURITY;

--
-- Name: platform_credentials; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.platform_credentials ENABLE ROW LEVEL SECURITY;

--
-- Name: dead_events_quarantine quarantine_lane_insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY quarantine_lane_insert ON public.dead_events_quarantine FOR INSERT TO app_rw, app_user WITH CHECK ((tenant_id IS NULL));


--
-- Name: r4_crash_barriers; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.r4_crash_barriers ENABLE ROW LEVEL SECURITY;

--
-- Name: r4_task_attempts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.r4_task_attempts ENABLE ROW LEVEL SECURITY;

--
-- Name: raw_event_payloads; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.raw_event_payloads ENABLE ROW LEVEL SECURITY;

--
-- Name: reconciliation_runs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.reconciliation_runs ENABLE ROW LEVEL SECURITY;

--
-- Name: revenue_cache_entries; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.revenue_cache_entries ENABLE ROW LEVEL SECURITY;

--
-- Name: revenue_ledger; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.revenue_ledger ENABLE ROW LEVEL SECURITY;

--
-- Name: revenue_state_transitions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.revenue_state_transitions ENABLE ROW LEVEL SECURITY;

--
-- Name: session_authority; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.session_authority ENABLE ROW LEVEL SECURITY;

--
-- Name: b24_fit_policy_replan_lineage tenant_isolation_b24_fit_policy_replan_lineage; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_b24_fit_policy_replan_lineage ON public.b24_fit_policy_replan_lineage FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: attribution_allocations tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.attribution_allocations USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: attribution_events tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.attribution_events USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: auth_access_token_denylist tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.auth_access_token_denylist USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: auth_refresh_tokens tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.auth_refresh_tokens USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: auth_user_token_cutoffs tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.auth_user_token_cutoffs USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: budget_jobs tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.budget_jobs USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: budget_optimization_jobs tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.budget_optimization_jobs USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: channel_assignment_corrections tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.channel_assignment_corrections USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: dead_events tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.dead_events USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: explanation_cache tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.explanation_cache USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: investigation_jobs tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.investigation_jobs TO app_rw, app_ro, app_user USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: investigation_tool_calls tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.investigation_tool_calls USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: investigations tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.investigations USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: llm_api_calls tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.llm_api_calls USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));


--
-- Name: llm_breaker_state tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.llm_breaker_state USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));


--
-- Name: llm_budget_reservations tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.llm_budget_reservations USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));


--
-- Name: llm_call_audit tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.llm_call_audit USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));


--
-- Name: llm_hourly_shutoff_state tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.llm_hourly_shutoff_state USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));


--
-- Name: llm_monthly_budget_state tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.llm_monthly_budget_state USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));


--
-- Name: llm_monthly_costs tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.llm_monthly_costs USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));


--
-- Name: llm_semantic_cache tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.llm_semantic_cache USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));


--
-- Name: llm_validation_failures tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.llm_validation_failures USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: oauth_handshake_sessions tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.oauth_handshake_sessions USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: platform_connections tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.platform_connections USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: platform_credentials tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.platform_credentials USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: r4_crash_barriers tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.r4_crash_barriers TO app_user USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: r4_task_attempts tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.r4_task_attempts TO app_user USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: reconciliation_runs tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.reconciliation_runs USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: revenue_cache_entries tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.revenue_cache_entries USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: revenue_ledger tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.revenue_ledger USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: revenue_state_transitions tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.revenue_state_transitions USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: session_authority tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.session_authority USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: tenant_membership_roles tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.tenant_membership_roles USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: tenant_memberships tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.tenant_memberships USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: worker_failed_jobs tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.worker_failed_jobs USING (((tenant_id IS NULL) OR ((tenant_id)::text = current_setting('app.current_tenant_id'::text, true))));


--
-- Name: worker_side_effects tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.worker_side_effects TO app_user USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: agent_clients tenant_isolation_policy_agent_clients; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_agent_clients ON public.agent_clients USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: agent_scope_grants tenant_isolation_policy_agent_scope_grants; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_agent_scope_grants ON public.agent_scope_grants USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: agent_service_credentials tenant_isolation_policy_agent_service_credentials; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_agent_service_credentials ON public.agent_service_credentials USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: agent_token_revocations tenant_isolation_policy_agent_token_revocations; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_agent_token_revocations ON public.agent_token_revocations USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: attribution_commerce_identities tenant_isolation_policy_attribution_commerce_identities; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_attribution_commerce_identities ON public.attribution_commerce_identities USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b23_exception_records tenant_isolation_policy_b23_exception_records; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b23_exception_records ON public.b23_exception_records USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b23_match_task_dispatches tenant_isolation_policy_b23_match_task_dispatches; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b23_match_task_dispatches ON public.b23_match_task_dispatches USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b23_match_verdicts tenant_isolation_policy_b23_match_verdicts; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b23_match_verdicts ON public.b23_match_verdicts USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b23_revenue_events tenant_isolation_policy_b23_revenue_events; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b23_revenue_events ON public.b23_revenue_events USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b23_webhook_ingestion_logs tenant_isolation_policy_b23_webhook_ingestion_logs; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b23_webhook_ingestion_logs ON public.b23_webhook_ingestion_logs USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b24_active_execution_leases tenant_isolation_policy_b24_active_execution_leases; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b24_active_execution_leases ON public.b24_active_execution_leases USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b24_dirty_events tenant_isolation_policy_b24_dirty_events; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b24_dirty_events ON public.b24_dirty_events USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b24_feature_authority_build_outbox tenant_isolation_policy_b24_feature_authority_build_outbox; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b24_feature_authority_build_outbox ON public.b24_feature_authority_build_outbox USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b24_feature_authority_build_requests tenant_isolation_policy_b24_feature_authority_build_requests; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b24_feature_authority_build_requests ON public.b24_feature_authority_build_requests USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b24_fit_dispatch_outbox tenant_isolation_policy_b24_fit_dispatch_outbox; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b24_fit_dispatch_outbox ON public.b24_fit_dispatch_outbox USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b24_fit_recovery_outbox tenant_isolation_policy_b24_fit_recovery_outbox; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b24_fit_recovery_outbox ON public.b24_fit_recovery_outbox USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: b24_source_window_feature_authority tenant_isolation_policy_b24_source_window_feature_authority; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b24_source_window_feature_authority ON public.b24_source_window_feature_authority USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b27_explanation_materializations tenant_isolation_policy_b27_explanation_materializations; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b27_explanation_materializations ON public.b27_explanation_materializations USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b28_proposals tenant_isolation_policy_b28_proposals; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b28_proposals ON public.b28_proposals USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b28_simulation_requests tenant_isolation_policy_b28_simulation_requests; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b28_simulation_requests ON public.b28_simulation_requests USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: b28_simulation_results tenant_isolation_policy_b28_simulation_results; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_b28_simulation_results ON public.b28_simulation_results USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifact_storage_quotas tenant_isolation_policy_bayesian_artifact_storage_quotas; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifact_storage_quotas ON public.bayesian_artifact_storage_quotas USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts tenant_isolation_policy_bayesian_artifacts; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts ON public.bayesian_artifacts USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p00 tenant_isolation_policy_bayesian_artifacts_p00; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p00 ON public.bayesian_artifacts_p00 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p01 tenant_isolation_policy_bayesian_artifacts_p01; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p01 ON public.bayesian_artifacts_p01 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p02 tenant_isolation_policy_bayesian_artifacts_p02; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p02 ON public.bayesian_artifacts_p02 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p03 tenant_isolation_policy_bayesian_artifacts_p03; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p03 ON public.bayesian_artifacts_p03 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p04 tenant_isolation_policy_bayesian_artifacts_p04; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p04 ON public.bayesian_artifacts_p04 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p05 tenant_isolation_policy_bayesian_artifacts_p05; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p05 ON public.bayesian_artifacts_p05 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p06 tenant_isolation_policy_bayesian_artifacts_p06; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p06 ON public.bayesian_artifacts_p06 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p07 tenant_isolation_policy_bayesian_artifacts_p07; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p07 ON public.bayesian_artifacts_p07 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p08 tenant_isolation_policy_bayesian_artifacts_p08; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p08 ON public.bayesian_artifacts_p08 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p09 tenant_isolation_policy_bayesian_artifacts_p09; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p09 ON public.bayesian_artifacts_p09 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p10 tenant_isolation_policy_bayesian_artifacts_p10; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p10 ON public.bayesian_artifacts_p10 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p11 tenant_isolation_policy_bayesian_artifacts_p11; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p11 ON public.bayesian_artifacts_p11 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p12 tenant_isolation_policy_bayesian_artifacts_p12; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p12 ON public.bayesian_artifacts_p12 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p13 tenant_isolation_policy_bayesian_artifacts_p13; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p13 ON public.bayesian_artifacts_p13 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p14 tenant_isolation_policy_bayesian_artifacts_p14; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p14 ON public.bayesian_artifacts_p14 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_artifacts_p15 tenant_isolation_policy_bayesian_artifacts_p15; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_artifacts_p15 ON public.bayesian_artifacts_p15 USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: bayesian_model_fits tenant_isolation_policy_bayesian_model_fits; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits ON public.bayesian_model_fits USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p00 tenant_isolation_policy_bayesian_model_fits_p00; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p00 ON public.bayesian_model_fits_p00 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p01 tenant_isolation_policy_bayesian_model_fits_p01; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p01 ON public.bayesian_model_fits_p01 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p02 tenant_isolation_policy_bayesian_model_fits_p02; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p02 ON public.bayesian_model_fits_p02 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p03 tenant_isolation_policy_bayesian_model_fits_p03; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p03 ON public.bayesian_model_fits_p03 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p04 tenant_isolation_policy_bayesian_model_fits_p04; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p04 ON public.bayesian_model_fits_p04 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p05 tenant_isolation_policy_bayesian_model_fits_p05; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p05 ON public.bayesian_model_fits_p05 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p06 tenant_isolation_policy_bayesian_model_fits_p06; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p06 ON public.bayesian_model_fits_p06 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p07 tenant_isolation_policy_bayesian_model_fits_p07; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p07 ON public.bayesian_model_fits_p07 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p08 tenant_isolation_policy_bayesian_model_fits_p08; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p08 ON public.bayesian_model_fits_p08 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p09 tenant_isolation_policy_bayesian_model_fits_p09; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p09 ON public.bayesian_model_fits_p09 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p10 tenant_isolation_policy_bayesian_model_fits_p10; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p10 ON public.bayesian_model_fits_p10 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p11 tenant_isolation_policy_bayesian_model_fits_p11; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p11 ON public.bayesian_model_fits_p11 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p12 tenant_isolation_policy_bayesian_model_fits_p12; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p12 ON public.bayesian_model_fits_p12 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p13 tenant_isolation_policy_bayesian_model_fits_p13; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p13 ON public.bayesian_model_fits_p13 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p14 tenant_isolation_policy_bayesian_model_fits_p14; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p14 ON public.bayesian_model_fits_p14 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: bayesian_model_fits_p15 tenant_isolation_policy_bayesian_model_fits_p15; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_bayesian_model_fits_p15 ON public.bayesian_model_fits_p15 USING ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid));


--
-- Name: compliance_audit_ledger tenant_isolation_policy_compliance_audit_ledger; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_compliance_audit_ledger ON public.compliance_audit_ledger USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: ephemeral_click_resolution tenant_isolation_policy_ephemeral_click_resolution; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_ephemeral_click_resolution ON public.ephemeral_click_resolution USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: ephemeral_order_resolution tenant_isolation_policy_ephemeral_order_resolution; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_ephemeral_order_resolution ON public.ephemeral_order_resolution USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: raw_event_payloads tenant_isolation_policy_raw_event_payloads; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_raw_event_payloads ON public.raw_event_payloads USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: trust_access_log tenant_isolation_policy_trust_access_log; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_trust_access_log ON public.trust_access_log USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: trust_envelope_issuance_log tenant_isolation_policy_trust_envelope_issuance_log; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_trust_envelope_issuance_log ON public.trust_envelope_issuance_log USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: trust_export_artifact_attempts tenant_isolation_policy_trust_export_artifact_attempts; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_trust_export_artifact_attempts ON public.trust_export_artifact_attempts USING ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid));


--
-- Name: trust_issuance_attempts tenant_isolation_policy_trust_issuance_attempts; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_trust_issuance_attempts ON public.trust_issuance_attempts USING ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid));


--
-- Name: trust_rate_limit_state tenant_isolation_policy_trust_rate_limit_state; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_trust_rate_limit_state ON public.trust_rate_limit_state USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: trust_replay_events tenant_isolation_policy_trust_replay_events; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_trust_replay_events ON public.trust_replay_events USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: trust_request_nonces tenant_isolation_policy_trust_request_nonces; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_trust_request_nonces ON public.trust_request_nonces USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: trust_scope_denial_events tenant_isolation_policy_trust_scope_denial_events; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_trust_scope_denial_events ON public.trust_scope_denial_events USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: webhook_ingress_identities tenant_isolation_policy_webhook_ingress_identities; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy_webhook_ingress_identities ON public.webhook_ingress_identities USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));


--
-- Name: dead_events_quarantine tenant_lane_insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_lane_insert ON public.dead_events_quarantine FOR INSERT TO app_rw, app_user WITH CHECK (((tenant_id IS NOT NULL) AND (tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)));


--
-- Name: dead_events_quarantine tenant_lane_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_lane_select ON public.dead_events_quarantine FOR SELECT TO app_rw, app_ro, app_user USING (((tenant_id IS NOT NULL) AND (tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)));


--
-- Name: tenant_membership_roles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tenant_membership_roles ENABLE ROW LEVEL SECURITY;

--
-- Name: tenant_memberships; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tenant_memberships ENABLE ROW LEVEL SECURITY;

--
-- Name: trust_access_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.trust_access_log ENABLE ROW LEVEL SECURITY;

--
-- Name: trust_envelope_issuance_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.trust_envelope_issuance_log ENABLE ROW LEVEL SECURITY;

--
-- Name: trust_export_artifact_attempts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.trust_export_artifact_attempts ENABLE ROW LEVEL SECURITY;

--
-- Name: trust_issuance_attempts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.trust_issuance_attempts ENABLE ROW LEVEL SECURITY;

--
-- Name: trust_rate_limit_state; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.trust_rate_limit_state ENABLE ROW LEVEL SECURITY;

--
-- Name: trust_replay_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.trust_replay_events ENABLE ROW LEVEL SECURITY;

--
-- Name: trust_request_nonces; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.trust_request_nonces ENABLE ROW LEVEL SECURITY;

--
-- Name: trust_scope_denial_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.trust_scope_denial_events ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

--
-- Name: users users_provision_insert_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY users_provision_insert_policy ON public.users FOR INSERT TO app_user WITH CHECK (((id IS NOT NULL) AND (length(TRIM(BOTH FROM login_identifier_hash)) > 0) AND (auth_provider = ANY (ARRAY['password'::text, 'oauth_google'::text, 'oauth_microsoft'::text, 'oauth_github'::text, 'sso'::text]))));


--
-- Name: users users_self_select_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY users_self_select_policy ON public.users FOR SELECT USING ((id = (current_setting('app.current_user_id'::text, true))::uuid));


--
-- Name: users users_self_update_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY users_self_update_policy ON public.users FOR UPDATE USING ((id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((id = (current_setting('app.current_user_id'::text, true))::uuid));


--
-- Name: webhook_ingress_identities; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.webhook_ingress_identities ENABLE ROW LEVEL SECURITY;

--
-- Name: worker_failed_jobs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.worker_failed_jobs ENABLE ROW LEVEL SECURITY;

--
-- Name: worker_side_effects; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.worker_side_effects ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict QsUcjoLVBbEIoyyMaF4RS5kfY5mMsWSbLomjXrS662qIcRJQdpcE98GuOfjq7Jd

