# B0.5.5 Phase 3 EG9/Topology/Idempotency Remediation Evidence

## Repo Pin
```
branch: b055-phase3-eg9-topology-idempotency-remediation
candidate_sha: 214a98d3a1423ac3d1d3166097d8a6cbfef5a6de
status:
(clean)
```

## EG-A Worker Purity (no get_session in workers)
Command:
```
rg -n "get_session" backend/app/workers/llm.py
```
Output:
```
<no matches>
```

## EG-B Controller Ownership (tasks inject session)
Command:
```
rg -n "get_session" backend/app/tasks/llm.py
```
Output:
```
13:from app.db.session import get_session
71:        async with get_session(tenant_id=model.tenant_id) as session:
104:        async with get_session(tenant_id=model.tenant_id) as session:
137:        async with get_session(tenant_id=model.tenant_id) as session:
170:        async with get_session(tenant_id=model.tenant_id) as session:
```

## EG-C Topology Gate (task names + routing)
### Task name strings preserved (`backend/app/tasks/llm.py`)
```
  38: @celery_app.task(
  39:     bind=True,
  40:     name="app.tasks.llm.route",
  41:     routing_key="llm.task",
  42:     max_retries=3,
  43:     default_retry_delay=30,
  44: )
  77: @celery_app.task(bind=True, name="app.tasks.llm.explanation", max_retries=3, default_retry_delay=30)
 110: @celery_app.task(bind=True, name="app.tasks.llm.investigation", max_retries=3, default_retry_delay=30)
 143: @celery_app.task(bind=True, name="app.tasks.llm.budget_optimization", max_retries=3, default_retry_delay=30)
```

### Topology test execution
Command:
```
$env:DATABASE_URL='postgresql+asyncpg://app_user:app_user@127.0.0.1:5432/skeldir_validation'; pytest -q backend/tests/test_b052_queue_topology_and_dlq.py -k "QueueTopology" -q
```
Output:
```
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_explicit_queues_defined PASSED [ 20%]
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_task_routing_rules_defined PASSED [ 40%]
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_llm_task_routes_via_router PASSED [ 60%]
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_task_names_stable PASSED [ 80%]
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_queue_routing_deterministic PASSED [100%]

================ 5 passed, 6 deselected, 129 warnings in 0.47s ================
```

### CI topology proof (Test Backend job)
Run: https://github.com/Muk223/skeldir-2.0/actions/runs/20966812220
```
Test Backend  Run tests  2026-01-13T17:48:04.1567801Z 
tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_explicit_queues_defined PASSED [ 20%]
Test Backend  Run tests  2026-01-13T17:48:04.1577032Z 
tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_task_routing_rules_defined PASSED [ 40%]
Test Backend  Run tests  2026-01-13T17:48:04.1609532Z 
tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_llm_task_routes_via_router PASSED [ 60%]
Test Backend  Run tests  2026-01-13T17:48:04.1662857Z 
tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_task_names_stable PASSED [ 80%]
Test Backend  Run tests  2026-01-13T17:48:04.3404648Z 
tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_queue_routing_deterministic PASSED [100%]
```

## EG-D Idempotency Gate
### Migration (unique constraint + request_id column)
File: alembic/versions/004_llm_subsystem/202601131610_add_llm_api_call_idempotency.py
```
revision = "202601131610"

down_revision = "202601031930"

op.add_column(
    "llm_api_calls",
    sa.Column(
        "request_id",
        sa.Text(),
        nullable=False,
        server_default=sa.text("md5(random()::text || clock_timestamp()::text)"),
    ),
)

op.execute(
    """
    UPDATE llm_api_calls
    SET request_id = COALESCE(
        NULLIF(request_metadata->>'request_id', ''),
        request_id
    )
    """
)

op.alter_column("llm_api_calls", "request_id", server_default=None)

op.create_unique_constraint(
    "uq_llm_api_calls_tenant_request_endpoint",
    "llm_api_calls",
    ["tenant_id", "request_id", "endpoint"],
)
```

