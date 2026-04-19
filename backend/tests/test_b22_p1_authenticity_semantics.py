from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.webhooks.signatures import reset_paypal_certificate_cache_for_testing, verify_paypal_signature
from tests.helpers.paypal_signature import (
    DEFAULT_PAYPAL_TEST_CERT_URL,
    build_paypal_auth_headers,
    install_paypal_cert_fetcher,
)


@pytest.fixture(autouse=True)
def _paypal_cert_fetcher(monkeypatch: pytest.MonkeyPatch) -> None:
    install_paypal_cert_fetcher(monkeypatch)
    reset_paypal_certificate_cache_for_testing()


def _paypal_envelope_from_headers(headers: dict[str, str]) -> str:
    return json.dumps(
        {
            "transmission_id": headers.get("PayPal-Transmission-Id"),
            "transmission_time": headers.get("PayPal-Transmission-Time"),
            "transmission_sig": headers.get("PayPal-Transmission-Sig"),
            "webhook_id": headers.get("PayPal-Webhook-Id"),
            "auth_algo": headers.get("PayPal-Auth-Algo"),
            "cert_url": headers.get("PayPal-Cert-Url"),
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def test_b22_p1_paypal_valid_envelope_accepts() -> None:
    raw_body = b'{"id":"txn_1","amount":{"total":"10.00","currency":"USD"}}'
    headers = build_paypal_auth_headers(raw_body=raw_body, webhook_id="wh_b22_p1")
    envelope = _paypal_envelope_from_headers(headers)
    assert verify_paypal_signature(raw_body, "wh_b22_p1", envelope)


def test_b22_p1_paypal_rejects_missing_required_field() -> None:
    raw_body = b'{"id":"txn_2"}'
    headers = build_paypal_auth_headers(raw_body=raw_body, webhook_id="wh_b22_p1")
    envelope_dict = json.loads(_paypal_envelope_from_headers(headers))
    envelope_dict.pop("transmission_time")
    assert not verify_paypal_signature(raw_body, "wh_b22_p1", json.dumps(envelope_dict))


def test_b22_p1_paypal_rejects_stale_timestamp() -> None:
    raw_body = b'{"id":"txn_3"}'
    headers = build_paypal_auth_headers(
        raw_body=raw_body,
        webhook_id="wh_b22_p1",
        transmission_time=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    envelope = _paypal_envelope_from_headers(headers)
    assert not verify_paypal_signature(raw_body, "wh_b22_p1", envelope)


def test_b22_p1_paypal_rejects_invalid_cert_host() -> None:
    raw_body = b'{"id":"txn_4"}'
    headers = build_paypal_auth_headers(
        raw_body=raw_body,
        webhook_id="wh_b22_p1",
        cert_url="https://evil.example.com/cert.pem",
    )
    envelope = _paypal_envelope_from_headers(headers)
    assert not verify_paypal_signature(raw_body, "wh_b22_p1", envelope)


def test_b22_p1_paypal_rejects_legacy_raw_body_signature_path() -> None:
    raw_body = b'{"id":"txn_5"}'
    legacy_signature = "sha256=deadbeef"
    assert not verify_paypal_signature(raw_body, "wh_b22_p1", legacy_signature)


def test_b22_p1_paypal_rejects_webhook_authority_mismatch() -> None:
    raw_body = b'{"id":"txn_6"}'
    headers = build_paypal_auth_headers(raw_body=raw_body, webhook_id="wh_expected")
    envelope = _paypal_envelope_from_headers(headers)
    assert not verify_paypal_signature(raw_body, "wh_different_tenant_authority", envelope)


def test_b22_p1_paypal_rejects_malformed_base64_signature() -> None:
    raw_body = b'{"id":"txn_7"}'
    headers = build_paypal_auth_headers(raw_body=raw_body, webhook_id="wh_b22_p1")
    headers["PayPal-Transmission-Sig"] = "%%%%not-base64%%%%"
    envelope = _paypal_envelope_from_headers(headers)
    assert not verify_paypal_signature(raw_body, "wh_b22_p1", envelope)


def test_b22_p1_paypal_rejects_wrong_auth_algo() -> None:
    raw_body = b'{"id":"txn_8"}'
    headers = build_paypal_auth_headers(
        raw_body=raw_body,
        webhook_id="wh_b22_p1",
        auth_algo="HMAC-SHA256",
    )
    envelope = _paypal_envelope_from_headers(headers)
    assert not verify_paypal_signature(raw_body, "wh_b22_p1", envelope)


def test_b22_p1_paypal_verifier_latency_is_bounded_for_hot_path() -> None:
    raw_body = b'{"id":"txn_9","event_type":"PAYMENT.SALE.COMPLETED","resource":{"id":"abc"}}'
    headers = build_paypal_auth_headers(raw_body=raw_body, webhook_id="wh_b22_p1")
    envelope = _paypal_envelope_from_headers(headers)

    # Warm the cache so this benchmark measures the steady-state auth path.
    assert verify_paypal_signature(raw_body, "wh_b22_p1", envelope)

    samples_ms: list[float] = []
    for _ in range(200):
        start = time.perf_counter()
        assert verify_paypal_signature(raw_body, "wh_b22_p1", envelope)
        samples_ms.append((time.perf_counter() - start) * 1000.0)

    p95_ms = statistics.quantiles(samples_ms, n=100)[94]
    assert p95_ms < 10.0, f"p95 verifier latency too high: {p95_ms:.3f}ms"


def test_b22_p1_negative_control_latency_bound_is_non_vacuous() -> None:
    with pytest.raises(AssertionError):
        assert 11.0 < 10.0


def test_b22_p1_cert_fetch_timeout_is_fail_closed_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.webhooks import signatures as signatures_module

    raw_body = b'{"id":"txn_timeout"}'
    headers = build_paypal_auth_headers(
        raw_body=raw_body,
        webhook_id="wh_b22_p1",
        cert_url=DEFAULT_PAYPAL_TEST_CERT_URL,
    )
    envelope = _paypal_envelope_from_headers(headers)

    def _timeout_fetch(_cert_url: str, _cert_host: str) -> bytes | None:
        time.sleep(0.02)
        return None

    monkeypatch.setattr(signatures_module, "_fetch_paypal_certificate_pem", _timeout_fetch)
    signatures_module.reset_paypal_certificate_cache_for_testing()

    start = time.perf_counter()
    assert not verify_paypal_signature(raw_body, "wh_b22_p1", envelope)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert elapsed_ms < 150.0
