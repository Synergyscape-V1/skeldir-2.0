CREATE SCHEMA auth;

CREATE SCHEMA security;

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;

CREATE FUNCTION auth.lookup_user_auth_by_login_hash(p_login_identifier_hash text) RETURNS TABLE(user_id uuid, is_active boolean, auth_provider text, password_hash text)
    LANGUAGE sql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
            SELECT
                u.id AS user_id,
                u.is_active,
                u.auth_provider,
                u.password_hash
            FROM users AS u
            WHERE login_identifier_hash = p_login_identifier_hash
            LIMIT 1
        $$;

CREATE FUNCTION auth.lookup_user_by_login_hash(p_login_identifier_hash text) RETURNS TABLE(user_id uuid, is_active boolean, auth_provider text)
    LANGUAGE sql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
            SELECT
                u.id AS user_id,
                u.is_active,
                u.auth_provider
            FROM users AS u
            WHERE login_identifier_hash = p_login_identifier_hash
            LIMIT 1
        $$;

CREATE FUNCTION public.check_allocation_sum() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            event_revenue INTEGER;
            allocated_sum INTEGER;
            tolerance_cents INTEGER := 1;
        BEGIN
            SELECT revenue_cents INTO event_revenue
            FROM attribution_events
            WHERE id = COALESCE(event_id, event_id);

            SELECT COALESCE(SUM(allocated_revenue_cents), 0) INTO allocated_sum
            FROM attribution_allocations
            WHERE event_id = COALESCE(event_id, event_id)
              AND model_version = COALESCE(model_version, model_version);

            IF ABS(allocated_sum - event_revenue) > tolerance_cents THEN
                RAISE EXCEPTION 'Allocation sum mismatch: allocated=% expected=% drift=%',
                    allocated_sum, event_revenue, ABS(allocated_sum - event_revenue);
            END IF;

            RETURN COALESCE(NEW, OLD);
        END;
        $$;

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
              ON tenant_id = tenant_id
             AND id = event_id
            CROSS JOIN LATERAL (
                SELECT COALESCE(SUM(allocated_revenue_cents), 0) AS allocated_sum
                FROM attribution_allocations aa
                WHERE tenant_id = tenant_id
                  AND event_id = event_id
                  AND (
                    (a.recompute_job_id IS NOT NULL AND aa.recompute_job_id = a.recompute_job_id)
                    OR (
                        a.recompute_job_id IS NULL
                        AND recompute_job_id IS NULL
                        AND model_version = model_version
                    )
                  )
            ) s
            WHERE ABS(allocated_sum - revenue_cents) > tolerance_cents
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
              ON tenant_id = tenant_id
             AND id = event_id
            CROSS JOIN LATERAL (
                SELECT COALESCE(SUM(allocated_revenue_cents), 0) AS allocated_sum
                FROM attribution_allocations aa
                WHERE tenant_id = tenant_id
                  AND event_id = event_id
                  AND (
                    (a.recompute_job_id IS NOT NULL AND aa.recompute_job_id = a.recompute_job_id)
                    OR (
                        a.recompute_job_id IS NULL
                        AND recompute_job_id IS NULL
                        AND model_version = model_version
                    )
                  )
            ) s
            WHERE ABS(allocated_sum - revenue_cents) > tolerance_cents
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
              ON tenant_id = tenant_id
             AND id = event_id
            CROSS JOIN LATERAL (
                SELECT COALESCE(SUM(allocated_revenue_cents), 0) AS allocated_sum
                FROM attribution_allocations aa
                WHERE tenant_id = tenant_id
                  AND event_id = event_id
                  AND (
                    (a.recompute_job_id IS NOT NULL AND aa.recompute_job_id = a.recompute_job_id)
                    OR (
                        a.recompute_job_id IS NULL
                        AND recompute_job_id IS NULL
                        AND model_version = model_version
                    )
                  )
            ) s
            WHERE ABS(allocated_sum - revenue_cents) > tolerance_cents
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
                    FROM attribution_commerce_identities
                    WHERE last_observed_at < cutoff
                    ORDER BY last_observed_at ASC
                    LIMIT GREATEST(max_delete, 1)
                )
                DELETE FROM public.attribution_commerce_identities target
                USING doomed
                WHERE id = id;

                GET DIAGNOSTICS deleted_count = ROW_COUNT;
                RETURN deleted_count;
            END;
            $$;

CREATE FUNCTION public.fn_b23_p0_prune_attribution_commerce_identities_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
            BEGIN
                PERFORM public.fn_b23_p0_prune_attribution_commerce_identities(1000);
                RETURN NULL;
            END;
            $$;

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

CREATE FUNCTION public.fn_bind_session_authority_from_event() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            authority_now timestamptz;
        BEGIN
            authority_now := now();
            IF NEW.session_id IS NULL THEN
                NEW.session_id := gen_random_uuid();
            END IF;

            INSERT INTO public.session_authority
            (
                tenant_id,
                session_id,
                issued_at,
                expires_at,
                last_seen_at,
                invalidated_at,
                invalidation_reason,
                issued_by,
                created_at,
                updated_at
            )
            VALUES
            (
                NEW.tenant_id,
                NEW.session_id,
                authority_now,
                authority_now + interval '24 hours',
                authority_now,
                NULL,
                NULL,
                'attribution_event_insert',
                authority_now,
                authority_now
            )
            ON CONFLICT (tenant_id, session_id)
            DO UPDATE SET
                last_seen_at = GREATEST(public.session_authority.last_seen_at, EXCLUDED.last_seen_at),
                updated_at = EXCLUDED.updated_at;

            IF EXISTS (
                SELECT 1
                FROM session_authority sa
                WHERE tenant_id = tenant_id
                  AND session_id = session_id
                  AND (invalidated_at IS NOT NULL OR expires_at <= authority_now)
            ) THEN
                RAISE EXCEPTION
                    'session authority violation: stale or invalidated session_id on attribution_events insert';
            END IF;

            RETURN NEW;
        END;
        $$;

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

CREATE FUNCTION public.fn_compliance_audit_ledger_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            RAISE EXCEPTION
                'compliance_audit_ledger is append-only; UPDATE and DELETE are forbidden';
        END;
        $$;

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

CREATE FUNCTION public.fn_events_prevent_mutation() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN

            IF current_user = 'migration_owner' THEN
                RETURN NULL;
            END IF;

            RAISE EXCEPTION 'attribution_events is append-only; updates and deletes are not allowed. Use INSERT with correlation_id for corrections.';
        END;
        $$;

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

CREATE FUNCTION public.fn_ledger_prevent_mutation() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN

            IF current_user = 'migration_owner' THEN
                RETURN NULL;
            END IF;

            RAISE EXCEPTION 'revenue_ledger is immutable; updates and deletes are not allowed. Use INSERT for corrections.';
        END;
        $$;

CREATE FUNCTION public.fn_llm_call_audit_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            RAISE EXCEPTION 'llm_call_audit is append-only; UPDATE and DELETE are forbidden';
        END;
        $$;

CREATE FUNCTION public.fn_log_channel_assignment_correction() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
        DECLARE
            correction_by_val VARCHAR(255);
            correction_reason_val TEXT;
        BEGIN

            IF (NEW.channel_code IS DISTINCT FROM OLD.channel_code) THEN

                correction_by_val := COALESCE(
                    current_setting('app.correction_by', true),
                    'system'
                );
                correction_reason_val := COALESCE(
                    NULLIF(current_setting('app.correction_reason', true), ''),
                    'No reason provided'
                );

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

CREATE FUNCTION public.fn_log_channel_state_change() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
        DECLARE
            change_by_val VARCHAR(255);
            change_reason_val TEXT;
        BEGIN

            IF (NEW.state IS DISTINCT FROM OLD.state) THEN

                change_by_val := COALESCE(
                    current_setting('app.channel_state_change_by', true),
                    'system'
                );
                change_reason_val := NULLIF(
                    current_setting('app.channel_state_change_reason', true),
                    ''
                );

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

CREATE FUNCTION public.fn_scan_pii_contamination() RETURNS integer
    LANGUAGE plpgsql
    AS $$
        DECLARE
            finding_count INTEGER := 0;
            rec RECORD;
            detected_key_var TEXT;
        BEGIN

            FOR rec IN
                SELECT id, raw_payload
                FROM attribution_events
                WHERE fn_detect_pii_keys(raw_payload)
            LOOP

                SELECT key INTO detected_key_var
                FROM jsonb_object_keys(raw_payload) key
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
                    'Redacted for security'
                );

                finding_count := finding_count + 1;
            END LOOP;

            FOR rec IN
                SELECT id, raw_payload
                FROM dead_events
                WHERE fn_detect_pii_keys(raw_payload)
            LOOP

                SELECT key INTO detected_key_var
                FROM jsonb_object_keys(raw_payload) key
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

            FOR rec IN
                SELECT id, metadata
                FROM revenue_ledger
                WHERE metadata IS NOT NULL AND fn_detect_pii_keys(metadata)
            LOOP

                SELECT key INTO detected_key_var
                FROM jsonb_object_keys(metadata) key
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
          FROM tenants t
          WHERE api_key_hash = $1
          LIMIT 1
        $_$;

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);

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

