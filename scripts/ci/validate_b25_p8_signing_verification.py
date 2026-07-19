#!/usr/bin/env python3
"""Validate B2.5-P8 TrustEnvelope signing, verification, JWKS, and downgrade defense."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import hmac
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.trust.hash_identity import (  # noqa: E402
    compute_artifact_hash,
    compute_semantic_truth_hash,
)
from app.trust.jwks import (  # noqa: E402
    TrustJWKSError,
    assert_jwks_public_only,
    build_jwks_response,
    registry_from_public_jwks,
)
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey  # noqa: E402
from app.trust.signing import sign_trust_envelope  # noqa: E402
from app.trust.signing import (  # noqa: E402
    encode_ed25519_signature,
    prepare_payload_for_signing,
    verify_ed25519_signature as _verify_ed25519_signature,
)
from app.trust.verification import verify_trust_envelope  # noqa: E402
from app.trust.canonicalization import (  # noqa: E402
    canonicalize_envelope_payload,
    canonicalize_signature_material,
)
import time as _time  # noqa: E402


class B25P8ValidationError(RuntimeError):
    """Raised when P8 validation fails."""


EXAMPLES = ROOT / "contracts/trust-api/examples"
SIGNING_TIME = datetime(2026, 6, 24, 10, 0, 2, tzinfo=timezone.utc)
VERIFY_TIME = datetime(2026, 6, 24, 10, 5, 0, tzinfo=timezone.utc)
P8_RUNTIME_PATHS = (
    ROOT / "backend/app/trust/schema_verification.py",
    ROOT / "backend/app/trust/key_registry.py",
    ROOT / "backend/app/trust/signing.py",
    ROOT / "backend/app/trust/verification.py",
    ROOT / "backend/app/trust/jwks.py",
    ROOT / "backend/app/api/trust_keys.py",
)
P8_WORKFLOW = ROOT / ".github/workflows/b2_5-p8-signing-verification.yml"
MAKEFILE = ROOT / "Makefile"
ENFORCER_REGISTRY = ROOT / "docs/ci/enforcer_registry.yaml"
GATE_MATRIX = ROOT / "docs/ci/gate_subsumption_matrix.yaml"
EVIDENCE_PACK = ROOT / "docs/forensics/B2.5-P8 Remediation Evidence Pack.md"
FORBIDDEN_LLM_IMPORTS = ("app.llm", "backend.app.llm", "openai", "anthropic")
FORBIDDEN_DYNAMIC_NAMES = {"importlib", "__import__", "pkg_resources"}
FORBIDDEN_DISPATCH_TOKENS = {
    "asyncio.create_task",
    "asyncio.ensure_future",
    "ThreadPoolExecutor",
    "ProcessPoolExecutor",
    "Celery",
    ".delay(",
    ".apply_async(",
}
FORBIDDEN_LATER_PHASE_RUNTIME_TOKENS = (
    "/trust/v1/envelopes",
    "/trust/v1/verify",
    "machine_caller",
    "agent_client",
    "rate_limit",
    "mcp",
    "export_trust",
    "trust.action.execute",
)


def _private_key(label: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(label.encode()).digest())


def _key(
    kid: str,
    *,
    label: str,
    state: str = "active",
    valid_from: datetime = SIGNING_TIME - timedelta(days=1),
    valid_until: datetime | None = SIGNING_TIME + timedelta(days=30),
    retired_at: datetime | None = None,
) -> TrustSigningKey:
    private_key = _private_key(label)
    return TrustSigningKey(
        kid=kid,
        algorithm="ed25519",
        public_key=private_key.public_key(),
        private_key=private_key if state == "active" else None,
        state=state,  # type: ignore[arg-type]
        valid_from=valid_from,
        valid_until=valid_until,
        retired_at=retired_at if state == "verification_only" else None,
    )


def _registry() -> TrustKeyRegistry:
    return TrustKeyRegistry(
        (
            _key("kid:b25-p8-active-a", label="b25-p8-active-a"),
            _key(
                "kid:b25-p8-verify-old",
                label="b25-p8-verify-old",
                state="verification_only",
                retired_at=SIGNING_TIME,
            ),
        )
    )


def _fixture(name: str = "revenue_claim_valid_with_verified_revenue_minor.json") -> dict[str, Any]:
    payload = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    payload["created_at"] = "2026-06-24T10:00:02Z"
    payload["valid_until"] = "2026-06-25T10:00:02Z"
    return payload


def _signed_payload(name: str = "revenue_claim_valid_with_verified_revenue_minor.json") -> dict[str, Any]:
    return sign_trust_envelope(_fixture(name), key_registry=_registry())


def _set_path(payload: dict[str, Any], path: str, value: Any) -> None:
    target: Any = payload
    parts = path.split(".")
    for part in parts[:-1]:
        target = target[part[:-3]][0] if part.endswith("[0]") else target[part]
    final = parts[-1]
    if final.endswith("[0]"):
        target[final[:-3]][0] = value
    else:
        target[final] = value


def validate_positive_signing() -> tuple[int, int]:
    registry = _registry()
    signed = sign_trust_envelope(_fixture(), key_registry=registry)
    public_registry = registry_from_public_jwks(build_jwks_response(registry))
    result = verify_trust_envelope(
        signed,
        key_registry=public_registry,
        at_time=VERIFY_TIME,
    )
    if result.verification_status != "verified":
        raise B25P8ValidationError(f"public verification failed: {result}")
    if not signed["signature"].startswith("ed25519:"):
        raise B25P8ValidationError("signature prefix is not envelope Ed25519")
    if signed["semantic_truth_hash"] != compute_semantic_truth_hash(signed):
        raise B25P8ValidationError("semantic_truth_hash not recomputed")
    return 3, 3


def validate_hmac_jwt_rejection() -> tuple[int, int]:
    signed = _signed_payload()
    hmac_fake = copy.deepcopy(signed)
    hmac_fake["signature"] = "hmac-sha256:" + hmac.new(
        b"secret",
        json.dumps(signed, sort_keys=True).encode(),
        hashlib.sha256,
    ).hexdigest()
    jwt_fake = copy.deepcopy(signed)
    jwt_fake["signature"] = jwt.encode(
        {"signature_hash": signed["signature_hash"]},
        "secret",
        algorithm="HS256",
    )
    counts = [0, 0]
    for index, payload in enumerate((hmac_fake, jwt_fake)):
        result = verify_trust_envelope(
            payload,
            key_registry=_registry().public_only(),
            at_time=VERIFY_TIME,
        )
        if result.verification_status != "rejected":
            raise B25P8ValidationError("HMAC/JWT fake signature verified")
        counts[index] += 1
    return counts[0], counts[1]


def validate_tamper_controls() -> tuple[int, int, int, int]:
    vectors: tuple[tuple[str, Any], ...] = (
        ("verified_revenue_minor", 99999),
        ("currency", "EUR"),
        ("deterministic_verification_status", "disputed"),
        ("confidence_metadata.confidence_status", "available"),
        ("benchmark_metadata.benchmark_status", "available"),
        ("policy_action_authority.policy_state", "approval_required"),
        ("provenance_chain[0].source_snapshot_hash", "sha256:" + "a" * 64),
        ("audit_ref", "urn:skeldir:audit:tampered"),
        ("audit_hash", "sha256:" + "b" * 64),
        ("subject_type", "attribution_result"),
        ("subject_ref", "urn:skeldir:revenue_claim:tampered"),
        ("tenant_id_hash", "sha256:" + "c" * 64),
        ("created_at", "2026-06-24T10:10:02Z"),
        ("valid_until", "2026-06-25T11:00:02Z"),
        ("schema_version", "trust-envelope-schema-v0"),
        ("canonicalization_version", "trust-canonical-json-v999"),
        ("semantic_truth_hash", "sha256:" + "d" * 64),
        ("signature_hash", "sha256:" + "e" * 64),
        ("signing_algorithm", "HS256"),
        ("signing_key_id", "kid:b25-p8-unknown"),
        ("fallback_applied", True),
        ("fallback_reason", "policy_denied"),
    )
    tamper_controls = policy_controls = provenance_controls = audit_controls = 0
    for path, value in vectors:
        payload = _signed_payload()
        _set_path(payload, path, value)
        result = verify_trust_envelope(
            payload,
            key_registry=_registry().public_only(),
            at_time=VERIFY_TIME,
        )
        if result.verification_status != "rejected":
            raise B25P8ValidationError(f"tamper verified unexpectedly: {path}")
        tamper_controls += 1
        if path.startswith("policy_action_authority"):
            policy_controls += 1
        if path.startswith("provenance_chain"):
            provenance_controls += 1
        if path.startswith("audit_"):
            audit_controls += 1

    match_payload = _signed_payload("deterministic_only_verified.json")
    match_payload["match_verdict_status"] = "unmatched"
    if (
        verify_trust_envelope(
            match_payload,
            key_registry=_registry().public_only(),
            at_time=VERIFY_TIME,
        ).verification_status
        != "rejected"
    ):
        raise B25P8ValidationError("match_verdict_status tamper verified")
    tamper_controls += 1

    artifact_fixture = _fixture("artifact_pruned_degraded.json")
    artifact_fixture["artifact_ref"] = "urn:skeldir:artifact:p8_fixture"
    artifact_fixture["artifact_hash"] = compute_artifact_hash(b"artifact-p8")
    artifact_signed = sign_trust_envelope(artifact_fixture, key_registry=_registry())
    for field, value in (
        ("artifact_ref", "urn:skeldir:artifact:tampered"),
        ("artifact_hash", compute_artifact_hash(b"artifact-tampered")),
    ):
        tampered = copy.deepcopy(artifact_signed)
        tampered[field] = value
        if (
            verify_trust_envelope(
                tampered,
                key_registry=_registry().public_only(),
                at_time=VERIFY_TIME,
            ).verification_status
            != "rejected"
        ):
            raise B25P8ValidationError(f"{field} tamper verified")
        tamper_controls += 1
    return tamper_controls, policy_controls, provenance_controls, audit_controls


def validate_key_rotation() -> tuple[int, int, int]:
    key_a = _key("kid:b25-p8-active-a", label="b25-p8-active-a")
    key_b = _key("kid:b25-p8-active-b", label="b25-p8-active-b")
    signed_a = sign_trust_envelope(_fixture(), key_registry=TrustKeyRegistry((key_a,)))
    signed_b = sign_trust_envelope(_fixture(), key_registry=TrustKeyRegistry((key_b,)))
    public_registry = TrustKeyRegistry((key_a.public_only(), key_b.public_only()))
    if signed_a["semantic_truth_hash"] != signed_b["semantic_truth_hash"]:
        raise B25P8ValidationError("key rotation changed semantic_truth_hash")
    if signed_a["signature_hash"] == signed_b["signature_hash"]:
        raise B25P8ValidationError("key rotation did not change signature_hash")
    for payload in (signed_a, signed_b):
        result = verify_trust_envelope(
            payload,
            key_registry=public_registry,
            at_time=VERIFY_TIME,
        )
        if result.verification_status != "verified":
            raise B25P8ValidationError(f"historical key verification failed: {result}")
    revoked = TrustKeyRegistry(
        (_key("kid:b25-p8-active-a", label="b25-p8-active-a", state="revoked"),)
    )
    if (
        verify_trust_envelope(
            signed_a,
            key_registry=revoked.public_only(),
            at_time=VERIFY_TIME,
        ).verification_status
        != "rejected"
    ):
        raise B25P8ValidationError("revoked key verified")
    return 3, 2, 1


def validate_temporal_and_downgrade_controls() -> tuple[int, int, int, int]:
    signed = _signed_payload()
    schema_controls = canonical_controls = signature_controls = algorithm_controls = 0
    cases: tuple[tuple[str, Any, str], ...] = (
        ("schema_version", None, "schema"),
        ("schema_version", "v0", "schema"),
        ("schema_version", "trust-envelope-schema-v999", "schema"),
        ("canonicalization_version", None, "canonical"),
        ("canonicalization_version", "trust-canonical-json-v999", "canonical"),
        ("signing_algorithm", None, "algorithm"),
        ("signing_algorithm", "HMAC", "algorithm"),
        ("signing_algorithm", "RS256", "algorithm"),
        ("signing_key_id", None, "signature"),
        ("signature", None, "signature"),
    )
    for field, value, bucket in cases:
        payload = copy.deepcopy(signed)
        if value is None:
            payload.pop(field, None)
        else:
            payload[field] = value
        result = verify_trust_envelope(
            payload,
            key_registry=_registry().public_only(),
            at_time=VERIFY_TIME,
        )
        if result.verification_status != "rejected":
            raise B25P8ValidationError(f"downgrade accepted: {field}")
        if bucket == "schema":
            schema_controls += 1
        elif bucket == "canonical":
            canonical_controls += 1
        elif bucket == "signature":
            signature_controls += 1
        elif bucket == "algorithm":
            algorithm_controls += 1

    if (
        verify_trust_envelope(
            signed,
            key_registry=_registry().public_only(),
            at_time=datetime(2026, 6, 26, tzinfo=timezone.utc),
        ).reason_code
        != "envelope_expired"
    ):
        raise B25P8ValidationError("expired envelope did not fail closed")
    signature_controls += 1
    return schema_controls, canonical_controls, signature_controls, algorithm_controls


def validate_temporal_forgery_and_dos_controls() -> tuple[int, int, int]:
    """Negative controls for retired-key temporal forgery and DoS short-circuit."""
    temporal_controls = dos_controls = historical_controls = 0

    retired_key = _key(
        "kid:b25-p8-verify-old",
        label="b25-p8-verify-old",
        state="verification_only",
        retired_at=SIGNING_TIME,
    )
    active_key = _key("kid:b25-p8-active-a", label="b25-p8-active-a")
    verify_registry = TrustKeyRegistry(
        (active_key.public_only(), retired_key.public_only())
    )

    payload = _fixture()
    payload["created_at"] = "2026-06-25T10:00:02Z"
    payload["valid_until"] = "2026-06-26T10:00:02Z"
    prepared = prepare_payload_for_signing(
        payload,
        signing_key_id="kid:b25-p8-verify-old",
        signing_algorithm="ed25519",
    )
    material = canonicalize_signature_material(prepared)
    private_key = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"b25-p8-verify-old").digest()
    )
    prepared["signature"] = encode_ed25519_signature(private_key.sign(material))
    canonicalize_envelope_payload(prepared)

    forgery_result = verify_trust_envelope(
        prepared,
        key_registry=verify_registry,
        at_time=datetime(2026, 6, 25, 10, 5, 0, tzinfo=timezone.utc),
    )
    if forgery_result.verification_status != "rejected":
        raise B25P8ValidationError("retired key forged net-new envelope")
    if forgery_result.reason_code != "temporal_forgery_rejected:created_after_key_retirement":
        raise B25P8ValidationError(
            f"temporal forgery wrong reason: {forgery_result.reason_code}"
        )
    temporal_controls += 1

    historical_payload = _fixture()
    historical_payload["created_at"] = "2026-06-24T10:00:02Z"
    historical_payload["valid_until"] = "2026-06-25T10:00:02Z"
    historical_prepared = prepare_payload_for_signing(
        historical_payload,
        signing_key_id="kid:b25-p8-verify-old",
        signing_algorithm="ed25519",
    )
    historical_material = canonicalize_signature_material(historical_prepared)
    historical_prepared["signature"] = encode_ed25519_signature(
        private_key.sign(historical_material)
    )
    canonicalize_envelope_payload(historical_prepared)
    historical_result = verify_trust_envelope(
        historical_prepared,
        key_registry=verify_registry,
        at_time=VERIFY_TIME,
    )
    if historical_result.verification_status != "verified":
        raise B25P8ValidationError("historical envelope from retired key rejected")
    historical_controls += 1

    signed = _signed_payload()
    for bad_value in ("trust-envelope-schema-v999", None):
        bad = copy.deepcopy(signed)
        if bad_value is None:
            bad.pop("schema_version", None)
        else:
            bad["schema_version"] = bad_value
        crypto_calls: list[int] = []
        original_verify = _verify_ed25519_signature

        def spy(public_key: Any, signature: str, mat: bytes) -> None:
            crypto_calls.append(1)
            return original_verify(public_key, signature, mat)

        import app.trust.verification as _vmod
        _orig_attr = _vmod.verify_ed25519_signature
        _vmod.verify_ed25519_signature = spy
        try:
            start = _time.perf_counter()
            result = verify_trust_envelope(
                bad,
                key_registry=_registry().public_only(),
                at_time=VERIFY_TIME,
            )
            elapsed_ms = (_time.perf_counter() - start) * 1000
        finally:
            _vmod.verify_ed25519_signature = _orig_attr
        if result.verification_status != "rejected":
            raise B25P8ValidationError(f"invalid schema accepted: {bad_value}")
        if len(crypto_calls) != 0:
            raise B25P8ValidationError(
                f"crypto called for invalid schema: {bad_value}"
            )
        if elapsed_ms >= 1000:
            raise B25P8ValidationError(
                f"schema rejection too slow: {elapsed_ms}ms"
            )
        dos_controls += 1

    return temporal_controls, historical_controls, dos_controls


def validate_jwks_public_only() -> tuple[int, int]:
    jwks = build_jwks_response(_registry())
    public_count = assert_jwks_public_only(jwks)
    text = json.dumps(jwks, sort_keys=True).lower()
    for token in ("private", "seed", "secret", "scalar"):
        if token in text:
            raise B25P8ValidationError(f"JWKS leaked token: {token}")
    bad = copy.deepcopy(jwks)
    bad["keys"][0]["d"] = "private-scalar"
    try:
        assert_jwks_public_only(bad)
    except TrustJWKSError:
        return public_count, 1
    raise B25P8ValidationError("private-key JWKS negative control passed")


def _imports_for(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def validate_scope_boundary() -> tuple[int, int, int, int]:
    scope_controls = llm_controls = dynamic_controls = dispatch_controls = 0
    for path in P8_RUNTIME_PATHS:
        text = path.read_text(encoding="utf-8")
        imports = _imports_for(path)
        if any(
            module == forbidden or module.startswith(f"{forbidden}.")
            for module in imports
            for forbidden in FORBIDDEN_LLM_IMPORTS
        ):
            raise B25P8ValidationError(f"forbidden LLM import in {path}")
        llm_controls += 1
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_DYNAMIC_NAMES:
                        raise B25P8ValidationError(f"dynamic import in {path}")
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(
                    node.func, "attr", None
                )
                if name in {"__import__", "import_module"}:
                    raise B25P8ValidationError(f"dynamic import call in {path}")
        dynamic_controls += 1
        for token in FORBIDDEN_DISPATCH_TOKENS:
            if token in text:
                raise B25P8ValidationError(f"compute dispatch token {token} in {path}")
        dispatch_controls += 1
    runtime_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "backend/app/api").glob("*.py")
    )
    for token in FORBIDDEN_LATER_PHASE_RUNTIME_TOKENS:
        if token in runtime_text:
            raise B25P8ValidationError(f"P9/P10/P11 scope token present: {token}")
    scope_controls += len(FORBIDDEN_LATER_PHASE_RUNTIME_TOKENS)
    for path in (P8_WORKFLOW, MAKEFILE, ENFORCER_REGISTRY, GATE_MATRIX, EVIDENCE_PACK):
        if not path.exists():
            raise B25P8ValidationError(f"missing P8 wiring/evidence path: {path}")
    scope_controls += 5
    return scope_controls, llm_controls, dynamic_controls, dispatch_controls


def run_pytest() -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "backend/tests/trust/test_b25_p8_signing_verification.py", "-q"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=300,
    )
    if proc.returncode != 0:
        raise B25P8ValidationError(
            f"P8 pytest failed stdout={proc.stdout[-1500:]} stderr={proc.stderr[-1500:]}"
        )
    return 1


def validate_all(*, include_pytest: bool) -> None:
    asymmetric_controls, public_controls = validate_positive_signing()
    hmac_controls, jwt_controls = validate_hmac_jwt_rejection()
    (
        tamper_controls,
        policy_controls,
        provenance_controls,
        audit_controls,
    ) = validate_tamper_controls()
    rotation_controls, historical_controls, revoked_controls = validate_key_rotation()
    (
        schema_controls,
        canonical_controls,
        signature_controls,
        algorithm_controls,
    ) = validate_temporal_and_downgrade_controls()
    temporal_controls, historical_controls, dos_controls = (
        validate_temporal_forgery_and_dos_controls()
    )
    jwks_controls, private_controls = validate_jwks_public_only()
    (
        scope_controls,
        llm_controls,
        dynamic_controls,
        dispatch_controls,
    ) = validate_scope_boundary()
    pytest_controls = run_pytest() if include_pytest else 0
    print("B25_P8_SIGNING_VERIFICATION_VALIDATION_PASS")
    print(f"asymmetric_signer_controls_passed={asymmetric_controls}")
    print(f"public_verification_controls_passed={public_controls}")
    print(f"hmac_external_signature_rejection_controls_passed={hmac_controls}")
    print(f"jwt_signature_confusion_rejection_controls_passed={jwt_controls}")
    print(f"load_bearing_tamper_controls_passed={tamper_controls}")
    print(f"policy_signature_binding_controls_passed={policy_controls}")
    print(f"provenance_signature_binding_controls_passed={provenance_controls}")
    print(f"audit_signature_binding_controls_passed={audit_controls}")
    print(f"key_rotation_semantic_identity_controls_passed={rotation_controls}")
    print(f"historical_key_verification_controls_passed={historical_controls}")
    print(f"revoked_key_rejection_controls_passed={revoked_controls}")
    print(f"jwks_public_only_controls_passed={jwks_controls}")
    print(f"private_key_exposure_negative_controls_passed={private_controls}")
    print(f"schema_downgrade_rejection_controls_passed={schema_controls}")
    print(f"canonicalization_version_rejection_controls_passed={canonical_controls}")
    print(f"signature_version_rejection_controls_passed={signature_controls}")
    print(f"unsupported_algorithm_rejection_controls_passed={algorithm_controls}")
    print(f"temporal_forgery_rejection_controls_passed={temporal_controls}")
    print(f"retired_key_historical_verification_controls_passed={historical_controls}")
    print(f"dos_short_circuit_controls_passed={dos_controls}")
    print(f"p8_scope_boundary_controls_passed={scope_controls}")
    print(f"no_llm_signing_path_controls_passed={llm_controls}")
    print(f"no_dynamic_import_signing_path_controls_passed={dynamic_controls}")
    print(f"no_compute_dispatch_signing_path_controls_passed={dispatch_controls}")
    print(f"pytest_controls_passed={pytest_controls}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args()
    try:
        validate_all(include_pytest=not args.skip_pytest)
    except Exception as exc:
        print(f"B25_P8_SIGNING_VERIFICATION_VALIDATION_FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
