"""
Vendor-specific signature verification helpers for webhook endpoints.
"""
import base64
import hashlib
import hmac
import time
from typing import Optional


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
    signed_payload = f"{timestamp}.{raw_body.decode()}".encode()
    computed = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


def verify_paypal_signature(raw_body: bytes, secret: Optional[str], header: Optional[str]) -> bool:
    """
    Simplified HMAC-based verification using PayPal-Transmission-Sig.
    """
    if not secret or not header:
        return False
    computed = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, header)
