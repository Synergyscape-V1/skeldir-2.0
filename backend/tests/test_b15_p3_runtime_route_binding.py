from __future__ import annotations

from typing import Callable
from uuid import UUID, uuid4

import pytest
import jwt
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text

from app.core.identity import SYSTEM_USER_ID
from app.db.session import engine, get_session
from app.main import app
from app.security.auth import mint_internal_jwt
from app.services.budget_job import BudgetJobService
from app.services.investigation import InvestigationService
from app.services.review_mutation_ledger import scoped_review_idempotency_key


def _token_for(tenant_id: UUID, user_id: UUID) -> str:
    return mint_internal_jwt(
        tenant_id=tenant_id,
        user_id=user_id,
        expires_in_seconds=3600,
        additional_claims={"role": "viewer", "roles": ["viewer"], "scopes": ["viewer"]},
    )


def _headers(
    token: str,
    *,
    correlation_id: UUID,
    idempotency_key: UUID | None = None,
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": str(correlation_id),
    }
    if idempotency_key is not None:
        headers["X-Idempotency-Key"] = str(idempotency_key)
    return headers


@pytest.fixture(autouse=True)
def _b15_p3_auth_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRACT_TESTING", "0")

    async def _no_revocation(_token_claims):
        return None

    def _decode_without_verification(token: str):
        return jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )

    monkeypatch.setattr("app.security.auth._decode_token", _decode_without_verification)
    monkeypatch.setattr("app.security.auth.assert_access_token_active", _no_revocation)


@pytest.mark.asyncio
async def test_b15_p3_routes_are_mounted_and_visible_in_runtime_openapi() -> None:
    paths = set(app.openapi().get("paths", {}).keys())
    required_paths = {
        "/api/investigations",
        "/api/investigations/{investigation_id}/status",
        "/api/investigations/{investigation_id}",
        "/api/investigations/{investigation_id}/approve",
        "/api/investigations/{investigation_id}/reject",
        "/api/investigations/{investigation_id}/refine",
        "/api/investigations/{investigation_id}/rerun",
        "/api/investigations/{investigation_id}/retry",
        "/api/investigations/{investigation_id}/cancel",
        "/api/budget/optimize",
        "/api/budget/recommendations/{job_id}/status",
        "/api/budget/recommendations/{job_id}",
        "/api/budget/recommendations/{job_id}/approve",
        "/api/budget/recommendations/{job_id}/reject",
        "/api/budget/recommendations/{job_id}/refine",
        "/api/budget/recommendations/{job_id}/rerun",
        "/api/budget/recommendations/{job_id}/retry",
        "/api/budget/recommendations/{job_id}/cancel",
    }
    assert required_paths.issubset(paths)


@pytest.mark.asyncio
async def test_b15_p3_launch_routes_bind_to_authority_services(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)
    corr_inv = uuid4()
    corr_budget = uuid4()
    enqueued: list[tuple[str, str, str]] = []

    class _FakeTaskResult:
        id = uuid4()

    def _fake_enqueue(task_name: str, payload):
        enqueued.append((task_name, str(payload.tenant_id), str(payload.request_id)))
        return _FakeTaskResult()

    monkeypatch.setattr("app.api.investigations.enqueue_llm_task", _fake_enqueue)
    monkeypatch.setattr("app.api.budget.enqueue_llm_task", _fake_enqueue)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        inv_resp = await client.post(
            "/api/investigations",
            json={"question": "Why did channel spend efficiency drop this week?"},
            headers=_headers(token, correlation_id=corr_inv),
        )
        budget_resp = await client.post(
            "/api/budget/optimize",
            json={"total_budget": 50000, "optimization_goal": "maximize_roas"},
            headers=_headers(token, correlation_id=corr_budget),
        )

    assert inv_resp.status_code == 202, inv_resp.text
    assert budget_resp.status_code == 202, budget_resp.text
    inv_body = inv_resp.json()
    budget_body = budget_resp.json()
    assert inv_body["status"] == "submitted"
    assert budget_body["status"] == "submitted"
    assert any(item[0] == "investigation" for item in enqueued)
    assert any(item[0] == "budget_optimization" for item in enqueued)

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        inv_row = (
            (
                await session.execute(
                    text(
                        """
                        SELECT status, request_id
                        FROM investigation_jobs
                        WHERE tenant_id = :tenant_id
                          AND id = :job_id
                        """
                    ),
                    {"tenant_id": str(test_tenant), "job_id": inv_body["investigation_id"]},
                )
            )
            .mappings()
            .first()
        )
        budget_row = (
            (
                await session.execute(
                    text(
                        """
                        SELECT status, request_id
                        FROM budget_jobs
                        WHERE tenant_id = :tenant_id
                          AND id = :job_id
                        """
                    ),
                    {"tenant_id": str(test_tenant), "job_id": budget_body["job_id"]},
                )
            )
            .mappings()
            .first()
        )
    assert inv_row is not None
    assert budget_row is not None
    assert inv_row["status"] == "submitted"
    assert budget_row["status"] == "submitted"
    assert inv_row["request_id"] == str(corr_inv)
    assert budget_row["request_id"] == str(corr_budget)


