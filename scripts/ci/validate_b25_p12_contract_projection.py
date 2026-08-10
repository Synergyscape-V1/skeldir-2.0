#!/usr/bin/env python3
"""B2.5-P12-P0 contract-projection gate.

The defect this closes
----------------------
Protected main issued export artifacts under protocol **v2** while the
authoritative ``POST /api/trust/v1/exports/match-verdicts`` 200 response still
resolved to a **v1-only** schema. Every phase-local validator passed: the
manifest said v2, and the v1 example validated against the v1 schema. Nothing
validated *what the server actually emits* against *what the contract actually
publishes*.

That is the general failure mode P12-H01 names: proof was fragmented rather than
compositional. This gate is the composition.

What it proves
--------------
1. A real artifact, produced by the production issuance path, validates with
   zero errors against the schema resolved from the canonical OpenAPI 200
   response for the machine export route.
2. The active protocol is exactly one protocol, and it is the one the runtime
   registry marks issuable.
3. Historical protocols remain published as verification-only and are never
   advertised as a successful issuance response.
4. Examples are lifecycle-classified: an active-issuance example validates
   against the active schema, and a historical example validates against its own
   historical schema and *fails* the active one.

Why it builds a live artifact rather than reading a fixture
-----------------------------------------------------------
A fixture proves what someone wrote down. Calling ``build_export_artifact`` and
``sign_export_artifact`` proves what the code emits. The defect existed
precisely because a fixture agreed with a schema while the runtime did not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "contracts/trust-api"
TRUST_OPENAPI = SCHEMA_DIR / "trust-api.openapi.yaml"
HASH_MANIFEST = SCHEMA_DIR / "hash-domain-manifest.v1.yaml"
ARTIFACT_MODULE = ROOT / "backend/app/trust/export_artifact.py"

MACHINE_EXPORT_PATH = "/api/trust/v1/exports/match-verdicts"

ACTIVE_ARTIFACT_SCHEMA = "export-artifact.v2.yaml"
HISTORICAL_ARTIFACT_SCHEMAS = ("export-artifact.v1.yaml",)

ACTIVE_EXAMPLE = SCHEMA_DIR / "examples/export_artifact_signed_valid_v2.json"
HISTORICAL_EXAMPLE = SCHEMA_DIR / "examples/export_artifact_signed_valid.json"

LIFECYCLE_KEY = "x-skeldir-protocol-lifecycle"
LIFECYCLE_ACTIVE = "active_issuance"
LIFECYCLE_HISTORICAL = "verification_only"


class B25P12ProjectionError(RuntimeError):
    """Raised when the published contract and the runtime disagree."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise B25P12ProjectionError(reason)


def _load(path: Path, overrides: dict[Path, str] | None = None) -> Any:
    overrides = overrides or {}
    if path in overrides:
        text = overrides[path]
    else:
        text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def _schema_registry(overrides: dict[Path, str] | None = None) -> Registry:
    """Resolve sibling ``$ref`` filenames the way the contract tree uses them."""
    registry = Registry()
    for path in (*SCHEMA_DIR.glob("*.yaml"), *SCHEMA_DIR.glob("*.json")):
        document = _load(path, overrides)
        if not isinstance(document, dict):
            continue
        resource = DRAFT202012.create_resource(document)
        registry = registry.with_resource(path.name, resource)
        identifier = document.get("$id")
        if isinstance(identifier, str) and identifier:
            registry = registry.with_resource(identifier, resource)
    return registry


def resolve_success_response_schema_ref(
    overrides: dict[Path, str] | None = None,
) -> str:
    """Return the ``$ref`` the OpenAPI publishes for a successful machine export."""
    spec = _load(TRUST_OPENAPI, overrides)
    paths = spec.get("paths") or {}
    _require(
        MACHINE_EXPORT_PATH in paths,
        f"machine_export_path_missing:{MACHINE_EXPORT_PATH}",
    )
    operation = (paths[MACHINE_EXPORT_PATH] or {}).get("post")
    _require(isinstance(operation, dict), "machine_export_post_operation_missing")
    response = (operation.get("responses") or {}).get("200") or {}
    media = (response.get("content") or {}).get("application/json") or {}
    schema = media.get("schema") or {}
    ref = schema.get("$ref")
    _require(
        isinstance(ref, str) and bool(ref), "machine_export_200_schema_ref_missing"
    )
    return ref


