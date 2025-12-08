--
-- PostgreSQL database dump
--

\restrict ZIznBR7sfkJaJAk4OtVPKg5rT5SYSQode9rx17OXBkLhcF05E3hSnf1hMZuhIzT

-- Dumped from database version 18.0
-- Dumped by pg_dump version 18.0

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: check_allocation_sum(); Type: FUNCTION; Schema: public; Owner: ayewhy
--

CREATE FUNCTION public.check_allocation_sum() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            event_revenue INTEGER;
            allocated_sum INTEGER;
            tolerance_cents INTEGER := 1; -- ┬▒1 cent rounding tolerance
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


ALTER FUNCTION public.check_allocation_sum() OWNER TO ayewhy;

--
-- Name: FUNCTION check_allocation_sum(); Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON FUNCTION public.check_allocation_sum() IS 'Validates that allocations sum to event revenue per (event_id, model_version) with ┬▒1 cent tolerance. Purpose: Enforce sum-equality invariant for deterministic revenue accounting. Raises exception if sum mismatch exceeds tolerance.';


--
-- Name: fn_detect_pii_keys(jsonb); Type: FUNCTION; Schema: public; Owner: ayewhy
--

CREATE FUNCTION public.fn_detect_pii_keys(payload jsonb) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE
    AS $$
        BEGIN
            -- Returns TRUE if any PII key is detected in the JSONB payload
            -- Uses ? operator for fast key existence check (index-friendly)
            -- Blocklist: 13 keys across 6 PII categories
            
            RETURN (
                payload ? 'email' OR
                payload ? 'email_address' OR
                payload ? 'phone' OR
                payload ? 'phone_number' OR
                payload ? 'ssn' OR
                payload ? 'social_security_number' OR
                payload ? 'ip_address' OR
                payload ? 'ip' OR
                payload ? 'first_name' OR
                payload ? 'last_name' OR
                payload ? 'full_name' OR
                payload ? 'address' OR
                payload ? 'street_address'
            );
        END;
        $$;


ALTER FUNCTION public.fn_detect_pii_keys(payload jsonb) OWNER TO ayewhy;

--
-- Name: FUNCTION fn_detect_pii_keys(payload jsonb); Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON FUNCTION public.fn_detect_pii_keys(payload jsonb) IS 'PII detection function (Layer 2 guardrail). Returns TRUE if any PII key is detected in JSONB payload. Scope: Key-based detection only (not value scanning). Performance: IMMUTABLE function using ? operator for fast key checks. Blocklist: email, email_address, phone, phone_number, ssn, social_security_number, ip_address, ip, first_name, last_name, full_name, address, street_address. Reference: ADR-003-PII-Defense-Strategy.md.';


--
-- Name: fn_enforce_pii_guardrail(); Type: FUNCTION; Schema: public; Owner: ayewhy
--

CREATE FUNCTION public.fn_enforce_pii_guardrail() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            detected_key TEXT;
        BEGIN
            -- Enforce PII guardrail on attribution_events and dead_events (raw_payload)
            IF TG_TABLE_NAME IN ('attribution_events', 'dead_events') THEN
                IF fn_detect_pii_keys(NEW.raw_payload) THEN
                    -- Find first PII key for error message
                    SELECT key INTO detected_key
                    FROM jsonb_object_keys(NEW.raw_payload) key
                    WHERE key IN (
                        'email', 'email_address', 
                        'phone', 'phone_number', 
                        'ssn', 'social_security_number', 
                        'ip_address', 'ip', 
                        'first_name', 'last_name', 'full_name', 
                        'address', 'street_address'
                    )
                    LIMIT 1;
                    
                    RAISE EXCEPTION 'PII key detected in %.raw_payload. Ingestion blocked by database policy (Layer 2 guardrail). Key found: %. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from payload before retry.', 
                        TG_TABLE_NAME, 
                        detected_key
                    USING ERRCODE = '23514';  -- check_violation
                END IF;
            END IF;
            
            -- Enforce PII guardrail on revenue_ledger (metadata) - only if NOT NULL
            IF TG_TABLE_NAME = 'revenue_ledger' AND NEW.metadata IS NOT NULL THEN
                IF fn_detect_pii_keys(NEW.metadata) THEN
                    -- Find first PII key for error message
                    SELECT key INTO detected_key
                    FROM jsonb_object_keys(NEW.metadata) key
                    WHERE key IN (
                        'email', 'email_address', 
                        'phone', 'phone_number', 
                        'ssn', 'social_security_number', 
                        'ip_address', 'ip', 
                        'first_name', 'last_name', 'full_name', 
                        'address', 'street_address'
                    )
                    LIMIT 1;
                    
                    RAISE EXCEPTION 'PII key detected in revenue_ledger.metadata. Write blocked by database policy (Layer 2 guardrail). Key found: %. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from metadata before retry.', 
                        detected_key
                    USING ERRCODE = '23514';  -- check_violation
                END IF;
            END IF;
            
            RETURN NEW;
        END;
        $$;


ALTER FUNCTION public.fn_enforce_pii_guardrail() OWNER TO ayewhy;

--
-- Name: FUNCTION fn_enforce_pii_guardrail(); Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON FUNCTION public.fn_enforce_pii_guardrail() IS 'PII enforcement trigger function (Layer 2 guardrail). Raises EXCEPTION if PII key detected in JSONB payload. Scope: attribution_events.raw_payload, dead_events.raw_payload, revenue_ledger.metadata. Behavior: BEFORE INSERT trigger blocks write with detailed error message. Performance: <1ms overhead per INSERT. Limitation: Key-based detection only (not value scanning). Reference: ADR-003-PII-Defense-Strategy.md.';


--
-- Name: fn_events_prevent_mutation(); Type: FUNCTION; Schema: public; Owner: ayewhy
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


ALTER FUNCTION public.fn_events_prevent_mutation() OWNER TO ayewhy;

--
-- Name: FUNCTION fn_events_prevent_mutation(); Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON FUNCTION public.fn_events_prevent_mutation() IS 'Prevents UPDATE/DELETE operations on attribution_events table. Purpose: Defense-in-depth enforcement of events immutability. Allows migration_owner for emergency repairs only. Raises exception for all other roles attempting UPDATE/DELETE.';


--
-- Name: fn_ledger_prevent_mutation(); Type: FUNCTION; Schema: public; Owner: ayewhy
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


ALTER FUNCTION public.fn_ledger_prevent_mutation() OWNER TO ayewhy;

--
-- Name: FUNCTION fn_ledger_prevent_mutation(); Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON FUNCTION public.fn_ledger_prevent_mutation() IS 'Prevents UPDATE/DELETE operations on revenue_ledger table. Purpose: Defense-in-depth enforcement of ledger immutability. Allows migration_owner for emergency repairs only. Raises exception for all other roles attempting UPDATE/DELETE.';


--
-- Name: fn_log_channel_assignment_correction(); Type: FUNCTION; Schema: public; Owner: ayewhy
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


ALTER FUNCTION public.fn_log_channel_assignment_correction() OWNER TO ayewhy;

--
-- Name: FUNCTION fn_log_channel_assignment_correction(); Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON FUNCTION public.fn_log_channel_assignment_correction() IS 'Trigger function to log attribution_allocations channel_code corrections to channel_assignment_corrections table. 
            Purpose: Ensure every post-ingestion assignment correction produces a corresponding audit row. 
            Invariant: No assignment correction without matching correction row. 
            Security: SECURITY DEFINER to bypass RLS during trigger execution (reads tenant_id from allocation, already RLS-protected).';


--
-- Name: fn_log_channel_state_change(); Type: FUNCTION; Schema: public; Owner: ayewhy
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


ALTER FUNCTION public.fn_log_channel_state_change() OWNER TO ayewhy;

--
-- Name: FUNCTION fn_log_channel_state_change(); Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON FUNCTION public.fn_log_channel_state_change() IS 'Trigger function to log channel_taxonomy state transitions to channel_state_transitions table. 
            Purpose: Ensure every state change produces a corresponding audit row. 
            Invariant: No taxonomy state change without matching transition row. 
            Security: SECURITY DEFINER to ensure trigger can insert audit records.';


--
-- Name: fn_log_revenue_state_change(); Type: FUNCTION; Schema: public; Owner: ayewhy
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


ALTER FUNCTION public.fn_log_revenue_state_change() OWNER TO ayewhy;

--
-- Name: FUNCTION fn_log_revenue_state_change(); Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON FUNCTION public.fn_log_revenue_state_change() IS 'Trigger function for atomic audit logging of revenue_ledger state changes. 
            Purpose: Ensure every state change produces a corresponding revenue_state_transitions row. 
            Invariant: No ledger state change without matching transition row. 
            Security: SECURITY DEFINER to bypass RLS on revenue_state_transitions during trigger execution.';


--
-- Name: fn_scan_pii_contamination(); Type: FUNCTION; Schema: public; Owner: ayewhy
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


ALTER FUNCTION public.fn_scan_pii_contamination() OWNER TO ayewhy;

--
-- Name: FUNCTION fn_scan_pii_contamination(); Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON FUNCTION public.fn_scan_pii_contamination() IS 'PII contamination scanning function (Layer 3 operations audit). Returns: Count of PII findings detected. Scope: Scans all three JSONB surfaces (attribution_events.raw_payload, dead_events.raw_payload, revenue_ledger.metadata). Behavior: Inserts findings into pii_audit_findings table for each detected PII key. Performance: Batch operation, intended for periodic scheduled execution (not per-transaction). Security: Does not log actual PII values, only record IDs and key names. Reference: ADR-003-PII-Defense-Strategy.md Section "Layer 3 (Operations)".';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: ayewhy
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO ayewhy;

