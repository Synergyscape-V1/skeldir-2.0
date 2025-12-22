"""Block worker-context mutations to ingestion tables.

Revision ID: 202512171700
Revises: 202512171500
Create Date: 2025-12-17 20:45:00

Migration Description:
- Adds a guard function + triggers that raise when a Celery worker (identified
  via app.execution_context = 'worker') attempts INSERT/UPDATE/DELETE against
  ingestion inputs: attribution_events and dead_events.
- Preserves ingestion/API ability to write by scoping the guard to worker
  execution context only.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202512171700"
down_revision: Union[str, None] = "202512171500"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GUARD_FN = """
CREATE OR REPLACE FUNCTION fn_block_worker_ingestion_mutation() RETURNS trigger AS $$
BEGIN
    IF current_setting('app.execution_context', true) = 'worker' THEN
        RAISE EXCEPTION 'ingestion tables are read-only in worker context (table=%)', TG_TABLE_NAME;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    # Guard function
    op.execute(GUARD_FN)

    # Triggers for ingestion tables (block INSERT/UPDATE/DELETE when worker context is set)
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_block_worker_mutation_events ON attribution_events;
        CREATE TRIGGER trg_block_worker_mutation_events
        BEFORE INSERT OR UPDATE OR DELETE ON attribution_events
        FOR EACH ROW EXECUTE FUNCTION fn_block_worker_ingestion_mutation();
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_block_worker_mutation_dead_events ON dead_events;
        CREATE TRIGGER trg_block_worker_mutation_dead_events
        BEFORE INSERT OR UPDATE OR DELETE ON dead_events
        FOR EACH ROW EXECUTE FUNCTION fn_block_worker_ingestion_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_block_worker_mutation_events ON attribution_events")
    op.execute("DROP TRIGGER IF EXISTS trg_block_worker_mutation_dead_events ON dead_events")
    op.execute("DROP FUNCTION IF EXISTS fn_block_worker_ingestion_mutation")
