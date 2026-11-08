"""Remove the temporary account ownership-transfer chain.

Revision ID: 202611080001
Revises: 202611070001
Create Date: 2026-11-08 00:01:00

Revision 202611070001 needed a temporary migration-owner membership chain to
transfer the two SECURITY DEFINER account functions to their intended NOLOGIN
owners.  That transfer is a one-time construction step.  This revision removes
the chain so the migrated runtime/migration authority graph no longer contains
``migration_owner -> app_account_provisioner -> app_auth_lookup`` or a direct
temporary migration-owner membership in the lookup owner.

The function owners and account-only privileges are deliberately unchanged.
"""

from __future__ import annotations

from alembic import op


revision = "202611080001"
down_revision = "202611070001"
branch_labels = None
depends_on = None


def _revoke_if_present(role: str, member: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                  FROM pg_auth_members m
                  JOIN pg_roles r ON r.oid = m.roleid
                  JOIN pg_roles u ON u.oid = m.member
                 WHERE r.rolname = '{role}'
                   AND u.rolname = '{member}'
            ) THEN
                EXECUTE 'REVOKE {role} FROM {member}';
            END IF;
        END $$;
        """
    )


def _grant_if_both_present(role: str, member: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}')
               AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{member}')
               AND NOT EXISTS (
                   SELECT 1
                     FROM pg_auth_members m
                     JOIN pg_roles r ON r.oid = m.roleid
                     JOIN pg_roles u ON u.oid = m.member
                    WHERE r.rolname = '{role}'
                      AND u.rolname = '{member}'
               )
            THEN
                EXECUTE 'GRANT {role} TO {member} WITH ADMIN OPTION';
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    from sqlalchemy import text

    actor = str(op.get_bind().execute(text("SELECT current_user")).scalar())

    # PostgreSQL 16 only lets the grantor (or a superuser) revoke a
    # membership.  Preparation grants the lookup -> provisioner edge with the
    # migration principal as grantor, so this edge is removable here.  The
    # principal's own two memberships are attempted directly: PostgreSQL 15
    # removes them, while PostgreSQL 16 leaves memberships granted by another
    # role in place without making the cleanup fail.
    _revoke_if_present("app_auth_lookup", "app_account_provisioner")
    _revoke_if_present("app_account_provisioner", actor)
    _revoke_if_present("app_auth_lookup", actor)


def downgrade() -> None:
    # Restore exactly the two temporary edges that revision 202611070001
    # relied on for its initial ownership transfer.  Direct migration-owner
    # membership in the lookup owner was already revoked at the predecessor
    # head and is not recreated here.
    _grant_if_both_present("app_auth_lookup", "app_account_provisioner")
    _grant_if_both_present("app_account_provisioner", "migration_owner")
