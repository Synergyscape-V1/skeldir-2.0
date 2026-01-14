# B0.5.5 Phase 3 v4 Request ID Stability Remediation Evidence

## Repo pin
```
branch: b055-phase3-v4-orm-coc-idempotency
pr: https://github.com/Muk223/skeldir-2.0/pull/19
head_sha: 671ea4bf643534840273d0affd213c05db6650c3
ci_run: https://github.com/Muk223/skeldir-2.0/actions/runs/20973767676
status: clean
```

## H1 - Retry regenerates request_id (validated)
Evidence (request_id derived from stable inputs; no self.request.id fallback):
```
39:def _stable_request_id(tenant_id: UUID, endpoint: str, correlation_id: str) -> str:
44:def _resolve_request_context(
52:    request = request_id or _stable_request_id(tenant_id, endpoint, correlation)
90:    correlation, request_id = _resolve_request_context(
140:    correlation, request_id = _resolve_request_context(
194:    correlation, request_id = _resolve_request_context(
248:    correlation, request_id = _resolve_request_context(
```

## H2 - Callers omit request_id (validated)
Evidence (only tests call delay/apply_async; no production callsites passing request_id):
```
backend	ests	est_b051_celery_foundation.py:343:            llm_routing_worker.delay(payload={}).get(timeout=5)
```

## H3 - Retry path does not preserve ids (fixed)
Evidence (retry kwargs carry correlation_id + request_id):
```
    except Exception as exc:
        raise self.retry(
            exc=exc,
            kwargs=_retry_kwargs(
                payload=payload,
                tenant_id=tenant_id,
                correlation_id=correlation,
                request_id=request_id,
                max_cost_cents=max_cost_cents,
            ),
        )
```

## H4 - Tests only cover injected request_id (fixed)
Evidence (new retry test without request_id):
```
async def test_llm_explanation_retry_preserves_request_id_when_omitted(test_tenant, monkeypatch):
    ...
    with pytest.raises(RetryCapture, match="retry"):
        llm_explanation_worker.run(
            payload,
            tenant_id=test_tenant,
            max_cost_cents=0,
            force_failure=True,
        )
    ...
    llm_explanation_worker.run(**retry_kwargs)
    llm_explanation_worker.run(**retry_kwargs)
    ...
    assert len(api_calls) == 1
```

## H5 - Chain-of-custody mismatch (fixed)
Evidence (local HEAD matches PR head; CI run for that SHA):
```
local_head: 671ea4bf643534840273d0affd213c05db6650c3
pr_head:    671ea4bf643534840273d0affd213c05db6650c3
ci_run:     https://github.com/Muk223/skeldir-2.0/actions/runs/20973767676
```

## Diff summary (request_id origin change)
```
671ea4b Stabilize LLM request_id across retries
M	backend/app/tasks/llm.py
M	backend/tests/test_b055_llm_worker_stubs.py
```

## Local test outputs
### Topology gate (local)
```
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_explicit_queues_defined PASSED [ 20%]
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_task_routing_rules_defined PASSED [ 40%]
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_llm_task_routes_via_router PASSED [ 60%]
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_task_names_stable PASSED [ 80%]
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_queue_routing_deterministic PASSED [100%]

================ 5 passed, 6 deselected, 129 warnings in 0.36s ================
```

### Idempotency retry (local) - blocked by DB auth
```
backend/tests/test_b055_llm_worker_stubs.py::test_llm_explanation_retry_preserves_request_id_when_omitted ERROR [100%]
...
asyncpg.exceptions.InvalidPasswordError: password authentication failed for user 'app_user'
```

## CI evidence (PR head SHA)
### Topology invariants (Test Backend)
```
Test Backend Run tests 2026-01-13T21:48:42.3540593Z tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_explicit_queues_defined PASSED [ 20%]
Test Backend Run tests 2026-01-13T21:48:42.3548844Z tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_task_routing_rules_defined PASSED [ 40%]
Test Backend Run tests 2026-01-13T21:48:42.3577979Z tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_llm_task_routes_via_router PASSED [ 60%]
Test Backend Run tests 2026-01-13T21:48:42.3625477Z tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_task_names_stable PASSED [ 80%]
Test Backend Run tests 2026-01-13T21:48:42.4614802Z tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_queue_routing_deterministic PASSED [100%]
```

### Idempotency + integrity + parity (Celery Foundation B0.5.1)
```
Celery Foundation B0.5.1 Run Celery foundation tests 2026-01-13T21:49:50.8574201Z tests/test_b055_llm_worker_stubs.py::test_llm_stub_atomic_writes_roll_back_on_failure PASSED [ 68%]
Celery Foundation B0.5.1 Run Celery foundation tests 2026-01-13T21:49:51.4676567Z tests/test_b055_llm_worker_stubs.py::test_llm_stub_rls_blocks_cross_tenant_reads PASSED [ 81%]
Celery Foundation B0.5.1 Run Celery foundation tests 2026-01-13T21:49:51.7828850Z tests/test_b055_llm_worker_stubs.py::test_llm_explanation_idempotency_prevents_duplicate_audit_rows PASSED [ 87%]
Celery Foundation B0.5.1 Run Celery foundation tests 2026-01-13T21:49:52.0771755Z tests/test_b055_llm_worker_stubs.py::test_llm_explanation_retry_preserves_request_id_when_omitted PASSED [ 90%]
Celery Foundation B0.5.1 Run Celery foundation tests 2026-01-13T21:49:52.3765181Z tests/test_b055_llm_worker_stubs.py::test_llm_monthly_costs_concurrent_updates_are_atomic PASSED [ 93%]
Celery Foundation B0.5.1 Run Celery foundation tests 2026-01-13T21:49:52.5470252Z tests/test_b055_llm_worker_stubs.py::test_llm_route_idempotency_prevents_duplicate_audit_rows PASSED [ 96%]
Celery Foundation B0.5.1 Run Celery foundation tests 2026-01-13T21:49:55.0232679Z tests/test_b055_llm_model_parity.py::test_llm_models_reflection_parity PASSED [100%]
```
