"""Rename celery_task_failures to worker_failed_jobs (B0.5.3.1 canonical DLQ).

Revision ID: 202512151200
Revises: 202512131600
Create Date: 2025-12-15 12:00:00

B0.5.3.1: DLQ Table Canonicalization

This migration renames celery_task_failures to worker_failed_jobs to align with
B0.5.2 canonical naming convention. The schema remains identical, only the table
name changes for consistency with worker DLQ terminology.

Rationale:
- B0.5.2 documentation specifies worker_failed_jobs as canonical table name
- Actual implementation used celery_task_failures (naming inconsistency)
- B0.5.3.1 gap closure requires canonicalization before attribution work begins

Exit Gates:
- Table renamed without data loss
- All indexes, constraints, and policies preserved
- app_user privileges preserved
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "202512151200"
down_revision = "202512131600"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename celery_task_failures to worker_failed_jobs."""

    # Rename the table
    op.rename_table(
        "celery_task_failures",
        "worker_failed_jobs",
        schema="public",
    )

    # Rename indexes to match new table name
    op.execute("""
        ALTER INDEX idx_celery_task_failures_status
        RENAME TO idx_worker_failed_jobs_status
    """)

    op.execute("""
        ALTER INDEX idx_celery_task_failures_task_name
        RENAME TO idx_worker_failed_jobs_task_name
    """)

    # Rename constraints to match new table name
    op.execute("""
        ALTER TABLE worker_failed_jobs
        RENAME CONSTRAINT ck_celery_task_failures_status_valid
        TO ck_worker_failed_jobs_status_valid
    """)

    op.execute("""
        ALTER TABLE worker_failed_jobs
        RENAME CONSTRAINT ck_celery_task_failures_retry_count_positive
        TO ck_worker_failed_jobs_retry_count_positive
    """)

    # Note: RLS policy tenant_isolation_policy remains unchanged (table-agnostic)
    # Note: Privileges are automatically preserved with table rename


def downgrade() -> None:
    """Rename worker_failed_jobs back to celery_task_failures."""

    # Rename constraints back
    op.execute("""
        ALTER TABLE worker_failed_jobs
        RENAME CONSTRAINT ck_worker_failed_jobs_retry_count_positive
        TO ck_celery_task_failures_retry_count_positive
    """)

    op.execute("""
        ALTER TABLE worker_failed_jobs
        RENAME CONSTRAINT ck_worker_failed_jobs_status_valid
        TO ck_celery_task_failures_status_valid
    """)

    # Rename indexes back
    op.execute("""
        ALTER INDEX idx_worker_failed_jobs_task_name
        RENAME TO idx_celery_task_failures_task_name
    """)

    op.execute("""
        ALTER INDEX idx_worker_failed_jobs_status
        RENAME TO idx_celery_task_failures_status
    """)

    # Rename the table back
    op.rename_table(
        "worker_failed_jobs",
        "celery_task_failures",
        schema="public",
    )