@pytest.mark.asyncio
async def test_b15_p3_review_mutation_is_idempotent_and_audited(
    test_tenant: UUID,
) -> None:
    service = InvestigationService(min_hold_seconds=0)
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)
    correlation_id = uuid4()
    mutation_key = uuid4()
    request_id = f"b15-p3-approve-{uuid4().hex[:8]}"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        job = await service.get_or_create_job(
            session,
            tenant_id=test_tenant,
            request_id=request_id,
            correlation_id=str(correlation_id),
        )
        await service.mark_ready_for_review(
            session,
            tenant_id=test_tenant,
            job_id=job.id,
            result_payload={"deterministic_findings": []},
        )
        job_id = job.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            f"/api/investigations/{job_id}/approve",
            headers=_headers(token, correlation_id=correlation_id, idempotency_key=mutation_key),
        )
        second = await client.post(
            f"/api/investigations/{job_id}/approve",
            headers=_headers(token, correlation_id=correlation_id, idempotency_key=mutation_key),
        )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["idempotency_replayed"] is False
    assert second.json()["idempotency_replayed"] is True
    assert second.headers["X-Idempotency-Replayed"].lower() == "true"

    scoped_key = scoped_review_idempotency_key(
        domain="investigation",
        entity_id=job_id,
        action="approve",
        idempotency_key=mutation_key,
    )
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                        SELECT actor, correlation_id, occurred_at, idempotency_key, effects
                        FROM compliance_audit_ledger
                        WHERE tenant_id = :tenant_id
                          AND idempotency_key = :idempotency_key
                        """
                    ),
                    {"tenant_id": str(test_tenant), "idempotency_key": scoped_key},
                )
            )
            .mappings()
            .first()
        )
    assert row is not None
    assert row["idempotency_key"] == scoped_key
    assert str(row["actor"]) == str(user_id)
    assert str(row["correlation_id"]) == str(correlation_id)
    assert row["occurred_at"] is not None
    assert row["effects"]["mutation_intent"] == "approve"


@pytest.mark.asyncio
async def test_b15_p3_illegal_transition_is_rejected(
    test_tenant: UUID,
) -> None:
    service = InvestigationService()
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)
    correlation_id = uuid4()
    request_id = f"b15-p3-illegal-{uuid4().hex[:8]}"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        job = await service.get_or_create_job(
            session,
            tenant_id=test_tenant,
            request_id=request_id,
            correlation_id=str(correlation_id),
        )
        job_id = job.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/investigations/{job_id}/approve",
            headers=_headers(token, correlation_id=correlation_id, idempotency_key=uuid4()),
        )

    assert response.status_code == 409, response.text
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    assert response.json()["code"] == "INVALID_STATE_TRANSITION"


@pytest.mark.asyncio
async def test_b15_p3_boundary_rejects_undeclared_mutation_fields(
    test_tenant: UUID,
) -> None:
    service = BudgetJobService()
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)
    correlation_id = uuid4()
    request_id = f"b15-p3-budget-{uuid4().hex[:8]}"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        job = await service.get_or_create_job(
            session,
            tenant_id=test_tenant,
            request_id=request_id,
            correlation_id=str(correlation_id),
        )
        await service.mark_ready_for_review(
            session,
            tenant_id=test_tenant,
            job_id=job.id,
            result_payload={"deterministic_recommendation": {}},
        )
        job_id = job.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/budget/recommendations/{job_id}/reject",
            json={"reason": "insufficient evidence", "unexpected": "field"},
            headers=_headers(token, correlation_id=correlation_id, idempotency_key=uuid4()),
        )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("terminal_status", "terminalizer"),
    [
        (
            "timeout",
            lambda service, session, tenant_id, job_id: service.timeout_job(
                session,
                tenant_id=tenant_id,
                job_id=job_id,
                failure_reason="provider_timeout",
            ),
        ),
        (
            "failed",
            lambda service, session, tenant_id, job_id: service.fail_job(
                session,
                tenant_id=tenant_id,
                job_id=job_id,
                failure_code="failed",
                failure_reason="provider_failure",
            ),
        ),
        (
            "cancelled",
            lambda service, session, tenant_id, job_id: service.cancel_job(
                session,
                tenant_id=tenant_id,
                job_id=job_id,
                reason="manual_cancel",
            ),
        ),
    ],
)
async def test_b15_p3_status_surfaces_terminal_failure_truth(
    test_tenant: UUID,
    terminal_status: str,
    terminalizer: Callable[..., object],
) -> None:
    service = InvestigationService(min_hold_seconds=0)
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)
    correlation_id = uuid4()
    request_id = f"b15-p3-terminal-{terminal_status}-{uuid4().hex[:8]}"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        job = await service.get_or_create_job(
            session,
            tenant_id=test_tenant,
            request_id=request_id,
            correlation_id=str(correlation_id),
        )
        await terminalizer(service, session, test_tenant, job.id)
        job_id = job.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/investigations/{job_id}/status",
            headers=_headers(token, correlation_id=correlation_id),
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == terminal_status
    assert payload["failure"]["code"] == terminal_status


@pytest.mark.asyncio
async def test_b15_p3_status_route_uses_lightweight_projection_query(
    test_tenant: UUID,
) -> None:
    service = InvestigationService(min_hold_seconds=0)
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)
    correlation_id = uuid4()
    request_id = f"b15-p3-projection-{uuid4().hex[:8]}"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        job = await service.get_or_create_job(
            session,
            tenant_id=test_tenant,
            request_id=request_id,
            correlation_id=str(correlation_id),
        )
        await service.mark_ready_for_review(
            session,
            tenant_id=test_tenant,
            job_id=job.id,
            result_payload={
                "deterministic_findings": [
                    {"payload": "x" * 1024}
                ]
            },
        )
        job_id = job.id

    captured: list[str] = []

    def _capture_sql(_conn, _cursor, statement, _params, _context, _many):
        if "FROM investigation_jobs" in statement and "SELECT" in statement:
            captured.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _capture_sql)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/investigations/{job_id}/status",
                headers=_headers(token, correlation_id=correlation_id),
            )
        assert response.status_code == 200, response.text
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _capture_sql)

    assert captured, "expected status polling query against investigation_jobs"
    assert all("result" not in statement.lower() for statement in captured)


@pytest.mark.asyncio
async def test_b15_p3_idempotency_reuse_with_different_payload_is_conflict(
    test_tenant: UUID,
) -> None:
    service = InvestigationService(min_hold_seconds=0)
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)
    correlation_id = uuid4()
    idempotency_key = uuid4()
    request_id = f"b15-p3-idempo-conflict-{uuid4().hex[:8]}"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        job = await service.get_or_create_job(
            session,
            tenant_id=test_tenant,
            request_id=request_id,
            correlation_id=str(correlation_id),
        )
        await service.mark_ready_for_review(
            session,
            tenant_id=test_tenant,
            job_id=job.id,
            result_payload={"deterministic_findings": []},
        )
        job_id = job.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            f"/api/investigations/{job_id}/reject",
            json={"reason": "first"},
            headers=_headers(token, correlation_id=correlation_id, idempotency_key=idempotency_key),
        )
        second = await client.post(
            f"/api/investigations/{job_id}/reject",
            json={"reason": "second"},
            headers=_headers(token, correlation_id=correlation_id, idempotency_key=idempotency_key),
        )

    assert first.status_code == 200, first.text
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "IDEMPOTENCY_KEY_CONFLICT"
