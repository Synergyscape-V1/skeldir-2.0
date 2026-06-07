from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.bayesian.artifact_repository import ArtifactMetadata, artifact_metadata_select
from app.bayesian.artifacts import (
    DEFAULT_P8_ARTIFACT_POLICY,
    artifact_sha256,
    canonical_json_bytes,
    decompress_payload_bytes,
    encode_payload_bytes,
)
from app.bayesian.exceptions import BayesianArtifactPolicyError
from app.bayesian.models import BayesianArtifact


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts/ci/validate_b24_p8_artifact_lifecycle.py"
ARTIFACT_REPOSITORY = ROOT / "backend/app/bayesian/artifact_repository.py"
ARTIFACTS = ROOT / "backend/app/bayesian/artifacts.py"
ENUMS = ROOT / "backend/app/bayesian/enums.py"
MODELS = ROOT / "backend/app/bayesian/models.py"
MIGRATION = (
    ROOT
    / "alembic/versions/007_skeldir_foundation/202606061200_b24_p8_artifact_lifecycle.py"
)
FOLLOW_UP_MIGRATION = (
    ROOT
    / "alembic/versions/007_skeldir_foundation/202606071200_b24_p8_follow_up_airgap_quota.py"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_b24_p8_artifact_lifecycle", VALIDATOR
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_b24_p8_policy_rejects_trace_type_and_oversized_payloads() -> None:
    validator = _load_validator()

    with pytest.raises(validator.ValidationError, match="posterior_trace"):
        validator.validate_models_and_migration(
            enums_text=_read(ENUMS) + "\nPOSTERIOR_TRACE = 'posterior_trace'\n"
        )
    with pytest.raises(BayesianArtifactPolicyError, match="JSON payload"):
        canonical_json_bytes(
            {
                "kind": "summary",
                "payload": "x" * (DEFAULT_P8_ARTIFACT_POLICY.max_json_bytes + 1),
            }
        )
    with pytest.raises(BayesianArtifactPolicyError, match="PII-like key"):
        canonical_json_bytes({"email": "person@example.invalid"})


def test_b24_p8_hash_binds_to_exact_encoded_bytes() -> None:
    payload = {"schema_version": "test", "fit_id": str(uuid4()), "values": [3, 1, 2]}
    stored, digest = encode_payload_bytes(payload)

    assert stored == json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert digest == artifact_sha256(stored)
    assert digest != artifact_sha256(stored + b"\n")

    compressed, compressed_hash = encode_payload_bytes(payload, compression="gzip")
    assert compressed_hash == artifact_sha256(compressed)
    assert decompress_payload_bytes(compressed, compression="gzip") == stored


def test_b24_p8_metadata_projection_airgaps_payload_bytes() -> None:
    payload_property = BayesianArtifact.__mapper__.attrs.payload_bytes
    assert payload_property.deferred is True
    assert payload_property.strategy_key == (
        ("deferred", True),
        ("instrument", True),
        ("raiseload", True),
    )

    compiled = str(
        artifact_metadata_select().compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "payload_bytes" not in compiled

    metadata_fields = set(ArtifactMetadata.__dataclass_fields__)
    assert "payload_bytes" not in metadata_fields
    assert "payload_byte_count" in metadata_fields


def test_b24_p8_validator_negative_controls() -> None:
    validator = _load_validator()

    validator.validate_policy_module()
    validator.validate_repository()
    validator.validate_models_and_migration()
    validator.validate_fit_execution()

    with pytest.raises(validator.ValidationError, match="MAX_P8_ARTIFACT_BYTES"):
        validator.validate_policy_module(
            artifacts_text=_read(ARTIFACTS).replace(
                "MAX_P8_ARTIFACT_BYTES = 64 * 1024",
                "MAX_P8_ARTIFACT_BYTES = 1024 * 1024",
            )
        )
    with pytest.raises(validator.ValidationError, match="object_storage"):
        validator.validate_models_and_migration(
            enums_text=_read(ENUMS) + "\nOBJECT_STORAGE = 'object_storage'\n"
        )
    with pytest.raises(validator.ValidationError, match="ungoverned"):
        validator.validate_fit_execution(
            fit_execution_text=_read(ROOT / "backend/app/bayesian/fit_execution.py")
            + "\nartifact_ref='b24://p6-summary/x'\n"
        )
    with pytest.raises(validator.ValidationError, match="deferred_raiseload"):
        validator.validate_models_and_migration(
            models_text=_read(MODELS).replace("deferred_raiseload=True,", "")
        )
    with pytest.raises(validator.ValidationError, match="active_artifact_count"):
        validator.validate_repository(
            repository_text=_read(ARTIFACT_REPOSITORY).replace(
                "active_artifact_count + 1 <= max_artifact_count",
                "active_artifact_count <= max_artifact_count",
            )
        )


def test_b24_p8_repository_contains_no_forbidden_storage_or_decompression() -> None:
    repository = _read(ARTIFACT_REPOSITORY)
    artifacts = _read(ARTIFACTS)
    migration_upgrade = "\n".join(
        (
            _load_validator()._upgrade_text(_read(MIGRATION)),
            _load_validator()._upgrade_text(_read(FOLLOW_UP_MIGRATION)),
        )
    )
    combined = "\n".join((repository, artifacts, migration_upgrade, _read(MODELS)))

    for token in (
        "boto3",
        "google-cloud-storage",
        "azure-storage-blob",
        "pg_largeobject",
        "lo_create",
        "lo_import",
        "lo_export",
        "connection.lobject",
        "posterior_trace",
        "object_storage",
        "local_fs",
        "gzip.decompress(",
        "zlib.decompress(",
    ):
        assert token not in combined
