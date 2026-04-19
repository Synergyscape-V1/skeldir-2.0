from __future__ import annotations

import base64
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID


DEFAULT_PAYPAL_TEST_CERT_URL = "https://api-m.paypal.com/v1/notifications/certs/CERT-LOCAL-TEST"
DEFAULT_PAYPAL_AUTH_ALGO = "SHA256withRSA"


@dataclass(frozen=True)
class PayPalTestKeyMaterial:
    private_key: rsa.RSAPrivateKey
    certificate_pem: bytes


@lru_cache(maxsize=1)
def paypal_test_key_material() -> PayPalTestKeyMaterial:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PayPal Test"),
            x509.NameAttribute(NameOID.COMMON_NAME, "api-m.paypal.com"),
        ]
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("api-m.paypal.com"),
                    x509.DNSName("api.sandbox.paypal.com"),
                ]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    certificate_pem = certificate.public_bytes(encoding=Encoding.PEM)
    return PayPalTestKeyMaterial(private_key=private_key, certificate_pem=certificate_pem)


def build_paypal_auth_headers(
    *,
    raw_body: bytes,
    webhook_id: str,
    transmission_time: datetime | None = None,
    transmission_id: str | None = None,
    cert_url: str = DEFAULT_PAYPAL_TEST_CERT_URL,
    auth_algo: str = DEFAULT_PAYPAL_AUTH_ALGO,
    valid_signature: bool = True,
    include_webhook_id_header: bool = True,
) -> dict[str, str]:
    transmission_time_token = (
        transmission_time or datetime.now(timezone.utc)
    ).isoformat().replace("+00:00", "Z")
    normalized_transmission_id = transmission_id or f"tr_{uuid4().hex[:16]}"
    signature = sign_paypal_message(
        raw_body=raw_body,
        webhook_id=webhook_id,
        transmission_id=normalized_transmission_id,
        transmission_time=transmission_time_token,
    )
    if not valid_signature:
        signature = base64.b64encode(b"\x00" * 64).decode("utf-8")

    headers = {
        "PayPal-Transmission-Id": normalized_transmission_id,
        "PayPal-Transmission-Time": transmission_time_token,
        "PayPal-Transmission-Sig": signature,
        "PayPal-Auth-Algo": auth_algo,
        "PayPal-Cert-Url": cert_url,
    }
    if include_webhook_id_header:
        headers["PayPal-Webhook-Id"] = webhook_id
    return headers


def sign_paypal_message(
    *,
    raw_body: bytes,
    webhook_id: str,
    transmission_id: str,
    transmission_time: str,
) -> str:
    crc32_value = zlib.crc32(raw_body) & 0xFFFFFFFF
    message = f"{transmission_id}|{transmission_time}|{webhook_id}|{crc32_value}".encode("utf-8")
    key_material = paypal_test_key_material()
    signature = key_material.private_key.sign(
        message,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def install_paypal_cert_fetcher(monkeypatch) -> None:
    from app.webhooks import signatures as signatures_module

    key_material = paypal_test_key_material()
    signatures_module.reset_paypal_certificate_cache_for_testing()

    def _fake_fetch(cert_url: str, cert_host: str) -> bytes | None:
        if cert_url != DEFAULT_PAYPAL_TEST_CERT_URL:
            return None
        if cert_host != "api-m.paypal.com":
            return None
        return key_material.certificate_pem

    monkeypatch.setattr(signatures_module, "_fetch_paypal_certificate_pem", _fake_fetch)