--
-- Name: attribution_allocations; Type: TABLE; Schema: public; Owner: ayewhy
--

CREATE TABLE public.attribution_allocations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    event_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    channel_code text CONSTRAINT attribution_allocations_channel_not_null NOT NULL,
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
    CONSTRAINT attribution_allocations_allocated_revenue_cents_check CHECK ((allocated_revenue_cents >= 0)),
    CONSTRAINT ck_allocations_confidence_score CHECK (((confidence_score >= (0)::numeric) AND (confidence_score <= (1)::numeric))),
    CONSTRAINT ck_attribution_allocations_allocation_ratio_bounds CHECK (((allocation_ratio >= (0)::numeric) AND (allocation_ratio <= (1)::numeric))),
    CONSTRAINT ck_attribution_allocations_revenue_positive CHECK ((allocated_revenue_cents >= 0))
);

ALTER TABLE ONLY public.attribution_allocations FORCE ROW LEVEL SECURITY;


ALTER TABLE public.attribution_allocations OWNER TO ayewhy;

--
-- Name: TABLE attribution_allocations; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TABLE public.attribution_allocations IS 'Stores attribution model allocations (channel credit assignments). Purpose: Store channel credit for attribution calculations. Data class: Non-PII. Ownership: Attribution service. RLS enabled for tenant isolation. AUDIT TRAIL: Allocations persist even when source events are deleted (event_id becomes NULL).';


--
-- Name: COLUMN attribution_allocations.event_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_allocations.event_id IS 'Foreign key to attribution_events table. Purpose: Link allocation to source event for context. Data class: Non-PII. NULLABLE: event_id = NULL means event was deleted but allocation preserved for audit trail. ON DELETE SET NULL preserves financial records.';


--
-- Name: COLUMN attribution_allocations.channel_code; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_allocations.channel_code IS 'Canonical channel code (FK to channel_taxonomy.code). Purpose: Identify attribution channel using canonical taxonomy. Data class: Non-PII.';


--
-- Name: COLUMN attribution_allocations.correlation_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_allocations.correlation_id IS 'Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing and event stitching across tables. Links attribution_allocations, attribution_events, and dead_events. Data class: Non-PII.';


--
-- Name: COLUMN attribution_allocations.allocation_ratio; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_allocations.allocation_ratio IS 'Allocation ratio (0.0 to 1.0) representing the proportion of event revenue allocated to this channel. Purpose: Enable deterministic revenue accounting and sum-equality validation. Data class: Non-PII.';


--
-- Name: COLUMN attribution_allocations.model_version; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_allocations.model_version IS 'Attribution model version (semantic version string). Purpose: Track which model version generated this allocation, enabling model rollups and sum-equality validation per model version. Data class: Non-PII.';


--
-- Name: COLUMN attribution_allocations.model_type; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_allocations.model_type IS 'Type of attribution model used (e.g., last_touch, linear, bayesian). INVARIANT: analytics_important. Purpose: Identify attribution methodology for model comparison. Data class: Non-PII. Required for: B2.1 attribution model selection and analysis.';


--
-- Name: COLUMN attribution_allocations.confidence_score; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_allocations.confidence_score IS 'Statistical confidence score of the allocation (0.0 to 1.0). INVARIANT: analytics_important. Purpose: Quantify uncertainty in attribution. Data class: Non-PII. Required for: B2.1 Bayesian attribution, confidence-weighted reporting. Must be between 0 and 1.';


--
-- Name: COLUMN attribution_allocations.credible_interval_lower_cents; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_allocations.credible_interval_lower_cents IS 'Lower bound of the credible interval for allocated revenue (Bayesian). INVARIANT: analytics_important. Purpose: Quantify uncertainty bounds for revenue allocation. Data class: Non-PII. Required for: B2.1 Bayesian attribution uncertainty quantification.';


--
-- Name: COLUMN attribution_allocations.credible_interval_upper_cents; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_allocations.credible_interval_upper_cents IS 'Upper bound of the credible interval for allocated revenue (Bayesian). INVARIANT: analytics_important. Purpose: Quantify uncertainty bounds for revenue allocation. Data class: Non-PII. Required for: B2.1 Bayesian attribution uncertainty quantification.';


--
-- Name: COLUMN attribution_allocations.convergence_r_hat; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_allocations.convergence_r_hat IS 'R-hat statistic for MCMC convergence diagnostics (Gelman-Rubin). INVARIANT: analytics_important. Purpose: Validate MCMC chain convergence. Data class: Non-PII. Required for: B2.1 Bayesian model quality assurance. Values near 1.0 indicate convergence.';


--
-- Name: COLUMN attribution_allocations.effective_sample_size; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_allocations.effective_sample_size IS 'Effective sample size for MCMC diagnostics. INVARIANT: analytics_important. Purpose: Assess MCMC sampling efficiency. Data class: Non-PII. Required for: B2.1 Bayesian model quality assurance.';


--
-- Name: COLUMN attribution_allocations.verified; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_allocations.verified IS 'Whether the allocation has been verified against ground truth. INVARIANT: analytics_important. Purpose: Flag allocations that have been reconciled. Data class: Non-PII. Required for: B2.4 revenue verification and reconciliation.';


--
-- Name: COLUMN attribution_allocations.verification_source; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_allocations.verification_source IS 'Source of verification (e.g., manual, reconciliation_run, stripe_webhook). INVARIANT: analytics_important. Purpose: Track verification provenance. Data class: Non-PII. Required for: B2.4 reconciliation audit trail.';


--
-- Name: COLUMN attribution_allocations.verification_timestamp; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_allocations.verification_timestamp IS 'Timestamp when the allocation was verified. INVARIANT: analytics_important. Purpose: Track verification timing. Data class: Non-PII. Required for: B2.4 reconciliation audit trail.';


--
-- Name: CONSTRAINT ck_allocations_confidence_score ON attribution_allocations; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON CONSTRAINT ck_allocations_confidence_score ON public.attribution_allocations IS 'Ensures confidence_score is between 0 and 1. Purpose: Enforce valid probability bounds. Required for: B2.1 statistical attribution.';


--
-- Name: attribution_events; Type: TABLE; Schema: public; Owner: ayewhy
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


ALTER TABLE public.attribution_events OWNER TO ayewhy;

--
-- Name: TABLE attribution_events; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TABLE public.attribution_events IS 'Stores attribution events for revenue tracking. Purpose: Event ingestion and attribution calculations. Data class: Non-PII (PII stripped from raw_payload). Ownership: Attribution service. RLS enabled for tenant isolation. Append-only: No UPDATE/DELETE for app roles; corrections via new events only.';


--
-- Name: COLUMN attribution_events.correlation_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_events.correlation_id IS 'Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing and event stitching across tables. Links attribution_events, dead_events, and future attribution_allocations. Data class: Non-PII.';


--
-- Name: COLUMN attribution_events.idempotency_key; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_events.idempotency_key IS 'Unique key to prevent duplicate event ingestion. INVARIANT: idempotency_critical. Purpose: Ensure exactly-once event processing. Data class: Non-PII. Required for: B0.4 ingestion deduplication. Must be unique across all tenants.';


--
-- Name: COLUMN attribution_events.event_type; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_events.event_type IS 'Categorization of the event (click, impression, purchase, etc.). INVARIANT: idempotency_critical. Purpose: Enable event-type specific processing and analytics. Data class: Non-PII. Required for: B0.4 ingestion routing, B0.5 worker queue.';


--
-- Name: COLUMN attribution_events.channel; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_events.channel IS 'Marketing channel associated with the event (FK to channel_taxonomy.code). INVARIANT: idempotency_critical. Purpose: Enable channel-level attribution and reporting with DB-enforced canonical codes. Data class: Non-PII. Required for: B0.4 ingestion, B2.1 attribution models.';


--
-- Name: COLUMN attribution_events.campaign_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_events.campaign_id IS 'Campaign identifier for attribution tracking. INVARIANT: analytics_important. Purpose: Link events to campaigns for attribution. Data class: Non-PII. Required for: B2.1 attribution models.';


--
-- Name: COLUMN attribution_events.conversion_value_cents; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_events.conversion_value_cents IS 'Monetary value of the conversion event in cents. INVARIANT: financial_critical. Purpose: Track revenue associated with events. Data class: Non-PII. Required for: B2.1 attribution models, revenue allocation.';


--
-- Name: COLUMN attribution_events.currency; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_events.currency IS 'ISO 4217 currency code (e.g., USD, EUR). INVARIANT: financial_critical. Purpose: Support multi-currency revenue tracking. Data class: Non-PII. Required for: B2.3 currency conversion.';


--
-- Name: COLUMN attribution_events.event_timestamp; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_events.event_timestamp IS 'Timestamp when the event occurred. INVARIANT: idempotency_critical. Purpose: Temporal ordering and time-series analysis. Data class: Non-PII. Required for: B0.5 event processing, B2.1 attribution models.';


--
-- Name: COLUMN attribution_events.processed_at; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_events.processed_at IS 'Timestamp when the event was processed. INVARIANT: analytics_important. Purpose: Track processing latency and audit trail. Data class: Non-PII. Required for: B0.5 worker monitoring.';


--
-- Name: COLUMN attribution_events.processing_status; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_events.processing_status IS 'Current processing status (pending, processed, failed). INVARIANT: idempotency_critical. Purpose: Enable worker queue and retry logic. Data class: Non-PII. Required for: B0.5 worker queue, error handling.';


