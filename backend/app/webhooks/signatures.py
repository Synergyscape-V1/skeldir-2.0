"""
Vendor-specific signature verification helpers for webhook endpoints.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import socket
import time
import zlib
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Optional
from urllib.parse import urlparse

import httpx
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa


PAYPAL_AUTH_TOLERANCE_SECONDS = 300
PAYPAL_ALLOWED_CERT_HOST_SUFFIXES = ("paypal.com", "paypalobjects.com")
PAYPAL_ALLOWED_AUTH_ALGOS = {"SHA256WITHRSA"}
PAYPAL_CERT_FETCH_CONNECT_TIMEOUT_SECONDS = 0.35
PAYPAL_CERT_FETCH_READ_TIMEOUT_SECONDS = 0.35
PAYPAL_CERT_MAX_BYTES = 128 * 1024
PAYPAL_CERT_CACHE_MAX_ENTRIES = 256
PAYPAL_CERT_CACHE_TTL_SECONDS = 6 * 60 * 60
PAYPAL_CERT_EXPIRY_SAFETY_SECONDS = 60


@dataclass
class _PayPalCertCacheEntry:
    public_key: rsa.RSAPublicKey
    expires_at_monotonic: float


_PAYPAL_CERT_CACHE: "OrderedDict[str, _PayPalCertCacheEntry]" = OrderedDict()
_PAYPAL_CERT_CACHE_LOCK = Lock()
_PAYPAL_CERT_HTTP_CLIENT: httpx.Client | None = None
_PAYPAL_CERT_HTTP_CLIENT_LOCK = Lock()


def verify_shopify_signature(raw_body: bytes, secret: Optional[str], header: Optional[str]) -> bool:
    if not secret or not header:
        return False
    computed = hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()
    try:
        provided = base64.b64decode(header)
    except Exception:
        return False
    return hmac.compare_digest(computed, provided)


def verify_woocommerce_signature(raw_body: bytes, secret: Optional[str], header: Optional[str]) -> bool:
    if not secret or not header:
        return False
    computed = hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()
    provided = None
    try:
        provided = base64.b64decode(header)
    except Exception:
        return False
    return hmac.compare_digest(computed, provided)


def verify_stripe_signature(raw_body: bytes, secret: Optional[str], header: Optional[str], tolerance: int = 300) -> bool:
    """
    Minimal Stripe-style signature verification.

    Header format: "t=<timestamp>,v1=<signature>"
    """
    if not secret or not header:
        return False
    parts = dict(item.split("=", 1) for item in header.split(",") if "=" in item)
    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        return False
    try:
        ts_int = int(timestamp)
    except ValueError:
        return False
    if abs(int(time.time()) - ts_int) > tolerance:
        return False
    try:
        body_text = raw_body.decode("utf-8")
    except UnicodeDecodeError:
        return False
    signed_payload = f"{timestamp}.{body_text}".encode()
    computed = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


def verify_paypal_signature(raw_body: bytes, secret: Optional[str], header: Optional[str]) -> bool:
    """
    Provider-correct local PayPal verification.

    The header argument is a JSON-encoded envelope containing:
    - transmission_id
    - transmission_time
    - transmission_sig
    - auth_algo
    - cert_url
    - optional webhook_id (consistency assertion only)

    Signature law:
    RSA-SHA256 verify over:
    "{transmission_id}|{transmission_time}|{tenant_authoritative_webhook_id}|{crc32(raw_body_decimal)}"
    """
    if not secret or not header:
        return False
    expected_webhook_id = str(secret).strip()
    if not expected_webhook_id:
        return False

    envelope = _parse_paypal_envelope(header)
    if envelope is None:
        return False

    transmission_time = envelope["transmission_time"]
    transmission_timestamp = _parse_paypal_transmission_timestamp(transmission_time)
    if transmission_timestamp is None:
        return False
    if abs(int(time.time()) - transmission_timestamp) > PAYPAL_AUTH_TOLERANCE_SECONDS:
        return False

    if _normalize_paypal_auth_algo(envelope["auth_algo"]) not in PAYPAL_ALLOWED_AUTH_ALGOS:
        return False

    cert_url = envelope["cert_url"]
    cert_host, dns_tokens = _validate_paypal_cert_url(cert_url)
    if cert_host is None:
        return False

    envelope_webhook_id = envelope.get("webhook_id")
    if envelope_webhook_id is not None and envelope_webhook_id != expected_webhook_id:
        return False

    try:
        signature = base64.b64decode(envelope["transmission_sig"], validate=True)
    except (ValueError, TypeError):
        return False
    if not signature:
        return False

    public_key = _resolve_paypal_public_key(cert_url, cert_host, dns_tokens)
    if public_key is None:
        return False

    crc32_value = zlib.crc32(raw_body) & 0xFFFFFFFF
    canonical_message = (
        f"{envelope['transmission_id']}|"
        f"{transmission_time}|"
        f"{expected_webhook_id}|"
        f"{crc32_value}"
    ).encode("utf-8")

    try:
        public_key.verify(
            signature,
            canonical_message,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature:
        return False
    except Exception:
        return False
    return True


def _parse_paypal_envelope(header: str) -> dict[str, str] | None:
    try:
        payload = json.loads(header)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    required_fields = (
        "transmission_id",
        "transmission_time",
        "transmission_sig",
        "auth_algo",
        "cert_url",
    )
    normalized: dict[str, str] = {}
    for field in required_fields:
        value = payload.get(field)
        token = str(value).strip() if value is not None else ""
        if not token:
            return None
        normalized[field] = token

    optional_webhook_id = payload.get("webhook_id")
    if optional_webhook_id is not None:
        token = str(optional_webhook_id).strip()
        if token:
            normalized["webhook_id"] = token
    return normalized


def _parse_paypal_transmission_timestamp(token: str) -> int | None:
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return int(parsed.astimezone(timezone.utc).timestamp())


def _normalize_paypal_auth_algo(raw: str) -> str:
    return "".join(ch for ch in raw.upper() if ch.isalnum())


def _validate_paypal_cert_url(cert_url: str) -> tuple[str | None, set[str]]:
    parsed = urlparse(cert_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https":
        return None, set()
    if not host:
        return None, set()
    if parsed.username is not None or parsed.password is not None:
        return None, set()
    if parsed.fragment:
        return None, set()
    if parsed.query:
        return None, set()
    if parsed.port not in (None, 443):
        return None, set()
    if not any(host == suffix or host.endswith(f".{suffix}") for suffix in PAYPAL_ALLOWED_CERT_HOST_SUFFIXES):
        return None, set()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return None, set()

    dns_tokens = _resolve_public_ip_tokens(host)
    if not dns_tokens:
        return None, set()
    return host, dns_tokens


def _resolve_public_ip_tokens(host: str) -> set[str]:
    tokens: set[str] = set()
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return set()
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip_token = str(sockaddr[0]).strip()
        if not ip_token:
            continue
        try:
            parsed_ip = ipaddress.ip_address(ip_token)
        except ValueError:
            return set()
        if not parsed_ip.is_global:
            return set()
        tokens.add(ip_token)
    return tokens


def _get_paypal_cert_http_client() -> httpx.Client:
    global _PAYPAL_CERT_HTTP_CLIENT
    with _PAYPAL_CERT_HTTP_CLIENT_LOCK:
        if _PAYPAL_CERT_HTTP_CLIENT is None:
            _PAYPAL_CERT_HTTP_CLIENT = httpx.Client(
                timeout=httpx.Timeout(
                    connect=PAYPAL_CERT_FETCH_CONNECT_TIMEOUT_SECONDS,
                    read=PAYPAL_CERT_FETCH_READ_TIMEOUT_SECONDS,
                    write=PAYPAL_CERT_FETCH_READ_TIMEOUT_SECONDS,
                    pool=PAYPAL_CERT_FETCH_CONNECT_TIMEOUT_SECONDS,
                ),
                follow_redirects=False,
                trust_env=False,
            )
        return _PAYPAL_CERT_HTTP_CLIENT


def _fetch_paypal_certificate_pem(cert_url: str, cert_host: str) -> bytes | None:
    try:
        response = _get_paypal_cert_http_client().get(cert_url, follow_redirects=False)
    except Exception:
        return None
    if response.status_code != 200:
        return None
    if response.url.scheme.lower() != "https":
        return None
    if (response.url.host or "").lower() != cert_host:
        return None
    if response.headers.get("location"):
        return None
    content = response.content
    if not content or len(content) > PAYPAL_CERT_MAX_BYTES:
        return None
    return content


def _resolve_paypal_public_key(
    cert_url: str,
    cert_host: str,
    dns_tokens_before_fetch: set[str],
) -> rsa.RSAPublicKey | None:
    cached = _get_cached_paypal_public_key(cert_url)
    if cached is not None:
        return cached

    certificate_bytes = _fetch_paypal_certificate_pem(cert_url, cert_host)
    if certificate_bytes is None:
        return None

    dns_tokens_after_fetch = _resolve_public_ip_tokens(cert_host)
    if not dns_tokens_after_fetch:
        return None
    if dns_tokens_before_fetch.isdisjoint(dns_tokens_after_fetch):
        return None

    loaded = _load_paypal_rsa_public_key(certificate_bytes)
    if loaded is None:
        return None
    public_key, ttl_seconds = loaded
    _store_cached_paypal_public_key(cert_url, public_key, ttl_seconds)
    return public_key


def _load_paypal_rsa_public_key(cert_bytes: bytes) -> tuple[rsa.RSAPublicKey, int] | None:
    certificate = _parse_x509_certificate(cert_bytes)
    if certificate is None:
        return None

    not_before = _coerce_x509_dt_utc(certificate, attr="not_valid_before")
    not_after = _coerce_x509_dt_utc(certificate, attr="not_valid_after")
    if not_before is None or not_after is None:
        return None

    now_utc = datetime.now(timezone.utc)
    if now_utc < not_before or now_utc >= not_after:
        return None

    public_key = certificate.public_key()
    if not isinstance(public_key, rsa.RSAPublicKey):
        return None

    remaining_seconds = max(1, int((not_after - now_utc).total_seconds()) - PAYPAL_CERT_EXPIRY_SAFETY_SECONDS)
    ttl_seconds = min(PAYPAL_CERT_CACHE_TTL_SECONDS, remaining_seconds)
    return public_key, ttl_seconds


def _parse_x509_certificate(cert_bytes: bytes) -> x509.Certificate | None:
    try:
        return x509.load_pem_x509_certificate(cert_bytes)
    except ValueError:
        pass
    try:
        return x509.load_der_x509_certificate(cert_bytes)
    except ValueError:
        return None


def _coerce_x509_dt_utc(certificate: x509.Certificate, *, attr: str) -> datetime | None:
    utc_attr = f"{attr}_utc"
    dt = getattr(certificate, utc_attr, None)
    if isinstance(dt, datetime):
        return dt
    fallback = getattr(certificate, attr, None)
    if not isinstance(fallback, datetime):
        return None
    if fallback.tzinfo is None:
        return fallback.replace(tzinfo=timezone.utc)
    return fallback.astimezone(timezone.utc)


def _get_cached_paypal_public_key(cert_url: str) -> rsa.RSAPublicKey | None:
    now = time.monotonic()
    with _PAYPAL_CERT_CACHE_LOCK:
        entry = _PAYPAL_CERT_CACHE.get(cert_url)
        if entry is None:
            return None
        if entry.expires_at_monotonic <= now:
            _PAYPAL_CERT_CACHE.pop(cert_url, None)
            return None
        _PAYPAL_CERT_CACHE.move_to_end(cert_url)
        return entry.public_key


def _store_cached_paypal_public_key(cert_url: str, public_key: rsa.RSAPublicKey, ttl_seconds: int) -> None:
    expires = time.monotonic() + float(max(1, ttl_seconds))
    with _PAYPAL_CERT_CACHE_LOCK:
        _PAYPAL_CERT_CACHE[cert_url] = _PayPalCertCacheEntry(
            public_key=public_key,
            expires_at_monotonic=expires,
        )
        _PAYPAL_CERT_CACHE.move_to_end(cert_url)
        while len(_PAYPAL_CERT_CACHE) > PAYPAL_CERT_CACHE_MAX_ENTRIES:
            _PAYPAL_CERT_CACHE.popitem(last=False)


def reset_paypal_certificate_cache_for_testing() -> None:
    with _PAYPAL_CERT_CACHE_LOCK:
        _PAYPAL_CERT_CACHE.clear()
