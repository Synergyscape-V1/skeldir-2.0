"""Contract tests for the LLM task payload schema."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.llm_payloads import LLMTaskPayload


def _render_schema() -> str:
    schema_fn = getattr(LLMTaskPayload, "model_json_schema", None)
    schema = schema_fn() if schema_fn else LLMTaskPayload.schema()
    return json.dumps(schema, sort_keys=True, indent=2)


def test_llm_payload_schema_matches_snapshot() -> None:
    snapshot_path = Path(__file__).parent / "snapshots" / "llm_task_payload.schema.json"
    snapshot = snapshot_path.read_text(encoding="utf-8")
    assert _render_schema() == snapshot


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"tenant_id": str(uuid4()), "max_cost_cents": "invalid"},
    ],
)
def test_llm_payload_invalid_rejected(payload: dict) -> None:
    with pytest.raises(ValidationError):
        LLMTaskPayload(**payload)