--
-- Name: COLUMN attribution_events.retry_count; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.attribution_events.retry_count IS 'Number of times processing has been retried. INVARIANT: analytics_important. Purpose: Track retry attempts for failed events. Data class: Non-PII. Required for: B0.5 retry logic, dead event handling.';


--
-- Name: channel_assignment_corrections; Type: TABLE; Schema: public; Owner: ayewhy
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


ALTER TABLE public.channel_assignment_corrections OWNER TO ayewhy;

--
-- Name: TABLE channel_assignment_corrections; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TABLE public.channel_assignment_corrections IS 'Audit log of all post-ingestion channel assignment corrections. Purpose: Provide immutable audit trail for revenue reclassifications, enabling reconciliation and dispute resolution. Data class: Non-PII. Ownership: Data Governance.';


--
-- Name: COLUMN channel_assignment_corrections.id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_assignment_corrections.id IS 'Primary key for correction record. Data class: Non-PII.';


--
-- Name: COLUMN channel_assignment_corrections.tenant_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_assignment_corrections.tenant_id IS 'Tenant whose data was corrected (FK to tenants.id). Data class: Non-PII.';


--
-- Name: COLUMN channel_assignment_corrections.entity_type; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_assignment_corrections.entity_type IS 'Type of entity corrected: ''event'' or ''allocation''. Data class: Non-PII.';


--
-- Name: COLUMN channel_assignment_corrections.entity_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_assignment_corrections.entity_id IS 'ID of corrected entity (references attribution_events.id or attribution_allocations.id). Data class: Non-PII.';


--
-- Name: COLUMN channel_assignment_corrections.from_channel; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_assignment_corrections.from_channel IS 'Previous channel assignment. Data class: Non-PII.';


--
-- Name: COLUMN channel_assignment_corrections.to_channel; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_assignment_corrections.to_channel IS 'New channel assignment (FK to channel_taxonomy.code). Data class: Non-PII.';


--
-- Name: COLUMN channel_assignment_corrections.corrected_by; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_assignment_corrections.corrected_by IS 'User/service that made correction (e.g., support@skeldir.com). Data class: Non-PII.';


--
-- Name: COLUMN channel_assignment_corrections.corrected_at; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_assignment_corrections.corrected_at IS 'Timestamp when correction occurred. Data class: Non-PII.';


--
-- Name: COLUMN channel_assignment_corrections.reason; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_assignment_corrections.reason IS 'Mandatory explanation for correction. Data class: Non-PII.';


--
-- Name: COLUMN channel_assignment_corrections.metadata; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_assignment_corrections.metadata IS 'Additional context (e.g., ticket reference). Data class: Non-PII.';


--
-- Name: channel_state_transitions; Type: TABLE; Schema: public; Owner: ayewhy
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


ALTER TABLE public.channel_state_transitions OWNER TO ayewhy;

--
-- Name: TABLE channel_state_transitions; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TABLE public.channel_state_transitions IS 'Audit log of all channel_taxonomy state transitions. Purpose: Provide immutable audit trail for channel lifecycle changes, enabling compliance and PE-readiness. Data class: Non-PII. Ownership: Data Governance.';


--
-- Name: COLUMN channel_state_transitions.id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_state_transitions.id IS 'Primary key for transition record. Data class: Non-PII.';


--
-- Name: COLUMN channel_state_transitions.channel_code; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_state_transitions.channel_code IS 'Channel that transitioned (FK to channel_taxonomy.code). Data class: Non-PII.';


--
-- Name: COLUMN channel_state_transitions.from_state; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_state_transitions.from_state IS 'Previous state (NULL for first assignment). Data class: Non-PII.';


--
-- Name: COLUMN channel_state_transitions.to_state; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_state_transitions.to_state IS 'New state after transition. Data class: Non-PII.';


--
-- Name: COLUMN channel_state_transitions.changed_by; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_state_transitions.changed_by IS 'User/service that triggered transition (e.g., admin@skeldir.com, migration:20251117). Data class: Non-PII.';


--
-- Name: COLUMN channel_state_transitions.changed_at; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_state_transitions.changed_at IS 'Timestamp when transition occurred. Data class: Non-PII.';


--
-- Name: COLUMN channel_state_transitions.reason; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_state_transitions.reason IS 'Human-readable explanation for transition (optional but recommended). Data class: Non-PII.';


--
-- Name: COLUMN channel_state_transitions.metadata; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_state_transitions.metadata IS 'Additional context (e.g., ticket reference, migration ID). Data class: Non-PII.';


--
-- Name: channel_taxonomy; Type: TABLE; Schema: public; Owner: ayewhy
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


ALTER TABLE public.channel_taxonomy OWNER TO ayewhy;

--
-- Name: TABLE channel_taxonomy; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TABLE public.channel_taxonomy IS 'Canonical channel taxonomy for attribution. Guarantees all allocation channel codes are valid. 
            All unmapped channels MUST be normalized to the ''unknown'' code. Purpose: Provide single source 
            of truth for channel codes, ensuring consistency across ingestion, allocation models, and UI. 
            Data class: Non-PII. Ownership: Attribution service.';


--
-- Name: COLUMN channel_taxonomy.code; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_taxonomy.code IS 'Canonical channel identifier used throughout system. Primary key. Must match values referenced by attribution_allocations.channel_code FK. Data class: Non-PII.';


--
-- Name: COLUMN channel_taxonomy.family; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_taxonomy.family IS 'Normalized family grouping for higher-level reporting (e.g., "paid_social", "paid_search", "organic", "referral"). Purpose: Enable family-level aggregation and analysis. Data class: Non-PII.';


--
-- Name: COLUMN channel_taxonomy.is_paid; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_taxonomy.is_paid IS 'Indicates whether spend is expected for this channel. Purpose: Enable paid vs organic channel segmentation. Data class: Non-PII.';


--
-- Name: COLUMN channel_taxonomy.display_name; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_taxonomy.display_name IS 'Human-friendly label for UI display. Purpose: Provide user-facing channel name. Data class: Non-PII.';


--
-- Name: COLUMN channel_taxonomy.is_active; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_taxonomy.is_active IS 'Used to soft-deprecate channels without breaking existing rows. Purpose: Allow channel retirement while preserving historical data. Data class: Non-PII.';


--
-- Name: COLUMN channel_taxonomy.created_at; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_taxonomy.created_at IS 'Timestamp when channel was added to taxonomy. Purpose: Audit trail for channel lifecycle. Data class: Non-PII.';


--
-- Name: COLUMN channel_taxonomy.state; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.channel_taxonomy.state IS 'Channel lifecycle state: draft (testing), active (production), deprecated (soft retirement), archived (hard retirement). Purpose: Enable state machine governance and auditability. Data class: Non-PII.';


--
-- Name: dead_events; Type: TABLE; Schema: public; Owner: ayewhy
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
    CONSTRAINT ck_dead_events_remediation_status_valid CHECK (((remediation_status)::text = ANY ((ARRAY['pending'::character varying, 'in_progress'::character varying, 'resolved'::character varying, 'abandoned'::character varying])::text[]))),
    CONSTRAINT ck_dead_events_retry_count_positive CHECK ((retry_count >= 0))
);

ALTER TABLE ONLY public.dead_events FORCE ROW LEVEL SECURITY;


ALTER TABLE public.dead_events OWNER TO ayewhy;

--
-- Name: TABLE dead_events; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TABLE public.dead_events IS 'Dead-letter queue for invalid/unparseable webhook payloads. Purpose: Store failed ingestion attempts for operator triage. Data class: Non-PII (PII stripped from raw_payload). Ownership: Ingestion service. RLS enabled for tenant isolation.';


--
-- Name: COLUMN dead_events.correlation_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.dead_events.correlation_id IS 'Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing and event stitching across tables. Links dead_events, attribution_events, and future attribution_allocations. Data class: Non-PII.';


--
-- Name: COLUMN dead_events.event_type; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.dead_events.event_type IS 'Type of event that failed processing. INVARIANT: processing_critical. Purpose: Enable event-type specific remediation workflows. Data class: Non-PII. Required for: B0.5 error handling, remediation routing.';


--
-- Name: COLUMN dead_events.error_type; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.dead_events.error_type IS 'Categorization of the error (e.g., validation_error, network_error, data_corruption). INVARIANT: processing_critical. Purpose: Enable error-type specific remediation and alerting. Data class: Non-PII. Required for: B0.5 error classification, alert routing.';


--
-- Name: COLUMN dead_events.error_message; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.dead_events.error_message IS 'Detailed error message describing what went wrong. INVARIANT: processing_critical. Purpose: Provide diagnostic information for remediation. Data class: Non-PII (may contain limited technical data). Required for: B0.5 error debugging, remediation.';


--
-- Name: COLUMN dead_events.error_traceback; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.dead_events.error_traceback IS 'Stack trace of the error for debugging. INVARIANT: processing_critical. Purpose: Provide detailed technical context for engineering investigation. Data class: Non-PII. Required for: B0.5 error debugging.';


--
-- Name: COLUMN dead_events.retry_count; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.dead_events.retry_count IS 'Number of times processing has been retried. INVARIANT: processing_critical. Purpose: Track retry attempts to prevent infinite loops. Data class: Non-PII. Required for: B0.5 retry logic, dead event detection.';


