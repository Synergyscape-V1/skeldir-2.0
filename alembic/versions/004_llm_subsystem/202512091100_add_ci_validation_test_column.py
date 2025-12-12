"""Add CI validation test column

Revision ID: 202512091100
Revises: 202512081510
Create Date: 2025-12-09 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '202512091100'
down_revision = '202512081510'  # Points to last migration in 004_llm_subsystem
branch_labels = None
depends_on = None


def upgrade():
    # EMPIRICAL VALIDATION TEST: Add harmless test column to llm_inference_cache
    # This migration serves to validate:
    # 1. GitHub Actions automatically triggers on schema changes
    # 2. Migration deploys to Neon production
    # 3. CI audit logs capture the deployment
    
    op.add_column(
        'llm_inference_cache',
        sa.Column(
            'ci_validation_test',
            sa.Boolean(),
            nullable=True,
            server_default=sa.false(),
            comment='Test column to validate CI-exclusive schema deployment'
        )
    )


def downgrade():
    # Remove test column
    op.drop_column('llm_inference_cache', 'ci_validation_test')
