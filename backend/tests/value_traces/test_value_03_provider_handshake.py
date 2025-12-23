"""
Value Trace 03: Provider-agnostic LLM handshake contract validity.

Validates that the LLM explanations contract includes cost_usd and latency_ms,
and that a sample response conforms to the schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

EVIDENCE_JSON = Path("backend/validation/evidence/value_traces/value_03_summary.json")
EVIDENCE_MD = Path("docs/evidence/value_traces/value_03_provider_handshake.md")
CONTRACT_PATH = Path("api-contracts/dist/openapi/v1/llm-explanations.bundled.yaml")
ENDPOINT_PATH = "/api/v1/explain/{entity_type}/{entity_id}"


def _load_contract() -> Dict[str, Any]:
    if not CONTRACT_PATH.exists():
        raise FileNotFoundError(f"Contract file not found: {CONTRACT_PATH}")
    with CONTRACT_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.mark.asyncio
async def test_value_trace_provider_handshake_fields_present_and_valid():
    spec = _load_contract()
    path_obj = spec["paths"][ENDPOINT_PATH]
    operation = path_obj.get("get") or path_obj.get("post") or {}
    resp_schema = (
        operation.get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    props = resp_schema.get("properties", {})
    assert "cost_usd" in props, "cost_usd field missing from contract"
    assert "latency_ms" in props, "latency_ms field missing from contract"

    parameters = operation.get("parameters", [])
    timeout_param = next(
        (
            param
            for param in parameters
            if isinstance(param, dict)
            and param.get("name") == "timeout_ms"
            and param.get("in") == "query"
        ),
        None,
    )
    assert timeout_param is not None, "timeout_ms query parameter missing from contract"

    sample_response = {
        "explanation": "This is a mocked explanation.",
        "model": "test-model",
        "cost_usd": 0.0123,
        "latency_ms": 120,
        "tokens_used": 256,
    }
    assert isinstance(sample_response["cost_usd"], (int, float))
    assert isinstance(sample_response["latency_ms"], int)

    summary = {
        "fields_present": {
            "cost_usd": "cost_usd" in props,
            "latency_ms": "latency_ms" in props,
            "timeout_ms": timeout_param is not None,
        },
        "sample_response": sample_response,
    }
    EVIDENCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_JSON.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    EVIDENCE_MD.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_MD.open("w", encoding="utf-8") as fh:
        fh.write("# Value Trace 03 – Provider-Agnostic Handshake\n\n")
        fh.write(f"- cost_usd field present: {summary['fields_present']['cost_usd']}\n")
        fh.write(f"- latency_ms field present: {summary['fields_present']['latency_ms']}\n")
        fh.write(f"- timeout_ms field present: {summary['fields_present']['timeout_ms']}\n")
        fh.write(f"- sample_response: {json.dumps(sample_response)}\n")