--
-- Name: COLUMN dead_events.last_retry_at; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.dead_events.last_retry_at IS 'Timestamp of the last retry attempt. INVARIANT: processing_critical. Purpose: Track retry timing for backoff logic and monitoring. Data class: Non-PII. Required for: B0.5 exponential backoff, retry monitoring.';


--
-- Name: COLUMN dead_events.remediation_status; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.dead_events.remediation_status IS 'Status of the remediation effort (pending, in_progress, resolved, ignored). INVARIANT: processing_critical. Purpose: Track remediation workflow state. Data class: Non-PII. Required for: B0.5 remediation queue, SLA tracking.';


--
-- Name: COLUMN dead_events.remediation_notes; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.dead_events.remediation_notes IS 'Notes on remediation actions taken by engineers. INVARIANT: processing_critical. Purpose: Document remediation history for knowledge base. Data class: Non-PII. Required for: B0.5 remediation documentation, postmortem analysis.';


--
-- Name: COLUMN dead_events.resolved_at; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.dead_events.resolved_at IS 'Timestamp when the dead event was successfully resolved. INVARIANT: processing_critical. Purpose: Track resolution timing for SLA and metrics. Data class: Non-PII. Required for: B0.5 remediation SLA tracking, metrics.';


--
-- Name: CONSTRAINT ck_dead_events_retry_count_positive ON dead_events; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON CONSTRAINT ck_dead_events_retry_count_positive ON public.dead_events IS 'Ensures retry_count is non-negative. Purpose: Prevent invalid retry counts. Required for: B0.5 retry logic.';


--
-- Name: mv_allocation_summary; Type: MATERIALIZED VIEW; Schema: public; Owner: ayewhy
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


ALTER MATERIALIZED VIEW public.mv_allocation_summary OWNER TO ayewhy;

--
-- Name: MATERIALIZED VIEW mv_allocation_summary; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON MATERIALIZED VIEW public.mv_allocation_summary IS 'Aggregates allocation sums per (tenant_id, event_id, model_version) for sum-equality validation. Purpose: Enable reporting and validation of revenue accounting correctness. NULL HANDLING: event_id may be NULL (event deleted); validation fields (is_balanced, drift_cents) are NULL when event unavailable. LEFT JOIN ensures all allocations included in financial totals. Refresh policy: CONCURRENTLY with TTL-based refresh (30-60s).';


--
-- Name: mv_channel_performance; Type: MATERIALIZED VIEW; Schema: public; Owner: ayewhy
--

CREATE MATERIALIZED VIEW public.mv_channel_performance AS
 SELECT tenant_id,
    channel_code,
    date_trunc('day'::text, created_at) AS allocation_date,
    count(DISTINCT event_id) AS total_conversions,
    sum(allocated_revenue_cents) AS total_revenue_cents,
    avg(confidence_score) AS avg_confidence_score,
    count(*) AS total_allocations
   FROM public.attribution_allocations
  WHERE (created_at >= (CURRENT_DATE - '90 days'::interval))
  GROUP BY tenant_id, channel_code, (date_trunc('day'::text, created_at))
  WITH NO DATA;


ALTER MATERIALIZED VIEW public.mv_channel_performance OWNER TO ayewhy;

--
-- Name: MATERIALIZED VIEW mv_channel_performance; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON MATERIALIZED VIEW public.mv_channel_performance IS 'Pre-aggregates channel performance by day for fast dashboard queries. Supports B2.6 API. Refresh CONCURRENTLY. 90-day rolling window. Purpose: Enable sub-500ms p95 channel performance queries without full table scans on attribution_allocations. Columns: tenant_id, channel_code, allocation_date (day), total_conversions (distinct events), total_revenue_cents (sum), avg_confidence_score, total_allocations (count). Refresh policy: REFRESH MATERIALIZED VIEW CONCURRENTLY mv_channel_performance on schedule (recommended: hourly or on-demand). Index: UNIQUE on (tenant_id, channel_code, allocation_date) enables REFRESH CONCURRENTLY.';


--
-- Name: revenue_ledger; Type: TABLE; Schema: public; Owner: ayewhy
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
    allocation_id uuid NOT NULL,
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
    CONSTRAINT ck_revenue_ledger_revenue_positive CHECK ((revenue_cents >= 0)),
    CONSTRAINT ck_revenue_ledger_state_valid CHECK (((state)::text = ANY ((ARRAY['authorized'::character varying, 'captured'::character varying, 'refunded'::character varying, 'chargeback'::character varying])::text[]))),
    CONSTRAINT revenue_ledger_revenue_cents_check CHECK ((revenue_cents >= 0))
);

ALTER TABLE ONLY public.revenue_ledger FORCE ROW LEVEL SECURITY;


ALTER TABLE public.revenue_ledger OWNER TO ayewhy;

--
-- Name: TABLE revenue_ledger; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TABLE public.revenue_ledger IS 'Write-once financial ledger. Application roles may only INSERT. No UPDATE/DELETE for app roles; corrections via new ledger entries. Purpose: Revenue verification and aggregation. Data class: Non-PII. Ownership: Reconciliation service. RLS enabled for tenant isolation.';


--
-- Name: COLUMN revenue_ledger.allocation_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_ledger.allocation_id IS 'Foreign key to attribution_allocations table (NOT NULL). Purpose: Link ledger entry to specific allocation for allocation-based posting. Ensures all ledger entries are traceable. Data class: Non-PII.';


--
-- Name: COLUMN revenue_ledger.posted_at; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_ledger.posted_at IS 'Timestamp when revenue was posted to the ledger. Purpose: Track posting time for audit trail and reconciliation. Data class: Non-PII.';


--
-- Name: COLUMN revenue_ledger.transaction_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_ledger.transaction_id IS 'Unique identifier for the financial transaction from payment processor (e.g., Stripe payment intent ID). INVARIANT: financial_critical. Purpose: Enable webhook idempotency and transaction deduplication. Data class: Non-PII. Required for: B2.2 webhook processing, transaction tracking. Must be unique.';


--
-- Name: COLUMN revenue_ledger.order_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_ledger.order_id IS 'Order identifier associated with the transaction. INVARIANT: financial_critical. Purpose: Link revenue to orders for reconciliation. Data class: Non-PII. Required for: B2.4 order-level revenue tracking.';


--
-- Name: COLUMN revenue_ledger.state; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_ledger.state IS 'Current state of the revenue transaction (authorized, captured, refunded, chargeback). INVARIANT: financial_critical. Purpose: Track revenue lifecycle and support refund processing. Data class: Non-PII. Required for: B2.4 refund tracking, state machine enforcement. Must be valid enum value.';


--
-- Name: COLUMN revenue_ledger.previous_state; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_ledger.previous_state IS 'Previous state of the revenue transaction for audit trail. INVARIANT: financial_critical. Purpose: Enable state transition tracking and audit. Data class: Non-PII. Required for: B2.4 revenue state audit trail.';


--
-- Name: COLUMN revenue_ledger.amount_cents; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_ledger.amount_cents IS 'Transaction amount in cents in its original currency. INVARIANT: financial_critical. Purpose: Store exact transaction amount without loss of precision. Data class: Non-PII. Required for: B2.2 revenue tracking, B2.3 currency conversion. Must not be NULL.';


--
-- Name: COLUMN revenue_ledger.currency; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_ledger.currency IS 'ISO 4217 currency code of the transaction (e.g., USD, EUR, GBP). INVARIANT: financial_critical. Purpose: Support multi-currency revenue tracking and conversion. Data class: Non-PII. Required for: B2.3 currency conversion, international revenue reporting. Must not be NULL.';


--
-- Name: COLUMN revenue_ledger.verification_source; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_ledger.verification_source IS 'Source that verified this ledger entry (e.g., Stripe, manual, reconciliation_run). INVARIANT: financial_critical. Purpose: Track verification provenance for audit. Data class: Non-PII. Required for: B2.4 reconciliation audit trail. Must not be NULL.';


--
-- Name: COLUMN revenue_ledger.verification_timestamp; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_ledger.verification_timestamp IS 'Timestamp when the ledger entry was verified. INVARIANT: financial_critical. Purpose: Track verification timing for audit and SLA monitoring. Data class: Non-PII. Required for: B2.4 reconciliation audit trail, verification latency tracking. Must not be NULL.';


--
-- Name: COLUMN revenue_ledger.metadata; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_ledger.metadata IS 'Additional metadata for the ledger entry (e.g., FX rates, processor details, refund reason). INVARIANT: analytics_important. Purpose: Store supplementary transaction data. Data class: Non-PII (may contain processor IDs). Required for: B2.3 FX rate tracking, B2.4 refund analysis.';


--
-- Name: CONSTRAINT ck_revenue_ledger_state_valid ON revenue_ledger; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON CONSTRAINT ck_revenue_ledger_state_valid ON public.revenue_ledger IS 'Ensures state is a valid enum value. Purpose: Enforce state machine integrity. Required for: B2.4 refund tracking state machine.';


--
-- Name: mv_daily_revenue_summary; Type: MATERIALIZED VIEW; Schema: public; Owner: ayewhy
--

CREATE MATERIALIZED VIEW public.mv_daily_revenue_summary AS
 SELECT tenant_id,
    date_trunc('day'::text, verification_timestamp) AS revenue_date,
    state,
    currency,
    sum(amount_cents) AS total_amount_cents,
    count(*) AS transaction_count
   FROM public.revenue_ledger
  WHERE ((state)::text = ANY ((ARRAY['captured'::character varying, 'refunded'::character varying, 'chargeback'::character varying])::text[]))
  GROUP BY tenant_id, (date_trunc('day'::text, verification_timestamp)), state, currency
  WITH NO DATA;


