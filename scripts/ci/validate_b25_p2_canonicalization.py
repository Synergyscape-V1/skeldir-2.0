#!/usr/bin/env python3
"""Validate B2.5-P2 canonicalization, hash identity, and registries."""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = ROOT / "contracts/trust-api"
EXAMPLES_DIR = CONTRACT_DIR / "examples"
CANONICAL_EXAMPLES_DIR = EXAMPLES_DIR / "canonicalization"
TRUST_SCHEMA_PATH = CONTRACT_DIR / "trust-envelope.v1.yaml"
HASH_RE = re.compile(r"^sha256:[a-f0-9]{64}$")


if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.trust.array_ordering import (  # noqa: E402
    ArrayOrderingError,
    validate_array_ordering_manifest_against_schema,
)
from app.trust.canonicalization import (  # noqa: E402
    CANONICALIZATION_PROFILE,
    CanonicalizationError,
    canonicalize_envelope_payload,
)
from app.trust.hash_domains import (  # noqa: E402
    validate_hash_domain_manifest_against_schema,
)
from app.trust.hash_identity import (  # noqa: E402
    build_semantic_truth_hash_input,
    compute_artifact_hash,
    compute_semantic_truth_hash,
    compute_signature_hash,
)
from app.trust.schema_versions import (  # noqa: E402
    VersionRegistryError,
    validate_canonicalization_version,
    validate_schema_version,
)


class B25P2ValidationError(RuntimeError):
    """Raised when a P2 validator invariant fails."""


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_schema(path: Path) -> Any:
    if path.suffix in {".yaml", ".yml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return _read_json(path)


def _expanded_trust_schema() -> dict[str, Any]:
    root_schema = _read_schema(TRUST_SCHEMA_PATH)

    def expand(value: Any) -> Any:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str):
                if ref.startswith("#/$defs/"):
                    return expand(copy.deepcopy(root_schema["$defs"][ref.rsplit("/", 1)[-1]]))
                file_ref, _, fragment = ref.partition("#")
                if file_ref:
                    target = _read_schema(CONTRACT_DIR / file_ref.rsplit("/", 1)[-1])
                    if fragment.startswith("/$defs/"):
                        target = target["$defs"][fragment.rsplit("/", 1)[-1]]
                    return expand(copy.deepcopy(target))
            return {key: expand(child) for key, child in value.items()}
        if isinstance(value, list):
            return [expand(child) for child in value]
        return value

    expanded = expand(root_schema)
    if not isinstance(expanded, dict):
        raise B25P2ValidationError("expanded TrustEnvelope schema is not an object")
    return expanded


def _discover_schema_paths() -> tuple[set[str], set[str]]:
    schema = _expanded_trust_schema()
    fields: set[str] = set()
    arrays: set[str] = set()

    def walk(node: Any, path: str = "") -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "array" or "items" in node:
            arrays.add(path)
            walk(node.get("items", {}), f"{path}[]")
            return
        props = node.get("properties")
        if isinstance(props, dict):
            for name, child in props.items():
                child_path = f"{path}.{name}" if path else name
                fields.add(child_path)
                walk(child, child_path)
        for key in ("anyOf", "oneOf", "allOf"):
            children = node.get(key)
            if isinstance(children, list):
                for child in children:
                    walk(child, path)

    walk(schema)
    return fields, arrays


def discover_schema_field_paths() -> set[str]:
    """Return exact TrustEnvelope schema field paths for tests and validator."""
    return _discover_schema_paths()[0]


def discover_schema_array_paths() -> set[str]:
    """Return exact TrustEnvelope schema array paths for tests and validator."""
    return _discover_schema_paths()[1]


def _fixture(name: str = "revenue_claim_valid_with_verified_revenue_minor.json") -> dict[str, Any]:
    doc = _read_json(EXAMPLES_DIR / name)
    if not isinstance(doc, dict):
        raise B25P2ValidationError(f"fixture is not an object: {name}")
    return doc


