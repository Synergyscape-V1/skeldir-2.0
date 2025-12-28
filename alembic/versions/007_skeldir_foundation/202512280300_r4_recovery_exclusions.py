"""R4-FIX: Add broker recovery exclusion table.

Kombu SQLAlchemy transport marks messages invisible on delivery and does not
remove them deterministically on ack in a way the harness can rely on.
The worker-side visibility recovery sweep therefore re-queues old invisible
messages to simulate redelivery after worker loss.

To prevent infinite redelivery loops once a crash probe has successfully
redelivered, the crash task writes a completion marker keyed by (scenario, task_id).
The recovery sweep excludes any task_id present in this table.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202512280300"
down_revision: Union[str, None] = "202512280200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS r4_recovery_exclusions (
            scenario text NOT NULL,
            task_id text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (scenario, task_id)
        );

        GRANT SELECT, INSERT, DELETE ON TABLE public.r4_recovery_exclusions TO app_user;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.r4_recovery_exclusions;")