ALTER MATERIALIZED VIEW public.mv_daily_revenue_summary OWNER TO ayewhy;

--
-- Name: MATERIALIZED VIEW mv_daily_revenue_summary; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON MATERIALIZED VIEW public.mv_daily_revenue_summary IS 'Pre-aggregates daily revenue, refunds, and chargebacks by currency. Supports B2.6 API. Refresh CONCURRENTLY. Purpose: Enable sub-500ms p95 daily revenue queries for KPI dashboards without full table scans on revenue_ledger. Columns: tenant_id, revenue_date (day), state (captured/refunded/chargeback), currency (ISO 4217), total_amount_cents (sum), transaction_count (count). Refresh policy: REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_revenue_summary on schedule (recommended: hourly or on-demand). Index: UNIQUE on (tenant_id, revenue_date, state, currency) enables REFRESH CONCURRENTLY and fast multi-currency queries.';


--
-- Name: pii_audit_findings; Type: TABLE; Schema: public; Owner: ayewhy
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


ALTER TABLE public.pii_audit_findings OWNER TO ayewhy;

--
-- Name: TABLE pii_audit_findings; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TABLE public.pii_audit_findings IS 'PII audit findings repository (Layer 3 operations audit). Purpose: Store PII contamination detections from periodic scans. Data class: Non-PII (contains record IDs and key names only, not actual PII values). Ownership: Operations/Security team. Use: Detect Layer 1/Layer 2 failures, compliance auditing, incident response. Schedule: Daily (non-prod), Hourly/Daily (prod). Reference: ADR-003-PII-Defense-Strategy.md Section "Layer 3 (Operations)".';


--
-- Name: COLUMN pii_audit_findings.table_name; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.pii_audit_findings.table_name IS 'Source table where PII was detected (attribution_events, dead_events, or revenue_ledger). Purpose: Identify contamination source for remediation.';


--
-- Name: COLUMN pii_audit_findings.column_name; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.pii_audit_findings.column_name IS 'Source column where PII was detected (raw_payload or metadata). Purpose: Identify contamination location.';


--
-- Name: COLUMN pii_audit_findings.record_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.pii_audit_findings.record_id IS 'UUID of the contaminated record. Purpose: Enable record-level remediation and investigation.';


--
-- Name: COLUMN pii_audit_findings.detected_key; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.pii_audit_findings.detected_key IS 'PII key that was detected (e.g., email, phone, ssn). Purpose: Identify PII category for compliance reporting.';


--
-- Name: COLUMN pii_audit_findings.sample_snippet; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.pii_audit_findings.sample_snippet IS 'Optional snippet of contaminated payload (redacted). Purpose: Aid investigation without exposing full PII. May be NULL.';


--
-- Name: COLUMN pii_audit_findings.detected_at; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.pii_audit_findings.detected_at IS 'Timestamp when PII was detected by audit scan. Purpose: Track detection timing for SLA and incident response.';


--
-- Name: pii_audit_findings_id_seq; Type: SEQUENCE; Schema: public; Owner: ayewhy
--

CREATE SEQUENCE public.pii_audit_findings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.pii_audit_findings_id_seq OWNER TO ayewhy;

--
-- Name: pii_audit_findings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ayewhy
--

ALTER SEQUENCE public.pii_audit_findings_id_seq OWNED BY public.pii_audit_findings.id;


--
-- Name: reconciliation_runs; Type: TABLE; Schema: public; Owner: ayewhy
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


ALTER TABLE public.reconciliation_runs OWNER TO ayewhy;

--
-- Name: TABLE reconciliation_runs; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TABLE public.reconciliation_runs IS 'Stores reconciliation pipeline run status and metadata. Purpose: Track reconciliation pipeline execution. Data class: Non-PII. Ownership: Reconciliation service. RLS enabled for tenant isolation.';


--
-- Name: revenue_state_transitions; Type: TABLE; Schema: public; Owner: ayewhy
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


ALTER TABLE public.revenue_state_transitions OWNER TO ayewhy;

--
-- Name: TABLE revenue_state_transitions; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TABLE public.revenue_state_transitions IS 'Audit log for revenue ledger state changes. INVARIANT: financial_critical. Purpose: Track complete history of revenue state transitions for compliance and analytics. Data class: Non-PII. Ownership: Revenue service. Required for: B2.4 refund tracking, financial audit, compliance.';


--
-- Name: COLUMN revenue_state_transitions.id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_state_transitions.id IS 'Primary key UUID for the state transition record. Purpose: Unique identifier for each transition. Data class: Non-PII.';


--
-- Name: COLUMN revenue_state_transitions.ledger_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_state_transitions.ledger_id IS 'Foreign key to revenue_ledger table. INVARIANT: financial_critical. Purpose: Link transition to specific ledger entry. Data class: Non-PII. Required for: B2.4 state transition audit trail. ON DELETE CASCADE ensures transitions are deleted with ledger entry.';


--
-- Name: COLUMN revenue_state_transitions.from_state; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_state_transitions.from_state IS 'State before the transition (nullable for initial state). INVARIANT: financial_critical. Purpose: Track previous state for audit trail. Data class: Non-PII. Required for: B2.4 state transition analysis, compliance audit.';


--
-- Name: COLUMN revenue_state_transitions.to_state; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_state_transitions.to_state IS 'State after the transition (NOT NULL). INVARIANT: financial_critical. Purpose: Track new state for audit trail. Data class: Non-PII. Required for: B2.4 state machine enforcement, refund tracking. Must not be NULL.';


--
-- Name: COLUMN revenue_state_transitions.reason; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_state_transitions.reason IS 'Optional reason for the state transition (e.g., customer_request, fraud_detected, chargeback_received). INVARIANT: financial_critical. Purpose: Document business reason for transition. Data class: Non-PII. Required for: B2.4 refund reason tracking, compliance documentation.';


--
-- Name: COLUMN revenue_state_transitions.transitioned_at; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.revenue_state_transitions.transitioned_at IS 'Timestamp when the state transition occurred (NOT NULL DEFAULT now()). INVARIANT: financial_critical. Purpose: Track exact timing of state changes for audit. Data class: Non-PII. Required for: B2.4 state transition timeline, compliance audit. Must not be NULL.';


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: ayewhy
--

CREATE TABLE public.tenants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    api_key_hash character varying(255) NOT NULL,
    notification_email character varying(255) NOT NULL,
    CONSTRAINT ck_tenants_name_not_empty CHECK ((length(TRIM(BOTH FROM name)) > 0))
);


ALTER TABLE public.tenants OWNER TO ayewhy;

--
-- Name: TABLE tenants; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TABLE public.tenants IS 'Stores tenant information for multi-tenant isolation. Purpose: Tenant identity and management. Data class: Non-PII. Ownership: Backend service. RLS enabled for tenant isolation.';


--
-- Name: COLUMN tenants.id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.tenants.id IS 'Primary key UUID. Purpose: Unique tenant identifier. Data class: Non-PII.';


--
-- Name: COLUMN tenants.name; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.tenants.name IS 'Tenant name. Purpose: Human-readable tenant identification. Data class: Non-PII.';


--
-- Name: COLUMN tenants.created_at; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.tenants.created_at IS 'Record creation timestamp. Purpose: Audit trail. Data class: Non-PII.';


--
-- Name: COLUMN tenants.updated_at; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.tenants.updated_at IS 'Record update timestamp. Purpose: Audit trail. Data class: Non-PII.';


--
-- Name: COLUMN tenants.api_key_hash; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.tenants.api_key_hash IS 'Hashed API key for tenant authentication. INVARIANT: auth_critical. Purpose: Authenticate API requests and link to tenant. Data class: Security credential (hashed). Required for: B0.4 ingestion, B1.2 auth service. Must be unique.';


--
-- Name: COLUMN tenants.notification_email; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON COLUMN public.tenants.notification_email IS 'Email address for tenant-specific notifications. INVARIANT: auth_critical. Purpose: Send reconciliation alerts, system notifications. Data class: PII (email address). Required for: B0.4 notifications, B2.x alerting. Must not be empty.';


