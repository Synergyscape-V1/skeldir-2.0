"""B1.6-P1 grant runtime roles access to llm_validation_failures sink.

Revision ID: 202603301230
Revises: 202603251200
Create Date: 2026-03-30 12:30:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "202603301230"
down_revision: Union[str, None] = "202603251200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _grant_if_role_exists(role: str, privileges: str, table_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE 'GRANT {privileges} ON TABLE {table_name} TO {role}';
            END IF;
        END
        $$;
        """
    )


def _revoke_if_role_exists(role: str, table_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE 'REVOKE ALL ON TABLE {table_name} FROM {role}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    _grant_if_role_exists("app_rw", "SELECT, INSERT", "llm_validation_failures")
    _grant_if_role_exists("app_user", "SELECT, INSERT", "llm_validation_failures")
    _grant_if_role_exists("app_ro", "SELECT", "llm_validation_failures")


def downgrade() -> None:
    _revoke_if_role_exists("app_ro", "llm_validation_failures")
    _revoke_if_role_exists("app_user", "llm_validation_failures")
    _revoke_if_role_exists("app_rw", "llm_validation_failures")
