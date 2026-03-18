"""B1.4-P1: allow redacted PII keys in dead_events while keeping canonical strict.

Revision ID: 202603161130
Revises: 202603101530
Create Date: 2026-03-16 11:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202603161130"
down_revision: Union[str, None] = "202603101530"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PII_KEYS = [
    "email",
    "email_address",
    "phone",
    "phone_number",
    "ssn",
    "social_security_number",
    "ip_address",
    "ip",
    "first_name",
    "last_name",
    "full_name",
    "address",
    "street_address",
]


def _strict_detection_cases(field_name: str) -> str:
    return "\n".join(
        [
            f"            IF jsonb_path_exists({field_name}, '$.**.{key}') THEN detected_key := '{key}'; END IF;"
            for key in PII_KEYS
        ]
    )


def _unredacted_detection_cases(field_name: str) -> str:
    return "\n".join(
        [
            "            IF jsonb_path_exists("
            f"{field_name}, '$.**.{key} ? (@ != \"[REDACTED_B1.4]\")'"
            f") THEN detected_key := '{key}'; END IF;"
            for key in PII_KEYS
        ]
    )


def upgrade() -> None:
    strict_cases_events = _strict_detection_cases("NEW.raw_payload")
    strict_cases_metadata = _strict_detection_cases("NEW.metadata")
    unredacted_cases_dead = _unredacted_detection_cases("NEW.raw_payload")

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION fn_enforce_pii_guardrail()
        RETURNS TRIGGER AS $$
        DECLARE
            detected_key TEXT;
        BEGIN
            IF TG_TABLE_NAME = 'attribution_events' THEN
                IF fn_detect_pii_keys(NEW.raw_payload) THEN
                    detected_key := NULL;
{strict_cases_events}
                    RAISE EXCEPTION
                      'PII key detected in %.raw_payload. Ingestion blocked by database policy (Layer 2 guardrail). Key found: %. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from payload before retry.',
                      TG_TABLE_NAME,
                      COALESCE(detected_key, 'unknown')
                    USING ERRCODE = '23514';
                END IF;
            END IF;

            IF TG_TABLE_NAME = 'dead_events' THEN
                detected_key := NULL;
{unredacted_cases_dead}
                IF detected_key IS NOT NULL THEN
                    RAISE EXCEPTION
                      'PII key detected in %.raw_payload with unredacted value. Dead-letter payloads must use [REDACTED_B1.4] for banned keys. Key found: %.',
                      TG_TABLE_NAME,
                      detected_key
                    USING ERRCODE = '23514';
                END IF;
            END IF;

            IF TG_TABLE_NAME = 'revenue_ledger' THEN
                IF NEW.metadata IS NOT NULL THEN
                    IF fn_detect_pii_keys(NEW.metadata) THEN
                        detected_key := NULL;
{strict_cases_metadata}
                        RAISE EXCEPTION
                          'PII key detected in revenue_ledger.metadata. Write blocked by database policy (Layer 2 guardrail). Key found: %. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from metadata before retry.',
                          COALESCE(detected_key, 'unknown')
                        USING ERRCODE = '23514';
                    END IF;
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # Historical environments may still wire guardrail triggers to split
    # functions (fn_enforce_pii_guardrail_events / _revenue). Rebind those
    # semantics if they exist, without introducing new functions in clean graphs.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_proc
                WHERE proname = 'fn_enforce_pii_guardrail_events'
                  AND pg_function_is_visible(oid)
            ) THEN
                EXECUTE $ddl$
                CREATE OR REPLACE FUNCTION public.fn_enforce_pii_guardrail_events()
                RETURNS trigger AS $fn$
                DECLARE
                    detected_key text;
                BEGIN
                    IF TG_TABLE_NAME = 'attribution_events' THEN
                        detected_key := NULL;
{strict_cases_events}
                        IF detected_key IS NOT NULL THEN
                            RAISE EXCEPTION
                              'PII key detected in %.raw_payload. Ingestion blocked by database policy (Layer 2 guardrail). Key found: %. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from payload before retry.',
                              TG_TABLE_NAME,
                              COALESCE(detected_key, 'unknown')
                            USING ERRCODE = '23514';
                        END IF;
                    END IF;

                    IF TG_TABLE_NAME = 'dead_events' THEN
                        detected_key := NULL;
{unredacted_cases_dead}
                        IF detected_key IS NOT NULL THEN
                            RAISE EXCEPTION
                              'PII key detected in %.raw_payload with unredacted value. Dead-letter payloads must use [REDACTED_B1.4] for banned keys. Key found: %.',
                              TG_TABLE_NAME,
                              detected_key
                            USING ERRCODE = '23514';
                        END IF;
                    END IF;

                    RETURN NEW;
                END;
                $fn$ LANGUAGE plpgsql;
                $ddl$;
            END IF;

            IF EXISTS (
                SELECT 1
                FROM pg_proc
                WHERE proname = 'fn_enforce_pii_guardrail_revenue'
                  AND pg_function_is_visible(oid)
            ) THEN
                EXECUTE $ddl$
                CREATE OR REPLACE FUNCTION public.fn_enforce_pii_guardrail_revenue()
                RETURNS trigger AS $fn$
                DECLARE
                    detected_key text;
                BEGIN
                    IF NEW.metadata IS NOT NULL THEN
                        IF fn_detect_pii_keys(NEW.metadata) THEN
                            detected_key := NULL;
{strict_cases_metadata}
                            RAISE EXCEPTION
                              'PII key detected in revenue_ledger.metadata. Write blocked by database policy (Layer 2 guardrail). Key found: %. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from metadata before retry.',
                              COALESCE(detected_key, 'unknown')
                            USING ERRCODE = '23514';
                        END IF;
                    END IF;
                    RETURN NEW;
                END;
                $fn$ LANGUAGE plpgsql;
                $ddl$;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    strict_cases_events = _strict_detection_cases("NEW.raw_payload")
    strict_cases_metadata = _strict_detection_cases("NEW.metadata")

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION fn_enforce_pii_guardrail()
        RETURNS TRIGGER AS $$
        DECLARE
            detected_key TEXT;
        BEGIN
            IF TG_TABLE_NAME IN ('attribution_events', 'dead_events') THEN
                IF fn_detect_pii_keys(NEW.raw_payload) THEN
                    detected_key := NULL;
{strict_cases_events}
                    RAISE EXCEPTION
                      'PII key detected in %.raw_payload. Ingestion blocked by database policy (Layer 2 guardrail). Key found: %. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from payload before retry.',
                      TG_TABLE_NAME,
                      COALESCE(detected_key, 'unknown')
                    USING ERRCODE = '23514';
                END IF;
            END IF;

            IF TG_TABLE_NAME = 'revenue_ledger' THEN
                IF NEW.metadata IS NOT NULL THEN
                    IF fn_detect_pii_keys(NEW.metadata) THEN
                        detected_key := NULL;
{strict_cases_metadata}
                        RAISE EXCEPTION
                          'PII key detected in revenue_ledger.metadata. Write blocked by database policy (Layer 2 guardrail). Key found: %. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from metadata before retry.',
                          COALESCE(detected_key, 'unknown')
                        USING ERRCODE = '23514';
                    END IF;
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_proc
                WHERE proname = 'fn_enforce_pii_guardrail_events'
                  AND pg_function_is_visible(oid)
            ) THEN
                EXECUTE $ddl$
                CREATE OR REPLACE FUNCTION public.fn_enforce_pii_guardrail_events()
                RETURNS trigger AS $fn$
                DECLARE
                    detected_key text;
                BEGIN
                    IF fn_detect_pii_keys(NEW.raw_payload) THEN
                        detected_key := NULL;
{strict_cases_events}
                        RAISE EXCEPTION
                          'PII key detected in %.raw_payload. Ingestion blocked by database policy (Layer 2 guardrail). Key found: %. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from payload before retry.',
                          TG_TABLE_NAME,
                          COALESCE(detected_key, 'unknown')
                        USING ERRCODE = '23514';
                    END IF;
                    RETURN NEW;
                END;
                $fn$ LANGUAGE plpgsql;
                $ddl$;
            END IF;

            IF EXISTS (
                SELECT 1
                FROM pg_proc
                WHERE proname = 'fn_enforce_pii_guardrail_revenue'
                  AND pg_function_is_visible(oid)
            ) THEN
                EXECUTE $ddl$
                CREATE OR REPLACE FUNCTION public.fn_enforce_pii_guardrail_revenue()
                RETURNS trigger AS $fn$
                DECLARE
                    detected_key text;
                BEGIN
                    IF NEW.metadata IS NOT NULL AND fn_detect_pii_keys(NEW.metadata) THEN
                        detected_key := NULL;
{strict_cases_metadata}
                        RAISE EXCEPTION
                          'PII key detected in revenue_ledger.metadata. Write blocked by database policy (Layer 2 guardrail). Key found: %. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from metadata before retry.',
                          COALESCE(detected_key, 'unknown')
                        USING ERRCODE = '23514';
                    END IF;
                    RETURN NEW;
                END;
                $fn$ LANGUAGE plpgsql;
                $ddl$;
            END IF;
        END
        $$;
        """
    )
