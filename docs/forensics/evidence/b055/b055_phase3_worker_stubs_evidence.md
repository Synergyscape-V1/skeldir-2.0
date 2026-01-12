# B0.5.5 Phase 3 Evidence Pack — Worker Stub Layer + ORM Audit Writes

## Repo Pin
```text
7e54364a4fc327085de91ad6b013b6ede5446628
b055-phase3-worker-stubs
```

## H1 — Contract/Execution Interface Drift Risk
Verdict: TRUE (canonical payload module is singular; tasks/workers import it)
```text
rg -n "class LLMTaskPayload" backend/app/schemas/llm_payloads.py
15:class LLMTaskPayload(BaseModel):
rg -n "LLMTaskPayload" backend/app/tasks/llm.py backend/app/workers/llm.py
backend/app/tasks/llm.py:14:from app.schemas.llm_payloads import LLMTaskPayload
backend/app/tasks/llm.py:26:def _prepare_context(model: LLMTaskPayload) -> str:
backend/app/tasks/llm.py:47:    model = LLMTaskPayload(
backend/app/tasks/llm.py:65:    model = LLMTaskPayload(
backend/app/tasks/llm.py:83:    model = LLMTaskPayload(
backend/app/tasks/llm.py:101:    model = LLMTaskPayload(
backend/app/workers/llm.py:24:from app.schemas.llm_payloads import LLMTaskPayload
backend/app/workers/llm.py:31:def _resolve_request_id(model: LLMTaskPayload) -> str:
backend/app/workers/llm.py:35:def _resolve_correlation_id(model: LLMTaskPayload) -> str:
backend/app/workers/llm.py:47:    model: LLMTaskPayload,
backend/app/workers/llm.py:92:async def route_request(model: LLMTaskPayload) -> Dict[str, Any]:
backend/app/workers/llm.py:124:async def generate_explanation(model: LLMTaskPayload) -> Dict[str, Any]:
backend/app/workers/llm.py:156:async def run_investigation(model: LLMTaskPayload) -> Dict[str, Any]:
backend/app/workers/llm.py:198:async def optimize_budget(model: LLMTaskPayload) -> Dict[str, Any]:
```

## H2 — RLS Proof (Postgres-backed)
Verdict: PENDING (local Postgres not available; CI required)
```text
Get-Content -Path .github/workflows/ci.yml | Select-String -Pattern "celery-foundation" -Context 0,40

  celery-foundation:
    name: Celery Foundation B0.5.1
    runs-on: ubuntu-latest
    needs: checkout
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: postgres
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      DATABASE_URL: postgresql://app_user:app_user@127.0.0.1:5432/skeldir_validation
      CELERY_BROKER_URL: sqla+postgresql://app_user:app_user@127.0.0.1:5432/skeldir_validation
      CELERY_RESULT_BACKEND: db+postgresql://app_user:app_user@127.0.0.1:5432/skeldir_validation
      CELERY_METRICS_PORT: 9546
      CELERY_METRICS_ADDR: 127.0.0.1
```
```text
rg -n "get_session|set_tenant_guc_sync" backend/app/db/session.py
87:async def get_session(tenant_id: UUID) -> AsyncGenerator[AsyncSession, None]:
144:def set_tenant_guc_sync(
```

## H3 — ORM Drift From DB Schema
Verdict: PARTIAL (models + parity test added; local run blocked by DB)
```text
rg -n "__tablename__" backend/app/models/llm.py
30:    __tablename__ = "llm_api_calls"
70:    __tablename__ = "llm_monthly_costs"
104:    __tablename__ = "investigations"
147:    __tablename__ = "budget_optimization_jobs"
```
```text
rg -n "CREATE TABLE (llm_api_calls|llm_monthly_costs|investigations|budget_optimization_jobs)" alembic/versions/004_llm_subsystem/202512081500_create_llm_tables.py
54:        CREATE TABLE llm_api_calls (
89:        CREATE TABLE llm_monthly_costs (
116:        CREATE TABLE investigations (
202:        CREATE TABLE budget_optimization_jobs (
```

