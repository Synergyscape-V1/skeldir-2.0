from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts/ci/validate_b24_p1_authority_schema.py"
MIGRATION = REPO_ROOT / "alembic/versions/007_skeldir_foundation/202605201200_b24_p1_authority_schema.py"
CORRECTIVE_MIGRATION = REPO_ROOT / "alembic/versions/007_skeldir_foundation/202605201430_b24_p1_corrective_authority_closure.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_b24_p1_authority_schema", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _migration_chain() -> str:
    return "\n\n".join(
        path.read_text(encoding="utf-8") for path in (MIGRATION, CORRECTIVE_MIGRATION)
    )


def test_b24_p1_validator_passes_current_repo() -> None:
    module = _load_validator()
    module.validate_all(REPO_ROOT)


def test_negative_control_missing_tenant_index_fails() -> None:
    module = _load_validator()
    text = _migration_chain()
    mutated = text.replace("idx_bayesian_model_fits_tenant_id", "idx_bayesian_model_fits_tenant_id_removed", 1)
    with pytest.raises(module.ValidationError, match="idx_bayesian_model_fits_tenant_id"):
        module.validate_migration_text(mutated)


def test_negative_control_concurrent_index_in_transaction_fails() -> None:
    module = _load_validator()
    text = _migration_chain()
    mutated = text + "\nop.execute('CREATE INDEX CONCURRENTLY idx_bad ON public.bayesian_artifacts (tenant_id)')\n"
    with pytest.raises(module.ValidationError, match="CREATE INDEX CONCURRENTLY"):
        module.validate_migration_text(mutated)


def test_negative_control_native_enum_fails() -> None:
    module = _load_validator()
    text = _migration_chain()
    mutated = text + "\nop.execute('CREATE TYPE b24_status AS ENUM (''pending'')')\n"
    with pytest.raises(module.ValidationError, match="native PostgreSQL enum"):
        module.validate_migration_text(mutated)


def test_negative_control_missing_hash_constraint_fails() -> None:
    module = _load_validator()
    text = _migration_chain()
    mutated = text.replace(
        "ck_bayesian_artifacts_artifact_hash_sha256",
        "ck_bayesian_artifacts_artifact_hash_removed",
        1,
    )
    with pytest.raises(module.ValidationError, match="ck_bayesian_artifacts_artifact_hash_sha256"):
        module.validate_migration_text(mutated)


def test_negative_control_missing_tenant_bound_artifact_fk_fails() -> None:
    module = _load_validator()
    mutated = _migration_chain().replace(
        "fk_bayesian_artifacts_tenant_fit",
        "fk_bayesian_artifacts_tenant_fit_removed",
        1,
    )
    with pytest.raises(module.ValidationError, match="tenant-bound FK"):
        module.validate_migration_text(mutated)


def test_negative_control_missing_fit_identity_window_fails() -> None:
    module = _load_validator()
    mutated = _migration_chain().replace(
        "source_window_start,\n            source_window_end,\n            source_snapshot_hash",
        "source_snapshot_hash",
        1,
    )
    with pytest.raises(module.ValidationError, match="uq_bayesian_model_fits_tenant_model_window_snapshot"):
        module.validate_migration_text(mutated)


def test_negative_control_bayesian_pii_field_fails() -> None:
    module = _load_validator()
    mutated = _migration_chain().replace(
        "updated_at timestamp with time zone DEFAULT now() NOT NULL,",
        "email character varying(255),\n            updated_at timestamp with time zone DEFAULT now() NOT NULL,",
        1,
    )
    with pytest.raises(module.ValidationError, match="forbidden privacy/identity field"):
        module.validate_migration_text(mutated)


def test_negative_control_identity_bearing_fk_fails() -> None:
    module = _load_validator()
    mutated = (
        _migration_chain()
        + "\nop.execute('ALTER TABLE public.bayesian_artifacts ADD CONSTRAINT fk_bad_identity "
        "FOREIGN KEY (fit_id) REFERENCES public.webhook_ingress_identities(id)')\n"
    )
    with pytest.raises(module.ValidationError, match="identity-bearing table"):
        module.validate_migration_text(mutated)


def test_negative_control_missing_fit_fillfactor_fails() -> None:
    module = _load_validator()
    mutated = _migration_chain().replace(
        "ALTER TABLE public.bayesian_model_fits SET (fillfactor = 90)",
        "ALTER TABLE public.bayesian_model_fits RESET (fillfactor)",
        1,
    )
    with pytest.raises(module.ValidationError, match="fillfactor=90"):
        module.validate_migration_text(mutated)
