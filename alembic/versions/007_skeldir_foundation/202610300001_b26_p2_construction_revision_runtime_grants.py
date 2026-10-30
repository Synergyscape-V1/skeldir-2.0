"""Grant the construction-revision reader to publisher runtime roles.

C19 runs the real Bayesian publisher process under
``app_dispatch_publisher``. That process must verify the live schema
revision before it publishes; the function is read-only and SECURITY
DEFINER, so the grant adds no table authority. The earlier grants covered
the API, worker, read-only and ingress roles but omitted the publisher
roles, which made the guard fail with permission denied instead of
performing its verification.

Revision ID: 202610300001
Revises: 202610280001
"""

from __future__ import annotations

from alembic import op


revision = "202610300001"
down_revision = "202610280001"
branch_labels = None
depends_on = None


_PUBLISHER_ROLES = (
    "app_dispatch_publisher",
    "app_worker_bayesian_publisher",
)


def _grant_if_present(role: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
            GRANT EXECUTE ON FUNCTION
              public.skeldir_database_construction_revisions()
              TO {role};
          END IF;
        END $$;
        """
    )


def upgrade() -> None:
    for role in _PUBLISHER_ROLES:
        _grant_if_present(role)


def downgrade() -> None:
    for role in _PUBLISHER_ROLES:
        op.execute(
            f"""
            DO $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                REVOKE ALL ON FUNCTION
                  public.skeldir_database_construction_revisions()
                  FROM {role};
              END IF;
            END $$;
            """
        )
