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
CORRECTIVE_MIGRATION_PATH = Path(
    "alembic/versions/007_skeldir_foundation/202605201430_b24_p1_corrective_authority_closure.py"
)
PARTITION_MIGRATION_PATH = Path(
    "alembic/versions/007_skeldir_foundation/202605211200_b24_p1_partitioned_authority_schema.py"
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
    "bayesian_model_fits_pkey",
    "bayesian_artifacts_pkey",
    "uq_bayesian_model_fits_tenant_model_window_snapshot",
    "fk_bayesian_artifacts_tenant_fit",
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

FORBIDDEN_BAYESIAN_FIELD_FRAGMENTS = {
    "email",
    "name",
    "phone",
    "address",
    "ip_address",
    "user_agent",
    "oauth",
    "token",
    "raw_payload",
}

IDENTITY_BEARING_TABLES = {
    "attribution_commerce_identities",
    "webhook_ingress_identities",
}

IDENTITY_BEARING_IMPORT_TOKENS = {
    "attribution_commerce_identities",
    "webhook_ingress_identities",
    "commerce_identity",
    "ingress_identity",
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
    matches = list(re.finditer(rf"CREATE TABLE public\.{re.escape(table)} \((.*?)\n\s*\)", text, re.S))
    return matches[-1].group(1) if matches else ""


def _migration_chain_text(root: Path) -> str:
    return "\n\n".join(_read(root, path) for path in (MIGRATION_PATH, CORRECTIVE_MIGRATION_PATH, PARTITION_MIGRATION_PATH))


def _latest_upgrade_text(text: str) -> str:
    marker = 'revision: str = "202605211200"'
    if marker not in text:
        return text
    tail = text[text.index(marker) :]
    downgrade_marker = "def downgrade() -> None:"
    if downgrade_marker in tail:
        return tail[: tail.index(downgrade_marker)]
    return tail


def _column_present(table_sql: str, column: str) -> bool:
    return re.search(rf"(?m)^\s*{re.escape(column)}\s+", table_sql) is not None


def _contains_forbidden_import(module: str) -> bool:
    return any(module == root or module.startswith(f"{root}.") for root in FORBIDDEN_IMPORT_ROOTS)


def _contains_identity_bearing_import(module: str) -> bool:
    module_lower = module.lower()
    return any(token in module_lower for token in IDENTITY_BEARING_IMPORT_TOKENS)


def _normalized_sql(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _require_ordered_unique(text: str, name: str, columns: tuple[str, ...]) -> None:
    pattern = (
        rf"CONSTRAINT\s+{re.escape(name)}\s+UNIQUE\s*\("
        + r"\s*"
        + r"\s*,\s*".join(re.escape(column) for column in columns)
        + r"\s*\)"
    )
    _require(re.search(pattern, text, re.I | re.S) is not None, f"missing required unique constraint: {name}")


def _require_ordered_primary_key(text: str, table: str, columns: tuple[str, ...]) -> None:
    pattern = (
        rf"CONSTRAINT\s+{re.escape(table)}_pkey\s+PRIMARY\s+KEY\s*\("
        + r"\s*"
        + r"\s*,\s*".join(re.escape(column) for column in columns)
        + r"\s*\)"
    )
    _require(
        re.search(pattern, text, re.I | re.S) is not None,
        f"{table} primary key must include partition key: {columns}",
    )


def _require_hash_partitioned(text: str, table: str) -> None:
    matches = list(re.finditer(rf"CREATE TABLE public\.{re.escape(table)}\s*\(", text))
    _require(matches, f"{table} must be physically HASH partitioned by tenant_id")
    start = matches[-1].start()
    next_table = text.find("CREATE TABLE public.", start + 1)
    segment = text[start:] if next_table < 0 else text[start:next_table]
    helper_name = "_create_model_fits_table" if table == "bayesian_model_fits" else "_create_artifacts_table"
    dynamic_partition_call = f"{helper_name}(partitioned=True)" in text and "PARTITION BY HASH (tenant_id)" in text
    _require(
        re.search(r"PARTITION BY HASH\s*\(\s*tenant_id\s*\)", segment, re.I) is not None
        or dynamic_partition_call,
        f"{table} must be physically HASH partitioned by tenant_id",
    )
    _require(
        f'_create_partitions("{table}"' in text or f"CREATE TABLE public.{table}_p00" in text,
        f"{table} missing initial partition family",
    )


def _require_fit_identity_not_null(table_sql: str) -> None:
    for column in (
        "tenant_id",
        "model_type",
        "model_version",
        "source_window_start",
        "source_window_end",
        "source_snapshot_hash",
    ):
        pattern = rf"(?m)^\s*{re.escape(column)}\s+.+?\bNOT\s+NULL\b"
        _require(
            re.search(pattern, table_sql) is not None,
            f"fit identity column must be NOT NULL under standard UNIQUE: {column}",
        )


def _require_tenant_bound_artifact_fk(text: str) -> None:
    pattern = (
        r"CONSTRAINT\s+fk_bayesian_artifacts_tenant_fit\s+"
        r"FOREIGN KEY\s*\(\s*tenant_id\s*,\s*fit_id\s*\)\s*"
        r"REFERENCES\s+public\.bayesian_model_fits\s*\(\s*tenant_id\s*,\s*id\s*\)\s*"
        r"ON DELETE RESTRICT"
    )
    _require(
        re.search(pattern, text, re.I | re.S) is not None,
        "bayesian_artifacts missing tenant-bound FK (tenant_id, fit_id) -> bayesian_model_fits(tenant_id, id)",
    )


def _validate_privacy_boundary_text(text: str) -> None:
    bayesian_references: list[str] = []
    for table in ("bayesian_model_fits", "bayesian_artifacts"):
        table_sql = _table_window(text, table)
        _require(table_sql, f"could not parse {table} table body")
        bayesian_references.append(table_sql)
        for line in table_sql.splitlines():
            column_match = re.match(r"\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+", line)
            if not column_match:
                continue
            column = column_match.group(1).lower()
            for fragment in FORBIDDEN_BAYESIAN_FIELD_FRAGMENTS:
                _require(
                    fragment not in column,
                    f"Bayesian authority table {table} contains forbidden privacy/identity field: {column}",
                )
    for line in text.splitlines():
        lowered_line = line.lower()
        if "bayesian_model_fits" in lowered_line or "bayesian_artifacts" in lowered_line:
            bayesian_references.append(line)
    lowered = "\n".join(bayesian_references).lower()
    for table in IDENTITY_BEARING_TABLES:
        _require(
            table not in lowered,
            f"Bayesian authority schema must not reference identity-bearing table: {table}",
        )


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
                _require(
                    not _contains_identity_bearing_import(module),
                    f"identity-bearing import forbidden in {rel}: {module}",
                )
        lowered = text.lower()
        for token in IDENTITY_BEARING_IMPORT_TOKENS:
            allowed_p2_forbidden_list = (
                rel == "backend/app/bayesian/input_contract.py"
                and "forbidden_manifest_sources" in lowered
                and "allowed_source_read_models" in lowered
            )
            _require(
                allowed_p2_forbidden_list or token not in lowered,
                f"identity-bearing reference forbidden in {rel}: {token}",
            )

    app_model_init = _read(root, MODEL_INIT_PATH)
    _require("BayesianModelFit" in app_model_init, "ORM metadata package missing BayesianModelFit export")
    _require("BayesianArtifact" in app_model_init, "ORM metadata package missing BayesianArtifact export")


def validate_migration_text(text: str) -> None:
    schema_text = _latest_upgrade_text(text)
    _require("CREATE TABLE public.bayesian_model_fits" in schema_text, "migration missing bayesian_model_fits table")
    _require("CREATE TABLE public.bayesian_artifacts" in schema_text, "migration missing bayesian_artifacts table")
    _require("CREATE TYPE" not in text.upper(), "native PostgreSQL enum DDL is forbidden for B2.4 P1 states")
    _require("CREATE INDEX CONCURRENTLY" not in text.upper(), "CREATE INDEX CONCURRENTLY forbidden in transactional migration")
    _require("postgresql_concurrently=True" not in text, "postgresql_concurrently=True forbidden in transactional migration")

    fit_sql = _table_window(schema_text, "bayesian_model_fits")
    artifact_sql = _table_window(schema_text, "bayesian_artifacts")
    _require(fit_sql, "could not parse bayesian_model_fits table body")
    _require(artifact_sql, "could not parse bayesian_artifacts table body")
    _require_hash_partitioned(schema_text, "bayesian_model_fits")
    _require_hash_partitioned(schema_text, "bayesian_artifacts")
    _require_ordered_primary_key(schema_text, "bayesian_model_fits", ("tenant_id", "id"))
    _require_ordered_primary_key(schema_text, "bayesian_artifacts", ("tenant_id", "id"))
    _require_fit_identity_not_null(fit_sql)

    missing_fit = sorted(column for column in REQUIRED_FIT_COLUMNS if not _column_present(fit_sql, column))
    missing_artifact = sorted(column for column in REQUIRED_ARTIFACT_COLUMNS if not _column_present(artifact_sql, column))
    _require(not missing_fit, f"bayesian_model_fits missing columns: {missing_fit}")
    _require(not missing_artifact, f"bayesian_artifacts missing columns: {missing_artifact}")

    _require("source_snapshot_hash character varying(64) NOT NULL" in schema_text, "source_snapshot_hash must be VARCHAR(64) NOT NULL")
    _require("artifact_hash character varying(64)" in schema_text, "artifact_hash must be VARCHAR(64)")
    _require("'^[a-f0-9]{{64}}$'" in schema_text or "'^[a-f0-9]{64}$'" in schema_text, "SHA-256 lowercase hex regex check missing")
    _require("fallback_applied = true" in schema_text, "fallback partial index predicate missing")
    _require("last_eligibility_check_at DESC" in schema_text, "eligibility recency index missing DESC timestamp")
    _require("ON DELETE RESTRICT" in schema_text, "artifact fit FK must avoid cascade-delete by default")
    _require("DROP CONSTRAINT IF EXISTS bayesian_artifacts_fit_id_fkey" in text, "single-column artifact FK must be dropped")
    _require_tenant_bound_artifact_fk(schema_text)
    _require_ordered_unique(
        schema_text,
        "uq_bayesian_model_fits_tenant_model_window_snapshot",
        (
            "tenant_id",
            "model_type",
            "model_version",
            "source_window_start",
            "source_window_end",
            "source_snapshot_hash",
        ),
    )
    _require(
        '_create_partitions("bayesian_model_fits", fillfactor=90)' in schema_text
        or re.search(r"ALTER TABLE\s+public\.bayesian_model_fits_p\d{2}\s+SET\s*\(\s*fillfactor\s*=\s*90\s*\)", schema_text, re.I) is not None,
        "bayesian_model_fits partitions must set explicit fillfactor=90",
    )
    _require("Final physical table family: HASH partitioned by tenant_id" in schema_text, "partitioning cannot be deferred")
    _validate_privacy_boundary_text(text)

    for index in REQUIRED_INDEXES:
        _require(
            re.search(rf"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+{re.escape(index)}\b", schema_text, re.I) is not None,
            f"migration missing required index: {index}",
        )
    for constraint in REQUIRED_CONSTRAINTS:
        _require(constraint in schema_text, f"migration missing required constraint: {constraint}")

    for table in ("bayesian_model_fits", "bayesian_artifacts"):
        _require(
            f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in schema_text
            or 'ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY' in text,
            f"{table} missing ENABLE RLS",
        )
        _require(
            f"ALTER TABLE ONLY public.{table} FORCE ROW LEVEL SECURITY" in schema_text
            or 'ALTER TABLE ONLY public.{table_name} FORCE ROW LEVEL SECURITY' in text,
            f"{table} missing FORCE RLS",
        )
        _require("current_setting('app.current_tenant_id', true)::uuid" in schema_text, f"{table} policy missing tenant GUC")


def validate_canonical_schema(root: Path) -> None:
    canonical = _read(root, CANONICAL_SCHEMA_PATH)
    yaml_text = _read(root, CANONICAL_YAML_PATH)
    for table in ("bayesian_model_fits", "bayesian_artifacts"):
        _require(f"CREATE TABLE public.{table}" in canonical, f"canonical schema missing table: {table}")
        _require_hash_partitioned(canonical, table)
        _require(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in canonical, f"canonical schema missing RLS: {table}")
        _require(table in yaml_text, f"canonical schema YAML missing table: {table}")
    for index in REQUIRED_INDEXES:
        _require(index in canonical, f"canonical schema missing index: {index}")
    for constraint in REQUIRED_CONSTRAINTS:
        _require(constraint in canonical, f"canonical schema missing constraint: {constraint}")
    _require("bayesian_artifacts_fit_id_fkey" not in canonical, "canonical schema retains single-column artifact fit FK")
    _require_tenant_bound_artifact_fk(canonical)
    _require_ordered_primary_key(canonical, "bayesian_model_fits", ("tenant_id", "id"))
    _require_ordered_primary_key(canonical, "bayesian_artifacts", ("tenant_id", "id"))
    _require_ordered_unique(
        canonical,
        "uq_bayesian_model_fits_tenant_model_window_snapshot",
        (
            "tenant_id",
            "model_type",
            "model_version",
            "source_window_start",
            "source_window_end",
            "source_snapshot_hash",
        ),
    )
    _require_fit_identity_not_null(_table_window(canonical, "bayesian_model_fits"))
    _require("fillfactor='90'" in canonical or "fillfactor = 90" in canonical, "canonical schema missing bayesian_model_fits fillfactor=90")
    _validate_privacy_boundary_text(canonical)
    _require("partition_readiness" not in yaml_text, "canonical YAML still defers partitioning")
    _require("partitioning:" in yaml_text, "canonical YAML missing final partitioning decision")
    bayesian_yaml_lines = "\n".join(
        line
        for line in yaml_text.splitlines()
        if "bayesian_model_fits" in line.lower() or "bayesian_artifacts" in line.lower()
    ).lower()
    for table in IDENTITY_BEARING_TABLES:
        _require(
            table not in bayesian_yaml_lines,
            f"canonical YAML Bayesian section references identity-bearing table: {table}",
        )


def validate_models(root: Path) -> None:
    models_text = _read(root, BAYESIAN_PACKAGE / "models.py")
    for token in (
        '__tablename__ = "bayesian_model_fits"',
        '__tablename__ = "bayesian_artifacts"',
        "PGUUID(as_uuid=True)",
        "server_default=func.gen_random_uuid()",
        "CheckConstraint",
        "ForeignKeyConstraint",
        "PrimaryKeyConstraint",
        "fk_bayesian_artifacts_tenant_fit",
        "uq_bayesian_model_fits_tenant_model_window_snapshot",
        '"fit_partition_fillfactor": 90',
        '"partitioning": {"strategy": "hash", "key": ["tenant_id"], "partitions": 16}',
        "fillfactor",
        "postgresql_where=text(\"fallback_applied = true\")",
    ):
        _require(token in models_text, f"Bayesian ORM model missing token: {token}")
    _validate_privacy_boundary_text(_migration_chain_text(root))


def validate_all(root: Path) -> None:
    validate_module_surface(root)
    validate_migration_text(_migration_chain_text(root))
    validate_canonical_schema(root)
    validate_models(root)


def run_negative_controls(root: Path) -> None:
    migration = _migration_chain_text(root)
    for label, mutated, expected in (
        (
            "B24_P1_NC_REMOVE_FIT_TABLE_PASS",
            migration.replace("CREATE TABLE public.bayesian_model_fits", "CREATE TABLE public.bayesian_model_fits_removed"),
            "bayesian_model_fits",
        ),
        (
            "B24_P1_NC_REMOVE_HASH_CHECK_PASS",
            migration.replace("ck_bayesian_model_fits_source_snapshot_hash_sha256", "ck_bayesian_model_fits_source_snapshot_hash_removed"),
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
        (
            "B24_P1_NC_MISSING_TENANT_BOUND_ARTIFACT_FK_PASS",
            migration.replace("fk_bayesian_artifacts_tenant_fit", "fk_bayesian_artifacts_tenant_fit_removed"),
            "tenant-bound FK",
        ),
        (
            "B24_P1_NC_MISSING_FIT_IDENTITY_WINDOW_PASS",
            migration.replace("source_window_start,\n                    source_window_end,\n                    source_snapshot_hash", "source_snapshot_hash", 1),
            "uq_bayesian_model_fits_tenant_model_window_snapshot",
        ),
        (
            "B24_P1_NC_BAYESIAN_PII_FIELD_PASS",
            migration.replace("updated_at timestamp with time zone DEFAULT now() NOT NULL,", "email character varying(255),\n            updated_at timestamp with time zone DEFAULT now() NOT NULL,"),
            "forbidden privacy/identity field",
        ),
        (
            "B24_P1_NC_BAYESIAN_IDENTITY_FK_PASS",
            migration + "\n# regression\nop.execute('ALTER TABLE public.bayesian_artifacts ADD CONSTRAINT fk_bad_identity FOREIGN KEY (fit_id) REFERENCES public.attribution_commerce_identities(id)')\n",
            "identity-bearing table",
        ),
        (
            "B24_P1_NC_MISSING_FIT_FILLFACTOR_PASS",
            migration.replace('_create_partitions("bayesian_model_fits", fillfactor=90)', '_create_partitions("bayesian_model_fits")', 1),
            "fillfactor=90",
        ),
        (
            "B24_P1_NC_PARTITION_DEFERRAL_PASS",
            migration.replace("PARTITION BY HASH (tenant_id)", "WITH (fillfactor = 90)"),
            "HASH partitioned",
        ),
        (
            "B24_P1_NC_PARTITION_INCOMPATIBLE_PK_PASS",
            migration.replace("CONSTRAINT bayesian_model_fits_pkey PRIMARY KEY (tenant_id, id)", "CONSTRAINT bayesian_model_fits_pkey PRIMARY KEY (id)", 1),
            "primary key must include partition key",
        ),
        (
            "B24_P1_NC_PARTITION_INCOMPATIBLE_UNIQUE_PASS",
            migration.replace("tenant_id,\n                    model_type,", "model_type,", 1),
            "uq_bayesian_model_fits_tenant_model_window_snapshot",
        ),
        (
            "B24_P1_NC_NULLABLE_FIT_IDENTITY_PASS",
            migration.replace("source_window_end timestamp with time zone NOT NULL", "source_window_end timestamp with time zone"),
            "fit identity column must be NOT NULL",
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

    with tempfile.TemporaryDirectory(prefix="b24_p1_bad_identity_import_") as tmp:
        tmp_root = Path(tmp)
        package = tmp_root / BAYESIAN_PACKAGE
        package.mkdir(parents=True)
        for module in REQUIRED_MODULES:
            (package / module).write_text("", encoding="utf-8")
        (package / "models.py").write_text("from app.ingestion.webhook_ingress_identities import Loader\n", encoding="utf-8")
        app_models = tmp_root / MODEL_INIT_PATH
        app_models.parent.mkdir(parents=True, exist_ok=True)
        app_models.write_text("BayesianModelFit = object\nBayesianArtifact = object\n", encoding="utf-8")
        try:
            validate_module_surface(tmp_root)
        except ValidationError as exc:
            _require("identity-bearing import" in str(exc), f"B24_P1_NC_IDENTITY_IMPORT_PASS unexpected reason: {exc}")
            print(f"B24_P1_NC_IDENTITY_IMPORT_PASS: {exc}")
        else:
            raise ValidationError("B24_P1_NC_IDENTITY_IMPORT_PASS did not fail")


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
