# B055 Month Bucket Remediation Evidence

## PR / CI Adjudication (Authority Model)
- PR: https://github.com/Muk223/skeldir-2.0/pull/23
- PR head SHA: `adjudicated_sha` from bundle `MANIFEST.json`
- CI run: `workflow_run_id` from bundle `MANIFEST.json`
- Evidence bundle rule: `b055-evidence-bundle-${ADJUDICATED_SHA}`
- Authority: the bundle `MANIFEST.json` is the source of truth for adjudicated binding

## MANIFEST Binding (bundle `MANIFEST.json`)
- `adjudicated_sha`: (see manifest)
- `pr_head_sha`: (see manifest)
- `workflow_run_id`: (see manifest)
- `run_attempt`: (see manifest)

## Root Cause (H-MB1 / H-MB2 / H-MB3)
- `_month_start_utc()` previously hardcoded epoch and collapsed monthly buckets.
- Monthly cost aggregation now derives month start from the request’s audit timestamp (`LLMApiCall.created_at`), ensuring retry stability.
- `llm_monthly_costs.month` is a DATE column; month start is stored as `YYYY-MM-01` in UTC.

## Code Evidence (After Fix)
`backend/app/workers/llm.py`:
```
def _month_start_utc(occurred_at: datetime) -> date:
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    else:
        occurred_at = occurred_at.astimezone(timezone.utc)
    return date(occurred_at.year, occurred_at.month, 1)

async def _claim_api_call(...):
    ...
    .returning(LLMApiCall.id, LLMApiCall.created_at)

async def record_monthly_costs(..., occurred_at: datetime) -> None:
    month = _month_start_utc(occurred_at)
```

## Test Evidence
`backend/tests/test_b055_llm_worker_stubs.py`:
```
def test_month_start_utc_mid_month(): ...
def test_month_start_utc_boundary(): ...
def test_month_start_utc_timezone_normalizes_to_utc(): ...
async def test_monthly_costs_use_api_call_timestamp(...): ...
```

Pytest log excerpt (bundle `LOGS/pytest_b055.log`):
```
tests/test_b055_llm_worker_stubs.py::test_month_start_utc_mid_month PASSED
tests/test_b055_llm_worker_stubs.py::test_month_start_utc_boundary PASSED
tests/test_b055_llm_worker_stubs.py::test_month_start_utc_timezone_normalizes_to_utc PASSED
tests/test_b055_llm_worker_stubs.py::test_monthly_costs_use_api_call_timestamp PASSED
tests/test_b055_llm_worker_stubs.py::test_llm_monthly_costs_concurrent_updates_are_atomic PASSED
```

## Phase 5 Lock Preservation
- Hermeticity scan: `LOGS/hermeticity_scan.log` → `Violations: 0`
- Determinism scan: `LOGS/determinism_scan.log` → `Violations: 0`

## Bundle Completeness (Phase 4 + Phase 5)
Required bundle paths present (see manifest `required_files`):
- `SCHEMA/schema.sql`
- `ALEMBIC/current.txt`
- `ENV/git_sha.txt`
- `LOGS/pytest_b055.log`
- `LOGS/migrations.log`
- `LOGS/hermeticity_scan.log`
- `LOGS/determinism_scan.log`
