from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts/ci/validate_b24_p1_authority_schema.py"
MIGRATION = REPO_ROOT / "alembic/versions/007_skeldir_foundation/202605201200_b24_p1_authority_schema.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_b24_p1_authority_schema", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_b24_p1_validator_passes_current_repo() -> None:
    module = _load_validator()
    module.validate_all(REPO_ROOT)


def test_negative_control_missing_tenant_index_fails() -> None:
    module = _load_validator()
    text = MIGRATION.read_text(encoding="utf-8")
    mutated = text.replace("idx_bayesian_model_fits_tenant_id", "idx_bayesian_model_fits_tenant_id_removed", 1)
    with pytest.raises(module.ValidationError, match="idx_bayesian_model_fits_tenant_id"):
        module.validate_migration_text(mutated)


def test_negative_control_concurrent_index_in_transaction_fails() -> None:
    module = _load_validator()
    text = MIGRATION.read_text(encoding="utf-8")
    mutated = text + "\nop.execute('CREATE INDEX CONCURRENTLY idx_bad ON public.bayesian_artifacts (tenant_id)')\n"
    with pytest.raises(module.ValidationError, match="CREATE INDEX CONCURRENTLY"):
        module.validate_migration_text(mutated)


def test_negative_control_native_enum_fails() -> None:
    module = _load_validator()
    text = MIGRATION.read_text(encoding="utf-8")
    mutated = text + "\nop.execute('CREATE TYPE b24_status AS ENUM (''pending'')')\n"
    with pytest.raises(module.ValidationError, match="native PostgreSQL enum"):
        module.validate_migration_text(mutated)


def test_negative_control_missing_hash_constraint_fails() -> None:
    module = _load_validator()
    text = MIGRATION.read_text(encoding="utf-8")
    mutated = text.replace(
        "ck_bayesian_artifacts_artifact_hash_sha256",
        "ck_bayesian_artifacts_artifact_hash_removed",
        1,
    )
    with pytest.raises(module.ValidationError, match="ck_bayesian_artifacts_artifact_hash_sha256"):
        module.validate_migration_text(mutated)
