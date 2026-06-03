"""B2.4-P6 fit-id resolution policy for RLS-bound workers.

Revision ID: 202606031200
Revises: 202606021200
Create Date: 2026-06-03 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202606031200"
down_revision: Union[str, None] = "202606021200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PARTITION_COUNT = 16

FIT_POLICY_USING = """
(
    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    OR id = NULLIF(current_setting('app.b24_fit_resolution_id', true), '')::uuid
)
"""

FIT_POLICY_WITH_CHECK = """
tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
"""

FIT_POLICY_USING_DOWN = """
tenant_id = current_setting('app.current_tenant_id', true)::uuid
"""

FIT_POLICY_WITH_CHECK_DOWN = """
tenant_id = current_setting('app.current_tenant_id', true)::uuid
"""


def _fit_tables() -> tuple[str, ...]:
    partitions = tuple(
        f"bayesian_model_fits_p{remainder:02d}" for remainder in range(PARTITION_COUNT)
    )
    return ("bayesian_model_fits", *partitions)


def _alter_fit_policy(table_name: str, *, using_sql: str, with_check_sql: str) -> None:
    if table_name != "bayesian_model_fits":
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_policies
                    WHERE schemaname = 'public'
                      AND tablename = '{table_name}'
                      AND policyname = 'tenant_isolation_policy_{table_name}'
                ) THEN
                    ALTER POLICY tenant_isolation_policy_{table_name}
                    ON public.{table_name}
                    USING ({using_sql})
                    WITH CHECK ({with_check_sql});
                END IF;
            END
            $$;
            """
        )
        return
    op.execute(
        f"""
        ALTER POLICY tenant_isolation_policy_{table_name}
        ON public.{table_name}
        USING ({using_sql})
        WITH CHECK ({with_check_sql})
        """
    )


def upgrade() -> None:
    for table_name in _fit_tables():
        _alter_fit_policy(
            table_name,
            using_sql=FIT_POLICY_USING,
            with_check_sql=FIT_POLICY_WITH_CHECK,
        )


def downgrade() -> None:
    for table_name in _fit_tables():
        _alter_fit_policy(
            table_name,
            using_sql=FIT_POLICY_USING_DOWN,
            with_check_sql=FIT_POLICY_WITH_CHECK_DOWN,
        )
