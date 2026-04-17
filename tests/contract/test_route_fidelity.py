"""
Route-Contract Fidelity Tests - Phase E
Validates 1:1 mapping between FastAPI routes and OpenAPI contract operations.

Exit criteria:
- Every in-scope FastAPI route has a corresponding OpenAPI operation
- Every OpenAPI operation has a corresponding FastAPI route (or is allowlisted)
- Operation IDs match between implementation and contract
"""

import os
import sys
from pathlib import Path
import yaml
import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))
from app.testing.jwt_rs256 import private_ring_payload, public_ring_payload

os.environ.setdefault("AUTH_JWT_SECRET", private_ring_payload())
os.environ.setdefault("AUTH_JWT_PUBLIC_KEY_RING", public_ring_payload())
os.environ.setdefault("AUTH_JWT_ALGORITHM", "RS256")
os.environ.setdefault("AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
os.environ.setdefault("AUTH_JWT_AUDIENCE", "skeldir-api")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
)
os.environ.setdefault(
    "MIGRATION_DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/postgres",
)
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("CONTRACT_TESTING", "1")

# Contract scope configuration
CONTRACT_SCOPE_FILE = (
    Path(__file__).parent.parent.parent
    / "backend"
    / "app"
    / "config"
    / "contract_scope.yaml"
)
CONTRACTS_DIR = (
    Path(__file__).parent.parent.parent / "api-contracts" / "dist" / "openapi" / "v1"
)


def load_contract_scope():
    """Load contract scope configuration."""
    with open(CONTRACT_SCOPE_FILE, "r") as f:
        return yaml.safe_load(f)


