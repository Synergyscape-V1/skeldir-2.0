# B0.5.5 Phase 3 EG9/Topology/Idempotency Context (Pre-Remediation)

## Repo Pin
```
branch: b055-phase3-eg9-topology-idempotency-remediation
HEAD: a087fadacedf7bb99e63071ad11bf8c2c1879df7
status:
?? docs/forensics/b055_phase3_eg9_topology_idempotency_context.md
```

## Topology Baseline (Task Names + Routing)
### Task definitions (`backend/app/tasks/llm.py`)
```
   37: @celery_app.task(
   38:     bind=True,
   39:     name="app.tasks.llm.route",
   40:     routing_key="llm.task",
   41:     max_retries=3,
   42:     default_retry_delay=30,
   43: )
   63: @celery_app.task(bind=True, name="app.tasks.llm.explanation", max_retries=3, default_retry_delay=30)
   83: @celery_app.task(bind=True, name="app.tasks.llm.investigation", max_retries=3, default_retry_delay=30)
  103: @celery_app.task(bind=True, name="app.tasks.llm.budget_optimization", max_retries=3, default_retry_delay=30)
```

### Queue routing config (`backend/app/celery_app.py`)
```
 175:         task_queues=[
 176:             Queue('housekeeping', routing_key='housekeeping.#'),
 177:             Queue('maintenance', routing_key='maintenance.#'),
 178:             Queue(QUEUE_LLM, routing_key='llm.#'),
 179:             Queue('attribution', routing_key='attribution.#'),
 180:         ],
 181:         task_routes={
 182:             'app.tasks.housekeeping.*': {'queue': 'housekeeping', 'routing_key': 'housekeeping.task'},
 183:             'app.tasks.maintenance.*': {'queue': 'maintenance', 'routing_key': 'maintenance.task'},
 184:             'app.tasks.matviews.*': {'queue': 'maintenance', 'routing_key': 'maintenance.task'},
 185:             'app.tasks.llm.*': {'queue': QUEUE_LLM, 'routing_key': 'llm.task'},
 186:             'app.tasks.attribution.*': {'queue': 'attribution', 'routing_key': 'attribution.task'},
 187:             'app.tasks.r4_failure_semantics.*': {'queue': 'housekeeping', 'routing_key': 'housekeeping.task'},
 188:             'app.tasks.r6_resource_governance.*': {'queue': 'housekeeping', 'routing_key': 'housekeeping.task'},
 189:         },
```

## EG9 DI Gap Baseline (Worker Coupled to get_session)
### Worker import + usage (`backend/app/workers/llm.py`)
```
  18: from app.db.session import get_session
 133: async def route_request(
 138:     request_id = _resolve_request_id(model)
 139:     correlation_id = _resolve_correlation_id(model)
 140:     async with get_session(tenant_id=model.tenant_id) as session:
 141:         async with session.begin_nested():
 142:             api_call = await _record_api_call(
```

## Idempotency Surface (llm_api_calls)
### Migration definition (`alembic/versions/004_llm_subsystem/202512081500_create_llm_tables.py`)
```
  54:         CREATE TABLE llm_api_calls (
  55:             id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  56:             tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  57:             created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  58:             endpoint TEXT NOT NULL,
  59:             model TEXT NOT NULL,
  60:             input_tokens INTEGER NOT NULL CHECK (input_tokens >= 0),
  61:             output_tokens INTEGER NOT NULL CHECK (output_tokens >= 0),
  62:             cost_cents INTEGER NOT NULL CHECK (cost_cents >= 0),
  63:             latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
  64:             was_cached BOOLEAN DEFAULT FALSE,
  65:             request_metadata JSONB
  66:         )
```

### Indexes (no unique idempotency key)
```
  70:         CREATE INDEX idx_llm_calls_tenant_endpoint
  71:             ON llm_api_calls(tenant_id, endpoint, created_at DESC)
  75:         CREATE INDEX idx_llm_calls_tenant_created_at
  76:             ON llm_api_calls(tenant_id, created_at DESC)
```
