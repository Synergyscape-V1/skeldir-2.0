from __future__ import annotations

import inspect
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.celery_app import celery_app
# Force registration for test-only representative tenant task.
from app.tasks import attribution as _tasks_attribution  # noqa: F401
from app.tasks import llm as _tasks_llm  # noqa: F401
from app.tasks import maintenance as _tasks_maintenance  # noqa: F401
from app.tasks import matviews as _tasks_matviews  # noqa: F401
from app.tasks import observability_test as _tasks_observability_test  # noqa: F401
from app.tasks.authority import AUTHORITY_ENVELOPE_HEADER, SessionAuthorityEnvelope
from app.tasks.enqueue import TENANT_SCOPED_TASK_NAMES
from app.tasks.tenant_base import task_tenant_id


def test_tenant_scoped_tasks_use_canonical_tenant_context_helper() -> None:
    missing_helper_calls: list[str] = []
    direct_request_access: list[str] = []
    for task_name in sorted(TENANT_SCOPED_TASK_NAMES):
        task_obj = celery_app.tasks[task_name]
        source = inspect.getsource(task_obj.run)
        if "task_tenant_id(" not in source:
            missing_helper_calls.append(task_name)
        if "self.request.tenant_id" in source:
            direct_request_access.append(task_name)
    assert not missing_helper_calls, f"tenant tasks must resolve tenant context via task_tenant_id helper: {missing_helper_calls}"
    assert not direct_request_access, f"tenant tasks must not read tenant context directly from self.request: {direct_request_access}"


def test_representative_tenant_task_reads_context_without_signature_authority_fields(test_tenant) -> None:
    user_id = uuid4()
    task = celery_app.tasks["app.tasks.observability_test.tenant_context_probe"]
    result = task.apply(
        kwargs={"correlation_id": str(uuid4())},
        headers={
            AUTHORITY_ENVELOPE_HEADER: SessionAuthorityEnvelope(
                tenant_id=test_tenant,
                user_id=user_id,
                jti=uuid4(),
                iat=1760000000,
            ).model_dump(mode="json")
        },
    )
    payload = result.get(propagate=True)
    assert payload["tenant"] == str(test_tenant)
    assert payload["user"] == str(user_id)


def test_task_tenant_id_helper_fails_fast_when_request_context_is_unbound() -> None:
    with pytest.raises(ValueError, match="tenant_id missing from tenant task request context"):
        task_tenant_id(SimpleNamespace(request=SimpleNamespace()))
