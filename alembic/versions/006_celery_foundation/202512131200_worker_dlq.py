"""Create worker DLQ table for failed Celery tasks.

Revision ID: 202512131200
Revises: 202512120900
Create Date: 2025-12-13 12:00:00

B0.5.2: Worker-Level DLQ Schema

This migration creates celery_task_failures table for persistent storage of
failed background task executions, enabling replay and remediation workflows.

Schema Design:
- Adapts dead_events pattern from B0.4 ingestion DLQ
- Adds Celery-specific metadata (task_id, queue, worker)
- Supports both tenant-scoped and global task failures (nullable tenant_id)
- Maintains RLS compatibility for tenant-scoped failures

Exit Gates:
- Migration applies cleanly
- celery_task_failures table exists with proper columns
- app_user has CRUD privileges
- RLS policy created (optional enforcement based on tenant_id presence)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

# revision identifiers, used by Alembic.
revision = "202512131200"
down_revision = "202512120900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create celery_task_failures table with B0.4 DLQ pattern alignment."""

    op.create_table(
        "celery_task_failures",
        # Primary Key
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),

        # Celery Task Metadata
        sa.Column("task_id", sa.String(155), nullable=False, index=True, comment="Celery task execution ID"),
        sa.Column("task_name", sa.String(255), nullable=False, index=True, comment="Fully qualified task name (app.tasks.module.function)"),
        sa.Column("queue", sa.String(100), nullable=True, comment="Target queue name (housekeeping, maintenance, llm)"),
        sa.Column("worker", sa.String(255), nullable=True, comment="Worker hostname/PID that executed task"),

        # Task Arguments (JSONB for structured storage)
        sa.Column("task_args", JSONB, nullable=True, comment="Positional arguments as JSON array"),
        sa.Column("task_kwargs", JSONB, nullable=True, comment="Keyword arguments as JSON object"),

        # Tenant Context (nullable for global tasks)
        sa.Column("tenant_id", PGUUID(as_uuid=True), nullable=True, index=True, comment="Tenant UUID if task is tenant-scoped"),

        # Error Classification (aligned with B0.4 DLQ pattern)
        sa.Column("error_type", sa.String(100), nullable=False, comment="Error classification (transient, permanent, unknown)"),
        sa.Column("exception_class", sa.String(255), nullable=False, comment="Python exception class name"),
        sa.Column("error_message", sa.Text, nullable=False, comment="Exception message (first 500 chars)"),
        sa.Column("traceback", sa.Text, nullable=True, comment="Full Python traceback (first 2000 chars)"),

        # Retry & Remediation (aligned with B0.4 DLQ pattern)
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0", comment="Number of retry attempts"),
        sa.Column("last_retry_at", sa.TIMESTAMP(timezone=True), nullable=True, comment="Timestamp of last retry attempt"),
        sa.Column("status", sa.String(50), nullable=False, server_default="'pending'", comment="Remediation status (pending, in_progress, resolved, abandoned)"),
        sa.Column("remediation_notes", sa.Text, nullable=True, comment="Engineer notes on remediation actions"),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True, comment="Timestamp when task failure resolved"),

        # Correlation & Observability
        sa.Column("correlation_id", PGUUID(as_uuid=True), nullable=True, comment="Request correlation ID from task context"),

        # Timestamps
        sa.Column("failed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="Timestamp when task failed"),

        schema="public",
    )

    # Indexes for query performance
    op.create_index("idx_celery_task_failures_status", "celery_task_failures", ["status", "failed_at"], schema="public")
    op.create_index("idx_celery_task_failures_task_name", "celery_task_failures", ["task_name"], schema="public")

    # CHECK constraints (aligned with dead_events pattern)
    op.execute("""
        ALTER TABLE celery_task_failures
        ADD CONSTRAINT ck_celery_task_failures_status_valid
        CHECK (status IN ('pending', 'in_progress', 'resolved', 'abandoned'))
    """)

    op.execute("""
        ALTER TABLE celery_task_failures
        ADD CONSTRAINT ck_celery_task_failures_retry_count_positive
        CHECK (retry_count >= 0)
    """)

    # Grant privileges to app_user (RLS-restricted role)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_task_failures TO app_user;
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
            END IF;
        END
        $$;
    """)

    # Optional: RLS policy for tenant-scoped failures
    # Note: RLS only enforced when tenant_id IS NOT NULL (global tasks bypass RLS)
    op.execute("""
        ALTER TABLE celery_task_failures ENABLE ROW LEVEL SECURITY;
    """)

    op.execute("""
        CREATE POLICY tenant_isolation_policy ON celery_task_failures
        FOR ALL
        TO app_user
        USING (
            tenant_id IS NULL OR
            tenant_id::text = current_setting('app.current_tenant_id', true)
        );
    """)


def downgrade() -> None:
    """Drop celery_task_failures table."""

    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON celery_task_failures")
    op.execute("ALTER TABLE celery_task_failures DROP CONSTRAINT IF EXISTS ck_celery_task_failures_retry_count_positive")
    op.execute("ALTER TABLE celery_task_failures DROP CONSTRAINT IF EXISTS ck_celery_task_failures_status_valid")
    op.drop_index("idx_celery_task_failures_task_name", table_name="celery_task_failures", schema="public")
    op.drop_index("idx_celery_task_failures_status", table_name="celery_task_failures", schema="public")
    op.drop_table("celery_task_failures", schema="public")
