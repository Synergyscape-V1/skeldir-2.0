# B0.5.5 Phase 3 v4 ORM/CoC/Idempotency Remediation Evidence

## Repo Pin
```
branch: b055-phase3-v4-orm-coc-idempotency
tested_logic_sha: 1ab05359985ed9b743a39203972056186d87b850
current_pr_head_sha: 405e3c5cb81e7f65bf36c1710808e3422eb93a9e
authoritative_ci_run: https://github.com/Muk223/skeldir-2.0/actions/runs/20970419269
status:
(clean)
```

## 3.1 PR Head SHA + CI Run (baseline)
- PR: https://github.com/Muk223/skeldir-2.0/pull/19
- PR head SHA: 405e3c5cb81e7f65bf36c1710808e3422eb93a9e
- CI run: https://github.com/Muk223/skeldir-2.0/actions/runs/20970419269

## 3.2 ORM constraint mismatch (baseline)
### Migration unique constraint
File: alembic/versions/004_llm_subsystem/202601131610_add_llm_api_call_idempotency.py
```
op.create_unique_constraint(
    "uq_llm_api_calls_tenant_request_endpoint",
    "llm_api_calls",
    ["tenant_id", "request_id", "endpoint"],
)
```

### ORM model (LLMApiCall __table_args__)
File: backend/app/models/llm.py
```
__table_args__ = (
    CheckConstraint("input_tokens >= 0", name="ck_llm_api_calls_input_tokens_positive"),
    CheckConstraint("output_tokens >= 0", name="ck_llm_api_calls_output_tokens_positive"),
    CheckConstraint("cost_cents >= 0", name="ck_llm_api_calls_cost_cents_positive"),
    CheckConstraint("latency_ms >= 0", name="ck_llm_api_calls_latency_ms_positive"),
)
```

## 3.3 Idempotency + parity coverage (baseline)
### Idempotency tests currently present
File: backend/tests/test_b055_llm_worker_stubs.py
```
async def test_llm_route_idempotency_prevents_duplicate_audit_rows(test_tenant):
    ...
```
No explicit explanation idempotency test present.

### Parity test scope (constraints not checked)
File: backend/tests/test_b055_llm_model_parity.py
```
for col_name, db_col in db_columns.items():
    model_col = model_columns[col_name]
    assert _normalize_type(db_col["type"]) == _normalize_type(model_col.type)
    assert db_col["nullable"] == model_col.nullable
    db_has_default = db_col["default"] is not None
    model_has_default = model_col.server_default is not None
    assert db_has_default == model_has_default
```

## Hypotheses
- H-ORM-1: TRUE (parity test ignores constraints; ORM missing UniqueConstraint)
- H-COC-1: TRUE (evidence not yet pinned to PR head SHA)
- H-IDEMP-1: TRUE (idempotency implemented but no explanation-specific test)

## Remediation (v4)
### ORM constraint parity applied
File: backend/app/models/llm.py
```
__table_args__ = (
    CheckConstraint("input_tokens >= 0", name="ck_llm_api_calls_input_tokens_positive"),
    CheckConstraint("output_tokens >= 0", name="ck_llm_api_calls_output_tokens_positive"),
    CheckConstraint("cost_cents >= 0", name="ck_llm_api_calls_cost_cents_positive"),
    CheckConstraint("latency_ms >= 0", name="ck_llm_api_calls_latency_ms_positive"),
    UniqueConstraint(
        "tenant_id",
        "request_id",
        "endpoint",
        name="uq_llm_api_calls_tenant_request_endpoint",
    ),
)
```

### Explanation idempotency test added
File: backend/tests/test_b055_llm_worker_stubs.py
```
async def test_llm_explanation_idempotency_prevents_duplicate_audit_rows(test_tenant):
    ...
```

## CI evidence (PR head SHA)
- PR: https://github.com/Muk223/skeldir-2.0/pull/19
- PR head SHA: 405e3c5cb81e7f65bf36c1710808e3422eb93a9e
- CI run: https://github.com/Muk223/skeldir-2.0/actions/runs/20970419269

### Topology invariants (Test Backend job)
```
Test Backend  Run tests  2026-01-13T19:51:14.2098672Z 
tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_explicit_queues_defined PASSED [ 20%]
Test Backend  Run tests  2026-01-13T19:51:14.2105915Z 
tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_task_routing_rules_defined PASSED [ 40%]
Test Backend  Run tests  2026-01-13T19:51:14.2132903Z 
tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_llm_task_routes_via_router PASSED [ 60%]
Test Backend  Run tests  2026-01-13T19:51:14.2175755Z 
tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_task_names_stable PASSED [ 80%]
Test Backend  Run tests  2026-01-13T19:51:14.3341598Z 
tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_queue_routing_deterministic PASSED [100%]
```

### Idempotency + integrity + parity (Celery Foundation job)
```
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-13T19:52:24.3361030Z 
tests/test_b055_llm_worker_stubs.py::test_llm_stub_atomic_writes_roll_back_on_failure PASSED [ 70%]
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-13T19:52:24.9631241Z 
tests/test_b055_llm_worker_stubs.py::test_llm_stub_rls_blocks_cross_tenant_reads PASSED [ 83%]
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-13T19:52:25.2840039Z 
tests/test_b055_llm_worker_stubs.py::test_llm_explanation_idempotency_prevents_duplicate_audit_rows PASSED [ 90%]
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-13T19:52:25.5888223Z 
tests/test_b055_llm_worker_stubs.py::test_llm_monthly_costs_concurrent_updates_are_atomic PASSED [ 93%]
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-13T19:52:25.7627037Z 
tests/test_b055_llm_worker_stubs.py::test_llm_route_idempotency_prevents_duplicate_audit_rows PASSED [ 96%]
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-13T19:52:28.5669390Z 
tests/test_b055_llm_model_parity.py::test_llm_models_reflection_parity PASSED [100%]
```
