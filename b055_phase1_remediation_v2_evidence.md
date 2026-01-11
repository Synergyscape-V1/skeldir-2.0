# B0.5.5 Phase 1 Remediation v2 Evidence

## Repo Pin
```
git rev-parse HEAD
7fff114015faa6721a13a6da2b258b83fa388092

git branch --show-current
b055-phase1-payload-contract

git status --porcelain
 M frontend/src/assets/brand/colors.css
 M frontend/src/components/logos/StripeLogo.tsx
?? .hypothesis/constants/024f09cc582833b5
?? .hypothesis/constants/089f1ba4254e2a69
?? .hypothesis/constants/0b2df83a51968d74
?? .hypothesis/constants/1e65dc7a8f7385af
?? .hypothesis/constants/1fcb8b6770b9d806
?? .hypothesis/constants/2fb346ec6c9156ec
?? .hypothesis/constants/3031cb3b4415bcb5
?? .hypothesis/constants/355c51d5f74295dc
?? .hypothesis/constants/379bd6a47c6472ca
?? .hypothesis/constants/37e4fc8785c69038
?? .hypothesis/constants/3fdabcaff36d1d88
?? .hypothesis/constants/4216c64fca41831c
?? .hypothesis/constants/430e9f7140c1b51f
?? .hypothesis/constants/5211ee55a93855b1
?? .hypothesis/constants/52d25ccce273a455
?? .hypothesis/constants/57360c3e51a75201
?? .hypothesis/constants/576c096a7fe96afb
?? .hypothesis/constants/594bc897941d1754
?? .hypothesis/constants/5be7b8752eee86de
?? .hypothesis/constants/600b2908479b32c1
?? .hypothesis/constants/6584b8a69cbcddd1
?? .hypothesis/constants/6d31e0f6f613c030
?? .hypothesis/constants/7a02ff24182d0ca3
?? .hypothesis/constants/7b7204ecdc6a19b5
?? .hypothesis/constants/7daf89908ac047f0
?? .hypothesis/constants/7f34c187745ef947
?? .hypothesis/constants/80adc0924a1f1149
?? .hypothesis/constants/86d4c05451170723
?? .hypothesis/constants/88eb6299a639677c
?? .hypothesis/constants/8c5e84112301e262
?? .hypothesis/constants/8d15246a298d2027
?? .hypothesis/constants/a06bf2c028ce58d9
?? .hypothesis/constants/a0783a9c4475c8bf
?? .hypothesis/constants/a0cd82dbcc32e0d6
?? .hypothesis/constants/a75a15e19681488a
?? .hypothesis/constants/a7edbdd661851e74
?? .hypothesis/constants/a99687e68e9b91d5
?? .hypothesis/constants/a9fd8f8f83b3e88e
?? .hypothesis/constants/af36914832c67a26
?? .hypothesis/constants/b66dfc8830fb9229
?? .hypothesis/constants/b6aa0736ee30e41b
?? .hypothesis/constants/bb1e3d3218307e72
?? .hypothesis/constants/bb5a18dfc925f6f3
?? .hypothesis/constants/beb5cdc233ca4d51
?? .hypothesis/constants/c04ae0bf584eda3a
?? .hypothesis/constants/c0aae2c99f189c21
?? .hypothesis/constants/c6821cbf9a72f295
?? .hypothesis/constants/d198513989057cac
?? .hypothesis/constants/d2620c792b239974
?? .hypothesis/constants/d2dc32ea29346e08
?? .hypothesis/constants/d2fda89efc0ed351
?? .hypothesis/constants/d3b4c63bc8a96974
?? .hypothesis/constants/d4351ef0a27c08f5
?? .hypothesis/constants/d6423c009e477003
?? .hypothesis/constants/d959df446d8bd4ed
?? .hypothesis/constants/dd95cace318d8677
?? .hypothesis/constants/e1262e2214538193
?? .hypothesis/constants/e356c482ef274c97
?? .hypothesis/constants/e5e350f13869348a
?? .hypothesis/constants/e7eeadd3f37bbae0
?? .hypothesis/constants/ea7cf563b42702b2
?? .hypothesis/constants/eb9a2c460b85b8ed
?? .hypothesis/constants/ed8b56737372d360
?? .hypothesis/constants/ee8d865397123cda
?? .hypothesis/constants/f02ea05e3f89642a
?? .hypothesis/constants/f225359a42656bd7
?? .hypothesis/constants/f42151766ca28ff6
?? .hypothesis/constants/f6d6ee392149b423
?? .hypothesis/constants/faad358200ea766f
?? .hypothesis/constants/fc5e309e12aa5309
?? artifacts/b0545_ci_main_run_20883741633/
?? artifacts/b0545_ci_run_20882762997/
?? artifacts/b0545_ci_run_20882844400/
?? artifacts/b0545_ci_run_20882999191/
?? artifacts/b0545_ci_run_20883117336/
?? artifacts/b0545_ci_run_20883180371/
?? artifacts/b0545_ci_run_20883267894/
?? artifacts/b0545_ci_run_20883349059/
?? b0545-kinetic-evidence-1e35e08bca6be14eb424ca12c77b423503c654d0 (2).zip
?? b055_context_gathering_evidence.md
?? b055_phase1_payload_contract_evidence.md
```
Note: frontend modifications and untracked artifacts pre-existed; no frontend files were edited in this remediation.

