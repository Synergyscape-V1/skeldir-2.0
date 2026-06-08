"""B2.4-P9 worker tenant hygiene artifact authority closure.

Revision ID: 202606081200
Revises: 202606071200
Create Date: 2026-06-08 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202606081200"
down_revision: Union[str, None] = "202606071200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_ARTIFACT_REF_PATTERN = (
    "^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$"
)
OLD_ARTIFACT_REF_PATTERN = (
    "^b24://artifact/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$"
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.bayesian_artifacts "
        "DROP CONSTRAINT IF EXISTS ck_bayesian_artifacts_internal_uri"
    )  # CI:DESTRUCTIVE_OK - B2.4-P9 replaces artifact-ref authority regex with tenant-bound refs.
    op.execute(
        f"""
        UPDATE public.bayesian_artifacts
        SET artifact_ref = 'b24://artifact/' || tenant_id::text || '/' ||
                substring(artifact_ref FROM '^{OLD_ARTIFACT_REF_PATTERN[1:-1]}$'),
            artifact_uri_internal = 'b24://artifact/' || tenant_id::text || '/' ||
                substring(artifact_ref FROM '^{OLD_ARTIFACT_REF_PATTERN[1:-1]}$'),
            updated_at = now()
        WHERE artifact_ref ~ '{OLD_ARTIFACT_REF_PATTERN}'
        """
    )
    op.execute(
        f"""
        UPDATE public.bayesian_model_fits
        SET artifact_ref = 'b24://artifact/' || tenant_id::text || '/' ||
                substring(artifact_ref FROM '^{OLD_ARTIFACT_REF_PATTERN[1:-1]}$'),
            updated_at = now()
        WHERE artifact_ref ~ '{OLD_ARTIFACT_REF_PATTERN}'
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_internal_uri
            CHECK (
                lifecycle_status IN ('pruned', 'rejected')
                OR (
                    artifact_uri_internal = artifact_ref
                    AND artifact_uri_internal ~ '{NEW_ARTIFACT_REF_PATTERN}'
                )
            )
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.bayesian_artifacts "
        "DROP CONSTRAINT IF EXISTS ck_bayesian_artifacts_internal_uri"
    )  # CI:DESTRUCTIVE_OK - rollback restores the B2.4-P8 artifact-ref regex.
    op.execute(
        f"""
        UPDATE public.bayesian_artifacts
        SET artifact_ref = 'b24://artifact/' ||
                substring(artifact_ref FROM '^b24://artifact/[a-f0-9-]{{36}}/(.*)$'),
            artifact_uri_internal = 'b24://artifact/' ||
                substring(artifact_uri_internal FROM '^b24://artifact/[a-f0-9-]{{36}}/(.*)$'),
            updated_at = now()
        WHERE artifact_ref ~ '{NEW_ARTIFACT_REF_PATTERN}'
        """
    )
    op.execute(
        f"""
        UPDATE public.bayesian_model_fits
        SET artifact_ref = 'b24://artifact/' ||
                substring(artifact_ref FROM '^b24://artifact/[a-f0-9-]{{36}}/(.*)$'),
            updated_at = now()
        WHERE artifact_ref ~ '{NEW_ARTIFACT_REF_PATTERN}'
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_internal_uri
            CHECK (
                lifecycle_status IN ('pruned', 'rejected')
                OR (
                    artifact_uri_internal = artifact_ref
                    AND artifact_uri_internal ~ '{OLD_ARTIFACT_REF_PATTERN}'
                )
            )
        """
    )