--
-- Name: pii_audit_findings id; Type: DEFAULT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.pii_audit_findings ALTER COLUMN id SET DEFAULT nextval('public.pii_audit_findings_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: attribution_allocations attribution_allocations_pkey; Type: CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.attribution_allocations
    ADD CONSTRAINT attribution_allocations_pkey PRIMARY KEY (id);


--
-- Name: attribution_events attribution_events_pkey; Type: CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.attribution_events
    ADD CONSTRAINT attribution_events_pkey PRIMARY KEY (id);


--
-- Name: channel_assignment_corrections channel_assignment_corrections_pkey; Type: CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.channel_assignment_corrections
    ADD CONSTRAINT channel_assignment_corrections_pkey PRIMARY KEY (id);


--
-- Name: channel_state_transitions channel_state_transitions_pkey; Type: CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.channel_state_transitions
    ADD CONSTRAINT channel_state_transitions_pkey PRIMARY KEY (id);


--
-- Name: channel_taxonomy channel_taxonomy_pkey; Type: CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.channel_taxonomy
    ADD CONSTRAINT channel_taxonomy_pkey PRIMARY KEY (code);


--
-- Name: dead_events dead_events_pkey; Type: CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.dead_events
    ADD CONSTRAINT dead_events_pkey PRIMARY KEY (id);


--
-- Name: pii_audit_findings pii_audit_findings_pkey; Type: CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.pii_audit_findings
    ADD CONSTRAINT pii_audit_findings_pkey PRIMARY KEY (id);


--
-- Name: reconciliation_runs reconciliation_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.reconciliation_runs
    ADD CONSTRAINT reconciliation_runs_pkey PRIMARY KEY (id);


--
-- Name: revenue_ledger revenue_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.revenue_ledger
    ADD CONSTRAINT revenue_ledger_pkey PRIMARY KEY (id);


--
-- Name: revenue_state_transitions revenue_state_transitions_pkey; Type: CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.revenue_state_transitions
    ADD CONSTRAINT revenue_state_transitions_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: idx_allocations_channel_performance; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_allocations_channel_performance ON public.attribution_allocations USING btree (tenant_id, channel_code, created_at DESC) INCLUDE (allocated_revenue_cents, confidence_score);


--
-- Name: idx_attribution_allocations_channel; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_attribution_allocations_channel ON public.attribution_allocations USING btree (channel_code);


--
-- Name: idx_attribution_allocations_event_id; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_attribution_allocations_event_id ON public.attribution_allocations USING btree (event_id);


--
-- Name: idx_attribution_allocations_tenant_created_at; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_attribution_allocations_tenant_created_at ON public.attribution_allocations USING btree (tenant_id, created_at DESC);


--
-- Name: idx_attribution_allocations_tenant_event_model_channel; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE UNIQUE INDEX idx_attribution_allocations_tenant_event_model_channel ON public.attribution_allocations USING btree (tenant_id, event_id, model_version, channel_code) WHERE (model_version IS NOT NULL);


--
-- Name: INDEX idx_attribution_allocations_tenant_event_model_channel; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_attribution_allocations_tenant_event_model_channel IS 'Unique index ensuring idempotency per (tenant_id, event_id, model_version, channel). Purpose: Prevent duplicate allocations for the same event/model/channel combination. Supports sum-equality validation.';


--
-- Name: idx_attribution_allocations_tenant_model_version; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_attribution_allocations_tenant_model_version ON public.attribution_allocations USING btree (tenant_id, model_version);


--
-- Name: INDEX idx_attribution_allocations_tenant_model_version; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_attribution_allocations_tenant_model_version IS 'Composite index on (tenant_id, model_version). Purpose: Enable fast model rollups and sum-equality validation queries per model version.';


--
-- Name: idx_attribution_events_session_id; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_attribution_events_session_id ON public.attribution_events USING btree (session_id) WHERE (session_id IS NOT NULL);


--
-- Name: idx_attribution_events_tenant_occurred_at; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_attribution_events_tenant_occurred_at ON public.attribution_events USING btree (tenant_id, occurred_at DESC);


--
-- Name: idx_channel_assignment_corrections_channels; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_channel_assignment_corrections_channels ON public.channel_assignment_corrections USING btree (from_channel, to_channel, corrected_at DESC);


--
-- Name: idx_channel_assignment_corrections_entity; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_channel_assignment_corrections_entity ON public.channel_assignment_corrections USING btree (tenant_id, entity_type, entity_id, corrected_at DESC);


--
-- Name: idx_channel_assignment_corrections_tenant; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_channel_assignment_corrections_tenant ON public.channel_assignment_corrections USING btree (tenant_id, corrected_at DESC);


--
-- Name: idx_channel_state_transitions_channel_changed_at; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_channel_state_transitions_channel_changed_at ON public.channel_state_transitions USING btree (channel_code, changed_at DESC);


--
-- Name: idx_channel_state_transitions_to_state_changed_at; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_channel_state_transitions_to_state_changed_at ON public.channel_state_transitions USING btree (to_state, changed_at DESC);


--
-- Name: idx_dead_events_error_code; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_dead_events_error_code ON public.dead_events USING btree (error_code);


--
-- Name: idx_dead_events_remediation; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_dead_events_remediation ON public.dead_events USING btree (remediation_status, ingested_at DESC);


--
-- Name: INDEX idx_dead_events_remediation; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_dead_events_remediation IS 'Optimizes remediation queue queries. Purpose: Enable fast lookup of events by remediation status. Required for: B0.5 remediation dashboard.';


--
-- Name: idx_dead_events_source; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_dead_events_source ON public.dead_events USING btree (source);


--
-- Name: idx_dead_events_tenant_ingested_at; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_dead_events_tenant_ingested_at ON public.dead_events USING btree (tenant_id, ingested_at DESC);


--
-- Name: idx_events_idempotency; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE UNIQUE INDEX idx_events_idempotency ON public.attribution_events USING btree (idempotency_key);


--
-- Name: INDEX idx_events_idempotency; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_events_idempotency IS 'Ensures idempotency_key uniqueness for deduplication. Purpose: Prevent duplicate event ingestion. Required for: B0.4 ingestion.';


--
-- Name: idx_events_processing_status; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_events_processing_status ON public.attribution_events USING btree (processing_status, processed_at) WHERE ((processing_status)::text = 'pending'::text);


--
-- Name: INDEX idx_events_processing_status; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_events_processing_status IS 'Partial index for pending event queue. Purpose: Enable fast worker queue queries. Required for: B0.5 worker queue.';


--
-- Name: idx_events_tenant_timestamp; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_events_tenant_timestamp ON public.attribution_events USING btree (tenant_id, event_timestamp DESC);


--
-- Name: INDEX idx_events_tenant_timestamp; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_events_tenant_timestamp IS 'Optimizes tenant-scoped time-series queries. Purpose: Enable fast event retrieval by tenant and time. Required for: B2.1 attribution models.';


--
-- Name: idx_mv_allocation_summary_key; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE UNIQUE INDEX idx_mv_allocation_summary_key ON public.mv_allocation_summary USING btree (tenant_id, event_id, model_version);


--
-- Name: INDEX idx_mv_allocation_summary_key; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_mv_allocation_summary_key IS 'Unique index on (tenant_id, event_id, model_version) for REFRESH CONCURRENTLY support. NULL event_id values are treated as distinct (multiple NULLs allowed).';


--
-- Name: idx_mv_channel_performance_unique; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE UNIQUE INDEX idx_mv_channel_performance_unique ON public.mv_channel_performance USING btree (tenant_id, channel_code, allocation_date);


--
-- Name: idx_mv_daily_revenue_summary_unique; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE UNIQUE INDEX idx_mv_daily_revenue_summary_unique ON public.mv_daily_revenue_summary USING btree (tenant_id, revenue_date, state, currency);


--
-- Name: idx_pii_audit_findings_detected_key; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_pii_audit_findings_detected_key ON public.pii_audit_findings USING btree (detected_key);


--
-- Name: INDEX idx_pii_audit_findings_detected_key; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_pii_audit_findings_detected_key IS 'Performance index for PII category reporting. Purpose: Fast aggregation queries like "count findings by PII type". Query pattern: WHERE detected_key = X OR GROUP BY detected_key.';


--
-- Name: idx_pii_audit_findings_table_detected_at; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_pii_audit_findings_table_detected_at ON public.pii_audit_findings USING btree (table_name, detected_at DESC);


--
-- Name: INDEX idx_pii_audit_findings_table_detected_at; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_pii_audit_findings_table_detected_at IS 'Performance index for table-scoped queries with time ordering. Purpose: Fast queries like "show recent findings for attribution_events". Query pattern: WHERE table_name = X ORDER BY detected_at DESC.';


--
-- Name: idx_reconciliation_runs_state; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_reconciliation_runs_state ON public.reconciliation_runs USING btree (state);


--
-- Name: idx_reconciliation_runs_tenant_last_run_at; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_reconciliation_runs_tenant_last_run_at ON public.reconciliation_runs USING btree (tenant_id, last_run_at DESC);


--
-- Name: idx_revenue_ledger_is_verified; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_revenue_ledger_is_verified ON public.revenue_ledger USING btree (is_verified) WHERE (is_verified = true);


--
-- Name: idx_revenue_ledger_state; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_revenue_ledger_state ON public.revenue_ledger USING btree (state);


--
-- Name: INDEX idx_revenue_ledger_state; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_revenue_ledger_state IS 'Optimizes queries by state for refund processing. Purpose: Enable fast lookups of transactions by state. Required for: B2.4 refund processing queries.';


--
-- Name: idx_revenue_ledger_tenant_allocation_id; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE UNIQUE INDEX idx_revenue_ledger_tenant_allocation_id ON public.revenue_ledger USING btree (tenant_id, allocation_id) WHERE (allocation_id IS NOT NULL);


--
-- Name: INDEX idx_revenue_ledger_tenant_allocation_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_revenue_ledger_tenant_allocation_id IS 'Unique index on (tenant_id, allocation_id) where allocation_id IS NOT NULL. Purpose: Prevent duplicate ledger entries for the same allocation, ensuring idempotent allocation-based posting. Data class: Non-PII.';


--
-- Name: idx_revenue_ledger_tenant_state; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_revenue_ledger_tenant_state ON public.revenue_ledger USING btree (tenant_id, state, created_at DESC);


--
-- Name: INDEX idx_revenue_ledger_tenant_state; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_revenue_ledger_tenant_state IS 'Optimizes tenant-scoped state queries with temporal ordering. Purpose: Enable fast tenant revenue reporting by state. Required for: B2.4 tenant dashboards.';


--
-- Name: idx_revenue_ledger_tenant_updated_at; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_revenue_ledger_tenant_updated_at ON public.revenue_ledger USING btree (tenant_id, updated_at DESC);


--
-- Name: idx_revenue_ledger_transaction_id; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE UNIQUE INDEX idx_revenue_ledger_transaction_id ON public.revenue_ledger USING btree (transaction_id);


--
-- Name: INDEX idx_revenue_ledger_transaction_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_revenue_ledger_transaction_id IS 'Ensures transaction_id uniqueness for webhook idempotency. Purpose: Prevent duplicate ledger entries for the same transaction. Required for: B2.2 webhook deduplication.';


--
-- Name: idx_revenue_state_transitions_ledger_id; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_revenue_state_transitions_ledger_id ON public.revenue_state_transitions USING btree (ledger_id, transitioned_at DESC);


--
-- Name: INDEX idx_revenue_state_transitions_ledger_id; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_revenue_state_transitions_ledger_id IS 'Optimizes lookups of state transitions by ledger entry with temporal ordering. Purpose: Enable fast retrieval of state history for a ledger entry. Required for: B2.4 state history queries, refund audit trail.';


--
-- Name: idx_revenue_state_transitions_tenant_id; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_revenue_state_transitions_tenant_id ON public.revenue_state_transitions USING btree (tenant_id, transitioned_at DESC);


--
-- Name: idx_tenants_api_key_hash; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE UNIQUE INDEX idx_tenants_api_key_hash ON public.tenants USING btree (api_key_hash);


--
-- Name: INDEX idx_tenants_api_key_hash; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON INDEX public.idx_tenants_api_key_hash IS 'Ensures api_key_hash uniqueness for authentication. Purpose: Prevent duplicate API keys across tenants. Required for: B0.4 ingestion authentication.';


--
-- Name: idx_tenants_name; Type: INDEX; Schema: public; Owner: ayewhy
--

CREATE INDEX idx_tenants_name ON public.tenants USING btree (name);


--
-- Name: attribution_allocations trg_allocations_channel_correction_audit; Type: TRIGGER; Schema: public; Owner: ayewhy
--

CREATE TRIGGER trg_allocations_channel_correction_audit AFTER UPDATE OF channel_code ON public.attribution_allocations FOR EACH ROW WHEN ((old.channel_code IS DISTINCT FROM new.channel_code)) EXECUTE FUNCTION public.fn_log_channel_assignment_correction();


--
-- Name: TRIGGER trg_allocations_channel_correction_audit ON attribution_allocations; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TRIGGER trg_allocations_channel_correction_audit ON public.attribution_allocations IS 'Automatically logs all channel_code corrections to channel_assignment_corrections table. 
            Purpose: Provide atomic audit trail for revenue reclassifications. 
            Fires: Only when channel_code column changes (not on other column updates). 
            Note: Does NOT fire on INSERT (corrections are post-ingestion only).';


--
-- Name: channel_taxonomy trg_channel_taxonomy_state_audit; Type: TRIGGER; Schema: public; Owner: ayewhy
--

CREATE TRIGGER trg_channel_taxonomy_state_audit AFTER UPDATE OF state ON public.channel_taxonomy FOR EACH ROW WHEN (((old.state)::text IS DISTINCT FROM (new.state)::text)) EXECUTE FUNCTION public.fn_log_channel_state_change();


--
-- Name: TRIGGER trg_channel_taxonomy_state_audit ON channel_taxonomy; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TRIGGER trg_channel_taxonomy_state_audit ON public.channel_taxonomy IS 'Automatically logs all state transitions to channel_state_transitions table. 
            Purpose: Provide atomic audit trail for channel lifecycle changes. 
            Fires: Only when state column changes (not on other column updates).';


--
-- Name: attribution_allocations trg_check_allocation_sum; Type: TRIGGER; Schema: public; Owner: ayewhy
--

CREATE TRIGGER trg_check_allocation_sum AFTER INSERT OR DELETE OR UPDATE ON public.attribution_allocations FOR EACH ROW EXECUTE FUNCTION public.check_allocation_sum();


--
-- Name: TRIGGER trg_check_allocation_sum ON attribution_allocations; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TRIGGER trg_check_allocation_sum ON public.attribution_allocations IS 'Enforces sum-equality invariant: allocations must sum to event revenue per (event_id, model_version) with ┬▒1 cent tolerance. Purpose: Real-time validation of revenue accounting correctness.';


--
-- Name: attribution_events trg_events_prevent_mutation; Type: TRIGGER; Schema: public; Owner: ayewhy
--

CREATE TRIGGER trg_events_prevent_mutation BEFORE DELETE OR UPDATE ON public.attribution_events FOR EACH ROW EXECUTE FUNCTION public.fn_events_prevent_mutation();


--
-- Name: TRIGGER trg_events_prevent_mutation ON attribution_events; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TRIGGER trg_events_prevent_mutation ON public.attribution_events IS 'Guard trigger preventing UPDATE/DELETE operations on attribution_events. Purpose: Defense-in-depth enforcement of events immutability. Timing: BEFORE UPDATE OR DELETE. Level: FOR EACH ROW. Function: fn_events_prevent_mutation().';


--
-- Name: revenue_ledger trg_ledger_prevent_mutation; Type: TRIGGER; Schema: public; Owner: ayewhy
--

CREATE TRIGGER trg_ledger_prevent_mutation BEFORE DELETE OR UPDATE ON public.revenue_ledger FOR EACH ROW EXECUTE FUNCTION public.fn_ledger_prevent_mutation();


--
-- Name: TRIGGER trg_ledger_prevent_mutation ON revenue_ledger; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TRIGGER trg_ledger_prevent_mutation ON public.revenue_ledger IS 'Guard trigger preventing UPDATE/DELETE operations on revenue_ledger. Purpose: Defense-in-depth enforcement of ledger immutability. Timing: BEFORE UPDATE OR DELETE. Level: FOR EACH ROW. Function: fn_ledger_prevent_mutation().';


--
-- Name: attribution_events trg_pii_guardrail_attribution_events; Type: TRIGGER; Schema: public; Owner: ayewhy
--

CREATE TRIGGER trg_pii_guardrail_attribution_events BEFORE INSERT ON public.attribution_events FOR EACH ROW EXECUTE FUNCTION public.fn_enforce_pii_guardrail();


--
-- Name: TRIGGER trg_pii_guardrail_attribution_events ON attribution_events; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TRIGGER trg_pii_guardrail_attribution_events ON public.attribution_events IS 'PII guardrail trigger (Layer 2 defense-in-depth). Blocks INSERT if raw_payload contains PII keys. Timing: BEFORE INSERT. Level: FOR EACH ROW. Function: fn_enforce_pii_guardrail(). Reference: ADR-003-PII-Defense-Strategy.md Section "Layer 2 (Database Secondary Guardrail)".';


--
-- Name: dead_events trg_pii_guardrail_dead_events; Type: TRIGGER; Schema: public; Owner: ayewhy
--

CREATE TRIGGER trg_pii_guardrail_dead_events BEFORE INSERT ON public.dead_events FOR EACH ROW EXECUTE FUNCTION public.fn_enforce_pii_guardrail();


--
-- Name: TRIGGER trg_pii_guardrail_dead_events ON dead_events; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TRIGGER trg_pii_guardrail_dead_events ON public.dead_events IS 'PII guardrail trigger (Layer 2 defense-in-depth). Blocks INSERT if raw_payload contains PII keys. Timing: BEFORE INSERT. Level: FOR EACH ROW. Function: fn_enforce_pii_guardrail(). Reference: ADR-003-PII-Defense-Strategy.md Section "Layer 2 (Database Secondary Guardrail)".';


--
-- Name: revenue_ledger trg_pii_guardrail_revenue_ledger; Type: TRIGGER; Schema: public; Owner: ayewhy
--

CREATE TRIGGER trg_pii_guardrail_revenue_ledger BEFORE INSERT ON public.revenue_ledger FOR EACH ROW EXECUTE FUNCTION public.fn_enforce_pii_guardrail();


--
-- Name: TRIGGER trg_pii_guardrail_revenue_ledger ON revenue_ledger; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TRIGGER trg_pii_guardrail_revenue_ledger ON public.revenue_ledger IS 'PII guardrail trigger (Layer 2 defense-in-depth). Blocks INSERT if metadata contains PII keys (NULL metadata allowed). Timing: BEFORE INSERT. Level: FOR EACH ROW. Function: fn_enforce_pii_guardrail(). Reference: ADR-003-PII-Defense-Strategy.md Section "Layer 2 (Database Secondary Guardrail)".';


--
-- Name: revenue_ledger trg_revenue_ledger_state_audit; Type: TRIGGER; Schema: public; Owner: ayewhy
--

CREATE TRIGGER trg_revenue_ledger_state_audit AFTER UPDATE OF state ON public.revenue_ledger FOR EACH ROW WHEN (((old.state)::text IS DISTINCT FROM (new.state)::text)) EXECUTE FUNCTION public.fn_log_revenue_state_change();


--
-- Name: TRIGGER trg_revenue_ledger_state_audit ON revenue_ledger; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON TRIGGER trg_revenue_ledger_state_audit ON public.revenue_ledger IS 'Audit trigger for revenue_ledger state changes. 
            Purpose: Automatically log all state transitions to revenue_state_transitions table. 
            Fires: AFTER UPDATE OF state when state value changes. 
            Atomicity: Trigger execution is atomic within the same transaction as the UPDATE.';


--
-- Name: attribution_allocations attribution_allocations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.attribution_allocations
    ADD CONSTRAINT attribution_allocations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: attribution_events attribution_events_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.attribution_events
    ADD CONSTRAINT attribution_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: channel_assignment_corrections channel_assignment_corrections_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.channel_assignment_corrections
    ADD CONSTRAINT channel_assignment_corrections_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: channel_assignment_corrections channel_assignment_corrections_to_channel_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.channel_assignment_corrections
    ADD CONSTRAINT channel_assignment_corrections_to_channel_fkey FOREIGN KEY (to_channel) REFERENCES public.channel_taxonomy(code);


--
-- Name: channel_state_transitions channel_state_transitions_channel_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.channel_state_transitions
    ADD CONSTRAINT channel_state_transitions_channel_code_fkey FOREIGN KEY (channel_code) REFERENCES public.channel_taxonomy(code) ON DELETE CASCADE;


--
-- Name: dead_events dead_events_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.dead_events
    ADD CONSTRAINT dead_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: attribution_allocations fk_allocations_event_id_set_null; Type: FK CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.attribution_allocations
    ADD CONSTRAINT fk_allocations_event_id_set_null FOREIGN KEY (event_id) REFERENCES public.attribution_events(id) ON DELETE SET NULL;


--
-- Name: attribution_allocations fk_attribution_allocations_channel_code; Type: FK CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.attribution_allocations
    ADD CONSTRAINT fk_attribution_allocations_channel_code FOREIGN KEY (channel_code) REFERENCES public.channel_taxonomy(code);


--
-- Name: attribution_events fk_attribution_events_channel; Type: FK CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.attribution_events
    ADD CONSTRAINT fk_attribution_events_channel FOREIGN KEY (channel) REFERENCES public.channel_taxonomy(code) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: reconciliation_runs reconciliation_runs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.reconciliation_runs
    ADD CONSTRAINT reconciliation_runs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: revenue_ledger revenue_ledger_allocation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.revenue_ledger
    ADD CONSTRAINT revenue_ledger_allocation_id_fkey FOREIGN KEY (allocation_id) REFERENCES public.attribution_allocations(id) ON DELETE CASCADE;


--
-- Name: revenue_ledger revenue_ledger_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.revenue_ledger
    ADD CONSTRAINT revenue_ledger_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: revenue_state_transitions revenue_state_transitions_ledger_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.revenue_state_transitions
    ADD CONSTRAINT revenue_state_transitions_ledger_id_fkey FOREIGN KEY (ledger_id) REFERENCES public.revenue_ledger(id) ON DELETE CASCADE;


--
-- Name: revenue_state_transitions revenue_state_transitions_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ayewhy
--

ALTER TABLE ONLY public.revenue_state_transitions
    ADD CONSTRAINT revenue_state_transitions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: attribution_allocations; Type: ROW SECURITY; Schema: public; Owner: ayewhy
--

ALTER TABLE public.attribution_allocations ENABLE ROW LEVEL SECURITY;

--
-- Name: attribution_events; Type: ROW SECURITY; Schema: public; Owner: ayewhy
--

ALTER TABLE public.attribution_events ENABLE ROW LEVEL SECURITY;

--
-- Name: channel_assignment_corrections; Type: ROW SECURITY; Schema: public; Owner: ayewhy
--

ALTER TABLE public.channel_assignment_corrections ENABLE ROW LEVEL SECURITY;

--
-- Name: dead_events; Type: ROW SECURITY; Schema: public; Owner: ayewhy
--

ALTER TABLE public.dead_events ENABLE ROW LEVEL SECURITY;

--
-- Name: reconciliation_runs; Type: ROW SECURITY; Schema: public; Owner: ayewhy
--

ALTER TABLE public.reconciliation_runs ENABLE ROW LEVEL SECURITY;

--
-- Name: revenue_ledger; Type: ROW SECURITY; Schema: public; Owner: ayewhy
--

ALTER TABLE public.revenue_ledger ENABLE ROW LEVEL SECURITY;

--
-- Name: revenue_state_transitions; Type: ROW SECURITY; Schema: public; Owner: ayewhy
--

ALTER TABLE public.revenue_state_transitions ENABLE ROW LEVEL SECURITY;

--
-- Name: attribution_allocations tenant_isolation_policy; Type: POLICY; Schema: public; Owner: ayewhy
--

CREATE POLICY tenant_isolation_policy ON public.attribution_allocations USING ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid));