CREATE TABLE public.auth_user_token_cutoffs (
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    tokens_invalid_before timestamp with time zone NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by_user_id uuid
);

ALTER TABLE ONLY public.auth_user_token_cutoffs FORCE ROW LEVEL SECURITY;

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

CREATE SEQUENCE public.celery_taskmeta_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.celery_taskmeta_id_seq OWNED BY public.celery_taskmeta.id;

CREATE TABLE public.celery_tasksetmeta (
    id integer NOT NULL,
    taskset_id character varying(155) NOT NULL,
    result bytea,
    date_done timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE SEQUENCE public.celery_tasksetmeta_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.celery_tasksetmeta_id_seq OWNED BY public.celery_tasksetmeta.id;

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
    CONSTRAINT explanation_cache_cache_hit_count_check CHECK ((cache_hit_count >= 0))
);

ALTER TABLE ONLY public.explanation_cache FORCE ROW LEVEL SECURITY;

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

CREATE TABLE public.kombu_message (
    id integer NOT NULL,
    visible boolean DEFAULT true NOT NULL,
    "timestamp" timestamp without time zone,
    payload text NOT NULL,
    version smallint DEFAULT '1'::smallint NOT NULL,
    queue_id integer NOT NULL
);

CREATE SEQUENCE public.kombu_message_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.kombu_message_id_seq OWNED BY public.kombu_message.id;

CREATE TABLE public.kombu_queue (
    id integer NOT NULL,
    name character varying(200) NOT NULL
);

CREATE SEQUENCE public.kombu_queue_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.kombu_queue_id_seq OWNED BY public.kombu_queue.id;

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

CREATE SEQUENCE public.message_id_sequence
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.message_id_sequence OWNED BY public.kombu_message.id;

CREATE MATERIALIZED VIEW mv_allocation_summary AS
 SELECT tenant_id,
    event_id,
    model_version,
    sum(allocated_revenue_cents) AS total_allocated_cents,
    revenue_cents AS event_revenue_cents,
        CASE
            WHEN (revenue_cents IS NULL) THEN NULL::boolean
            ELSE (sum(allocated_revenue_cents) = revenue_cents)
        END AS is_balanced,
        CASE
            WHEN (revenue_cents IS NULL) THEN NULL::bigint
            ELSE abs((sum(allocated_revenue_cents) - revenue_cents))
        END AS drift_cents
   FROM (attribution_allocations aa
     LEFT JOIN attribution_events e ON ((event_id = id)))
  GROUP BY tenant_id, event_id, model_version, revenue_cents
  WITH NO DATA;

CREATE MATERIALIZED VIEW mv_channel_performance AS
 SELECT tenant_id,
    channel_code,
    date_trunc('day'::text, created_at) AS allocation_date,
    count(DISTINCT event_id) AS total_conversions,
    sum(allocated_revenue_cents) AS total_revenue_cents,
    avg(confidence_score) AS avg_confidence_score,
    count(*) AS total_allocations
   FROM attribution_allocations
  WHERE (created_at >= (CURRENT_DATE - '90 days'::interval))
  GROUP BY tenant_id, channel_code, (date_trunc('day'::text, created_at))
  WITH NO DATA;

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

CREATE MATERIALIZED VIEW mv_daily_revenue_summary AS
 SELECT tenant_id,
    date_trunc('day'::text, verification_timestamp) AS revenue_date,
    state,
    currency,
    sum(amount_cents) AS total_amount_cents,
    count(*) AS transaction_count
   FROM revenue_ledger
  WHERE ((state)::text = ANY ((ARRAY['captured'::character varying, 'refunded'::character varying, 'chargeback'::character varying])::text[]))
  GROUP BY tenant_id, (date_trunc('day'::text, verification_timestamp)), state, currency
  WITH NO DATA;

CREATE MATERIALIZED VIEW mv_realtime_revenue AS
 SELECT tenant_id,
    ((COALESCE(sum(COALESCE(amount_cents, revenue_cents)), (0)::bigint))::numeric / 100.0) AS total_revenue,
    bool_or(COALESCE(is_verified, false)) AS verified,
    (EXTRACT(epoch FROM (now() - max(updated_at))))::integer AS data_freshness_seconds
   FROM revenue_ledger rl
  GROUP BY tenant_id
  WITH NO DATA;

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

CREATE MATERIALIZED VIEW mv_reconciliation_status AS
 SELECT tenant_id,
    state,
    last_run_at,
    id AS reconciliation_run_id
   FROM (reconciliation_runs rr
     JOIN ( SELECT tenant_id,
            max(last_run_at) AS max_last_run_at
           FROM reconciliation_runs
          GROUP BY tenant_id) latest ON (((tenant_id = tenant_id) AND (last_run_at = max_last_run_at))))
  WITH NO DATA;

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

