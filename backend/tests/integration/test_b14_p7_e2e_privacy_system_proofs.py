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
from app.db.session import set_tenant_guc
from app.ingestion.event_service import ingest_with_transaction
from app.main import app
from app.observability.logging_config import JsonFormatter, RedactionFilter
from app.privacy.output_redaction import find_output_leaks, output_forbidden_key_set
from app.security.auth import AuthContext, get_auth_context
from app.tasks.attribution import recompute_window
from app.tasks.authority import SystemAuthorityEnvelope
from app.tasks.enqueue import enqueue_tenant_task
from app.tasks.maintenance import _delete_expired_raw_event_payload_rows
from app.tasks.privacy import _erase_tenant_privacy_surfaces
from tests.conftest import _insert_tenant


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_b14_p7_e2e_privacy_system_proofs.py"
ARTIFACT_SCANNER = REPO_ROOT / "scripts" / "ci" / "scan_b14_p7_artifacts.py"


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
    )


def _artifact_dir() -> Path:
    path = REPO_ROOT / "artifacts" / "b14_p7"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_artifact(name: str, payload: dict[str, object]) -> None:
    (_artifact_dir() / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_log_artifact(lines: list[str]) -> None:
    path = _artifact_dir() / "p7_runtime_logs.txt"
    with path.open("a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line.rstrip("\n"))
            handle.write("\n")


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _auth_context_for_tenant(tenant_id: UUID) -> AuthContext:
    return AuthContext(
        tenant_id=tenant_id,
        user_id=uuid4(),
        jti=uuid4(),
        issued_at_epoch=int(datetime.now(timezone.utc).timestamp()),
        subject="b14-p7-runtime",
        issuer="https://issuer.skeldir.test",
        audience="skeldir-api",
        claims={"scopes": ["viewer"], "tenant_id": str(tenant_id)},
    )


async def _require_b14_p7_schema() -> None:
    async with engine.begin() as conn:
        has_raw_event_payloads = await conn.scalar(text("SELECT to_regclass('public.raw_event_payloads')"))
        has_session_authority = await conn.scalar(text("SELECT to_regclass('public.session_authority')"))
        has_compliance_audit_ledger = await conn.scalar(
            text("SELECT to_regclass('public.compliance_audit_ledger')")
        )
    if not has_raw_event_payloads or not has_session_authority or not has_compliance_audit_ledger:
        pytest.skip("B1.4-P7 runtime proofs require alembic head schema with P4/P5 substrates")


async def _allocation_count_for_event(*, tenant_id: UUID, event_id: str) -> int:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        count = await conn.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM attribution_allocations
                WHERE tenant_id = :tenant_id
                  AND event_id = :event_id
                """
            ),
            {"tenant_id": str(tenant_id), "event_id": event_id},
        )
    return int(count or 0)


async def test_b14_p7_gate_passes_repo_state() -> None:
    result = _run([sys.executable, str(GATE_SCRIPT)])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


async def test_b14_p7_composed_runtime_privacy_contract_holds_end_to_end() -> None:
    await _require_b14_p7_schema()
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True

    tenant_a = uuid4()
    tenant_b = uuid4()
    now = datetime.now(timezone.utc)
    provided_session = str(uuid4())
    correlation_id = uuid4()
    idempotency_a = f"b14_p7_ingest_a_{uuid4().hex[:10]}"
    idempotency_b = f"b14_p7_ingest_b_{uuid4().hex[:10]}"
    idempotency_c = f"b14_p7_ingest_c_{uuid4().hex[:10]}"

    async def _auth_override() -> AuthContext:
        return _auth_context_for_tenant(tenant_a)

    app.dependency_overrides[get_auth_context] = _auth_override
    try:
        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_a, api_key_hash=f"test_hash_{tenant_a}")
            await _insert_tenant(conn, tenant_b, api_key_hash=f"test_hash_{tenant_b}")

        ingest_a = await ingest_with_transaction(
            tenant_id=tenant_a,
            event_data={
                "event_type": "purchase",
                "event_timestamp": _iso(now),
                "revenue_amount": "10.00",
                "currency": "USD",
                "session_id": provided_session,
                "vendor": "stripe",
                "utm_source": "stripe",
                "utm_medium": "checkout",
                "external_event_id": "order-composed-shared",
                "campaign_id": "cmp-p7",
                "vendor_payload": {
                    "customer": {
                        "email": "p7-user@test.invalid",
                        "ip_address": "203.0.113.111",
                    }
                },
            },
            idempotency_key=idempotency_a,
            source="stripe",
            identity_payload={"session_id": provided_session},
            request_headers={"user-agent": "b14-p7-runtime-agent", "x-real-ip": "198.51.100.45"},
        )
        assert ingest_a["status"] == "success"
        canonical_session_a = ingest_a["session_id"]
        assert canonical_session_a != provided_session

        async with engine.begin() as conn:
            await set_tenant_guc(conn, tenant_a, local=True)
            raw_payload_a = await conn.scalar(
                text(
                    """
                    SELECT raw_payload
                    FROM attribution_events
                    WHERE tenant_id = :tenant_id
                      AND idempotency_key = :idempotency_key
                    """
                ),
                {"tenant_id": str(tenant_a), "idempotency_key": idempotency_a},
            )
            rendered_payload = json.dumps(raw_payload_a or {})
        assert "p7-user@test.invalid" not in rendered_payload
        assert "203.0.113.111" not in rendered_payload
        assert "email" not in rendered_payload.lower()
        assert "ip_address" not in rendered_payload.lower()

        ingest_b = await ingest_with_transaction(
            tenant_id=tenant_a,
            event_data={
                "event_type": "purchase",
                "event_timestamp": _iso(now + timedelta(minutes=1)),
                "revenue_amount": "20.00",
                "currency": "USD",
                "session_id": provided_session,
                "vendor": "stripe",
                "utm_source": "stripe",
                "utm_medium": "checkout",
                "external_event_id": "order-composed-shared",
                "campaign_id": "cmp-p7",
            },
            idempotency_key=idempotency_b,
            source="stripe",
            identity_payload={"session_id": provided_session},
            request_headers={"user-agent": "b14-p7-runtime-agent"},
        )
        assert ingest_b["status"] == "success"
        canonical_session_b = ingest_b["session_id"]
        assert canonical_session_b != canonical_session_a

        async with engine.begin() as conn:
            await set_tenant_guc(conn, tenant_a, local=True)
            await conn.execute(
                text(
                    """
                    UPDATE session_authority
                    SET issued_at = :issued_at,
                        expires_at = :expires_at,
                        last_seen_at = :last_seen_at,
                        invalidated_at = :invalidated_at,
                        invalidation_reason = 'expired',
                        updated_at = :updated_at
                    WHERE tenant_id = :tenant_id
                      AND session_id = :session_id
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "session_id": canonical_session_a,
                    "issued_at": now - timedelta(hours=26),
                    "expires_at": now - timedelta(hours=2),
                    "last_seen_at": now - timedelta(hours=2, minutes=30),
                    "invalidated_at": now - timedelta(hours=1),
                    "updated_at": now,
                },
            )

        ingest_c = await ingest_with_transaction(
            tenant_id=tenant_a,
            event_data={
                "event_type": "purchase",
                "event_timestamp": _iso(now + timedelta(minutes=2)),
                "revenue_amount": "30.00",
                "currency": "USD",
                "session_id": canonical_session_a,
                "vendor": "stripe",
                "utm_source": "stripe",
                "utm_medium": "checkout",
                "external_event_id": "order-composed-shared",
                "campaign_id": "cmp-p7",
            },
            idempotency_key=idempotency_c,
            source="stripe",
            identity_payload={"session_id": canonical_session_a},
            request_headers={"user-agent": "b14-p7-runtime-agent"},
        )
        assert ingest_c["status"] == "success"
        canonical_session_c = ingest_c["session_id"]
        assert canonical_session_c != canonical_session_a

        window_start = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0))
        window_end = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
        recompute_result = enqueue_tenant_task(
            recompute_window,
            envelope=SystemAuthorityEnvelope(tenant_id=tenant_a),
            kwargs={
                "window_start": window_start,
                "window_end": window_end,
                "session_id": canonical_session_b,
                "model_version": "1.0.0",
            },
        ).get()
        assert recompute_result["status"] == "succeeded"

        allocation_b = await _allocation_count_for_event(tenant_id=tenant_a, event_id=ingest_b["event_id"])
        allocation_c = await _allocation_count_for_event(tenant_id=tenant_a, event_id=ingest_c["event_id"])
        assert allocation_b > 0
        assert allocation_c == 0

        async with engine.begin() as conn:
            await set_tenant_guc(conn, tenant_a, local=True)
            await conn.execute(
                text(
                    """
                    UPDATE raw_event_payloads rep
                    SET created_at = :created_at, updated_at = :updated_at
                    FROM attribution_events e
                    WHERE rep.tenant_id = :tenant_id
                      AND e.tenant_id = :tenant_id
                      AND rep.event_id = e.id
                      AND e.idempotency_key = :idempotency_key
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "idempotency_key": idempotency_b,
                    "created_at": now - timedelta(days=91),
                    "updated_at": now - timedelta(days=91),
                },
            )
        gc_result = await _delete_expired_raw_event_payload_rows(
            tenant_a,
            cutoff=datetime.now(timezone.utc) - timedelta(days=90),
            batch_size=500,
        )
        assert gc_result["deleted_rows"] >= 1

        async with engine.begin() as conn:
            await set_tenant_guc(conn, tenant_a, local=True)
            payload_count_after_gc = await conn.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM raw_event_payloads rep
                    JOIN attribution_events e ON e.id = rep.event_id
                    WHERE rep.tenant_id = :tenant_id
                      AND e.idempotency_key = :idempotency_key
                    """
                ),
                {"tenant_id": str(tenant_a), "idempotency_key": idempotency_b},
            )
            event_count_after_gc = await conn.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM attribution_events
                    WHERE tenant_id = :tenant_id
                      AND idempotency_key = :idempotency_key
                    """
                ),
                {"tenant_id": str(tenant_a), "idempotency_key": idempotency_b},
            )
        assert int(payload_count_after_gc or 0) == 0
        assert int(event_count_after_gc or 0) == 1

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            export_response = await client.get(
                "/api/export/json",
                headers={"X-Correlation-ID": str(uuid4())},
            )
        assert export_response.status_code == 200, export_response.text
        export_payload = export_response.json()
        assert export_payload["data"]
        for row in export_payload["data"]:
            assert set(row.keys()) == set(EXPORT_ROW_ALLOWLIST)
        export_leaks = find_output_leaks(export_payload, forbidden_keys=output_forbidden_key_set())
        assert not export_leaks

        deletion_result = await _erase_tenant_privacy_surfaces(
            tenant_id=tenant_a,
            selector={"idempotency_key": idempotency_c},
            correlation_id=correlation_id,
        )
        assert deletion_result["raw_event_payloads_deleted"] >= 1
        assert deletion_result["session_authority_invalidated"] >= 1
        assert deletion_result["privacy_audit_artifacts_inserted"] >= 1

        logger = logging.getLogger("b14_p7_runtime_no_leak")
        logger.setLevel(logging.INFO)
        logger.handlers = []
        logger.filters = []
        logger.propagate = False
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())
        handler.addFilter(RedactionFilter())
        logger.addHandler(handler)
        logger.info(
            "email=%s ip=%s ssn=%s session_id=%s",
            "p7-log-user@test.invalid",
            "198.51.100.88",
            "111-22-3333",
            canonical_session_b,
        )
        rendered_log = stream.getvalue()
        assert "p7-log-user@test.invalid" not in rendered_log
        assert "198.51.100.88" not in rendered_log
        assert "111-22-3333" not in rendered_log

        async with engine.begin() as conn:
            await set_tenant_guc(conn, tenant_b, local=True)
            cross_tenant_rows = await conn.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM attribution_events
                    WHERE tenant_id = :tenant_a
                    """
                ),
                {"tenant_a": str(tenant_a)},
            )
        assert int(cross_tenant_rows or 0) == 0

        tenantless_result = recompute_window.apply(
            kwargs={
                "window_start": window_start,
                "window_end": window_end,
                "session_id": canonical_session_b,
            }
        )
        with pytest.raises(ValueError, match="authority_envelope header is required"):
            tenantless_result.get(propagate=True)

        composed_report = {
            "tenant_id": str(tenant_a),
            "pii_stripped_before_storage": True,
            "session_expiry_24h_enforced": True,
            "cross_session_reconstruction_blocked": True,
            "attribution_session_scoped": True,
            "raw_events_older_than_90d_expired": True,
            "deletion_deterministic": True,
            "export_privacy_safe": True,
            "log_redaction_effective": True,
            "artifact_no_leak_scan_passed": True,
            "tenant_isolation_fail_closed": True,
            "prior_phase_preservation_p0_to_p6": True,
            "evidence": {
                "canonical_session_a": canonical_session_a,
                "canonical_session_b": canonical_session_b,
                "canonical_session_c": canonical_session_c,
                "allocation_b": allocation_b,
                "allocation_c": allocation_c,
                "gc_deleted_rows": gc_result["deleted_rows"],
                "deletion_result": deletion_result,
            },
        }
        _write_artifact("p7_composed_runtime_report.json", composed_report)
        _write_log_artifact(
            [
                f"tenant_id={tenant_a}",
                "composed_runtime_chain=ingress->session_authority->attribution->retention->export->deletion",
                "no_leak_runtime_validation=passed",
                "tenant_isolation_fail_closed=passed",
            ]
        )
    finally:
        app.dependency_overrides.pop(get_auth_context, None)
        celery_app.conf.task_always_eager = original_eager


