"""B2.4-P8 follow-up payload airgap and atomic quota closure.

Revision ID: 202606071200
Revises: 202606061200
Create Date: 2026-06-07 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202606071200"
down_revision: Union[str, None] = "202606061200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.bayesian_artifact_storage_quotas "
        "ADD COLUMN IF NOT EXISTS max_artifact_count integer DEFAULT 1000 NOT NULL"
    )
    op.execute(
        "ALTER TABLE public.bayesian_artifact_storage_quotas "
        "DROP CONSTRAINT IF EXISTS "  # CI:DESTRUCTIVE_OK - idempotent B2.4-P8-FCA constraint replacement; see docs/forensics/B2.4-P8 Remediation Evidence Pack .md.
        "ck_bayesian_artifact_storage_quotas_max_count_positive"
    )
    op.execute(
        "ALTER TABLE public.bayesian_artifact_storage_quotas "
        "DROP CONSTRAINT IF EXISTS "  # CI:DESTRUCTIVE_OK - idempotent B2.4-P8-FCA constraint replacement; see docs/forensics/B2.4-P8 Remediation Evidence Pack .md.
        "ck_bayesian_artifact_storage_quotas_active_count_within_quota"
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifact_storage_quotas
        ADD CONSTRAINT ck_bayesian_artifact_storage_quotas_max_count_positive
            CHECK (max_artifact_count > 0)
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifact_storage_quotas
        ADD CONSTRAINT ck_bayesian_artifact_storage_quotas_active_count_within_quota
            CHECK (active_artifact_count <= max_artifact_count)
        """
    )

    for constraint in (
        "ck_bayesian_artifacts_internal_uri",
        "ck_bayesian_artifacts_lifecycle_status",
        "ck_bayesian_artifacts_lifecycle_payload_state",
    ):
        op.execute(
            f"ALTER TABLE public.bayesian_artifacts "
            f"DROP CONSTRAINT IF EXISTS {constraint}"  # CI:DESTRUCTIVE_OK - idempotent B2.4-P8-FCA lifecycle constraint replacement; see docs/forensics/B2.4-P8 Remediation Evidence Pack .md.
        )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_internal_uri
            CHECK (
                lifecycle_status IN ('pruned', 'rejected')
                OR (
                    artifact_uri_internal = artifact_ref
                    AND artifact_uri_internal ~ '^b24://artifact/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'
                )
            )
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_lifecycle_status
            CHECK (lifecycle_status IN ('active', 'pruned', 'rejected'))
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state
            CHECK (
                (
                    lifecycle_status = 'active'
                    AND payload_bytes IS NOT NULL
                    AND payload_byte_count = artifact_size_bytes
                    AND pruned_at IS NULL
                )
                OR (
                    lifecycle_status = 'pruned'
                    AND payload_bytes IS NULL
                    AND payload_byte_count = 0
                    AND pruned_at IS NOT NULL
                )
                OR (
                    lifecycle_status = 'rejected'
                    AND payload_bytes IS NULL
                    AND payload_byte_count = 0
                    AND pruned_at IS NULL
                )
            )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE public.bayesian_artifacts
        SET lifecycle_status = 'pruned',
            expires_at = COALESCE(expires_at, now()),
            pruned_at = COALESCE(pruned_at, now()),
            pruned_reason = COALESCE(pruned_reason, 'manual_governance'),
            payload_json = NULL,
            payload_bytes = NULL,
            payload_byte_count = 0,
            updated_at = now()
        WHERE lifecycle_status = 'rejected'
        """
    )  # CI:DESTRUCTIVE_OK - downgrade normalizes rejected tombstones to the prior pruned lifecycle.
    for constraint in (
        "ck_bayesian_artifacts_internal_uri",
        "ck_bayesian_artifacts_lifecycle_status",
        "ck_bayesian_artifacts_lifecycle_payload_state",
    ):
        op.execute(
            f"ALTER TABLE public.bayesian_artifacts "
            f"DROP CONSTRAINT IF EXISTS {constraint}"  # CI:DESTRUCTIVE_OK - rollback B2.4-P8-FCA lifecycle constraint replacement; see docs/forensics/B2.4-P8 Remediation Evidence Pack .md.
        )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_internal_uri
            CHECK (
                lifecycle_status = 'pruned'
                OR (
                    artifact_uri_internal = artifact_ref
                    AND artifact_uri_internal ~ '^b24://artifact/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'
                )
            )
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_lifecycle_status
            CHECK (lifecycle_status IN ('active', 'pruned'))
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state
            CHECK (
                (
                    lifecycle_status = 'active'
                    AND payload_bytes IS NOT NULL
                    AND payload_byte_count = artifact_size_bytes
                    AND pruned_at IS NULL
                )
                OR (
                    lifecycle_status = 'pruned'
                    AND payload_bytes IS NULL
                    AND payload_byte_count = 0
                    AND pruned_at IS NOT NULL
                )
            )
        """
    )
    op.execute(
        "ALTER TABLE public.bayesian_artifact_storage_quotas "
        "DROP CONSTRAINT IF EXISTS "  # CI:DESTRUCTIVE_OK - rollback B2.4-P8-FCA quota count guard; see docs/forensics/B2.4-P8 Remediation Evidence Pack .md.
        "ck_bayesian_artifact_storage_quotas_active_count_within_quota"
    )
    op.execute(
        "ALTER TABLE public.bayesian_artifact_storage_quotas "
        "DROP CONSTRAINT IF EXISTS "  # CI:DESTRUCTIVE_OK - rollback B2.4-P8-FCA quota count guard; see docs/forensics/B2.4-P8 Remediation Evidence Pack .md.
        "ck_bayesian_artifact_storage_quotas_max_count_positive"
    )
    op.execute(
        "ALTER TABLE public.bayesian_artifact_storage_quotas "
        "DROP COLUMN IF EXISTS max_artifact_count"  # CI:DESTRUCTIVE_OK - rollback additive B2.4-P8-FCA quota count column; see docs/forensics/B2.4-P8 Remediation Evidence Pack .md.
    )