CREATE TABLE public.pii_audit_findings (
    id bigint NOT NULL,
    table_name text NOT NULL,
    column_name text NOT NULL,
    record_id uuid NOT NULL,
    detected_key text NOT NULL,
    sample_snippet text,
    detected_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.pii_audit_findings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.pii_audit_findings_id_seq OWNED BY public.pii_audit_findings.id;

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

CREATE SEQUENCE public.queue_id_sequence
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.queue_id_sequence OWNED BY public.kombu_queue.id;

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

CREATE TABLE public.r4_recovery_exclusions (
    scenario text NOT NULL,
    task_id text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

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

CREATE TABLE public.roles (
    code text NOT NULL,
    description text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_roles_code_lowercase CHECK ((code = lower(code))),
    CONSTRAINT ck_roles_code_not_empty CHECK ((length(TRIM(BOTH FROM code)) > 0))
);

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

CREATE SEQUENCE public.task_id_sequence
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.task_id_sequence OWNED BY public.celery_taskmeta.id;

CREATE SEQUENCE public.taskset_id_sequence
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.taskset_id_sequence OWNED BY public.celery_tasksetmeta.id;

CREATE TABLE public.tenant_membership_roles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    membership_id uuid NOT NULL,
    role_code text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.tenant_membership_roles FORCE ROW LEVEL SECURITY;

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

CREATE TABLE public.worker_side_effects (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    task_id text NOT NULL,
    correlation_id uuid,
    effect_key text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.worker_side_effects FORCE ROW LEVEL SECURITY;

ALTER TABLE ONLY public.celery_taskmeta ALTER COLUMN id SET DEFAULT nextval('public.task_id_sequence'::regclass);

ALTER TABLE ONLY public.celery_tasksetmeta ALTER COLUMN id SET DEFAULT nextval('public.taskset_id_sequence'::regclass);

ALTER TABLE ONLY public.kombu_message ALTER COLUMN id SET DEFAULT nextval('public.message_id_sequence'::regclass);

ALTER TABLE ONLY public.kombu_queue ALTER COLUMN id SET DEFAULT nextval('public.queue_id_sequence'::regclass);

ALTER TABLE ONLY public.pii_audit_findings ALTER COLUMN id SET DEFAULT nextval('public.pii_audit_findings_id_seq'::regclass);

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);

ALTER TABLE ONLY public.attribution_allocations
    ADD CONSTRAINT attribution_allocations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.attribution_commerce_identities
    ADD CONSTRAINT attribution_commerce_identities_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.attribution_events
    ADD CONSTRAINT attribution_events_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.attribution_recompute_jobs
    ADD CONSTRAINT attribution_recompute_jobs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.auth_refresh_tokens
    ADD CONSTRAINT auth_refresh_tokens_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.b23_exception_records
    ADD CONSTRAINT b23_exception_records_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.b23_match_verdicts
    ADD CONSTRAINT b23_match_verdicts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.b23_revenue_events
    ADD CONSTRAINT b23_revenue_events_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.b23_webhook_ingestion_logs
    ADD CONSTRAINT b23_webhook_ingestion_logs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.budget_jobs
    ADD CONSTRAINT budget_jobs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.budget_optimization_jobs
    ADD CONSTRAINT budget_optimization_jobs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.worker_failed_jobs
    ADD CONSTRAINT celery_task_failures_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.celery_taskmeta
    ADD CONSTRAINT celery_taskmeta_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.celery_taskmeta
    ADD CONSTRAINT celery_taskmeta_task_id_key UNIQUE (task_id);

ALTER TABLE ONLY public.celery_tasksetmeta
    ADD CONSTRAINT celery_tasksetmeta_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.celery_tasksetmeta
    ADD CONSTRAINT celery_tasksetmeta_taskset_id_key UNIQUE (taskset_id);

ALTER TABLE ONLY public.channel_assignment_corrections
    ADD CONSTRAINT channel_assignment_corrections_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.channel_state_transitions
    ADD CONSTRAINT channel_state_transitions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.channel_taxonomy
    ADD CONSTRAINT channel_taxonomy_pkey PRIMARY KEY (code);

ALTER TABLE public.b23_match_verdicts
    ADD CONSTRAINT ck_b23_match_verdicts_matched_requires_attribution_event CHECK ((((status)::text <> ALL ((ARRAY['matched_provisional'::character varying, 'matched_confirmed'::character varying, 'adjusted'::character varying])::text[])) OR (attribution_event_id IS NOT NULL))) NOT VALID;

ALTER TABLE ONLY public.compliance_audit_ledger
    ADD CONSTRAINT compliance_audit_ledger_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.dead_events
    ADD CONSTRAINT dead_events_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.dead_events_quarantine
    ADD CONSTRAINT dead_events_quarantine_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.ephemeral_click_resolution
    ADD CONSTRAINT ephemeral_click_resolution_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.ephemeral_order_resolution
    ADD CONSTRAINT ephemeral_order_resolution_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.explanation_cache
    ADD CONSTRAINT explanation_cache_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.explanation_cache
    ADD CONSTRAINT explanation_cache_tenant_id_entity_type_entity_id_key UNIQUE (tenant_id, entity_type, entity_id);

ALTER TABLE ONLY public.investigation_jobs
    ADD CONSTRAINT investigation_jobs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.investigation_tool_calls
    ADD CONSTRAINT investigation_tool_calls_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT investigations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.jwt_verification_cache
    ADD CONSTRAINT jwt_verification_cache_pkey PRIMARY KEY (singleton_id);

ALTER TABLE ONLY public.kombu_message
    ADD CONSTRAINT kombu_message_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.kombu_queue
    ADD CONSTRAINT kombu_queue_name_key UNIQUE (name);

ALTER TABLE ONLY public.kombu_queue
    ADD CONSTRAINT kombu_queue_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.llm_api_calls
    ADD CONSTRAINT llm_api_calls_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.llm_breaker_state
    ADD CONSTRAINT llm_breaker_state_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.llm_breaker_state
    ADD CONSTRAINT llm_breaker_state_tenant_id_user_id_breaker_key_key UNIQUE (tenant_id, user_id, breaker_key);

ALTER TABLE ONLY public.llm_budget_reservations
    ADD CONSTRAINT llm_budget_reservations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.llm_budget_reservations
    ADD CONSTRAINT llm_budget_reservations_tenant_id_user_id_endpoint_request__key UNIQUE (tenant_id, user_id, endpoint, request_id);

ALTER TABLE ONLY public.llm_call_audit
    ADD CONSTRAINT llm_call_audit_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.llm_hourly_shutoff_state
    ADD CONSTRAINT llm_hourly_shutoff_state_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.llm_hourly_shutoff_state
    ADD CONSTRAINT llm_hourly_shutoff_state_tenant_id_user_id_hour_start_key UNIQUE (tenant_id, user_id, hour_start);

ALTER TABLE ONLY public.llm_monthly_budget_state
    ADD CONSTRAINT llm_monthly_budget_state_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.llm_monthly_budget_state
    ADD CONSTRAINT llm_monthly_budget_state_tenant_id_user_id_month_key UNIQUE (tenant_id, user_id, month);

ALTER TABLE ONLY public.llm_monthly_costs
    ADD CONSTRAINT llm_monthly_costs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.llm_semantic_cache
    ADD CONSTRAINT llm_semantic_cache_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.llm_semantic_cache
    ADD CONSTRAINT llm_semantic_cache_tenant_id_user_id_endpoint_cache_key_key UNIQUE (tenant_id, user_id, endpoint, cache_key);

ALTER TABLE ONLY public.llm_validation_failures
    ADD CONSTRAINT llm_validation_failures_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.oauth_handshake_sessions
    ADD CONSTRAINT oauth_handshake_sessions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.pii_audit_findings
    ADD CONSTRAINT pii_audit_findings_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.auth_access_token_denylist
    ADD CONSTRAINT pk_auth_access_token_denylist PRIMARY KEY (tenant_id, user_id, jti);

ALTER TABLE ONLY public.auth_user_token_cutoffs
    ADD CONSTRAINT pk_auth_user_token_cutoffs PRIMARY KEY (tenant_id, user_id);

ALTER TABLE ONLY public.platform_connections
    ADD CONSTRAINT platform_connections_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.platform_credentials
    ADD CONSTRAINT platform_credentials_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.r4_crash_barriers
    ADD CONSTRAINT r4_crash_barriers_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.r4_recovery_exclusions
    ADD CONSTRAINT r4_recovery_exclusions_pkey PRIMARY KEY (scenario, task_id);

ALTER TABLE ONLY public.r4_task_attempts
    ADD CONSTRAINT r4_task_attempts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.raw_event_payloads
    ADD CONSTRAINT raw_event_payloads_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.reconciliation_runs
    ADD CONSTRAINT reconciliation_runs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.revenue_cache_entries
    ADD CONSTRAINT revenue_cache_entries_pkey PRIMARY KEY (tenant_id, cache_key);

ALTER TABLE ONLY public.revenue_ledger
    ADD CONSTRAINT revenue_ledger_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.revenue_state_transitions
    ADD CONSTRAINT revenue_state_transitions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (code);

ALTER TABLE ONLY public.session_authority
    ADD CONSTRAINT session_authority_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.tenant_membership_roles
    ADD CONSTRAINT tenant_membership_roles_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT tenant_memberships_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.attribution_commerce_identities
    ADD CONSTRAINT uq_attr_commerce_identity_tenant_event UNIQUE (tenant_id, attribution_event_id);

ALTER TABLE ONLY public.attribution_commerce_identities
    ADD CONSTRAINT uq_attr_commerce_identity_tenant_provider_reference UNIQUE (tenant_id, provider, canonical_commerce_reference);

ALTER TABLE ONLY public.attribution_events
    ADD CONSTRAINT uq_attribution_events_tenant_idempotency_key UNIQUE (tenant_id, idempotency_key);

ALTER TABLE ONLY public.b23_match_verdicts
    ADD CONSTRAINT uq_b23_match_verdicts_tenant_provider_event_ref UNIQUE (tenant_id, provider, provider_native_event_reference);

ALTER TABLE ONLY public.b23_revenue_events
    ADD CONSTRAINT uq_b23_revenue_events_tenant_provider_event_ref UNIQUE (tenant_id, provider, provider_native_event_reference);

ALTER TABLE ONLY public.budget_jobs
    ADD CONSTRAINT uq_budget_jobs_tenant_request_id UNIQUE (tenant_id, request_id);

ALTER TABLE ONLY public.budget_optimization_jobs
    ADD CONSTRAINT uq_budget_optimization_jobs_tenant_request_id UNIQUE (tenant_id, request_id);

ALTER TABLE ONLY public.compliance_audit_ledger
    ADD CONSTRAINT uq_compliance_audit_ledger_tenant_idempotency_key UNIQUE (tenant_id, idempotency_key);

ALTER TABLE ONLY public.ephemeral_click_resolution
    ADD CONSTRAINT uq_ephemeral_click_resolution_tenant_click UNIQUE (tenant_id, click_id);

ALTER TABLE ONLY public.ephemeral_order_resolution
    ADD CONSTRAINT uq_ephemeral_order_resolution_tenant_order UNIQUE (tenant_id, order_id);

ALTER TABLE ONLY public.investigation_jobs
    ADD CONSTRAINT uq_investigation_jobs_tenant_request_id UNIQUE (tenant_id, request_id);

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT uq_investigations_tenant_request_id UNIQUE (tenant_id, request_id);

ALTER TABLE ONLY public.llm_api_calls
    ADD CONSTRAINT uq_llm_api_calls_tenant_request_endpoint UNIQUE (tenant_id, request_id, endpoint);

ALTER TABLE ONLY public.llm_monthly_costs
    ADD CONSTRAINT uq_llm_monthly_costs_tenant_user_month UNIQUE (tenant_id, user_id, month);

ALTER TABLE ONLY public.oauth_handshake_sessions
    ADD CONSTRAINT uq_oauth_handshake_sessions_tenant_state_hash UNIQUE (tenant_id, state_nonce_hash);

ALTER TABLE ONLY public.raw_event_payloads
    ADD CONSTRAINT uq_raw_event_payloads_tenant_event UNIQUE (tenant_id, event_id);

ALTER TABLE ONLY public.session_authority
    ADD CONSTRAINT uq_session_authority_tenant_session_id UNIQUE (tenant_id, session_id);

ALTER TABLE ONLY public.tenant_membership_roles
    ADD CONSTRAINT uq_tenant_membership_roles_membership_role UNIQUE (membership_id, role_code);

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT uq_tenant_memberships_id_tenant UNIQUE (id, tenant_id);

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT uq_tenant_memberships_tenant_user UNIQUE (tenant_id, user_id);

ALTER TABLE ONLY public.webhook_ingress_identities
    ADD CONSTRAINT uq_webhook_ingress_identities_event_id UNIQUE (event_id);

ALTER TABLE ONLY public.webhook_ingress_identities
    ADD CONSTRAINT uq_webhook_ingress_identities_tenant_event UNIQUE (tenant_id, event_id);

ALTER TABLE ONLY public.webhook_ingress_identities
    ADD CONSTRAINT uq_webhook_ingress_identities_tenant_idempotency UNIQUE (tenant_id, idempotency_key);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_login_identifier_hash_key UNIQUE (login_identifier_hash);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.webhook_ingress_identities
    ADD CONSTRAINT webhook_ingress_identities_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.worker_side_effects
    ADD CONSTRAINT worker_side_effects_pkey PRIMARY KEY (id);

CREATE INDEX idx_allocations_channel_performance ON public.attribution_allocations USING btree (tenant_id, channel_code, created_at DESC) INCLUDE (allocated_revenue_cents, confidence_score);

CREATE INDEX idx_allocations_tenant_projection_channel ON public.attribution_allocations USING btree (tenant_id, recompute_job_id, model_type, channel_code);

CREATE INDEX idx_attr_commerce_identity_last_observed ON public.attribution_commerce_identities USING btree (last_observed_at);

CREATE INDEX idx_attr_commerce_identity_tenant_last_observed ON public.attribution_commerce_identities USING btree (tenant_id, last_observed_at DESC);

CREATE INDEX idx_attr_commerce_identity_tenant_provider_reference ON public.attribution_commerce_identities USING btree (tenant_id, provider, canonical_commerce_reference);

CREATE INDEX idx_attribution_allocations_channel ON public.attribution_allocations USING btree (channel_code);

CREATE INDEX idx_attribution_allocations_event_id ON public.attribution_allocations USING btree (event_id);

CREATE INDEX idx_attribution_allocations_tenant_created_at ON public.attribution_allocations USING btree (tenant_id, created_at DESC);

CREATE INDEX idx_attribution_allocations_tenant_event_model ON public.attribution_allocations USING btree (tenant_id, event_id, model_version);

CREATE UNIQUE INDEX idx_attribution_allocations_tenant_event_model_channel ON public.attribution_allocations USING btree (tenant_id, event_id, model_version, channel_code) WHERE ((model_version IS NOT NULL) AND (recompute_job_id IS NULL));

CREATE INDEX idx_attribution_allocations_tenant_event_projection ON public.attribution_allocations USING btree (tenant_id, event_id, recompute_job_id) WHERE (recompute_job_id IS NOT NULL);

CREATE UNIQUE INDEX idx_attribution_allocations_tenant_event_projection_channel ON public.attribution_allocations USING btree (tenant_id, event_id, recompute_job_id, channel_code) WHERE (recompute_job_id IS NOT NULL);

CREATE INDEX idx_attribution_allocations_tenant_model_version ON public.attribution_allocations USING btree (tenant_id, model_version);

CREATE INDEX idx_attribution_events_session_id ON public.attribution_events USING btree (session_id) WHERE (session_id IS NOT NULL);

CREATE INDEX idx_attribution_events_tenant_occurred_at ON public.attribution_events USING btree (tenant_id, occurred_at DESC);

CREATE INDEX idx_attribution_recompute_jobs_tenant_created_at ON public.attribution_recompute_jobs USING btree (tenant_id, created_at DESC);

CREATE INDEX idx_attribution_recompute_jobs_tenant_status ON public.attribution_recompute_jobs USING btree (tenant_id, status);

CREATE UNIQUE INDEX idx_attribution_recompute_jobs_window_identity ON public.attribution_recompute_jobs USING btree (tenant_id, window_start, window_end, model_version);

CREATE INDEX idx_auth_access_token_denylist_expires_at ON public.auth_access_token_denylist USING btree (expires_at DESC);

CREATE INDEX idx_auth_access_token_denylist_jti ON public.auth_access_token_denylist USING btree (jti);

CREATE INDEX idx_auth_access_token_denylist_tenant_user_revoked_at ON public.auth_access_token_denylist USING btree (tenant_id, user_id, revoked_at DESC);

CREATE INDEX idx_auth_refresh_tokens_family_created_at ON public.auth_refresh_tokens USING btree (family_id, created_at DESC);

CREATE INDEX idx_auth_refresh_tokens_tenant_created_at ON public.auth_refresh_tokens USING btree (tenant_id, created_at DESC);

CREATE INDEX idx_auth_refresh_tokens_tenant_user_created_at ON public.auth_refresh_tokens USING btree (tenant_id, user_id, created_at DESC);

CREATE INDEX idx_auth_user_token_cutoffs_tenant_user ON public.auth_user_token_cutoffs USING btree (tenant_id, user_id);

CREATE INDEX idx_b23_exception_records_tenant_provider_reference ON public.b23_exception_records USING btree (tenant_id, provider, canonical_commerce_reference);

CREATE INDEX idx_b23_exception_records_tenant_status_severity ON public.b23_exception_records USING btree (tenant_id, status, severity, raised_at DESC);

CREATE INDEX idx_b23_match_verdicts_tenant_discrepancy_band ON public.b23_match_verdicts USING btree (tenant_id, discrepancy_band, last_transition_at DESC);

CREATE INDEX idx_b23_match_verdicts_tenant_discrepancy_ratio_bps ON public.b23_match_verdicts USING btree (tenant_id, discrepancy_ratio_bps, last_transition_at DESC);

CREATE INDEX idx_b23_match_verdicts_tenant_provider_commerce_native ON public.b23_match_verdicts USING btree (tenant_id, provider, provider_native_commerce_reference);

CREATE INDEX idx_b23_match_verdicts_tenant_provider_reference ON public.b23_match_verdicts USING btree (tenant_id, provider, canonical_commerce_reference);

CREATE INDEX idx_b23_match_verdicts_tenant_state_timestamps ON public.b23_match_verdicts USING btree (tenant_id, pending_since, provisional_expires_at, confirmed_at, unmatched_marked_at, adjusted_at);

CREATE INDEX idx_b23_match_verdicts_tenant_status_transition ON public.b23_match_verdicts USING btree (tenant_id, status, last_transition_at DESC);

CREATE INDEX idx_b23_p4_attribution_event_tenant_id ON public.attribution_events USING btree (tenant_id, id);

CREATE INDEX idx_b23_p4_attribution_order_ref_expr ON public.attribution_events USING btree (tenant_id, ((raw_payload ->> 'order_id'::text)), occurred_at DESC) WHERE (raw_payload ? 'order_id'::text);

CREATE INDEX idx_b23_p4_match_rate_tenant_transition_status ON public.b23_match_verdicts USING btree (tenant_id, last_transition_at DESC, status) WHERE ((status)::text = ANY ((ARRAY['matched_provisional'::character varying, 'matched_confirmed'::character varying, 'adjusted'::character varying, 'unmatched'::character varying])::text[]));

CREATE INDEX idx_b23_p4_verdict_webhook_identity ON public.b23_match_verdicts USING btree (tenant_id, webhook_ingress_identity_id) WHERE (webhook_ingress_identity_id IS NOT NULL);

CREATE INDEX idx_b23_p4_webhook_failure_tenant_platform_time ON public.b23_webhook_ingestion_logs USING btree (tenant_id, provider, received_at DESC) WHERE ((ingestion_status)::text = 'failed'::text);

CREATE INDEX idx_b23_p4_webhook_identity_claim ON public.webhook_ingress_identities USING btree (tenant_id, verified_commerce_ingress_state, event_timestamp, id) WHERE ((verified_commerce_ingress_state)::text = 'authenticity_verified'::text);

CREATE INDEX idx_b23_p4_worker_dlq_open_status_failed_at ON public.worker_failed_jobs USING btree (status, tenant_id, failed_at DESC) WHERE ((status)::text = ANY ((ARRAY['pending'::character varying, 'in_progress'::character varying])::text[]));

CREATE INDEX idx_b23_revenue_events_tenant_event_effect_sign ON public.b23_revenue_events USING btree (tenant_id, event_type, net_effect_sign, event_occurred_at DESC);

CREATE INDEX idx_b23_revenue_events_tenant_event_type_recorded ON public.b23_revenue_events USING btree (tenant_id, event_type, recorded_at DESC);

CREATE INDEX idx_b23_revenue_events_tenant_gross_capture_correction ON public.b23_revenue_events USING btree (tenant_id, match_verdict_id, is_gross_capture_correction, event_occurred_at DESC);

CREATE INDEX idx_b23_revenue_events_tenant_provider_commerce_native ON public.b23_revenue_events USING btree (tenant_id, provider, provider_native_commerce_reference);

CREATE INDEX idx_b23_revenue_events_tenant_provider_reference ON public.b23_revenue_events USING btree (tenant_id, provider, canonical_commerce_reference, event_occurred_at DESC);

CREATE INDEX idx_b23_webhook_ingestion_logs_tenant_provider_received ON public.b23_webhook_ingestion_logs USING btree (tenant_id, provider, received_at DESC);

CREATE INDEX idx_b23_webhook_ingestion_logs_tenant_status_received ON public.b23_webhook_ingestion_logs USING btree (tenant_id, ingestion_status, received_at DESC);

CREATE INDEX idx_budget_jobs_tenant_status ON public.budget_optimization_jobs USING btree (tenant_id, status, created_at DESC);

CREATE INDEX idx_channel_assignment_corrections_channels ON public.channel_assignment_corrections USING btree (from_channel, to_channel, corrected_at DESC);

CREATE INDEX idx_channel_assignment_corrections_entity ON public.channel_assignment_corrections USING btree (tenant_id, entity_type, entity_id, corrected_at DESC);

CREATE INDEX idx_channel_assignment_corrections_tenant ON public.channel_assignment_corrections USING btree (tenant_id, corrected_at DESC);

CREATE INDEX idx_channel_state_transitions_channel_changed_at ON public.channel_state_transitions USING btree (channel_code, changed_at DESC);

CREATE INDEX idx_channel_state_transitions_to_state_changed_at ON public.channel_state_transitions USING btree (to_state, changed_at DESC);

CREATE INDEX idx_compliance_audit_ledger_tenant_correlation ON public.compliance_audit_ledger USING btree (tenant_id, correlation_id);

CREATE INDEX idx_compliance_audit_ledger_tenant_created ON public.compliance_audit_ledger USING btree (tenant_id, created_at DESC);

CREATE INDEX idx_dead_events_error_code ON public.dead_events USING btree (error_code);

CREATE INDEX idx_dead_events_quarantine_null_lane ON public.dead_events_quarantine USING btree (ingested_at DESC) WHERE (tenant_id IS NULL);

CREATE INDEX idx_dead_events_quarantine_tenant_idempotency_key ON public.dead_events_quarantine USING btree (tenant_id, idempotency_key) WHERE (idempotency_key IS NOT NULL);

CREATE INDEX idx_dead_events_quarantine_tenant_ingested_at ON public.dead_events_quarantine USING btree (tenant_id, ingested_at DESC);

CREATE INDEX idx_dead_events_remediation ON public.dead_events USING btree (remediation_status, ingested_at DESC);

CREATE INDEX idx_dead_events_source ON public.dead_events USING btree (source);

CREATE INDEX idx_dead_events_tenant_idempotency_key ON public.dead_events USING btree (tenant_id, idempotency_key) WHERE (idempotency_key IS NOT NULL);

CREATE INDEX idx_dead_events_tenant_ingested_at ON public.dead_events USING btree (tenant_id, ingested_at DESC);

CREATE INDEX idx_ephemeral_click_resolution_tenant_click ON public.ephemeral_click_resolution USING btree (tenant_id, click_id);

CREATE INDEX idx_ephemeral_click_resolution_tenant_expires ON public.ephemeral_click_resolution USING btree (tenant_id, expires_at);

CREATE INDEX idx_ephemeral_order_resolution_tenant_expires ON public.ephemeral_order_resolution USING btree (tenant_id, expires_at);

CREATE INDEX idx_ephemeral_order_resolution_tenant_order ON public.ephemeral_order_resolution USING btree (tenant_id, order_id);

CREATE INDEX idx_events_processing_status ON public.attribution_events USING btree (processing_status, processed_at) WHERE ((processing_status)::text = 'pending'::text);

CREATE INDEX idx_events_tenant_timestamp ON public.attribution_events USING btree (tenant_id, event_timestamp DESC);

CREATE INDEX idx_explanation_cache_lookup ON public.explanation_cache USING btree (tenant_id, entity_type, entity_id);

CREATE INDEX idx_investigation_jobs_min_hold ON public.investigation_jobs USING btree (min_hold_until) WHERE ((status)::text = 'PENDING'::text);

CREATE INDEX idx_investigation_jobs_tenant_status ON public.investigation_jobs USING btree (tenant_id, status, created_at DESC);

CREATE INDEX idx_investigations_tenant_status ON public.investigations USING btree (tenant_id, status, created_at DESC);

CREATE INDEX idx_llm_api_calls_prompt_fingerprint ON public.llm_api_calls USING btree (tenant_id, prompt_fingerprint, created_at DESC);

CREATE INDEX idx_llm_breaker_state_tenant_user_updated ON public.llm_breaker_state USING btree (tenant_id, user_id, updated_at DESC);

CREATE INDEX idx_llm_budget_reservations_tenant_user_month ON public.llm_budget_reservations USING btree (tenant_id, user_id, month DESC);

CREATE INDEX idx_llm_call_audit_decision ON public.llm_call_audit USING btree (decision, created_at DESC);

CREATE INDEX idx_llm_call_audit_prompt_fingerprint ON public.llm_call_audit USING btree (tenant_id, prompt_fingerprint, created_at DESC);

CREATE INDEX idx_llm_call_audit_request_id ON public.llm_call_audit USING btree (request_id);

CREATE INDEX idx_llm_call_audit_tenant_created ON public.llm_call_audit USING btree (tenant_id, created_at DESC);

CREATE INDEX idx_llm_call_audit_tenant_user_created ON public.llm_call_audit USING btree (tenant_id, user_id, created_at DESC);

CREATE INDEX idx_llm_calls_tenant_created_at ON public.llm_api_calls USING btree (tenant_id, created_at DESC);

CREATE INDEX idx_llm_calls_tenant_endpoint ON public.llm_api_calls USING btree (tenant_id, endpoint, created_at DESC);

CREATE INDEX idx_llm_calls_tenant_user_created_at ON public.llm_api_calls USING btree (tenant_id, user_id, created_at DESC);

CREATE INDEX idx_llm_failures_created_at ON public.llm_validation_failures USING btree (created_at DESC);

CREATE INDEX idx_llm_failures_tenant_endpoint ON public.llm_validation_failures USING btree (tenant_id, endpoint, created_at DESC);

CREATE INDEX idx_llm_hourly_shutoff_disabled_until ON public.llm_hourly_shutoff_state USING btree (tenant_id, user_id, disabled_until DESC);

CREATE INDEX idx_llm_hourly_shutoff_tenant_user_hour ON public.llm_hourly_shutoff_state USING btree (tenant_id, user_id, hour_start DESC);

CREATE INDEX idx_llm_monthly_budget_state_tenant_user_month ON public.llm_monthly_budget_state USING btree (tenant_id, user_id, month DESC);

CREATE INDEX idx_llm_monthly_tenant_user_month ON public.llm_monthly_costs USING btree (tenant_id, user_id, month DESC);

CREATE INDEX idx_llm_semantic_cache_tenant_user_endpoint ON public.llm_semantic_cache USING btree (tenant_id, user_id, endpoint, updated_at DESC);

CREATE UNIQUE INDEX idx_mv_allocation_summary_key ON public.mv_allocation_summary USING btree (tenant_id, event_id, model_version);

CREATE UNIQUE INDEX idx_mv_channel_performance_unique ON public.mv_channel_performance USING btree (tenant_id, channel_code, allocation_date);

CREATE UNIQUE INDEX idx_mv_daily_revenue_summary_unique ON public.mv_daily_revenue_summary USING btree (tenant_id, revenue_date, state, currency);

CREATE UNIQUE INDEX idx_mv_realtime_revenue_tenant_id ON public.mv_realtime_revenue USING btree (tenant_id);

CREATE UNIQUE INDEX idx_mv_reconciliation_status_tenant_id ON public.mv_reconciliation_status USING btree (tenant_id);

CREATE INDEX idx_oauth_handshake_sessions_expires_at ON public.oauth_handshake_sessions USING btree (expires_at DESC);

CREATE INDEX idx_oauth_handshake_sessions_gc_after ON public.oauth_handshake_sessions USING btree (gc_after);

CREATE INDEX idx_oauth_handshake_sessions_tenant_platform_user_created ON public.oauth_handshake_sessions USING btree (tenant_id, platform, user_id, created_at DESC);

CREATE INDEX idx_oauth_handshake_sessions_tenant_state_lookup ON public.oauth_handshake_sessions USING btree (tenant_id, state_nonce_hash, status);

CREATE INDEX idx_pii_audit_findings_detected_key ON public.pii_audit_findings USING btree (detected_key);

CREATE INDEX idx_pii_audit_findings_table_detected_at ON public.pii_audit_findings USING btree (table_name, detected_at DESC);

CREATE INDEX idx_platform_connections_tenant_platform_updated_at ON public.platform_connections USING btree (tenant_id, platform, updated_at DESC);

CREATE INDEX idx_platform_credentials_refresh_due ON public.platform_credentials USING btree (tenant_id, lifecycle_status, next_refresh_due_at) WHERE (next_refresh_due_at IS NOT NULL);

CREATE INDEX idx_platform_credentials_tenant_lifecycle_updated ON public.platform_credentials USING btree (tenant_id, lifecycle_status, updated_at DESC);

CREATE INDEX idx_platform_credentials_tenant_platform_updated_at ON public.platform_credentials USING btree (tenant_id, platform, updated_at DESC);

CREATE INDEX idx_platform_credentials_tenant_revoked_at ON public.platform_credentials USING btree (tenant_id, revoked_at DESC) WHERE (revoked_at IS NOT NULL);

CREATE INDEX idx_r4_crash_barriers_scenario_wrote_at ON public.r4_crash_barriers USING btree (scenario, wrote_at DESC);

CREATE INDEX idx_r4_task_attempts_scenario_created_at ON public.r4_task_attempts USING btree (scenario, created_at DESC);

CREATE INDEX idx_r4_task_attempts_tenant_task ON public.r4_task_attempts USING btree (tenant_id, task_id);

CREATE INDEX idx_raw_event_payloads_event_id ON public.raw_event_payloads USING btree (event_id);

CREATE INDEX idx_raw_event_payloads_payload_json_gin ON public.raw_event_payloads USING gin (payload_json jsonb_path_ops);

CREATE INDEX idx_raw_event_payloads_tenant_created ON public.raw_event_payloads USING btree (tenant_id, created_at DESC);

CREATE INDEX idx_raw_event_payloads_tenant_lookup_hash ON public.raw_event_payloads USING btree (tenant_id, lookup_hash);

CREATE INDEX idx_reconciliation_runs_state ON public.reconciliation_runs USING btree (state);

CREATE INDEX idx_reconciliation_runs_tenant_last_run_at ON public.reconciliation_runs USING btree (tenant_id, last_run_at DESC);

CREATE INDEX idx_revenue_cache_entries_error_cooldown ON public.revenue_cache_entries USING btree (error_cooldown_until);

CREATE INDEX idx_revenue_cache_entries_expires_at ON public.revenue_cache_entries USING btree (expires_at);

CREATE INDEX idx_revenue_ledger_is_verified ON public.revenue_ledger USING btree (is_verified) WHERE (is_verified = true);

CREATE INDEX idx_revenue_ledger_state ON public.revenue_ledger USING btree (state);

CREATE UNIQUE INDEX idx_revenue_ledger_tenant_allocation_id ON public.revenue_ledger USING btree (tenant_id, allocation_id) WHERE (allocation_id IS NOT NULL);

CREATE INDEX idx_revenue_ledger_tenant_order_reconciliation ON public.revenue_ledger USING btree (tenant_id, order_id, created_at DESC) WHERE (order_id IS NOT NULL);

CREATE INDEX idx_revenue_ledger_tenant_state ON public.revenue_ledger USING btree (tenant_id, state, created_at DESC);

CREATE INDEX idx_revenue_ledger_tenant_updated_at ON public.revenue_ledger USING btree (tenant_id, updated_at DESC);

CREATE UNIQUE INDEX idx_revenue_ledger_transaction_id ON public.revenue_ledger USING btree (transaction_id);

CREATE INDEX idx_revenue_state_transitions_ledger_id ON public.revenue_state_transitions USING btree (ledger_id, transitioned_at DESC);

CREATE INDEX idx_revenue_state_transitions_tenant_id ON public.revenue_state_transitions USING btree (tenant_id, transitioned_at DESC);

CREATE INDEX idx_session_authority_active ON public.session_authority USING btree (tenant_id, session_id, expires_at DESC) WHERE (invalidated_at IS NULL);

CREATE INDEX idx_session_authority_tenant_expires ON public.session_authority USING btree (tenant_id, expires_at DESC);

CREATE INDEX idx_session_authority_tenant_last_seen ON public.session_authority USING btree (tenant_id, last_seen_at DESC);

CREATE INDEX idx_tenant_membership_roles_tenant_created_at ON public.tenant_membership_roles USING btree (tenant_id, created_at DESC);

CREATE INDEX idx_tenant_memberships_tenant_created_at ON public.tenant_memberships USING btree (tenant_id, created_at DESC);

CREATE INDEX idx_tenant_memberships_user_created_at ON public.tenant_memberships USING btree (user_id, created_at DESC);

CREATE UNIQUE INDEX idx_tenants_api_key_hash ON public.tenants USING btree (api_key_hash);

CREATE INDEX idx_tenants_name ON public.tenants USING btree (name);

CREATE INDEX idx_tool_calls_investigation ON public.investigation_tool_calls USING btree (investigation_id, created_at);

CREATE INDEX idx_tool_calls_tenant ON public.investigation_tool_calls USING btree (tenant_id, created_at DESC);

CREATE INDEX idx_webhook_ingress_identities_tenant_provider_created ON public.webhook_ingress_identities USING btree (tenant_id, provider, created_at DESC);

CREATE INDEX idx_webhook_ingress_identities_tenant_reference ON public.webhook_ingress_identities USING btree (tenant_id, normalized_commerce_reference_kind, normalized_commerce_reference_value);

CREATE INDEX idx_webhook_ingress_identities_tenant_verified_state ON public.webhook_ingress_identities USING btree (tenant_id, verified_commerce_ingress_state, event_timestamp DESC);

CREATE INDEX idx_worker_failed_jobs_status ON public.worker_failed_jobs USING btree (status, failed_at);

CREATE INDEX idx_worker_failed_jobs_task_name ON public.worker_failed_jobs USING btree (task_name);

CREATE INDEX idx_worker_side_effects_tenant_created_at ON public.worker_side_effects USING btree (tenant_id, created_at DESC);

CREATE INDEX ix_celery_taskmeta_task_id ON public.celery_taskmeta USING btree (task_id);

CREATE INDEX ix_celery_tasksetmeta_taskset_id ON public.celery_tasksetmeta USING btree (taskset_id);

CREATE INDEX ix_kombu_message_timestamp_id ON public.kombu_message USING btree ("timestamp", id);

CREATE INDEX ix_kombu_message_visible ON public.kombu_message USING btree (visible);

CREATE INDEX ix_public_celery_task_failures_task_id ON public.worker_failed_jobs USING btree (task_id);

CREATE INDEX ix_public_celery_task_failures_task_name ON public.worker_failed_jobs USING btree (task_name);

CREATE INDEX ix_public_celery_task_failures_tenant_id ON public.worker_failed_jobs USING btree (tenant_id);

CREATE UNIQUE INDEX uq_b23_exception_records_one_open_per_verdict ON public.b23_exception_records USING btree (tenant_id, match_verdict_id) WHERE ((status)::text = ANY ((ARRAY['open'::character varying, 'acknowledged'::character varying])::text[]));

CREATE UNIQUE INDEX uq_platform_connections_tenant_platform_account ON public.platform_connections USING btree (tenant_id, platform, platform_account_id);

CREATE UNIQUE INDEX uq_platform_credentials_tenant_platform_connection ON public.platform_credentials USING btree (tenant_id, platform, platform_connection_id);

CREATE UNIQUE INDEX ux_r4_crash_barriers_tenant_task_attempt ON public.r4_crash_barriers USING btree (tenant_id, task_id, attempt_no);

CREATE UNIQUE INDEX ux_r4_task_attempts_tenant_task_attempt ON public.r4_task_attempts USING btree (tenant_id, task_id, attempt_no);

CREATE UNIQUE INDEX ux_worker_side_effects_tenant_task_id ON public.worker_side_effects USING btree (tenant_id, task_id);

CREATE TRIGGER trg_allocations_channel_correction_audit AFTER UPDATE OF channel_code ON public.attribution_allocations FOR EACH ROW WHEN ((old.channel_code IS DISTINCT FROM new.channel_code)) EXECUTE FUNCTION public.fn_log_channel_assignment_correction();

CREATE TRIGGER trg_b23_p0_prune_attribution_commerce_identities AFTER INSERT OR UPDATE OF last_observed_at ON public.attribution_commerce_identities FOR EACH STATEMENT EXECUTE FUNCTION public.fn_b23_p0_prune_attribution_commerce_identities_trigger();

CREATE TRIGGER trg_bind_session_authority_from_event BEFORE INSERT ON public.attribution_events FOR EACH ROW EXECUTE FUNCTION public.fn_bind_session_authority_from_event();

CREATE TRIGGER trg_block_worker_mutation_dead_events BEFORE INSERT OR DELETE OR UPDATE ON public.dead_events FOR EACH ROW EXECUTE FUNCTION public.fn_block_worker_ingestion_mutation();

CREATE TRIGGER trg_block_worker_mutation_events BEFORE INSERT OR DELETE OR UPDATE ON public.attribution_events FOR EACH ROW EXECUTE FUNCTION public.fn_block_worker_ingestion_mutation();

CREATE TRIGGER trg_channel_taxonomy_state_audit AFTER UPDATE OF state ON public.channel_taxonomy FOR EACH ROW WHEN (((old.state)::text IS DISTINCT FROM (new.state)::text)) EXECUTE FUNCTION public.fn_log_channel_state_change();

CREATE TRIGGER trg_check_allocation_sum AFTER INSERT ON public.attribution_allocations REFERENCING NEW TABLE AS newrows FOR EACH STATEMENT EXECUTE FUNCTION public.check_allocation_sum_stmt_insert();

CREATE TRIGGER trg_check_allocation_sum_delete AFTER DELETE ON public.attribution_allocations REFERENCING OLD TABLE AS oldrows FOR EACH STATEMENT EXECUTE FUNCTION public.check_allocation_sum_stmt_delete();

CREATE TRIGGER trg_check_allocation_sum_update AFTER UPDATE ON public.attribution_allocations REFERENCING OLD TABLE AS oldrows NEW TABLE AS newrows FOR EACH STATEMENT EXECUTE FUNCTION public.check_allocation_sum_stmt_update();

CREATE TRIGGER trg_compliance_audit_ledger_append_only BEFORE DELETE OR UPDATE ON public.compliance_audit_ledger FOR EACH ROW EXECUTE FUNCTION public.fn_compliance_audit_ledger_append_only();

CREATE TRIGGER trg_events_prevent_mutation BEFORE DELETE OR UPDATE ON public.attribution_events FOR EACH ROW EXECUTE FUNCTION public.fn_events_prevent_mutation();

CREATE TRIGGER trg_guard_attribution_events_payload_identity BEFORE INSERT ON public.attribution_events FOR EACH ROW EXECUTE FUNCTION public.fn_guard_attribution_events_payload_identity();

CREATE TRIGGER trg_ledger_prevent_mutation BEFORE DELETE OR UPDATE ON public.revenue_ledger FOR EACH ROW EXECUTE FUNCTION public.fn_ledger_prevent_mutation();

CREATE TRIGGER trg_llm_call_audit_append_only BEFORE DELETE OR UPDATE ON public.llm_call_audit FOR EACH ROW EXECUTE FUNCTION public.fn_llm_call_audit_append_only();

CREATE TRIGGER trg_pii_guardrail_attribution_events BEFORE INSERT ON public.attribution_events FOR EACH ROW EXECUTE FUNCTION public.fn_enforce_pii_guardrail();

CREATE TRIGGER trg_pii_guardrail_dead_events BEFORE INSERT ON public.dead_events FOR EACH ROW EXECUTE FUNCTION public.fn_enforce_pii_guardrail();

CREATE TRIGGER trg_pii_guardrail_revenue_ledger BEFORE INSERT ON public.revenue_ledger FOR EACH ROW EXECUTE FUNCTION public.fn_enforce_pii_guardrail();

CREATE TRIGGER trg_revenue_ledger_state_audit AFTER UPDATE OF state ON public.revenue_ledger FOR EACH ROW WHEN (((old.state)::text IS DISTINCT FROM (new.state)::text)) EXECUTE FUNCTION public.fn_log_revenue_state_change();

ALTER TABLE ONLY public.attribution_allocations
    ADD CONSTRAINT attribution_allocations_recompute_job_id_fkey FOREIGN KEY (recompute_job_id) REFERENCES public.attribution_recompute_jobs(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.attribution_allocations
    ADD CONSTRAINT attribution_allocations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.attribution_commerce_identities
    ADD CONSTRAINT attribution_commerce_identities_attribution_event_id_fkey FOREIGN KEY (attribution_event_id) REFERENCES public.attribution_events(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.attribution_commerce_identities
    ADD CONSTRAINT attribution_commerce_identities_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.attribution_events
    ADD CONSTRAINT attribution_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.attribution_recompute_jobs
    ADD CONSTRAINT attribution_recompute_jobs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.auth_access_token_denylist
    ADD CONSTRAINT auth_access_token_denylist_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.auth_refresh_tokens
    ADD CONSTRAINT auth_refresh_tokens_replaced_by_id_fkey FOREIGN KEY (replaced_by_id) REFERENCES public.auth_refresh_tokens(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.auth_refresh_tokens
    ADD CONSTRAINT auth_refresh_tokens_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.auth_refresh_tokens
    ADD CONSTRAINT auth_refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.auth_user_token_cutoffs
    ADD CONSTRAINT auth_user_token_cutoffs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.b23_exception_records
    ADD CONSTRAINT b23_exception_records_match_verdict_id_fkey FOREIGN KEY (match_verdict_id) REFERENCES public.b23_match_verdicts(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.b23_exception_records
    ADD CONSTRAINT b23_exception_records_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.b23_match_verdicts
    ADD CONSTRAINT b23_match_verdicts_attribution_event_id_fkey FOREIGN KEY (attribution_event_id) REFERENCES public.attribution_events(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.b23_match_verdicts
    ADD CONSTRAINT b23_match_verdicts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.b23_match_verdicts
    ADD CONSTRAINT b23_match_verdicts_webhook_ingress_identity_id_fkey FOREIGN KEY (webhook_ingress_identity_id) REFERENCES public.webhook_ingress_identities(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.b23_revenue_events
    ADD CONSTRAINT b23_revenue_events_match_verdict_id_fkey FOREIGN KEY (match_verdict_id) REFERENCES public.b23_match_verdicts(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.b23_revenue_events
    ADD CONSTRAINT b23_revenue_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.b23_revenue_events
    ADD CONSTRAINT b23_revenue_events_webhook_ingress_identity_id_fkey FOREIGN KEY (webhook_ingress_identity_id) REFERENCES public.webhook_ingress_identities(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.b23_webhook_ingestion_logs
    ADD CONSTRAINT b23_webhook_ingestion_logs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.budget_jobs
    ADD CONSTRAINT budget_jobs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.budget_optimization_jobs
    ADD CONSTRAINT budget_optimization_jobs_authority_job_id_fkey FOREIGN KEY (authority_job_id) REFERENCES public.budget_jobs(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.budget_optimization_jobs
    ADD CONSTRAINT budget_optimization_jobs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.channel_assignment_corrections
    ADD CONSTRAINT channel_assignment_corrections_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.channel_assignment_corrections
    ADD CONSTRAINT channel_assignment_corrections_to_channel_fkey FOREIGN KEY (to_channel) REFERENCES public.channel_taxonomy(code);

ALTER TABLE ONLY public.channel_state_transitions
    ADD CONSTRAINT channel_state_transitions_channel_code_fkey FOREIGN KEY (channel_code) REFERENCES public.channel_taxonomy(code) ON DELETE CASCADE;

ALTER TABLE ONLY public.compliance_audit_ledger
    ADD CONSTRAINT compliance_audit_ledger_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.dead_events_quarantine
    ADD CONSTRAINT dead_events_quarantine_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.dead_events
    ADD CONSTRAINT dead_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.ephemeral_click_resolution
    ADD CONSTRAINT ephemeral_click_resolution_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.ephemeral_order_resolution
    ADD CONSTRAINT ephemeral_order_resolution_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.explanation_cache
    ADD CONSTRAINT explanation_cache_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.attribution_allocations
    ADD CONSTRAINT fk_allocations_event_id_set_null FOREIGN KEY (event_id) REFERENCES public.attribution_events(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.attribution_allocations
    ADD CONSTRAINT fk_attribution_allocations_channel_code FOREIGN KEY (channel_code) REFERENCES public.channel_taxonomy(code);

ALTER TABLE ONLY public.attribution_events
    ADD CONSTRAINT fk_attribution_events_channel FOREIGN KEY (channel) REFERENCES public.channel_taxonomy(code) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.attribution_events
    ADD CONSTRAINT fk_attribution_events_session_authority FOREIGN KEY (tenant_id, session_id) REFERENCES public.session_authority(tenant_id, session_id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE ONLY public.kombu_message
    ADD CONSTRAINT fk_kombu_message_queue FOREIGN KEY (queue_id) REFERENCES public.kombu_queue(id);

ALTER TABLE ONLY public.tenant_membership_roles
    ADD CONSTRAINT fk_tenant_membership_roles_membership_tenant FOREIGN KEY (membership_id, tenant_id) REFERENCES public.tenant_memberships(id, tenant_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.investigation_jobs
    ADD CONSTRAINT investigation_jobs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.investigation_tool_calls
    ADD CONSTRAINT investigation_tool_calls_investigation_id_fkey FOREIGN KEY (investigation_id) REFERENCES public.investigations(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.investigation_tool_calls
    ADD CONSTRAINT investigation_tool_calls_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT investigations_authority_job_id_fkey FOREIGN KEY (authority_job_id) REFERENCES public.investigation_jobs(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT investigations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.llm_api_calls
    ADD CONSTRAINT llm_api_calls_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.llm_breaker_state
    ADD CONSTRAINT llm_breaker_state_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.llm_budget_reservations
    ADD CONSTRAINT llm_budget_reservations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.llm_call_audit
    ADD CONSTRAINT llm_call_audit_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.llm_hourly_shutoff_state
    ADD CONSTRAINT llm_hourly_shutoff_state_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.llm_monthly_budget_state
    ADD CONSTRAINT llm_monthly_budget_state_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.llm_monthly_costs
    ADD CONSTRAINT llm_monthly_costs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.llm_semantic_cache
    ADD CONSTRAINT llm_semantic_cache_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.llm_validation_failures
    ADD CONSTRAINT llm_validation_failures_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.oauth_handshake_sessions
    ADD CONSTRAINT oauth_handshake_sessions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.oauth_handshake_sessions
    ADD CONSTRAINT oauth_handshake_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.platform_connections
    ADD CONSTRAINT platform_connections_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.platform_credentials
    ADD CONSTRAINT platform_credentials_platform_connection_id_fkey FOREIGN KEY (platform_connection_id) REFERENCES public.platform_connections(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.platform_credentials
    ADD CONSTRAINT platform_credentials_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.r4_crash_barriers
    ADD CONSTRAINT r4_crash_barriers_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.r4_task_attempts
    ADD CONSTRAINT r4_task_attempts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.raw_event_payloads
    ADD CONSTRAINT raw_event_payloads_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.attribution_events(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.raw_event_payloads
    ADD CONSTRAINT raw_event_payloads_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.reconciliation_runs
    ADD CONSTRAINT reconciliation_runs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.revenue_cache_entries
    ADD CONSTRAINT revenue_cache_entries_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.revenue_ledger
    ADD CONSTRAINT revenue_ledger_allocation_id_fkey FOREIGN KEY (allocation_id) REFERENCES public.attribution_allocations(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.revenue_ledger
    ADD CONSTRAINT revenue_ledger_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.revenue_state_transitions
    ADD CONSTRAINT revenue_state_transitions_ledger_id_fkey FOREIGN KEY (ledger_id) REFERENCES public.revenue_ledger(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.revenue_state_transitions
    ADD CONSTRAINT revenue_state_transitions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.session_authority
    ADD CONSTRAINT session_authority_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.tenant_membership_roles
    ADD CONSTRAINT tenant_membership_roles_role_code_fkey FOREIGN KEY (role_code) REFERENCES public.roles(code) ON DELETE RESTRICT;

ALTER TABLE ONLY public.tenant_membership_roles
    ADD CONSTRAINT tenant_membership_roles_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT tenant_memberships_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT tenant_memberships_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.webhook_ingress_identities
    ADD CONSTRAINT webhook_ingress_identities_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.attribution_events(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.webhook_ingress_identities
    ADD CONSTRAINT webhook_ingress_identities_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.worker_side_effects
    ADD CONSTRAINT worker_side_effects_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

ALTER TABLE public.attribution_allocations ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.attribution_commerce_identities ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.attribution_events ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.attribution_recompute_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY attribution_recompute_jobs_tenant_isolation ON public.attribution_recompute_jobs USING (((tenant_id)::text = current_setting('app.current_tenant_id'::text, true))) WITH CHECK (((tenant_id)::text = current_setting('app.current_tenant_id'::text, true)));

ALTER TABLE public.auth_access_token_denylist ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.auth_refresh_tokens ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.auth_user_token_cutoffs ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.b23_exception_records ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.b23_match_verdicts ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.b23_revenue_events ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.b23_webhook_ingestion_logs ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.budget_jobs ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.budget_optimization_jobs ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.channel_assignment_corrections ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.compliance_audit_ledger ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.dead_events ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.dead_events_quarantine ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.ephemeral_click_resolution ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.ephemeral_order_resolution ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.explanation_cache ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.investigation_jobs ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.investigation_tool_calls ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.investigations ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.llm_api_calls ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.llm_breaker_state ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.llm_budget_reservations ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.llm_call_audit ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.llm_hourly_shutoff_state ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.llm_monthly_budget_state ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.llm_monthly_costs ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.llm_semantic_cache ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.llm_validation_failures ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.oauth_handshake_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY ops_quarantine_select ON public.dead_events_quarantine FOR SELECT USING (((tenant_id IS NULL) AND (CURRENT_USER = 'app_ops'::name)));

ALTER TABLE public.platform_connections ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.platform_credentials ENABLE ROW LEVEL SECURITY;

CREATE POLICY quarantine_lane_insert ON public.dead_events_quarantine FOR INSERT TO app_user, app_rw WITH CHECK ((tenant_id IS NULL));

ALTER TABLE public.r4_crash_barriers ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.r4_task_attempts ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.raw_event_payloads ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.reconciliation_runs ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.revenue_cache_entries ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.revenue_ledger ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.revenue_state_transitions ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.session_authority ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON public.attribution_allocations USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.attribution_events USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.auth_access_token_denylist USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.auth_refresh_tokens USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.auth_user_token_cutoffs USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.budget_jobs USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.budget_optimization_jobs USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.channel_assignment_corrections USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.dead_events USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.explanation_cache USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.investigation_jobs TO app_user, app_rw, app_ro USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.investigation_tool_calls USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.investigations USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.llm_api_calls USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));

CREATE POLICY tenant_isolation_policy ON public.llm_breaker_state USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));

CREATE POLICY tenant_isolation_policy ON public.llm_budget_reservations USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));

CREATE POLICY tenant_isolation_policy ON public.llm_call_audit USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));

CREATE POLICY tenant_isolation_policy ON public.llm_hourly_shutoff_state USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));

CREATE POLICY tenant_isolation_policy ON public.llm_monthly_budget_state USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));

CREATE POLICY tenant_isolation_policy ON public.llm_monthly_costs USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));

CREATE POLICY tenant_isolation_policy ON public.llm_semantic_cache USING (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid))) WITH CHECK (((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid) AND (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));

CREATE POLICY tenant_isolation_policy ON public.llm_validation_failures USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.oauth_handshake_sessions USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.platform_connections USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.platform_credentials USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.r4_crash_barriers TO app_user USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.r4_task_attempts TO app_user USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.reconciliation_runs USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.revenue_cache_entries USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.revenue_ledger USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.revenue_state_transitions USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.session_authority USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.tenant_membership_roles USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.tenant_memberships USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy ON public.worker_failed_jobs TO app_user USING (((tenant_id IS NULL) OR ((tenant_id)::text = current_setting('app.current_tenant_id'::text, true))));

CREATE POLICY tenant_isolation_policy ON public.worker_side_effects TO app_user USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy_attribution_commerce_identities ON public.attribution_commerce_identities USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy_b23_exception_records ON public.b23_exception_records USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy_b23_match_verdicts ON public.b23_match_verdicts USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy_b23_revenue_events ON public.b23_revenue_events USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy_b23_webhook_ingestion_logs ON public.b23_webhook_ingestion_logs USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy_compliance_audit_ledger ON public.compliance_audit_ledger USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy_ephemeral_click_resolution ON public.ephemeral_click_resolution USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy_ephemeral_order_resolution ON public.ephemeral_order_resolution USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy_raw_event_payloads ON public.raw_event_payloads USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_isolation_policy_webhook_ingress_identities ON public.webhook_ingress_identities USING ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid));

CREATE POLICY tenant_lane_insert ON public.dead_events_quarantine FOR INSERT TO app_user, app_rw WITH CHECK (((tenant_id IS NOT NULL) AND (tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)));

CREATE POLICY tenant_lane_select ON public.dead_events_quarantine FOR SELECT TO app_user, app_rw, app_ro USING (((tenant_id IS NOT NULL) AND (tenant_id = (current_setting('app.current_tenant_id'::text, true))::uuid)));

ALTER TABLE public.tenant_membership_roles ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.tenant_memberships ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

CREATE POLICY users_provision_insert_policy ON public.users FOR INSERT TO app_user WITH CHECK (((id IS NOT NULL) AND (length(TRIM(BOTH FROM login_identifier_hash)) > 0) AND (auth_provider = ANY (ARRAY['password'::text, 'oauth_google'::text, 'oauth_microsoft'::text, 'oauth_github'::text, 'sso'::text]))));

CREATE POLICY users_self_select_policy ON public.users FOR SELECT USING ((id = (current_setting('app.current_user_id'::text, true))::uuid));

CREATE POLICY users_self_update_policy ON public.users FOR UPDATE USING ((id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.webhook_ingress_identities ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.worker_failed_jobs ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.worker_side_effects ENABLE ROW LEVEL SECURITY;


-- b21_p3_guard_token: aa.recompute_job_id IS NULL
