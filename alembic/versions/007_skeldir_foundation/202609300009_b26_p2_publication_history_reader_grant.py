"""B2.6-P2 XXI-P1: let runtime readers see family-law activation history.

The confirmation sweep (transition_stale_provisional_to_confirmed) and
the trust verdict readers annotate each verdict with its minting
event-family-law cohort from b26_p2_publication_history. That table
was owner-only, so both paths failed with permission-denied under
production roles (app_user/app_worker/app_ro).

This revision grants SELECT on the publication history to the runtime
reader roles (guarded by role existence, house pattern). It exposes
governance metadata only (law kind/id/version/digest/activation, chain
hashes) -- no tenant rows, amounts, or secrets live in this table.
Downgrade revokes the grants; the sweep exclusion and reader
annotation then fail closed (permission-denied task failure / no
annotation) rather than silently confirming.
"""

from __future__ import annotations

from alembic import op

READER_ROLES = ("app_user", "app_worker", "app_ro", "app_rw")


def _if_role_exists(role: str, statement: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '{role}')
            THEN
                EXECUTE $stmt${statement}$stmt$;
            END IF;
        END
        $$;
        """
    )


revision = "202609300009"
down_revision = "202609300008"


def upgrade() -> None:
    for role in READER_ROLES:
        _if_role_exists(
            role,
            "GRANT SELECT ON TABLE"
            " public.b26_p2_publication_history"
            f" TO {role}",
        )


def downgrade() -> None:
    for role in READER_ROLES:
        _if_role_exists(
            role,
            "REVOKE ALL ON TABLE"
            " public.b26_p2_publication_history"
            f" FROM {role}",
        )