## Hypothesis Adjudication (H1-H4)

### H1 — Mixed packaging roots caused fallback import
Evidence (prior state):
```
git show 722bc32a6260f08978e8908f175779b8b824557e:backend/app/tasks/llm.py | Select-String -Pattern "llm_payloads" -Context 1,1

  try:
>     from backend.app.schemas.llm_payloads import LLMTaskPayload
  except ModuleNotFoundError:  # pragma: no cover - runtime may only expose `app` on PYTHONPATH
>     from app.schemas.llm_payloads import LLMTaskPayload
  from app.tasks.context import tenant_task
```
Sys.path roots (cwd differs):
```
python -c "import sys, os; print(os.getcwd()); print(sys.path[:5])"
C:\Users\ayewhy\II SKELDIR II
['', 'C:\\Python311\\python311.zip', 'C:\\Python311\\DLLs', 'C:\\Python311\\Lib', 'C:\\Python311']

python -c "import sys, os; print(os.getcwd()); print(sys.path[:5])"   # run from backend/
C:\Users\ayewhy\II SKELDIR II\backend
['', 'C:\\Python311\\python311.zip', 'C:\\Python311\\DLLs', 'C:\\Python311\\Lib', 'C:\\Python311']
```
Verdict: TRUE. The fallback import was present; it is now removed in the remediation commit.

### H2 — conftest sys.path injection masked config issues
Evidence (prior state):
```
git show 722bc32a6260f08978e8908f175779b8b824557e:backend/tests/conftest.py | Select-String -Pattern "sys.path" -Context 2,2

  os.environ["TESTING"] = "1"
  
> # Ensure backend package path is on sys.path for local runs.
  backend_dir = Path(__file__).resolve().parents[1]
> if str(backend_dir) not in sys.path:
>     sys.path.insert(0, str(backend_dir))
  
  # B0.5.3.3 Gate C: CI-first credential coherence (MUST execute before any imports)
```
Verdict: TRUE. The global sys.path mutation existed and is removed.

### H3 — CI “Test Backend” skipped due to PR condition
Evidence (prior state):
```
git show 722bc32a6260f08978e8908f175779b8b824557e:.github/workflows/ci.yml | Select-String -Pattern "test-backend|Test Backend|if:" -Context 0,2

>   test-backend:
>     name: Test Backend
      runs-on: ubuntu-latest
      needs: checkout
>     if: contains(github.event.head_commit.modified, 'backend/') || contains(github.event.head_commit.added, 'backend/')
```
Verdict: TRUE. The condition relied on head_commit fields not present in PR events.

