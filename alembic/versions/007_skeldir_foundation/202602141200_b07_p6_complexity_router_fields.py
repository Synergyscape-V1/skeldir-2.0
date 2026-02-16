"""B0.7-P6 complexity router ledger fields.

Revision ID: 202602141200
Revises: 202602121210
Create Date: 2026-02-14 12:00:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "202602141200"
down_revision: Union[str, None] = "202602121210"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE llm_api_calls ADD COLUMN complexity_score DOUBLE PRECISION NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE llm_api_calls ADD COLUMN complexity_bucket INTEGER NOT NULL DEFAULT 1"
    )
    op.execute(
        "ALTER TABLE llm_api_calls ADD COLUMN chosen_tier TEXT NOT NULL DEFAULT 'cheap'"
    )
    op.execute(
        "ALTER TABLE llm_api_calls ADD COLUMN chosen_provider TEXT NOT NULL DEFAULT 'openai'"
    )
    op.execute(
        "ALTER TABLE llm_api_calls ADD COLUMN chosen_model TEXT NOT NULL DEFAULT 'gpt-4o-mini'"
    )
    op.execute(
        "ALTER TABLE llm_api_calls ADD COLUMN policy_id TEXT NOT NULL DEFAULT 'unknown'"
    )
    op.execute(
        "ALTER TABLE llm_api_calls ADD COLUMN policy_version TEXT NOT NULL DEFAULT 'unknown'"
    )
    op.execute(
        "ALTER TABLE llm_api_calls ADD COLUMN routing_reason TEXT NOT NULL DEFAULT 'bucket_policy'"
    )

    op.execute(
        """
        ALTER TABLE llm_api_calls
        ADD CONSTRAINT ck_llm_api_calls_complexity_score_range
        CHECK (complexity_score >= 0 AND complexity_score <= 1)
        """
    )
    op.execute(
        """
        ALTER TABLE llm_api_calls
        ADD CONSTRAINT ck_llm_api_calls_complexity_bucket_range
        CHECK (complexity_bucket >= 1 AND complexity_bucket <= 10)
        """
    )
    op.execute(
        """
        ALTER TABLE llm_api_calls
        ADD CONSTRAINT ck_llm_api_calls_chosen_tier_valid
        CHECK (chosen_tier IN ('cheap', 'standard', 'premium'))
        """
    )


def downgrade() -> None:
<<<<<<< HEAD
    op.execute(
        "ALTER TABLE llm_api_calls DROP CONSTRAINT IF EXISTS ck_llm_api_calls_chosen_tier_valid"
    )
    op.execute(
        "ALTER TABLE llm_api_calls DROP CONSTRAINT IF EXISTS ck_llm_api_calls_complexity_bucket_range"
    )
    op.execute(
        "ALTER TABLE llm_api_calls DROP CONSTRAINT IF EXISTS ck_llm_api_calls_complexity_score_range"
    )

    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS routing_reason")
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS policy_version")
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS policy_id")
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS chosen_model")
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS chosen_provider")
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS chosen_tier")
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS complexity_bucket")
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS complexity_score")
=======
    op.execute("ALTER TABLE llm_api_calls DROP CONSTRAINT IF EXISTS ck_llm_api_calls_chosen_tier_valid")  # CI:DESTRUCTIVE_OK - Downgrade rollback for additive Phase 6 constraints.
    op.execute("ALTER TABLE llm_api_calls DROP CONSTRAINT IF EXISTS ck_llm_api_calls_complexity_bucket_range")  # CI:DESTRUCTIVE_OK - Downgrade rollback for additive Phase 6 constraints.
    op.execute("ALTER TABLE llm_api_calls DROP CONSTRAINT IF EXISTS ck_llm_api_calls_complexity_score_range")  # CI:DESTRUCTIVE_OK - Downgrade rollback for additive Phase 6 constraints.

    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS routing_reason")  # CI:DESTRUCTIVE_OK - Downgrade rollback for additive Phase 6 columns.
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS policy_version")  # CI:DESTRUCTIVE_OK - Downgrade rollback for additive Phase 6 columns.
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS policy_id")  # CI:DESTRUCTIVE_OK - Downgrade rollback for additive Phase 6 columns.
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS chosen_model")  # CI:DESTRUCTIVE_OK - Downgrade rollback for additive Phase 6 columns.
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS chosen_provider")  # CI:DESTRUCTIVE_OK - Downgrade rollback for additive Phase 6 columns.
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS chosen_tier")  # CI:DESTRUCTIVE_OK - Downgrade rollback for additive Phase 6 columns.
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS complexity_bucket")  # CI:DESTRUCTIVE_OK - Downgrade rollback for additive Phase 6 columns.
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS complexity_score")  # CI:DESTRUCTIVE_OK - Downgrade rollback for additive Phase 6 columns.
>>>>>>> 2df083e09a5bb0ba4d3888d774dd055b2cb42bd4
