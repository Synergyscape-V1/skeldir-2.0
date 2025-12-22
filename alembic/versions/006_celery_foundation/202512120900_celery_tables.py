"""Create Celery broker/result tables for Postgres SQLA transport."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202512120900"
down_revision = "202511131121"  # EG-1B: Depend on core schema (tenants table exists)
branch_labels = ("celery_foundation",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kombu_queue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=200), nullable=False, unique=True),
        schema="public",
    )

    op.create_table(
        "kombu_message",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("visible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("version", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("queue", sa.String(length=255), nullable=False),
        schema="public",
    )
    op.create_index("ix_kombu_message_queue", "kombu_message", ["queue"], schema="public")
    op.create_index("ix_kombu_message_visible", "kombu_message", ["visible"], schema="public")
    op.create_index("ix_kombu_message_timestamp", "kombu_message", ["timestamp"], schema="public")

    op.create_table(
        "celery_taskmeta",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(length=155), nullable=False, unique=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("result", sa.LargeBinary(), nullable=True),
        sa.Column("date_done", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column("name", sa.String(length=155), nullable=True),
        sa.Column("args", sa.Text(), nullable=True),
        sa.Column("kwargs", sa.Text(), nullable=True),
        sa.Column("worker", sa.String(length=155), nullable=True),
        sa.Column("retries", sa.Integer(), nullable=True),
        schema="public",
    )
    op.create_index("ix_celery_taskmeta_task_id", "celery_taskmeta", ["task_id"], schema="public")

    op.create_table(
        "celery_tasksetmeta",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("taskset_id", sa.String(length=155), nullable=False, unique=True),
        sa.Column("result", sa.LargeBinary(), nullable=True),
        sa.Column("date_done", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema="public",
    )
    op.create_index("ix_celery_tasksetmeta_taskset_id", "celery_tasksetmeta", ["taskset_id"], schema="public")

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.kombu_message TO app_user;
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.kombu_queue TO app_user;
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_taskmeta TO app_user;
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_tasksetmeta TO app_user;
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_celery_tasksetmeta_taskset_id", table_name="celery_tasksetmeta", schema="public")
    op.drop_table("celery_tasksetmeta", schema="public")
    op.drop_index("ix_celery_taskmeta_task_id", table_name="celery_taskmeta", schema="public")
    op.drop_table("celery_taskmeta", schema="public")
    op.drop_index("ix_kombu_message_timestamp", table_name="kombu_message", schema="public")
    op.drop_index("ix_kombu_message_visible", table_name="kombu_message", schema="public")
    op.drop_index("ix_kombu_message_queue", table_name="kombu_message", schema="public")
    op.drop_table("kombu_message", schema="public")
    op.drop_table("kombu_queue", schema="public")