def extract_openapi_operations(contract_path):
    """Extract all operations from an OpenAPI spec."""
    with open(contract_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    operations = []
    if "paths" not in spec:
        return operations

    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if method.lower() in ["get", "post", "put", "patch", "delete"]:
                operations.append(
                    {
                        "method": method.upper(),
                        "path": path,
                        "operation_id": operation.get("operationId", "N/A"),
                        "summary": operation.get("summary", "N/A"),
                    }
                )

    return operations


def extract_fastapi_routes():
    """Extract all routes from FastAPI app."""
    try:
        from app.main import app

        routes = []
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                # Filter out HEAD and OPTIONS
                methods = route.methods - {"HEAD", "OPTIONS"}
                operation_id = getattr(route, "operation_id", None)
                name = getattr(route, "name", "N/A")

                for method in methods:
                    routes.append(
                        {
                            "method": method,
                            "path": route.path,
                            "operation_id": operation_id,
                            "name": name,
                        }
                    )

        return routes
    except ImportError as e:
        pytest.skip(f"FastAPI app not importable: {e}")
        return []


def test_contract_scope_configuration_exists():
    """Verify contract scope configuration exists."""
    assert (
        CONTRACT_SCOPE_FILE.exists()
    ), f"Contract scope config not found: {CONTRACT_SCOPE_FILE}"


def test_contracts_directory_exists():
    """Verify contracts directory exists."""
    assert CONTRACTS_DIR.exists(), f"Contracts directory not found: {CONTRACTS_DIR}"


def test_route_to_contract_mapping():
    """Test that all in-scope FastAPI routes have corresponding contract operations."""
    scope = load_contract_scope()
    in_scope_prefixes = scope.get("in_scope_prefixes", [])
    out_of_scope_paths = scope.get("out_of_scope_paths", [])

    routes = extract_fastapi_routes()

    # Collect all contract operations
    all_contract_operations = {}
    for contract_file in CONTRACTS_DIR.glob("*.bundled.yaml"):
        operations = extract_openapi_operations(contract_file)
        for op in operations:
            key = f"{op['method']} {op['path']}"
            all_contract_operations[key] = op

    unmapped_routes = []

    for route in routes:
        # Skip out-of-scope routes
        is_out_of_scope = any(
            route["path"].startswith(prefix.rstrip("*"))
            for prefix in out_of_scope_paths
        )
        if is_out_of_scope:
            continue

        # Check if route is in-scope
        is_in_scope = any(
            route["path"].startswith(prefix) for prefix in in_scope_prefixes
        )

        if is_in_scope:
            # Check if contract operation exists
            route_key = f"{route['method']} {route['path']}"
            if route_key not in all_contract_operations:
                unmapped_routes.append(route)

    assert len(unmapped_routes) == 0, (
        f"Found {len(unmapped_routes)} in-scope routes without contract operations:\n"
        + "\n".join(f"  - {r['method']} {r['path']}" for r in unmapped_routes)
    )


def test_contract_to_route_mapping():
    """Test that all contract operations have corresponding FastAPI routes (or are allowlisted)."""
    scope = load_contract_scope()
    spec_mappings = scope.get("spec_mappings", {})
    contract_only_allowlist = scope.get("contract_only_allowlist", [])

    routes = extract_fastapi_routes()
    route_keys = {f"{r['method']} {r['path']}" for r in routes}

    # Collect contract operations that should be implemented
    expected_operations = []
    for prefix, contract_path in spec_mappings.items():
        full_path = Path(__file__).parent.parent.parent / contract_path
        if full_path.exists():
            operations = extract_openapi_operations(full_path)
            for op in operations:
                key = f"{op['method']} {op['path']}"
                expected_operations.append((key, op))

    unimplemented_operations = []

    for key, op in expected_operations:
        if key not in route_keys and key not in contract_only_allowlist:
            unimplemented_operations.append(op)

    canonical_b17_operation = [
        op
        for op in unimplemented_operations
        if op.get("operation_id") == "explainAttributionEntity"
        and op.get("method") == "GET"
        and op.get("path") == "/api/attribution/explain/{entity_type}/{entity_id}"
    ]
    assert not canonical_b17_operation, (
        "B1.7 explanation route fidelity drift is merge-blocking: "
        "GET /api/attribution/explain/{entity_type}/{entity_id} must remain mounted and contract-mapped."
    )

    attribution_unimplemented = [
        op for op in unimplemented_operations if str(op.get("path", "")).startswith("/api/attribution")
    ]
    assert not attribution_unimplemented, (
        "Canonical attribution operations declared in contract but unmounted at runtime are merge-blocking:\n"
        + "\n".join(
            f"  - {op['method']} {op['path']} ({op.get('operation_id', 'N/A')})"
            for op in attribution_unimplemented
        )
    )

    # In Phase B0.1, many operations are still expected to be unimplemented.
    # B1.7 explanation route drift is explicitly fail-closed above.
    remaining_unimplemented = [
        op
        for op in unimplemented_operations
        if op not in canonical_b17_operation and op not in attribution_unimplemented
    ]
    if remaining_unimplemented:
        print(
            f"\nNOTE: {len(remaining_unimplemented)} contract operations not yet implemented (expected in B0.1):"
        )
        for op in remaining_unimplemented[:5]:  # Show first 5
            print(f"  - {op['method']} {op['path']} ({op['operation_id']})")
        if len(remaining_unimplemented) > 5:
            print(f"  ... and {len(remaining_unimplemented) - 5} more")


def test_operation_id_consistency():
    """Test that operation IDs are consistent between routes and contracts."""
    routes = extract_fastapi_routes()

    # Collect contract operations by path
    contract_operations = {}
    for contract_file in CONTRACTS_DIR.glob("*.bundled.yaml"):
        operations = extract_openapi_operations(contract_file)
        for op in operations:
            key = f"{op['method']} {op['path']}"
            contract_operations[key] = op

    mismatched_ids = []

    for route in routes:
        route_key = f"{route['method']} {route['path']}"
        if route_key in contract_operations:
            contract_op = contract_operations[route_key]
            if (
                route["operation_id"]
                and route["operation_id"] != contract_op["operation_id"]
            ):
                mismatched_ids.append(
                    {
                        "route": route_key,
                        "route_id": route["operation_id"],
                        "contract_id": contract_op["operation_id"],
                    }
                )

    assert len(mismatched_ids) == 0, (
        f"Found {len(mismatched_ids)} routes with mismatched operation IDs:\n"
        + "\n".join(
            f"  - {m['route']}: route='{m['route_id']}' vs contract='{m['contract_id']}'"
            for m in mismatched_ids
        )
    )


def test_b17_canonical_explain_route_mounted_and_runtime_openapi_converged():
    """B1.7-P1/P2 hard gate: canonical explanation route and fast-path lock must exist in runtime."""
    attribution_source = (
        Path(__file__).parent.parent.parent
        / "api-contracts"
        / "openapi"
        / "v1"
        / "attribution.yaml"
    )
    with open(attribution_source, "r", encoding="utf-8") as handle:
        source_doc = yaml.safe_load(handle) or {}

    canonical_path = "/api/attribution/explain/{entity_type}/{entity_id}"
    source_operation = (
        source_doc.get("paths", {}).get(canonical_path, {}).get("get", {})
    )
    assert source_operation.get("operationId") == "explainAttributionEntity"

    b17_lock = source_operation.get("x-skeldir-b17-p1", {})
    assert b17_lock.get("implementation_status") == "mounted_operational_authority_read"
    b17_p2_lock = source_operation.get("x-skeldir-b17-p2", {})
    assert (
        b17_p2_lock.get("implementation_status")
        == "mounted_fastpath_sidecar_validation_bound"
    )
    assert b17_p2_lock.get("fast_tier_profile", {}).get("provider_neutral") is True
    assert (
        b17_p2_lock.get("fast_tier_profile", {}).get("config_key")
        == "LLM_B17_EXPLANATION_FAST_TIER"
    )
    assert (
        b17_p2_lock.get("fast_timeout_profile", {}).get("config_key")
        == "LLM_B17_EXPLANATION_TIMEOUT_MS"
    )
    assert (
        b17_p2_lock.get("output_envelope", {}).get("schema_key")
        == "attribution_explanation_fastpath_v1"
    )
    assert b17_p2_lock.get("output_envelope", {}).get("summary_max_length") == 320
    b17_p3_lock = source_operation.get("x-skeldir-b17-p3", {})
    assert (
        b17_p3_lock.get("implementation_status")
        == "deterministic_watermark_cache_identity_replay_rejection"
    )
    replay_topology = b17_p3_lock.get("cache_replay_topology", {})
    assert (
        replay_topology.get(
            "authoritative_watermark_lookup_required_before_cache_replay"
        )
        is True
    )
    assert replay_topology.get("prompt_hash_only_identity_forbidden") is True
    stale_policy = b17_p3_lock.get("stale_replay_policy", {})
    assert stale_policy.get("stale_replay_rejection_required") is True
    assert stale_policy.get("provider_reentry_on_stale_forbidden") is True
    citation_coherence = b17_p3_lock.get("citation_coherence", {})
    assert citation_coherence.get("structured_truth_snapshot_required") is True
    b17_p4_lock = source_operation.get("x-skeldir-b17-p4", {})
    assert (
        b17_p4_lock.get("implementation_status")
        == "cold_path_strategy_closed_with_bounded_event_prewarm"
    )
    strategy = b17_p4_lock.get("cold_path_strategy", {})
    assert strategy.get("decision") == "prewarm_required"
    assert strategy.get("warm_path_only_proof_forbidden") is True
    assert strategy.get("ordinary_pr_ci_live_vendor_load_forbidden") is True
    execution_metadata = b17_p4_lock.get("execution_metadata", {})
    assert set(execution_metadata.get("schema_required_fields", [])) >= {
        "execution_path_state",
        "cold_path_strategy",
        "prewarm_state",
    }
    assert set(execution_metadata.get("path_classes", [])) >= {
        "warm_cache_hit",
        "cold_path_generated",
        "stale_rejected_provider_blocked",
        "prewarm_assisted_cache_hit",
    }
    prewarm_policy = b17_p4_lock.get("prewarm_policy", {})
    assert prewarm_policy.get("trigger_mode") == "deterministic_truth_change_event"
    assert prewarm_policy.get("default_cron_forbidden") is True

    routes = extract_fastapi_routes()
    route_keys = {f"{item['method']} {item['path']}" for item in routes}
    assert "GET /api/attribution/explain/{entity_type}/{entity_id}" in route_keys

    from app.main import app

    runtime_openapi = app.openapi()
    runtime_paths = runtime_openapi.get("paths", {})
    assert canonical_path in runtime_paths
    runtime_operation = runtime_paths[canonical_path]["get"]
    assert runtime_operation.get("operationId") == "explainAttributionEntity"
    responses = runtime_operation.get("responses", {})
    assert "200" in responses
    assert "503" in responses
    schema_ref = (
        responses["200"]
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
        .get("$ref")
    )
    assert schema_ref == "#/components/schemas/AttributionExplanationResponse"

    runtime_lock = runtime_operation.get("x-skeldir-b17-p1", {})
    assert (
        runtime_lock.get("implementation_status")
        == "mounted_operational_authority_read"
    )
    runtime_p2_lock = runtime_operation.get("x-skeldir-b17-p2", {})
    assert (
        runtime_p2_lock.get("implementation_status")
        == "mounted_fastpath_sidecar_validation_bound"
    )
    assert runtime_p2_lock.get("fast_tier_profile", {}).get("provider_neutral") is True
    assert (
        runtime_p2_lock.get("fast_tier_profile", {}).get("config_key")
        == "LLM_B17_EXPLANATION_FAST_TIER"
    )
    assert (
        runtime_p2_lock.get("fast_timeout_profile", {}).get("config_key")
        == "LLM_B17_EXPLANATION_TIMEOUT_MS"
    )
    assert (
        runtime_p2_lock.get("output_envelope", {}).get("schema_key")
        == "attribution_explanation_fastpath_v1"
    )
    assert runtime_p2_lock.get("output_envelope", {}).get("summary_max_length") == 320
    runtime_p3_lock = runtime_operation.get("x-skeldir-b17-p3", {})
    assert (
        runtime_p3_lock.get("implementation_status")
        == "deterministic_watermark_cache_identity_replay_rejection"
    )
    runtime_stale_policy = runtime_p3_lock.get("stale_replay_policy", {})
    assert runtime_stale_policy.get("stale_replay_rejection_required") is True
    assert runtime_stale_policy.get("provider_reentry_on_stale_forbidden") is True
    runtime_p4_lock = runtime_operation.get("x-skeldir-b17-p4", {})
    assert (
        runtime_p4_lock.get("implementation_status")
        == "cold_path_strategy_closed_with_bounded_event_prewarm"
    )
    runtime_strategy = runtime_p4_lock.get("cold_path_strategy", {})
    assert runtime_strategy.get("decision") == "prewarm_required"
    assert runtime_strategy.get("warm_path_only_proof_forbidden") is True
    runtime_execution_metadata = runtime_p4_lock.get("execution_metadata", {})
    assert set(runtime_execution_metadata.get("schema_required_fields", [])) >= {
        "execution_path_state",
        "cold_path_strategy",
        "prewarm_state",
    }

    explanation_schema = (
        runtime_openapi.get("components", {})
        .get("schemas", {})
        .get("AttributionNonAuthoritativeExplanation", {})
    )
    assert (
        explanation_schema.get("properties", {})
        .get("non_authoritative_summary", {})
        .get("maxLength")
        == 320
    )
    assert (
        explanation_schema.get("properties", {})
        .get("cache_replay_state", {})
        .get("type")
        == "string"
    )
    assert (
        explanation_schema.get("properties", {}).get("truth_snapshot", {}).get("$ref")
        == "#/components/schemas/AttributionTruthSnapshot"
    )
    assert (
        explanation_schema.get("properties", {})
        .get("execution_path_state", {})
        .get("type")
        == "string"
    )
    cold_path_strategy_schema = (
        explanation_schema.get("properties", {}).get("cold_path_strategy", {})
    )
    assert cold_path_strategy_schema.get("enum") == [
        "prewarm_required_event_driven_bounded"
    ] or cold_path_strategy_schema.get("const") == "prewarm_required_event_driven_bounded"
    assert (
        explanation_schema.get("properties", {}).get("prewarm_state", {}).get("$ref")
        == "#/components/schemas/AttributionPrewarmState"
    )
    assert set(explanation_schema.get("required", [])) >= {
        "execution_path_state",
        "cold_path_strategy",
        "prewarm_state",
    }
    prewarm_schema = (
        runtime_openapi.get("components", {})
        .get("schemas", {})
        .get("AttributionPrewarmState", {})
    )
    assert set(
        prewarm_schema.get("properties", {}).get("trigger_reason", {}).get("enum", [])
    ) >= {
        "triggered",
        "already_prewarmed_for_watermark",
        "tenant_hourly_cap_reached",
        "stale_replay_path_suppressed",
    }
    authoritative_schema = (
        runtime_openapi.get("components", {})
        .get("schemas", {})
        .get("AttributionAuthoritativeMetric", {})
    )
    assert (
        authoritative_schema.get("properties", {}).get("truth_snapshot", {}).get("$ref")
        == "#/components/schemas/AttributionTruthSnapshot"
    )


def test_b21_channels_route_mounted_and_runtime_openapi_converged():
    """B2.1-P0 hard gate: canonical channels route must be mounted and contract-aligned."""
    attribution_source = (
        Path(__file__).parent.parent.parent
        / "api-contracts"
        / "openapi"
        / "v1"
        / "attribution.yaml"
    )
    with open(attribution_source, "r", encoding="utf-8") as handle:
        source_doc = yaml.safe_load(handle) or {}

    canonical_path = "/api/attribution/channels"
    source_operation = source_doc.get("paths", {}).get(canonical_path, {}).get("get", {})
    assert source_operation.get("operationId") == "getChannelAttribution"
    source_responses = source_operation.get("responses", {})
    assert "422" in source_responses
    b21_lock = source_operation.get("x-skeldir-b21-p0", {})
    assert b21_lock.get("implementation_status") == "mounted_deterministic_channels_surface"

    routes = extract_fastapi_routes()
    route_keys = {f"{item['method']} {item['path']}" for item in routes}
    assert "GET /api/attribution/channels" in route_keys

    from app.main import app

    runtime_openapi = app.openapi()
    runtime_paths = runtime_openapi.get("paths", {})
    assert canonical_path in runtime_paths
    runtime_operation = runtime_paths[canonical_path]["get"]
    assert runtime_operation.get("operationId") == "getChannelAttribution"
    query_params = {
        item.get("name"): item
        for item in runtime_operation.get("parameters", [])
        if item.get("in") == "query"
    }
    assert "model_type" in query_params
    assert "recompute_job_id" in query_params
    assert query_params["model_type"].get("required") is True
    assert query_params["recompute_job_id"].get("required") is True
    assert "start_date" not in query_params
    assert "end_date" not in query_params

    responses = runtime_operation.get("responses", {})
    assert "200" in responses
    assert "304" in responses
    assert "422" in responses
    schema_ref = (
        responses["200"]
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
        .get("$ref")
    )
    assert schema_ref == "#/components/schemas/ChannelAttributionResponse"

    response_schema = (
        runtime_openapi.get("components", {})
        .get("schemas", {})
        .get("ChannelAttributionResponse", {})
    )
    assert set(response_schema.get("required", [])) >= {
        "projection",
        "channels",
        "total_revenue",
        "total_revenue_cents",
        "tenant_id",
        "last_updated",
        "data_freshness_seconds",
    }
    projection_schema = (
        runtime_openapi.get("components", {})
        .get("schemas", {})
        .get("ChannelProjectionIdentity", {})
    )
    assert set(projection_schema.get("required", [])) >= {
        "recompute_job_id",
        "model_type",
        "model_version",
        "window_start",
        "window_end",
    }

    channel_schema = (
        runtime_openapi.get("components", {})
        .get("schemas", {})
        .get("ChannelAttribution", {})
    )
    channel_name_schema = channel_schema.get("properties", {}).get("channel_name", {})
    if "$ref" in channel_name_schema:
        ref_name = channel_name_schema["$ref"].split("/")[-1]
        enum_values = (
            runtime_openapi.get("components", {})
            .get("schemas", {})
            .get(ref_name, {})
            .get("enum", [])
        )
    else:
        enum_values = channel_name_schema.get("enum", [])
    assert "Unknown" in enum_values
    allocation_ratio_schema = channel_schema.get("properties", {}).get("allocation_ratio", {})
    assert allocation_ratio_schema.get("type") == "string"
    assert allocation_ratio_schema.get("pattern") == "^(0|1)\\.\\d{5}$"
    attribution_weight_schema = channel_schema.get("properties", {}).get("attribution_weight", {})
    assert attribution_weight_schema.get("type") == "string"
    assert attribution_weight_schema.get("pattern") == "^(0|1)\\.\\d{5}$"
    confidence_schema = channel_schema.get("properties", {}).get("confidence_score", {})
    assert confidence_schema.get("type") == "string"
    assert confidence_schema.get("pattern") == "^(0|1)\\.\\d{3}$"

    frontend_types = (
        Path(__file__).parent.parent.parent / "frontend" / "src" / "types" / "api" / "attribution.ts"
    ).read_text(encoding="utf-8")
    assert "getChannelAttribution" in frontend_types
    assert "responses: {" in frontend_types
    assert "422:" in frontend_types
    assert "ATTRIBUTION_WINDOW_OUT_OF_RANGE" in frontend_types


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
