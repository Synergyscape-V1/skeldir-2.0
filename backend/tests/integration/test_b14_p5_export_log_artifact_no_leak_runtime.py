"""B1.4-P5 DB-backed runtime proofs for export/log/artifact no-leak closure."""

from __future__ import annotations

import io
import json
import logging
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.export import EXPORT_ROW_ALLOWLIST
from app.celery_app import celery_app
from app.core.db import engine
from app.db.session import get_session
from app.ingestion.dlq_handler import DLQHandler, route_unresolved_tenant_to_quarantine
from app.ingestion.event_service import ingest_with_transaction
from app.main import app
from app.observability.logging_config import JsonFormatter, RedactionFilter
from app.privacy.output_redaction import find_output_leaks, output_forbidden_key_set
from app.security.auth import AuthContext, get_auth_context
from app.tasks.attribution import recompute_window
from app.tasks.authority import SystemAuthorityEnvelope
from app.tasks.enqueue import enqueue_tenant_task
from tests.conftest import _insert_tenant


REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_SCANNER = REPO_ROOT / "scripts" / "ci" / "scan_b14_p5_artifacts.py"
PROXY_FAILURE_FORBIDDEN_KEYS = {
    "order_id",
    "click_id",
    "gclid",
    "fbclid",
    "external_event_id",
}


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _auth_context_for_tenant(tenant_id: UUID) -> AuthContext:
    return AuthContext(
        tenant_id=tenant_id,
        user_id=uuid4(),
        jti=uuid4(),
        issued_at_epoch=int(datetime.now(timezone.utc).timestamp()),
        subject="b14-p5-runtime",
        issuer="https://issuer.skeldir.test",
        audience="skeldir-api",
        claims={"scopes": ["viewer"], "tenant_id": str(tenant_id)},
    )


def _collect_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key).strip().lower())
            keys.update(_collect_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_collect_keys(item))
    return keys


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b14_p5_runtime_export_allowlist_blocks_identity_fields():
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    tenant_id = uuid4()
    now = datetime.now(timezone.utc)
    session_id = uuid4()

    async def _auth_override() -> AuthContext:
        return _auth_context_for_tenant(tenant_id)

    app.dependency_overrides[get_auth_context] = _auth_override
    try:
        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")

        result = await ingest_with_transaction(
            tenant_id=tenant_id,
            event_data={
                "event_type": "purchase",
                "event_timestamp": _iso(now),
                "revenue_amount": "42.00",
                "currency": "USD",
                "session_id": str(session_id),
                "vendor": "stripe",
                "utm_source": "stripe",
                "utm_medium": "checkout",
                "external_event_id": f"p5-export-{uuid4().hex[:8]}",
                "campaign_id": "cmp-p5-export",
                "order_id": f"order-{uuid4().hex[:8]}",
                "click_id": f"click-{uuid4().hex[:8]}",
            },
            idempotency_key=f"b14_p5_export_{uuid4().hex[:10]}",
            source="stripe",
            identity_payload={
                "session_id": str(session_id),
                "order_id": f"order-{uuid4().hex[:8]}",
                "click_id": f"click-{uuid4().hex[:8]}",
            },
            request_headers={
                "user-agent": "b14-p5-export-agent",
                "x-real-ip": "198.51.100.90",
            },
        )
        assert result["status"] == "success"

        window_start = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0))
        window_end = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
        recompute_result = enqueue_tenant_task(
            recompute_window,
            envelope=SystemAuthorityEnvelope(tenant_id=tenant_id),
            kwargs={
                "window_start": window_start,
                "window_end": window_end,
                "model_version": "1.0.0",
            },
        ).get()
        assert recompute_result["status"] == "succeeded"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            json_response = await client.get(
                "/api/export/json",
                headers={"X-Correlation-ID": str(uuid4())},
            )
            csv_response = await client.get(
                "/api/export/csv",
                headers={"X-Correlation-ID": str(uuid4())},
            )
    finally:
        app.dependency_overrides.pop(get_auth_context, None)
        celery_app.conf.task_always_eager = original_eager

    assert json_response.status_code == 200, json_response.text
    payload = json_response.json()
    assert set(payload.keys()) == {"tenant_id", "generated_at", "date_range", "data"}
    assert payload["tenant_id"] == str(tenant_id)
    assert set(payload["date_range"].keys()) == {"start", "end"}
    assert payload["data"]
    for row in payload["data"]:
        assert set(row.keys()) == set(EXPORT_ROW_ALLOWLIST)

    leaks = find_output_leaks(payload, forbidden_keys=output_forbidden_key_set())
    assert not leaks

    assert csv_response.status_code == 200
    csv_lines = [line.strip() for line in csv_response.text.splitlines() if line.strip()]
    assert csv_lines[0] == "date,channel,revenue,conversions,confidence"
    assert len(csv_lines) >= 2


