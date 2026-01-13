"""Add llm_api_calls idempotency key

Revision ID: 202601131610
Revises: 202601031930
Create Date: 2026-01-13 16:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "202601131610"
down_revision = "202601031930"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "llm_api_calls",
        sa.Column(
            "request_id",
            sa.Text(),
            nullable=False,
            server_default=sa.text("md5(random()::text || clock_timestamp()::text)"),
        ),
    )

    op.execute(
        """
        UPDATE llm_api_calls
        SET request_id = COALESCE(
            NULLIF(request_metadata->>'request_id', ''),
            request_id
        )
        """
    )

    op.alter_column("llm_api_calls", "request_id", server_default=None)

    op.create_unique_constraint(
        "uq_llm_api_calls_tenant_request_endpoint",
        "llm_api_calls",
        ["tenant_id", "request_id", "endpoint"],
    )


def downgrade():
    op.drop_constraint(
        "uq_llm_api_calls_tenant_request_endpoint",
        "llm_api_calls",
        type_="unique",
    )
    op.drop_column("llm_api_calls", "request_id")  # CI:DESTRUCTIVE_OK - Downgrade rollback
