#!/usr/bin/env python3
"""Validate B2.4-P8 artifact lifecycle and storage governance."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BAYESIAN_PACKAGE = Path("backend/app/bayesian")
ARTIFACTS = BAYESIAN_PACKAGE / "artifacts.py"
ARTIFACT_REPOSITORY = BAYESIAN_PACKAGE / "artifact_repository.py"
ENUMS = BAYESIAN_PACKAGE / "enums.py"
MODELS = BAYESIAN_PACKAGE / "models.py"
FIT_EXECUTION = BAYESIAN_PACKAGE / "fit_execution.py"
P8_TESTS = Path("backend/tests/test_b24_p8_artifact_lifecycle.py")
P8_DB_TESTS = Path("backend/tests/test_b24_p8_postgres_runtime.py")
P8_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202606061200_b24_p8_artifact_lifecycle.py"
)
WORKFLOW = Path(".github/workflows/b2_4-gate-dry-run.yml")
MAKEFILE = Path("Makefile")
ENFORCER_REGISTRY = Path("docs/ci/enforcer_registry.yaml")
SUBSUMPTION_MATRIX = Path("docs/ci/gate_subsumption_matrix.yaml")
TOPOLOGY_MAP = Path("docs/ci/ci_topology_map.md")
REQUIRED_STATUS_CONTRACT = Path(
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
)

REQUIRED_FILES = {
    ARTIFACTS,
    ARTIFACT_REPOSITORY,
    ENUMS,
    MODELS,
    FIT_EXECUTION,
    P8_TESTS,
    P8_DB_TESTS,
    P8_MIGRATION,
    WORKFLOW,
    MAKEFILE,
    ENFORCER_REGISTRY,
    SUBSUMPTION_MATRIX,
    TOPOLOGY_MAP,
    REQUIRED_STATUS_CONTRACT,
}


class ValidationError(RuntimeError):
    pass


def _read(path: Path) -> str:
    full = ROOT / path
    if not full.exists():
        raise ValidationError(f"missing required file: {path.as_posix()}")
    return full.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _upgrade_text(migration_text: str) -> str:
    start = migration_text.index("def upgrade()")
    end = migration_text.index("def downgrade()")
    return migration_text[start:end]


def validate_policy_module(artifacts_text: str | None = None) -> None:
    artifacts = artifacts_text if artifacts_text is not None else _read(ARTIFACTS)
    for token in (
        "B24_P8_ARTIFACT_POLICY_VERSION",
        "b24-p8-artifact-policy-v1",
        "MAX_P8_ARTIFACT_BYTES = 64 * 1024",
        "MAX_P8_JSON_BYTES = 32 * 1024",
        "MAX_P8_WAL_BUDGET_BYTES_PER_FIT = 128 * 1024",
        "DEFAULT_P8_TENANT_QUOTA_BYTES",
        "P8_ALLOWED_ARTIFACT_TYPES",
        "P8_ALLOWED_COMPRESSIONS",
        "canonical_json_bytes",
        "artifact_sha256",
        "validate_artifact_ref",
        "decompressobj",
    ):
        _require(token in artifacts, f"P8 policy missing: {token}")
    for forbidden in ("gzip.decompress(", "zlib.decompress(", "pickle", "cloudpickle"):
        _require(
            forbidden not in artifacts,
            f"P8 policy uses forbidden operation: {forbidden}",
        )


def validate_repository(repository_text: str | None = None) -> None:
    repository = (
        repository_text if repository_text is not None else _read(ARTIFACT_REPOSITORY)
    )
    for token in (
        "persist_artifact_sync",
        "verify_artifact_bytes_sync",
        "prune_expired_artifacts_sync",
        "bayesian_artifact_storage_quotas",
        "ON CONFLICT (tenant_id)",
        "active_bytes + :size_bytes <= quota_bytes",
        "max_artifact_wal_budget_bytes_per_fit",
        "FOR UPDATE SKIP LOCKED",
        "payload_bytes = NULL",
        "pruned_metadata",
        "artifact_uri_internal",
        "'postgres'",
        "idempotent_replay",
    ):
        _require(token in repository, f"P8 repository missing: {token}")
    for forbidden in (
        "boto3",
        "google-cloud-storage",
        "azure-storage-blob",
        "pg_largeobject",
        "lo_create",
        "lo_import",
        "lo_export",
        "lo_open",
        "lo_write",
        "lo_unlink",
        "connection.lobject",
    ):
        _require(
            forbidden not in repository,
            f"P8 repository has forbidden storage token: {forbidden}",
        )


def validate_models_and_migration(
    models_text: str | None = None,
    enums_text: str | None = None,
    migration_text: str | None = None,
) -> None:
    models = models_text if models_text is not None else _read(MODELS)
    enums = enums_text if enums_text is not None else _read(ENUMS)
    migration = migration_text if migration_text is not None else _read(P8_MIGRATION)
    upgrade = _upgrade_text(migration)
    for token in (
        "payload_json",
        "payload_bytes",
        "payload_byte_count",
        "lifecycle_status",
        "policy_version",
        "pruned_metadata",
        "BayesianArtifactStorageQuota",
        "ck_bayesian_artifacts_storage_backend",
        "storage_backend = 'postgres'",
        "ck_bayesian_artifacts_size_p8_cap",
        "ck_bayesian_artifacts_lifecycle_payload_state",
        "bayesian_artifact_storage_quotas",
        "ENABLE ROW LEVEL SECURITY",
        "FORCE ROW LEVEL SECURITY",
    ):
        _require(token in models or token in upgrade, f"P8 schema missing: {token}")
    combined_current = "\n".join((models, enums, upgrade))
    for forbidden in (
        "posterior_trace",
        "object_storage",
        "local_fs",
        "zstd",
        "pg_largeobject",
        "lo_create",
        "LargeObject",
    ):
        _require(
            forbidden not in combined_current,
            f"P8 current schema allows forbidden token: {forbidden}",
        )


def validate_fit_execution(fit_execution_text: str | None = None) -> None:
    fit_execution = (
        fit_execution_text if fit_execution_text is not None else _read(FIT_EXECUTION)
    )
    for token in (
        "from app.bayesian.artifact_repository import persist_artifact_sync",
        "persist_artifact_sync(",
        'artifact_type="diagnostics"',
        'retention_class="standard"',
    ):
        _require(token in fit_execution, f"P8 fit execution wiring missing: {token}")
    _require(
        "b24://p6-summary/" not in fit_execution,
        "fit execution still writes ungoverned summary refs",
    )


def validate_no_public_or_cloud_scope() -> None:
    relevant_paths = (
        ARTIFACTS,
        ARTIFACT_REPOSITORY,
        ENUMS,
        MODELS,
        FIT_EXECUTION,
        P8_MIGRATION,
    )
    combined = "\n".join(_read(path) for path in relevant_paths)
    for forbidden in (
        "FastAPI",
        "APIRouter",
        "TrustEnvelope",
        "openai",
        "anthropic",
        "boto3",
        "google.cloud.storage",
        "azure.storage.blob",
        "S3",
        "GCS",
        "Azure Blob",
    ):
        _require(
            forbidden not in combined,
            f"P8 leaked forbidden public/cloud/LLM scope: {forbidden}",
        )
    for path in relevant_paths:
        tree = ast.parse(_read(path), filename=path.as_posix())
        imports = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        from_imports = {
            node.module
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        forbidden_imports = {"boto3", "openai", "anthropic", "fastapi"}
        _require(not (forbidden_imports & imports), f"forbidden import in {path}")
        _require(not (forbidden_imports & from_imports), f"forbidden import in {path}")


def validate_tests_and_ci(
    workflow_text: str | None = None,
    required_status_text: str | None = None,
) -> None:
    tests = _read(P8_TESTS)
    db_tests = _read(P8_DB_TESTS)
    workflow = workflow_text if workflow_text is not None else _read(WORKFLOW)
    required_status = (
        required_status_text
        if required_status_text is not None
        else _read(REQUIRED_STATUS_CONTRACT)
    )
    makefile = _read(MAKEFILE)
    registry = _read(ENFORCER_REGISTRY)
    subsumption = _read(SUBSUMPTION_MATRIX)
    topology = _read(TOPOLOGY_MAP)
    for token in (
        "test_b24_p8_policy_rejects_trace_type_and_oversized_payloads",
        "test_b24_p8_hash_binds_to_exact_encoded_bytes",
        "test_b24_p8_validator_negative_controls",
    ):
        _require(token in tests, f"P8 unit proof missing: {token}")
    for token in (
        "test_b24_p8_repository_persists_verifies_quota_and_prunes",
        "SKELDIR_B24_P8_REQUIRE_DB_PROOFS",
        "verify_artifact_bytes_sync",
        "prune_expired_artifacts_sync",
    ):
        _require(token in db_tests, f"P8 DB proof missing: {token}")
    for token in (
        "validate-b24-p8-artifact-lifecycle",
        "B2.4-P8 Artifact Lifecycle Proof",
        "test_b24_p8_artifact_lifecycle.py",
        "test_b24_p8_postgres_runtime.py",
        "SKELDIR_B24_P8_REQUIRE_DB_PROOFS",
        "scripts/ci/validate_b24_p8_artifact_lifecycle.py --negative-control",
    ):
        _require(token in workflow, f"P8 workflow wiring missing: {token}")
    _require(
        "validate-b24-p8-artifact-lifecycle" in makefile,
        "Makefile missing P8 validator target",
    )
    for text, name in (
        (registry, "enforcer registry"),
        (subsumption, "gate subsumption matrix"),
        (topology, "CI topology map"),
    ):
        _require(
            "validate-b24-p8-artifact-lifecycle" in text, f"{name} missing P8 gate"
        )
        _require("B2.4-P8 Artifact Lifecycle Proof" in text, f"{name} missing P8 job")
    _require(
        '"B2.4-P8 Artifact Lifecycle Proof"' in required_status,
        "required-status contract missing P8 proof context",
    )


def validate_all() -> None:
    for path in REQUIRED_FILES:
        _read(path)
    validate_policy_module()
    validate_repository()
    validate_models_and_migration()
    validate_fit_execution()
    validate_no_public_or_cloud_scope()
    validate_tests_and_ci()


def run_negative_controls() -> None:
    controls = (
        (
            "missing_byte_cap",
            lambda: validate_policy_module(
                artifacts_text=_read(ARTIFACTS).replace(
                    "MAX_P8_ARTIFACT_BYTES = 64 * 1024",
                    "MAX_P8_ARTIFACT_BYTES = 1024 * 1024",
                )
            ),
            "MAX_P8_ARTIFACT_BYTES",
        ),
        (
            "cloud_backend_allowed",
            lambda: validate_models_and_migration(
                enums_text=_read(ENUMS) + "\nOBJECT_STORAGE = 'object_storage'\n"
            ),
            "object_storage",
        ),
        (
            "ungoverned_fit_ref",
            lambda: validate_fit_execution(
                fit_execution_text=_read(FIT_EXECUTION)
                + "\nartifact_ref='b24://p6-summary/x'\n"
            ),
            "ungoverned",
        ),
        (
            "missing_required_status",
            lambda: validate_tests_and_ci(
                required_status_text=_read(REQUIRED_STATUS_CONTRACT).replace(
                    '"B2.4-P8 Artifact Lifecycle Proof"',
                    '"B2.4-P8 Missing Proof"',
                )
            ),
            "required-status",
        ),
    )
    for name, runner, expected in controls:
        try:
            runner()
        except ValidationError as exc:
            _require(
                expected.lower() in str(exc).lower(),
                f"{name} failed for wrong reason: {exc}",
            )
        else:
            raise ValidationError(f"negative control did not fail: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        validate_all()
        if args.negative_control:
            run_negative_controls()
    except ValidationError as exc:
        print(f"B24_P8_ARTIFACT_LIFECYCLE_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P8_ARTIFACT_LIFECYCLE_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
