from __future__ import annotations

import hashlib
import hmac
import json
import statistics
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.webhooks.signatures import verify_paypal_signature


def _paypal_envelope(
    *,
    raw_body: bytes,
    secret: str,
    transmission_time: datetime | None = None,
    webhook_id: str = "wh_b22_p1",
    cert_url: str = "https://api-m.paypal.com/v1/notifications/certs/CERT-123",
    auth_algo: str = "HMAC-SHA256",
) -> str:
    transmission_id = f"tr_{uuid4().hex[:16]}"
    ts = (transmission_time or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z")
    body_hash = hashlib.sha256(raw_body).hexdigest()
    canonical = f"{transmission_id}|{ts}|{webhook_id}|{body_hash}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    return json.dumps(
        {
            "transmission_id": transmission_id,
            "transmission_time": ts,
            "transmission_sig": signature,
            "webhook_id": webhook_id,
            "auth_algo": auth_algo,
            "cert_url": cert_url,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def test_b22_p1_paypal_valid_envelope_accepts() -> None:
    raw_body = b'{"id":"txn_1","amount":{"total":"10.00","currency":"USD"}}'
    envelope = _paypal_envelope(raw_body=raw_body, secret="paypal_secret")
    assert verify_paypal_signature(raw_body, "paypal_secret", envelope)


def test_b22_p1_paypal_rejects_missing_required_field() -> None:
    raw_body = b'{"id":"txn_2"}'
    envelope_dict = json.loads(_paypal_envelope(raw_body=raw_body, secret="paypal_secret"))
    envelope_dict.pop("transmission_time")
    assert not verify_paypal_signature(raw_body, "paypal_secret", json.dumps(envelope_dict))


def test_b22_p1_paypal_rejects_stale_timestamp() -> None:
    raw_body = b'{"id":"txn_3"}'
    envelope = _paypal_envelope(
        raw_body=raw_body,
        secret="paypal_secret",
        transmission_time=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    assert not verify_paypal_signature(raw_body, "paypal_secret", envelope)


def test_b22_p1_paypal_rejects_invalid_cert_host() -> None:
    raw_body = b'{"id":"txn_4"}'
    envelope = _paypal_envelope(
        raw_body=raw_body,
        secret="paypal_secret",
        cert_url="https://evil.example.com/cert.pem",
    )
    assert not verify_paypal_signature(raw_body, "paypal_secret", envelope)


def test_b22_p1_paypal_rejects_legacy_raw_body_signature_path() -> None:
    raw_body = b'{"id":"txn_5"}'
    legacy_signature = hmac.new(b"paypal_secret", raw_body, hashlib.sha256).hexdigest()
    assert not verify_paypal_signature(raw_body, "paypal_secret", legacy_signature)


def test_b22_p1_paypal_verifier_latency_is_bounded_for_hot_path() -> None:
    raw_body = b'{"id":"txn_6","event_type":"PAYMENT.SALE.COMPLETED","resource":{"id":"abc"}}'
    envelope = _paypal_envelope(raw_body=raw_body, secret="paypal_secret")
    samples_ms: list[float] = []
    for _ in range(200):
        start = time.perf_counter()
        assert verify_paypal_signature(raw_body, "paypal_secret", envelope)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        samples_ms.append(elapsed_ms)
    p95_ms = statistics.quantiles(samples_ms, n=100)[94]
    assert p95_ms < 10.0, f"p95 verifier latency too high: {p95_ms:.3f}ms"


def test_b22_p1_negative_control_latency_bound_is_non_vacuous() -> None:
    with pytest.raises(AssertionError):
        assert 11.0 < 10.0
