"""Align kombu_message schema with Kombu SQLAlchemy transport models.

Kombu's SQLAlchemy transport expects a queue_id foreign key column and stores
payloads as text with a timestamp column. The initial migration created a
string queue column and used a binary payload, which causes worker startup
failures when the transport queries kombu_message.queue_id.

This migration adds the missing queue_id column (with FK to kombu_queue),
backfills it from the legacy queue name when present, aligns column types with
Kombu defaults, and updates indexes to match the transport's metadata.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202512131600"
down_revision = "202512131530"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop legacy queue index so the column can be removed safely.
    op.execute("DROP INDEX IF EXISTS public.ix_kombu_message_queue;")

    # Align Celery result backend nullable semantics (date_done can be NULL).
    op.execute("ALTER TABLE public.celery_taskmeta ALTER COLUMN date_done DROP NOT NULL;")
    op.execute("ALTER TABLE public.celery_tasksetmeta ALTER COLUMN date_done DROP NOT NULL;")

    # Add queue_id FK required by Kombu transport; populate from legacy queue name if present.
    op.execute("ALTER TABLE public.kombu_message ADD COLUMN IF NOT EXISTS queue_id INTEGER;")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_kombu_message_queue'
                  AND conrelid = 'public.kombu_message'::regclass
            ) THEN
                ALTER TABLE public.kombu_message
                ADD CONSTRAINT fk_kombu_message_queue
                FOREIGN KEY (queue_id) REFERENCES public.kombu_queue(id);
            END IF;
        END
        $$;
        """
    )
    # Kombu allows NULL timestamps; drop the old NOT NULL constraint to match.
    op.execute('ALTER TABLE public.kombu_message ALTER COLUMN "timestamp" DROP NOT NULL;')
    op.execute(
        """
        UPDATE public.kombu_message m
        SET queue_id = q.id
        FROM public.kombu_queue q
        WHERE m.queue_id IS NULL
          AND m.queue IS NOT NULL
          AND q.name = m.queue;
        """
    )

    # Align column types with Kombu's model definitions.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'kombu_message'
                  AND column_name = 'timestamp'
                  AND data_type <> 'timestamp without time zone'
            ) THEN
                ALTER TABLE public.kombu_message
                ALTER COLUMN "timestamp" TYPE TIMESTAMP WITHOUT TIME ZONE
                USING to_timestamp("timestamp");
                ALTER TABLE public.kombu_message
                ALTER COLUMN "timestamp" DROP NOT NULL;
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'kombu_message'
                  AND column_name = 'payload'
                  AND data_type <> 'text'
            ) THEN
                ALTER TABLE public.kombu_message
                ALTER COLUMN payload TYPE TEXT
                USING convert_from(payload, 'UTF8');
            END IF;
        END
        $$;
        """
    )

    # Enforce queue_id presence going forward and remove unused legacy queue name column.
    op.execute("ALTER TABLE public.kombu_message ALTER COLUMN queue_id SET NOT NULL;")
    op.execute("ALTER TABLE public.kombu_message DROP COLUMN IF EXISTS queue;")

    # Refresh indexes to match Kombu metadata (timestamp/id composite).
    op.execute("DROP INDEX IF EXISTS public.ix_kombu_message_timestamp;")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_kombu_message_timestamp_id
            ON public.kombu_message ("timestamp", id);
        """
    )


def downgrade() -> None:
    # Restore legacy queue column for backward compatibility.
    op.execute("ALTER TABLE public.kombu_message ADD COLUMN IF NOT EXISTS queue VARCHAR(255);")
    op.execute(
        """
        UPDATE public.kombu_message m
        SET queue = q.name
        FROM public.kombu_queue q
        WHERE m.queue_id IS NOT NULL
          AND q.id = m.queue_id;
        """
    )

    op.execute("ALTER TABLE public.celery_taskmeta ALTER COLUMN date_done SET NOT NULL;")
    op.execute("ALTER TABLE public.celery_tasksetmeta ALTER COLUMN date_done SET NOT NULL;")

    # Remove Kombu-specific alignment changes.
    op.execute("DROP INDEX IF EXISTS public.ix_kombu_message_timestamp_id;")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_kombu_message_timestamp
            ON public.kombu_message ("timestamp");
        """
    )
    op.execute("ALTER TABLE public.kombu_message DROP CONSTRAINT IF EXISTS fk_kombu_message_queue;")
    op.execute("ALTER TABLE public.kombu_message ALTER COLUMN queue_id DROP NOT NULL;")
    op.execute("ALTER TABLE public.kombu_message DROP COLUMN IF EXISTS queue_id;")

    # Best-effort type reversion to prior state.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'kombu_message'
                  AND column_name = 'payload'
                  AND data_type <> 'bytea'
            ) THEN
                ALTER TABLE public.kombu_message
                ALTER COLUMN payload TYPE BYTEA
                USING convert_to(payload, 'UTF8');
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'kombu_message'
                  AND column_name = 'timestamp'
                  AND data_type <> 'double precision'
            ) THEN
                ALTER TABLE public.kombu_message
                ALTER COLUMN "timestamp" TYPE DOUBLE PRECISION;
                ALTER TABLE public.kombu_message
                ALTER COLUMN "timestamp" SET NOT NULL;
            END IF;
        END
        $$;
        """
    )