### Idempotency test execution
Command:
```
$env:DATABASE_URL='postgresql+asyncpg://app_user:app_user@127.0.0.1:5432/skeldir_validation'; pytest -q backend/tests/test_b055_llm_worker_stubs.py backend/tests/test_b055_llm_model_parity.py -q
```
Output:
```
backend/tests/test_b055_llm_worker_stubs.py::test_llm_stub_atomic_writes_roll_back_on_failure PASSED [ 11%]
backend/tests/test_b055_llm_worker_stubs.py::test_llm_route_stub_writes_audit_rows PASSED [ 22%]
backend/tests/test_b055_llm_worker_stubs.py::test_llm_investigation_stub_writes_job PASSED [ 33%]
backend/tests/test_b055_llm_worker_stubs.py::test_llm_budget_stub_writes_job PASSED [ 44%]
backend/tests/test_b055_llm_worker_stubs.py::test_llm_stub_rls_blocks_cross_tenant_reads PASSED [ 55%]
backend/tests/test_b055_llm_worker_stubs.py::test_llm_explanation_stub_writes_api_call PASSED [ 66%]
backend/tests/test_b055_llm_worker_stubs.py::test_llm_monthly_costs_concurrent_updates_are_atomic PASSED [ 77%]
backend/tests/test_b055_llm_worker_stubs.py::test_llm_route_idempotency_prevents_duplicate_audit_rows PASSED [ 88%]
backend/tests/test_b055_llm_model_parity.py::test_llm_models_reflection_parity PASSED [100%]

======================= 9 passed, 129 warnings in 2.24s =======================
```

### CI idempotency + integrity proof (Celery Foundation job)
Run: https://github.com/Muk223/skeldir-2.0/actions/runs/20966812220
```
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-13T17:49:08.9130528Z 
tests/test_b055_llm_worker_stubs.py::test_llm_stub_atomic_writes_roll_back_on_failure PASSED [ 73%]
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-13T17:49:09.5463634Z 
tests/test_b055_llm_worker_stubs.py::test_llm_stub_rls_blocks_cross_tenant_reads PASSED [ 86%]
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-13T17:49:10.0039763Z 
tests/test_b055_llm_worker_stubs.py::test_llm_monthly_costs_concurrent_updates_are_atomic PASSED [ 93%]
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-13T17:49:10.1826194Z 
tests/test_b055_llm_worker_stubs.py::test_llm_route_idempotency_prevents_duplicate_audit_rows PASSED [ 96%]
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-13T17:49:14.2483660Z 
tests/test_b055_llm_model_parity.py::test_llm_models_reflection_parity PASSED [100%]
```

## EG-E Integrity Regression (atomicity/concurrency/RLS/parity)
Covered by the same Phase 3 test suite output above (atomicity, concurrency, RLS, parity).

## EG-F CI Adjudication (pass)
- PR: https://github.com/Muk223/skeldir-2.0/pull/18
- CI run: https://github.com/Muk223/skeldir-2.0/actions/runs/20966812220
- CI jobs: CI + R5: Determinism + Scaling Proof (green)
- Post-merge main CI run: https://github.com/Muk223/skeldir-2.0/actions/runs/20967066505

## EG-G Scope/Hygiene
```
git diff --name-status origin/main...HEAD
A	alembic/versions/004_llm_subsystem/202601131610_add_llm_api_call_idempotency.py
M	.github/workflows/r5-remediation.yml
M	backend/app/models/llm.py
M	backend/app/tasks/llm.py
M	backend/app/workers/llm.py
M	backend/tests/test_b055_llm_worker_stubs.py
M	docs/forensics/INDEX.md
A	docs/forensics/b055_phase3_eg9_topology_idempotency_context.md
A	docs/forensics/b055_phase3_eg9_topology_idempotency_remediation_evidence.md
```
