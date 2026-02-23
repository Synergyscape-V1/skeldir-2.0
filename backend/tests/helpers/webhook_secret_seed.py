from __future__ import annotations

from typing import Mapping

from sqlalchemy import text

from app.core.secrets import get_platform_encryption_material_for_write

PROVIDERS = ("shopify", "stripe", "paypal", "woocommerce")


def _provider_secret_columns() -> str:
    cols: list[str] = []
    for provider in PROVIDERS:
        cols.append(f"{provider}_webhook_secret_ciphertext")
        cols.append(f"{provider}_webhook_secret_key_id")
    return ", ".join(cols)


def _provider_secret_values_sql(*, secret_param_prefix: str = "") -> str:
    values: list[str] = []
    for provider in PROVIDERS:
        secret_name = f"{secret_param_prefix}{provider}_secret"
        values.append(f"pgp_sym_encrypt(:{secret_name}, :webhook_secret_key)")
        values.append(":webhook_secret_key_id")
    return ", ".join(values)


def webhook_secret_insert_columns() -> str:
    return _provider_secret_columns()


def webhook_secret_insert_values_sql() -> str:
    return _provider_secret_values_sql()


def webhook_secret_insert_params(
    *,
    shopify_secret: str,
    stripe_secret: str,
    paypal_secret: str,
    woocommerce_secret: str,
) -> dict[str, str]:
    key_id, key = get_platform_encryption_material_for_write()
    return {
        "shopify_secret": shopify_secret,
        "stripe_secret": stripe_secret,
        "paypal_secret": paypal_secret,
        "woocommerce_secret": woocommerce_secret,
        "webhook_secret_key_id": key_id,
        "webhook_secret_key": key,
    }


def enrich_params_with_webhook_secrets(
    params: Mapping[str, object],
    *,
    shopify_secret: str,
    stripe_secret: str,
    paypal_secret: str,
    woocommerce_secret: str,
) -> dict[str, object]:
    payload = dict(params)
    payload.update(
        webhook_secret_insert_params(
            shopify_secret=shopify_secret,
            stripe_secret=stripe_secret,
            paypal_secret=paypal_secret,
            woocommerce_secret=woocommerce_secret,
        )
    )
    return payload


def tenant_insert_with_webhook_secret_sql(base_columns: str, base_values: str) -> str:
    # RAW_SQL_ALLOWLIST: centralized test fixture helper for tenant webhook secret seeding.
    return (
        "INSERT INTO tenants ("
        f"{base_columns}, {webhook_secret_insert_columns()}"
        ") VALUES ("
        f"{base_values}, {webhook_secret_insert_values_sql()}"
        ")"
    )


def tenant_insert_statement(base_columns: str, base_values: str):
    return text(tenant_insert_with_webhook_secret_sql(base_columns, base_values))
