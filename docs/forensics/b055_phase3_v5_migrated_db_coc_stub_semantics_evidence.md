# B0.5.5 Phase 3 v5 Migrated DB + CoC + Stub Semantics Evidence

## Artifact promotion snapshot (Option 2)
- PR: https://github.com/Muk223/skeldir-2.0/pull/19
- tested_logic_sha: 3893c70526c0e1348d609f6f2da5aff22881d234
- current_pr_head_sha: (doc-only promotion commit; read from PR head in GitHub to avoid self-referential hash)
- authoritative_ci_run_for_logic: https://github.com/Muk223/skeldir-2.0/actions/runs/20979320024
- checks: green on tested_logic_sha

## Test DB construction audit (H1)
### create_all/drop_all search
```
# rg -n "create_all|drop_all|Base.metadata" backend/tests backend/app -S
# (no matches)
```
### Fixture review (no ORM schema fabrication)
`backend/tests/conftest.py` does not call `Base.metadata.create_all()` or `drop_all()`; it only uses `engine.begin()` to insert tenants.

## Migration execution audit (H2)
### CI migration step (Celery Foundation job)
```
Celery Foundation B0.5.1  Run migrations  2026-01-14T01:47:50.8386437Z alembic upgrade head
```
### Workflow wiring (schema created by Alembic)
`.github/workflows/ci.yml` (Celery Foundation job):
```
- name: Run migrations
  run: |
    alembic upgrade 202511131121
    alembic upgrade skeldir_foundation@head
    alembic upgrade head
```

## Constraint catalog proof (EG-B)
### Catalog test (DB-level)
`backend/tests/test_b055_llm_worker_stubs.py`:
```
async def test_llm_api_calls_unique_constraint_present():
    ...
    WHERE con.conname = 'uq_llm_api_calls_tenant_request_endpoint'
      AND rel.relname = 'llm_api_calls'
```
### CI pass (Celery Foundation job)
```
tests/test_b055_llm_worker_stubs.py::test_llm_api_calls_unique_constraint_present PASSED
```

## Stub semantics audit (H4)
### ORM defaults (no default for model/request_metadata)
`backend/app/models/llm.py`:
```
model: Mapped[str] = mapped_column(Text, nullable=False)
request_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
```
### Worker write-site sets markers explicitly
`backend/app/workers/llm.py`:
```
insert(LLMApiCall).values(
    ...
    model=_STUB_MODEL,
    ...
    request_metadata={
        "stubbed": True,
        "request_id": request_id,
        "correlation_id": correlation_id,
    },
)
```
### Tests assert persisted markers
`backend/tests/test_b055_llm_worker_stubs.py`:
```
assert api_call.model == "llm_stub"
assert api_call.request_metadata is not None
assert api_call.request_metadata.get("stubbed") is True
```

## Idempotency + retry proofs (EG-D)
CI (Celery Foundation job):
```
tests/test_b055_llm_worker_stubs.py::test_llm_explanation_retry_preserves_request_id_when_omitted PASSED
tests/test_b055_llm_worker_stubs.py::test_llm_route_idempotency_prevents_duplicate_audit_rows PASSED
```

## Topology invariants (EG-E)
CI (Test Backend job):
```
TestQueueTopology::test_explicit_queues_defined PASSED
TestQueueTopology::test_task_routing_rules_defined PASSED
TestQueueTopology::test_llm_task_routes_via_router PASSED
TestQueueTopology::test_task_names_stable PASSED
TestQueueTopology::test_queue_routing_deterministic PASSED
```

## CI pass excerpts (tested logic SHA)
```
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-14T01:48:20.1156248Z tests/test_b055_llm_worker_stubs.py::test_llm_api_calls_unique_constraint_present PASSED
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-14T01:48:21.0484931Z tests/test_b055_llm_worker_stubs.py::test_llm_explanation_stub_writes_api_call PASSED
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-14T01:48:21.5192906Z tests/test_b055_llm_worker_stubs.py::test_llm_explanation_retry_preserves_request_id_when_omitted PASSED
Celery Foundation B0.5.1  Run Celery foundation tests  2026-01-14T01:48:25.4809362Z tests/test_b055_llm_model_parity.py::test_llm_models_reflection_parity PASSED
```