### H4 — Integration pipeline cleanup deletes schemas
Evidence (prior state):
```
git show 722bc32a6260f08978e8908f175779b8b824557e:scripts/integration_test_pipeline.sh | Select-String -Pattern "schemas" -Context 1,1

  rm -rf api-contracts/dist
> rm -f backend/app/schemas/*.py
```
Verdict: TRUE. Cleanup command would delete canonical schemas.

## Remediation Outputs

### git diff --name-status origin/main...HEAD
```
git diff --name-status origin/main...HEAD
M	.github/workflows/ci.yml
M	.gitignore
M	backend/.gitignore
A	backend/__init__.py
A	backend/app/schemas/llm_payloads.py
M	backend/app/tasks/llm.py
A	backend/tests/snapshots/llm_task_payload.schema.json
M	backend/tests/test_channel_audit_e2e.py
A	backend/tests/test_llm_payload_contract.py
M	pytest.ini
M	scripts/integration_test_pipeline.sh
```

### EG1-C2 — Deterministic Import Gate
```
rg -n "try:|except ModuleNotFoundError|backend\.app\.schemas\.llm_payloads" backend/app/tasks/llm.py
# no matches
```
Current import is single-root:
```
rg -n "LLMTaskPayload" backend/app/tasks/llm.py
14:from app.schemas.llm_payloads import LLMTaskPayload
20:def _prepare_context(model: LLMTaskPayload) -> str:
36:    model = LLMTaskPayload(...)
48:    model = LLMTaskPayload(...)
60:    model = LLMTaskPayload(...)
72:    model = LLMTaskPayload(...)
```

### EG1-H2 — Harness Safety Gate
```
rg -n "sys\.path\.insert|sys\.path\.append" backend/tests/conftest.py
# no matches
```
Declarative config (root `pytest.ini`):
```
[pytest]
...
pythonpath = backend
```

### EG1-PATH — Packaging Consistency Gate
```
rg -n "backend\.app" backend/app backend/tests
# no matches
```

### EG1-PIPE — Integration Pipeline Survival Gate
```
rg -n "backend/app/schemas/.*\.py|schemas/\*\.py|rm .*schemas|generated_.*\.py" scripts/integration_test_pipeline.sh
11:find backend/app/schemas -maxdepth 1 -type f -name "generated_*.py" -delete
```

### EG1-CI — CI Enforcement Gate (workflow change)
```
# .github/workflows/ci.yml (Test Backend job)
if: github.event_name == 'pull_request' || (github.event_name == 'push' && (contains(github.event.head_commit.modified, 'backend/') || contains(github.event.head_commit.added, 'backend/')))
...
pytest tests/test_llm_payload_contract.py -q
```

### EG1-SNAP — Snapshot/Validation Gate (local)
```
$env:DATABASE_URL="postgresql://app_user:app_user@127.0.0.1:5432/skeldir_validation"; $env:CELERY_BROKER_URL="sqla+postgresql://app_user:app_user@127.0.0.1:5432/skeldir_validation"; $env:CELERY_RESULT_BACKEND="db+postgresql://app_user:app_user@127.0.0.1:5432/skeldir_validation"; pytest -q backend/tests/test_llm_payload_contract.py

backend/tests/test_llm_payload_contract.py::test_llm_payload_schema_matches_snapshot PASSED [ 33%]
backend/tests/test_llm_payload_contract.py::test_llm_payload_invalid_rejected[payload0] PASSED [ 66%]
backend/tests/test_llm_payload_contract.py::test_llm_payload_invalid_rejected[payload1] PASSED [100%]

============================== warnings summary ===============================
<string>:1: 129 warnings
  <string>:1: PydanticDeprecatedSince20: Using extra keyword arguments on `Field` is deprecated and will be removed. Use `json_schema_extra` instead. (Extra keys: 'example'). Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 3 passed, 129 warnings in 0.27s =======================
```

## CI Run Reference
- Pending: PR checks must be re-queried after push to confirm Test Backend executed (not skipped). This will be updated once CI completes.