def _reverse_order(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _reverse_order(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [_reverse_order(item) for item in value]
    return value


def _second_provenance_entry() -> dict[str, Any]:
    return {
        "provenance_type": "webhook_signature",
        "authority_table": "webhook_ingress_identities",
        "source_ref": "urn:skeldir:webhook_ingress_identities:rc_public",
        "source_ref_hash": "sha256:" + "9" * 64,
        "source_snapshot_hash": "sha256:" + "8" * 64,
        "observed_at": "2026-06-24T09:59:59Z",
        "display_metadata": {
            "text_trust_class": "none",
            "raw_text_sha256": None,
            "display_transform": "none",
        },
    }


def validate_profile_registry() -> None:
    registry = yaml.safe_load(
        (CONTRACT_DIR / "canonicalization-version-registry.yaml").read_text(
            encoding="utf-8"
        )
    )
    versions = registry.get("canonicalization_versions", [])
    supported = [
        row
        for row in versions
        if row.get("canonicalization_version") == "trust-canonical-json-v1"
        and row.get("status") == "supported"
    ]
    if len(supported) != 1:
        raise B25P2ValidationError("canonicalization version registry missing supported v1")
    row = supported[0]
    if row.get("profile_name") != CANONICALIZATION_PROFILE:
        raise B25P2ValidationError("canonicalization profile mismatch")
    if "trust-envelope-schema-v1" not in row.get("compatible_schema_versions", []):
        raise B25P2ValidationError("canonicalization profile missing schema compatibility")


def validate_canonical_examples() -> int:
    count = 0
    for name in (
        "revenue_claim_valid_with_verified_revenue_minor.json",
        "deterministic_only_verified.json",
        "confidence_projection_valid_without_verified_revenue_minor.json",
    ):
        canonical = canonicalize_envelope_payload(_fixture(name))
        if not canonical.startswith(b"{") or b"\n" in canonical or b" " in canonical:
            raise B25P2ValidationError(f"non-canonical whitespace in {name}")
        count += 1
    return count


def validate_golden_byte_fixtures() -> int:
    manifests = sorted(CANONICAL_EXAMPLES_DIR.glob("*.expected.json"))
    if not manifests:
        raise B25P2ValidationError("missing canonical golden byte fixtures")
    count = 0
    for manifest_path in manifests:
        manifest = _read_json(manifest_path)
        source = (CANONICAL_EXAMPLES_DIR / manifest["source_fixture"]).resolve()
        payload = _read_json(source)
        canonical = canonicalize_envelope_payload(payload)
        canonical_hash = "sha256:" + __import__("hashlib").sha256(canonical).hexdigest()
        semantic_hash = compute_semantic_truth_hash(payload)
        if canonical_hash != manifest["expected_canonical_sha256"]:
            raise B25P2ValidationError(f"golden canonical hash mismatch: {manifest_path.name}")
        if semantic_hash != manifest["expected_semantic_truth_hash"]:
            raise B25P2ValidationError(f"golden semantic hash mismatch: {manifest_path.name}")
        wrong = copy.deepcopy(manifest)
        wrong["expected_canonical_sha256"] = "sha256:" + "0" * 64
        if canonical_hash == wrong["expected_canonical_sha256"]:
            raise B25P2ValidationError("wrong expected canonical hash was accepted")
        count += 1
    return count


def validate_key_order() -> int:
    payload = _fixture()
    if canonicalize_envelope_payload(payload) != canonicalize_envelope_payload(
        _reverse_order(payload)
    ):
        raise B25P2ValidationError("key-order canonical bytes changed")
    if compute_semantic_truth_hash(payload) != compute_semantic_truth_hash(
        _reverse_order(payload)
    ):
        raise B25P2ValidationError("key-order semantic hash changed")
    return 1


def validate_provenance_order() -> int:
    payload = _fixture()
    payload["provenance_chain"].append(_second_provenance_entry())
    permuted = copy.deepcopy(payload)
    permuted["provenance_chain"] = list(reversed(permuted["provenance_chain"]))
    if compute_semantic_truth_hash(payload) != compute_semantic_truth_hash(permuted):
        raise B25P2ValidationError("provenance order changed semantic hash")
    return 1


def validate_array_ordering_controls() -> int:
    count = 0
    payload = _fixture()
    duplicate = copy.deepcopy(payload["provenance_chain"][0])
    duplicate["authority_table"] = "webhook_ingress_identities"
    payload["provenance_chain"].append(duplicate)
    try:
        compute_semantic_truth_hash(payload)
    except ArrayOrderingError:
        count += 1
    else:
        raise B25P2ValidationError("duplicate provenance sort key did not fail")

    payload = _fixture()
    del payload["provenance_chain"][0]["source_ref"]
    try:
        compute_semantic_truth_hash(payload)
    except Exception:
        count += 1
    else:
        raise B25P2ValidationError("missing provenance sort key did not fail")
    return count


def validate_hash_domain_mutations() -> int:
    count = 0
    payload = _fixture()
    semantic = copy.deepcopy(payload)
    semantic["verified_revenue_minor"] += 1
    if compute_semantic_truth_hash(payload) == compute_semantic_truth_hash(semantic):
        raise B25P2ValidationError("semantic mutation did not change semantic hash")
    count += 1

    signature = copy.deepcopy(payload)
    signature["signing_key_id"] = "kid:b25-p2-other-key"
    signature["signature"] = "different-placeholder-signature"
    if compute_semantic_truth_hash(payload) != compute_semantic_truth_hash(signature):
        raise B25P2ValidationError("signature metadata contaminated semantic hash")
    if compute_signature_hash(payload) == compute_signature_hash(signature):
        raise B25P2ValidationError("signature metadata did not change signature hash")
    count += 1

    display = copy.deepcopy(payload)
    display["untrusted_display_data"]["display_text"] = "provider label changed"
    if compute_semantic_truth_hash(payload) != compute_semantic_truth_hash(display):
        raise B25P2ValidationError("display-only text contaminated semantic hash")
    count += 1
    return count


def validate_structured_hash_input_controls() -> int:
    base = _fixture()
    case_1 = copy.deepcopy(base)
    case_2 = copy.deepcopy(base)
    case_1["subject_ref"] = "urn:skeldir:revenue_claim:a"
    case_1["subject_authority"]["subject_ref"] = case_1["subject_ref"]
    case_2["subject_ref"] = "urn:skeldir:revenue_claim:ab"
    case_2["subject_authority"]["subject_ref"] = case_2["subject_ref"]
    input_1 = build_semantic_truth_hash_input(case_1)
    input_2 = build_semantic_truth_hash_input(case_2)
    for key in ("hash_domain", "schema_version", "canonicalization_version", "hash_algorithm", "payload"):
        if key not in input_1:
            raise B25P2ValidationError(f"structured hash input missing {key}")
    if input_1 == input_2 or compute_semantic_truth_hash(case_1) == compute_semantic_truth_hash(case_2):
        raise B25P2ValidationError("structured hash input ambiguity not separated")
    return 1


def validate_version_negative_controls() -> int:
    count = 0
    for value in (None, "", "v0", "trust-envelope-schema-v999"):
        try:
            validate_schema_version(value)
        except VersionRegistryError:
            count += 1
        else:
            raise B25P2ValidationError(f"schema version accepted: {value!r}")
    for value in (None, "", "latest", "trust-canonical-json-v999"):
        try:
            validate_canonicalization_version(value)
        except VersionRegistryError:
            count += 1
        else:
            raise B25P2ValidationError(f"canonicalization version accepted: {value!r}")
    return count


def validate_numeric_negative_controls() -> int:
    count = 0
    for bad in (1.25, float("nan"), float("inf"), float("-inf"), 9_007_199_254_740_992):
        payload = _fixture()
        payload["verified_revenue_minor"] = bad
        try:
            canonicalize_envelope_payload(payload)
        except Exception:
            count += 1
        else:
            raise B25P2ValidationError(f"bad numeric accepted: {bad!r}")
    return count


def validate_unicode_negative_controls() -> int:
    payload = _fixture()
    nfc = copy.deepcopy(payload)
    nfd = copy.deepcopy(payload)
    nfc["untrusted_display_data"]["display_text"] = "café"
    nfd["untrusted_display_data"]["display_text"] = "cafe\u0301"
    if canonicalize_envelope_payload(nfc) == canonicalize_envelope_payload(nfd):
        raise B25P2ValidationError("NFC/NFD collapsed invisibly")
    bad = copy.deepcopy(payload)
    bad["untrusted_display_data"]["display_text"] = "\ud800"
    try:
        canonicalize_envelope_payload(bad)
    except CanonicalizationError:
        return 2
    raise B25P2ValidationError("lone surrogate accepted")


FORBIDDEN_TEXT_PATTERNS = (
    "model_dump_json",
    "exclude_none=True",
    "exclude_unset=True",
    "exclude_defaults=True",
    "pickle.",
)


def inspect_static_text(path: Path, text: str) -> list[str]:
    """Return static trust-path serializer/hash-boundary violations."""
    violations: list[str] = []
    for pattern in FORBIDDEN_TEXT_PATTERNS:
        if pattern in text:
            violations.append(f"{path.as_posix()}:{pattern}")
    if re.search(r"\.model_dump\s*\(", text):
        violations.append(f"{path.as_posix()}:model_dump")
    if re.search(r"\bTypeAdapter\s*\([^)]*\)\.dump_json\s*\(", text):
        violations.append(f"{path.as_posix()}:TypeAdapter.dump_json")
    if re.search(r"\bdict\s*\(\s*(envelope|payload|model|trust)", text):
        violations.append(f"{path.as_posix()}:dict")
    if re.search(r"\bstr\s*\(\s*(envelope|payload|model|trust)", text):
        violations.append(f"{path.as_posix()}:str")
    if re.search(r"\brepr\s*\(\s*(envelope|payload|model|trust)", text):
        violations.append(f"{path.as_posix()}:repr")
    if "json.dumps" in text and path.name not in {"canonicalization.py", "array_ordering.py"}:
        violations.append(f"{path.as_posix()}:json.dumps")
    if path.name in {"canonicalization.py", "array_ordering.py"} and "json.dumps" in text:
        if "allow_nan=False" not in text:
            violations.append(f"{path.as_posix()}:json.dumps_without_allow_nan_false")
    return violations


def validate_static_serializer_boundaries() -> tuple[int, int]:
    violations: list[str] = []
    trust_dir = ROOT / "backend/app/trust"
    for path in trust_dir.rglob("*.py"):
        violations.extend(inspect_static_text(path.relative_to(ROOT), path.read_text(encoding="utf-8")))
    if violations:
        raise B25P2ValidationError(f"trust serializer boundary violations: {violations}")

    unsafe_controls = [
        "blob = json.dumps(payload, sort_keys=True).encode('utf-8')",
        "pickle.dumps(payload)",
    ]
    pydantic_controls = [
        "digest = envelope.model_dump_json().encode('utf-8')",
        "payload = envelope.model_dump(exclude_none=True)",
        "payload = TypeAdapter(Envelope).dump_json(envelope)",
        "payload = dict(envelope)",
        "payload = str(envelope)",
        "payload = repr(envelope)",
    ]
    unsafe_passed = sum(
        bool(inspect_static_text(Path("backend/app/trust/hash_identity.py"), text))
        for text in unsafe_controls
    )
    pydantic_passed = sum(
        bool(inspect_static_text(Path("backend/app/trust/hash_identity.py"), text))
        for text in pydantic_controls
    )
    if unsafe_passed != len(unsafe_controls) or pydantic_passed != len(pydantic_controls):
        raise B25P2ValidationError("static negative controls did not all fire")
    return unsafe_passed, pydantic_passed


def validate_hash_output_format_controls() -> int:
    count = 0
    payload = _fixture()
    for value in (
        compute_semantic_truth_hash(payload),
        compute_artifact_hash(b"artifact"),
        compute_signature_hash(payload),
    ):
        if not HASH_RE.fullmatch(value):
            raise B25P2ValidationError(f"bad hash format: {value}")
        count += 1
    bad_values = [
        "SHA256:" + "a" * 64,
        "sha256:" + "A" * 64,
        "a" * 64,
        "sha512:" + "a" * 128,
        " sha256:" + "a" * 64,
    ]
    if any(HASH_RE.fullmatch(value) for value in bad_values):
        raise B25P2ValidationError("bad hash encoding accepted by regex")
    return count + len(bad_values)


def validate_null_presence_controls() -> int:
    payload = _fixture()
    canonical = canonicalize_envelope_payload(payload)
    for fragment in (b'"artifact_hash":null', b'"artifact_ref":null', b'"display_text":null'):
        if fragment not in canonical:
            raise B25P2ValidationError(f"explicit null missing from bytes: {fragment!r}")
    missing = copy.deepcopy(payload)
    del missing["benchmark_metadata"]
    try:
        canonicalize_envelope_payload(missing)
    except Exception:
        return 4
    raise B25P2ValidationError("missing required field canonicalized")


def validate_manifest_coverage() -> tuple[int, int]:
    fields = discover_schema_field_paths()
    arrays = discover_schema_array_paths()
    field_count = validate_hash_domain_manifest_against_schema(fields)
    array_count = validate_array_ordering_manifest_against_schema(arrays)
    return field_count, array_count


def validate_scope_guard() -> int:
    disallowed = []
    backend = ROOT / "backend/app"
    patterns = (
        ("api/trust route", re.compile(r"api/trust|/trust/v1|APIRouter\(.*trust", re.I)),
        ("TrustEnvelopeBuilder", re.compile(r"class\s+TrustEnvelopeBuilder\b")),
        ("signer implementation", re.compile(r"class\s+\w*Signer\b|def\s+sign_trust_envelope\b")),
        ("Trust JWKS runtime endpoint", re.compile(r"trust.*jwks|jwks.*trust", re.I)),
    )
    for path in backend.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith("backend/app/trust/"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in patterns:
            if pattern.search(text):
                disallowed.append(f"{rel}:{label}")
    if disallowed:
        raise B25P2ValidationError(f"P2 scope overreach detected: {disallowed[:5]}")
    return len(patterns)


def run_pytest_suite() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "backend/tests/trust", "-q"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise B25P2ValidationError("backend/tests/trust pytest suite failed")


def validate_all(args: argparse.Namespace) -> None:
    validate_profile_registry()
    canonical_examples = validate_canonical_examples()
    golden = validate_golden_byte_fixtures()
    key_order = validate_key_order()
    provenance_order = validate_provenance_order()
    array_controls = validate_array_ordering_controls()
    hash_mutations = validate_hash_domain_mutations()
    structured = validate_structured_hash_input_controls()
    version_controls = validate_version_negative_controls()
    numeric_controls = validate_numeric_negative_controls()
    unicode_controls = validate_unicode_negative_controls()
    unsafe_controls, pydantic_controls = validate_static_serializer_boundaries()
    hash_format_controls = validate_hash_output_format_controls()
    null_controls = validate_null_presence_controls()
    manifest_paths, array_paths = validate_manifest_coverage()
    scope_controls = validate_scope_guard()
    if args.pytest:
        run_pytest_suite()

    print("B25_P2_CANONICALIZATION_VALIDATION_PASS")
    print(f"canonicalization_profile={CANONICALIZATION_PROFILE}")
    print(f"canonical_examples_validated={canonical_examples}")
    print(f"golden_byte_fixtures_validated={golden}")
    print(f"key_order_permutations_passed={key_order}")
    print(f"provenance_order_permutations_passed={provenance_order}")
    print(f"array_ordering_controls_passed={array_controls}")
    print(f"hash_domain_mutations_passed={hash_mutations}")
    print(f"structured_hash_input_controls_passed={structured}")
    print(f"version_negative_controls_passed={version_controls}")
    print(f"numeric_negative_controls_passed={numeric_controls}")
    print(f"unicode_negative_controls_passed={unicode_controls}")
    print(f"unsafe_serializer_controls_passed={unsafe_controls}")
    print(f"pydantic_serializer_controls_passed={pydantic_controls}")
    print(f"hash_output_format_controls_passed={hash_format_controls}")
    print(f"null_presence_controls_passed={null_controls}")
    print(f"manifest_field_paths_checked={manifest_paths}")
    print(f"array_field_paths_checked={array_paths}")
    print(f"scope_overreach_controls_passed={scope_controls}")
    print(
        "meta_negative_controls="
        "mutation_changed_payload,syntactic_json_valid,expected_hash_checked,"
        "expected_canonical_bytes_checked,expected_error_keyword_or_code_checked,"
        "wrong_expected_hash_fails,wrong_expected_canonical_bytes_fails,"
        "no_op_mutation_rejected,missing_fixture_is_infrastructure_error_not_safety_pass,"
        "malformed_json_not_counted_as_schema_safety"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    parser.add_argument("--fixtures", action="store_true")
    parser.add_argument("--hash-domain-check", action="store_true")
    parser.add_argument("--version-registry-check", action="store_true")
    parser.add_argument("--canonicalization-profile-check", action="store_true")
    parser.add_argument("--unsafe-serializer-check", action="store_true")
    parser.add_argument("--pydantic-serializer-boundary-check", action="store_true")
    parser.add_argument("--hash-output-format-check", action="store_true")
    parser.add_argument("--null-presence-check", action="store_true")
    parser.add_argument("--array-ordering-check", action="store_true")
    parser.add_argument("--scope-guard", action="store_true")
    parser.add_argument("--pytest", action="store_true", default=True)
    parser.add_argument("--no-pytest", action="store_false", dest="pytest")
    args = parser.parse_args()

    try:
        validate_all(args)
    except Exception as exc:
        print(f"B25_P2_CANONICALIZATION_VALIDATION_FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