def build_live_artifact() -> dict[str, Any]:
    """Issue an artifact through the real production path, not a fixture."""
    sys.path.insert(0, str(ROOT / "backend"))
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from app.trust.export_artifact import (  # noqa: PLC0415
        build_export_artifact,
        sign_export_artifact,
    )
    from app.trust.key_registry import (
        TrustKeyRegistry,
        TrustSigningKey,
    )  # noqa: PLC0415
    from app.trust.signing import sign_trust_envelope  # noqa: PLC0415

    private = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"b25-p12-contract-projection-probe").digest()
    )
    registry = TrustKeyRegistry(
        (
            TrustSigningKey(
                kid="kid:b25-p12-projection-probe",
                algorithm="ed25519",
                public_key=private.public_key(),
                private_key=private,
                state="active",
                valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        )
    )

    def _utc(value: datetime) -> str:
        return (
            value.astimezone(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    issued = datetime.now(timezone.utc)
    envelope = json.loads(
        (SCHEMA_DIR / "examples/deterministic_only_verified.json").read_text(
            encoding="utf-8"
        )
    )
    envelope["created_at"] = _utc(issued)
    envelope["valid_until"] = _utc(issued + timedelta(days=1))
    signed_envelope = sign_trust_envelope(envelope, key_registry=registry)

    unsigned = build_export_artifact(
        envelopes=[signed_envelope],
        tenant_id_hash=str(signed_envelope["tenant_id_hash"]),
        generated_at=issued,
    )
    return sign_export_artifact(unsigned, key_registry=registry)


def validate_projection(overrides: dict[Path, str] | None = None) -> dict[str, int]:
    """Compose runtime issuance against the published success-response schema."""
    counters = {
        "response_schema_composition_controls": 0,
        "protocol_lifecycle_controls": 0,
        "example_lifecycle_controls": 0,
        "runtime_registry_controls": 0,
    }
    registry = _schema_registry(overrides)

    # --- 1. Live artifact validates against the PUBLISHED success schema -----
    published_ref = resolve_success_response_schema_ref(overrides)
    schema_path = SCHEMA_DIR / published_ref
    _require(schema_path.exists(), f"published_response_schema_missing:{published_ref}")
    published_schema = _load(schema_path, overrides)

    artifact = build_live_artifact()
    errors = sorted(
        Draft202012Validator(published_schema, registry=registry).iter_errors(artifact),
        key=lambda error: list(error.path),
    )
    if errors:
        detail = "; ".join(
            f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors[:4]
        )
        raise B25P12ProjectionError(
            f"live_response_does_not_validate_against_published_schema:{detail}"
        )
    counters["response_schema_composition_controls"] += 1

    # The published schema must be the ACTIVE one, not merely any schema the
    # live artifact happens to satisfy.
    _require(
        published_ref == ACTIVE_ARTIFACT_SCHEMA,
        f"success_response_not_bound_to_active_schema:{published_ref}",
    )
    counters["response_schema_composition_controls"] += 1

    # --- 2. Lifecycle classification is explicit and singular ---------------
    active_schema = _load(SCHEMA_DIR / ACTIVE_ARTIFACT_SCHEMA, overrides)
    _require(
        active_schema.get(LIFECYCLE_KEY) == LIFECYCLE_ACTIVE,
        "active_schema_missing_active_lifecycle_marker",
    )
    counters["protocol_lifecycle_controls"] += 1
    for historical in HISTORICAL_ARTIFACT_SCHEMAS:
        historical_schema = _load(SCHEMA_DIR / historical, overrides)
        _require(
            historical_schema.get(LIFECYCLE_KEY) == LIFECYCLE_HISTORICAL,
            f"historical_schema_not_marked_verification_only:{historical}",
        )
        _require(
            published_ref != historical,
            f"historical_schema_published_as_success_response:{historical}",
        )
        counters["protocol_lifecycle_controls"] += 1

    # --- 3. Runtime registry agrees with the contract ------------------------
    manifest = _load(HASH_MANIFEST, overrides)
    rows = manifest.get("export_artifact_protocol_registry") or []
    _require(bool(rows), "artifact_protocol_registry_missing")
    active_rows = [row for row in rows if row.get("support_status") == "active"]
    _require(
        len(active_rows) == 1,
        f"expected_exactly_one_active_protocol:{len(active_rows)}",
    )
    active_row = active_rows[0]
    _require(
        active_row.get("artifact_schema_version")
        == active_schema["properties"]["artifact_schema_version"]["const"],
        "manifest_active_version_disagrees_with_active_schema",
    )
    _require(
        active_row.get("canonicalization_version")
        == active_schema["properties"]["canonicalization_version"]["const"],
        "manifest_active_canonicalization_disagrees_with_active_schema",
    )
    counters["runtime_registry_controls"] += 1

    # The emitted artifact must carry the active tuple, which is what makes the
    # schema binding meaningful rather than coincidental.
    _require(
        artifact["artifact_schema_version"] == active_row["artifact_schema_version"],
        "runtime_artifact_version_is_not_the_active_protocol",
    )
    counters["runtime_registry_controls"] += 1

    # --- 4. Examples are lifecycle-aware ------------------------------------
    active_example = _load(ACTIVE_EXAMPLE, overrides)
    active_example_errors = list(
        Draft202012Validator(active_schema, registry=registry).iter_errors(
            active_example
        )
    )
    _require(not active_example_errors, "active_example_fails_active_schema")
    counters["example_lifecycle_controls"] += 1

    # A historical example must NOT validate against the active schema. If it
    # did, the two protocols would be indistinguishable at the contract layer,
    # which is the ambiguity the third P11 corrective removed.
    historical_example = _load(HISTORICAL_EXAMPLE, overrides)
    historical_against_active = list(
        Draft202012Validator(active_schema, registry=registry).iter_errors(
            historical_example
        )
    )
    _require(
        bool(historical_against_active),
        "historical_example_validates_against_active_schema",
    )
    counters["example_lifecycle_controls"] += 1

    historical_schema = _load(SCHEMA_DIR / HISTORICAL_ARTIFACT_SCHEMAS[0], overrides)
    historical_errors = list(
        Draft202012Validator(historical_schema, registry=registry).iter_errors(
            historical_example
        )
    )
    _require(not historical_errors, "historical_example_fails_its_own_schema")
    counters["example_lifecycle_controls"] += 1

    return counters


def _mutate(path: Path, old: str, new: str) -> dict[Path, str]:
    """Structured mutation with proof the intended location actually changed.

    P12-H23: a text replacement that silently matches the wrong occurrence
    produces a control that fails for the wrong reason, or does not fire at all.
    """
    source = path.read_text(encoding="utf-8")
    occurrences = source.count(old)
    _require(
        occurrences == 1,
        f"negative_control_anchor_not_unique:{path.name}:{occurrences}",
    )
    mutated = source.replace(old, new, 1)
    _require(mutated != source, f"negative_control_mutation_inert:{path.name}")
    return {path: mutated}


def run_negative_controls() -> int:
    """Semantic falsifiers. Each must fail for its intended causal reason."""
    controls: tuple[tuple[str, dict[Path, str], str], ...] = (
        (
            # NC-P12-P0-01: the exact defect this gate closes. Runtime stays v2,
            # the published success response reverts to the v1-only schema.
            "NC-P12-P0-01",
            _mutate(
                TRUST_OPENAPI,
                "                $ref: export-artifact.v2.yaml",
                "                $ref: export-artifact.v1.yaml",
            ),
            "live_response_does_not_validate_against_published_schema",
        ),
        (
            # NC-P12-P0-02: historical protocol advertised as active issuance.
            "NC-P12-P0-02",
            _mutate(
                SCHEMA_DIR / "export-artifact.v1.yaml",
                "x-skeldir-protocol-lifecycle: verification_only",
                "x-skeldir-protocol-lifecycle: active_issuance",
            ),
            "historical_schema_not_marked_verification_only",
        ),
        (
            # NC-P12-P0-03: two protocols simultaneously marked issuable.
            "NC-P12-P0-03",
            _mutate(
                HASH_MANIFEST,
                "    support_status: verification_only",
                "    support_status: active",
            ),
            "expected_exactly_one_active_protocol",
        ),
    )

    fired = 0
    for name, overrides, expected in controls:
        try:
            validate_projection(overrides)
        except B25P12ProjectionError as exc:
            reason = str(exc)
            _require(
                reason.startswith(expected),
                f"negative_control_wrong_reason:{name}:expected={expected}:observed={reason[:120]}",
            )
            fired += 1
            continue
        raise B25P12ProjectionError(f"negative_control_silent:{name}")
    return fired


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.5 contract projection: runtime issuance vs published contract."
    )
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args(argv)

    try:
        counters = validate_projection()
        negative_controls = run_negative_controls() if args.negative_control else 0
        if args.negative_control:
            _require(negative_controls == 3, "negative_control_count_drift")
    except (B25P12ProjectionError, Exception) as exc:  # noqa: BLE001
        if isinstance(exc, B25P12ProjectionError):
            print(f"B25_P12_CONTRACT_PROJECTION_VALIDATION_FAIL:{exc}")
        else:
            print(f"B25_P12_CONTRACT_PROJECTION_VALIDATION_FAIL:unexpected:{exc}")
        return 1

    print("B25_P12_CONTRACT_PROJECTION_VALIDATION_PASS")
    print(f"active_artifact_schema={ACTIVE_ARTIFACT_SCHEMA}")
    for key, value in counters.items():
        print(f"{key}_passed={value}")
    print(f"projection_negative_controls_fired={negative_controls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
