"""B2.4-P8 bounded artifact policy and byte canonicalization."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
import re
import zlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from app.bayesian.enums import ArtifactType, Compression, RetentionClass
from app.bayesian.exceptions import BayesianArtifactPolicyError


B24_P8_ARTIFACT_POLICY_VERSION = "b24-p8-artifact-policy-v1"
MAX_P8_ARTIFACT_BYTES = 64 * 1024
MAX_P8_JSON_BYTES = 32 * 1024
MAX_P8_WAL_BUDGET_BYTES_PER_FIT = 128 * 1024
DEFAULT_P8_TENANT_QUOTA_BYTES = 1024 * 1024
MAX_P8_PRUNE_BATCH_SIZE = 100

P8_ALLOWED_ARTIFACT_TYPES = frozenset(
    {
        ArtifactType.DIAGNOSTICS.value,
        ArtifactType.SUMMARY.value,
        ArtifactType.SOURCE_MANIFEST.value,
        ArtifactType.FIT_METADATA.value,
        ArtifactType.INPUT_MANIFEST.value,
        ArtifactType.MODEL_SPEC.value,
        ArtifactType.POSTERIOR_SUMMARY.value,
    }
)
P8_ALLOWED_COMPRESSIONS = frozenset({Compression.NONE.value, Compression.GZIP.value})
P8_ALLOWED_RETENTION_CLASSES = frozenset(
    {
        RetentionClass.EPHEMERAL.value,
        RetentionClass.STANDARD.value,
        RetentionClass.AUDIT.value,
    }
)
RETENTION_TTLS = {
    RetentionClass.EPHEMERAL.value: timedelta(days=7),
    RetentionClass.STANDARD.value: timedelta(days=90),
    RetentionClass.AUDIT.value: None,
}
PII_KEY_PATTERN = re.compile(
    r"(email|phone|ip_address|address|first_name|last_name|full_name|customer_name)",
    re.IGNORECASE,
)
UNSAFE_REF_PATTERN = re.compile(
    r"(@|\\\\|/users/|/home/|[a-z]:\\\\|secret|token)", re.IGNORECASE
)


@dataclass(frozen=True)
class ArtifactPolicy:
    """Versioned physical storage limits for P8 artifacts."""

    policy_version: str = B24_P8_ARTIFACT_POLICY_VERSION
    max_artifact_bytes: int = MAX_P8_ARTIFACT_BYTES
    max_json_bytes: int = MAX_P8_JSON_BYTES
    max_artifact_wal_budget_bytes_per_fit: int = MAX_P8_WAL_BUDGET_BYTES_PER_FIT
    default_tenant_quota_bytes: int = DEFAULT_P8_TENANT_QUOTA_BYTES
    max_prune_batch_size: int = MAX_P8_PRUNE_BATCH_SIZE


DEFAULT_P8_ARTIFACT_POLICY = ArtifactPolicy()


def _walk_json(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from _walk_json(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _walk_json(item)


def _reject_pii_keys(payload: dict[str, Any]) -> None:
    for key, _value in _walk_json(payload):
        if PII_KEY_PATTERN.search(str(key)):
            raise BayesianArtifactPolicyError(
                f"artifact payload contains PII-like key: {key}"
            )


def canonical_json_bytes(
    payload: dict[str, Any], *, policy: ArtifactPolicy = DEFAULT_P8_ARTIFACT_POLICY
) -> bytes:
    """Return the deterministic bytes that are persisted and hashed."""

    _reject_pii_keys(payload)
    for _, value in _walk_json(payload):
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float) and not math.isfinite(float(value)):
            raise BayesianArtifactPolicyError(
                "artifact payload contains non-finite number"
            )
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > policy.max_json_bytes:
        raise BayesianArtifactPolicyError("artifact JSON payload exceeds P8 JSON cap")
    return encoded


def artifact_sha256(payload_bytes: bytes) -> str:
    return hashlib.sha256(payload_bytes).hexdigest()


def validate_artifact_ref(ref: str) -> None:
    if UNSAFE_REF_PATTERN.search(ref):
        raise BayesianArtifactPolicyError(
            "artifact ref contains unsafe path, secret, or PII-like token"
        )
    if not ref.startswith("b24://artifact/"):
        raise BayesianArtifactPolicyError(
            "artifact ref must use internal b24://artifact/ scheme"
        )


def encode_payload_bytes(
    payload: dict[str, Any],
    *,
    compression: str = Compression.NONE.value,
    policy: ArtifactPolicy = DEFAULT_P8_ARTIFACT_POLICY,
) -> tuple[bytes, str]:
    """Encode, cap, and hash the exact bytes persisted in Postgres bytea."""

    if compression not in P8_ALLOWED_COMPRESSIONS:
        raise BayesianArtifactPolicyError("artifact compression is not P8-governed")
    canonical = canonical_json_bytes(payload, policy=policy)
    if compression == Compression.GZIP.value:
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as gz:
            gz.write(canonical)
        stored = buffer.getvalue()
    else:
        stored = canonical
    if len(stored) > policy.max_artifact_bytes:
        raise BayesianArtifactPolicyError("artifact payload exceeds P8 bytea cap")
    return stored, artifact_sha256(stored)


def decompress_payload_bytes(
    stored: bytes,
    *,
    compression: str,
    policy: ArtifactPolicy = DEFAULT_P8_ARTIFACT_POLICY,
) -> bytes:
    """Bounded gzip decompression for verification paths; avoids one-shot APIs."""

    if compression == Compression.NONE.value:
        if len(stored) > policy.max_artifact_bytes:
            raise BayesianArtifactPolicyError("stored artifact exceeds P8 bytea cap")
        return stored
    if compression != Compression.GZIP.value:
        raise BayesianArtifactPolicyError("unsupported artifact compression")
    obj = zlib.decompressobj(16 + zlib.MAX_WBITS)
    output = bytearray()
    for offset in range(0, len(stored), 4096):
        chunk = obj.decompress(stored[offset : offset + 4096])
        output.extend(chunk)
        if len(output) > policy.max_artifact_bytes:
            raise BayesianArtifactPolicyError(
                "artifact decompression exceeds P8 output cap"
            )
    output.extend(obj.flush())
    if len(output) > policy.max_artifact_bytes:
        raise BayesianArtifactPolicyError(
            "artifact decompression exceeds P8 output cap"
        )
    return bytes(output)
