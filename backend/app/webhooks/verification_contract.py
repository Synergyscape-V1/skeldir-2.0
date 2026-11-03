"""Provider verification surface shared by API and auth root.

This module deliberately contains no Celery, database, or webhook endpoint
imports. The auth root needs the verifier mapping and auth-method label without
acquiring the API's task-publishing authority.
"""

from __future__ import annotations

from collections.abc import Callable
from types import MappingProxyType
from typing import Optional

from app.webhooks.signatures import (
    verify_paypal_signature,
    verify_shopify_signature,
    verify_stripe_signature,
    verify_woocommerce_signature,
)

WebhookVerifier = Callable[[bytes, Optional[str], Optional[str]], bool]

WEBHOOK_VERIFIERS: dict[str, tuple[str, WebhookVerifier]] = {
    "shopify": ("shopify_webhook_secret", verify_shopify_signature),
    "stripe": ("stripe_webhook_secret", verify_stripe_signature),
    "paypal": ("paypal_webhook_secret", verify_paypal_signature),
    "woocommerce": ("woocommerce_webhook_secret", verify_woocommerce_signature),
}

_PROVIDER_AUTH_METHOD = MappingProxyType(
    {
        "shopify": "hmac-sha256-base64",
        "stripe": "hmac-sha256-timestamped-hex",
        "paypal": "rsa-sha256-transmission",
        "woocommerce": "hmac-sha256-base64",
    }
)


def provider_auth_method(provider: str) -> str:
    return _PROVIDER_AUTH_METHOD.get(provider.strip().lower(), "unknown")