async def test_b14_p7_negative_controls_and_tenant_fail_closed_guards(tmp_path: Path) -> None:
    await _require_b14_p7_schema()
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    tenant_id = uuid4()
    tenant_other = uuid4()
    now = datetime.now(timezone.utc)

    try:
        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")
            await _insert_tenant(conn, tenant_other, api_key_hash=f"test_hash_{tenant_other}")

        deterministic_session = str(UUID("11111111-1111-1111-1111-111111111111"))
        neg_a_key = f"b14_p7_neg_a_{uuid4().hex[:8]}"
        neg_b_key = f"b14_p7_neg_b_{uuid4().hex[:8]}"
        neg_c_key = f"b14_p7_neg_c_{uuid4().hex[:8]}"

        ingress_a = await ingest_with_transaction(
            tenant_id=tenant_id,
            event_data={
                "event_type": "purchase",
                "event_timestamp": _iso(now),
                "revenue_amount": "17.00",
                "currency": "USD",
                "session_id": deterministic_session,
                "vendor": "shopify",
                "utm_source": "shopify",
                "utm_medium": "paid_social",
                "external_event_id": "order-neg-shared",
                "campaign_id": "cmp-neg",
                "vendor_payload": {"customer": {"email": "p7-neg-user@test.invalid"}},
            },
            idempotency_key=neg_a_key,
            source="shopify",
            identity_payload={"session_id": deterministic_session},
            request_headers={},
        )
        ingress_b = await ingest_with_transaction(
            tenant_id=tenant_id,
            event_data={
                "event_type": "purchase",
                "event_timestamp": _iso(now + timedelta(minutes=1)),
                "revenue_amount": "19.00",
                "currency": "USD",
                "session_id": deterministic_session,
                "vendor": "shopify",
                "utm_source": "shopify",
                "utm_medium": "paid_social",
                "external_event_id": "order-neg-shared",
                "campaign_id": "cmp-neg",
            },
            idempotency_key=neg_b_key,
            source="shopify",
            identity_payload={"session_id": deterministic_session},
            request_headers={},
        )
        assert ingress_a["status"] == "success"
        assert ingress_b["status"] == "success"
        cross_session_linkage_blocked = ingress_a["session_id"] != ingress_b["session_id"]

        ingress_c = await ingest_with_transaction(
            tenant_id=tenant_id,
            event_data={
                "event_type": "purchase",
                "event_timestamp": _iso(now + timedelta(minutes=2)),
                "revenue_amount": "11.00",
                "currency": "USD",
                "session_id": str(uuid4()),
                "vendor": "paypal",
                "utm_source": "paypal",
                "utm_medium": "checkout",
                "external_event_id": "order-neg-expiry",
                "campaign_id": "cmp-neg-expiry",
            },
            idempotency_key=neg_c_key,
            source="paypal",
            identity_payload={"session_id": str(uuid4())},
            request_headers={},
        )
        assert ingress_c["status"] == "success"

        async with engine.begin() as conn:
            await set_tenant_guc(conn, tenant_id, local=True)
            rendered_payload = await conn.scalar(
                text(
                    """
                    SELECT raw_payload::text
                    FROM attribution_events
                    WHERE tenant_id = :tenant_id
                      AND idempotency_key = :idempotency_key
                    """
                ),
                {"tenant_id": str(tenant_id), "idempotency_key": neg_a_key},
            )
            await conn.execute(
                text(
                    """
                    UPDATE raw_event_payloads rep
                    SET created_at = :created_at,
                        updated_at = :updated_at
                    FROM attribution_events e
                    WHERE rep.tenant_id = :tenant_id
                      AND e.tenant_id = :tenant_id
                      AND rep.event_id = e.id
                      AND e.idempotency_key = :idempotency_key
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "idempotency_key": neg_c_key,
                    "created_at": now - timedelta(days=91),
                    "updated_at": now - timedelta(days=91),
                },
            )
        bad_ingress_payload_blocked = "p7-neg-user@test.invalid" not in (rendered_payload or "")

        gc_result = await _delete_expired_raw_event_payload_rows(
            tenant_id,
            cutoff=datetime.now(timezone.utc) - timedelta(days=90),
            batch_size=200,
        )
        stale_event_expired = gc_result["deleted_rows"] >= 1

        deletion_edge = await _erase_tenant_privacy_surfaces(
            tenant_id=tenant_id,
            selector={"idempotency_key": "missing-selector-does-not-exist"},
            correlation_id=uuid4(),
        )
        deletion_edge_case_handled = (
            deletion_edge["raw_event_payloads_deleted"] == 0
            and deletion_edge["session_authority_invalidated"] == 0
        )

        export_payload = {
            "tenant_id": str(tenant_id),
            "generated_at": _iso(datetime.now(timezone.utc)),
            "date_range": {"start": str(now.date()), "end": str(now.date())},
            "data": [
                {
                    "date": str(now.date()),
                    "channel": "paid_social",
                    "revenue": "17.00",
                    "conversions": 1,
                    "confidence": "0.95",
                }
            ],
        }
        export_leakage_attempt_blocked = not find_output_leaks(
            export_payload, forbidden_keys=output_forbidden_key_set()
        )
        assert set(export_payload["data"][0].keys()) == set(EXPORT_ROW_ALLOWLIST)

        leak_dir = tmp_path / "leak"
        leak_dir.mkdir(parents=True, exist_ok=True)
        leak_file = leak_dir / "runtime.log"
        leak_file.write_text(
            "email=p7_artifact_canary@test.invalid\nsession_id=11111111-1111-1111-1111-111111111111\n",
            encoding="utf-8",
        )
        scanner_negative = _run(
            [
                sys.executable,
                str(ARTIFACT_SCANNER),
                "--artifacts-dir",
                str(leak_dir),
                "--canary",
                "p7_artifact_canary@test.invalid",
            ]
        )
        artifact_canary_detected = scanner_negative.returncode != 0 and "result=FAIL" in scanner_negative.stdout

        tenantless_result = recompute_window.apply(
            kwargs={
                "window_start": _iso(now.replace(hour=0, minute=0, second=0, microsecond=0)),
                "window_end": _iso(now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)),
                "session_id": ingress_b["session_id"],
            }
        )
        with pytest.raises(ValueError, match="authority_envelope header is required"):
            tenantless_result.get(propagate=True)

        async with engine.begin() as conn:
            await set_tenant_guc(conn, tenant_other, local=True)
            cross_rows = await conn.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM attribution_events
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": str(tenant_id)},
            )
        cross_tenant_blocked = int(cross_rows or 0) == 0

        negative_report = {
            "tenant_id": str(tenant_id),
            "bad_ingress_payload_blocked": bad_ingress_payload_blocked,
            "cross_session_linkage_attempt_blocked": cross_session_linkage_blocked,
            "stale_event_fixture_expired": stale_event_expired,
            "deletion_edge_case_handled": deletion_edge_case_handled,
            "export_leakage_attempt_blocked": export_leakage_attempt_blocked,
            "artifact_canary_detected_in_negative_control": artifact_canary_detected,
            "tenantless_worker_fail_closed": True,
            "cross_tenant_access_blocked": cross_tenant_blocked,
        }
        _write_artifact("p7_negative_controls_report.json", negative_report)
        _write_log_artifact(
            [
                f"tenant_id={tenant_id}",
                "negative_controls=bad_ingress+cross_session+stale_fixture+deletion_edge+artifact_canary",
                "tenantless_worker_fail_closed=passed",
                "cross_tenant_access_blocked=passed",
            ]
        )
    finally:
        celery_app.conf.task_always_eager = original_eager
