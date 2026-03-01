"""B1.2-P3 corrective: Postgres-backed JWT verification cache + refresh telemetry.

Revision ID: 202603011930
Revises: 202602281430
Create Date: 2026-03-01 19:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202603011930"
down_revision: Union[str, None] = "202602281430"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _grant_if_role_exists(role: str, grant_sql: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE '{grant_sql}';
            END IF;
        END
        $$;
        """
    )


def _revoke_if_role_exists(role: str, revoke_sql: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE '{revoke_sql}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.jwt_verification_cache (
            singleton_id SMALLINT PRIMARY KEY CHECK (singleton_id = 1),
            jwks_json TEXT NULL,
            fetched_at TIMESTAMPTZ NULL,
            next_allowed_refresh_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_refresh_error_at TIMESTAMPTZ NULL,
            refresh_error_count INTEGER NOT NULL DEFAULT 0,
            refresh_event_count BIGINT NOT NULL DEFAULT 0,
            last_refresh_reason TEXT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.jwt_verification_cache TO app_user",
    )
    _grant_if_role_exists(
        "skeldir",
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.jwt_verification_cache TO skeldir",
    )


def downgrade() -> None:
    _revoke_if_role_exists(
        "app_user",
        "REVOKE SELECT, INSERT, UPDATE ON TABLE public.jwt_verification_cache FROM app_user",
    )
    _revoke_if_role_exists(
        "skeldir",
        "REVOKE SELECT, INSERT, UPDATE ON TABLE public.jwt_verification_cache FROM skeldir",
    )