## H4 — Domain Schema Pollution Trap (status='stubbed')
Verdict: TRUE (status constrained; stub writes use 'completed')
```text
rg -n "status TEXT NOT NULL CHECK" alembic/versions/004_llm_subsystem/202512081500_create_llm_tables.py
122:            status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
207:            status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
```
```text
rg -n "status=" backend/app/workers/llm.py
170:            status="completed",
211:            status="completed",
```

## Worker Module Presence
```text
Test-Path backend/app/workers/llm.py
True
Get-ChildItem -Path backend/app/workers -Force | Select-Object -ExpandProperty Name
__pycache__
llm.py
__init__.py
```

## No Provider Leak
```text
rg -n "anthropic|openai|httpx|requests|ollama|vertex|bedrock" backend/app/workers backend/app/tasks
```

## CI Enforcement (Phase 3 Tests Wired)
```text
rg -n "test_b055_llm_worker_stubs|test_b055_llm_model_parity" .github/workflows/ci.yml
492:              tests/test_b055_llm_worker_stubs.py \
493:              tests/test_b055_llm_model_parity.py -q
```

## Test Output (Local)
```text
$env:DATABASE_URL="postgresql://app_user:app_user@127.0.0.1:5432/skeldir_validation"; cd backend; pytest tests/test_b055_llm_worker_stubs.py tests/test_b055_llm_model_parity.py -q


tests\test_b055_llm_worker_stubs.py::test_llm_route_stub_writes_audit_rows ERROR [ 16%]
tests\test_b055_llm_worker_stubs.py::test_llm_investigation_stub_writes_job ERROR [ 33%]
tests\test_b055_llm_worker_stubs.py::test_llm_budget_stub_writes_job ERROR [ 50%]
tests\test_b055_llm_worker_stubs.py::test_llm_stub_rls_blocks_cross_tenant_reads ERROR [ 66%]
tests\test_b055_llm_worker_stubs.py::test_llm_explanation_stub_writes_api_call ERROR [ 83%]
tests\test_b055_llm_model_parity.py::test_llm_models_reflection_parity FAILED [100%]

=================================== ERRORS ====================================
___________ ERROR at setup of test_llm_route_stub_writes_audit_rows ___________

self = <Coroutine test_llm_route_stub_writes_audit_rows>

    def setup(self) -> None:
        runner_fixture_id = f"_{self._loop_scope}_scoped_runner"
        if runner_fixture_id not in self.fixturenames:
            self.fixturenames.append(runner_fixture_id)
>       return super().setup()
               ^^^^^^^^^^^^^^^

C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:458: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:743: in pytest_fixture_setup
    hook_result = yield
                  ^^^^^
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:313: in _asyncgen_fixture_wrapper
    result = runner.run(setup(), context=context)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\base_events.py:654: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:309: in setup
    res = await gen_obj.__anext__()
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests\conftest.py:109: in test_tenant
    async with engine.begin() as conn:
C:\Python311\Lib\contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\engine.py:1068: in begin
    async with conn:
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:3277: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:3301: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:447: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:1264: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:711: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:388: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:673: in __init__
    self.__connect()
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:899: in __connect
    with util.safe_reraise():
C:\Python311\Lib\site-packages\sqlalchemy\util\langhelpers.py:224: in __exit__
    raise exc_value.with_traceback(exc_tb)
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:895: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\create.py:661: in connect
    return dialect.connect(*cargs, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\default.py:629: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\dialects\postgresql\asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connection.py:2443: in connect
    return await connect_utils._connect(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1249: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1218: in _connect
    conn = await _connect_addr(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1054: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1099: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:969: in _create_ssl_connection
    tr, pr = await loop.create_connection(
C:\Python311\Lib\asyncio\base_events.py:1086: in create_connection
    raise exceptions[0]
C:\Python311\Lib\asyncio\base_events.py:1070: in create_connection
    sock = await self._connect_sock(
C:\Python311\Lib\asyncio\base_events.py:974: in _connect_sock
    await self.sock_connect(sock, address)
C:\Python311\Lib\asyncio\proactor_events.py:726: in sock_connect
    return await self._proactor.connect(sock, address)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\windows_events.py:854: in _poll
    value = callback(transferred, key, ov)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

trans = 0, key = 0, ov = <_overlapped.Overlapped object at 0x00000286F166C4B0>

    def finish_connect(trans, key, ov):
>       ov.getresult()
E       ConnectionRefusedError: [WinError 1225] The remote computer refused the network connection

C:\Python311\Lib\asyncio\windows_events.py:641: ConnectionRefusedError
__________ ERROR at setup of test_llm_investigation_stub_writes_job ___________

self = <Coroutine test_llm_investigation_stub_writes_job>

    def setup(self) -> None:
        runner_fixture_id = f"_{self._loop_scope}_scoped_runner"
        if runner_fixture_id not in self.fixturenames:
            self.fixturenames.append(runner_fixture_id)
>       return super().setup()
               ^^^^^^^^^^^^^^^

C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:458: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:743: in pytest_fixture_setup
    hook_result = yield
                  ^^^^^
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:313: in _asyncgen_fixture_wrapper
    result = runner.run(setup(), context=context)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\base_events.py:654: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:309: in setup
    res = await gen_obj.__anext__()
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests\conftest.py:109: in test_tenant
    async with engine.begin() as conn:
C:\Python311\Lib\contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\engine.py:1068: in begin
    async with conn:
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:3277: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:3301: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:447: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:1264: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:711: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:388: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:673: in __init__
    self.__connect()
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:899: in __connect
    with util.safe_reraise():
C:\Python311\Lib\site-packages\sqlalchemy\util\langhelpers.py:224: in __exit__
    raise exc_value.with_traceback(exc_tb)
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:895: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\create.py:661: in connect
    return dialect.connect(*cargs, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\default.py:629: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\dialects\postgresql\asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connection.py:2443: in connect
    return await connect_utils._connect(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1249: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1218: in _connect
    conn = await _connect_addr(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1054: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1099: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:969: in _create_ssl_connection
    tr, pr = await loop.create_connection(
C:\Python311\Lib\asyncio\base_events.py:1086: in create_connection
    raise exceptions[0]
C:\Python311\Lib\asyncio\base_events.py:1070: in create_connection
    sock = await self._connect_sock(
C:\Python311\Lib\asyncio\base_events.py:974: in _connect_sock
    await self.sock_connect(sock, address)
C:\Python311\Lib\asyncio\proactor_events.py:726: in sock_connect
    return await self._proactor.connect(sock, address)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\windows_events.py:854: in _poll
    value = callback(transferred, key, ov)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

trans = 0, key = 0, ov = <_overlapped.Overlapped object at 0x00000286F153C330>

    def finish_connect(trans, key, ov):
>       ov.getresult()
E       ConnectionRefusedError: [WinError 1225] The remote computer refused the network connection

C:\Python311\Lib\asyncio\windows_events.py:641: ConnectionRefusedError
______________ ERROR at setup of test_llm_budget_stub_writes_job ______________

self = <Coroutine test_llm_budget_stub_writes_job>

    def setup(self) -> None:
        runner_fixture_id = f"_{self._loop_scope}_scoped_runner"
        if runner_fixture_id not in self.fixturenames:
            self.fixturenames.append(runner_fixture_id)
>       return super().setup()
               ^^^^^^^^^^^^^^^

C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:458: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:743: in pytest_fixture_setup
    hook_result = yield
                  ^^^^^
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:313: in _asyncgen_fixture_wrapper
    result = runner.run(setup(), context=context)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\base_events.py:654: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:309: in setup
    res = await gen_obj.__anext__()
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests\conftest.py:109: in test_tenant
    async with engine.begin() as conn:
C:\Python311\Lib\contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\engine.py:1068: in begin
    async with conn:
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:3277: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:3301: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:447: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:1264: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:711: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:388: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:673: in __init__
    self.__connect()
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:899: in __connect
    with util.safe_reraise():
C:\Python311\Lib\site-packages\sqlalchemy\util\langhelpers.py:224: in __exit__
    raise exc_value.with_traceback(exc_tb)
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:895: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\create.py:661: in connect
    return dialect.connect(*cargs, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\default.py:629: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\dialects\postgresql\asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connection.py:2443: in connect
    return await connect_utils._connect(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1249: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1218: in _connect
    conn = await _connect_addr(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1054: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1099: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:969: in _create_ssl_connection
    tr, pr = await loop.create_connection(
C:\Python311\Lib\asyncio\base_events.py:1086: in create_connection
    raise exceptions[0]
C:\Python311\Lib\asyncio\base_events.py:1070: in create_connection
    sock = await self._connect_sock(
C:\Python311\Lib\asyncio\base_events.py:974: in _connect_sock
    await self.sock_connect(sock, address)
C:\Python311\Lib\asyncio\proactor_events.py:726: in sock_connect
    return await self._proactor.connect(sock, address)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\windows_events.py:854: in _poll
    value = callback(transferred, key, ov)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

trans = 0, key = 0, ov = <_overlapped.Overlapped object at 0x00000286F166C9F0>

    def finish_connect(trans, key, ov):
>       ov.getresult()
E       ConnectionRefusedError: [WinError 1225] The remote computer refused the network connection

C:\Python311\Lib\asyncio\windows_events.py:641: ConnectionRefusedError
________ ERROR at setup of test_llm_stub_rls_blocks_cross_tenant_reads ________

self = <Coroutine test_llm_stub_rls_blocks_cross_tenant_reads>

    def setup(self) -> None:
        runner_fixture_id = f"_{self._loop_scope}_scoped_runner"
        if runner_fixture_id not in self.fixturenames:
            self.fixturenames.append(runner_fixture_id)
>       return super().setup()
               ^^^^^^^^^^^^^^^

C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:458: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:743: in pytest_fixture_setup
    hook_result = yield
                  ^^^^^
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:313: in _asyncgen_fixture_wrapper
    result = runner.run(setup(), context=context)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\base_events.py:654: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:309: in setup
    res = await gen_obj.__anext__()
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests\conftest.py:152: in test_tenant_pair
    async with engine.begin() as conn:
C:\Python311\Lib\contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\engine.py:1068: in begin
    async with conn:
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:3277: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:3301: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:447: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:1264: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:711: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:388: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:673: in __init__
    self.__connect()
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:899: in __connect
    with util.safe_reraise():
C:\Python311\Lib\site-packages\sqlalchemy\util\langhelpers.py:224: in __exit__
    raise exc_value.with_traceback(exc_tb)
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:895: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\create.py:661: in connect
    return dialect.connect(*cargs, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\default.py:629: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\dialects\postgresql\asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connection.py:2443: in connect
    return await connect_utils._connect(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1249: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1218: in _connect
    conn = await _connect_addr(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1054: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1099: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:969: in _create_ssl_connection
    tr, pr = await loop.create_connection(
C:\Python311\Lib\asyncio\base_events.py:1086: in create_connection
    raise exceptions[0]
C:\Python311\Lib\asyncio\base_events.py:1070: in create_connection
    sock = await self._connect_sock(
C:\Python311\Lib\asyncio\base_events.py:974: in _connect_sock
    await self.sock_connect(sock, address)
C:\Python311\Lib\asyncio\proactor_events.py:726: in sock_connect
    return await self._proactor.connect(sock, address)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\windows_events.py:854: in _poll
    value = callback(transferred, key, ov)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

trans = 0, key = 0, ov = <_overlapped.Overlapped object at 0x00000286F13E31B0>

    def finish_connect(trans, key, ov):
>       ov.getresult()
E       ConnectionRefusedError: [WinError 1225] The remote computer refused the network connection

C:\Python311\Lib\asyncio\windows_events.py:641: ConnectionRefusedError
_________ ERROR at setup of test_llm_explanation_stub_writes_api_call _________

self = <Coroutine test_llm_explanation_stub_writes_api_call>

    def setup(self) -> None:
        runner_fixture_id = f"_{self._loop_scope}_scoped_runner"
        if runner_fixture_id not in self.fixturenames:
            self.fixturenames.append(runner_fixture_id)
>       return super().setup()
               ^^^^^^^^^^^^^^^

C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:458: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:743: in pytest_fixture_setup
    hook_result = yield
                  ^^^^^
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:313: in _asyncgen_fixture_wrapper
    result = runner.run(setup(), context=context)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\base_events.py:654: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\pytest_asyncio\plugin.py:309: in setup
    res = await gen_obj.__anext__()
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests\conftest.py:109: in test_tenant
    async with engine.begin() as conn:
C:\Python311\Lib\contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\engine.py:1068: in begin
    async with conn:
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:3277: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:3301: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:447: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:1264: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:711: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:388: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:673: in __init__
    self.__connect()
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:899: in __connect
    with util.safe_reraise():
C:\Python311\Lib\site-packages\sqlalchemy\util\langhelpers.py:224: in __exit__
    raise exc_value.with_traceback(exc_tb)
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:895: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\create.py:661: in connect
    return dialect.connect(*cargs, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\default.py:629: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\dialects\postgresql\asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connection.py:2443: in connect
    return await connect_utils._connect(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1249: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1218: in _connect
    conn = await _connect_addr(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1054: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1099: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:969: in _create_ssl_connection
    tr, pr = await loop.create_connection(
C:\Python311\Lib\asyncio\base_events.py:1086: in create_connection
    raise exceptions[0]
C:\Python311\Lib\asyncio\base_events.py:1070: in create_connection
    sock = await self._connect_sock(
C:\Python311\Lib\asyncio\base_events.py:974: in _connect_sock
    await self.sock_connect(sock, address)
C:\Python311\Lib\asyncio\proactor_events.py:726: in sock_connect
    return await self._proactor.connect(sock, address)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\windows_events.py:854: in _poll
    value = callback(transferred, key, ov)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

trans = 0, key = 0, ov = <_overlapped.Overlapped object at 0x00000286F166C630>

    def finish_connect(trans, key, ov):
>       ov.getresult()
E       ConnectionRefusedError: [WinError 1225] The remote computer refused the network connection

C:\Python311\Lib\asyncio\windows_events.py:641: ConnectionRefusedError
================================== FAILURES ===================================
______________________ test_llm_models_reflection_parity ______________________

    @pytest.mark.asyncio
    async def test_llm_models_reflection_parity():
        table_map = {
            "llm_api_calls": LLMApiCall,
            "llm_monthly_costs": LLMMonthlyCost,
            "investigations": Investigation,
            "budget_optimization_jobs": BudgetOptimizationJob,
        }
    
>       async with engine.connect() as conn:

tests\test_b055_llm_model_parity.py:40: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\ext\asyncio\engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:3277: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\base.py:3301: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:447: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:1264: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:711: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:388: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:673: in __init__
    self.__connect()
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:899: in __connect
    with util.safe_reraise():
C:\Python311\Lib\site-packages\sqlalchemy\util\langhelpers.py:224: in __exit__
    raise exc_value.with_traceback(exc_tb)
C:\Python311\Lib\site-packages\sqlalchemy\pool\base.py:895: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\create.py:661: in connect
    return dialect.connect(*cargs, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\engine\default.py:629: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\dialects\postgresql\asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\sqlalchemy\util\_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connection.py:2443: in connect
    return await connect_utils._connect(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1249: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1218: in _connect
    conn = await _connect_addr(
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1054: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:1099: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
C:\Python311\Lib\site-packages\asyncpg\connect_utils.py:969: in _create_ssl_connection
    tr, pr = await loop.create_connection(
C:\Python311\Lib\asyncio\base_events.py:1086: in create_connection
    raise exceptions[0]
C:\Python311\Lib\asyncio\base_events.py:1070: in create_connection
    sock = await self._connect_sock(
C:\Python311\Lib\asyncio\base_events.py:974: in _connect_sock
    await self.sock_connect(sock, address)
C:\Python311\Lib\asyncio\proactor_events.py:726: in sock_connect
    return await self._proactor.connect(sock, address)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Python311\Lib\asyncio\windows_events.py:854: in _poll
    value = callback(transferred, key, ov)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

trans = 0, key = 0, ov = <_overlapped.Overlapped object at 0x00000286F166C9F0>

    def finish_connect(trans, key, ov):
>       ov.getresult()
E       ConnectionRefusedError: [WinError 1225] The remote computer refused the network connection

C:\Python311\Lib\asyncio\windows_events.py:641: ConnectionRefusedError
============================== warnings summary ===============================
<string>:1: 129 warnings
  <string>:1: PydanticDeprecatedSince20: Using extra keyword arguments on `Field` is deprecated and will be removed. Use `json_schema_extra` instead. (Extra keys: 'example'). Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED tests\test_b055_llm_model_parity.py::test_llm_models_reflection_parity
ERROR tests\test_b055_llm_worker_stubs.py::test_llm_route_stub_writes_audit_rows
ERROR tests\test_b055_llm_worker_stubs.py::test_llm_investigation_stub_writes_job
ERROR tests\test_b055_llm_worker_stubs.py::test_llm_budget_stub_writes_job - ...
ERROR tests\test_b055_llm_worker_stubs.py::test_llm_stub_rls_blocks_cross_tenant_reads
ERROR tests\test_b055_llm_worker_stubs.py::test_llm_explanation_stub_writes_api_call
================= 1 failed, 129 warnings, 5 errors in 14.76s ==================
```

