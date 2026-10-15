"""B2.6-P2 F5: let the authentication trust root verify construction.

ADD2-VF5 proved the auth root's construction-authority guard inoperative
under production roles: app_ingress holds no EXECUTE on
skeldir_database_construction_revisions(), so the guard's revision read
fails with permission-denied, the bare except-Exception branch logs
'deferred' and the root serves without ever verifying schema.

This revision grants that single EXECUTE to app_ingress (guarded by
role existence, house pattern). It changes no behavior by itself: the
guard code that turns verification into refusal/observability ships
with the application tree. With the grant, the guard can verify; the
server change makes unverifiable operation fatal and observable
instead of silently served (readiness endpoint + per-request check).

Downgrade revokes the grant; the guard then fails closed (fatal) on
lanes running the new code, exactly as F5 requires.
"""

from __future__ import annotations

from alembic import op


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


revision = "202609300008"
down_revision = "202609300007"


def upgrade() -> None:
    _if_role_exists(
        "app_ingress",
        "GRANT EXECUTE ON FUNCTION"
        " public.skeldir_database_construction_revisions()"
        " TO app_ingress",
    )


def downgrade() -> None:
    _if_role_exists(
        "app_ingress",
        "REVOKE ALL ON FUNCTION"
        " public.skeldir_database_construction_revisions()"
        " FROM app_ingress",
    )
