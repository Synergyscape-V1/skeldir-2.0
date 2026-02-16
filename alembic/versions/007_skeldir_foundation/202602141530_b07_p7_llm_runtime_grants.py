"""B0.7-P7 runtime grants for LLM ledger/audit tables.

Revision ID: 202602141530
Revises: 202602141200
Create Date: 2026-02-14 15:30:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "202602141530"
down_revision: Union[str, None] = "202602141200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


<<<<<<< HEAD
RW_TABLES = (
    "llm_api_calls",
    "llm_call_audit",
    "llm_monthly_costs",
    "llm_breaker_state",
    "llm_hourly_shutoff_state",
    "llm_monthly_budget_state",
    "llm_budget_reservations",
    "llm_semantic_cache",
)
=======
TABLE_PRIVILEGES = {
    "llm_api_calls": "SELECT, INSERT, UPDATE",
    "llm_call_audit": "SELECT, INSERT",
    "llm_monthly_costs": "SELECT, INSERT, UPDATE",
    "llm_breaker_state": "SELECT, INSERT, UPDATE",
    "llm_hourly_shutoff_state": "SELECT, INSERT, UPDATE",
    "llm_monthly_budget_state": "SELECT, INSERT, UPDATE",
    "llm_budget_reservations": "SELECT, INSERT, UPDATE",
    "llm_semantic_cache": "SELECT, INSERT, UPDATE",
}
>>>>>>> 2df083e09a5bb0ba4d3888d774dd055b2cb42bd4


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
<<<<<<< HEAD
    for table_name in RW_TABLES:
        _grant_if_role_exists("app_rw", "SELECT, INSERT, UPDATE", table_name)
        _grant_if_role_exists("app_user", "SELECT, INSERT, UPDATE", table_name)
=======
    for table_name, privileges in TABLE_PRIVILEGES.items():
        _grant_if_role_exists("app_rw", privileges, table_name)
        _grant_if_role_exists("app_user", privileges, table_name)
>>>>>>> 2df083e09a5bb0ba4d3888d774dd055b2cb42bd4
        _grant_if_role_exists("app_ro", "SELECT", table_name)


def downgrade() -> None:
<<<<<<< HEAD
    for table_name in RW_TABLES:
=======
    for table_name in TABLE_PRIVILEGES:
>>>>>>> 2df083e09a5bb0ba4d3888d774dd055b2cb42bd4
        _revoke_if_role_exists("app_ro", table_name)
        _revoke_if_role_exists("app_user", table_name)
        _revoke_if_role_exists("app_rw", table_name)
