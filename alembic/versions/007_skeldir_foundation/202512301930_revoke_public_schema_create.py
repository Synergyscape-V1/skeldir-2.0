"""R4/R6 governance: revoke CREATE on public schema for app_user.

Enforces least-privilege by preventing application/worker roles from
creating tables in the public schema.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202512301930"
down_revision: Union[str, None] = "202512291600"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC;")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                REVOKE CREATE ON SCHEMA public FROM app_user;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("GRANT CREATE ON SCHEMA public TO PUBLIC;")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT CREATE ON SCHEMA public TO app_user;
            END IF;
        END
        $$;
        """
    )
