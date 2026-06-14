"""B1.7-P5 runtime anti-chat adjudication checks for explanation surface."""

from __future__ import annotations

import os
import sys
import importlib
from pathlib import Path

from starlette.routing import WebSocketRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.testing.jwt_rs256 import private_ring_payload, public_ring_payload

os.environ.setdefault("AUTH_JWT_SECRET", private_ring_payload())
os.environ.setdefault("AUTH_JWT_PUBLIC_KEY_RING", public_ring_payload())
os.environ.setdefault("AUTH_JWT_ALGORITHM", "RS256")
os.environ.setdefault("AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
os.environ.setdefault("AUTH_JWT_AUDIENCE", "skeldir-api")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres")
os.environ.setdefault(
    "MIGRATION_DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/postgres",
)
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("CONTRACT_TESTING", "1")

import app.main as main_module

app = importlib.reload(main_module).app


def test_b17_p5_explanation_surface_preserves_anti_chat_boundary() -> None:
    websocket_routes = [route for route in app.router.routes if isinstance(route, WebSocketRoute)]
    assert websocket_routes == []

    route_keys: set[str] = set()
    for route in app.routes:
        if not hasattr(route, "methods") or not hasattr(route, "path"):
            continue
        methods = set(route.methods) - {"HEAD", "OPTIONS"}
        for method in methods:
            route_keys.add(f"{method} {route.path}")
    assert "GET /api/attribution/explain/{entity_type}/{entity_id}" in route_keys

    app.openapi_schema = None
    runtime_paths = set(app.openapi().get("paths", {}).keys())
    assert "/api/attribution/explain/{entity_type}/{entity_id}" in runtime_paths
    assert all("/chat" not in path and "/stream" not in path for path in runtime_paths)


def test_b17_p5_explanation_route_runtime_openapi_is_non_streaming_json_only() -> None:
    app.openapi_schema = None
    operation = (
        app.openapi()
        .get("paths", {})
        .get("/api/attribution/explain/{entity_type}/{entity_id}", {})
        .get("get", {})
    )
    assert operation, "Missing runtime OpenAPI operation for canonical explanation route"

    responses = operation.get("responses", {})
    for response in responses.values():
        if not isinstance(response, dict):
            continue
        media_types = set((response.get("content") or {}).keys())
        assert "text/event-stream" not in media_types
        if "200" in responses:
            assert "application/json" in set(
                (responses["200"].get("content") or {}).keys()
            )
