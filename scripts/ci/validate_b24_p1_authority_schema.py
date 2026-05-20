#!/usr/bin/env python3
"""Validate B2.4-P1 Bayesian authority schema implementation."""

from __future__ import annotations

import argparse
import ast
import re
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = Path(
    "alembic/versions/007_skeldir_foundation/202605201200_b24_p1_authority_schema.py"
)
CANONICAL_SCHEMA_PATH = Path("db/schema/canonical_schema.sql")
CANONICAL_YAML_PATH = Path("db/schema/canonical_schema.yaml")
BAYESIAN_PACKAGE = Path("backend/app/bayesian")
MODEL_INIT_PATH = Path("backend/app/models/__init__.py")

REQUIRED_MODULES = {
    "__init__.py",
    "enums.py",
    "exceptions.py",
    "models.py",
    "repository.py",
    "artifact_repository.py",
    "schema.py",
}

REQUIRED_FIT_COLUMNS = {
    "id",
    "tenant_id",
    "model_type",
    "model_version",
    "source_window_start",
    "source_window_end",
    "source_snapshot_hash",
    "status",
    "eligibility_status",
    "data_completeness_status",
    "fallback_applied",
    "fallback_reason",
    "sampling_started_at",
    "last_eligibility_check_at",
    "last_fit_at",
    "completed_at",
    "runtime_seconds",
    "max_runtime_seconds",
    "max_samples",
    "max_cores",
    "n_chains",
    "n_samples_actual",
    "r_hat_max",
    "ess_min",
    "divergence_count",
    "credible_interval_status",
    "confidence_bucket",
    "confidence_bucket_reason",
    "confidence_policy_version",
    "artifact_ref",
    "artifact_hash",
    "created_at",
    "updated_at",
}

REQUIRED_ARTIFACT_COLUMNS = {
    "id",
    "tenant_id",
    "fit_id",
    "artifact_ref",
    "artifact_hash",
    "artifact_type",
    "storage_backend",
    "artifact_uri_internal",
    "artifact_size_bytes",
    "compression",
    "retention_class",
    "expires_at",
    "pruned_at",
    "created_at",
}

REQUIRED_INDEXES = {
    "idx_bayesian_model_fits_tenant_id",
    "idx_bayesian_artifacts_tenant_id",
    "idx_bayesian_model_fits_tenant_model_window",
    "idx_bayesian_model_fits_tenant_source_snapshot_hash",
    "idx_bayesian_model_fits_tenant_status",
    "idx_bayesian_artifacts_tenant_fit",
    "idx_bayesian_artifacts_tenant_artifact_ref",
    "idx_bayesian_artifacts_tenant_artifact_hash",
    "idx_bayesian_model_fits_tenant_model_eligibility",
    "idx_bayesian_model_fits_tenant_model_fallback",
    "idx_bayesian_model_fits_tenant_model_window_latest",
}

REQUIRED_CONSTRAINTS = {
    "ck_bayesian_model_fits_source_snapshot_hash_sha256",
    "ck_bayesian_model_fits_artifact_hash_sha256",
    "ck_bayesian_artifacts_artifact_hash_sha256",
    "ck_bayesian_model_fits_status",
    "ck_bayesian_model_fits_eligibility_status",
    "ck_bayesian_model_fits_data_completeness_status",
    "ck_bayesian_model_fits_fallback_reason",
    "ck_bayesian_model_fits_credible_interval_status",
    "ck_bayesian_model_fits_confidence_bucket",
    "ck_bayesian_artifacts_artifact_type",
    "ck_bayesian_artifacts_storage_backend",
    "ck_bayesian_artifacts_size_non_negative",
    "ck_bayesian_model_fits_source_window_order",
    "ck_bayesian_model_fits_r_hat_max_positive",
    "ck_bayesian_model_fits_ess_min_non_negative",
}

FORBIDDEN_IMPORT_ROOTS = {
    "app.llm",
    "backend.app.llm",
    "openai",
    "anthropic",
    "aisuite",
    "pymc",
    "pytensor",
    "arviz",
    "pymc_marketing",
}


class ValidationError(RuntimeError):
    pass


def _read(root: Path, path: Path) -> str:
    full = root / path
    if not full.exists():
        raise ValidationError(f"missing required file: {path.as_posix()}")
    return full.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _table_window(text: str, table: str) -> str:
    match = re.search(rf"CREATE TABLE public\.{re.escape(table)} \((.*?)\n\s*\)", text, re.S)
    return match.group(1) if match else ""