--
-- Name: POLICY tenant_isolation_policy ON attribution_allocations; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON POLICY tenant_isolation_policy ON public.attribution_allocations IS 'RLS policy enforcing tenant isolation. Purpose: Prevent cross-tenant data access. Requires app.current_tenant_id to be set via set_config().';


--
-- Name: attribution_events tenant_isolation_policy; Type: POLICY; Schema: public; Owner: ayewhy
--

CREATE POLICY tenant_isolation_policy ON public.attribution_events USING ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid));


--
-- Name: POLICY tenant_isolation_policy ON attribution_events; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON POLICY tenant_isolation_policy ON public.attribution_events IS 'RLS policy enforcing tenant isolation. Purpose: Prevent cross-tenant data access. Requires app.current_tenant_id to be set via set_config().';


--
-- Name: channel_assignment_corrections tenant_isolation_policy; Type: POLICY; Schema: public; Owner: ayewhy
--

CREATE POLICY tenant_isolation_policy ON public.channel_assignment_corrections USING ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid));


--
-- Name: POLICY tenant_isolation_policy ON channel_assignment_corrections; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON POLICY tenant_isolation_policy ON public.channel_assignment_corrections IS 'Ensures tenants can only see their own correction records. Purpose: Multi-tenant isolation for audit data. Security: Default deny if app.current_tenant_id is unset.';


