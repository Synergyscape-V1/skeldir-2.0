from __future__ import annotations

from pathlib import Path

from scripts.ci.validate_b25_p2_canonicalization import inspect_static_text


def test_pydantic_serializer_boundary_negative_controls_are_detected() -> None:
    text = 'digest = envelope.model_dump_json().encode("utf-8")\n'

    violations = inspect_static_text(Path("backend/app/trust/hash_identity.py"), text)

    assert any("model_dump_json" in violation for violation in violations)


def test_exclude_none_negative_control_is_detected() -> None:
    text = "payload = envelope.model_dump(exclude_none=True)\n"

    violations = inspect_static_text(Path("backend/app/trust/hash_identity.py"), text)

    assert any("exclude_none" in violation for violation in violations)


def test_unsafe_serializer_negative_control_is_detected_outside_allowlist() -> None:
    text = "blob = json.dumps(payload, sort_keys=True).encode('utf-8')\n"

    violations = inspect_static_text(Path("backend/app/trust/hash_identity.py"), text)

    assert any("json.dumps" in violation for violation in violations)

