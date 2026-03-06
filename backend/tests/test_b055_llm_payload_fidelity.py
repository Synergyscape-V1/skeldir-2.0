from __future__ import annotations

from uuid import uuid4

from kombu.serialization import registry

from app.celery_app import _ensure_celery_configured, celery_app
from app.schemas.llm_payloads import LLMTaskPayload
from app.services.llm_dispatch import enqueue_llm_task
from app.tasks.llm import llm_explanation_worker


def test_llm_payload_json_roundtrip_fidelity():
    _ensure_celery_configured()
    serializer = celery_app.conf["task_serializer"]
    assert serializer == "json"
    assert celery_app.conf["result_serializer"] == "json"
    accept_content = celery_app.conf.get("accept_content", [])
    assert "json" in accept_content
    assert "application/x-python-serialize" not in accept_content

    request_id = str(uuid4())
    payload = LLMTaskPayload(
        tenant_id=uuid4(),
        user_id=uuid4(),
        correlation_id=str(uuid4()),
        request_id=request_id,
        prompt={"question": "explain deterministic pipeline"},
        max_cost_cents=0,
    )

    content_type, content_encoding, body = registry.dumps(
        payload.model_dump(mode="json"),
        serializer=serializer,
    )
    decoded = registry.loads(body, content_type, content_encoding)
    rehydrated = LLMTaskPayload.model_validate(decoded)

    assert rehydrated.model_dump(mode="json") == payload.model_dump(mode="json")


def test_llm_enqueue_payload_mapping(monkeypatch):
    captured = {}

    def _fake_apply_async(*, kwargs, queue=None, correlation_id=None):
        captured["kwargs"] = kwargs
        captured["queue"] = queue
        captured["correlation_id"] = correlation_id

        class _Result:
            id = "test-task-id"

        return _Result()

    monkeypatch.setattr(llm_explanation_worker, "apply_async", _fake_apply_async)

    payload = LLMTaskPayload(
        tenant_id=uuid4(),
        user_id=uuid4(),
        correlation_id=str(uuid4()),
        request_id=str(uuid4()),
        prompt={"prompt": "payload fidelity"},
        max_cost_cents=0,
    )
    result = enqueue_llm_task("explanation", payload)

    assert result.id == "test-task-id"
    assert captured["kwargs"]["payload"] == payload.prompt
    assert captured["kwargs"]["user_id"] == payload.user_id
    assert captured["kwargs"]["correlation_id"] == payload.correlation_id
    assert captured["kwargs"]["request_id"] == payload.request_id
    assert captured["kwargs"]["max_cost_cents"] == payload.max_cost_cents
    assert captured["kwargs"]["authority_envelope"]["context_type"] == "system"
    assert captured["kwargs"]["authority_envelope"]["tenant_id"] == str(payload.tenant_id)
    assert captured["correlation_id"] == payload.correlation_id
