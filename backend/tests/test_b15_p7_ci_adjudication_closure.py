from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from starlette.routing import WebSocketRoute

from app.core.identity import SYSTEM_USER_ID
from app.db.session import get_session
from app.main import app
from app.security.auth import mint_internal_jwt
from app.services.budget_job import BudgetJobService
from app.services.investigation import FixedClock, InvestigationService
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
def _b15_p7_auth_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
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
async def test_b15_p7_canonical_launch_poll_review_terminalization_journey(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    fixed_clock = FixedClock(datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc))
    investigation_service = InvestigationService(clock=fixed_clock, min_hold_seconds=5)
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)
    launch_correlation_id = uuid4()
    mutation_key = uuid4()

    def _fake_enqueue(_task_name: str, _payload) -> None:
        return None

    monkeypatch.setattr("app.api.investigations.enqueue_llm_task", _fake_enqueue)
    monkeypatch.setattr(
        "app.api.investigations._INVESTIGATION_SERVICE",
        investigation_service,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        launch = await client.post(
            "/api/investigations",
            json={"question": "Why did deterministic ROAS decline this week?"},
            headers=_headers(token, correlation_id=launch_correlation_id),
        )
        assert launch.status_code == 202, launch.text
        launch_body = launch.json()
        investigation_id = launch_body["investigation_id"]
        assert launch_body["status"] == "submitted"

        status_t0 = await client.get(
            f"/api/investigations/{investigation_id}/status",
            headers=_headers(token, correlation_id=uuid4()),
        )
        assert status_t0.status_code == 200, status_t0.text
        assert status_t0.json()["status"] == "submitted"
        assert status_t0.json()["review_required"] is False

        fixed_clock.advance(5)
        status_ready = await client.get(
            f"/api/investigations/{investigation_id}/status",
            headers=_headers(token, correlation_id=uuid4()),
        )
        assert status_ready.status_code == 200, status_ready.text
        ready_body = status_ready.json()
        assert ready_body["status"] == "ready_for_review"
        assert ready_body["review_required"] is True
        assert set(ready_body["available_actions"]).issuperset(
            {"approve", "reject", "refine"}
        )

        approve = await client.post(
            f"/api/investigations/{investigation_id}/approve",
            headers=_headers(
                token,
                correlation_id=uuid4(),
                idempotency_key=mutation_key,
            ),
        )
        assert approve.status_code == 200, approve.text
        approve_body = approve.json()
        assert approve_body["status"] == "approved"
        assert approve_body["idempotency_replayed"] is False

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        await investigation_service.complete_job(
            session,
            tenant_id=test_tenant,
            job_id=UUID(investigation_id),
        )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        completed = await client.get(
            f"/api/investigations/{investigation_id}/status",
            headers=_headers(token, correlation_id=uuid4()),
        )
        assert completed.status_code == 200, completed.text
        completed_body = completed.json()
        assert completed_body["status"] == "completed"
        assert completed_body["review_required"] is False

        result = await client.get(
            f"/api/investigations/{investigation_id}",
            headers=_headers(token, correlation_id=uuid4()),
        )
        assert result.status_code == 200, result.text
        result_body = result.json()
        assert result_body["status"] == "completed"
        assert isinstance(result_body["deterministic_findings"], list)
        assert "llm_synthesis" in result_body

    scoped_key = scoped_review_idempotency_key(
        domain="investigation",
        entity_id=UUID(investigation_id),
        action="approve",
        idempotency_key=mutation_key,
    )
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        ledger_row = (
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*) AS count
                        FROM compliance_audit_ledger
                        WHERE tenant_id = :tenant_id
                          AND idempotency_key = :idempotency_key
                        """
                    ),
                    {"tenant_id": str(test_tenant), "idempotency_key": scoped_key},
                )
            )
            .mappings()
            .one()
        )
    assert int(ledger_row["count"]) == 1


@pytest.mark.asyncio
async def test_b15_p7_poll_cadence_controlled_time_stays_within_three_to_seven_seconds(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    fixed_clock = FixedClock(datetime(2026, 3, 1, 13, 0, tzinfo=timezone.utc))
    investigation_service = InvestigationService(clock=fixed_clock, min_hold_seconds=15)
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)

    def _fake_enqueue(_task_name: str, _payload) -> None:
        return None

    monkeypatch.setattr("app.api.investigations.enqueue_llm_task", _fake_enqueue)
    monkeypatch.setattr(
        "app.api.investigations._INVESTIGATION_SERVICE",
        investigation_service,
    )

    poll_times: list[datetime] = []
    poll_statuses: list[str] = []

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        launch = await client.post(
            "/api/investigations",
            json={"question": "How did blended CAC drift over the last 30 days?"},
            headers=_headers(token, correlation_id=uuid4()),
        )
        assert launch.status_code == 202, launch.text
        investigation_id = launch.json()["investigation_id"]

        for index in range(4):
            status = await client.get(
                f"/api/investigations/{investigation_id}/status",
                headers=_headers(token, correlation_id=uuid4()),
            )
            assert status.status_code == 200, status.text
            poll_statuses.append(status.json()["status"])
            poll_times.append(fixed_clock.now())
            if index < 3:
                fixed_clock.advance(5)

    deltas = [
        int((current - previous).total_seconds())
        for previous, current in zip(poll_times, poll_times[1:])
    ]
    assert deltas
    assert all(3 <= delta <= 7 for delta in deltas)
    assert poll_statuses[0] in {"submitted", "validating", "investigating"}
    assert poll_statuses[-1] == "ready_for_review"


@pytest.mark.asyncio
async def test_b15_p7_failure_timeout_cancel_and_retry_are_distinct_and_recoverable(
    test_tenant: UUID,
) -> None:
    service = InvestigationService(min_hold_seconds=0)
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)
    correlation_id = uuid4()

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        failed_job = await service.get_or_create_job(
            session,
            tenant_id=test_tenant,
            request_id=f"b15-p7-failed-{uuid4().hex[:8]}",
            correlation_id=str(correlation_id),
        )
        await service.fail_job(
            session,
            tenant_id=test_tenant,
            job_id=failed_job.id,
            failure_code="provider_failed",
            failure_reason="provider_failure_path",
        )

        timeout_job = await service.get_or_create_job(
            session,
            tenant_id=test_tenant,
            request_id=f"b15-p7-timeout-{uuid4().hex[:8]}",
            correlation_id=str(correlation_id),
        )
        await service.timeout_job(
            session,
            tenant_id=test_tenant,
            job_id=timeout_job.id,
            failure_reason="timeout_budget_exhausted",
        )

        cancelled_job = await service.get_or_create_job(
            session,
            tenant_id=test_tenant,
            request_id=f"b15-p7-cancelled-{uuid4().hex[:8]}",
            correlation_id=str(correlation_id),
        )
        cancelled_job_id = cancelled_job.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        failed_status = await client.get(
            f"/api/investigations/{failed_job.id}/status",
            headers=_headers(token, correlation_id=uuid4()),
        )
        timeout_status = await client.get(
            f"/api/investigations/{timeout_job.id}/status",
            headers=_headers(token, correlation_id=uuid4()),
        )
        cancel_mutation = await client.post(
            f"/api/investigations/{cancelled_job_id}/cancel",
            headers=_headers(
                token,
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            ),
            json={"reason": "operator_cancelled"},
        )
        cancelled_status = await client.get(
            f"/api/investigations/{cancelled_job_id}/status",
            headers=_headers(token, correlation_id=uuid4()),
        )

        assert failed_status.status_code == 200, failed_status.text
        assert timeout_status.status_code == 200, timeout_status.text
        assert cancel_mutation.status_code == 200, cancel_mutation.text
        assert cancelled_status.status_code == 200, cancelled_status.text

        failed_body = failed_status.json()
        timeout_body = timeout_status.json()
        cancelled_body = cancelled_status.json()

        assert failed_body["status"] == "failed"
        assert failed_body["failure"]["code"] == "failed"
        assert failed_body["progress_percentage"] == 100

        assert timeout_body["status"] == "timeout"
        assert timeout_body["failure"]["code"] == "timeout"
        assert timeout_body["progress_percentage"] == 100

        assert cancelled_body["status"] == "cancelled"
        assert cancelled_body["failure"]["code"] == "cancelled"
        assert cancelled_body["progress_percentage"] == 100
        assert cancelled_body["available_actions"] == ["retry"]

        retry = await client.post(
            f"/api/investigations/{cancelled_job_id}/retry",
            headers=_headers(
                token,
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            ),
            json={"reason": "retry_after_cancelled"},
        )
        assert retry.status_code == 200, retry.text
        retry_body = retry.json()
        assert retry_body["status"] == "rerun_requested"
        assert retry_body["mutation_accepted"] is True

        retry_status = await client.get(
            f"/api/investigations/{cancelled_job_id}/status",
            headers=_headers(token, correlation_id=uuid4()),
        )
        assert retry_status.status_code == 200, retry_status.text
        retry_status_body = retry_status.json()
        assert retry_status_body["status"] == "rerun_requested"
        assert retry_status_body["progress_percentage"] == 85
        assert retry_status_body["current_step"] == "Rerun requested"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "payload"),
    [
        ("approve", None),
        ("reject", {"reason": "reject_regression_guard"}),
        ("refine", {"reason": "refine_regression_guard"}),
    ],
)
async def test_b15_p7_network_layer_duplicate_review_actions_are_single_effect(
    test_tenant: UUID,
    action: str,
    payload: dict[str, str] | None,
) -> None:
    service = BudgetJobService()
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)
    mutation_key = uuid4()
    correlation_id = uuid4()

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        job = await service.get_or_create_job(
            session,
            tenant_id=test_tenant,
            request_id=f"b15-p7-idempotency-{action}-{uuid4().hex[:8]}",
            correlation_id=str(correlation_id),
        )
        await service.mark_ready_for_review(
            session,
            tenant_id=test_tenant,
            job_id=job.id,
            result_payload={
                "deterministic_recommendation": {
                    "optimization_goal": "maximize_roas",
                    "allocations": [],
                    "evidence": [],
                }
            },
        )
        job_id = job.id

    route = f"/api/budget/recommendations/{job_id}/{action}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            route,
            headers=_headers(
                token,
                correlation_id=correlation_id,
                idempotency_key=mutation_key,
            ),
            json=payload,
        )
        second = await client.post(
            route,
            headers=_headers(
                token,
                correlation_id=correlation_id,
                idempotency_key=mutation_key,
            ),
            json=payload,
        )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["idempotency_replayed"] is False
    assert second.json()["idempotency_replayed"] is True
    assert second.headers["X-Idempotency-Replayed"].lower() == "true"

    scoped_key = scoped_review_idempotency_key(
        domain="budget",
        entity_id=job_id,
        action=action,
        idempotency_key=mutation_key,
    )
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*) AS count
                        FROM compliance_audit_ledger
                        WHERE tenant_id = :tenant_id
                          AND idempotency_key = :idempotency_key
                        """
                    ),
                    {"tenant_id": str(test_tenant), "idempotency_key": scoped_key},
                )
            )
            .mappings()
            .one()
        )
    assert int(row["count"]) == 1


