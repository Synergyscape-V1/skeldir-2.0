"""Directive-II conservation, cursor, streaming-ingress, and liveness proofs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.api import trust_api
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey
from app.trust.machine_auth import MachineCallerContext
from app.trust.machine_identity import AgentScope
from app.trust.query_continuation import (
    CURSOR_TTL,
    TrustQueryContinuationError,
    continuation_expiry,
    issue_trust_query_continuation,
    trust_query_binding_hash,
    verify_trust_query_continuation,
)
from app.trust.source_adapters import MatchVerdictSource
from app.trust.tenant_security import (
    TENANT_AUDIT_ACQUIRE_TIMEOUT_SECONDS,
    TENANT_AUDIT_OPERATION_TIMEOUT_SECONDS,
    TENANT_CONTEXT_EXTERNAL_REASON,
    TENANT_EMERGENCY_SIGNALS,
    TENANT_HANDLER_TIMEOUT_SECONDS,
    TenantContextMissingException,
    record_tenant_context_failure_durable,
    tenant_context_missing_exception_handler,
)


def _registry(seed: bytes = b"directive-ii-cursor-domain-key") -> TrustKeyRegistry:
    private = Ed25519PrivateKey.from_private_bytes(hashlib.sha256(seed).digest())
    return TrustKeyRegistry(
        (
            TrustSigningKey(
                kid="kid:b25-p10-directive-ii",
                algorithm="ed25519",
                public_key=private.public_key(),
                private_key=private,
                state="active",
                valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        )
    )


def _caller(tenant_id: UUID) -> MachineCallerContext:
    return MachineCallerContext(
        agent_client_id=uuid4(),
        tenant_id=tenant_id,
        audience="b25-p10-directive-ii-agent",
        scopes=frozenset({AgentScope.ENVELOPE_READ, AgentScope.ENVELOPE_VERIFY}),
        nonce_value="directive-ii-nonce-0001",
        request_identity_hash="sha256:" + "7" * 64,
    )


def _headers(
    tenant_id: UUID, *, idempotency: str = "directive-ii-request"
) -> dict[str, str]:
    return {
        "Authorization": "Bearer directive-ii-machine-token",
        "X-Tenant-ID": str(tenant_id),
        "X-Trust-Nonce": "directive-ii-nonce-0001",
        "X-Correlation-ID": str(uuid4()),
        "X-Idempotency-Key": idempotency,
    }


def _source(tenant_id: UUID, verdict_id: UUID, order: int) -> MatchVerdictSource:
    observed = datetime(2026, 7, 1, tzinfo=timezone.utc) + timedelta(seconds=order)
    return MatchVerdictSource(
        id=verdict_id,
        tenant_id=tenant_id,
        webhook_ingress_identity_id=None,
        provider="stripe",
        canonical_commerce_reference=f"order-{order}",
        provider_native_event_reference=f"event-{order}",
        provider_native_commerce_reference=f"commerce-{order}",
        status="matched_confirmed",
        match_quality="exact",
        canonical_net_verified_amount_minor=1000 + order,
        currency_code="USD",
        last_transition_at=observed,
        created_at=observed - timedelta(days=1),
        updated_at=observed,
    )


def _route_app(registry: TrustKeyRegistry) -> FastAPI:
    app = FastAPI()
    app.include_router(trust_api.router, prefix="/api")
    app.add_exception_handler(
        trust_api.TrustRequestBoundaryException,
        trust_api.trust_request_boundary_exception_handler,
    )

    async def session_dependency():
        yield object()

    async def trusted(request: Request) -> MachineCallerContext:
        return _caller(UUID(request.headers["X-Tenant-ID"]))

    app.dependency_overrides[trust_api.get_machine_db_session] = session_dependency
    app.dependency_overrides[trust_api.require_envelope_read_tenant_context] = trusted
    app.dependency_overrides[trust_api.require_envelope_verify_tenant_context] = trusted
    app.dependency_overrides[trust_api.get_runtime_signing_registry] = lambda: registry
    app.dependency_overrides[trust_api.get_runtime_verification_registry] = (
        lambda: registry.public_only()
    )
    return app


@pytest.mark.asyncio
async def test_complete_fifty_reference_lifecycle_conserves_every_input_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    verdict_ids = [uuid4() for _ in range(50)]
    refs = [f"urn:skeldir:match_verdict:{value}" for value in verdict_ids]
    qualifying_indexes = {0, 1, 5, 10, 11, 24, 31, 48, 49}
    qualifying = {
        verdict_ids[index]: _source(tenant_id, verdict_ids[index], 100 - index)
        for index in qualifying_indexes
    }
    page_calls: list[list[str]] = []
    issued_refs: list[str] = []

    async def select_sources(session, *, subject_refs, row_limit, **kwargs):
        _ = session, kwargs
        page_calls.append(list(subject_refs))
        assert 1 <= len(subject_refs) <= trust_api.MAX_EVALUATED_REFS_PER_PAGE
        assert row_limit == len(subject_refs)
        selected = [
            qualifying[UUID(value.rsplit(":", 1)[1])]
            for value in subject_refs
            if UUID(value.rsplit(":", 1)[1]) in qualifying
        ]
        return tuple(reversed(selected))  # Deliberately disagree with input order.

    async def issue(**kwargs):
        issued_refs.append(kwargs["subject_ref"])
        return {
            "subject_ref": kwargs["subject_ref"],
            "signature": "ed25519:directive-ii-test",
        }

    monkeypatch.setattr(trust_api, "query_match_verdict_sources", select_sources)
    monkeypatch.setattr(trust_api, "_issue_signed_envelope", issue)
    app = _route_app(_registry())
    request_body: dict[str, object] = {
        "subject_types": ["match_verdict"],
        "subject_refs": refs,
    }
    responses: list[dict[str, object]] = []
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        while True:
            response = await client.post(
                "/api/trust/v1/envelopes/query",
                headers=_headers(tenant_id),
                json=request_body,
            )
            assert response.status_code == 200, response.text
            body = response.json()
            responses.append(body)
            page = body["page"]
            assert page["evaluated_count"] + page["remaining_count"] == 50
            assert page["page_evaluated_count"] <= 2
            if page["complete"]:
                assert page["remaining_count"] == 0
                assert body["continuation_token"] is None
                break
            assert body["continuation_token"]
            request_body["continuation_token"] = body["continuation_token"]

    assert len(responses) == 25
    assert [item for page in page_calls for item in page] == refs
    expected = [refs[index] for index in range(50) if index in qualifying_indexes]
    assert issued_refs == expected
    assert len(issued_refs) == len(set(issued_refs)) == len(qualifying_indexes)


@pytest.mark.asyncio
async def test_cursor_tenant_request_predicate_integrity_expiry_and_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _registry()
    tenant_a = uuid4()
    tenant_b = uuid4()
    refs = [f"urn:skeldir:match_verdict:{uuid4()}" for _ in range(4)]
    source_calls = 0

    async def no_matches(*args, **kwargs):
        nonlocal source_calls
        source_calls += 1
        return ()

    monkeypatch.setattr(trust_api, "query_match_verdict_sources", no_matches)
    now = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(trust_api, "_utc_now", lambda: now)
    app = _route_app(registry)
    initial = {"subject_types": ["match_verdict"], "subject_refs": refs}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post(
            "/api/trust/v1/envelopes/query",
            headers=_headers(tenant_a),
            json=initial,
        )
        assert first.status_code == 200
        token = first.json()["continuation_token"]
        assert token and str(tenant_a) not in token and refs[0] not in token
        calls_after_first = source_calls

        invalid_requests = [
            (_headers(tenant_b), {**initial, "continuation_token": token}),
            (
                _headers(tenant_a),
                {
                    **initial,
                    "subject_refs": [
                        *refs[:-1],
                        f"urn:skeldir:match_verdict:{uuid4()}",
                    ],
                    "continuation_token": token,
                },
            ),
            (
                _headers(tenant_a),
                {
                    **initial,
                    "created_at_after": "2026-08-01T00:00:00Z",
                    "created_at_before": "2026-08-02T00:00:00Z",
                    "continuation_token": token,
                },
            ),
            (
                _headers(tenant_a),
                {
                    **initial,
                    "continuation_token": token[:-1]
                    + ("A" if token[-1] != "A" else "B"),
                },
            ),
        ]
        for headers, body in invalid_requests:
            refused = await client.post(
                "/api/trust/v1/envelopes/query", headers=headers, json=body
            )
            assert refused.status_code == 422
            assert refused.json()["reason_code"] == "continuation_invalid"
        assert source_calls == calls_after_first

        page_two_body = {**initial, "continuation_token": token}
        page_two = await client.post(
            "/api/trust/v1/envelopes/query",
            headers=_headers(tenant_a),
            json=page_two_body,
        )
        retry = await client.post(
            "/api/trust/v1/envelopes/query",
            headers=_headers(tenant_a),
            json=page_two_body,
        )
        assert page_two.status_code == retry.status_code == 200
        assert (
            page_two.json()["continuation_token"] == retry.json()["continuation_token"]
        )
        assert page_two.json()["page"]["complete"] is True

        monkeypatch.setattr(trust_api, "_utc_now", lambda: now + CURSOR_TTL)
        expired = await client.post(
            "/api/trust/v1/envelopes/query",
            headers=_headers(tenant_a),
            json=page_two_body,
        )
        assert expired.status_code == 422
        assert expired.json()["reason_code"] == "continuation_expired"


def test_cursor_domain_is_explicit_and_public_only_verification_is_sufficient() -> None:
    registry = _registry()
    tenant_id = uuid4()
    binding = trust_query_binding_hash(
        tenant_id=tenant_id,
        subject_types=["match_verdict"],
        subject_refs=[f"urn:skeldir:match_verdict:{uuid4()}" for _ in range(3)],
        updated_at_after=None,
        updated_at_before=None,
    )
    now = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    token = issue_trust_query_continuation(
        key_registry=registry,
        binding_hash=binding,
        next_position=2,
        total_accepted=3,
        expires_at=continuation_expiry(now),
    )
    state = verify_trust_query_continuation(
        token,
        key_registry=registry.public_only(),
        expected_binding_hash=binding,
        expected_total=3,
        now=now,
    )
    assert state.next_position == 2
    with pytest.raises(TrustQueryContinuationError, match="continuation_invalid"):
        verify_trust_query_continuation(
            token,
            key_registry=_registry(b"different-key").public_only(),
            expected_binding_hash=binding,
            expected_total=3,
            now=now,
        )


def _request_with_chunks(
    chunks: list[bytes],
    *,
    headers: list[tuple[bytes, bytes]] | None = None,
) -> tuple[Request, list[int]]:
    messages = [
        {"type": "http.request", "body": chunk, "more_body": index < len(chunks) - 1}
        for index, chunk in enumerate(chunks)
    ]
    consumed: list[int] = []

    async def receive():
        message = messages.pop(0)
        consumed.append(len(message["body"]))
        return message

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/trust/v1/envelopes/query",
        "raw_path": b"/api/trust/v1/envelopes/query",
        "query_string": b"",
        "headers": headers or [],
        "client": ("127.0.0.1", 1),
        "server": ("test", 80),
    }
    return Request(scope, receive), consumed


@pytest.mark.asyncio
async def test_streaming_ingress_exact_limit_and_declared_overage() -> None:
    valid = json.dumps(
        {
            "subject_types": ["match_verdict"],
            "subject_refs": [f"urn:skeldir:match_verdict:{uuid4()}"],
        },
        separators=(",", ":"),
    ).encode()
    exact = valid + b" " * (trust_api.MAX_QUERY_BODY_BYTES - len(valid))
    request, consumed = _request_with_chunks(
        [exact], headers=[(b"content-length", str(len(exact)).encode())]
    )
    parsed = await trust_api.validate_trust_query_request(request)
    assert len(parsed.subject_refs) == 1
    assert sum(consumed) == trust_api.MAX_QUERY_BODY_BYTES
    assert request.state.p10_ingress_bytes_consumed == trust_api.MAX_QUERY_BODY_BYTES

    declared, consumed = _request_with_chunks(
        [b"must-not-be-read"],
        headers=[(b"content-length", str(trust_api.MAX_QUERY_BODY_BYTES + 1).encode())],
    )
    with pytest.raises(trust_api.TrustRequestBoundaryException) as exc_info:
        await trust_api.validate_trust_query_request(declared)
    assert exc_info.value.status_code == 413
    assert consumed == []
    assert declared.state.p10_ingress_bytes_consumed == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers",
    [
        [],
        [(b"content-length", b"1")],
    ],
)
async def test_streaming_ingress_missing_or_false_length_stops_at_limit_plus_one(
    headers: list[tuple[bytes, bytes]],
) -> None:
    request, consumed = _request_with_chunks(
        [b"{" + b"x" * (trust_api.MAX_QUERY_BODY_BYTES - 1), b"x"],
        headers=headers,
    )
    with pytest.raises(trust_api.TrustRequestBoundaryException) as exc_info:
        await trust_api.validate_trust_query_request(request)
    assert exc_info.value.status_code == 413
    assert sum(consumed) == trust_api.MAX_QUERY_BODY_BYTES + 1
    assert (
        request.state.p10_ingress_bytes_consumed == trust_api.MAX_QUERY_BODY_BYTES + 1
    )


@pytest.mark.asyncio
async def test_streaming_ingress_rejects_compression_before_consumption() -> None:
    request, consumed = _request_with_chunks(
        [b"compressed"], headers=[(b"content-encoding", b"gzip")]
    )
    with pytest.raises(trust_api.TrustRequestBoundaryException) as exc_info:
        await trust_api.validate_trust_query_request(request)
    assert exc_info.value.status_code == 415
    assert exc_info.value.reason_code == "unsupported_content_encoding"
    assert consumed == []


@pytest.mark.asyncio
async def test_verify_streaming_ingress_exact_limit_and_limit_plus_one() -> None:
    exact_payload = b"{}" + b" " * (trust_api.MAX_VERIFY_BODY_BYTES - 2)
    exact, consumed = _request_with_chunks([exact_payload])
    parsed = await trust_api.validate_trust_verify_request(exact)
    assert parsed.root == {}
    assert sum(consumed) == trust_api.MAX_VERIFY_BODY_BYTES
    assert exact.state.p10_ingress_bytes_consumed == trust_api.MAX_VERIFY_BODY_BYTES

    oversized, consumed = _request_with_chunks(
        [b"{" + b"x" * (trust_api.MAX_VERIFY_BODY_BYTES - 1), b"x"]
    )
    with pytest.raises(trust_api.TrustRequestBoundaryException) as exc_info:
        await trust_api.validate_trust_verify_request(oversized)
    assert exc_info.value.status_code == 413
    assert sum(consumed) == trust_api.MAX_VERIFY_BODY_BYTES + 1
    assert (
        oversized.state.p10_ingress_bytes_consumed
        == trust_api.MAX_VERIFY_BODY_BYTES + 1
    )


def _tenant_failure() -> TenantContextMissingException:
    return TenantContextMissingException(
        tenant_id=uuid4(),
        agent_client_id=uuid4(),
        correlation_identity=str(uuid4()),
        route_template="/api/trust/v1/envelopes/query",
        method="POST",
    )


@pytest.mark.asyncio
async def test_tenant_failure_connection_acquisition_has_250ms_deadline() -> None:
    class SlowSession:
        async def connection(self):
            await asyncio.sleep(5)

    class Context:
        async def __aenter__(self):
            return SlowSession()

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    started = time.perf_counter()
    with pytest.raises(asyncio.TimeoutError):
        await record_tenant_context_failure_durable(
            _tenant_failure(), audit_session_factory=Context
        )
    elapsed = time.perf_counter() - started
    assert elapsed <= TENANT_AUDIT_ACQUIRE_TIMEOUT_SECONDS + 0.150


@pytest.mark.asyncio
async def test_tenant_failure_audit_operation_has_750ms_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Session:
        async def connection(self):
            return self

        async def execute(self, *args, **kwargs):
            return None

        async def commit(self):
            return None

    class Context:
        async def __aenter__(self):
            return Session()

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    async def stalled_audit(*args, **kwargs):
        await asyncio.sleep(5)

    monkeypatch.setattr(
        "app.trust.tenant_security.record_trust_audit_event", stalled_audit
    )
    started = time.perf_counter()
    with pytest.raises(asyncio.TimeoutError):
        await record_tenant_context_failure_durable(
            _tenant_failure(), audit_session_factory=Context
        )
    elapsed = time.perf_counter() - started
    assert elapsed <= TENANT_AUDIT_OPERATION_TIMEOUT_SECONDS + 0.150


@pytest.mark.asyncio
async def test_tenant_failure_handler_saturates_to_emergency_within_total_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def stalled_writer(*args, **kwargs):
        await asyncio.sleep(5)

    monkeypatch.setattr(
        "app.trust.tenant_security.record_tenant_context_failure_durable",
        stalled_writer,
    )
    request = SimpleNamespace(state=SimpleNamespace())
    before = len(TENANT_EMERGENCY_SIGNALS)
    started = time.perf_counter()
    response = await tenant_context_missing_exception_handler(
        request, _tenant_failure()
    )
    elapsed = time.perf_counter() - started
    assert elapsed <= TENANT_HANDLER_TIMEOUT_SECONDS + 0.100
    assert response.status_code == 503
    assert json.loads(response.body) == {
        "status": "unavailable",
        "reason_code": TENANT_CONTEXT_EXTERNAL_REASON,
    }
    assert request.state.tenant_context_audit_outcome == "emergency_only"
    assert len(TENANT_EMERGENCY_SIGNALS) == before + 1
    assert TENANT_EMERGENCY_SIGNALS[-1]["audit_outcome"] == "emergency_only"


@pytest.mark.asyncio
async def test_tenant_failure_outcome_is_truthful_and_emergency_sink_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def committed_writer(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.trust.tenant_security.record_tenant_context_failure_durable",
        committed_writer,
    )
    durable_request = SimpleNamespace(state=SimpleNamespace())
    durable = await tenant_context_missing_exception_handler(
        durable_request, _tenant_failure()
    )
    assert durable.status_code == 503
    assert durable_request.state.tenant_context_audit_outcome == "durable_committed"

    async def broken_writer(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    async def stalled_log(*args, **kwargs):
        await asyncio.sleep(5)

    monkeypatch.setattr(
        "app.trust.tenant_security.record_tenant_context_failure_durable",
        broken_writer,
    )
    monkeypatch.setattr("app.trust.tenant_security.asyncio.to_thread", stalled_log)
    emergency_request = SimpleNamespace(state=SimpleNamespace())
    started = time.perf_counter()
    emergency = await tenant_context_missing_exception_handler(
        emergency_request, _tenant_failure()
    )
    elapsed = time.perf_counter() - started
    assert emergency.status_code == 503
    assert elapsed <= 0.400
    assert emergency_request.state.tenant_context_audit_outcome == "emergency_only"
    assert len(TENANT_EMERGENCY_SIGNALS) <= TENANT_EMERGENCY_SIGNALS.maxlen