def _column_present(table_sql: str, column: str) -> bool:
    return re.search(rf"(?m)^\s*{re.escape(column)}\s+", table_sql) is not None


def _contains_forbidden_import(module: str) -> bool:
    return any(module == root or module.startswith(f"{root}.") for root in FORBIDDEN_IMPORT_ROOTS)


def validate_module_surface(root: Path) -> None:
    package = root / BAYESIAN_PACKAGE
    _require(package.exists(), "backend/app/bayesian package is missing")
    observed = {path.name for path in package.glob("*.py")}
    missing = sorted(REQUIRED_MODULES - observed)
    _require(not missing, f"backend/app/bayesian missing modules: {missing}")

    for path in sorted(package.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(root).as_posix()
        _require("APIRouter" not in text, f"public router symbol forbidden in {rel}")
        _require("include_router" not in text, f"router registration forbidden in {rel}")
        tree = ast.parse(text, filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            else:
                continue
            for module in modules:
                _require(not _contains_forbidden_import(module), f"forbidden import in {rel}: {module}")

    app_model_init = _read(root, MODEL_INIT_PATH)
    _require("BayesianModelFit" in app_model_init, "ORM metadata package missing BayesianModelFit export")
    _require("BayesianArtifact" in app_model_init, "ORM metadata package missing BayesianArtifact export")


def validate_migration_text(text: str) -> None:
    _require("CREATE TABLE public.bayesian_model_fits" in text, "migration missing bayesian_model_fits table")
    _require("CREATE TABLE public.bayesian_artifacts" in text, "migration missing bayesian_artifacts table")
    _require("CREATE TYPE" not in text.upper(), "native PostgreSQL enum DDL is forbidden for B2.4 P1 states")
    _require("CREATE INDEX CONCURRENTLY" not in text.upper(), "CREATE INDEX CONCURRENTLY forbidden in transactional migration")
    _require("postgresql_concurrently=True" not in text, "postgresql_concurrently=True forbidden in transactional migration")

    fit_sql = _table_window(text, "bayesian_model_fits")
    artifact_sql = _table_window(text, "bayesian_artifacts")
    _require(fit_sql, "could not parse bayesian_model_fits table body")
    _require(artifact_sql, "could not parse bayesian_artifacts table body")

    missing_fit = sorted(column for column in REQUIRED_FIT_COLUMNS if not _column_present(fit_sql, column))
    missing_artifact = sorted(column for column in REQUIRED_ARTIFACT_COLUMNS if not _column_present(artifact_sql, column))
    _require(not missing_fit, f"bayesian_model_fits missing columns: {missing_fit}")
    _require(not missing_artifact, f"bayesian_artifacts missing columns: {missing_artifact}")

    _require("source_snapshot_hash character varying(64) NOT NULL" in text, "source_snapshot_hash must be VARCHAR(64) NOT NULL")
    _require("artifact_hash character varying(64)" in text, "artifact_hash must be VARCHAR(64)")
    _require("'^[a-f0-9]{64}$'" in text, "SHA-256 lowercase hex regex check missing")
    _require("fallback_applied = true" in text, "fallback partial index predicate missing")
    _require("last_eligibility_check_at DESC" in text, "eligibility recency index missing DESC timestamp")
    _require("ON DELETE RESTRICT" in text, "artifact fit FK must avoid cascade-delete by default")

    for index in REQUIRED_INDEXES:
        _require(
            re.search(rf"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+{re.escape(index)}\b", text, re.I) is not None,
            f"migration missing required index: {index}",
        )
    for constraint in REQUIRED_CONSTRAINTS:
        _require(constraint in text, f"migration missing required constraint: {constraint}")

    for table in ("bayesian_model_fits", "bayesian_artifacts"):
        _require(
            f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in text
            or 'ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY' in text,
            f"{table} missing ENABLE RLS",
        )
        _require(
            f"ALTER TABLE ONLY public.{table} FORCE ROW LEVEL SECURITY" in text
            or 'ALTER TABLE ONLY public.{table_name} FORCE ROW LEVEL SECURITY' in text,
            f"{table} missing FORCE RLS",
        )
        _require("current_setting('app.current_tenant_id', true)::uuid" in text, f"{table} policy missing tenant GUC")


def validate_canonical_schema(root: Path) -> None:
    canonical = _read(root, CANONICAL_SCHEMA_PATH)
    yaml_text = _read(root, CANONICAL_YAML_PATH)
    for table in ("bayesian_model_fits", "bayesian_artifacts"):
        _require(f"CREATE TABLE public.{table}" in canonical, f"canonical schema missing table: {table}")
        _require(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in canonical, f"canonical schema missing RLS: {table}")
        _require(table in yaml_text, f"canonical schema YAML missing table: {table}")
    for index in REQUIRED_INDEXES:
        _require(index in canonical, f"canonical schema missing index: {index}")
    for constraint in REQUIRED_CONSTRAINTS:
        _require(constraint in canonical, f"canonical schema missing constraint: {constraint}")


def validate_models(root: Path) -> None:
    models_text = _read(root, BAYESIAN_PACKAGE / "models.py")
    for token in (
        '__tablename__ = "bayesian_model_fits"',
        '__tablename__ = "bayesian_artifacts"',
        "PGUUID(as_uuid=True)",
        "server_default=func.gen_random_uuid()",
        "CheckConstraint",
        "postgresql_where=text(\"fallback_applied = true\")",
    ):
        _require(token in models_text, f"Bayesian ORM model missing token: {token}")


def validate_all(root: Path) -> None:
    validate_module_surface(root)
    validate_migration_text(_read(root, MIGRATION_PATH))
    validate_canonical_schema(root)
    validate_models(root)


def run_negative_controls(root: Path) -> None:
    migration = _read(root, MIGRATION_PATH)
    for label, mutated, expected in (
        (
            "B24_P1_NC_REMOVE_FIT_TABLE_PASS",
            migration.replace("CREATE TABLE public.bayesian_model_fits", "CREATE TABLE public.bayesian_model_fits_removed", 1),
            "bayesian_model_fits",
        ),
        (
            "B24_P1_NC_REMOVE_HASH_CHECK_PASS",
            migration.replace("ck_bayesian_model_fits_source_snapshot_hash_sha256", "ck_bayesian_model_fits_source_snapshot_hash_removed", 1),
            "ck_bayesian_model_fits_source_snapshot_hash_sha256",
        ),
        (
            "B24_P1_NC_CONCURRENT_INDEX_PASS",
            migration + "\n# regression\nop.execute('CREATE INDEX CONCURRENTLY idx_bad ON public.bayesian_model_fits (tenant_id)')\n",
            "CREATE INDEX CONCURRENTLY",
        ),
        (
            "B24_P1_NC_NATIVE_ENUM_PASS",
            migration + "\n# regression\nop.execute('CREATE TYPE b24_bad AS ENUM (''x'')')\n",
            "native PostgreSQL enum",
        ),
    ):
        try:
            validate_migration_text(mutated)
        except ValidationError as exc:
            _require(expected in str(exc), f"{label} failed for unexpected reason: {exc}")
            print(f"{label}: {exc}")
        else:
            raise ValidationError(f"{label} did not fail")

    with tempfile.TemporaryDirectory(prefix="b24_p1_bad_import_") as tmp:
        tmp_root = Path(tmp)
        package = tmp_root / BAYESIAN_PACKAGE
        package.mkdir(parents=True)
        for module in REQUIRED_MODULES:
            (package / module).write_text("", encoding="utf-8")
        (package / "models.py").write_text("from app.llm.provider_boundary import SkeldirLLMProvider\n", encoding="utf-8")
        app_models = tmp_root / MODEL_INIT_PATH
        app_models.parent.mkdir(parents=True, exist_ok=True)
        app_models.write_text("BayesianModelFit = object\nBayesianArtifact = object\n", encoding="utf-8")
        try:
            validate_module_surface(tmp_root)
        except ValidationError as exc:
            _require("forbidden import" in str(exc), f"B24_P1_NC_LLM_IMPORT_PASS unexpected reason: {exc}")
            print(f"B24_P1_NC_LLM_IMPORT_PASS: {exc}")
        else:
            raise ValidationError("B24_P1_NC_LLM_IMPORT_PASS did not fail")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        validate_all(ROOT)
        if args.negative_control:
            run_negative_controls(ROOT)
    except ValidationError as exc:
        print(f"B24_P1_AUTHORITY_SCHEMA_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P1_AUTHORITY_SCHEMA_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
