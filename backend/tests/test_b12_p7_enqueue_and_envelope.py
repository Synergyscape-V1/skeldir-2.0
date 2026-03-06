from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.celery_app import celery_app
# Force task registration for direct task lookups in this module.
from app.tasks import attribution as _tasks_attribution  # noqa: F401
from app.tasks import health as _tasks_health  # noqa: F401
from app.tasks import housekeeping as _tasks_housekeeping  # noqa: F401
from app.tasks import llm as _tasks_llm  # noqa: F401
from app.tasks import maintenance as _tasks_maintenance  # noqa: F401
from app.tasks import matviews as _tasks_matviews  # noqa: F401
from app.tasks.authority import SessionAuthorityEnvelope, SystemAuthorityEnvelope
from app.tasks.enqueue import TENANT_SCOPED_TASK_NAMES, enqueue_tenant_task, tenant_task_signature
from app.tasks.tenant_base import TenantTask


def test_tenant_scoped_tasks_are_registered_with_tenant_base() -> None:
    for task_name in sorted(TENANT_SCOPED_TASK_NAMES):
        task = celery_app.tasks.get(task_name)
        assert task is not None, f"missing registered task: {task_name}"
        assert isinstance(task, TenantTask), f"task must use TenantTask base: {task_name}"


def test_enqueue_chokepoint_rejects_non_tenant_task() -> None:
    with pytest.raises(ValueError, match="not registered as tenant-scoped"):
        enqueue_tenant_task(
            celery_app.tasks["app.tasks.health.probe"],
            envelope=SystemAuthorityEnvelope(tenant_id=uuid4()),
            kwargs={},
        )


def test_enqueue_chokepoint_validates_session_envelope_fields() -> None:
    with pytest.raises(Exception):
        enqueue_tenant_task(
            celery_app.tasks["app.tasks.attribution.recompute_window"],
            envelope={
                "context_type": "session",
                "tenant_id": str(uuid4()),
                "user_id": str(uuid4()),
                "jti": str(uuid4()),
                # iat intentionally missing
            },
            kwargs={"window_start": "2026-01-01T00:00:00Z", "window_end": "2026-01-02T00:00:00Z"},
        )


def test_tenant_signature_builder_injects_authority_envelope() -> None:
    sig = tenant_task_signature(
        celery_app.tasks["app.tasks.attribution.recompute_window"],
        envelope=SystemAuthorityEnvelope(tenant_id=uuid4()),
        kwargs={"window_start": "2026-01-01T00:00:00Z", "window_end": "2026-01-02T00:00:00Z"},
    )
    assert "authority_envelope" in sig.kwargs
    assert sig.kwargs["authority_envelope"]["context_type"] == "system"


def test_tenant_task_default_deny_requires_envelope_when_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("SKELDIR_B12_P7_STRICT_ENVELOPE", "1")
    task = celery_app.tasks["app.tasks.attribution.recompute_window"]

    result = task.apply(
        kwargs={
            "tenant_id": str(uuid4()),
            "window_start": "2026-01-01T00:00:00Z",
            "window_end": "2026-01-02T00:00:00Z",
        }
    )
    with pytest.raises(ValueError, match="authority_envelope is required"):
        result.get(propagate=True)


def test_no_direct_delay_or_apply_async_for_tenant_tasks_in_app_code() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_root = repo_root / "backend" / "app"
    deny_symbols = {
        "recompute_window",
        "llm_routing_worker",
        "llm_explanation_worker",
        "llm_investigation_worker",
        "llm_budget_optimization_worker",
        "refresh_matview_for_tenant",
        "scan_for_pii_contamination_task",
        "enforce_data_retention_task",
        "matview_refresh_single",
        "matview_refresh_all_for_tenant",
    }
    violations: list[str] = []
    for path in app_root.rglob("*.py"):
        if path.name == "enqueue.py":
            continue
        text = path.read_text(encoding="utf-8")
        for symbol in deny_symbols:
            if f"{symbol}.delay(" in text or f"{symbol}.apply_async(" in text:
                violations.append(str(path.relative_to(repo_root)))
                break
    assert not violations, f"tenant-task enqueue bypass found: {violations}"