def test_b14_p5_runtime_logging_redaction_blocks_direct_and_proxy_canaries():
    email_canary = "p5_canary_user@test.invalid"
    ip_canary = "203.0.113.88"
    ssn_canary = "111-22-3333"
    session_canary = "11111111-1111-1111-1111-111111111111"
    order_canary = "order-canary-p5"
    idempotency_canary = "idempotency-canary-p5"
    click_canary = "click-canary-p5"
    ua_canary = "b14-p5-canary-agent"

    logger = logging.getLogger("b14_p5_no_leak_runtime")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers = []
    logger.filters = []

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    logger.addHandler(handler)

    logger.info(
        "email=%s ip=%s ssn=%s session_id=%s order_id=%s idempotency_key=%s click_id=%s user_agent=%s",
        email_canary,
        ip_canary,
        ssn_canary,
        session_canary,
        order_canary,
        idempotency_canary,
        click_canary,
        ua_canary,
    )
    logger.info(
        {
            "event_type": "p5_canary_log",
            "vendor_payload": {"email": email_canary, "ip_address": ip_canary},
            "order_id": order_canary,
            "idempotency_key": idempotency_canary,
            "click_id": click_canary,
        }
    )

    try:
        raise RuntimeError(
            f"session_id={session_canary} order_id={order_canary} click_id={click_canary}"
        )
    except RuntimeError:
        logger.exception("failure idempotency_key=%s", idempotency_canary)

    rendered = stream.getvalue()
    for marker in (
        email_canary,
        ip_canary,
        ssn_canary,
        session_canary,
        order_canary,
        idempotency_canary,
        click_canary,
        ua_canary,
    ):
        assert marker not in rendered
    assert "***" in rendered


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b14_p5_runtime_failure_surfaces_redact_dead_letter_and_quarantine(test_tenant):
    tenant_id = test_tenant
    correlation = str(uuid4())
    payload = {
        "event_type": "purchase",
        "event_timestamp": _iso(datetime.now(timezone.utc)),
        "revenue_amount": "13.37",
        "currency": "USD",
        "session_id": str(uuid4()),
        "idempotency_key": f"b14_p5_dlq_{uuid4().hex[:8]}",
        "external_event_id": f"ext_{uuid4().hex[:8]}",
        "order_id": f"order_{uuid4().hex[:8]}",
        "click_id": f"click_{uuid4().hex[:8]}",
        "gclid": f"gclid_{uuid4().hex[:8]}",
        "fbclid": f"fbclid_{uuid4().hex[:8]}",
        "vendor_payload": {
            "customer": {
                "email": "deadletter-user@test.invalid",
                "ip_address": "198.51.100.44",
            }
        },
    }

    async with get_session(tenant_id=tenant_id) as session:
        handler = DLQHandler()
        dead_event = await handler.route_to_dlq(
            session=session,
            tenant_id=tenant_id,
            original_payload=payload,
            error=ValueError("p5 no-leak canary"),
            correlation_id=correlation,
            source="b14_p5_runtime",
            identity_payload=payload,
            request_headers={"user-agent": "b14-p5-runtime-agent"},
        )
        await session.commit()
        dead_event_id = dead_event.id

    async with get_session(tenant_id=tenant_id) as session:
        row = await session.execute(
            text("SELECT raw_payload, error_message, error_detail FROM dead_events WHERE id = :id"),
            {"id": str(dead_event_id)},
        )
        persisted = row.mappings().one()
        raw_payload = persisted["raw_payload"]
        key_set = _collect_keys(raw_payload)
        assert "deadletter-user@test.invalid" not in json.dumps(raw_payload)
        assert "198.51.100.44" not in json.dumps(raw_payload)
        assert PROXY_FAILURE_FORBIDDEN_KEYS.isdisjoint(key_set)
        assert "p5 no-leak canary" in persisted["error_message"]

    quarantine_source = f"b14_p5_quarantine_{uuid4().hex[:8]}"
    await route_unresolved_tenant_to_quarantine(
        source=quarantine_source,
        payload=payload,
        error_message="p5 quarantine failure",
        correlation_id=str(uuid4()),
        identity_payload=payload,
        request_headers={"user-agent": "b14-p5-quarantine-agent"},
    )

    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT id, raw_payload
                    FROM dead_events_quarantine
                    WHERE source = :source
                    ORDER BY ingested_at DESC
                    LIMIT 1
                    """
                ),
                {"source": quarantine_source},
            )
        ).mappings().one()
        raw_payload = row["raw_payload"]
        key_set = _collect_keys(raw_payload)
        assert "deadletter-user@test.invalid" not in json.dumps(raw_payload)
        assert "198.51.100.44" not in json.dumps(raw_payload)
        assert PROXY_FAILURE_FORBIDDEN_KEYS.isdisjoint(key_set)
        await conn.execute(text("DELETE FROM dead_events_quarantine WHERE id = :id"), {"id": row["id"]})


def test_b14_p5_runtime_artifact_scanner_fails_on_seeded_canaries_and_passes_sanitized_bundle(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    leak_file = artifacts_dir / "worker.log"
    leak_file.write_text(
        "\n".join(
            [
                "runtime probe output",
                "email=p5_artifact_canary@test.invalid",
                "session_id=11111111-1111-1111-1111-111111111111",
            ]
        ),
        encoding="utf-8",
    )

    failure = subprocess.run(
        [
            sys.executable,
            str(ARTIFACT_SCANNER),
            "--artifacts-dir",
            str(artifacts_dir),
            "--canary",
            "p5_artifact_canary@test.invalid",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
    )
    assert failure.returncode != 0
    assert "result=FAIL" in failure.stdout

    leak_file.write_text(
        "\n".join(
            [
                "runtime probe output",
                "email=***",
                "session_id=***",
            ]
        ),
        encoding="utf-8",
    )
    success = subprocess.run(
        [
            sys.executable,
            str(ARTIFACT_SCANNER),
            "--artifacts-dir",
            str(artifacts_dir),
            "--canary",
            "p5_artifact_canary@test.invalid",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
    )
    assert success.returncode == 0, success.stdout + "\n" + success.stderr
    assert "result=PASS" in success.stdout
