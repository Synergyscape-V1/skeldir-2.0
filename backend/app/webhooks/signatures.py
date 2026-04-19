"""
Vendor-specific signature verification helpers for webhook endpoints.
"""
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse


PAYPAL_AUTH_TOLERANCE_SECONDS = 300
PAYPAL_ALLOWED_CERT_HOST_SUFFIXES = ("paypal.com", "paypalobjects.com")


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
    Provider-appropriate local PayPal verification.

    The header argument is a JSON-encoded envelope containing:
    - transmission_id
    - transmission_time
    - transmission_sig
    - webhook_id
    - auth_algo
    - cert_url

    Signature law:
    HMAC-SHA256(secret, "{transmission_id}|{transmission_time}|{webhook_id}|{sha256(raw_body)}")
    """
    if not secret or not header:
        return False
    try:
        envelope = json.loads(header)
    except (TypeError, json.JSONDecodeError):
        return False
    if not isinstance(envelope, dict):
        return False

    required_fields = (
        "transmission_id",
        "transmission_time",
        "transmission_sig",
        "webhook_id",
        "auth_algo",
        "cert_url",
    )
    normalized: dict[str, str] = {}
    for field in required_fields:
        raw_value = envelope.get(field)
        token = str(raw_value).strip() if raw_value is not None else ""
        if not token:
            return False
        normalized[field] = token

    parsed_time: datetime
    try:
        parsed_time = datetime.fromisoformat(
            normalized["transmission_time"].replace("Z", "+00:00")
        )
    except ValueError:
        return False
    if parsed_time.tzinfo is None:
        return False
    transmission_ts = int(parsed_time.astimezone(timezone.utc).timestamp())
    if abs(int(time.time()) - transmission_ts) > PAYPAL_AUTH_TOLERANCE_SECONDS:
        return False

    auth_algo = normalized["auth_algo"].upper()
    if auth_algo not in {"HMAC-SHA256", "SHA256", "SHA-256"}:
        return False

    parsed_cert_url = urlparse(normalized["cert_url"])
    cert_host = parsed_cert_url.hostname or ""
    if parsed_cert_url.scheme.lower() != "https":
        return False
    if not cert_host:
        return False
    lowered_host = cert_host.lower()
    if not any(
        lowered_host == suffix or lowered_host.endswith(f".{suffix}")
        for suffix in PAYPAL_ALLOWED_CERT_HOST_SUFFIXES
    ):
        return False

    provided_signature = normalized["transmission_sig"]
    if provided_signature.lower().startswith("sha256="):
        provided_signature = provided_signature.split("=", 1)[1]
    provided_signature = provided_signature.lower()

    body_hash = hashlib.sha256(raw_body).hexdigest()
    canonical_message = (
        f"{normalized['transmission_id']}|"
        f"{normalized['transmission_time']}|"
        f"{normalized['webhook_id']}|"
        f"{body_hash}"
    ).encode("utf-8")
    computed_signature = hmac.new(
        secret.encode("utf-8"),
        canonical_message,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed_signature, provided_signature)
