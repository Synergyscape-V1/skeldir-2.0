"""Bounded, domain-separated signed export artifacts for B2.5-P11."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Literal

from app.trust.canonicalization import canonicalize_envelope_payload
from app.trust.hash_identity import (
    compute_artifact_hash,
    compute_detached_signature_hash,
)
from app.trust.key_registry import TrustKeyRegistry
from app.trust.signing import (
    TrustEnvelopeSigningError,
    encode_ed25519_signature,
    verify_ed25519_signature,
)
from app.trust.verification import verify_trust_envelope


# ---------------------------------------------------------------------------
# Artifact protocol registry (B2.5-P11 third corrective)
# ---------------------------------------------------------------------------
# A version tuple must denote exactly one cryptographic algorithm. The second
# corrective cycle changed what the artifact hash covers -- signer identity moved
# out of the artifact identity and into the signature material -- while leaving
# the ``v1`` markers byte-identical. That made ``v1`` ambiguous: two incompatible
# algorithms shared one name, and an artifact legitimately signed under the older
# framing failed current verification as an indistinguishable
# ``artifact_hash_mismatch``.
#
# The protocols are now separated. ``v1`` is frozen with its original semantics
# and remains verifiable; ``v2`` carries the corrected signer-independent
# identity and is the only protocol that may be issued.
#
#   version tuple -> exactly one framing/hash/signature-material algorithm
#
# Adding a protocol means adding an entry here plus its framing function and a
# manifest entry; it never means editing an existing entry's semantics.

EXPORT_ARTIFACT_SCHEMA_VERSION_V1 = "b25-p11-export-artifact-v1"
EXPORT_ARTIFACT_CANONICALIZATION_VERSION_V1 = "b25-p11-artifact-framing-v1"
EXPORT_ARTIFACT_SIGNING_DOMAIN_V1 = b"skeldir:b25-p11:export-artifact:v1\x00"
EXPORT_ARTIFACT_SIGNING_DOMAIN_LABEL_V1 = "skeldir:b25-p11:export-artifact:v1\\0"

EXPORT_ARTIFACT_SCHEMA_VERSION_V2 = "b25-p11-export-artifact-v2"
EXPORT_ARTIFACT_CANONICALIZATION_VERSION_V2 = "b25-p11-artifact-framing-v2"
EXPORT_ARTIFACT_SIGNING_DOMAIN_V2 = b"skeldir:b25-p11:export-artifact:v2\x00"
EXPORT_ARTIFACT_SIGNING_DOMAIN_LABEL_V2 = "skeldir:b25-p11:export-artifact:v2\\0"

#: The protocol new artifacts are issued under.
EXPORT_ARTIFACT_SCHEMA_VERSION = EXPORT_ARTIFACT_SCHEMA_VERSION_V2
EXPORT_ARTIFACT_CANONICALIZATION_VERSION = EXPORT_ARTIFACT_CANONICALIZATION_VERSION_V2
EXPORT_ARTIFACT_SIGNING_DOMAIN = EXPORT_ARTIFACT_SIGNING_DOMAIN_V2
EXPORT_ARTIFACT_SIGNING_DOMAIN_LABEL = EXPORT_ARTIFACT_SIGNING_DOMAIN_LABEL_V2

MAX_EXPORT_ARTIFACT_ENVELOPES = 2

_BASE_FIELDS = frozenset(
    {
        "artifact_schema_version",
        "canonicalization_version",
        "artifact_signing_domain",
        "envelopes",
        "generated_at",
        "tenant_id_hash",
    }
)
_SIGNED_FIELDS = _BASE_FIELDS | frozenset(
    {
        "artifact_hash",
        "signature_hash",
        "signature",
        "signing_key_id",
        "signing_algorithm",
    }
)


class ExportArtifactError(ValueError):
    """Raised when an export artifact violates identity or signing physics."""


@dataclass(frozen=True)
class ExportArtifactVerificationResult:
    verification_status: Literal["verified", "rejected"]
    reason_code: str | None
    artifact_hash: str | None
    signing_key_id: str | None

    def external_projection(self) -> dict[str, object | None]:
        return asdict(self)


def _utc_second(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ExportArtifactError("artifact_generated_at_timezone_required")
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _frame(label: str, payload: bytes) -> bytes:
    label_bytes = label.encode("utf-8")
    return (
        len(label_bytes).to_bytes(2, "big")
        + label_bytes
        + len(payload).to_bytes(8, "big")
        + payload
    )


def _require_text(value: Any, field_path: str) -> str:
    if not isinstance(value, str):
        raise ExportArtifactError(f"artifact_text_field_invalid:{field_path}")
    return value


def _ordered_envelopes(envelopes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    copied = [deepcopy(value) for value in envelopes]
    return sorted(
        copied,
        key=lambda value: (
            _require_text(value.get("subject_ref"), "envelopes[].subject_ref"),
            _require_text(
                value.get("semantic_truth_hash"),
                "envelopes[].semantic_truth_hash",
            ),
            _require_text(value.get("envelope_id"), "envelopes[].envelope_id"),
        ),
    )


def _assert_no_raw_tenant_or_float(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        if "tenant_id" in value:
            raise ExportArtifactError(f"raw_tenant_id_forbidden:{path}")
        for key, child in value.items():
            _assert_no_raw_tenant_or_float(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_raw_tenant_or_float(child, f"{path}[{index}]")
        return
    if isinstance(value, float):
        raise ExportArtifactError(f"artifact_float_forbidden:{path}")


def _validate_envelopes(
    envelopes: list[dict[str, Any]],
    *,
    tenant_id_hash: str,
    key_registry: TrustKeyRegistry | None = None,
) -> None:
    if not 1 <= len(envelopes) <= MAX_EXPORT_ARTIFACT_ENVELOPES:
        raise ExportArtifactError("artifact_envelope_count_out_of_bounds")
    for envelope in envelopes:
        canonicalize_envelope_payload(envelope)
        if envelope.get("subject_type") != "match_verdict":
            raise ExportArtifactError("unsupported_export_subject_type")
        if envelope.get("tenant_id_hash") != tenant_id_hash:
            raise ExportArtifactError("artifact_envelope_tenant_mismatch")
        if key_registry is not None:
            result = verify_trust_envelope(
                envelope,
                key_registry=key_registry.public_only(),
            )
            if result.verification_status != "verified":
                raise ExportArtifactError(
                    f"embedded_envelope_verification_failed:{result.reason_code}"
                )


def build_export_artifact(
    *,
    envelopes: Iterable[dict[str, Any]],
    tenant_id_hash: str,
    generated_at: datetime,
    protocol: "ExportArtifactProtocol | None" = None,
) -> dict[str, Any]:
    """Build deterministic unsigned artifact content from complete envelopes.

    ``protocol`` exists so historical-protocol fixtures can be constructed by
    the test suite through the same production framing code that would have
    produced them originally. Production issuance always uses the active
    protocol default.
    """
    resolved = protocol or ACTIVE_EXPORT_ARTIFACT_PROTOCOL
    ordered = _ordered_envelopes(envelopes)
    _validate_envelopes(ordered, tenant_id_hash=tenant_id_hash)
    artifact = {
        "artifact_schema_version": resolved.schema_version,
        "canonicalization_version": resolved.canonicalization_version,
        "artifact_signing_domain": resolved.signing_domain_label,
        "envelopes": ordered,
        "generated_at": _utc_second(generated_at),
        "tenant_id_hash": tenant_id_hash,
    }
    _assert_no_raw_tenant_or_float(artifact)
    return artifact


def _artifact_identity_bytes_v1(payload: dict[str, Any]) -> bytes:
    """Frozen v1 identity framing: signer metadata participates in identity.

    Retained verbatim from the pre-second-corrective implementation so artifacts
    issued under the original ``v1`` markers keep exactly one interpretation and
    remain verifiable. Do not modify: changing this function silently
    reinterprets already-issued artifacts, which is the defect this registry
    exists to prevent.
    """
    required = _BASE_FIELDS | {"signing_key_id", "signing_algorithm"}
    if not required.issubset(payload):
        raise ExportArtifactError("artifact_identity_fields_missing")
    envelopes = _ordered_envelopes(payload["envelopes"])
    pieces = [
        _frame(
            "artifact_schema_version",
            _require_text(
                payload["artifact_schema_version"], "artifact_schema_version"
            ).encode("utf-8"),
        ),
        _frame(
            "canonicalization_version",
            _require_text(
                payload["canonicalization_version"], "canonicalization_version"
            ).encode("utf-8"),
        ),
        _frame(
            "artifact_signing_domain",
            _require_text(
                payload["artifact_signing_domain"], "artifact_signing_domain"
            ).encode("utf-8"),
        ),
        _frame(
            "generated_at",
            _require_text(payload["generated_at"], "generated_at").encode("utf-8"),
        ),
        _frame(
            "tenant_id_hash",
            _require_text(payload["tenant_id_hash"], "tenant_id_hash").encode("utf-8"),
        ),
        _frame(
            "signing_key_id",
            _require_text(payload["signing_key_id"], "signing_key_id").encode("utf-8"),
        ),
        _frame(
            "signing_algorithm",
            _require_text(payload["signing_algorithm"], "signing_algorithm").encode(
                "utf-8"
            ),
        ),
        _frame("envelope_count", str(len(envelopes)).encode("ascii")),
    ]
    pieces.extend(
        _frame(f"envelopes[{index}]", canonicalize_envelope_payload(envelope))
        for index, envelope in enumerate(envelopes)
    )
    return b"".join(pieces)


def _export_artifact_signature_material_v1(
    artifact_hash: str,
    *,
    signing_key_id: str,
    signing_algorithm: str,
) -> bytes:
    """Frozen v1 signature material: domain plus the raw artifact hash bytes.

    Signer identity is already inside the v1 artifact hash, so it is not framed
    again here. Parameters are accepted for a uniform dispatch signature.
    """
    del signing_key_id, signing_algorithm
    return EXPORT_ARTIFACT_SIGNING_DOMAIN_V1 + artifact_hash.encode("ascii")


def _artifact_identity_bytes_v2(payload: dict[str, Any]) -> bytes:
    """Active v2 identity framing: signer-independent artifact identity.

    Signer metadata is deliberately excluded here and bound in the signature
    material instead, so re-signing identical content under a rotated key leaves
    ``artifact_hash`` stable while ``signature_hash`` and ``signature`` change.
    """
    if not _BASE_FIELDS.issubset(payload):
        raise ExportArtifactError("artifact_identity_fields_missing")
    envelopes = _ordered_envelopes(payload["envelopes"])
    pieces = [
        _frame(
            "artifact_schema_version",
            _require_text(
                payload["artifact_schema_version"], "artifact_schema_version"
            ).encode("utf-8"),
        ),
        _frame(
            "canonicalization_version",
            _require_text(
                payload["canonicalization_version"], "canonicalization_version"
            ).encode("utf-8"),
        ),
        _frame(
            "artifact_signing_domain",
            _require_text(
                payload["artifact_signing_domain"], "artifact_signing_domain"
            ).encode("utf-8"),
        ),
        _frame(
            "generated_at",
            _require_text(payload["generated_at"], "generated_at").encode("utf-8"),
        ),
        _frame(
            "tenant_id_hash",
            _require_text(payload["tenant_id_hash"], "tenant_id_hash").encode("utf-8"),
        ),
        _frame("envelope_count", str(len(envelopes)).encode("ascii")),
    ]
    pieces.extend(
        _frame(f"envelopes[{index}]", canonicalize_envelope_payload(envelope))
        for index, envelope in enumerate(envelopes)
    )
    return b"".join(pieces)


def _export_artifact_signature_material_v2(
    artifact_hash: str,
    *,
    signing_key_id: str,
    signing_algorithm: str,
) -> bytes:
    """Active v2 signature material: bind signer to signer-independent identity."""
    return b"".join(
        (
            EXPORT_ARTIFACT_SIGNING_DOMAIN_V2,
            _frame("artifact_hash", artifact_hash.encode("ascii")),
            _frame("signing_key_id", signing_key_id.encode("utf-8")),
            _frame("signing_algorithm", signing_algorithm.encode("utf-8")),
        )
    )


@dataclass(frozen=True)
class ExportArtifactProtocol:
    """One immutable version tuple bound to exactly one algorithm."""

    schema_version: str
    canonicalization_version: str
    signing_domain: bytes
    signing_domain_label: str
    identity_bytes: Any
    signature_material: Any
    issuable: bool


EXPORT_ARTIFACT_PROTOCOL_V1 = ExportArtifactProtocol(
    schema_version=EXPORT_ARTIFACT_SCHEMA_VERSION_V1,
    canonicalization_version=EXPORT_ARTIFACT_CANONICALIZATION_VERSION_V1,
    signing_domain=EXPORT_ARTIFACT_SIGNING_DOMAIN_V1,
    signing_domain_label=EXPORT_ARTIFACT_SIGNING_DOMAIN_LABEL_V1,
    identity_bytes=_artifact_identity_bytes_v1,
    signature_material=_export_artifact_signature_material_v1,
    # Verification-only: historical artifacts stay verifiable, but nothing new
    # may be issued under the superseded framing.
    issuable=False,
)

EXPORT_ARTIFACT_PROTOCOL_V2 = ExportArtifactProtocol(
    schema_version=EXPORT_ARTIFACT_SCHEMA_VERSION_V2,
    canonicalization_version=EXPORT_ARTIFACT_CANONICALIZATION_VERSION_V2,
    signing_domain=EXPORT_ARTIFACT_SIGNING_DOMAIN_V2,
    signing_domain_label=EXPORT_ARTIFACT_SIGNING_DOMAIN_LABEL_V2,
    identity_bytes=_artifact_identity_bytes_v2,
    signature_material=_export_artifact_signature_material_v2,
    issuable=True,
)

#: Keyed by ``(artifact_schema_version, canonicalization_version)``. The mapping
#: is a function: one tuple can never resolve to two algorithms.
EXPORT_ARTIFACT_PROTOCOLS: dict[tuple[str, str], ExportArtifactProtocol] = {
    (
        EXPORT_ARTIFACT_PROTOCOL_V1.schema_version,
        EXPORT_ARTIFACT_PROTOCOL_V1.canonicalization_version,
    ): EXPORT_ARTIFACT_PROTOCOL_V1,
    (
        EXPORT_ARTIFACT_PROTOCOL_V2.schema_version,
        EXPORT_ARTIFACT_PROTOCOL_V2.canonicalization_version,
    ): EXPORT_ARTIFACT_PROTOCOL_V2,
}

ACTIVE_EXPORT_ARTIFACT_PROTOCOL = EXPORT_ARTIFACT_PROTOCOL_V2


def resolve_export_artifact_protocol(
    schema_version: Any, canonicalization_version: Any
) -> ExportArtifactProtocol:
    """Dispatch a declared version tuple to its single governed algorithm."""
    if not isinstance(schema_version, str):
        raise ExportArtifactError("artifact_schema_version_unsupported")
    if not isinstance(canonicalization_version, str):
        raise ExportArtifactError("artifact_canonicalization_version_unsupported")
    protocol = EXPORT_ARTIFACT_PROTOCOLS.get((schema_version, canonicalization_version))
    if protocol is None:
        # Distinguish an unknown/mismatched protocol from ordinary artifact
        # corruption: a caller must never see `artifact_hash_mismatch` when the
        # real problem is that the version tuple is not a governed protocol.
        raise ExportArtifactError(
            "artifact_protocol_version_unsupported:"
            f"{schema_version}/{canonicalization_version}"
        )
    return protocol


def export_artifact_signature_material(
    artifact_hash: str,
    *,
    signing_key_id: str,
    signing_algorithm: str,
    protocol: ExportArtifactProtocol | None = None,
) -> bytes:
    """Return signature material under the active or an explicit protocol."""
    resolved = protocol or ACTIVE_EXPORT_ARTIFACT_PROTOCOL
    return resolved.signature_material(
        artifact_hash,
        signing_key_id=signing_key_id,
        signing_algorithm=signing_algorithm,
    )


def sign_export_artifact(
    payload: dict[str, Any],
    *,
    key_registry: TrustKeyRegistry,
    allow_historical_protocol: bool = False,
) -> dict[str, Any]:
    """Hash and sign an export with the P8 active key only.

    ``allow_historical_protocol`` is reserved for constructing historical
    protocol fixtures in the verification test suite. Production issuance never
    sets it, so a superseded protocol cannot be emitted by any route.
    """
    if set(payload) != _BASE_FIELDS:
        raise ExportArtifactError("unsigned_artifact_shape_invalid")
    key = key_registry.active_signing_key()
    if key.private_key is None:
        raise ExportArtifactError("active_signing_key_missing_private_material")
    signed = deepcopy(payload)
    signed["signing_key_id"] = key.kid
    signed["signing_algorithm"] = key.algorithm
    _validate_envelopes(
        signed["envelopes"],
        tenant_id_hash=_require_text(signed["tenant_id_hash"], "tenant_id_hash"),
        key_registry=key_registry,
    )
    protocol = resolve_export_artifact_protocol(
        signed["artifact_schema_version"], signed["canonicalization_version"]
    )
    if not protocol.issuable and not allow_historical_protocol:
        raise ExportArtifactError(
            f"artifact_protocol_not_issuable:{protocol.schema_version}"
        )
    signed["artifact_hash"] = compute_artifact_hash(protocol.identity_bytes(signed))
    signature_material = protocol.signature_material(
        _require_text(signed["artifact_hash"], "artifact_hash"),
        signing_key_id=key.kid,
        signing_algorithm=key.algorithm,
    )
    signed["signature_hash"] = compute_detached_signature_hash(signature_material)
    signed["signature"] = encode_ed25519_signature(
        key.private_key.sign(signature_material)
    )
    _assert_no_raw_tenant_or_float(signed)
    return signed


def verify_export_artifact(
    payload: dict[str, Any],
    *,
    key_registry: TrustKeyRegistry,
) -> ExportArtifactVerificationResult:
    """Verify artifact shape, embedded envelopes, hash, domain, and signature."""
    candidate = deepcopy(payload) if isinstance(payload, dict) else {}
    try:
        if set(candidate) != _SIGNED_FIELDS:
            raise ExportArtifactError("artifact_shape_invalid")
        # Dispatch on the declared version tuple before touching any framing, so
        # an unsupported/retired protocol reports that fact rather than
        # surfacing as generic hash corruption.
        protocol = resolve_export_artifact_protocol(
            candidate["artifact_schema_version"],
            candidate["canonicalization_version"],
        )
        if candidate["artifact_signing_domain"] != protocol.signing_domain_label:
            raise ExportArtifactError("artifact_signing_domain_mismatch")
        if candidate["signing_algorithm"] != "ed25519":
            raise ExportArtifactError("artifact_signing_algorithm_unsupported")
        _assert_no_raw_tenant_or_float(candidate)
        _validate_envelopes(
            candidate["envelopes"],
            tenant_id_hash=_require_text(candidate["tenant_id_hash"], "tenant_id_hash"),
            key_registry=key_registry,
        )
        expected_hash = compute_artifact_hash(protocol.identity_bytes(candidate))
        if candidate["artifact_hash"] != expected_hash:
            raise ExportArtifactError("artifact_hash_mismatch")
        signature_material = protocol.signature_material(
            expected_hash,
            signing_key_id=_require_text(candidate["signing_key_id"], "signing_key_id"),
            signing_algorithm=_require_text(
                candidate["signing_algorithm"], "signing_algorithm"
            ),
        )
        expected_signature_hash = compute_detached_signature_hash(signature_material)
        if candidate["signature_hash"] != expected_signature_hash:
            raise ExportArtifactError("signature_hash_mismatch")
        key = key_registry.verification_key(
            _require_text(candidate["signing_key_id"], "signing_key_id")
        )
        verify_ed25519_signature(
            key.public_key,
            _require_text(candidate["signature"], "signature"),
            signature_material,
        )
    except (
        ExportArtifactError,
        TrustEnvelopeSigningError,
        ValueError,
        TypeError,
    ) as exc:
        reason = str(exc)
        if not reason or len(reason) > 180:
            reason = "artifact_verification_failed"
        rejected_hash = candidate.get("artifact_hash")
        rejected_key_id = candidate.get("signing_key_id")
        return ExportArtifactVerificationResult(
            verification_status="rejected",
            reason_code=reason,
            artifact_hash=rejected_hash if isinstance(rejected_hash, str) else None,
            signing_key_id=(
                rejected_key_id if isinstance(rejected_key_id, str) else None
            ),
        )
    return ExportArtifactVerificationResult(
        verification_status="verified",
        reason_code=None,
        artifact_hash=_require_text(candidate["artifact_hash"], "artifact_hash"),
        signing_key_id=_require_text(candidate["signing_key_id"], "signing_key_id"),
    )
