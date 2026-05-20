"""B2.4-P1 corrective authority closure.

Revision ID: 202605201430
Revises: 202605201200
Create Date: 2026-05-20 14:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605201430"
down_revision: Union[str, None] = "202605201200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.bayesian_artifacts "
        "DROP CONSTRAINT IF EXISTS bayesian_artifacts_fit_id_fkey"
    )
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "DROP CONSTRAINT IF EXISTS uq_bayesian_model_fits_tenant_source_snapshot_model"
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
        ADD CONSTRAINT uq_bayesian_model_fits_tenant_id_id
        UNIQUE (tenant_id, id)
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
        ADD CONSTRAINT uq_bayesian_model_fits_tenant_model_window_snapshot
        UNIQUE (
            tenant_id,
            model_type,
            model_version,
            source_window_start,
            source_window_end,
            source_snapshot_hash
        )
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT fk_bayesian_artifacts_tenant_fit
        FOREIGN KEY (tenant_id, fit_id)
        REFERENCES public.bayesian_model_fits (tenant_id, id)
        ON DELETE RESTRICT
        """
    )
    op.execute("ALTER TABLE public.bayesian_model_fits SET (fillfactor = 90)")
    op.execute(
        """
        COMMENT ON TABLE public.bayesian_model_fits IS
            'B2.4-P1 tenant-scoped Bayesian fit authority records. Defines persistence only; no statistical runtime, source snapshot computation, diagnostics computation, projection, or public API behavior. Corrective closure sets fillfactor=90 for lifecycle updates and requires a pre-P3/P5 partition decision before fit workers or artifact lifecycle volume.'
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.bayesian_artifacts "
        "DROP CONSTRAINT IF EXISTS fk_bayesian_artifacts_tenant_fit"
    )
    op.execute("ALTER TABLE public.bayesian_model_fits RESET (fillfactor)")
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "DROP CONSTRAINT IF EXISTS uq_bayesian_model_fits_tenant_model_window_snapshot"
    )
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "DROP CONSTRAINT IF EXISTS uq_bayesian_model_fits_tenant_id_id"
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
        ADD CONSTRAINT uq_bayesian_model_fits_tenant_source_snapshot_model
        UNIQUE (tenant_id, model_type, model_version, source_snapshot_hash)
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT bayesian_artifacts_fit_id_fkey
        FOREIGN KEY (fit_id)
        REFERENCES public.bayesian_model_fits (id)
        ON DELETE RESTRICT
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.bayesian_model_fits IS
            'B2.4-P1 tenant-scoped Bayesian fit authority records. Defines persistence only; no statistical runtime, source snapshot computation, diagnostics computation, projection, or public API behavior.'
        """
    )
