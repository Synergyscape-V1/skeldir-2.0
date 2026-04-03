"""B1.7-P0 explanation surface lock enforcer tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _backend_root() -> Path:
    return _repo_root() / "backend"


if str(_backend_root()) not in sys.path:
    sys.path.insert(0, str(_backend_root()))

from app.testing.jwt_rs256 import private_ring_payload, public_ring_payload

os.environ.setdefault("AUTH_JWT_SECRET", private_ring_payload())
os.environ.setdefault("AUTH_JWT_PUBLIC_KEY_RING", public_ring_payload())
os.environ.setdefault("AUTH_JWT_ALGORITHM", "RS256")
os.environ.setdefault("AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
os.environ.setdefault("AUTH_JWT_AUDIENCE", "skeldir-api")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres")
os.environ.setdefault(
    "MIGRATION_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
)
os.environ.setdefault("CONTRACT_TESTING", "1")
os.environ.setdefault("TESTING", "1")

from app.main import app
from app.security.auth import AuthContext, get_auth_context


def _script_path() -> Path:
    return _repo_root() / "scripts" / "ci" / "enforce_b17_p0_explanation_surface_lock.py"


def _run_enforcer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_script_path()), *args],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )


def _runtime_routes() -> list[str]:
    items: set[str] = set()
    for route in app.routes:
        if not hasattr(route, "methods") or not hasattr(route, "path"):
            continue
        methods = set(route.methods) - {"HEAD", "OPTIONS"}
        for method in methods:
            items.add(f"{method} {route.path}")
    return sorted(items)


def _runtime_openapi() -> dict:
    return app.openapi()


def test_b17_p0_enforcer_passes_repo_baseline() -> None:
    result = _run_enforcer()
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b17_p0_enforcer_negative_control_synthetic_regression() -> None:
    result = _run_enforcer("--simulate-regression")
    assert result.returncode != 0
    assert "synthetic_regression" in (result.stdout + result.stderr)


def test_b17_p0_enforcer_negative_control_fails_when_canonical_route_absent_from_runtime(
    tmp_path: Path,
) -> None:
    routes = _runtime_routes()
    routes = [item for item in routes if item != "GET /api/attribution/explain/{entity_type}/{entity_id}"]
    payload = {"routes": routes}
    mutated_routes_file = tmp_path / "runtime_routes.regression.json"
    mutated_routes_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run_enforcer("--runtime-routes-file", str(mutated_routes_file))
    assert result.returncode != 0
    assert "canonical_route_not_mounted_runtime" in (result.stdout + result.stderr)


def test_b17_p0_enforcer_negative_control_fails_when_canonical_route_absent_from_runtime_openapi(
    tmp_path: Path,
) -> None:
    runtime_doc = _runtime_openapi()
    runtime_doc.get("paths", {}).pop("/api/attribution/explain/{entity_type}/{entity_id}", None)
    mutated_runtime_openapi = tmp_path / "runtime_openapi.regression.json"
    mutated_runtime_openapi.write_text(json.dumps(runtime_doc, indent=2), encoding="utf-8")

    result = _run_enforcer("--runtime-openapi-file", str(mutated_runtime_openapi))
    assert result.returncode != 0
    assert "canonical_route_missing_from_runtime_openapi" in (result.stdout + result.stderr)


def test_b17_p0_enforcer_negative_control_detects_noncanonical_authority_regression(
    tmp_path: Path,
) -> None:
    source_file = _repo_root() / "api-contracts" / "openapi" / "v1" / "llm-explanations.yaml"
    payload = yaml.safe_load(source_file.read_text(encoding="utf-8")) or {}
    op = payload["paths"]["/api/v1/explain/{entity_type}/{entity_id}"]["get"]
    op.setdefault("x-skeldir-b17-p0", {})["authority_status"] = "authoritative"
    mutated_source = tmp_path / "llm-explanations.regression.yaml"
    mutated_source.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    result = _run_enforcer("--noncanonical-source-file", str(mutated_source))
    assert result.returncode != 0
    assert "noncanonical_source_missing_invalid_authority_status" in (result.stdout + result.stderr)


def test_b17_p0_enforcer_negative_control_detects_endpoint_semantics_drift(tmp_path: Path) -> None:
    source_file = _repo_root() / "api-contracts" / "openapi" / "v1" / "attribution.yaml"
    payload = yaml.safe_load(source_file.read_text(encoding="utf-8")) or {}
    op = payload["paths"]["/api/attribution/explain/{entity_type}/{entity_id}"]["get"]
    op["x-skeldir-b17-p0"]["performance_semantics"]["overall_endpoint_p95_ms"] = 900
    mutated_source = tmp_path / "attribution.regression.yaml"
    mutated_source.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    result = _run_enforcer("--attribution-source-file", str(mutated_source))
    assert result.returncode != 0
    assert "b17_lock_performance_p95_mismatch" in (result.stdout + result.stderr)


def test_b17_p0_canonical_route_returns_contract_defined_non_operational_mode() -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    fake_context = AuthContext(
        tenant_id=tenant_id,
        user_id=uuid.uuid4(),
        jti=uuid.uuid4(),
        issued_at_epoch=0,
        subject="test-user",
        issuer="https://issuer.skeldir.test",
        audience="skeldir-api",
        claims={"scopes": ["viewer"]},
    )

    async def _fake_auth_context():
        return fake_context

    app.dependency_overrides[get_auth_context] = _fake_auth_context
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/attribution/explain/attribution_score/{uuid.uuid4()}",
                headers={"X-Correlation-ID": str(uuid.uuid4())},
            )
        assert response.status_code == 503, response.text
        assert response.headers.get("content-type", "").startswith("application/problem+json")
        assert response.headers.get("Retry-After") == "60"
        body = response.json()
        assert body["code"] == "EXPLAIN_SURFACE_NOT_READY"
        assert body["status"] == 503
    finally:
        app.dependency_overrides.clear()
