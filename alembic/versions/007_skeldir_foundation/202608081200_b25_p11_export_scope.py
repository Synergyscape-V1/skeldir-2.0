"""B2.5-P11 bounded machine export scope.

Revision ID: 202608081200
Revises: 202607191200
Create Date: 2026-08-08 12:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "202608081200"
down_revision = "202607191200"
branch_labels = None
depends_on = None


_RESERVED_SCOPE_EXCLUSION = """
    AND scope_value NOT IN (
        'trust.action.propose',
        'trust.action.execute',
        'trust.action.approve',
        'trust.action.reject',
        'auto_executable_within_policy'
    )
"""


def _replace_scope_constraint(*, include_export_scope: bool) -> None:
    permitted = [
        "'trust.envelope.read'",
        "'trust.envelope.verify'",
        "'trust.audit.read'",
        "'trust.keys.read'",
    ]
    if include_export_scope:
        permitted.append("'trust.export.create_limited'")
    values = ",\n                    ".join(permitted)
    op.execute(
        "ALTER TABLE public.agent_scope_grants "
        "DROP CONSTRAINT ck_agent_scope_grants_scope_value"
    )
    op.execute(
        f"""
        ALTER TABLE public.agent_scope_grants
        ADD CONSTRAINT ck_agent_scope_grants_scope_value CHECK (
            scope_value IN (
                {values}
            )
            {_RESERVED_SCOPE_EXCLUSION}
        )
        """
    )


def upgrade() -> None:
    _replace_scope_constraint(include_export_scope=True)


def downgrade() -> None:
    _replace_scope_constraint(include_export_scope=False)