@pytest.mark.asyncio
async def test_b15_p7_runtime_anti_theater_no_streaming_and_no_hidden_auto_accept(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    fixed_clock = FixedClock(datetime(2026, 3, 1, 14, 0, tzinfo=timezone.utc))
    investigation_service = InvestigationService(clock=fixed_clock, min_hold_seconds=5)
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)

    websocket_routes = [route for route in app.router.routes if isinstance(route, WebSocketRoute)]
    assert websocket_routes == []
    path_set = set(app.openapi().get("paths", {}).keys())
    assert all("/stream" not in path and "/chat" not in path for path in path_set)

    def _fake_enqueue(_task_name: str, _payload) -> None:
        return None

    monkeypatch.setattr("app.api.investigations.enqueue_llm_task", _fake_enqueue)
    monkeypatch.setattr(
        "app.api.investigations._INVESTIGATION_SERVICE",
        investigation_service,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        launch = await client.post(
            "/api/investigations",
            json={"question": "Why did deterministic conversion quality shift today?"},
            headers=_headers(token, correlation_id=uuid4()),
        )
        assert launch.status_code == 202, launch.text
        body = launch.json()
        investigation_id = body["investigation_id"]

        # Runtime anti-theater proof: launch is async and does not return instant result data.
        assert "deterministic_findings" not in body
        assert "llm_synthesis" not in body
        assert body["status"] == "submitted"

        premature_result = await client.get(
            f"/api/investigations/{investigation_id}",
            headers=_headers(token, correlation_id=uuid4()),
        )
        assert premature_result.status_code == 409, premature_result.text
        error_body = premature_result.json()
        assert error_body["code"] == "RESULT_NOT_READY"

        fixed_clock.advance(5)
        ready_status = await client.get(
            f"/api/investigations/{investigation_id}/status",
            headers=_headers(token, correlation_id=uuid4()),
        )
        assert ready_status.status_code == 200, ready_status.text
        ready_body = ready_status.json()
        assert ready_body["status"] == "ready_for_review"
        assert ready_body["review_required"] is True
        assert ready_body["status"] not in {"approved", "completed"}