--
-- Name: dead_events tenant_isolation_policy; Type: POLICY; Schema: public; Owner: ayewhy
--

CREATE POLICY tenant_isolation_policy ON public.dead_events USING ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid));


--
-- Name: POLICY tenant_isolation_policy ON dead_events; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON POLICY tenant_isolation_policy ON public.dead_events IS 'RLS policy enforcing tenant isolation. Purpose: Prevent cross-tenant data access. Requires app.current_tenant_id to be set via set_config().';


--
-- Name: reconciliation_runs tenant_isolation_policy; Type: POLICY; Schema: public; Owner: ayewhy
--

CREATE POLICY tenant_isolation_policy ON public.reconciliation_runs USING ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid));


--
-- Name: POLICY tenant_isolation_policy ON reconciliation_runs; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON POLICY tenant_isolation_policy ON public.reconciliation_runs IS 'RLS policy enforcing tenant isolation. Purpose: Prevent cross-tenant data access. Requires app.current_tenant_id to be set via set_config().';


--
-- Name: revenue_ledger tenant_isolation_policy; Type: POLICY; Schema: public; Owner: ayewhy
--

CREATE POLICY tenant_isolation_policy ON public.revenue_ledger USING ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid));


--
-- Name: POLICY tenant_isolation_policy ON revenue_ledger; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON POLICY tenant_isolation_policy ON public.revenue_ledger IS 'RLS policy enforcing tenant isolation. Purpose: Prevent cross-tenant data access. Requires app.current_tenant_id to be set via set_config().';


--
-- Name: revenue_state_transitions tenant_isolation_policy; Type: POLICY; Schema: public; Owner: ayewhy
--

CREATE POLICY tenant_isolation_policy ON public.revenue_state_transitions USING ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid));


--
-- Name: POLICY tenant_isolation_policy ON revenue_state_transitions; Type: COMMENT; Schema: public; Owner: ayewhy
--

COMMENT ON POLICY tenant_isolation_policy ON public.revenue_state_transitions IS 'RLS policy enforcing tenant isolation on audit table. 
            Purpose: Prevent cross-tenant access to audit trail. 
            Requires app.current_tenant_id to be set via set_config().';


--
-- Name: TABLE attribution_allocations; Type: ACL; Schema: public; Owner: ayewhy
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.attribution_allocations TO app_rw;
GRANT SELECT ON TABLE public.attribution_allocations TO app_ro;


--
-- Name: TABLE attribution_events; Type: ACL; Schema: public; Owner: ayewhy
--

GRANT SELECT,INSERT ON TABLE public.attribution_events TO app_rw;
GRANT SELECT ON TABLE public.attribution_events TO app_ro;


--
-- Name: TABLE dead_events; Type: ACL; Schema: public; Owner: ayewhy
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.dead_events TO app_rw;
GRANT SELECT ON TABLE public.dead_events TO app_ro;


--
-- Name: TABLE revenue_ledger; Type: ACL; Schema: public; Owner: ayewhy
--

GRANT SELECT,INSERT ON TABLE public.revenue_ledger TO app_rw;
GRANT SELECT ON TABLE public.revenue_ledger TO app_ro;


--
-- Name: TABLE pii_audit_findings; Type: ACL; Schema: public; Owner: ayewhy
--

GRANT SELECT ON TABLE public.pii_audit_findings TO app_rw;
GRANT SELECT ON TABLE public.pii_audit_findings TO app_ro;


--
-- Name: SEQUENCE pii_audit_findings_id_seq; Type: ACL; Schema: public; Owner: ayewhy
--

GRANT SELECT,USAGE ON SEQUENCE public.pii_audit_findings_id_seq TO app_rw;


--
-- Name: TABLE reconciliation_runs; Type: ACL; Schema: public; Owner: ayewhy
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.reconciliation_runs TO app_rw;
GRANT SELECT ON TABLE public.reconciliation_runs TO app_ro;


--
-- PostgreSQL database dump complete
--

\unrestrict ZIznBR7sfkJaJAk4OtVPKg5rT5SYSQode9rx17OXBkLhcF05E3hSnf1hMZuhIzT

