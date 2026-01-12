# B0.5.5 Phase 3 Remediation v2 — Integrity Evidence Pack

## Repo Pin
- Branch: b055-phase3-worker-stubs
- HEAD: 93b58beb442798c217ba1a03c80bb280ab806a0e
- Status:
```
 M frontend/src/assets/brand/colors.css
```

## Environment Investigation
### netstat (5432 listener)
```
  TCP    0.0.0.0:5432           0.0.0.0:0              LISTENING       5272
  TCP    [::]:5432              [::]:0                 LISTENING       5272
```

### docker ps (Docker daemon)
```
error during connect: Get "http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine/v1.51/containers/json": open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```

### docker compose ps
```
no configuration file provided: not found
```

### psql connectivity
```
 ?column? 
----------
        1
(1 row)
```

### alembic upgrade head (sync DSN)
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
```

## Contract Coupling Proof
### LLMTaskPayload usage (tasks + workers)
```
backend\app\workers\llm.py:25:from app.schemas.llm_payloads import LLMTaskPayload
backend\app\workers\llm.py:32:def _resolve_request_id(model: LLMTaskPayload) -> str:
backend\app\workers\llm.py:36:def _resolve_correlation_id(model: LLMTaskPayload) -> str:
backend\app\workers\llm.py:48:    model: LLMTaskPayload,
backend\app\workers\llm.py:134:    model: LLMTaskPayload,
backend\app\workers\llm.py:179:    model: LLMTaskPayload,
backend\app\workers\llm.py:224:    model: LLMTaskPayload,
backend\app\workers\llm.py:279:    model: LLMTaskPayload,
backend\app\tasks\llm.py:14:from app.schemas.llm_payloads import LLMTaskPayload
backend\app\tasks\llm.py:26:def _prepare_context(model: LLMTaskPayload) -> str:
backend\app\tasks\llm.py:47:    model = LLMTaskPayload.model_validate(
backend\app\tasks\llm.py:67:    model = LLMTaskPayload.model_validate(
backend\app\tasks\llm.py:87:    model = LLMTaskPayload.model_validate(
backend\app\tasks\llm.py:107:    model = LLMTaskPayload.model_validate(
```

### Provider/HTTP leakage scan (workers/tasks)
```
<no matches>
```

## Code Excerpts (Exact Blocks)
### Worker atomic writes + monthly upsert (`backend/app/workers/llm.py`)
```
  73: def _build_model_breakdown_update(
  74:     *,
  75:     model_label: str,
  76:     cost_cents: int,
  77:     calls: int,
  78: ):
  79:     base_breakdown = func.coalesce(LLMMonthlyCost.model_breakdown, cast("{}", JSONB))
  80:     existing_calls = func.coalesce(
  81:         cast(func.jsonb_extract_path_text(base_breakdown, model_label, "calls"), Integer),
  82:         0,
  83:     )
  84:     existing_cost = func.coalesce(
  85:         cast(func.jsonb_extract_path_text(base_breakdown, model_label, "cost_cents"), Integer),
  86:         0,
  87:     )
  88:     new_entry = func.jsonb_build_object(
  89:         "calls",
  90:         existing_calls + literal(calls),
  91:         "cost_cents",
  92:         existing_cost + literal(cost_cents),
  93:     )
  94:     path = cast([model_label], ARRAY(Text))
  95:     return func.jsonb_set(base_breakdown, path, new_entry, True)
  96: 
  98: async def record_monthly_costs(
  99:     session: AsyncSession,
 100:     *,
 101:     tenant_id: UUID,
 102:     model_label: str,
 103:     cost_cents: int,
 104:     calls: int,
 105: ) -> None:
 106:     month = _month_start_utc()
 107:     insert_stmt = (
 108:         insert(LLMMonthlyCost)
 109:         .values(
 110:             tenant_id=tenant_id,
 111:             month=month,
 112:             total_cost_cents=cost_cents,
 113:             total_calls=calls,
 114:             model_breakdown={model_label: {"calls": calls, "cost_cents": cost_cents}},
 115:         )
 116:     )
 117:     excluded = insert_stmt.excluded
 118:     stmt = insert_stmt.on_conflict_do_update(
 119:         index_elements=["tenant_id", "month"],
 120:         set_={
 121:             "total_cost_cents": LLMMonthlyCost.total_cost_cents + excluded.total_cost_cents,
 122:             "total_calls": LLMMonthlyCost.total_calls + excluded.total_calls,
 123:             "model_breakdown": _build_model_breakdown_update(
 124:                 model_label=model_label,
 125:                 cost_cents=cost_cents,
 126:                 calls=calls,
 127:             ),
 128:         },
 129:     )
 130:     await session.execute(stmt)

 133: async def route_request(
 134:     model: LLMTaskPayload,
 135:     *,
 136:     force_failure: bool = False,
 137: ) -> Dict[str, Any]:
 138:     request_id = _resolve_request_id(model)
 139:     correlation_id = _resolve_correlation_id(model)
 140:     async with get_session(tenant_id=model.tenant_id) as session:
 141:         async with session.begin_nested():
 142:             api_call = await _record_api_call(
 143:                 session,
 144:                 model=model,
 145:                 endpoint="app.tasks.llm.route",
 146:                 request_id=request_id,
 147:                 correlation_id=correlation_id,
 148:             )
 149:             if force_failure:
 150:                 raise RuntimeError("forced failure after api call")
 151:             await record_monthly_costs(
 152:                 session,
 153:                 tenant_id=model.tenant_id,
 154:                 model_label=_STUB_MODEL,
 155:                 cost_cents=0,
 156:                 calls=1,
 157:             )
```

### Tenant RLS session setup (`backend/app/db/session.py`)
```
  86: @asynccontextmanager
  87: async def get_session(tenant_id: UUID) -> AsyncGenerator[AsyncSession, None]:
  88:     """
  89:     Yield an async session with tenant context set for RLS enforcement.
  90: 
  91:     The session variable `app.current_tenant_id` is set before yielding the
  92:     session so all subsequent queries evaluate row-level policies correctly.
  93:     Session lifecycle is managed automatically with rollback on exception and
  94:     closure on exit.
  95:     """
  96:     async with AsyncSessionLocal() as session:
  97:         await session.execute(
  98:             text(
  99:                 "SELECT set_config('app.current_tenant_id', :tenant_id, false)"
 100:             ),
 101:             {"tenant_id": str(tenant_id)},
 102:         )
 103:         try:
 104:             yield session
 105:             await session.commit()
 106:         except Exception:
 107:             await session.rollback()
 108:             raise
```

### Task model_validate coupling (`backend/app/tasks/llm.py`)
```
  45: def llm_routing_worker(self, payload: dict, tenant_id: UUID, correlation_id: Optional[str] = None, max_cost_cents: int = 0):
  46:     correlation = correlation_id or str(uuid4())
  47:     model = LLMTaskPayload.model_validate(
  48:         {
  49:             "tenant_id": tenant_id,
  50:             "correlation_id": correlation,
  51:             "prompt": payload,
  52:             "max_cost_cents": max_cost_cents,
  53:         }
  54:     )
```

## Integrity Tests (Postgres-backed)
### RLS/Atomicity/Concurrency test definitions (`backend/tests/test_b055_llm_worker_stubs.py`)
```
  30: def _assert_postgres_engine() -> None:
  31:     assert engine.dialect.name == "postgresql", "RLS tests must run on Postgres"
  34: @pytest.mark.asyncio
  35: async def test_llm_stub_atomic_writes_roll_back_on_failure(test_tenant):
  46:     with pytest.raises(RuntimeError, match="forced failure"):
  47:         await route_request(payload, force_failure=True)
  49:     async with get_session(tenant_id=test_tenant) as session:
  50:         api_calls = (
  51:             await session.execute(
  52:                 select(LLMApiCall).where(
  53:                     LLMApiCall.request_metadata["request_id"].astext == request_id
  54:                 )
  55:             )
  56:         ).scalars().all()
  57:         assert not api_calls, "Atomicity failed: api call persisted after failure"

 111: @pytest.mark.asyncio
 112: async def test_llm_stub_rls_blocks_cross_tenant_reads(test_tenant_pair):
 119:     async with engine.begin() as conn:
 120:         policies = await conn.execute(
 121:             text(
 122:                 """
 123:                 SELECT tablename
 124:                 FROM pg_policies
 125:                 WHERE schemaname = 'public'
 126:                   AND tablename IN (
 127:                     'llm_api_calls',
 128:                     'llm_monthly_costs',
 129:                     'investigations',
 130:                     'budget_optimization_jobs'
 131:                   )
 132:                 """
 133:             )
 134:         )
 135:         policy_tables = {row[0] for row in policies.fetchall()}
 136:         assert policy_tables == {
 137:             "llm_api_calls",
 138:             "llm_monthly_costs",
 139:             "investigations",
 140:             "budget_optimization_jobs",
 141:         }, f"Missing RLS policies: {policy_tables}"

 163: @pytest.mark.asyncio
 164: async def test_llm_monthly_costs_concurrent_updates_are_atomic(test_tenant):
 169:     async def _apply_increment():
 170:         async with get_session(tenant_id=test_tenant) as session:
 171:             async with session.begin_nested():
 172:                 await record_monthly_costs(
 173:                     session,
 174:                     tenant_id=test_tenant,
 175:                     model_label="concurrency",
 176:                     cost_cents=increment,
 177:                     calls=1,
 178:                 )
 180:     await asyncio.gather(*[_apply_increment() for _ in range(calls)])
 182:     async with get_session(tenant_id=test_tenant) as session:
 183:         row = (
 184:             await session.execute(
 185:                 select(LLMMonthlyCost).where(LLMMonthlyCost.tenant_id == test_tenant)
 186:             )
 187:         ).scalars().one()
 188:         assert row.total_cost_cents == increment * calls
 189:         assert row.total_calls == calls
```

### ORM parity test (`backend/tests/test_b055_llm_model_parity.py`)
```
  31: @pytest.mark.asyncio
  32: async def test_llm_models_reflection_parity():
  33:     assert engine.dialect.name == "postgresql", "ORM parity tests must run on Postgres"
  34:     table_map = {
  35:         "llm_api_calls": LLMApiCall,
  36:         "llm_monthly_costs": LLMMonthlyCost,
  37:         "investigations": Investigation,
  38:         "budget_optimization_jobs": BudgetOptimizationJob,
  39:     }
  41:     async with engine.connect() as conn:
  42:         def _inspect(sync_conn):
  43:             inspector = inspect(sync_conn)
  44:             for table_name, model in table_map.items():
  45:                 db_columns = {col["name"]: col for col in inspector.get_columns(table_name)}
```

### pytest output (local)
Command:
```
$env:DATABASE_URL='postgresql+asyncpg://app_user:app_user@127.0.0.1:5432/skeldir_validation'; pytest -q backend/tests/test_b055_llm_worker_stubs.py backend/tests/test_b055_llm_model_parity.py -q
```
Output:
```
backend/tests/test_b055_llm_worker_stubs.py::test_llm_stub_atomic_writes_roll_back_on_failure PASSED [ 12%]
backend/tests/test_b055_llm_worker_stubs.py::test_llm_route_stub_writes_audit_rows PASSED [ 25%]
backend/tests/test_b055_llm_worker_stubs.py::test_llm_investigation_stub_writes_job PASSED [ 37%]
backend/tests/test_b055_llm_worker_stubs.py::test_llm_budget_stub_writes_job PASSED [ 50%]
backend/tests/test_b055_llm_worker_stubs.py::test_llm_stub_rls_blocks_cross_tenant_reads PASSED [ 62%]
backend/tests/test_b055_llm_worker_stubs.py::test_llm_explanation_stub_writes_api_call PASSED [ 75%]
backend/tests/test_b055_llm_worker_stubs.py::test_llm_monthly_costs_concurrent_updates_are_atomic PASSED [ 87%]
backend/tests/test_b055_llm_model_parity.py::test_llm_models_reflection_parity PASSED [100%]

======================= 8 passed, 129 warnings in 1.81s =======================
```

## PR/CI
- PR: https://github.com/Muk223/skeldir-2.0/pull/17
- Code commit: 93b58beb442798c217ba1a03c80bb280ab806a0e
- CI run: pending (not available locally)
