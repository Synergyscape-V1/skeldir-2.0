"""Backfill Kombu SQLA transport sequences for Celery broker tables.

This migration aligns the Postgres schema with Kombu's SQLAlchemy transport
expectations by creating the explicitly named sequences used for kombu_queue
and kombu_message primary keys. It also sets column defaults to use these
sequences and ensures the sequence counters are advanced to existing maxima
to avoid primary key collisions on upgraded databases.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202512131530"
down_revision = "202512131200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Kombu's SQLAlchemy transport defines explicit sequences for queue/message
    # IDs, and Celery's database result backend defines explicit sequences for
    # task/taskset IDs. Create them if missing so inserts do not fail on clean
    # databases.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'S'
                  AND n.nspname = 'public'
                  AND c.relname = 'queue_id_sequence'
            ) THEN
                CREATE SEQUENCE public.queue_id_sequence;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'S'
                  AND n.nspname = 'public'
                  AND c.relname = 'message_id_sequence'
            ) THEN
                CREATE SEQUENCE public.message_id_sequence;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'S'
                  AND n.nspname = 'public'
                  AND c.relname = 'task_id_sequence'
            ) THEN
                CREATE SEQUENCE public.task_id_sequence;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'S'
                  AND n.nspname = 'public'
                  AND c.relname = 'taskset_id_sequence'
            ) THEN
                CREATE SEQUENCE public.taskset_id_sequence;
            END IF;
        END
        $$;
        """
    )

    # Align sequence counters with existing data to prevent PK conflicts when
    # switching defaults from the auto-generated *_id_seq sequences.
    op.execute(
        """
        SELECT setval(
            'public.queue_id_sequence',
            GREATEST((SELECT COALESCE(MAX(id), 0) FROM public.kombu_queue), 1),
            (SELECT MAX(id) IS NOT NULL FROM public.kombu_queue)
        );
        """
    )
    op.execute(
        """
        SELECT setval(
            'public.message_id_sequence',
            GREATEST((SELECT COALESCE(MAX(id), 0) FROM public.kombu_message), 1),
            (SELECT MAX(id) IS NOT NULL FROM public.kombu_message)
        );
        SELECT setval(
            'public.task_id_sequence',
            GREATEST((SELECT COALESCE(MAX(id), 0) FROM public.celery_taskmeta), 1),
            (SELECT MAX(id) IS NOT NULL FROM public.celery_taskmeta)
        );
        SELECT setval(
            'public.taskset_id_sequence',
            GREATEST((SELECT COALESCE(MAX(id), 0) FROM public.celery_tasksetmeta), 1),
            (SELECT MAX(id) IS NOT NULL FROM public.celery_tasksetmeta)
        );
        """
    )

    # Set ownership and defaults so Kombu inserts use the expected sequences.
    op.execute("ALTER SEQUENCE public.queue_id_sequence OWNED BY public.kombu_queue.id;")
    op.execute("ALTER SEQUENCE public.message_id_sequence OWNED BY public.kombu_message.id;")
    op.execute("ALTER SEQUENCE public.task_id_sequence OWNED BY public.celery_taskmeta.id;")
    op.execute("ALTER SEQUENCE public.taskset_id_sequence OWNED BY public.celery_tasksetmeta.id;")

    op.alter_column(
        "kombu_queue",
        "id",
        server_default=sa.text("nextval('queue_id_sequence')"),
        schema="public",
    )
    op.alter_column(
        "kombu_message",
        "id",
        server_default=sa.text("nextval('message_id_sequence')"),
        schema="public",
    )
    op.alter_column(
        "celery_taskmeta",
        "id",
        server_default=sa.text("nextval('task_id_sequence')"),
        schema="public",
    )
    op.alter_column(
        "celery_tasksetmeta",
        "id",
        server_default=sa.text("nextval('taskset_id_sequence')"),
        schema="public",
    )

    # Keep app_user privileges consistent with earlier migration grants.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT USAGE, SELECT ON SEQUENCE public.queue_id_sequence TO app_user;
                GRANT USAGE, SELECT ON SEQUENCE public.message_id_sequence TO app_user;
                GRANT USAGE, SELECT ON SEQUENCE public.task_id_sequence TO app_user;
                GRANT USAGE, SELECT ON SEQUENCE public.taskset_id_sequence TO app_user;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # Revert defaults to the auto-generated sequences created with the tables.
    op.alter_column(
        "kombu_queue",
        "id",
        server_default=sa.text("nextval('kombu_queue_id_seq'::regclass)"),
        schema="public",
    )
    op.alter_column(
        "kombu_message",
        "id",
        server_default=sa.text("nextval('kombu_message_id_seq'::regclass)"),
        schema="public",
    )
    op.alter_column(
        "celery_taskmeta",
        "id",
        server_default=sa.text("nextval('celery_taskmeta_id_seq'::regclass)"),
        schema="public",
    )
    op.alter_column(
        "celery_tasksetmeta",
        "id",
        server_default=sa.text("nextval('celery_tasksetmeta_id_seq'::regclass)"),
        schema="public",
    )

    op.execute("ALTER SEQUENCE IF EXISTS public.queue_id_sequence OWNED BY NONE;")
    op.execute("ALTER SEQUENCE IF EXISTS public.message_id_sequence OWNED BY NONE;")
    op.execute("ALTER SEQUENCE IF EXISTS public.task_id_sequence OWNED BY NONE;")
    op.execute("ALTER SEQUENCE IF EXISTS public.taskset_id_sequence OWNED BY NONE;")

    op.execute("DROP SEQUENCE IF EXISTS public.queue_id_sequence;")
    op.execute("DROP SEQUENCE IF EXISTS public.message_id_sequence;")
    op.execute("DROP SEQUENCE IF EXISTS public.task_id_sequence;")
    op.execute("DROP SEQUENCE IF EXISTS public.taskset_id_sequence;")