## Diff Summary
```text
git diff --name-status origin/main...HEAD
M	.github/workflows/ci.yml
M	backend/.gitignore
M	backend/app/models/__init__.py
A	backend/app/models/llm.py
A	backend/app/schemas/llm_payloads.py
M	backend/app/tasks/llm.py
A	backend/app/workers/__init__.py
A	backend/app/workers/llm.py
A	backend/tests/test_b055_llm_model_parity.py
A	backend/tests/test_b055_llm_worker_stubs.py
M	docs/forensics/INDEX.md
A	docs/forensics/evidence/b055/b055_phase3_worker_stubs_evidence.md
```

## Chain of Custody
```text
git log --oneline --decorate -n 10
7e54364 (HEAD -> b055-phase3-worker-stubs, origin/b055-phase3-worker-stubs) B055 Phase3: add evidence pack
f03b8bc B055 Phase3: add LLM worker stubs, ORM models, and tests
7e313c8 (origin/main, origin/HEAD, main) Merge pull request #16 from Muk223/b055-phase2-queue-constantization
aface84 (origin/b055-phase2-queue-constantization, b055-phase2-queue-constantization) B055 Phase2: record CI run + PR link
9490dca CI: guard missing LLM payload contract test
2a827c5 CI: set DATABASE_URL for test-backend
567dcf8 B055 Phase2: refresh evidence pack metadata
8343f58 B055 Phase2: add queue constantization evidence
d464730 B055 Phase2: introduce QUEUE_LLM constant + routing proof
0066937 Merge pull request #15 from Muk223/docs-evidence-hygiene
756e141 (origin/docs-evidence-hygiene, docs-evidence-hygiene-fix) CI: bump upload-artifact to v4
git remote -v
origin	https://github.com/Muk223/skeldir-2.0.git (fetch)
origin	https://github.com/Muk223/skeldir-2.0.git (push)
```

## PR Metadata
```text
PR: https://github.com/Muk223/skeldir-2.0/pull/17
Branch: b055-phase3-worker-stubs
Commit (HEAD): 7e54364a4fc327085de91ad6b013b6ede5446628
Commit (code): f03b8bc2a881fe8d102e40e190793ca7c9b10af2
CI: pending (not visible locally)
```
