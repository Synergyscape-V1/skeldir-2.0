# B055 Phase 5 Follow-Up Evidence Pack (EG5-F2 / EG5-E / EG5-G / COC)

## PR / CI Adjudication (Authority Model)
- PR: https://github.com/Muk223/skeldir-2.0/pull/22
- PR head SHA: `adjudicated_sha` from `MANIFEST.json`
- Evidence bundle rule: `b055-evidence-bundle-${ADJUDICATED_SHA}`
- Authority: `MANIFEST.json` in the CI artifact is the source of truth for
  adjudicated binding (do not hardcode CI run IDs in source-controlled docs).

## MANIFEST Binding (bundle `MANIFEST.json`)
- The manifest must satisfy: `adjudicated_sha == pr_head_sha`
- The artifact suffix must match `adjudicated_sha`
- Evidence documents defer to manifest fields for `workflow_run_id` and `run_attempt`

## H1 — Production Config Lock (Falsified & Fixed)
**Finding:** Tests now import production Celery app and assert JSON-only serializer config.

Excerpt (`backend/tests/test_b055_llm_payload_fidelity.py`):
```
from app.celery_app import _ensure_celery_configured, celery_app

def test_llm_payload_json_roundtrip_fidelity():
    _ensure_celery_configured()
    serializer = celery_app.conf["task_serializer"]
    assert serializer == "json"
    assert celery_app.conf["result_serializer"] == "json"
    accept_content = celery_app.conf.get("accept_content", [])
    assert "json" in accept_content
    assert "application/x-python-serialize" not in accept_content
```

Production config (`backend/app/celery_app.py`):
```
celery_app.conf.update(
    broker_url=broker_url,
    result_backend=_build_result_backend(),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    ...
)
```

## H2 — Determinism Origin Trap (Falsified & Fixed)
**Finding:** Fallback ID no longer depends on prompt content.

Excerpt (`backend/app/workers/llm.py`):
```
def _stable_fallback_id(model: LLMTaskPayload, endpoint: str, label: str) -> str:
    payload = {
        "tenant_id": str(model.tenant_id),
        "endpoint": endpoint,
        "correlation_id": model.correlation_id,
        "request_id": model.request_id,
    }
```

Test (`backend/tests/test_b055_llm_worker_stubs.py`):
```
def test_llm_fallback_id_ignores_prompt_variation():
    payload_a = LLMTaskPayload(... prompt={"question": "why deterministic?"})
    payload_b = LLMTaskPayload(... prompt={"question": "why  deterministic?", "whitespace": True})
    fallback_a = _resolve_request_id(payload_a, "app.tasks.llm.route")
    fallback_b = _resolve_request_id(payload_b, "app.tasks.llm.route")
    assert fallback_a == fallback_b
```

## H3 — Flight Recorder Regression (Falsified)
**Finding:** Bundle generator requires Phase 4 baseline + Phase 5 logs; CI fails if missing.

Excerpt (`scripts/ci/b055_evidence_bundle.py`):
```
REQUIRED_FILES = [
    "MANIFEST.json",
    "SCHEMA/schema.sql",
    "SCHEMA/catalog_constraints.json",
    "ALEMBIC/current.txt",
    "ALEMBIC/heads.txt",
    "ALEMBIC/history.txt",
    "LOGS/pytest_b055.log",
    "LOGS/migrations.log",
    "LOGS/hermeticity_scan.log",
    "LOGS/determinism_scan.log",
    "ENV/git_sha.txt",
    "ENV/python_version.txt",
    "ENV/pip_freeze.txt",
    "ENV/ci_context.json",
]
```

## H4 — CoC Drift (Falsified)
**Finding:** Adjudicated SHA is bound via MANIFEST; remediation evidence doc defers to MANIFEST.

Excerpt (`docs/forensics/b055_phase5_remediation_evidence.md`):
```
- The authoritative binding between CI run and merge candidate is the bundle MANIFEST.json.
- Evidence documents must not hardcode SHA/run IDs; they must defer to the manifest.
```

## EG5 Proof Snippets (CI Logs)
From bundle logs:
- `LOGS/hermeticity_scan.log`: `Violations: 0`
- `LOGS/determinism_scan.log`: `Violations: 0`
- `LOGS/pytest_b055.log` includes:
  - `tests/test_b055_llm_payload_fidelity.py::test_llm_payload_json_roundtrip_fidelity PASSED`
  - `tests/test_b055_llm_worker_stubs.py::test_llm_fallback_id_ignores_prompt_variation PASSED`

## Required Bundle Paths Present (from `MANIFEST.json`)
- Phase 4 baseline: `SCHEMA/schema.sql`, `ALEMBIC/current.txt`, `ENV/git_sha.txt`
- Phase 5 logs: `LOGS/hermeticity_scan.log`, `LOGS/determinism_scan.log`, `LOGS/pytest_b055.log`, `LOGS/migrations.log`
